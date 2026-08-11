"""PlanCompiler fusion tests: weighted RRF over per-operator rankings, the
cross-operator agreement signal, and the rerank slot's declared semantics.

The operators here are canned-ranking fakes, NOT the real grep/BM25/ANN:
fusion is pure rank arithmetic and must be tested against rankings chosen to
expose it (a candidate two operators agree on beating a candidate one ranks
higher; weights flipping an order), which live backends cannot produce on
demand. The fakes still pass the real conformance gate — they are registered
through OperatorRegistry like any operator, so this file also keeps the
"every registered operator handles a conformance probe" rule honest for
planner-level tests. Only the trace store touches Postgres.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from datum.kernel.operator import CandidateSet, CostEstimate, OperatorPlan
from datum.kernel.plan import Budget
from datum.kernel.principal import Principal
from datum.operators.common import execute_conformance, is_conformance_fragment
from datum.operators.conformance.types import make_record
from datum.operators.registry import OperatorRegistry
from datum.planner.compiler import PlanCompiler
from datum.planner.trace import TraceStore
from datum.policy.rule_table import Fusion
from datum.storage.migrations import run_migrations

_DSN = os.environ.get("DATUM_PG_DSN", "postgresql://localhost/datum")
_ACME = "tenant:acme"


def _pg_reachable(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(_DSN),
    reason=f"no reachable Postgres at DATUM_PG_DSN={_DSN!r}",
)

# One shared record pool so operators can rank overlapping candidates.
_RECORDS = {rid: make_record(rid, namespace=_ACME) for rid in
            ("r1", "r2", "r3", "r4", "r5", "r6", "r7")}


class CannedOperator:
    """Returns a fixed ranking for any real QueryFragment; fully conformant
    on probes (via the shared canonical path), so the registry admits it.
    """

    def __init__(self, kind: str, ranking: tuple[str, ...]) -> None:
        self.kind = kind
        self._ranking = ranking

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        n = len(self._ranking)
        return CandidateSet(
            records=tuple(_RECORDS[rid] for rid in self._ranking),
            scores=tuple(float(n - i) for i in range(n)),  # descending, arbitrary scale
            score_method=f"canned-{self.kind}",
        )

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class RepeatingOperator:
    """Returns the SAME record twice (a single operator listing a duplicate) —
    the shape that must NOT inflate RRF rank or the cross-operator agreement
    signal (adversarial review, MED finding on fusion double-counting).
    """

    def __init__(self, kind: str, rid: str) -> None:
        self.kind = kind
        self._rid = rid

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        rec = _RECORDS[self._rid]
        return CandidateSet(records=(rec, rec), scores=(9.0, 8.0), score_method=f"canned-{self.kind}")

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class ForeignNamespaceOperator:
    """Returns a record from a DIFFERENT namespace than the caller's — a
    fail-open operator the conformance gate cannot catch (it only exercises
    the probe path). The compiler's namespace backstop must drop it.
    """

    kind = "rogue"

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        evil = make_record("evil1", namespace="tenant:evil")
        return CandidateSet(records=(evil,), scores=(5.0,), score_method="canned-rogue")

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class CannedDenseOperator:
    """A canned operator that reports a fixed dense COSINE similarity, so the
    abstention floor can be tested deterministically without loading a model
    (decision #29). score_method='cosine' is what the compiler keys the
    abstention signal on.
    """

    kind = "ann"

    def __init__(self, rid: str, similarity: float) -> None:
        self._rid = rid
        self._similarity = similarity

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        return CandidateSet(records=(_RECORDS[self._rid],), scores=(self._similarity,), score_method="cosine")

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class RaisingOperator:
    """An operator whose real query path raises — the shape decision #27 is
    about: a search that fails mid-execution must still leave an audit trace.
    Conformant on the probe path so it registers.
    """

    kind = "boom"

    def plan(self, fragment: object, budget: Budget) -> OperatorPlan:
        del budget
        return OperatorPlan(operator_kind=self.kind, params={"fragment": fragment})

    def execute(self, op_plan: OperatorPlan) -> CandidateSet:
        fragment = op_plan.params["fragment"]
        if is_conformance_fragment(fragment):
            return execute_conformance(fragment)
        raise RuntimeError("operator exploded mid-query")

    def cost_model(self, fragment: object) -> CostEstimate:
        del fragment
        return CostEstimate(tokens=0, dollars=0.0, latency_ms=1.0)


class StaticPolicy:
    """A test policy declaring exactly the fusion the test needs."""

    name = "static-test-policy"
    version = "test"

    def __init__(self, fusion: Fusion) -> None:
        self._fusion = fusion

    def select(self, context: object) -> Fusion:
        del context
        return self._fusion


class ReversingReranker:
    """A fake 'real' reranker: reverses its head and stamps its own method —
    enough to observe that the slot cuts to depth and replaces scores.
    """

    name = "reversing-test-reranker"
    version = "v1"

    def rerank(self, query: str, candidates: CandidateSet, depth: int) -> CandidateSet:
        del query
        head = candidates.records[: min(depth, len(candidates.records))]
        reordered = tuple(reversed(head))
        return CandidateSet(
            records=reordered,
            scores=tuple(float(len(reordered) - i) for i in range(len(reordered))),
            score_method=f"rerank:{self.name}",
        )


@pytest.fixture
def trace_store():
    run_migrations(_DSN)
    with psycopg.connect(_DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE plan_traces")
    store = TraceStore(_DSN)
    yield store
    store.close()


def _compiler(fusion: Fusion, trace_store: TraceStore, reranker=None) -> PlanCompiler:
    registry = OperatorRegistry()
    registry.register(CannedOperator("opa", ("r1", "r2", "r3")))
    registry.register(CannedOperator("opb", ("r3", "r1")))
    # store=None is safe: the compiler never touches the ground store itself,
    # operators do, and these fakes hold no store.
    return PlanCompiler(registry, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                        policy=StaticPolicy(fusion), reranker=reranker)


def _principal() -> Principal:
    return Principal(id="tester", namespace=_ACME)


def test_rrf_fuses_rankings_not_scores(trace_store):
    # opa: r1, r2, r3   opb: r3, r1   (equal weights, K=60)
    # r1: 1/61 + 1/62 > r3: 1/63 + 1/61 > r2: 1/62 alone.
    fusion = Fusion(
        operator_kinds=("opa", "opb"),
        fusion_weights={"opa": 1.0, "opb": 1.0},
        rerank_depth=0,
    )
    plan = _compiler(fusion, trace_store).compile("q", _principal())
    evidence = plan.execute()
    ids = [str(item.record_id) for item in evidence.items]
    assert ids == ["r1", "r3", "r2"]
    assert evidence.extra["sufficiency_method"] == "uncalibrated-heuristic-v2"


def test_fusion_weights_can_flip_the_order(trace_store):
    # Same rankings, but opb's vote now counts 3x: r3 overtakes r1.
    fusion = Fusion(
        operator_kinds=("opa", "opb"),
        fusion_weights={"opa": 1.0, "opb": 3.0},
        rerank_depth=0,
    )
    plan = _compiler(fusion, trace_store).compile("q", _principal())
    evidence = plan.execute()
    ids = [str(item.record_id) for item in evidence.items]
    assert ids[0] == "r3"
    assert set(ids) == {"r1", "r2", "r3"}


def test_single_operator_fusion_preserves_its_ranking(trace_store):
    fusion = Fusion(operator_kinds=("opa",), fusion_weights={"opa": 1.0}, rerank_depth=0)
    plan = _compiler(fusion, trace_store).compile("q", _principal())
    evidence = plan.execute()
    assert [str(i.record_id) for i in evidence.items] == ["r1", "r2", "r3"]


def test_agreement_raises_sufficiency_for_multi_operator_consensus(trace_store):
    # Two operators overlapping on r1/r3 -> agreement measured (2 of 3 fused
    # candidates seen twice). A single-operator run of the same head count
    # reports agreement=None. Consensus must never LOWER the estimate.
    both = Fusion(
        operator_kinds=("opa", "opb"), fusion_weights={"opa": 1.0, "opb": 1.0}, rerank_depth=0
    )
    solo = Fusion(operator_kinds=("opa",), fusion_weights={"opa": 1.0}, rerank_depth=0)
    ev_both = _compiler(both, trace_store).compile("q", _principal()).execute()
    ev_solo = _compiler(solo, trace_store).compile("q", _principal()).execute()
    assert ev_both.sufficiency >= ev_solo.sufficiency
    assert ev_both.sufficiency <= 0.9  # the uncalibrated cap holds


def test_rerank_slot_reorders_and_appears_in_explain(trace_store):
    fusion = Fusion(
        operator_kinds=("opa", "opb"),
        fusion_weights={"opa": 1.0, "opb": 1.0},
        rerank_depth=2,
    )
    plan = _compiler(fusion, trace_store, reranker=ReversingReranker()).compile(
        "q", _principal()
    )
    explain = plan.explain()
    assert "rerank" in explain and "reversing-test-reranker@v1" in explain
    evidence = plan.execute()
    # Fused order is r1, r3, r2. The rerank pool is the fused top-2 UNIONED
    # with each operator's own top-2 (decisions.md #38): opa's own top-2 is
    # (r1, r2), which adds r2 — a plain fused-top-2 cut (r1, r3) would have
    # dropped it. With only 3 distinct records total here the union happens
    # to cover all of them; see the next test for a fixture where the cut
    # is actually visible. ReversingReranker reverses the whole pool:
    # (r1, r3, r2) -> (r2, r3, r1).
    assert [str(i.record_id) for i in evidence.items] == ["r2", "r3", "r1"]


def test_rerank_pool_guarantees_each_operators_top_pick_reaches_rerank(trace_store):
    # decisions.md #38: naive fused-top-depth truncation lets a candidate
    # several operators mildly agree on outrank a candidate only ONE operator
    # ranks highly — even at that operator's #1 position — because RRF sums
    # contributions across operators. opa ranks r1/r2/r3 #1-#3, but opb
    # agrees with opa on r6/r7, so fused order is r7, r6, r1, r2, r3, r4, r5
    # (verified numerically). A depth=2 cut on the fused order ALONE would
    # only ever see {r7, r6} — r1/r2/r3 could never reach the reranker no
    # matter how relevant they are.
    registry = OperatorRegistry()
    registry.register(CannedOperator("opa", ("r1", "r2", "r3", "r4", "r5", "r6", "r7")))
    registry.register(CannedOperator("opb", ("r7", "r6")))
    fusion = Fusion(
        operator_kinds=("opa", "opb"), fusion_weights={"opa": 1.0, "opb": 1.0}, rerank_depth=2
    )
    plan = PlanCompiler(
        registry, store=None, trace_store=trace_store,  # type: ignore[arg-type]
        policy=StaticPolicy(fusion), reranker=ReversingReranker(),
    ).compile("q", _principal())
    evidence = plan.execute()
    ids = {str(i.record_id) for i in evidence.items}
    # Pool = fused top-2 (r7, r6) UNION opa's own top-3 (r1, r2, r3) UNION
    # opb's own top-3 (r7, r6 — already present, only 2 total). r1/r2/r3 now
    # reach the reranker despite being fused-rank 2, 3, 4.
    assert ids == {"r7", "r6", "r1", "r2", "r3"}
    # Still a real, bounded cut — not "give up and rerank everything": r4/r5
    # are opa's rank-3/4 picks (outside its own top-3) and never appear in
    # any operator's top-3, so they are correctly excluded from the pool.
    # (The coverage guarantee is deliberately narrow — top-3, not top-depth —
    # because widening it measurably regressed an unrelated query in the
    # real corpus; see `_COVERAGE_TOP_N`'s docstring.)
    assert "r4" not in ids and "r5" not in ids


def test_identity_reranker_means_no_rerank_step(trace_store):
    fusion = Fusion(
        operator_kinds=("opa", "opb"),
        fusion_weights={"opa": 1.0, "opb": 1.0},
        rerank_depth=2,  # policy declares a depth, but the slot holds identity
    )
    plan = _compiler(fusion, trace_store).compile("q", _principal())
    assert all(step.op_name != "rerank" for step in plan.steps)
    evidence = plan.execute()
    assert [str(i.record_id) for i in evidence.items] == ["r1", "r3", "r2"]  # uncut


def test_single_operator_duplicate_does_not_fake_agreement(trace_store):
    # opdup returns r1 TWICE; opsolo returns r2 once. r1 was surfaced by ONE
    # operator, so it must contribute ONE RRF term and count as zero
    # cross-operator agreement. These assertions are the exact numbers the
    # fix produces and that the pre-fix occurrence-counting bug does NOT:
    #   - relevance.value is max(rrf). Fix: r1 = 1/(60+0+1) = 1/61 ≈ 0.016393.
    #     Bug (double-counted): 1/61 + 1/62 ≈ 0.032522.
    #   - sufficiency v2 with agreement=0.0. Fix ≈ 0.2715; bug (agreement
    #     flips to 0.5 because the duplicate reads as a second "operator")
    #     ≈ 0.4261. `<= 0.9` (the cap) would NOT discriminate — these do.
    registry = OperatorRegistry()
    registry.register(RepeatingOperator("opdup", "r1"))
    registry.register(CannedOperator("opsolo", ("r2",)))
    fusion = Fusion(
        operator_kinds=("opdup", "opsolo"),
        fusion_weights={"opdup": 1.0, "opsolo": 1.0},
        rerank_depth=0,
    )
    compiler = PlanCompiler(registry, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                            policy=StaticPolicy(fusion))
    evidence = compiler.compile("q", _principal()).execute()
    ids = [str(i.record_id) for i in evidence.items]
    assert ids.count("r1") == 1  # duplicate collapsed to one row
    assert evidence.relevance.value == pytest.approx(1 / 61)  # single RRF term, not doubled
    assert evidence.sufficiency == pytest.approx(0.2715, abs=1e-4)  # agreement=0.0, not 0.5


def test_namespace_backstop_drops_foreign_records(trace_store):
    # A fail-open operator returns a tenant:evil record to a tenant:acme
    # caller. The compiler must drop it before fusion — nothing foreign
    # reaches the evidence, even though the operator "passed" registration.
    registry = OperatorRegistry()
    registry.register(ForeignNamespaceOperator())
    registry.register(CannedOperator("opa", ("r1",)))
    fusion = Fusion(
        operator_kinds=("rogue", "opa"),
        fusion_weights={"rogue": 1.0, "opa": 1.0},
        rerank_depth=0,
    )
    compiler = PlanCompiler(registry, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                            policy=StaticPolicy(fusion))
    evidence = compiler.compile("q", _principal()).execute()
    ids = [str(i.record_id) for i in evidence.items]
    assert ids == ["r1"]  # the evil record never reaches the caller
    assert all(i.provenance.writer.namespace == _ACME for i in evidence.items)


def test_abstains_when_dense_similarity_is_below_the_floor(trace_store):
    # Decision #29: dense retrieval always returns neighbors, so a weak match
    # must be gated out. Below the floor -> insufficient_evidence, empty hits;
    # above -> the hit comes through. Floor set explicitly on the Fusion.
    below = Fusion(operator_kinds=("ann",), fusion_weights={"ann": 1.0},
                   rerank_depth=0, abstain_min_similarity=0.63)
    reg = OperatorRegistry()
    reg.register(CannedDenseOperator("r1", similarity=0.40))
    ev = PlanCompiler(reg, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                      policy=StaticPolicy(below)).compile("q", _principal()).execute()
    assert ev.items == ()
    assert ev.status == "insufficient_evidence"
    assert ev.sufficiency == 0.0

    above = Fusion(operator_kinds=("ann",), fusion_weights={"ann": 1.0},
                   rerank_depth=0, abstain_min_similarity=0.63)
    reg2 = OperatorRegistry()
    reg2.register(CannedDenseOperator("r1", similarity=0.80))
    plan = PlanCompiler(reg2, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                        policy=StaticPolicy(above)).compile("q", _principal())
    ev2 = plan.execute()
    assert [str(i.record_id) for i in ev2.items] == ["r1"]
    assert ev2.status == "ok"
    assert "abstain_check" in plan.explain() and "min_dense_similarity=0.63" in plan.explain()


def test_no_abstention_floor_leaves_weak_matches_alone(trace_store):
    # A grep/BM25-only plan (no dense signal) sets no floor, so a weak match
    # is NOT gated — the floor applies only where a cosine signal exists.
    fusion = Fusion(operator_kinds=("opa",), fusion_weights={"opa": 1.0},
                    rerank_depth=0, abstain_min_similarity=None)
    reg = OperatorRegistry()
    reg.register(CannedOperator("opa", ("r1",)))
    plan = PlanCompiler(reg, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                        policy=StaticPolicy(fusion)).compile("q", _principal())
    ev = plan.execute()
    assert [str(i.record_id) for i in ev.items] == ["r1"]
    assert "abstain_check" not in plan.explain()


def test_failed_search_still_persists_an_auditable_trace(trace_store):
    # Decision #27: a search that raises mid-execution must leave a loadable
    # Plan trace with a terminal error status — the audit trail is
    # unconditional — while the exception still propagates to the caller.
    registry = OperatorRegistry()
    registry.register(RaisingOperator())
    fusion = Fusion(operator_kinds=("boom",), fusion_weights={"boom": 1.0}, rerank_depth=0)
    compiler = PlanCompiler(registry, store=None, trace_store=trace_store,  # type: ignore[arg-type]
                            policy=StaticPolicy(fusion))
    plan = compiler.compile("q", _principal())

    with pytest.raises(RuntimeError, match="operator exploded mid-query"):
        plan.execute()  # the failure is NOT swallowed

    # ...but a trace was persisted under this plan_id anyway.
    loaded = trace_store.load(plan.plan_id)
    assert loaded is not None, "a failed search left no audit trace"
    recorded_plan, recorded_evidence = loaded
    assert recorded_evidence.status == "error"
    assert recorded_evidence.items == ()
    assert recorded_evidence.extra.get("error_type") == "RuntimeError"
    assert "exploded" in recorded_evidence.extra.get("error", "")
    # explain() over the failed plan still works (it reads the plan, not the
    # evidence) — the audit view of a retrieval that failed.
    assert "acl_filter" in recorded_plan.explain()


def test_explain_names_every_operator_with_its_weight(trace_store):
    fusion = Fusion(
        operator_kinds=("opa", "opb"),
        fusion_weights={"opa": 1.0, "opb": 2.5},
        rerank_depth=0,
    )
    plan = _compiler(fusion, trace_store).compile("q", _principal())
    explain = plan.explain()
    assert "operator='opa'" in explain and "operator='opb'" in explain
    assert "fusion_weight=2.5" in explain
    assert "acl_filter" in explain and "[fails closed]" in explain
