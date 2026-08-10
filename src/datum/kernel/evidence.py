"""EvidenceState: typed, calibrated-or-honestly-not, conflict-aware, abstention-capable (L7).

`insufficient_evidence` and `conflicted` are outcomes a plan can produce, on
the same footing as "here are the results" — never a generation-time
surprise the caller has to detect by noticing the answer sounds uncertain.

v1's CalibratedScore is explicitly uncalibrated: `calibrated=False` and
`method="uncalibrated-raw-v1"` rather than silently presenting a raw
similarity score as if it had probabilistic meaning. Real calibration
(isotonic regression on a corpus-specific human-anchored slice) is a Phase 1
addition behind the same type, not a breaking change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from datum.kernel.ids import RecordID
from datum.kernel.plan import CostTrace
from datum.kernel.record import BoundingBox, ProvenanceCapsule, Span

# "error" is the audit-only terminal status: a retrieval that raised mid-
# execution never RETURNS an EvidenceState with this status to a caller (the
# exception still propagates), but the planner persists one under it so the
# Plan trace is unconditional — a failed search is as auditable as a
# successful one (decisions.md #27). Widening this Literal is a compatible
# extension: it is not a budgeted kernel symbol, and no existing consumer
# enumerates the set exhaustively.
EvidenceStatus = Literal[
    "ok", "insufficient_evidence", "conflicted", "budget_exhausted", "error"
]


@dataclass(frozen=True)
class CalibratedScore:
    value: float
    method: str  # "uncalibrated-raw-v1" at MVP; e.g. "isotonic-v1-on-corpus-X" once calibrated
    calibrated: bool = False


@dataclass(frozen=True)
class EvidenceItem:
    """These fields are copied straight through from Record.body.StructuredBody
    at wrap time (evidence.wrap) — never re-derived. That is what makes the
    acceptance test "every retrieved chunk traces to page + bounding region"
    true at the retrieval surface, not just in storage.

    `record_id` is the item's link back to the exact ground-store record it
    came from — the provenance anchor a provenance-first result must carry.
    It is what the agent-facing surface mints an opaque `hit_id` against, and
    what `fetch(hit_id)` resolves through to re-read the record (decisions.md
    #18). It never crosses the MCP boundary as a token the model reads; the
    surface exposes only the opaque hit_id.
    """

    record_id: "RecordID"
    content: str
    span: Span
    section_path: tuple[str, ...]
    page: int | None
    bbox: BoundingBox | None
    provenance: ProvenanceCapsule
    trust_tier: str
    freshness: datetime
    authority_tier: str


@dataclass(frozen=True)
class Conflict:
    item_a: EvidenceItem
    item_b: EvidenceItem
    description: str


@dataclass(frozen=True)
class EvidenceState:
    items: tuple[EvidenceItem, ...]
    relevance: CalibratedScore
    conflicts: tuple[Conflict, ...]
    sufficiency: float
    status: EvidenceStatus
    plan_id: str
    cost: CostTrace
    extra: dict[str, str] = field(default_factory=dict)
