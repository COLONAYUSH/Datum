"""LineageManifest: the L2->L4 derivation-edge contract.

This is a Protocol, not an implementation — the concrete, Postgres-backed
implementation lives in derivation.lineage, which is where the actual I/O
belongs. Kernel only pins the shape: what a derivation edge looks like, and
what any implementation must support.

v1 uses `record_edge`/`edges_for_source` for the "only the touched chunk
re-derives" property (CI-07's acceptance test) and `propagate_forget` in its
tombstone-only form. The crypto-shred walk FRAMEWORK.md describes for
`propagate_forget` — cryptographically destroying a key rather than deleting
rows — is Phase 1; v1's implementation of this Protocol still walks the same
edges, it just tombstones rather than shreds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from datum.kernel.ids import RecordID
from datum.kernel.writeop import ForgetMode


@dataclass(frozen=True)
class LineageEdge:
    source_record_id: RecordID
    derived_record_id: RecordID
    view_name: str
    producer_version: str
    created_at: datetime


class LineageManifest(Protocol):
    def record_edge(self, edge: LineageEdge) -> None: ...

    def edges_for_source(self, source_record_id: RecordID) -> tuple[LineageEdge, ...]: ...

    def propagate_forget(self, record_id: RecordID, mode: ForgetMode) -> frozenset[str]:
        """Returns the set of view names the erasure was propagated to."""
        ...
