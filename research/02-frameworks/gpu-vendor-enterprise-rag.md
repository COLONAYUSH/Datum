# Regulated / GPU-Vendor Enterprise RAG Stacks: NVIDIA NeMo Retriever & IBM watsonx (Granite / Docling)

> Framework-autopsy dossier, compiled and consolidated **2026-08-05**. Steelman first, then dissect.
> Every issue carries a link/ID plus a gist or quote, and a label:
> `documented-recurring` / `single-anecdote` / `architectural-inference`.

**Method note (stated up front, because it shapes what evidence exists below).** The session's keyword-search budget was exhausted upstream (200/200 WebSearch calls) before the first query in this pass returned. All evidence was therefore gathered by **direct fetch of primary sources**: vendor documentation, GitHub REST/search API (`gh`), raw repository files, the HuggingFace model API, arXiv, NVD, a reader proxy for JS-rendered IBM Documentation pages, and the HN Algolia API. This biases the dossier toward primary sources (docs, repos, issue trackers, model cards) and away from blog/forum commentary. Two specific blockers: `ibm.com/docs` and `cloud.ibm.com/docs` are JS-rendered and return 403/blank HTML to programmatic fetch (worked around via reader proxy — see [dx-docs](#dx-docs)), and Reddit's public JSON/pullpush endpoints were unavailable, so Reddit sentiment is not represented.

---

## Identity & adoption

Two very different animals filed under one heading — and the difference is the finding.

### NVIDIA NeMo Retriever + NIM RAG stack

| Attribute | Value |
|---|---|
| Vendor | NVIDIA |
| What it is | A family of **NIM microservices** (containerised GPU inference services) for document extraction, embedding, and reranking, plus reference **Blueprints** that wire them into a RAG application |
| Core repo | [`NVIDIA/NeMo-Retriever`](https://github.com/NVIDIA/NeMo-Retriever) — renamed from `NVIDIA/nv-ingest` in 2026. **2,958 stars**, **233 open issues**, Apache-2.0 pipeline code; releases CalVer 24.08 (Sept 2024) → 26.05 |
| Blueprint repos | [`NVIDIA-AI-Blueprints/rag`](https://github.com/NVIDIA-AI-Blueprints/rag) — 723 stars, 309 forks, 488 commits, Apache-2.0; [`NVIDIA-AI-Blueprints/aiq-research-assistant`](https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant) — 824 stars, 243 forks, Apache-2.0 |
| Model weights | Published on HF under the **NVIDIA Open Model License** (+ Llama 3.2 Community License for Llama-derived models). `llama-nemotron-embed-1b-v2`: **827,762 downloads**; `llama-nemotron-rerank-1b-v2`: **765,118**; `Nemotron-3-Embed-1B-BF16`: 455,847; `llama-nemotron-embed-vl-1b-v2`: 79,239 |
| Production licensing | **NVIDIA AI Enterprise (NVAIE)**, licensed **per GPU**: "A software license is required for every GPU installed on the server or workstation that will host any software that is included with NVIDIA AI Enterprise." Multi-GPU cards need one license each; activation uses the **GPU serial number**. Annual subscription / cloud-hourly / perpetual (perpetual carries a mandatory 5-year support attach). ([licensing guide](https://docs.nvidia.com/ai-enterprise/planning-resource/licensing-guide/latest/licensing.html)) |
| Pricing signal | **Not published.** Product page and FAQ describe tiers without numbers. The circulated community figure is ~**$4,500/GPU/year** (HN comment, Aug 2024: "It's $4500 per GPU license… Last year Nvidia SW run rate was $1b, this year it's $2b according to CFO" — [HN 41389079](https://news.ycombinator.com/item?id=41389079)). **Flagged low-credibility for the exact number**; the *existence* of per-GPU paid production licensing is confirmed by NVIDIA's own licensing guide |
| Distribution | NGC (`nvcr.io`), NVIDIA API Catalog (`build.nvidia.com`) hosted endpoints, Helm, NIM Operator, Red Hat OpenShift (added 2.6.0), and OEM racks — **Dell AI Factory with NVIDIA**, **HPE Private Cloud AI** |
| Momentum (2026) | High and churning. Blueprint 2.3.2 (2025-12-25) → 2.4.0 (2026-02-20) → 2.5.0 (2026-03-17) → 2.5.1 (2026-04-29) → 2.6.0 (2026-05-30). README: the team is "phasing out legacy ingestion APIs and simplifying the dependencies" |

### IBM watsonx (watsonx.ai + Orchestrate + Granite + Docling)

| Attribute | Value |
|---|---|
| Vendor | IBM. **Docling is now hosted by the LF AI & Data Foundation**, originated at IBM Research Zurich |
| What it is | Not one RAG framework. A managed platform (`watsonx.ai` vector index / AutoAI for RAG / Prompt Lab), an agent platform (`watsonx Orchestrate`), a model family (Granite embeddings, Granite-Docling VLM), and an OSS parser (Docling) |
| Platform launch | watsonx announced 2023-05-09 (watsonx.ai / .data / .governance + Assistant/Orchestrate) |
| Docling | [`docling-project/docling`](https://github.com/docling-project/docling) — **64,280 stars**, 4.6k forks, **MIT**, OpenSSF Best Practices badge, **883 open / 1,055 closed issues**, 201 tagged releases to **v2.118.0** (2026-08-03), releasing ~twice weekly. Companion [`docling-serve`](https://github.com/docling-project/docling-serve): 1,720 stars, MIT |
| Granite models | `ibm-granite/granite-docling-258M`: **512,696 downloads / 1,236 likes**, Apache-2.0. `granite-embedding-311m-multilingual-r2`: ModernBERT, `max_position_embeddings: 32768`, Apache-2.0, 47,567 downloads. `granite-embedding-125m-english`: 74,486. `granite-embedding-278m-multilingual`: 42,483. `granite-embedding-english-r2` (149M, 8k ctx) **deliberately excludes MS-MARCO because of its non-commercial license**, training on IBM-curated commercial-safe data |
| Deployment surfaces | SaaS on IBM Cloud and AWS, **AWS GovCloud (US)**, on-prem via **IBM Software Hub / Cloud Pak for Data**, local **Developer Edition** — each with an explicitly published *feature-parity gap table* |
| Momentum (2026) | Docling: very high. watsonx.ai **retrieval primitives: stalled** (see [R1](#retrieval-quality)) |
| Retreat signal | **InstructLab is archived.** [`instructlab/instructlab`](https://github.com/instructlab/instructlab) is `archived: true`, last push 2026-03-30, 1,420 stars; README carries a **2025-09-02** notice splitting the project up, with components relocated to `Red-Hat-AI-Innovation-Team/sdg_hub` and `training_hub` |
| Adoption evidence vs marketing | IBM reports a generative-AI "book of business" **>$7.5B inception-to-date** (Q2 2025 earnings) but discloses **no watsonx-specific revenue and no software/consulting split**; named public deployments (ESPN Fantasy Football, Wimbledon, Grammys, Wind Tre) are showcase/media accounts, not deep RAG case studies |

**Adoption asymmetry worth flagging.** On HuggingFace, NVIDIA's retrieval encoders out-download IBM's by roughly 10–20× (827k / 765k vs 42k–74k). IBM's genuine open-source hit is **document parsing** (Docling 64k stars; granite-docling 512k downloads) — *not retrieval*. That cuts directly against IBM's positioning of watsonx as the regulated-enterprise **retrieval** platform.

---

## Retrieval-pipeline architecture

### NVIDIA: retrieval decomposed into GPU-billable microservices

The architecture is unusually legible because every stage is a separately deployed container with an OpenAI-compatible HTTP API. Composite of the [repo README](https://github.com/NVIDIA/NeMo-Retriever), [extraction docs](https://docs.nvidia.com/nemo/retriever/latest/extraction/overview/), and blueprint 2.6.0 [support matrix](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/support-matrix.md) / [release notes](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/release-notes.md):

```
Documents
  │
  ├─► NeMo Retriever Library (ex nv-ingest) — page split/parallelize, then fan out to NIMs:
  │      • nemotron-page-elements-v3      (YOLOX-derived object detection: text/table/chart regions)
  │      • nemotron-table-structure-v1    (table structure recognition)
  │      • nemotron-graphic-elements-v1   (charts / infographics)
  │      • nemotron-ocr-v1                (OCR; replaced PaddleOCR as default in 2.6.0)
  │      • Nemotron Parse                 (optional end-to-end VLM parse: C-RADIO features + mBART)
  │      • VLM captioning                 (optional; OFF by default)
  │
  ├─► Contextualize → normalized JSON metadata schema
  │      (2.4.0 reserved the field names `type`, `subtype`, `location` for internal use)
  │
  ├─► Embedding NIM: llama-nemotron-embed-vl-1b-v2 (default since 2.6.0)
  │      or llama-nemotron-embed-1b-v2 (text-only); 8192-token ctx; Matryoshka dims 384/512/768/1024/2048
  │
  ├─► Vector DB: Elasticsearch (blueprint default since 2.6.0) | Milvus + cuVS GPU index
  │      | LanceDB (new library path).  Object store: SeaweedFS (was MinIO)
  │
  └─► Query: hybrid dense+sparse (weighted) → Reranking NIM (llama-nemotron-rerank-1b-v2,
         or VLM reranker opt-in) → LangChain/LangGraph rag-server → LLM NIM
         (nemotron-3-super-120b-a12b) → optional NeMo Guardrails, optional self-reflection
```

Three properties define the design:

1. **Every retrieval stage is a GPU workload.** Extraction is 4–6 GPU-resident vision models. Embedding and reranking are GPU NIMs. Indexing is optionally GPU (cuVS). NVIDIA's own blog frames indexing as "up to 7x better indexing throughput" *because* it moved to the GPU. Retrieval, classically a CPU/IO-bound problem, has been re-architected as an accelerator-bound one.
2. **Configuration lives in container/Helm/env space, not code.** Behaviour is driven by env vars (`APP_NVINGEST_EXTRACTIMAGES`, `ENABLE_VLM_INFERENCE`, `APP_VLM_THINKING_TOKEN_BUDGET`, `VLM_TO_LLM_FALLBACK`, `VLM_FILTER_THINK_TOKENS`) and Helm values files. "Library mode" is a thin wrapper over the same services.
3. **The blueprint is the product surface, not a library.** There is no stable public Python abstraction for "a retriever"; there is a reference application you fork, with orchestration logic living in LangChain glue.

**Stated system requirements are extraordinary for a "foundational" pipeline** (primary sources: blueprint `docs/support-matrix.md`, extraction [prerequisites](https://docs.nvidia.com/nemo/retriever/latest/extraction/prerequisites-support-matrix/)):

- Docker self-hosted default: **3× H100 / 3× B200 / 3× RTX PRO 6000** — the default LLM alone takes 2 GPUs at FP8 TP2.
- Kubernetes/Helm default: **8× H100-80GB** (5× with MIG), plus "one additional GPU for each optional service that you enable, such as VLM generation, VLM captioning, VLM reranking, Nemotron Parse, or audio processing."
- Ingestion library alone: **≥256 GB RAM, ≥32 CPU cores, ≥24 GB VRAM, ~150 GB disk**.
- Blueprint disk: **≥200 GB**, of which "NIM model downloads and caching (largest component, ~100-150GB)."
- OS/driver floor: **Ubuntu 22.04 only**; GPU driver ≥ 560; CUDA ≥ 12.9.

### IBM: parser-first, model-frugal, product-stitched

There is no single IBM RAG pipeline. There are at least three, with different capabilities.

**(a) Docling (OSS, MIT) — the ingestion heart.** `DocumentConverter` maps each format to a backend and runs a pipeline of small specialist models — **DocLayNet-derived layout model** (now `docling-layout-heron`) + **TableFormer** table-structure recognition + optional OCR engines — into a unified **DoclingDocument**, with serializers (Markdown/HTML/JSON) and chunkers (**HybridChunker**) as subclassable extension points ([architecture](https://docling-project.github.io/docling/concepts/architecture/), [tech report](https://arxiv.org/abs/2408.09869)). Runs on commodity CPUs; GPU optional. Granite-Docling-258M (2025) added a compact VLM path.

Module layout (`docling/`): `backend/`, `chunking/`, `cli/`, `datamodel/`, `models/`, `pipeline/`, `service_client/`, `experimental/`, `document_converter.py`, `document_extractor.py`. Note that `pipeline/` contains **three parallel PDF pipelines simultaneously** — `legacy_standard_pdf_pipeline.py`, `standard_pdf_pipeline.py`, `threaded_standard_pdf_pipeline.py` — plus `vlm_pipeline.py`, `extraction_vlm_pipeline.py`, `asr_pipeline.py`, `video_pipeline.py`; and `chunking/` contains only `__init__.py` (chunkers live in `docling-core`). **Docling does no retrieval at all**: it emits a document representation and hands off to LangChain / LlamaIndex / Haystack / CrewAI.

**(b) watsonx.ai vector index / AutoAI for RAG.** From the [RAG pattern doc](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-rag.html?context=wx) and [vector index settings](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/vector-index-settings.html?context=wx):

```
Grounding docs ──► text classification/extraction API ──► chunking (size/overlap)
   ──► platform-hosted embedding model ──► vector store:
          • "In memory" Chroma  (auto-created, temporary, project-scoped)
          • Elasticsearch        (customer-provisioned connection)
          • watsonx.data Milvus  (customer-provisioned)
        + explicit field mapping: Vector query | Document name | Text | Page number | Document url
   ──► retrieve ──► optional rerank (cross-encoder/ms-marco-minilm-l-12-v2)
   ──► foundation model
```

**AutoAI for RAG** layers hyper-parameter optimisation over that pipeline: "avoids testing all RAG configuration options (for example, it avoids a grid search) by using a hyper-parameter optimization algorithm," bounded at "**Up to 20 files or folders** for the document collection… For larger document collections, AutoAI runs the experiment with a **sample of 1 GB**" and "up to **25 question and answer pairs** to evaluate patterns," in a fixed "Large: 8 CPU and 32 GB RAM" environment. It publishes an itemised cost model (100 pages + 25 QA records ⇒ **3,267,000 tokens**).

**(c) watsonx Assistant / Orchestrate — retrieval as an agent tool.** Conversational search wires an assistant to a search backend: an Elasticsearch-based **watsonx Discovery** deployment or a custom search integration. The RAG pipeline is therefore assembled by **stacking separately priced IBM products** (Assistant/Orchestrate plan + Discovery/Elasticsearch + watsonx.ai inference), with watsonx.governance as the audit layer.

**The architectural contrast, stated plainly:** *NVIDIA verticalises retrieval into one GPU-dense pipeline it controls end to end and bills per accelerator. IBM horizontalises it into a parser it gave away, an encoder API it barely maintains, and a vector store it asks you to provision.*

---

## Agentic integration

### NVIDIA

- **Agentic RAG (blueprint 2.6.0, May 2026)** — plan-and-execute with streaming, verification, and query rewriting, built on **LangGraph/LangChain**, not an NVIDIA abstraction. The published [limitations](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/agentic-rag.md) are candid and highly informative:
  - "Latency and LLM-call count exceed the standard chain."
  - "The agentic path does **not** use NeMo Guardrails, Self-Reflection, Query Decomposition, or VLM Inference."
  - "Verification runs once; there is no nested verification loop."
  - "Tasks in a plan run at one parallel level; there is **no DAG or depends-on construct**."
  - "Response metadata that is specific to the Standard RAG single-pass pipeline can be omitted or returned empty for Agentic RAG."
- **MCP** — the blueprint exposes RAG via an MCP server (2.4.0) plus an OpenAI-compatible search endpoint. Open FEA: "Enable re-ranker with MCP tools" (`NeMo-Retriever` #2344).
- **AI-Q Research Assistant** — orchestration node → intent classification → shallow agent (tool-augmented, cited) or deep agent (planning + concurrent workers), on **NeMo Agent Toolkit 1.8.0 + LangChain Deep Agents**, with web search (Tavily/Exa/You.com/Nimble) and paper search (Serper/SerpAPI/SearchAPI). Its security posture, quoted verbatim from the current `main` README (re-verified 2026-08-05): the roadmap lists as **unchecked** "**MCP Authentication:** Implement secure login/auth for MCP connections" and "**Skills & Sandboxing:** Support custom skills within isolated environments"; "End users are **encouraged to add** [NeMo Guardrails] and additional prompt content filtering to the blueprint. Guardrails **will be native in upcoming release**"; and "The AI-Q Blueprint doesn't currently generate any code that may require sandboxing." So authenticated MCP, native guardrails, and sandboxing are all roadmap, not shipped.
- **Agent-operated infrastructure** — the blueprint repo ships `AGENTS.md`, `CLAUDE.md`, `.openclaw/`, `skills/`, `skill-eval/`. 2.5.0: "agentic skills support: the `rag-blueprint` skill enables AI coding assistants (Claude Code, Cursor, Codex, etc.) to deploy, configure, troubleshoot, and manage the RAG Blueprint autonomously." 2.6.0 added an "OpenClaw plugin for agent-driven deploy/configure/eval workflows." This is the most genuinely forward-looking thing in either stack: **the operator is expected to be an agent, with an eval harness attached.**

### IBM

- **watsonx Orchestrate** is the agentic surface: agent builder, prebuilt domain agents, tool catalog, **MCP toolkits**, **A2A agents**, agentic workflows with parallel branches and **human-in-the-loop review**, an "agentic control plane" for alerts/incidents, and agent analytics.
- Retrieval appears as conversational search / document-processing *skills* invoked by agents, not as a first-class retrieval graph.
- **Agentic capability is deployment-dependent.** The [feature-parity doc](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=notes-feature-parity-across-deployments) classifies AWS SaaS, IBM Cloud SaaS, **AWS GovCloud (US)**, **IBM Software Hub (on-prem)**, and Developer Edition as full / partial / no support *per feature*, and warns "Some features can be configured only through ADK CLI, as they are not available through the user interface." For buyers who *must* run on-prem or GovCloud, the agentic feature set is a strict subset — and the doc exists because that subset repeatedly surprises people.
- Docling is the de-facto document tool for many *third-party* agent stacks (MCP server included) — IBM's agentic mindshare in retrieval is via the OSS component, not the platform.
- **Readiness verdict.** Both stacks treat agents as an application layer bolted *beside* the retrieval substrate rather than beneath it. Neither exposes retrieval as a stateful, ACL-aware, permission-propagating agent tool. NVIDIA's unauthenticated MCP endpoint in an *enterprise* blueprint, and IBM's document-processing→HITL flow breaking in embedded chat, are the emblematic failures on each side.

---

## Strengths (steelman)

**NVIDIA NeMo Retriever — the strongest case:**

1. **It treats multimodal PDF ingestion as a real engineering problem, not a `pdf.extract_text()` call.** Page-element detection → table/chart/infographic specialists → OCR → schema'd JSON is the most explicit productionization of "PDFs are images, not text" among major stacks (audio and video included). NVIDIA's own ablations show the payoff: on ViDoRe-v3 Pharmaceuticals, text-LLM → VLM pipeline lifts accuracy 0.759 → 0.849; Industrial 0.677 → 0.733; Physics 0.840 → 0.910.
2. **Genuinely strong, genuinely open-weighted retrieval encoders.** `llama-nemotron-embed-1b-v2`: 8192-token context, **Matryoshka dims (384–2048)**, 26 evaluated languages, "ready for commercial use" under the NVIDIA Open Model License, 827k HF downloads. Dynamic embedding size is the right answer to vector-store cost and is under-copied elsewhere. Component-level leaderboard wins are real: **NV-Embed topped MTEB** (69.32 avg over 56 tasks, June 2024; runner-up 68.28), and `llama-nemoretriever-colembed-3b-v1` ranked **#1 on ViDoRe V1 (0.9100 nDCG@5) / V2 (0.6352) / MTEB-VDR (0.8315)** in June 2025.
3. **Honest, unusually detailed operational documentation.** Published first-deploy timings (Docker 15–30 min; **Helm 60–70 min**, of which 40–50 min is NIM cache download, "no progress bar visible"), a 22-item "All Known Issues" register, per-GPU-family caveats, and MIG guidance. Most OSS RAG frameworks publish nothing comparable.
4. **Deployment engineering OSS frameworks ignore.** Helm charts, NIM Operator, OpenShift routes/SCCs, MIG slicing, OpenTelemetry tracing with Grafana dashboards, nightly CVE-scan tracking, air-gap- capable containers, API-stable production branches and LTS branches with enterprise SLAs. This is the FIPS-adjacent / audit / support-contract requirements list LangChain and LlamaIndex never had to satisfy.
5. **A published evaluation harness.** `scripts/eval/`, RAGAS notebooks, seven public datasets, documented judge model, and dedicated `agentic_*` Prometheus metrics — more eval transparency than most OSS frameworks, even though the methodology is circular (see [E1](#evaluation-observability)).
6. **Agent-operated infrastructure as a shipped feature**, not a demo (skills, `AGENTS.md`, OpenClaw plugin, `skill-eval/`).

**IBM watsonx / Granite / Docling — the strongest case:**

1. **Docling is the best thing either vendor produced, and IBM gave it away.** MIT, 64k stars, OpenSSF Best Practices badge, LF AI & Data governance, runs fully locally for "sensitive/air-gapped environments," ships an MCP server and a REST service (`docling-serve`, 1.7k stars), and integrates with every major OSS RAG framework. `granite-docling-258M` at 512k downloads / 1,236 likes is real adoption, not a press release. Independent developer assessment quoted by IBM Research: "The output quality is the best of all the open-source solutions."
2. **Regulated-industry surface area OSS frameworks do not have**: AWS GovCloud (US), on-prem IBM Software Hub, published regulatory-compliance and licences-and-entitlements pages, a known-issues register with a per-issue **"Workaround available: Yes/No"** column, named support escalation paths, and watsonx.governance as an audit layer.
3. **License-clean training data as a product feature.** `granite-embedding-english-r2` deliberately **excludes MS-MARCO because of its non-commercial license**, training on IBM-curated commercial-safe corpora. That is a differentiated, regulated-industry answer to "can I get sued for my embeddings?" — a posture no popular OSS embedding recipe takes.
4. **AutoAI for RAG is a real idea, honestly costed.** Automated HPO over chunking / embedding / retrieval depth / LLM choice, with a published token-and-CUH cost model, is more evaluation rigour than most teams ever apply by hand.
5. **Small, fast, permissive, modern encoders.** `granite-embedding-311m-multilingual-r2` is a ModernBERT (`max_position_embeddings: 32768`), Apache-2.0, CPU-servable; `granite-embedding-english-r2` reports 59.5 MTEB-style avg / 53.1 BEIR at **149M params** with 8k context, beating `e5-base-v2` and `bge-base-en-v1.5` (IBM-reported, but MTEB is independently checkable). **This matters analytically: IBM's own line demonstrates that competitive retrieval quality does not require the GPU floor NVIDIA's architecture assumes.**
6. **Human-in-the-loop review as a documented workflow primitive** — the right shape for regulated review gates, even where the implementation is incomplete.

---

## Issues & failure modes

Severity: **critical** = blocks production or silently corrupts retrieval; **major** = significant cost / reliability / quality tax with workarounds; **minor** = friction.

### retrieval-quality

**R1. watsonx.ai's platform retrieval primitives are years behind IBM's own open models — and behind the state of the art.** *Severity: critical. Label: documented-recurring (vendor docs).* As of 2026-08-05 the [supported encoder models](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx) on watsonx.ai are:

| Model | Max input tokens | Dims |
|---|---|---|
| `ibm/granite-embedding-278m-multilingual` | **512** | 768 |
| `ibm/slate-125m-english-rtrvr-v2` | **512** | 768 |
| `ibm/slate-30m-english-rtrvr-v2` | **512** | 384 |
| `intfloat/multilingual-e5-large` | **512** | 1,024 |
| `sentence-transformers/all-minilm-l6-v2` | **128** | 384 — *"This model is deprecated and will be withdrawn on June 8, 2026"* |

And the **only** reranker offered is `cross-encoder/ms-marco-minilm-l-12-v2` (Microsoft, 512 tokens, **English only** — the language table states flatly: "Reranker models | English"). That is a community MS MARCO cross-encoder from the pre-LLM era, sold as the sole reranking option on a platform marketed to regulated multinationals. Meanwhile IBM's *own* `granite-embedding-311m-multilingual-r2` (ModernBERT, 32k positional capacity, Apache-2.0, published to HF) **is not in the platform roster at all**, and NVIDIA's comparable NIM offers 8192 tokens and 2048 dims. Consequences: on watsonx.ai you cannot embed a long contract clause, cannot rerank a French or Japanese corpus, and cannot use IBM's best encoder through IBM's own platform. This is also a structural insight — *when adding a model is a platform release event, the model roster rots.*

**R2. NVIDIA's own accuracy numbers show the fully GPU-accelerated stack still fails 30–50% of hard enterprise queries.** *Severity: major. Label: documented-recurring (vendor's own benchmark doc).* From [`docs/accuracy-benchmarks.md`](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/accuracy-benchmarks.md) (RAGAS NVIDIA Answer Accuracy, default config, LLM = `llama-3.3-nemotron-super-49b-v1.5`):

| Dataset | LLM, reasoning off | LLM, reasoning on | VLM, reasoning off | VLM, reasoning on |
|---|---|---|---|---|
| FinanceBench | 0.612 | 0.668 | 0.622 | **0.697** |
| KG-RAG | 0.569 | 0.593 | 0.596 | **0.643** |
| RAGBattlepacket | 0.812 | 0.818 | **0.867** | 0.842 |
| DC767 | 0.906 | 0.899 | **0.907** | 0.897 |
| HotpotQA | 0.672 | **0.676** | n/a | n/a |
| Google Frames | 0.486 | **0.597** | n/a | n/a |
| ViDoRe Finance-FR | 0.639 | 0.647 | 0.683 | **0.687** |

The multimodal + reasoning machinery buys real gains (+0.11 on Google Frames), but a table-heavy financial corpus still yields ~30% wrong answers and multi-hop ~40%. These are honest and unremarkable, and they are the most useful datapoint in either vendor's documentation — they undercut the surrounding marketing.

**R3. Cross-page and hierarchical document structure is lost by both stacks.** *Severity: major. Label: documented-recurring.*
- NVIDIA blueprint [#240](https://github.com/NVIDIA-AI-Blueprints/rag/issues/240) "[BUG]: QA of pdf cannot identify cross-page information" — open since 2026-01-20.
- Docling [#287](https://github.com/docling-project/docling/issues/287) "Identify table of contents for better chunking / Hierarchy Identification" — **open since 2024-11-09 with 44 comments** (~21 months, against a ~twice-weekly release cadence).
- Docling [#1023](https://github.com/docling-project/docling/issues/1023) "Export to markdown only contains H2 headers" — open since 2025-02-19, 26 comments. Heading-level collapse destroys exactly the signal hierarchical chunkers need.
- Also Docling [#960](https://github.com/docling-project/docling/issues/960) "Docling Produces Unreadable Text Output for PDFs" (**open** since 2025-02-13, 15 comments) and [#828](https://github.com/docling-project/docling/issues/828) "Hyperlinks not identified in PDFs" (**closed**, 21 comments) — both verified via the GitHub API. Both stacks invest heavily in *page-local* structure (tables, charts, layout) and comparatively little in *document-global* structure (section hierarchy, cross-page tables, entity continuity) — which is precisely where regulated documents (10-Qs, protocols, SOPs, technical orders) carry their meaning. **Hierarchy-aware chunking is the main reason to use a structural parser, and it is what these bugs undermine.**

**R4. Default-off multimodality silently degrades accuracy for non-PDF inputs (NVIDIA).** *Severity: major. Label: documented-recurring (vendor known-issues list).* "The accuracy of the pipeline is optimized for certain file types like `.pdf`, `.txt`, `.docx`. The accuracy may be poor for other file types supported by NeMo Retriever Library, **since image captioning is disabled by default**." And `APP_NVINGEST_EXTRACTIMAGES` default remains `False`. A user ingesting PPTX/XLSX gets quiet quality loss with no signal at query time.

**R5. IBM retrieval quality is model-card-only.** *Severity: minor. Label: architectural-inference.* Granite embedding numbers are IBM-reported; **watsonx Discovery / conversational search has no public retrieval-quality evaluation at all.** Closed-platform opacity means regulated buyers must trust claims they cannot audit or reproduce.

### evaluation-observability

**E1. NVIDIA's accuracy benchmarking has no external baseline and a self-selected judge.** *Severity: critical (for the credibility of every downstream claim). Label: architectural-inference from primary docs.* `accuracy-benchmarks.md` compares **only NVIDIA's own configuration ablations** — LLM vs VLM × reasoning on/off — across seven datasets. There is **no comparison against any competing pipeline** (no LlamaIndex, Haystack, Azure AI Search, Vertex, MinerU, or Docling baseline). The judge is chosen by NVIDIA's own leaderboard: "We chose `mistralai/Mixtral-8x22B-Instruct-v0.1` as the LLM judge, guided by performance on the [Judge's Verdict](https://huggingface.co/spaces/nvidia/judges-verdict) benchmark" — an NVIDIA-published benchmark. The metric is "the NVIDIA Answer Accuracy metric from RAGAS." So NVIDIA selects **the pipeline, the hardware, the metric, the judge model, and the judge-selection benchmark.** The result is internally useful and externally unfalsifiable.

**E2. The headline speed/efficiency claims are all vendor-measured and none independently replicated.** *Severity: major. Label: architectural-inference (the claims are documented; the absence of replication is the finding).* From NVIDIA's [developer blog](https://developer.nvidia.com/blog/nvidia-nemo-retriever-delivers-accurate-multimodal-pdf-data-extraction-15x-faster/): "15x throughput increase in multimodal data extraction" vs unnamed "open-source alternatives" (1× H100 SXM); "3x better embedding throughput"; "1.6x better reranking throughput"; "up to 7x better indexing throughput" (8× L4 vs CPU); "reducing storage requirements by 35x"; "50% fewer incorrect answers." Every number is NVIDIA-measured, on NVIDIA silicon, against unnamed baselines; the 35× storage figure is restated verbatim in the model card. **No independent replication of any of these figures was found.** The 7× indexing claim is structurally circular: GPU beats CPU at indexing because NVIDIA chose to move indexing to the GPU.

**E3. Agentic RAG returns empty/missing response metadata.** *Severity: major. Label: documented-recurring (vendor docs).* "Response metadata that is specific to the Standard RAG single-pass pipeline can be omitted or returned empty for Agentic RAG when it does not map cleanly to the multi-step agentic flow." Downstream evaluation, citation checking, and audit logging that depend on that metadata break exactly when you enable the mode you would most want to audit. The `agentic_*` Prometheus metrics are aggregate-only and live on a **separate** Grafana dashboard from standard RAG.

**E4. watsonx Orchestrate ships a known issue literally titled "Observability", with no workaround.** *Severity: major. Label: documented-recurring.* [Building tools known issues](https://www.ibm.com/docs/en/SSAVQO/about/knownissues/building-tools.html), at-a-glance table: "**Observability | Workaround available: No**." Also "A2A agents: User feedback count is not updated when Thumbs up/Thumbs down is selected | No." On a platform whose pitch is governed, auditable enterprise AI, the trace and feedback layer is a documented open defect.

**E5. AutoAI for RAG optimises against a 25-question test set.** *Severity: major. Label: documented-recurring (vendor docs).* "An experiment will use **up to 25 question and answer pairs** to evaluate patterns," over "up to 20 files or folders" (larger collections sampled to 1 GB). Selecting chunk size, embedding model, retrieval depth, and LLM by hyper-parameter optimisation against 25 questions is an overfitting machine, and the docs present the winner as "an optimized, **production-quality** RAG pattern."

### production-ops

**P1. Unbounded memory growth in ingestion — the same failure shape in both stacks, from four independent reporters.** *Severity: critical. Label: documented-recurring.*
- NVIDIA blueprint [#66](https://github.com/NVIDIA-AI-Blueprints/rag/issues/66) "[BUG]: nv-ingest service RAM continuously increases and eventually fails" — open since 2025-11-06: "during this procedure the memory used by `compose-nv-ingest-ms-runtime-1` is continuously increasing."
- Docling [#2209](https://github.com/docling-project/docling/issues/2209) "Memory leak in DoclingParseV2DocumentBackend — 13GB accumulation on repeated conversions" — **open since 2025-09-05**, 15 comments: "accumulates memory on repeated conversions and never releases it… can consume 10GB+ RAM in minutes" — on a **0.41 MB, 35-page PDF**.
- Docling [#2779](https://github.com/docling-project/docling/issues/2779) "Docling consumes all available memory and gets killed" — open since 2025-12-13; community guidance in-thread is "split pdfs and then send to docling," i.e. manual sharding as the memory strategy.
- Docling [#2788](https://github.com/docling-project/docling/issues/2788) "Potential memory leak in docling pdf conversion" — open, 14 comments. An **eleven-month-open severe leak in the default parse backend**, against ~2 releases per week, is the sharpest single indictment in this dossier. Batch ingestion — the only mode that matters for enterprise corpora — is the exact workload that trips it.

**P2. Ingestion hangs, deadlocks, and silent stalls.** *Severity: critical. Label: documented-recurring.*
- Blueprint [#181](https://github.com/NVIDIA-AI-Blueprints/rag/issues/181) "[BUG]: Ingestion hangs with errors in nv-ingest pod logs" — open since 2025-12-23.
- `NeMo-Retriever` [#1052](https://github.com/NVIDIA/NeMo-Retriever/issues/1052) "[BUG]: Deadlock (infinite loop) when paddle is not ready" — "Jobs hang indefinitely… client defaults to infinite retries; `submit_job` not gated by readiness… sessions can run for 30+ minutes with near-zero utilization… **no fail-fast or clear error**."
- `NeMo-Retriever` [#165](https://github.com/NVIDIA/NeMo-Retriever/issues/165) "[BUG]: nv-ingest-ms-runtime container failed to connect yolox endpoints" — **open since 2024-10-15**, 12 comments (~22 months).
- `NeMo-Retriever` [#966](https://github.com/NVIDIA/NeMo-Retriever/issues/966) "Subsequent Document Upload Re-ingests Previous Document with Significant Delay" — no incremental/idempotent ingestion contract. The fan-out-to-many-NIMs architecture multiplies readiness/health-check surface: any one of 5–7 GPU services being unready can hang the whole ingest with no user-visible timeout.

**P3. Microservice-mesh fragility dominates NVIDIA's trackers.** *Severity: major. Label: documented-recurring.* "invalid ports for nemoretriever-graphic-elements-v1" ([#30](https://github.com/NVIDIA-AI-Blueprints/rag/issues/30)); "404 Error for nemoretriever-table-structure-v1 API Endpoint" ([#44](https://github.com/NVIDIA-AI-Blueprints/rag/issues/44), open); "Helm deploy fails with permission error" ([#11](https://github.com/NVIDIA-AI-Blueprints/rag/issues/11)); "rag-nim-llm Unhealthy: Startup probe failed: connection refused" ([#31](https://github.com/NVIDIA-AI-Blueprints/rag/issues/31)); `MilvusException: dim (2048) of field data(vector) is not equal to schema dim (1024)` when mixing hosted and local model dims ([#7](https://github.com/NVIDIA-AI-Blueprints/rag/issues/7)); "nv-ingest Deployment renders duplicate `OTEL_EXPORTER_OTLP_ENDPOINT` env entry — **rejected by SSA / Fleet / strict admission**" ([#687](https://github.com/NVIDIA-AI-Blueprints/rag/issues/687), open — i.e. the shipped Helm chart is invalid under GitOps strict admission, a hard blocker in exactly the governed clusters this product targets); "rag-server image 2.5.1 doesn't exist" ([#618](https://github.com/NVIDIA-AI-Blueprints/rag/issues/618), open); "Unauthorized error pulling nv-ingest:26.1.0-RC3 (nvstaging)" ([#193](https://github.com/NVIDIA-AI-Blueprints/rag/issues/193)); "Kubernetes service names are not customizable" ([#662](https://github.com/NVIDIA-AI-Blueprints/rag/issues/662)). **A dozen cooperating containers means a dozen new ways to be down.**

**P4. Deploy and startup friction is extreme — and vendor-documented.** *Severity: major. Label: documented-recurring.* From the support matrix and [troubleshooting doc](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/troubleshooting.md): 3× H100 (Docker) / **8× H100-80GB** (Helm) floor, +1 GPU per optional service; **200 GB disk**; Ubuntu 22.04 only; driver ≥560; CUDA ≥12.9; **first Helm deploy 60–70 minutes** ("NIM cache downloads: 40-50 minutes," "no progress bar visible"); "The NeMo LLM microservice can take **5-6 minutes to start for every deployment**." For comparison, a LangChain/Chroma prototype is `pip install` and minutes. The NVIDIA stack's entry cost is an 8-GPU cluster and an hour of image pulls before the first query.

**P5. GPU-sharing and heterogeneous-hardware paths are second-class.** *Severity: major. Label: documented-recurring (vendor known-issues + field reports).* Blueprint known issues: "**B200 GPUs are not supported** for the following advanced features… Image captioning… NeMo Guardrails… VLM-based inferencing in RAG… PDF extraction with Nemotron Parse" — NVIDIA's newest datacentre GPU cannot run NVIDIA's own best extraction path. Also: "For MIG support, currently the ingestion profile has been scaled down… **large bulk ingestion jobs might fail**"; "Audio model deployment on Kubernetes on RTX-6000 Pro is not supported in this release." Field reports: [#51](https://github.com/NVIDIA-AI-Blueprints/rag/issues/51) MIG failure for embedding and reranking at a 20 GB VRAM slice; [#21](https://github.com/NVIDIA-AI-Blueprints/rag/issues/21) GRID 570 / CUDA 12.8.93; [#39](https://github.com/NVIDIA-AI-Blueprints/rag/issues/39) "SIGBUS Error in milvus-gpu docker with Querying"; and on [#48](https://github.com/NVIDIA-AI-Blueprints/rag/issues/48) a user reports "**ive been having milvus crash out on 2xh100 and had to switch to cpu milvus**" — the GPU-accelerated vector DB abandoned for the CPU one on a two-H100 box. The support matrix also documents the reranker requiring "shutdown of core services on smaller GPUs" rather than offering a CPU fallback.

**P6. Docling hard-crashes on managed / serverless runtimes.** *Severity: major. Label: documented-recurring.* [#3201](https://github.com/docling-project/docling/issues/3201) "SIGABRT crash on Python 3.12 — **all** docling versions fail on Databricks Serverless" (open since 2026-03-27, 17 comments, trivial 10-page PDF); [#1973](https://github.com/docling-project/docling/issues/1973) "Docling with AWS Bedrock" (17 comments); [#603](https://github.com/docling-project/docling/issues/603) "Error building extension 'MultiScaleDeformableAttention'" (17 comments); [#2466](https://github.com/docling-project/docling/issues/2466) missing `libgl1`/`libglib2`; [#3483](https://github.com/docling-project/docling/issues/3483) MPS float64 failure on Apple Silicon. The native-extension + torch-model dependency stack is brittle exactly where enterprises actually run Python data pipelines, undermining the "runs anywhere / runs locally" claim.

**P7. Hard, low ceilings in the managed paths.** *Severity: major. Label: documented-recurring (vendor docs).* NVIDIA: "Individual file uploads are limited to a maximum size of **400 MB**"; "**Slow VDB upload** is observed in Helm deployments for Elasticsearch"; "The Blueprint responses can have **significant latency** when using NVIDIA API Catalog cloud hosted models." IBM watsonx.ai vector index: "**Do not add more than 10 files in a single upload**"; max total size **50 MB** (PDF/DOCX/CSV) and **5 MB** (`.txt`); plus a genuinely surprising composition rule — "the maximum allowable size… depends on the **lowest** maximum file size among all the uploaded file types. For example, if you upload 1 plain text file and 2 PDF files, the sum of the sizes of the PDF files (maximum 50 MB) must not exceed the maximum file size for the `.txt` file type which is 5 MB." Mixing one small `.txt` into a batch silently collapses your PDF budget by 10×.

**P8. Ecosystem abandonment risk at IBM.** *Severity: major. Label: documented-recurring.* InstructLab — marketed through 2024 as *the* enterprise path to customized Granite models — is **archived** (`archived: true`, wind-down notice dated 2025-09-02, components dispersed to Red Hat AI Innovation Team repos). Watson-brand history amplifies the pattern (Watson Health sold for parts — [HN 30046432](https://news.ycombinator.com/item?id=30046432), 687 comments). Enterprises betting on IBM AI middleware have been burned before, and say so.

### abstraction-design

**A1. NVIDIA's RAG abstraction is a forkable reference app, not a composable library — so upgrades are migrations.** *Severity: major. Label: architectural-inference (supported by repo structure and release notes).* The unit of reuse is a repo you clone plus Helm values you edit; swapping any component is a documented-but-manual fork (`docs/change-model.md`, `docs/change-vectordb.md`); orchestration lives in LangChain glue. There is a `docs/migration_guide.md` because there has to be. **The abstraction boundary is the GPU service, not the retrieval concept** — so users inherit both LangChain's and NVIDIA's abstractions at once, and every default change is a breaking change for every fork.

**A2. Naming, model-ID, and default churn imposes a continuous migration tax.** *Severity: major. Label: documented-recurring (release notes).* Within roughly six months (2.4.0 Feb 2026 → 2.6.0 May 2026):
- `nvidia/llama-3.2-nv-embedqa-1b-v2` → `nvidia/llama-nemotron-embed-1b-v2`
- `nvidia/llama-3.2-nv-rerankqa-1b-v2` → `nvidia/llama-nemotron-rerank-1b-v2`
- `nemoretriever-page-elements-v3` → `nemotron-page-elements-v3` (same for graphic-elements, table-structure)
- `nemoretriever-ocr-v1` → `nemotron-ocr-v1`, and PaddleOCR → Nemotron OCR as default
- `llama-3.2-nemoretriever-1b-vlm-embed-v1` → `llama-nemotron-embed-vl-1b-v2`
- **default vector DB Milvus → Elasticsearch**; **default object store MinIO → SeaweedFS**; default embedder text-only → VLM
- "Reserved field names `type`, `subtype`, and `location` for NeMo Retriever Library exclusive use in metadata schemas" — a retroactive namespace grab on *user* metadata
- "Multi-turn conversation support is no longer the default for either retrieval or generation stage" Layered on top: the product line renamed from nv-ingest → "NeMo Retriever extraction" → "NeMo Retriever Library," the GitHub repo `NVIDIA/nv-ingest` now resolving to `NVIDIA/NeMo-Retriever`, and the model lineage NV-EmbedQA-e5/Mistral → llama-3.2-nv-embedqa → llama-nemotron-embed. Three different "default" vector stores in two years (Milvus, Elasticsearch, LanceDB). **Enterprises buying "stability" get a stack whose names, APIs, and storage layer changed three times in two years — and for a *regulated* buyer, each rename is a revalidation event.**

**A3. Docling has accreted parallel pipelines with no clear selection guidance.** *Severity: minor. Label: architectural-inference.* `pipeline/` holds `legacy_standard_pdf_pipeline.py`, `standard_pdf_pipeline.py`, `threaded_standard_pdf_pipeline.py`, `vlm_pipeline.py`, `extraction_vlm_pipeline.py` simultaneously, plus an `experimental/` package, while `chunking/` is an empty re-export shell. Users must choose a backend/pipeline combination that materially changes memory behaviour (P1 is backend-specific) and output fidelity, with tradeoffs undocumented. Corroborating confusion: [#2102](https://github.com/docling-project/docling/issues/2102) "Please add more descriptions on how to use VLM" (23 comments), [#2186](https://github.com/docling-project/docling/issues/2186) "clarity about picture and table enrichment" (16), [#3033](https://github.com/docling-project/docling/issues/3033) "Docling return nothing when using VLM pipeline" (14), [#2312](https://github.com/docling-project/docling/issues/2312) "I can't disable OCR using `do_ocr=False`". Also **high-frequency breaking evolution**: 201 releases to v2.118, plus a v1→v2 API break — pinned enterprise deployments drift fast.

**A4. IBM's RAG story is three products with three abstraction models and no unifying retrieval interface.** *Severity: major. Label: architectural-inference.* Docling (Python library, no retrieval) → watsonx.ai vector index (managed asset with field-mapping config) → Orchestrate (agent tool). Moving a pipeline from Prompt Lab to AutoAI to an Orchestrate agent means re-expressing it three times, and the *available encoder differs by surface*: the task-support matrix shows ELSER usable **only** in "Chat with documents in Prompt Lab"; `ms-marco-minilm-l-12-v2` **only** via the rerank API; `granite-embedding-278m` in AutoAI but `slate-30m` not.

### security-governance

**S1. Documented SSRF in watsonx Orchestrate agentic-workflow file upload, with mitigation pushed to the customer.** *Severity: critical. Label: documented-recurring (vendor known-issues page).* Verbatim from [building-tools known issues](https://www.ibm.com/docs/en/SSAVQO/about/knownissues/building-tools.html): "The file upload functionality in agentic workflows **does not validate the URL of uploaded files against an allowlist of approved domains**. An attacker can intercept the file upload API request and replace the legitimate URL with an external URL. This allows the server to potentially execute arbitrary requests to external servers, exposing the system to SSRF attacks. **Workaround: Add URL validation directly in the** [workflow]." On the platform explicitly sold for governed, compliant enterprise AI, a server-side request forgery in the *document-ingestion path* is disclosed as a known issue with a customer-implemented workaround.

**S2. LLM-mangled signed URLs — the agent corrupts its own auth tokens.** *Severity: major. Label: documented-recurring.* [Orchestrate Chat known issues](https://www.ibm.com/docs/en/SSAVQO/about/knownissues/orchestrate-chat.html): "File download URLs fail with Access Denied error… URLs in agent responses are incomplete or malformed… This issue occurs intermittently **due to LLM hallucination during response generation**." Affected: "Pre-signed S3 URLs with authentication parameters," "Temporary download links with expiration tokens," "API endpoints with authentication tokens," "Webhook URLs with query parameters." IBM's stated root cause: "The LLM treats URLs as **text to summarize rather than exact strings to preserve**… High risk: GPT-OSS 120B (via Groq)." The workaround is to set `sync_tool_flow_interactions: false` — i.e. to stop the agent from seeing tool output at all. This is a first-class architectural lesson, not a bug report.

**S3. Internal scheduling tools are visible and deletable via the ADK CLI — no workaround.** *Severity: major. Label: documented-recurring.* Same page: "Internal scheduling tools visible and deletable through ADK CLI | Workaround available: **No**." A tenant-scoped privilege-boundary leak in an agent platform.

**S4. NVIDIA guardrails are structurally optional and unavailable on the paths that need them most.** *Severity: major. Label: documented-recurring (vendor docs).* Blueprint known issues: "Currently, **Helm-based deployment is not supported for NeMo Guardrails**" and "Optional features reflection and image captioning are not available in Helm-based deployment." Agentic RAG "does not use NeMo Guardrails." B200 cannot run guardrails. So the **production deployment method (Helm)**, the **newest hardware (B200)**, and the **newest pipeline (agentic)** each independently exclude the safety layer. AI-Q adds the same pattern one level up: guardrails are customer-added and "will be native in upcoming release" (see S7).

**S5. The benchmark-topping model is not the shippable model (NVIDIA).** *Severity: major. Label: documented-recurring (verified against the HF API).* `nvidia/llama-nemoretriever-colembed-3b-v1` — the ViDoRe #1 model NVIDIA promotes — carries `license_name: customized-nscl-v1`, i.e. the **NVIDIA Non-Commercial Software License** (397 downloads / 74 likes). The commercial alternative is a different, smaller model (`llama-3_2-nemoretriever-1b-vlm-embed-v1` → now `llama-nemotron-embed-vl-1b-v2`). **Marketing benchmarks and deployable licenses diverge** — a governance trap for buyers who cite the leaderboard in an architecture review.

**S6. NVIDIA's local/RTX RAG showcase shipped with high-severity vulnerabilities.** *Severity: major. Label: documented-recurring.* ChatRTX — the RTX local-RAG demo app — [CVE-2024-0082](https://nvd.nist.gov/vuln/detail/CVE-2024-0082), re-verified against the NVD API on 2026-08-05: `cvssMetricV31` baseScore **8.2 HIGH**, description verbatim — "NVIDIA ChatRTX for Windows contains a vulnerability in the UI, where an attacker can cause improper privilege management by sending open file requests to the application. A successful exploit of this vulnerability might lead to local escalation of privileges, information disclosure, and data tampering." RAG applications handling users' private documents were not engineered to the security bar of the enterprise pitch.

**S7. The agentic blueprint's MCP surface has no authentication, and guardrails are not native.** *Severity: major. Label: documented-recurring (verified verbatim in the current AI-Q README).* AI-Q's roadmap carries, as **unchecked** items, "**MCP Authentication:** Implement secure login/auth for MCP connections" and "**Skills & Sandboxing:** Support custom skills within isolated environments," while the security section says "End users are **encouraged to add** [NeMo Guardrails] and additional prompt content filtering to the blueprint. Guardrails **will be native in upcoming release**." For a stack sold on governance, the shipped state of the agent boundary is: unauthenticated MCP, customer-supplied guardrails, no sandbox.

**S8. Model-family hallucination risk documented, then delegated to prompt engineering.** *Severity: minor. Label: documented-recurring.* Blueprint known issues: `llama-3.3-nemotron-super-49b-v1.5` "may respond with information not available in given context. Also for out of domain queries the model may provide responses based on its own knowledge. **Developers are strongly advised to tune the prompt**." In a grounded-retrieval product, "tune the prompt" is not a groundedness guarantee.

**S9. Nightly CVE scanning is an open tracker issue, and frontend CVEs shipped in a release.** *Severity: minor. Label: single-anecdote.* [#617](https://github.com/NVIDIA-AI-Blueprints/rag/issues/617) "Nightly CVE Scan Tracker" (open); 2.5.0 release notes list "frontend CVE resolutions" as a fix. For an air-gapped regulated deployment, container CVE posture is a procurement gate, and the public evidence trail is a GitHub issue.

### performance-cost

**C1. The GPU-vendor conflict of interest is structural, not rhetorical.** *Severity: critical. Label: architectural-inference (from licensing + architecture primary sources).* NVIDIA licenses AI Enterprise **per GPU**, activated by GPU serial number, and resells it inside GPU racks (Dell AI Factory, HPE Private Cloud AI). It has simultaneously re-architected **every** stage of retrieval — extraction (4–6 vision models), embedding, reranking, *and indexing* (cuVS) — as a GPU-resident service, with a documented floor of 3 GPUs (Docker) / 8 GPUs (Helm) plus "one additional GPU for each optional service." Every accuracy improvement NVIDIA ships (VLM embedder, VLM reranker, Nemotron Parse, reasoning mode) adds GPU demand, and release notes move defaults *toward* the heavier options (2.6.0 promoted the VLM embedder to default). There is no honest way to read "7x better indexing throughput [vs] CPU approaches" as vendor-neutral engineering advice. **Counter-evidence, stated only as far as the evidence goes:** IBM ships permissively licensed 149M–311M-parameter long-context encoders (`granite-embedding-311m-multilingual-r2`, ModernBERT, `max_position_embeddings: 32768`, Apache-2.0 — verified from `config.json`), which indicates the **embedding and reranking** stages need not be GPU-resident at all. The **extraction** stage is where NVIDIA's GPU cost actually concentrates (4–6 vision models), and **neither vendor publishes a CPU-baseline comparison for extraction** — so the GPU dependence of the expensive stage is untested rather than demonstrated. That gap is the point: the party with the incentive to test it is the party billing per GPU. This is the single most important finding for a next-generation framework: *the entity defining what state-of-the-art retrieval costs is compensated per unit of that cost.*

**C2. GPU-accelerated vector search is gated behind commercial access.** *Severity: major. Label: documented-recurring (release notes).* 2.6.0: the default VDB is Elasticsearch, and "[GPU accelerated support] **needs enterprise access** and is disabled by default." The flagship GPU-acceleration story for indexing is therefore (a) off the default path and (b) behind a commercial gate — while the 7×-indexing marketing claim remains in circulation.

**C3. Unpriced production licensing.** *Severity: major. Label: documented-recurring.* NVAIE has **no published price** on the [product page](https://www.nvidia.com/en-us/data-center/products/ai-enterprise/) or the licensing guide — "Contact Us," a 90-day trial, per-GPU / perpetual / cloud-hourly options with a mandatory 5-year support attach on perpetual. Prototyping is free via NGC / API Catalog; production is a sales conversation. **Teams cannot model TCO from documentation** — precisely the modelling a regulated buyer must complete before an architecture review. Community relies on secondhand figures (~$4,500/GPU/yr, [HN 41389079](https://news.ycombinator.com/item?id=41389079) — low credibility for the exact number). Every layer carries a different license (blueprint Apache-2.0, weights NVIDIA Open Model License, some models Non-Commercial, NIM containers NVAIE), and the blueprint README itself warns third-party components "require separate review."

**C4. Docling is slow and effectively single-threaded by default.** *Severity: major. Label: documented-recurring.* [#1256](https://github.com/docling-project/docling/issues/1256) "Multi-threading and multi-processing for faster parsing" (14 comments, open); [#115](https://github.com/docling-project/docling/issues/115) "Support concurrency" (15 comments); [#1069](https://github.com/docling-project/docling/issues/1069) request for progress/logs during conversion. `threaded_standard_pdf_pipeline.py` exists but is not the documented default; users on Databricks/servers route around it with process pools.

**C5. Agentic mode's cost is acknowledged but unquantified.** *Severity: minor. Label: documented-recurring.* "Latency and LLM-call count exceed the standard chain. Prefer the per-request override over a global default on latency-sensitive paths." No published multiplier, no token accounting — in contrast to IBM's AutoAI doc, which does itemise (3,267,000 tokens for a 100-page / 25-QA experiment).

### data-processing

**D1. NVIDIA's flagship extraction demo output is itself garbled.** *Severity: major. Label: documented-recurring.* **Re-verified 2026-08-05 by fetching `README.md` from `main` and grepping the strings.** The repo's own sample output renders the test table as one-word-per-cell Markdown — `| Animal | Activity | Place |` followed by `| Giraffe | Driving | a | car | At | the | beach |` and `| Cat | Jumping | onto | a | laptop | In | a | home | office |`, with the caption row spilling into `| This | table | describes | some | animals, … | specific |` / `| locations. |` — emits the **identical** table and chart three times under "Table 1/2/3" and "Chart 1/2/3" (and the chart body is labelled "Chart 1" under all three headings), and carries ligature OCR artifacts `Gira@e` and `o@ice` in the raw text stream. **When the vendor's curated happy path shows structure loss and duplication, real-world PDFs fare worse.** Related: [#53](https://github.com/NVIDIA/NeMo-Retriever/issues/53) "Error extracting image: Cannot handle this data type", [#1030](https://github.com/NVIDIA/NeMo-Retriever/issues/1030) VLM caption prompt issues.

**D2. Docling's third-party benchmark position was weak where it was last measured — and it has since disappeared from the live leaderboard.** *Severity: major. Label: documented-recurring, with an explicit dating caveat.* [OmniDocBench](https://github.com/opendatalab/OmniDocBench) (CVPR 2025, [arXiv 2412.07626](https://arxiv.org/abs/2412.07626)) added Docling on 2025-01-16. In the README at commit [`2344c320`](https://github.com/opendatalab/OmniDocBench/blob/2344c320/README.md) (**2025-01-17**), Docling's end-to-end scores were:

| Metric (EN / ZH) | Docling | MinerU-0.9.3 | Mathpix | Marker-1.2.3 |
|---|---|---|---|---|
| Text Edit ↓ | **0.416 / 0.987** | 0.061 / 0.211 | 0.101 / 0.358 | 0.080 / 0.315 |
| Formula CDM ↑ | **0 / 0** | 66.9 / 49.5 | 71.4 / 72.7 | 20.1 / 16.8 |
| Table TEDS ↑ | **61.3 / 25.0** | 78.6 / 62.1 | 77.0 / 67.1 | 67.6 / 49.2 |
| Read Order Edit ↓ | **0.313 / 0.837** | 0.079 / 0.288 | 0.105 / 0.275 | 0.114 / 0.340 |
| Overall Edit ↓ | **0.589 / 0.909** | 0.150 / 0.355 | 0.189 / 0.352 | 0.336 / 0.556 |

Two caveats, stated plainly: (i) Formula CDM 0 alongside formula edit ≈ 1.0 means *that version emitted essentially no usable formula output*, not "0% formula accuracy"; (ii) the near-1.0 Chinese edit distance reflects the OCR configuration used in that run. **Dating caveat:** in the current (2026) README, Docling appears only in the model-version appendix (`docling-layout-heron`) and is **absent from the live end-to-end leaderboard**, whose current top entries are specialist VLMs (PaddleOCR-VL-1.6 at 96.34 overall; MinerU2.5-Pro 95.75), with the best remaining classical pipeline tool at 86.47 and Marker at 78.44. So: *the last public third-party measurement of Docling was poor, and the benchmark no longer tracks it — meaning **no current independent quality number for Docling exists**.* That absence is itself a finding for a paper about evaluation.

**D3. Docling parsing-correctness defects on real-world PDFs — the corruption class.** *Severity: major. Label: documented-recurring.* [#2334](https://github.com/docling-project/docling/issues/2334) "Some PDF fonts are not parsed correctly on the backend" (highest-reaction open issue); [#1111](https://github.com/docling-project/docling/issues/1111) "Convert PDF file error [RuntimeError: Invalid code point]" (open since 2025-03-04, 17 comments); [#1000](https://github.com/docling-project/docling/issues/1000) "IndexError while processing a PDF file"; [#1635](https://github.com/docling-project/docling/issues/1635) "RapidOcr causes merging of text while parsing" (14 comments); [#2899](https://github.com/docling-project/docling/issues/2899) fillable-PDF handling (18 comments); [#1648](https://github.com/docling-project/docling/issues/1648) "Mean of Empty Slice During Conversion of PDF". "Metadata extraction and chemistry structure recognition" remain "coming soon" — the latter a direct gap for pharma. **Why this class is worse than a crash:** a font or code-point mis-parse *silently poisons the index*, and neither stack provides per-document extraction-confidence scores or a quarantine path.

**D4. Metadata/schema extensibility is a repeated blocker in both stacks.** *Severity: minor. Label: documented-recurring.* NVIDIA [#17](https://github.com/NVIDIA-AI-Blueprints/rag/issues/17) "[FEA]: Ingestion with custom metadata field" and `NeMo-Retriever` [#647](https://github.com/NVIDIA/NeMo-Retriever/issues/647) "[FEA]: Ingest pdf with custom metadata" — while 2.4.0 simultaneously *reserved* `type`, `subtype`, `location` for internal use. IBM requires explicit field mapping (Vector query / Document name / Text / Page number / Document url) to bridge an external index into a watsonx vector index asset, with "Vector query — Required for Elasticsearch indexes only."

### agentic-integration

**G1. Agentic RAG has no dependency graph.** *Severity: major. Label: documented-recurring (vendor docs).* "Tasks in a plan run at one parallel level; there is no DAG or depends-on construct." Multi-hop retrieval where step 2's query depends on step 1's result — the canonical hard case, and precisely where NVIDIA's own Google Frames score is lowest (0.486–0.597) — is exactly what a flat plan cannot express.

**G2. Capability regresses when you switch to the agentic path.** *Severity: major. Label: documented-recurring.* The agentic path drops Guardrails, Self-Reflection, **Query Decomposition**, and VLM Inference. Adopting agents means giving up query decomposition *in an agentic system*. This is the symptom of agentic RAG being bolted **beside**, rather than **beneath**, the retrieval pipeline.

**G3. IBM's agentic layer has documented breakage exactly at the retrieval/agent boundary.** *Severity: major. Label: documented-recurring.* Beyond S2 (URL corruption): "**Human review is not supported in embedded chat** — When an agentic flow that uses **document processing skills** reaches a Human-in-the-Loop review step, the embedded chat displays an 'Unsupported content' message and **the flow does not continue**" (no workaround). Also "Multi-file upload tools with ReAct style agents | No"; "Remote MCP toolkit import fails with gateway name conflict"; "Chat with documents is not supported in voice"; "Text extractor output mapping"; "Document upload fails"; "Unable to scroll the extracted fields | No"; "Parallel branches pause on user interaction"; "Chat-based table search results are not editable | No". **The document-processing → agent → human-review path — the single most important flow for regulated document work — has multiple documented breaks.**

**G4. Neither stack exposes retrieval as an ACL-aware agent substrate.** *Severity: major. Label: architectural-inference.* NVIDIA delegates agent logic to LangGraph inside its own blueprints and ships MCP stateless and unauthenticated; IBM splits agents (Orchestrate) from retrieval (Discovery / watsonx.ai) across separately priced products, so identity and permission context does not propagate as a first-class retrieval constraint. There is no "retrieve as this user, with these entitlements, and log it" primitive in either.

### dx-docs

**X1. Documentation drift and dependency-hell tickets dominate both trackers.** *Severity: minor. Label: documented-recurring.* `NeMo-Retriever` carries a large standing `[DOC]:` backlog (#90 CLI man page, #120 container setup for the client notebook, #100 per-stage tracing, #25 "Add 'blueprint' diagram and explain", #28 "Document the JSON schema for extracted content", #59 image-viewer steps). Blueprint: [#43](https://github.com/NVIDIA-AI-Blueprints/rag/issues/43) "[DOC]: B-Series Compatibility", [#19](https://github.com/NVIDIA-AI-Blueprints/rag/issues/19) "Missing configuration for Grafana container", [#49](https://github.com/NVIDIA-AI-Blueprints/rag/issues/49) "dotenv ModuleNotFoundError", [#38](https://github.com/NVIDIA-AI-Blueprints/rag/issues/38) "missing 1 required positional argument: 'otel_ctx'". Environment fragility in quickstarts: `NeMo-Retriever` [#182](https://github.com/NVIDIA/NeMo-Retriever/issues/182) Docker build failure, [#450](https://github.com/NVIDIA/NeMo-Retriever/issues/450) conda client package missing its `pymilvus` dependency. Docling: [#1108](https://github.com/docling-project/docling/issues/1108) "missing changelog", [#2116](https://github.com/docling-project/docling/issues/2116) transformers `Idefics3ImageProcessor` registration failure, [#3026](https://github.com/docling-project/docling/issues/3026) "CodeFormulaV2 Preset Missing torch_dtype Causes Flash Attention 2 Incompatibility", [#1308](https://github.com/docling-project/docling/issues/1308) `LocalEntryNotFoundError`. **Note the irony of the last item:** Docling's headline regulated-industry feature is local/air-gapped execution, yet model-weight acquisition is a HuggingFace hub call.

**X2. IBM documentation is not programmatically auditable.** *Severity: minor. Label: architectural-inference (observed directly).* `ibm.com/docs` and `cloud.ibm.com/docs` are JS-rendered and return 403/blank to non-browser fetches; retrieving IBM's own known-issues register required a reader proxy. Compare NVIDIA's plain-HTML and raw-Markdown-in-Git docs. For a compliance-marketed platform this matters twice over: humans can read it, but agents, auditors' scrapers, and LLM self-service cannot.

**X3. Internal trackers leak into public release notes.** *Severity: minor. Label: single-anecdote.* Release 2.5.1: "Tracked under [BCS-445](https://jirasw.nvidia.com/browse/BCS-445)" — an NVIDIA-internal Jira link in public release notes. Symptomatic of a product whose real issue tracker is not the public one.

---

## Community sentiment over time

**The most striking finding here is an absence — and it is a finding, not merely a gap in the search.**

- **NVIDIA NeMo Retriever: near-zero organic discussion.** HN Algolia for "NeMo Retriever" returns one on-topic story — *"Nvidia NeMo Retriever's Generalizable Agentic Retrieval Pipeline"* (2026-03-16,
  [47399622](https://news.ycombinator.com/item?id=47399622)) — at **2 points, 0 comments**. "Nvidia OCR" (2025-03-07, [43287531](https://news.ycombinator.com/item?id=43287531)): 9 points, 0 comments. The GitHub trackers are the only public feedback channel, and they skew overwhelmingly toward deployment breakage rather than feature debate. NIM commentary that *does* exist is about the free hosted tier's limits ("Nvidia is offering free access to top models for free through NIM - but you have 40 RPM limits" — [48191322](https://news.ycombinator.com/item?id=48191322)) — hobbyists using `build.nvidia.com` as a free API, not enterprises discussing retrieval architecture. Positive sentiment exists mainly about *strategy*: "people don't actually want GPUs, they want solutions that happen to run best on GPUs. Nvidia understands that" ([41996912](https://news.ycombinator.com/item?id=41996912), Oct 2024). **Interpretation: adoption is top-down via OEM/enterprise procurement, not developer-led.**
- **IBM watsonx: shadowed by Watson-brand distrust, and frozen in 2023.** HN "watsonx" peaks in 2023 on a non-RAG topic — *"Watsonx: IBM's code assistant for turning COBOL into Java"* (127 points, 178 comments, [38508250](https://news.ycombinator.com/item?id=38508250)) and *"COBOL gets new life in the cloud thanks to Watsonx and AI"* (41/45). Everything after is ≤14 points. **There is no HN discussion of watsonx retrieval at all.** Historic distrust remains heavily upvoted ("A rising sentiment that IBM's Watson can't deliver on its promises", 503 pts, 2017; "Watson Health sold off in parts", 687 pts, [30046432](https://news.ycombinator.com/item?id=30046432)), and 2025–26 comments still read watsonx as a rebrand ("Watson… was way over promised and overhyped," story 46124324; "WatsonX AI quantum angstroms for e-business," story 48674967). The one consistently positive note: air-gapped/regulated deployment ("IBM makes WatsonX for corporate who want airgapped AI").
- **Docling is the exception, and it is IBM's real asset.** Bottom-up enthusiasm: 10k stars in under a month at launch, #1 GitHub trending Nov 2024, 64k stars by 2026, steady Show-HN/RAG-tutorial presence. Note the shape though: story-level HN scores are small (the original Nov 2024 posts: 13/1, 8/0, 5/0) — Docling's adoption expresses itself as **stars, downloads, and integrations** rather than discourse. Sentiment cools specifically around **memory and performance in production threads**.
- **InstructLab: one spike, then silence, then archival.** "Instructlab AI CLI" (65 points, 5 comments, May 2024, [40285986](https://news.ycombinator.com/item?id=40285986)) → nothing → archived 2026.
- **Trajectory:** NVIDIA sentiment flat-but-invisible (procurement-driven); IBM platform sentiment skeptical-stable; Docling strongly positive with growing production-grade grumbling; InstructLab enthusiasm → abandonment.

**Why this matters for the paper.** For OSS RAG frameworks, failure evidence is public: issues, HN threads, migration postmortems. For these stacks the record is asymmetric:
- NVIDIA has *partially* public failure evidence, because the blueprints are Apache-2.0 on GitHub — and that evidence is rich (233 open issues on `NeMo-Retriever`, hundreds on `rag`).
- IBM's watsonx retrieval failure evidence exists almost exclusively **inside IBM's own known-issues register** (which, to IBM's credit, is unusually detailed and public) plus support tickets and `ideas.ibm.com`. There is no public issue tracker for the platform's retrieval path.
- **Every critical IBM finding in this dossier (S1 SSRF, S2 URL corruption, E4 observability, G3 HITL break) came from IBM's own documentation.** There was no other way to find them. For closed regulated platforms, the vendor decides which failures enter the public record — and a research community that only mines GitHub will systematically under-count enterprise failure modes.

---

## Benchmarks & third-party evaluations

| Source | What it measures | Result | Credibility |
|---|---|---|---|
| [NVIDIA developer blog](https://developer.nvidia.com/blog/nvidia-nemo-retriever-delivers-accurate-multimodal-pdf-data-extraction-15x-faster/) | Extraction/embedding/rerank/index throughput, storage, accuracy | 15× extraction vs "open-source alternatives" (1× H100 SXM); 3× embedding; 1.6× rerank; 7× indexing (8× L4 vs CPU); 35× storage reduction; 50% fewer incorrect answers | **Vendor-measured, vendor hardware, unnamed baselines, no independent replication found** |
| [Blueprint `accuracy-benchmarks.md`](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/accuracy-benchmarks.md) | End-to-end answer accuracy; RAGAS NVIDIA Answer Accuracy; judge Mixtral-8x22B | FinanceBench 0.612→0.697; KG-RAG 0.569→0.643; RAGBattle 0.812→0.867; DC767 ~0.90 flat; HotpotQA 0.672→0.676; Google Frames 0.486→0.597; ViDoRe-v3 subsets 0.639–0.931 | **Vendor-run; no external pipeline baseline; self-selected judge — but datasets, methodology, and a runnable notebook are published, and the numbers are unflatteringly honest** |
| MTEB, June 2024 | Text embedding, 56 tasks | **NV-Embed #1 at 69.32** avg (runner-up 68.28) | Independent leaderboard; NVIDIA-announced but publicly checkable. **Model-level, not pipeline-level** |
| ViDoRe V1/V2, MTEB-VDR, June 2025 | Visual document retrieval | `llama-nemoretriever-colembed-3b-v1` **#1**: 0.9100 / 0.6352 / 0.8315 nDCG@5 | Independent leaderboards — but the model is **Non-Commercial licensed** (verified: `customized-nscl-v1`), so the win is not the deployable artifact |
| [OmniDocBench](https://github.com/opendatalab/OmniDocBench) (CVPR 2025), README @ `2344c320`, **2025-01-17** | Document parsing vs ground truth; 981 pages, 9 doc types, 3 languages | Docling Overall Edit **0.589 EN / 0.909 ZH**; Table TEDS 61.3 / 25.0; Formula CDM 0 / 0 — vs MinerU-0.9.3 0.150/0.355, Mathpix 0.189/0.352 | **Independent and adversarial.** Dated Jan 2025 |
| OmniDocBench current README (2026) | Same, updated | PaddleOCR-VL-1.6 96.34 overall; MinerU2.5-Pro 95.75; best classical pipeline 86.47; Marker 78.44. **Docling absent from results tables** | Independent; Docling's absence means **no current independent number exists** |
| Docling technical reports ([2408.09869](https://arxiv.org/abs/2408.09869), [2501.17887](https://arxiv.org/abs/2501.17887)) | Architecture / efficiency | "runs efficiently on commodity hardware in a small resource budget" | Authors' own papers (AAAI-25 workshop); qualitative |
| `granite-embedding-english-r2` model card | Retrieval quality at 149M params, 8k ctx | 59.5 MTEB-style avg / 53.1 BEIR, beating `e5-base-v2` and `bge-base-en-v1.5`; ~144 docs/sec on H100 | IBM self-reported, but MTEB/BEIR are independently checkable |
| HuggingFace download counts (API, 2026-08-05) | Adoption proxy | nvidia embed-1b-v2 827,762; nvidia rerank-1b-v2 765,118; granite-docling-258M 512,696; granite-embedding-125m-english 74,486; granite-embedding-311m-r2 47,567; colembed-3b 397 | Adoption proxy only, not quality |
| IBM AutoAI for RAG docs | Token/CUH cost of RAG optimisation | 3,267,000 tokens for 100 pages + 25 QA pairs; 20 CUH/hour environment | Vendor-published, itemised, genuinely useful |
| watsonx Discovery / conversational search | End-to-end retrieval quality | **Nothing published** | — |

**Net assessment.** Neither stack has a credible *independent, end-to-end* retrieval-pipeline evaluation (extraction → embed → rerank → answer) as of August 2026. What exists is (a) component-level model leaderboards — where NVIDIA genuinely wins, sometimes with a non-commercial model — and (b) vendor-run pipeline evals. NVIDIA publishes plenty of numbers but grades its own homework with its own judge on its own hardware. IBM publishes essentially no retrieval-quality numbers for the platform path. The one adversarial third-party benchmark that touched either stack (OmniDocBench on Docling) was unflattering and no longer tracks it. **For a paper motivating a next-generation framework, the evaluation vacuum around enterprise RAG stacks is arguably a bigger finding than any single defect.**

---

## Lessons for a next-generation framework

1. **Treat "who profits from the recommended architecture" as an evaluation input.** The GPU-vendor conflict (C1) is not corruption; it is incentive. When the vendor that licenses per GPU also declares that every retrieval stage — including indexing — belongs on a GPU, the claim needs an independent cost-quality Pareto frontier before adoption. IBM's permissively licensed 149M–311M long-context encoders show the *embedding/rerank* stages need no accelerator; the *extraction* stage's GPU dependence has never been tested against a CPU baseline by either vendor. **A next-gen framework should ship a hardware-neutral cost model: quality-per-dollar and quality-per-watt for CPU-only, single-GPU, and multi-GPU configurations of the same pipeline, measured by the framework itself.**
2. **Never round-trip exact identifiers through generative text.** IBM's URL-corruption defect (S2) is the general case: signed URLs, chunk IDs, document IDs, citation anchors, and page numbers must travel in a structured channel the LLM cannot rewrite. Make identifier passthrough *structurally incorruptible* — opaque handles resolved outside the model — rather than something you disable via `sync_tool_flow_interactions: false` after an incident.
3. **The agentic path must be a superset, not a fork.** Both stacks *lose* capability when agents turn on: NVIDIA's agentic RAG drops guardrails, self-reflection, query decomposition, and VLM inference, has no task DAG, and returns empty metadata (G1, G2, E3). Design retrieval so planning, verification, guardrails, and observability are **layers beneath** both single-shot and multi-step execution — with a real dependency graph, since dependent multi-hop is precisely where measured accuracy is worst (0.486 on Google Frames).
4. **Ingestion is the reliability frontier; make it bounded, resumable, and observable by construction.** The most-corroborated defect across two independent vendors is unbounded memory growth in batch ingestion (P1: four reports, one open eleven months), followed by silent hangs and deadlocks with "no fail-fast or clear error" (P2, one open 22 months), and non-idempotent re-ingestion. Make streaming, bounded-memory, checkpointed, per-document-isolated ingestion the *only* mode: per-document memory ceilings, hard timeouts, readiness gates before job submission, and a resumable manifest with idempotency keys.
5. **Prefer in-process modularity with optional service extraction over mandatory distribution.** Port mismatches, endpoint 404s, image-tag drift, duplicate env vars rejected by admission controllers, and dim mismatches between hosted and local models dominate NVIDIA's trackers (P3). A dozen cooperating GPU containers is a dozen new ways to be down; distribution should be an opt-in deployment topology, not an architectural precondition.
6. **Document-global structure is the unsolved half of parsing, and structure fidelity must be a tested contract.** Both stacks are strong on page-local structure and weak on hierarchy, cross-page continuity, and TOC-aware chunking (R3; Docling #287 open 21 months; NVIDIA #240) — and the vendor's own demo output shows shattered tables (D1). Treat document structure extraction as a first-class typed output: a tree with **stable node identity across pages and revisions**, with golden-file regression suites, and make chunking a function of that tree rather than of character counts.
7. **Corruption-aware ingestion.** A font mis-parse or invalid code point (D3) that silently poisons an index is worse than a crash. Emit **per-document, per-region extraction-confidence scores**, and provide a quarantine path plus a re-extract-on-better-model workflow. Neither stack does this.
8. **Model rosters must be decoupled from platform release cycles.** watsonx.ai's 512-token / 768-dim roster with a single English-only 2021-era reranker (R1) — while IBM ships a 32k-capacity ModernBERT encoder on HuggingFace — is what happens when adding a model is a platform release event. Treat encoders and rerankers as **hot-swappable, versioned, independently benchmarkable plugins**, with an in-framework harness that answers "does swapping help *on my corpus*?"
9. **Naming, defaults, and licenses are a compliance surface, not cosmetics.** A2's rename cascade (six model IDs, default vector DB, default object store, default embedder, reserved metadata keys — in six months; three vector-DB defaults in two years) is annoying for a hobbyist and a **revalidation event** for a regulated deployment. Ship stable logical model aliases with pinned resolution, machine-readable deprecation metadata, license metadata per artifact (S5's non-commercial trap), and a migration linter that diffs two framework versions against a running configuration.
10. **Build the evaluation harness before the pipeline, and make external baselines mandatory.** E1 is the deepest structural flaw: a vendor that selects its own pipeline, hardware, metric, judge, and judge-selection benchmark cannot produce a falsifiable quality claim; and S5 shows the leaderboard-topping model may not even be licensable. Ship (a) a default harness with pinned public datasets, (b) at least one **adversarial external baseline** run in the same harness, (c) multi-judge agreement with reported inter-judge variance, (d) retrieval-only metrics (recall@k, nDCG) reported separately from end-to-end answer metrics so retrieval regressions cannot hide behind a stronger LLM, and (e) evals published **only for the exact licensed configuration a user can actually run**, reproducible in CI.
11. **Secure-by-default at the agent and retrieval boundary.** An enterprise blueprint shipping an unauthenticated MCP server (S7), a local RAG app with a CVSS-8.2 CVE (S6), an SSRF in an agentic upload path (S1), and a guardrail layer unavailable on Helm / B200 / agentic paths (S4) together make the case: authn/z, sandboxing, ACL-propagating retrieval ("retrieve as this user, with these entitlements, and log it"), and threat modeling belong in the substrate from day one — and safety layers must be available on **every** execution path, or they are decoration.
12. **Regulated requirements OSS frameworks ignore — the real lesson from these stacks.** What NVIDIA and IBM get right, and typical OSS RAG frameworks do not even model:
    - **Air-gap as a first-class mode**: mirrored registries, offline model caches, no implicit egress. (Both still fail partially: Docling #1308 `LocalEntryNotFoundError` shows an HF-hub dependency inside the "runs locally" path.)
    - **Published hardware/OS/driver floors and expected deploy timings** — 3×/8× H100, 200 GB disk, Ubuntu 22.04, 60–70 min Helm deploy. Unglamorous and enormously useful.
    - **A machine-readable known-issues register with per-issue workaround status** — IBM's "Workaround available: Yes/No" column is a pattern OSS should copy wholesale.
    - **Deployment-tier feature-parity matrices** — IBM documents full/partial/no support per feature across SaaS, GovCloud, on-prem, and local dev. Any framework claiming on-prem parity should be forced to publish this.
    - **Human-in-the-loop review as a retrieval-pipeline primitive with audit trails** — not a UI afterthought that breaks in embedded chat (G3).
    - **Data-residency and regional constraints as configuration** — IBM documents region-specific failures ("File downloads do not work outside customer network in Paris region"); a framework should be able to *express* residency constraints, not discover them.
    - **Support/entitlement metadata in the artifact** — which components carry a support contract, which are community, which are experimental, which need "enterprise access" (C2). That belongs in machine-readable capability metadata, not a release-note sentence.
    - **License-clean provenance as a feature** — IBM excluding MS-MARCO for its non-commercial terms is the right instinct; a framework should track and surface training-data provenance for every model it can install.
    - **LTS branches, CVE scanning, and deprecation windows** — the things enterprises actually pay for, and the reason these stacks win procurement despite the defects above.
13. **Unbundle the parser (and everything else).** Docling's cross-ecosystem adoption — 64k stars, MIT, LF AI & Data governance, used by LangChain/LlamaIndex/Haystack/CrewAI — versus watsonx's opacity is the clearest natural experiment in this dossier. Open, framework-neutral, individually consumable components earn the mindshare that closed platforms then try to monetize. A next-gen framework should be consumable piecemeal, and should assume its best component will be used *without* it.
14. **Make the operator an agent, deliberately.** NVIDIA's `skills/`, `AGENTS.md`, `.openclaw/`, and `skill-eval/` are the most genuinely novel thing in either stack: the deploy/configure/troubleshoot/ evaluate loop is designed for an AI operator with an eval harness attached. Treat **agent-operability** as a design constraint — declarative capability manifests, machine-readable error taxonomies, idempotent operations, plain-text/Git-native docs (contrast X2), and a self-evaluation loop the agent can close — rather than retrofitting a CLI wrapper.

---

## Sources

All fetched **2026-08-05** via GitHub REST/search API, raw repository files, HuggingFace API, arXiv, NVD, direct document fetch, a reader proxy for JS-rendered IBM Documentation, and the HN Algolia API. WebSearch was unavailable (session budget exhausted upstream); no claim below rests on a search-result snippet.

### NVIDIA — primary
1. `NVIDIA/NeMo-Retriever` (ex `nv-ingest`; README incl. sample extraction output; 2,958 stars; 233 open issues; releases 24.08→26.05) — https://github.com/NVIDIA/NeMo-Retriever
2. RAG Blueprint repo (723 stars, Apache-2.0) — https://github.com/NVIDIA-AI-Blueprints/rag
3. Support matrix (3×/8× H100, 200 GB disk, Ubuntu 22.04, driver 560, CUDA 12.9) — https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/support-matrix.md
4. Release notes + "All Known Issues" (22 items) — https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/release-notes.md
5. Troubleshooting (deploy timings: Docker 15–30 min, Helm 60–70 min) — https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/troubleshooting.md
6. Agentic RAG limitations (no DAG; guardrails/decomposition dropped; empty metadata) — https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/agentic-rag.md
7. Accuracy benchmarks (7 datasets; Mixtral-8x22B judge; Judge's Verdict selection) — https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/accuracy-benchmarks.md
8. AI-Q Research Assistant blueprint (824 stars; stateless unauthenticated MCP; opt-in guardrails) — https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant
9. NeMo Retriever docs hub / extraction overview — https://docs.nvidia.com/nemo/retriever/ ; https://docs.nvidia.com/nemo/retriever/latest/extraction/overview/
10. Extraction prerequisites & support matrix (256 GB RAM / 32 cores / 24 GB VRAM / 150 GB disk) — https://docs.nvidia.com/nemo/retriever/latest/extraction/prerequisites-support-matrix/
11. NeMo Retriever text-embedding NIM overview — https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/overview.html
12. NVIDIA AI Enterprise licensing guide (per-GPU, serial-number activation, perpetual + 5-yr support) — https://docs.nvidia.com/ai-enterprise/planning-resource/licensing-guide/latest/licensing.html
13. NVIDIA AI Enterprise product page + FAQ (no public pricing; 90-day trial) — https://www.nvidia.com/en-us/data-center/products/ai-enterprise/
14. "NeMo Retriever delivers accurate multimodal PDF data extraction 15x faster" (15×/3×/1.6×/7×/35×/50% claims) — https://developer.nvidia.com/blog/nvidia-nemo-retriever-delivers-accurate-multimodal-pdf-data-extraction-15x-faster/
15. NIM launch press release (vector-DB partner list) — https://nvidianews.nvidia.com/news/generative-ai-microservices-for-developers
16. "NVIDIA text embedding model tops MTEB leaderboard" (69.32 vs 68.28) — https://developer.nvidia.com/blog/nvidia-text-embedding-model-tops-mteb-leaderboard/
17. Model card `llama-nemotron-embed-1b-v2` (8192 ctx, Matryoshka, NVIDIA Open Model License, 35× storage claim, 827,762 downloads) — https://huggingface.co/nvidia/llama-nemotron-embed-1b-v2
18. Model card `llama-nemoretriever-colembed-3b-v1` (ViDoRe #1; license verified `customized-nscl-v1` = Non-Commercial) — https://huggingface.co/nvidia/llama-nemoretriever-colembed-3b-v1
19. CVE-2024-0082 — ChatRTX improper privilege management, CVSS 8.2 HIGH — https://nvd.nist.gov/vuln/detail/CVE-2024-0082

### NVIDIA — issues cited
20. `rag` #66 nv-ingest RAM grows to failure — https://github.com/NVIDIA-AI-Blueprints/rag/issues/66
21. `rag` #181 ingestion hangs — https://github.com/NVIDIA-AI-Blueprints/rag/issues/181
22. `rag` #240 cross-page information not identified — https://github.com/NVIDIA-AI-Blueprints/rag/issues/240
23. `rag` #48 H100 resource requirements (+ "milvus crash out on 2xh100… switch to cpu milvus") — https://github.com/NVIDIA-AI-Blueprints/rag/issues/48
24. `rag` #51 MIG failure at 20 GB slice — https://github.com/NVIDIA-AI-Blueprints/rag/issues/51
25. `rag` #687 duplicate OTEL env rejected by strict admission — https://github.com/NVIDIA-AI-Blueprints/rag/issues/687
26. `rag` #7 Milvus dim 2048 vs 1024 mismatch — https://github.com/NVIDIA-AI-Blueprints/rag/issues/7
27. `rag` #11 Helm permission error; #31 startup probe refused; #30 invalid ports; #44 404 table-structure endpoint; #49 dotenv; #38 otel_ctx; #19 Grafana config; #43 B-series docs; #193 nvstaging pull unauthorized; #618 image 2.5.1 missing; #617 CVE scan tracker; #662 service names not customizable; #17 custom metadata — https://github.com/NVIDIA-AI-Blueprints/rag/issues
28. `NeMo-Retriever` #165 yolox endpoint failure (open since 2024-10-15) — https://github.com/NVIDIA/NeMo-Retriever/issues/165
29. `NeMo-Retriever` #1052 deadlock when paddle not ready ("no fail-fast or clear error") — https://github.com/NVIDIA/NeMo-Retriever/issues/1052
30. `NeMo-Retriever` #966 re-ingests previous documents — https://github.com/NVIDIA/NeMo-Retriever/issues/966
31. `NeMo-Retriever` #2344 reranker via MCP tools; #647 custom metadata; #53 image extraction dtype; #1030 VLM caption prompt; #182 Docker build failure; #450 missing pymilvus dep; #2346 LanceDB index metadata — https://github.com/NVIDIA/NeMo-Retriever/issues

### IBM — primary
32. watsonx.ai RAG pattern overview — https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-rag.html?context=wx
33. Vector index settings (10-file cap; 50 MB/5 MB limits; lowest-max composition rule; field mapping; Chroma/Elasticsearch/Milvus) — https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/vector-index-settings.html?context=wx
34. Supported encoder foundation models (512-token roster; sole reranker `ms-marco-minilm-l-12-v2`, English; all-minilm-l6-v2 withdrawal 2026-06-08) — https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx
35. AutoAI for RAG (20 files / 1 GB sample / 25 QA pairs; 8 CPU 32 GB env; 3,267,000-token cost example) — https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/autoai-programming-rag.html?context=wx
36. watsonx Orchestrate known issues index (last updated 2026-06-26) — https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=notes-known-issues-limitations
37. Building tools known issues (SSRF; "Observability | No"; internal scheduling tools deletable via ADK CLI; multi-file upload with ReAct; remote MCP gateway conflict) — https://www.ibm.com/docs/en/SSAVQO/about/knownissues/building-tools.html
38. Orchestrate Chat known issues (LLM-corrupted signed URLs; HITL unsupported in embedded chat; Paris-region downloads; document upload fails) — https://www.ibm.com/docs/en/SSAVQO/about/knownissues/orchestrate-chat.html
39. Feature parity across deployments (AWS / IBM Cloud / AWS GovCloud / IBM Software Hub / Developer Edition; ADK-only features) — https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=notes-feature-parity-across-deployments
40. Docling repo (64,280 stars; MIT; LF AI & Data; OpenSSF badge; 883 open / 1,055 closed issues; 201 releases to v2.118.0) — https://github.com/docling-project/docling
41. Docling architecture concepts (DocumentConverter, backends, DoclingDocument, HybridChunker) — https://docling-project.github.io/docling/concepts/architecture/
42. `docling-serve` (1,720 stars, MIT) — https://github.com/docling-project/docling-serve
43. Docling technical reports — https://arxiv.org/abs/2408.09869 ; https://arxiv.org/abs/2501.17887
44. IBM Research blog on Docling ("output quality is the best of all the open-source solutions") — https://research.ibm.com/blog/docling-generative-AI
45. `ibm-granite/granite-docling-258M` (512,696 downloads; 1,236 likes; Apache-2.0) — https://huggingface.co/ibm-granite/granite-docling-258M
46. `ibm-granite/granite-embedding-311m-multilingual-r2` (ModernBERT, `max_position_embeddings: 32768`, Apache-2.0) — https://huggingface.co/ibm-granite/granite-embedding-311m-multilingual-r2
47. `ibm-granite/granite-embedding-english-r2` (149M, 8k ctx; MS-MARCO excluded for license reasons; 59.5 avg / 53.1 BEIR self-reported) — https://huggingface.co/ibm-granite/granite-embedding-english-r2
48. `instructlab/instructlab` — archived, 2025-09-02 wind-down notice, components → Red Hat AI Innovation Team (`sdg_hub`, `training_hub`) — https://github.com/instructlab/instructlab
49. IBM Q2 2025 results (>$7.5B gen-AI book of business, no watsonx-specific split) — https://newsroom.ibm.com/2025-07-23-ibm-releases-second-quarter-results
50. watsonx platform background — https://en.wikipedia.org/wiki/Watsonx

### IBM / Docling — issues cited
51. #2209 13 GB memory leak in DoclingParseV2 (open since 2025-09-05) — https://github.com/docling-project/docling/issues/2209
52. #2779 consumes all memory, killed — https://github.com/docling-project/docling/issues/2779
53. #2788 potential memory leak in PDF conversion — https://github.com/docling-project/docling/issues/2788
54. #287 TOC / hierarchy identification for chunking (open since 2024-11-09, 44 comments) — https://github.com/docling-project/docling/issues/287
55. #1023 markdown export only H2 headers — https://github.com/docling-project/docling/issues/1023
56. #3201 SIGABRT on Python 3.12; all versions fail on Databricks Serverless — https://github.com/docling-project/docling/issues/3201
57. #2334 PDF fonts not parsed correctly — https://github.com/docling-project/docling/issues/2334
58. #1111 Invalid code point RuntimeError — https://github.com/docling-project/docling/issues/1111
59. #1256 multi-threading/multi-processing; #115 support concurrency; #1069 progress/logs — https://github.com/docling-project/docling/issues/1256
60. #1308 LocalEntryNotFoundError (air-gap relevance); #603 MultiScaleDeformableAttention build; #2466 missing libgl1 — https://github.com/docling-project/docling/issues/1308
61. #2102 VLM usage docs; #2186 enrichment clarity; #3033 VLM pipeline returns nothing; #2312 cannot disable OCR; #1635 RapidOCR merges text; #960 unreadable output; #828 hyperlinks lost; #2899 fillable PDFs; #1000 IndexError; #1648 empty-slice mean; #1108 missing changelog; #2116 Idefics3ImageProcessor; #3026 CodeFormulaV2 torch_dtype; #1973 AWS Bedrock; #3483 MPS float64 — https://github.com/docling-project/docling/issues

### Third-party / community
62. OmniDocBench (CVPR 2025) — https://github.com/opendatalab/OmniDocBench ; paper https://arxiv.org/abs/2412.07626 ; Jan-2025 leaderboard containing Docling — https://github.com/opendatalab/OmniDocBench/blob/2344c320/README.md
63. HN: "Nvidia NeMo Retriever's Generalizable Agentic Retrieval Pipeline" (2 pts, 0 comments, 2026-03-16) — https://news.ycombinator.com/item?id=47399622
64. HN: "Nvidia OCR" (9 pts, 0 comments) — https://news.ycombinator.com/item?id=43287531
65. HN: NVAIE "$4500 per GPU license" — community figure, **low credibility for the exact number** — https://news.ycombinator.com/item?id=41389079
66. HN: "solutions that happen to run best on GPUs" — https://news.ycombinator.com/item?id=41996912
67. HN: NIM free tier "40 RPM limits" — https://news.ycombinator.com/item?id=48191322
68. HN: "Watsonx: IBM's code assistant for turning COBOL into Java" (127 pts, 178 comments) — https://news.ycombinator.com/item?id=38508250
69. HN: "Watson Health sold off in parts" (687 comments) — https://news.ycombinator.com/item?id=30046432 ; "Watson can't deliver on its promises" (503 pts, 2017) — https://news.ycombinator.com/item?id=14979642
70. HN: watsonx sentiment 2025–26 (stories 46124324 "way over promised and overhyped" / "airgapped AI"; 48674967) ; InstructLab launch (65 pts) — https://news.ycombinator.com/item?id=40285986
71. HN: Docling original posts (13/1, 8/0, 5/0, Nov 2024) — https://news.ycombinator.com/item?id=42033264

**Verification caveats.** (a) Where a number comes from a community comment rather than a primary source it is labeled low-credibility inline (C3, the $4,500/GPU figure). (b) The OmniDocBench Docling figures are dated 2025-01-17 and Docling is absent from the current leaderboard — stated explicitly in D2. (c) All vendor throughput/accuracy claims are labeled as vendor-measured; none were independently replicated. (d) `ibm.com/docs` and `cloud.ibm.com/docs` required a reader proxy to fetch; the extracted text was cross-checked against IBM's own on-page anchors and quoted verbatim. (e) Reddit was unavailable, so no Reddit sentiment is represented.

**(f) Provenance of carried-forward claims — read this before citing.** This dossier consolidates two evidence-gathering passes on the same target. The following claims were compiled in the earlier pass and were **not re-fetched** in the final pass; they are attributed to vendor announcements or model cards and should be re-verified before appearing in a published paper: the MTEB June-2024 figures (69.32 / 68.28), the ViDoRe V1/V2/MTEB-VDR nDCG@5 figures (0.9100 / 0.6352 / 0.8315), the `granite-embedding-english-r2` self-reported 59.5 avg / 53.1 BEIR / ~144 docs-per-second numbers and its MS-MARCO-exclusion rationale, the IBM Q2-2025 ">$7.5B gen-AI book of business" figure, the extraction-library floor of 256 GB RAM / 32 cores / 24 GB VRAM, LanceDB as a third default vector store, the ChatRTX companion CVE-2024-0083 (XSS), the IBM Research blog quote "the output quality is the best of all the open-source solutions," Docling issues #2466 (missing `libgl1`) and #603/#1973/#3483 comment counts, the HN story IDs 46124324 / 48674967 / 14979642 and the Watson-era point totals, and the "10k stars in under a month / #1 GitHub trending Nov 2024" adoption detail.

Claims **re-verified in the final pass with primary sources** include: D1 (README garbled sample output — strings `Giraffe | Driving | a | car`, `Gira@e`, `o@ice`, triplicated Table/Chart 1–3, grepped from `main`), S5 (`colembed-3b-v1` license `customized-nscl-v1`), S6 (NVD API: `cvssMetricV31` baseScore 8.2 HIGH plus verbatim description), S7 (AI-Q README roadmap items and guardrails wording), R3/#960 open and /#828 closed with comment counts, `docling-serve` 1,720 stars, `granite-embedding-311m-multilingual-r2` `config.json`, all HuggingFace download counts, all NVIDIA blueprint doc quotes (support matrix, release notes, troubleshooting, agentic-rag, accuracy-benchmarks), all IBM watsonx doc quotes (RAG pattern, vector index settings, encoder models, AutoAI, three known-issues pages, feature parity), the OmniDocBench Jan-2025 table (read from commit `2344c320`) and Docling's absence from the current leaderboard, GitHub issue numbers/states/dates/comment counts for every issue cited with a date, and the HN Algolia hit counts underpinning the community-sentiment section.
