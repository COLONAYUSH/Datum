"""The Agent Tool Surface's own response types (L8) — deliberately distinct
from kernel.evidence.EvidenceState.

EvidenceState is the full-detail, server-internal shape (provenance,
trust_tier, authority_tier — everything a downstream disambiguation step
might need). What actually crosses the MCP boundary to a calling model is
grep-shaped and much smaller: SearchHit carries an opaque `hit_id` instead
of trust/authority metadata. A caller that needs to check those calls
`explain()` or a disambiguation step with the hit_id, never gets them mixed
into the content stream itself — this is the mechanism, not a convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from datum.kernel.evidence import EvidenceStatus


@dataclass(frozen=True)
class SearchHit:
    hit_id: str  # opaque; resolves server-side via mcp_server.hit_registry.HitRegistry
    content: str
    source_path: str
    section_path: tuple[str, ...] = ()
    page: int | None = None
    score: float | None = None


@dataclass(frozen=True)
class StructureNode:
    path: str
    kind: Literal["document", "section", "table", "page"]
    children: tuple["StructureNode", ...] = ()
    hit_id: str | None = None  # set only if this node can be fetch()'d directly


@dataclass(frozen=True)
class StructureView:
    root: StructureNode


@dataclass(frozen=True)
class Evidence:
    """What search() actually returns to a caller: hits plus a sufficiency
    signal, never provenance/trust metadata inline with content.
    """

    hits: tuple[SearchHit, ...]
    status: EvidenceStatus
    sufficiency: float
    plan_id: str


ChangeKind = Literal["created", "superseded", "forgotten"]


@dataclass(frozen=True)
class ChangeRecord:
    hit_id: str
    change_kind: ChangeKind
    occurred_at: datetime


@dataclass(frozen=True)
class ChangeSet:
    changes: tuple[ChangeRecord, ...]
    since_marker: str
    as_of_marker: str  # opaque WAL position; pass as the next call's `since` marker
