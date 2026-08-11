"""Feedback-driven per-namespace calibration (decisions.md #44): the learned
relevance loop's mechanism, shipped promotion-gated.

`run_calibration(corpus, namespace)` turns accumulated relevance judgments
(`relevance_feedback`, written by Corpus.feedback / the MCP feedback verb)
into calibrated fusion weights + abstention floor for ONE namespace — and
promotes them only if they beat the namespace's CURRENT policy on held-out
judgments. No improvement on holdout = no change: a deployment cannot tune
itself into a worse place on the strength of noise, and every promoted
override records its evidence basis (row counts, holdout scores) in the
`policy_overrides` table, auditable like every other decision in the system.

What this deliberately is NOT: a gradient-trained ranker. It is a small grid
search over the parameters the rule-table policy already declares — honest
about how much signal a few dozen judgments carry. The Phase-2 learned policy
replaces the SEARCH, not the discipline: judged feedback in, holdout
promotion gate, audited basis out.

Method: each judged plan_id joins back to its persisted trace, which carries
the ORIGINAL query text — so calibration re-executes the real queries a user
actually judged, under each candidate parameter set, and scores the mean
reciprocal rank (MRR) of the records the user marked useful. Queries split
80/20 into train/holdout by a deterministic hash of plan_id (stable across
runs; no RNG, decisions.md discipline on reproducibility).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import psycopg

from datum.kernel.principal import Principal
from datum.policy.rule_table import RuleTablePolicy

# At least this many DISTINCT judged queries before calibration will run at
# all: below it, a grid search is guaranteed to overfit noise. Refusing loudly
# beats silently tuning on nothing.
MIN_JUDGED_QUERIES = 8

_DEFAULT_WEIGHT_GRID = [0.5, 1.0, 2.0]
_DEFAULT_FLOOR_GRID = [0.35, 0.44, 0.53]


@dataclass(frozen=True)
class CalibrationResult:
    promoted: bool
    params: dict
    train_mrr: float
    holdout_mrr: float
    baseline_holdout_mrr: float
    n_queries: int
    reason: str


def _judged_queries(conn: psycopg.Connection, corpus, namespace: str) -> dict[str, dict]:
    """plan_id -> {query, useful: set[record_id], not_useful: set[record_id]}.
    Judgments whose plan trace is gone (or which came from non-search verbs,
    e.g. a navigate hit token) are skipped — calibration only uses judgments
    it can tie back to a replayable query."""
    rows = conn.execute(
        "SELECT plan_id, record_id, useful FROM relevance_feedback WHERE namespace = %s",
        (namespace,),
    ).fetchall()
    out: dict[str, dict] = {}
    for plan_id, record_id, useful in rows:
        entry = out.get(plan_id)
        if entry is None:
            loaded = corpus._trace.load(plan_id)
            if loaded is None:
                continue
            plan, _ = loaded
            query = next(
                (str(s.params["query"]) for s in plan.steps if s.op_name == "search" and "query" in s.params),
                None,
            )
            if query is None:
                continue
            entry = out[plan_id] = {"query": query, "useful": set(), "not_useful": set()}
        (entry["useful"] if useful else entry["not_useful"]).add(record_id)
    return {k: v for k, v in out.items() if v["useful"]}  # MRR needs at least one useful


def _mrr(corpus, namespace: str, judged: list[dict]) -> float:
    principal = Principal(id="calibrate", namespace=namespace)
    total = 0.0
    for entry in judged:
        ev = corpus.search(entry["query"], principal=principal)
        rank = None
        seen = 0
        for h in ev.hits:
            seen += 1
            payload = corpus._hits.resolve(h.hit_id)
            if payload["content_ref"] in entry["useful"]:
                rank = seen
                break
        total += (1.0 / rank) if rank else 0.0
    return total / len(judged) if judged else 0.0


def run_calibration(
    corpus,
    namespace: str,
    *,
    weight_grid: list[float] | None = None,
    floor_grid: list[float] | None = None,
    min_queries: int = MIN_JUDGED_QUERIES,
) -> CalibrationResult:
    weight_grid = weight_grid or _DEFAULT_WEIGHT_GRID
    floor_grid = floor_grid or _DEFAULT_FLOOR_GRID

    with psycopg.connect(corpus._dsn) as conn:
        judged_map = _judged_queries(conn, corpus, namespace)
    n = len(judged_map)
    if n < min_queries:
        return CalibrationResult(
            promoted=False, params={}, train_mrr=0.0, holdout_mrr=0.0,
            baseline_holdout_mrr=0.0, n_queries=n,
            reason=f"insufficient feedback: {n} judged queries < required {min_queries} "
                   "— refusing to tune on noise.",
        )

    # Deterministic 80/20 split by plan_id hash: stable across runs, no RNG.
    train, holdout = [], []
    for plan_id, entry in sorted(judged_map.items()):
        bucket = int(hashlib.sha256(plan_id.encode()).hexdigest(), 16) % 5
        (holdout if bucket == 0 else train).append(entry)
    if not holdout:  # tiny-N edge: force at least one holdout query
        holdout.append(train.pop())

    original_policy = corpus._compiler._policy

    def eval_with(params: dict | None, judged: list[dict]) -> float:
        overrides = {namespace: params} if params else {}
        corpus._compiler._policy = RuleTablePolicy(overrides=overrides)
        try:
            return _mrr(corpus, namespace, judged)
        finally:
            corpus._compiler._policy = original_policy

    baseline_holdout = eval_with(None, holdout)

    best_params, best_train = None, -1.0
    for wg in weight_grid:
        for wb in weight_grid:
            for wa in weight_grid:
                for floor in floor_grid:
                    params = {
                        "fusion_weights": {"grep": wg, "bm25": wb, "ann": wa},
                        "abstain_min_similarity": floor,
                    }
                    score = eval_with(params, train)
                    if score > best_train:
                        best_train, best_params = score, params

    holdout_score = eval_with(best_params, holdout)
    if holdout_score <= baseline_holdout:
        return CalibrationResult(
            promoted=False, params=best_params or {}, train_mrr=best_train,
            holdout_mrr=holdout_score, baseline_holdout_mrr=baseline_holdout,
            n_queries=n,
            reason=f"holdout MRR {holdout_score:.4f} does not beat current policy "
                   f"{baseline_holdout:.4f} — promotion refused, defaults kept.",
        )

    basis = {
        "n_judged_queries": n,
        "train_mrr": round(best_train, 4),
        "holdout_mrr": round(holdout_score, 4),
        "baseline_holdout_mrr": round(baseline_holdout, 4),
        "policy_version": RuleTablePolicy.version,
    }
    with psycopg.connect(corpus._dsn) as conn:
        conn.execute(
            "INSERT INTO policy_overrides (namespace, params, basis) VALUES (%s, %s, %s) "
            "ON CONFLICT (namespace) DO UPDATE SET params = EXCLUDED.params, "
            "basis = EXCLUDED.basis, created_at = now()",
            (namespace, json.dumps(best_params), json.dumps(basis)),
        )
        conn.commit()
    return CalibrationResult(
        promoted=True, params=best_params, train_mrr=best_train,
        holdout_mrr=holdout_score, baseline_holdout_mrr=baseline_holdout,
        n_queries=n,
        reason="promoted: beats current policy on held-out judgments; "
               "takes effect for this namespace on the next Corpus.open.",
    )
