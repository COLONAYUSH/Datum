# Graph & Structure-Augmented RAG: Lineage, Evidence, Failure Modes, and Open Problems (as of mid-2026)

## Scope

This document surveys retrieval-augmented generation systems that impose explicit *structure* — knowledge graphs (KGs), entity graphs, hierarchical community trees, hypergraphs, temporal graphs, and inference-time structurization — between a corpus and an LLM. It covers:

- The Microsoft GraphRAG family (local/global/DRIFT search, community summaries, LazyGraphRAG) and its cost economics.
- The Personalized-PageRank (PPR) line: HippoRAG 1 & 2, fast-graphrag.
- Lightweight graph-index systems: LightRAG, PathRAG, MiniRAG, nano-graphrag.
- Schema-constrained and logic-guided systems: KAG (Ant/OpenSPG), StructRAG, HyperGraphRAG, AutoSchemaKG.
- GNN-based graph retrieval: GNN-RAG, G-Retriever.
- Temporal knowledge graphs for agent memory: Zep/Graphiti.
- Query interfaces: text-to-Cypher vs embedding-graph hybrids.
- The KG-quality problem (LLM triple-extraction noise, entity resolution, incompleteness) and the incremental-update problem.
- Independent comparative evidence (graph vs vector vs hybrid vs agentic search), evaluation-methodology critiques, and an honest verdict on when graph structure is justified.

Audience: ML-systems researchers designing a next-generation RAG framework. Emphasis is on failure modes, critiques, and open problems; vendor claims are flagged as such throughout.

Method note: every citation below was seen directly in a web search result or a fetched primary page during this research pass (August 5, 2026). Claims that could not be verified against a primary source are explicitly marked *uncertain*.

---

## Lineage & chronological development

**2024 — the founding wave.**

- **Feb 2024 — G-Retriever** (He et al., arXiv:2402.07630) frames retrieval over textual graphs as a Prize-Collecting Steiner Tree optimization, returning a connected subgraph to the LLM; introduces the GraphQA benchmark. First general "RAG for textual graphs" formulation.
- **Apr 2024 — Microsoft GraphRAG** ("From Local to Global: A Graph RAG Approach to Query-Focused Summarization", Edge et al., arXiv:2404.16130; v2 Feb 2025). LLM extracts entities/relationships/claims per chunk; Leiden community detection builds a hierarchy; each community gets an LLM-written summary; *global search* map-reduces over community summaries, *local search* expands entity neighborhoods. Targeted at "global sensemaking" questions ordinary top-k RAG cannot answer, evaluated on ~1M-token corpora with LLM-judge win rates (comprehensiveness/diversity). This paper created the category and most of its downstream critiques (cost, LLM-judge evaluation).
- **May 2024 — HippoRAG** (Gutiérrez et al., arXiv:2405.14831, NeurIPS 2024). Neurobiologically inspired (hippocampal indexing theory): OpenIE-extracted KG + Personalized PageRank seeded from query entities. Reported up to ~20% improvement on multi-hop QA over strong retrievers, and comparable performance to iterative retrieval (IRCoT) while being 10–30× cheaper and 6–13× faster.
- **May 2024 — GNN-RAG** (Mavromatis & Karypis, arXiv:2405.20139; ACL 2025 Findings). Lightweight GNN scores KG nodes for KGQA; shortest paths from question entities to GNN answer candidates are verbalized as LLM context. A tuned 7B LLM matches/outperforms GPT-4 on WebQSP/CWQ; +8.9–15.5 F1 points over LLM-based retrieval on multi-hop/multi-entity questions with ~9× fewer KG tokens.
- **Aug 2024 — first survey** ("Graph Retrieval-Augmented Generation: A Survey", Peng et al., arXiv:2408.08921) formalizes the G-Indexing / G-Retrieval / G-Generation pipeline taxonomy.
- **Sep 2024 — KAG** (Ant Group, arXiv:2409.13731; WWW 2025 Companion). Rejects noisy OpenIE: schema-constrained KG on the OpenSPG engine, KG↔chunk *mutual indexing*, logical-form-guided hybrid reasoning (retrieval, KG reasoning, language reasoning, numerical calculation). Reported +19.6 F1 on HotpotQA and +33.5 on 2WikiMultiHopQA over NaiveRAG/HippoRAG baselines (vendor-run evaluation). Deployed in Ant's E-Government/E-Health.
- **Oct 2024 — LightRAG** (HKUDS, arXiv:2410.05779; EMNLP 2025 Findings). Dual-level retrieval (low-level entities, high-level themes) over a lightweight LLM-extracted graph; incremental insertion; far cheaper than Microsoft GraphRAG. Became the most-adopted OSS alternative.
- **Oct 2024 — StructRAG** (Li et al., arXiv:2410.08815). Inference-time *hybrid structurization*: pick the best structure type (table, graph, tree, chunk, algorithm) per task, convert retrieved documents into that structure, then reason. Structure as a query-time decision, not an index-time commitment — a conceptual bridge to LazyGraphRAG.
- **Oct–Nov 2024 — Microsoft iterates**: *dynamic community selection* for global search (Microsoft Research blog) prunes irrelevant communities to cut global-search cost; **DRIFT search** (blog) mixes global (community) and local (entity) search via dynamic traversal; **LazyGraphRAG** (blog, Nov 2024) replaces LLM index-time extraction with NLP noun-phrase co-occurrence graphs + query-time iterative-deepening (best-first + breadth-first) with a *relevance test budget* knob. Claims: indexing cost identical to vector RAG (0.1% of full GraphRAG); at 4% of GraphRAG global-search query cost it outperforms all compared methods on local and global queries; >700× lower query cost than global search at comparable quality.

**2025 — proliferation and the first reckoning.**

- **Jan 2025 — MiniRAG** (Fan et al., arXiv:2501.06713): heterogeneous chunk+entity graph designed so small language models can do graph-guided retrieval; ~25% of the storage of LLM-centric methods (author-reported).
- **Jan 2025 — Zep/Graphiti** (Rasmussen et al., arXiv:2501.13956): temporal KG engine (Graphiti) for agent memory; bi-temporal facts with validity intervals, fusing conversational and business data. Reported 94.8% vs MemGPT's 93.4% on DMR and up to +18.5% accuracy with ~90% latency reduction on LongMemEval (vendor paper; DMR itself is a weak, near-saturated benchmark — note the 1.4-point margin).
- **Feb 2025 — HippoRAG 2** ("From RAG to Memory", arXiv:2502.14802): passage+phrase dual-node graph, deeper passage integration, LLM triple filtering with PPR; ~7 F1 points over embedding retrievers on associative (multi-hop) tasks without regressing simple retrieval — positioned as non-parametric continual learning/memory.
- **Feb 2025 — PathRAG** (Chen et al., arXiv:2502.14902): argues the core graph-RAG problem is *redundancy*, not recall; flow-based pruning selects key relational paths, verbalized as chains.
- **Feb 2025 — the first serious independent comparison**: "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights" (Han et al., arXiv:2502.11371, v3 Mar 2026) — details in Comparative Evidence below.
- **Mar 2025 — HyperGraphRAG** (Luo et al., arXiv:2503.21322; NeurIPS 2025): n-ary facts as hyperedges, attacking the binary-triple expressiveness ceiling shared by GraphRAG/LightRAG/HippoRAG.
- **May 2025 — AutoSchemaKG** (Bai et al., arXiv:2505.23628): LLM-driven KG construction with *dynamic schema induction* (entities + events) at web scale — ATLAS: 900M+ nodes, 5.9B edges from 50M+ documents; 92% semantic alignment with human-crafted schemas (author-reported).
- **May–Jun 2025 — evaluation audits**: "How Significant Are the Real Performance Gains? An Unbiased Evaluation Framework for GraphRAG" (Zeng et al., arXiv:2506.06331) and **GraphRAG-Bench** ("When to use Graphs in RAG", Xiang et al., arXiv:2506.05690; ICLR 2026) both find GraphRAG gains "much more moderate than reported" and that GraphRAG "frequently underperforms vanilla RAG on many real-world tasks."
- **Jun 2025 — BenchmarkQED** (Microsoft Research blog): automated local/global query synthesis + LLM-judge evaluation; Microsoft reports LazyGraphRAG beating all comparators including 1M-token-context vector RAG (vendor-run).

**2026 — agentic search changes the question.**

- **Feb–Jul 2026 — frontier preprints** push past static graphs: "Breaking the Static Graph: Context-Aware Traversal for Robust RAG" (arXiv:2602.01965), GraphRAG-Router (RL routing across GraphRAG variants and LLMs, arXiv:2604.16401), HKVM-RAG (hypergraph evidence organization for multi-hop, arXiv:2606.07218), "Implicit Graph, Explicit Retrieval" (long-horizon memory, arXiv:2601.03417), SAG (SQL-RAG with query-time dynamic hyperedges, arXiv:2606.15971). (Titles/abstract-level only; treat as early preprints.)
- **Apr 2026 — RAGSearch** ("Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems", Fan et al., arXiv:2604.09666): unified benchmark of dense RAG vs five GraphRAG families as *retrieval infrastructure under agentic (multi-round) search*. Single-shot: GraphRAG wins multi-hop QA by ~+27 points average. With agentic search (especially RL-trained), dense RAG closes most of the gap; GraphRAG retains an edge on complex multi-hop and yields more *stable* agent behavior — but only pays off when offline indexing cost is amortized.
- **Jun 2026 — "Is GraphRAG Needed?"** (Chen et al., arXiv:2606.25656; ACL 2026 GEM workshop): 9-scenario decision framework across basic/Graph/Modular/Agentic RAG; finds a *retrieval–generation gap* — expanded retrieval doesn't proportionally improve generation, so retrieval metrics overstate advanced-RAG advantages; context-engineering cut tokens 19–53%.
- **2026 — surveys of the merged paradigm**: "A Survey of Agentic GraphRAG: From Retrieval-augmented Generation to Graph-native Agents" (Chen, Zheng, Zhu; SSRN 6713979) marks the field's pivot from static graph pipelines to graph-native agent traversal.

---

## State of the art — mid-2026 snapshot

1. **The default answer is no longer "build a KG."** Three independent 2025–2026 evaluations (Han et al. 2502.11371; GraphRAG-Bench 2506.05690; Zeng et al. 2506.06331) converge: graph structure is a *specialized* upgrade that wins on multi-hop/relational/sensemaking queries and loses (or ties at much higher cost) on single-hop, detail-oriented, and general QA. GraphRAG-Bench's framing — "GraphRAG frequently underperforms vanilla RAG on many real-world tasks" — is now the consensus prior.
2. **Agentic search is the main competitor to graph structure.** RAGSearch (2604.09666) shows multi-round agentic retrieval over a plain dense index recovers most of GraphRAG's multi-hop advantage. The live question is no longer "graph vs vector" but "offline structure vs inference-time compute," with graphs justified when query volume amortizes indexing and when agent-behavior *stability* matters.
3. **Cost pressure killed index-time maximalism.** Full GraphRAG indexing (~$20–48 reported for ~1M-token corpora on GPT-4o-class models; practitioner figures, corpus sizes vary) pushed the field to LazyGraphRAG (NLP-only indexing, deferred LLM), LightRAG/MiniRAG (cheap extraction), and fast-graphrag (claimed 6× cheaper than GraphRAG on a test book; vendor number).
4. **The strongest-evidence graph wins are narrow and reproducible:** PPR over entity graphs for multi-hop retrieval (HippoRAG 1/2), GNN retrieval over *curated* KGs for KGQA (GNN-RAG), and temporal graphs for evolving agent memory (Zep/Graphiti — vendor-evaluated but architecturally distinct).
5. **Hybrids beat purists.** Han et al. find selection/integration of RAG + GraphRAG consistently beats either; HippoRAG 2 and KAG both keep raw passages first-class alongside graph structure; LazyGraphRAG is effectively vector RAG + a cheap concept graph. Pure triple-only retrieval is dead.
6. **Evaluation hygiene is now a first-order concern.** Position bias in LLM-judge win rates can flip verdicts (>30-point win-rate swings when answer order is reversed, per the audit line of work); questions synthesized from the indexed corpus inflate graph-method scores.

---

## The Microsoft GraphRAG family

**Full GraphRAG (arXiv:2404.16130).** Indexing: chunk → LLM entity/relationship/claim extraction → weighted entity graph → Leiden hierarchical communities → LLM community summaries at each level. Query: *global search* (map-reduce over community summaries; strong on corpus-level sensemaking), *local search* (entity-neighborhood expansion mixing graph + chunks). Contribution: defined "global questions" as a distinct failure mode of top-k RAG. Limitations established by later work: (a) index cost scales with corpus × LLM price — a practitioner analysis reports ~$47.9 on GPT-4o for a moderate corpus, and ~$20–40 per 1M tokens is commonly cited (secondary sources; treat as order-of-magnitude); (b) evaluation used LLM-judge win rates on two 1–1.7M-token English corpora with position-bias problems (audited by arXiv:2506.06331); (c) global search sacrifices fine-grained detail and hallucinates on unanswerable ("null") queries (Han et al.); (d) community summaries go stale on corpus update (Leiden re-clustering is non-incremental — see Incremental Update below).

**Dynamic community selection & DRIFT (MS Research blogs, 2024).** Global-search cost reduction via LLM-rated community relevance pruning; DRIFT combines global priming with local traversal for detail. Incremental engineering, same index economics.

**LazyGraphRAG (MS Research blog, Nov 2024).** The self-correction: no LLM at index time (noun-phrase co-occurrence concept graph + community structure), all LLM work deferred to query-time iterative deepening under an explicit *relevance test budget* (Z100/Z500/Z1500 configurations). Claims (vendor, but directionally accepted by the community): index cost = vector RAG (0.1% of GraphRAG); beats GraphRAG global search at >700× lower query cost; at Z500 (~4% of global-search query cost) outperforms all compared methods on local *and* global queries. BenchmarkQED (MS blog, Jun 2025) extends this with automated query synthesis — but both remain vendor-run with LLM judges. Significance: Microsoft itself demonstrated that *most of the LLM-built KG was unnecessary* for the headline wins — the deferred, query-adaptive structure did the work. Ecosystem demand is visible (e.g., RAGFlow issue #3862 requesting LazyGraphRAG support).

## The PPR line: HippoRAG 1 & 2

HippoRAG (2405.14831, NeurIPS 2024) is the most-replicated graph-RAG win: seed PPR from query entities over an OpenIE graph; single-step retrieval matches multi-step iterative retrieval at 10–30× lower cost. HippoRAG 2 (2502.14802) fixes HippoRAG 1's main weaknesses (triple-only lossiness, entity-linking brittleness) by adding passage nodes to the graph, running recognition-memory-style LLM triple filtering, and integrating passages into PPR — ~7 F1 over embedding retrievers on associative tasks while preserving simple-QA performance. Framed as non-parametric continual learning ("RAG as memory"). Known limits: still binary triples; still dependent on extraction quality; PPR over a noisy graph propagates noise (motivating 2026's context-aware-traversal work, e.g., arXiv:2602.01965). fast-graphrag (circlemind-ai, GitHub, 3.8k stars) is the engineering popularization of the same PPR idea, claiming $0.08 vs GraphRAG's $0.48 to index *The Wizard of Oz* (vendor benchmark).

## Lightweight graph indexes: LightRAG, PathRAG, MiniRAG, nano-graphrag

- **LightRAG** (2410.05779, EMNLP 2025 Findings): dual-level (entity/theme) keyed retrieval over a cheap graph; incremental insertion; the de-facto OSS standard (HKUDS repo, very active). Critique: its original evaluation used LLM-judge win rates on questions generated from the same corpora — precisely the methodology the 2025 audits found inflates graph-method gains; GraphRAG-Bench and Zeng et al. report much more moderate real gains for this family.
- **PathRAG** (2502.14902): diagnosis that graph-RAG retrieval is *redundant* rather than insufficient; flow-based pruning to key relational paths, verbalized as chains. Directionally consistent with the "retrieval–generation gap" finding of arXiv:2606.25656 (more retrieved structure ≠ better generation).
- **MiniRAG** (2501.06713): graph indexing as a *compensation for weak models* — heterogeneous chunk+entity graph lets small LMs approximate LLM-based RAG at ~25% storage. Notable inversion: structure helps most when the reader is weak; strong readers extract relations from raw text themselves (consistent with GraphRAG-Bench's model-strength sensitivity findings).
- **nano-graphrag** (gusye1234, GitHub, ~1,100 LoC, 4k+ stars): hackable GraphRAG reimplementation (drops covariates; top-K community selection instead of full map-reduce). Its existence and popularity are evidence that the official pipeline was over-engineered relative to the effective mechanism.

## Schema, logic, and structure choice: KAG, StructRAG, HyperGraphRAG, AutoSchemaKG

- **KAG** (2409.13731, WWW'25 Companion; OpenSPG/KAG on GitHub): the strongest "engineered KG" counterpoint to OpenIE noise — domain-schema-constrained modeling, KG↔chunk mutual indexing, logical-form query decomposition over four operator types, knowledge alignment via semantic reasoning. Large vendor-reported multi-hop gains (+19.6 HotpotQA F1, +33.5 2Wiki vs NaiveRAG/HippoRAG). Cost: heavy schema/ontology investment; adoption largely inside Ant's ecosystem; independent replications scarce.
- **StructRAG** (2410.08815): structure as an *inference-time, task-conditional* choice among table/graph/tree/chunk/algorithm formats — cognitively motivated, and an early articulation of the principle LazyGraphRAG operationalized: commit to structure late.
- **HyperGraphRAG** (2503.21322, NeurIPS 2025): binary triples cannot represent n-ary facts (dosage–condition–population, contract clauses); hyperedges can. Reports accuracy/speed gains across medicine/agriculture/CS/law. Early; construction noise concerns transfer directly from triple extraction to n-ary extraction.
- **AutoSchemaKG** (2505.23628): schema induction at web scale (ATLAS: 900M nodes / 5.9B edges) — attempts to dissolve the schema-vs-OpenIE dilemma by inducing schemas automatically (92% alignment with human schemas, author-reported).

## GNN-based retrieval

**GNN-RAG** (2405.20139, ACL'25 Findings) and **G-Retriever** (2402.07630) show that when a *curated* KG exists (Freebase-style KGQA, scene graphs), learned graph retrieval beats LLM-driven traversal decisively (GNN-RAG: +8.9–15.5 F1 on multi-hop/multi-entity; 7B model ≈ GPT-4; G-Retriever: PCST subgraph selection reduces hallucination, handles graphs beyond context limits). Caveats: both presuppose a clean graph — they do not solve, and are downstream of, the KG-construction problem that dominates document-corpus GraphRAG; GNN retrievers need training data and generalize poorly across graph schemas (motivating e.g. arXiv:2506.09645 on generalizable graph retrievers).

## Temporal knowledge graphs & agent memory: Zep/Graphiti

Zep (2501.13956) + Graphiti (getzep/graphiti, ~20k+ stars per Zep materials) is the flagship *temporal* graph-RAG system: every edge carries validity intervals (bi-temporal: event time vs ingestion time), contradictory new facts *invalidate* rather than overwrite old edges, and retrieval hybridizes semantic, BM25, and graph traversal. This targets the dimension static GraphRAG ignores: knowledge that changes. Claims are vendor-produced: the DMR margin over MemGPT (94.8 vs 93.4) is on a near-saturated benchmark; LongMemEval gains (up to +18.5%, ~90% latency reduction) are more meaningful but not independently replicated as of this writing (uncertain). Architecturally, Graphiti is the most complete answer to the incremental-update problem (below), at the price of per-ingestion LLM extraction + entity-resolution cost and dependence on extraction correctness for edge invalidation.

## Query interfaces: text-to-Cypher vs embedding-graph hybrids

Two ways to *ask* a graph: (1) translate NL → formal graph query (Cypher/SPARQL/Gremlin); (2) embed-then-traverse (vector similarity to find entry nodes, then structural expansion — the GraphRAG/HippoRAG/LightRAG pattern). Evidence: **Text2Cypher** (Ozsoy et al., arXiv:2412.10064, Neo4j) shows off-the-shelf LLMs "often struggle to capture complex nuances, resulting in incomplete or incorrect outputs" and that fine-tuning on a curated 44,387-instance dataset substantially improves BLEU/exact-match — i.e., reliable NL→Cypher still requires task-specific training and a *stable schema*, which LLM-extracted graphs don't have. Consequence, visible across the ecosystem: text-to-Cypher dominates when the graph is a governed enterprise/database asset with a fixed ontology; embedding-entry + traversal dominates over LLM-extracted document graphs; production systems (Graphiti, KAG, Neo4j's own guidance) are hybrids — vector/BM25 entry, structured expansion, optional formal queries for aggregations that embeddings fundamentally cannot do (counts, joins, time filters). KAG's logical-form layer is the most developed middle path: decompose NL into a plan whose steps dispatch to graph ops, retrieval, or calculation.

## The KG-quality problem

The load-bearing weakness of the entire document-graph paradigm: the graph is only as good as LLM extraction, and extraction is noisy.

- **Incompleteness:** Han et al. (2502.11371) measured that only ~65.5% of answer entities appeared in the constructed KG at all — a hard ceiling on triple-only retrieval, and the empirical reason every surviving system (HippoRAG 2, KAG, LightRAG hybrid mode) retains raw text.
- **Extraction noise & duplication:** OpenIE-style prompts yield malformed, redundant, and hallucinated triples; the same real-world entity fragments into multiple nodes ("Sagar S" / "Sagar Shankaran" / "S Shankaran" — the "entity drift" example circulating in practitioner writeups). Entity resolution is typically a heuristic LLM/string-similarity dedup pass with no correctness guarantees; errors are *structural* — a bad merge or missed merge silently corrupts every downstream traversal, unlike a bad chunk which affects one retrieval.
- **Model-strength sensitivity:** Han et al. found GraphRAG quality strongly depends on the extraction LLM (GPT-4o ≫ GPT-4o-mini) — graph quality is a hidden hyperparameter that makes cross-paper comparison unreliable.
- **Responses:** schema constraints (KAG), schema induction (AutoSchemaKG), non-LLM extraction (LazyGraphRAG's noun phrases; GraphMERT, arXiv:2510.09580, distilling "reliable" KGs with efficient encoders), extraction-then-filter (HippoRAG 2's triple filtering). None is a solved answer; there is still no standard benchmark for *KG-construction fidelity* independent of end-task QA (GraphRAG-Bench's pipeline-stage evaluation is the closest attempt).

## The incremental-update problem

Full GraphRAG's index is a *global* artifact: Leiden communities and their summaries depend on the whole graph, so document arrival/edit/deletion invalidates clustering and summaries; recomputation is the default (Microsoft has shipped update tooling, but merge quality vs full re-index is not independently characterized — uncertain). Responses across the ecosystem: LightRAG and nano-graphrag advertise incremental insertion (union-merge of new entities/edges — cheap but compounds duplication/drift over time, since no re-resolution occurs); fast-graphrag claims real-time incremental updates; LazyGraphRAG shrinks the problem by making the index cheap to rebuild; Graphiti is the only design that treats updates as first-class *semantics* (temporal invalidation, not just appending). Deletion/retraction (compliance, corrected facts) remains essentially unaddressed outside Graphiti-style invalidation. For agentic-memory use cases, this problem — not retrieval accuracy — is the binding constraint.

## Comparative evidence: do graphs actually win?

The four most credible independent evaluations:

1. **Han et al., arXiv:2502.11371 (MSU/Meta-affiliated per press coverage; v3 2026).** Unified protocol (same chunking/embeddings/generator). Single-hop NQ: RAG 64.78 F1 vs best graph method 63.01. MultiHop-RAG: community-local GraphRAG 69.01 vs RAG 67.02 overall accuracy (press coverage quotes slightly different numbers, 70.3/67.0 — version discrepancy; both directions agree). Efficiency: index construction 135s (RAG) vs 5,560–7,702s (GraphRAG variants); KG-GraphRAG also had the *highest retrieval latency* (14,434s vs 1,724s aggregate). Summarization verdicts flipped with answer order (LLM-judge position bias). Conclusion: no single winner; combine.
2. **GraphRAG-Bench / "When to use Graphs in RAG", arXiv:2506.05690 (ICLR 2026).** Four difficulty tiers (fact retrieval → complex reasoning → contextual summarization → creative generation), pipeline-stage evaluation, two domains. Headline: graphs pay off on reasoning-heavy tiers; on fact retrieval they frequently *underperform* vanilla RAG; gains depend on construction quality and retrieval design more than on "having a graph."
3. **Zeng et al., arXiv:2506.06331.** Audit of GraphRAG evaluation practice: corpus-derived synthetic questions favor graph methods; LLM-judge position bias shifts win rates >30 points; with grounded questions + debiased judging, "performance gains are much more moderate than reported previously."
4. **RAGSearch / "Do We Still Need GraphRAG?", arXiv:2604.09666 (2026).** Under single-shot inference GraphRAG dominates multi-hop QA (avg +27.23 over dense RAG); under agentic (especially RL-trained) multi-round search the gap mostly closes; GraphRAG retains an edge in multi-hop accuracy and agent stability *iff* offline cost is amortized over enough queries.

Supporting: "Is GraphRAG Needed?" (2606.25656) adds the retrieval–generation gap (retrieval-metric wins overstate end-quality wins) and shows context engineering (19–53% token cuts) is often the cheaper lever.

**Synthesis.** Graphs win, with independent evidence, on: (a) multi-hop/relational QA over dispersed evidence (roughly +2 to +27 points depending on setup and inference regime); (b) corpus-level sensemaking/summarization *on diversity/comprehensiveness axes* (with judge-bias caveats); (c) KGQA over curated graphs (large, clean wins); (d) temporally evolving agent memory (architecturally, vendor-evidenced). Graphs lose or tie-at-higher-cost on: single-hop and detail-centric QA, general QA under agentic search, freshness-sensitive corpora, and any deployment whose query volume can't amortize 40–60× index-construction overhead.

---

## Comparison tables

### Systems

| System | Structure | Index-time LLM? | Retrieval mechanism | Incremental updates | Strongest evidence | Key weakness |
|---|---|---|---|---|---|---|
| MS GraphRAG (2404.16130) | Entity graph + Leiden community hierarchy + summaries | Heavy | Global map-reduce / local expansion / DRIFT | Poor (global clustering) | Global sensemaking (vendor, judge-based) | Cost; detail loss; stale communities |
| LazyGraphRAG (MS blog) | Noun-phrase co-occurrence graph | None | Query-time iterative deepening, budgeted | Good (cheap rebuild) | Beats GraphRAG at ~4% query cost (vendor) | Vendor-only eval; concept graph shallower than KG |
| HippoRAG 1/2 (2405.14831, 2502.14802) | OpenIE triples (+passage nodes in v2) | Moderate | PPR from query seeds | Append-friendly | Independent multi-hop wins; replicated | Extraction noise propagates through PPR |
| LightRAG (2410.05779) | Lightweight entity/relation graph, dual-level keys | Moderate | Entity + theme keyed lookup | Insertion supported, no re-resolution | Cheap; huge adoption | Win-rate eval methodology audited as inflated |
| PathRAG (2502.14902) | Same class as LightRAG | Moderate | Flow-based path pruning | Similar to LightRAG | Redundancy reduction | Incremental preprint evidence |
| MiniRAG (2501.06713) | Chunk+entity heterogeneous graph | Light (SLM-capable) | Topology-enhanced, SLM-friendly | Insertion | SLM deployments, 25% storage | Author-reported only |
| KAG (2409.13731) | Schema-constrained KG + mutual chunk index | Heavy + human schema | Logical-form planning over 4 operators | Schema-managed | Big multi-hop gains (vendor); production use | Ontology cost; few independent replications |
| StructRAG (2410.08815) | Task-chosen structure at inference | None (index) | Structurize-then-reason | N/A (query-time) | Knowledge-intensive reasoning SOTA (author) | Per-query structurization latency |
| HyperGraphRAG (2503.21322) | Hypergraph (n-ary facts) | Heavy | Hyperedge retrieval | Unclear | NeurIPS'25 accept; n-ary expressiveness | Extraction noise, early days |
| GNN-RAG (2405.20139) / G-Retriever (2402.07630) | Pre-existing curated KG / textual graph | None (train GNN) | GNN scoring + paths / PCST subgraph | N/A (given graph) | Strong independent KGQA wins | Requires clean graph + training |
| Zep/Graphiti (2501.13956) | Bi-temporal episodic KG | Per-ingestion | Hybrid semantic+BM25+traversal | First-class (edge invalidation) | LongMemEval gains (vendor) | Vendor eval; per-update LLM cost |
| nano-/fast-graphrag (GitHub) | GraphRAG-lite / PPR graph | Moderate | Top-K communities / PPR | Insertion / real-time (claimed) | Ecosystem adoption | Community projects, informal evals |

### When does structure pay? (evidence-weighted)

| Task regime | Verdict | Basis |
|---|---|---|
| Single-hop factual QA | Vector RAG ≥ graph (and ~40–60× cheaper to index) | 2502.11371, 2506.05690 |
| Multi-hop QA, single-shot inference | Graph wins clearly (up to ~+27 avg) | 2604.09666, 2502.11371 |
| Multi-hop QA, agentic multi-round | Gap mostly closes; graph = stability + residual edge | 2604.09666 |
| Corpus-level sensemaking/summarization | Graph/community methods win on comprehensiveness/diversity — but judge-bias caveats apply | 2404.16130, 2506.06331 |
| KGQA over curated KGs | Learned graph retrieval wins decisively | 2405.20139, 2402.07630 |
| Evolving agent memory | Temporal graph architecturally justified; independent evidence thin | 2501.13956 |
| Detail-centric / null-query robustness | Vector RAG; global graph search hallucinates on nulls | 2502.11371 |

---

## Failure modes & critiques

1. **Garbage graph in, garbage reasoning out.** LLM extraction misses ~a third of answer entities (65.5% coverage, 2502.11371), duplicates entities (entity drift), and hallucinates relations. All traversal-based gains sit on this foundation; errors are structural and silent.
2. **Evaluation inflation.** The field's headline wins were built on LLM-judge win rates over corpus-derived synthetic questions — audited to show >30-point position-bias swings and "much more moderate" real gains (2506.06331; corroborated by 2502.11371's order-reversal experiment and GraphRAG-Bench). Vendor evaluations (Microsoft, Ant, Zep, circlemind) dominate the marketing narrative; independent replications consistently shrink the gaps.
3. **Cost asymmetry.** Index construction is 40–60× slower/costlier than vector RAG (2502.11371 timings; $20–48/1M-token practitioner figures); KG-based retrieval can also be *slower at query time* (14,434s vs 1,724s aggregate latency in 2502.11371). Amortization requires high query volume on a stable corpus — the opposite of most agentic workloads.
4. **Detail loss and null-query hallucination in community/global search.** Summaries compress away specifics; global search confidently answers unanswerable queries (2502.11371).
5. **Redundancy, not recall, limits generation.** PathRAG's diagnosis plus the retrieval–generation gap (2606.25656): piling retrieved structure into context does not proportionally improve answers.
6. **Staleness and the update tax.** Global structures (communities, summaries, PPR statistics) resist incremental maintenance; insertion-only updates accumulate entity-resolution debt; deletion/correction is unsolved outside temporal invalidation (Graphiti).
7. **Binary-triple expressiveness ceiling.** Real facts are n-ary, conditional, and temporal; triples flatten them (HyperGraphRAG's motivation; Zep's motivation). Most deployed graph RAG cannot represent "X was true of Y between t1 and t2 under condition Z."
8. **Schema dilemma.** Schema-free extraction is noisy (KAG's critique of OpenIE); schema-constrained construction is expensive and domain-locked; automatic schema induction (AutoSchemaKG) is promising but young.
9. **Agentic search substitution.** The 2026 result: inference-time multi-round retrieval over a plain index buys most of what the graph bought (2604.09666) — offline structure now competes against test-time compute on price and freshness, not just against vector top-k.
10. **Hidden hyperparameter: extraction-model strength.** GPT-4o-vs-mini gaps in graph quality (2502.11371) mean published numbers don't transfer across model choices or corpora; text-to-Cypher similarly fails without fine-tuning and stable schemas (2412.10064).

## Open problems

These are the first-principles gaps a next-generation framework should target:

1. **Construction-fidelity measurement.** No accepted benchmark scores a *graph* (entity coverage, resolution correctness, relation precision, n-ary/temporal fidelity) independently of end-task QA. Design metric: answer-entity coverage (cf. the 65.5% finding) generalized to relation-path coverage, with error-propagation analysis from graph defects to answer defects.
2. **Late-binding structure.** LazyGraphRAG and StructRAG both suggest the right principle: commit to expensive structure at *query time*, conditioned on the query, under an explicit budget. Open: a principled controller (not heuristics) that chooses among {no structure, concept graph, KG traversal, formal query, agentic search} per query — early routing work (GraphRAG-Router, 2604.16401) is RL-over-variants, not budgeted structure synthesis.
3. **Entity resolution as a first-class, revisable operation.** Current pipelines resolve once, at ingestion, irreversibly. Needed: probabilistic/reversible merges whose downstream retrieval effects can be audited and rolled back as evidence accumulates — nothing in the surveyed literature does this.
4. **Incremental global structure.** Communities, summaries, and PPR statistics that update in sublinear time with bounded quality loss versus full recomputation — including *deletion* and *retraction*, which only Graphiti-style temporal invalidation addresses, and only for facts it correctly extracts.
5. **Temporal-by-default representation.** Bi-temporal validity should be a property of the base representation, not a vendor add-on; open questions include cheap conflict detection at scale and querying counterfactual/past states without a formal query language.
6. **Structure vs test-time compute exchange rate.** RAGSearch establishes the phenomenon; nobody has a predictive model of *when* (corpus size, hop depth, query volume, freshness rate) offline graph cost beats inference-time agentic search cost. A framework should expose this as an explicit, measurable trade-off.
7. **Beyond binary triples without new noise.** N-ary/event/hypergraph extraction inherits and amplifies triple-extraction noise; schema induction at scale (AutoSchemaKG) needs independent stress-testing. Open: representations expressive enough for conditions and time yet robust to extractor error.
8. **Debiased, ecologically valid evaluation.** Standardize graph-grounded question generation with contamination controls, order-randomized judging, null-query robustness, and *joint* cost-quality reporting (index $ + query $ + latency + update $) — BenchmarkQED, GraphRAG-Bench, and the Zeng audit each cover a slice; no benchmark covers the whole surface, and none prices the update/staleness axis at all.

## Bibliography

Peer-reviewed / venue-accepted:

- GraphRAG: "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" — Edge et al. — arXiv:2404.16130 — 2024 (v2 2025). https://arxiv.org/abs/2404.16130
- HippoRAG — Gutiérrez et al. — arXiv:2405.14831 — NeurIPS 2024. https://arxiv.org/abs/2405.14831
- HippoRAG 2: "From RAG to Memory: Non-Parametric Continual Learning for LLMs" — arXiv:2502.14802 — 2025 (OpenReview: LWH8yn4HS2). https://arxiv.org/abs/2502.14802
- GNN-RAG — Mavromatis & Karypis — arXiv:2405.20139 — ACL 2025 Findings. https://arxiv.org/abs/2405.20139
- G-Retriever — He et al. — arXiv:2402.07630 — 2024 (NeurIPS 2024 per common citation; uncertain from abstract page alone). https://arxiv.org/abs/2402.07630
- LightRAG — HKUDS — arXiv:2410.05779 — EMNLP 2025 Findings. https://arxiv.org/abs/2410.05779 ; https://github.com/hkuds/lightrag
- KAG — Ant Group/OpenSPG — arXiv:2409.13731 — WWW 2025 Companion. https://arxiv.org/abs/2409.13731 ; https://github.com/OpenSPG/openspg
- HyperGraphRAG — Luo et al. — arXiv:2503.21322 — NeurIPS 2025. https://arxiv.org/abs/2503.21322
- GraphRAG-Bench: "When to use Graphs in RAG" — Xiang et al. — arXiv:2506.05690 — ICLR 2026. https://arxiv.org/abs/2506.05690 ; https://github.com/GraphRAG-Bench/GraphRAG-Benchmark
- "Is GraphRAG Needed? From Basic RAG to Graph-/Agentic Solutions with Context Optimization" — Chen et al. — arXiv:2606.25656 — ACL 2026 GEM Workshop. https://arxiv.org/abs/2606.25656

Preprints (arXiv):

- "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights" — Han et al. — arXiv:2502.11371 — 2025 (v3 2026). https://arxiv.org/abs/2502.11371
- "Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems" (RAGSearch) — Fan et al. — arXiv:2604.09666 — 2026. https://arxiv.org/abs/2604.09666
- "How Significant Are the Real Performance Gains? An Unbiased Evaluation Framework for GraphRAG" — Zeng et al. — arXiv:2506.06331 — 2025. https://arxiv.org/abs/2506.06331
- PathRAG — Chen et al. — arXiv:2502.14902 — 2025 (v2 Nov 2025). https://arxiv.org/abs/2502.14902
- MiniRAG — Fan et al. — arXiv:2501.06713 — 2025. https://arxiv.org/abs/2501.06713
- StructRAG — Li et al. — arXiv:2410.08815 — 2024. https://arxiv.org/abs/2410.08815
- Zep: "A Temporal Knowledge Graph Architecture for Agent Memory" — Rasmussen et al. — arXiv:2501.13956 — 2025 (vendor-authored). https://arxiv.org/abs/2501.13956
- AutoSchemaKG — Bai et al. — arXiv:2505.23628 — 2025. https://arxiv.org/abs/2505.23628
- Text2Cypher — Ozsoy et al. (Neo4j) — arXiv:2412.10064 — 2024. https://arxiv.org/abs/2412.10064
- "Graph Retrieval-Augmented Generation: A Survey" — Peng et al. — arXiv:2408.08921 — 2024. https://arxiv.org/abs/2408.08921
- GraphMERT: "Efficient and Scalable Distillation of Reliable Knowledge Graphs from Unstructured Data" — arXiv:2510.09580 (seen in search results; abstract not fetched). https://arxiv.org/pdf/2510.09580
- Frontier 2026 preprints (title/ID seen in search results, light verification only): "Breaking the Static Graph" arXiv:2602.01965; GraphRAG-Router arXiv:2604.16401; HKVM-RAG arXiv:2606.07218; "Implicit Graph, Explicit Retrieval" arXiv:2601.03417; SAG arXiv:2606.15971; "Learning Efficient and Generalizable Graph Retriever for KGQA" arXiv:2506.09645.
- "A Survey of Agentic GraphRAG" — Chen, Zheng, Zhu — SSRN 6713979 — 2026. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6713979

Vendor/engineering sources (marketing-adjacent; treated as claims, not evidence):

- LazyGraphRAG — Microsoft Research blog. https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- DRIFT search — Microsoft Research blog. https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/
- Dynamic community selection — Microsoft Research blog. https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/
- BenchmarkQED — Microsoft Research blog. https://www.microsoft.com/en-us/research/blog/benchmarkqed-automated-benchmarking-of-rag-systems/
- GraphRAG docs (DRIFT) — https://microsoft.github.io/graphrag/query/drift_search/
- nano-graphrag — https://github.com/gusye1234/nano-graphrag
- fast-graphrag — https://github.com/circlemind-ai/fast-graphrag
- HippoRAG repo — https://github.com/osu-nlp-group/hipporag
- Zep temporal-KG explainer — https://www.getzep.com/ai-agents/temporal-knowledge-graph/
- Awesome-GraphRAG curated list — https://github.com/DEEP-PolyU/Awesome-GraphRAG
- RAGFlow issue #3862 (LazyGraphRAG demand signal) — https://github.com/infiniflow/ragflow/issues/3862

Press/practitioner (secondary; used only for cost anecdotes and framing, flagged in text):

- "Stop graphing everything: When GraphRAG actually beats vector RAG" — VentureBeat (page fetch blocked; content seen via search excerpt). https://venturebeat.com/orchestration/stop-graphing-everything-when-graphrag-actually-beats-vector-rag
- Beancount research log on GraphRAG (cost figures incl. $47.9 GPT-4o practitioner analysis). https://beancount.io/bean-labs/research-logs/2026/06/04/graphrag-local-to-global-query-focused-summarization
- CallSphere blog (entity-drift example) — https://callsphere.ai/blog/vw6g-microsoft-graphrag-knowledge-graph-2026
