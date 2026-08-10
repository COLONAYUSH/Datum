"""Milestone A acceptance: the walking skeleton, end to end, against a real
Postgres and with ZERO ML dependencies (grep reads canonical records; no
FastCDC-derived index, embeddings, or pgvector involved).

This is the plan's first reviewable checkpoint stated as an executable test:
ingest a document, search it, get typed evidence back, fetch/navigate the
structure, explain the plan, read the change feed with since(), and replay a
past plan by record — all through the real Corpus composition root, the same
object the MCP server and CLI drive.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from datum import Corpus
from datum.kernel.errors import PrincipalResolutionError
from datum.kernel.principal import Principal

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"
_ALICE = Principal(id="alice", namespace=_ACME)
_OUTSIDER = Principal(id="mallory", namespace="tenant:other")

_RUNBOOK = """# Deploy Runbook

Deploy the service by running the deploy script against the production cluster.

## Rollback

If a deploy goes wrong, roll back by pinning the previous image tag and redeploying.

## Incident response

Page the on-call engineer if error rate exceeds five percent for ten minutes.
"""


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _pg_reachable(_DSN), reason=f"no Postgres at {_DSN!r}")


@pytest.fixture
def corpus():
    with psycopg.connect(_DSN, autocommit=True) as conn:
        # Fresh state, but only after migrations exist; Corpus.open migrates.
        pass
    c = Corpus.open(_DSN, hit_signing_key=b"walking-skeleton-key")
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        # Reset the L4 view state too, or a stale view_cursors marker left
        # ahead of the RESTART'd WAL silently disables the derivation engine
        # for this namespace — ANN's view never re-derives, and the hybrid
        # tests below would pass through grep/BM25 alone without exercising
        # (or even noticing) the dense operator. (Found wiring the eval gate.)
        conn.execute("TRUNCATE TABLE view_cursors")
        for view_table in ("view_dense", "view_lexical"):
            if conn.execute(
                "SELECT to_regclass(%s)", (view_table,)
            ).fetchone()[0] is not None:
                conn.execute(f"DELETE FROM {view_table}")
    yield c
    c.close()


def test_end_to_end_ingest_search_fetch_navigate_explain_since_replay(corpus):
    # 1. INGEST a real document through the write path.
    n = corpus.ingest("runbook.md", _RUNBOOK, principal=_ALICE)
    assert n >= 3  # intro + Rollback + Incident response, at least

    # 2. SEARCH it — real hybrid-less grep retrieval, typed Evidence back.
    ev = corpus.search("roll back the deploy", principal=_ALICE)
    assert ev.status == "ok"
    assert ev.hits, "expected at least one hit for a term in the document"
    assert 0.0 < ev.sufficiency < 1.0  # uncalibrated, never a fake certainty
    top = ev.hits[0]
    assert "roll back" in top.content.lower()
    assert "Rollback" in top.section_path  # structural provenance survived to the surface

    # 3. FETCH the top hit by its opaque hit_id — resolves to full content.
    fetched = corpus.fetch(top.hit_id, principal=_ALICE)
    assert fetched is not None and "roll back" in fetched.content.lower()

    # 4. NAVIGATE the document's structure without materializing chunk text.
    view = corpus.navigate("runbook.md", principal=_ALICE)
    assert view.root.path == "runbook.md"
    section_paths = {child.path for child in view.root.children}
    assert any("Rollback" in p for p in section_paths)

    # 5. EXPLAIN the plan that produced the search — reconstructed from trace.
    explanation = corpus.explain(ev.plan_id, principal=_ALICE)
    assert "acl_filter" in explanation and "fails closed" in explanation
    assert "search" in explanation

    # 6. SINCE: the change feed for this namespace shows the ingest writes.
    changes = corpus.since(None, principal=_ALICE)
    assert len(changes.changes) >= 3
    assert all(c.change_kind == "created" for c in changes.changes)
    assert changes.as_of_marker != ""

    # 7. REPLAY by record: the exact original evidence, even after the corpus
    #    changes underneath it.
    replayed = corpus.replay(ev.plan_id)
    original_contents = [i.content for i in replayed.items]
    # mutate the corpus: forget everything by re-ingesting a replacement doc
    corpus.ingest("runbook.md", "# Deploy Runbook\n\nTotally different content now.\n", principal=_ALICE)
    replayed_again = corpus.replay(ev.plan_id)
    assert [i.content for i in replayed_again.items] == original_contents  # unchanged by record


def test_search_is_namespace_fail_closed(corpus):
    corpus.ingest("runbook.md", _RUNBOOK, principal=_ALICE)
    # An outsider in a different namespace searching the same term gets nothing
    # — the coarse ACL partition is resolved before the operator runs.
    ev = corpus.search("roll back the deploy", principal=_OUTSIDER)
    assert ev.hits == ()
    assert ev.status == "insufficient_evidence"


def test_fetch_across_namespaces_yields_nothing(corpus):
    corpus.ingest("runbook.md", _RUNBOOK, principal=_ALICE)
    ev = corpus.search("roll back", principal=_ALICE)
    hit_id = ev.hits[0].hit_id
    # A valid hit_id, but fetched by a principal in another namespace: fail closed.
    assert corpus.fetch(hit_id, principal=_OUTSIDER) is None


def test_search_with_no_matches_reports_insufficient_evidence(corpus):
    corpus.ingest("runbook.md", _RUNBOOK, principal=_ALICE)
    ev = corpus.search("quantum chromodynamics", principal=_ALICE)
    assert ev.hits == ()
    assert ev.status == "insufficient_evidence"
    assert ev.sufficiency == 0.0


def test_replay_against_current_champion_reexecutes(corpus):
    corpus.ingest("runbook.md", _RUNBOOK, principal=_ALICE)
    ev = corpus.search("deploy", principal=_ALICE)
    corpus.ingest("runbook.md", "# Deploy Runbook\n\nThe deploy deploy deploy word appears thrice.\n", principal=_ALICE)
    # replay-by-record is frozen; against='current_champion' re-runs the query
    fresh = corpus.replay(ev.plan_id, against="current_champion")
    assert any("thrice" in i.content for i in fresh.items)


def test_compile_plan_refuses_a_principal_with_no_namespace(corpus):
    with pytest.raises(PrincipalResolutionError):
        corpus.compile_plan("anything", Principal(id="ghost", namespace=""))
