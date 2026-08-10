"""Self-check: proves `ConformanceSuite` actually catches what it claims to.

This is the suite testing itself, not testing a real operator: the positive
control (`CorrectFixtureOperator`) must pass every case, and the negative
control (`MistranslatingFixtureOperator`) -- which implements everything
correctly except silently dropping the tenancy predicate, the LangChain4j
#2513 root cause -- must fail `tenancy_fail_closed` and *only*
`tenancy_fail_closed`. Asserting the exact set of failing case names, not
merely `report.passed is False`, is what actually proves the suite
localizes a defect rather than just noticing something, somewhere, broke.

pytest is used here, and only here, in this module's tree -- everything
under `datum.operators.conformance` itself is plain functions with zero
`import pytest`, so this suite is callable at production
`datum.register_operator()` time with no test-framework dependency; this
file only wraps that logic for CI visibility.
"""

from __future__ import annotations

from datum.operators.conformance.fixtures import CorrectFixtureOperator, MistranslatingFixtureOperator
from datum.operators.conformance.suite import ConformanceSuite

_ALL_CASE_NAMES = frozenset(
    {"filter_algebra", "score_contract", "tenancy_fail_closed", "entitlement_staleness"}
)


def _failing_case_names(report) -> frozenset[str]:
    return frozenset(result.name for result in report.results if not result.passed)


def test_correct_fixture_passes_every_case():
    report = ConformanceSuite.run(CorrectFixtureOperator())

    assert report.passed is True
    assert _failing_case_names(report) == frozenset()
    assert {result.name for result in report.results} == _ALL_CASE_NAMES


def test_mistranslating_fixture_fails_only_tenancy_fail_closed():
    report = ConformanceSuite.run(MistranslatingFixtureOperator())

    assert report.passed is False
    # The load-bearing assertion: exactly one case fails, and it is the one
    # whose defect this fixture actually has -- not "something is broken,"
    # but "this specific thing is broken and nothing else is."
    assert _failing_case_names(report) == frozenset({"tenancy_fail_closed"})

    by_name = {result.name: result for result in report.results}
    assert by_name["filter_algebra"].passed is True
    assert by_name["score_contract"].passed is True
    assert by_name["entitlement_staleness"].passed is True
    assert by_name["tenancy_fail_closed"].passed is False

    # And the failure detail actually names the mechanism, not just "failed".
    detail = by_name["tenancy_fail_closed"].detail
    assert "u1" in detail
    assert "LangChain4j" in detail


def test_suite_report_failures_property_matches_results():
    report = ConformanceSuite.run(MistranslatingFixtureOperator())

    assert report.failures == tuple(r for r in report.results if not r.passed)
    assert len(report.failures) == 1
    assert report.failures[0].name == "tenancy_fail_closed"
