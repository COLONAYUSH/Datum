"""WriteOrchestrator: L3, the admission-controlled write path.

Sits between a WritePolicy (which turns raw input into WriteOps) and the
ground store (which persists them atomically). Its job is the admission
control no policy should be trusted to do itself:

1. **The authority-tier clamp** (`_kernel_admit`): a write may only claim
   `authority_tier` "primary"/"corroborated" if the acting principal holds
   the `verified_source` capability. Otherwise the tier is clamped down to
   "inferred" — a policy (or a compromised one) cannot mint high-authority
   records by simply asserting they are. This is enforced here, on every op,
   regardless of which policy produced it.
2. **The write-side namespace guard**: a principal may not write a record
   whose provenance names a different namespace than the principal's own
   (groundstore.require_writer_namespace) — the write-side complement of
   read-side ACL.
3. **Preconditions**: caller-registered reject-destructive-composition checks
   (groundstore.precondition), consulted per op before it reaches the store.

Only after all three does an op reach `store.apply`, where it commits
atomically with its WAL entry.
"""

from __future__ import annotations

from dataclasses import replace

from datum.groundstore.precondition import PreconditionRegistry
from datum.groundstore.store import GroundStore, require_writer_namespace
from datum.kernel.ids import RecordID
from datum.kernel.principal import Principal
from datum.kernel.writeop import ErasureReceipt, RawInput, WriteOp, WritePolicy


class WriteOrchestrator:
    def __init__(
        self, store: GroundStore, preconditions: PreconditionRegistry | None = None
    ) -> None:
        self._store = store
        self._preconditions = preconditions or PreconditionRegistry()
        self._policies: dict[str, WritePolicy] = {}

    def register_policy(self, source_type: str, policy: WritePolicy) -> None:
        self._policies[source_type] = policy

    def execute(
        self, source_type: str, raw: RawInput, principal: Principal
    ) -> list[RecordID | ErasureReceipt]:
        """Run a raw input through its policy and apply every resulting op,
        each admission-controlled, returning the results in order.
        """
        policy = self._policies.get(source_type)
        if policy is None:
            raise KeyError(
                f"no WritePolicy registered for source_type {source_type!r}; "
                f"registered: {sorted(self._policies)}"
            )
        results: list[RecordID | ErasureReceipt] = []
        for op in policy.ingest(raw, principal):
            admitted = self._admit(op, principal)
            # The acting namespace goes to the store explicitly: it scopes a
            # forget to the principal's own partition (a forget op carries no
            # provenance to derive it from) and double-checks assert/supersede
            # provenance at the L2 seam (decisions.md #19).
            results.append(self._store.apply(admitted, namespace=principal.namespace))
        return results

    def _admit(self, op: WriteOp, principal: Principal) -> WriteOp:
        """Apply the three admission gates and return the (possibly clamped)
        op that may proceed to the store. Raises AdmissionError (from the
        namespace guard or a precondition) on rejection.
        """
        op = _kernel_admit(op, principal)
        # forget targets a record by id and carries no provenance/body to
        # namespace-check or precondition-check here; execute() scopes it to
        # the acting principal's namespace at the store call, which fails
        # closed on a target outside that partition.
        if op.kind in ("assert", "supersede"):
            require_writer_namespace(op, principal)
            if op.source_id is not None and op.stable_key is not None and op.body is not None:
                prior = self._store.find_span(
                    op.source_id, op.stable_key, namespace=principal.namespace
                )
                self._preconditions.evaluate(prior, op.body)
        return op


def _kernel_admit(op: WriteOp, principal: Principal) -> WriteOp:
    """Clamp a claimed high-authority tier down to 'inferred' unless the
    principal is a verified source. Applied to every op before it reaches the
    WAL — not a WritePolicy-author convention, and not something a registered
    policy can opt out of (FRAMEWORK.md §Core abstractions #2's `_kernel_admit`
    sketch, verbatim in intent).
    """
    if op.provenance is None:
        return op
    tier = op.provenance.authority_tier
    if tier in ("primary", "corroborated") and not principal.has_capability("verified_source"):
        clamped = replace(op.provenance, authority_tier="inferred")
        return replace(op, provenance=clamped)
    return op
