"""RuleTablePolicy: v1's plan-selection policy — a declared, dated, static
rule table occupying the fusion-weight slot in the Plan Compiler.

This is the "optimizer demoted to a policy" resolution (FRAMEWORK.md §Design
axioms): plan-selection is a versioned Policy in a slot, and v1 fills that slot
with zero learned or cost-based components — a hand-declared table. Shipping
the *interface commitment* (a slot exists; EXPLAIN and replay work) without
waiting on optimizer research is the single most important MVP-scoping
decision the design names. Phase 2 replaces the table behind this same slot
with a promotion-gated learned policy; nothing above the slot changes.

`name`/`version` are dated so a trace records exactly which selection rule
produced a plan (CI-14: defaults are declared and dated, never a frozen
mystery).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Fusion:
    """A concrete FusionDecision (kernel.plan.FusionDecision): which operators
    to run and how to combine them.

    `abstain_min_similarity` is the evidence-sufficiency floor: if the best
    dense (cosine) similarity among the fused candidates is below it, the plan
    ABSTAINS (returns insufficient_evidence) rather than surfacing whatever the
    always-returns-something ANN operator ranked first. None disables the check
    (e.g. a grep+BM25-only deployment with no dense signal to threshold on).
    """

    operator_kinds: tuple[str, ...]
    fusion_weights: dict[str, float] = field(default_factory=dict)
    rerank_depth: int = 0
    abstain_min_similarity: float | None = None


class _SelectionContext(Protocol):
    available_operator_kinds: tuple[str, ...]


class RuleTablePolicy:
    name = "rule-table"
    version = "2026-08-11"

    #: The declared table, Milestone B edition: grep + BM25 + ANN fused by
    #: weighted reciprocal-rank fusion in the compiler. Equal weights are the
    #: honest hand declaration — no tuning data exists yet to justify others;
    #: Phase 2's promotion loop earns changes to this table, nothing else does.
    _WEIGHTS = {"grep": 1.0, "bm25": 1.0, "ann": 1.0}

    #: How many fused candidates the cross-encoder re-scores — and, when a
    #: real reranker is active, the final candidate count (decisions.md #22).
    #: Hand-declared: deep enough that fusion recall feeds it, small enough
    #: that a CPU cross-encoder answers interactively.
    _RERANK_DEPTH = 16

    #: The abstention floor on top dense cosine similarity (decisions.md #29).
    #: UNLIKE the weights and rerank depth above (declared before any fixture
    #: existed), this value is READ OFF the eval fixture — on that 11-case /
    #: 5-document set, genuine matches score >= 0.669 dense cosine and
    #: out-of-corpus queries <= 0.606, a 0.06 gap; 0.63 sits inside it. It is
    #: therefore fixture-derived and uncalibrated: real calibration on a
    #: held-out slice is Phase 1 (the sufficiency score it complements is
    #: `calibrated=False` for the same reason). The margin is thin — the
    #: jargon-heavy circuit-breaker/backoff queries (dense ~0.67) are the
    #: closest positives and will be the first to abstain wrongly as the
    #: corpus grows, which is the signal that calibration is overdue.
    _ABSTAIN_MIN_SIMILARITY = 0.63

    def select(self, context: _SelectionContext) -> Fusion:
        available = tuple(k for k in self._WEIGHTS if k in context.available_operator_kinds)
        if not available:
            available = context.available_operator_kinds
        weights = {k: self._WEIGHTS.get(k, 1.0) for k in available}
        # The floor only applies when a dense operator is present to produce a
        # similarity to threshold on; grep/BM25-only has no such signal.
        abstain = self._ABSTAIN_MIN_SIMILARITY if "ann" in available else None
        return Fusion(
            operator_kinds=available,
            fusion_weights=weights,
            rerank_depth=self._RERANK_DEPTH,
            abstain_min_similarity=abstain,
        )
