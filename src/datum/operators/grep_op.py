"""GrepOperator: L5, the walking-skeleton retrieval operator.

Reads L2 canonical records DIRECTLY (via GroundStore.live_in_namespace),
not an L4 View — which is exactly why a complete retrieval path exists
before FastCDC-derived indexes, embeddings, or pgvector do (the plan's
walking-skeleton bet). It is a boolean/occurrence-count text matcher over the
already-namespace-scoped record set.

Dual-fragment by design, so it is a genuinely conformant operator, gated
identically to the Phase-B BM25/ANN operators rather than special-cased:

- Real query time: a `GrepFragment` (query text + namespace + limit). The
  planner has already resolved the coarse namespace partition (v1 ACL), so
  grep matches text within that partition and never evaluates a fine-grained
  predicate itself.
- Conformance time: a `ConformanceFragment` (synthetic rows + a filter /
  tenancy predicate / entitlement snapshot). grep applies the SAME canonical
  inclusion semantics the reference fixture uses (shared `evaluate_expr`,
  tenancy fail-closed on an unevaluable predicate, entitlement staleness),
  proving it can fail closed on a predicate handed to it. v1 query time does
  not hand it fine-grained predicates; conformance proves it would honor them
  if it did.

The two paths are told apart by structural duck-typing on the fragment
(`rows` present -> conformance probe), not by a flag, so no self-reported
capability is ever trusted.
"""

from __future__ import annotations

from datum.groundstore.store import GroundStore
from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.kernel.record import Record
from datum.operators.common import (
    QueryFragment,
    execute_conformance,
    is_conformance_fragment,
)

# Historical name from the walking skeleton, kept importable: the fragment
# shape is shared by every operator since Milestone B (operators/common.py).
GrepFragment = QueryFragment


def _term_score(text: str, terms: list[str]) -> tuple[int, int]:
    """Score a record against query terms. Returns (distinct terms matched,
    total occurrences). Ranking by distinct-terms-first, occurrences-second
    puts a record matching many of the query's words above one that merely
    repeats a single common word — a sensible recall-first grep ranking
    without an arbitrary stopword list. Matching the whole query as one
    literal substring (the first-draft bug) misses any record that doesn't
    contain the exact phrase, which is almost all of them.
    """
    low = text.lower()
    distinct = 0
    total = 0
    for term in terms:
        c = low.count(term)
        if c > 0:
            distinct += 1
            total += c
    return distinct, total


class GrepOperator:
    kind = "grep"

    def __init__(self, store: GroundStore) -> None:
        self._store = store

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget  # grep has no budget-dependent planning at v1
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        return self._execute_query(fragment)

    def _execute_query(self, fragment: QueryFragment) -> CandidateSet:
        terms = [t for t in fragment.query.lower().split() if t]
        if not terms:
            # An empty/whitespace query has no search intent. Returning every
            # record at a flat score (the first-draft behavior) made an empty
            # search report status=ok with a fabricated ~0.3 sufficiency over
            # the whole namespace (review finding L2); it also disagreed with
            # BM25/ANN, which already return nothing for a blank query. Empty
            # in, empty out — the caller sees insufficient_evidence.
            return CandidateSet(records=(), scores=(), score_method="grep-term-match")
        matched: list[tuple[Record, float]] = []
        for record in self._store.live_in_namespace(fragment.namespace):
            distinct, total = _term_score(record.body_text(), terms)
            if distinct > 0:
                # distinct-term count dominates; occurrence count breaks ties.
                matched.append((record, distinct * 1000.0 + total))
        matched.sort(key=lambda rs: rs[1], reverse=True)
        matched = matched[: fragment.limit]
        return CandidateSet(
            records=tuple(r for r, _ in matched),
            scores=tuple(s for _, s in matched),
            score_method="grep-term-match",
        )

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=5.0)
