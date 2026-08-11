"""LexicalView (L4) tests, against a real Postgres.

Not mocked: the view's whole point is server-side tokenization (ONE canonical
to_tsvector in SQL, matching what websearch_to_tsquery does to query text at
retrieval time — lexical.py's module docstring), so a mock would test nothing
that matters. Follows the established DB-test pattern (tests/storage/
test_wal.py): module-level skipif when Postgres at DATUM_PG_DSN is
unreachable, per-test migrate + truncate.

The transaction-ownership tests are the load-bearing ones: derive/remove run
on a caller cursor and must neither commit nor roll back (base.py's contract
— the engine's WAL cursor and the view's rows advance together or not at
all). Every fixture DROPs view_lexical on teardown: sibling test modules
truncate `records` without CASCADE, and a leftover FK-bearing view table
would break them.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
import pytest

from datum.derivation.views.base import RecordRow
from datum.derivation.views.lexical import LexicalView
from datum.groundstore.store import RECORD_SELECT_COLUMNS, GroundStore, record_from_row
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


@pytest.fixture
def conn():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as c:
        # Drop first so ensure_schema is exercised from a clean slate, and so
        # a plain truncate cannot trip over the view's FK from a crashed run.
        c.execute("DROP TABLE IF EXISTS view_lexical")
        c.execute("TRUNCATE TABLE records, wal_entries RESTART IDENTITY CASCADE")
        yield c
        c.execute("DROP TABLE IF EXISTS view_lexical")


@pytest.fixture
def store(conn):
    wal = WAL(_DSN)
    gs = GroundStore(_DSN, wal)
    yield gs
    gs.close()
    wal.close()


def _live_rows(conn) -> list[RecordRow]:
    """Live records as the DerivationEngine would hand them to derive():
    surrogate row_id + the kernel Record, decoded by the store's ONE decoder.
    """
    rows = conn.execute(
        f"SELECT row_id, {RECORD_SELECT_COLUMNS} FROM records "
        "WHERE tx_to IS NULL ORDER BY row_id"
    ).fetchall()
    return [RecordRow(row_id=r[0], record=record_from_row(tuple(r[1:]))) for r in rows]


def _view_count(conn) -> int:
    return conn.execute("SELECT count(*) FROM view_lexical").fetchone()[0]


def test_ensure_schema_creates_table_and_indexes_idempotently(conn):
    view = LexicalView()
    view.ensure_schema(conn)
    view.ensure_schema(conn)  # second run must be a no-op, not an error

    (tsv_type,) = conn.execute(
        "SELECT udt_name FROM information_schema.columns "
        "WHERE table_name = 'view_lexical' AND column_name = 'tsv'"
    ).fetchone()
    assert tsv_type == "tsvector"

    index_defs = [
        d for (d,) in conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'view_lexical'"
        ).fetchall()
    ]
    assert any("USING gin (tsv)" in d for d in index_defs), index_defs
    assert any("USING btree (namespace)" in d for d in index_defs), index_defs
    assert any("pkey" in d and "(row_id)" in d for d in index_defs), index_defs

    # The FK to records(row_id) cascades on delete, so a hard-deleted record
    # can never leave an orphaned view row behind.
    (confdeltype,) = conn.execute(
        "SELECT confdeltype FROM pg_constraint "
        "WHERE conrelid = 'view_lexical'::regclass AND contype = 'f'"
    ).fetchone()
    assert confdeltype == "c"


def test_derive_computes_tsv_server_side_and_stamps_provenance_columns(conn, store):
    store.apply(_assert_op("The runner was running daily", source_id="docA", stable_key="s1"))
    store.apply(
        _assert_op("other-tenant text", source_id="docB", stable_key="s1", namespace="tenant:other")
    )
    view = LexicalView()
    view.ensure_schema(conn)
    rows = _live_rows(conn)

    with conn.transaction():
        assert view.derive(conn.cursor(), rows) == 2

    by_row_id = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT row_id, record_id, namespace, producer_version FROM view_lexical"
        ).fetchall()
    }
    assert set(by_row_id) == {r.row_id for r in rows}
    for row in rows:
        record_id, namespace, producer_version = by_row_id[row.row_id]
        assert record_id == str(row.record.id)
        # namespace comes from provenance.writer.namespace (decisions.md #7)
        assert namespace == row.record.provenance.writer.namespace
        assert producer_version == "lexical-v2-ctx/pg-tsvector-english"

    # Server-side tokenization: 'running' was stemmed to the lexeme 'run' by
    # the SAME config query text goes through at retrieval time.
    (stemmed,) = conn.execute(
        "SELECT tsv @@ to_tsquery('english', 'run') FROM view_lexical "
        "WHERE namespace = %s",
        (_ACME,),
    ).fetchone()
    assert stemmed is True


def test_derive_runs_in_the_callers_transaction_and_never_commits(conn, store):
    store.apply(_assert_op("some text", source_id="docA", stable_key="s1"))
    view = LexicalView()
    view.ensure_schema(conn)
    rows = _live_rows(conn)

    class Boom(Exception):
        pass

    # Rolled-back path: derive's writes must vanish with the caller's abort.
    with pytest.raises(Boom):
        with conn.transaction():
            assert view.derive(conn.cursor(), rows) == 1
            raise Boom
    assert _view_count(conn) == 0

    # Committed path: same call, caller commits, rows persist.
    with conn.transaction():
        assert view.derive(conn.cursor(), rows) == 1
    assert _view_count(conn) == 1


def test_remove_is_idempotent_and_respects_the_callers_transaction(conn, store):
    store.apply(_assert_op("first", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("second", source_id="docA", stable_key="s2"))
    view = LexicalView()
    view.ensure_schema(conn)
    rows = _live_rows(conn)
    with conn.transaction():
        view.derive(conn.cursor(), rows)
    row_ids = [r.row_id for r in rows]

    class Boom(Exception):
        pass

    # A rolled-back remove deletes nothing.
    with pytest.raises(Boom):
        with conn.transaction():
            assert view.remove(conn.cursor(), row_ids) == 2
            raise Boom
    assert _view_count(conn) == 2

    # Committed remove deletes both; a re-run of the same batch is a clean 0
    # (a crashed batch may re-run — base.py's idempotency requirement).
    with conn.transaction():
        assert view.remove(conn.cursor(), row_ids) == 2
    assert _view_count(conn) == 0
    with conn.transaction():
        assert view.remove(conn.cursor(), row_ids) == 0


def test_derive_and_remove_of_empty_input_return_zero(conn):
    view = LexicalView()
    view.ensure_schema(conn)
    with conn.transaction():
        assert view.derive(conn.cursor(), []) == 0
        assert view.remove(conn.cursor(), []) == 0
    assert _view_count(conn) == 0
