"""Tests for the L4 dense view (derivation/views/dense.py), against a real
Postgres with pgvector.

Not mocked: the view's whole job is dimension-parameterized DDL, vector
round-tripping through pgvector's wire format, and transaction discipline on
a caller's cursor — none of which a mock exercises. All tests use a
deterministic FakeEmbedder (hash-bucket vectors, no model load), so the
suite never touches sentence-transformers; the one real-model integration
test lives in tests/operators/test_ann_op.py.

The fixture DROPs view_dense rather than truncating it, on setup AND
teardown: the table's vector dimension is itself under test (created at dim
8 by one test, dim 4 by the mismatch test), and sibling test modules
truncate `records` without CASCADE, so a leftover FK-bearing view table
would break them. The view is disposable by design — dropping it is the
documented rebuild path, and L2 stays untouched.
"""

from __future__ import annotations

import hashlib
import math
import os
from datetime import datetime, timezone

import psycopg
import pytest

from datum.derivation.views.base import RecordRow
from datum.derivation.views.dense import DenseView
from datum.groundstore.store import GroundStore, record_from_row, record_select_columns
from datum.kernel.errors import DatumError
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(_DSN),
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}",
)


class FakeEmbedder:
    """Deterministic, model-free embedder: each token contributes a
    pseudo-random direction derived from its sha256 digest, summed and
    L2-normalized (continuous components so distance ties are essentially
    impossible — see tests/operators/test_ann_op.py's copy for why that
    matters). Call counters let tests assert the empty-input contract.
    """

    name = "fake-hash"
    version = "v1"

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim
        self.document_calls = 0
        self.query_calls = 0

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            while len(digest) < 4 * self.dim:
                digest += hashlib.sha256(digest).digest()
            for i in range(self.dim):
                vec[i] += int.from_bytes(digest[4 * i : 4 * i + 4], "big") / 2**32 - 0.5
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def encode_documents(self, texts):
        self.document_calls += 1
        return [self._embed(t) for t in texts]

    def encode_query(self, text):
        self.query_calls += 1
        return self._embed(text)


def _prov(namespace: str = _ACME) -> ProvenanceCapsule:
    return ProvenanceCapsule(
        writer=Principal(id="ingestor", namespace=namespace),
        ingestion_path="pdf_upload",
        authority_tier="UNVERIFIED",
        trust_class="trusted",
        source_version="docling-2.4",
    )


def _assert_op(text: str, *, source_id: str, stable_key: str, namespace: str = _ACME) -> WriteOp:
    return WriteOp.assert_(
        body=StructuredBody(text=text, section_path=(source_id, stable_key)),
        valid_from=datetime.now(timezone.utc),
        provenance=_prov(namespace),
        policy_id="default-acl",  # type: ignore[arg-type]
        source_id=source_id,
        stable_key=stable_key,
    )


def _write_records(texts: list[str], namespace: str = _ACME) -> None:
    """Through the real write path (GroundStore), so view rows key real
    records.row_id values and the FK holds.
    """
    wal = WAL(_DSN)
    store = GroundStore(_DSN, wal)
    try:
        for i, text in enumerate(texts):
            store.apply(
                _assert_op(text, source_id=f"doc-{namespace}", stable_key=f"s{i}", namespace=namespace)
            )
    finally:
        store.close()
        wal.close()


def _live_rows(conn) -> list[RecordRow]:
    rows = conn.execute(
        f"SELECT row_id, {record_select_columns('records')} FROM records "
        "WHERE tx_to IS NULL ORDER BY row_id"
    ).fetchall()
    return [RecordRow(row_id=row[0], record=record_from_row(row[1:])) for row in rows]


def _view_count(conn) -> int:
    return conn.execute("SELECT count(*) FROM view_dense").fetchone()[0]


@pytest.fixture
def conn():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS view_dense")
        c.execute("TRUNCATE TABLE records, wal_entries RESTART IDENTITY CASCADE")
        yield c
        c.execute("DROP TABLE IF EXISTS view_dense")


def test_ensure_schema_creates_table_and_indexes_and_is_idempotent(conn):
    view = DenseView(FakeEmbedder(dim=8))
    view.ensure_schema(conn)

    dim = conn.execute(
        "SELECT atttypmod FROM pg_attribute "
        "WHERE attrelid = to_regclass('view_dense') AND attname = 'embedding'"
    ).fetchone()[0]
    assert dim == 8

    index_defs = [
        row[0]
        for row in conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'view_dense'"
        ).fetchall()
    ]
    assert any("hnsw" in d and "vector_cosine_ops" in d for d in index_defs)
    assert any("btree (namespace)" in d for d in index_defs)

    view.ensure_schema(conn)  # second run must be a no-op, not an error
    assert view.producer_version == "dense-v1/fake-hash@v1"


def test_ensure_schema_refuses_a_dimension_mismatch_and_touches_nothing(conn):
    DenseView(FakeEmbedder(dim=8)).ensure_schema(conn)
    _write_records(["alpha beta"])
    rows = _live_rows(conn)
    with conn.transaction():
        DenseView(FakeEmbedder(dim=8)).derive(conn.cursor(), rows)

    with pytest.raises(DatumError) as excinfo:
        DenseView(FakeEmbedder(dim=4)).ensure_schema(conn)
    message = str(excinfo.value)
    assert "8" in message and "4" in message  # names both dims
    assert "view_dense" in message and "view_cursors" in message  # states the fix

    # never silently adapts, never drops data itself
    dim = conn.execute(
        "SELECT atttypmod FROM pg_attribute "
        "WHERE attrelid = to_regclass('view_dense') AND attname = 'embedding'"
    ).fetchone()[0]
    assert dim == 8
    assert _view_count(conn) == 1


def test_derive_and_remove_round_trip_on_the_callers_cursor(conn):
    embedder = FakeEmbedder(dim=8)
    view = DenseView(embedder)
    view.ensure_schema(conn)
    _write_records(["alpha beta", "gamma delta"])
    rows = _live_rows(conn)

    with conn.transaction():
        assert view.derive(conn.cursor(), rows) == 2
    assert embedder.document_calls == 1  # one batch, not per-row

    got = conn.execute(
        "SELECT row_id, record_id, namespace, producer_version, embedding::text "
        "FROM view_dense ORDER BY row_id"
    ).fetchall()
    assert [g[0] for g in got] == [r.row_id for r in rows]
    assert [g[1] for g in got] == [str(r.record.id) for r in rows]
    assert all(g[2] == _ACME for g in got)  # namespace from provenance.writer
    assert all(g[3] == view.producer_version for g in got)
    # the vector survives the wire format (pgvector stores float4)
    stored = [float(x) for x in got[0][4].strip("[]").split(",")]
    assert stored == pytest.approx(embedder._embed("alpha beta"), rel=1e-5)

    with conn.transaction():
        assert view.remove(conn.cursor(), [r.row_id for r in rows]) == 2
    assert _view_count(conn) == 0
    with conn.transaction():
        # idempotent: a re-run of a crashed batch deletes nothing, errors nothing
        assert view.remove(conn.cursor(), [r.row_id for r in rows]) == 0


def test_derive_never_commits_the_callers_transaction(conn):
    view = DenseView(FakeEmbedder(dim=8))
    view.ensure_schema(conn)
    _write_records(["alpha beta"])
    rows = _live_rows(conn)

    with pytest.raises(RuntimeError):
        with conn.transaction():
            assert view.derive(conn.cursor(), rows) == 1
            raise RuntimeError("force rollback")
    # the derive vanished with the caller's aborted transaction
    assert _view_count(conn) == 0


def test_derive_of_no_rows_returns_zero_without_calling_the_embedder(conn):
    embedder = FakeEmbedder(dim=8)
    view = DenseView(embedder)
    view.ensure_schema(conn)
    with conn.transaction():
        assert view.derive(conn.cursor(), []) == 0
    assert embedder.document_calls == 0
