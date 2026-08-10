"""BM25Operator: L5 lexical retrieval over view_lexical (Postgres FTS).

"bm25" names this operator's slot in the plan vocabulary, not the scoring
formula: decisions.md #4's go/no-go resolved NO-GO on ParadeDB pg_search, so
the backing is the sanctioned fallback — the tsvector+GIN view
(derivation/views/lexical.py) ranked by ts_rank_cd. That satisfies the
conformance score contract exactly as written ("monotonic in relevance,"
never "matches BM25's formula"), so a later swap to a true BM25 backend
happens behind this same operator surface without touching the gate, the
planner, or any caller.

Dual-fragment by design, mirroring grep_op: a conformance probe (detected
structurally — `rows` present — never by a self-reported flag) runs through
the shared operators.common path and MUST NOT touch the database, because
the gate runs at register_operator() time with no live infrastructure. That
is also why the connection opens lazily on the first real execute:
constructing and registering this operator needs no reachable Postgres.

Two properties of the real query path are load-bearing:

- Query text reaches Postgres only as a bound parameter to
  websearch_to_tsquery(), never as interpolated tsquery syntax — hostile
  text cannot inject operators, and websearch_to_tsquery never raises on
  garbage. An empty or stopword-only query yields an empty tsquery; the
  numnode() guard turns that into an empty CandidateSet, not an error.
- A view row alone admits nothing: candidates JOIN back to `records` and
  re-check namespace (exact equality, decisions.md #13) and liveness
  (tx_to IS NULL) against L2, the source of truth at query time. The view's
  own namespace column is an optimization only; a stale view row for a
  closed record cannot leak through the join.
"""

from __future__ import annotations

from typing import Any

import psycopg

from datum.groundstore.store import record_from_row, record_select_columns
from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.operators.common import (
    QueryFragment,
    execute_conformance,
    is_conformance_fragment,
)

# Record columns decoded by groundstore.record_from_row — ONE decoding
# implementation shared with the store, not a per-operator copy (see
# RECORD_SELECT_COLUMNS' own comment in groundstore/store.py).
_QUERY_SQL = f"""
SELECT {record_select_columns("r")}, ts_rank_cd(v.tsv, q.query) AS rank
FROM view_lexical v
     JOIN records r ON r.row_id = v.row_id,
     websearch_to_tsquery(%s::regconfig, %s) AS q(query)
WHERE numnode(q.query) > 0
  AND r.namespace = %s
  AND r.tx_to IS NULL
  AND v.tsv @@ q.query
ORDER BY rank DESC, r.record_id
LIMIT %s
"""
# numnode() = 0 is the empty-tsquery case (empty/stopword-only query text):
# it matches nothing, and the guard makes that an explicit empty result
# rather than a property of @@'s behavior a reader has to know. The
# record_id tie-break makes equal-rank output deterministic across runs.

# Query-text hardening (review finding M2). websearch_to_tsquery is already
# injection-proof (a bound param, never interpolated syntax), but two inputs
# still reached Postgres and RAISED, propagating up through Corpus.search:
#   - a NUL byte, which Postgres text columns cannot hold (psycopg DataError);
#   - a query with a huge term count (a 1MB paste is ~200k words), which
#     builds a tsquery deep enough to blow Postgres's stack-depth limit.
# The bar for hostile input is "no query may raise, records intact." So the
# text is stripped of NUL and capped to a generous term count BEFORE the FTS
# call; a real query never approaches the cap, so this only defuses abuse.
_MAX_QUERY_TERMS = 2000


def _sanitize_query(query: str) -> str:
    without_nul = query.replace("\x00", " ")
    terms = without_nul.split()
    if len(terms) > _MAX_QUERY_TERMS:
        terms = terms[:_MAX_QUERY_TERMS]
    return " ".join(terms)


class BM25Operator:
    kind = "bm25"

    def __init__(self, dsn: str, fts_config: str = "english") -> None:
        # The query-time config must match the one view_lexical was derived
        # with, or query lexemes and indexed lexemes disagree — same default,
        # same constructor knob as LexicalView.
        self._dsn = dsn
        self._fts_config = fts_config
        self._conn: psycopg.Connection[Any] | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget  # no budget-dependent planning at v1; plan() does no I/O
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        return self._execute_query(fragment)

    def _execute_query(self, fragment: QueryFragment) -> CandidateSet:
        query = _sanitize_query(fragment.query)
        rows = self._connect().execute(
            _QUERY_SQL,
            (self._fts_config, query, fragment.namespace, fragment.limit),
        ).fetchall()
        return CandidateSet(
            records=tuple(record_from_row(row[:-1]) for row in rows),
            scores=tuple(float(row[-1]) for row in rows),
            score_method="ts_rank_cd",
        )

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=10.0)

    def _connect(self) -> psycopg.Connection[Any]:
        # Lazy: first REAL execute pays for the connection (module docstring —
        # registration must work with no reachable database). Autocommit, so
        # reads never hold a snapshot open between calls (groundstore's rule).
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn, autocommit=True)
        return self._conn
