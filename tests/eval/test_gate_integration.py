"""The eval gate, end to end against a real Corpus (Milestone C).

Distinct from `tests/eval/test_regression.py`, which proves the pass/fail
LOGIC against a hand-written fake evidence_fn: this file proves the WIRING —
the fixed, human-curated regression set actually passes when run through the
real hybrid pipeline (dense + BM25 + ANN, fused, reranked) over the sample
corpus. It IS the config-change gate the plan calls for: if a change to the
policy rule table, fusion weights, the embedder, an operator, or the compiler
regresses retrieval on the fixed set, this test goes red.

Uses the real embedder + reranker, so it skips without the `datum[embed]`
extra (a meaningful hybrid gate needs the dense operator); the pass/fail
logic itself is covered ML-free in test_regression.py.
"""

from __future__ import annotations

import importlib.util
import os

import psycopg
import pytest

from datum.corpus import Corpus
from datum.eval.gate import DEFAULT_CORPUS_DIR, DEFAULT_REGRESSION_SET, run_gate

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")


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
        reason="the datum[embed] extra is not installed; the hybrid eval gate needs the embedder",
    ),
]


@pytest.fixture
def corpus():
    c = Corpus.open(_DSN, hit_signing_key=b"eval-gate-key")
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE records RESTART IDENTITY CASCADE")
        conn.execute("TRUNCATE TABLE wal_entries RESTART IDENTITY")
        conn.execute("TRUNCATE TABLE plan_traces")
        conn.execute("TRUNCATE TABLE view_cursors")
        conn.execute("DELETE FROM view_dense")
        conn.execute("DELETE FROM view_lexical")
    yield c
    c.close()


def test_fixed_regression_set_passes_against_real_hybrid_retrieval(corpus):
    report = run_gate(
        corpus, corpus_dir=DEFAULT_CORPUS_DIR, regression_set=DEFAULT_REGRESSION_SET
    )
    # A failure here is a real retrieval regression — surface every failing
    # case's own diagnostic, not just a bare assert, so CI shows what broke.
    failures = [(c.query, c.principal_namespace, detail) for c, ok, detail in report.results if not ok]
    assert report.passed, "eval gate regressed:\n" + "\n".join(
        f"  [{ns}] {q!r}: {detail}" for q, ns, detail in failures
    )
    # Sanity: the gate actually exercised the whole fixed set, not zero cases.
    assert len(report.results) >= 10
