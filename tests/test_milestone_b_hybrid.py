"""Milestone B acceptance: hybrid retrieval returns semantically-relevant hits,
not just term matches, end to end through the real Corpus.

This is the checkpoint the handoff names ("semantically-relevant hits, not
just term matches, on the sample corpus"). It uses the REAL bge-small
embedder and the REAL cross-encoder reranker, so it is skipped when the
`datum[embed]` extra is absent; a fast structural cousin
(test_walking_skeleton) already covers the ML-free path. The single decisive
assertion is the one BM25 alone cannot satisfy: a query sharing NO content
word with the relevant section still retrieves it, above an off-topic section
that shares more surface words — which is only possible because the dense
operator contributes to the fusion.
"""

from __future__ import annotations

import importlib.util
import os

import psycopg
import pytest

from datum.corpus import Corpus
from datum.kernel.principal import Principal

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _pg_reachable(_DSN), reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}"
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("sentence_transformers") is None,
        reason="the datum[embed] extra is not installed; hybrid acceptance needs the real embedder",
    ),
]

_KB = """# Account access

## Signing in
People confirm who they are with a username, a password, and a one-time
passcode from the authenticator app. A session stays valid for twelve hours.

## Recovering a lost password
The self-service portal emails a reset link that stays usable for fifteen
minutes.

# Weeknight cooking

## Banana bread
Mash three very ripe bananas, fold them into a brown-butter batter, and bake
at 175 degrees for about fifty-five minutes.
"""


@pytest.fixture
def corpus():
    c = Corpus.open(_DSN, hit_signing_key=b"milestone-b-key")
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("DELETE FROM view_dense")
        conn.execute("DELETE FROM view_lexical")
    yield c
    c.close()


def test_hybrid_retrieves_semantically_without_term_overlap(corpus):
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))

    # "log in" / "credentials" appear NOWHERE in the corpus; the signing-in
    # section talks about "confirm who they are", "username", "passcode". A
    # pure lexical retriever cannot bridge that gap; the dense operator can.
    ev = corpus.search("how do I log in with my credentials", principal=Principal(id="alice", namespace=_ACME))

    assert ev.status == "ok"
    assert ev.hits, "hybrid retrieval returned nothing for a semantically-clear query"
    top = ev.hits[0]
    assert "Signing in" in top.section_path, (
        f"expected the sign-in section on top, got section_path={top.section_path!r} "
        f"content={top.content!r}"
    )
    # The off-topic cooking section must not outrank the relevant one.
    banana_ranks = [i for i, h in enumerate(ev.hits) if "Banana bread" in h.section_path]
    signin_ranks = [i for i, h in enumerate(ev.hits) if "Signing in" in h.section_path]
    assert signin_ranks and (not banana_ranks or signin_ranks[0] < banana_ranks[0])


def test_hybrid_plan_explains_all_three_operators(corpus):
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    plan = corpus.compile_plan("session timeout", Principal(id="alice", namespace=_ACME))
    explain = plan.explain()
    for kind in ("grep", "bm25", "ann"):
        assert f"operator={kind!r}" in explain, f"{kind} missing from EXPLAIN:\n{explain}"
    # A real reranker is wired when the embed extra is present, so the rerank
    # step must be visible in the plan too.
    assert "rerank" in explain


def test_namespace_isolation_holds_under_hybrid(corpus):
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    # A principal in another tenant, querying the very text acme holds, gets
    # nothing: the coarse ACL partition is resolved before any operator runs,
    # and every operator re-checks namespace at the records join.
    ev = corpus.search(
        "how do I log in with my credentials",
        principal=Principal(id="mallory", namespace="tenant:evil"),
    )
    assert ev.hits == ()
    assert ev.status == "insufficient_evidence"


def test_empty_query_reports_insufficient_evidence(corpus):
    # Review finding L2: an empty/whitespace query used to return the whole
    # namespace at status=ok with a fabricated ~0.3 sufficiency (grep scored
    # every record 1.0). It must now report insufficient_evidence across the
    # hybrid, matching BM25/ANN which already return nothing for a blank query.
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    for q in ["", "   "]:
        ev = corpus.search(q, principal=Principal(id="alice", namespace=_ACME))
        assert ev.hits == (), f"empty query {q!r} returned hits"
        assert ev.status == "insufficient_evidence"
        assert ev.sufficiency == 0.0


def test_tiny_budget_still_returns_a_hit(corpus):
    # Review finding L1: budget.tokens_max in 1..79 floor-divided to LIMIT 0,
    # so a tiny budget silently returned nothing as if the corpus were empty.
    # A retrieval asks for at least one hit.
    from datum.kernel.plan import Budget

    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    # A query that clears the abstention floor (a strong match), so this test
    # isolates the limit-flooring fix (L1) rather than the abstention gate (#29):
    # tokens_max=40 floor-divides to LIMIT 0 without the fix, returning nothing.
    ev = corpus.search(
        "how do I log in with my credentials", principal=Principal(id="alice", namespace=_ACME),
        budget=Budget(tokens_max=40),
    )
    assert ev.hits, "a tiny (but non-zero) budget must still return at least one hit"


def test_path_glob_sufficiency_reflects_the_filtered_hits(corpus):
    # Review finding M3: path_glob narrowed the returned hits but reported the
    # sufficiency of the UNFILTERED set. path_glob is now a real plan step
    # applied before sufficiency, so the confidence matches the hits returned,
    # and EXPLAIN names the filter.
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    corpus.ingest("other", "# Misc\n\nlogging in and passwords elsewhere\n", principal=Principal(id="alice", namespace=_ACME))
    p = Principal(id="alice", namespace=_ACME)
    unfiltered = corpus.search("how do I log in", principal=p)
    filtered = corpus.search("how do I log in", principal=p, path_glob="kb")
    assert filtered.hits, "expected the kb source to still match"
    assert all(h.source_path == "kb" for h in filtered.hits)
    # The 'other' source also matches 'log in', so the filter MUST drop hits
    # (unconditional — the assertion never sits behind a condition on the very
    # thing under test), and the reported sufficiency must reflect the smaller
    # filtered set rather than copy the pre-filter score.
    assert any(h.source_path != "kb" for h in unfiltered.hits), "test needs a non-kb hit to filter"
    assert len(filtered.hits) < len(unfiltered.hits)
    assert filtered.sufficiency != unfiltered.sufficiency
    # EXPLAIN names the filter AND orders it before rerank — the order _run
    # actually executes (filter the fused set, then rerank the filtered head).
    explain = corpus.compile_plan("how do I log in", p, path_glob="kb").explain()
    assert "source_filter" in explain and "path_glob='kb'" in explain
    assert explain.index("source_filter") < explain.index("rerank")


def test_replay_champion_preserves_the_source_filter(corpus):
    # A champion re-run must apply the same source filter the recorded plan
    # carried, or it answers a broader question than the plan it replays
    # (advisor follow-up on the M3 fix).
    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    corpus.ingest("other", "# Misc\n\nlogging in elsewhere\n", principal=Principal(id="alice", namespace=_ACME))
    p = Principal(id="alice", namespace=_ACME)
    ev = corpus.search("how do I log in", principal=p, path_glob="kb")
    champion = corpus.replay(ev.plan_id, against="current_champion")
    # Every re-run hit stays within the kb source — the filter survived replay.
    assert champion.items, "champion re-run returned nothing"
    assert all(i.section_path and i.section_path[0] == "kb" for i in champion.items)


def test_real_operators_obey_the_score_contract_on_the_live_path(corpus):
    # Review finding H3: the conformance gate only exercises the synthetic
    # probe path, never the real query SQL. This asserts the score contract
    # (finite scores, 1:1 with records, no duplicate record ids) directly on
    # each real operator's live path — the check the gate structurally cannot
    # make (decisions.md #24/#26).
    import math

    from datum.operators.common import QueryFragment
    from datum.kernel.plan import Budget

    corpus.ingest("kb", _KB, principal=Principal(id="alice", namespace=_ACME))
    frag = QueryFragment(query="signing in with a password", namespace=_ACME, limit=50)
    for kind in corpus._registry.kinds():
        op = corpus._registry.get(kind)
        cs = op.execute(op.plan(frag, Budget()))
        assert len(cs.records) == len(cs.scores), f"{kind}: score/record length mismatch"
        assert all(math.isfinite(s) for s in cs.scores), f"{kind}: non-finite score"
        ids = [str(r.id) for r in cs.records]
        assert len(ids) == len(set(ids)), f"{kind}: duplicate record id in output"
