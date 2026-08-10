"""Plan: compiled query, plan-selection-as-policy-slot, EXPLAIN, replay-by-record.

kernel stays zero-I/O: Plan here is the pure compiled *representation*
(steps, which policy chose the fusion, principal, budget) plus the three
methods FRAMEWORK.md's own sketch shows on a plan value — `explain()`
(formats fields the plan already carries), `execute()` (delegates to an
executor the planner BOUND at compile time; the kernel type never does I/O
itself, it only carries the callable), and `diff(other)` (pure field
comparison of two plans — the drift report separating "what happened" from
"what would happen now").

Two of the spec sketch's entry points are deliberately NOT classmethods
here (recorded as Decision 8 in docs/decisions.md): `Plan.compile(...)` and
`Plan.replay(...)` both require live runtime context (registered operators,
the trace store) — as classmethods they would force module-global mutable
state. They live on Corpus (`corpus.compile_plan(...)`, `corpus.replay(...)`)
which FRAMEWORK.md itself designates as the composition root; the spec's
own note says the CAL/compile surface is "optional expert plumbing — most
callers never write this."

`propensity` is 1.0 for every Plan at v1, honestly: the MVP's plan-selection
policy is a deterministic rule table, so there is no distribution over
actions to log a probability against. The field exists now so the trace
shape doesn't change when Phase 2 installs a stochastic policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Protocol

from datum.kernel.errors import DatumError
from datum.kernel.ids import PolicyID
from datum.kernel.principal import Principal

if TYPE_CHECKING:
    from datum.kernel.evidence import EvidenceState


@dataclass(frozen=True)
class Budget:
    """Doubles as a query-time spend limit and a View refresh budget —
    which fields are set depends on which caller constructs it.
    """

    tokens_max: int | None = None
    latency_ms_max: float | None = None
    dollars_max: float | None = None
    # index-time (View refresh) fields:
    dollars_per_hour: float | None = None
    tokens_per_doc_max: int | None = None
    degrade: tuple[str, ...] = ()  # e.g. ("full", "sampled_20pct", "skip")


@dataclass(frozen=True)
class PlanStep:
    op_name: str  # "search" | "rerank" | "acl_filter" | "sufficiency_check" | ...
    params: dict[str, Any] = field(default_factory=dict)
    fails_closed: bool = False  # True only for the acl_filter step


@dataclass(frozen=True)
class CostTrace:
    """>=95% of billed tokens attributable to a named stage is the v1
    production-metric target (FRAMEWORK.md, Evaluation plan). `by_stage`
    is what makes that number computable rather than asserted.
    """

    total_tokens: int
    total_dollars: float
    total_latency_ms: float
    by_stage: dict[str, float] = field(default_factory=dict)  # stage name -> tokens
    attributed_fraction: float = 1.0


# Fields excluded from diff(): identity/bookkeeping, not plan content.
_DIFF_EXCLUDED_FIELDS = frozenset({"plan_id", "created_at"})


@dataclass(frozen=True)
class Plan:
    plan_id: str
    steps: tuple[PlanStep, ...]
    plan_selector: str  # name@version of the Policy that produced this fusion
    principal: Principal
    budget: Budget
    policy_id: PolicyID
    created_at: datetime
    cost_trace: CostTrace | None = None
    propensity: float = 1.0  # trivial constant at v1 — see module docstring
    # Bound by planner.compiler at compile time; never constructed by hand.
    # compare=False keeps two otherwise-identical plans equal regardless of
    # which live executor instance they were bound to.
    executor: Callable[["Plan"], "EvidenceState"] | None = field(
        default=None, compare=False, repr=False
    )

    def explain(self) -> str:
        lines = [f"Plan(plan_id={self.plan_id!r}, plan_selector={self.plan_selector!r})"]
        for step in self.steps:
            marker = "  [fails closed]" if step.fails_closed else ""
            params = ", ".join(f"{k}={v!r}" for k, v in step.params.items())
            lines.append(f"  -> {step.op_name}({params}){marker}")
        return "\n".join(lines)

    def execute(self) -> "EvidenceState":
        if self.executor is None:
            raise DatumError(
                "This Plan is not bound to an executor. Plans obtained from "
                "corpus.compile_plan()/search() are executable; a Plan "
                "reconstructed by replay carries its persisted results and is "
                "not re-executed (that distinction is the point of "
                "replay-by-record — use corpus.replay(plan_id, "
                "against='current_champion') for an explicit re-execution)."
            )
        return self.executor(self)

    def diff(self, other: "Plan") -> dict[str, tuple[object, object]]:
        """Pure field-by-field drift report between two plans (e.g. a
        replayed historical plan vs. a re-execution under today's champion).
        Identity fields (plan_id, created_at) are excluded — two runs of
        anything differ on those; the report is about plan *content*.
        """
        out: dict[str, tuple[object, object]] = {}
        for f in fields(self):
            if f.name in _DIFF_EXCLUDED_FIELDS or not f.compare:
                continue
            mine, theirs = getattr(self, f.name), getattr(other, f.name)
            if mine != theirs:
                out[f.name] = (mine, theirs)
        return out


class PlanContext(Protocol):
    """What a plan-selection Policy sees. Internal to the policy-selection
    seam, not part of the kernel symbol budget (only Policy itself is).
    """

    principal: Principal
    budget: Budget
    available_operator_kinds: tuple[str, ...]


class FusionDecision(Protocol):
    """What a plan-selection Policy returns: which operators to run and
    how to weight/combine them. Internal, same reasoning as PlanContext.
    """

    operator_kinds: tuple[str, ...]
    fusion_weights: dict[str, float]
    rerank_depth: int


class Policy(Protocol):
    """The plan-selection slot. FRAMEWORK.md names this slot and its role
    ("a versioned Policy occupying a slot in the plan compiler") without a
    method signature; `select` is this implementation's first-draft
    interface (plan Decision 3) and may be revised once policy.rule_table
    is implemented against it.
    """

    name: str
    version: str

    def select(self, context: PlanContext) -> FusionDecision: ...
