"""Proves load_regression_set parses the real fixture and run_regression
actually detects failures, not just successes, using hand-written fake
evidence_fn callables (this module has no Corpus/planner to call for real).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datum.eval.regression import (
    RegressionCase,
    RegressionReport,
    load_regression_set,
    run_regression,
)
from datum.kernel import Evidence, SearchHit

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
REGRESSION_SET_PATH = FIXTURES_DIR / "regression_set.yaml"
CORPUS_DIR = FIXTURES_DIR / "sample_corpus"


def _load_corpus() -> dict[str, str]:
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(CORPUS_DIR.glob("*.md"))}


# ---------------------------------------------------------------------------
# load_regression_set
# ---------------------------------------------------------------------------


def test_load_regression_set_parses_the_real_fixture() -> None:
    cases = load_regression_set(str(REGRESSION_SET_PATH))

    assert isinstance(cases, tuple)
    assert len(cases) == 11  # a truncated/half-parsed YAML file would silently under-count here

    first = cases[0]
    assert first == RegressionCase(
        query="How many consecutive failures does it take before the circuit breaker opens?",
        expected_content_substrings=("five consecutive failures within a 30 second window",),
        min_sufficiency=0.5,
        principal_namespace="eng",
    )

    # the two abstention-by-design cases parsed with a genuinely empty tuple,
    # not e.g. a one-element tuple containing an empty string
    abstain_cases = [c for c in cases if c.expected_content_substrings == ()]
    assert len(abstain_cases) == 3  # out-of-corpus x2 + the cross-namespace negative control


def test_fixture_substrings_actually_appear_in_the_sample_corpus() -> None:
    """Guards against the likeliest real defect in this fixture: a hand-typed
    expected_content_substrings entry drifting from the doc text it was
    copied from -- or from a *different* doc's text than the one the case
    means to exercise.

    Checked per-document, not against the whole corpus concatenated: a
    single doc must contain ALL of a case's substrings. Checking against
    the concatenated blob would let a phrase that drifted into the wrong
    document (e.g. copied from eng_incident_response.md into a case that
    means to test hr_pto_policy.md) pass silently, which defeats the point
    of this check.
    """
    cases = load_regression_set(str(REGRESSION_SET_PATH))
    corpus_docs = _load_corpus()

    for case in cases:
        if not case.expected_content_substrings:
            continue
        matching_docs = [
            name
            for name, text in corpus_docs.items()
            if all(s in text for s in case.expected_content_substrings)
        ]
        assert matching_docs, (
            f"case query={case.query!r} expects substrings "
            f"{case.expected_content_substrings!r}, but no single document under "
            "tests/fixtures/sample_corpus/ contains all of them"
        )


def test_load_regression_set_accepts_json(tmp_path: Path) -> None:
    json_path = tmp_path / "cases.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "query": "q1",
                    "expected_content_substrings": ["alpha"],
                    "min_sufficiency": 0.4,
                    "principal_namespace": "eng",
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_regression_set(str(json_path))

    assert cases == (
        RegressionCase(
            query="q1",
            expected_content_substrings=("alpha",),
            min_sufficiency=0.4,
            principal_namespace="eng",
        ),
    )


def test_load_regression_set_names_the_bad_case_on_missing_field(tmp_path: Path) -> None:
    json_path = tmp_path / "broken.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "query": "fine",
                    "min_sufficiency": 0.5,
                    "principal_namespace": "eng",
                },
                {
                    "query": "missing min_sufficiency",
                    "principal_namespace": "eng",
                },
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"index 1.*min_sufficiency"):
        load_regression_set(str(json_path))


def test_load_regression_set_rejects_unknown_extension(tmp_path: Path) -> None:
    bad_path = tmp_path / "cases.txt"
    bad_path.write_text("not a real format", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.txt"):
        load_regression_set(str(bad_path))


# ---------------------------------------------------------------------------
# run_regression, against hand-written fake evidence_fn callables
# ---------------------------------------------------------------------------


def _doc_namespace(doc_name: str) -> str:
    return doc_name.split("_", 1)[0]


def _make_correct_evidence_fn(query_to_doc: dict[str, str]):
    """A fake evidence_fn that behaves like a correctly namespace-scoped
    retriever: it only returns a document if the query maps to one AND that
    document's namespace matches the principal's namespace. Anything else
    (unmapped query, or mapped but wrong namespace) abstains.
    """
    docs = _load_corpus()

    def fn(query: str, namespace: str) -> Evidence:
        doc_name = query_to_doc.get(query)
        if doc_name is None or _doc_namespace(doc_name) != namespace:
            return Evidence(hits=(), status="insufficient_evidence", sufficiency=0.05, plan_id="fake-plan")
        hit = SearchHit(hit_id="h1", content=docs[doc_name], source_path=f"{doc_name}.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.9, plan_id="fake-plan")

    return fn


QUERY_TO_DOC = {
    "How many consecutive failures does it take before the circuit breaker opens?": "eng_incident_response",
    "What formula does the retry backoff use before opening the circuit?": "eng_incident_response",
    "What is the PTO accrual rate for full-time employees?": "hr_pto_policy",
    "How large are the batches used when backfilling a new column?": "eng_database_migration",
    "What must a new hire sign before payroll can be activated?": "hr_onboarding_checklist",
    "How much notice do callers get before a deprecated public API is fully retired?": "eng_api_deprecation",
    "How quickly must an on-call engineer escalate a SEV1 incident to the on-call lead?": "eng_incident_response",
    "How quickly should a PTO balance question be escalated to a HR business partner?": "hr_pto_policy",
}


def test_run_regression_all_cases_pass_against_a_correctly_scoped_fake() -> None:
    cases = load_regression_set(str(REGRESSION_SET_PATH))
    evidence_fn = _make_correct_evidence_fn(QUERY_TO_DOC)

    report = run_regression(cases, evidence_fn)

    assert isinstance(report, RegressionReport)
    assert report.passed is True
    assert len(report.results) == len(cases)
    for case, ok, detail in report.results:
        assert ok is True, f"case {case.query!r} unexpectedly failed: {detail}"


def test_run_regression_detects_a_missing_substring() -> None:
    case = RegressionCase(
        query="How many consecutive failures does it take before the circuit breaker opens?",
        expected_content_substrings=("five consecutive failures within a 30 second window",),
        min_sufficiency=0.5,
        principal_namespace="eng",
    )

    def wrong_content_fn(query: str, namespace: str) -> Evidence:
        # Returns real evidence, but from the wrong document entirely --
        # the expected phrase is simply not in it.
        hit = SearchHit(hit_id="h1", content=_load_corpus()["eng_api_deprecation"], source_path="eng_api_deprecation.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.9, plan_id="fake-plan")

    report = run_regression([case], wrong_content_fn)

    assert report.passed is False
    ((got_case, ok, detail),) = report.results
    assert got_case == case
    assert ok is False
    assert "missing expected substring" in detail


def test_run_regression_detects_sufficiency_below_the_declared_minimum() -> None:
    case = RegressionCase(
        query="anything",
        expected_content_substrings=("needle",),
        min_sufficiency=0.8,
        principal_namespace="eng",
    )

    def low_sufficiency_fn(query: str, namespace: str) -> Evidence:
        hit = SearchHit(hit_id="h1", content="contains the needle but barely", source_path="doc.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.1, plan_id="fake-plan")

    report = run_regression([case], low_sufficiency_fn)

    assert report.passed is False
    ((_, ok, detail),) = report.results
    assert ok is False
    assert "sufficiency" in detail


def test_run_regression_detects_a_failure_to_abstain() -> None:
    """The out-of-corpus / out-of-namespace case: expected_content_substrings
    is empty, meaning "this should come back insufficient_evidence." A fake
    that wrongly returns 'ok' content must be caught, not passed.
    """
    case = RegressionCase(
        query="out of corpus question",
        expected_content_substrings=(),
        min_sufficiency=0.0,
        principal_namespace="hr",
    )

    def hallucinating_fn(query: str, namespace: str) -> Evidence:
        hit = SearchHit(hit_id="h1", content="an answer that should not exist", source_path="doc.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.6, plan_id="fake-plan")

    report = run_regression([case], hallucinating_fn)

    assert report.passed is False
    ((_, ok, detail),) = report.results
    assert ok is False
    assert "insufficient_evidence" in detail


def test_run_regression_detects_a_cross_namespace_leak() -> None:
    """The fixture's case 11: querying as 'hr' for content that only exists
    in the 'eng' namespace must abstain under correct scoping. A fake that
    ignores the namespace argument entirely (the leak) must be caught.
    """
    negative_control_query = "How much notice do callers get before a deprecated public API is fully retired?"
    cases = load_regression_set(str(REGRESSION_SET_PATH))
    negative_control_case = next(
        c
        for c in cases
        if c.query == negative_control_query and c.principal_namespace == "hr"
    )
    assert negative_control_case.expected_content_substrings == ()

    def leaky_fn(query: str, namespace: str) -> Evidence:
        # Ignores `namespace` -- looks the query up regardless of who is asking,
        # which is exactly the defect a namespace-isolation case exists to catch.
        doc_name = QUERY_TO_DOC[query]
        docs = _load_corpus()
        hit = SearchHit(hit_id="h1", content=docs[doc_name], source_path=f"{doc_name}.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.9, plan_id="fake-plan")

    report = run_regression([negative_control_case], leaky_fn)

    assert report.passed is False
    ((_, ok, detail),) = report.results
    assert ok is False
    assert "insufficient_evidence" in detail
