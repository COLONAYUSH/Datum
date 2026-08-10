"""Live cross-namespace tenancy conformance, against a real Postgres.

The in-package ConformanceSuite runs at register_operator() time with NO live
infrastructure, so it exercises an operator's `execute()` only through the
synthetic probe path — it never runs `_execute_query`, where the real
`WHERE records.namespace = %s` SQL lives. That gap is exactly what the
approved plan's build-order step 7 ("run the suite against real bm25_op/ann_op
... needs real multi-tenant data") and conformance/fixtures.py's
`TODO(scratch-namespace provisioning)` reserve for a LIVE tier. This is that
tier: real records in two namespaces, each real operator's real query path,
asserting the physical partition isolation the synthetic fixtures explicitly
cannot (decisions.md #24).

It codifies the Milestone B adversarial review's Attack 1 (cross-namespace
leakage, including a planted "lying" view row whose namespace column claims
the caller's tenant while its underlying record is in another) as a permanent
regression, so a future operator or view change that reopened the leak would
fail here rather than in a one-off review.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
import pytest

from datum.derivation.engine import DerivationEngine
from datum.derivation.views.dense import DenseView
from datum.derivation.views.lexical import LexicalView
from datum.groundstore.store import GroundStore
from datum.kernel.operator import OperatorPlan
from datum.kernel.plan import Budget
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
from datum.operators.ann_op import ANNOperator
from datum.operators.bm25_op import BM25Operator
from datum.operators.common import QueryFragment
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"
_EVIL = "tenant:evil"


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
    """Deterministic, no model load: a token-hash direction summed per doc,
    then L2-normalized. Enough geometry for a nearest-neighbor query; the
    point of this file is tenancy, not embedding quality.
    """

    name = "fake-embedder"
    version = "test"
    dim = 16

    def _vec(self, text: str) -> list[float]:
        import hashlib
        import math

        acc = [0.0] * self.dim
        for tok in text.lower().split():
            h = hashlib.sha256(tok.encode()).digest()
            for i in range(self.dim):
                acc[i] += (h[i] / 255.0) - 0.5
        norm = math.sqrt(sum(x * x for x in acc)) or 1.0
        return [x / norm for x in acc]

    def encode_documents(self, texts):
        return [self._vec(t) for t in texts]

    def encode_query(self, text):
        return self._vec(text)


def _prov(namespace: str) -> ProvenanceCapsule:
    return ProvenanceCapsule(
        writer=Principal(id="ingestor", namespace=namespace),
        ingestion_path="test",
        authority_tier="UNVERIFIED",
        trust_class="trusted",
        source_version="test-v1",
    )


def _assert_op(text: str, *, source_id: str, stable_key: str, namespace: str) -> WriteOp:
    return WriteOp.assert_(
        body=StructuredBody(text=text, section_path=(source_id, stable_key)),
        valid_from=datetime.now(timezone.utc),
        provenance=_prov(namespace),
        policy_id="default-acl",  # type: ignore[arg-type]
        source_id=source_id,
        stable_key=stable_key,
    )


def _drop_views() -> None:
    # DROP (not truncate) view_dense so this file's dim-16 FakeEmbedder never
    # collides with a sibling test's real 384-dim view_dense on the shared
    # scratch DB — the dimension guard (dense.py) is doing its job, so the
    # fixture must give it a clean slate, and restore one on teardown so the
    # real-embedder tests that follow rebuild their own schema.
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS view_dense")
        conn.execute("DROP TABLE IF EXISTS view_lexical")


@pytest.fixture
def wired():
    run_migrations(_DSN)
    _drop_views()
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE view_cursors")
    embedder = FakeEmbedder()
    engine = DerivationEngine(_DSN, [LexicalView(), DenseView(embedder)])
    engine.ensure_schemas()
    wal = WAL(_DSN)
    store = GroundStore(_DSN, wal)
    bm25 = BM25Operator(_DSN)
    ann = ANNOperator(_DSN, embedder)
    yield store, engine, bm25, ann
    bm25.close()
    ann.close()
    engine.close()
    store.close()
    wal.close()
    _drop_views()  # leave no dim-16 view_dense for the real-embedder tests


def _run(operator, namespace: str) -> list[str]:
    """Drive an operator's REAL query path (not the synthetic probe path) and
    return the namespaces of the records it returned.
    """
    frag = QueryFragment(query="secret alpha payload beta", namespace=namespace, limit=50)
    result = operator.execute(operator.plan(frag, Budget()))
    return [r.provenance.writer.namespace for r in result.records]


@pytest.mark.parametrize("op_name", ["bm25", "ann"])
def test_real_query_path_never_crosses_namespaces(wired, op_name):
    store, engine, bm25, ann = wired
    operator = {"bm25": bm25, "ann": ann}[op_name]

    store.apply(_assert_op("secret alpha payload beta acme", source_id="d", stable_key="s1", namespace=_ACME))
    store.apply(_assert_op("secret alpha payload beta evil topsecret", source_id="d", stable_key="s1", namespace=_EVIL))
    engine.refresh(_ACME)
    engine.refresh(_EVIL)

    acme_ns = _run(operator, _ACME)
    evil_ns = _run(operator, _EVIL)
    assert acme_ns and all(ns == _ACME for ns in acme_ns), f"{op_name} leaked cross-namespace: {acme_ns}"
    assert evil_ns and all(ns == _EVIL for ns in evil_ns), f"{op_name} leaked cross-namespace: {evil_ns}"


@pytest.mark.parametrize("op_name,view_table", [("bm25", "view_lexical"), ("ann", "view_dense")])
def test_lying_view_row_cannot_leak_foreign_content(wired, op_name, view_table):
    # Attack 1's hardest case: flip the view row's namespace column to claim
    # the caller's tenant while its underlying records row stays foreign. The
    # operator's JOIN filters on records.namespace, not the view column, so
    # the lie must not leak — and content always comes from the joined records
    # row, so a mis-derived view row can at worst cause a false MATCH, never
    # surface another tenant's text.
    store, engine, bm25, ann = wired
    operator = {"bm25": bm25, "ann": ann}[op_name]

    store.apply(_assert_op("secret alpha payload beta acme", source_id="d", stable_key="s1", namespace=_ACME))
    store.apply(_assert_op("secret alpha payload beta evil topsecret", source_id="d", stable_key="s1", namespace=_EVIL))
    engine.refresh(_ACME)
    engine.refresh(_EVIL)

    with psycopg.connect(_DSN, autocommit=True) as conn:
        # Point the lie at the evil record's view row.
        conn.execute(
            f"UPDATE {view_table} SET namespace=%s "
            "WHERE record_id IN (SELECT record_id FROM records WHERE namespace=%s)",
            (_ACME, _EVIL),
        )
    returned = operator.execute(operator.plan(QueryFragment(query="secret alpha payload beta", namespace=_ACME, limit=50), Budget()))
    namespaces = {r.provenance.writer.namespace for r in returned.records}
    contents = [r.body_text() for r in returned.records]
    assert _EVIL not in namespaces, f"{op_name} leaked evil records via a lying view row: {namespaces}"
    assert not any("topsecret" in c for c in contents), f"{op_name} leaked evil content: {contents}"
