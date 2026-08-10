"""Regression fixtures: one narrowly-broken operator per confirmed conformance
gap, each proving the corresponding case now catches the defect it previously
let through -- and, for the raising/fabricating/duplicating shapes, that
`ConformanceSuite.run()` returns a complete `SuiteReport` instead of aborting
with an uncaught exception.

Every operator here is a *localization* control, not a strawman: each fails
exactly one case, the one whose fix this file guards. Asserting the exact set
of failing case names (not merely `report.passed is False`) is what proves the
suite still pins a defect to its mechanism rather than noticing that something,
somewhere, broke -- the same discipline `test_suite_self_check.py` applies to
the shipped positive/negative controls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.operators.conformance import fixtures
from datum.operators.conformance.fixtures import CorrectFixtureOperator, _included
from datum.operators.conformance.suite import ConformanceSuite
from datum.operators.conformance.types import (
    BoolExpr,
    ConformanceFragment,
    _evaluate_predicate,
    evaluate_expr,
    make_record,
)


def _failing_case_names(report) -> frozenset[str]:
    return frozenset(result.name for result in report.results if not result.passed)


def _cost() -> CostEstimate:
    return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


# --------------------------------------------------------------------------
# FINDING 1: tenancy-channel `eq` leaves that always evaluate True.
# --------------------------------------------------------------------------


def _eval_eq_fail_open(expr: BoolExpr, fields) -> bool:
    """`types.evaluate_expr`, except every `eq` leaf short-circuits to True.
    Correct everywhere else -- the surgical defect a positive-match sub-check
    must catch and the unevaluable/NOT-IN sub-checks structurally cannot.
    """
    if expr.kind == "not":
        return not _eval_eq_fail_open(expr.children[0], fields)
    if expr.kind == "and":
        return all(_eval_eq_fail_open(child, fields) for child in expr.children)
    if expr.kind == "or":
        return any(_eval_eq_fail_open(child, fields) for child in expr.children)
    assert expr.predicate is not None
    if expr.predicate.op == "eq":
        return True
    return _evaluate_predicate(expr.predicate, fields)


class EqFailOpenTenancyOperator:
    """Honors the filter and entitlement channels correctly; applies the
    tenancy predicate but treats `eq` as always-True, so `tenant eq <mine>`
    admits every tenant -- a cross-tenant leak invisible to the NOT-IN and
    unevaluable probes.
    """

    kind = "test-eq-fail-open"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = []
        for row in fragment.rows:
            if fragment.filter is not None and not evaluate_expr(fragment.filter, row.fields):
                continue
            if fragment.tenancy is not None:
                if str(row.record.id) in fragment.tenancy.unevaluable_row_ids:
                    continue  # exclude on unevaluable -- correct
                if not _eval_eq_fail_open(fragment.tenancy.filter, row.fields):
                    continue
            if fragment.entitlement is not None and not fragment.entitlement.permits(row):
                continue
            kept.append(row)
        return CandidateSet(
            records=tuple(row.record for row in kept),
            scores=tuple(row.relevance for row in kept),
            score_method=fragment.score_method,
        )

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return _cost()


def test_eq_fail_open_fails_only_tenancy():
    report = ConformanceSuite.run(EqFailOpenTenancyOperator())

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({"tenancy_fail_closed"})
    detail = {r.name: r.detail for r in report.results}["tenancy_fail_closed"]
    assert "positive-match" in detail


# --------------------------------------------------------------------------
# FINDING 2: rows lacking the entitlement field admitted unconditionally.
# --------------------------------------------------------------------------


class MissingEntitlementFieldFailOpenOperator:
    """Honors filter and tenancy correctly; on the entitlement channel it
    admits any row that simply lacks the entitlement field, trusting a row it
    has no entitlement data for -- fail-open on the shape that never reaches
    the `granted` membership test.
    """

    kind = "test-missing-entitlement-fail-open"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = []
        for row in fragment.rows:
            if fragment.filter is not None and not evaluate_expr(fragment.filter, row.fields):
                continue
            if fragment.tenancy is not None:
                try:
                    if not fragment.tenancy.evaluate(row):
                        continue
                except Exception:
                    continue
            if fragment.entitlement is not None:
                if fragment.entitlement.entitlement_field not in row.fields:
                    pass  # BUG: no entitlement data -> admit anyway
                elif not fragment.entitlement.permits(row):
                    continue
            kept.append(row)
        return CandidateSet(
            records=tuple(row.record for row in kept),
            scores=tuple(row.relevance for row in kept),
            score_method=fragment.score_method,
        )

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return _cost()


def test_missing_entitlement_field_fail_open_fails_only_entitlement():
    report = ConformanceSuite.run(MissingEntitlementFieldFailOpenOperator())

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({"entitlement_staleness"})


# --------------------------------------------------------------------------
# FINDINGS 3 + 6: an operator that raises inside plan()/execute() must become a
# failed case, never an uncaught exception that aborts ConformanceSuite.run().
# One parameterizable raiser, driven three ways.
# --------------------------------------------------------------------------


class RaisingOperator:
    """Behaves correctly except it raises on one probe shape -- the shape a
    given unguarded case used to hand it. `run()` must still return a report.
    """

    kind = "test-raising"

    def __init__(self, raise_on: str) -> None:
        self.raise_on = raise_on

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        if self.raise_on == "tenancy" and fragment.tenancy is not None:
            raise NotImplementedError("tenancy channel not implemented")
        if self.raise_on == "entitlement" and fragment.entitlement is not None:
            raise RuntimeError("entitlement channel exploded")
        if (
            self.raise_on == "filterless"
            and fragment.filter is None
            and fragment.tenancy is None
            and fragment.entitlement is None
        ):
            raise RuntimeError("cannot handle a filter-less fragment")
        kept = [row for row in fragment.rows if _included(fragment, row, honor_tenancy=True)]
        return CandidateSet(
            records=tuple(row.record for row in kept),
            scores=tuple(row.relevance for row in kept),
            score_method=fragment.score_method,
        )

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return _cost()


@pytest.mark.parametrize(
    "raise_on, expected_case",
    [
        ("tenancy", "tenancy_fail_closed"),
        ("filterless", "score_contract"),
        ("entitlement", "entitlement_staleness"),
    ],
)
def test_raising_operator_yields_failed_case_not_crash(raise_on, expected_case):
    # The load-bearing property: run() RETURNS rather than propagating the raise.
    report = ConformanceSuite.run(RaisingOperator(raise_on=raise_on))

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({expected_case})
    assert len(report.results) == 4  # a complete report, no case skipped
    detail = {r.name: r.detail for r in report.results}[expected_case]
    assert "raised" in detail


# --------------------------------------------------------------------------
# FINDING 5: a fabricated record (an id the probe never supplied) is a leak
# shape and previously crashed the monotonic loop with a KeyError.
# --------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _is_score_contract_shape(fragment: ConformanceFragment) -> bool:
    """The score_contract probe is the only fragment with no filter/tenancy/
    entitlement gate at all; restricting the score-shape defects to it keeps
    these operators failing exactly one case."""
    return fragment.filter is None and fragment.tenancy is None and fragment.entitlement is None


class FabricatedRecordOperator:
    """On the score_contract probe, invents a record the probe never supplied."""

    kind = "test-fabricated-record"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = [row for row in fragment.rows if _included(fragment, row, honor_tenancy=True)]
        records = [row.record for row in kept]
        scores = [row.relevance for row in kept]
        if _is_score_contract_shape(fragment):
            records.append(make_record("ghost", namespace="acme"))
            scores.append(0.99)
        return CandidateSet(records=tuple(records), scores=tuple(scores), score_method=fragment.score_method)

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return _cost()


def test_fabricated_record_fails_score_contract_without_crash():
    report = ConformanceSuite.run(FabricatedRecordOperator())  # must not raise KeyError

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({"score_contract"})
    detail = {r.name: r.detail for r in report.results}["score_contract"]
    assert "fabricated" in detail
    assert "ghost" in detail


# --------------------------------------------------------------------------
# FINDING 14: the same record returned twice with two different scores used to
# collapse to last-write-wins in a plain dict and pass silently.
# --------------------------------------------------------------------------


class DuplicateRecordOperator:
    """On the score_contract probe, returns its first record twice under two
    different scores."""

    kind = "test-duplicate-record"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = [row for row in fragment.rows if _included(fragment, row, honor_tenancy=True)]
        records = [row.record for row in kept]
        scores = [row.relevance for row in kept]
        if _is_score_contract_shape(fragment) and kept:
            records.append(kept[0].record)  # duplicate id
            scores.append(kept[0].relevance + 0.05)  # ... at a different score
        return CandidateSet(records=tuple(records), scores=tuple(scores), score_method=fragment.score_method)

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return _cost()


def test_duplicate_record_fails_score_contract_without_crash():
    report = ConformanceSuite.run(DuplicateRecordOperator())

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({"score_contract"})
    detail = {r.name: r.detail for r in report.results}["score_contract"]
    assert "duplicate" in detail


# --------------------------------------------------------------------------
# FINDING 15: no case reads a self-reported fail-closed flag from the plan, and
# neither fixture emits one -- the suite tests behavior, not trust claims.
# --------------------------------------------------------------------------


def test_fixtures_carry_no_self_reported_trust_flag():
    from datum.operators.conformance.fixtures import MistranslatingFixtureOperator

    for operator in (CorrectFixtureOperator(), MistranslatingFixtureOperator()):
        op_plan = operator.plan(ConformanceFragment(rows=()), Budget())
        assert set(op_plan.params) == {"fragment"}
        assert "fails_closed" not in op_plan.params


# --------------------------------------------------------------------------
# FINDING 18: filter_algebra's expected sets must be independent of the oracle
# the operator uses for inclusion, so an oracle-level bug in the operator is
# caught rather than self-certified by a co-recomputed expected set.
# --------------------------------------------------------------------------


def test_every_scenario_has_a_hand_derived_expected_set():
    from datum.operators.conformance.cases import filter_algebra

    # The expected sets are concrete literal frozensets keyed 1:1 to the
    # scenarios -- not a comprehension over the oracle. This guards the
    # realistic Finding-18 regression: a scenario added to _scenarios() without
    # a matching hand-derived expectation, which the source now turns into a
    # failed case rather than a KeyError that aborts run().
    assert set(filter_algebra._EXPECTED) == set(filter_algebra._scenarios())
    assert all(isinstance(v, frozenset) for v in filter_algebra._EXPECTED.values())


def test_filter_algebra_catches_an_operator_whose_oracle_is_wrong(monkeypatch):
    # Break the operator's inclusion oracle (its own copy of evaluate_expr, used
    # only for the filter channel). If filter_algebra's expected sets were still
    # recomputed from this same oracle, operator and expectation would be wrong
    # in lockstep and the case would pass -- the circularity Finding 18 names.
    # With hard-coded expectations it must instead FAIL, and only here.
    monkeypatch.setattr(fixtures, "evaluate_expr", lambda expr, fields: True)

    report = ConformanceSuite.run(CorrectFixtureOperator())

    assert report.passed is False
    assert _failing_case_names(report) == frozenset({"filter_algebra"})
