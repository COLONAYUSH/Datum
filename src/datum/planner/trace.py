"""TraceStore: persist and replay compiled plans by record (L6).

Replay-by-record (FRAMEWORK.md §Core abstractions #5): a plan's full result is
serialized into `plan_traces` at execution time, and `load()` reconstructs it
verbatim — it never re-runs operators against the live corpus. That is what
lets `replay(plan_id)` reproduce exactly what happened even after the corpus
changes, and keeps it distinct from an explicit re-execution against today's
system (`Corpus.replay(plan_id, against="current_champion")`).

Serialization is deliberately explicit (no pickling): the trace is an audit
artifact that must remain readable and stable across code versions, so every
kernel value is written as plain JSON with named fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from datum.kernel.evidence import CalibratedScore, EvidenceItem, EvidenceState
from datum.kernel.plan import Budget, CostTrace, Plan, PlanStep
from datum.kernel.principal import Principal
from datum.kernel.record import BoundingBox, ProvenanceCapsule, Span


# --- serialization (kernel value -> JSON-safe dict and back) ---


def _ser_provenance(p: ProvenanceCapsule) -> dict[str, Any]:
    return {
        "writer": {
            "id": p.writer.id,
            "namespace": p.writer.namespace,
            "capabilities": sorted(p.writer.capabilities),
        },
        "ingestion_path": p.ingestion_path,
        "authority_tier": p.authority_tier,
        "trust_class": p.trust_class,
        "source_version": p.source_version,
    }


def _de_provenance(d: dict[str, Any]) -> ProvenanceCapsule:
    w = d["writer"]
    return ProvenanceCapsule(
        writer=Principal(w["id"], w["namespace"], frozenset(w["capabilities"])),
        ingestion_path=d["ingestion_path"],
        authority_tier=d["authority_tier"],
        trust_class=d["trust_class"],
        source_version=d["source_version"],
    )


def _ser_item(item: EvidenceItem) -> dict[str, Any]:
    bbox = None
    if item.bbox is not None:
        bbox = {"page": item.bbox.page, "x0": item.bbox.x0, "y0": item.bbox.y0,
                "x1": item.bbox.x1, "y1": item.bbox.y1}
    return {
        "record_id": item.record_id,
        "content": item.content,
        "span": {"start": item.span.start, "end": item.span.end},
        "section_path": list(item.section_path),
        "page": item.page,
        "bbox": bbox,
        "provenance": _ser_provenance(item.provenance),
        "trust_tier": item.trust_tier,
        "freshness": item.freshness.isoformat(),
        "authority_tier": item.authority_tier,
    }


def _de_item(d: dict[str, Any]) -> EvidenceItem:
    bbox = None
    if d["bbox"] is not None:
        b = d["bbox"]
        bbox = BoundingBox(b["page"], b["x0"], b["y0"], b["x1"], b["y1"])
    return EvidenceItem(
        record_id=d["record_id"],
        content=d["content"],
        span=Span(d["span"]["start"], d["span"]["end"]),
        section_path=tuple(d["section_path"]),
        page=d["page"],
        bbox=bbox,
        provenance=_de_provenance(d["provenance"]),
        trust_tier=d["trust_tier"],
        freshness=datetime.fromisoformat(d["freshness"]),
        authority_tier=d["authority_tier"],
    )


def _ser_cost(c: CostTrace) -> dict[str, Any]:
    return {
        "total_tokens": c.total_tokens,
        "total_dollars": c.total_dollars,
        "total_latency_ms": c.total_latency_ms,
        "by_stage": c.by_stage,
        "attributed_fraction": c.attributed_fraction,
    }


def _de_cost(d: dict[str, Any]) -> CostTrace:
    return CostTrace(
        total_tokens=d["total_tokens"],
        total_dollars=d["total_dollars"],
        total_latency_ms=d["total_latency_ms"],
        by_stage=d["by_stage"],
        attributed_fraction=d["attributed_fraction"],
    )


def _ser_evidence(e: EvidenceState) -> dict[str, Any]:
    return {
        "items": [_ser_item(i) for i in e.items],
        "relevance": {"value": e.relevance.value, "method": e.relevance.method,
                      "calibrated": e.relevance.calibrated},
        "conflicts": [],  # v1 surfaces none; the field exists for forward-compat
        "sufficiency": e.sufficiency,
        "status": e.status,
        "plan_id": e.plan_id,
        "cost": _ser_cost(e.cost),
        "extra": e.extra,
    }


def _de_evidence(d: dict[str, Any]) -> EvidenceState:
    r = d["relevance"]
    return EvidenceState(
        items=tuple(_de_item(i) for i in d["items"]),
        relevance=CalibratedScore(r["value"], r["method"], r["calibrated"]),
        conflicts=(),
        sufficiency=d["sufficiency"],
        status=d["status"],
        plan_id=d["plan_id"],
        cost=_de_cost(d["cost"]),
        extra=d.get("extra", {}),
    )


def _ser_plan(plan: Plan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "plan_selector": plan.plan_selector,
        "policy_id": plan.policy_id,
        "propensity": plan.propensity,
        "created_at": plan.created_at.isoformat(),
        "principal": {
            "id": plan.principal.id,
            "namespace": plan.principal.namespace,
            "capabilities": sorted(plan.principal.capabilities),
        },
        "budget": {
            "tokens_max": plan.budget.tokens_max,
            "latency_ms_max": plan.budget.latency_ms_max,
            "dollars_max": plan.budget.dollars_max,
        },
        "steps": [
            {"op_name": s.op_name, "params": s.params, "fails_closed": s.fails_closed}
            for s in plan.steps
        ],
    }


def _de_plan(d: dict[str, Any]) -> Plan:
    p = d["principal"]
    b = d["budget"]
    return Plan(
        plan_id=d["plan_id"],
        steps=tuple(
            PlanStep(op_name=s["op_name"], params=s["params"], fails_closed=s["fails_closed"])
            for s in d["steps"]
        ),
        plan_selector=d["plan_selector"],
        principal=Principal(p["id"], p["namespace"], frozenset(p["capabilities"])),
        budget=Budget(
            tokens_max=b["tokens_max"], latency_ms_max=b["latency_ms_max"],
            dollars_max=b["dollars_max"],
        ),
        policy_id=d["policy_id"],
        created_at=datetime.fromisoformat(d["created_at"]),
        propensity=d["propensity"],
        executor=None,  # a replayed plan is not re-executable — replay is by record
    )


class TraceStore:
    def __init__(self, dsn: str) -> None:
        self._conn = psycopg.connect(dsn, autocommit=True)

    def close(self) -> None:
        self._conn.close()

    def persist(self, plan: Plan, evidence: EvidenceState) -> None:
        self._conn.execute(
            "INSERT INTO plan_traces (plan_id, namespace, plan_selector, propensity, "
            "plan_json, evidence_json) VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (plan_id) DO NOTHING",
            (
                plan.plan_id,
                plan.principal.namespace,
                plan.plan_selector,
                plan.propensity,
                Jsonb(_ser_plan(plan)),
                Jsonb(_ser_evidence(evidence)),
            ),
        )

    def load(self, plan_id: str) -> tuple[Plan, EvidenceState] | None:
        row = self._conn.execute(
            "SELECT plan_json, evidence_json FROM plan_traces WHERE plan_id=%s",
            (plan_id,),
        ).fetchone()
        if row is None:
            return None
        return _de_plan(row[0]), _de_evidence(row[1])
