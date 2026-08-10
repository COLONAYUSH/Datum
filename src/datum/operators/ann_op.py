"""ANNOperator: L5, dense retrieval over the L4 view_dense index.

Mirrors grep_op's dual-fragment structure exactly, and is gated identically
through OperatorRegistry.register — no special-casing for being the "smart"
operator:

- Real query time: a `QueryFragment` (operators/common.py). The planner has
  already resolved the coarse namespace partition (decisions.md #13); this
  operator embeds the query once and reads within that partition only.
- Conformance time: a `ConformanceFragment` — executed through the shared
  canonical path (operators.common.execute_conformance) with NO database and
  NO embedder touched, because the gate runs at register_operator() time
  with no live infrastructure. The two paths are told apart by structural
  duck-typing on the fragment, never a self-reported flag.

The security-load-bearing line is the JOIN: candidates come from
`view_dense JOIN records`, with BOTH the namespace filter and the liveness
filter (`tx_to IS NULL`) evaluated against `records` — L2 is the source of
truth at query time. The view's own namespace column is an optimization
only, and a stale view row for a superseded/forgotten record (the engine
crashed between remove and cursor advance, or a bug planted one) is filtered
by the join rather than trusted (FRAMEWORK.md §The architecture, "L4 —
Derivation": nothing in a view is ever the source of truth). Rows are
decoded with groundstore's public record_from_row so this operator cannot
drift from the store's own Record decoding.

Infrastructure is lazy: the connection opens on the first real execute, so
constructing and registering the operator needs no reachable database.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg

from datum.derivation.views.dense import Embedder, vector_literal
from datum.groundstore.store import record_from_row, record_select_columns
from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.operators.common import (
    QueryFragment,
    execute_conformance,
    is_conformance_fragment,
)


class ANNOperator:
    kind = "ann"

    def __init__(self, dsn: str, embedder: Embedder) -> None:
        self._dsn = dsn
        self._embedder = embedder
        self._conn: psycopg.Connection[Any] | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget  # ANN has no budget-dependent planning at v1
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        return self._execute_query(fragment)

    def _execute_query(self, fragment: QueryFragment) -> CandidateSet:
        if not fragment.query.strip():
            # Nothing to embed; an empty query has no nearest neighbor.
            return CandidateSet(records=(), scores=(), score_method="cosine")
        # Embedded ONCE per execute; the literal is passed twice (SELECT and
        # ORDER BY) but computed here exactly one time.
        query_vec = vector_literal(self._embedder.encode_query(fragment.query))
        rows = self._connect().execute(
            f"""
            SELECT {record_select_columns("r")}, (v.embedding <=> %s::vector) AS dist
            FROM view_dense v JOIN records r ON r.row_id = v.row_id
            WHERE r.namespace = %s AND r.tx_to IS NULL
            ORDER BY v.embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vec, fragment.namespace, query_vec, fragment.limit),
        ).fetchall()
        # <=> is cosine distance; 1 - distance is cosine similarity, so higher
        # is nearer and the score contract's monotonicity holds. A zero-norm
        # stored vector makes pgvector's cosine distance NaN under a sequential
        # scan (review finding M1); a NaN score would violate the contract's
        # finiteness rule for any consumer reading this operator directly. The
        # shipped bge embedder never emits a zero-norm vector, but a custom one
        # could and the conformance gate cannot see this query path — so a
        # non-finite distance drops the row here rather than surfacing NaN.
        kept: list[tuple[Any, float]] = []
        for row in rows:
            dist = float(row[-1])
            if not math.isfinite(dist):
                continue
            kept.append((record_from_row(row[:-1]), 1.0 - dist))
        return CandidateSet(
            records=tuple(r for r, _ in kept),
            scores=tuple(s for _, s in kept),
            score_method="cosine",
        )

    def _connect(self) -> psycopg.Connection[Any]:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn, autocommit=True)
        return self._conn

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        # Rough constant: one local query embedding + one HNSW probe.
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=25.0)
