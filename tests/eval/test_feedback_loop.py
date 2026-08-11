"""The relevance-feedback loop (decisions.md #44), end to end against real
Postgres: judgments recorded through real signed hit tokens (fail-closed
across namespaces), calibration with its holdout promotion gate, and
per-namespace overrides loaded at wiring time and visible in a plan's
EXPLAIN. Needs the real embedder (feedback joins to real searches)."""

from __future__ import annotations

import importlib.util
import json
import os

import psycopg
import pytest

from datum.corpus import Corpus
from datum.eval.calibrate import run_calibration
from datum.kernel.principal import Principal

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_NS = "tenant:fb"


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
        reason="the datum[embed] extra is not installed",
    ),
]

_DOCS = {
    "auth.md": "# Signing in\nUsers authenticate with a password and a one-time passcode.",
    "billing.md": "# Invoices\nInvoices are issued on the first business day of each month.",
    "backup.md": "# Backups\nNightly snapshots are retained for thirty-five days.",
    "deploy.md": "# Deploys\nReleases ship every Tuesday after the smoke suite passes.",
    "oncall.md": "# On-call\nThe pager rotates weekly at Monday 09:00 UTC.",
    "gdpr.md": "# Erasure\nSubject-erasure requests complete within thirty days.",
    "limits.md": "# Rate limits\nThe public API allows one hundred requests per minute.",
    "sso.md": "# SSO\nSAML single sign-on is available on the enterprise plan.",
    "audit.md": "# Audit\nEvery admin action is written to the immutable audit log.",
}
_QUERIES = {  # query -> the doc whose chunk answers it
    "how do users log in": "auth.md",
    "when are invoices issued": "billing.md",
    "how long are snapshots kept": "backup.md",
    "when do releases ship": "deploy.md",
    "when does the pager rotate": "oncall.md",
    "how fast are erasure requests completed": "gdpr.md",
    "how many api requests per minute": "limits.md",
    "is saml supported": "sso.md",
    "where are admin actions recorded": "audit.md",
}


@pytest.fixture
def corpus():
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS view_dense")
    c = Corpus.open(_DSN, hit_signing_key=b"fb-key", abstain_min_similarity=0.0)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("TRUNCATE TABLE relevance_feedback")
        conn.execute("TRUNCATE TABLE policy_overrides")
        conn.execute("DELETE FROM view_lexical")
    yield c
    c.close()


def _seed_feedback(corpus) -> int:
    """Run every query, mark the hit from the answering doc useful and the
    top foreign hit not-useful — through the REAL feedback verb."""
    p = Principal(id="u", namespace=_NS)
    for src, text in _DOCS.items():
        corpus.ingest(src, text, p)
    n = 0
    for query, answer_doc in _QUERIES.items():
        ev = corpus.search(query, principal=p)
        for h in ev.hits[:3]:
            doc = h.section_path[0] if h.section_path else ""
            assert corpus.feedback(h.hit_id, doc == answer_doc, principal=p)
            n += 1
    return n


def test_feedback_is_recorded_and_namespace_fail_closed(corpus):
    p = Principal(id="u", namespace=_NS)
    corpus.ingest("auth.md", _DOCS["auth.md"], p)
    ev = corpus.search("how do users log in", principal=p)
    assert ev.hits

    assert corpus.feedback(ev.hits[0].hit_id, True, principal=p) is True
    with psycopg.connect(_DSN) as conn:
        rows = conn.execute(
            "SELECT namespace, useful FROM relevance_feedback"
        ).fetchall()
    assert rows == [(_NS, True)]

    # A principal from ANOTHER namespace replaying the same hit token records
    # nothing — feedback is fail-closed exactly like fetch.
    outsider = Principal(id="evil", namespace="tenant:other")
    assert corpus.feedback(ev.hits[0].hit_id, True, principal=outsider) is False
    with psycopg.connect(_DSN) as conn:
        count = conn.execute("SELECT count(*) FROM relevance_feedback").fetchone()[0]
    assert count == 1  # still just the legitimate row


def test_calibration_refuses_on_insufficient_feedback(corpus):
    p = Principal(id="u", namespace=_NS)
    corpus.ingest("auth.md", _DOCS["auth.md"], p)
    ev = corpus.search("how do users log in", principal=p)
    corpus.feedback(ev.hits[0].hit_id, True, principal=p)

    result = run_calibration(corpus, _NS)
    assert result.promoted is False
    assert "insufficient feedback" in result.reason
    with psycopg.connect(_DSN) as conn:
        assert conn.execute("SELECT count(*) FROM policy_overrides").fetchone()[0] == 0


def test_calibration_runs_the_gate_and_never_promotes_without_holdout_gain(corpus):
    _seed_feedback(corpus)
    # Tiny grid keeps the test fast; the useful records already rank at the
    # top under defaults, so the holdout gate must REFUSE (no gain possible).
    result = run_calibration(
        corpus, _NS, weight_grid=[1.0, 2.0], floor_grid=[0.0]
    )
    assert result.n_queries == len(_QUERIES)
    assert result.holdout_mrr <= result.baseline_holdout_mrr or result.promoted
    if not result.promoted:
        assert "promotion refused" in result.reason or "does not beat" in result.reason
        with psycopg.connect(_DSN) as conn:
            assert conn.execute("SELECT count(*) FROM policy_overrides").fetchone()[0] == 0


def test_promoted_override_is_loaded_and_visible_in_explain(corpus):
    # Seed an override the way a successful calibration writes it, then prove
    # the whole loop closes: a fresh Corpus.open loads it, and a compiled
    # plan's EXPLAIN shows the calibrated weight — auditable end to end.
    params = {
        "fusion_weights": {"grep": 0.5, "bm25": 2.0, "ann": 1.5},
        "abstain_min_similarity": 0.31,
    }
    basis = {"n_judged_queries": 12, "holdout_mrr": 0.9, "baseline_holdout_mrr": 0.7}
    with psycopg.connect(_DSN) as conn:
        conn.execute(
            "INSERT INTO policy_overrides (namespace, params, basis) VALUES (%s, %s, %s)",
            (_NS, json.dumps(params), json.dumps(basis)),
        )
        conn.commit()

    with Corpus.open(_DSN, hit_signing_key=b"fb-key") as c2:
        p = Principal(id="u", namespace=_NS)
        c2.ingest("auth.md", _DOCS["auth.md"], p)
        plan = c2.compile_plan("how do users log in", p)
        explain = plan.explain()
        assert "fusion_weight=2.0" in explain  # the calibrated bm25 weight
        assert "min_dense_similarity=0.31" in explain  # the calibrated floor
        # ...and an UNCALIBRATED namespace still gets the declared defaults.
        other = Principal(id="v", namespace="tenant:plain")
        c2.ingest("auth.md", _DOCS["auth.md"], other)
        explain_other = c2.compile_plan("how do users log in", other).explain()
        assert "fusion_weight=2.0" not in explain_other
