# RAGFlow (InfiniFlow) — Framework Autopsy

> Evidence-based deep autopsy of RAGFlow as of August 2026. Steelman first, then dissect.
> Every issue carries a concrete evidence pointer and a confidence label:
> `documented-recurring` / `single-anecdote` / `architectural-inference`.

---

## Identity & adoption

| Field | Value |
|---|---|
| Maintainer | InfiniFlow (Shanghai-based AI-infrastructure company; also maintains the Infinity hybrid-search database) |
| License | Apache-2.0 (repo); note early community caution that some YOLO/ultralytics-lineage vision components are AGPL-3 upstream (HN 39896923) |
| GitHub | ~86.9k stars, ~10.2k forks, ~1.9k open issues (GitHub API, Aug 5 2026) |
| Created | Dec 2023; open-sourced April 2024 |
| Current version | v0.26.4 (July 2026) — still pre-1.0 after 2.5 years |
| Funding | Opaque; "limited public funding and team transparency" (Tekai analysis via Crunchbase/PitchBook profiles); monetizes via managed cloud "base subscription + add-on packs + enterprise customization" |
| Momentum | One of the fastest-growing OSS projects by contributor engagement — reported ~2,596% YoY contributor-activity growth in 2025 (aixyz.ca summary); very frequent releases (roughly monthly minor versions) |
| Positioning | "Leading open-source RAG engine that fuses cutting-edge RAG with Agent capabilities to create a superior context layer for LLMs" (repo tagline) |

RAGFlow is not a library like LangChain/LlamaIndex — it is a **self-hosted product**: a Docker-composed, multi-service platform (web UI + API + background workers + 4–5 stateful stores) that you operate, not import.

---

## Retrieval-pipeline architecture

Sources: repo README, DeepWiki architecture pages (deepwiki.com/infiniflow/ragflow), ragflow.io docs, release notes.

### Deployment topology
- **API tier**: Python Quart async server (REST + Python/HTTP SDKs); newer high-throughput paths (ingestion/sync/search admin) in a **Go server** (added in the 2025–26 refactors).
- **Task Executor** (`rag/svr/task_executor.py`): background worker consuming **Redis Streams** for parsing/embedding/indexing jobs. This process is the chronic hotspot for memory/CPU complaints (see Issues).
- **Storage**: MySQL/PostgreSQL (metadata, via Peewee ORM), **Elasticsearch by default** for combined full-text + vector index, **MinIO** for raw files, **Redis/Valkey** for queues. `DOC_ENGINE` env var can switch ES → **Infinity** (InfiniFlow's own DB), OpenSearch, OceanBase, or SeekDB.
- **Sandbox Manager**: gVisor-isolated code execution for agent code nodes (added after code-exec CVEs; see Security).
- Minimum stated requirements: **4 cores / 16 GB RAM / 50 GB disk**, Docker ≥ 24 (README). Slim image ≈ 2 GB compressed / ~7 GB unpacked on disk (docs + issue #10992).

### Ingestion → parsing
- **DeepDoc** is the differentiator: an in-house visual document-understanding pipeline — OCR, document **layout recognition**, and **table structure recognition (TSR)** models (YOLO-family vision models) that reconstruct semantic structure from PDFs/DOCX/scans before chunking. Since v0.18, a VLM can replace/augment layout recognition; v0.22 added the **Docling** parser as an alternative; MinerU can be plugged in via `MINERU_BACKEND`/`MINERU_SERVER_URL` (issue #11622).
- v0.21 introduced **orchestratable ingestion pipelines**: a canvas-based DAG for custom parse→transform→index flows, plus **table-of-contents extraction** explicitly motivated by "context loss caused by inaccurate or excessive chunking" (release notes) — an implicit admission that flat template chunking loses document-level context.
- **Data connectors** (v0.26+): S3, Confluence, Notion, Google Drive, SharePoint, Slack, BigQuery, Outlook/Teams, Salesforce, with incremental sync.

### Chunking
- **Template-based chunking**: user picks a per-knowledge-base template — General/Naive, Book, Paper, Laws, Manual, Table, Q&A, Resume, Presentation, Picture, One, Tag. Templates encode structure heuristics (e.g., Laws splits on Chapter/Article regexes; Table serializes each row with headers as `Key: Value`; Manual splits on heading styles). Chunks are **visualized in the UI and human-editable** — "explainable chunking" is a genuine UX innovation.
- v0.26-era addition: child/parent ("child chunking") dual-layer strategy docs.
- Independent benchmarking of the templates (kdjingpai.com) found they work as advertised on well-formed docs but: Manual silently fails on bold-text pseudo-headings; Q&A is "merely a specialized TABLE application"; and — significantly — **metadata exists only at document level, with no chunk-level metadata and no metadata-filtered retrieval API**.

### Embedding & indexing
- Pluggable embedding models (BYO API or local); pre-v0.22 "full" images bundled embedding models, dropped from v0.22 onward (slim-only shipping).
- Hybrid index: dense vector + BM25 full-text (+ sparse in Infinity). RAGFlow's FAQ states only ES and Infinity qualify as doc engines because RAGFlow **requires** full-text + vector hybrid in one store — pure vector DBs are unsupported.
- Optional enrichment: auto-keyword and auto-question generation per chunk (LLM calls — flagged in RAGFlow's own acceleration docs as a cost/latency multiplier), auto-tagging, **GraphRAG** (entity/relation extraction into a KG per KB) and **RAPTOR** (hierarchical summary tree). Since v0.21, GraphRAG/RAPTOR moved from automatic incremental building to **manual batch construction** — another retreat from an over-ambitious default.

### Query handling → retrieval → rerank → synthesis
- Query side: optional keyword extraction, multi-turn query rewrite, cross-language search (v0.19), knowledge-graph lookup, "Deep Research" iterative reasoning mode (v0.17).
- Retrieval: weighted fusion of keyword similarity and vector cosine, defaults **similarity threshold 0.2, vector weight 0.3 / keyword 0.7** (docs: run_retrieval_test). With a rerank model enabled, vector score is replaced by rerank score — and the docs warn reranking "will significantly increase the time to receive a response". Built-in ONNX rerank models were **removed in v0.18** "due to minimal impact versus performance costs" (release notes).
- KG chunks bypass hybrid search and use pure cosine (docs) — an inconsistent scoring regime inside one pipeline.
- Synthesis: templated chat with **grounded citations** to chunk provenance (a signature feature), configurable LLM per assistant; Text2SQL, cross-KB search.
- Tuning caveat straight from docs: retrieval-test settings "will not be automatically saved" to the assistant — a recurring user footgun.

---

## Agentic integration

- **Agent/workflow canvas**: no-code visual DAG (DSL-backed) unifying "Agents and Workflows" since the v0.20 rewrite (Aug 2025) — tool-calling agent nodes, loops, code-exec nodes, retrieval components.
- **MCP**: v0.18 exposed RAGFlow as an MCP server; v0.20 added MCP-client import of external tool servers.
- **Memory**: user-level memory storage/retrieval APIs added v0.24 (Feb 2026), memory interface v0.23 — late additions bolted onto the chat/agent layer, not a first-class memory substrate.
- **Sandbox**: gVisor code execution + chart generation (v0.25).
- Reality check: the agent layer is a **workflow engine with an agent skin**. The v0.20 rewrite was a hard break — "all existing Agents from previous versions must be rebuilt following the upgrade" (release notes). Retrieval is exposed to agents as a canvas component, not as a queryable service with fine-grained filters (no chunk-metadata filtering per kdjingpai analysis), which limits precise agentic retrieval. Multiple RCEs shipped through the agent path (ExeSQL SQLi, Canvas CodeExec RCE, Jinja2 prompt-generator injection — see Security), indicating agent features outran hardening.

---

## Strengths (steelman)

1. **Best-in-class open-source document understanding at ingestion.** DeepDoc's layout/OCR/TSR pipeline demonstrably beats naive text extraction and even paid services on hard tables — an HN user reported RAGFlow "correctly identify tables that paid models like AWS Textract Document Analysis API fail to identify" (HN 40351510 thread family). The core thesis — "quality in, quality out"; most RAG failure is parsing failure — is correct and validated by later benchmarks like OHRBench/OmniDocBench showing OCR noise cascades into RAG accuracy.
2. **Explainable, human-in-the-loop chunking.** Visualizing chunks against the source page and letting operators edit them is a genuinely differentiated UX that most frameworks still lack.
3. **Hybrid search by default.** BM25 + dense fusion out of the box (with grounded citations) reflects hard-won practice; a 2026 reviewer noted hybrid "consistently outperformed pure vector search for technical documentation" (scored.tools review).
4. **End-to-end product completeness.** UI, multi-user teams, connectors with incremental sync, agent canvas, MCP, Langfuse tracing integration, GraphRAG/RAPTOR — one deployable system rather than a pile of libraries. Maintainers have real scale experience (claim of scaling search to "15M papers" on ES, r/LangChain thread).
5. **Velocity and responsiveness.** Monthly releases, fast CVE patching post-2025, honest engineering retreats (removing weak built-in rerankers, making GraphRAG manual) show a team that measures and corrects.
6. **Apache-2.0 with a real company behind it**, and the Infinity DB bet gives a coherent long-term "RAG database" story.

---

## Issues & failure modes

### production-ops

- **[critical | documented-recurring] Chronic memory leaks and unbounded memory growth in the task executor / server.**
  Evidence: issue #4031 "documents parsing complete, but the memory is not released"; #7995 "Memory leak? after updating to v0.19.0" (RAM climbs to 100% on an idle 16 GB API-only deployment, needs Docker restarts); #11296 task_executor idling at ~12.8 GB (>40% of host RAM); #7602 "High Memory and CPU Usage During PDF Parsing" (CPU pegged at 99% regardless of doc size); #7622; #11822 "Deepdoc pdf parsing consumes too much memory" (OOM even with 62 GB RAM). Mitigation PR #14973 ("save startup memory… 200MiB") shows ongoing triage, not resolution.
- **[major | documented-recurring] Parsing stalls/hangs are so common they headline the official FAQ.** FAQ dedicates entries to progress "stalls at under one percent" or "near completion", attributing them to OOM-killed executors, dead task-executor processes, Redis queue buildup ("xxx tasks are ahead in the queue"), and network fetches of model weights (ragflow.io/docs/faq).
- **[major | documented-recurring] Heavyweight multi-service monolith with fragile inter-service dependencies.** Minimum 4 CPU/16 GB/50 GB; slim image ~2 GB compressed / ~7 GB on disk (docs; issue #10992); mandatory ES + MySQL + MinIO + Redis. FAQ troubleshoots recurring "Can't connect to ES cluster" and notes "container status does not necessarily reflect service status". Early community verdict: "immature and in terrible state deployment-wise" (r/LocalLLaMA 1cm6u9f); a 2026 review still says self-hosting "requires significant technical expertise… Kubernetes, Docker, and distributed systems" (scored.tools).
- **[major | single-anecdote→architectural-inference] No documented horizontal-scale story.** Issue #6213 "[Question]: production deployment — can it handle multiple simultaneous requests on a large scale?" sat unanswered/unassigned. Scale-out guidance (multi-executor sharding, ES sizing) is folklore, not docs.
- **[minor | documented-recurring] Infinity, the in-house "preferred future" engine, is still not production-stable.** Issue #7917 advises keeping Elasticsearch "until Infinity is more stable"; #5999 crashes under large file volumes with the workaround "remove all data in Infinity directory… re-insert all files"; docs concede Infinity will become default only "once fully mature".

### performance-cost

- **[major | documented-recurring] DeepDoc parsing is extremely slow/costly on CPU, and GPU support is flaky.** Issue #9382 "Using deepdoc for OCR is too slow, and using GPU is not fast either"; #5088 a 2 MB/68-page PDF "parsed 3 hours and still" incomplete (GraphRAG path); #8805 DeepDoc silently falls back to CPU on Windows+Docker despite correct GPU config, causing OOM. Official "accelerate_doc_indexing" doc tells users to disable auto-keyword/auto-question — RAGFlow's own enrichment defaults are the cost driver.
- **[major | documented-recurring] GraphRAG/RAPTOR options are token- and time-hungry at scale.** KG chunking of an 875-page PDF exhausted 32 GB RAM (issue #4668); entity/relation embedding done "one-by-one instead of in batches" (#16205); project retreated to manual batch KG construction in v0.21 (release notes). Docs also warn KG retrieval "will significantly increase" response time.
- **[minor | single-anecdote] LLM serving overhead:** VRAM usage via RAGFlow "much higher than… ollama run qwen3:14b" directly (issue #7859).

### security-governance

- **[critical | documented-recurring] A sustained string of serious CVEs, several RCE-class, across the agent/execution surface.**
  - CVE-2025-27135 — SQL injection: ExeSQL component "extracts the SQL statement from the input and sends it directly to the database query" (≤0.15.1; NVD noted no patched version at publication).
  - CVE-2025-25282 — IDOR enabling **cross-tenant** account listing/modification by any authenticated user (NVD) — a direct hit on the team/tenant feature set.
  - CVE-2025-68700 — RCE in the Canvas CodeExec component (<0.23.0).
  - CVE-2026-45312 — authenticated Jinja2 template-injection RCE via the prompt generator (SentinelOne/Halo Security).
  - CVE-2026-24770 — RCE (SentinelOne); CVE-2026-28797 — CVSS 8.8 (Glexia); GHSA-v7cf-w7gj-pgf4 — Zip-Slip arbitrary file overwrite → RCE via malicious ZIP.
  Pattern: product features (SQL nodes, code nodes, template prompts, archive ingestion) repeatedly shipped without input hardening; gVisor sandboxing arrived only in v0.25 (2026), after exploitation classes were public.
- **[major | architectural-inference] Coarse governance model.** Multi-tenancy exists (teams/KBs) but there are no document/chunk-level ACLs propagated into retrieval, and the IDOR CVE shows tenant isolation was enforceable at the app layer only — inadequate for regulated-enterprise RAG.

### data-processing

- **[major | documented-recurring] No chunk-level metadata and no metadata-filtered retrieval.** Independent benchmark of the chunk templates: "System lacks chunk-level metadata support (only document-level available)… No built-in metadata-based filtering in retrieval APIs" (kdjingpai.com/en/ragflow-wendangqiepian/). This caps precision for agentic/filtered retrieval and forces KB-per-facet workarounds.
- **[major | documented-recurring] Template chunking is brittle outside its happy path.** Manual template requires true heading styles ("plain bold text goes unrecognized" — kdjingpai); early HN review found the multi-parser design inconsistent: "mixing multiple PDF parsers… it's not clear which one it defaults to as it seems to be different in different places" (HN 39896923). RAGFlow itself shipped ToC extraction in v0.21 to fix "context loss caused by inaccurate or excessive chunking" (release notes) — self-acknowledged structure loss.
- **[minor | documented-recurring] Retrieval returns nothing after "successful" parsing** — silent index/version mismatches, e.g. issue #8001 (retrieval test returns 0 chunks despite successful parse, tied to specific image versions).

### retrieval-quality

- **[major | architectural-inference (with doc evidence)] Static, hand-tuned fusion defaults with no learning loop.** Defaults are similarity-threshold 0.2 and 0.7 keyword / 0.3 vector weight (docs) — sensible for CJK-heavy enterprise corpora but unvalidated per-domain, and there is "no automatic optimization; you'll spend time optimizing chunk sizes, embedding models, and re-ranking parameters" (scored.tools review). Retrieval-test tunings silently don't persist to assistants (docs) — a UX trap that leaves production on defaults.
- **[minor | documented-recurring] Rerank story regressed.** Built-in rerank models were removed in v0.18 for "minimal impact versus performance costs" (release notes), and docs warn external rerankers significantly slow responses — so the "fusion re-ranking" marketing headline in practice defaults to weighted-sum-only.
- **[minor | documented-recurring] Inconsistent scoring regimes:** KG-derived chunks scored by pure cosine while normal chunks use hybrid fusion (docs) — results from the two paths are not calibrated against each other.

### evaluation-observability

- **[major | architectural-inference (with community evidence)] No built-in retrieval-quality evaluation loop.** Assessment relies on the manual "retrieval test" UI; there are no golden-set/regression evals, no answer-quality metrics, no A/B of chunk templates. Tracing exists only via third-party Langfuse integration (langfuse.com/integrations/no-code/ragflow); evaluation tracking is a community feature request (issue #6155). A HN commenter generalized the gap: RAG platforms "spend too much energy on UI/playgrounds" while lacking "proper tracing, versioning of entire LLM callchains" (zwaps, HN 42381139).
- **[minor | documented-recurring] No published benchmarks for DeepDoc/retrieval.** From launch, reviewers asked "How well does it work? Please include benchmarks" and criticized vague "deep document understanding" claims (esafak, HN 39896923). As of 2026 there is still no official OmniDocBench/OHRBench-style evaluation of DeepDoc vs MinerU/Docling/Marker — the quality-vs-marketing gap is unfalsifiable by design.

### abstraction-design

- **[major | documented-recurring] Closed-world, non-reusable components.** "I'm partly sad at the approach this and other engines take: reimplement each part (PDF parser, etc.) in a way where they are pretty much useless except in their specific engine" (zzleeper, HN 39896923). DeepDoc, templates, and retrieval are usable only inside the RAGFlow deployment; the API-first product is "opinionated… constraining for teams preferring ad-hoc scripting" (sider.ai review).
- **[major | architectural-inference] Pipeline opacity.** The parse→template→enrich→index chain runs inside the task executor with progress percentages as the primary signal; when it stalls, the FAQ prescribes grepping container logs. There is no per-stage inspection API (which parser fired, which template rule matched, why a chunk boundary landed where it did) beyond the final chunk view.

### dx-docs

- **[major | documented-recurring] Breaking changes across minor versions of a pre-1.0 product used in production.** v0.20: "all existing Agents from previous versions must be rebuilt" (release notes); v0.22: slim-only image shipping changed tags/behavior; v0.26.4 upgrade FAQ documents "Request error 404: undefined" requiring explicit tags/source updates; v0.20.2 shipped "multiple interface problems" forcing rollbacks or nightly images (issue #9572); Python floor jumped to 3.13 (v0.25.5).
- **[minor | documented-recurring] Docs lag features; troubleshooting is thin.** "Advanced configuration and troubleshooting information is sparse" (scored.tools); local/offline deployment was possible-but-undocumented at launch (rosspackard, HN 39896923); with ~1.9k open issues the tracker doubles as the real documentation.

### agentic-integration

- **[minor | architectural-inference] Agent layer is a workflow DSL, retrieval is a node, memory arrived late (v0.24) as an API rather than a substrate.** For an external agent (e.g., via MCP) RAGFlow is a decent retrieval tool, but the absence of chunk-metadata filters, scoped ad-hoc queries, and calibrated scores makes fine-grained agentic retrieval control impossible without forking. The hard v0.20 agent-format break shows agent definitions are not treated as durable artifacts.

---

## Community sentiment over time

- **2023-12 → 2024-04 (launch):** Strong technical interest in DeepDoc ("the layout recogniser model hosted on huggingface is pretty good!"), tempered by immediate demands for benchmarks, modularity complaints, licensing caution (AGPL YOLO lineage), and limited LLM support (HN 39896923). Reddit r/LocalLLaMA early verdict: "immature and in terrible state deployment-wise."
- **2024–2025:** Steady feature cadence (GraphRAG, RAPTOR, Text2SQL, Deep Research, MCP, agent canvas) with heavy self-promotion by maintainer accounts (yingfeng, vissidarte_choi, demilich, KevinHuSh) on HN — most RAGFlow HN threads are maintainer-posted with thin organic discussion (e.g., 40936082: 13 points/5 comments). Meanwhile the issue tracker fills with memory/parsing/stability reports (#4031, #4668, #5088, #7602, #7622, #7995).
- **2025:** Security year — SQLi, IDOR, code-exec CVEs land; project responds with sandboxing and patches. v0.20 agent rewrite breaks all existing agents.
- **2026:** Mainstream acceptance as the default self-hosted "RAG appliance" (~87k stars, huge contributor growth; positive third-party reviews ~7/10), but with a stable critique set: operational heaviness, hand-tuning burden, sparse advanced docs, opaque enterprise pricing, and continuing memory/OOM issue flow (#11296, #11822). Sentiment pattern: **admired ingest quality, tolerated ops pain, unverified retrieval claims.**

---

## Benchmarks & third-party evaluations

- **No official benchmarks exist** for DeepDoc parsing accuracy or end-to-end retrieval quality — requested since launch (HN 39896923) and still absent in 2026. This is the single biggest evidence gap for the project's central claim ("quality in, quality out").
- **kdjingpai.com chunk-template benchmark** (independent, 2025): templates behave as designed on well-formed Chinese legal/tabular docs; found Manual's heading-style dependency, Q&A ≈ Table, and the missing chunk-metadata/filtering layer; concluded "a production-grade RAG system is much more than" slicing.
- **Anecdotal head-to-heads:** RAGFlow's TSR beat AWS Textract on specific hard tables (HN); no controlled study.
- **Adjacent academic context:** OmniDocBench (arXiv:2412.07626) and OCR-noise-cascade studies validate RAGFlow's *thesis* that parsing dominates RAG quality, but none of the major parsing benchmarks report a DeepDoc row vs MinerU/Docling/Marker — notable given RAGFlow itself added Docling and MinerU backends (v0.22; issue #11622), implicitly conceding DeepDoc is not always best/fastest.
- **Comparison literature** (sider.ai, Medium platform comparisons) is directional only: "Dify is easier for newcomers, while RAGFlow tends to appeal to experts who want fine-grained retrieval control" — none measure answer quality.
- Academic PoCs (e.g., arXiv:2511.08600, pediatric SLP vignette generation) use RAGFlow as infrastructure but do not evaluate the framework itself.

---

## Lessons for a next-generation framework

1. **Ingestion quality is the right hill — but it must be benchmarked and decoupled.** DeepDoc proved structure-aware parsing is the highest-leverage RAG stage; its non-reusability and unbenchmarked claims squandered trust. Ship parsing as an independently benchmarked, embeddable component (RAGFlow later bolting on Docling/MinerU proves demand for pluggability).
2. **Explainable chunking should extend to explainable retrieval.** RAGFlow visualizes chunks but not *why* a chunk was retrieved/ranked; per-stage inspection (parser choice, template rule, fusion contribution) must be first-class, not log-grepping.
3. **Chunk-level metadata + filtered retrieval is table stakes for agentic use.** Document-level-only metadata caps precision and forces KB proliferation.
4. **Background enrichment must be budgeted and elastic.** Unbounded LLM enrichment (auto-keyword/question, GraphRAG one-by-one embedding) produced OOMs, 3-hour parses, and cost blowups; a next-gen framework needs per-corpus token/compute budgets, batch APIs, and resumable/streaming ingestion with hard memory ceilings (the task-executor OOM saga is the anti-pattern).
5. **Evaluation must be built in, not bolted on via Langfuse.** Golden-question regression sets per KB, template A/B, and drift alarms would have caught most "retrieval returns 0 chunks" and "defaults never tuned" failures.
6. **Agent surfaces are attack surfaces.** SQL/code/template nodes require sandboxing and tenancy enforcement from day one; RAGFlow's CVE string (SQLi → IDOR → CodeExec RCE → Jinja2 RCE → Zip-Slip) is the canonical cautionary tale.
7. **Appliance ergonomics vs. operational weight is a false dichotomy.** 16 GB minimum, 5 stateful services, and fragile ES coupling drive away exactly the mid-size teams the UI targets; a next-gen system needs a single-binary/dev mode that scales to the distributed topology without config divergence.
8. **Pre-1.0 semantics with production users is a governance failure.** Rebuilding all agents at v0.20 and image-tag breaks at v0.22 argue for versioned, migratable artifacts (pipelines, agents, KB schemas) as durable contracts.

---

## Sources

**Repo / official**
- https://github.com/infiniflow/ragflow (README, stats: 86.9k★, Apache-2.0, v0.26.4; GitHub API: 1,892 open issues, created 2023-12-12)
- https://ragflow.io/docs/faq — parsing stalls, MEM_LIMIT, ES connectivity, queue buildup, upgrade 404s
- https://ragflow.io/docs/run_retrieval_test — defaults (threshold 0.2, vector weight 0.3), rerank/KG latency warnings, non-persisting settings
- https://ragflow.io/docs/release_notes — v0.18–v0.26 features; v0.20 agent-rebuild breaking change; v0.22 slim-only; rerank-model removal; ToC-extraction rationale
- https://ragflow.io/docs/accelerate_doc_indexing; https://ragflow.io/docs/build_docker_image
- https://deepwiki.com/infiniflow/ragflow — architecture (Quart+Go, task executor, storage tiers, canvas DSL)

**GitHub issues (evidence anchors)**
- Memory/perf: #4031, #4668, #5088, #7602, #7622, #7859, #7995, #9382, #11296, #11822, #16205; PR #14973
- Stability/ops: #5999, #7917 (Infinity), #6213 (production scale, unanswered), #8001, #8279, #8805, #9572, #10992, #11622
- Agent/eval: #6145 (canvas data-flow bug), #6155 (evaluation/tracing feature request)

**Security**
- CVE-2025-27135 (ExeSQL SQLi, NVD); CVE-2025-25282 (IDOR cross-tenant, NVD); CVE-2025-68700 (Canvas CodeExec RCE); CVE-2026-45312 (Jinja2 RCE, SentinelOne/Halo); CVE-2026-24770 (RCE, SentinelOne); CVE-2026-28797 (CVSS 8.8, Glexia); GHSA-v7cf-w7gj-pgf4 (Zip-Slip RCE)

**Community**
- HN: https://news.ycombinator.com/item?id=39896923 (launch critiques: parsers, modularity, AGPL, benchmarks); 40351510 (vs ZenDB); 40936082 (GraphRAG positioning); 42381139 (zwaps on tracing gap); 42460501; 43253467; 44834725
- Reddit: r/LocalLLaMA 1cm6u9f ("immature… terrible state deployment-wise"); r/LocalLLaMA 1bt1kb5; r/MachineLearning 1btycwl; r/LangChain 1d3fy9h (15M-paper ES scaling claim)

**Third-party reviews / benchmarks**
- https://www.kdjingpai.com/en/ragflow-wendangqiepian/ — chunk-template benchmark; chunk-metadata gap
- https://scored.tools/blog/ragflow-review-2026/ — 7.2/10; setup complexity, no auto-optimization, docs gaps
- https://sider.ai/blog/ai-tools/ragflow-review-is-this-open-source-rag-engine-ready-for-production — infra footprint, opinionated API
- https://aixyz.ca/ragflow-the-open-source-rag-engine-thats-changing-how-ai-handles-knowledge/ — 2026 adoption/contributor growth
- https://langfuse.com/integrations/no-code/ragflow — external tracing integration
- arXiv:2412.07626 (OmniDocBench); arXiv:2511.08600 (RAGFlow-based PoC)
- InfiniFlow company: LinkedIn/Crunchbase profiles via Tekai analysis (funding opacity); enterprise pricing via GitHub discussions
