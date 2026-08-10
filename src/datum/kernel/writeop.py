"""WriteOp: the transactional write path, source-specific policies.

Deviation from FRAMEWORK.md, decided in the implementation plan (Decision 1):
the design doc's own two sketches of WriteOp conflict — one shows it as a
Protocol with executor methods (`assert_(...) -> RecordID`), the other has
`WritePolicy.ingest()` return `list[WriteOp]` built by appending
`WriteOp.assert_(...)` calls, which only type-checks if those calls
construct values, not execute anything. This module resolves it as a frozen
value type with a `kind` discriminator and classmethod constructors. The
original executor return types (-> RecordID, -> ErasureReceipt) are realized
where the op is actually executed: writepath.orchestrator.WriteOrchestrator.execute().

v1 supports three kinds only: assert, supersede, forget[tombstone]. invalidate
and consolidate are Phase 1 (ConsolidationView is a pre-budgeted, unbuilt
kernel symbol — see datum/__init__.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from datum.kernel.ids import PolicyID, RecordID
from datum.kernel.principal import Principal
from datum.kernel.record import ProvenanceCapsule, StructuredBody

WriteOpKind = Literal["assert", "supersede", "forget"]
ForgetMode = Literal["tombstone", "crypto_shred"]


@dataclass(frozen=True)
class WriteOp:
    kind: WriteOpKind
    body: str | StructuredBody | None = None
    valid_from: datetime | None = None
    provenance: ProvenanceCapsule | None = None
    policy_id: PolicyID | None = None
    idempotency_key: str | None = None
    old_id: RecordID | None = None  # supersede: the record being replaced
    target_id: RecordID | None = None  # forget: the record being erased
    mode: ForgetMode | None = None  # forget only
    # Span identity for assert/supersede (decisions.md #17). Together these
    # are the ground store's uniqueness-CAS key: at most one live record per
    # (source_id, stable_key). `source_id` names the document/source; and
    # `stable_key` names the span within it (a section path, a chunk key) —
    # stable across re-ingests of the same span, which is what lets a
    # re-ingest supersede rather than duplicate. None for forget (which
    # targets a record_id directly). Carried on the op, not passed alongside
    # it, so the op is a complete, self-describing, WAL-serializable record
    # of the write — the audit trail gets span identity for free.
    source_id: str | None = None
    stable_key: str | None = None
    # Per-span extraction confidence the parser produced, carried through to
    # the resulting Record.parser_confidence. Optional: a plain-text or
    # already-trusted source has no confidence to report (None).
    parser_confidence: float | None = None

    @classmethod
    def assert_(
        cls,
        body: str | StructuredBody,
        valid_from: datetime,
        provenance: ProvenanceCapsule,
        policy_id: PolicyID,
        *,
        source_id: str,
        stable_key: str,
        idempotency_key: str | None = None,
        parser_confidence: float | None = None,
    ) -> "WriteOp":
        return cls(
            kind="assert",
            body=body,
            valid_from=valid_from,
            provenance=provenance,
            policy_id=policy_id,
            source_id=source_id,
            stable_key=stable_key,
            idempotency_key=idempotency_key,
            parser_confidence=parser_confidence,
        )

    @classmethod
    def supersede(
        cls,
        old_id: RecordID,
        body: str | StructuredBody,
        valid_from: datetime,
        provenance: ProvenanceCapsule,
        *,
        source_id: str,
        stable_key: str,
        idempotency_key: str | None = None,
        parser_confidence: float | None = None,
    ) -> "WriteOp":
        return cls(
            kind="supersede",
            old_id=old_id,
            body=body,
            valid_from=valid_from,
            provenance=provenance,
            source_id=source_id,
            stable_key=stable_key,
            idempotency_key=idempotency_key,
            parser_confidence=parser_confidence,
        )

    @classmethod
    def forget(cls, target_id: RecordID, mode: ForgetMode = "tombstone") -> "WriteOp":
        if mode != "tombstone":
            raise NotImplementedError(
                "crypto_shred forgetting is Phase 1 (deferred per FRAMEWORK.md's "
                "MVP definition — v1 ships tombstone-only erasure)."
            )
        return cls(kind="forget", target_id=target_id, mode=mode)


class RawInput(Protocol):
    """What a WritePolicy.ingest() receives. Deliberately loose and internal —
    not part of the kernel symbol budget. A document upload's raw shape and a
    conversation transcript's raw shape are genuinely different; this Protocol
    only pins the two fields every policy in this codebase actually reads.
    """

    source_id: str
    policy_id: PolicyID


class WritePolicy(Protocol):
    name: str
    version: str

    def ingest(self, raw: RawInput, principal: Principal) -> list[WriteOp]: ...


@dataclass(frozen=True)
class ErasureReceipt:
    record_id: RecordID
    mode: ForgetMode
    propagated_to: frozenset[str]  # view names the erasure was propagated to
    completed_at: datetime
    key_shredded_at: datetime | None = None  # always None at v1 (tombstone-only)
