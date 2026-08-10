# JVM & JS/Edge RAG Ecosystems: Spring AI, LangChain4j, LlamaIndex.TS, Vercel AI SDK, Cloudflare AutoRAG

> Framework-autopsy report, August 5, 2026. Evidence gathered from official docs, GitHub repos/issues (via `gh` API), npm registry stats, Hacker News (Algolia API), and vendor blogs. Note: session web-search budget was exhausted upstream, so evidence collection leaned on direct fetches of primary sources (docs, GitHub issues, registries) — arguably higher-quality evidence than search-engine results, but independent long-form blog critiques are under-sampled; where a claim rests on a single comment or inference it is labeled as such.

---

## Identity & adoption

| Framework | Maintainer | License | Stars (Aug 2026) | Status / momentum |
|---|---|---|---|---|
| Spring AI | Broadcom/VMware Tanzu (Spring team) | Apache-2.0 | 9,252 (1,389 open issues) | 1.0 GA May 20, 2025; **2.0.0 June 12, 2026**; very active (pushed Aug 5, 2026) |
| LangChain4j | Independent OSS (Dmytro Liubarskyi et al.; not the LangChain company) | Apache-2.0 | 12,794 (870 open issues) | 0.x from 2023, 1.0.0 May 14, 2025, now 1.18.x; ~monthly releases |
| LlamaIndex.TS | run-llama (LlamaIndex Inc.) | MIT | 3,079 | **DEPRECATED March 2026** — "This project is deprecated and no longer maintained" (README); last release 0.12.2 Mar 2026 |
| Vercel AI SDK (`ai`) | Vercel | Apache-2.0 (GitHub shows NOASSERTION; LICENSE file is Apache-2.0) | 26,032 (1,768 open issues) | v5 Jul 2025 → v6 Dec 2025 → v7 Jun 2026; **79.1M npm downloads/month** (Jul–Aug 2026) vs `llamaindex` 527K/month |
| Cloudflare AutoRAG | Cloudflare (closed platform) | n/a (proprietary managed service) | n/a | Launched open beta Apr 7, 2025; renamed **"AI Search"** in late 2025 (docs at `/autorag/` now render "AI Search"); "available on all plans", but pricing page still describes an "open beta phase" with free usage |

Adoption signal summary: the Vercel AI SDK is by far the most-adopted LLM library in any language by raw distribution (79M monthly downloads, though inflated by Next.js template inclusion). Spring AI and LangChain4j are the two serious JVM contenders and both hit 1.0 within a week of each other (May 2025). LlamaIndex.TS — the only attempt to port a full Python "data framework" to TypeScript — is dead, which is itself the most important datapoint in this ecosystem.

---

## Retrieval-pipeline architecture

### Spring AI (1.0 → 2.0)
- **Advisors API**: an interceptor chain around `ChatClient` (Spring's AOP idiom applied to prompts). RAG is an advisor: `QuestionAnswerAdvisor` (simple: similarity search → stuff context) and `RetrievalAugmentationAdvisor` (modular, explicitly modeled on the *Modular RAG* paper: LEGO-like pre-retrieval/retrieval/post-retrieval components) ([docs](https://docs.spring.io/spring-ai/reference/api/retrieval-augmented-generation.html)).
- Modular components: `CompressionQueryTransformer`, `RewriteQueryTransformer`, `TranslationQueryTransformer`, `MultiQueryExpander` (pre-retrieval); `VectorStoreDocumentRetriever` + `ConcatenationDocumentJoiner` (retrieval); `DocumentPostProcessor` (rerank interface, few shipped impls) and `ContextualQueryAugmenter` (post-retrieval).
- **VectorStore abstraction**: 20+ backends behind one interface with a portable SQL-like metadata **Filter Expression DSL** (`FilterExpressionBuilder`), converted per-backend by `FilterExpressionConverter` implementations.
- **ETL pipeline**: `DocumentReader → DocumentTransformer (TokenTextSplitter, KeywordMetadataEnricher…) → DocumentWriter`, readers for filesystem/web/S3/GCS/Kafka/JDBC etc. Deliberately lightweight vs Python's ingestion ecosystems.
- **Observability**: first-class Micrometer metrics + tracing across models, vector stores, tool calls, advisors — the strongest built-in observability story of any framework in this report ([1.0 GA announcement](https://spring.io/blog/2025/05/20/spring-ai-1-0-GA-released)).
- The Spring idiom: everything is a bean, auto-configured via Boot starters, strictly typed builders, DI-injectable `Supplier<Filter.Expression>` for per-tenant filters.

### LangChain4j
- Despite the name, an independent clean-room Java design, far more disciplined than Python LangChain. Core RAG types: `EmbeddingStore` (30+ vendor impls), `ContentRetriever` (embedding store, web search, SQL — the SQL retriever is in `langchain4j-experimental-sql`), and `RetrievalAugmentor` as pipeline orchestrator.
- `DefaultRetrievalAugmentor` pipeline: `QueryTransformer → QueryRouter → ContentRetriever(s) → ContentAggregator (RRF, re-ranking) → ContentInjector` ([docs](https://docs.langchain4j.dev/tutorials/rag)).
- **AI Services**: annotation-driven declarative interfaces (`@SystemMessage`, proxy-generated implementations) with a `contentRetriever`/`retrievalAugmentor` parameter — RAG wired into a typed service interface; sources retrievable via `Result<T>`.
- "Easy RAG" module for zero-config ingestion (Tika-based loader + in-memory store).
- Full-text/hybrid search only on Azure AI Search and Elasticsearch (docs admit this).

### LlamaIndex.TS
- Port of the Python architecture: `Reader → NodeParser/SentenceSplitter → VectorStoreIndex → Retriever → QueryEngine / ChatEngine`, plus workflows. Always trailed Python badly on stores, readers, evaluation, and advanced retrievers (open issues: "Document Missing Vector Stores" [#1152], missing evaluation [#161]). Deprecated before ever closing the gap; run-llama now points TS users at LlamaCloud (managed) — an open-core endgame.

### Vercel AI SDK
- **Deliberately has no retrieval pipeline.** Primitives only: `embed` / `embedMany` (+ `cosineSimilarity`), and since v7 a reranking model spec (`rerank`, `31-reranking.mdx` in docs). No document loaders, no chunker, no vector-store interface, no retriever abstraction.
- The official [RAG Agent guide](https://github.com/vercel/ai/blob/main/content/cookbook/00-guides/01-rag-chatbot.mdx) has you hand-roll chunking (literally splitting on periods in the tutorial), store vectors with Drizzle ORM + pgvector, and expose retrieval **as a tool** (`addResource`/`getInformation`) that the model calls inside `streamText`'s agent loop — retrieval as tool-use, not as a pipeline stage. BYO retrieval is the doctrine; templates fill the gap.
- Strengths are elsewhere: streaming UI (`useChat`, UI message streams), provider abstraction (LanguageModelV2/EmbeddingModelV2 specs), middleware, OpenTelemetry via `@ai-sdk/otel`, edge-runtime compatibility.

### Cloudflare AutoRAG / AI Search
- Fully managed edge RAG. **Indexing**: data source (R2 bucket, website crawl, or Items API) → Workers AI Markdown Conversion (any file type → markdown, image object detection) → **fixed recursive chunking** (only token size + 0–30% overlap configurable; strategy itself not swappable) → Workers AI embeddings → optional BM25 inverted index → Vectorize + R2. Continuous re-indexing is automatic ([how it works](https://developers.cloudflare.com/ai-search/concepts/how-ai-search-works/)).
- **Query**: optional LLM query rewriting → embed → vector search (+ optional BM25 + fusion) → optional cross-encoder reranking → `search` (chunks only) or `ai-search` (generation). Query-able via Workers binding, REST, or a built-in **MCP server endpoint**.
- Hard limits ([limits & pricing](https://developers.cloudflare.com/autorag/platform/limits-pricing/)): **4 MB max file size**, 100K files/instance free (1M paid, 500K with hybrid search), **5 custom metadata fields**, 500-char text metadata values, 100 namespaces/account, 20K queries/month free. AutoRAG itself free in beta; you pay for Workers AI + AI Gateway underneath.

---

## Agentic integration

- **Spring AI**: became the JVM home of **MCP** — client + server (WebMVC/WebFlux transports, `@McpTool` annotations). Judging by issue traffic, MCP is now *the* dominant use of the project (top-commented issues are overwhelmingly MCP: #3178, #2675, #3145, #2506, #2740…), which pulls maintainer attention away from the RAG/ETL core. Tool-calling moved into the advisor chain in 2.0 (#4997 requested exactly this). Retrieval-as-tool is possible but the advisor idiom biases toward static pipeline RAG per request.
- **LangChain4j**: AI Services + `@Tool` annotations give typed agent loops; MCP client support shipped 2025. RAG and tools compose in one declarative service, but dynamic per-query control of retrieval from within an agent loop is awkward (see #1122: passing extra parameters to RAG providers via AI Services took a feature request).
- **Vercel AI SDK**: the most agent-native — retrieval is just a tool inside the model loop (`stopWhen`/`maxSteps`), MCP tool support (`16-mcp-tools.mdx`), agent abstraction and harness packages in v6/v7. Best-in-class for "agentic RAG where the model decides when to search"; worst-in-class if you want a managed retrieval pipeline.
- **AutoRAG/AI Search**: ships an MCP server per instance out of the box — a managed retrieval tool any agent can mount. Genuinely forward-looking, but the retrieval behind that MCP endpoint is the same non-tunable black box.
- **LlamaIndex.TS**: had agents + workflows; now unmaintained — do not build on it.

---

## Strengths (steelman)

1. **Spring AI's Modular-RAG-as-code is the cleanest pipeline formalization in any framework.** Pre/retrieval/post stages are real typed interfaces (not callbacks), explicitly citing the Modular RAG paper; per-tenant filtering via injected `Supplier<Filter.Expression>` is a production pattern Python frameworks lack.
2. **First-class observability as a framework feature, not an add-on** (Spring AI): Micrometer metrics/tracing across model calls, vector stores, and advisors from day one — evidence that the JVM's ops culture transfers to RAG.
3. **LangChain4j's AI Services show what strict typing buys**: a RAG-augmented LLM call is a compile-time-checked Java interface returning `Result<T>` with sources — declarative, testable, DI-friendly; retrieval config is code, not stringly-typed chains.
4. **Vercel AI SDK's refusal to own retrieval is a coherent architectural bet**: retrieval is a tool the model calls, storage is your database (pgvector via your ORM), and the SDK owns only what's genuinely hard on the edge — provider abstraction, streaming UI state, and the agent loop. 79M downloads/month says the market accepts it.
5. **AutoRAG proves continuous, zero-ops indexing is possible**: file→markdown conversion of arbitrary formats, automatic re-indexing on change, hybrid search + reranking + MCP endpoint with literally zero pipeline code — a bar for "time to first RAG query" no framework matches.
6. **Both JVM frameworks reached disciplined 1.0s with semver intent** (May 2025), unlike Python LangChain's long-running churn — enterprise Java expectations forced maturity earlier.

---

## Issues & failure modes

### abstraction-design

**A1. Spring AI's portable filter DSL breaks differently on each backend — the leaky-abstraction tax of "20+ vector stores behind one interface."** Severity: **critical** (silently wrong retrieval). Label: **documented-recurring**.
Evidence: [#3577](https://github.com/spring-projects/spring-ai/issues/3577) PgVector emits filter without parentheses so `(a OR b) AND c` becomes `a || b && c` — "the final expression that is generated does not use parentheses, and so the expression is broken" (34 comments); [#1179](https://github.com/spring-projects/spring-ai/issues/1179) incorrect SQL for IN/NOT IN in PgVector; [#3876](https://github.com/spring-projects/spring-ai/issues/3876) (open) DSL has no boolean type; [#3222](https://github.com/spring-projects/spring-ai/issues/3222) (open) Elasticsearch filter-expression errors; [#6422](https://github.com/spring-projects/spring-ai/issues/6422) S3Vectors delete-by-filter builds an invalid request → 400; [#3179](https://github.com/spring-projects/spring-ai/issues/3179) `VectorStoreDocumentRetriever` ignored the typed `Filter.Expression` object. One portable DSL × 20 converters = 20 places for the same class of correctness bug, and filter bugs corrupt retrieval *silently*.

**A2. Spring AI's core RAG types resist extension — framework-knows-best sealed design.** Severity: major. Label: **documented-recurring**.
Evidence: [#4552](https://github.com/spring-projects/spring-ai/issues/4552) "SearchRequest cannot be inherited" (73 comments — private fields force full reimplementation for custom search params); [#3644](https://github.com/spring-projects/spring-ai/issues/3644) TokenTextSplitter config fields had no getters (91 comments); [#2655](https://github.com/spring-projects/spring-ai/issues/2655) maintainer-acknowledged epic to "make ChatClient and Advisor APIs more robust, consistent, and flexible"; [#2525](https://github.com/spring-projects/spring-ai/issues/2525) (open) advisors can't search two vector stores; [#4952](https://github.com/spring-projects/spring-ai/issues/4952) (open) advisor chain NPEs when context contains nulls. Java's encapsulation idiom, applied to a fast-moving domain, produces abstractions users must fork rather than extend.

**A3. LangChain4j couples RAG into chat memory and generation in ways users keep fighting.** Severity: major. Label: **documented-recurring**.
Evidence: [#3498](https://github.com/langchain4j/langchain4j/issues/3498) retrieved RAG content was stored into chat memory (context bloat + cost, took a feature request to avoid); [#1851](https://github.com/langchain4j/langchain4j/issues/1851) (open since 2024) "Skip generation if nothing was retrieved" — the pipeline can't short-circuit; [#2929](https://github.com/langchain4j/langchain4j/issues/2929) (open) can't stop a response mid-RAG in AiServices; [#1122](https://github.com/langchain4j/langchain4j/issues/1122) passing per-call parameters into RAG components through AI Services required new API. The declarative AI-Service proxy is elegant until you need per-request control of the pipeline inside it.

**A4. Vercel AI SDK's "no retrieval layer" pushes every team to reinvent chunking/retrieval — and its own primitives have batching bugs.** Severity: major (for RAG usage). Label: **documented-recurring** (bugs) + **architectural-inference** (the gap).
Evidence: official RAG guide implements chunking as splitting on periods ([01-rag-chatbot.mdx](https://github.com/vercel/ai/blob/main/content/cookbook/00-guides/01-rag-chatbot.mdx)); [#10082](https://github.com/vercel/ai/issues/10082) (open) `embedMany` does not split oversized batches → provider errors; [#16101](https://github.com/vercel/ai/issues/16101) `embedMany` over-batches Google embedding models; [#6268](https://github.com/vercel/ai/issues/6268) wrong chunk size for `text-embedding-004`; [#14425](https://github.com/vercel/ai/issues/14425)/[#14926](https://github.com/vercel/ai/issues/14926) `embed`/`embedMany` crash on providers omitting `warnings`; reranking only arrived as a spec in v7 ([#17811](https://github.com/vercel/ai/issues/17811) still requesting `rerankMany` batching). The SDK owns *just enough* of retrieval (embedding calls) to also own its failure modes, while owning none of the quality-critical parts.

### retrieval-quality

**R1. LangChain4j metadata filtering: capability rolled out store-by-store over years, with silent-corruption bugs en route.** Severity: **critical** (one bug matched ALL content). Label: **documented-recurring**.
Evidence: [#2513](https://github.com/langchain4j/langchain4j/issues/2513) `.isNotIn` on PgVector generated `metadata->>'id' IS NULL OR ... NOT IN (...)` — "if you add this .isNotIn query at the end of any filter chain, chained with AND, it will lead to all content being matched" (i.e., tenant-isolation filters silently disabled); [#5906](https://github.com/langchain4j/langchain4j/issues/5906) (open) Coherence filters read the wrong metadata key; the filtering feature itself arrived piecemeal — [#151](https://github.com/langchain4j/langchain4j/issues/151) (core), [#1263](https://github.com/langchain4j/langchain4j/issues/1263) (Azure), [#1600](https://github.com/langchain4j/langchain4j/issues/1600) (Qdrant), [#1252](https://github.com/langchain4j/langchain4j/issues/1252) (Neo4j, still open), [#1615](https://github.com/langchain4j/langchain4j/issues/1615) (open, metadata-only queries impossible on PgVector). Same lesson as Spring AI A1, independently rediscovered: a uniform store interface without a conformance test suite is a correctness minefield.

**R2. AutoRAG's retrieval quality ceiling is fixed by Cloudflare.** Severity: major. Label: **architectural-inference** (from documented constraints).
Evidence: chunking strategy is fixed recursive splitting — "users cannot choose different chunking strategies" ([chunking docs](https://developers.cloudflare.com/autorag/configuration/chunking/)); embedding/generation restricted to Workers AI catalog; max 5 custom metadata fields with 500-char values ([limits](https://developers.cloudflare.com/autorag/platform/limits-pricing/)) makes rich metadata filtering (the main precision lever in the other frameworks) impossible. No re-chunking without full re-index. When quality is insufficient there is no escape hatch short of leaving the product.

### data-processing

**D1. Spring AI's `TokenTextSplitter` — the default and near-only chunker — is demonstrably unfit.** Severity: major. Label: **documented-recurring**.
Evidence: [#2123](https://github.com/spring-projects/spring-ai/issues/2123) (open since 2024) **no chunk-overlap support at all**; [#6447](https://github.com/spring-projects/spring-ai/issues/6447) infinite loop when `chunkSize` is 0; [#1167](https://github.com/spring-projects/spring-ai/issues/1167) (open) splitter reassigns document IDs breaking provenance/upserts; [#1834](https://github.com/spring-projects/spring-ai/issues/1834) chunks violate the configured token count; [#4981](https://github.com/spring-projects/spring-ai/issues/4981) small text without terminal punctuation split into multiple chunks; [#3166](https://github.com/spring-projects/spring-ai/issues/3166) builder fails with partial params; [#2381](https://github.com/spring-projects/spring-ai/issues/2381) (open) not parallelized. A framework whose ETL story is "one token splitter" — and that splitter can't do overlap in 2026 — signals ingestion is a second-class citizen vs the Python ecosystem.

**D2. LlamaIndex.TS data ingestion never worked reliably, then was abandoned.** Severity: major. Label: **documented-recurring**.
Evidence (all open at deprecation): [#836](https://github.com/run-llama/LlamaIndexTS/issues/836) PapaCSVReader fails on some CSVs; [#2021](https://github.com/run-llama/LlamaIndexTS/issues/2021) Hebrew PDFs extracted with reversed text; [#1098](https://github.com/run-llama/LlamaIndexTS/issues/1098) SentenceSplitter ignores `excludedEmbedMetadataKeys`; [#1095](https://github.com/run-llama/LlamaIndexTS/issues/1095) no JSON reader guidance; [#1363](https://github.com/run-llama/LlamaIndexTS/issues/1363) LlamaParse fails on docx.

### evaluation-observability

**E1. LangChain4j has no built-in tracing/eval story; the most-demanded observability integration has been open for 20 months.** Severity: major. Label: **documented-recurring**.
Evidence: [#2328](https://github.com/langchain4j/langchain4j/issues/2328) "Langfuse: implement tracing" — opened Dec 23, 2024, 47 comments, **still open Aug 2026**; the framework ships no evaluation module at all (contrast Spring AI's `RelevancyEvaluator`/`FactCheckingEvaluator`, themselves basic LLM-as-judge stubs). Retrieval quality is unmeasurable in-framework.

**E2. No framework in this group ships retrieval-quality evaluation; observability ends at spans/tokens.** Severity: major. Label: **architectural-inference**.
Evidence: Spring AI's Micrometer integration measures latency/tokens/tool calls (GA blog) but has no recall/precision/groundedness instrumentation; AI SDK telemetry is OpenTelemetry spans of model calls (`60-telemetry.mdx`); AutoRAG's observability is AI Gateway logs of model usage. Nobody answers "did retrieval return the right chunks?" — the question RAG failures actually hinge on.

### production-ops

**P1. Breaking-change velocity outruns enterprise upgrade cycles — in *both* ecosystems.** Severity: major. Label: **documented-recurring**.
Evidence: Spring AI shipped **2.0.0 thirteen months after 1.0 GA** (Jun 12, 2026) with module renames (`spring-ai-advisors-vector-store` → `spring-ai-vector-store-advisor`), vector stores deleted (HANA) or expelled to vendors (Cosmos DB, OCI), config-property flattening, chat-memory schema migration requiring SQL `ALTER TABLE`, and advisor-order changes ([upgrade notes](https://docs.spring.io/spring-ai/reference/upgrade-notes.html)). Vercel AI SDK shipped **three majors in 11 months** (v5 Jul 31 2025, v6 Dec 22 2025, v7 Jun 25 2026) with documented migration-guide gaps ([#8017](https://github.com/vercel/ai/issues/8017) `processDataStream` missing despite migration guide, [#7072](https://github.com/vercel/ai/issues/7072) guide missing usage-token migration) and dual-track maintenance (6.0.242 and 7.0.52 patched the same day). LangChain4j spent 2.5 years at 0.x with per-release breakage before 1.0 ([#2133](https://github.com/langchain4j/langchain4j/issues/2133) "0.36 Spring Boot starter breaks configuration classes").

**P2. LlamaIndex.TS: total abandonment of the only full-stack TS RAG framework, with an open-core redirect.** Severity: **critical** for its users. Label: **documented-recurring**.
Evidence: README deprecation notice committed Mar 11, 2026 — "This project is deprecated and no longer maintained… For LlamaCloud/LlamaParse usage, check out our docs" ([repo](https://github.com/run-llama/LlamaIndexTS)); 109+ open issues stranded; still ~527K npm downloads/month of an unmaintained package. Lesson: a VC-backed vendor's second-language port is maintained only while it feeds the managed platform.

**P3. AutoRAG operational opacity: shared-infra outages, beta pricing ambiguity, and a product rename mid-flight.** Severity: minor-to-major. Label: **single-anecdote** (outage/quality reports) + documented (rename/pricing).
Evidence: docs simultaneously say "available on all plans" and describe an "open beta phase" free tier ([limits/pricing](https://developers.cloudflare.com/autorag/platform/limits-pricing/)) — cost at scale is unknowable; AutoRAG listed among services affected in Cloudflare's June 12, 2025 outage (HN [44261970](https://news.ycombinator.com/item?id=44261970)); "AutoRAG has huge issues too, not to mention the whole MCP/Agents suite of SDKs" (HN [45587797](https://news.ycombinator.com/item?id=45587797), Oct 2025 — single anecdote); the AutoRAG→AI Search rebrand churned URLs/docs within 6 months of launch.

### agentic-integration

**G1. Spring AI's issue tracker shows MCP/agent plumbing crowding out the RAG core.** Severity: minor. Label: **architectural-inference** (from issue distribution).
Evidence: 9 of the 15 most-commented issues are MCP transport/auth/reconnection problems ([#3178](https://github.com/spring-projects/spring-ai/issues/3178), [#2506](https://github.com/spring-projects/spring-ai/issues/2506) "MCP server: Authentication lost in tool execution", [#2740](https://github.com/spring-projects/spring-ai/issues/2740) open: clients don't reconnect after server restart), while core retrieval issues like #2123 (chunk overlap) sit open for 18+ months. The advisor-chain design also predates agent loops: tool execution had to be restructured into the advisor layer in 2.0 ([#4997](https://github.com/spring-projects/spring-ai/issues/4997)).

### dx-docs

**X1. JVM packaging idioms violated: LangChain4j split packages break the Java module system.** Severity: minor. Label: **documented-recurring** (42 comments; fixed only at 1.0 restructure).
Evidence: [#1066](https://github.com/langchain4j/langchain4j/issues/1066) "the unnamed module reads package dev.langchain4j.retriever from both langchain4j and langchain4j.core" — unusable on the module path; "Easy RAG" starter shipped with broken transitive deps ([#1330](https://github.com/langchain4j/langchain4j/issues/1330) FileSystemDocumentLoader retrieves nothing, [#2117](https://github.com/langchain4j/langchain4j/issues/2117) `NoClassDefFoundError` on commons-io).

**X2. Vercel AI SDK's hard Zod coupling.** Severity: minor. Label: **documented-recurring**.
Evidence: [#1062](https://github.com/vercel/ai/issues/1062) "Support for validation libraries other than zod (or no validation)" (13 comments); Zod v4 support lagged ([#5682](https://github.com/vercel/ai/issues/5682)) — schema-library churn becomes framework churn, a bundle-size and lock-in concern on edge runtimes.

### performance-cost

**C1. AutoRAG hard limits make it a demo-to-mid-scale product: 4 MB per file, 20K queries/month free, hybrid search halves file capacity.** Severity: major (for the "fully-managed enterprise RAG" positioning). Label: **documented-recurring** (limits page).
Evidence: [limits & pricing](https://developers.cloudflare.com/autorag/platform/limits-pricing/) — 4 MB max file size (most enterprise PDFs exceed this), 100K files free / 1M paid but only 500K with hybrid search enabled, 5 metadata fields. No SLA or GA pricing published 16 months after launch.

---

## Community sentiment over time

- **Spring AI**: 2024 milestone era — enthusiasm from Java shops ("finally a Spring-idiomatic way"); May 2025 GA well received (HN tool-calling tutorial hit 101 points, [44548906](https://news.ycombinator.com/item?id=44548906)). 2025–26: issue tracker sentiment shifts toward MCP pain and extension friction (#4552's 73 comments are largely "+1 please unlock this class"). The 2.0 release (June 2026) re-triggered upgrade grumbling but was more disciplined than Python LangChain's equivalent transitions.
- **LangChain4j**: consistently warmer sentiment than its Python namesake — perceived as pragmatic and community-driven; the recurring complaints are integration-lag ("store X doesn't support filtering yet") and observability. The 1.0 (May 2025) was seen as overdue but real stabilization; 1.x cadence since has been fast but non-breaking.
- **LlamaIndex.TS**: 2024 excitement ("LlamaIndex.ts support" requested inside vercel/ai, [#923](https://github.com/vercel/ai/issues/923)); 2025 visible slowdown (issues idle for months); March 2026 deprecation confirmed community suspicions. Sentiment now: cautionary tale cited in "don't bet on vendor OSS ports" arguments.
- **Vercel AI SDK**: adoration for `useChat`/streaming DX + persistent resentment of major-version churn; each major (v4→v5→v6→v7) produces a wave of migration issues. RAG-specific sentiment is basically absent — users don't consider it a RAG framework, which matches its design.
- **AutoRAG**: launch buzz was mild (HN launch posts: 8 and 2 points, zero comments — [43611057](https://news.ycombinator.com/item?id=43611057)); an April 2025 first-impressions review called it "pretty decent" with suggestions ([bauva.com](https://bauva.com/blog/cloudflare-autorag-first-impressions/), site unreachable at review time, HN [43804727](https://news.ycombinator.com/item?id=43804727)); by Oct 2025 skeptics on HN grouped it with Cloudflare's "huge issues" AI suite ([45587797](https://news.ycombinator.com/item?id=45587797)). Overall: low mindshare relative to Cloudflare's platform reach.

---

## Benchmarks & third-party evaluations

Honest finding: **there is essentially no credible third-party retrieval-quality benchmarking of any of these five** — a striking contrast with the Python ecosystem (RAGAS-style evals, BEIR runs against LangChain/LlamaIndex pipelines). What exists:
- Vendor self-benchmarks: Cloudflare publishes no AutoRAG quality numbers at all; Spring AI/LangChain4j publish none (their eval modules are for *users'* apps).
- Micro-benchmarks of components (e.g., embedding throughput via `embedMany`) circulate in blogs, but none met the credibility bar for citation here.
- The absence is itself evidence for issue **E2**: none of these frameworks makes retrieval quality measurable enough for third parties to benchmark cheaply. JVM/JS RAG quality claims in the wild are anecdotal.

---

## Lessons for a next-generation framework

1. **A portable vector-store abstraction is worthless without a conformance test suite.** Spring AI (#3577, #1179, #3876) and LangChain4j (#2513, #5906) independently shipped the same class of silent filter-translation corruption across backends. A next-gen framework must ship a mandatory cross-backend contract test (filter semantics, boolean types, null handling, delete-by-filter) that every store integration must pass — and should treat filter bugs as security bugs (they break tenant isolation).
2. **Chunking is not a utility function.** Spring AI's overlap-less `TokenTextSplitter` and the AI SDK's split-on-periods tutorial show both ecosystems treat ingestion as an afterthought; AutoRAG shows users will accept managed chunking but need strategy escape hatches. Ingestion deserves the same modular, observable, versioned treatment as retrieval — including stable chunk/document identity across re-splits (#1167).
3. **Retrieval-as-tool and retrieval-as-pipeline must be the same component.** The AI SDK proves agents want retrieval as a callable tool; Spring AI/LangChain4j prove enterprises want declarative pipelines; AutoRAG's MCP endpoint proves managed retrieval can serve agents. Today you pick an idiom; a next-gen framework should expose one retriever as pipeline stage, tool, and MCP server simultaneously.
4. **Evaluation must be built into the pipeline, not bolted on.** Nobody in this group can answer "was retrieval correct?" in production (E1, E2, no third-party benchmarks). Instrument recall/groundedness hooks at the retriever boundary from v0.
5. **API stability is a feature enterprises will trade capability for.** Three AI SDK majors in 11 months, Spring AI 2.0 renaming modules 13 months after GA, and LangChain4j's 2.5-year 0.x run all generated the loudest community pain in this report. A next-gen framework needs a stable narrow core (documents, chunks, queries, filters) with churn quarantined to integration packages.
6. **Do not depend on a vendor's second-priority port; design for a small, embeddable core instead.** LlamaIndex.TS died pointing users to the vendor's cloud. The AI SDK survived by owning a small surface. AutoRAG's limits show managed services cap you. The durable position is a small, runtime-agnostic core (works on JVM constraints *and* edge bundle-size constraints) with retrieval quality logic — not integrations — as the moat.
7. **The JVM ecosystem's genuine contributions — typed pipelines, DI-injected per-tenant filters, Micrometer-grade observability, declarative AI services — should be table stakes**, not Java exotica. Python frameworks still lack all four; a next-gen framework should steal them.

---

## Sources

Primary docs & announcements:
- Spring AI RAG reference — https://docs.spring.io/spring-ai/reference/api/retrieval-augmented-generation.html
- Spring AI 1.0 GA announcement (May 20, 2025) — https://spring.io/blog/2025/05/20/spring-ai-1-0-GA-released
- Spring AI upgrade notes (1.x→2.0 breaking changes) — https://docs.spring.io/spring-ai/reference/upgrade-notes.html
- LangChain4j RAG tutorial — https://docs.langchain4j.dev/tutorials/rag ; site — https://docs.langchain4j.dev/
- Cloudflare AutoRAG/AI Search docs — https://developers.cloudflare.com/autorag/ ; how it works — https://developers.cloudflare.com/ai-search/concepts/how-ai-search-works/ ; chunking — https://developers.cloudflare.com/autorag/configuration/chunking/ ; limits & pricing — https://developers.cloudflare.com/autorag/platform/limits-pricing/ ; launch blog — https://blog.cloudflare.com/introducing-autorag-on-cloudflare/
- Vercel AI SDK embeddings/telemetry/RAG-guide docs (from repo): `content/docs/03-ai-sdk-core/30-embeddings.mdx`, `60-telemetry.mdx`, `31-reranking.mdx`, `content/cookbook/00-guides/01-rag-chatbot.mdx` — https://github.com/vercel/ai

GitHub issues (all verified via GitHub API, Aug 5, 2026):
- Spring AI: #3577, #1179, #3876, #3222, #6422, #3179, #4552, #3644, #2655, #2525, #4952, #2123, #6447, #1167, #1834, #4981, #3166, #2381, #4997, #2506, #2740, #3178 — https://github.com/spring-projects/spring-ai/issues
- LangChain4j: #2513, #5906, #151, #1263, #1600, #1252, #1615, #2328, #3498, #1851, #2929, #1122, #1066, #1330, #2117, #2133 — https://github.com/langchain4j/langchain4j/issues
- LlamaIndex.TS: README deprecation notice (commits of Mar 11, 2026); #1152, #161, #836, #2021, #1098, #1095, #1363 — https://github.com/run-llama/LlamaIndexTS
- Vercel AI SDK: #10082, #16101, #6268, #14425, #14926, #17811, #1062, #5682, #8017, #7072, #923 — https://github.com/vercel/ai/issues

Adoption/registry data:
- GitHub API repo stats (stars/issues/license/push dates) for spring-projects/spring-ai, langchain4j/langchain4j, run-llama/LlamaIndexTS, vercel/ai (Aug 5, 2026)
- npm downloads (Jul 6–Aug 4, 2026): `ai` 79,075,854/month; `llamaindex` 526,872/month — https://api.npmjs.org/downloads/point/last-month/ai , …/llamaindex
- Release dates via GitHub releases API: langchain4j 1.0.0 (2025-05-14), 1.18.1 (2026-07-29); spring-ai v2.0.0 (2026-06-12); ai@5.0.0 (2025-07-31), ai@6.0.0 (2025-12-22), ai@7.0.0 (2026-06-25)

Community sentiment (HN via Algolia API):
- AutoRAG launch/impressions: items 43611057, 43616798, 43804727 (→ https://bauva.com/blog/cloudflare-autorag-first-impressions/ — unreachable, HTTP 521, at review time)
- AutoRAG criticism: comment 45587797 (Oct 2025); Cloudflare outage report mentioning AutoRAG: comment 44261970 (Jun 2025)
- Spring AI tool-calling tutorial: item 44548906 (101 points, Jul 2025); AI SDK 5 announcement: item 44747192

Caveat: Cloudflare community-forum search returned HTTP 403 to automated fetch; forum-level AutoRAG complaints are therefore under-represented and the AutoRAG quality criticisms above rest on HN anecdotes plus documented limits.
