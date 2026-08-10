"""Record: the canonical, bitemporal, typed substrate entity (L2).

A record is never edited in place. When a document changes, the old record's
tx_to is closed and a new record's tx_from is opened in the same WAL append
(see writepath.orchestrator) — nothing is silently overwritten, so it is
always possible to ask what the system believed at any point in the past.

`body` keeps the structure a document actually has (section path, table
cells, page, bounding box, character offsets) rather than flattening to a
bare string. EvidenceItem (kernel.evidence) copies these fields straight
through at retrieval time; it never re-derives them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from datum.kernel.ids import PolicyID, RecordID
from datum.kernel.principal import Principal

RecordKind = Literal["document", "chunk", "memory", "fact", "enrichment"]
AuthorityTier = Literal["primary", "corroborated", "inferred", "user-asserted", "UNVERIFIED"]
TrustClass = Literal["trusted", "untrusted", "quarantined"]


@dataclass(frozen=True)
class Span:
    """Character offsets into the record's own raw text."""

    start: int
    end: int


@dataclass(frozen=True)
class BoundingBox:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class TableCell:
    row: int
    col: int
    text: str
    is_header: bool = False


@dataclass(frozen=True)
class StructuredBody:
    """The typed shape a flattened string erases.

    Populated by the structural parser (Docling) at ingestion and by the
    chunker at derivation time. `section_path` and `page`/`bbox` survive
    chunking so a retrieved chunk always traces back to an exact place in
    an exact document, not "somewhere in a file."
    """

    text: str
    section_path: tuple[str, ...] = ()
    page: int | None = None
    bbox: BoundingBox | None = None
    table_cells: tuple[TableCell, ...] | None = None
    span: Span | None = None


@dataclass(frozen=True)
class ProvenanceCapsule:
    """Fixed-size, O(1) per record, checked once per candidate.

    `authority_tier` defaults to UNVERIFIED everywhere no registry says
    otherwise — the honest default, not a placeholder. It can only be
    upgraded to "primary"/"corroborated" by a principal holding the
    verified_source capability; writepath.orchestrator enforces this
    clamp on every write, regardless of which WritePolicy produced it.

    `trust_class` defaults to "untrusted" for anything a policy did not
    explicitly mark "trusted" — see writepath.policies.document vs. the
    (Phase 1) conversation policy for why documents and agent-inferred
    writes get different defaults here.
    """

    writer: Principal
    ingestion_path: str
    authority_tier: AuthorityTier
    trust_class: TrustClass
    source_version: str  # parser/embedder/extractor version — the CI-07 lineage tuple


@dataclass(frozen=True)
class Record:
    id: RecordID
    kind: RecordKind
    body: str | StructuredBody
    valid_from: datetime
    valid_to: datetime | None
    tx_from: datetime
    tx_to: datetime | None
    provenance: ProvenanceCapsule
    policy_id: PolicyID
    parser_confidence: float | None
    supersedes: RecordID | None = None

    @property
    def is_live(self) -> bool:
        return self.tx_to is None

    def body_text(self) -> str:
        return self.body if isinstance(self.body, str) else self.body.text
