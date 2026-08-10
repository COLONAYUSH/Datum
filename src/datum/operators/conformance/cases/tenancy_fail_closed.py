"""cases.tenancy_fail_closed: the direct fix for the LangChain4j #2513 /
Spring AI #3577 class of bug -- a filter that fails OPEN (silently matches
everything) instead of closed when the tenancy/namespace predicate cannot
be evaluated cleanly.

Two sub-checks, folded into one CaseResult because both exercise the same
fail-closed obligation at the tenancy/ACL layer, through the two mechanisms
that class of bug actually took in production:

  (a) unevaluable -- the tenancy predicate cannot be evaluated for a given
      row at all (an entitlement lookup fails or the row lacks data the
      predicate needs). The row must be excluded, not guessed at.
  (b) not-in-chained -- LangChain4j #2513 itself: a NOT-IN clause chained at
      the end of an AND expression generated SQL that matched every row.
      This reproduces that exact shape against
      `ConformanceFragment.tenancy.filter`, deliberately NOT the generic
      `ConformanceFragment.filter` cases/filter_algebra.py already covers --
      a passing filter_algebra result must never be read as "tenancy-safe,"
      and this case is what makes that true rather than assumed.

Plain function, zero `import pytest` -- see cases/filter_algebra.py's module
docstring for why.
"""

from __future__ import annotations

from datum.kernel.operator import Operator
from datum.kernel.plan import Budget
from datum.operators.conformance.types import (
    BoolExpr,
    CaseResult,
    ConformanceFragment,
    ProbeRow,
    TenancyPredicate,
    make_record,
)


def _row(row_id: str, tenant: str) -> ProbeRow:
    return ProbeRow(record=make_record(row_id, namespace=tenant), fields={"tenant": tenant})


class _OperatorRaised(Exception):
    """Wraps an exception an operator threw inside plan()/execute(), so each
    sub-check can turn it into a failure message rather than letting it abort
    ConformanceSuite.run() -- a crashed tenancy gate is indistinguishable from
    an absent one, exactly the fail-open shape this case exists to catch.
    """


def _execute(operator: Operator, fragment: ConformanceFragment) -> frozenset[str]:
    try:
        op_plan = operator.plan(fragment, Budget())
        candidates = operator.execute(op_plan)
    except Exception as exc:
        raise _OperatorRaised(f"operator.plan()/execute() raised {exc!r} instead of returning") from exc
    return frozenset(str(record.id) for record in candidates.records)


def _check_positive_match(operator: Operator) -> str | None:
    """A tenancy predicate that positively selects the caller's own tenant must
    return exactly the matching rows and exclude every other tenant. Without
    this, an operator whose tenancy-channel leaves always evaluate True fails
    open on a plain `tenant eq <mine>` predicate -- it passes the unevaluable
    and NOT-IN sub-checks (neither uses a positive `eq`/`in` leaf) yet leaks
    every cross-tenant row. Covers both the `eq` and `in` selection shapes.
    """
    rows = (
        _row("p1", "tenant-a"),
        _row("p2", "tenant-a"),
        _row("p3", "tenant-b"),
        _row("p4", "tenant-c"),
    )
    checks = (
        ("eq", BoolExpr.leaf("tenant", "eq", "tenant-a"), {"p1", "p2"}),
        ("in", BoolExpr.leaf("tenant", "in", ("tenant-a", "tenant-b")), {"p1", "p2", "p3"}),
    )
    for shape, expr, expected in checks:
        try:
            returned = _execute(operator, ConformanceFragment(rows=rows, tenancy=TenancyPredicate(filter=expr)))
        except _OperatorRaised as exc:
            return str(exc)
        if returned != expected:
            leaked = sorted(returned - expected)
            return (
                f"positive-match tenancy predicate (tenant {shape} own-tenant) returned "
                f"{sorted(returned)}, expected {sorted(expected)}"
                + (f" -- leaked cross-tenant rows {leaked}, failing OPEN" if leaked else "")
            )
    return None


def _check_unevaluable(operator: Operator) -> str | None:
    rows = (
        _row("u1", "tenant-a"),
        _row("u2", "tenant-a"),
        _row("u3", "tenant-b"),
    )
    tenancy = TenancyPredicate(
        filter=BoolExpr.leaf("tenant", "eq", "tenant-a"),
        unevaluable_row_ids=frozenset({"u1"}),
    )
    try:
        returned = _execute(operator, ConformanceFragment(rows=rows, tenancy=tenancy))
    except _OperatorRaised as exc:
        return str(exc)
    if "u1" in returned:
        return (
            "row 'u1' has an unevaluable tenancy predicate (simulated entitlement-lookup "
            "failure) and was still returned -- failing OPEN, not closed"
        )
    return None


def _check_not_in_chained(operator: Operator) -> str | None:
    rows = (
        _row("n1", "tenant-a"),  # excluded tenant -- must never appear in output
        _row("n2", "tenant-a"),
        _row("n3", "tenant-b"),
        _row("n4", "tenant-c"),
    )
    # The exact LangChain4j #2513 shape: an ordinary predicate AND'd with a
    # NOT-IN clause chained at the end.
    tenancy = TenancyPredicate(
        filter=BoolExpr.and_(
            BoolExpr.leaf("tenant", "is_not_null"),
            BoolExpr.leaf("tenant", "not_in", ("tenant-a",)),
        )
    )
    try:
        returned = _execute(operator, ConformanceFragment(rows=rows, tenancy=tenancy))
    except _OperatorRaised as exc:
        return str(exc)
    leaked = sorted(returned & {"n1", "n2"})
    if leaked:
        return (
            f"NOT-IN tenancy filter chained at the end of an AND expression silently matched "
            f"excluded rows {leaked} -- the exact LangChain4j #2513 failure shape"
        )
    if returned != {"n3", "n4"}:
        return f"expected exactly {{'n3', 'n4'}} to remain, got {sorted(returned)}"
    return None


def check(operator: Operator) -> CaseResult:
    failures = [
        message
        for message in (
            _check_positive_match(operator),
            _check_unevaluable(operator),
            _check_not_in_chained(operator),
        )
        if message is not None
    ]
    if failures:
        return CaseResult(name="tenancy_fail_closed", passed=False, detail=" | ".join(failures))
    return CaseResult(
        name="tenancy_fail_closed",
        passed=True,
        detail=(
            "positive-match tenancy predicate returned exactly its own tenant's rows; "
            "unevaluable tenancy predicate excluded its row; NOT-IN chained at the end of an "
            "AND expression did not silently match everything."
        ),
    )
