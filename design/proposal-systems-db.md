# Strata — Retrieval as a Data-Systems Problem

*A design proposal for a next-generation agentic-retrieval framework. Every major claim below is grounded in a specific file/section of `research/03-synthesis/common-issues.md` (cited as `CI-NN`) and the `research/01-landscape/` and `research/02-frameworks/` corpus. Design against the RESTATED, verified claims in `common-issues.md`, not the headline names.*

---

## Design axioms

1. **A retrieval call is a compiled query, not a hard-wired physical plan.** Every mainstream framework's `VectorStore.similarity_search(query, k)` *is* the physical plan — one Python method per backend, 20–100 independent reimplementations of filter translation and score semantics with no shared conformance suite (`common-issues.md` CI-03). Separate the logical plan (what evidence, under what policy and budget) from the physical plan (which operators, in what order, at what cost) the way System R separated SQL from access paths, and an entire defect class — silent wrong-or-unfiltered results — has nowhere left to hide.

2. **Every derived artifact is a versioned materialized view over a canonical, content-addressed source of truth — never a primary artifact.** CI-07's root cause is explicit: "the index is treated as the primary artifact rather than a derived view of a canonical parsed corpus." Chunks, embeddings, graph edges, contextual headers, summaries, and caches are all such views; a shared lineage semantic across all of them is what makes CI-06's incremental-correctness contract and CI-07's rebuild-from-scratch target implementable instead of aspirational.

3. **Corpus mutation is transactional, and every downstream view is incrementally, not batch, maintained.** Incremental sync APIs exist almost everywhere and break silently in the configurations users actually run (CI-06). The fix is a WAL-committed transaction log with streaming incremental view maintenance (IVM) as the *only* way a derived artifact is ever produced — full rebuild becomes a special case of IVM (replay the whole log), not a separate, fragile code path.

4. **Principal, policy, and budget are non-optional, typed inputs to plan compilation — never smuggled through a metadata filter.** CI-05: authorization has no slot in `retrieve(query, k)`. CI-03: because it has no slot, authorization gets smuggled into the filter channel, which is why a relevance bug (LangChain4j #2513's `.isNotIn`) and a tenancy bug are the *same code path* with opposite required failure semantics (degrade gracefully vs fail closed). CI-09: cost has no slot either. One typed signature with three non-optional fields closes all three at once.

5. **Every returned score is a typed, method-tagged evidence-state, and "insufficient evidence" is a compilable plan outcome.** CI-10: no OSS framework returns calibrated relevance/coverage/freshness by default, and abstention is nowhere a first-class result. A plan that can terminate in `insufficient_evidence` — rather than always emitting a top-k — is a different type signature, not a UX feature bolted on after generation.

6. **Every plan is EXPLAIN-able before it runs and REPLAY-able after.** CI-11: no framework emits a typed per-stage trace as a default artifact; tracing stops at the LLM span. EXPLAIN and WAL-replay are forty-year-old database primitives; making them the *default* output of every call — not an opt-in observability SKU — is what turns "why is this chunk in my context" into an answerable question for 100% of responses, not a six-object debugging session (Octomind, HN 40739982, `langchain-langgraph.md`).

7. **Physical operators are heterogeneous, pluggable, and conformance-gated — the framework costs them, it does not crown one.** grep, BM25, ANN, late-interaction, graph traversal, and SQL predicates are different points on a recall/cost/latency surface, not competing religions (`production-industry.md` F10 — the "RAG is dead" debate resolves to "the unit of retrieval is being renegotiated, not eliminated"). Every operator must pass the same filter-algebra/score-contract/tenancy-isolation suite before registration — CI-03's testable acceptance criterion, taken literally as a merge gate.

8. **A small, semver-stable kernel is the only thing an agent's trained policy is asked to trust.** CI-08: the ecosystem rewrites APIs on 6–18-month cycles and never separated a stable kernel from the experimental orchestration layer, even though the data-layer vocabulary (document/chunk/query/score) has been stable since DrQA/DPR (`common-issues.md` CI-08, "What research offers"). Models are also measurably suspicious of bespoke tool schemas — "so heavily RL'd with grep that they do not trust results in other forms" (CI-24). The fix for both is the same: expose four boring, stable verbs and hide the optimizer behind them.

### Alignment with the evidence base's non-negotiables

The design brief names eight non-negotiable constraints. Restating each against the design, rather than leaving the mapping implicit in the axioms above:

| Non-negotiable | Where this design satisfies it |
|---|---|
| Retrieval is consumed by trained agent policies via tools, not hand-wired pipelines | The four-verb Agent Tool Surface (axiom 8) is the *only* thing a policy calls; the pipeline is entirely behind the Optimizer. |
| Models' training priors distrust custom tools | The four verbs are deliberately grep/SQL-shaped, not bespoke schemas (CI-24) — this is the whole reason the verb count is fixed at four, not forty. |
| Single-vector embeddings have proven capacity ceilings | ANN is one Operator among six (grep, BM25, ANN, late-interaction, graph, SQL); late-interaction (ColBERT-class) and lexical operators are first-class fallbacks the Optimizer can route to for exactly the reasoning-intensive/negation-heavy queries where single-vector similarity is known to fail (`retrieval-reranking-fusion.md` §2, BRIGHT). |
| Parsing fidelity dominates chunking sophistication | The Canonical Corpus's typed IR and per-span parser confidence are the substrate; the Derivation Engine's default chunking (content-defined) is deliberately unglamorous, and no claim is made to beat the OHR-Bench ceiling (Anti-scope). |
| Evaluation must be built-in or it will not exist | Eval/Replay is a core-tier, cross-cutting subsystem (Architecture), not an add-on — directly answering CI-01's root-cause diagnosis that eval is the universal open-core paywall. |
| Incremental corpus mutation is the common case, not the exception | Axiom 3 makes the transaction log + IVM the *only* write path; batch rebuild is a degenerate case of it, not a separate default. |
| Permission-aware retrieval is a hard requirement for enterprise | Axiom 4 makes `principal`/`policy` non-optional compiled fields with a mandatory entitlement conformance suite (CI-05), though the identity-mapping/group-sync half is explicitly not solved here (Issue-coverage table, CI-05). |
| Must avoid both the over-abstraction death spiral (LangChain) and the underspecification trap (BYO-everything) | The fixed public-symbol budget (Anti-scope) is the mechanism against the first; shipping strong, benchmarked default profiles (CI-14) with everything swappable through one conformance-gated Operator interface (CI-18) is the mechanism against the second. |

---

## The core insight

Every framework in the 22-autopsy corpus makes the same architectural choice, usually without naming it: the index — whatever downstream artifact retrieval actually reads, be it an HNSW graph, a GraphRAG community hierarchy, or a set of contextualized chunks — is the *primary* artifact of the system, and the code path that produces it is a *fixed, hand-written physical plan chosen once at framework-design time*. LangChain's, LlamaIndex's, and Haystack's `VectorStore` interfaces do not compile a query; they *are* the query, one Python method with dozens of independent per-backend implementations of what should be one filter algebra (CI-03). Nothing above that layer knows a plan exists, so nothing above it can cost it, explain it, or replan it when the world changes.

Databases stopped doing this in the 1970s. System R's separation of a declarative logical layer (SQL) from a cost-based physical layer (access paths chosen by an optimizer against live statistics) is the founding idea of relational databases — and it is precisely the idea nineteen years of RAG frameworks re-discovered piece by piece, one GitHub issue at a time, without ever generalizing it. The taxonomy's own causal map traces the root far enough back to say so directly: "type signatures frozen before the domain was understood... `retrieve(query, k) → docs`... cannot express a principal, a policy or trust tier, a budget, a calibrated evidence-state, provenance that survives transformation, or an audit handle" (`common-issues.md`, "Three root engines," #3). A frozen physical-plan signature cannot express any of the things a *query* — as opposed to a function call — is supposed to carry.

Once the missing logical/physical split is visible, four seemingly unrelated defect clusters turn out to be the same bug reported four times.

**The filter channel is the ACL channel is the cost sink is the calibration failure — one overloaded construct doing four jobs.** With no principal, policy, or budget slot in the signature, all three get smuggled into the one structured input that exists: the metadata filter. That is why LangChain4j #2513's `.isNotIn` bug and a tenant-isolation failure are the *same line of code* (CI-03), why authorization ships as a commercial tier bolted onto that same filter dict rather than as a property of the call (CI-05), and why nothing in the signature can carry a budget for an optimizer to plan against (CI-09). A relevance filter should degrade gracefully under a bug; a security filter must fail closed. The ecosystem asked one channel to do both and got the worse of each — CI-03's own root cause line says this explicitly.

**Derived state has no owner, no versioning, no export path — and it is one omission, not five.** This is the taxonomy's own diagnosis, worth quoting because a synthesis independently converging on the identical conclusion this proposal starts from is stronger evidence than restating it in a new voice: "Because the index is the primary artifact with no lineage, incremental change is a rebuild (CI-06), configuration is a one-way door (CI-07), upgrades and restores corrupt (CI-07), and platform death strands everything (CI-08) — five ostensibly separate operational failures that are one omission: derived state has no owner, no versioning, no export path" (`common-issues.md`, "The state cascade"). Three concrete instances, named directly in this project's brief: LlamaIndex's docstore and vector-store are two unsynchronized stores, so `refresh_ref_docs` breaks in the *default production configuration* and stays broken across three tracked issues (#13604, #14057, #13860 — `llamaindex.md`, "P1"). GraphRAG's community hierarchy is a single global artifact that one new document invalidates, so incremental append was begged for from month one (#741, 35 comments) and shipped half-working twenty months later, with deletion still out of scope (`microsoft-graphrag.md`). Bedrock's chunking strategy is welded in at knowledge-base creation with no recorded derivation, so changing it means a new KB and a full paid re-ingest (CI-07). Three frameworks, three names for the same missing primitive: none of them treats the *canonical parsed document* as the durable artifact and the chunks/vectors/graph as *its* versioned derived views. A database calls this a materialized view over a base table with incremental maintenance on write. RAG frameworks call it, variously, a docstore-sync bug, a begged-for GitHub issue, and a paid-tier limitation — because none of them built the primitive database systems built forty years ago.

**Models already trust a query interface — it just isn't the one frameworks built.** The constraint most existing designs quietly violate is that trained agent policies consume tools, and those policies are measurably suspicious of bespoke ones (CI-24). A cost-based optimizer is not in tension with that constraint; it *resolves* it. A database client calls four or five verbs — connect, query, explain, commit — and has done so for decades while the storage engine underneath was rebuilt repeatedly; the stability is in the interface, not the implementation. The agentic-RAG turn responded to exactly this problem by doing the opposite: bolting an "agentic mode" beside the existing pipeline (CI-12) and multiplying tool surface rather than shrinking it. The fix is not a smarter agent loop; it is fewer, more boring verbs — `search`, `fetch`, `explain`, `since` — that resemble the grep/SQL surfaces models already trust, compiled underneath by exactly the optimizer this document proposes.

---

## Architecture

```
                        ┌──────────────────────────────────────────┐
                        │     Agent / caller (trained tool policy)  │
                        │   search()   fetch()   explain()  since() │
                        └────────────────────┬───────────────────────┘
                                              │  CAL plan (principal, policy, budget)
                        ┌─────────────────────▼────────────────────────┐
                        │                 OPTIMIZER                     │
                        │  logical plan → physical plan                 │
                        │  cost model = (tokens, $, latency, recall-risk)│
                        │  EXPLAIN before · REPLAY after                 │
                        └──────────┬─────────────────────┬──────────────┘
                                   │                      │
                  ┌────────────────▼────────────┐  ┌───────▼──────────────────┐
                  │      PHYSICAL OPERATORS      │  │      EVIDENCE-STATE       │
                  │  grep · BM25 · ANN ·          │  │  calibrated score +       │
                  │  late-interaction · graph ·   │─►│  sufficiency + provenance  │
                  │  SQL predicate                │  │  + insufficient_evidence   │
                  │  (conformance-gated)          │  └───────────────────────────┘
                  └────────────────┬─────────────┘
                                   │ reads
                  ┌────────────────▼───────────────────────────────────┐
                  │               DERIVATION ENGINE                     │
                  │  Views: chunk · embed[v] · graph-extract · summarize │
                  │  content-defined chunking · lineage per view          │
                  │  refresh budget + staleness SLO per view              │
                  │  streaming incremental view maintenance (IVM)         │
                  └────────────────┬───────────────────────────────────┘
                                   │ subscribes to
                  ┌────────────────▼───────────────────────────────────┐
                  │        TRANSACTION LOG (WAL) — the only writer path │
                  └────────────────┬───────────────────────────────────┘
                                   │ commits
                  ┌────────────────▼───────────────────────────────────┐
                  │   CANONICAL CORPUS — content-addressed, typed IR,   │
                  │   ACL principals, per-span parser confidence        │
                  └───────────────────────────────────────────────────┘

     cross-cutting: EVAL / REPLAY subsystem — self-bootstrapping golden-set
     generation, regression gates on any View change, calibration curves fed
     back into the Optimizer's live statistics (closes CI-16's open loop)
```

**Canonical Corpus.** The only layer a caller writes to directly. Documents are stored as a typed structural IR — element trees with section paths, table structure, page/bbox coordinates, character offsets, ACL principal, embedder/parser version, and per-span parser confidence — the exact shape CI-02's testable requirement specifies. Content-addressed (hash of normalized content = identity), following the "object storage as source of truth" pattern that turbopuffer and Lance already use at the index layer (`indexing-vector-databases.md` §3, §7) — generalized here to the whole corpus, not just vectors.

**Transaction Log.** Every mutation — insert, patch, delete, ACL change — is a WAL-committed transaction. This is the single writer path; nothing downstream is allowed to mutate state except by subscribing to this log, which is what makes CI-06's "mutating one document is O(changed content)" acceptance test a property of the architecture rather than a best practice someone might follow.

**Derivation Engine.** A DAG of registered *View* definitions (parse → chunk → embed → enrich → graph-extract → summarize), each with declared inputs, a producer identity (model + version + config hash), and — this is the design's sharpest departure from classical incremental-view-maintenance (IVM) literature — a **refresh budget and staleness SLO**, not just a recompute rule. Classical IVM assumes microsecond-cost recompute; an LLM-enrichment view (contextual headers, entity extraction) costs dollars and seconds per unit, so the Derivation Engine performs *admission control and tier-degradation on the write path*, symmetric to what the Optimizer does on the query path: a view can run at full fidelity, sampled fidelity, or skip entirely depending on its declared budget and the corpus's current mutation rate. Chunking is **content-defined** — rolling-hash boundaries in the rsync/CDC tradition, a technique `document-processing-chunking.md` names explicitly as unbuilt for RAG ("No published system I found does *stable-boundary* chunking... for RAG — an obvious open problem," §"Metadata, dedup, incremental ingestion") — so a chunk's identity is a function of its content, not its offset. Editing one paragraph therefore invalidates only the touched chunk and its dependent views, not the whole document's tail, and chunk IDs never get silently reassigned (closing the Spring AI #1167 class of bug, CI-02).

**Physical Operator Layer.** grep/regex, BM25, ANN, late-interaction, graph traversal, and SQL/structured-predicate operators, each implementing one typed contract: `plan(query_fragment, budget) -> OperatorPlan`, `execute(plan) -> CandidateSet`, `cost_model(fragment) -> CostEstimate`. Every operator must pass a mandatory, versioned conformance suite (filter-algebra nesting/negation/NOT-IN, score-contract normalization, tenancy-isolation fail-closed cases) before it can register — CI-03's acceptance criterion taken as a literal merge gate, not a best-effort test file.

**Optimizer.** Compiles a CAL logical plan into a physical plan against live statistics (corpus size, per-predicate selectivity, per-operator cost/latency/recall profile, calibration curves from the Eval subsystem). The cost vector is `(tokens, dollars, latency, recall-risk)`, not I/O alone — the database optimizer's currency, extended to what an agent actually pays for. Emits an EXPLAIN plan before execution and a persisted, replayable trace after.

**Evidence-State layer.** Wraps physical output into a typed `EvidenceState`: items with provenance and trust tier, a method-tagged calibrated relevance score, a sufficiency estimate, per-item freshness, and a `status` that can be `insufficient_evidence` — a plan outcome the Optimizer can actually choose, not a fallback string.

**Agent Tool Surface.** Four verbs — `search`, `fetch`, `explain`, `since` — compiled to CAL underneath. This is the only surface a trained tool-use policy sees; everything above this line is implementation detail that can change release to release without the caller's prompt or fine-tuning distribution moving.

**Eval/Replay subsystem (cross-cutting).** Bootstraps a judge-aligned golden set from the corpus itself (adapting Chroma's generative-benchmarking method, cited as the counter-example in CI-01), gates any View-definition change with a before/after regression report, and feeds observed calibration and outcome data back into the Optimizer's statistics — the mechanism that closes CI-16's "feedback never reaches the retriever" loop.

### Worked example: Day 1 → Day 30

A concrete trace through the stack, because the layers above are easy to describe in the abstract and easy to under-specify in practice.

**Day 1.** A team points `Corpus.open()` at an S3 prefix of PDFs and Confluence exports. Ingestion parses each source into typed IR, commits one transaction per source, and the Derivation Engine's default views (content-defined chunk → embed under the `2026-hybrid-rerank` profile) materialize incrementally as each commit lands — there is no separate "build the index" step to run and forget. The team calls `search()` with no tuning; the Optimizer plans BM25+ANN fused by RRF, reranked, against the default profile's benchmarked recall numbers (CI-14), and every response carries a `plan_id` they can `explain()` the moment an answer looks wrong.

**Day 8.** Legal flags that three documents contain data subject to an erasure request. `corpus.erase()` walks the lineage graph recorded by every View, deletes from chunks/embeddings/graph/cache, and returns a completion proof enumerating exactly which derived artifacts were touched — the request is closeable, in the audit sense, the same day (CI-06's testable target), not "eventually, on the next full reindex."

**Day 15.** A new embedding model ships. The team registers `embeddings_v4` as a new View reading the same `chunks` View, sets a `dual_read` flag, and the Optimizer routes a sampled fraction of live traffic to the new index while the Eval subsystem reports a retrieval-overlap drift number against `embeddings_v3` — a dual-read cutover with a measured drift report, not a silent full re-embed on a vendor's billing meter (CI-07) and not an unversioned in-place swap that breaks yesterday's citations.

**Day 30.** Someone asks why an answer three weeks ago cited a policy document that has since been deleted. `Plan.replay(plan_id, as_of="2026-08-08")` reconstructs the exact plan against the corpus snapshot as it existed that day — the reproducibility primitive CI-25 and `production-industry.md`'s O1 both name as absent everywhere in production today.

None of these four moments requires a special mode, a paid tier, or an out-of-band script; each is the same small set of kernel verbs called against a corpus that has been transactionally consistent since the first commit.

---

## Core abstractions & API

Six load-bearing abstractions. Each is shown at Day-1 usage (works with zero configuration) and expert usage (the same object, pushed harder).

### 1. `Corpus` — the transactional canonical store

```python
from strata import Corpus, Document

corpus = Corpus.open("s3://acme/knowledge", canonical_format="strata-ir-v1")

# Day 1: ingest a folder; Strata parses to typed IR and commits transactionally.
tx = corpus.begin()
for path in glob("./handbook/**/*.pdf"):
    tx.put(Document.from_file(path))       # typed IR: sections, tables, bbox, offsets, ACL
tx.commit()                                  # WAL-durable; triggers downstream views

# Expert: patch one paragraph. Content-defined chunking (Derivation Engine)
# means only the touched chunk, and views that depend on it, are invalidated.
tx = corpus.begin()
tx.patch("doc:handbook/onboarding.pdf", op="replace_span",
         start=4820, end=5011,
         text="Employees may take up to 6 weeks of parental leave...")
tx.commit()

# Verified erasure: a completion proof enumerated across every lineage-tracked view.
proof = corpus.erase("doc:handbook/2019-policy.pdf", deadline="30d")
assert proof.propagated_to == {"chunks_v3", "embeddings_v2", "graph_v1", "cache"}
```

### 2. `View` — materialized, lineage-tracked, budgeted derivation

```python
from strata import view, Budget

# Day 1: the built-in default chunk/embed views need no configuration.
corpus.use_default_views(profile="2026-hybrid-rerank")   # dated, benchmarked (CI-14)

# Expert: register a custom enrichment view with a hard refresh budget —
# admission control and tier-degradation on the WRITE path, mirroring what
# the Optimizer does on the query path (this is the answer to CI-09's
# index-time half and CI-26's ungated-enrichment problem).
@view(name="contextual_headers", inputs=["chunks", "canonical"],
      producer_version="claude-context-2026.08",
      refresh_budget=Budget(dollars_per_hour=25, tokens_per_doc_max=2000,
                             degrade=["full", "sampled_20pct", "skip"]),
      staleness_sla="1h")
def contextualize(chunk, doc):
    return llm_generate_context(chunk, doc)

# Every view carries lineage: source_version, producer, producer_version, config_hash.
print(corpus.views["contextual_headers"].lineage_of("chunk:9f2a...12"))
```

### 3. `Plan` — the compiled CAL query, EXPLAIN, and replay

```python
from strata import Plan

# Day 1: a plain-language intent compiles against the default profile.
plan = Plan.compile("""
  EVIDENCE FROM handbook
  WHERE intent = "parental leave policy for engineers hired after 2024"
  NEED sufficient
  AS principal = user("alex@acme.com") POLICY "default-acl"
  BUDGET tokens <= 4000, latency <= 800ms, dollars <= 0.02
""")

print(plan.explain())
# Plan(cost_estimate={tokens: 3200, latency_ms: 410, dollars: 0.008})
#  -> BM25(k=50) + ANN(k=50, index=embeddings_v3) -- RRF
#  -> rerank(cross_encoder, top=20)
#  -> acl_filter(pre_rank=True, policy="default-acl")     [fail-closed]
#  -> sufficiency_check(method="autorater-v1")

result = plan.execute()
if result.status == "insufficient_evidence":
    escalate_or_abstain(result)

# Expert: replay last week's exact plan against today's corpus to see drift.
old = Plan.replay(plan_id="pl_9f2a...", as_of="2026-08-01")
diff = old.diff(plan.execute())
```

### 4. `Operator` — the conformance-gated physical-operator contract

```python
from strata import Operator, ConformanceSuite

# Day 1: built-ins (grep, bm25, ann, graph, sql) are already registered.

# Expert: register a new physical operator (e.g. a late-interaction index).
class ColBERTOperator(Operator):
    kind = "late_interaction"
    def plan(self, fragment, budget) -> "OperatorPlan": ...
    def execute(self, op_plan) -> "CandidateSet": ...
    def cost_model(self, fragment) -> "CostEstimate": ...

report = ConformanceSuite.run(ColBERTOperator())   # filter algebra, score contract,
                                                     # tenancy isolation, NOT-IN fail-closed
assert report.passed, report.failures              # registration is refused on failure
strata.register_operator(ColBERTOperator())
```

### 5. `EvidenceState` — the typed, calibrated, abstention-capable result

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class EvidenceState:
    items: list["EvidenceItem"]        # content, span, provenance, trust_tier, freshness
    relevance: "CalibratedScore"       # method-tagged, e.g. "isotonic-v1 on corpus X"
    sufficiency: float                 # 0..1, autorater-scored
    status: Literal["ok", "insufficient_evidence", "budget_exhausted"]
    plan_id: str                       # -> Plan.replay(plan_id)
    cost_spent: "CostTrace"            # >=95% of billed tokens attributed, per CI-09

# Day 1: callers branch on `status`, not on eyeballing a bare list of strings.
if evidence.status == "insufficient_evidence":
    return "The corpus does not contain enough information to answer this."
```

### 6. `search` / `fetch` / `explain` / `since` — the agent tool surface

```python
# The ONLY surface a trained tool-use policy sees. Everything above compiles
# to this. Deliberately four verbs, deliberately grep/SQL-shaped (CI-24).

def search(intent: str, budget: "Budget", principal: "Principal") -> EvidenceState: ...
def fetch(id: str, principal: "Principal") -> "Document": ...
def explain(plan_id: str) -> "Plan": ...
def since(version: str, principal: "Principal") -> "ChangeSet": ...

# Expert usage is identical to Day-1 usage — that is the point. An agent
# framework wraps these four functions as tool schemas; it never sees Corpus,
# View, Operator, or the Optimizer directly.
```

---

## Issue-coverage traceability

Verdicts use the RESTATED claim and stated acceptance criteria from `common-issues.md`, not the headline names.

| CI | Restated claim | Verdict | How Strata addresses it |
|---|---|---|---|
| CI-01 | No integrated, self-maintaining eval loop in any core tier | Mitigated | Eval/Replay subsystem bootstraps a judge-aligned golden set from the canonical corpus (adapting Chroma's method, not new judge science) and gates any View change with a before/after report. Judge calibration and eval-set maintenance under drift remain the named open research gap — Strata gives the hook, not a solved theory. |
| CI-02 | Structure/provenance survive only by convention; no cross-stage contract validation | Mitigated | Typed IR is the only format Views compile against; a destructive composition is rejected at registration (CI-02's "Haystack-#8491-class rejected before it runs" test). Parsing fidelity's ~14% OHR-Bench F1 ceiling is untouched by architecture. |
| CI-03 | Filter-translation defects are silent; the filter channel doubles as the ACL channel | **Solved** | Mandatory conformance suite (filter algebra, score contract, tenancy fail-closed) gates every Operator's registration; principal/policy predicates compile through a distinct path from relevance filters with differentiated fail-closed vs degrade-gracefully semantics enforced at the type level (axiom 4). The two failure modes CI-03 says got conflated can no longer share a code path. |
| CI-04 | No provenance/trust label survives transformation; unguarded instruction channel | Mitigated | Writer identity, ingestion path, and trust tier are typed IR fields that propagate through View lineage by construction. Admission-controlled commits close the "cheap-now" half. Typed values that structurally cannot reach the instruction position — CI-04's named research frontier — is out of this layer; EvidenceState is designed to compose with a CaMeL-class enforcement boundary, not replace one. |
| CI-05 | Authorization has no slot in the retrieval signature; ships as a paid tier | Mitigated | `principal`/`policy` are non-optional compiled Plan fields, and a mandatory entitlement suite gates backend registration — closing the *signature* half. The acceptance criterion's harder half — "the contract must cover ACL-interchange formats, identity mapping, and group-membership sync... or the fix will not matter" — is not solved: Strata defines a `GroupResolution` view type that *can* host an IdP sync, but operating one (Glean's User Store, Q Business's identity crawler) is deployment-specific work this design enables, not performs. |
| CI-06 | Sync/delete/erasure are fragile, silently-failing afterthoughts | Mitigated | Content-defined chunking gives every chunk a stable, content-addressed identity, so an edit invalidates only the touched chunk and its dependents — CI-06's "O(changed content)" test as an architectural consequence, not a promise. `erase()` returns a completion proof across every lineage-tracked view. Not solved: unrecoverability against embedding inversion strictly *before* physical compaction is a timing race no framework closes with a proof, only a policy. |
| CI-07 | Chunking/embedding/index config welded in at ingest, no recorded derivation | **Solved** (per the rewritten target) | The Canonical Corpus is the framework-owned durable artifact; every index — including closed vendor backends — is a disposable, rebuildable View with recorded lineage (producer + config + source version). This is exactly CI-07's corrected acceptance target: "given only the framework's own canonical store, rebuild any vendor index... from scratch, cheaply and on command." In-place migration of a vendor's own index format remains outside any framework's reach, as CI-07 itself concludes. |
| CI-08 | 6–18-month breaking-change cycles; retrieval demoted; platforms die | Mitigated | A semver-stable kernel (Corpus, View, Plan, Operator, EvidenceState, four tool verbs) is walled off from experimental orchestration by a fixed public-symbol budget (see Anti-scope) — the enforcement mechanism CI-08's fix demands, not just the intent. Defangs churn for adopters who pin the kernel; cannot defang platform death of Strata itself. |
| CI-09 | Cost is never an enforceable input to retrieval or indexing | **Solved** (enforcement half) | `budget` is a non-optional typed Plan field the Optimizer plans against, with tier-wise degradation on both the query path and, via View refresh budgets, the *derivation* path — CI-09's literal spend-never-exceeds-budget test. Pre-flight cost *estimation* for agentic fan-out, which CI-09 says static estimators cannot do, is a live-statistics projection here, not a guarantee; the ±25% accuracy target is unvalidated. |
| CI-10 | No calibrated sufficiency signal; abstention not a default result | Mitigated | EvidenceState always carries a method-tagged score, a sufficiency estimate, and `insufficient_evidence` as a compilable outcome — the type-level fix CI-10 asks for. Cross-corpus calibration without labeled data is flagged as statistically hard and partly open across the corpus; Strata starts from cheap uncertainty estimators, not solved calibration. |
| CI-11 | No typed per-stage trace by default; tracing stops at the LLM span | **Solved** | Every Plan is EXPLAIN-able and REPLAY-able by construction, not an opt-in SKU. The Plan *is* the typed per-stage trace — rewrites, per-operator candidates and scores, fusion weights, rendered prompts — persisted under `plan_id`. CI-11's literal test: "why is this chunk in my context" answerable from the trace alone for 100% of responses. |
| CI-12 | Bolted-on agentic modes; loop-correctness bugs; memory writes without transactions | Mitigated (memory leg only) | An agent using the Corpus's transaction log as its memory substrate gets ACID writes, idempotency, and concurrency safety — leg (c). Legs (a) capability regression and (b) loop-correctness are properties of an agent-executor layer this framework deliberately does not build (Anti-scope); Strata supplies the idempotent, budgeted tool surface such an executor needs, not the executor. |
| CI-13 | RAG-defining features are the CVE surface | Mitigated | Anti-scope removes the dominant CVE class by not shipping a template-rendering engine, user-authored code nodes, or a visual pipeline serializer. Typed query construction (axiom 1/7) closes the filter-string-injection sub-class by construction. The CAL parser/Optimizer are new, smaller attack surface — a reduction, not zero. |
| CI-14 | Frozen, unrevisited demo-grade defaults | **Solved** | The Optimizer ships dated, versioned, benchmarked default profiles (e.g. `2026-hybrid-rerank`) instead of scattered constants, with regression numbers published per release via the in-core Eval subsystem. |
| CI-15 | Measurement theater — vendor self-benchmarks, uncalibrated judges | Mitigated | Content-addressed snapshots, pinned View manifests, and Plan replay make any Strata-based claim reproducible-by-construction. Constrains claims about Strata; has no jurisdiction over third parties' own benchmarking. |
| CI-16 | Feedback never reaches the retriever; drift never alarms | Mitigated | Eval/Replay feeds outcome and calibration data back into the Optimizer's live statistics, closing the loop that terminates in a dashboard everywhere else. Google's own ≥250k-logged-event floor for unbiased LTR is a data-volume problem the architecture cannot supply for low-traffic deployments. |
| CI-17 | Docs/issue-tracker rot outpaces a churning API | Mitigated | The fixed public-symbol budget that defangs CI-08's churn is the same mechanism that keeps docs from rotting under a stable kernel; kernel doc examples run in the same CI gate as View/Plan compatibility checks. A governance commitment, not a guarantee against neglect. |
| CI-18 | No extension gradient between "use the built-in" and "fork everything" | **Solved** | Built-in Operators register through the exact same conformance-gated interface a third party uses — no privileged internal path — so a single-operator swap is a conformance pass away, matching CI-18's "≤5 lines" test by construction. |
| CI-19 | Ingestion is a library loop, not a resource-governed job runtime | Mitigated | View refresh budgets require admission control and tier-degradation on rebuild, presupposing bounded, checkpointable execution. A 7-day-soak-under-declared-RSS guarantee depends on the chosen execution runtime (see Feasibility) and is not yet demonstrated. |
| CI-20 | Billing decoupled from workload; orphaned resources at teardown | Mitigated | Every registered backend declares its billed dependents in its conformance manifest; `Corpus` teardown enumerates and releases them — aimed at the Bedrock-orphans-a-Neptune-graph failure. Depends on honest vendor-integration declarations Strata cannot enforce on a vendor's own billing system. |
| CI-21 | Tail-latency opacity; hard, undeclared QPS ceilings | Mitigated | The Optimizer's cost model targets p99-at-stated-recall, following `indexing-vector-databases.md`'s tail-recall-SLO seed. The underlying measurement science (Robustness-δ@K) is 2025-era and not yet standard practice anywhere, including here. |
| CI-22 | English-centric retrieval stacks; static fusion weights | **Unaddressed** | Nothing in this design calibrates per-language analyzers or fusion weights. Operators could be registered per-language and MIRACL-style inversions could inform Optimizer statistics, but this proposal does not design that mechanism. |
| CI-23 | Vendors document the hazard and ship the workaround | Mitigated | A "governed profile" — refusing to compile without authz/guardrails/audit configured — extends axiom 4's non-optional principal/policy field, but is specified at the level of intent here, not shipped as an enforced default. |
| CI-24 | Provider lock-in; MCP immaturity; models distrust bespoke tool schemas | Mitigated | The four-verb tool surface is a provider-agnostic, conformance-tested retrieval-tool contract — CI-24's literal acceptance criterion for the *contract* half. Whether trained policies extend grep/bash-level trust to a new-but-boring verb set is an empirical bet flagged in Risks, not a result claimed here. |
| CI-25 | No reproducible-run primitive (model+corpus+config pinned) | **Solved** | Content-hashed snapshots, pinned View manifests (producer version + config hash), and recorded, replayable Plans are exactly the tuple CI-25 asks pinned; eval results bind to a manifest, not a library version. |
| CI-26 | Ungated LLM enrichment injects noise below cheaper baselines | Mitigated | Enrichment Views carry the same refresh-budget/degrade-tier machinery as any View, so a corpus owner can cap spend and force sampled QA before broad rollout. The entity-resolution/graph-quality problem CI-26 actually names is a modeling problem inside a given View's implementation, not something budget machinery solves alone. |
| CI-27 | Egress is a default, not a decision | Mitigated | grep/BM25/local-ANN are first-class, equally-weighted Operators, so a no-egress Plan constraint is an ordinary Optimizer constraint rather than a bolted-on "offline mode." Whether every registered enrichment View respects that constraint is an integration-discipline requirement on whoever wrote the View. |

**Tally: 7 solved, 19 mitigated, 1 unaddressed** (of 27).

---

## What this framework deliberately does NOT do

- **Not an agent-loop executor.** No ReAct loop, no multi-agent orchestration, no LLM provider SDK. Strata ships the substrate plus the four-verb tool contract; whoever builds the loop (LangGraph, a custom executor, a model's own tool-use loop) calls in. CI-12's loop-correctness and capability-regression legs are executor-layer bugs, and the corpus's own evidence is that the two frameworks that tried to own both layers (LangChain, Haystack) each spent a full rewrite getting the executor right (CI-12, "Root cause") — Strata does not take on that second full systems problem.
- **Not a low-code visual builder, and does not ship a template-rendering prompt engine or user-authored code-execution node.** This single decision removes the dominant CVE class in the corpus (CI-13: Langflow's CISA-KEV RCE, RAGFlow's Jinja2 RCE, Haystack's YAML-loading RCE, n8n/Dify's code nodes) by not building the feature that causes it, not by hardening it after the fact.
- **Not an embedding model, reranker, or LLM.** Bring-your-own. Strata is the substrate underneath, extending `indexing-vector-databases.md`'s own convergence thesis — vector search is becoming a feature of the data system, not a category — one layer up.
- **Not a from-scratch ANN or storage engine.** The MVP embeds proven index implementations (a DiskANN/turbopuffer-lineage or IVF+RaBitQ engine, Lance-format storage, an existing BM25 engine) behind the conformance-gated Operator contract rather than re-deriving index math. This follows the non-negotiable that parsing fidelity, not index cleverness, dominates quality.
- **Not a hosted managed-service business on day one.** The canonical corpus format is open and content-addressed by design; "kill-the-vendor" — rebuild everything from exported artifacts with the framework's own binaries deleted — is a target this document holds itself to, matching CI-08's fix.
- **Not a parsing/OCR research project.** Pluggable parsers carry per-span confidence through the pipeline; Strata does not claim to beat the ~14% F1 OHR-Bench ceiling, because that is a modeling problem, not an architecture problem (`document-processing-chunking.md`, Failure modes #1).
- **Not multilingual-first in v1** (CI-22, honestly unaddressed above).
- **The enforcement mechanism, not the intent.** The kernel — `Corpus`, `View`, `Plan`, `Operator`, `EvidenceState`, the four tool verbs — is governed by a **fixed public-symbol budget**: a new exported kernel symbol requires deleting one, checked in CI by a symbol-diff gate against the previous minor version. LangChain and LlamaIndex did not lack a discipline *statement* — both eventually wrote one down (Haystack's breaking-change policy, LangChain 1.0's stability pledge, CI-08's own steelman) only after the trust damage was done. Shipping the enforcement mechanism from commit one, rather than adopting a promise post-hoc, is the only version of "we won't repeat the death spiral" that a merge gate can actually check.

---

## Novelty vs prior art

- **vs LangChain / LlamaIndex / Haystack** (`langchain-langgraph.md`, `llamaindex.md`, `haystack.md`): these hard-wire the physical plan per backend inside `VectorStore`/`Retriever` classes; Strata compiles a logical CAL plan against live statistics. LangChain's own 1.0 migration — demoting retrieval to `langchain-classic` while rebuilding the agent loop as LangGraph — reads here as a tacit admission that stable-data-kernel and churning-orchestration needed separating; Strata separates them from day one instead of after the churn (CI-08).
- **vs Databricks Vector Search / Snowflake Cortex Search** (`datacloud-rag.md`): both already do CDC-style sync-from-source well (Delta Sync, dynamic tables). Strata's transaction log generalizes exactly this pattern, but neither platform versions the *derivation* (chunking/embedding/enrichment) the way View lineage does, and both weld the physical plan shut (Databricks' fixed RRF k=60 with no reranker choice; Snowflake's unexplainable zero-relevance results) — `datacloud-rag.md`'s own Lesson #4 calls for "the strong default and the tuning surface and score transparency," which a cost-based Optimizer with EXPLAIN provides where a fixed pipeline cannot.
- **vs turbopuffer / LanceDB / S3 Vectors** (`indexing-vector-databases.md` §3, §7): the closest prior art for axioms 2–3 — "object storage as source of truth, stateless compute, WAL-committed, async-indexed" is turbopuffer's and Lance's own architecture, and SPFresh's streaming cluster maintenance is the index-layer ancestor of the Derivation Engine. What is new is generalizing that pattern *above* the ANN index to the whole derivation DAG — chunks, graphs, contextual headers, caches — none of which turbopuffer, Lance, or S3 Vectors version or incrementally maintain; they solved it for one artifact type.
- **vs Microsoft GraphRAG / LazyGraphRAG** (`microsoft-graphrag.md`): GraphRAG treats the community hierarchy as a primary, eagerly-built artifact; LazyGraphRAG's actual fix — defer expensive computation to query time under budget — is what the Optimizer does for every operator, generalized past graph construction into a framework primitive rather than one project's cost optimization.
- **vs Azure agentic retrieval / Bedrock Managed KB agentic retrieval** (`production-industry.md`, Stage 4): both already run plan → parallel subqueries → rerank → sufficiency check as a managed pipeline, and Azure's activity log is the closest existing thing to EXPLAIN in production — but neither exposes a declarative language a caller compiles against their own statistics, neither treats their own index as a disposable derived view, and Azure's own hard-coded quotas (10/3/5 knowledge sources by reasoning effort) stand in for the cost-based plan selection the Optimizer is designed to make explicit and tunable (`production-industry.md` F12).
- **vs CaMeL / SD-RAG** (cited via `common-issues.md` CI-04/CI-05, `cross-cutting-gaps.md` O3–O4): these are the target enforcement contracts EvidenceState and principal/policy compilation are designed to compose with, not inventions of this document — SD-RAG's `(query, principal, policy) → (docs, provenance, privacy-cost)` is close to the Plan signature, and CaMeL's ~7-utility-point enforcement cost is the price this design expects to pay once that layer is integrated, not a problem it claims to have solved.
- **vs Chroma's generative benchmarking / Google's Sufficient Context** (CI-01, CI-10): adopted as the Eval subsystem's bootstrapping method and EvidenceState's sufficiency signal respectively. The contribution here is wiring them into the framework core as *defaults*, not improving the underlying science.
- **The genuinely new combination:** no framework or paper in this corpus combines (a) materialized-view lineage across the *entire* derivation DAG, not just the ANN index; (b) a cost vector of `(tokens, dollars, latency, recall-risk)` as the Optimizer's currency, not I/O alone; (c) principal/policy/budget as compiled, non-optional plan fields with differentiated fail-open/fail-closed semantics by construction; (d) EXPLAIN/replay as a default artifact of every call; and (e) budgeted, admission-controlled *derivation* — not just querying — as one discipline. Each piece has partial prior art named above; the combination, and specifically extending (a) and (e) above the index layer, is what is new.

---

## Feasibility

**MVP.**
- Canonical Corpus: content-addressed doc store with typed IR, backed by a relational store for the transaction log/metadata plus object storage for blobs/IR — the Lance/turbopuffer pattern, not a new storage engine.
- Content-defined chunking as the default chunk View — decades of dedup/backup prior art, genuinely unbuilt for RAG (`document-processing-chunking.md`), cheap to build correctly the first time.
- Three MVP Operators, each wrapping an existing, proven engine: grep/regex, BM25 (an existing Lucene/Tantivy-class engine), ANN (an embedded DiskANN-lineage or IVF+RaBitQ engine via Lance/pgvectorscale) — no new index math.
- A **rule-based** Optimizer for v1, with the EXPLAIN/Plan representation correct from day one. Cost-based optimization with live selectivity statistics over heterogeneous operator types is, per `indexing-vector-databases.md` §5 and its cited 2026 preprints (arXiv:2602.11443, arXiv:2602.17914), an open systems-research question even for filtered ANN alone; v1 ships a working heuristic behind the interface a cost-based planner will occupy later, so the interface commitment doesn't wait on the research.
- Principal/policy/budget as typed, enforced Plan fields from v1 — cheap, because it is a type-system and admission-control decision, not a modeling one.
- EvidenceState with an explicitly *uncalibrated-but-typed* score in v1, labeled as such. Full cross-corpus calibration is deferred rather than mis-claimed.
- Eval subsystem: adapt Chroma's generative-benchmarking method as the v1 bootstrapper, not a new judge-calibration invention.
- EXPLAIN/replay sequenced early, not bolted on later — precisely because CI-11's lesson is that bolting it on later is why it never happens.

**What is hard, or depends on research that does not exist yet.**
- A genuinely cost-based optimizer over heterogeneous operator types with live, calibrated statistics — filter-strategy selection alone is unsolved research as of the cited 2026 preprints; v1→v2 depends on this maturing, and this document is explicit that v1 is heuristic under the hood.
- Well-calibrated, cross-query-comparable relevance probabilities that survive fusion — open across both `retrieval-reranking-fusion.md` (open problem #2) and CI-10's "What research offers."
- Verified, provable erasure against embedding inversion strictly before compaction — CI-06 names this a live open problem no production ANN design closes with a proof rather than a policy.
- Set-level sufficiency selection (the minimal jointly-sufficient document set, not top-k by summed relevance) — `retrieval-reranking-fusion.md` open problem #1, genuinely combinatorial; EvidenceState's `sufficiency` field is a per-set autorater score in v1, not a selection algorithm optimizing for it.
- Typed values that structurally cannot reach the instruction position — CI-04's named research frontier; Strata's provenance/trust-tier propagation is the cheap-now half CI-04 distinguishes from this, integrating with a CaMeL-class layer rather than building one.
- Entity-resolution quality for graph Views at production cost — CI-26's actual defect (exact-string-match merging, spurious edges) is a modeling problem the budget machinery disciplines the *spend* on, not the *quality* of.

**Phasing.**

| Phase | Scope | Exit criterion |
|---|---|---|
| 0 — Kernel | Canonical Corpus, transaction log, content-defined chunking, `Plan`/EXPLAIN representation (no optimizer logic yet — plans are hand-specified) | A hand-written plan replays byte-identically against a pinned snapshot (CI-25) |
| 1 — Operators + heuristic planner | grep, BM25, ANN operators behind the conformance suite; rule-based Optimizer; principal/policy/budget enforced | Conformance suite passes for all three operators; a query at three budget levels never exceeds spend (CI-09) |
| 2 — Derivation + Eval | View refresh budgets, dual-read embedding migration, Eval subsystem golden-set bootstrap, regression gates | Edit-one-paragraph soak shows O(changed content) blast radius (CI-06); zero-config harness reports recall/nDCG for the default profile (CI-14) |
| 3 — Calibration + statistics-driven planning | Calibration curves feed the Optimizer's live statistics; cost-based (not merely rule-based) operator selection begins | Ablation shows the cost-based planner beats the Phase-1 heuristic on quality-per-dollar on at least one workload class |
| 4 — Enforcement composition | Integrate a CaMeL-class capability-enforcement boundary above EvidenceState; publish the ACL pre/post-ranking recall bound | Planted-imperative test shows zero behavior change (CI-04) |

Phases 0–2 are conventional systems engineering over existing prior art (Lance, an embedded ANN engine, Chroma's benchmarking method); Phase 3 depends on the filter-strategy-selection and calibration research named as open above; Phase 4 depends on integrating, not inventing, research this document does not claim credit for.

---

## Risks & open questions

1. **Optimizer-complexity risk.** A real cost-based optimizer for five-plus heterogeneous operator families is a multi-year systems-research undertaking even in pure relational databases' own history. Risk of shipping a rule table wearing an optimizer's costume; mitigation is labeling, release by release, exactly which decisions are cost-based vs heuristic — the CI-15 discipline applied to Strata's own claims about itself.
2. **Abstraction-soup relapse risk.** The DB stance is one CAL-surface leak away from recreating CI-11's black-box pipeline in new syntax. The four-verb tool surface and the fixed public-symbol budget are the concrete mitigations; discipline under adoption pressure is the same failure mode that broke every predecessor's *stated* intentions (CI-08's steelman: Haystack and LangChain both wrote policies only after the damage).
3. **Conformance-suite sustainability.** CI-03's own root cause is that a conformance suite is "unglamorous engineering" that loses to integration-count-as-growth-metric under the same open-core economics that hollowed out every predecessor (`common-issues.md`, "Three root engines," #1). Mandating conformance as a merge gate fights that incentive gradient; it is a governance risk, not only a technical one.
4. **Calibration may not be fully achievable in general**, not merely unbuilt. EvidenceState must degrade honestly (explicitly flag low-confidence calibration) rather than present false precision.
5. **Budgeted derivation at LLM-enrichment cost/latency** (dollars and seconds, not microseconds) breaks the classical IVM cost model. Admission control and staleness SLOs at that price point are addressed architecturally (§Derivation Engine) but untested.
6. **Open question — pre- vs post-ranking ACL recall guarantee.** What, formally, should a low-privilege caller's recall degradation look like, and can Strata publish a bound rather than a best-effort (CI-05's open residue, `cross-cutting-gaps.md` O4)?
7. **Open question — do trained tool-use policies actually extend grep/bash-level trust to a new four-verb surface**, or is the trust CI-24 documents specific to the literal tools models were RL'd against? This needs empirical measurement against real model policies, not an architectural assumption.
8. **Open question — business model.** Can an OSS core this conformance- and eval-heavy resist the exact open-core gravity (`common-issues.md`, "Three root engines," #1) that hollowed out eval, security, and conformance in every predecessor, especially since those are precisely the unmonetizable, unglamorous cost centers the taxonomy says get paywalled or deprioritized first?
9. **Cold-start risk.** A brand-new corpus has no selectivity histograms, no calibration curve, and no eval golden set yet — exactly the statistics the Optimizer and EvidenceState depend on. The rule-based Phase-1 planner (Feasibility, "Phasing") exists precisely to give a Day-1 user a working, if unoptimized, plan while those statistics accumulate; if they never accumulate (a low-traffic deployment, per Risk 6 above), the system should be honest that it is running on priors, not measured statistics — a labeling discipline, not a solved cold-start algorithm.
10. **Operator-gate friction risk.** The same conformance suite that closes CI-03 by construction is also a barrier to entry for third-party operator contributions (mirroring the CI-18 extension-gradient tension in the opposite direction: too easy to extend and you reproduce CI-03's unvetted-adapter problem; too hard to pass conformance and you reproduce the "black box or fork" complaint CI-18 raises about other frameworks). The conformance suite's own maintenance burden and turnaround time are unmeasured in this proposal and are a real adoption risk if they are slow.

---

## Evaluation plan

1. **Conformance suite as the primary correctness benchmark.** Golden filter/score/tenancy queries return identical result sets across every registered Operator×backend combination, published as a pass/fail table in CI — CI-03's literal acceptance test.
2. **Cost-budget adherence.** Same query at three budget levels; verify spend never exceeds budget; report the quality-degradation curve — CI-09's literal acceptance test.
3. **Incremental-correctness soak.** Edit one paragraph of a 100-page doc, measure blast radius (chunks re-derived); delete, measure time-to-zero-retrievable against a declared SLA; upsert-heavy soak measuring tombstone-driven recall decay — CI-06's literal acceptance tests.
4. **Reproducibility/replay.** Replay the same Plan against a pinned corpus snapshot across release N and N+4; byte-identical or diff-explainable — CI-08's kernel-compatibility test and CI-25.
5. **Tail-recall SLO, not mean recall.** Robustness-δ@K-style measurement (`indexing-vector-databases.md` §8) across filtered, OOD, and actively-updating workloads — the combination the same file calls the field's biggest benchmark gap.
6. **Abstention benchmark.** Measure abstention rate on a properly constructed, disambiguated benchmark (not the discredited `retrievalci` n=5 anecdote CI-10 demotes) against the field's documented ~0% baseline; report the monotone coverage/accuracy curve CI-10's acceptance test demands.
7. **Kill-the-vendor drill.** Delete every derived View/index for a registered vendor backend, rebuild from the canonical store alone, measure cost and wall-clock time — CI-07's rewritten acceptance target.
8. **Security pre-release gates.** PoisonedRAG/AgentPoison-style poisoning suites and CI-03's tenancy-isolation fail-closed cases run as merge gates, pass rate published over time; a planted-imperative test for zero behavior change (CI-04).
9. **Production A/B.** Shadow-deploy against an existing pipeline (LlamaIndex/LangChain baseline) on the same live corpus; report recall/nDCG parity plus the axes incumbent pipelines don't report at all — cost-at-budget adherence, tail-recall-δ, abstention-quality correlation, EXPLAIN-attributable-failure rate.
10. **Ablations isolating the stance's own load-bearing claims.** Cost-based vs rule-based planner (does the added complexity earn its keep, measured in quality-per-dollar); provenance/trust-tier on vs off (the planted-imperative zero-behavior-change test, CI-04); calibrated vs raw-similarity scores feeding the abstention decision (does calibration measurably move the coverage/accuracy curve, CI-10).
