# Multimodal & Structured-Data RAG: Landscape, Failure Modes, and Open Problems (as of August 2026)

## Scope

This document surveys retrieval-augmented generation beyond plain text: (1) vision-native document
retrieval (page-as-image, OCR-free); (2) tables and text+table RAG; (3) text-to-SQL as a retrieval
problem, hybrid SQL+vector systems, and semantic layers; (4) code retrieval for software agents;
(5) video and audio RAG; (6) chart/figure understanding; (7) the multimodal embedding-model
landscape; and (8) architecture patterns for unifying knowledge bases, APIs, and databases behind
one retrieval interface. Emphasis is on 2024–2026 work, with failure modes, critiques, and open
problems foregrounded because this feeds the design of a next-generation RAG framework.

Sourcing notes: arXiv IDs are given for every paper actually seen in search results or fetched.
Preprints are distinguished from peer-reviewed venues. Several claims sourced from vendor or
practitioner blogs are labeled as such. Claims marked *(uncertain)* were reported in secondary
summaries and could not be verified against the primary source in this session.

---

## Lineage & chronological development

**Pre-2024 context (compressed).** Text RAG's canonical pipeline — parse → chunk → embed → ANN
search → stuff context — was built for prose. Everything in this document is a reaction to the ways
that pipeline breaks on PDFs, tables, schemas, codebases, video, and audio. Late interaction
(ColBERT-style multi-vector scoring) and CLIP-style dual encoders are the two pre-existing
retrieval primitives that the multimodal wave reused.

**2024 — the "screenshot turn."**
- *DSE — Unifying Multimodal Retrieval via Document Screenshot Embedding* — Ma et al. — EMNLP 2024
  — arXiv:2406.11251. Encode the rendered page screenshot directly with a VLM into a single dense
  vector; no parsing/OCR pipeline at all. Beat BM25 by 17 points top-1 accuracy on web-page
  retrieval and OCR-text pipelines by >15 nDCG@10 on slide retrieval. Established that parsing is
  a lossy, error-prone preprocessing stage that can be deleted.
- *ColPali: Efficient Document Retrieval with Vision Language Models* — Faysse et al. —
  arXiv:2407.01449 — 2024. The multi-vector counterpart to DSE: a VLM (PaliGemma) emits a grid of
  ~128-dim patch embeddings per page; queries score against patches via ColBERT-style MaxSim.
  Introduced the ViDoRe benchmark, on which ColPali hit nDCG@5 = 81.3 vs 67.0 for the best
  text+OCR+captioning pipeline. This single result reframed document retrieval for the field.
- *VisRAG* — Yu et al. — arXiv:2410.10594 — 2024 (rev. 2025). First end-to-end vision-based RAG
  pipeline (VLM retriever + VLM generator over page images); reported 20–40% end-to-end gain over
  text-based RAG on multimodality documents.
- *M3DocRAG* — Cho et al. — arXiv:2411.04952 — 2024. Scaled the recipe to open-domain, multi-page,
  multi-document settings: ColPali-style retrieval over page images, top-k raw pages fed to an
  MLLM (e.g., Qwen2-VL). Argued explicitly that text-extraction pipelines discard figures/layout.
- *TableRAG: Million-Token Table Understanding* — Chen et al. — NeurIPS 2024 — arXiv:2410.04739.
  Query expansion + schema retrieval + cell retrieval so the LM never sees the full table;
  scales table QA to million-token tables; new benchmarks derived from Arcade and BIRD-SQL.
- *Spider 2.0* — Lei et al. — arXiv:2411.07763 — 2024 (rev. 2025). Reframed text-to-SQL as an
  enterprise *workflow* problem (632 tasks; multiple dialects, cloud warehouses, metadata and
  docs that must be consulted). o1-preview: 21.3% success, vs 91.2% on Spider 1.0 and 73.0% on
  BIRD — the clearest single number showing academic text-to-SQL benchmarks had saturated on an
  unrealistic problem formulation.
- *Video-RAG (visually-aligned auxiliary texts)* — arXiv:2411.13093 — 2024. Training-free long-video
  comprehension via retrieval of aligned auxiliary text (OCR/ASR/detection) rather than raw frames.
- *MegaPairs* — arXiv:2412.14475 — 2024. Massive synthetic data generation for universal multimodal
  retrieval — the data-side enabler for universal multimodal embedders.
- *SpeechRAG* — ICASSP 2025 — arXiv:2412.16500. Retrieval over raw speech without ASR: a speech
  adapter aligned into a frozen text retriever's embedding space, avoiding ASR error propagation.

**2025 — consolidation, benchmarks, and the first critique wave.**
- ColQwen2/2.5 (Qwen2-VL/2.5-VL backbones, dynamic resolution) replace ColPali as the default
  visual retrievers; ColQwen-Omni extends toward mixed text/visual input (practitioner sources:
  Mixpeek guide; EmergentMind ColPali topic page).
- Surveys arrive: *Ask in Any Modality* (arXiv:2502.08826, ACL 2025 Findings); *A Survey of
  Multimodal RAG* (arXiv:2504.08748); *Scaling Beyond Context* — Gao et al. (arXiv:2510.15253,
  ACL 2026) for document understanding specifically.
- *VideoRAG: Retrieval-Augmented Generation over Video Corpus* — Jeong et al. — ACL 2025 Findings
  — arXiv:2501.05874; and *VideoRAG: RAG with extreme long-context videos* — arXiv:2502.01549.
- *WavRAG* — ACL 2025 — arXiv:2502.14727. First end-to-end audio-native RAG (no ASR anywhere);
  ~10x faster than ASR-text RAG pipelines at comparable retrieval quality.
- *VDocRAG* — Tanaka et al. — CVPR 2025 — arXiv:2504.09795. Self-supervised pretraining to compress
  page images into dense tokens; introduced OpenDocVQA, the first unified open-domain document-VQA
  retrieval collection.
- Critique/efficiency wave for visual retrieval: ViDoRe V2 (arXiv:2505.17166) responds to V1
  saturation (>90% nDCG@5 for top models); reproducibility study of late interaction
  (arXiv:2505.07730); Light-ColPali storage study (arXiv:2506.04997, ACL 2025 Findings);
  hierarchical patch compression (arXiv:2506.21601); pixel-poisoning attacks on screenshot
  retrievers (arXiv:2501.16902).
- Code side: *cAST* AST-based chunking (arXiv:2506.15655, EMNLP 2025 Findings); *RepoGraph*
  (arXiv:2410.14684, ICLR 2025); Agentless-style hierarchical localization becomes the de facto
  SWE-bench recipe; the "grep vs embeddings" practitioner debate peaks (Augment/Flaherty, Sept 2025).
- Tables: *T²-RAGBench* (arXiv:2506.12071, EACL 2026) shows text+table RAG remains unsolved;
  Table-QA survey (arXiv:2510.09671).
- Embeddings: MMEB/VLM2Vec (ICLR 2025) → MMEB-V2 (78 tasks incl. video + visual docs, TMLR 2026);
  MetaEmbed test-time-flexible late interaction (arXiv:2509.18095); jina-embeddings-v4
  (Qwen2.5-VL-3B backbone, task LoRAs, text+image+PDF in one space).

**Late 2025 – mid 2026 — agentic and reasoning-centric multimodal RAG.**
- Visual RAG goes agentic/iterative: VisRAG 2.0 evidence-guided multi-image reasoning
  (arXiv:2510.09733); Vgent graph-based retrieve-reason for long video (arXiv:2510.14032);
  Doc-V* coarse-to-fine interactive visual reasoning (arXiv:2604.13731); UniDoc-RL RL-trained
  coarse-to-fine visual RAG (arXiv:2604.14967); deferred visual ingestion ("index light, reason
  deep", arXiv:2602.14162); VLD-RAG agentic vision-language doc RAG (arXiv:2607.24748).
- Failure-mode literature matures: attention distraction in retrieval-augmented LVLMs
  (arXiv:2602.00344); "hallucination on hallucination" compounding (arXiv:2603.27253); agentic
  query visual pre-processing benchmark "Fix Before Search" (arXiv:2602.13179); utility-oriented
  visual evidence selection (arXiv:2605.13277); BayesRAG cross-modal evidence corroboration
  (arXiv:2601.07329).
- Structured data: CIDR 2026 paper "Text-to-SQL Benchmarks are Broken" (annotation-error analysis
  of BIRD/Spider 2.0-Snow); semantic-layer-vs-text-to-SQL benchmarks (dbt blog, Feb 2026;
  arXiv:2604.25149) show near-100% accuracy when a curated semantic layer exists.
- Embeddings: MMEB-V3 (COLM 2026) adds audio + agent-centric retrieval; Gemini Embedding 2,
  Qwen3-VL-2B, Voyage Multimodal 3.5, Cohere Embed v4 define the production frontier
  (Milvus/practitioner benchmarks, 2026).

---

## State of the art — mid-2026 snapshot

- **Documents:** Vision-native retrieval (ColQwen2.5-class multi-vector, or single-vector
  DSE-style/jina-v4/voyage-multimodal for cheaper indexes) is the default for visually rich PDFs.
  OCR has not died: it survives as (a) a hybrid signal fused with visual retrieval, (b) the path
  to structured *extraction* (not retrieval), and (c) the cheap option for text-dense corpora,
  where the reproducibility literature (arXiv:2505.07730) shows visual late interaction's edge
  narrows. Generation over retrieved *page images* with a frontier MLLM is standard.
- **Storage/latency:** multi-vector page indexes cost ~10–100x a single-vector index; pooling and
  merging recover ~98% quality at ~12% memory (Light-ColPali, arXiv:2506.04997); binary
  quantization + two-stage rerank is standard production practice (practitioner sources).
- **Tables:** no single winner. Schema+cell retrieval (TableRAG) for giant tables; hybrid
  BM25+dense for text+table corpora (best on T²-RAGBench but still far from solved); serious
  numerical-reasoning failures persist.
- **NL→data:** the field has largely accepted that raw text-to-SQL over messy warehouses is
  unreliable (Spider 2.0: ~21–40% for top systems vs 90%+ on toy benchmarks); the pragmatic SOTA
  is retrieval over a *semantic layer* (curated metrics/joins), where accuracy approaches 100%
  and failures become refusals instead of confidently wrong numbers (dbt 2026 benchmark;
  arXiv:2604.25149).
- **Code:** agentic grep/AST navigation beats static embedding indexes on small repos
  (SWE-bench-style), but embeddings/graphs win on large unfamiliar corpora; production systems use
  hybrid: structural index (tree-sitter graph / RepoGraph) + lexical + embeddings, exposed as
  tools to an agent.
- **Video/audio:** retrieval is the accepted answer to context-length limits; native audio
  retrieval (WavRAG) and graph/storyline-structured video retrieval (Vgent, SVAgent) are the
  research frontier; production video RAG is still mostly ASR+caption+frame-sampling pipelines.
- **Embeddings:** universal "omni" embedders (text+image+video+audio+PDF in one space) exist
  (Gemini Embedding 2; Qwen3-VL-2B open-source; jina-v4; Voyage Multimodal 3.5) and are evaluated
  on MMEB-V3 (COLM 2026); the modality gap — not parameter count — is the best predictor of
  cross-modal retrieval quality (Milvus 2026 benchmark: Qwen gap 0.25 vs Gemini 0.73).

---

## Vision-native document retrieval: do we still need OCR?

### The case against parsing
The parse→chunk pipeline loses layout, figures, charts, handwriting, stamps, and reading order;
parsing is brittle and expensive per document type. DSE (arXiv:2406.11251) and ColPali
(arXiv:2407.01449) showed page-as-image retrieval beats tuned OCR pipelines by wide margins on
visually rich corpora; M3DocRAG (arXiv:2411.04952) and VisRAG (arXiv:2410.10594) showed the same
end-to-end. VDocRAG (CVPR 2025, arXiv:2504.09795) strengthened generalization via dedicated
pretraining. "Any Information Is Just Worth One Single Screenshot" (arXiv:2502.11431) pushes the
logical endpoint: unify *all* retrieval as visualized information retrieval.

### The case that OCR survives
- **Text-dense corpora:** the late-interaction reproducibility study (Qiao et al.,
  arXiv:2505.07730) found visual late interaction's query-token→patch matching is *not* the crisp
  lexical alignment ColBERT exhibits — tokens match visually-similar or neighboring patches — and
  robustness on text-intensive datasets at scale is a real concern. On clean digital text, text
  retrieval remains cheaper and at least as accurate.
- **Cost:** multi-vector page embeddings (≈1000+ patch vectors/page) explode index size and
  MaxSim latency. Mitigations are active research: Light-ColPali (98.2% quality at 11.8% memory;
  notable negative result: *random* pruning beat "sophisticated" pruning methods —
  arXiv:2506.04997); hierarchical patch compression w/ dynamic pruning + quantization
  (arXiv:2506.21601); training-free pooling + multi-stage search (arXiv:2602.12510); pyramid
  indexing (arXiv:2511.21121).
- **Benchmark saturation & bias:** ViDoRe V1 saturated (>90% nDCG@5), and its queries were largely
  synthetic, page-answerable, extractive questions. ViDoRe V2 (arXiv:2505.17166) added blind
  contextual and long cross-document queries and immediately re-opened a large headroom gap —
  i.e., the "OCR is dead" conclusion was partly an artifact of easy benchmarks.
- **Downstream structure needs:** retrieval is only half the job; agents often need *structured*
  values (amounts, dates, keys) that still require extraction, where OCR/parsing (olmOCR-class
  VLM parsers) remains the tool. *(Ecosystem observation; specific tool comparisons not verified
  this session.)*
- **Security:** document screenshot retrievers are vulnerable to *pixel poisoning* — adversarial
  images crafted to rank for many queries (arXiv:2501.16902). A text pipeline has different (and
  better-understood) injection surfaces.

### Newer directions (2026)
Spatially-grounded retrieval propagates patch relevance to page *regions*, giving
sub-page citations (arXiv:2512.02660). Multilingual visual retrieval remains behind English
(M3DR, arXiv:2512.03514). CausalEmbed generates multi-vector representations auto-regressively
(arXiv:2601.21262). "Index light, reason deep" (arXiv:2602.14162) inverts the pipeline: keep a
cheap index, defer expensive visual ingestion to query time — a design directly relevant to a
next-gen framework.

**Verdict:** the field's answer to "do we still need OCR?" in mid-2026 is *"not for retrieval of
visually rich pages; yes for structured extraction, text-dense corpora at scale, and cost-bounded
indexes."* The interesting framework question is no longer OCR-vs-pixels but *when to pay which
cost* — a routing/policy problem no current system solves explicitly.

---

## Tables and text+table RAG

- **TableRAG (NeurIPS 2024, arXiv:2410.04739):** treats the table itself as a corpus — schema
  retrieval + cell retrieval with query expansion; scales to million-token tables; SOTA on
  Arcade/BIRD-SQL-derived benchmarks. Limitation: designed for single large tables, not corpora
  of heterogeneous documents containing tables.
- **Name collision warning:** a different 2025 "TableRAG" (heterogeneous document reasoning
  framework) exists; the literature now contains at least two unrelated systems with this name.
- **T²-RAGBench (EACL 2026, arXiv:2506.12071):** 23,088 question-context-answer triples over
  real-world financial text+table documents, deliberately built so 91.3% of questions are
  context-independent (fixing the multiple-valid-answers flaw of prior QA sets). Findings: hybrid
  BM25 (sparse+dense) is the best retriever for text+table data, and *all* SOTA RAG methods remain
  weak — numerical reasoning over retrieved tables is a standing failure.
- **Retrieval of tables (as items):** question generation from partial tables improves table
  retrieval (arXiv:2508.06168). The comprehensive Table-QA survey (arXiv:2510.09671) catalogs the
  LLM-era task landscape.
- **How tables break vanilla RAG (well-replicated practitioner findings, consistent with the
  above):** naive chunking slices rows from headers; linearized tables embed poorly; cell-level
  answers need exact lookup, not semantic similarity; aggregations need computation, not
  retrieval. The convergent lesson across TableRAG and text-to-SQL work: *tables want symbolic
  execution, with retrieval used to locate the right table/columns/cells — not to "read" the
  table via embeddings.*

---

## Text-to-SQL as retrieval; hybrid SQL+vector; semantic layers

### The reality check
Spider 2.0 (arXiv:2411.07763) is the pivotal document: real enterprise workflows (dialects,
metadata, project docs, 1000+ column schemas) drop frontier-model success from 91.2% (Spider 1.0)
and 73.0% (BIRD) to 21.3% (o1-preview). Enterprise-focused follow-ups (OpenReview gXkIkSN2Ha)
argue benchmarks must include *retrieving the right tables from massive scopes* and *locating
scattered knowledge in documents* — i.e., text-to-SQL is substantially a retrieval problem
(schema linking, business-glossary lookup, example-query retrieval), not a translation problem.

### The benchmarks themselves are broken
- "Text-to-SQL Benchmarks are Broken" (CIDR 2026, Jin et al.): systematic annotation-error
  analysis of BIRD and Spider 2.0-Snow — question/logic mismatches, question/data mismatches,
  ambiguous targets; 22 gold BIRD queries outright wrong; correcting them shifts model rankings.
- BIRD's hand-written per-query "evidence" is unrealistic: production systems must *retrieve*
  that domain knowledge (MotherDuck, "Your Data Model Is the Semantic Layer"). A FLEX-metric
  study found BIRD execution-accuracy agrees with human experts only ~62% of the time
  *(number reported in secondary summaries; primary source not fetched — uncertain)*.

### Semantic layers: the current pragmatic answer
The dbt Labs 2026 benchmark (vendor blog, but paired-design): for queries covered by a
well-modeled semantic layer, Claude Sonnet 4.6 goes 90.0%→98.2% and GPT-5.3-Codex 84.1%→100.0%
vs raw text-to-SQL; crucially, semantic-layer failures are *refusals* while text-to-SQL failures
are *confident wrong numbers* — a failure-mode asymmetry that matters more than the accuracy
delta. Independent support: arXiv:2604.25149 (paired accuracy/hallucination benchmark across
three frontier models). Critique: semantic layers only answer questions someone anticipated when
modeling; coverage, staleness, and modeling cost are the new bottleneck (MotherDuck blog).

### Hybrid relational+vector execution
Two architecture families (surveyed via EmergentMind "Hybrid Relational-Vector Systems" and
arXiv:2505.18458 LLM×Data survey; individual systems below not independently verified this
session): (a) SQL-dialect extensions embedding semantic operators — BlendSQL (LLM calls inside a
SQL superset), Text2VectorSQL (vector ops native in SQL); (b) unified query planners over
relational + semantic predicates (arXiv:2604.02444). Related: OLAP-style multidimensional corpus
partitioning for RAG (arXiv:2601.03748). Gap repeatedly noted: no single engine unifies
full-text + vector + graph + relational retrieval with one planner; RAG stacks bolt these
together in application code.

---

## Code retrieval for agents

- **Agentless (GitHub: OpenAutoCoder/Agentless):** hierarchical localization — LLM-guided
  file/function narrowing combined with embedding retrieval for additional suspicious files —
  became the template showing a simple pipeline rivals complex agents on SWE-bench.
- **RepoGraph (ICLR 2025, arXiv:2410.14684):** line-level repository graph (def/ref edges) as a
  plug-in; ~32.8% relative SWE-bench improvement across four host methods. Successors: RANGER
  (arXiv:2509.25257), LARGER lexically-anchored graph exploration (arXiv:2605.16352), programming
  knowledge graphs for context-augmented codegen (arXiv:2601.20810), tree-sitter knowledge graphs
  served over MCP (arXiv:2603.27277).
- **Chunking matters:** cAST (EMNLP 2025 Findings, arXiv:2506.15655) — AST-respecting chunking
  (recursively split large nodes, merge siblings) — +4.3 Recall@5 on RepoEval, +2.67 Pass@1 on
  SWE-bench as a drop-in change. Evidence that *ingestion structure*, not just the retriever,
  moves end-task numbers.
- **The grep-vs-embeddings debate:** Augment's Colin Flaherty (Sept 2025, via jxnl.co): grep+find
  sufficed for their top SWE-bench agent because repos are small, code is keyword-rich, and a
  persistent agent can iterate searches — with explicit caveats that embeddings become necessary
  for large unfamiliar codebases, non-code content, and third-party code. Counter-evidence: a
  2025–2026 study reported embedding-based retrieval outperforming agent-led in-context retrieval
  (41.7% vs 36.1% pass rate) *(figures seen only in a secondary search summary; attribution
  uncertain — candidates include arXiv:2606.22417 "Code Isn't Memory" and the FSE 2025
  "Demystifying LLM-Based Software Engineering Agents")*. The honest synthesis: retrieval-tool
  choice is contingent on corpus size, familiarity (in-training-data or not), and agent iteration
  budget — SWE-bench systematically understates the value of semantic indexes because its repos
  are popular, small, and memorized.
- **Structural indexes as agent memory:** "Code Isn't Memory" (arXiv:2606.22417) and
  Codebase-Memory (arXiv:2603.27277) position the code index as persistent agent memory queried
  via tools (MCP), not as a top-k context-stuffer — an architectural shift from RAG-as-pipeline
  to retrieval-as-tool that generalizes beyond code.

---

## Video & audio RAG

**Video.** Two "VideoRAG" lineages: corpus-level retrieval of relevant videos with joint
visual+textual representation (Jeong et al., ACL 2025 Findings, arXiv:2501.05874) and extreme
long-context single-video RAG (arXiv:2502.01549). Training-free Video-RAG retrieves auxiliary
aligned texts (OCR/ASR) instead of frames (arXiv:2411.13093). Efficiency-focused: E-VRAG
(arXiv:2508.01546), AdaVideoRAG adaptive omni-contextual retrieval (arXiv:2506.13589). Structure-
aware: Vgent's graph-based retrieve→reason pipeline notes that naive frame retrieval *disrupts
temporal dependencies* and admits irrelevant clips (arXiv:2510.14032); SVAgent uses storyline-
guided multi-agent decomposition (arXiv:2604.05079). Core unresolved tension: chunking video
destroys temporality; keeping temporality blows the context budget.

**Audio.** SpeechRAG (ICASSP 2025, arXiv:2412.16500): text-query→speech-passage retrieval without
ASR, killing ASR error propagation. WavRAG (ACL 2025, arXiv:2502.14727): first fully
audio-native RAG (audio in KB and query), ~10x faster than cascaded ASR pipelines at comparable
retrieval quality. PlanRAG-Audio adds planning for long-form audio (arXiv:2605.20414). Audio RAG
remains the least mature modality: tiny benchmark ecosystem, and most production systems still
transcribe.

---

## Charts & figures

Chart QA benchmarks (ChartQA → ChartQAPro 2025, mChartQA arXiv:2404.01548, LongChart VQA
arXiv:2608.01328) show MLLMs still fail on implicit numeric reading, color-pattern
disambiguation, and multi-chart reasoning; the 2026 chart-understanding survey (arXiv:2602.10138)
frames current MLLMs as perceptually strong but cognitively shallow on charts. Two pipeline
options — chart-to-text/table conversion vs direct visual QA — mirror the OCR-vs-pixels debate
and have the same conclusion: conversion loses information, direct reading loses precision.
Cross-modal multi-hop reasoning over text+tables+charts (FCMR, arXiv:2412.12567) is a distinctly
harder setting than any single modality. For *retrieval*, charts mostly ride along inside page
images (ColQwen-class retrievers), which works for locating but not for answering: the precise-
value-readout failure transfers to the generation stage of visual RAG.

---

## Multimodal embedding models — 2026 state

- **Benchmarks:** MMEB (ICLR 2025, 36 tasks) → MMEB-V2 (TMLR 2026, 78 tasks; adds video +
  structured/visual documents) → MMEB-V3 (COLM 2026; omni-modality incl. audio, visual docs, and
  *agent-centric retrieval*) — GitHub: TIGER-AI-Lab/VLM2Vec. Long-context multimodal embedding
  (MMLongEmbed, arXiv:2606.14747) and video embedding (MVEB, arXiv:2606.14958) benchmarks appear
  in 2026, both showing sharp degradation regimes.
- **Models (production tier, per Milvus/Zilliz 2026 benchmark blog + vendor pages):** Gemini
  Embedding 2 (5 modalities incl. PDF; 0.997 cross-lingual; but modality gap 0.73), Qwen3-VL-2B
  (open-source; best text↔image 0.945; modality gap 0.25), Voyage Multimodal 3.5 (MRL: <1% loss at
  256 dims), Cohere Embed v4, jina-embeddings-v4 (Qwen2.5-VL-3B + task LoRAs; text+image+PDF;
  cross-modal alignment 0.71 vs 0.15 for CLIP per Jina's own reporting — vendor numbers).
- **Key empirical insight:** the *modality gap* (distance between text and image embedding
  clusters) predicts cross-modal retrieval better than model size. VLM-backbone embedders
  (jina-v4, Qwen3-VL) largely close the gap that CLIP-style dual encoders cannot.
- **Research directions:** MLLM-as-judge training signal (UniME-V2, arXiv:2510.13515); test-time
  flexible late interaction letting one model serve single-vector or multi-vector regimes
  (MetaEmbed, arXiv:2509.18095); reasoning-enhanced embedding (arXiv:2604.06156); synthetic-data
  scaling (MegaPairs, arXiv:2412.14475).

---

## Unifying KB + API + database retrieval: architecture patterns

Observed patterns across the sources above:
1. **Single-engine convergence:** one store with lexical + vector (+ scalar filter) executing a
   fused query (Meilisearch/Elastic-style; vector-DB hybrid search). Still no engine credibly
   unifies full-text + vector + graph + relational for RAG (gap noted across the LLM×Data survey
   arXiv:2505.18458 and practitioner sources).
2. **Split-engine + application fusion:** parallel queries to specialized stores, fused (RRF etc.)
   in the app layer. Dominant in production; fragile weight tuning per modality
   ("dominant-modality bias" — bigdataboutique 2026 blog).
3. **SQL-as-substrate:** semantic operators embedded in a relational algebra (BlendSQL,
   Text2VectorSQL, unified relational-semantic planners arXiv:2604.02444) — interpretable, but
   adoption is early.
4. **Semantic-layer mediation:** NL → governed metric/join definitions → SQL (dbt-style). Highest
   reliability, lowest coverage; effectively *retrieval over a curated ontology*.
5. **Retrieval-as-tools for agents (ascendant, 2025–2026):** every source (vector KB, SQL, code
   graph, API) is a tool behind MCP-style interfaces; the LLM plans and iterates. The
   grep-beats-embeddings result and structural-index-as-memory papers (arXiv:2606.22417,
   arXiv:2603.27277) are early evidence this reframing changes what retrieval infrastructure
   should optimize for: *iterability, groundedness, and inspectability* rather than one-shot
   top-k recall.
6. **Agentic multimodal RAG:** surveys (arXiv:2504.08748; arXiv:2510.15253) track the same shift
   inside multimodal pipelines: coarse-to-fine, plan-then-retrieve, evidence-corroborating
   (BayesRAG arXiv:2601.07329; MG²-RAG multi-granularity graphs arXiv:2604.04969; Doc-V*,
   UniDoc-RL).

---

## Comparison tables

### Vision-native document retrieval

| System | ID / venue | Representation | Strength | Key weakness |
|---|---|---|---|---|
| DSE | 2406.11251, EMNLP'24 | 1 dense vec/page | Cheap index, no parsing | Single vector caps fine-grained matching |
| ColPali | 2407.01449 | ~1k patch vecs/page, MaxSim | Fine-grained, +14 nDCG@5 vs OCR pipelines | 10–100x storage, MaxSim latency |
| ColQwen2/2.5 | (model releases) | Dynamic-res patches | Higher res, aspect-ratio aware | Same cost profile |
| VisRAG | 2410.10594 | Dual-encoder page emb. | End-to-end vision RAG, 20–40% gain | Single-page bias; weak multi-image reasoning (→VisRAG 2.0) |
| M3DocRAG | 2411.04952 | ColPali idx + MLLM gen | Open-domain, multi-doc | Inherits retriever costs; top-k page ceiling |
| VDocRAG | 2504.09795, CVPR'25 | Compressed dense tokens | Pretraining for compression; OpenDocVQA | Costs under-reported |
| Light-ColPali | 2506.04997, ACL'25-F | Merged patch vecs | 98.2% quality @ 11.8% memory | Still multi-vector; merging tuned per model |

### Structured-data access routes

| Route | Reliability (mid-2026) | Coverage | Failure mode |
|---|---|---|---|
| Raw text-to-SQL on warehouse | ~21–40% on Spider 2.0-class tasks | Unlimited | Confident wrong numbers |
| + retrieved schema/doc evidence | Better; benchmark-dependent | Unlimited | Evidence-retrieval misses; ambiguity |
| Semantic layer | ~98–100% on covered queries | Only modeled questions | Refusals; stale/absent models |
| TableRAG-style cell retrieval | SOTA for giant single tables | Single-table QA | Aggregations; multi-table joins |
| Embed linearized tables (naive) | Poor (T²-RAGBench) | Any | Header/row separation; numeric errors |

### Modality maturity (retrieval + generation, mid-2026)

| Modality | Retrieval maturity | Bottleneck |
|---|---|---|
| Text | Mature | — |
| Doc pages (visual) | Production-ready | Index cost; multilingual; sub-page grounding |
| Tables | Fragmented | Symbolic vs semantic split; numeric reasoning |
| SQL/warehouse | Semantic-layer-gated | Coverage & modeling cost |
| Code | Production (hybrid) | Benchmark bias (SWE-bench); staleness of indexes |
| Video | Research | Temporal chunking; cost |
| Audio | Early research | Benchmarks; native-audio embedders |
| Charts (as answers) | Weak | Precise value readout by MLLMs |

---

## Failure modes & critiques

**F1. Benchmark inflation → premature "solved" narratives.** ViDoRe V1 saturated on synthetic
extractive queries (V2 paper, arXiv:2505.17166); Spider 1.0/BIRD wildly overstated text-to-SQL
(Spider 2.0: 91%→21%); BIRD gold queries contain outright errors that reorder leaderboards
(CIDR 2026). Any framework claim must be validated on V2-class, workflow-style benchmarks.

**F2. Multi-vector visual retrieval cost is a first-class constraint, not an implementation
detail.** Patch embeddings inflate storage 10–100x and MaxSim scan cost; an entire subfield
(2506.04997, 2506.21601, 2602.12510, 2511.21121) exists to claw this back. The negative result
that random pruning beats principled pruning (Light-ColPali) suggests our understanding of what
patch vectors encode is shallow.

**F3. Visual matching is not lexical matching.** Query tokens match visually similar/neighboring
patches, not the semantically corresponding region (arXiv:2505.07730). Consequences: weaker
interpretability than ColBERT, unpredictable behavior on text-dense pages, and no reliable
sub-page attribution (partially addressed by arXiv:2512.02660).

**F4. Generation-side multimodal failures compound retrieval wins.** Retrieval-augmented LVLMs
exhibit *attention distraction* — image tokens absorb attention that answer-bearing context needs
(arXiv:2602.00344); multi-image evidence integration is unstable, motivating VisRAG 2.0
(arXiv:2510.09733); "hallucination on hallucination": flawed retrieval seeds compounded generation
errors (arXiv:2603.27253). A framework that only optimizes retrieval nDCG misses the dominant
end-to-end error source.

**F5. Production multimodal-RAG pathologies (practitioner-reported, bigdataboutique 2026):**
caption drift (VLM-generated captions hallucinate details into the *index*); modality leakage
(image embeddings retrieve template-similar but wrong pages); dominant-modality bias in fusion;
stale-embedding lock-in (model upgrade forces full re-index — versioning is unsolved).

**F6. Tables resist embedding-space treatment.** Best-known hybrid retrieval still leaves
T²-RAGBench "challenging even for SOTA LLMs and RAG methods" (arXiv:2506.12071); the recurring
error class is numeric: aggregation, unit handling, cell-precision lookup.

**F7. Text-to-SQL fails asymmetrically and silently.** Confident wrong numbers, not refusals
(dbt 2026; arXiv:2604.25149). Also: hand-fed "evidence" in benchmarks hides the real retrieval
subproblem (schema linking + business-glossary retrieval at enterprise scale — OpenReview
gXkIkSN2Ha, MotherDuck).

**F8. Code-retrieval evaluation is distorted by SWE-bench.** Small, popular, memorized repos make
grep+agent-iteration look sufficient (Augment/jxnl.co); conclusions do not transfer to large
private codebases; meanwhile index-based approaches carry their own staleness and build costs.
Contradictory results across studies (grep-sufficient vs embeddings-win-41.7%-to-36.1%
*(uncertain attribution)*) indicate the field lacks a controlled study isolating corpus size,
familiarity, and iteration budget.

**F9. Temporal structure is destroyed by chunking.** Video RAG's central critique (Vgent,
arXiv:2510.14032): clip-level retrieval breaks temporal dependencies; the same argument applies to
long meetings/audio and to event-ordered logs.

**F10. Security surface of pixel-space retrieval.** Pixel poisoning attacks rank adversarial
pages for broad query sets (arXiv:2501.16902); multimodal indexes lack the sanitization tooling
text pipelines have.

**F11. Query-side degradation is unhandled.** Real user queries include blurry photos, cropped
screenshots, mixed-language text; "Fix Before Search" (arXiv:2602.13179) shows agentic query
pre-processing is necessary and largely missing from current pipelines.

**F12. Fragmented stacks.** No unified engine plans across lexical/vector/graph/relational;
fusion logic lives in glue code with hand-tuned weights; each modality has its own chunker,
embedder, index, and reranker with no shared cost model.

---

## Open problems (framework-design seeds)

**O1. Cost-aware modality routing.** No system decides *per corpus / per query* whether to pay
for pixels (multi-vector), a single visual vector, OCR text, or hybrid — despite clear evidence
each wins in different regimes (F2, F3). A next-gen framework should treat representation choice
as a learned/optimized policy with an explicit cost model (index $, latency, quality), not a
config constant.

**O2. Deferred / progressive ingestion.** "Index light, reason deep" (arXiv:2602.14162) gestures
at the principle: index cheaply at scale, escalate to expensive perception (full-page VLM read,
table parse, SQL execution) only for query-time candidates. Generalizing this into a uniform
anytime-retrieval contract across modalities is open.

**O3. Symbolic-semantic unification for structured data.** The evidence says: locate with
embeddings, answer with execution (TableRAG; semantic layers; hybrid SQL+vector). Missing: a
planner that decomposes a question into retrieve-vs-compute steps across documents, tables, and
warehouses with a single provenance trail — and that can *build/extend the semantic layer
automatically* to attack the coverage bottleneck (F7).

**O4. Refusal-calibrated retrieval.** The semantic-layer result (failures→refusals) is the only
place in this landscape where the failure mode is safe. Making *all* retrieval paths express
calibrated confidence — "I found a page that looks relevant but cannot ground the number" —
is unsolved and arguably the highest-leverage reliability problem (F4, F7).

**O5. Sub-document, cross-modal grounding.** Page-level retrieval + MLLM readout gives citations
at page granularity at best. Region-level relevance (arXiv:2512.02660) and cell/branch-level
grounding for tables/code need to become the default provenance unit for auditable systems.

**O6. Temporal-structure-preserving retrieval.** Retrieval units that carry ordering and
causality (video, meetings, logs, git history) rather than i.i.d. chunks; graph/storyline
approaches (Vgent, SVAgent) are point solutions, not a general abstraction (F9).

**O7. Index lifecycle & embedding versioning.** Re-index-the-world on every model upgrade is
untenable at multimodal scale (F5). Open: compatibility layers, dual-encoding transitions,
representation-agnostic late-interaction contracts (MetaEmbed's flexible budgets are a hint).

**O8. Adversarial robustness of perceptual indexes.** Poisoning defenses, index sanitization,
and provenance verification for pixel/audio-space retrieval barely exist (F10).

**O9. Retrieval-as-tool vs retrieval-as-pipeline.** The agentic turn (grep debates, MCP code
graphs, coarse-to-fine visual agents) implies the framework primitive should be an *iterable,
inspectable search tool with explicit state*, not a one-shot top-k function. What the optimal
tool-surface is (operators? cursors? relevance feedback? cost meters exposed to the agent?) is
an open design question with almost no controlled research (F8).

**O10. Evaluation that resists saturation.** Workflow-level, contamination-resistant,
annotation-audited benchmarks (Spider 2.0-style; ViDoRe V2-style living benchmarks; T²-RAGBench's
context-independence discipline) need multimodal, cross-source analogs — especially for the
unified KB+API+DB setting where no benchmark currently exists.

---

## Bibliography

Vision-native document retrieval
- ColPali: Efficient Document Retrieval with Vision Language Models — arXiv:2407.01449 (2024). https://arxiv.org/abs/2407.01449
- DSE: Unifying Multimodal Retrieval via Document Screenshot Embedding — Ma et al. — EMNLP 2024 — arXiv:2406.11251. https://arxiv.org/abs/2406.11251
- VisRAG: Vision-based RAG on Multi-modality Documents — Yu et al. — arXiv:2410.10594 (2024). https://arxiv.org/abs/2410.10594
- M3DocRAG — arXiv:2411.04952 (2024). https://arxiv.org/abs/2411.04952 ; project: https://m3docrag.github.io/
- VDocRAG — Tanaka et al. — CVPR 2025 — arXiv:2504.09795. https://arxiv.org/abs/2504.09795
- ViDoRe Benchmark V2 — Macé, Loison, Faysse — arXiv:2505.17166 (2025). https://arxiv.org/abs/2505.17166
- Reproducibility, Replicability, and Insights into Visual Document Retrieval with Late Interaction — Qiao et al. — arXiv:2505.07730 (2025). https://arxiv.org/abs/2505.07730
- Towards Storage-Efficient Visual Document Retrieval (Light-ColPali) — Ma et al. — ACL 2025 Findings — arXiv:2506.04997. https://arxiv.org/abs/2506.04997
- Hierarchical Patch Compression for ColPali — arXiv:2506.21601 (2025). https://arxiv.org/abs/2506.21601
- Visual RAG Toolkit: Training-Free Pooling and Multi-Stage Search — arXiv:2602.12510 (2026). https://arxiv.org/abs/2602.12510
- Beyond Patch Aggregation: 3-Pass Pyramid Indexing — arXiv:2511.21121 (2025). https://arxiv.org/abs/2511.21121
- Spatially-Grounded Document Retrieval via Patch-to-Region Relevance Propagation — arXiv:2512.02660 (2025). https://arxiv.org/abs/2512.02660
- Document Screenshot Retrievers are Vulnerable to Pixel Poisoning Attacks — arXiv:2501.16902 (2025). https://arxiv.org/abs/2501.16902
- Any Information Is Just Worth One Single Screenshot (VisIR) — arXiv:2502.11431 (2025). https://arxiv.org/abs/2502.11431
- M3DR: Universal Multilingual Multimodal Document Retrieval — arXiv:2512.03514 (2025). https://arxiv.org/abs/2512.03514
- CausalEmbed: Auto-Regressive Multi-Vector Generation — arXiv:2601.21262 (2026). https://arxiv.org/abs/2601.21262
- Index Light, Reason Deep: Deferred Visual Ingestion — arXiv:2602.14162 (2026). https://arxiv.org/abs/2602.14162
- VisRAG 2.0: Evidence-Guided Multi-Image Reasoning — arXiv:2510.09733 (2025). https://arxiv.org/abs/2510.09733
- Doc-V*: Coarse-to-Fine Interactive Visual Reasoning — arXiv:2604.13731 (2026). https://arxiv.org/abs/2604.13731
- UniDoc-RL — arXiv:2604.14967 (2026). https://arxiv.org/abs/2604.14967
- VLD-RAG: Agentic Vision-Language RAG — arXiv:2607.24748 (2026). https://arxiv.org/abs/2607.24748
- Late Interaction Retrieval guide (ColBERT/ColPali/ColQwen) — Mixpeek (practitioner). https://mixpeek.com/guides/late-interaction-retrieval
- ColPali Methodology topic page — EmergentMind (secondary). https://www.emergentmind.com/topics/colpali-methodology

Surveys & multimodal-RAG failure analysis
- Ask in Any Modality: Comprehensive Survey on Multimodal RAG — ACL 2025 Findings — arXiv:2502.08826. https://github.com/llm-lab-org/Multimodal-RAG-Survey
- A Survey of Multimodal Retrieval-Augmented Generation — arXiv:2504.08748 (2025). https://arxiv.org/abs/2504.08748
- Scaling Beyond Context: Survey of Multimodal RAG for Document Understanding — Gao et al. — ACL 2026 — arXiv:2510.15253. https://arxiv.org/abs/2510.15253
- When RAG Hurts: Attention Distraction in Retrieval-Augmented LVLMs — An et al. — arXiv:2602.00344 (2026). https://arxiv.org/abs/2602.00344
- Mitigating Hallucination on Hallucination in RAG via Ensemble Voting — arXiv:2603.27253 (2026). https://arxiv.org/abs/2603.27253
- Fix Before Search: Agentic Query Visual Pre-processing in MRAG — arXiv:2602.13179 (2026). https://arxiv.org/abs/2602.13179
- Utility-Oriented Visual Evidence Selection for MRAG — arXiv:2605.13277 (2026). https://arxiv.org/abs/2605.13277
- BayesRAG: Probabilistic Mutual Evidence Corroboration — arXiv:2601.07329 (2026). https://arxiv.org/abs/2601.07329
- MG²-RAG: Multi-Granularity Graph for MRAG — arXiv:2604.04969 (2026). https://arxiv.org/abs/2604.04969
- Text-Based vs Image-Based Retrieval in MRAG Systems — arXiv:2511.16654 (2025). https://arxiv.org/abs/2511.16654
- Multimodal RAG in 2026 (production pathologies) — BigDataBoutique blog (practitioner). https://bigdataboutique.com/blog/multimodal-rag-retrieval-over-images-pdfs-and-text

Tables & text+table
- TableRAG: Million-Token Table Understanding — NeurIPS 2024 — arXiv:2410.04739. https://arxiv.org/abs/2410.04739
- T²-RAGBench — Strich et al. — EACL 2026 — arXiv:2506.12071. https://arxiv.org/abs/2506.12071
- Table Question Answering in the Era of LLMs: Survey — arXiv:2510.09671 (2025). https://arxiv.org/abs/2510.09671
- Improving Table Retrieval with Question Generation from Partial Tables — arXiv:2508.06168 (2025). https://arxiv.org/abs/2508.06168
- Awesome-Tabular-LLMs (paper collection). https://github.com/SpursGoZmy/Awesome-Tabular-LLMs

Text-to-SQL, semantic layers, hybrid structured retrieval
- Spider 2.0 — Lei et al. — arXiv:2411.07763 (2024). https://arxiv.org/abs/2411.07763
- Text-to-SQL Benchmarks are Broken: Annotation Errors — Jin et al. — CIDR 2026. https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf
- Text-to-SQL Benchmarks for Enterprise Realities — OpenReview. https://openreview.net/forum?id=gXkIkSN2Ha
- Semantic Layer vs Text-to-SQL: 2026 Benchmark — dbt Labs blog (vendor). https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026
- Semantic Layers for Reliable LLM-Powered Data Analytics — arXiv:2604.25149 (2026). https://arxiv.org/abs/2604.25149
- Your Data Model Is the Semantic Layer — MotherDuck blog (practitioner). https://motherduck.com/blog/bird-bench-and-data-models/
- ReViSQL: Achieving Human-Level Text-to-SQL — arXiv:2603.20004 (2026). https://arxiv.org/abs/2603.20004
- Agent Bain vs. Agent McKinsey: Business Text-to-SQL Benchmark — arXiv:2510.07309 (2025). https://arxiv.org/abs/2510.07309
- Unified Relational-Semantic Execution Framework — arXiv:2604.02444 (2026). https://arxiv.org/abs/2604.02444
- Bridging OLAP and RAG — arXiv:2601.03748 (2026). https://arxiv.org/abs/2601.03748
- A Survey of LLM × DATA — arXiv:2505.18458 (2025). https://arxiv.org/abs/2505.18458
- Hybrid Relational-Vector Systems topic page — EmergentMind (secondary; source for BlendSQL/Text2VectorSQL mentions). https://www.emergentmind.com/topics/hybrid-relational-vector-unstructured-systems

Code retrieval for agents
- cAST: Structural Chunking via AST — EMNLP 2025 Findings — arXiv:2506.15655. https://arxiv.org/abs/2506.15655
- RepoGraph — Ouyang et al. — ICLR 2025 — arXiv:2410.14684. https://arxiv.org/abs/2410.14684
- Agentless — GitHub. https://github.com/OpenAutoCoder/Agentless
- Why Grep Beat Embeddings in Our SWE-Bench Agent (Augment / C. Flaherty via J. Liu, Sept 2025). https://jxnl.co/writing/2025/09/11/why-grep-beat-embeddings-in-our-swe-bench-agent-lessons-from-augment/
- Code Isn't Memory: A Structural Codebase Index Inside a Coding Agent — arXiv:2606.22417 (2026). https://arxiv.org/abs/2606.22417
- Codebase-Memory: Tree-Sitter KGs for LLM Code Exploration via MCP — arXiv:2603.27277 (2026). https://arxiv.org/abs/2603.27277
- RANGER: Graph-Enhanced Repository Retrieval — arXiv:2509.25257 (2025). https://arxiv.org/abs/2509.25257
- LARGER: Lexically Anchored Repository Graph Exploration — arXiv:2605.16352 (2026). https://arxiv.org/abs/2605.16352
- Context-Augmented Code Generation Using Programming Knowledge Graphs — arXiv:2601.20810 (2026). https://arxiv.org/abs/2601.20810
- Demystifying LLM-Based Software Engineering Agents — FSE 2025. https://lingming.cs.illinois.edu/publications/fse2025.pdf
- Awesome Repo-Level Code Generation (collection). https://github.com/YerbaPage/Awesome-Repo-Level-Code-Generation

Video & audio
- VideoRAG: RAG over Video Corpus — Jeong et al. — ACL 2025 Findings — arXiv:2501.05874. https://github.com/starsuzi/VideoRAG
- VideoRAG: RAG with Extreme Long-Context Videos — arXiv:2502.01549 (2025).
- Video-RAG: Visually-aligned Retrieval-Augmented Long Video Comprehension — arXiv:2411.13093 (2024). https://arxiv.org/abs/2411.13093
- Vgent: Graph-based Retrieval-Reasoning for Long Video — arXiv:2510.14032 (2025). https://arxiv.org/abs/2510.14032
- E-VRAG — arXiv:2508.01546 (2025). https://arxiv.org/abs/2508.01546
- AdaVideoRAG — arXiv:2506.13589 (2025). https://arxiv.org/abs/2506.13589
- SVAgent: Storyline-Guided Long Video Understanding — arXiv:2604.05079 (2026). https://arxiv.org/abs/2604.05079
- WavRAG — ACL 2025 — arXiv:2502.14727. https://arxiv.org/abs/2502.14727
- SpeechRAG (Speech RAG without ASR) — ICASSP 2025 — arXiv:2412.16500. https://arxiv.org/abs/2412.16500
- PlanRAG-Audio — arXiv:2605.20414 (2026). https://arxiv.org/abs/2605.20414

Charts & figures
- mChartQA — arXiv:2404.01548 (2024). https://arxiv.org/abs/2404.01548
- Multimodal Information Fusion for Chart Understanding: Survey — arXiv:2602.10138 (2026). https://arxiv.org/abs/2602.10138
- LongChart VQA — arXiv:2608.01328 (2026). https://arxiv.org/abs/2608.01328
- FCMR: Financial Cross-Modal Multi-Hop Reasoning — arXiv:2412.12567 (2024). https://arxiv.org/abs/2412.12567
- ChartQAPro (2025) — seen referenced; ID not verified this session.

Embedding models & benchmarks
- VLM2Vec / MMEB (ICLR 2025), MMEB-V2 (TMLR 2026), MMEB-V3 (COLM 2026) — GitHub. https://github.com/TIGER-AI-Lab/VLM2Vec
- MetaEmbed: Flexible Late Interaction at Test Time — arXiv:2509.18095 (2025). https://arxiv.org/abs/2509.18095
- UniME-V2: MLLM-as-a-Judge Embedding Learning — arXiv:2510.13515 (2025). https://arxiv.org/abs/2510.13515
- MegaPairs — arXiv:2412.14475 (2024). https://arxiv.org/abs/2412.14475
- MMEmb-R1 — arXiv:2604.06156 (2026). https://arxiv.org/abs/2604.06156
- MMLongEmbed — arXiv:2606.14747 (2026). https://arxiv.org/abs/2606.14747
- MVEB: Massive Video Embedding Benchmark — arXiv:2606.14958 (2026). https://arxiv.org/abs/2606.14958
- jina-embeddings-v4 — Jina AI (vendor). https://jina.ai/models/jina-embeddings-v4/
- Best Embedding Model for RAG 2026 — Milvus blog (vendor/practitioner benchmark). https://milvus.io/blog/choose-embedding-model-rag-2026.md
- Which Embedding Model Should You Actually Use in 2026? — C. Zhang (practitioner). https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html
- DocRetriever: Plug-and-Play Multimodal Document Retrieval — arXiv:2605.30027 (2026). https://arxiv.org/abs/2605.30027
