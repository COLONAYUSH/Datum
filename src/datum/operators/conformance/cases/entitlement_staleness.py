"""cases.entitlement_staleness: a stale entitlement snapshot must cause
exclusion, not inclusion.

FRAMEWORK.md's own addendum to CI-03 (`Operator` section, second callout):
the conformance suite as originally specified verifies that a predicate
operator translates a filter *correctly* -- it says nothing about whether
the entitlement data (role/trial/tier membership) the predicate evaluates
against is *current*. Identity/ACL-sync freshness stays explicit anti-scope
for Datum (it does not mirror an identity provider); this case only checks
that staleness is a typed, checkable, fail-closed condition rather than a
silent one -- a snapshot older than its declared `max_staleness` must
exclude every row it gates, never include one it can no longer vouch for.

The fresh-snapshot half of this check is not decoration: an operator that
excludes every row unconditionally would trivially pass the staleness half
while failing the actual contract (fail closed on staleness, not fail
closed on everything), so this case also asserts a fresh snapshot still
admits the rows it correctly grants.

Plain function, zero `import pytest` -- see cases/filter_algebra.py's module
docstring for why.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from datum.kernel.operator import Operator
from datum.kernel.plan import Budget
from datum.operators.conformance.types import (
    CaseResult,
    ConformanceFragment,
    EntitlementSnapshot,
    ProbeRow,
    make_record,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _row(row_id: str, role: str) -> ProbeRow:
    return ProbeRow(record=make_record(row_id, namespace="acme"), fields={"role": role})


def _row_missing_field(row_id: str) -> ProbeRow:
    """A row carrying no entitlement field at all -- distinct from a row whose
    field holds an ungranted value. An operator that trusts a row it has no
    entitlement data for is failing open on exactly the shape that never
    reaches the `granted` membership test, so this must be probed explicitly.
    """
    return ProbeRow(record=make_record(row_id, namespace="acme"), fields={})


def _execute(operator: Operator, fragment: ConformanceFragment) -> frozenset[str]:
    op_plan = operator.plan(fragment, Budget())
    candidates = operator.execute(op_plan)
    return frozenset(str(record.id) for record in candidates.records)


def check(operator: Operator) -> CaseResult:
    rows = (
        _row("e1", "finance-eu"),
        _row("e2", "finance-eu"),
        _row("e3", "legal-us"),
        # No `role` field at all: a fresh snapshot must still exclude it, because
        # the caller was granted only 'finance-eu' and this row carries no
        # entitlement the snapshot can vouch for. An operator that admits a
        # field-less row fails open here even with a perfectly fresh snapshot.
        _row_missing_field("e4"),
    )
    max_staleness = timedelta(minutes=15)

    stale = EntitlementSnapshot(
        granted=frozenset({"finance-eu"}),
        entitlement_field="role",
        as_of=_NOW - timedelta(hours=6),
        max_staleness=max_staleness,
        now=_NOW,
    )
    try:
        stale_returned = _execute(operator, ConformanceFragment(rows=rows, entitlement=stale))
    except Exception as exc:
        # A raise inside plan()/execute() must become a failed case, never an
        # uncaught exception that aborts ConformanceSuite.run() and denies the
        # caller a SuiteReport at register_operator() time.
        return CaseResult(
            name="entitlement_staleness",
            passed=False,
            detail=f"operator.plan()/execute() raised {exc!r} instead of returning",
        )
    if stale_returned:
        return CaseResult(
            name="entitlement_staleness",
            passed=False,
            detail=(
                f"stale entitlement snapshot (as_of 6h ago, max_staleness {max_staleness}) "
                f"still returned rows {sorted(stale_returned)} -- staleness must exclude, "
                "never include"
            ),
        )

    fresh = EntitlementSnapshot(
        granted=frozenset({"finance-eu"}),
        entitlement_field="role",
        as_of=_NOW - timedelta(minutes=1),
        max_staleness=max_staleness,
        now=_NOW,
    )
    try:
        fresh_returned = _execute(operator, ConformanceFragment(rows=rows, entitlement=fresh))
    except Exception as exc:
        return CaseResult(
            name="entitlement_staleness",
            passed=False,
            detail=f"operator.plan()/execute() raised {exc!r} instead of returning",
        )
    if fresh_returned != {"e1", "e2"}:
        return CaseResult(
            name="entitlement_staleness",
            passed=False,
            detail=(
                f"a fresh entitlement snapshot must still admit correctly granted rows -- "
                f"expected {{'e1', 'e2'}}, got {sorted(fresh_returned)} (an operator that "
                "excludes everything unconditionally would wrongly pass the staleness half "
                "of this case)"
            ),
        )

    return CaseResult(
        name="entitlement_staleness",
        passed=True,
        detail="stale snapshot excluded all rows; fresh snapshot correctly admitted only entitled rows.",
    )
