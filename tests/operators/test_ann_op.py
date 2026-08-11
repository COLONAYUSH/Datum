"""ANNOperator (L5) tests.

Same two-profile split as tests/operators/test_bm25_op.py, and for the same
reason the Postgres skipif is per-test rather than module-level: the
conformance tests MUST run with no database AND no embedder — the gate runs
at register_operator() time with no live infrastructure, and an ANN operator
whose registration needed a reachable Postgres or a loaded model would be
failing that requirement silently (ExplodingEmbedder + _NOWHERE_DSN make any
such touch a loud failure, not a lucky pass). Everything else runs against a
real Postgres through the real write path, because the properties under test
— join-enforced liveness against L2, namespace exactness (decisions.md #13),
distance-to-similarity scoring — are properties of the SQL, not of Python
around it. DB tests use a deterministic FakeEmbedder (hash-bucket geometry,
no model load); the single real-model test at the bottom is the only one
that loads the configured default embedder (bge-m3).

Fixtures DROP view_dense on teardown: sibling test modules truncate
`records` without CASCADE, and a leftover FK-bearing view table would break
them.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import os
from datetime import datetime, timezone

import psycopg
import pytest

from datum.derivation.views.base import RecordRow
from datum.derivation.views.dense import DenseView, SentenceTransformersEmbedder
from datum.groundstore.store import GroundStore, record_from_row, record_select_columns
from datum.kernel.plan import Budget
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
from datum.operators.ann_op import ANNOperator
from datum.operators.common import QueryFragment
from datum.operators.conformance.suite import ConformanceSuite
from datum.operators.registry import OperatorRegistry
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"

# A DSN that cannot connect: proves construction/registration never dials out.
_NOWHERE_DSN = "postgresql://nobody@127.0.0.1:9/nowhere"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_reachable(_DSN),
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}",
)


class FakeEmbedder:
    """Deterministic, model-free embedder: each token contributes a
    pseudo-random direction derived from its sha256 digest, summed and
    L2-normalized. Documents sharing tokens with a query land measurably
    nearer — enough geometry to test ranking without loading a model. The
    components are continuous, deliberately: a bucket-COUNT embedder lets two
    disjoint token sets collide into an exact distance tie the database then
    breaks arbitrarily (a real flake this suite hit), while continuous
    components make ties essentially impossible, so rankings are strict.
    """

    name = "fake-hash"
    version = "v1"

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

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
        return [self._embed(t) for t in texts]

    def encode_query(self, text):
        return self._embed(text)


class ExplodingEmbedder:
    """Fails loudly if any encode is attempted — the conformance path and the
    empty-query path must touch neither the model nor the database.
    """

    name = "exploding"
    version = "v0"
    dim = 8

    def encode_documents(self, texts):
        raise AssertionError("encode_documents must not be called on this path")

    def encode_query(self, text):
        raise AssertionError("encode_query must not be called on this path")


# --- conformance: no database, no embedder, by requirement ------------------


def test_registration_passes_the_gate_with_no_database_and_no_embedder():
    registry = OperatorRegistry()
    registry.register(ANNOperator(_NOWHERE_DSN, ExplodingEmbedder()))  # must not raise
    assert registry.kinds() == ("ann",)
    assert registry.get("ann").kind == "ann"


def test_conformance_suite_passes_with_no_live_infrastructure():
    report = ConformanceSuite.run(ANNOperator(_NOWHERE_DSN, ExplodingEmbedder()))
    assert report.passed, report.failures
    assert len(report.results) == 4  # every mandatory case ran, none skipped


def test_plan_does_no_io_and_carries_the_fragment():
    op = ANNOperator(_NOWHERE_DSN, ExplodingEmbedder())
    fragment = QueryFragment(query="anything", namespace=_ACME, limit=7)
    op_plan = op.plan(fragment, Budget())
    assert op_plan.operator_kind == "ann"
    assert op_plan.params["fragment"] is fragment


def test_blank_query_returns_empty_without_embedding_or_connecting():
    op = ANNOperator(_NOWHERE_DSN, ExplodingEmbedder())
    op_plan = op.plan(QueryFragment(query="   \n\t", namespace=_ACME, limit=5), Budget())
    candidates = op.execute(op_plan)
    assert candidates.records == ()
    assert candidates.scores == ()
    assert candidates.score_method == "cosine"


def test_cost_model_is_a_rough_constant():
    estimate = ANNOperator(_NOWHERE_DSN, ExplodingEmbedder()).cost_model(object())
    assert estimate.tokens == 0
    assert estimate.latency_ms > 0.0


# --- real query path: real Postgres, real write path ------------------------


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
        c.execute("DROP TABLE IF EXISTS view_dense")
        c.execute("TRUNCATE TABLE records, wal_entries RESTART IDENTITY CASCADE")
        yield c
        c.execute("DROP TABLE IF EXISTS view_dense")


@pytest.fixture
def store(conn):
    wal = WAL(_DSN)
    gs = GroundStore(_DSN, wal)
    yield gs
    gs.close()
    wal.close()


def _live_rows(conn) -> list[RecordRow]:
    rows = conn.execute(
        f"SELECT row_id, {record_select_columns('records')} FROM records "
        "WHERE tx_to IS NULL ORDER BY row_id"
    ).fetchall()
    return [RecordRow(row_id=row[0], record=record_from_row(row[1:])) for row in rows]


def _derive_live(conn, view: DenseView) -> list[RecordRow]:
    rows = _live_rows(conn)
    with conn.transaction():
        view.derive(conn.cursor(), rows)
    return rows


def _search(op: ANNOperator, query: str, *, namespace: str = _ACME, limit: int = 10):
    return op.execute(op.plan(QueryFragment(query=query, namespace=namespace, limit=limit), Budget()))


@requires_pg
def test_returns_the_semantically_nearest_record_first(conn, store):
    embedder = FakeEmbedder()
    view = DenseView(embedder)
    view.ensure_schema(conn)
    for i, text in enumerate(["alpha beta gamma", "delta epsilon zeta", "eta theta iota"]):
        store.apply(_assert_op(text, source_id="doc", stable_key=f"s{i}"))
    _derive_live(conn, view)

    op = ANNOperator(_DSN, embedder)
    try:
        candidates = _search(op, "alpha beta")
    finally:
        op.close()

    assert len(candidates.records) == 3
    assert candidates.records[0].body_text() == "alpha beta gamma"
    assert candidates.score_method == "cosine"
    assert list(candidates.scores) == sorted(candidates.scores, reverse=True)
    assert candidates.scores[0] > candidates.scores[-1]  # nearest is strictly nearer


@requires_pg
def test_namespace_isolation_is_enforced_by_the_join_to_records(conn, store):
    embedder = FakeEmbedder()
    view = DenseView(embedder)
    view.ensure_schema(conn)
    store.apply(_assert_op("alpha beta gamma", source_id="doc-acme", stable_key="s0"))
    # The other tenant holds STRICTLY better matches for the query.
    for i, text in enumerate(["alpha beta", "alpha beta gamma"]):
        store.apply(
            _assert_op(text, source_id="doc-other", stable_key=f"s{i}", namespace="tenant:other")
        )
    _derive_live(conn, view)
    # every tenant's vectors ARE in the one view table...
    assert conn.execute("SELECT count(*) FROM view_dense").fetchone()[0] == 3

    op = ANNOperator(_DSN, embedder)
    try:
        candidates = _search(op, "alpha beta")
    finally:
        op.close()

    # ...but only the resolved partition's records ever come back.
    assert len(candidates.records) == 1
    assert candidates.records[0].body_text() == "alpha beta gamma"
    assert all(r.provenance.writer.namespace == _ACME for r in candidates.records)


@requires_pg
def test_liveness_superseded_records_never_return_even_from_a_stale_view_row(conn, store):
    embedder = FakeEmbedder()
    view = DenseView(embedder)
    view.ensure_schema(conn)
    old_id = store.apply(_assert_op("alpha beta original", source_id="doc", stable_key="s0"))
    old_rows = _derive_live(conn, view)

    new_id = store.apply(
        WriteOp.supersede(
            old_id=old_id,
            body=StructuredBody(text="alpha beta revised", section_path=("doc", "s0")),
            valid_from=datetime.now(timezone.utc),
            provenance=_prov(),
            source_id="doc",
            stable_key="s0",
        )
    )
    # The engine's delete-then-rederive discipline, by hand: remove the closed
    # row's view entry, derive the new live row, one transaction.
    new_rows = [r for r in _live_rows(conn) if r.row_id != old_rows[0].row_id]
    with conn.transaction():
        assert view.remove(conn.cursor(), [old_rows[0].row_id]) == 1
        view.derive(conn.cursor(), new_rows)

    op = ANNOperator(_DSN, embedder)
    try:
        ids = [str(r.id) for r in _search(op, "alpha beta original").records]
        assert str(new_id) in ids
        assert str(old_id) not in ids

        # Now plant a deliberately stale view row for the CLOSED record row —
        # the state a crash between remove() and the cursor advance could
        # leave. The join to records must filter it; the view's own columns
        # are never trusted for liveness.
        with conn.transaction():
            view.derive(conn.cursor(), [old_rows[0]])
        ids = [str(r.id) for r in _search(op, "alpha beta original").records]
        assert str(old_id) not in ids
        assert str(new_id) in ids
    finally:
        op.close()


@requires_pg
def test_limit_bounds_the_candidate_count(conn, store):
    embedder = FakeEmbedder()
    view = DenseView(embedder)
    view.ensure_schema(conn)
    for i in range(5):
        store.apply(_assert_op(f"alpha common token {i}", source_id="doc", stable_key=f"s{i}"))
    _derive_live(conn, view)

    op = ANNOperator(_DSN, embedder)
    try:
        candidates = _search(op, "alpha common", limit=2)
    finally:
        op.close()
    assert len(candidates.records) == 2
    assert len(candidates.scores) == 2


# --- the one real-model integration test -------------------------------------


@requires_pg
@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers not installed (datum[embed] extra)",
)
def test_real_embedder_ranks_authentication_above_banana_bread(conn, store):
    embedder = SentenceTransformersEmbedder()
    view = DenseView(embedder)
    view.ensure_schema(conn)  # dim comes from the embedder (embedder-driven DDL)
    texts = {
        "s0": "Authentication and passwords: how users sign in to their accounts.",
        "s1": "Resetting a forgotten password restores access to a user account.",
        "s2": "A banana bread recipe with ripe bananas, butter, and cinnamon.",
    }
    for key, text in texts.items():
        store.apply(_assert_op(text, source_id="kb", stable_key=key))
    _derive_live(conn, view)

    op = ANNOperator(_DSN, embedder)
    try:
        candidates = _search(op, "how do I log in", limit=3)
    finally:
        op.close()

    bodies = [r.body_text() for r in candidates.records]
    assert len(bodies) == 3
    assert bodies.index(texts["s0"]) < bodies.index(texts["s2"])
    assert bodies[-1] == texts["s2"]  # the unrelated text ranks last of the three
    assert candidates.score_method == "cosine"
    assert list(candidates.scores) == sorted(candidates.scores, reverse=True)
