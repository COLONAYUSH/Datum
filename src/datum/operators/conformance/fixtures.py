"""The suite's own positive and negative controls.

`CorrectFixtureOperator` implements the `datum.kernel.operator.Operator`
Protocol faithfully against every probe field the four cases in `cases/`
define (filter, tenancy, entitlement) -- it exists so
`tests/conformance/test_suite_self_check.py` can prove `ConformanceSuite`
actually passes a conformant operator, not just fails a bad one.

`MistranslatingFixtureOperator` is the negative control this suite's own
credibility rests on: it implements generic filter algebra, score
reporting, and entitlement-staleness correctly (so it is not a strawman
that fails everything, which would prove nothing about localization) but
silently ignores `ConformanceFragment.tenancy` entirely -- exactly the
LangChain4j #2513 root cause named in FRAMEWORK.md's `Operator` section
("tenant-isolation filters silently disabled: failing open"). One
narrowly-scoped defect, injected on purpose, must fail exactly one case
(`tenancy_fail_closed`) and no other -- that is what
`test_suite_self_check.py` verifies.

# TODO(scratch-namespace provisioning): the one thing genuinely out of
# reach for synthetic fixtures is physical cross-namespace partition
# isolation -- FRAMEWORK.md's coarse-dimension partitioning half of
# Security & governance (namespace-per-tenant enforced at the storage
# layer, distinct from the predicate-layer fail-closed behavior these
# fixtures exercise). That needs real multi-tenant writepath data written
# across more than one physical namespace, and the in-package suite here
# stays infra-free by design (it must gate registration anywhere, with no
# database). RESOLVED at Milestone B (decisions.md #26): that live tier now
# lives in tests/conformance/test_live_tenancy.py -- real records in two
# namespaces run through each real operator's real query path, the check
# this synthetic layer structurally cannot make. Not faked here.
"""

from __future__ import annotations

from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.operators.conformance.types import ConformanceFragment, ProbeRow, evaluate_expr


def _included(fragment: ConformanceFragment, row: ProbeRow, *, honor_tenancy: bool) -> bool:
    """Shared inclusion logic for both fixtures. `honor_tenancy=False` is the
    one line that turns `CorrectFixtureOperator`'s logic into
    `MistranslatingFixtureOperator`'s -- everything else is identical, so
    the only behavioral difference between the two fixtures is exactly the
    one defect this module's docstring names.
    """
    if fragment.filter is not None and not evaluate_expr(fragment.filter, row.fields):
        return False
    if honor_tenancy and fragment.tenancy is not None:
        try:
            if not fragment.tenancy.evaluate(row):
                return False
        except Exception:
            return False  # unevaluable -> exclude, never include
    if fragment.entitlement is not None and not fragment.entitlement.permits(row):
        return False
    return True


class CorrectFixtureOperator:
    """The positive control. Implements the exact
    `datum.kernel.operator.Operator` shape -- `kind`, `plan()`, `execute()`,
    `cost_model()` -- with no extra methods, so passing this fixture is
    evidence the Protocol itself is sufficient for a conformant
    implementation, not evidence of some richer interface the suite
    secretly assumes.
    """

    kind = "conformance-fixture-correct"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget  # unused: this fixture has no budget-dependent behavior to plan against
        return OperatorPlan(
            operator_kind=self.kind,
            params={"fragment": fragment},
        )

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = [row for row in fragment.rows if _included(fragment, row, honor_tenancy=True)]
        return CandidateSet(
            records=tuple(row.record for row in kept),
            scores=tuple(row.relevance for row in kept),
            score_method=fragment.score_method,
        )

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class MistranslatingFixtureOperator:
    """The negative control. See this module's own docstring for exactly
    which single defect is injected and why.
    """

    kind = "conformance-fixture-mistranslating"

    def plan(self, fragment: ConformanceFragment, budget: Budget) -> OperatorPlan:
        del budget
        # This fixture's only defect is enforcement, not declaration: execute()
        # simply never applies the tenancy predicate. The suite tests observed
        # behavior, not a self-reported trust flag -- a checked "I fail closed"
        # claim is exactly the anti-pattern the whole design opposes -- so the
        # plan carries no such flag for either fixture.
        return OperatorPlan(
            operator_kind=self.kind,
            params={"fragment": fragment},
        )

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment: ConformanceFragment = op_plan.params["fragment"]
        kept = [row for row in fragment.rows if _included(fragment, row, honor_tenancy=False)]
        return CandidateSet(
            records=tuple(row.record for row in kept),
            scores=tuple(row.relevance for row in kept),
            score_method=fragment.score_method,
        )

    def cost_model(self, fragment: ConformanceFragment) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)
