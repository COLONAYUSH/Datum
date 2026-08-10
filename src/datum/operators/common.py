"""Shared operator vocabulary (L5): the one query-time fragment shape and the
one canonical conformance-probe execution path every registered operator uses.

Extracted from grep_op.py at the start of Milestone B, when BM25 and ANN
arrived. Every v1 operator answers the same logical request — (query text,
already-ACL-resolved namespace, limit) — so they share ONE fragment type
rather than three structurally identical ones the planner would have to
construct case-by-case. The planner resolves the coarse namespace partition
FIRST (decisions.md #13); an operator only ever reads within it.

The conformance path is shared for a stronger reason than convenience: the
gate's fail-closed semantics (filter -> tenancy fail-closed on unevaluable ->
entitlement staleness) must be ONE implementation, not three copies that can
drift. An operator that wants different conformance behavior than this module
implements is exactly the operator the gate exists to refuse. The two paths
are told apart by structural duck-typing on the fragment (`rows` present ->
conformance probe), never by a self-reported flag, so no operator can claim
its way past the probe.
"""

from __future__ import annotations

from dataclasses import dataclass

from datum.kernel.operator import CandidateSet
from datum.operators.conformance.types import evaluate_expr


@dataclass(frozen=True)
class QueryFragment:
    """The real query-time fragment every retrieval operator executes.
    `namespace` is the coarse ACL partition the planner already resolved
    (v1 exact-equality, decisions.md #13); an operator only ever reads
    within it. `limit` bounds how many candidates the operator returns —
    the planner's fusion may keep fewer.
    """

    query: str
    namespace: str
    limit: int = 50


def is_conformance_fragment(fragment: object) -> bool:
    """Structural detection of a conformance probe: probes carry synthetic
    `rows`; real query fragments never do.
    """
    return hasattr(fragment, "rows")


def conformance_included(fragment: object, row: object) -> bool:
    """The canonical inclusion decision for one probe row, identical to the
    reference fixture's semantics: filter -> tenancy (fail closed on an
    unevaluable predicate) -> entitlement (stale snapshot permits nothing).
    """
    filt = fragment.filter  # type: ignore[attr-defined]
    if filt is not None and not evaluate_expr(filt, row.fields):  # type: ignore[attr-defined]
        return False
    tenancy = fragment.tenancy  # type: ignore[attr-defined]
    if tenancy is not None:
        try:
            if not tenancy.evaluate(row):
                return False
        except Exception:
            return False  # unevaluable -> exclude, never include
    entitlement = fragment.entitlement  # type: ignore[attr-defined]
    if entitlement is not None and not entitlement.permits(row):
        return False
    return True


def execute_conformance(fragment: object) -> CandidateSet:
    """Execute a conformance probe fragment with the canonical semantics.
    Row order is preserved and scores are the probe's own ground-truth
    relevance values, which satisfies the score contract (monotonic in
    relevance) without inventing an ordering the probe didn't ask for.
    """
    kept = [row for row in fragment.rows if conformance_included(fragment, row)]  # type: ignore[attr-defined]
    return CandidateSet(
        records=tuple(row.record for row in kept),
        scores=tuple(row.relevance for row in kept),
        score_method=fragment.score_method,  # type: ignore[attr-defined]
    )
