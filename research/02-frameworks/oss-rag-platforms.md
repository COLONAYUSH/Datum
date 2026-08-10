# OSS RAG Platforms: R2R, Onyx (Danswer), AnythingLLM, Verba, Kotaemon, Cognita, Morphik

Autopsy date: 2026-08-05. This file covers seven open-source "RAG platform" products (turnkey engines/apps, as opposed to composition libraries like LangChain/LlamaIndex). The headline finding, established with repo-level evidence below: **the OSS RAG-platform category has a survivorship crisis.** Of the seven platforms examined, as of August 2026 two are formally archived (Verba, Cognita), one is dormant with unpatched critical security vulnerabilities (R2R, no commit since 2025-11-07), one has pivoted its company entirely out of the RAG business while keeping the OSS repo as a trailing artifact (Morphik), one has pivoted its product identity from enterprise search to generic chat UI (Onyx), and one answers "is this still developed?" with silence (Kotaemon). Only AnythingLLM retains both momentum and its original mission — and it carries the longest CVE tail of the group.

---

## Identity & adoption

Snapshot pulled live from the GitHub API on 2026-08-05:

| Platform | Repo | Stars | License | Last push | Open issues | Status |
|---|---|---|---|---|---|---|
| AnythingLLM | Mintplex-Labs/anything-llm | 64,370 | MIT | 2026-08-05 (active) | 318 | Active; desktop + Docker |
| Onyx (ex-Danswer) | onyx-dot-app/onyx | 31,433 | MIT + proprietary EE (`NOASSERTION`) | 2026-08-05 (active) | 392 | Active; pivoted to "chat UI / application layer for LLMs" (Launch HN, Nov 2025) |
| Kotaemon | Cinnamon/kotaemon | 25,689 | Apache-2.0 | 2026-07-14 | 239 | Sporadic; unanswered "is it developed?" discussion (#778) |
| R2R | SciPhi-AI/R2R | 7,947 | MIT | **2025-11-07** | 122 | **Dormant ~9 months**; docs site down; unpatched security issues |
| Verba | weaviate/Verba | 7,713 | BSD-3-Clause | 2026-06-08 | 78 | **Archived** — "will not receive further updates, bug fixes, security patches" |
| Cognita | truefoundry/cognita | 4,414 | Apache-2.0 | 2026-03-13 | 22 | **Archived 2026-03-13** — "no longer actively maintained" |
| Morphik Core | morphik-org/morphik-core | 3,697 | **BUSL-1.1** (`NOASSERTION`; not OSI open source) | 2026-07-23 | 60 | Repo alive, but company pivoted to "AI workers for skilled nursing & senior living" |

Maintainers/backers: AnythingLLM — Mintplex Labs (VC-backed startup, also sells hosted/desktop). Onyx — YC W24, VC-funded ([Launch HN](https://news.ycombinator.com/item?id=46045987), 254 points). Kotaemon — Cinnamon Inc. (Japanese enterprise-AI company; the tool is a side project of a services firm). R2R — SciPhi-AI (startup; sciphi.ai failed TLS handshake when fetched 2026-08-05, and the R2R docs site outage went unfixed — see issue #2274). Verba — Weaviate (built as a showcase for their vector DB; Weaviate now points users to its "Elysia" agentic assistant instead). Cognita — TrueFoundry (MLOps platform company; RAG framework was adjacent to core business). Morphik — YC-backed startup, now a vertical back-office-automation company.

---

## Retrieval-pipeline architecture

### R2R (SciPhi-AI)
- **Promise:** "SoTA production-ready AI retrieval system. Agentic RAG with a RESTful API." Opinionated engine (explicitly *not* a framework), Postgres/pgvector-centric with knowledge-graph construction.
- **Ingestion/parsing/chunking:** server-side ingestion API; multimodal parsers (PDF, images, audio w/ transcription); automatic entity/relationship extraction into a graph ("GraphRAG-style" community building). Originally required pgvecto-rs, which blocked managed Postgres (RDS/CloudSQL/Azure) deployment — flagged on HN at V2 launch.
- **Indexing/query:** hybrid semantic + full-text search in Postgres, HyDE, reranking, collection-scoped ACLs, users/documents as first-class API objects.
- **Synthesis:** RAG and multi-step "agentic" retrieval endpoints (`/rag`, agent with retrieval tools), streaming, citations.
- **Extensibility:** TOML config for providers; V2→V3 was a full API rewrite (Dec 2024, "V3 API Release"), a documented breaking-change cliff.

### Onyx (formerly Danswer)
- **Promise (original):** enterprise search — 40+ connectors (Slack, Confluence, Jira, Drive, GitHub…), document-level permission sync, hybrid search. **Promise (2025+):** "the application layer for LLMs" — chat UX first, RAG one feature among many.
- **Architecture:** microservices — Postgres (metadata), **Vespa** (vector + keyword index), Redis, MinIO, background workers for connector indexing jobs, separate model-inference servers. Default Docker compose is ~12 containers needing ~4 vCPU/10 GB RAM (self-reported by founders in the Launch HN thread when challenged).
- **Ingestion:** pull-based connector framework with periodic re-sync; chunking + embedding in background workers; document-level ACL mirroring gated to Cloud/Enterprise Edition.
- **Query:** hybrid retrieval from Vespa, reranking, query expansion; chat layer adds agents/web search/MCP.

### AnythingLLM (Mintplex Labs)
- **Promise:** all-in-one desktop + server AI app: "chat with your documents" with any LLM, any embedder, any vector DB (LanceDB default), agents, MCP.
- **Pipeline:** upload → text conversion → fixed chunking → embedding → workspace-scoped vector store. Query flow, per its own docs: vectorize query → cosine top-k (4–6 chunks) → similarity-threshold filter → stuff into system prompt. The official docs page "LLM not using my documents" concedes "there is no guarantee that relevant text stays together" during chunking and that results depend heavily on settings tuning.
- **Escape hatch:** document "pinning" — inject the *entire* document into context, bypassing retrieval; users have asked to automate this (issue #3587), i.e., to abandon retrieval whenever it matches anything.
- **Notably absent by default:** hybrid/keyword search (open feature request #4338), reranking, graph retrieval (#1008 open since 2024).

### Verba (Weaviate) — archived
- Cleanest modular design of the group: five swappable component types — Reader (ingestion incl. Unstructured, Firecrawl, AssemblyAI), Chunker (token/semantic/recursive/HTML/Markdown/code/JSON), Embedder (OpenAI/Cohere/Ollama/…), Retriever (hybrid search on Weaviate), Generator. A textbook reference architecture — and now a textbook example that clean architecture doesn't fund maintenance.

### Kotaemon (Cinnamon)
- Gradio-based document-QA app: multi-user, file collections, hybrid retrieval with reranking, citations with in-browser PDF preview, and GraphRAG/LightRAG/nano-graphrag integrations as optional indices. Pipeline extensible via Python classes. GraphRAG integration is the flagship differentiator and its most bug-reported surface.

### Cognita (TrueFoundry) — archived
- API/deployment-first modular RAG: separate **Indexing Job** (scan→parse→chunk→embed), **Metadata Store** (collections, parser configs, embedder associations), and **Query Controllers** (RAG endpoints auto-registered as FastAPI routes), incremental indexing. Positioned as "LangChain/LlamaIndex organized for production." Archived 2026-03-13.

### Morphik Core
- **Promise:** multimodal-first retrieval — treats PDF pages as images embedded with ColPali/ColQwen (layout, charts, diagrams preserved), plus knowledge graph, rules-based metadata extraction (bounding boxes, classification), KV-cache-augmented generation, MCP server, LiteLLM for models.
- **Honest framing in its own README:** "Traditional RAG approaches that work in proof-of-concepts often fail spectacularly in production" — the category's demo-vs-production gap stated by a vendor.
- **Reality checks:** ColPali-style ingestion cost 15–20 s/page on an M2 laptop, 4–5 s/page on an A100 (founders' own numbers in the Show HN thread); BUSL-1.1 license; "we cannot provide full support for self-hosted deployments"; the recommended path is the hosted service.

---

## Agentic integration

- **R2R** was earliest to market with an "agentic RAG" agent endpoint (retrieval tools, multi-step reasoning, extended thinking) — but it is now frozen in its Nov-2025 state; open feature requests for agent memory (#2299) and retrieval-freshness verdicts for agent actions (#2300) sit uncommented.
- **Onyx** post-pivot is arguably an agent platform: MCP client support, web search, code execution, deep research, "memory," reminder-prompt context management. Retrieval is a tool inside a chat loop rather than the product.
- **AnythingLLM** ships `@agent` invocations, custom agent skills, and MCP support, but agent plumbing is buggy at the edges (agent chat contaminating other threads #1349; agent-skill toggle with no event handler #5301) and agent memory management is a feature request (#4288).
- **Kotaemon** added MCP tool support (Mar 2026 commit) late in life. **Verba/Cognita**: static pipelines, no agent loop — both predate and never adapted to the agentic turn, which plausibly contributed to their abandonment (Weaviate explicitly redirects users to its agentic Elysia project).
- **Morphik** ships an MCP server and markets "agentic" deep-search over documents.

Pattern: none of the seven treats **retrieval as a first-class tool contract for agents** (structured relevance/confidence signals, freshness metadata, memory integration). Agent features are bolted onto chat apps, not designed into the retrieval layer.

---

## Strengths (steelman)

1. **Time-to-working-demo is genuinely excellent.** AnythingLLM: one desktop installer to local RAG with any LLM — 64k stars is real distribution. Kotaemon on HN: "dead simple to spin up locally and use."
2. **Onyx's connector + permission-sync catalog is the deepest OSS attempt at enterprise search**; 40+ maintained connectors with document-level ACL mirroring is something no composition library offers, and the company is alive and shipping daily.
3. **R2R's design was ahead of its time**: REST-first retrieval service, users/collections/ACLs as API objects, hybrid + graph retrieval, built-in observability — the correct *shape* for a retrieval engine, validated by two 150+ point HN launches.
4. **Morphik correctly diagnosed text-extraction RAG's blindness to visual documents** and shipped a working ColPali pipeline with page-image chunks kept aligned (e.g., commit "Keep blank PDF pages as chunks to preserve page/chunk alignment", #432) — a real technical contribution.
5. **Verba's Reader/Chunker/Embedder/Retriever/Generator decomposition** remains one of the cleanest published reference architectures for a modular RAG app.
6. **Kotaemon's citation UX** (answers linked to highlighted regions in a PDF preview) set a bar most commercial tools still miss.

---

## Issues & failure modes

### production-ops

**P1. Platform mortality: archive/dormancy/pivot is the dominant failure mode of the category.** Severity: critical. Label: documented-recurring.
- Verba README: "no longer in active development… will not receive further updates, bug fixes, security patches" (repo archived; [github.com/weaviate/Verba](https://github.com/weaviate/Verba)).
- Cognita: "This repository was archived by the owner on Mar 13, 2026… no longer actively maintained" ([github.com/truefoundry/cognita](https://github.com/truefoundry/cognita)).
- R2R: last commit 2025-11-07 (GitHub API); docs site down for months — issue [#2274](https://github.com/SciPhi-AI/R2R/issues/2274), user comment (Nov 2025): "Nothing says 'this project is abandoned' like the website being down for a week and no one fixing it"; follow-up (Mar 2026): "this project, at least the open source side of it, is definitely abandoned." sciphi.ai itself failed TLS on fetch (2026-08-05).
- Kotaemon: discussion [#778](https://github.com/Cinnamon/kotaemon/discussions/778) "Is Kotaemon still being developed?" (Aug 2025) — zero maintainer replies; commit gaps of 2–3 months through 2026.
- Morphik README (July 2026 commit "split Morphik (company) and Morphik Core (OSS) identities"): "Morphik builds AI workers that run back-office operations — AP, billing, collections, and payroll — for skilled nursing and senior living operators"; morphik.ai no longer mentions RAG/ColPali at all.

**P2. Heavy multi-service deployments with un-diagnosed resource blowups (Onyx).** Severity: major. Label: documented-recurring.
- Launch HN complaint: default Docker setup is "12 containers", "4 vCPU and 10GB RAM," impractical for localhost ([HN 46045987](https://news.ycombinator.com/item?id=46045987)).
- Issue [#3427](https://github.com/onyx-dot-app/onyx/issues/3427): Vespa OOM-killed on a 64 GB host (42 GB used), backend 503s — closed "not planned"/Stale with no maintainer resolution.

**P3. Indexing throughput and progress opacity (Onyx).** Severity: major. Label: documented-recurring.
- Issue [#1546](https://github.com/onyx-dot-app/onyx/issues/1546): Slack indexing ~1 doc/sec, "80k documents by now and no end in sight," no ETA, blocks other connectors, no GPU utilization — closed "not planned"/Stale. Related: [#1378](https://github.com/onyx-dot-app/onyx/issues/1378) connectors stuck in 'Deleting' state (17 comments).

**P4. Self-hosting is second-class for open-core vendors.** Severity: major. Label: documented-recurring. Morphik README: "we cannot provide full support for self-hosted deployments"; recommended path is the hosted cloud. Onyx pushes Cloud/EE for permission sync. R2R's hosted cloud disappeared along with the docs.

### security-governance

**S1. R2R: unpatched critical vulnerabilities in a dormant repo advertised as "production-ready."** Severity: critical. Label: documented-recurring (multiple independent reports, all unanswered).
- [#2295](https://github.com/SciPhi-AI/R2R/issues/2295) (June 2026): CRITICAL — `auth_wrapper` returns a **default admin superuser for unauthenticated requests**; plus JWT type confusion (refresh tokens accepted as access tokens) and tokens not revoked on password change. No maintainer response, no labels, no fix.
- [#2290](https://github.com/SciPhi-AI/R2R/issues/2290): SQL injection in vector index management (`create_index`/`delete_index`). Open, unfixed.
- [#2292](https://github.com/SciPhi-AI/R2R/issues/2292): cross-user conversation IDOR. [#2297](https://github.com/SciPhi-AI/R2R/issues/2297): a reporter asking for *any* private disclosure channel for an unpatched authz bug — unanswered.

**S2. AnythingLLM: a long recurring CVE tail.** Severity: major. Label: documented-recurring. GitHub Advisory Database lists 16+ advisories ([github.com/advisories?query=anything-llm](https://github.com/advisories?query=anything-llm)): CVE-2026-5627 (critical path traversal), CVE-2024-3279 (improper access control), CVE-2024-8196 (unauthenticated server access, desktop), CVE-2024-6842 (unauthenticated `/setup-complete`), CVE-2025-63390 (auth bypass on `/api/workspaces`, v1.8.5), multiple path traversals (CVE-2024-10513, -10109, -13059), Prisma injection (CVE-2024-8251), DoS (CVE-2024-8249, -5216). The team does patch, but the pattern (repeated path traversal and auth-bypass classes across years) indicates security was not architectural.

**S3. ACL depth is enterprise-gated and brittle.** Severity: major. Label: documented (vendor docs). Onyx document-permission sync is **Cloud/EE only**; the GitHub connector's permission sync silently fails per-user unless the GitHub email is public: "If a user's email is set to private, they will not get access to any documents" ([docs.onyx.app/admins/connectors/official/github](https://docs.onyx.app/admins/connectors/official/github)). Identity mapping via public email is a fragile ACL foundation. None of the other six platforms offers source-ACL mirroring at all (AnythingLLM/Kotaemon have coarse workspace/user roles; R2R has collections but is unmaintained).

### retrieval-quality

**R1. Naive default retrieval in the highest-adoption platform.** Severity: major. Label: documented-recurring. AnythingLLM's default pipeline is fixed chunking → cosine top-4–6 → threshold filter, no hybrid, no rerank. Its own docs acknowledge the failure mode ("LLM not using my documents": "no guarantee that relevant text stays together," results depend on settings — [docs.anythingllm.com/llm-not-using-my-docs](https://docs.anythingllm.com/llm-not-using-my-docs)). User evidence: issue [#645](https://github.com/Mintplex-Labs/anything-llm/issues/645) "The accuracy of data retrieval is not high" (15 comments); hybrid search still an open feature request ([#4338](https://github.com/Mintplex-Labs/anything-llm/issues/4338)); knowledge-graph support open since 2024 ([#1008](https://github.com/Mintplex-Labs/anything-llm/issues/1008)); context loss with RAG ([#4033](https://github.com/Mintplex-Labs/anything-llm/issues/4033)).

**R2. "Pinning" as the sanctioned workaround = retrieval capitulation.** Severity: minor (but diagnostic). Label: documented. AnythingLLM's answer to poor retrieval is pinning whole documents into context; issue [#3587](https://github.com/Mintplex-Labs/anything-llm/issues/3587) asks to auto-pin any document a vector search touches — i.e., users trust the retriever only as a document-router, not a passage-selector.

**R3. Retrieval quality unfalsifiable out of the box.** Severity: major. Label: architectural-inference (corroborated by user reports). None of the seven ships an evaluation loop (golden-set QA, retrieval metrics, regression testing). HN on Onyx post-pivot: product "full of features ticked off a list that nobody has actually tried to use," can't "map back to documents cleanly" ([HN 46045987](https://news.ycombinator.com/item?id=46045987)). See E1.

### data-processing

**D1. Connector ingestion is the perpetual breakage surface (Onyx).** Severity: major. Label: documented-recurring. Confluence connector fails on single pages ([#2149](https://github.com/onyx-dot-app/onyx/issues/2149)); Jira project indexing AttributeError ([#1194](https://github.com/onyx-dot-app/onyx/issues/1194)); GitLab connector fails on unsupported files ([#4265](https://github.com/onyx-dot-app/onyx/issues/4265)); generic "Fail to index" ([#1204](https://github.com/onyx-dot-app/onyx/issues/1204), 16 comments). Each SaaS API drift becomes a user-visible indexing failure; long-tail connectors rot fastest.

**D2. Generic chunking acknowledged as unsolved even by the platforms' fans.** Severity: major. Label: documented-recurring. R2R V2 HN thread: "It really seems like document chunking is not a problem that can be solved well generically"; multiple commenters identified extraction/chunking, not retrieval, as the real bottleneck ([HN 40799791](https://news.ycombinator.com/item?id=40799791)). Kotaemon HN: "RAG usually requires a decent amount of customization to your input data for chunk formatting" ([HN 42571272](https://news.ycombinator.com/item?id=42571272)).

**D3. GraphRAG integrations are chronically unstable (Kotaemon).** Severity: major. Label: documented-recurring. Most-commented issues are indexing/graph failures: [#143](https://github.com/Cinnamon/kotaemon/issues/143) upload/indexing error (46 comments, still open), [#140](https://github.com/Cinnamon/kotaemon/issues/140) `create_base_entity_graph` failure (26 comments), [#628](https://github.com/Cinnamon/kotaemon/issues/628) LightRAG installation (21 comments, open).

### performance-cost

**C1. Multimodal (ColPali) retrieval has an unpriced ingestion/serving cost.** Severity: major. Label: documented. Morphik founders' own numbers: 15–20 s/page (M2), 4–5 s/page (A100); Show HN users reported "processing for over an hour" and repeated "failed to fetch" upload errors; one commenter: ask multimodal-RAG vendors about scale and "the project evaporates" ([HN 43763814](https://news.ycombinator.com/item?id=43763814)). Late-interaction multi-vector indexes also multiply storage/serving cost — none of this is surfaced to adopters up front.

### dx-docs

**X1. Install/dependency hell and upgrade breakage.** Severity: major. Label: documented-recurring.
- Kotaemon: chromadb 0.4.3 + fastapi 0.99.1 pydantic pin conflicts (Jan 2025 report); "Unable to run in Docker on ARM Mac" ([#132](https://github.com/Cinnamon/kotaemon/issues/132), 22 comments); "Not able to run the project as end user" ([#133](https://github.com/Cinnamon/kotaemon/issues/133), open, 20 comments).
- AnythingLLM: "Cannot embed into ChromaDB after updating to 1.9.0" ([#4712](https://github.com/Mintplex-Labs/anything-llm/issues/4712)) — point-release breakage of the core pipeline.
- R2R: V2→V3 full API rewrite (Dec 2024); earlier HN: "The quick start is definitely not quick… a collection of a lot of things that's not really providing any extra ease" ([HN 40799791](https://news.ycombinator.com/item?id=40799791)); Docker demanded undocumented credentials ([#1234](https://github.com/SciPhi-AI/R2R/issues/1234)).
- Onyx: "Setting new search settings is temporarily disabled" after upgrade ([#8154](https://github.com/onyx-dot-app/onyx/issues/8154)); Postgres install failures ([#7378](https://github.com/onyx-dot-app/onyx/issues/7378), 16 comments).

**X2. Stale-bot governance converts unresolved production problems into closed issues.** Severity: minor (process), major (signal distortion). Label: documented-recurring. Onyx's highest-signal ops complaints (#1546 indexing throughput, #3427 Vespa OOM) were closed "not planned"/Stale without resolution — issue metrics look healthy while the underlying problems persist.

### evaluation-observability

**E1. No platform ships an evaluation loop; observability is logs at best.** Severity: major. Label: architectural-inference (design review of all seven, corroborated by R3 evidence). R2R had the best story (request logging/analytics) and is dead. AnythingLLM's official debugging advice for bad answers is to manually tweak chunk/threshold/embedder settings — trial and error with no measurement harness. Onyx exposes indexing status but users report they "can't keep track of what's been processed" (HN). None ships golden-set retrieval eval, drift detection, or per-stage quality attribution.

### agentic-integration

**A1. Agent features are chat-app bolt-ons, not retrieval-layer contracts.** Severity: major. Label: architectural-inference (with documented fragments). AnythingLLM agent state leaks across threads ([#1349](https://github.com/Mintplex-Labs/anything-llm/issues/1349)); agent memory management is an open request ([#4288](https://github.com/Mintplex-Labs/anything-llm/issues/4288)); R2R's agent-memory and freshness-signal requests ([#2299](https://github.com/SciPhi-AI/R2R/issues/2299), [#2300](https://github.com/SciPhi-AI/R2R/issues/2300)) landed in a dead repo. No platform returns calibrated relevance/coverage/freshness metadata that an agent loop could branch on.

### abstraction-design

**B1. "All-in-one" scope guarantees breadth-over-depth mediocrity.** Severity: major. Label: architectural-inference (echoed by users). Each platform owns UI + ingestion + vector store + LLM routing + agents + auth simultaneously; the result is HN's verdict on Onyx — features "ticked off a list that nobody has actually tried to use" — and AnythingLLM's years-open requests for table-stakes retrieval (hybrid search). Kotaemon HN: "not this again, we've already seen hundreds of such things." The category competes on checkbox count, not retrieval quality.

### other (business-model gravity)

**O1. Open-core economics pull vendors away from retrieval.** Severity: critical (for adopters). Label: documented-recurring. Onyx: Danswer (enterprise search) → Onyx (chat UI; founders on HN: users mostly wanted multi-model chat). Morphik: multimodal RAG engine → skilled-nursing back-office automation. Verba: Weaviate demo → archived when marketing value expired. Cognita: TrueFoundry side project → archived. R2R: startup ran out of road → silent abandonment with the "production-ready" README still up. The "demo-great, production-brittle" pattern from the seed brief is **confirmed** — and it compounds into "production-brittle, then unmaintained."

---

## Community sentiment over time

- **2023–mid-2024 (exuberance):** big Show HN receptions — R2R Feb/Jun 2024 (167/251 points), Cognita Apr 2024 (142), AnythingLLM Sep 2024 (368), each with "finally, RAG that works out of the box" energy, but already threaded with skepticism about generic chunking and quickstart friction ([HN 39510874](https://news.ycombinator.com/item?id=39510874), [40799791](https://news.ycombinator.com/item?id=40799791), [40181306](https://news.ycombinator.com/item?id=40181306), [41457633](https://news.ycombinator.com/item?id=41457633)).
- **Late 2024–2025 (saturation fatigue):** Kotaemon's Jan 2025 thread (191 points) is dominated by "document search is table stakes," "hundreds of such things," and doubts any standalone RAG tool can survive platform players ([HN 42571272](https://news.ycombinator.com/item?id=42571272)). Morphik's Apr 2025 thread (200 points) mixes genuine interest in ColPali with live-fire failures (hour-long processing, upload errors) and licensing confusion ([HN 43763814](https://news.ycombinator.com/item?id=43763814)).
- **2025–2026 (consolidation and exit):** Verba archived; Cognita archived (Mar 2026); R2R goes dark (Nov 2025) with users narrating the abandonment inside issue #2274; Kotaemon users ask if it's alive (discussion #778, unanswered); Onyx relaunches as a chat UI and HN's reception is "a million other projects just like this one… no moat" ([HN 46045987](https://news.ycombinator.com/item?id=46045987)). Surviving energy concentrates in AnythingLLM (local/desktop personal use) and Onyx (funded, pivoted).

## Benchmarks & third-party evaluations

The most damning finding is scarcity: **none of the seven platforms appears in a rigorous third-party retrieval-quality benchmark.** arXiv full-text search (export.arxiv.org API, 2026-08-05) finds essentially no measured evaluations — AnythingLLM appears only as an *apparatus* in application papers (e.g., "KidneyTalk-open: No-code Deployment of a Private LLM… " uses it as deployment vehicle; "LLM Chatbot-Creation Approaches" surveys it), not as an evaluated retrieval system; Kotaemon, Danswer/Onyx, R2R, Verba, Cognita, Morphik: no independent quantitative evaluations surfaced. Vendor-side numbers exist (Morphik's "GPT vs Morphik multimodal" blog; R2R's SoTA claims) but are self-reported and unreproduced. The platforms compete on features and stars; nobody — including the vendors — publishes retrieval-precision numbers on standard corpora. A next-gen framework paper can honestly state that the OSS RAG-platform category operates without an evaluation culture.

## Lessons for a next-generation framework

1. **Design for maintainer mortality.** The base rate of abandonment/pivot in this category over ~2.5 years is ≥5/7. A next-gen framework should be a small, spec-driven core with data (indexes, configs, eval sets) in portable open formats, so death of the vendor doesn't strand deployments the way R2R stranded users with unpatched auth bypasses.
2. **Security must be architectural, not incidental.** A retrieval server is an auth server (it gatekeeps documents). R2R's default-admin-on-unauthenticated and AnythingLLM's recurring path-traversal/auth-bypass classes show bolt-on auth fails repeatedly. ACL mirroring must be core and open, not EE-gated, and not keyed to fragile identity joins (Onyx's public-GitHub-email requirement).
3. **Ship the eval loop before the feature list.** Every platform lets you change chunkers/embedders/thresholds; none lets you *measure* the change. Golden-set retrieval eval, per-stage attribution, and regression gates should be the default UX for "why is my answer wrong," replacing AnythingLLM-style knob-twiddling folklore.
4. **Treat connectors as the product's hardest engineering, with SLOs.** Onyx's issue tracker shows connectors are where enterprise RAG lives and dies: throughput visibility (ETA, per-connector progress), parallelism, incremental sync, and graceful API-drift handling — not stale-bot closure of OOM and throughput reports.
5. **Expose retrieval as an agent-grade contract.** Return calibrated relevance/coverage/freshness signals an agent loop can branch on; make memory a first-class store, not a chat-app bolt-on. Users are already asking for this in dead repos (R2R #2299/#2300).
6. **Be honest about cost curves.** ColPali-class multimodal quality at 15–20 s/page and multi-vector index blowup, or Vespa needing >42 GB RAM, must be priced into the design (tiered indexing, lazy/visual-on-demand embedding), not discovered in production.
7. **Right-size the deployment.** 12 containers to try a chat app kills adoption; single-binary/embedded mode with a scale-out path (the AnythingLLM desktop insight, minus its retrieval naivety) is the winning on-ramp.
8. **Avoid all-in-one scope creep.** The checkbox arms race (UI+agents+connectors+auth+everything) produced breadth-over-depth mediocrity and no moat. A focused retrieval engine with excellent contracts outlives a feature-list app.

## Sources

- GitHub API repo metadata (stars/license/pushed/archived), retrieved 2026-08-05, for: SciPhi-AI/R2R; onyx-dot-app/onyx; Mintplex-Labs/anything-llm; weaviate/Verba; Cinnamon/kotaemon; truefoundry/cognita; morphik-org/morphik-core.
- R2R: https://github.com/SciPhi-AI/R2R — issues #2295 (auth bypass), #2290 (SQLi), #2292 (IDOR), #2297 (no disclosure channel), #2274 (docs down / "definitely abandoned" comments), #2299/#2300 (agent memory/freshness), #1234; Show HN threads https://news.ycombinator.com/item?id=39510874 and https://news.ycombinator.com/item?id=40799791.
- Onyx: https://github.com/onyx-dot-app/onyx — issues #1546, #3427, #2149, #1378, #1194, #4265, #1204, #8154, #7378, #971; Launch HN https://news.ycombinator.com/item?id=46045987; GitHub connector permission-sync docs https://docs.onyx.app/admins/connectors/official/github.
- AnythingLLM: https://github.com/Mintplex-Labs/anything-llm — issues #645, #3587, #4338, #1008, #4033, #1349, #4288, #4712, #5301; docs https://docs.anythingllm.com/llm-not-using-my-docs; GitHub Advisory Database https://github.com/advisories?query=anything-llm (CVE-2026-5627, CVE-2024-3279, CVE-2024-8196, CVE-2024-6842, CVE-2025-63390, CVE-2024-10513, CVE-2024-8251, et al.); Show HN https://news.ycombinator.com/item?id=41457633.
- Verba: https://github.com/weaviate/Verba (archived notice, component architecture); https://weaviate.io/blog/verba-open-source-rag-app.
- Kotaemon: https://github.com/Cinnamon/kotaemon — issues #143, #140, #132, #133, #628, #154; discussion #778; HN https://news.ycombinator.com/item?id=42571272.
- Cognita: https://github.com/truefoundry/cognita (archived 2026-03-13; architecture from README); Show HN https://news.ycombinator.com/item?id=40181306.
- Morphik: https://github.com/morphik-org/morphik-core (README incl. company/OSS identity split and BUSL-1.1 licensing; commits #430–#432); https://www.morphik.ai (pivot to skilled-nursing back-office AI workers, fetched 2026-08-05); Show HN https://news.ycombinator.com/item?id=43763814.
- arXiv full-text search via export.arxiv.org API (2026-08-05) for third-party evaluations of each platform (negative result; AnythingLLM apparatus mentions in KidneyTalk-open and chatbot-survey papers).
- sciphi.ai fetch attempt 2026-08-05: TLS handshake failure (corroborating R2R hosting/company decay).
