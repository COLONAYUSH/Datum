# Legend — retrieval as a tool ecology for trained policies

*A capability contract and corpus substrate for the agent-native retrieval framework. Stance: agent-native. Compiled 2026-08-06 against `research/03-synthesis/common-issues.md` (verified taxonomy, CI-01…CI-27), `research/01-landscape/agentic-rag-deep-research.md`, `memory-context-engineering.md`, `frontier-2025-2026.md`, and the "Lessons for a next-generation framework" sections of `research/02-frameworks/{langchain-langgraph,llamaindex,agent-framework-retrieval,dspy,cross-cutting-gaps,haystack}.md`.*

---

## Design axioms

1. **Retrieval is a tool contract for a trained policy, not a hand-wired pipeline.** By mid-2026 the center of gravity moved from "RAG pipeline with an agent bolted on" to "agent with retrieval tools," and query formulation, routing, and stopping now live in the policy, increasingly RL-installed (`agentic-rag-deep-research.md` §State of the art; Search-R1/DeepResearcher/Tongyi DR/WebSailor lineage). A framework that hard-wires that logic is fighting the model it will be run under in 18 months.
2. **A corpus cannot be governed by a policy that cannot see it.** No published system formalizes "what does this corpus expose, at what cost, at what freshness" (`agentic-rag-deep-research.md` O1). Legibility — a declared, queryable capability schema — has to exist *before* navigation can be delegated to the model.
3. **A frozen, semver-stable kernel beneath a fast-moving policy layer.** CI-08 shows the ecosystem's defining operational failure is churn/demotion/death of exactly the retrieval plumbing users depend on, because no framework separated a stable substrate from the experimental orchestration layer riding fashion cycles.
4. **Budget is a typed, enforced input — never an afterthought.** Token spend explains ~80% of agentic-search performance variance (`agentic-rag-deep-research.md` §Retrieval budgets, Anthropic BrowseComp analysis) and CI-09 documents that no `retrieve()` signature anywhere accepts or honors `{tokens, latency, dollars}`. A capability contract without a budget contract is half a contract.
5. **Provenance and principal are non-optional slots in the type signature, not smuggled through a filter.** CI-04 and CI-05 are the same root cause twice: 2023-era IR signatures cannot express a writer, a trust tier, or a principal, so both get bolted on badly (or not at all) and CI-03 shows the bolt-on (metadata filters as ACL) fails silently and independently in four codebases.
6. **Evaluation is a default artifact of every retrieval call, not a paid feature bootstrapped from labeled data the user doesn't have.** CI-01's restated claim survives at ~12 cohorts: nobody ships an *integrated, self-maintaining* regression loop in a free tier. If measurement isn't structurally free, it will not exist (the taxonomy's own causal map: "evaluation is the load-bearing absence").
7. **The corpus is a canonical, versioned substrate; every index is a disposable, rebuildable derived view.** CI-02, CI-06, and CI-07 are three faces of one omission — no framework retains a durable, lineage-tagged parsed corpus independent of any single index's format, so sync breaks, erasure is unverifiable, and vendor lock-in is total.
8. **One contract, two consumers.** A frontier trained policy and a weak model calling the same corpus cannot be served by two different frameworks without duplicating the substrate; they must be served by the same tool contract at two different levels of scaffolding — a decoupled, cheaply-trained default searcher (`agentic-rag-deep-research.md` §RL-trained search agents, s3: 2.4k samples, model-agnostic frozen-generator design) sitting *in front of* the same tools a frontier policy calls directly.

---

## The core insight

Every framework in the corpus made the same category error, in one of two directions, and both directions trace to the same misdiagnosis: they thought the thing to invest in was **the loop**, when the loop was always going to be re-founded by whoever trained the best policy, and the thing that actually needed engineering discipline was **the substrate underneath the loop** — the part no policy, however smart, can bootstrap for itself from inside a context window.

Direction one is the over-abstraction death spiral: LangChain, LlamaIndex, and the low-code builders poured years of engineering into chains, DAGs, query engines, and visual retrieval pipelines — the loop — while leaving the substrate underneath at 2023 defaults: `str + dict` documents (CI-02), `retrieve(query, k) → docs` with no principal (CI-05) and no budget (CI-09), one-shot ingest with no lineage (CI-06, CI-07), and 20–100 independently-reimplemented store adapters with no conformance suite (CI-03). When the frontier proved the loop belongs to a trained policy — Search-R1, s3, WebSailor, Tongyi DeepResearch, GrepSeek, Claude Code's grep-only success (`agentic-rag-deep-research.md` §The agentic-search-vs-static-RAG debate; `frontier-2025-2026.md` §State of the art, item 1) — the years of loop-engineering became stranded cost, and LangChain's own 1.0 response was to demote the abandoned loop-work (retrievers, indexing API) to `langchain-classic` while the substrate underneath it *still* has no conformance suite, no budget primitive, and no principal today (CI-03, CI-05, CI-09 remain open in the same codebase that just re-founded its loop).

Direction two is the underspecification trap: DSPy, and increasingly the raw-SDK/BYO-everything posture the "RAG is dead" discourse encourages, correctly refuse to hand-wire the loop — and then leave the substrate to the user too. DSPy's own "Lessons" file names this precisely: "a RAG framework that optimizes query/synthesis prompts while treating ingestion, chunking, indexing, freshness, and ACLs as out-of-scope... optimizes the easy half" (`research/02-frameworks/dspy.md`). Refusing to own the loop is right. Refusing to own the substrate is not the same decision, and conflating them is the trap.

The corpus's own frontier evidence resolves which parts of "retrieval intelligence" actually moved into the model and which didn't. Query formulation, routing, and stopping moved — that's what RLVR training installs (`agentic-rag-deep-research.md` §RL-trained search agents: "RL installs behaviors prompting cannot reliably elicit — persistence, cross-source verification, knowing-when-to-stop"). But nothing in that literature shows a trained policy can *itself* enforce a conformance-tested filter algebra across store backends, propagate a provenance bit through chunking and compression, verify an entitlement set has zero false positives, or prove an erasure request actually removed embedding-invertible content before compaction. Those are not reasoning tasks a bigger model solves; they are correctness and security properties that must be true regardless of which policy — frontier or weak, trained or prompted — is issuing the query. Conflating "the model got smart enough to formulate good queries" with "the model got smart enough to be its own security boundary" is the single most consequential category error visible across all 27 issues: CI-04's provenance bit, CI-05's principal, and CI-03's filter algebra all fail for the same reason — the *substrate* delegated a correctness property to something with no obligation to enforce it.

So the fix is not "no framework" (BYO-everything strands every team on the same 27 issues independently) and it is not "big framework that hand-wires the loop" (the loop is exactly the part the frontier is racing to re-found monthly, per CI-08's 6–18-month churn cycles). The fix is a **thin, stable, capability-declaring tool contract on top of a thick, opinionated, boring corpus substrate underneath** — thin enough that a frontier policy calls it directly with no scaffolding tax, thick enough that a weak model's naive tool calls still can't violate an ACL, blow a budget, or retrieve unprovenanced text into the instruction position. "Make corpora legible, budgetable, and navigable — and get out of the way" (the provocation this document was asked to sharpen) does not mean building nothing; it means the framework's discipline is deciding, permanently, which half is the model's job and which half never can be.

---

## Architecture

Five layers. The bottom two are the "thick, boring" substrate (durable, framework-owned, semver-stable). The top three are the "thin" tool contract and its consumers (churn absorbed here, by design).

```
┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 4 — POLICY CONSUMERS  (churn lives here; framework does not own it) │
│                                                                            │
│   frontier trained policy ──┐        ┌── weak/local model                 │
│   (calls tools directly)    │        │   (driven by SearcherShim,         │
│                              │        │    s3-style decoupled searcher)    │
│                              ▼        ▼                                   │
│              host agent loop (LangGraph / Claude Agent SDK / CrewAI /     │
│              a custom ReAct loop) — Legend does not implement this        │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │  MCP / function-call boundary
┌────────────────────────────────▼───────────────────────────────────────────┐
│ LAYER 3 — WAYPOINT TOOL CONTRACT  (small, semver-stable, conformance-tested)│
│                                                                              │
│   search(intent, principal, budget, channels?) -> EvidenceSet              │
│   navigate(ref, depth, principal)              -> StructureView (headings, │
│                                                    section paths — no text  │
│                                                    materialized yet)        │
│   fetch(ref, span?, principal, budget)         -> Evidence (materializes   │
│                                                    exact span from Layer 0, │
│                                                    not a frozen chunk)      │
│   expand(evidence, principal, budget)          -> EvidenceSet (neighbors)  │
│   cite(evidence_ids)                           -> ProvenanceChain          │
│                                                                              │
│   Every call: principal-checked, budget-metered, sufficiency-scored,       │
│   trace-emitted. No call can return content without a provenance chain.    │
└───────────────────┬───────────────────────────────┬────────────────────────┘
                     │                               │
┌────────────────────▼──────────────┐  ┌─────────────▼─────────────────────┐
│ LAYER 2 — CAPABILITY MANIFEST      │  │ CROSS-CUTTING: GOLDEN LOOP          │
│ ("the Legend")                     │  │ (self-bootstrapping eval)           │
│                                     │  │                                      │
│ per-channel: scoring family,       │  │ generates golden set FROM the       │
│ cost/1k tok, coverage, freshness,  │  │ canonical corpus (zero labels);     │
│ match-explanation format,          │  │ gates every derived-view change;    │
│ conformance-suite status           │  │ ingests production feedback         │
└────────────────────┬───────────────┘  └─────────────┬────────────────────┘
                     │                                 │
┌────────────────────▼─────────────────────────────────▼────────────────────┐
│ LAYER 1 — DERIVED VIEW LEDGER  (versioned, lineage-tagged, disposable)     │
│                                                                              │
│  lexical/BM25 view   dense_v1 view   dense_v2 view   graph view   ...     │
│  each: {producer_version, config_hash, built_from=canonical, conformance} │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │  always rebuilt FROM layer 0, never from another view
┌────────────────────▼────────────────────────────────────────────────────────┐
│ LAYER 0 — CANONICAL CORPUS STORE  (durable, framework-owned, typed IR)     │
│                                                                              │
│  Document{ tree, section_paths, table_structure, page_coords, char_offsets,│
│            per_span_parser_confidence, acl_principal, writer_identity,     │
│            ingestion_path, content_hash }                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Dataflow, Day 1.** A document lands in Layer 0 via `corpus.ingest()`: it is parsed into the typed IR (tables, headings, offsets, ACL principal, per-span confidence — CI-02's requirement), content-hashed, and stored. Layer 1 derives one or more views from Layer 0 — never from another view (this is what makes Layer 0, not the vendor's index, the artifact that survives a re-embed, a vendor sunset, or a framework's own death: CI-07's rewritten acceptance target). Layer 2 aggregates every registered view's declared cost/coverage/freshness/conformance status into one queryable schema. Layer 3 is the only thing a policy ever calls: it resolves an `intent` against the manifest, checks the caller's `principal` against the entitlement suite, meters the call against `budget`, and returns a typed `EvidenceSet` with a sufficiency estimate and a provenance chain — never a bare list of strings. Layer 4 — the loop — is explicitly not Legend's problem; a frontier policy calls Layer 3 directly, a weak model is handed the `SearcherShim` reference policy that calls Layer 3 on its behalf. The Golden Loop watches every Layer 1 change and every Layer 3 call, without needing labeled data on day one, and gates promotion.

**Why this resolves the "frontier vs weak model" tension.** The provocation asks how one framework serves both. The answer in this architecture is: it doesn't have to choose, because the tool contract at Layer 3 is the *only* thing either consumer sees, and it is small and stable enough that a frontier policy's own training-time tool-use habits (grep-shaped calls, code-mediated batch access, semantically meaningful identifiers — `agentic-rag-deep-research.md` §Retrieval as tools) are satisfied natively, while a weak model gets the identical contract mediated by a small, cheaply-trained `SearcherShim` that does the query formulation and stopping the weak model can't reliably do itself — the s3 pattern (`agentic-rag-deep-research.md` §RL-trained search agents: 2.4k training samples, frozen generator, model-agnostic) generalized from "research artifact" to "shipped default." Neither consumer needs, or gets, a different substrate.

**A request, walked through all five layers.** A finance analyst's agent is asked "what drove EMEA churn in Q3?" against a corpus of contracts, CRM exports, and support tickets. Layer 4 (the host agent loop, not Legend's code) decides to call the `search` tool with that intent. At the Layer 3 boundary, the call is rejected in under a millisecond if `principal` is missing or `budget` is absent — there is no code path that reaches a store without both. The call resolves against the Layer 2 manifest, which reports that the `graph_v1` channel only covers 22% of this corpus and is 24 hours stale, so the planner (inside Layer 3, not the policy) weights it down and leans on `lexical` + `dense_v2`. Both channels are Layer 1 views built from the same Layer 0 canonical snapshot, so their results carry comparable, if not identical, coordinate spaces — a fusion step, not a coin flip. The entitlement conformance suite has already certified that `finance-eu` cannot see contracts tagged `acl_principal=legal-only`, so those rows are excluded before scoring, not after. The returned `EvidenceSet` carries a `sufficiency.coverage` of 0.81 — high enough that the loop proceeds to generation rather than issuing another `search` call — and every evidence item's `writer_identity` and `span` are attached, so the eventual answer's citations trace back to a page and a bounding region, not a chunk ID nobody can audit. The whole call is logged as one typed trace, identical in shape whether this was the only retrieval call in a single-shot pipeline or the fortieth call in a long agentic loop (CI-11's static/agentic parity requirement, met by construction because Layer 3 has exactly one code path regardless of caller).

### The frozen kernel

CI-08's acceptance test — "release N's kernel test suite passes against N+4" — only means something if the kernel's *type surface* is named, not just asserted stable. Layers 0–3 commit to exactly these types for the life of the project's major version; everything else (which parser, which embedder, which agent loop, which prompt) is free to churn above or beside it:

| Type | Owns | Frozen at |
|---|---|---|
| `Document` | typed structural IR: tree, section paths, table structure, page coords, char offsets, per-span parser confidence, content hash | Layer 0 |
| `Principal` | caller identity + groups/clearance used at every entitlement check | Layer 0/3 boundary |
| `DerivedView` | `(producer_version, config_hash, built_from=canonical_snapshot_hash)` — a view's full lineage | Layer 1 |
| `Channel` (capability record) | scoring family, cost/1k tokens, coverage, freshness, conformance status | Layer 2 |
| `Budget` | `{max_tokens, max_latency_ms, max_cost_usd}` plus a marginal-value-of-next-call estimate | Layer 3 |
| `EvidenceSet` / `Sufficiency` | evidence items with provenance + trust tier; calibrated coverage/relevance; `insufficient_evidence` as a value | Layer 3 |
| `ProvenanceChain` | writer identity + ingestion path + trust tier, surviving chunking/compression | Layer 0→3 |
| `Trace` | query, rewrites, per-stage candidates+scores, fusion weights — identical shape static or agentic | Layer 3 |

Explicitly **not** in the kernel, and therefore free to break every quarter without violating the CI-08 promise: the agent loop and its checkpointing/replay semantics (Layer 4), the generation-time prompt template, the `SearcherShim`'s internal policy (it may be retrained or replaced entirely — only its call shape into Layer 3 is stable), any specific embedder or parser choice, and the visual/UI layer, because there isn't one.

---

## Core abstractions & API

Eight load-bearing abstractions. Package name `legend`.

### 1. `Corpus` and the Canonical Document (Layer 0)

Owns the durable, typed structural IR — CI-02's requirement (section paths, table structure, page coordinates, char offsets, per-span parser confidence, ACL principal, writer identity) — and is the artifact every vendor index is rebuilt from, which is what makes CI-07's rewritten acceptance ("the framework's own state suffices to rebuild any vendor index from scratch") achievable.

```python
# The typed IR itself — not optional metadata, the object every stage operates on
@dataclass
class Document:
    content_hash: str
    tree: ElementTree              # headings, paragraphs, table cells, in reading order
    section_paths: list[str]       # e.g. ["4. Terms", "4.2 Termination"]
    table_structure: list[Table]   # cell spans, header rows — not flattened to text
    page_coords: list[BoundingBox]
    char_offsets: list[Span]
    parser_confidence: list[float] # per span — low-confidence spans are queryable,
                                    # not silently trusted (OHR-Bench's unmeasured gap)
    acl_principal: PrincipalRef
    writer_identity: str
    ingestion_path: str
```

```python
# Day 1
from legend import Corpus

corpus = Corpus.open(
    canonical_store="postgres://acme/legend_corpus",
    blob_store="s3://acme-docs-raw/",
)
corpus.ingest("./contracts/**/*.pdf", parser="docling", acl_from="frontmatter.owner_group")
# every Document gets: content_hash, section tree, table structure, page coords,
# per-span parser confidence, acl_principal — all typed, none optional.
```

```python
# Expert: enforce cross-stage contracts at build time (rejects the
# Haystack-#8491-class destructive composition before it ships)
from legend.contracts import requires_delimiter

@corpus.pipeline_stage("clean")
def strip_boilerplate(doc):
    return doc.without_footers()

corpus.validate_pipeline(["clean", "chunk"])
# raises ContractViolation: stage 'clean' strips '\n\n' that stage
# 'chunk(split_by="passage")' requires — rejected at build, not at query time.
```

### 2. `DerivedView` and the Ledger (Layer 1)

Every index — lexical, dense, multi-vector, graph, temporal — is a versioned, lineage-tagged view built from the canonical store, never from another view. Solves CI-06's incremental-correctness contract and CI-25's reproducible-run primitive by construction: a view's identity is `(producer_version, config_hash, built_from=canonical_snapshot_hash)`.

```python
# Day 1: default profile picks a dated, benchmarked hybrid+rerank recipe (CI-14)
view = corpus.derive_view(profile="2026-hybrid-rerank")
```

```python
# Expert: embedder migration with dual-read cutover and a drift report —
# the CI-07 acceptance test for the framework's *own* state, verbatim.
v2 = corpus.derive_view(name="dense_v2", channel="dense", embedder="voyage-3-large@1024d")
with corpus.dual_read(old="dense_v1", new="dense_v2", traffic_pct=0.10) as cutover:
    drift = cutover.overlap_report()   # retrieval-overlap drift, per CI-07's acceptance
    if drift.acceptable():
        cutover.promote()
    else:
        cutover.rollback()

# erasure with propagation verification (CI-06), not a best-effort delete —
# NOT a claim of proven unrecoverability against embedding inversion, which
# remains a named open problem (see Feasibility)
proof = corpus.erase(doc_id="contract-0091")
assert proof.propagated_to == {"canonical", "dense_v1", "dense_v2", "lexical", "graph"}
assert proof.non_retrieval_confirmed_within("PT1H")  # measured SLA, probed, not asserted-unrecoverable
```

### 3. `CapabilityManifest` — "the Legend" (Layer 2)

The negotiated capability schema `agentic-rag-deep-research.md` (O1) names as unformalized: what channels exist, at what cost, coverage, freshness, and scoring-function family, so a policy — or a human — can plan over heterogeneous retrieval, rather than the framework picking one scoring function by fashion (CI-14's frozen defaults; the LIMIT/MED tension the framework resolves by declaring, not picking, a scoring family per channel — see *Novelty*).

```python
manifest = corpus.manifest()
for ch in manifest.channels:
    print(ch.name, ch.scoring_family, ch.cost_per_1k_tokens, ch.coverage, ch.freshness)
# lexical      | sparse        | $0.0000 | 1.00 | live
# dense_v2     | single-vector | $0.0021 | 0.94 | 6h-lag
# multi_vec_v1 | late-interact | $0.0180 | 0.61 | 24h-lag
# graph_v1     | graph         | $0.0400 | 0.22 | 24h-lag
print(manifest.profile)   # "2026-hybrid-rerank" — dated and versioned, per CI-14
```

```python
# Expert: register a new channel; it cannot ship without a conformance report (CI-03)
@corpus.register_channel("multi_vec_v1")
class LateInteractionChannel(RetrievalChannel):
    scoring_family = "multi-vector"
    def search(self, query, principal, budget): ...
    def conformance_suite(self):
        return FILTER_ALGEBRA_CONFORMANCE_SUITE   # boolean nesting, IN/NOT-IN,
                                                    # datetime/tz, score normalization,
                                                    # tenancy isolation — CI merge gate
```

### 4. The `Waypoint` tool contract (Layer 3)

The MCP-native, semantically-identified, token-efficient tool surface — Anthropic's own tool-design guidance operationalized (`agentic-rag-deep-research.md` §Retrieval as tools: consolidate don't wrap, token-efficient responses, semantically meaningful identifiers) — and the CI-24 fix: one provider-agnostic retrieval-tool contract, conformance-tested, not a per-vendor bespoke surface.

```python
# Day 1: hand the toolset to any agent framework
from legend.tools import waypoint_toolset

tools = waypoint_toolset(corpus, principal=Principal.from_session(session))
agent = ClaudeAgent(model="claude-...", tools=tools)   # or LangGraph, CrewAI, raw MCP client
```

```python
# Expert: call directly, no agent framework at all
result = corpus.search(
    intent="Q3 2026 EMEA churn drivers",
    principal=principal,
    budget=Budget(max_tokens=4000, max_latency_ms=800, max_cost_usd=0.02),
    channels=None,   # let the manifest-aware planner choose; or pin explicitly
)
```

**Late-binding granularity.** CI-07's research note names index-time chunk-boundary commitment "architecturally wrong" (FreeChunker, Mix-of-Granularity, RSE; late chunking, arXiv:2409.04701) — and Layer 1's dense/multi-vector views necessarily commit to *some* granularity at build time, because that is an inherent property of precomputed embedding scoring, not an oversight. `navigate` and `fetch` exist precisely so a policy is never limited to whatever boundary a dense view froze: `navigate` walks Layer 0's structural tree (headings, section paths, table boundaries) without materializing any text, and `fetch` then materializes an arbitrary-boundary span directly from the canonical tree — a paragraph, a table row, a whole section — chosen at query time, not read back from a pre-chunked view. A policy that finds a promising heading via a cheap `navigate` call can decide how much of it to materialize, at what granularity, per query:

```python
# Expert: structure-first navigation, chunk boundary decided at query time —
# not frozen into whatever the dense_v2 view committed to at build time
structure = corpus.navigate(ref=doc_ref, depth=2, principal=principal)
for section in structure.sections:
    print(section.path, section.heading)   # "4.2 Termination" — no text materialized yet

ev = corpus.fetch(ref=doc_ref, span=structure.sections[3].full_span, principal=principal, budget=budget)
# materializes the whole section verbatim from Layer 0's tree — a table row,
# a subsection, or the full section, decided by the caller, not by an index
```

The MCP tool schema itself follows Anthropic's own tool-design guidance verbatim — consolidated (not a raw store wrapper), token-efficient with a `response_format` enum, and semantically identified rather than opaque:

```json
{
  "name": "search",
  "description": "Search the corpus for evidence relevant to an intent. Returns a typed EvidenceSet with provenance and a sufficiency estimate — never a bare list.",
  "input_schema": {
    "intent": "string — natural-language description of the information need",
    "budget": {"max_tokens": "int", "max_latency_ms": "int", "max_cost_usd": "number"},
    "channels": "string[] | null — omit to let the manifest-aware planner choose",
    "response_format": "'concise' | 'detailed' — trade tokens for evidence detail"
  }
}
```

### 5. `Budget` and the anytime contract

CI-09's fix, verbatim: `retrieve(intent, budget, principal) → evidence + cost trace`, enforced, degrading anytime, attributed per stage — and O2's marginal-value-of-next-call estimate, which no published system exposes as a controllable knob (`agentic-rag-deep-research.md` §Retrieval budgets: "nothing in current systems exposes it").

```python
budget = Budget(max_tokens=4000, max_latency_ms=800, max_cost_usd=0.02)
result = corpus.search(intent=q, principal=principal, budget=budget)
result.cost_trace
# {"lexical": {"ms": 12,  "usd": 0.0000}, "dense_v2": {"ms": 340, "usd": 0.0084}}
result.truncated          # True/False — flagged, never silent
result.marginal_value_of_next_call   # 0.14 — planner's own estimate
```

```python
# Expert: tiered degradation instead of overspend (CI-09's acceptance: full →
# sampled → embedding-only, never a silent full re-embed à la Snowflake)
plan = corpus.plan(intent=q, budget=Budget(max_cost_usd=0.005))
plan.tier   # "sampled" — chosen because full-hybrid would exceed budget
```

### 6. `EvidenceSet` — the typed, provenance-carrying, sufficiency-scored result

Never a bare top-k list. Carries CI-10's calibrated sufficiency signal (`insufficient_evidence` as a first-class value, not a threshold knob with a magic default) and CI-04's cheap-now half of the trust boundary: a provenance bit that survives chunking, distinguishing "user said this" from "we retrieved this" from "we stored this" — the exact bit whose absence caused Mem0's 808× re-extraction loop.

```python
@dataclass
class Evidence:
    text: str
    source: DocumentRef
    span: Span
    # grounded in what Layer 0 actually attests at ingestion — not a write-time
    # judgment call, and no "self_generated" tier: Legend has no memory
    # subsystem, so nothing in this design ever writes agent-generated content
    # back into the corpus as if it were a source.
    trust_tier: Literal["verified_source", "unverified_source"]
    writer_identity: str
    confidence: float             # inherited from Document.parser_confidence, not re-invented

@dataclass
class Sufficiency:
    coverage: float
    calibrated_relevance: float
    method: str                   # named, so "calibrated" is falsifiable, not a marketing word
    insufficient: bool            # first-class result type, per CI-10's acceptance test

result = corpus.search(intent=q, principal=principal, budget=budget)
for ev in result.evidence:
    ev.text, ev.source, ev.trust_tier, ev.span, ev.writer_identity

result.sufficiency
# Sufficiency(coverage=0.81, calibrated_relevance=0.77, method="qpp-v1")
if result.sufficiency.insufficient:
    raise InsufficientEvidence(result.sufficiency.explanation)   # first-class, not a hallucination
```

```python
# Expert: composition constraints for high-stakes answers (CI-04's requirement:
# minimum independent origins) and a byte-identical trace whether the call was
# static or issued from inside an agentic loop (CI-11's parity acceptance test)
result = corpus.search(intent=q, principal=principal, budget=budget,
                        min_independent_origins=2)
trace = result.trace   # {query, rewrites, per-stage candidates+scores, fusion weights}
```

### 7. `Principal` and the entitlement conformance suite (Layer 3 boundary)

CI-05's fix as a compile-time-shaped constraint, not a paywalled tier: `search()`/`fetch()`/`expand()` do not run without a `principal`, and every registered channel must pass a mandatory entitlement suite before it ships.

```python
principal = Principal(user_id="u123", groups=["finance-eu"], clearance="internal")
corpus.search(intent=q, principal=principal, budget=budget)   # principal is not optional
```

```python
# Expert: run the entitlement conformance suite in CI — the merge gate
from legend.conformance import entitlement_suite

report = entitlement_suite(corpus, channels=["dense_v2", "graph_v1"])
assert report.zero_out_of_entitlement_docs()
assert report.fail_open_cases == []   # the LangChain4j-#2513-class bug, caught before merge
```

### 8. `SearcherShim` — the decoupled default policy (Layer 4 reference implementation)

The s3 pattern (`agentic-rag-deep-research.md` §RL-trained search agents), generalized: a small, cheaply-trained-or-prompted searcher, decoupled from and agnostic to the generator, shipped as the Day-1 default so a weak or local model gets scaffolding without the framework hand-wiring the loop for everyone else.

```python
# Day 1 (weak/local model, or anyone who wants scaffolding)
from legend.policy import SearcherShim

shim = SearcherShim(generator=my_local_llm, corpus=corpus, principal=principal)
answer = shim.run("What drove EMEA churn in Q3?")
# shim formulates queries, decides when to call expand() vs search(),
# decides when sufficiency is met or budget is exhausted, and stops.
```

```python
# Expert: a frontier trained policy bypasses the shim entirely and calls
# Layer 3 natively — the same tools, no scaffolding tax
tools = waypoint_toolset(corpus, principal=principal)
agent = Agent(model="claude-opus-...", tools=tools)   # policy owns query
                                                        # formulation/stopping
```

---

## Issue-coverage traceability

Graded against each issue's **restated definition and testable acceptance criteria**, not its headline name. `Solved` = the design's architecture directly implements the rewritten acceptance test. `Mitigated` = the architecture provides the necessary hook or partial coverage but the full acceptance test depends on work outside a retrieval framework's reach (identity-sync machinery, model training, ecosystem-wide adoption, or genuinely open research). `Unaddressed` = deliberately out of scope or not reached by this design.

| CI | Issue (restated) | Legend's answer | Verdict |
|---|---|---|---|
| CI-01 | No integrated, self-maintaining eval loop in any core tier | Golden Loop generates a golden set from the canonical corpus with zero labeled data, gates every Layer-1 change; judge-calibration label budgets remain partly open research (per the issue's own "What research offers") | **Mitigated** |
| CI-02 | Structure/provenance survive only by convention | Layer 0's typed IR (section paths, table structure, offsets, per-span confidence) plus `validate_pipeline()` cross-stage contract rejection | **Solved** |
| CI-03 | Silent retrieval corruption via unconformant store abstractions; filter=ACL channel | One typed filter algebra + mandatory public conformance suite per registered channel (Abstraction 3), merge-gated | **Solved** |
| CI-04 | Unguarded trust boundary — no provenance/trust tier/corroboration | Provenance bit + writer identity survive into `EvidenceSet` (cheap-now half, solved); structurally preventing retrieved text from reaching the instruction position is the named research frontier (CaMeL-class), not solved here | **Mitigated** |
| CI-05 | Authorization as a paid tier, not a primitive | `principal` is a non-optional argument at every Layer-3 call, with a mandatory entitlement conformance suite; the expensive 95% (ACL-interchange, identity mapping, connector sync) is explicitly not built by this framework | **Mitigated** |
| CI-06 | Sync/deletion/erasure fragile and silently failing | Incremental-correctness contract on framework-owned Layer-1 views; `erase()` gives a propagation-completion proof and a measured, probed non-retrieval SLA. Verified *unrecoverability* against embedding inversion is explicitly not claimed — CI-06's own text names this a genuinely open problem, and this design does not solve it | **Mitigated** |
| CI-07 | Ingest-time one-way doors; lineage-free derived state | Canonical store + versioned derived views matches the rewritten acceptance exactly: "the framework's own state suffices to rebuild any vendor index from scratch" | **Solved** |
| CI-08 | Churn, retrieval demotion, platform death | Explicit kernel/orchestration split (Layer 0–3 semver-stable; Layer 4 explicitly not owned) quarantines churn; cannot guarantee this framework's own governance avoids the same economic fate | **Mitigated** |
| CI-09 | No cost primitive; cost never an enforceable input | `Budget` is a mandatory typed argument, enforced, attributed per stage, with tiered graceful degradation (Abstraction 5) | **Solved** |
| CI-10 | No calibrated sufficiency signal, no default abstention | `EvidenceSet.sufficiency` with `insufficient_evidence` as a first-class value; the calibration method itself (score calibration on RLHF'd models) is partly open research | **Mitigated** |
| CI-11 | Black-box pipeline — abstraction soup, hidden prompts, spans not stages | Every retrieval call emits a typed per-stage trace by default (Abstraction 6); `SearcherShim`'s query-formulation prompts and the Golden Loop's judge prompts are enumerable and overridable via a registry (avoiding DSPy's own most-cited adoption killer — unextractable compiled prompts); the *final answer* synthesis prompt remains explicitly anti-scope, owned by the host agent framework | **Mitigated** |
| CI-12 | Pipeline-era executor meets agent loop | Layer-1 derived-view writes are transactional and idempotent (a database-engineering property of the ledger, not a memory-consolidation feature); Legend ships no agent memory subsystem at all, which per CI-12's own steelman is "arguably correct separation of concerns, not a defect" — the memory-write-path leg belongs to the memory-product cohort, not a retrieval framework; the loop-native executor and superset-parity rule remain Layer 4, owned by the host agent framework | **Mitigated** |
| CI-13 | RAG-defining features are the CVE surface | No generation-prompt templating engine, no visual builder, no code-execution nodes exist to be the CVE surface; parameterized filter construction and sandboxed default-deny ingestion address the ingestion/filter half | **Mitigated** |
| CI-14 | Frozen demo-grade retrieval defaults | Dated, versioned, benchmark-backed manifest profiles (`profile="2026-hybrid-rerank"`) replace scattered constants; every release publishes regression numbers | **Solved** |
| CI-15 | Measurement theater — vendor self-benchmarks, uncalibrated judges | Golden Loop ships a replicable, pinned-config harness with disclosed judges; cannot force the ecosystem's vendors to stop self-benchmarking | **Mitigated** |
| CI-16 | Open-loop production — feedback never reaches the retriever | Golden Loop ingests production query/click logs into the regression corpus; a full debiased learning-to-rank system is not shipped out of the box | **Mitigated** |
| CI-17 | DX-governance decay — docs contradict the API, issue theater | Kernel stability reduces the churn that drives doc rot; doc-example execution in CI is a stated discipline, not yet a proven track record | **Mitigated** |
| CI-18 | Broken extension gradient — black box or fork | Built-ins (channels, parsers, policy shims) are dogfooded through the same public `RetrievalChannel`/manifest interfaces exposed to users | **Mitigated** |
| CI-19 | No resource-governed runtime — memory leaks, unbounded growth | Not addressed by this design; streaming-ingestion memory ceilings and kill-9 resume are an implementation/ops concern this document does not specify | **Unaddressed** |
| CI-20 | Billing decoupled from workload — idle floors, orphaned resources | Canonical-store ownership makes teardown/rebuild cheap and visible in the manifest; vendor idle-billing floors on closed backends are outside the framework's control | **Mitigated** |
| CI-21 | Tail-latency opacity, hard QPS ceilings | Manifest schema carries a required declared-latency/cost field per channel, making the gap visible; no SLO benchmarking harness is shipped | **Mitigated** |
| CI-22 | English-centric retrieval stacks | Not addressed; per-language analyzers, fusion weights, and telemetry are not part of this design | **Unaddressed** |
| CI-23 | Vendor documents the hazard and ships the workaround | A "governed" profile that refuses to activate without ACL/provenance/sandboxing declared is a stated design commitment, not yet proven across third-party channel integrations | **Mitigated** |
| CI-24 | Broken retrieval-tool seam; model priors distrust custom tools | One provider-agnostic, MCP-native, conformance-tested tool contract (Abstraction 4); cannot retrain a model's learned distrust of non-grep tools, only design toward it | **Mitigated** |
| CI-25 | No reproducible-run primitive | Content-hashed canonical snapshots + versioned view manifests + recorded per-stage traces give exactly the pinned-manifest, deterministic-replay primitive this issue demands | **Solved** |
| CI-26 | Ungated LLM enrichment injects noise below cheaper baselines | Derived-view versioning gives enrichment (graph/summary) views the same lineage and Golden-Loop gating as any other view; entity-resolution quality itself is not solved here | **Mitigated** |
| CI-27 | Egress is a default, not a decision | Governed profile design commitment supports a verifiable no-egress mode; the loopback-only test harness itself is an implementation task, not yet built | **Mitigated** |

**Tally: 6 solved (CI-02, CI-03, CI-07, CI-09, CI-14, CI-25) · 19 mitigated · 2 unaddressed (CI-19, CI-22).** A table with everything marked "solved" would be evidence the exercise wasn't taken seriously — several of the taxonomy's own restated acceptance criteria (CI-05's connector-sync machinery, CI-04's structural-separation frontier, CI-10's calibration method) are honestly beyond what a retrieval framework, as opposed to an identity platform or a model-training program, can close.

---

## What this framework deliberately does NOT do

The anti-scope is the discipline that keeps Layer 0–3 thin enough to stay stable for the CI-08 kernel promise. Everything below is a considered exclusion, not an oversight:

- **No agent loop, orchestrator, or scheduler.** LangGraph, the Claude Agent SDK, CrewAI, or a bespoke ReAct loop own Layer 4. Legend ships `SearcherShim` as a *reference* default policy for weak models, not a mandatory executor — and explicitly does not attempt the "loop-native executor" CI-12 demands; that is the host framework's problem to solve, and several (LangGraph via checkpointing, Haystack via its 2.7 rework) already are.
- **No generation-time prompt templating engine.** The final answer's prompt belongs to the agent framework or the application. This is not laziness: CI-13's dominant CVE surface is precisely templated-prompt injection (RAGFlow's Jinja2 RCE, Haystack's PromptBuilder RCE) — not having this component removes that attack surface by non-existence rather than by hardening it. (Legend does own two narrower, non-templated prompt surfaces — `SearcherShim`'s query-formulation prompt and the Golden Loop's judge prompt — and both are registered, diffable, and overridable at one site, precisely so they don't reproduce DSPy's unextractable-compiled-prompt complaint; neither is a general-purpose templating engine and neither renders user-controlled input as executable template syntax.)
- **No visual DAG/pipeline builder.** Low-code retrieval builders are the single most CVE-dense cohort in the corpus (CI-13: Langflow's CVE-2025-3248, CVSS 9.8, on CISA KEV) precisely because they ship user-authored code nodes as a product feature. Legend has no such surface.
- **No proprietary vector index or vector database.** Legend is index-agnostic by design; it ships conformance suites and a canonical-corpus contract that any store (Postgres/pgvector, Qdrant, Weaviate, a managed Bedrock KB) must satisfy to be registered as a channel — it does not compete with them.
- **No multi-agent orchestration framework.** Delegation contracts (coverage spec, budget, stop conditions — `agentic-rag-deep-research.md` O7) are exposed as a schema any orchestrator can consume; Legend does not implement subagent spawning, context handoff, or synthesis.
- **No model training.** Legend consumes trained policies (frontier or the shipped `SearcherShim`); it does not run RLVR pipelines, curate SFT data, or claim to train anything beyond the shim's own narrow, cheap-to-retrain searcher.
- **No agent memory subsystem.** `memory-context-engineering.md`'s convergence thesis argues memory and retrieval share a read path (context selection under a budget) but differ on the write path (consolidation, invalidation, provenance-at-write-time). Legend owns exactly the read-path substrate the thesis says transfers — typed provenance, principal, budget, sufficiency — and deliberately does not build the write/consolidation layer (extraction pipelines, forgetting policies, ADD/UPDATE/DELETE adjudication) that CI-12's memory-transactionality leg and the memory landscape file both locate in a different product category. A memory product can be built as a Layer-4 consumer that writes into Layer 0 through the same `ingest()` contract everything else uses; Legend does not ship one.
- **No standalone hallucination-detection or guardrails product.** `EvidenceSet`'s typed provenance and sufficiency fields are the substrate other trust/safety tooling should build on; Legend does not ship a generation-time fact-checker.
- **No proprietary document parser.** Layer 0 plugs into best-of-breed parsers (Docling, vendor OCR, custom extractors) behind the canonical-IR interface; it does not attempt to out-parse OHR-Bench's finding that no current parser is adequate for RAG.
- **No cross-lingual retrieval stack, no resource-governed ingestion runtime.** Named explicitly in the traceability table as unaddressed (CI-19, CI-22) rather than silently ignored.

The rule this anti-scope encodes: **if a capability can be expressed as a declaration in the manifest or a typed field in the contract, it belongs in Legend; if it requires Legend to make a judgment call that a trained policy, a specialized security product, or an orchestration framework is better positioned to make, it does not.**

---

## Novelty vs prior art

At a glance, against the specific frameworks named below:

| Prior art | Owns the loop | Owns the substrate | What Legend adds |
|---|---|---|---|
| LangChain / LangGraph | Yes (re-founded via LangGraph) | Partially (`langchain-classic`, unconformant) | Conformance suite, principal, budget as non-optional |
| LlamaIndex | Transitioning away | Partially (docstore/vector-store split) | One persistence plane; manifest-driven routing |
| DSPy | Deliberately no | Deliberately no | Owns Layer 0–2 so the data layer isn't "someone else's problem" |
| Haystack | Yes (2.7 rework) | Best-in-cohort (typed sockets) | Cross-store conformance; principal; canonical/derived-view split |
| CrewAI / Letta / Mastra / pydantic-ai | Yes (retrieval-as-tool, correctly) | No (no conformance, no trust tier) | The substrate this cohort's own bet was missing |
| Bedrock KB / Snowflake Cortex / managed stores | N/A (no loop exposed) | Vendor-owned, closed | Canonical store the vendor never owns; index becomes disposable |
| MCP reference servers | N/A | Explicitly disclaimed | Conformance suite as a CI gate, not a README footnote |

- **vs. LangChain / LangGraph.** LangChain 1.0 already validated axiom 3 empirically — retrievers and the Indexing API were demoted to `langchain-classic` while investment moved to the agent loop (`research/02-frameworks/langchain-langgraph.md`, Lesson 1). Legend takes that demotion as *confirmation of where churn belongs*, but inverts what gets frozen: LangChain froze the loop-era retrieval code and left the substrate (conformance, budget, principal) exactly as unspecified as before. Legend freezes the substrate and treats the loop as permanently someone else's layer.
- **vs. LlamaIndex.** LlamaIndex's own pivot post concedes "the query-engine-as-app model is fading" and its autopsy's Lesson 7 calls for exposing retrieval as "cheap, composable, idempotent tools... for agent loops" (`research/02-frameworks/llamaindex.md`) — the Waypoint contract is that recommendation made concrete, with the addition LlamaIndex's own docstore/vector-store split shows it still lacks: one persistence plane (Layer 0) that the derived views (Layer 1) cannot silently diverge from.
- **vs. DSPy.** DSPy correctly refuses to hand-wire the loop and ships an exportable, diffable optimized artifact — Legend borrows that "expose the compiled artifact" discipline for the manifest and the trace, but rejects DSPy's corollary that the data layer (ingestion, chunking, ACLs) is out of scope (`research/02-frameworks/dspy.md`, Lesson 2 names this gap explicitly). Legend owns Layer 0–2; DSPy-style optimizers are a plausible Layer-4 consumer, not a competitor.
- **vs. s3 (arXiv:2505.14146).** s3 demonstrated a small, decoupled searcher beats end-to-end entangled training at 1/70th the samples, with a frozen, provider-agnostic generator. `SearcherShim` generalizes this from a research result trained once on a fixed benchmark into a shipped, retrainable default policy that any Day-1 user gets for free — the paper's contribution becomes a product surface, not a citation.
- **vs. Claude Code / Cline / GrepSeek (index-free retrieval).** The corpus is explicit that this pattern has a measured boundary: GrepSeek concedes a lexical ceiling on surface-form variation, and LightOn's rebuttal notes "you can't grep a diagram" (`agentic-rag-deep-research.md` §The agentic-search-vs-static-RAG debate; `frontier-2025-2026.md` failure mode 11: designs that pick index-free *or* embedding-first "inherit the losing regime of the other"). Legend does not choose a side: the manifest declares each channel's scoring family (sparse/dense/multi-vector/graph/generative) and lets the policy route by predicted query-combinatorics, operationalizing the framework-implication both files name but neither builds ("the interesting design variable is... the interface contract between agent and corpus," `agentic-rag-deep-research.md` §Framework implication).
- **vs. the LIMIT/MED single-vector debate.** LIMIT (arXiv:2508.21038) proved single-vector top-k is combinatorially bounded; the corpus's own tension-preservation note is that this is routinely over-read as "abandon embeddings," while the MED = Θ(k) result (arXiv:2601.20844) shows the practical failure is geometry/training, not pure impossibility (`frontier-2025-2026.md` §2). Legend's answer is architectural, not rhetorical: declare the scoring family per channel in the manifest so a policy — or a benchmark — can *see* which channels are single-vector-bounded and route accordingly, rather than a framework quietly picking one embedding model as if the bound didn't exist (which is what CI-14's frozen defaults do today).
- **vs. Anthropic's context-engineering canon (Skills, MCP code execution, context editing).** Legend adopts the same defaults — progressive disclosure, reference-first loading, code-mediated bulk access — as load-bearing design commitments, not optional integrations (`frontier-2025-2026.md` §5, "progressive disclosure is the loading discipline"). What Anthropic's canon does not cover, and Legend adds, is the corpus-side substrate underneath those tools: conformance-tested backends, principal enforcement, lineage, and a self-bootstrapping eval loop. Anthropic ships the tool-design philosophy; Legend ships the thing the tools point at.
- **vs. MCP reference servers.** The MCP reference memory server explicitly disclaims production security in its own README (CI-04's weakest, self-labeled corroborator) and is copied as a template anyway. Every Waypoint channel Legend ships must pass the entitlement and filter-algebra conformance suites before registration — the disclaimer becomes a CI gate instead of a README footnote.
- **vs. Bedrock KB / Snowflake Cortex / managed vector stores.** These treat the vendor's index as the primary artifact (CI-07); Legend treats every one of them as a disposable, rebuildable *channel* registered against a canonical store the vendor never owns — precisely the target CI-07's verification pass rewrote the acceptance test to require.
- **vs. GraphRAG / LightRAG.** "Is GraphRAG Needed?" (arXiv:2606.25656) found expanded graph retrieval doesn't proportionally improve quality and basic RAG competes at 19–53% lower cost. Legend's manifest treats graph as one declared, costed, conditionally-selected channel rather than a universal architecture — the framework-level version of that paper's own conclusion.
- **vs. the agent-framework cohort (CrewAI, Letta, Mastra, pydantic-ai).** This cohort already committed to "retrieval-as-tool" years before the rest of the ecosystem — the autopsy's own Lesson 6 credits it with winning that architectural bet (`research/02-frameworks/agent-framework-retrieval.md`). What it didn't win is the substrate: CrewAI's `#5057` concatenates retrieved memory directly into the system prompt with no trust tier (the CI-04 mechanism this design's `Evidence.trust_tier` field exists specifically to prevent), Letta and Mastra's memory issues are recall/consolidation-quality bugs rather than transactional-write bugs, and none of the four ships a cross-backend conformance suite or a mandatory principal. Legend is the same architectural bet (retrieval-as-tool, agent owns the loop) with the substrate this cohort left unbuilt underneath it.

---

## Feasibility

**MVP (buildable with today's tools, no new research required).** Single-tenant deployment: Layer 0 on Postgres + object storage with one parser (Docling) behind the canonical-IR interface; Layer 1 with two channels — BM25 lexical and one dense embedder — each versioned by `(producer_version, config_hash, canonical_snapshot_hash)`; a Layer-2 manifest exposing both channels' declared cost/coverage/freshness; a Layer-3 MCP server implementing `search`/`fetch`/`expand`/`cite` with a static worst-case budget estimator and a single-provider RBAC-backed `Principal` check; a Golden Loop v1 that generates a stratified QA set from the canonical corpus via LLM-judge self-bootstrapping (no external labels) and gates any Layer-1 config change; `SearcherShim` as a lightly-prompted (not yet RL-trained) reference policy. This is squarely buildable: every individual piece (typed IR, filter conformance suites, budget accounting, RBAC checks, corpus-derived golden sets) is engineering the corpus's own "What research offers" sections repeatedly call *solved, ignored* — not a research bet.

**Genuinely hard, but tractable engineering.** A public, cross-backend filter-algebra and score-normalization conformance suite covering boolean nesting, negation, IN/NOT-IN, datetime/timezone, nulls, and tenancy isolation (CI-03's fix) is exactly the kind of decades-old database discipline (JDBC/ODBC conformance testing, Jepsen-style verification) the ecosystem has simply never built for vector stores — hard to get every backend to pass, not hard to specify. Dual-read cutover with a retrieval-overlap drift report (CI-07) and completion-proof erasure with propagation tracking (CI-06) are similarly hard-but-known distributed-systems engineering, not open research.

**Depends on research that does not yet exist.** Four items the design explicitly does not claim to solve: (1) **structurally preventing retrieved text from reaching the instruction position** — CI-04's research-frontier half; CaMeL-class provable injection resistance costs ~7 utility points today and is not yet a drop-in library primitive. (2) **A principled marginal-value-of-next-call estimator** — O2 in `agentic-rag-deep-research.md` is named as unsolved at the interface level; Legend's `marginal_value_of_next_call` field is a slot the contract reserves, not a solved estimator on day one, and will ship with a crude heuristic until better estimators exist. (3) **Score calibration on RLHF'd models for a general-purpose sufficiency signal** — CI-10's calibration method is explicitly flagged open; Legend's `Sufficiency` object is a typed home for whatever calibration method research produces, not proof that one exists yet. (4) **Verified, auditable erasure in ANN indexes** — CI-06's own text is unambiguous that this is "a named open problem — no production HNSW/IVF design offers auditable erasure." `corpus.erase()` gives a completion proof for *propagation* (every registered view actually received the delete) and a measured non-retrieval SLA via probe; it does not, and cannot yet, assert unrecoverability against embedding-inversion attacks (vec2text) on content a third-party backend may already have cached or exported before the erase call. The Layer-1 code sketch above is written to reflect exactly that boundary.

**What an MVP cannot claim.** It cannot claim to have solved CI-05's expensive 95% (ACL-interchange formats, identity mapping, group-membership sync at Glean/Q-Business scale) — that requires partnership with identity platforms (SCIM, OpenFGA) outside a retrieval framework's remit. It cannot claim CI-19's resource-governed runtime or CI-22's multilingual stack, both explicitly unaddressed above.

**Build sequence, phased against what depends on what.**

- **Phase 0 (MVP, above).** Single tenant, two channels, static budget estimator, lightly-prompted shim, zero-label Golden Loop. Proves the layering works end to end; proves nothing about scale, multi-backend conformance, or a trained shim.
- **Phase 1 (substrate hardening).** Multi-backend filter-algebra conformance suite extended to at least three real store vendors (the CI-03 fix has to be proven against more than Legend's own reference channel or it's not really a conformance suite); dual-read cutover and completion-proof erasure exercised against a live corpus mutation workload; entitlement suite extended to a real IdP integration (SCIM-backed group sync) rather than a toy RBAC table — this is where CI-05's honestly-unsolved 95% gets a first real answer, via partnership rather than in-house build.
- **Phase 2 (policy layer maturation).** `SearcherShim` moves from lightly-prompted to actually RL-trained (the s3 recipe, ~thousands of samples, frozen generator) so the weak-model experience risk named below has a real answer instead of a promise; `marginal_value_of_next_call` moves from a heuristic to something validated against the arXiv:2608.01913-style diagnostic (does the estimate actually correlate with whether continuing helped); manifest-aware routing is A/B tested against fixed fusion weights on real mixed workloads.
- **Phase 3 (ecosystem, not framework, work).** Getting third-party vendors (Pinecone, Qdrant, Bedrock) to publish their *own* conformance results against the public suite is a coordination problem, not an engineering one, and is realistically a multi-year adoption curve — the framework can only make the suite exist and free to run; it cannot compel anyone to run it.

---

## Risks & open questions

- **The framework itself could suffer CI-08's fate.** A design document cannot pre-commit an OSS project to surviving open-core economics; without a stated governance model (a semver pledge with teeth, a foundation rather than a single VC-backed vendor), Legend's own kernel is exactly as vulnerable to the churn/demotion/death cycle its axioms diagnose in everyone else. This has to be an organizational commitment, not just an architectural one.
- **The bitter-lesson risk.** If frontier training absorbs more of what Layer 3 currently formalizes — if models learn to self-enforce budgets or infer trust tiers from context alone — parts of this substrate could become a depreciating asset. The corpus's own evidence suggests this risk is asymmetric: query formulation and stopping are demonstrably learnable (RLVR results); ACL enforcement, provenance propagation, and conformance are correctness/security properties with no training signal that makes them go away, because a model has no incentive gradient toward refusing to retrieve unauthorized content it was never told was unauthorized.
- **Weak-model experience risk.** If `SearcherShim`'s default policy is mediocre, Day-1 users comparing Legend against LlamaIndex's or Haystack's more hand-holding defaults may get a worse out-of-box experience even though the substrate underneath is stronger — the MVP's shim ships lightly-prompted, not RL-trained, and that gap is real until someone trains it.
- **Conformance-suite adoption is a coordination problem, not just an engineering one.** CI-03's fix only works if store vendors actually run the suite; Legend can require it for anything it registers as a first-party channel, but cannot force Bedrock, Pinecone, or Qdrant to publish conformance results for their own APIs. The suite may end up catching only what Legend itself builds, not what it wraps.
- **MCP's own immaturity is inherited.** CI-24 documents that 9 of Spring AI's 15 most-commented issues are MCP transport/auth failures. Building the Waypoint contract MCP-native ties Legend's reliability to a protocol still shaking out its own auth and transport story.
- **The canonical corpus store becomes the highest-value target in the system.** Centralizing provenance, ACL principals, and raw content in one durable Layer 0 store is precisely what makes CI-07's rebuild-from-scratch acceptance test possible — and precisely what makes that store the single most attractive breach target in the architecture. This has to be treated as the crown-jewel asset from day one, not an afterthought.
- **Open question: does declaring a scoring family per channel actually change routing behavior, or just documentation?** The manifest's bet is that a policy (or a router trained against it) will use declared cost/coverage/scoring-family metadata to route better than a fixed fusion weight would. This is untested; §Evaluation plan below proposes the ablation, but it is a live risk that the manifest becomes descriptive metadata nobody's policy actually conditions on.
- **Manifest gaming and self-reported metadata.** A registered channel declares its own cost, coverage, and freshness — nothing in the architecture stops a poorly-implemented or adversarial backend from over-claiming coverage to win more routing traffic. The conformance suite catches correctness bugs (wrong results) but not honesty bugs (accurate results, dishonest metadata) unless coverage/freshness claims are independently audited against the canonical store, which this design does not yet specify a mechanism for.
- **Cold-start quality of the Golden Loop itself.** A zero-labeled-data golden set generated from a brand-new, small, or narrow corpus may be low-diversity or self-confirming — the framework could gate changes against a golden set that shares the same blind spots as the corpus it was generated from, producing false confidence rather than the false negative signal CI-01 is trying to fix. This risk is structurally similar to the "toy-target auto-tuning" pattern CI-15 already documents in auto-optimizers, and the Golden Loop needs its own held-out, adversarially-sampled slice to avoid reproducing it.

---

## Evaluation plan

**Substrate-level benchmarks (prove the kernel is correct, not just designed).**
- Filter-algebra and score-normalization conformance suite (CI-03) as a pass/fail CI gate across every registered backend — golden filter queries must return identical result sets; a mistranslating backend cannot merge.
- Entitlement conformance suite (CI-05) — zero out-of-entitlement documents across pre- and post-ranking filtering paths, including the fail-open NOT-IN case that broke LangChain4j.
- The **kill-the-vendor drill** (CI-08's acceptance test, run literally): delete Legend's own binaries, and using only the exported canonical store and view manifests, have a third party rebuild a recall-equivalent retrieval system from scratch. Recall parity on a held-out golden set is the pass condition.
- Erasure completion-proof SLA compliance via an automated probe: `erase()` → zero retrievable chunks across index/cache/replica within a declared window, on a soak test large enough to also surface tombstone-driven recall decay.

**Retrieval-quality benchmarks (prove the manifest and channels are worth having).**
- BEIR/MIRACL for baseline lexical/dense channel quality; LIMIT (arXiv:2508.21038) run explicitly to characterize *where* the dense channel's combinatorial ceiling binds, published in the manifest's own coverage metadata rather than discovered by users in production.
- EnterpriseRAG-Bench (arXiv:2605.05253 — explicitly the credible benchmark, disambiguated per CI-10's verification note from the discredited `retrievalci` anecdote) for abstention/sufficiency: measure the fraction of unanswerable questions on which `EvidenceSet.sufficiency.insufficient` fires correctly, against a baseline established by running the same managed platforms and OSS defaults CI-10 surveys through the identical harness — not the discredited five-question anecdote, and not assumed at 0% without measurement.
- "Is GraphRAG Needed?" (arXiv:2606.25656)-style ablation: with the graph channel declared-but-unused vs. declared-and-selected by the manifest-aware planner, confirm the planner avoids the graph channel exactly when basic hybrid retrieval would have won on cost-adjusted quality.

**Agentic-loop benchmarks (prove the contract serves both consumer types from axiom 8).**
- DeepResearch Bench II / GAIA / BrowseComp-class tasks run three ways on the same corpus: (a) a frontier trained policy calling Waypoint tools directly, (b) `SearcherShim` driving a weak/local model, (c) a hand-wired baseline pipeline (LangChain- or LlamaIndex-style) — measuring task success, token cost, and latency. The design's claim is falsified if (a) shows a meaningful scaffolding tax versus a bespoke tool integration, or if (b) fails to close a meaningful fraction of the gap to (a) for the same weak model.
- Diagnosing Search Behavior-style analysis (arXiv:2608.01913) applied to Legend-mediated runs: does `marginal_value_of_next_call` actually correlate with whether continuing to search improved the final answer, or is it noise dressed as a signal?
- A MemArena-style (arXiv:2608.02613) adapted permission-leak probe against the Waypoint contract specifically — the paper's finding that "permission-aware access fails universally" is exactly the regression Legend's entitlement suite is supposed to prevent; this is the test that would catch it if the suite has a gap.

**Ablations.**
- Golden Loop on/off: reproduce the Haystack `#8491`-class silently-destructive pipeline composition and confirm `validate_pipeline()` catches it before merge, and that the self-bootstrapped golden set catches the resulting recall regression without any external labels.
- Budget enforcement on/off: same query at three budget levels — confirm spend never exceeds budget and quality degrades monotonically (tier: full → sampled → embedding-only) rather than failing hard or silently overspending (the Snowflake/DSPy-optimizer failure mode CI-09 documents).
- Manifest-aware routing vs. fixed fusion weights: does letting the policy see per-channel cost/coverage/scoring-family metadata actually beat a static hybrid fusion constant on a mixed workload of precision-shaped and recall-shaped queries?

**Production metrics (the ones that matter after ship).**
- Recall/nDCG per dated manifest profile, tracked over time, with regression alarms wired to the Golden Loop (closing CI-16's open loop).
- Cost-per-resolved-query trend, and the fraction of billed tokens attributable to a named stage (CI-09's ≥95% attribution target).
- Conformance-suite pass rate across all registered backends in CI, tracked as a first-class release metric, not a one-time audit.
- Rate and correctness of `insufficient_evidence` firing against a held-out unanswerable-question set, re-run every release as the manifest's channels evolve — the number this whole design is ultimately staked on, since a sufficiency signal nobody trusts is worse than no signal at all.

**Falsification criteria — what would make this design wrong, not just incomplete.** The stance is falsified, not merely disappointed, if any of the following hold up under the benchmarks above: (a) a frontier policy calling Waypoint tools directly performs *measurably worse* than the same policy given a bespoke, hand-wired retrieval integration — meaning the "thin contract" imposed a real scaffolding tax rather than a negligible one; (b) `SearcherShim` fails to close a meaningful fraction of the gap between a weak model with no scaffolding and a frontier model, on the same corpus and budget — meaning the s3-style decoupling doesn't generalize past its original paper's conditions; (c) the entitlement or filter-algebra conformance suites pass in CI but a MemArena-style adversarial probe still finds a permission leak — meaning the suites are testing the wrong invariants, not just an incomplete set of them; (d) manifest-aware routing performs no better than a fixed fusion weight on a mixed precision/recall workload — meaning capability declaration is documentation, not a decision input, and axiom 2 does not actually cash out into better retrieval. Any one of these should be read as a design failure, not a tuning problem.
