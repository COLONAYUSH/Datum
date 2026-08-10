# Loom — the learned-policy retrieval framework

*Stance: retrieval that trains itself on production signal. Every decision point is a versioned policy with a default, a logged trace, and a promotion gate — but most policies stay cheap, because the thing nobody has built is the measure→gate→promote loop, not a smarter policy class.*

---

## Design axioms

1. **Learning is a property of the loop, not a mandate for sophistication at each site.** Self-RAG and FLARE fall at or below vanilla RAG under independent FlashRAG re-runs; REPLUG loses to standard RAG on 4/5 datasets; TF-IDF+SVM beats sentence embeddings for routing (`research/01-landscape/advanced-rag-architectures.md` §FlashRAG table, §RAGRouter-Bench baseline). Elaborate learned policies keep losing to cheap ones in independent audits. The architecture must make it *cheap to find out* which is true on a given corpus, not bet the design on any policy being clever.
2. **The decision trace is the training data.** A typed per-stage trace is CI-11's own testable requirement (`common-issues.md` CI-11) and, unmodified, is exactly the (context, action, score) record a policy needs to learn from. Building them as two systems is how frameworks end up with neither.
3. **Nothing is promoted without a statistical gate.** CI-01's restated acceptance criterion is a zero-labeled-data regression signal, offline, no paid tier (`common-issues.md` CI-01); CI-15 shows what happens when a framework grades its own homework with an uncalibrated judge. The gate must use calibrated judges (ARES/PPI-style intervals, Chroma-style aligned filtering) or it doesn't count as a gate.
4. **Feedback is guilty until debiased.** Click-through, accept/reject, and regenerate signals are exposure-biased by construction; unbiased learning-to-rank has been settled theory since 2016 and RAG re-imported none of it (`common-issues.md` CI-16). Every logged decision carries the propensity that produced it, or it cannot train anything.
5. **Learnability is declared, not assumed.** Google's own commerce search needs ≥250k logged events to tune ranking (`common-issues.md` CI-16); most enterprise RAG tenants will never see that volume for most decisions. "Still on the default; N events until eligible" is a first-class, visible state, not a silent failure.
6. **A permission boundary is a precondition, not a policy input.** Exploration for off-policy learning must never explore outside a principal's entitlement set — a policy that broadens candidates for exploration purposes is a CI-05/CI-03-class vulnerability wearing an ML costume.
7. **The corpus is the durable artifact; every index and every policy is a disposable, rebuildable derived view.** This is CI-07's corrected acceptance target — framework-owned state that can rebuild any vendor index from scratch, not a promise to migrate a vendor's index in place (`common-issues.md` CI-07, Steelman).
8. **Stability is load-bearing.** The kernel — the `Policy` interface, the `retrieve()` signature, the trace and feedback schemas, and the closed list of decision points — is semver-frozen; only the policy implementations inside it churn (`common-issues.md` CI-08).

**Where the brief's non-negotiables land.** Retrieval is consumed by trained agent policies via tools, not hand-wired pipelines — `retrieve()` is the only tool surface, and its shape (query, filters, budget, provenance, confidence) deliberately mirrors CI-24's own testable requirement so it reads to a model like the affordances it already trusts, rather than a bespoke wrapper the model's RL-instilled grep-preference will route around (`common-issues.md` CI-24; practitioners report models "so heavily RL'd with grep that they do not trust results in other forms"). Single-vector embeddings' proven capacity ceiling (LIMIT, arXiv:2508.21038) is why representation choice is decision point 5 and defaults to routing compositional queries away from single-vector search rather than trusting one embedding space universally. Parsing fidelity dominating chunking sophistication (OHR-Bench, `common-issues.md` CI-02) is why `CorpusStore` treats the canonical structural IR, not the chunker, as the artifact worth versioning. Incremental mutation as the common case, not the exception, is why L0 is lineage-tagged derived views over a canonical store rather than a write-once index (CI-06/CI-07). Permission-aware retrieval as a hard enterprise requirement is why `retrieve()` does not typecheck without a principal (CI-05). And the over-abstraction/underspecification trap is confronted directly in Anti-scope below with a closed, numbered decision-point list and a stated amendment cost, rather than an open-ended plugin philosophy in either direction.

---

## The core insight

The provocation for this design says every framework ships frozen 2023 heuristics because nothing in the architecture learns. That is half right, and the half that's wrong is the important half.

Things in this ecosystem *have* tried to learn, at almost every decision point the provocation names, and the independent audits are damning: Self-RAG's reflection tokens score at or below vanilla RAG on 4 of 5 FlashRAG datasets; FLARE's confidence trigger hits retrieval-timing accuracy of 56.5% — barely above chance-plus — while UAR's four-criteria classifier gets 85.3% and is itself beaten in QA quality by 27 plain uncertainty estimators that need no training at all (Moskvoretskii et al., arXiv:2501.12835); CRAG's learned retrieval evaluator turns out, on SHAP analysis, to be doing named-entity string matching, not relevance judgment, and collapses on domain shift; RAGRouter-Bench's own baseline study finds TF-IDF+SVM beats sentence-embedding routers by 3.1 macro-F1; classical query-performance prediction, a two-decade-old field, is *shown* to degrade significantly on neural retrieval and fail to generalize across collections and retriever architectures (Faggioli et al., ECIR 2023, arXiv:2302.09947; Chifu et al., arXiv:2504.01101) — precisely the per-deployment transfer a "ship a smart policy" design would need to assume away. FrugalRAG's own audit of the RL wave (arXiv:2507.07634) finds that reinforcement-learned search agents' real, replicated advantage over well-tuned prompting is *halving retrieval calls at matched accuracy*, not the double-digit accuracy jumps the original papers claimed against under-tuned baselines. `advanced-rag-architectures.md`'s own synthesis states the partition plainly: value concentrates in trained multi-step evidence integration (CoRAG, AutoRefine — sequence-level trained chains), not in decision-making scaffolding (routers, triggers, evaluators) — and calls that partition itself an unproven, testable claim (O7).

So the honest reading of "nothing learns" is not "nobody tried a learned policy." It is: **nobody built the infrastructure that finds out, per deployment and continuously, whether a proposed change to a cheap heuristic is actually better on this corpus — and safely tries it if so.** That infrastructure is what's missing, and it is mostly plumbing — measurement, debiasing, statistical gating, rollback — not exotic ML. The corpus's own evidence about *where* the plumbing pays off is specific: the Coverage Illusion production study (arXiv:2605.27220, cited in `evaluation-benchmarks.md` §Production evaluation) found pre-retrieval query-augmentation routing structurally unlearnable before index contact — four independent ML approaches failed — while a *post-retrieval* escalation cascade (decide to re-rank/re-query/abstain after seeing what came back) delivered +0.140 composite quality and −31.8% latency. That is direct evidence about which side of the pipeline is worth teaching to learn: post-retrieval control (stop/abstain, rerank depth, escalation) over pre-retrieval routing (parse route, query transformation), which should default to the cheapest thing that clears its bar (lexical features, score-distribution thresholds) and stay there unless proven wrong on this corpus.

This reframes the provocation's ambition rather than abandoning it. The learnable unit in Loom is not "a policy that is smart." It is "a policy whose default is honest, whose trace is a training example, whose challenger must clear a calibrated statistical bar before it sees production traffic, and whose regression triggers an automatic rollback." Most of the 8 decision points below should, on most corpora, stay on cheap defaults forever — and the framework's job is to prove that, continuously, rather than assume it once at ship time (which is CI-14's disease) or assume the opposite and bolt on unaudited cleverness (which is what Self-RAG, FLARE, and CRAG's evaluator turned out to be).

---

## Architecture

```
                              ┌─────────────────────────────────────────────┐
                              │  L8  Operator Console / Safety Rails         │
                              │  policy cards · pin/rollback · kill switch   │
                              └───────────────────────▲───────────────────────┘
                                                       │
┌────────────┐   retrieve(intent, principal,   ┌───────┴────────┐    typed evidence-state
│  Agent /    │   budget, policy_profile)       │  L1 Policy      │    + insufficient_evidence
│  consuming  ├────────────────────────────────►│  Kernel         ├──────────────────────────►
│  system     │◄────────────────────────────────┤  (frozen types) │
└────────────┘                                  └───────┬────────┘
                                                          │ fires, in sequence, against
                                                          │ the closed decision-point list
                                       ┌──────────────────┴──────────────────┐
                                       │  L2  Decision Points (8, versioned)  │
                                       │  parse-route · granularity ·         │
                                       │  representation · query-transform ·  │
                                       │  retrieval-depth · fusion-weights ·  │
                                       │  rerank-cascade · stop/abstain       │
                                       │  each: default heuristic + optional  │
                                       │  learned challenger, gated per-tier  │
                                       └──────┬────────────────────────┬──────┘
                                              │ every decision logged  │ reads/writes
                                              ▼                        ▼
                                  ┌───────────────────────┐   ┌──────────────────────┐
                                  │ L3 Trace & Telemetry   │   │  L0 Corpus Store      │
                                  │ Bus (typed, append-    │   │  canonical parsed     │
                                  │ only, per-request)     │   │  docs + lineage-      │
                                  └──────────┬─────────────┘   │  tagged derived views │
                                             │                 │  (chunks/vectors/     │
                       async, tagged by      │                 │  graphs), vendor index│
                       trace id               ▼                 │  = disposable view    │
                                  ┌───────────────────────┐     └──────────────────────┘
                                  │ L4 Feedback Capture &  │
                                  │ Debiasing (propensity  │
                                  │ logging, IPS/click     │
                                  │ models, admission      │
                                  │ control on writes)     │
                                  └──────────┬─────────────┘
                                             ▼
                                  ┌───────────────────────┐     ┌──────────────────────┐
                                  │ L5 Eval Harness         │◄──►│ L6 Promotion Pipeline │
                                  │ corpus-derived golden   │    │ champion/challenger,  │
                                  │ sets, calibrated judges │    │ statistical gate,     │
                                  │ (ARES/PPI, Chroma-style │    │ canary, auto-rollback │
                                  │ aligned filtering)      │    │                       │
                                  └───────────────────────┘     └──────────┬────────────┘
                                                                            │ promotes/rolls back
                                                                            ▼
                                                            ┌──────────────────────────┐
                                                            │ L7 Drift & Poisoning       │
                                                            │ Monitors: corpus telemetry,│
                                                            │ query-distribution drift,  │
                                                            │ feedback-channel anomaly   │
                                                            │ detection (self-poisoning) │
                                                            └──────────────────────────┘
```

**Why these layers, specifically.** `common-issues.md`'s own closing section names five load-bearing inversions a next-generation framework needs, derived from the full 27-issue taxonomy rather than from any single issue. Loom's layers map onto them directly rather than incidentally: L5's measurement-as-default-artifact is inversion (1) verbatim; L1's typed kernel carrying principal/budget/provenance is inversion (2); L0's canonical-documents-with-lineage-tagged-views is inversion (3); L2's loop-native decision points firing identically per call regardless of loop shape is inversion (4); and the conformance-suite discipline inherited at every store/adapter boundary (noted throughout the traceability table below) is inversion (5). The point of naming this explicitly is that Loom does not treat the 27 issues as a checklist to satisfy piecemeal — it targets the five mechanisms the taxonomy itself says generate most of the 27, and accepts that a few issues downstream of *other* root causes (open-core economics driving platform death, CI-08; adoption-driven security debt, CI-13) are not mechanisms this architecture can reach.

**Data flow.** A request enters through the frozen kernel signature carrying a principal, a policy profile, and a budget. The eight decision points fire in a fixed order, each consulting its *current champion* policy (default heuristic unless a challenger has been promoted); each firing logs its context, the candidates it considered, the action taken, the propensity of that action under whatever exploration distribution produced it, and its cost, into the trace. The response — a typed evidence-state, never a bare list, carrying calibrated relevance/coverage signals and a first-class `insufficient_evidence` outcome (CI-10's acceptance target) — is returned with a trace id. Feedback (explicit ratings, or implicit accept/reject/regenerate/citation-click/downstream-task-success wired in by the consuming agent) arrives asynchronously, tagged to that trace id, and passes through admission control and debiasing before it becomes training data. Per decision point, on a schedule gated by its declared feedback tier (below), a challenger is trained offline, evaluated against both the corpus-derived golden set and replayed production traffic, and only promoted if it clears a pre-registered statistical bar with no regression on guardrail metrics (cost, latency, per-slice quality). Drift and poisoning monitors watch the whole loop and can freeze any policy back to its default unilaterally.

**Worked example — one query, end to end.** A support agent asks "what's our refund policy for enterprise customers in the EU?" on behalf of a logged-in principal with `region:EU` entitlements:

1. `retrieve()` receives `(intent, principal, budget=800ms/4k tokens, policy_profile)`. No principal → the call does not typecheck; this is CI-05 enforced at the language level, not a runtime check that can be skipped.
2. Decision point 8 (parse route) and 6 (granularity) are corpus-level, not re-decided here — the request reads the already-built `chunks-v3`/`vectors-e5v3` derived views from `CorpusStore`.
3. Decision point 7 (query transformation) fires the lexical router default: this query's surface features look like a factual lookup, not a decomposition-worthy multi-hop question, so it passes through with no rewrite — logged with propensity 1.0 (deterministic default, no exploration at this tier yet).
4. Decision point 5 (representation choice) checks for LIMIT-flagged compositional structure (multiple independent constraints needing to co-rank); this query has one constraint (EU enterprise refund policy), so it stays on the default hybrid dense+sparse path rather than escalating to a structured/multi-vector route.
5. Decision points 3 and 4 (retrieval depth, fusion weights) run: if fusion weights are still Tier A for this tenant, the benchmarked static weights fire; if they crossed their floor months ago, the current champion bandit policy selects weights conditioned on corpus-slice features and logs its actual propensity for later IPS correction.
6. The candidate set is filtered by the principal's entitlements *before* decision point 2 (rerank cascade) ever sees it — exploration at any learned stage downstream operates only inside this already-authorized set, honoring the permission-boundary-as-precondition axiom.
7. Decision point 1 (stop/abstain) computes an NQC-style score-variance signal over the reranked set; if it clears the calibrated sufficiency threshold, the call returns a typed `EvidenceState` with provenance and cost spent; if not, it returns `insufficient_evidence` and the trace records exactly which stage's signal triggered the abstention.
8. The full `DecisionTrace` — eight potential stage entries, though only the ones that actually branched away from a pure default carry a non-trivial propensity — is persisted with the response's trace id.
9. The agent surfaces an answer with citations; the user clicks one citation and does not regenerate. `loom.feedback.emit(trace_id, "citation_click", 1.0)` fires asynchronously, is admission-controlled, and lands in the feedback store tagged to every stage in that trace, debiased against each stage's logged propensity before it can influence anything.

### The eight decision points and their learnability tiers

The provocation names eight decision points; the Coverage Illusion result and the deflation literature above argue they are not equally worth teaching to learn, and the CI-16 feedback-floor number argues they are not equally *learnable* from a typical enterprise tenant's traffic. Loom declares both dimensions up front instead of pretending uniformity:

| # | Decision point | Default (Tier A: cheap, ships day 1) | Feedback floor to attempt a learned challenger | Primary reward source |
|---|---|---|---|---|
| 1 | Stop / abstain | NQC-style score-variance threshold + calibrated `insufficient_evidence` gate | ~10²–10³ (few parameters, strong prior) | debiased accept/regenerate signal |
| 2 | Rerank cascade depth | fixed hybrid→cross-encoder cascade, static prune width | ~10³ | debiased citation-click / task-success |
| 3 | Retrieval depth (k, iterate) | k∈[3,10] with reranking (settled IR practice, `common-issues.md` CI-14) | ~10³–10⁴ | debiased accept/regenerate + cost |
| 4 | Fusion weights | fixed hybrid weights from a benchmarked profile | ~10³–10⁴ | contextual bandit on debiased reward |
| 5 | Representation choice (dense/sparse/multi-vector/structured) | corpus-statistics-driven static rule (LIMIT-aware: route compositional/multi-constraint queries away from single-vector) | ~10⁴ | golden-set win-rate, rarely production-fed |
| 6 | Granularity / chunk boundary | structure-aware default (headings/tables preserved), not re-decided per query | corpus-level, not per-query; re-tuned on ingest-time eval only | golden-set win-rate on re-ingest |
| 7 | Query transformation (rewrite/expand/decompose/route) | lexical router (TF-IDF-class features per RAGRouter-Bench's own deflationary result) + no-op default | ~10⁴–10⁵, and only for the *routing* decision, not full RL rewriting | golden-set + debiased downstream signal |
| 8 | Parse route (per-document-type ingestion path) | rule-based by MIME/structure detection | corpus-level, not per-query | ingest-time golden-set only |

Rows 1–4 (post-retrieval control) are where Loom concentrates learning effort, following the Coverage Illusion evidence that this side of the pipeline is where learning actually paid off in a production deployment. Rows 5–8 (pre-retrieval / corpus-level decisions) default to cheap, corpus-statistics-driven rules and are re-evaluated primarily against the golden set at ingest time, not against noisy per-query production feedback — consistent with the finding that pre-retrieval routing was unlearnable before index contact, and with RAGRouter-Bench's finding that lexical features already do the routing job. **A tenant whose traffic never crosses the row-4 floor is not broken — it is a framework in Tier-A-only mode, and the operator console says so explicitly.**

### Training loop mechanics

Three mechanics make the loop trustworthy rather than merely present:

1. **Off-policy reward estimation, not raw reward averaging.** A logged `FeedbackEvent` is only usable for training after it is converted into a debiased, per-action value estimate. Loom uses an inverse-propensity-weighted (IPS) estimator with a doubly-robust correction (a learned reward model as the "direct method" component, blended with the IPS term so that a poorly-calibrated propensity doesn't blow up variance):

   ```
   V̂(π) = (1/n) Σ_i [ r̂(x_i, π(x_i))
                        + (π(a_i|x_i) / p_i) * (r_i − r̂(x_i, a_i)) ]
   ```

   where `p_i` is the logged propensity from `StageTrace.propensity`, `π` is the challenger being scored, and `r̂` is a small reward model fit on the same logs. This is exactly the AIPW/doubly-robust family standard in off-policy evaluation for classical ranking and bandits — imported, not invented, per the provocation's own citation of debiased learning-to-rank as settled theory.
2. **Always-valid sequential testing, not a single end-of-window t-test.** Because feedback accrues continuously and a team will look at the dashboard whenever they feel like it, a promotion decision computed with a fixed-horizon significance test is exposed to peeking-inflated false-promotion rates. The gate uses an always-valid confidence sequence (mSPRT/e-process family) so "check now" never invalidates the statistics — this is the concrete mechanism behind `min_effect_size` being "pre-registered, not post-hoc" in the `PromotionGate` sketch above.
3. **Canary before full rollout, with an automatic trigger to roll back, not just a manual one.** A promoted challenger runs at a declared traffic percentage; the same guardrail metrics that gated promotion (cost, p99 latency, worst-slice quality) are monitored continuously during canary, and a regression on any of them reverts to the champion without requiring a human to notice first. A human is notified either way.

---

## Core abstractions & API

### 1. `Policy[Context, Action]` — the one interface every decision point implements

```python
from typing import Protocol, TypeVar, Generic

Context = TypeVar("Context")
Action = TypeVar("Action")

class Policy(Protocol, Generic[Context, Action]):
    version: str                      # semver; bumped on any behavior change
    tier: Literal["A", "B", "C"]       # declared learnability tier (feedback floor)

    def decide(self, ctx: Context) -> tuple[Action, "TraceFragment"]:
        """Must return the action AND the propensity/candidates that produced it —
        no policy may return a bare action; that is how CI-16 recurs."""

    def default(self) -> "Policy[Context, Action]":
        """Every policy can name its own frozen fallback. Fallback is not optional."""
```

Day-1 usage — nobody writes a `Policy`, they just retrieve:

```python
import loom

evidence = loom.retrieve(
    intent="What was Q3 revenue in the EMEA region?",
    principal=current_user,             # required — see CI-05
    budget=loom.Budget(max_tokens=4000, max_latency_ms=800),
    policy_profile="2026-hybrid-rerank",  # dated, benchmarked, versioned default
)
if evidence.status == "insufficient_evidence":
    escalate_or_ask_clarifying_question(evidence.trace_id)
```

Expert usage — register a challenger for one decision point without touching anything else:

```python
class MyFusionPolicy(loom.Policy[loom.FusionContext, loom.FusionWeights]):
    version = "0.3.0"
    tier = "B"

    def decide(self, ctx):
        weights = self.bandit.select(ctx.features)   # e.g. LinUCB over corpus-slice features
        return weights, loom.TraceFragment(candidates=self.bandit.arms, propensity=self.bandit.p(weights))

    def default(self):
        return loom.StaticFusionPolicy(weights=BENCHMARKED_DEFAULT)

loom.registry.register_challenger("fusion-weights", MyFusionPolicy(), promotion_gate=loom.PromotionGate(
    min_events=3000, min_effect_size=0.02, judge=loom.CalibratedJudge(slice="emea-finance"),
))
```

### 2. `retrieve()` — the frozen kernel signature

```python
def retrieve(
    intent: str,
    principal: Principal,             # CI-05: does not compile without one
    budget: Budget,                   # CI-09: {max_tokens, max_latency, max_cost}
    policy_profile: str = "2026-hybrid-rerank",
) -> EvidenceState:
    """Semver-frozen for ≥12 months per release (CI-08). Everything else may churn."""
```

`EvidenceState` is a typed evidence-state, not a bare list: calibrated relevance, coverage/sufficiency, freshness, provenance per item, cost spent, and a first-class `insufficient_evidence` variant (CI-10's acceptance target, verbatim).

### 3. `DecisionTrace` — the artifact that is simultaneously the debugger and the training set

```python
@dataclass
class DecisionTrace:
    request_id: str
    principal_id: str                          # for erasure propagation, never for training features directly
    stages: list["StageTrace"]                 # one per decision point that fired, in order
    corpus_manifest: CorpusManifest             # pinned (parser version, chunker version, embedder version, index snapshot)
    total_cost: Cost

@dataclass
class StageTrace:
    decision_point: str                         # one of the 8
    policy_id: str; policy_version: str
    candidates: list[Candidate]                 # what else was considered — required for IPS
    action: Action
    propensity: float                            # P(this action | this policy, this context)
    score: float | None                          # e.g. NQC-style variance, sufficiency estimate
    cost: Cost
```

Byte-identical schema whether the caller is a single-shot pipeline or an agent loop calling `retrieve()` N times per turn — this is CI-12's superset rule and CI-11's static/agentic trace parity requirement, satisfied by construction rather than by a parity test bolted on afterward.

### 4. `FeedbackEvent` — typed, propensity-carrying, admission-controlled

```python
@dataclass
class FeedbackEvent:
    trace_id: str
    signal: Literal["accept", "reject", "regenerate", "citation_click", "explicit_rating", "task_success"]
    value: float
    observed_at: datetime
    # propensity is NOT supplied by the caller — it is looked up from the DecisionTrace
    # this is what makes IPS debiasing possible instead of optional

loom.feedback.emit(trace_id=evidence.trace_id, signal="citation_click", value=1.0)
```

Every event passes through admission control (rate limits, anomaly scoring against the feedback-channel's own baseline distribution) before it is eligible to influence any policy — see Risks, "the feedback channel is a new attack surface."

### 5. `CorpusStore` — canonical documents, lineage-tagged derived views

```python
store = loom.CorpusStore(canonical="s3://acme-docs/")
store.derive("chunks-v3", producer="structure_chunker@2.1", from_="canonical")
store.derive("vectors-e5v3", producer="embedder@e5-mistral-v3", from_="chunks-v3")
# any vendor index is rebuildable on command from `store` alone — CI-07's corrected target
store.rebuild_index("bedrock-kb-prod", target="vectors-e5v3")
```

### 6. `EvalHarness` — corpus-derived, judge-calibrated, zero-label-to-start

```python
golden = loom.EvalHarness.bootstrap(corpus=store, n=400)   # generative benchmarking, Chroma-style
golden.calibrate_judge(human_anchor_slice=50, method="ARES-PPI")  # CI-15 self-collision guard
report = golden.evaluate(policy_profile="2026-hybrid-rerank")
```

### 7. `PromotionGate` / policy registry — the champion/challenger loop

```python
gate = loom.PromotionGate(
    min_events=3000,                     # tier floor for this decision point
    min_effect_size=0.02,                # pre-registered, not post-hoc
    guardrails=["cost", "p99_latency", "worst_slice_quality"],
    judge=golden,
)
result = loom.registry.evaluate_challenger("fusion-weights", gate)
if result.promoted:
    loom.registry.canary("fusion-weights", traffic_pct=5, rollback_on="any_guardrail_regression")
```

### 8. `DriftMonitor` — the abstraction that owns the risk this design creates

```python
class DriftMonitor:
    """Watches three things a learning system must watch that a frozen one doesn't need to:
    query-distribution drift, corpus drift, and feedback-channel anomalies (the self-poisoning
    and reward-hacking surface named in Risks). Any one tripping freezes the affected policy
    back to its `default()` — unilaterally, before a human is paged, not after."""

    def check_query_drift(self, window: TraceWindow) -> DriftReport: ...
    def check_corpus_drift(self, store: CorpusStore) -> DriftReport:
        # dedup rate, freshness, provenance mix, embedding-outlier score —
        # "corpus performance prediction" telemetry, per retrieval-training-lineage.md §6/O2,
        # used here as a heuristic input, not a validated predictive theory
        ...
    def check_feedback_anomaly(self, events: Iterable[FeedbackEvent]) -> AnomalyReport:
        # reward-distribution shift, coordinated-source detection, correlation with recent
        # writes to the corpus by the same principal (the self-poisoning shape from CI-04)
        ...

    def on_trip(self, report, policy_id: str):
        loom.registry.freeze(policy_id, reason=report.reason)  # reverts to Tier-A default
        loom.console.notify(report)                             # human sees it; doesn't gate it
```

Making this its own abstraction, rather than a background cron job bolted onto the promotion pipeline, is deliberate: it is the component that owns the fact that a learning system has an attack surface a frozen one does not, and it is designed to act (freeze) before it explains (notify), because the whole point of the self-poisoning shape is that a human reviewing a dashboard is the slow path, not the safety mechanism.

---

## Cold start, feedback sparsity, and operating without ML expertise

The provocation asks this design to confront three things directly rather than gesture at them. Here is the confrontation.

**Cold start.** On day one there is no production feedback at all, by definition. Loom does not wait for it: `EvalHarness.bootstrap()` generates a corpus-derived golden set (Chroma-style generative benchmarking — aligned-judge filtering measured elsewhere at 46%→75.2% human alignment over iterations) before a single query is served, and every decision point ships on its Tier-A default, benchmarked against that golden set, not against a hoped-for future feedback stream. A tenant can run for months on golden-set-validated defaults alone and get the CI-01/CI-11/CI-14 wins with zero production learning — this is not a degraded mode, it is the design's baseline mode, and "still on defaults" is not shameful the way frozen 2023 heuristics are, because it is continuously re-validated against a live, corpus-derived golden set rather than fixed once and forgotten.

**Feedback sparsity.** Most enterprise tenants will never reach the ≥250k-event floor Google's own commerce search needs (`common-issues.md` CI-16). Loom's response is not to lower the bar for what counts as "learned" until small numbers look sufficient — that is how CRAG's evaluator ends up doing entity matching and calling it relevance judgment. Instead: the eight-decision-point tiering table above is the sparsity plan, stated as numbers instead of aspiration. A decision point below its declared floor stays on Tier A and is re-evaluated only against the golden set (which can be regenerated indefinitely at no feedback cost) — this is strictly worse than real production learning but strictly better than either freezing forever (CI-14) or pretending 200 noisy clicks constitute a trained policy (the FLARE/Self-RAG failure mode). A concrete walkthrough for a mid-size enterprise deployment: **Day 1** — golden-set-validated Tier-A defaults only, full tracing on, feedback capture wired but inert. **Month 1** — stop/abstain (decision point 1) crosses its ~10²–10³ floor first, because every query produces a stop/continue decision; its first challenger enters shadow mode. **Month 3–6** — fusion weights and retrieval depth (points 3–4) cross their ~10³–10⁴ floors if query volume supports it; query-transformation routing (point 7) typically does not, and stays on its lexical default indefinitely at this scale — the console reports this plainly rather than silently understating it.

**Operating without ML expertise.** No step in the promotion path requires a human to tune a bandit, choose a learning rate, or read a p-value. The operator-facing surface is three actions, each a plain-language translation of a statistical fact:
- *"Policy X is eligible for promotion — it improved [metric] by [Y%] on [N] events with no regression on cost or latency. Approve / hold."* — a yes/no on a pre-computed, pre-gated recommendation, not a request to design an experiment.
- *"Policy Y was rolled back automatically — [guardrail] regressed during canary."* — a notification, not a decision; the rollback already happened.
- *Pin / kill switch* — revert one decision point, or the entire profile, to its frozen Tier-A default, unconditionally, at any time, for any reason (including "we don't trust this and want to think about it").

This closes the loop the provocation demands (implicit feedback → debiasing → adaptation) without requiring the team running it to be able to build that loop themselves — which is the actual, historically demonstrated failure mode this stance has to avoid: a framework that requires ML expertise to operate safely will be operated unsafely, or not operated at all, by exactly the teams `common-issues.md`'s open-core analysis says make up most of the market.

---

## Issue-coverage traceability

Verdicts use the taxonomy's RESTATED claims and acceptance criteria, not the headline names.

| Issue | Restated claim (acceptance target) | Verdict | How Loom addresses it |
|---|---|---|---|
| CI-01 | Integrated, self-maintaining regression loop, zero labeled data, offline, no paid tier | **solved** | `EvalHarness.bootstrap()` generates a corpus-derived golden set with no user labels; every promotion is gated on it in OSS core |
| CI-02 | Structure/provenance survive only by convention; needs enforced, typed IR + cross-stage contract validation | **mitigated** | `CorpusStore` canonical docs carry a typed structural IR with lineage; contract validation is a merge gate for new decision-point defaults, not a solved parsing-fidelity problem (OHR-Bench's ~14% F1 gap is a research frontier, not addressed) |
| CI-03 | One typed filter algebra + mandatory cross-backend conformance suite | **mitigated** | inherited discipline: every store adapter admitted to L0 must pass the conformance suite before it can back any decision point; this design does not innovate on filter algebra itself |
| CI-04 | Typed, propagating, enforcement-grade provenance; retrieved text structurally cannot reach the instruction position | **mitigated** | `StageTrace`/`CorpusStore` carry provenance and trust tier through the pipeline and into the feedback loop (closing the self-poisoning corollary specifically); structurally preventing retrieved text from reaching the instruction position remains the acknowledged research frontier per CI-04 itself |
| CI-05 | `retrieve()` does not compile without a principal; mandatory entitlement suite | **mitigated** | kernel signature enforces this in OSS core (no paywall); the expensive half — connector-side ACL mirroring and identity sync — is vendor/connector work outside the framework's reach, per CI-05's own steelman |
| CI-06 | Incremental mutation + *verified, orchestrated* erasure with a completion proof | **mitigated** | lineage-tagged derived views make mutation O(changed content); `erase()` is extended to propagate to `DecisionTrace`/`FeedbackEvent` records (a harder target than CI-06's own acceptance criterion); verified unrecoverability at the ANN-index layer remains open |
| CI-07 | Framework's own canonical state suffices to rebuild any vendor index from scratch (corrected target — not in-place vendor migration) | **mitigated** | exactly `CorpusStore.rebuild_index()`; in-place migration of closed managed backends (Bedrock, Snowflake, OpenAI vector stores) is explicitly out of reach, matching the corrected acceptance test |
| CI-08 | Semver-stable retrieval kernel, ≥12-month compatibility, churn quarantined to orchestration | **mitigated** | the `Policy`/`retrieve()`/`DecisionTrace` kernel is the stable surface; policy implementations are the quarantined churn zone. Does not fix the open-core economics that drives platform death elsewhere in the ecosystem |
| CI-09 | Budget is a typed, enforced input; degrades gracefully; ≥95% of cost attributed per stage | **mitigated** | `Budget` is a required kernel parameter; `StageTrace.cost` attributes spend per decision point by construction; graceful tier-wise degradation is a designed property of each policy's `default()`, not automatically guaranteed for every custom policy an expert writes |
| CI-10 | Calibrated evidence-state with first-class `insufficient_evidence`; shipped signal beats raw top-1 similarity | **mitigated** | `EvidenceState` is exactly this; calibration transferring across RLHF'd model families without per-deployment recalibration is the open half (Faggioli/Chifu) — Loom recalibrates per deployment via the golden set rather than assuming a universal signal |
| CI-11 | Typed per-stage trace, enumerable prompt/policy registry, static/agentic trace parity, all as default artifacts | **solved** | `DecisionTrace` is schema-identical across static and agentic call patterns by construction; every policy is registry-addressable and versioned |
| CI-12 | Loop-native executor; agentic path is a strict superset of the static path; memory writes get transactional discipline | **mitigated** | decision points fire identically per `retrieve()` call regardless of loop shape, satisfying the superset rule (the surviving core per the taxonomy's own round-2 narrowing); `FeedbackEvent` writes carry idempotency keys, partially addressing the memory-transactionality leg — full checkpoint/replay of long agent loops is not designed here |
| CI-13 | Five security surfaces closed by construction (template injection, filter SQLi, config RCE, ingestion sandboxing, code-exec sandboxing) | **unaddressed** | orthogonal to the learned-policy stance; Loom inherits whatever discipline the kernel's chosen implementation stack ships, but does not treat this as a design contribution |
| CI-14 | Dated, versioned, benchmark-backed default profiles; zero-config harness reports recall/nDCG for the active profile | **solved** | `policy_profile="2026-hybrid-rerank"` is exactly this, and the promotion pipeline exists specifically to keep the profile from freezing the way CI-14 describes |
| CI-15 | Replicable-by-construction eval claims; calibrated, bias-audited judges; statistical-power reporting | **mitigated** | `EvalHarness.calibrate_judge()` requires an ARES/PPI-style human-anchored slice before any judge score can gate a promotion — a direct pre-emption of the CI-01-steelman's "this is what CI-15 condemns" collision |
| CI-16 | Feedback reaches the retriever via a debiased loop; a plan for deployments below the 250k-event floor | **mitigated** | this is the design's central mechanism; the declared per-decision-point feedback tiers are the explicit sub-floor plan, but a tenant genuinely below Tier A's ~10²–10³ floor gets no learning at all — honestly, not silently |
| CI-17 | Docs executed in CI; issues close only with resolution state; machine-readable known-issues registers | **unaddressed** | kernel stability (CI-08) reduces the rate at which docs go stale, but this is not a designed CI/doc-governance system |
| CI-18 | Every shipped stage re-implementable out-of-tree via public APIs, ≤5-line swap | **mitigated** | every built-in decision point is itself a `Policy` registered through the same interface an expert uses — the extension gradient is the day-1 interface, not a separate escape hatch |
| CI-19 | Streaming ingestion under a hard memory cap with kill-9 resume | **unaddressed** | ingestion-runtime resource governance is orthogonal ops engineering, not designed here |
| CI-20 | Teardown enumerates/destroys every billed dependent; cost telemetry in a common decomposition | **mitigated** | `StageTrace.cost` gives a common cost decomposition across policies and vendors it touches, but cannot force a vendor's idle-billing floor or orphaned-resource teardown |
| CI-21 | Declared p99-at-recall SLOs with a reproducible harness | **mitigated** | `Budget.max_latency_ms` degrades tier-wise per policy and is logged, but Loom does not publish or benchmark p99-under-concurrent-write SLOs |
| CI-22 | Per-language analyzers, fusion weights, and telemetry by default | **unaddressed** | not designed; the fusion-weights bandit (decision point 4) *could* condition on language as a context feature, but this is not shipped |
| CI-23 | Signed deployment security manifest; "governed" profile refuses to start without required controls | **unaddressed** | the operator console's policy cards are adjacent in spirit but are not a security manifest |
| CI-24 | One provider-agnostic retrieval-tool contract (query, filters, budget, provenance, confidence), conformance-tested across ≥3 providers | **mitigated** | `retrieve()`'s signature is exactly this contract; the ≥3-provider conformance testing is inherited from the CI-03 adapter discipline, not newly solved here |
| CI-25 | Content-hashed corpus snapshots, pinned manifests, deterministic replay | **mitigated** | `DecisionTrace.corpus_manifest` pins (parser, chunker, embedder, index) versions per request; full deterministic replay is bounded by LLM-call nondeterminism outside the framework's control |
| CI-26 | Budgeted, quality-gated enrichment with automatic graph-vs-vector ablation per query class | **mitigated** | any enrichment path (e.g., graph extraction) is itself modeled as a decision-point policy subject to the same promotion gate and budget — it must beat a vector-only baseline on the golden set to ship, closing the "ungated" half of the issue |
| CI-27 | Verifiable no-egress profile; no implicit hosted defaults | **unaddressed** | `Budget`/`policy_profile` could in principle carry an egress constraint enforced at the kernel boundary, but this is not designed or tested here |

**Solved: 3. Mitigated: 16. Unaddressed: 8.** The unaddressed set is not incidental — CVE-class hardening (CI-13), doc/issue governance (CI-17), ingestion resource limits (CI-19), vendor billing legibility (CI-20), tail-latency SLOs (CI-21), multilingual defaults (CI-22), signed security manifests (CI-23), and no-egress guarantees (CI-27) are real, evidenced problems that a learned-policy architecture does not have a comparative advantage in solving. Claiming otherwise would be the same move CI-15 condemns.

---

## What this framework deliberately does NOT do

- **It does not become a ninth decision point every time someone has an idea.** The decision-point list is closed at eight, matching the provocation's own enumeration. Amending it costs three things, paid before any code merges: a written default heuristic, a declared feedback tier (A/B/C) with its floor, and a golden-set slice the new point's promotion gate will be scored against. No decision point ships "smart by default" — every one ships on Tier A until it earns Tier B/C with evidence from *this* corpus.
- **It is not a vector database.** Stores are conformance-tested adapters (CI-03 discipline); Loom does not compete with Qdrant/Weaviate/pgvector, it constrains what they're allowed to silently get wrong.
- **It is not a general agent-orchestration framework.** `retrieve()` is a tool any agent loop (LangGraph, a custom loop, a single-shot pipeline) calls; Loom does not own planning, tool-choice, or multi-agent coordination.
- **It does not own generation.** Judges and challenger-training use LLM calls, but Loom has no synthesis-time prompt-templating layer to compete with — that keeps it out of the CI-11 abstraction-soup trap from the other direction.
- **It is not a visual pipeline builder.** No DAG canvas, no low-code surface — the low-code cohort's CVE and churn record (`common-issues.md` CI-13, CI-08) is exactly the incentive structure this design avoids reproducing.
- **It does not chase GraphRAG-style enrichment as a default.** Enrichment is Tier-C-gated, budgeted, and must win an ablation against vector-only retrieval on the golden set before it ships to any tenant, closing CI-26 rather than repeating LightRAG's or GraphRAG's unmeasured-noise history.
- **It does not build in-house RL research.** Contextual bandits and off-policy estimators are consumed as libraries (LinUCB/Thompson-sampling-class methods, doubly-robust estimators); GEPA-style reflective evolution is a candidate technique for Tier-C textual policies (query rewrite templates), not a research program Loom runs itself.
- **It does not market CVE-hardening, multilingual defaults, or SLO benchmarking as its contribution.** These are real (CI-13, CI-21, CI-22) and worth building; claiming they fall out of a learned-policy architecture would be the CI-15 mistake applied to marketing instead of evaluation.

---

## Novelty vs. prior art

Every cited technique in the corpus optimizes **one** decision point in isolation, evaluated once against a fixed benchmark, with no standing infrastructure to keep re-checking the answer as a specific deployment's corpus and traffic evolve:

- **DSPy** ships the strongest validated compiler/optimizer abstraction in the space (`research/02-frameworks/dspy.md` Lesson 1) but explicitly treats ingestion, chunking, indexing, freshness, and ACLs as out of scope (Lesson 2) — it optimizes prompts and modules, not the retrieval decision points this design targets, and requires a labeled trainset most teams don't have (its own EO-1 gap).
- **GEPA** (arXiv:2507.19457) shows reflective program evolution works at tiny label budgets — a genuinely useful technique Loom adopts specifically for Tier-C *textual* policies (query-transformation templates), not as a universal training mechanism for every decision point.
- **s3** (arXiv:2505.14146) decouples a searcher policy from a frozen generator and trains it with a downstream-utility reward (Gain-Beyond-RAG) on 2.4k examples — the cleanest existing formulation of "policy optimized for utility, generator-agnostic," but it optimizes query formulation alone, with no trace/feedback bus, no promotion gate, and no declared feedback-floor discipline for deployments that never reach 2.4k labeled examples.
- **Search-R1 / R1-Searcher** (arXiv:2503.09516, arXiv:2503.05592) fold the whole search policy into the generator via outcome RL — maximal capability, maximal coupling, and (per FrugalRAG's audit) real gains that are smaller and differently shaped than first claimed. Loom deliberately keeps its learned components small, decoupled, and individually promotable instead of retraining a whole model per deployment.
- **Adaptive-RAG / UAR / semantic-router / RAGRouter-Bench's own baselines** each solve routing once, on a fixed benchmark; none ships a live promotion/rollback loop that re-checks the router's competence against a specific tenant's drifting corpus, and RAGRouter-Bench's own finding (lexical beats embedding-based routing) is precisely the evidence Loom uses to justify defaulting decision point 7 to a lexical router rather than building a bespoke one.
- **Chroma's generative benchmarking** and the **Coverage Illusion** production study supply the golden-set-bootstrapping and production-telemetry-as-eval techniques Loom's `EvalHarness` and drift monitors are built from — but neither is wired to a promotion gate that actually swaps production policies; they inform humans, they don't close a loop.
- **Unbiased learning-to-rank / IPS / click models** — the provocation's explicit citation — are classical search-ranking discipline that no framework autopsy in this corpus reports importing into RAG. Loom's mandatory propensity logging and debiasing layer between `FeedbackEvent` and any policy retrain is the direct, literal import.

| Prior art | What it learns | What it's missing (per this corpus's own audits) | What Loom adds |
|---|---|---|---|
| DSPy | prompts/modules via a compiler+optimizer | ingestion/chunking/indexing/ACLs out of scope; needs a labeled trainset | co-optimizes the retrieval decision points DSPy explicitly excludes, with a zero-label bootstrap |
| GEPA | reflective program evolution, tiny label budgets | a technique, not a system with a trace bus or a promotion gate | adopted for Tier-C textual policies only, wired into the same gate every other policy uses |
| s3 | a decoupled searcher policy via Gain-Beyond-RAG | 2.4k-example floor; no declared plan below it; one decision point | same decoupled-policy idea, generalized to 8 points, each with its own declared floor |
| Search-R1 / R1-Searcher | whole-model outcome RL | audited (FrugalRAG) as smaller-than-claimed gains; total generator coupling | keeps learned components small, decoupled, individually promotable/rollback-able |
| Adaptive-RAG / RAGRouter-Bench baselines | routing, once, on a fixed benchmark | no live re-check as a tenant's corpus drifts; lexical beats learned on their own benchmark | uses that exact finding to justify a permanent cheap default, re-validated continuously instead of shipped once |
| Chroma generative benchmarking / Coverage Illusion | golden-set bootstrapping / production-telemetry-as-signal | informs humans; not wired to a policy swap | is the direct input to `EvalHarness` and the drift monitor, wired to `PromotionGate` |
| Classical unbiased LTR / IPS / click models | debiased reward from biased exposure | never imported into a RAG framework per this corpus | the mandatory layer between every `FeedbackEvent` and any policy retrain |

**What is actually new here**: not a smarter policy for any single decision point (the corpus's deflation evidence argues against betting on that), but (1) a shared trace/feedback schema that makes every decision point's context, action, and propensity a training example by construction, satisfying CI-11's observability requirement and CI-01/16's training-data requirement with one artifact instead of two systems; (2) a closed, tiered decision-point list with declared, visible feedback floors, so "not enough data yet" is a legible system state instead of a silent failure or an over-claimed capability; (3) a promotion gate that is mandatory infrastructure, not a per-team discipline choice, pre-armored against the CI-15 self-collision its own golden-set generation would otherwise invite; and (4) an explicit bias toward learning post-retrieval control (stop/abstain, rerank depth) over pre-retrieval routing, following the one production study in the corpus that actually measured which side of the pipeline learning paid off on.

---

## Feasibility

**MVP (buildable today, no new research):** frozen `2026-hybrid-rerank` default profile across all eight decision points; full `DecisionTrace` logging with no learning enabled yet; `EvalHarness.bootstrap()` gating any *manual* config change (chunker swap, embedder upgrade) the way CI-01 demands; `FeedbackEvent` capture with propensity logging wired but unused for training. This alone claims the CI-01/CI-11/CI-14 wins in the traceability table with zero ML-safety risk, using off-the-shelf components: an LLM judge, an existing vector store behind a conformance-tested adapter, and a bandit library (LinUCB/Thompson-sampling implementations exist in River, Vowpal Wabbit, or a thin custom layer).

**Next increment:** promote exactly two Tier-A policies (decision points 1 and 4 — stop/abstain and fusion weights) to bandit-learned challengers with IPS debiasing and a real statistical promotion gate, running in shadow mode before any canary. This is the smallest slice that actually tests the stance's central falsifiable claim: does the loop measurably improve quality over static defaults on a real deployment.

**Rough build sequencing**, stated to be falsifiable rather than aspirational: quarter 1 ships the MVP above with zero learned policies — the kernel, trace bus, `CorpusStore`, and `EvalHarness` are the hard-to-retrofit parts and should be built first even though they produce no accuracy story on their own; quarter 2 adds `FeedbackEvent` capture, the IPS/AIPW estimator, and the always-valid promotion gate, tested in shadow mode against the two Tier-A candidates above with no production traffic depending on the outcome; quarter 3 is the first real canary and the first live test of `DriftMonitor`'s freeze behavior, deliberately on a low-stakes decision point; only in quarter 4, with a working promotion/rollback loop proven safe on cheap policies, does Tier-C work (query-transformation routing, GEPA-style textual policy evolution) become worth attempting — front-loading it earlier would mean training sophisticated policies with no safety infrastructure to catch a bad one, which is close to what Self-RAG's and CRAG's unaudited-at-ship-time controllers actually did.

**Genuinely hard, not solved by this design:**
- Reward design for non-QA retrieval needs (code-context lookup, exploratory search, multi-document synthesis) has no equivalent of Gain-Beyond-RAG; this is an open problem named directly in `query-understanding-transformation.md` (O7), not resolved here.
- Debiasing under sparse enterprise feedback below Google's 250k-event floor is mitigated by tiering, not solved; below-floor decision points learn only from golden-set labels, which is a real, acknowledged degradation of the stance's ambition, not a workaround that recovers it.
- The teacher/judge circularity CI-01's own steelman names (a golden set scored by an LLM judge is what CI-15 condemns when a vendor ships it) is bounded by calibration (ARES/PPI, human-anchored slices), not eliminated.
- Process-level reward for query-transformation *steps* (as opposed to end-task outcomes) is explicitly unbuilt per `query-understanding-transformation.md` O3; Tier-C query-transformation learning in Loom is correspondingly the least mature tier.
- Certified poisoning-robust curation bounds don't exist (`retrieval-training-lineage.md` §6, O6); Loom's poisoning monitor is a detector with no certified guarantee, which is the honest state of the art, not a gap unique to this design.

**Depends on research that does not exist yet:** a calibrated sufficiency signal that transfers across model families without per-deployment recalibration (Faggioli/Chifu say current QPP does not generalize across architectures — so Loom's per-deployment recalibration via the golden set is a workaround for a real, open gap, not a solution to it); and a validated theory of which decision points are worth teaching to learn at all, which `advanced-rag-architectures.md`'s own O7 flags as an unproven partition — Loom's tiering is a testable hypothesis about that partition, not a settled answer.

---

## Risks & open questions

- **The feedback channel is a new attack surface this design introduces.** `retrieval-training-lineage.md`'s self-poisoning corollary and CI-04's Mem0 finding (a hallucinated write re-extracted 808 times because nothing distinguished "user said this" from "we stored this") are the same shape as a policy trained on its own poisoned reward signal — an adversary, or simply a hallucinating downstream agent, can write content whose later retrieval generates the feedback that reinforces retrieving it again. Mitigation is admission control on `FeedbackEvent` writes, anomaly detection against the feedback channel's own baseline distribution, and quarantine above a promotion-impact threshold — but this is a risk Loom's architecture creates, not one it merely inherits, and should be named as such rather than buried in a generic monitor list.
- **Exploration vs. the permission boundary.** Off-policy learning needs stochastic exploration to generate valid propensities; exploration must be strictly bounded within the post-authorization candidate set for a given principal — a policy that widens candidates "for exploration" is a CI-05-class vulnerability. This invariant needs its own test in the same conformance suite that checks filter algebra (CI-03).
- **Erasure now has to reach the training loop, not just the index.** `erase(doc_id)` must propagate to every `DecisionTrace`/`FeedbackEvent` referencing that document — and, in a legally meaningful sense, to any policy weights derived from it, which may require scheduled retraining rather than mere deletion. This is a harder target than CI-06's own acceptance criterion and is left open here.
- **Silent policy staleness under drift.** RL/bandit-tuned policies are exploitable by, and brittle to, exactly the retriever/index/corpus changes they were tuned against (`query-understanding-transformation.md` §11 critique of RL rewriters); drift monitors must catch this before a stale champion silently degrades, and detection latency at deployment scale is unproven.
- **Judge/teacher circularity is bounded, not eliminated.** The same model family judging and generating is a structural risk statistical calibration reduces but cannot remove.
- **Governance surface increases, not decreases.** A self-modifying retrieval system is a harder compliance object than a frozen one; every promotion needs an immutable audit record (who/what/why, golden-set diff, statistical result), and this must be sized against real regimes (the EU AI Act's general-application date, noted in `cross-cutting-gaps.md`, had already passed as of this design's writing) — more audit surface, honestly, not less.
- **The non-ML-team operability claim is unvalidated UX, not just an engineering property.** Declared tiers and automatic gating remove the need to hand-tune a bandit, but a human still has to interpret a drift alarm or approve a rollback; the operator console's plain-language translation of statistical failures into actions is asserted here, not built or user-tested.
- **Full tracing has a cost, and sampling it is itself a bias decision.** Logging a `StageTrace` for every decision point on every request is storage and (potentially) latency overhead; the natural mitigation — sample traces under load — reintroduces exactly the exposure bias the debiasing layer exists to remove unless the sampling rate is itself logged as part of the propensity. This is a design detail this document asserts is solvable (log the sampling probability as another factor in the IPS weight) rather than one it has built and load-tested.
- **The closed, eight-point decision list is a testable bet, not a proof.** It is drawn directly from the provocation's own enumeration, but a load-bearing ninth decision point — embedding-model *selection* itself, as distinct from the granularity/representation choices already listed, is the most likely candidate, given CI-07's independent treatment of model-version lineage — may turn out to need first-class status rather than living inside `CorpusStore`'s lineage metadata. The stated amendment cost (default heuristic, declared tier, golden-set slice) exists precisely so this can be corrected without reopening the whole kernel, but the list being right on day one is an assumption, not a result.

---

## Evaluation plan

**Benchmarks used as diagnostics, not leaderboard entries.** LIMIT and BRIGHT characterize representation-ceiling and reasoning-intensive failures that learning cannot fix (they gate decision point 5's static routing rule, not a learned challenger). RAGRouter-Bench is the bar decision point 7's default lexical router must clear or beat before any learned challenger is even considered. CRAG/RAGBench/FreshStack measure end-to-end quality under exactly the popularity/dynamism/freshness stratification that hides failures behind healthy averages. The flagship validation is a Coverage-Illusion-style live production case study — a real deployment's telemetry — not another public-leaderboard number, because the corpus's own evidence is that public benchmarks and production traffic disagree.

**Ablations that test the stance's falsifiable core claims:**
1. *Frozen-default vs. shadow-learned, over time, on the same corpus and traffic* — does the promotion loop measurably improve the golden-set score and production guardrail metrics, or does it plateau at the default (the central claim of the entire design; a null result here falsifies the stance for that tenant's traffic regime).
2. *IPS-debiased vs. naive-click reward* — replicate the click-model literature's warning on Loom's own logs: show a naive reward signal degrades a policy that a debiased version does not, on the same data.
3. *Per-decision-point learning on/off* — directly test `advanced-rag-architectures.md`'s O7 partition (value concentrates in trained evidence integration, not scaffolding) against Loom's own tiering hypothesis: turn learning off for each of the 8 points independently and measure the quality/cost delta each one contributes.
4. *Cold-start simulation at 10², 10³, 10⁴, 10⁵ synthetic feedback events* — characterize each decision point's actual promotion-eligibility floor empirically, rather than citing Google's 250k number as if it transfers unchanged to a smaller-vocabulary enterprise retrieval task.
5. *Drift-injection and poisoning-injection red-team suites* — synthetic corpus drift and PoisonedRAG-style adversarial feedback, scored on detection latency and whether the promotion gate or drift monitor actually blocks the bad promotion, not just on whether a monitor exists.
6. *Independent-auditor replication* — hand a third party (not the team that built the challenger) only the logged trace, the golden set, and the promotion decision, and ask them to reproduce the promote/hold verdict from that artifact alone. This mirrors the role FlashRAG plays for the research literature — an independent standardized re-run that catches exactly the class of self-reported, non-reproduced gain this corpus's own audits keep finding — applied to a production promotion instead of a paper's claims.

**Production metrics, tracked continuously, not measured once:** promotion frequency and post-promotion regression rate; evidence-per-dollar trend (should improve monotonically if the stance is right); the abstention calibration curve (coverage vs. accuracy, per CI-10's acceptance test); time-to-detect injected drift; defect-escape rate through the conformance suite; and the cost/quality Pareto frontier specifically — following FrugalRAG's audited finding that the RL era's real, defensible win is frugality at matched accuracy, this design's headline production metric is *tokens/latency/dollars saved at matched or better quality over time*, not a raw accuracy delta against a leaderboard.
