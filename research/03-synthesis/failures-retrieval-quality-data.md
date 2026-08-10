# Retrieval-Quality & Data-Processing Failures — Cross-Framework Synthesis

*Synthesis date: 2026-08-05. Dimension: `retrieval-quality` + `data-processing` across the 19-file framework-autopsy corpus (`research/02-frameworks/`), read against the research landscape (`research/01-landscape/`: document-processing-chunking, embeddings-representation, retrieval-reranking-fusion, query-understanding-transformation, multilingual-crosslingual) and `cross-cutting-gaps.md`.*

---

## Method note

Every framework file's `retrieval-quality` and `data-processing` sections were read in full, plus surrounding architecture/defaults sections where the taxonomy label under-captures the finding (several files tag chunking-immutability or sync corruption under `production-ops`; where a failure corrupts *what the retriever returns*, it is claimed for this dimension). An issue is admitted as "common" only with evidence in **≥3 independent frameworks/platforms**, with documented-recurring evidence (GitHub issues, vendor docs, release notes, CVE/incident records) as the spine. Single-anecdote and architectural-inference items are used only as supporting color and are labeled.

Blacklisted claims from the corpus audit are excluded: no use of langchain-langgraph.md's SEO-farm quantifications, lowcode-builders.md's "10x from markdown chunking" figure or NVD keyword CVE counts, ragflow.md's third-party corroboration layer (kdjingpai/scored.tools/sider/aixyz/Tekai), vectordb-and-startup-platforms.md's Pinecone platform-risk claim or its "no independent replication found" negatives, or microsoft-graphrag.md's "$33,000 to index 5GB" figure. multilingual-crosslingual.md's production-practice claims are treated as flagged-uncertain; only its benchmark/paper findings are relied on. GitHub issue numbers, vendor primary docs, official incident postmortems, and arXiv IDs are treated as valid evidence.

One honest scoping note: "no built-in retrieval evaluation loop" recurs in nearly every file but is taxonomized under `evaluation-observability` and belongs to that dimension's synthesis. It appears here only as the *root-cause amplifier* it is — the reason none of the failures below generates corrective pressure.

---

## The common issues

Overview (frameworks counted only where the file supplies concrete evidence, not merely a plausible inference):

| # | Issue | Independent frameworks/platforms with evidence | Dominant evidence grade |
|---|---|---|---|
| 1 | Frozen demo-grade retrieval defaults | 12 (LlamaIndex, LangChain, Dify, n8n, AnythingLLM, CrewAI/ADK/AutoGen cohort, Bedrock, Databricks, RAGFlow, LightRAG, DSPy, GPT4All/LM Studio cohort) | documented-recurring |
| 2 | Structure-destroying ingestion / parsing ceiling | 13 (LangChain, Haystack, OpenAI, GraphRAG, Dify, Spring AI, Vercel AI SDK, NVIDIA/Docling, RAGFlow, Bedrock, Databricks/Snowflake, research toolkits, DSPy) | documented-recurring |
| 3 | Ingest-time one-way doors | 8 (Bedrock, Gemini File Search, Dify, Databricks, Snowflake, LightRAG, OpenAI, low-code cohort) + ecosystem-wide embedding-sunset evidence | documented-recurring |
| 4 | Silent retrieval corruption via leaky abstractions | 11 (Haystack, LangChain, Spring AI, LangChain4j, LlamaIndex, Bedrock, Dify, OpenAI, Azure, Qdrant/Chroma, RAGFlow) | documented-recurring |
| 5 | Mutating-corpus breakage | 10 (Flowise, Dify, LlamaIndex, GraphRAG, Azure, OpenAI, LightRAG, Khoj, Bedrock, LangChain) | documented-recurring |
| 6 | Unbudgeted LLM-in-the-loop enrichment noise | 5 (GraphRAG, LightRAG family, RAGFlow, Mem0, Bedrock GraphRAG) | documented-recurring + one forensic anecdote |
| 7 | English-centric retrieval stacks | 7 (Mem0, IBM watsonx, GraphRAG, Qdrant, LightRAG, LlamaIndex.TS, Khoj) + ecosystem analyzer evidence | documented-recurring |

### 1. Frozen demo-grade retrieval defaults (`no-eval-frozen-defaults`)

**Definition.** Frameworks ship out-of-box retrieval configurations — low top-k, similarity-only search, no reranker, hard-coded thresholds and fusion constants — that were plausible in the GPT-3.5 era and have never been revisited, so the default user gets measurably degraded recall with no signal that a better configuration exists.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| LlamaIndex | `llamaindex.md` R1: `DEFAULT_SIMILARITY_TOP_K = 2`, `DEFAULT_CONTEXT_WINDOW = 3900` verified in `constants.py` in 2026; support threads (#13856, #14491, #15075) routinely answered "raise top_k, add a reranker" — the defaults are not the recommended config | documented-recurring |
| LangChain | `langchain-langgraph.md` R2: `as_retriever()` k=4 similarity-only, character chunking, rerank opt-in; Chroma's controlled study measured up to ~9% recall spread across its splitters and had to patch the default separators; docs#4722 concedes no tuning guidance exists | documented-recurring |
| Dify (low-code) | `lowcode-builders.md`: documented defaults TopK=3, score threshold 0.5, rerank **disabled**; hybrid opt-in — recall-hostile defaults aimed at exactly the non-technical users who cannot diagnose them | documented-recurring |
| n8n (low-code) | `lowcode-builders.md`: default splitter falls back to paragraph/newline splitting; structure-aware splitting off by default and hidden; in-memory dev-only vector store is the frictionless default | documented-recurring |
| AnythingLLM | `oss-rag-platforms.md` R1: fixed chunking → cosine top-4–6 → threshold; hybrid search still an open feature request (#4338); its own docs concede "no guarantee that relevant text stays together" | documented-recurring |
| CrewAI / ADK / AutoGen | `agent-framework-retrieval.md` R1: CrewAI top-3 at 0.35 threshold with `text-embedding-3-small` hardcoded; ADK default memory is keyword matching; AutoGen 0.2 chunked at `0.4 × max_tokens` line-based | documented-recurring |
| Bedrock KB | `managed-aws-google.md`: semantic-only search default; ~300-token fixed chunks; `HYBRID` must be requested (and silently degrades — see issue 4); community playbook is "never trust defaults" | documented-recurring |
| Databricks Vector Search | `datacloud-rag.md` RQ-1: hybrid fusion hard-coded to RRF k=60, no built-in reranker, docs steer users *away* from hybrid on cost grounds | architectural-inference (documented constants) |
| RAGFlow | `ragflow.md`: built-in ONNX rerankers *removed* in v0.18 ("minimal impact versus performance costs"); static 0.7 keyword / 0.3 vector weights, threshold 0.2; retrieval-test tunings silently don't persist to assistants | documented-recurring |
| LightRAG | `hkuds-lightrag-family.md` P5: default storage stack is JSON/NetworkX/NanoVectorDB, README concedes not for production; rerank and citations off by default | documented (README) |
| DSPy | `dspy.md` RQ-3: no hybrid, no reranker, no retrieval defaults at all — ironic given the lab invented ColBERT | architectural-inference |
| GPT4All / LM Studio | `memory-and-localfirst.md` I8: undocumented naive retrieval; official advice is to guess the retriever's vocabulary in your query | documented-recurring |

The counter-witness matters: the managed platforms (`managed-openai-azure.md`, `datacloud-rag.md`) show good defaults are feasible — OpenAI file_search ships hybrid + query rewriting + a trained reranker by default; Azure's hybrid + semantic ranker scored highest of the hosted services in the independent retrievalci benchmark (recall 90.9%); Snowflake Cortex ships reranked hybrid by default and reports large internal NDCG lifts from it. Best-practice defaults exist in production; the OSS framework layer simply doesn't ship them.

**Root cause.** Defaults are set once, at framework birth (2022–23), by the constraints of the demo: fast, cheap, zero extra dependencies, works on a laptop. Three forces then freeze them. (i) *No feedback pressure*: with no in-framework eval loop, a bad default produces no measurable regression signal, only diffuse "my answers are wrong" issues that are closed with tuning advice. (ii) *Breaking-change economics*: changing a default is a breaking change nobody can justify without a benchmark the framework doesn't have. (iii) *Competitive incentives*: frameworks compete on integration count and time-to-first-answer, not measured relevance — and stronger defaults (reranker models, hybrid indexes) cost latency, money, and dependency weight in the demo. Rerankers being *removed* (RAGFlow v0.18) for performance cost is the incentive gradient stated openly.

**Research context.** The research side has settled what the default should be: the production-standard pipeline in `retrieval-reranking-fusion.md` is a cascade (hybrid first stage → cross-encoder rerank → pruning → position-aware ordering), and the toolkit harnesses (`research-toolkits.md`: FlashRAG, BERGEN) independently found the retriever/reranker choice dominates end-task quality (swapping BM25→E5 ≈ +10% end-task; "reranking largely boosts results") while prompt-level exotica mostly doesn't. Retrieval depth is known to be non-monotonic with optima around k∈[3,10] *with* reranking — top-k=2 similarity-only sits below the useful frontier. This is a **non-adoption gap, not a research gap**: the knowledge is a decade of IR practice plus three 2024 harness papers, and no mainstream framework operationalizes it as its default.

**Next-gen requirement.** Ship dated, versioned, benchmark-backed *retrieval profiles* (e.g. `profile="2026-hybrid-rerank"`) instead of scattered constants; the out-of-box profile must include hybrid retrieval + reranking, and every release must publish regression numbers for the default profile on a public corpus. **Test:** run the framework's own bundled eval harness with zero configuration; it must report recall/nDCG for the active default profile, and the profile identifier (with date) must appear in the run metadata.

---

### 2. Structure-destroying ingestion; parsing fidelity as the unacknowledged ceiling (`structure-destroying-ingestion`)

**Definition.** Frameworks flatten documents into untyped strings before chunking — losing tables, headings, reading order, cross-page structure, and provenance — while treating parsing as out of scope or as a utility, even though parsing fidelity is the empirically dominant determinant of end-to-end RAG quality.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| LangChain | `langchain-langgraph.md` D1: `Document = string + dict` erases tables/layout/hierarchy; splitter bugs (#30200 overlap not applied, #9305, #10410) | documented-recurring |
| Haystack | `haystack.md`: splitter-zoo cluster — code splits lose function identity (#11874), DOCX drops hyperlinks (#9104), chunk positions lost after cleaning (#8761); default `DocumentCleaner()` destroys the delimiters `split_by="passage"` needs (#8491, 22 comments); complex-PDF parsing delegated out of core (#12094) | documented-recurring |
| OpenAI file_search | `managed-openai-azure.md`: fixed token-window chunking only; docs admit no parsing of images/charts/tables inside documents; practitioners report answers split across page breaks so "neither chunk contain[ed] enough context" | documented-recurring |
| Microsoft GraphRAG | `microsoft-graphrag.md`: plain-text-in only — all structure flattened *before* the "structured" pipeline starts; token chunking with docs conceding fidelity loss | documented + architectural-inference |
| Dify | `lowcode-builders.md`: #31510 — character splitting strips section headers so queries fail against content under those headers; **closed as not planned**; discussion #29635 code blocks/nested lists split mid-structure | documented-recurring |
| Spring AI | `jvm-js-ecosystems.md` D1: the near-only chunker `TokenTextSplitter` had no overlap support (#2123, open since 2024), reassigns doc IDs breaking provenance (#1167) | documented-recurring |
| Vercel AI SDK | `jvm-js-ecosystems.md` A4: official RAG guide implements chunking as splitting on periods | documented |
| NVIDIA / IBM Docling | `gpu-vendor-enterprise-rag.md` R3/D1–D3: cross-page info not retrievable (blueprint #240); Docling heading-hierarchy collapse (#1023) and ToC/hierarchy identification open ~21 months (#287); NVIDIA's own README sample output renders its test table as one-word-per-cell garble | documented-recurring |
| RAGFlow | `ragflow.md`: v0.21 ToC extraction shipped explicitly to fix "context loss caused by inaccurate or excessive chunking" (release notes — self-acknowledged); template chunking brittle off the happy path; launch-era critique of inconsistent multi-parser defaults (HN 39896923) | documented-recurring |
| Bedrock KB | `managed-aws-google.md`: ~300-token default chunks "can split a table, a list, or a tightly-coupled argument down the middle"; CSV corpora retrieve poorly out of the box (SO 79591405) | documented-recurring |
| Databricks / Snowflake | `datacloud-rag.md` AD-1: parsing and chunking are entirely DIY outside the managed abstraction — the platform manages embed→index→serve and leaves the highest-leverage stage to the user, while marketing "no pipeline" | documented-recurring |
| Research toolkits | `research-toolkits.md`: FlashRAG/BERGEN ingest pre-chunked JSONL / hard-code 100-word chunks; none evaluates parsing at all | architectural-inference |
| DSPy | `dspy.md` DP-1: no ingestion/parsing/chunking layer; official RAG tutorial truncates documents at 6,000 chars | documented (official docs) |

**Root cause.** Three compounding mechanisms. (i) *The document model was chosen for demos*: `str + metadata dict` is the minimal type that makes a loader ecosystem cheap to grow; once hundreds of loaders emit it, structure cannot be retrofitted without breaking them all — the abstraction is load-bearing debt. (ii) *Open-core gravity*: parsing quality is the layer that monetizes — LlamaParse ("the OSS parsers are comparatively basic — an intentional open-core seam", `llamaindex.md` D2), RAGFlow's DeepDoc-in-product, GroundX/Vectara/Ragie closed extraction, AWS "Smart Parsing" in the paid Managed KB tier. The economic optimum for vendors is a naive OSS ingest layer plus a paid fix. (iii) *Invisible failure*: parsing errors silently poison the index — no mainstream stack emits per-span extraction confidence or a quarantine path (`gpu-vendor-enterprise-rag.md` D3), so degraded fidelity surfaces only as unattributable bad answers.

**Research context.** This is the strongest research-says/frameworks-ignore mismatch in the corpus. OHR-Bench (ICCV 2025, arXiv:2412.02592) shows **no current OCR/parsing solution is adequate for RAG knowledge bases** — even the best loses ~14% F1 end-to-end vs ground-truth text, more than the entire measured spread between chunking strategies (~9%, Chroma). arXiv:2605.00911 shows character-level OCR accuracy does not predict RAG outcomes: *structural* errors (merged columns, lost headers, broken reading order) are what kill retrieval — exactly the errors framework document models cannot even represent. Where structure is preserved, it pays: cAST (EMNLP 2025) shows grammar-aware chunking wins for code; element-typed models (Unstructured) and structure-native retrieval (RDR2, PageIndex) exist. The landscape verdict: "the frontier has moved upstream of the chunker" — while the framework layer still ships period-splitting tutorials. Meanwhile chunking research itself over-claims because it never touches real PDFs (`document-processing-chunking.md` failure 1) — the two layers systematically miss each other.

**Next-gen requirement.** A typed, structural document model (elements/trees with section paths, table structure, page coordinates, reading order, and per-span parser confidence) that survives from parser through chunker to retrieved result. **Test:** for a golden PDF set with tables and multi-page sections, (a) every retrieved chunk can be traced to page + bounding region; (b) a table row retrieved carries its header context; (c) parser confidence below threshold routes the document to a quarantine/re-parse path rather than silently indexing.

---

### 3. Ingest-time decisions are one-way doors (`ingest-one-way-doors`)

**Definition.** Chunking strategy, embedding model, and index configuration are irreversibly baked in at ingestion, so the highest-leverage quality knobs cannot be tuned after content exists without a full re-ingest/re-embed — making experimentation economically punitive and locking corpora to stale configurations.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| Bedrock KB | `managed-aws-google.md`: chunking strategy **immutable after KB creation**; changing it means recreating and re-syncing the KB (vendor docs + practitioner analysis) | documented-recurring |
| Gemini File Search | `managed-aws-google.md`: documents immutable once indexed — update = delete + re-upload; chunking config applies only at upload | documented-recurring |
| Dify | `lowcode-builders.md`: index mode (High-Quality vs Economical) "cannot switch" after KB creation; external-KB binding fixed at creation | documented-recurring |
| Databricks / Snowflake | `datacloud-rag.md` AD-2/PC-2: self-managed→managed index conversion impossible; source schema change requires index rebuild; `CREATE OR REPLACE` on a source table silently triggers **full re-embedding of the entire corpus** (Snowflake's own cost docs) | documented-recurring |
| LightRAG | `hkuds-lightrag-family.md`: changing the embedding model requires manually dropping vector tables and re-embedding (README) | documented |
| OpenAI vector stores | `managed-openai-azure.md`: embedder fixed (text-embedding-3-large @256d), not replaceable, embeddings not exportable — the corpus is welded to one model version | documented-recurring |
| All four low-code builders | `lowcode-builders.md`: switching embedding model silently invalidates the whole index; no incremental/versioned re-embedding path anywhere | documented-recurring |
| Ecosystem-wide | `cross-cutting-gaps.md` (d): vendor embedding sunsets (OpenAI 16-model shutdown 2024-01-04; Cohere v2 retirement 2026-04-04; Azure 18-month non-negotiable clock ending in `410 Gone`) force full re-embeds; **no mainstream framework versions embeddings** or supports rolling re-embed with dual-read cutover; three independent community tools exist purely to route around this | documented-recurring |

**Root cause.** The index is treated as the *primary artifact* rather than a derived view of a canonical parsed corpus. Embedding at write time welds three decisions (boundary placement, representation, storage layout) into one object; nothing retains the pre-chunk canonical form needed to re-derive it. Vendors have no incentive to fix this: re-embedding is billable (per-token embedding charges), immutability simplifies serving infrastructure, and lock-in is strategy (unexportable embeddings are explicitly a moat in the managed platforms). For OSS frameworks, it is a missing abstraction rather than malice — but the effect is identical: the field's most repeated tuning advice ("try different chunk sizes") is dispensed by systems in which trying is a full rebuild.

**Research context.** The landscape names this directly. `document-processing-chunking.md` failure 7: "index-time granularity commitment is architecturally wrong" — optimal granularity depends on the query (NVIDIA: factoid vs analytical want opposite chunk sizes), motivating late-binding granularity (FreeChunker, Mix-of-Granularity, RSE) where retrieval units are materialized at query time. `embeddings-representation.md` names **re-embedding debt** a first-order framework design constraint and notes incremental/compatible embedding upgrades remain research-grade with no accepted solution — i.e., the versioning half is genuinely unsolved research, but the *canonical-store + derived-view* half is pure engineering that no framework has done. Late chunking (arXiv:2409.04701) even shows boundary decisions can be partially decoupled from representation at near-zero cost — evidence the welding is unnecessary.

**Next-gen requirement.** Store canonical parsed documents as the durable artifact; treat chunking and embedding as re-runnable, versioned derived views, with embedding-model+version tags on every vector and dual-index/dual-read cutover for migrations. **Test:** on a live corpus, (a) change the chunking config and rebuild in place while queries continue serving the old view, with a cost/time estimate emitted up front; (b) migrate embedding model v1→v2 with both versions queryable during cutover and a drift report comparing retrieval overlap before the old index is dropped.

---

### 4. Silent retrieval corruption through leaky backend abstractions (`silent-retrieval-corruption`)

**Definition.** The "one interface, N vector stores" abstraction ships per-backend reimplementations of filters, score semantics, and hybrid capability that fail *silently* — returning wrong, partial, or unfiltered results that look like valid retrievals — so correctness (and tenant isolation) erodes with no error raised.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| Haystack | `haystack.md`: filter-DSL cluster — timestamp-format equality misses (#11962, #11583, #12246), `FilterPolicy.MERGE` **silently drops init filters** (#12065), typo'd operators raise cryptic KeyError (#11794); deepset itself proposed a FilterBuilder because filters are hard to write correctly | documented-recurring |
| LangChain | `langchain-langgraph.md` A2: `similarity_search_with_relevance_scores` returns raw distances instead of normalized scores per-backend (#38506, #38504 open), `NotImplementedError` on others (#12843), wrong `score_threshold` under MAX_INNER_PRODUCT (#32057) — thresholds break exactly where tuning needs them | documented-recurring |
| Spring AI | `jvm-js-ecosystems.md` A1: PgVector filter emitted **without parentheses** so `(a OR b) AND c` becomes `a || b && c` (#3577, 34 comments); wrong SQL for IN/NOT IN (#1179); typed `Filter.Expression` ignored (#3179) | documented-recurring |
| LangChain4j | `jvm-js-ecosystems.md` R1: `.isNotIn` on PgVector generated SQL that **matched all content** — tenant-isolation filters silently disabled (#2513); per-store filter support rolled out over years | documented-recurring |
| LlamaIndex | `llamaindex.md`: Azure AI Search OData filter not filtering chunks (#19370, open, 33 comments); advanced retrievers silently no-op when the docstore precondition isn't met with external vector stores (#14239, #8511) | documented-recurring |
| Bedrock KB | `managed-aws-google.md`: `HYBRID` **silently falls back to semantic-only** on unsupported stores; Mongo metadata filtering "doesn't work by default"; missing `keyword` subfields fail with a bare "Rewrite first" error; selective filters silently return too few results without `hnsw.iterative_scan` tuning — all from AWS's own docs | documented-recurring |
| Dify | `lowcode-builders.md`: TopK=10 returns ~5 chunks silently (#32421); knowledge retrieval returns empty for every query across configs (#36260) | documented-recurring |
| OpenAI / Azure | `managed-openai-azure.md`: chunk with the *highest* similarity absent from results until top_k≥45 (community bug 1381267 — single-anecdote but mechanistically damning); Azure docs warn `rerankerScore` distributions drift with infrastructure/model updates, breaking fixed thresholds; reranker sees only top-50 with 2,048-token truncation | documented-recurring + single-anecdote |
| Qdrant / Chroma | `vectordb-and-startup-platforms.md`: replica score comparison silently drops high-scoring points (qdrant #7889); metadata filter breaks over 20M chunks (chroma #4089) | documented-recurring |
| RAGFlow | `ragflow.md`: KG-derived chunks scored by pure cosine while normal chunks use hybrid fusion — two uncalibrated scoring regimes in one result list; retrieval test returns 0 chunks after "successful" parse (#8001) | documented-recurring |

**Root cause.** The uniform-store abstraction is a marketing surface, not a contract: each of 20–80 backend integrations independently reimplements filter translation and score conventions, and **no framework ships a conformance test suite** those integrations must pass — so the same class of bug (filter mistranslation, score-semantics mismatch, capability gaps papered over with fallbacks) is independently rediscovered in Haystack, LangChain, Spring AI, and LangChain4j. The failure shape guarantees longevity: a wrong filter or dropped result still returns a plausible top-k, generation produces a fluent answer, and nothing errors. Filters are simultaneously *correctness* code and *security* code (tenant isolation is implemented as metadata filtering nearly everywhere), yet they are maintained as integration glue.

**Research context.** The research layer diagnoses the deeper half: `retrieval-reranking-fusion.md` failure 3 — "uncalibrated scores everywhere": cross-encoder scores are incomparable across queries, RRF discards magnitudes entirely, so thresholding and abstention "are built on sand"; a probabilistic semantics for retrieval scores is open problem #2. Filtered ANN is a documented structural hazard even inside single engines (Qdrant's own docs: strict filters + soft-deleted points can disconnect the HNSW graph — `cross-cutting-gaps.md` (g)). So research explains *why* scores/filters are fragile, but the conformance-testing discipline that would catch the translation-bug class is not a research problem at all — it is standard database-engineering practice that the ecosystem skipped.

**Next-gen requirement.** One typed, tested filter algebra and score contract with a mandatory cross-backend conformance suite (filter semantics incl. datetimes/booleans/negation, score normalization, capability declaration); unsupported capabilities must fail loudly at plan time, never degrade silently. **Test:** (a) run the conformance suite against every store integration in CI — a backend that mistranslates `(a OR b) AND c` or NOT-IN cannot ship; (b) request hybrid search on a store without it → hard error naming the capability, not a silent semantic-only fallback; (c) golden-corpus filter queries return byte-identical result sets across all supported backends.

---

### 5. The mutating corpus: incremental update and deletion break retrieval correctness (`mutating-corpus-breakage`)

**Definition.** Ingestion is architected as batch-and-forget: document edits, upserts, and deletions leave stale vectors that keep getting retrieved, half-updated derived structures, and orphaned index state — so retrieval correctness silently decays on exactly the living corpora production RAG serves.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| Flowise | `lowcode-builders.md`: Record Manager cleanup=FULL upserts the new vector but **does not delete the old one** — stale content keeps being retrieved (#3570, 29 comments) | documented-recurring |
| Dify | `lowcode-builders.md`: retrieval degrades after adding a file/chunk — "obvious targets don't get hit at all" (#21964) | single-anecdote (supporting) |
| LlamaIndex | `llamaindex.md` P1 (critical): docstore/vector-store split breaks `refresh_ref_docs`/`ref_doc_info` with external vector stores — the default production configuration (#13604, #14057, #13860, #19605 open with 42 comments); node hashing ignored metadata, defeating change detection (#17871) | documented-recurring |
| Microsoft GraphRAG | `microsoft-graphrag.md`: users begged for append from month one (#741, 35 comments); the eventual `update` command shipped half-working — no LanceDB vector files (#1560), GraphML split in two (#1836); deletion explicitly out of scope | documented-recurring |
| Azure AI Search | `managed-openai-azure.md`: deletion detection is opt-in, must be configured **before** the first indexer run, and "neither native blob soft delete nor soft delete via custom metadata applies" to one-to-many (chunked) indexes — precisely the projection every RAG index uses; orphaned chunks require manual REST deletion | documented-recurring |
| OpenAI vector stores | `managed-openai-azure.md` / `agent-framework-retrieval.md` D3: no source sync at all (change = re-upload pipeline you build); docs state removed files may still appear in results "for a short period"; Sept 2025 incident: files added in a ~21h window mis-indexed, degrading retrieval ~6 days, remediation = customers remove and re-add files | documented-recurring (official postmortem) |
| LightRAG | `hkuds-lightrag-family.md` P4: deletion leaves inconsistent KG state (#985); orphan workspace nodes persist in Neo4j after deleting all documents (#2567); "incremental" holds for append, shaky for update/delete | documented-recurring |
| Khoj (personal RAG) | `memory-and-localfirst.md` I8c: three open sync/index-visibility issues (#1363, #1105, #1113) — the user cannot know which notes are indexed; no tombstones, so delete-the-file ≠ forget-the-content | documented-recurring |
| Bedrock KB | `managed-aws-google.md`: syncs stuck >24h with delete-the-KB as workaround; no API to stop a running sync; 30+ min syncs for one new file | documented-recurring |
| LangChain | `langchain-langgraph.md` P1: the Indexing API (the only sync mechanism) is subset-compatible, was SHA-1-based until 2025, and was demoted to `langchain-classic` in 1.0 | documented-recurring |

**Root cause.** Every layer assumes an immutable corpus because every layer was built from an immutable-corpus demo. Chunk boundaries are unstable under edits (one edited paragraph shifts all downstream fixed-size boundaries), derived artifacts (hierarchical summaries, graphs, contextual chunk headers) have O(document)-or-worse invalidation blast radius, and the substrate itself only soft-deletes (`cross-cutting-gaps.md` (c): HNSW deletion has been an open request since 2018; ES tombstones persist until merge; Qdrant documents that accumulated soft-deletes degrade recall). Update correctness is also unownable in split-persistence designs (LlamaIndex's docstore vs vector store) where the two planes drift independently. Nothing surfaces staleness: there is no "index freshness" state a user or agent can query, so decay is discovered through wrong answers.

**Research context.** Genuinely under-researched — this is one of the few issues here that is *not* a solved-elsewhere non-adoption story. `document-processing-chunking.md` flags incremental ingestion as unsupported by design and names **stable-boundary / content-defined chunking** (rsync-style boundaries invariant under local edits) as an obvious, unexplored open problem (#5); near-duplicate/version dedup has no benchmark or standard method (#8). The research corpus evaluates frozen snapshots (BERGEN's wiki-2018; FlashRAG's static JSONL), so the mutating-corpus regime is invisible to the literature's "which technique wins" results. The compliance coupling raises the stakes: deletion debt is simultaneously a GDPR-erasure liability and a recall regression (`cross-cutting-gaps.md` (c)).

**Next-gen requirement.** An incremental-correctness contract: idempotent upsert, verified delete (tombstone propagation checked, not assumed), bounded re-embed blast radius under edits, and per-document freshness state exposed to operators and agents. **Test:** (a) edit one paragraph of a 100-page document → only affected chunks re-embed, and a blast-radius report is emitted; (b) delete a document → zero of its chunks retrievable within a declared SLA, verified by an automated probe query; (c) an upsert-heavy soak test shows no stale-vector retrievals and no monotonic recall decay from tombstone accumulation.

---

### 6. Unbudgeted LLM-in-the-loop enrichment produces noise at scale (`enrichment-noise-unbudgeted`)

**Definition.** Ingest-time LLM enrichment — entity/relation extraction for graphs, memory-fact extraction, auto-keywords/summaries — runs open-loop with no entity resolution, no quality gates, and no compute/token budget, so it multiplies ingestion cost while injecting noise that measurably degrades retrieval below cheaper baselines.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| Microsoft GraphRAG | `microsoft-graphrag.md`: entity merging is exact title+type string match — no fuzzy resolution or coreference; dedup silently drops same-title/different-type entities (#1718, "closed as not planned"); Chinese extraction "very messy" (#596, 30 comments); indexing token burn documented as prohibitive at scale by its own successor (LazyGraphRAG: full indexing ≈1000× a vector index) | documented-recurring |
| LightRAG family | `hkuds-lightrag-family.md` R1–R3 (critical): extraction noise/misses are the dominant quality complaint (#749, #30 with 42 comments, #2339); no entity resolution — same entity under different surface forms becomes multiple nodes (#1323, 33 comments, open); spurious graph edges caused cross-document hallucination *worse than manual vector+rerank* (#3234, 38 comments) | documented-recurring |
| RAGFlow | `ragflow.md`: KG chunking of an 875-page PDF exhausted 32 GB RAM (#4668); entity/relation embedding done one-by-one (#16205); project retreated — GraphRAG/RAPTOR moved from automatic to **manual batch construction** in v0.21, and its own acceleration docs tell users to disable auto-keyword/auto-question enrichment | documented-recurring |
| Mem0 | `memory-and-localfirst.md` I2b/I2c: a 32-day production audit of 10,134 stored memories found 97.8% junk, including a hallucinated fact re-extracted 808 times through a feedback loop (#4573 — single-anecdote but forensically detailed); extraction's structured-output contract breaks on the local models its users run (#3410, #3391, #3918) | single-anecdote (forensic) + documented-recurring |
| Bedrock GraphRAG | `managed-aws-google.md`: Neptune graph auto-built by FM extraction with no graph-build customization, hard file caps, and orphaned-graph billing on delete | documented (vendor docs) |

**Root cause.** Enrichment is adopted on the promise of its papers, whose evaluations (LLM-judged win rates on small corpora) never priced noise or scale; frameworks then wire the extraction prompt directly into ingestion with no intermediate quality layer — because resolution/QA is unglamorous engineering the paper didn't need and the demo doesn't show. The economics invert silently: cost scales with corpus size at ingest (every chunk × extraction × gleaning × summary), while the benefit is concentrated in a narrow query class (multi-hop/global sensemaking — arXiv:2502.11371, arXiv:2503.04338 both find vector RAG competitive or better on ordinary factual QA). Because outputs are unaudited, noise compounds structurally: dirty entities propagate into communities, summaries, and answers (GraphRAG), or feed back into their own extraction (Mem0's 808× loop).

**Research context.** The research trajectory already conceded the point: LazyGraphRAG (MSR, Nov 2024) defers LLM work to query time under an explicit relevance-test budget; KET-RAG (arXiv:2502.09304) states LLM-based extraction "incurs prohibitively high indexing costs at scale" and matches quality >10× cheaper; GraphRAG-Bench (arXiv:2506.05690) measures LightRAG *below* vanilla RAG on fact retrieval with ~100× prompt-token overhead. Entity resolution is a mature discipline (blocking + matching + adjudication) that none of these systems imported. The chunking landscape adds the composition warning: enrichment artifacts (contextual headers, summary trees, propositions) are the structures with the worst invalidation behavior under corpus change (`document-processing-chunking.md` failure 10) — coupling issue 6 to issue 5.

**Next-gen requirement.** Enrichment must be budgeted, gated, and adaptive: explicit per-corpus token/compute budgets, entity resolution as a core primitive, sampled extraction-quality QA before graph/memory writes, provenance bits preventing re-extraction of injected content, and default routing that reserves graph/enrichment machinery for query classes where an in-framework ablation shows it beats the vector baseline. **Test:** (a) ingestion refuses to exceed a declared enrichment budget and reports projected cost before running; (b) a junk-rate metric over sampled extractions is emitted per run, with a configurable gate that blocks writes above threshold; (c) the framework can run an automatic graph-vs-vector ablation on a golden query set and report per-query-class deltas.

---

### 7. English-centric retrieval stacks (`english-centric-stack`)

**Definition.** Analyzers, keyword/entity extraction, fusion weights, and rerankers default to English assumptions, so the lexical leg of hybrid retrieval, extraction-based indexing, and score calibration silently degrade or break on non-English and mixed-language corpora — with no per-language telemetry to reveal it.

**Evidence.**

| Framework | Evidence (file + gist) | Label |
|---|---|---|
| Mem0 | `memory-and-localfirst.md` I7: BM25 keyword search and entity extraction are **English-only** (#4884) in a product marketed as a universal memory layer — and the 2026 retrieval redesign leans harder on keyword/entity signals, making the English assumption load-bearing | documented-recurring |
| IBM watsonx | `gpu-vendor-enterprise-rag.md` R1: the **only** reranker offered platform-wide is `ms-marco-minilm-l-12-v2` — vendor docs state flatly "Reranker models \| English" — on a platform sold to regulated multinationals | documented-recurring (vendor docs) |
| Microsoft GraphRAG | `microsoft-graphrag.md`: entity extraction from Chinese documents "very messy" (#596, 30 comments) — extraction quality collapses off-English, poisoning the graph (couples to issue 6) | documented-recurring |
| Qdrant | `vectordb-and-startup-platforms.md`: BM25 has no supported way to disable stemming; `language:"none"` is an undocumented footgun (#9289, open); miniCOIL sparse model is English-only with a 30k vocabulary (vendor-admitted) | documented-recurring |
| LightRAG | `hkuds-lightrag-family.md` R4: every non-naive query routes through an LLM keyword-extraction hop that misfires on small models and non-English input, silently degrading retrieval (#1348, #1408) | documented-recurring |
| LlamaIndex.TS | `jvm-js-ecosystems.md` D2: Hebrew PDFs extracted with reversed text (#2021, open at deprecation) — RTL ingestion broken outright | documented |
| Khoj | `memory-and-localfirst.md` I7: Slovenian notes — unless the keyword appeared verbatim, "results seemed more or less random" (HN 36933452) | single-anecdote (supporting) |
| Ecosystem-wide | `cross-cutting-gaps.md` (f): Elasticsearch's own docs hedge that its built-in CJK analyzer may be inferior to a plugin the user must discover; frameworks expose one global hybrid-fusion weight where the correct weight inverts by language | documented-recurring |

**Root cause.** The stack was built, benchmarked, and issue-triaged by an anglophone community against English benchmarks; language sensitivity lives in the least glamorous components (tokenizers, analyzers, stemmers, stopword lists, extraction prompts) that frameworks wrap rather than own. Aggregate dashboards and leaderboard averages hide per-language collapse, and the affected users are structurally least represented in the feedback channels — `cross-cutting-gaps.md` notes the categories that bite hardest in non-anglophone production are the ones anglophone open-source discourse discusses least, which is exactly how they stay off roadmaps. The hybrid-retrieval "best practice" quietly assumes a competent analyzer; where the analyzer is wrong, the sparse leg adds noise and nobody measures it.

**Research context.** Measured, published, and unpackaged. MIRACL (arXiv:2210.09984) shows ~3× nDCG spread across 18 languages within a single method, with lexical-vs-dense rankings *inverting* by language — so a single global fusion weight is guaranteed mis-set for a multilingual corpus. MMTEB (arXiv:2502.13595) shows aggregate leaderboard rank is a poor predictor of per-language quality (a 560M model beats 7B-class models on Indic retrieval). Amiraz et al. (ArabicNLP 2025, arXiv:2507.07543) isolate cross-language *score calibration* as the enterprise bottleneck, with cheap fixes (per-language quotas, query translation). Tokenizer inequity is quantified at up to 15× (arXiv:2305.15425), meaning fixed token-budget chunking and top-k allocations systematically short-change non-English content. NoMIRACL (arXiv:2312.11361) shows per-language hallucination/abstention behavior varies wildly. The landscape's own verdict: the mitigations are "published, cheap, and ignored — a framework-level packaging gap rather than a research gap" (treat that file's production-practice specifics as flagged-uncertain; the benchmark findings above stand on their own).

**Next-gen requirement.** Language as a first-class pipeline variable: per-language analyzer provisioning with a competence check (degrade to dense-only *loudly* if the sparse leg lacks a suitable analyzer), per-language fusion weights and score normalization, language-normalized token budgeting, and per-language retrieval telemetry by default. **Test:** ingest a mixed English/CJK/RTL golden corpus — the framework must (a) report retrieval quality per language, not aggregate-only; (b) refuse or warn when the sparse index uses an analyzer unfit for a detected language; (c) demonstrate that a cross-language query set is not starved by uncalibrated mixed-language ranking (per-language recall within a declared band).

---

## Near-misses

Patterns real but below the three-framework bar, resting on weak evidence, or better owned by another dimension:

- **Retrieval capitulation ("pinning").** AnythingLLM's sanctioned workaround for poor retrieval is pinning whole documents into context, and users asked to auto-pin anything a search touches (#3587); LM Studio stuffs full files when they fit. Two platforms — but diagnostically rich: users trust the retriever only as a document router, not a passage selector.
- **The OpenAI top_k≥45 recall bug** (community bug 1381267) is a single anecdote; it is cited inside issue 4 as color, not spine — but it is the cleanest known example of infrastructure-level silent recall loss in a flagship managed service.
- **Multimodal ingestion cost/fragility.** Morphik's founders' own numbers (15–20 s/page ColPali ingestion on laptop hardware), RAG-Anything's unanswered parsing-stuck/image-analysis bugs (#49, #70), and Dify's image-query rerank misclassification (#37116) suggest visual-retrieval pipelines ship with unpriced cost and unhardened paths — three data points but heterogeneous failure shapes; not yet one issue.
- **Semantic-chunking folk wisdom lag.** Research shows semantic chunking is largely a null result versus tuned recursive splitting (arXiv:2410.13070 NAACL 2025; two 2026 replications), yet it remains default tutorial advice across the ecosystem. This is a knowledge-transfer failure more than a framework defect; no framework *enforces* the bad advice.
- **Multi-query + RRF cargo cult.** The most-deployed query-side technique has the weakest evidence (ARAGOG negative; RAG-Fusion's own drift report; DMQR redundancy), reconcilable only when a reranker follows it (`query-understanding-transformation.md` §5) — a defaults-and-guidance gap adjacent to issue 1, but framework-side evidence of harm is thin.
- **Hosted-pipeline stage opacity.** Pinecone Assistant/Vectara/GroundX/Vertex AI Search hide chunker/embedder/ranker entirely (architectural-inference; "bad answer → support ticket"). Real and recurring, but the failure is *unobservability*, owned by the evaluation-observability dimension.

---

## Cross-issue interactions

The seven issues are not independent; the corpus shows them composing into failure chains that no single framework file fully names:

- **2 × 6:** structure-destroying ingestion feeds extraction-based enrichment — GraphRAG and LightRAG run LLM entity extraction over *already-flattened* text, so the graph inherits both parsing loss and extraction noise; GraphRAG's Chinese-extraction collapse (#596) is issues 2, 6, and 7 in one artifact.
- **3 × 5:** because chunking/embedding are one-way doors, teams cannot fix mutation bugs by re-deriving the index cheaply — Bedrock's answer to a broken sync is "delete the KB and re-ingest," which is only tolerable because the door was one-way to begin with.
- **4 × security:** silent filter corruption is the tenant-isolation mechanism failing quietly — LangChain4j #2513 (NOT-IN matches all content) and Haystack #12065 (merge silently drops init filters) are retrieval-quality bugs that are simultaneously data-exposure bugs, since nearly every framework implements ACLs as metadata filters (see the security dimension).
- **5 × 6:** enrichment artifacts have the worst mutation behavior — a single document edit invalidates ancestor summaries (RAPTOR-style trees), community reports (GraphRAG), and contextual chunk headers, so the frameworks that invested most in ingest-time intelligence are the most brittle under change.
- **1 × 7:** frozen defaults are frozen *English* defaults — a single global fusion weight or similarity threshold is not just stale but provably mis-set for most non-English slices of a corpus (MIRACL's per-language inversion), and the missing eval loop hides both at once.

These chains matter for the paper because they imply the fixes are not seven independent features: a canonical-store/derived-view architecture (req. 3) plus a conformance-and-eval discipline (reqs. 1, 4) removes the preconditions for most of the downstream compositions.

---

## Dimension synthesis

What this dimension reveals is that the ecosystem is stuck in a **quality-blind equilibrium**, and the mechanisms are visible in the evidence:

1. **The demo is the objective function.** Every recurring defect traces to optimizing time-to-first-answer: string-typed documents (cheap loader ecosystems), top-k-similarity defaults (no dependencies, no latency), batch ingestion (no sync machinery), one-shot enrichment (paper-shaped pipelines). The corpus's rare counter-examples — Cortex Search's reranked-hybrid default, Azure's measured recall — are managed platforms whose buyers evaluate outcomes, not demos.

2. **The feedback loop that would fix defaults does not exist.** With no in-framework retrieval evaluation (a finding in essentially every file, owned by the eval dimension), a bad default, a silent filter bug, a stale vector, or an English-only analyzer produces no regression signal — only unattributable "answers are wrong" issues that get closed with tuning folklore or stale-bots. Silent failure shape + no measurement = defects that persist for years across independent codebases (the filter-translation bug class was independently shipped by at least four frameworks).

3. **Open-core economics point quality-critical stages away from the commons.** Parsing fidelity (LlamaParse, DeepDoc, GroundX, "Smart Parsing"), ACL-aware sync, and managed re-indexing are consistently the monetized tier; the OSS layer keeps the naive version *because* its inadequacy sells the paid one. A next-gen framework that wants a healthy commons must make the quality-critical first mile open, benchmarked, and portable — or accept that its ecosystem's floor is set by someone's conversion funnel.

4. **The research-practice gap runs in both directions.** In one direction, solved-or-measured science is simply not packaged: hybrid+rerank cascades, structure-aware parsing evidence (OHR-Bench), per-language calibration fixes, budgeted lazy enrichment. In the other, research systematically cannot see the frameworks' real failure surface: chunking papers evaluate on pre-parsed clean text, harnesses freeze corpora, and no benchmark jointly varies parser × chunker × retriever under edit streams. The two literatures validate each other's blind spots.

5. **The deepest architectural error is treating ingest-time decisions as permanent and index state as primary.** One-way-door chunking/embedding (issue 3), mutation-hostile indexes (issue 5), and enrichment artifacts with unbounded invalidation (issue 6) are the same mistake at three layers: the framework stores *derived* representations as if they were the source of truth. The single highest-leverage design move available to a next-generation framework is inverting this — canonical parsed documents with structure and provenance as the durable artifact, and chunks, vectors, graphs, and enrichments as versioned, re-runnable, budgeted views whose correctness under change is contractually tested.

Testable requirements derived from the issues: (1) versioned, benchmark-backed default retrieval profiles with published per-release regressions; (2) a typed structural document model with provenance and parser confidence surviving to retrieval; (3) canonical-store + derived-view architecture enabling in-place re-chunk/re-embed with dual-read migration; (4) mandatory cross-backend conformance suites for filters/scores with loud capability failures; (5) an incremental-correctness contract (verified delete, bounded edit blast radius, freshness state); (6) budgeted, quality-gated enrichment with entity resolution and automatic vector-baseline ablations; (7) language-aware retrieval with per-language telemetry, analyzer competence checks, and calibrated cross-language ranking.
