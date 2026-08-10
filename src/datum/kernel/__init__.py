"""datum.kernel: pure typed contracts. Zero I/O, zero logic, by construction.

Every symbol re-exported here is part of the semver-frozen kernel surface
(see datum/__init__.py's __all__ and the kernel symbol budget table there).
Nothing in this package imports from storage, groundstore, writepath,
derivation, operators, planner, evidence, security, eval, or mcp_server —
that one-directional rule is what makes each of those layers testable in
isolation against kernel fakes.
"""

from datum.kernel.errors import (
    AdmissionError,
    BudgetExhaustedError,
    ConformanceError,
    DatumError,
    PrincipalResolutionError,
)
from datum.kernel.evidence import CalibratedScore, Conflict, EvidenceItem, EvidenceState
from datum.kernel.ids import PolicyID, RecordID
from datum.kernel.lineage import LineageManifest
from datum.kernel.operator import CandidateSet, CostEstimate, Operator, OperatorPlan
from datum.kernel.plan import Budget, CostTrace, Plan, Policy
from datum.kernel.principal import Principal
from datum.kernel.record import BoundingBox, ProvenanceCapsule, Record, Span
from datum.kernel.surface import ChangeSet, Evidence, SearchHit, StructureView
from datum.kernel.view import View
from datum.kernel.writeop import ErasureReceipt, WriteOp, WritePolicy

# Structural helper types (StructuredBody, TableCell, PlanStep, LineageEdge) are
# deliberately NOT re-exported at top level — see Decision 6 in the
# implementation notes. They stay reachable via their owning submodule
# (datum.kernel.record.StructuredBody, datum.kernel.plan.PlanStep, etc.) for
# anyone who needs them without adding to the budgeted top-level surface.

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
]
