"""Wrap a raw CandidateSet into a typed EvidenceState (L7).

The structural fields on each EvidenceItem (section_path, page, bbox, span)
are copied straight through from the record's StructuredBody — never
re-derived. That is exactly what makes "every retrieved chunk traces to page
+ bounding region" true at the retrieval surface and not only in storage
(CI-02's acceptance criterion).

"Not enough evidence" is a first-class outcome, not a caller's inference: an
empty candidate set produces `status="insufficient_evidence"`, so a caller
(or a downstream generator) branches on a typed field rather than guessing
from a low score.
"""

from __future__ import annotations

from datum.kernel.evidence import CalibratedScore, EvidenceItem, EvidenceState
from datum.kernel.operator import CandidateSet
from datum.kernel.plan import CostTrace
from datum.kernel.record import Record, Span, StructuredBody
from datum.evidence.sufficiency import SUFFICIENCY_METHOD, estimate_sufficiency

_RELEVANCE_METHOD = "uncalibrated-raw-v1"


def _item_from_record(record: Record, score: float) -> EvidenceItem:
    body = record.body
    text = record.body_text()
    if isinstance(body, StructuredBody):
        span = body.span if body.span is not None else Span(0, len(text))
        section_path = body.section_path
        page = body.page
        bbox = body.bbox
    else:
        span = Span(0, len(text))
        section_path = ()
        page = None
        bbox = None
    return EvidenceItem(
        record_id=record.id,
        content=text,
        span=span,
        section_path=section_path,
        page=page,
        bbox=bbox,
        provenance=record.provenance,
        trust_tier=record.provenance.trust_class,
        freshness=record.tx_from,
        authority_tier=record.provenance.authority_tier,
    )


def build_evidence_state(
    candidates: CandidateSet, *, plan_id: str, cost: CostTrace, agreement: float | None = None
) -> EvidenceState:
    items = tuple(
        _item_from_record(record, score)
        for record, score in zip(candidates.records, candidates.scores)
    )
    sufficiency = estimate_sufficiency(candidates, agreement=agreement)
    status = "ok" if items else "insufficient_evidence"
    top = max(candidates.scores) if candidates.scores else 0.0
    return EvidenceState(
        items=items,
        relevance=CalibratedScore(value=top, method=_RELEVANCE_METHOD, calibrated=False),
        conflicts=(),  # conflict detection is a later phase; no silent fusion happens here
        sufficiency=sufficiency,
        status=status,
        plan_id=plan_id,
        cost=cost,
        extra={"sufficiency_method": SUFFICIENCY_METHOD},
    )
