"""Operator: the conformance-gated physical operator contract (L5).

An Operator cannot be registered without first passing
operators.conformance.suite.ConformanceSuite.run() — that gate lives at the
call site of datum.register_operator(), not here; this module only pins the
shape every operator (grep, BM25, ANN, and anything a third party adds later)
must implement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from datum.kernel.plan import Budget
from datum.kernel.record import Record


@dataclass(frozen=True)
class OperatorPlan:
    """What Operator.plan() commits to before execute() runs — the piece of
    the compiled Plan (kernel.plan.Plan) that is this operator's own step.
    """

    operator_kind: str
    params: dict[str, Any] = field(default_factory=dict)
    estimated_cost: "CostEstimate | None" = None


@dataclass(frozen=True)
class CandidateSet:
    """Raw operator output before evidence.wrap.py turns it into an EvidenceState."""

    records: tuple[Record, ...]
    scores: tuple[float, ...]  # same length as records; NOT assumed comparable across operators
    score_method: str  # e.g. "bm25", "cosine" — declared, never silently mixed


@dataclass(frozen=True)
class CostEstimate:
    tokens: int = 0
    dollars: float = 0.0
    latency_ms: float = 0.0


class Operator(Protocol):
    kind: str

    def plan(self, fragment: Any, budget: Budget) -> OperatorPlan: ...

    def execute(self, op_plan: OperatorPlan) -> CandidateSet: ...

    def cost_model(self, fragment: Any) -> CostEstimate: ...
