"""BM25Operator (L5) tests.

Two deliberately different infrastructure profiles in one module, which is
why the Postgres skipif is per-test here rather than module-level (the one
deviation from tests/storage/test_wal.py's pattern): the conformance tests
MUST run with no database at all — the gate runs at register_operator() time
with no live infrastructure, and an operator whose registration needed a
reachable Postgres would be failing that requirement silently. Everything
else runs against a real Postgres through the real write path (GroundStore +
WriteOp), because the properties under test — join-enforced liveness,
namespace exactness (decisions.md #13), injection-proof query parsing — are
properties of the SQL, not of Python around it.

Fixtures DROP view_lexical on teardown: sibling test modules truncate
`records` without CASCADE, and a leftover FK-bearing view table would break
them.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
import pytest

from datum.derivation.views.base import RecordRow
from datum.derivation.views.lexical import LexicalView
from datum.groundstore.store import RECORD_SELECT_COLUMNS, GroundStore, record_from_row
from datum.kernel.operator import CandidateSet
from datum.kernel.plan import Budget
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody
from datum.kernel.writeop import WriteOp
from datum.operators.bm25_op import BM25Operator
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


# --- conformance: no database, by requirement -------------------------------


def test_registration_passes_the_gate_with_no_reachable_database():
    registry = OperatorRegistry()
    registry.register(BM25Operator(_NOWHERE_DSN))  # must not raise, must not connect
    assert registry.kinds() == ("bm25",)
    assert registry.get("bm25").kind == "bm25"


def test_conformance_suite_passes_with_no_live_infrastructure():
    report = ConformanceSuite.run(BM25Operator(_NOWHERE_DSN))
    assert report.passed, report.failures
    assert len(report.results) == 4  # every mandatory case ran, none skipped


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
        c.execute("DROP TABLE IF EXISTS view_lexical")
        c.execute("TRUNCATE TABLE records, wal_entries RESTART IDENTITY CASCADE")
        LexicalView().ensure_schema(c)
        yield c
        c.execute("DROP TABLE IF EXISTS view_lexical")


@pytest.fixture
def store(conn):
    wal = WAL(_DSN)
    gs = GroundStore(_DSN, wal)
    yield gs
    gs.close()
    wal.close()


@pytest.fixture
def op():
    operator = BM25Operator(_DSN)
    yield operator
    operator.close()


def _derive_live(conn) -> None:
    """What the DerivationEngine will do: project every live record row into
    the lexical view (delete-then-rederive discipline, so start clean).
    """
    rows = conn.execute(
        f"SELECT row_id, {RECORD_SELECT_COLUMNS} FROM records "
        "WHERE tx_to IS NULL ORDER BY row_id"
    ).fetchall()
    record_rows = [RecordRow(row_id=r[0], record=record_from_row(tuple(r[1:]))) for r in rows]
    view = LexicalView()
    with conn.transaction():
        cur = conn.cursor()
        view.remove(cur, [rr.row_id for rr in record_rows])
        view.derive(cur, record_rows)


def _search(op: BM25Operator, query: str, *, namespace: str = _ACME, limit: int = 50) -> CandidateSet:
    fragment = QueryFragment(query=query, namespace=namespace, limit=limit)
    return op.execute(op.plan(fragment, Budget()))


@requires_pg
def test_topical_record_outranks_a_marginal_one_and_unrelated_never_match(conn, store, op):
    store.apply(_assert_op(
        "Hybrid retrieval fuses lexical retrieval and dense retrieval; retrieval quality wins",
        source_id="docA", stable_key="s1",
    ))
    store.apply(_assert_op(
        "A gardening report that mentions retrieval once, amid tulips and trellises",
        source_id="docB", stable_key="s1",
    ))
    store.apply(_assert_op(
        "A soup recipe with basil and thyme and nothing else",
        source_id="docC", stable_key="s1",
    ))
    _derive_live(conn)

    result = _search(op, "retrieval")
    texts = [r.body_text() for r in result.records]
    assert len(texts) == 2  # the soup recipe never matches
    assert texts[0].startswith("Hybrid retrieval")  # topical beats marginal
    assert result.scores[0] > result.scores[1]
    assert result.scores == tuple(sorted(result.scores, reverse=True))
    assert result.score_method == "ts_rank_cd"


@requires_pg
def test_multi_term_query_matches_stemmed_variants(conn, store, op):
    store.apply(_assert_op(
        "Morning run: five kilometres before breakfast", source_id="docA", stable_key="s1",
    ))
    store.apply(_assert_op(
        "Evening pastries: five croissants after dinner", source_id="docB", stable_key="s1",
    ))
    _derive_live(conn)

    # "running" stems to the lexeme 'run', matching a record that only says
    # "run"; the multi-term query is AND-ed, so the pastry record (which
    # shares "morning"'s absence but not the stem) never appears.
    result = _search(op, "morning running")
    assert [r.body_text() for r in result.records] == [
        "Morning run: five kilometres before breakfast"
    ]


@requires_pg
def test_namespace_isolation_is_exact(conn, store, op):
    store.apply(_assert_op("zeppelin blueprints, acme edition", source_id="docA", stable_key="s1"))
    store.apply(_assert_op(
        "zeppelin blueprints, rival edition",
        source_id="docB", stable_key="s1", namespace="tenant:other",
    ))
    _derive_live(conn)

    acme = _search(op, "zeppelin")
    assert [r.body_text() for r in acme.records] == ["zeppelin blueprints, acme edition"]
    assert all(r.provenance.writer.namespace == _ACME for r in acme.records)

    other = _search(op, "zeppelin", namespace="tenant:other")
    assert [r.body_text() for r in other.records] == ["zeppelin blueprints, rival edition"]

    # Exact equality (decisions.md #13): no prefix/subtree creep.
    assert _search(op, "zeppelin", namespace="tenant").records == ()


@requires_pg
def test_superseded_records_view_row_removed_and_not_returned(conn, store, op):
    r1 = store.apply(_assert_op("obsolete zeppelin schematics", source_id="docA", stable_key="s1"))
    _derive_live(conn)
    r2 = store.apply(_assert_op("revised airship schematics", source_id="docA", stable_key="s1"))
    assert r2 != r1  # the span was superseded

    # Engine discipline: remove the closed row's view row, derive the new one.
    closed = conn.execute(
        "SELECT row_id FROM records WHERE tx_to IS NOT NULL"
    ).fetchall()
    with conn.transaction():
        LexicalView().remove(conn.cursor(), [r[0] for r in closed])
    _derive_live(conn)

    assert _search(op, "zeppelin").records == ()  # only v1 said "zeppelin"
    revised = _search(op, "airship")
    assert [str(r.id) for r in revised.records] == [str(r2)]


@requires_pg
def test_a_planted_stale_view_row_for_a_closed_record_is_filtered_by_the_join(conn, store, op):
    store.apply(_assert_op("obsolete zeppelin schematics", source_id="docA", stable_key="s1"))
    store.apply(_assert_op("revised airship schematics", source_id="docA", stable_key="s1"))
    _derive_live(conn)  # view now holds only the live v2 row

    # Sabotage: plant a view row for the CLOSED v1 record row, tsv and all.
    # L2 is the source of truth at query time — the operator's join on
    # r.tx_to IS NULL must filter this row no matter what the view claims.
    conn.execute(
        "INSERT INTO view_lexical (row_id, record_id, namespace, producer_version, tsv) "
        "SELECT row_id, record_id, namespace, 'planted-stale', "
        "       to_tsvector('english', body_text) "
        "FROM records WHERE tx_to IS NOT NULL"
    )
    (planted,) = conn.execute(
        "SELECT count(*) FROM view_lexical WHERE producer_version = 'planted-stale'"
    ).fetchone()
    assert planted == 1  # the stale row really is sitting in the view

    assert _search(op, "zeppelin").records == ()  # ...and still not returned


@requires_pg
def test_hostile_query_text_cannot_inject_tsquery_or_sql(conn, store, op):
    store.apply(_assert_op("an innocuous foo document about bar", source_id="docA", stable_key="s1"))
    _derive_live(conn)

    hostile = [
        "foo) | (bar'; DROP TABLE records; --",
        "!!! & | <-> :*",
        "foo:* & !bar",
        "'); TRUNCATE TABLE records; --",
    ]
    for query in hostile:
        result = _search(op, query)  # must not raise, whatever it matches
        assert isinstance(result, CandidateSet)
        assert len(result.records) == len(result.scores)

    # The records table survived every attempt, content intact.
    (count,) = conn.execute("SELECT count(*) FROM records").fetchone()
    assert count == 1


@requires_pg
def test_pathological_query_size_and_null_bytes_do_not_raise(conn, store, op):
    # Review finding M2: a NUL byte (Postgres text can't hold it) and a query
    # with a huge term count (a 1MB paste builds a tsquery deep enough to blow
    # Postgres's stack-depth limit) both used to RAISE, propagating up through
    # Corpus.search. The bar is "no query may raise, records intact."
    store.apply(_assert_op("an innocuous foo document about bar", source_id="docA", stable_key="s1"))
    _derive_live(conn)

    million_terms = " ".join(["term"] * 250_000)  # ~1.5MB of query text
    for query in ["cat\x00dog", million_terms, "\x00" * 1000, "foo " * 100_000]:
        result = _search(op, query)  # must not raise
        assert isinstance(result, CandidateSet)
        assert len(result.records) == len(result.scores)
    (count,) = conn.execute("SELECT count(*) FROM records").fetchone()
    assert count == 1


@requires_pg
def test_empty_and_stopword_only_queries_return_empty_cleanly(conn, store, op):
    store.apply(_assert_op("the quick brown fox", source_id="docA", stable_key="s1"))
    _derive_live(conn)

    for query in ["", "   ", "the of and", "the a an of"]:
        result = _search(op, query)
        assert result.records == ()
        assert result.scores == ()
        assert result.score_method == "ts_rank_cd"


@requires_pg
def test_limit_is_respected_and_ordering_is_deterministic(conn, store, op):
    for i in range(5):
        store.apply(_assert_op(
            f"kestrel sighting number {i} " + "kestrel " * i,
            source_id="docA", stable_key=f"s{i}",
        ))
    _derive_live(conn)

    limited = _search(op, "kestrel", limit=3)
    assert len(limited.records) == 3
    assert limited.scores == tuple(sorted(limited.scores, reverse=True))

    # Deterministic: the same query twice returns the identical ranking
    # (rank DESC, record_id tie-break — no run-to-run reshuffling).
    again = _search(op, "kestrel", limit=3)
    assert [str(r.id) for r in again.records] == [str(r.id) for r in limited.records]

    everything = _search(op, "kestrel", limit=50)
    assert len(everything.records) == 5
