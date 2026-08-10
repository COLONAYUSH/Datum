"""cases.filter_algebra: boolean nesting, negation, IN/NOT-IN, datetime/tz
comparison, and null handling against an Operator's real `plan()`/`execute()`.

This is CI-03's "next-gen requirement" read literally: "golden filter queries
return identical result sets across all shipped backends in CI; a
mistranslating backend cannot ship." `check()` builds a small synthetic row
corpus, computes the expected result set with the plain boolean/null oracle
in `conformance.types.evaluate_expr`, and asserts an Operator's `execute()`
returns exactly that set for each scenario — not a superset, not a subset.

Plain function, zero `import pytest`: `datum.register_operator()` (built by
a different module) calls this suite at runtime in production with no
test-framework dependency. Pytest only wraps `check()` for CI visibility —
see tests/conformance/test_suite_self_check.py — it does not contain any of
this module's logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from datum.kernel.operator import Operator
from datum.kernel.plan import Budget
from datum.operators.conformance.types import (
    BoolExpr,
    CaseResult,
    ConformanceFragment,
    ProbeRow,
    make_record,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _row(row_id: str, **fields: Any) -> ProbeRow:
    return ProbeRow(record=make_record(row_id, namespace="acme"), fields=fields)


def _scenario_rows() -> tuple[ProbeRow, ...]:
    return (
        _row("r1", department="finance", tier=2, region="EMEA", created_at=_NOW - timedelta(days=1)),
        _row("r2", department="finance", tier=1, region="AMER", created_at=_NOW - timedelta(days=400)),
        _row("r3", department="legal", tier=3, region="EMEA", created_at=_NOW - timedelta(hours=2)),
        _row("r4", department="legal", tier=2, region=None, created_at=_NOW),
        _row("r5", department="hr", tier=1, region="APAC", created_at=None),
    )


def _scenarios() -> dict[str, BoolExpr]:
    return {
        "and_or_nesting": BoolExpr.or_(
            BoolExpr.and_(
                BoolExpr.leaf("department", "eq", "finance"),
                BoolExpr.leaf("tier", "gte", 2),
            ),
            BoolExpr.leaf("department", "eq", "legal"),
        ),
        "negation": BoolExpr.not_(BoolExpr.leaf("department", "eq", "finance")),
        "in": BoolExpr.leaf("region", "in", ("EMEA", "APAC")),
        "not_in": BoolExpr.leaf("region", "not_in", ("EMEA",)),
        # datetime/tz: mixes a tz-aware cutoff against tz-aware row values.
        "datetime_tz": BoolExpr.leaf("created_at", "gt", _NOW - timedelta(days=30)),
        "null_is_null": BoolExpr.leaf("region", "is_null"),
        # A NOT-IN evaluated against a row whose comparison field is missing
        # entirely -- the null-handling nuance that made LangChain4j #2513's
        # NOT-IN mistranslation dangerous rather than merely wrong.
        "null_not_in_excludes_missing": BoolExpr.and_(
            BoolExpr.leaf("department", "eq", "hr"),
            BoolExpr.leaf("created_at", "not_in", (_NOW,)),
        ),
    }


# The expected id-set per scenario, written out by hand rather than recomputed
# with `evaluate_expr`. This is deliberate: `CorrectFixtureOperator` already
# derives its inclusion logic from `evaluate_expr`, so recomputing the oracle
# here would make the positive control circular -- any bug in `evaluate_expr`
# would self-certify (the operator and the "expected" set would be wrong in
# lockstep and still match). Hard-coding the literal sets makes this case prove
# the oracle's boolean/IN/NOT-IN/null semantics are right, rather than assume
# them. Keyed to `_scenario_rows()`; if either the rows or the scenarios change
# these must be re-derived by hand, on purpose.
_EXPECTED: dict[str, frozenset[str]] = {
    "and_or_nesting": frozenset({"r1", "r3", "r4"}),
    "negation": frozenset({"r3", "r4", "r5"}),
    "in": frozenset({"r1", "r3", "r5"}),
    # r4 (region=None) is excluded: NOT-IN over a missing/None field is never a
    # match, the LangChain4j #2513 null nuance this suite exists to pin.
    "not_in": frozenset({"r2", "r5"}),
    "datetime_tz": frozenset({"r1", "r3", "r4"}),
    "null_is_null": frozenset({"r4"}),
    # Empty on purpose: r5 is `hr` but its `created_at` is None, so the NOT-IN
    # leaf is False and the AND collapses -- a missing field does not match a
    # NOT-IN. This empty expectation is a meaningful assertion only because the
    # sibling scenarios above are non-empty (a return-nothing operator fails
    # those); do not delete a sibling without restoring that coverage.
    "null_not_in_excludes_missing": frozenset(),
}


def _run(operator: Operator, rows: tuple[ProbeRow, ...], expr: BoolExpr) -> frozenset[str]:
    fragment = ConformanceFragment(rows=rows, filter=expr)
    op_plan = operator.plan(fragment, Budget())
    candidates = operator.execute(op_plan)
    return frozenset(str(record.id) for record in candidates.records)


def check(operator: Operator) -> CaseResult:
    rows = _scenario_rows()
    scenarios = _scenarios()

    failures: list[str] = []
    for name, expr in scenarios.items():
        expected = _EXPECTED.get(name)
        if expected is None:
            # A scenario with no hand-derived expectation is a maintenance bug,
            # not an operator defect -- but it must surface as a failed case, not
            # a KeyError that aborts ConformanceSuite.run() and denies a caller
            # any SuiteReport (the no-raise contract cases 3/6 exist to hold).
            failures.append(f"{name}: no hand-derived expected id-set in _EXPECTED")
            continue
        try:
            actual = _run(operator, rows, expr)
        except Exception as exc:
            failures.append(f"{name}: operator.plan()/execute() raised {exc!r} instead of returning")
            continue
        if actual != expected:
            failures.append(f"{name}: expected {sorted(expected)}, got {sorted(actual)}")

    if failures:
        return CaseResult(name="filter_algebra", passed=False, detail="; ".join(failures))
    return CaseResult(
        name="filter_algebra",
        passed=True,
        detail=f"{len(scenarios)} filter-algebra scenarios matched plain boolean/null semantics exactly.",
    )
