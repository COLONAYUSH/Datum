"""Datum: a retrieval substrate for the agentic era.

`__all__` below IS the budgeted kernel surface FRAMEWORK.md pins at 35
counted / 40 budgeted symbols. It is meant to be diffed in CI against the
previous minor version's `__all__`: a new top-level symbol failing that diff
is axiom 8's semver-stability gate working as designed, not a bug to route
around.

This file grows as each build milestone lands (see the implementation
plan) — Corpus and HitRegistry are added once corpus.py and
mcp_server/hit_registry.py exist (Milestone A), not before. That growth is
itself tracked, not silent: each addition here is one commit, reviewable on
its own.

DEFERRED (pre-budgeted by FRAMEWORK.md, not built at v1 — declared here so
adding them later is accounted-for headroom, not a surprise):
    ConsolidationView   -- no consolidate() WriteOp at v1 (Phase 1)
    GovernedProfile      -- the formal deployment-refusal engine (Phase 1)
    DriftMonitor          -- the learning/promotion loop's poisoning monitor (Phase 2)
    PromptArtifact         -- no LLM-mediated enrichment View exists at v1 to register one against

DECISION 6 (implementation note, not in FRAMEWORK.md): four purely-structural
helper types that exist only as fields on already-budgeted types
(StructuredBody, TableCell, PlanStep, LineageEdge) are intentionally NOT
re-exported here, to keep the top-level surface close to the plan's counted
list. They remain reachable via their owning submodule. The five exception
types (DatumError and its four subclasses) ARE kept at top level despite not
being part of FRAMEWORK.md's original 35-symbol count, because catching a
specific exception type is a normal part of a Python library's public
contract, not incidental surface area — this is flagged here rather than
silently exceeding the budget without comment, and means the real ceiling
this build tracks against is 35 (original) + 5 (exceptions) = 40, with the
four DEFERRED symbols above needing that number to hold at exactly 40, not
grow further, once they land.
"""

from datum.kernel import (
    AdmissionError,
    BoundingBox,
    Budget,
    BudgetExhaustedError,
    CalibratedScore,
    CandidateSet,
    ChangeSet,
    Conflict,
    ConformanceError,
    CostEstimate,
    CostTrace,
    DatumError,
    ErasureReceipt,
    Evidence,
    EvidenceItem,
    EvidenceState,
    LineageManifest,
    Operator,
    OperatorPlan,
    Plan,
    Policy,
    PolicyID,
    Principal,
    PrincipalResolutionError,
    ProvenanceCapsule,
    Record,
    RecordID,
    SearchHit,
    Span,
    StructureView,
    View,
    WriteOp,
    WritePolicy,
)

from datum.corpus import Corpus
from datum.mcp_server.hit_registry import HitRegistry
from datum.operators.conformance.suite import ConformanceSuite

__version__ = "0.1.0"

__all__ = [
    "AdmissionError",
    "BoundingBox",
    "Budget",
    "BudgetExhaustedError",
    "CalibratedScore",
    "CandidateSet",
    "ChangeSet",
    "Conflict",
    "ConformanceError",
    "CostEstimate",
    "CostTrace",
    "DatumError",
    "ErasureReceipt",
    "Evidence",
    "EvidenceItem",
    "EvidenceState",
    "LineageManifest",
    "Operator",
    "OperatorPlan",
    "Plan",
    "Policy",
    "PolicyID",
    "Principal",
    "PrincipalResolutionError",
    "ProvenanceCapsule",
    "Record",
    "RecordID",
    "SearchHit",
    "Span",
    "StructureView",
    "View",
    "WriteOp",
    "WritePolicy",
    # Composition root + budgeted non-kernel public symbols (landed at
    # Milestone A / the parallel wave). These three are part of FRAMEWORK.md's
    # 35-symbol count; see docs/decisions.md #6 for the full budget accounting.
    "ConformanceSuite",
    "Corpus",
    "HitRegistry",
]
