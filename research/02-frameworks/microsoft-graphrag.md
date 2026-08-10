# Microsoft GraphRAG (+ LazyGraphRAG, nano/fast forks) — Framework Autopsy

*Research date: August 5, 2026. All repo statistics pulled live from the GitHub API on this date.*

---

## Identity & adoption

| Field | Value |
|---|---|
| Maintainer | Microsoft (Microsoft Research "Project GraphRAG"; repo under `microsoft/graphrag`) |
| License | MIT |
| Created | 2024-03-27 (public code release July 2024; paper arXiv:2404.16130, April 2024) |
| GitHub stars | **35,267** (3,702 forks) as of 2026-08-05 |
| Latest release | v3.1.1 (2026-07-18); v3.0.0 "monorepo restructure" 2026-01-28 |
| Issue hygiene | 828 total issues, only **4 open** — the project auto-closes aggressively (96 closed issues mention "stale") |
| Commit cadence 2025–2026 | Single-digit commits most months (e.g., 3 in Jun-2025, 4 in Oct-2025, 3 in Apr-2026); a 29-commit spike in Feb-2026 around the v3 restructure. Maintenance-mode tempo, not active feature development. |
| Companion assets | `Azure-Samples/graphrag-accelerator` (one-click Azure deployment): **archived**, last push 2025-05-27 |
| Ecosystem forks | nano-graphrag (gusye1234): 3,960★; fast-graphrag (circlemind-ai): 3,839★, last push Nov-2025; LightRAG (HKUDS): **38,535★ — now more stars than upstream GraphRAG itself**, actively pushed 2026-08-05 |

Adoption signal summary: GraphRAG was the highest-profile "structured RAG" release of 2024 (282-point HN thread on release, [HN 40857174](https://news.ycombinator.com/item?id=40857174)). By 2026 the research brand (LazyGraphRAG, Microsoft Discovery) is thriving inside Microsoft while the open-source library has settled into low-velocity maintenance, and the community's center of gravity has visibly migrated to lighter third-party reimplementations (LightRAG, nano-graphrag, fast-graphrag).

---

## Retrieval-pipeline architecture

GraphRAG is a **batch indexing pipeline + four query engines**, not a serving framework. Everything is Python, orchestrated as a DAG of "workflows" writing parquet tables to storage (file/blob/CosmosDB), with vectors in LanceDB/Azure AI Search/CosmosDB.

### Ingestion & parsing
- Input: text/CSV/JSON files from a directory or blob store (JSON added v2.1.0). No document-format parsing layer of its own — PDF/HTML/Office extraction is entirely out of scope; you bring plain text. No connector ecosystem, no ACL capture, no source-system sync.

### Chunking
- Documents → "TextUnits", default **1,200 tokens with 100 overlap**, token-count based. Docs concede the fidelity trade-off: "Larger chunks result in lower-fidelity output and less meaningful reference texts" ([default dataflow docs](https://microsoft.github.io/graphrag/index/default_dataflow/)). No structure-aware, semantic, or layout chunking.

### Graph extraction (the signature — and cost center)
- Every TextUnit goes through an LLM **entity + relationship extraction** prompt, with optional repeated "gleaning" passes to catch missed entities (multiplying token spend).
- Optional **claim/covariate extraction** — disabled by default and, per the docs, "generally requires prompt tuning to be useful."
- **Entity merging is exact-match**: "any entities with the same title and type are merged by creating an array of their descriptions," then an LLM summarizes the merged descriptions. There is **no fuzzy entity resolution / coreference layer** ("MSFT" ≠ "Microsoft"; "Bob Smith" ≠ "Robert Smith").

### Graph augmentation & community summaries
- **Hierarchical Leiden** clustering recursively partitions the entity graph into a multi-level community tree.
- An LLM writes a **community report** (executive-summary style) for every community at every level — another full round of LLM calls across the hierarchy.

### Embedding/indexing
- Embeds TextUnits, entity descriptions, and community-report text into a vector store (LanceDB default). Outputs are parquet tables (entities, relationships, communities, community_reports, text_units) plus optional GraphML snapshots.

### Query handling / retrieval / synthesis — four modes ([query docs](https://microsoft.github.io/graphrag/query/overview/))
1. **Local search** — embed the query, match entities, fan out to neighbors, related TextUnits, community reports and claims; build a mixed context window; one synthesis call. Best for entity-specific questions.
2. **Global search** — "a resource-intensive method": **map-reduce over all community reports** at a chosen level (each report batch scored/summarized by an LLM, then reduced). Designed for corpus-wide "what are the main themes" questions; cost scales with community count, i.e., with corpus size, *per query*.
3. **DRIFT search** — local search bootstrapped by community information; iteratively expands with follow-up sub-queries ("greatly expands the breadth of the query's starting point"). More comprehensive, more LLM calls.
4. **Basic search** — plain top-k vector RAG, included explicitly as a comparison baseline.
- **No reranker stage anywhere** — relevance is embedding similarity plus LLM map-scoring; there is no cross-encoder/reranking abstraction in the pipeline.
- There is **no automatic query router**: the caller must choose local vs global vs drift per query (E²GraphRAG, arXiv:2505.24226, calls out this reliance on "manually pre-defined query modes" as a practical limitation).

### Extensibility
- v2.x added a factory/registration pattern for LLM providers, storage, and custom pipeline injection (v2.4.0); v3.0 split the codebase into 7+ packages (`graphrag-llm`, `graphrag-chunking`, `graphrag-storage`, …) and switched model access to litellm. Prompt tuning has a dedicated auto-tuning CLI. Extensibility is real but arrived late and via repeated breaking rewrites (see Issues).

### LazyGraphRAG (the research successor)
- Announced 2024-11-25 ([MSR blog](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)): replaces upfront LLM extraction with **NLP noun-phrase co-occurrence concept graphs** (indexing cost ≈ vector RAG, "0.1% of the costs of full GraphRAG"), defers all LLM work to query time via best-first + breadth-first "iterative deepening" under a **relevance-test budget**. Claims: comparable quality to GraphRAG Global Search at **>700× lower query cost**; at 4% of global-search query cost it "significantly outperforms all competing methods" on 100 synthetic local+global queries.
- Availability reality (as of Aug 2026): shipped **inside Microsoft products only** (Microsoft Discovery; Azure Local public preview, June 2025). **Still not in the open-source library** — see Issues.

---

## Agentic integration

- GraphRAG predates the agent era and shows it: it is a **static two-phase batch pipeline** (index once, query many). There is no retrieval-as-tool packaging, no MCP server, no memory abstraction, no conversation state, no agent loop hooks in the core library.
- The query API is callable from LangChain/LlamaIndex/Semantic Kernel wrappers, and the community treats local/global/drift search as three separate tools an agent must choose between — the framework itself provides no routing policy.
- Fixed query modes are the opposite of what agentic systems want (adaptive, budgeted, multi-step retrieval). Ironically, **LazyGraphRAG's iterative-deepening design is agent-shaped** (budgeted relevance tests, query expansion), which is presumably why Microsoft routed it into its agentic Discovery platform rather than the OSS repo.
- The graph itself is opaque to agents: entities/relations live in parquet; there is no first-class graph-query surface (Cypher/SPARQL) an agent could traverse; GraphML export is a snapshot artifact, and incremental updates don't even refresh it (issue #1836).
- Freshness constraints (no cheap incremental update, see below) make it a poor substrate for agent memory, which is write-heavy.

---

## Strengths (steelman)

1. **It legitimized query-focused summarization over corpora.** The "From Local to Global" paper (arXiv:2404.16130) identified a real hole in vector RAG — global "sensemaking" questions ("what are the main themes?") that no top-k chunk retrieval can answer — and built a principled answer: hierarchical Leiden communities + pre-computed community summaries + map-reduce. Independent benchmarking confirms the niche: the systematic evaluation arXiv:2502.11371 and the unified-framework study arXiv:2503.04338 both find graph/global methods genuinely ahead of vector RAG on abstract, multi-hop, corpus-level questions.
2. **Reproducible, inspectable artifacts.** Deterministic parquet outputs at every stage (entities, relationships, communities, reports) are auditable and reusable by other tools — far more transparent than opaque vector stores.
3. **Honest self-baselining.** Shipping "basic search" (vanilla vector RAG) inside the framework as an explicit comparison mode is unusually intellectually honest.
4. **It spawned a research lineage.** LazyGraphRAG, DRIFT, dynamic community selection, and the entire third-party wave (LightRAG, fast-graphrag, KET-RAG, HippoRAG comparisons) all iterate on its skeleton; the cost of graph indexing fell ~1000× in 18 months partly due to this pressure ([Graph Praxis cost-cliff analysis](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4)).
5. **Azure-grade storage plumbing.** Blob/CosmosDB storage providers, Azure AI Search vectors, managed-identity auth — real enterprise plumbing that hobby frameworks lack.
6. **MIT license and real research pedigree** — free to fork, which the community did, productively.

---

## Issues & failure modes

### performance-cost

- **[CRITICAL / documented-recurring] Indexing token burn is economically prohibitive at corpus scale.** Every TextUnit gets LLM extraction (plus gleanings), merged entities get LLM re-summarization, and every community at every hierarchy level gets an LLM-written report. Concrete numbers: **$33,000 to index a single 5 GB legal corpus in early 2024** ([Graph Praxis](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4): "a 10,000× cost premium on indexing is not a conversation most engineering leads survive in a budget review"); extraction $20–50 per million tokens at GPT-4-class rates (Microsoft's own [cost-explainer blog](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-costs-explained-what-you-need-to-know/4207978)); day-one HN skepticism ("are the compute requirements here untenable for any decent sized dataset?" — [HN 40857174](https://news.ycombinator.com/item?id=40857174)). Academic confirmation: KET-RAG (arXiv:2502.09304) states LLM-based extraction "incurs prohibitively high indexing costs at scale" and matches/beats GraphRAG quality at >10× lower indexing cost; Microsoft's own LazyGraphRAG marketing concedes full GraphRAG indexing is ~1000× a vector index.
- **[MAJOR / documented-recurring] Global search cost scales with corpus size per query.** Map-reduce over *all* community reports means corpus-wide questions get more expensive as the corpus grows; Microsoft's LazyGraphRAG post quantifies its own baseline as **700× more expensive per global query** than the lazy alternative. Docs themselves label global search "resource-intensive." E²GraphRAG (arXiv:2505.24226) reports 10× faster indexing than GraphRAG while maintaining competitive QA.

### data-processing

- **[MAJOR / documented-recurring] Extraction noise and entity duplication — no entity resolution.** Merging is exact title+type string match (per official dataflow docs); no coreference or fuzzy resolution. Evidence: feature request #1244 "Improved coreference resolution when building knowledge graph" (closed unimplemented); HN release-thread practitioner comment that naive LLM graph construction yields "a very 'dirty' Knowledge Graph full with duplications" ([HN 40857174](https://news.ycombinator.com/item?id=40857174)); issue #596 "The entities extracted from Chinese manual documents are very messy" (30 comments) shows quality collapses further off-English.
- **[MAJOR / single-anecdote] Deduplication silently destroys valid entities.** Issue [#1718](https://github.com/microsoft/graphrag/issues/1718) "[Fatal Bug]: Incorrect deduplication of entities with same title but different type": `finalize_entities` drops by title alone, so "only the first node with the same title is kept, and the others are discarded" — data loss in the graph. **Closed as not planned.**
- **[MINOR / architectural-inference] No document parsing layer.** Plain-text-in only; all real-world structure (tables, PDF layout, headings) must be flattened upstream, so structure loss is guaranteed before the "structured" pipeline even starts.

### production-ops

- **[CRITICAL / documented-recurring] The incremental-update problem.** The architecture front-loads global computations (entity merge, Leiden communities, hierarchical reports) that are invalidated by new data. Users begged for append support from month one (issue [#741](https://github.com/microsoft/graphrag/issues/741), 35 comments; discussions #511, #1313, #1366); maintainers acknowledged worst case "degrades to standard indexing" cost. The eventual `update` command shipped half-working: incremental runs **didn't generate the LanceDB vector files** (#1560) and **didn't update the GraphML graph output, splitting it in two** (#1836). Scope explicitly excludes deletion, graph editing, and delta queries. Fast-graphrag exists largely to sell "real-time incremental updates" against this gap.
- **[MAJOR / documented-recurring] Not a serving system, and the managed path was abandoned.** The official Azure deployment vehicle, `graphrag-accelerator`, is **archived** (last push May 2025). The library has no service layer, multi-tenancy, or job orchestration; every production deployment is DIY. HN thread "Is anyone deploying GraphRAG in prod?" ([41597587](https://news.ycombinator.com/item?id=41597587)) surfaced ~zero direct production users of the Microsoft library; commenters instead described KG-quality struggles and cheaper bespoke memory designs ("performance and $ cost really hurt").
- **[MAJOR / documented-recurring] Fragile pipeline runs.** A long tail of high-comment crash issues in ordinary indexing: "Errors occurred during the pipeline run" (#369, 29c; #485; #1180), "Columns must be same length as key" on entity extraction output (#443, #362, #514 — the same parse-failure crash recurring across versions), vector-type crashes in query (#1335, 33c), `KeyError: 'title'` (#1805). The pattern: when the LLM's output deviates from expected format, the pipeline throws pandas/JSON errors deep in workflow code rather than degrading gracefully.

### retrieval-quality

- **[MAJOR / documented-recurring] On ordinary factual QA, vector RAG matches or beats it — at a fraction of the cost.** The systematic evaluation "RAG vs. GraphRAG" (arXiv:2502.11371) finds neither paradigm dominates and vector RAG remains competitive (and far cheaper) on simple factual QA; the unified-framework study (arXiv:2503.04338) confirms graph methods pay off mainly on abstract/multi-hop questions; practitioner write-ups converge on "GraphRAG often underperforms on simple retrieval… reserve that complexity for query types where it produces a measured improvement" ([casys.ai comparison](https://casys.ai/blog/graphrag-vs-vectorrag)). The default posture — graph-everything — is wrong for most workloads.
- **[MAJOR / architectural-inference] No reranking stage and no query router.** Relevance is embeddings + LLM map-scoring; there is no cross-encoder rerank abstraction, and the user must manually pick local/global/drift/basic per query — a misrouted query silently gets the wrong retrieval strategy (E²GraphRAG explicitly criticizes the "manually pre-defined query modes").
- **[MINOR / documented-recurring] Hallucination pass-through.** 17 issues mention hallucination; e.g., #687 reports answers "completely different from the original text"; the original paper's own evaluation used LLM-as-judge win rates (comprehensiveness/diversity/empowerment) rather than ground-truth faithfulness, so the framework shipped with no built-in faithfulness check.

### dx-docs

- **[MAJOR / documented-recurring] Four major versions with breaking changes in ~25 months.** v0.9 (Dec 2024) invalidated all caches; v1.0 (Dec 2024) required a migration notebook; v2.0 (Feb 2025) reworked workflows, output naming, the API callback model, and "Remove[d] config inheritance, hydration, and automatic env var overlays"; v3.0 (Jan 2026) restructured into a monorepo of 7+ new packages and required `graphrag init --force` to regenerate config. (All from official release notes.) Every pinned production integration broke repeatedly.
- **[MAJOR / documented-recurring] OpenAI/Azure lock-in by design; local models were a community-support problem.** The library was built around OpenAI/Azure OpenAI clients; running Ollama/OSS models was met with a `community_support` label rather than support (issue [#339](https://github.com/microsoft/graphrag/issues/339), 68 comments; #345, 29c; #657 "Support model providers other than OpenAI and Azure", 15c; even #1673 "O1 models not supported"). Smaller models routinely fail the strict JSON/tuple extraction formats (227 issues match "json error"), crashing indexing. litellm-based provider abstraction only landed with v3 in 2026.
- **[MINOR / documented-recurring] Issue-tracker theater.** 828 issues with only 4 open, 96 closed via staleness — problems like #1718 (data-loss bug) are "closed as not planned," which makes the tracker look healthy while recurring defects persist.

### evaluation-observability

- **[MAJOR / architectural-inference] No evaluation loop or retrieval observability in the framework.** There is no built-in eval harness, no relevance/faithfulness metrics, no query-time tracing of which entities/communities contributed to an answer beyond raw context dumps. Given the paper's own eval was LLM-judged win rates on two datasets, users have no way to know whether the expensive graph is actually helping on their corpus — precisely the gap third-party studies (2502.11371, 2503.04338) had to fill externally.

### abstraction-design

- **[MAJOR / documented-recurring] The official implementation is over-engineered relative to its ~1,100-line essence.** nano-graphrag's stated raison d'être: "GraphRAG is good and powerful, but the official implementation is difficult/painful to read or hack"; it reproduces core functionality in ~1,100 lines ([nano-graphrag](https://github.com/gusye1234/nano-graphrag)). The existence and traction of three major reimplementations (LightRAG 38.5k★ > upstream's 35.3k★; fast-graphrag claiming 6× cost reduction — $0.08 vs GraphRAG's $0.48 on *A Christmas Carol* — plus PageRank retrieval and incremental updates) is the community's structural verdict on the upstream codebase's hackability and defaults.

### agentic-integration

- **[MAJOR / architectural-inference] Static batch pipeline in an agentic world.** No tool/MCP surface, no memory API, no adaptive retrieval budget, fixed query modes, and an index too expensive and too stale-prone to serve as agent memory. Microsoft's own trajectory is the tell: the agent-friendly successor (LazyGraphRAG's budgeted iterative deepening) shipped into Microsoft Discovery and Azure Local, not into this library.

### other (roadmap governance)

- **[MAJOR / documented-recurring] The LazyGraphRAG bait-and-switch.** Announced Nov 2024 with spectacular claims (0.1% indexing cost, 700× cheaper global queries); maintainer stated Dec 9, 2024 it was "the next top priority item to release" ([discussion #1490](https://github.com/microsoft/graphrag/discussions/1490); issue #1512 "When will LazyGraphRAG arrive?", 44 comments). **20 months later it has still not appeared in the OSS library**, while shipping inside Microsoft products (Discovery, Azure Local preview). The discussion thread shows users asking monthly through 2025, questioning whether the project was "shelved," and defecting to HippoRAG 2 / KET-RAG. Net effect: the OSS repo's flagship fix for its flagship problem (cost) is vaporware for OSS users.

---

## Community sentiment over time

- **Jul 2024 (release):** Peak hype — 282-point HN thread, but the top technical comments were already the two themes that defined everything after: token cost ("untenable for any decent sized dataset?") and dirty-graph quality ([HN 40857174](https://news.ycombinator.com/item?id=40857174)).
- **H2 2024:** Explosive issue volume — local-model support (#339/#345), pipeline crashes, incremental indexing demands (#741), non-English extraction quality (#596). nano-graphrag appears as the "readable" alternative; LightRAG (Oct 2024) and fast-graphrag (Nov 2024) launch. Sep 2024 HN thread "Is anyone deploying GraphRAG in prod?" finds essentially nobody.
- **Nov 2024 – 2025:** LazyGraphRAG announcement resets expectations; the year becomes a slow-motion disappointment as it never lands in OSS (discussion #1490's monthly "any update?" cadence). Breaking releases v1→v2 churn integrators. Academic verdicts land: graph pays off for global/multi-hop questions only; KET-RAG/E²GraphRAG demonstrate 10× cheaper equivalents. Azure accelerator archived (May 2025).
- **2026:** Repo stabilizes at maintenance tempo (v3 monorepo, litellm, CosmosDB work — infrastructure, not retrieval science). LightRAG overtakes GraphRAG in stars. Community discourse now treats "Microsoft GraphRAG" as the reference *idea* and cost cautionary tale, while builders use LightRAG/fast-graphrag/custom lazy variants. The "cost cliff" retrospective frames it as history: "$33,000 became $33 in eighteen months" — but via techniques largely outside the upstream library.

---

## Benchmarks & third-party evaluations

| Source | Finding |
|---|---|
| Edge et al., arXiv:2404.16130 (the GraphRAG paper) | Global search wins LLM-judged comprehensiveness/diversity vs vector RAG on 2 corpora (~1M tokens). Note: win-rate LLM-as-judge eval, no ground-truth accuracy — weak by 2026 standards. |
| **RAG vs. GraphRAG: A Systematic Evaluation** (arXiv:2502.11371) | Neither paradigm dominates; vector RAG competitive on factual QA; GraphRAG helps on summarization/multi-hop; recommends hybrid selection/integration. |
| **In-depth Analysis of Graph-based RAG in a Unified Framework** (arXiv:2503.04338) | Across QA datasets, graph methods carry "substantial upfront investment in knowledge graph construction"; vector RAG remains more cost-efficient on simple factual QA; graph wins concentrate on abstract/multi-hop QA. |
| **KET-RAG** (arXiv:2502.09304) | GraphRAG's LLM extraction "incurs prohibitively high indexing costs at scale"; a keyword-bipartite skeleton achieves comparable/superior retrieval quality at **>10× lower indexing cost**. |
| **E²GraphRAG** (arXiv:2505.24226) | GraphRAG-style methods "suffer from inefficiency and rely on manually pre-defined query modes"; achieves 10× faster indexing than GraphRAG with competitive QA. |
| **LazyGraphRAG** (MSR blog, Nov 2024) | Microsoft's own numbers indict the original: lazy variant = 0.1% of GraphRAG indexing cost, comparable global-search quality at >700× lower query cost. |
| **fast-graphrag** (circlemind) | 6× cheaper than GraphRAG on a like-for-like ingest ($0.08 vs $0.48, *A Christmas Carol*). |
| Microsoft cost explainer (Tech Community, 2024) | Entity/relation extraction ≈ $20–50 per million tokens at GPT-4-class rates; indexing is the dominant cost. |
| Graph Praxis cost retrospective (2026) | $33k to index 5 GB legal corpus (early 2024) → ~1000× reduction by mid-2025 via lazy/NLP techniques. |

Consensus reading: GraphRAG's *global sensemaking* advantage is real but narrow; for the majority of enterprise queries (factual, local), well-tuned vector RAG (optionally + reranking) matches it at orders-of-magnitude lower cost, and successor designs (lazy indexing, PageRank retrieval, bipartite skeletons) achieve the global benefits without the token bonfire.

---

## Lessons for a next-generation framework

1. **Defer expensive computation to query time under an explicit budget.** LazyGraphRAG's core insight — cheap NLP-level indexing + budgeted, best-first LLM effort at query time — beat the eager pipeline by 700× on query cost with equal quality. Eager corpus-wide LLM summarization should be the exception, not the default.
2. **Incremental update must be a day-one architectural invariant.** Any global artifact (communities, hierarchy-wide summaries) that a single new document can invalidate is a production landmine. Design for monotone/localized updates, stable IDs, and deletion from the start.
3. **Entity resolution is the load-bearing wall of graph RAG.** Exact string-match merging produces dirty graphs whose noise compounds through clustering and summarization. A next-gen framework needs first-class resolution (blocking + embedding + LLM adjudication) and a way to measure graph quality.
4. **Route queries adaptively.** Local/global/drift as user-selected modes is an abstraction failure; the system should classify or iteratively discover the right retrieval strategy per query.
5. **Ship the evaluation loop.** A framework that can 100× your indexing bill must ship the harness proving (per corpus) that the spend improves answers over a vector baseline — otherwise adoption decisions are faith-based.
6. **Degrade gracefully on malformed model output.** Structured-output failures should trigger retry/fallback, not `ValueError: Columns must be same length as key` five workflows deep.
7. **Be provider-neutral and small.** The 1,100-line nano-graphrag and the LightRAG star-count flip show that hackability and local-model support beat corporate pedigree in this ecosystem.
8. **Don't decouple the research org from the OSS repo.** Announcing a 1000× improvement and shipping it only into proprietary products while the OSS community waits 20 months converts goodwill into fork momentum.
9. **Agent-native interfaces.** Expose retrieval as budgeted, composable tools (traversal, community lookup, summary drill-down) with provenance, rather than monolithic search() modes — the graph is most valuable when an agent can walk it.

---

## Sources

- Paper: Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* — https://arxiv.org/abs/2404.16130
- Official docs: https://microsoft.github.io/graphrag/ ; default dataflow: https://microsoft.github.io/graphrag/index/default_dataflow/ ; query overview: https://microsoft.github.io/graphrag/query/overview/
- Repo + API stats (2026-08-05): https://github.com/microsoft/graphrag (35,267★; releases v0.9→v3.1.1; 828 issues/4 open)
- LazyGraphRAG announcement: https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- LazyGraphRAG timeline saga: https://github.com/microsoft/graphrag/discussions/1490 ; issue #1512
- Incremental updates: https://github.com/microsoft/graphrag/issues/741 ; #1560; #1836; discussions #511, #1313, #1366
- Local/OSS model support: https://github.com/microsoft/graphrag/issues/339 ; #345; #657; #374; #1673
- Extraction/dedup quality: https://github.com/microsoft/graphrag/issues/1718 ; #1244; #596; #443; #362; #514
- Pipeline fragility: #369, #485, #1180, #1335, #1805
- Cost: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-costs-explained-what-you-need-to-know/4207978 ; https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4
- HN: release thread https://news.ycombinator.com/item?id=40857174 ; prod thread https://news.ycombinator.com/item?id=41597587
- Forks: https://github.com/gusye1234/nano-graphrag (3,960★) ; https://github.com/circlemind-ai/fast-graphrag (3,839★) ; https://github.com/HKUDS/LightRAG (38,535★)
- Azure accelerator (archived): https://github.com/Azure-Samples/graphrag-accelerator
- Independent evals: arXiv:2502.11371 (RAG vs GraphRAG); arXiv:2503.04338 (unified framework); arXiv:2502.09304 (KET-RAG); arXiv:2505.24226 (E²GraphRAG)
- Practitioner comparison: https://casys.ai/blog/graphrag-vs-vectorrag
