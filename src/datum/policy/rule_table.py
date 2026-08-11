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

    #: The per-source depth the cross-encoder pool draws from — the fused
    #: top-N unioned with each operator's OWN top-N (decisions.md #22,
    #: revised #38: a plain fused-order cut let a single operator's #1 pick
    #: be buried below the cut by candidates several operators mildly agree
    #: on). Hand-declared: deep enough that fusion recall feeds it, small
    #: enough that a CPU cross-encoder answers interactively even with the
    #: union's larger pool.
    _RERANK_DEPTH = 16

    #: Default abstention floor on top dense cosine similarity, and WHY it is
    #: a constructor parameter, not one hard number (decisions.md #29, revised
    #: #34). Real multi-corpus stress-testing proved a single global floor
    #: cannot work: the absolute cosine SCALE is corpus-dependent (a diverse
    #: 19-page report's genuine matches sit ~0.44–0.55 dense cosine; a small
    #: homogeneous policy corpus's sit ~0.53–0.75), and the two ranges do not
    #: share a threshold — a floor that abstains one corpus's out-of-corpus
    #: queries wrongly abstains the other's real answers. So the floor is
    #: PER-DEPLOYMENT: this default (0.44) is recall-biased for a diverse
    #: corpus (for a retrieval substrate feeding an LLM, a false abstention —
    #: refusing when the answer is present — is worse than returning weak
    #: evidence the model can judge), and a deployment raises it for a
    #: homogeneous corpus. Auto-derivation from each namespace's own
    #: similarity distribution is the Phase-1 replacement for hand-setting it.
    _ABSTAIN_MIN_SIMILARITY = 0.44

    def __init__(
        self,
        abstain_min_similarity: float | None = None,
        overrides: dict[str, dict] | None = None,
    ) -> None:
        self._abstain_min_similarity = (
            self._ABSTAIN_MIN_SIMILARITY
            if abstain_min_similarity is None
            else abstain_min_similarity
        )
        # Per-namespace calibrated parameters (decisions.md #44): the OUTPUT of
        # `datum calibrate`, loaded from the policy_overrides table at wiring
        # time. Keys: fusion_weights (dict), abstain_min_similarity (float).
        # A namespace without an override gets the hand-declared defaults —
        # calibration EARNS changes to this table per corpus; nothing else does
        # (the same promotion discipline the Phase-2 learned policy will use).
        self._overrides = overrides or {}

    def select(self, context: _SelectionContext) -> Fusion:
        available = tuple(k for k in self._WEIGHTS if k in context.available_operator_kinds)
        if not available:
            available = context.available_operator_kinds
        override = self._overrides.get(getattr(context, "namespace", None) or "", {})
        base_weights = override.get("fusion_weights", self._WEIGHTS)
        weights = {k: base_weights.get(k, self._WEIGHTS.get(k, 1.0)) for k in available}
        floor = override.get("abstain_min_similarity", self._abstain_min_similarity)
        # The floor only applies when a dense operator is present to produce a
        # similarity to threshold on; grep/BM25-only has no such signal.
        abstain = floor if "ann" in available else None
        return Fusion(
            operator_kinds=available,
            fusion_weights=weights,
            rerank_depth=self._RERANK_DEPTH,
            abstain_min_similarity=abstain,
        )
