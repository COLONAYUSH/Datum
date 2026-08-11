"""PlanCompiler: L6, request -> compiled Plan with a bound executor.

Compiles a retrieval request (query, principal, budget) into a `Plan` whose
steps are visible before it runs (EXPLAIN) and whose execution is bound as a
callable the kernel `Plan.execute()` invokes (decisions.md #8: the kernel
type carries the executor and does no I/O itself). The compiler resolves the
coarse namespace ACL FIRST — the fragment handed to every operator is scoped
to the principal's namespace, so no operator ever reads outside the caller's
partition (the spec's worked example: "L6 resolves the coarse ACL dimension
first ... before any operator runs"). This is fail-closed by construction: a
principal with no namespace can match nothing.

Which operators run, and how they fuse, is the plan-selection Policy's call
(policy.rule_table at v1) — a versioned slot, not a hard-coded choice. Since
Milestone B the fusion is real: every selected operator answers the same
QueryFragment, and the per-operator rankings combine by weighted reciprocal-
rank fusion (RRF, Cormack et al. 2009): score(d) = Σ_ops w_op / (K + rank).
Rank-based fusion is the only sound choice here because CandidateSet scores
are explicitly NOT comparable across operators (grep term counts, ts_rank_cd,
cosine) — RRF never reads them, only the orderings. K = 60, the literature's
conventional damping constant, hand-declared not tuned. A rerank slot
(planner.reranker) then re-scores the fused head when the policy declares a
depth and a real reranker is wired; under the identity reranker the step is
omitted from the plan entirely, so EXPLAIN never claims a rerank that will
not happen.

Every execution persists a full trace (planner.trace) so the plan is
replayable by record afterward.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch

from datum.evidence.sufficiency import SUFFICIENCY_METHOD
from datum.evidence.wrap import build_evidence_state
from datum.groundstore.store import GroundStore
from datum.kernel.errors import PrincipalResolutionError
from datum.kernel.evidence import CalibratedScore, EvidenceState
from datum.kernel.operator import CandidateSet, CostEstimate
from datum.kernel.plan import Budget, CostTrace, Plan, PlanStep
from datum.kernel.principal import Principal
from datum.operators.common import QueryFragment
from datum.operators.registry import OperatorRegistry
from datum.planner.reranker import IdentityReranker, Reranker
from datum.planner.trace import TraceStore
from datum.policy.rule_table import Fusion, RuleTablePolicy

_RRF_K = 60  # Cormack et al.'s conventional damping constant, declared not tuned


@dataclass(frozen=True)
class _Context:
    available_operator_kinds: tuple[str, ...]
    namespace: str = ""  # lets the policy apply per-namespace calibrated overrides


def _plan_id(query: str, principal: Principal, now: datetime) -> str:
    seed = f"{query}\x00{principal.id}\x00{principal.namespace}\x00{now.isoformat()}"
    return "pl_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


#: How many of an operator's OWN top picks are guaranteed a place in the
#: rerank pool regardless of fused rank (decisions.md #38). Deliberately
#: MUCH smaller than `rerank_depth`: the defect this closes is a #1 pick
#: buried by cross-operator RRF summing, so guaranteeing just the top few
#: closes it without flooding the pool with extra competitors. Measured, not
#: assumed — tested against the real stress corpus: depth-sized coverage
#: (adding each operator's own top-16) fixed the targeted case but ALSO
#: pushed an unrelated, previously-correct hit (a chart-value figure) out of
#: the final top-5, a real regression traded for a real win. Coverage of 3
#: fixed the targeted case with zero regressions on the full 42-question
#: two-way diff.
_COVERAGE_TOP_N = 3


def _build_rerank_pool(
    ordered: list[str],
    per_op: dict[str, tuple[str, ...]],
    record_by_id: dict[str, object],
    rrf: dict[str, float],
    depth: int,
    path_glob: str | None,
) -> CandidateSet:
    """The candidate pool fed to rerank: the fused top-`depth` UNIONED with
    each operator's OWN top-`_COVERAGE_TOP_N` ranking (decisions.md #38).

    Plain fused-order truncation lets a candidate several operators agree on
    (each contributing a modest RRF term) outrank a candidate only ONE
    operator found — even when that operator ranked it #1 — because RRF sums
    contributions across operators. Proven on the stress corpus: a record was
    ANN's rank-0 pick yet fused-rank 37, past a depth-16 fused cut, so the
    cross-encoder never got a chance to judge it on its actual content. This
    guarantees every operator's own top few picks always reach the reranker,
    regardless of how cross-operator RRF summing ranks them — the reranker
    still makes the final call by re-scoring the whole pool. The guarantee is
    deliberately narrow (top-`_COVERAGE_TOP_N`, not top-`depth`): widening it
    adds more candidates competing for the final top-k, which measurably
    pushed an unrelated correct hit out of range (see the constant's
    docstring) — the guarantee trades pool size for coverage, so it stays as
    small as the proven defect requires.

    `path_glob` is re-applied here (an operator's raw ranking, unlike
    `ordered`, has not been source-filtered yet) so a caller's narrowing is
    never bypassed by the coverage guarantee.
    """
    seen: set[str] = set()
    pool_ids: list[str] = []
    for rid in ordered[:depth]:
        if rid not in seen:
            seen.add(rid)
            pool_ids.append(rid)
    for ranking in per_op.values():
        for rid in ranking[:_COVERAGE_TOP_N]:
            if rid in seen:
                continue
            if path_glob is not None and not _source_matches(record_by_id[rid], path_glob):
                continue
            seen.add(rid)
            pool_ids.append(rid)
    return CandidateSet(
        records=tuple(record_by_id[rid] for rid in pool_ids),
        scores=tuple(rrf.get(rid, 0.0) for rid in pool_ids),
        score_method="rrf-v1",
    )


def _source_matches(record: object, path_glob: str) -> bool:
    """True if a record's source (its section_path[0], the source id
    DocumentPolicy keys section paths under) matches `path_glob` — the same
    `contracts/**`-style narrowing the search verb advertises."""
    body = record.body  # type: ignore[attr-defined]
    section_path = getattr(body, "section_path", ())
    source = section_path[0] if section_path else ""
    return fnmatch(source, path_glob)


class PlanCompiler:
    def __init__(
        self,
        registry: OperatorRegistry,
        store: GroundStore,
        trace_store: TraceStore,
        policy: RuleTablePolicy | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._trace = trace_store
        self._policy = policy or RuleTablePolicy()
        self._reranker = reranker or IdentityReranker()

    def compile(
        self,
        query: str,
        principal: Principal,
        budget: Budget | None = None,
        *,
        path_glob: str | None = None,
    ) -> Plan:
        if not principal.namespace:
            # Fail closed: no partition to read means nothing is authorized,
            # and that is an error at compile time, not an empty result later.
            raise PrincipalResolutionError(
                "principal has no namespace; a v1 retrieval is scoped to a namespace partition."
            )
        budget = budget or Budget(tokens_max=4000, latency_ms_max=800.0)
        now = datetime.now(timezone.utc)
        plan_id = _plan_id(query, principal, now)

        fusion = self._policy.select(_Context(self._registry.kinds(), principal.namespace))
        # rough token->hit budget, floored at 1: a tiny tokens_max (1..79)
        # used to floor-divide to a LIMIT 0 that returned nothing and reported
        # insufficient_evidence as if the corpus were empty (review finding
        # L1). A retrieval always asks for at least one hit.
        limit = max(1, budget.tokens_max // 80) if budget.tokens_max else 50
        rerank_active = fusion.rerank_depth > 0 and not isinstance(
            self._reranker, IdentityReranker
        )

        steps = (
            PlanStep("acl_filter", {"namespace": principal.namespace}, fails_closed=True),
            *[
                PlanStep(
                    "search",
                    {
                        "operator": k,
                        "query": query,
                        "k": limit,
                        "fusion_weight": fusion.fusion_weights.get(k, 1.0),
                    },
                )
                for k in fusion.operator_kinds
            ],
            # A source filter, when the caller passed one, is a real plan step
            # applied to the fused candidates BEFORE sufficiency (review finding
            # M3): the confidence a caller reads must be computed over the hits
            # it actually gets back, not over the pre-filter set. It is listed
            # BEFORE rerank because that is the order _run executes it (filter
            # the fused set, then rerank the filtered head) — EXPLAIN is the
            # audit view of what actually runs, so the step order must match.
            *([PlanStep("source_filter", {"path_glob": path_glob})] if path_glob else []),
            *(
                [
                    PlanStep(
                        "rerank",
                        {
                            "reranker": f"{self._reranker.name}@{self._reranker.version}",
                            "depth": fusion.rerank_depth,
                        },
                    )
                ]
                if rerank_active
                else []
            ),
            # The abstention gate: if the best dense similarity is below the
            # policy's floor, the plan returns insufficient_evidence rather
            # than surfacing a weak nearest-neighbor. Declared here so it is
            # visible in EXPLAIN (decisions.md #29).
            *(
                [PlanStep("abstain_check", {"min_dense_similarity": fusion.abstain_min_similarity})]
                if fusion.abstain_min_similarity is not None
                else []
            ),
            PlanStep("sufficiency_check", {"method": SUFFICIENCY_METHOD}),
        )

        def _executor(plan: Plan) -> EvidenceState:
            try:
                candidates, cost, agreement = self._run(
                    query, plan.principal, limit, fusion, rerank_active, path_glob
                )
            except Exception as exc:
                # Audit-trail logging is unconditional from v1 (FRAMEWORK.md
                # §MVP definition; decisions.md #27): a search that fails is
                # as auditable as one that succeeds. Persist a terminal
                # error trace naming what broke, THEN re-raise — the failure
                # is not swallowed, only recorded. Persisting must never mask
                # the original error, so its own failure is suppressed.
                self._persist_failure(plan, exc)
                raise
            evidence = build_evidence_state(
                candidates, plan_id=plan.plan_id, cost=cost, agreement=agreement
            )
            self._trace.persist(plan, evidence)
            return evidence

        return Plan(
            plan_id=plan_id,
            steps=steps,
            plan_selector=f"{self._policy.name}@{self._policy.version}",
            principal=principal,
            budget=budget,
            policy_id="default-acl",  # type: ignore[arg-type]
            created_at=now,
            executor=_executor,
        )

    def _persist_failure(self, plan: Plan, exc: Exception) -> None:
        """Persist a terminal error trace for a plan whose execution raised.
        Best-effort: a failure to persist the audit record must not replace
        the original exception the caller needs to see.
        """
        try:
            failed = EvidenceState(
                items=(),
                relevance=CalibratedScore(value=0.0, method="none", calibrated=False),
                conflicts=(),
                sufficiency=0.0,
                status="error",
                plan_id=plan.plan_id,
                cost=CostTrace(total_tokens=0, total_dollars=0.0, total_latency_ms=0.0),
                extra={"error_type": type(exc).__name__, "error": str(exc)[:500]},
            )
            self._trace.persist(plan, failed)
        except Exception:  # pragma: no cover - never mask the real error
            pass

    def _run(
        self,
        query: str,
        principal: Principal,
        limit: int,
        fusion: Fusion,
        rerank_active: bool,
        path_glob: str | None = None,
    ) -> tuple[CandidateSet, CostTrace, float | None]:
        """Run every selected operator over the SAME namespace-scoped
        fragment, fuse by weighted RRF, apply the source filter, optionally
        rerank. Returns the final candidates, the cost trace, and the
        cross-operator agreement fraction (None unless at least two operators
        actually ran — an unmeasured signal is reported as absent, not zero).
        """
        per_op: dict[str, tuple[str, ...]] = {}  # kind -> deduped record-id ranking
        record_by_id: dict[str, object] = {}
        total = CostEstimate()
        by_stage: dict[str, float] = {}
        top_dense_similarity: float | None = None  # best in-namespace cosine, for the abstention gate
        for kind in fusion.operator_kinds:
            operator = self._registry.get(kind)
            fragment = QueryFragment(query=query, namespace=principal.namespace, limit=limit)
            op_plan = operator.plan(fragment, Budget())
            est = operator.cost_model(fragment)
            result = operator.execute(op_plan)
            by_stage[f"search:{kind}"] = float(est.tokens)
            total = CostEstimate(
                tokens=total.tokens + est.tokens,
                dollars=total.dollars + est.dollars,
                latency_ms=total.latency_ms + est.latency_ms,
            )
            is_dense = result.score_method == "cosine"
            # Two guards applied to every operator's output before it can
            # influence fusion, both defense in depth (a correct operator
            # already satisfies them; a modified/buggy one is caught here
            # rather than trusted — the adversarial review's HIGH/MED findings):
            #  1. NAMESPACE BACKSTOP. The gated operator SQL filters on
            #     records.namespace, but the conformance gate cannot see that
            #     SQL (it only exercises the probe path), so a fail-open
            #     operator could register. A record whose writer namespace is
            #     not the caller's is dropped here — the compiler never lets a
            #     cross-partition record reach fusion, EXPLAIN, or evidence.
            #  2. PER-OPERATOR DEDUP. RRF and the agreement signal count
            #     DISTINCT operators; one operator listing a record twice must
            #     contribute once, not inflate rank or fake cross-operator
            #     consensus. Ranking keeps each record's best (first) position.
            seen: set[str] = set()
            ranking: list[str] = []
            for record, score in zip(result.records, result.scores):
                ns = record.provenance.writer.namespace  # type: ignore[attr-defined]
                if ns != principal.namespace:
                    continue
                rid = str(record.id)  # type: ignore[attr-defined]
                # Track the strongest dense similarity among in-namespace hits
                # (the abstention signal), measured on the raw operator score
                # before RRF flattens it to a rank contribution.
                if is_dense and (top_dense_similarity is None or score > top_dense_similarity):
                    top_dense_similarity = score
                if rid in seen:
                    continue
                seen.add(rid)
                ranking.append(rid)
                record_by_id.setdefault(rid, record)
            per_op[kind] = tuple(ranking)

        # Weighted RRF over rankings only — never over raw scores, which the
        # kernel declares incomparable across operators. `found_by` collects
        # the set of operator KINDS that surfaced each record, so agreement is
        # genuine cross-operator corroboration, not repeat listings.
        rrf: dict[str, float] = {}
        found_by: dict[str, set[str]] = {}
        for kind, ranking in per_op.items():
            weight = fusion.fusion_weights.get(kind, 1.0)
            for rank, rid in enumerate(ranking):
                rrf[rid] = rrf.get(rid, 0.0) + weight / (_RRF_K + rank + 1)
                found_by.setdefault(rid, set()).add(kind)
        ordered = sorted(rrf, key=lambda rid: (-rrf[rid], rid))
        # Source filter applied to the fused ranking BEFORE agreement and
        # rerank, so the sufficiency the caller reads is computed over the
        # hits it will actually receive, not the pre-filter set (review M3).
        if path_glob is not None:
            ordered = [rid for rid in ordered if _source_matches(record_by_id[rid], path_glob)]
        ordered = ordered[:limit]
        fused = CandidateSet(
            records=tuple(record_by_id[rid] for rid in ordered),  # type: ignore[misc]
            scores=tuple(rrf[rid] for rid in ordered),
            score_method="rrf-v1",
        )

        agreement: float | None = None
        if len(per_op) >= 2 and ordered:
            agreement = sum(1 for rid in ordered if len(found_by[rid]) >= 2) / len(ordered)

        # Abstention gate (decisions.md #29): dense retrieval always returns
        # its nearest neighbors, so a query whose answer is not in the corpus
        # still yields hits. When the strongest dense similarity is below the
        # policy floor, none of those neighbors is a real match — abstain by
        # returning an empty set, which build_evidence_state turns into
        # `insufficient_evidence`. Grep/BM25-only (no dense signal, floor None)
        # keeps its old empty-means-abstain behavior untouched.
        floor = fusion.abstain_min_similarity
        if floor is not None and (top_dense_similarity is None or top_dense_similarity < floor):
            empty = CandidateSet(records=(), scores=(), score_method="rrf-v1")
            abstain_cost = CostTrace(
                total_tokens=total.tokens,
                total_dollars=total.dollars,
                total_latency_ms=total.latency_ms,
                by_stage=by_stage,
                attributed_fraction=1.0,
            )
            return empty, abstain_cost, None

        candidates = fused
        if rerank_active and fused.records:
            pool = _build_rerank_pool(ordered, per_op, record_by_id, rrf, fusion.rerank_depth, path_glob)
            candidates = self._reranker.rerank(query, pool, len(pool.records))
            by_stage["rerank"] = 0.0  # local compute; no billed tokens at v1

        cost = CostTrace(
            total_tokens=total.tokens,
            total_dollars=total.dollars,
            total_latency_ms=total.latency_ms,
            by_stage=by_stage,
            attributed_fraction=1.0,
        )
        return candidates, cost, agreement
