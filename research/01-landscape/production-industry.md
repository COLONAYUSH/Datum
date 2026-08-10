# Production & Industry Practice in Retrieval (incl. Security) — Landscape Review, mid-2026

> Research note for a paper motivating a next-generation RAG / agent-memory framework.
> Dimension: **production-industry**. Compiled 2026-08-05.
> Every claim below is anchored to a source that was actually fetched during this session, or is
> explicitly marked `[NOT VERIFIED IN THIS SESSION]`. Vendor marketing is labelled as such.

---

## Scope

This document covers **how retrieval is actually shipped** by hyperscalers, model labs, enterprise search vendors, agent-search API startups, and managed-RAG startups in the 2024–2026 window, plus the production failure modes and the security surface that retrieval introduces. It deliberately privileges **critiques, postmortems, and open problems** over capability lists.

In scope:

- Model-lab retrieval surfaces: Anthropic (contextual retrieval, agentic filesystem search, memory
  tool, Skills progressive disclosure, MCP), OpenAI (`file_search` / vector stores in the Responses
  API), Google (Gemini File Search, Vertex AI RAG Engine), AWS (Bedrock Knowledge Bases, Kendra,
  GraphRAG), Microsoft (Azure AI Search agentic retrieval / knowledge bases / Foundry IQ).
- Agent-facing web search & ingestion APIs: Exa, Tavily, Parallel, Firecrawl.
- Managed RAG vendors: Contextual AI, Vectara, EyeLevel/GroundX, Ragie.
- Latency/cost engineering: semantic caching (GPTCache, Redis LangCache), reranking budgets,
  token-based billing.
- Security: indirect prompt injection through retrieved content, corpus poisoning, jamming/DoS,
  exfiltration, ACL enforcement and tenant isolation, embedding inversion, provenance/audit.

Out of scope (sibling documents): retriever architecture research, embedding-model research, GraphRAG algorithms per se, RAG evaluation methodology research.

Method caveat: this session's web-search budget was exhausted before work began, so sourcing relied on direct fetches of primary pages (vendor docs, arXiv abstract pages) plus the arXiv and Hacker News Algolia JSON APIs. Several seed-list items could not be verified and are flagged inline. **No citation, arXiv ID, or number in this file was reconstructed from memory.**

---

## Lineage & chronological development

The production lineage of RAG is best read as **five successive shifts in where the intelligence lives**, each shift a response to the previous stage's dominant failure mode.

### Stage 0 — Retrieve-then-read as a library pattern (2020–2023)

The pattern industry inherited: chunk documents at fixed size, embed with an off-the-shelf model, store in a vector database, retrieve top-k by cosine similarity, stuff into a prompt. Almost all production deployments in this era were assembled from LangChain/LlamaIndex tutorials. This is what Contextual AI later pejoratively named **"frozen RAG"** or "Frankenstein's monster" — a pipeline whose "individual components technically work, but the whole is far from optimal," coupling off-the-shelf embeddings, a vector DB, and a black-box LM together by prompting alone ([Contextual AI, RAG 2.0](https://contextual.ai/introducing-rag2/)).

The dominant failure mode of Stage 0 is **the demo-to-production cliff**: a system that looks correct on 100 documents and is unusable on 5,000,000. A widely-read practitioner writeup (551 points on HN, 2025-10-20) states this directly — the team shipped a prototype from tutorials quickly, but on the production corpus "the results were subpar and only the end users could tell," requiring months of system rewrites ([Production RAG: what I learned from processing 5M+ documents](https://blog.abdellatif.io/production-rag-processing-5m-documents)).

### Stage 1 — Fix the chunk (2024)

The first serious industrial correction was to attack the **context-free chunk**: a chunk severed from its document loses the referents ("the company," "in Q2," "this provision") that make it retrievable. Anthropic's **Contextual Retrieval** (September 2024) prepends 50–100 tokens of LLM-generated, chunk-specific context before embedding and before BM25 indexing. The reported effect on retrieval failure rate:

| Configuration | Retrieval failure rate | Reduction |
|---|---|---|
| Baseline (embeddings, top-20) | 5.7% | — |
| Contextual embeddings | 3.7% | 35% |
| Contextual embeddings + contextual BM25 | 2.9% | 49% |
| + reranking | 1.9% | 67% |

Two details matter more for framework design than the headline numbers. First, the one-time contextualization cost is quoted at **$1.02 per million document tokens** using prompt caching — i.e. industrial-scale index-time LLM calls became economically routine. Second, Anthropic's own guidance undercuts RAG for a large slice of use cases: for knowledge bases **under ~200,000 tokens (~500 pages), just put the whole corpus in the prompt** ([Anthropic, Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)). That threshold is a load-bearing admission — it means a meaningful fraction of "RAG projects" in industry are architecture chosen against the vendor's own advice.

### Stage 2 — Fix the query, not the chunk (2024–2025)

Practitioners converged, largely independently of academic work, on **query-side** interventions as the highest-ROI fix. The 5M-document writeup ranks its wins in explicit ROI order:

1. **Query generation** — use an LLM to read the conversation thread and emit multiple semantic and
   keyword query variants, run them in parallel, then merge and rerank. Ranked #1 by impact.
2. **Reranking** — "the highest value 5 lines of code you'll add." Their production configuration:
   **50 chunks into the reranker, top 15 to the LLM.**
3. **Chunking** — consumed the most engineering time and needed per-customer customization; no
   universal strategy.
4. **Metadata in the chunk text** — titles/authors concatenated with chunk body materially improved
   answers over text-only.
5. **Query routing** — a cheap classifier detects questions RAG cannot answer (whole-corpus
   summarization, attribution/aggregation) and routes them elsewhere.

**Cross-reference — this #1 ranking is contradicted by the academic ablations.** `query-understanding-transformation.md` calls multi-query "the most cargo-culted technique in practitioner RAG stacks relative to its evidence base" (ARAGOG found multi-query *underperforming* naive RAG; RAG-Fusion documents off-topic drift; DMQR-RAG shows naive paraphrases are near-duplicates). Both readings stand, and the tension is informative rather than a simple error. What differs is the intervention actually measured: the production win is LLM-generated **semantic *and* keyword** variants read off the whole conversation thread, run in parallel, merged, **and then passed through a cross-encoder reranker** (50 → 15) over 5M heterogeneous enterprise documents — the reranker repairs exactly the equal-weight-RRF dilution the negative results attribute to multi-query, and lexical+semantic variety pays off on heterogeneous corpora where a single embedding view misses. The ablations measure naive paraphrase multi-query fused by equal-weight RRF, **without** a reranker, on small homogeneous academic corpora. Read together: multi-query is a *recall broadening* device whose value is conditional on (a) a precision stage downstream and (b) corpus heterogeneity — not a standalone win, and not worthless. See the matching note in `query-understanding-transformation.md` §5.

Their infrastructure churn is itself a finding: vector store Azure → Pinecone → Turbopuffer; reranker none → Cohere 3.5 → Zerank. Production retrieval stacks in this period were not stable ([source](https://blog.abdellatif.io/production-rag-processing-5m-documents)).

### Stage 3 — Retrieval becomes a managed cloud primitive (2025)

Through 2025 every major platform shipped a hosted retrieval product, moving chunking, embedding, and ranking behind an API: **OpenAI `file_search`** over managed vector stores in the Responses API; **Google Gemini API File Search** (announced **2025-11-06**); **Vertex AI RAG Engine** (a six-stage pipeline with pluggable vector backends); **Amazon Bedrock Knowledge Bases**, bifurcated into Managed and Customer-managed tiers; and **Azure AI Search agentic retrieval / knowledge bases** (Build 2025, now partially GA in the `2026-04-01` REST API), which also became the substrate for **Foundry IQ**, Microsoft's "managed knowledge layer that transforms enterprise content into reusable, permission-aware knowledge bases for agents." Each is treated in detail in §2–§5 below.

Simultaneously, the standalone provisioned enterprise index went the other way: **Amazon Kendra closed to new customers**, with AWS pointing prospects at Bedrock Knowledge Bases (§6a).

### Stage 4 — Retrieval becomes agentic (2025–2026)

The current phase replaces the single-shot retrieve-then-read with a **loop**: the model plans queries, issues several in parallel, judges sufficiency, and iterates.

- **Anthropic's multi-agent research system** (orchestrator-worker; lead agent spawns subagents with
  private context windows that compress findings before returning) explicitly rejects static RAG in
  favour of "multi-step search that dynamically finds relevant information, adapts to new findings."
  Reported: Opus-4 lead + Sonnet-4 subagents beat single-agent Opus 4 by **90.2%** on an internal
  research eval; parallel tool calling cut research time **up to 90%**. The cost is stark: agents use
  ~**4×** the tokens of chat, multi-agent ~**15×**, and **token usage alone explains 80% of
  performance variance**
  ([Anthropic engineering](https://www.anthropic.com/engineering/multi-agent-research-system)).
- **Azure agentic retrieval** formalizes the same loop as a managed pipeline: LLM query planning →
  parallel subqueries (keyword/vector/hybrid) over one or more knowledge sources → per-subquery
  semantic (L2) reranking → merge, with optional references and an **activity log**. Reasoning effort
  is a dial: `minimal` skips planning entirely, `low` (default) and `medium` invoke the LLM. Microsoft
  states plainly that this "adds latency compared to a single-query pipeline"
  ([docs](https://learn.microsoft.com/en-us/azure/search/search-agentic-retrieval-concept)).
- **Bedrock Managed KB Agentic Retrieval** does multi-hop reasoning, decomposes queries into
  subqueries, retrieves iteratively across *multiple* knowledge bases, and "evaluates sufficiency of
  responses" ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)).

### Stage 5 — Retrieval as filesystem + context engineering (2025–2026)

Running in parallel is a stronger claim: that for many corpora you should not build an index at all. Claude Code popularized **agentic grep/glob/read over a live filesystem**, and the argument reached wide practitioner attention as *"The RAG Obituary: Killed by agents, buried by context windows"* (nicolasbustamante.com, **290 points / 179 comments on HN, 2025-10-01**, HN item `45439997`). The essay URL 404s from this session's fetches; the HN thread is the durable artifact. See **Failure modes & critiques** for the substance of the debate.

Anthropic's own tooling encodes the same philosophy without abandoning retrieval:

- **Agent Skills / progressive disclosure**: only `name` + `description` of every installed skill are
  preloaded into the system prompt; the full `SKILL.md` loads when the agent judges it relevant;
  bundled files load lazily below that. Because "agents with a filesystem and code execution tools
  don't need to read the entirety of a skill into their context window," the bundled context is
  "effectively unbounded"
  ([Anthropic engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)).
  This is **retrieval reframed as a documentation hierarchy the model navigates**, not a similarity
  search it queries.
- **Memory tool + context editing**: Claude creates/reads/updates/deletes files in a memory directory
  **on the developer's infrastructure**, persisting across conversations; context editing auto-evicts
  stale tool calls/results near the token limit. Reported: **+39%** on agentic search from memory +
  context editing, **+29%** from context editing alone, and **−84% token consumption** on a 100-turn
  web-search eval ([Claude platform blog](https://claude.com/blog/context-management)).
- **MCP** (announced **2024-11-25**) standardizes the connector layer, explicitly framed as solving
  the N×M problem where "every new data source requires its own custom implementation"
  ([Anthropic](https://www.anthropic.com/news/model-context-protocol)).

The through-line across stages 4–5: **industry has moved the retrieval decision from index time to inference time**, and is paying for it in tokens and latency.

---

## State of the art — mid-2026 snapshot

1. **Managed retrieval is the default, and it is opaque.** Every hyperscaler ships a hosted
   chunk-embed-rank pipeline. Vendors differ enormously in how much of the pipeline they disclose:
   Azure documents planning, fan-out, L2 reranking, per-subquery limits, and emits an activity log;
   OpenAI's `file_search` documentation discloses **neither chunk size, nor overlap, nor whether
   reranking occurs at all** — only `max_num_results` and metadata `filters`.
2. **Agentic multi-query retrieval is the SOTA managed pattern.** Azure knowledge bases, Bedrock
   Managed KB agentic retrieval, and lab-internal research agents all implement plan → parallel
   subqueries → rerank → sufficiency check → iterate. Latency and token cost are the acknowledged
   price.
3. **Billing has shifted from per-query to per-token, and is not cross-vendor comparable.** Azure
   moved from "uniform cost per query" (classic semantic ranker) to "variable cost per token
   (depends on reasoning effort)" for agentic retrieval. Meanwhile OpenAI bills `file_search` at
   **$2.50 / 1k tool calls + $0.10 / GB-day storage (1 GB free)**, and Google bills File Search at
   **$0.15 / 1M index-time tokens with free storage and free query embeddings**. These units do not
   convert into each other.
4. **Hybrid retrieval + cross-encoder reranking is settled practice, not a research question.**
   Contextual BM25 alongside contextual embeddings, then a reranker, is the industrial default;
   Azure hardwires semantic reranking into every subquery; the 5M-doc practitioner report calls the
   reranker the single highest-ROI line of code.
5. **The retrieval-vs-long-context boundary is drawn around a few hundred thousand tokens, and it
   moves.** Anthropic's ~200k-token / ~500-page guidance is the clearest published threshold.
6. **Agent-facing search APIs are a distinct product category with explicit latency tiers.** Exa
   exposes six search modes spanning **~250 ms (instant) to 12–40 s (deep-reasoning)** plus
   category-specific indexes (1B+ people, 50M+ companies, 350M+ scholarly publications) and
   token-efficient highlights ("10× more token-efficient extracts")
   ([Exa docs](https://exa.ai/docs/reference/getting-started)). Tavily returns aggregated,
   AI-scored, context-window-optimized results from up to 20 sources in one call
   ([Tavily docs](https://docs.tavily.com/documentation/about)). Firecrawl (161k GitHub stars,
   AGPL-3.0 core) ships scrape/search/crawl/map/agent endpoints with a claimed **P95 latency of
   3.4 s** and **96% web coverage** ([GitHub](https://github.com/firecrawl/firecrawl)).
7. **Security is the least-solved production dimension.** Indirect prompt injection through retrieved
   content is, as of mid-2026, an unsolved architectural problem with a shipped, patched,
   critical-severity CVE against a flagship enterprise RAG product (CVE-2025-32711, Microsoft 365
   Copilot, published 2025-06-11; **NVD 7.5 HIGH vs Microsoft's own 9.3 CRITICAL** — the vendor rates
   it more severely than NVD).
8. **Permission-aware retrieval is being pulled into the platform layer**, e.g. Bedrock Managed KB's
   document-level ACL filtering at retrieval time (all connectors except Web Crawler), and Microsoft
   Foundry IQ's "permission-aware knowledge bases." Notably, in Bedrock this is a **Managed-only**
   feature — teams that want control over the vector store lose ACL filtering.
9. **The standalone enterprise-search index is consolidating into the model platform.** Amazon Kendra
   — the archetype of the provisioned, always-billed semantic enterprise index — is **no longer open to
   new customers**, with AWS directing prospects to Bedrock Knowledge Bases
   ([Kendra docs](https://docs.aws.amazon.com/kendra/latest/dg/what-is-kendra.html)). Its
   pay-for-provisioned-index-even-if-empty billing is the model that consumption pricing displaced.
10. **Breadth and reasoning depth are explicitly rationed against each other.** Azure's published
   quotas allow **10** knowledge sources per knowledge base at `minimal` reasoning effort but only **3**
   at `low` (the default) and **5** at `medium`, because planning cost and fan-out scale with source
   count. Reranking has a matching hard ceiling: **2–4 concurrent semantic-ranker requests per search
   unit** with a 4–8 request queue
   ([service limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity)).
11. **Model-version drift in the embedding layer is now vendor-acknowledged.** Elastic advises
   explicitly pinning `inference_id` in production "to avoid model inconsistencies" — the only vendor in
   this review to name the hazard. Fully-managed products expose no equivalent pin.
12. **The 2026 attack literature is content-innocent, and the credible defences have moved out of the
   prompt.** Salience-induction and metadata-impersonation attacks carry no injected instruction;
   meanwhile CaMeL (control-flow isolation), SD-RAG (policy enforced at retrieval), and CleanBase
   (corpus-level clique detection) all enforce outside the prompt, while filtering-based layered
   defences still report double-digit residual attack success.

---

## Thematic subsections

### 1. Anthropic: retrieval as context engineering rather than as an index

Anthropic is the clearest example of a vendor whose *published* retrieval position moved from "improve the index" (2024) to "give the model tools and a filesystem" (2025–2026).

- **Contextual Retrieval (2024-09)** — index-time LLM enrichment; hybrid contextual embeddings +
  contextual BM25 + reranking; 5.7% → 1.9% retrieval failure; $1.02/M document tokens with prompt
  caching; explicit "<200k tokens, skip RAG" carve-out.
- **MCP (2024-11-25)** — the connector standard; "secure, two-way connections between data sources and
  AI-powered tools"; launched with servers for Google Drive, Slack, GitHub.
- **Multi-agent research system (2025)** — orchestrator-worker; subagent context isolation with
  compression on return; +90.2% vs single agent internally; 15× token multiplier; "start with broad
  searches before narrowing" as an explicit heuristic.
- **Agent Skills (2025–2026)** — three-level progressive disclosure (metadata → SKILL.md → bundled
  files), making bundled context "effectively unbounded."
- **Memory tool + context editing (2025)** — developer-hosted memory directory, file CRUD, automatic
  eviction of stale tool results; +39% agentic search, −84% tokens over 100 turns.
- **Claude Code's grep/glob/read search** — the archetype of index-free retrieval over source trees.
  `[NOT VERIFIED IN THIS SESSION: no Anthropic engineering post specifically documenting Claude Code's
  search-tool design was fetched. The general pattern is corroborated by the Skills post's statement
  that filesystem+code-execution agents avoid loading full context.]`

**Framework-relevant reading.** These five artifacts describe a coherent architecture in which retrieval is (a) hierarchical rather than flat, (b) navigated rather than queried, (c) stateful across sessions via files, and (d) budgeted, with eviction as a first-class operation. That is a materially different object from a top-k vector search, and none of the hosted vector-store APIs express it.

### 2. OpenAI: hosted vector stores with an undocumented middle

`file_search` is a hosted tool the model invokes autonomously; the developer creates a vector store, uploads files via the File API, references store IDs on the response, and gets back a `file_search_call` item plus a message with file citations. Supported inputs include PDF, Office, code, and plain text (UTF-8/UTF-16/ASCII).

What is exposed: `max_num_results` (explicitly a token/latency-vs-quality dial), metadata `filters` with key-value matching, citations, ZDR/data-residency options, tier-dependent rate limits of 100–1000 RPM.

What is **not** exposed in the fetched documentation: chunk size, chunk overlap, whether either is configurable, whether a reranker runs, which embedding model is used, per-store file counts, per-file size caps, or token limits. Pricing is documented separately: **$2.50 per 1k tool calls; $0.10 per GB per day, 1 GB free** ([file_search docs](https://developers.openai.com/api/docs/guides/tools-file-search), [pricing](https://developers.openai.com/api/docs/pricing)).

For comparison, the same pricing page lists **web search at $10.00/1k calls** (search content tokens billed at model rates) and a non-reasoning preview variant at **$25.00/1k calls** with free search content tokens. Retrieval-over-the-open-web is thus ~4–10× the unit price of retrieval-over-your-files at this vendor.

**Critique.** Undocumented chunking and ranking is a *reproducibility* problem, not merely an aesthetic one. If chunk boundaries and rank order can change without notice, then (i) an offline retrieval eval cannot be reproduced across dates, (ii) regressions cannot be attributed to the application vs the platform, and (iii) an academic result measured against `file_search` is not replicable. This directly conflicts with the eval-drift discipline that production teams report is essential.

`[NOT VERIFIED IN THIS SESSION: ChatGPT memory (saved memories vs "reference chat history") and ChatGPT connectors. openai.com and help.openai.com both returned HTTP 403 to this session's fetches. Claims about their mechanics are deliberately omitted rather than reconstructed.]`

### 3. Google: two products, two philosophies

**Gemini API File Search** is the "zero-config" end: Google manages storage, chunking ("optimal chunking strategies"), embeddings, and context injection, and returns built-in citations that "specify which parts of your documents were used." Launched 2025-11-06. Pricing is index-time-only (**$0.15/1M tokens**, `gemini-embedding-001`), with storage and query-time embedding free — a pricing shape that encourages large, rarely-rebuilt indexes and *discourages* frequent reindexing. That is a staleness incentive worth naming.

**Vertex AI RAG Engine** is the configurable end: explicit ingest → transform → embed → index → retrieve → generate stages; sources including Cloud Storage and Google Drive; backends spanning RagManagedDb, Agent Platform Vector Search 2.0, Weaviate, Pinecone, Feature Store, and Agent Platform Search. Documented constraints are operational rather than algorithmic: limited regional GA (select US/Europe; Asia in Preview), **allowlist required for `us-central1`, `us-east1`, `us-east4`**, VPC-SC and CMEK supported but **data residency not supported**, and billing for managed Spanner instances in GA locations.

**Critique.** "Data residency not supported" on a managed RAG service is a hard blocker for a large class of regulated enterprise deployments, and it is the kind of constraint that does not appear in any capability comparison. Regional allowlisting also means that a working architecture may be non-deployable in the region the customer requires.

### 4. AWS: the managed/self-managed fork is a governance fork

Bedrock Knowledge Bases' 2026 split is the most instructive vendor design in this landscape because the trade-off is not performance, it is **governance**:

| | Managed KB | Customer-managed KB |
|---|---|---|
| Embedding / rerank / "reasoning" models | Service-managed by default, overridable | Fully yours |
| Vector store | Managed, auto-scaling | OpenSearch Serverless, Aurora, **Neptune** |
| Third-party connectors (SharePoint, Confluence, Google Drive, OneDrive, Web Crawler, S3) | Yes | **No** |
| Document-level ACL filtering at retrieval time | **Yes** (all connectors except Web Crawler) | **No** |
| Native AgentCore Gateway (MCP tool exposure) | **Yes** | **No** |
| Multi-modal ingestion, Smart Parsing (PDF/PPTX/DOCX/embedded visuals/audio/video/scanned) | Yes | You build it |
| Agentic multi-hop retrieval across multiple KBs w/ sufficiency evaluation | Yes | You build it |
| Observability (retrieval traces, agentic traces, per-KB metrics) | Native AgentCore | You build it |

Source: [Bedrock KB user guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html). AWS also supports building a KB over an **Amazon Kendra GenAI index** and over **Neptune Analytics graphs** (the GraphRAG path), and supports image-as-query and mixed text+image queries via multimodal embedding models, plus rerank models "to influence the results that are retrieved."

**Critique.** Coupling **document-level permission enforcement** to the managed tier creates a perverse incentive: the teams with the strongest reasons to control their own vector store (regulated industries, data-locality constraints, custom embeddings) are exactly the teams that lose platform-provided ACL filtering and must reimplement it — the single most security-critical component — themselves. This is a recurring shape across vendors: **security features ride on the least-controllable tier.**

#### 4a. Bedrock GraphRAG (Neptune Analytics) — the most honestly-documented limitation set in this review

Mechanism: after an initial vector search over nodes, GraphRAG (1) retrieves related graph nodes / chunk identifiers linked to the retrieved chunks, (2) traverses the graph to expand those related chunks and pull their details from Neptune, (3) answers from the enriched context. It "automatically identifies and uses relationships between entities and structural elements (such as section titles) across multiple document sources," targeting the multi-hop / cross-document case ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html)). Available in 7 regions (Frankfurt, London, Ireland, Oregon, N. Virginia, Tokyo, Singapore).

Documented limitations, which read as a catalogue of GraphRAG's productization problems:

- **"Configuration options to customize the graph build are not supported."** The extraction schema is
  the vendor's.
- **Autoscaling is not supported** for Neptune Analytics graphs.
- **S3 only** as a data source — none of the connector fleet (SharePoint/Confluence/Drive/OneDrive)
  works with GraphRAG.
- A foundation model must be chosen for **graph construction**, and selecting one "automatically
  enables contextual enrichment" — i.e. index-time LLM cost is mandatory and coupled.
- **1,000 files per data source** by default, raisable to 10,000, else partition the S3 bucket into
  folders.
- With **hierarchical chunking**, GraphRAG "retrieves only the child chunks... It doesn't replace the
  child chunks with their corresponding parent chunks," so results lose the broader parent context —
  a silent interaction between two features the customer configured independently.
- Deleting the knowledge base **does not delete the Neptune graph**; "additional charges may be
  incurred until you explicitly delete the graph."
- AWS warns the graph-construction model can reach end-of-life (Claude 3 Haiku cited as Legacy),
  implying **graphs built with a deprecated extractor cannot be rebuilt identically**.

**Framework-relevant reading.** GraphRAG in production is a *derived artifact with its own lifecycle* — built by a model version, non-customizable, non-autoscaling, orphaned on delete, and silently interacting with the chunking strategy. Every one of those properties is a consequence of treating a knowledge graph as a build output rather than as a maintained index with provenance and versioning.

### 5. Microsoft: the most transparent managed pipeline, and the most complex billing

Azure AI Search's agentic retrieval is worth reading in full because Microsoft publishes the pipeline stages, the components, the knobs, and a worked cost model.

**Pipeline.** (1) app calls a knowledge base with a `retrieve` action carrying query + conversation history; (2) **query planning** — at `low`/`medium` reasoning effort an LLM emits focused subqueries; at `minimal` this is skipped and queries go straight to knowledge sources; (3) **query execution** — all subqueries run simultaneously, each keyword/vector/hybrid, each **semantically reranked (L2)**, references extracted for citation; (4) **synthesis** — merged content always returned; source references and an **execution activity log** optional.

**Components.** Knowledge base (orchestrator), knowledge source (**indexed** = backed by a local search index, or **remote** = fetched at query time from an external platform), search index with a semantic configuration, semantic ranker (internal L2), and an Azure OpenAI LLM for planning and source selection.

**Stated motivations** are unusually concrete: multi-ask questions ("hotel near the beach, with airport transportation, within walking distance of vegetarian restaurants"), questions depending on earlier conversation turns, queries benefiting from synonym maps and LLM paraphrasing, and **spelling mistakes**.

**Billing.** Two meters. Azure AI Search bills **retrieval tokens** consumed during subquery execution and semantic ranking (free monthly token allowance by default; standard plan enables PAYG beyond it); Azure OpenAI bills planning and answer-synthesis tokens. The documented shift:

| Aspect | Classic single-query pipeline | Agentic retrieval |
|---|---|---|
| Unit | Query based | **Token based** |
| Cost per unit | Uniform per query | **Variable per token (depends on reasoning effort)** |
| Cost estimation | Estimate query count | Estimate token usage |
| Free allowance | Monthly free *query* allowance | Monthly free *token* allowance |

Microsoft's worked example: 2,000 agentic retrievals × 3 subqueries = ~6,000 queries; 50 chunks reranked per subquery = 300,000 chunks; ~500 tokens/chunk = **150M reranking tokens → $3.30**; plus query planning with gpt-4o-mini (2,000 input tokens × 2,000 retrievals = 4M input = $0.60; 350 output tokens × 2,000 = 700k output = $0.42) → **$1.02 planning, $4.32 total**.

> **Caution on this example.** The doc states "a hypothetical price of 0.022 per token" and then
> derives $3.30 from 150M tokens; that arithmetic implies **$0.022 per *thousand* tokens**, so the
> stated unit in the doc is off by 1000×. Cite the **$3.30 / $4.32 totals and the query→token billing
> shift**, not the per-token figure. (Also note the coincidence that Microsoft's "$1.02 for query
> planning" is numerically identical to Anthropic's "$1.02 per million document tokens" for
> contextual retrieval — unrelated quantities.)

**Microsoft's own cost-control advice is a de facto list of agentic-retrieval failure modes**: review the activity log to see which queries hit which sources; **reduce the number of knowledge sources because consolidating content lowers fan-out and token volume**; lower reasoning effort to cut planning/expansion; and "organize content so the most relevant information can be found with fewer sources and documents (for example, curated summaries or tables)." The last item is significant: the vendor is telling customers that **corpus curation, not retrieval sophistication, is the cost lever**.

**A candid reproducibility admission.** Microsoft warns that you can reissue logged queries to estimate tokens, but "precise reconstruction of a query or response isn't guaranteed," citing factors including public web knowledge sources and "a remote SharePoint knowledge source that's predicated on a user identity." **Identity-dependent retrieval is therefore non-deterministic and non-reproducible by construction** — a first-order problem for both eval and audit.

**Hard limits, and an inversion worth naming.** The service-limits page ([Azure AI Search service limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity), doc date 2026-08-04) publishes agentic-retrieval quotas that contain a counter-intuitive shape:

| Limit | Free | Basic | S1 | S2/S3 | S3 HD | L1/L2 | Serverless Developer |
|---|---|---|---|---|---|---|---|
| Max knowledge sources per **service** | 3 | 5 or 15 | 50 | 200 | **0** | 10 | 30 |
| Max knowledge bases per **service** | 3 | 5 or 15 | 50 | 200 | **0** | 10 | 30 |
| Max knowledge sources per KB, `minimal` effort | 3 | 5 or 10 | 10 | 10 | 0 | 10 | 10 |
| Max knowledge sources per KB, `low` effort (default) | 3 | **3** | **3** | **3** | 0 | **3** | **3** |
| Max knowledge sources per KB, `medium` effort | 3 | **5** | **5** | **5** | 0 | **5** | **5** |

**More LLM reasoning buys you fewer knowledge sources**, not more: `minimal` (no query planning) allows 10 sources per knowledge base, `low` allows 3, `medium` allows 5. Microsoft explains this directly — "in earlier preview API versions, the `minimal` reasoning effort supports more knowledge sources than `low` or `medium` because it bypasses LLM-based query planning" — and notes `2026-05-01-preview` normalizes all three to 10. The underlying constraint is that **planning cost and fan-out scale multiplicatively with source count**, so the platform rations breadth against depth. Also note **S3 HD supports zero knowledge sources and zero knowledge bases** — the highest-density tier cannot do agentic retrieval at all.

**A throughput ceiling on reranking.** Semantic ranker — mandatory in every agentic subquery — is throttled by a queue: **max 2 (Basic) / 3 (S1) / 4 (S2 and above) concurrent requests per search unit**, with a request queue of **4 / 6 / 8** per SU; "if the queue is full, the system rejects further requests and they must be retried." Total semantic-ranker QPS depends on tier, SU count, **regional semantic-ranker capacity**, and per-query service time. Since agentic retrieval issues ~3 subqueries each requiring a rerank, **effective agentic-retrieval QPS is roughly the semantic-ranker concurrency limit divided by the fan-out** — a fact absent from the agentic-retrieval overview page but decisive for capacity planning.

Other constraining limits: max **4,096** dimensions per vector field; max **10** fields in a vector query; vector index quota **per partition** of 5 / 35 / 150 / 300 GB (Basic / S1 / S2 / S3-HD) for post-April-2024 services, where exceeding it is a **hard indexing failure**; Serverless capped at **300 MB vector index per index (~30% of index storage)** and 1 GB max index size; 24 B documents per index; ~16 MB max document/request payload; blob extraction capped at 256k–16M characters by tier; indexer max runtime 2 h (public execution env) or 24 h (private); and **minimum indexer schedule of 5 minutes — the platform floor on pull-mode index freshness**. Higher storage/vector limits are unavailable in Israel Central, Qatar Central, Spain Central, and South India.

**Preview-surface risk.** Features are split across `2026-04-01` (GA, programmatic only) and `2026-05-01-preview`; the Azure portal and Foundry portal expose *only* preview features. Microsoft further warns that preview connections to Microsoft and third-party services "might result in data processing or storage outside of the Azure compliance boundary, as well as data flowing into the Azure compliance boundary," and pushes responsibility for compliance boundaries, permissions, and responsible-AI mitigations onto the customer.

### 6. Enterprise search and permission-aware retrieval

#### 6a. Amazon Kendra is being sunset — the clearest consolidation signal in this landscape

The Kendra developer guide now opens with: **"Amazon Kendra is no longer open to new customers. For capabilities similar to Amazon Kendra, explore Amazon Bedrock Knowledge Bases."** ([docs](https://docs.aws.amazon.com/kendra/latest/dg/what-is-kendra.html)). This matters well beyond AWS product management, because Kendra was the archetype of the *provisioned enterprise search index*:

- **Semantic-first by design**: "Unlike traditional keyword-based search, Amazon Kendra uses semantic
  and contextual similarity—and ranking capabilities—to decide whether a text chunk or document is
  relevant to a retrieval query." Handles factoid, descriptive, and ambiguous keyword queries.
- **Three index types**: GenAI Enterprise Edition (highest accuracy, "latest information retrieval
  technologies and semantic models," recommended), Basic Enterprise Edition, Basic Developer Edition
  (PoC only). The **GenAI index** is consumable from Amazon Q Business and Bedrock Knowledge Bases.
- **Kendra Intelligent Ranking** lets you use Kendra's semantic model to **rerank another search
  engine's results** — an early instance of reranking sold as a standalone primitive.
- **Security posture**: "Your search results reflect the security model of your organization and can be
  filtered based on the user or group access to documents. **Customers are responsible for
  authenticating and authorizing user access.**" That last sentence is the crux — the platform filters,
  the customer must supply correct identity, and the seam between them is where ConfusedPilot-class
  bugs live.
- **Billing shape**: after the free trial, "you are charged for all provisioned Amazon Kendra indices,
  **even if they are empty and no queries are run**," plus charges for scanning and syncing documents.

**Why this is a finding, not a footnote.** Kendra's pricing model — pay for a provisioned index whether or not you query it — is the *opposite* of the 2025–2026 direction (OpenAI per-call, Google per-indexed- token, Azure per-retrieval-token, Serverless per-CU-hour). Its closure to new customers is evidence that **provisioned, always-on retrieval indexes lost to consumption-priced retrieval**, and that retrieval is being absorbed into the model-platform layer (Bedrock KB, Amazon Q) rather than sold as standalone enterprise search. A framework designed around a persistent, provisioned index is designing against the direction of the market.

#### 6b. Elastic: chunking as a mapping property, and a candid model-versioning warning

Elastic's `semantic_text` field type "simplifies the inference workflow by providing inference at ingestion time with sensible defaults" — documents are automatically sent to an inference endpoint for embedding on index, ELSER (`.elser-2-elasticsearch`) is a supported sparse model, and queries work through Query DSL `match` and ES|QL's `match` operator with semantic relevance scoring ([Elastic docs](https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text)). Chunking is a **first-class, declarative mapping setting** rather than application-side preprocessing; the reference page shows `chunking_settings` with `strategy`, `max_chunk_size`, and `overlap` (illustrated as `"word" / 120 / 40`) ([mapping reference](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/semantic-text)). `[UNCERTAIN: the pages fetched here do not state the *default* strategy/size/overlap values; the 120/40 figures appear in an example, not as documented defaults. Do not cite them as defaults.]`

The most transferable finding is a warning Elastic gives explicitly: **"for production environments we recommend explicitly specifying the `inference_id`"** to avoid model inconsistencies. That is a vendor acknowledging **embedding-model version drift** as a production hazard — if the default inference endpoint changes, new vectors are not comparable with old ones and the index silently degrades. None of the fully-managed retrieval products in Table A expose an equivalent pin.

`[NOT VERIFIED IN THIS SESSION: Elastic's RRF hybrid-ranking implementation and ELSER's retrieval quality numbers. elastic.co/blog/elasticsearch-relevance-engine-esre and the search-labs semantic_text post both 404'd.]`

#### 6c. Glean

`[NOT VERIFIED IN THIS SESSION. docs.glean.com's homepage confirms only the product surface — search over connected applications, Glean Chat, agents with prebuilt templates, and connectors to "connect all of your existing applications" — and contains no architectural detail. Four further URL attempts (glean.com/blog/glean-search-architecture, glean.com/blog/how-glean-search-works, help.glean.com/en/articles/10093163-permissions-in-glean, and its redirect target) returned 404. Glean is the flagship permissions-aware enterprise search vendor and any claim about its hybrid retrieval, knowledge graph, ranking signals, personalization, or query-time ACL enforcement would be reconstruction. Deliberately omitted. **This is the single largest sourcing gap in this document and should be filled by a follow-up pass with working search.**]`

What *is* verifiable about the permission-aware layer from platform docs:

- **Bedrock Managed KB**: "document-level permission filtering using Access Control Lists (except for
  Web Crawler) **at retrieval time**."
- **Azure / Foundry IQ**: "permission-aware knowledge bases for agents"; and remote knowledge sources
  (e.g. SharePoint) that are "predicated on a user identity."

Both place enforcement at **retrieval time**, filtering candidates against the calling identity — rather than, say, maintaining per-principal indexes. Retrieval-time filtering is the pragmatic choice but it has two known hazards discussed under Failure modes: **post-filtering starvation** (filtering after top-k collapses recall for low-privilege users) and **stale ACL windows** (permission changes propagate more slowly than content, so revoked access remains retrievable).

### 7. Agent-facing search and ingestion APIs

A genuinely new product category: search engines whose customer is a model, not a person.

| Vendor | Distinctive design point | Verified specifics |
|---|---|---|
| **Exa** | Latency tiers as a first-class API surface + category-specific indexes | 6 modes: instant ~250 ms, fast ~450 ms, auto ~1 s, deep-lite ~4 s, deep 4–15 s, deep-reasoning 12–40 s. Indexes: 1B+ people, 50M+ companies, 350M+ scholarly publications, news, blogs, financial reports. Outputs: highlights ("10× more token-efficient"), full text, LLM summaries, JSON-schema structured output. Separate Contents API for arbitrary URLs. |
| **Tavily** | Search→scrape→filter→extract collapsed into one call | Aggregates up to 20 sources/query, proprietary AI relevance scoring, results "optimized for language model context windows," includes a short answer for inter-agent communication. 1,000 free credits/month. LangChain and LlamaIndex partnerships. |
| **Parallel** | Two latency/quality modes plus an Extract API for objective-conditioned compression | Basic sub-1 s; Advanced ~3 s for multi-hop research. Claims leading results on BrowseComp, HLE, company-research, code-snippet precision, and FinanceBench recall vs Exa/Tavily. **Vendor-run evals; no independent verification available.** |
| **Firecrawl** | Open-core ingestion (AGPL-3.0) with an agent endpoint | 161k stars, 9.1k forks. Endpoints: scrape, search, crawl, map, agent (URL-free autonomous gathering), plus Interact for pre-extraction browser automation. Claims 96% web coverage, P95 3.4 s. Handles proxies/JS rendering/rate limits. MIT-licensed SDKs. |

**Two observations for framework design.** First, **every one of these vendors sells compression, not just recall** — highlights, summaries, objective-conditioned extraction, "token-efficient." The scarce resource in production retrieval is context, not candidates. Second, **latency is now a per-call parameter spanning two orders of magnitude** (250 ms to 40 s). A framework that models retrieval as a single latency class cannot express what these APIs already offer.

**Caveat on Exa's documentation practice:** the docs instruct AI coding agents to use a Dashboard Onboarding tool rather than build from the reference docs, calling it "significantly faster and less error-prone" — an admission that agent-readable API documentation is itself an unsolved retrieval problem.

### 8. Managed-RAG startups and the vendor-benchmark problem

- **Contextual AI — RAG 2.0 / CLMs.** The strongest *architectural* critique from a vendor: frozen
  pipelines are brittle because components are optimized independently, so RAG 2.0 "pretrains,
  fine-tunes, and aligns all components as a single integrated system, backpropagating through both
  the language model and the retriever." Claims: CLMs substantially beat GPT-4-based frozen RAG on
  NQ/TriviaQA/HotpotQA, better on HaluEvalQA/TruthfulQA faithfulness, and beat long-context models
  with less compute across 2K–2M-token haystacks ([RAG 2.0](https://contextual.ai/introducing-rag2/)).
  Limitations: benchmark comparisons are vendor-run, "adapted rather than standard" for the
  long-context comparison, and customer results are confidential.
- **Contextual AI — Grounded Language Model (GLM), 2025-03-04.** An LM tuned to prioritize
  "faithfulness to retrieved knowledge over information learned during pretraining," with inline
  citations emitted during generation. Claims SOTA on FACTS and to outperform all foundation models
  ([GLM announcement](https://contextual.ai/blog/introducing-grounded-language-model/)).
  **Vendor claim; unverified independently.** Notable framework implication regardless of the numbers:
  *groundedness as a model-level training objective* rather than a prompt instruction.
- **EyeLevel / GroundX.** Publishes a head-to-head accuracy study: **GroundX 97.83% vs
  LangChain/Pinecone 64.13% vs LlamaIndex 44.57%** on 92 questions over 1,000+ pages of complex
  Deloitte tax documents (textual/tabular/graphical), all with GPT-4 completion; attributes the gap to
  parsing documents into semantic "objects" plus a fine-tuned vision model for document components
  rather than cosine-similarity chunk matching
  ([EyeLevel](https://www.eyelevel.ai/post/most-accurate-rag)). **This is vendor-designed marketing
  material — the vendor chose the corpus, the questions, and the baselines' configuration.** Raw data
  and code are offered for verification. Treat the *direction* (parsing/tables/figures dominate
  accuracy on complex documents) as plausible and the *magnitudes* as unusable.
- **Vectara.** Best known publicly for the **hallucination leaderboard** (HHEM-2.3), which is more
  useful to this review as an eval artifact than as a product. See §9.
- **Ragie.** Managed RAG-as-a-service: connectors (Google Drive, Notion, Confluence, Slack),
  multimodal ingestion (text/PDF/image/audio/video), automatic chunking with **vector + keyword +
  summary indexes**, hybrid search, LLM reranking, entity extraction, and an MCP server. SOC 2 Type
  II / GDPR / HIPAA, cloud/VPC/on-prem, multi-tenant isolation ([ragie.ai](https://www.ragie.ai/)).
  The **summary index** alongside vector and keyword is the notable design point — it is the
  productized answer to the "RAG can't do whole-corpus summarization" routing problem the 5M-doc
  writeup describes.

**Pattern across this segment:** every vendor's differentiation is at the **ingestion/parsing** layer or the **model-training** layer, not the vector-search layer. Nobody in mid-2026 sells "better cosine similarity."

### 9. Groundedness measurement as shipped practice

Vectara's **hallucination leaderboard** operationalizes faithfulness as a production metric. Methodology: feed documents from news/tech/science/medicine/legal/sports/business/education to a model, instruct it to summarize **using only the passage**, and score factual consistency with HHEM-2.3. Corpus: **7,700+ articles, 50–24,000 words, deliberately unpublished to prevent overfitting**; temperature 0; refusals and minimal-content responses filtered out. Vectara states results are "proxies for RAG and agentic system performance."

Leaders as of the fetched snapshot (**May 2026**): Antgroup Finix S1 32B **1.8%**, OpenAI GPT-5.4-nano **3.1%**, Gemini 2.5 Flash Lite **3.3%**, Phi-4 **3.7%**, Llama 3.3 70B **4.1%**; lower-ranked models exceed **24%** ([leaderboard](https://github.com/vectara/hallucination-leaderboard)).

**Critiques Vectara itself acknowledges**: it measures only summarization-task hallucination, not all kinds; the metric is **gameable by extractive copying**; closed-book QA is untested; and it is model-graded evaluation, with the attendant bias concerns (Vectara argues scalability and reproducibility justify it).

**Two independent observations.** (a) That a 32B model leads and a small nano model places second suggests groundedness is largely orthogonal to scale — consistent with Contextual AI's claim that it is a *training-objective* property. (b) Because the metric rewards copying, a leaderboard-optimal system may be a **worse** RAG component: production RAG needs synthesis across chunks, which is precisely what extractive copying avoids. Optimizing the shipped metric can degrade the shipped product.

### 10. Latency and cost engineering: caching, fan-out, and the token budget

**Reranker fan-out is the dominant controllable cost in agentic retrieval.** Both the practitioner report (50 chunks in → 15 out) and Microsoft's cost model (50 chunks reranked per subquery × 3 subqueries) put the reranking window at ~50 and treat it as the main dial. Microsoft's own advice — consolidate knowledge sources to lower fan-out — is a cost-driven argument for *fewer, better-curated indexes*, which is in direct tension with the "connect everything" connector marketing of the same platforms.

**Semantic caching** is the standard latency/cost mitigation. GPTCache (Zilliz; 8.1k stars, 590 forks) is the reference open-source implementation: LLM adapter, embedding generator, vector store (Milvus/FAISS/PGVector/Chroma), cache storage (SQLite/Postgres/MongoDB/Redis), similarity evaluator, and cache manager with eviction and distributed caching. Claimed "10× reduction in API costs" and "100× speed boost" ([GitHub](https://github.com/zilliztech/GPTCache)). The README itself concedes the codebase "is undergoing swift development," and the fundamental limitation is intrinsic: semantic caching "inherently produces false positives and negatives — cache hits may return slightly incorrect results, while similar queries might miss the cache entirely."

Redis's practitioner guidance quantifies the operating envelope ([Redis, 2026-01-20, updated 2026-06-01](https://redis.io/blog/what-is-semantic-caching/)): thresholds "commonly 0.85–0.95"; vector search adds **5–20 ms** while saving **1–5 s**; typical cost reduction "50% or more"; TTLs tiered by volatility (5–15 min prices/inventory, 1–4 h descriptions, 24 h FAQs/policies) plus content-triggered invalidation. Most important is their own false-positive guidance: start at **0.90–0.95** and monitor, and **if false positives exceed 3–5%, threshold tuning alone won't fix it — you need architectural changes.**

**A correctness hazard worth stating plainly.** A semantic cache in front of a RAG system caches *answers keyed by question embedding*, while the *corpus* changes underneath. The cache is therefore a second, independent staleness surface with its own invalidation logic, and TTL-based invalidation cannot see corpus updates at all. Any per-user personalization or ACL-dependent answer makes the shared cache an access-control violation waiting to happen — a cross-tenant cache hit is indistinguishable from a correct hit at the similarity layer. (This is the same class of defect as the caching-based leakage path identified in ConfusedPilot; see §11.)

### 11. Security: the retrieval channel is an untrusted input channel

This is the most consequential section for a next-generation framework, because every architectural choice above is also an attack surface.

#### 11.1 The foundational result: retrieved content is executable

**"Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection"** — Greshake, Abdelnabi, Mishra, Endres, Holz, Fritz — arXiv **2302.12173** — 2023. Attackers place instructions in data the system will later retrieve. Demonstrated data exfiltration, self-propagating "worming," and information-ecosystem contamination against real systems including Bing's GPT-4 Chat and code-completion tools. The central insight: **"LLM-Integrated Applications blur the line between data and instructions."** Their conclusion — that existing defences inadequately address this — has held for three years.

#### 11.2 Corpus integrity attacks

- **PoisonedRAG: Knowledge Corruption Attacks to RAG** — Zou, Geng, Wang, Jia — arXiv **2402.07867** —
  **USENIX Security 2025** (peer-reviewed). First knowledge-corruption attack on RAG; formulated as an
  optimization problem with black-box and white-box variants. **~90% attack success by injecting five
  malicious texts per target question into databases containing millions of documents.** Evaluated
  defences were found insufficient. The five-documents-in-millions ratio is the headline: **corpus
  poisoning is cheap and does not require corpus dominance.**
- **Machine Against the RAG: Jamming RAG with Blocker Documents** — Shafran, Schuster, Shmatikov —
  arXiv **2406.05870** — **USENIX Security 2025** (peer-reviewed). A **single** injected "blocker"
  document, when retrieved, causes the system to fail to answer a target query — either by looking
  irrelevant or by tripping safety refusal. Includes a black-box optimization method needing **no**
  knowledge of the embedding model or LLM, no instruction injection, and no auxiliary LM. Finding with
  direct product consequences: **"existing safety metrics for LLMs do not capture their vulnerability
  to jamming"** — i.e. availability attacks on RAG are invisible to the safety evals vendors run.

#### 11.3 Enterprise RAG as a confused deputy

**ConfusedPilot: Confused Deputy Risks in RAG-based LLMs** — RoyChowdhury, Luo, Sahu, Banerjee, Tiwari — arXiv **2408.04870** — 2024. Studies Microsoft-365-Copilot-class systems and demonstrates three chained problems: (1) prompt injection via malicious text in modified documents corrupting responses; (2) **data leakage by exploiting caching mechanisms during retrieval**; (3) chained enterprise-wide misinformation. They note "the security implications of adopting such RAG-based systems are unclear" and propose design guidelines. The caching-leakage vector is under-appreciated and directly relevant to §10.

#### 11.4 The shipped, patched, critical bug

**CVE-2025-32711** — Microsoft 365 Copilot — **AI command injection (CWE-74: Improper Neutralization of Special Elements in Output)** — allows "an unauthorized attacker to disclose information over a network." **Published 2025-06-11**, last modified 2026-06-17.

| Assessor | CVSS 3.1 | Vector |
|---|---|---|
| NIST/NVD | **7.5 HIGH** | `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` |
| Microsoft | **9.3 CRITICAL** | `AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N` |

Source: [NVD](https://nvd.nist.gov/vuln/detail/CVE-2025-32711). Note both vectors are **`PR:N/UI:N`** — no privileges, **no user interaction**. That is the formal statement of a *zero-click* attack against an enterprise RAG product. The scoring disagreement is itself notable: Microsoft assigns `S:C` (scope change) and `I:L`, producing 9.3; NVD assigns `S:U` and `I:N`, producing 7.5. The vendor rates its own bug 1.8 points *more* severe than NVD — an inversion of the usual pattern, and a sign that CVSS 3.1 does not model AI-mediated data flows well.

`[PARTIALLY VERIFIED: this CVE is widely associated with the "EchoLeak" research disclosure (Aim Labs) and with a "RAG spraying" technique for guaranteeing that a malicious email enters the retrieved set. The Aim Security blog URL now redirects to catonetworks.com and was not successfully fetched in this session; the mechanism description above is limited to what NVD states.]`

#### 11.5 The lethal trifecta

Simon Willison's framing ([2025-06-16](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)) is the most useful *architectural* security lens for retrieval-bearing agents. Three capabilities that are individually fine and jointly fatal:

1. **Access to private data** (via tools),
2. **Exposure to untrusted content** (attacker-controlled text or images),
3. **Ability to communicate externally** (an exfiltration channel).

"An attacker can easily trick an agent into accessing your private data and sending it to that attacker." He lists affected systems: Microsoft 365 Copilot, GitHub's official MCP server, GitLab Duo, Google Bard/NotebookLM/AI Studio, Amazon Q, Slack, and ChatGPT variants. The pattern recurs because "LLMs follow instructions in content" regardless of provenance.

The key operational claim, and the one most relevant to framework design: **guardrails are insufficient — "95% detection rates represent inadequate security standards," and the only reliable defence is avoiding the full trifecta.** Note that a *RAG system over enterprise documents with any outbound tool* satisfies all three legs by construction. This is not an implementation bug class; it is the default architecture.

#### 11.6 Principled defences and their measured cost

- **AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM
  Agents** — Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr — arXiv **2406.13352**.
  97 realistic agent tasks (email, e-banking, travel) and **629 security test cases**, designed as an
  extensible environment rather than a fixed suite so adaptive attacks can be evaluated. Findings cut
  both ways: SOTA LLMs "fail at many tasks (even in the absence of attacks), and existing prompt
  injection attacks break some security properties but not all." **The utility baseline is itself
  low**, which complicates every security-vs-utility claim measured on it.
- **Defeating Prompt Injections by Design (CaMeL)** — Debenedetti, Shumailov, Fan, Hayes, Carlini,
  Fabian, Kern, Shi, Terzis, Tramèr — arXiv **2503.18813** — 2025. Two mechanisms: **control-flow
  isolation** so that "the untrusted data retrieved by the LLM can never impact the program flow," and
  **capability-based access control** enforcing policies at tool-call time to block exfiltration. On
  AgentDojo: **77% of tasks solved with provable security vs 84% undefended** — a ~7-point utility tax
  for a provable guarantee. This is the most important number in the defensive literature for a
  systems paper: **principled injection resistance currently costs single-digit percentage points of
  utility, not half the system.**
- **Design Patterns for Securing LLM Agents against Prompt Injections** — Beurer-Kellner, Buesser,
  Creţu, Debenedetti, Dobos, Fabian, Fischer, Froelicher, Grosse, Naeff, Ozoani, Paverd, Tramèr,
  Volhejn — arXiv **2506.08837** — 2025. Proposes "a set of principled design patterns for building AI
  agents with provable resistance to prompt injection" with utility/security trade-off case studies.
  `[The individual pattern names were not recoverable from the abstract page fetched; the full PDF was
  not read in this session.]`

#### 11.7 The vector store is a confidentiality boundary, and a weak one

**Text Embeddings Reveal (Almost) As Much As Text** — Morris, Kuleshov, Shmatikov, Rush — arXiv **2310.06816** — **EMNLP 2023**. `vec2text` inverts dense embeddings via a multi-step method that "iteratively corrects and re-embeds text," recovering **92% of 32-token inputs exactly** from state-of-the-art embedding models, including full names from clinical notes.

Consequence for production architecture: **an embedding index is not a de-identified or lossy artifact and must be classified at the same sensitivity as the source text.** Every "we only store vectors, not your data" claim — common in code-indexing and managed-RAG marketing — is defeated by this result. `[NOT VERIFIED IN THIS SESSION: Cursor's specific indexing design (Merkle-tree sync, server-side chunk embeddings, obfuscated paths). Both docs.cursor.com and cursor.com/security fetches failed to return the relevant technical content; the security page covers SOC 2, infrastructure, disclosure, and Privacy Mode only.]`

#### 11.8 The standards view

**OWASP Top 10 for LLM Applications 2025** ([genai.owasp.org](https://genai.owasp.org/llm-top-10/)) now contains at least five RAG-relevant entries, which is itself evidence that retrieval has been recognized as a distinct security domain:

| ID | Entry | RAG relevance |
|---|---|---|
| LLM01:2025 | Prompt Injection | Direct + indirect via retrieved content |
| LLM02:2025 | Sensitive Information Disclosure | Over-retrieval, ACL failures, cache leakage |
| LLM04:2025 | Data and Model Poisoning | Explicitly covers **embedding** data, not just pretraining/fine-tuning |
| LLM07:2025 | System Prompt Leakage | Injected content can elicit the operator prompt |
| LLM08:2025 | **Vector and Embedding Weaknesses** | A top-10 entry dedicated to the RAG storage layer |
| LLM09:2025 | Misinformation | Grounding failure / poisoned-corpus outcome |

LLM08's existence is the single clearest signal that vector stores are now treated as first-class security components rather than infrastructure detail.

#### 11.9 The 2026 literature: attacks have moved past instruction injection, defences have moved into the retriever

A descending-date query of the arXiv API for abstracts containing both "retrieval-augmented generation" and "prompt injection" returns a dense 2026 literature. Three entries were individually verified by fetching their abstract pages; the rest are reported from the API listing and marked accordingly.

**Verified by direct fetch:**

- **SoK: The Attack Surface of Agentic AI — Tools, and Autonomy** — Dehghantanha & Homayoun — arXiv
  **2603.22928** — **2026-03-24**. Systematizes attacks on LLM+tools+RAG+autonomy systems: prompt
  injection, **knowledge-base poisoning**, tool exploits. Synthesizes 20+ studies from 2023–2025,
  proposes security metrics, evaluates input sanitization and sandboxing, and ships a deployment
  checklist. The existence of an SoK is itself the signal: retrieval security is now a mature enough
  subfield to systematize.
- **CleanBase: Detecting Malicious Documents in RAG Knowledge Databases** — Jin, Wang, Zou, Jia, Gong —
  arXiv **2605.00460** — **2026-05-01**. First-line *detection* rather than mitigation, exploiting the
  observation that "malicious documents crafted for the same attack-targeted questions often exhibit
  high semantic similarity": build a document similarity graph and flag **cliques** as likely
  poisoning. Includes theoretical error-rate analysis and public code. Note the shared authorship with
  PoisonedRAG (Zou, Jia) — the attack authors are building the detector.
  **Implicit limitation worth flagging: a clique signature only catches *multi-document* poisoning of
  the kind PoisonedRAG performs (5 docs per target question); it should be blind to single-document
  jamming attacks (Shafran et al.) by construction.**
- **SD-RAG: A Prompt-Injection-Resilient Framework for Selective Disclosure in Retrieval-Augmented
  Generation** — Al Masoud, Arazzi, Nocera — arXiv **2601.11199** — **2026-01-16**. The most directly
  framework-relevant defence in this set: it "decouples the enforcement of security and privacy
  constraints from the generation process itself," applying human-readable policy constraints over a
  graph-based data structure **during retrieval, before data reaches the LM**, for fine-grained access
  management. Reports ~**58% privacy improvement** over prompt-based approaches plus injection
  resistance. This is exactly the architectural move CaMeL makes for control flow, applied to
  *disclosure*: **enforce at the retriever, not in the prompt.**

**Also verified by direct fetch** (these four are load-bearing for the open problems below):

- **Salience Induction against Multi-Hop RAG Agents: Threat and Defense** — Zhou, Wang, Zhou, Xie, Zhou
  — arXiv **2607.17535** — **2026-07-20**. Identifies a **"salience channel"**: rather than injecting
  false information or instructions, the attack repositions facts, adjusts emphasis, and manipulates
  semantic framing to misdirect agent reasoning **while keeping every claim truthful** —
  "truth-preserving edits that redirect Multi-Hop attribute binding." Evaluated across five LLM families
  (GPT, Claude, Gemini, DeepSeek, Qwen) and three agent architectures: **83.3% ASR at a 30% edit
  budget**. Their own defence, Salience Normalization, brings ASR to **15.3%** (standard) and **23.6%**
  (adaptive). Ships SalientWiki-MH as a benchmark. **This is the most important attack result in this
  set: nothing in the corpus is false and nothing is an instruction, so both fact-checking and
  injection-detection defences are structurally inapplicable.**
- **Document-Authored Control-Signal Impersonation: A Low-Cost Indirect Prompt Attack on RAG Safety
  Boundaries** — Zhu — arXiv **2606.09005** — **2026-06-08**. Attacker-controlled text inside a
  retrieved document masquerades as **trusted metadata or policy signals**, exploiting the fact that RAG
  "blend[s] trusted and untrusted text into a single natural language prompt." Explicitly **not**
  imperative-command injection. Evaluated over six model configurations with varying susceptibility;
  the authors are careful that this is "behavioral evidence rather than proof of internal mechanisms"
  and call for independent evaluation. **Direct consequence: prompt-serialization format is a security
  interface, and no reviewed platform documents its chunk+metadata serialization.**
- **LogicPoison: Logical Attacks on Graph Retrieval-Augmented Generation** — Xiao, Chen, Zhang, Zhang,
  Zhou, Yang, Ren, Yang, Huang — arXiv **2604.02954** — **2026-04-03**. Uses **type-preserving entity
  swapping** to perturb "global logic hubs" and reasoning paths in the knowledge graph, keeping text
  plausible while corrupting logical connections; reported to bypass GraphRAG defences and degrade
  performance more stealthily than comparable attacks. Directly relevant to §4a: **systems relying on
  graph topology integrity have no surface-level content check that can detect this.**
- **A Layered Security Framework Against Prompt Injection in RAG-Based Chatbots** — Saleem, Ahmed,
  Zaman, Hassan — arXiv **2606.19660** — **2026-06-17**. Three-layer middleware (rule-based pattern
  library + fine-tuned semantic anomaly classifier on input; instruction hierarchy at context assembly;
  output audit) requiring no LLM modification. Reports **ASR 71.4% → 11.3%** with a **4.8% false
  positive rate** over 5,080 samples on GPT-4o, Llama 3, and Mistral 7B. **Read against Willison's
  standard, an 11.3% residual ASR with 4.8% FPR is not a security boundary — it is a nuisance filter.**

**Remaining rows from the arXiv API listing, NOT individually verified** `[IDs, titles and first authors as returned by the arXiv API; the API-returned date column was internally inconsistent for several rows, and the API-summarized numbers were not confirmed, so both are omitted here. Verify before citing in a paper.]`: 2603.25164 *PIDP-Attack: Prompt Injection + Database Poisoning* (Haozhen Wang) — compound attack, injection plus poisoning together; 2603.03919 *TabooRAG: Exploiting Alignment Homogeneity* (Junchen Li) — transfers jamming/blocking attacks across models via shared refusal criteria; 2603.18433 *Prompt Control-Flow Integrity (PCFI)* (Md Takrim Ul Alam) — priority-aware middleware defence; 2606.26627 *Agents That Know Too Much: Privacy in LLM Agents* (Nada Lahjouji) — data-centric privacy survey across RAG, memory, SQL, multi-agent; 2601.10923 *Hidden-in-Plain-Text: Social-Web Indirect Prompt Injection* (Haoze Guo) — benchmark for web-native RAG attacks across sparse and dense retrievers; 2602.06268 *MPIB: Medical Prompt Injection Benchmark* (Junhyeok Lee) — separates attack success from patient harm; 2606.15656 *Overcoming Impedance Mismatch: Foundation Models + Knowledge Graphs* (Sahil Rajesh Dhayalkar); 2606.26793 *MIRROR: Novelty-Constrained Memory-Guided MCTS Red-Teaming* (Inderjeet Singh).

**Three trends read off this set.** (1) **Attacks have become content-innocent.** Salience induction (83.3% ASR, all claims true) and DACSI (metadata impersonation, no imperatives) carry no false statement and no injected instruction, so defences that detect injected imperatives or verify facts are structurally inapplicable. (2) **GraphRAG extended rather than reduced the poisoning surface** (LogicPoison), precisely because graph topology is a second, unvalidated derived artifact (§4a, F13). (3) **The credible defences all move enforcement out of the prompt** — into control flow (CaMeL, 77% vs 84% utility), into the retriever with explicit policy (SD-RAG, ~58% privacy improvement), or into corpus-level detection (CleanBase) — while the best filtering-based defence still reports **11.3% residual ASR at 4.8% FPR**, and even the salience paper's own normalization defence leaves 15.3–23.6%.

---

## Comparison tables

### Table A — Managed retrieval platforms: what is exposed vs hidden

The most decision-relevant table in this document, and one no vendor publishes. "—" = not stated in the documentation fetched for this review.

| | **OpenAI file_search** | **Gemini File Search** | **Vertex AI RAG Engine** | **Bedrock Managed KB** | **Bedrock Customer-managed KB** | **Azure AI Search agentic retrieval** |
|---|---|---|---|---|---|---|
| Chunk size / overlap configurable | **Not documented** | Managed ("optimal chunking strategies") | Yes — explicit transform/chunk stage | Smart Parsing auto-selects per document type | Fully yours | Yours (index-time) |
| Embedding model choice | **Not documented** | `gemini-embedding-001` (fixed) | Yes | Service-managed by default, **overridable** | Yes | Yes |
| Reranker exposed | **Not documented / not mentioned** | — | — | Yes (service-managed, overridable) | You build it | **Yes — semantic L2 ranker, mandatory per subquery** |
| Query planning / decomposition | Model decides when to call the tool | — | — | **Yes** — agentic multi-hop, multi-KB, sufficiency evaluation | You build it | **Yes** — explicit `minimal`/`low`/`medium` reasoning-effort dial |
| Result-count control | `max_num_results` | — | — | — | — | Reasoning effort + source count + tier limits |
| Metadata filtering | Yes (`filters`, key-value) | — | — | Yes | Yes | Yes |
| ACL enforcement point | Not documented | Not documented | Not documented | **Retrieval time, document-level, all connectors except Web Crawler** | **Not available** | Retrieval time; remote sources predicated on user identity |
| Citations / provenance | File citations in message | **Built-in citations to used passages** | Grounded responses referencing sources | Citations supported | You build it | Optional source references **+ execution activity log** |
| Observability | `file_search_call` item with search metadata | — | — | **AgentCore Observability: retrieval traces, agentic traces, per-KB metrics** | You build it | **Activity log of queries issued, sources hit, parameters used** |
| Multi-modal | PDF/Office/code/text | Broad file types | — | Images extracted & retrieved; image-as-query; text+image queries; audio/video/scanned | You build it | — |
| Pricing unit | **$2.50 / 1k tool calls + $0.10 / GB-day (1 GB free)** | **$0.15 / 1M index-time tokens**; storage & query embeddings free | Managed Spanner instance billing in GA regions | — | Your infra | **Retrieval tokens (search) + planning/synthesis tokens (AOAI)**; free monthly token allowance |
| Notable hard constraint | Rate limits 100–1000 RPM by tier | — | **Data residency NOT supported**; regional allowlist for us-central1/us-east1/us-east4 | Managed-tier lock-in for ACLs & connectors | **No third-party connectors, no doc-level permissions, no AgentCore Gateway** | GA/preview split across `2026-04-01` / `2026-05-01-preview`; portal is preview-only |

**Two further platforms, for contrast.** *Amazon Kendra* (closed to new customers) placed the whole pipeline behind a provisioned index with semantic ranking, offered its ranker separately as **Kendra Intelligent Ranking** over other engines' results, filtered results by user/group access while making the customer responsible for authn/authz, and billed for provisioned indexes **even when empty and unqueried**. *Elastic* sits at the opposite pole: `semantic_text` makes chunking a **declarative mapping setting** (`chunking_settings`: `strategy`, `max_chunk_size`, `overlap`), inference runs at ingest with "sensible defaults," ELSER provides sparse retrieval, and the docs advise pinning `inference_id` in production to avoid embedding-model inconsistency. Elastic is the only reviewed platform where chunking and embedding-model identity are both explicit, versionable schema.

**Two findings fall out of Table A.**

1. **Disclosure asymmetry is a procurement and science problem.** Azure documents every pipeline stage
   and emits an activity log; Bedrock documents its parsing, reranking, and permission model; OpenAI
   documents neither chunking nor reranking. An application cannot be tuned against a pipeline it
   cannot see, a regression cannot be attributed, and a published eval against `file_search` is not
   reproducible at a later date.
2. **Pricing units are mutually non-convertible.** $/1k tool calls, $/1M index-time tokens,
   $/GB-day, retrieval tokens with a reasoning-effort multiplier, and managed-database instance hours
   cannot be normalized without knowing per-vendor internal chunking and fan-out — which is exactly
   what the opaque vendors do not disclose. **Cross-vendor cost modeling of retrieval is structurally
   impossible in mid-2026**, and that is an open problem, not a table footnote.

### Table B — Where "intelligence" sits, by architecture

| Architecture | Index-time work | Query-time work | Dominant cost | Dominant failure mode |
|---|---|---|---|---|
| Frozen RAG (Stage 0) | Fixed-size chunk + embed | Top-k cosine | Storage, cheap | Context-free chunks; demo-to-prod cliff |
| Contextual retrieval (Stage 1) | **LLM per chunk** ($1.02/M tokens) + BM25 index | Hybrid + rerank | Index build | Reindex cost on corpus churn |
| Query-side heavy (Stage 2) | Standard | **LLM query expansion, 50→15 rerank** | Per-query LLM + rerank | Latency; fan-out cost; routing errors |
| Managed platform (Stage 3) | Vendor's | Vendor's | Opaque, per-call or per-token | Cannot debug, cannot reproduce |
| Agentic retrieval (Stage 4) | Standard | **Plan → parallel subqueries → rerank → sufficiency → iterate** | **Tokens: 4×–15× chat** | Cost/latency blowup; non-determinism |
| Filesystem/context engineering (Stage 5) | **None** | grep/glob/read + progressive disclosure + memory files | Tokens + tool round-trips | Doesn't scale to unstructured/non-lexical corpora; no ACL layer by default |

### Table C — Retrieval security surface by attack objective

| Objective | Mechanism | Representative source | Peer-reviewed? |
|---|---|---|---|
| **Integrity** — control the answer | Corpus poisoning; 5 docs per target question in a millions-document corpus, ~90% ASR | PoisonedRAG, arXiv 2402.07867 | **USENIX Sec 2025** |
| **Availability** — deny the answer | Single "blocker" document causes refusal/irrelevance; black-box, no model knowledge needed | Machine Against the RAG, arXiv 2406.05870 | **USENIX Sec 2025** |
| **Confidentiality** — exfiltrate private data | Indirect prompt injection + outbound channel (lethal trifecta) | arXiv 2302.12173; Willison 2025-06-16; CVE-2025-32711 (`PR:N/UI:N`) | Mixed: 2302.12173 preprint→widely cited; CVE is vendor-confirmed |
| **Confidentiality** — cross-user leakage | Retrieval **cache** exploitation; confused-deputy over enterprise ACLs | ConfusedPilot, arXiv 2408.04870 | Preprint |
| **Confidentiality** — leak from the index itself | Embedding inversion; 92% exact recovery of 32-token inputs | vec2text, arXiv 2310.06816 | **EMNLP 2023** |
| **Ecosystem** — propagate | Self-propagating "worming" through retrievable content | arXiv 2302.12173 | Preprint |

---

## Failure modes & critiques

### F1. Chunking is per-corpus engineering that nobody has abstracted

The 5M-document report is unambiguous: chunking "consumed the most development time," custom approaches were "necessary for each enterprise," and the requirement is logical units that never truncate mid-sentence. Anthropic's contextual retrieval is best read as an admission that the chunk abstraction is broken — it *repairs* chunks with a per-chunk LLM call rather than chunking better. Meanwhile GroundX's pitch (whatever one makes of its numbers) is to abandon chunks for semantic "objects" plus a vision model. **Three independent parties in three years all concluded the fixed chunk is the wrong unit, and no shared replacement exists.**

### F2. The demo-to-production cliff is the modal industry experience

Prototype on 100 docs looks fine; production on millions is "subpar and only the end users could tell." Two compounding problems: the evaluation set is drawn from the prototype corpus, and the failure is *silent* — a wrong-but-fluent grounded answer has no error signal. This is the strongest practical argument for provenance-first design: without per-claim attribution, RAG failures are undetectable in production by construction.

### F3. Agentic retrieval trades a cost problem for a worse cost problem

Anthropic's own numbers: 4× tokens for single agents, 15× for multi-agent, with token usage explaining 80% of performance variance. Microsoft's own guidance: reduce knowledge sources, lower reasoning effort, curate summaries. Both vendors, having shipped agentic retrieval, immediately advise customers to spend less on it. The uncomfortable reading: **agentic retrieval buys accuracy with tokens at a poor exchange rate, and its cost is superlinear in the number of connected sources** (fan-out × rerank window × subqueries).

### F4. Non-determinism destroys both eval and audit

Microsoft states outright that "precise reconstruction of a query or response isn't guaranteed," citing public-web sources and identity-predicated remote sources. Combine that with LLM query planning (stochastic), parallel subquery merging (order-sensitive), semantic caching (time-dependent), and platform-side chunker/ranker changes (silent), and a retrieval answer becomes **irreproducible in principle**. This breaks: A/B attribution, regression testing, incident forensics, and regulatory audit. No vendor in this review offers a "replay this exact retrieval" primitive; Azure's activity log is the closest and it is explicitly best-effort.

### F5. Eval drift and the metric-gaming trap

Vectara's leaderboard is honest that its metric is gameable by extractive copying. That generalizes: groundedness metrics reward quotation, production users want synthesis, so **the shipped metric and the shipped goal diverge**. Meanwhile GroundX's 97.83%-vs-44.57% study demonstrates the other half of the problem: vendor-designed benchmarks with vendor-chosen corpora and vendor-configured baselines are the primary public evidence base for managed RAG quality. There is no neutral, corpus-diverse, regularly-refreshed production RAG benchmark in this landscape.

### F6. Permissions are the hardest part and are treated as a tier feature

Bedrock provides document-level ACL filtering only on the Managed tier; Customer-managed KBs get none. Azure's remote knowledge sources are identity-predicated, which is correct but is also the source of its non-reproducibility admission. Neither vendor documents behaviour under the two classic hazards:

- **Post-filter starvation** — if ACL filtering happens *after* top-k, a low-privilege user's
  candidate list can be emptied, silently degrading recall rather than erroring. (Uncertain: no vendor
  doc fetched here states whether filtering is pre- or post-ranking.)
- **Stale ACL window** — permission revocation must propagate to the index at least as fast as content
  changes. No vendor in this review documents an ACL-propagation SLA.

ConfusedPilot's finding that retrieval **caching** leaks data is the third hazard and the least discussed.

### F7. The lethal trifecta is the default RAG architecture

Private data + untrusted retrieved content + any outbound tool = exploitable. An enterprise RAG assistant with a connector fleet and an email/webhook/MCP tool satisfies all three. Willison's claim that 95% guardrail detection is an inadequate security standard is the correct framing for a security-critical system: probabilistic filters do not compose into a boundary. CaMeL's 77%-vs-84% result shows the alternative — actual isolation and capability enforcement — is affordable, which makes the continued reliance on classifier-based injection filtering a choice rather than a necessity.

### F8. "We only store embeddings" is not a privacy control

vec2text recovers 92% of 32-token inputs exactly. Any architecture whose privacy story rests on storing vectors instead of text is misclassified. This has direct consequences for multi-tenant vector stores, code-indexing products, and cross-region embedding replication (embeddings crossing a border is text crossing a border).

### F9. Semantic caching introduces a second staleness surface and an ACL bypass

TTL-based invalidation cannot observe corpus changes; content-triggered invalidation requires a dependency map from cached answers to source documents that no reviewed product provides. Redis's own threshold guidance (start 0.90–0.95; >3–5% false positives means architecture, not tuning) quantifies the accuracy floor. And a shared semantic cache over ACL-dependent answers is a cross-tenant leak by similarity — the cache layer has no notion of principal unless explicitly keyed by one.

### F10. The "RAG is dead" claim — and the disagreement about it

The *RAG Obituary* thesis (agents + long context supersede chunk-and-embed retrieval) reached broad practitioner attention (HN item `45439997`: **290 points, 179 comments, 2025-10-01**). It is partly corroborated by primary sources in this review: Anthropic advises skipping RAG below ~200k tokens, ships filesystem-search agents and progressive disclosure, and reports large gains from context management over static retrieval.

But the same primary sources contradict the strong form:

- Anthropic shipped **contextual retrieval** and reports that **reranking** still cuts failures a
  further 34% relative — hybrid indexed retrieval was not abandoned.
- Every hyperscaler shipped or expanded a **managed vector-store** product in 2025–2026; Google
  launched File Search on **2025-11-06**, *after* the obituary.
- Azure's agentic retrieval is *built on* semantic reranking over a search index — the agentic layer
  sits **above** the index, it does not replace it.
- Filesystem/grep search presumes a lexically searchable, locally-mounted, permission-uniform corpus.
  Enterprise retrieval over SharePoint/Confluence/Slack/Drive with per-document ACLs and multimodal
  scanned PDFs satisfies none of those.
- Long-context economics are unfavourable at corpus scale: Contextual AI claims its trained system
  beats long-context models "using less compute on larger haystacks (2K–2M tokens)" (vendor claim);
  Anthropic's 15× token multiplier prices the alternative.

**Honest synthesis: the unit of retrieval is being renegotiated, not eliminated.** What is dying is *fixed-size chunk + single-shot top-k + no reranking*. What is growing is *hierarchical, navigable, tool-mediated, budget-aware retrieval over indexes that still exist underneath.* Sources genuinely disagree on how much index remains; the vendor actions (all of them shipping indexes) are better evidence than the essays.

### F11. Retrieval-time compression is now the real product, and it is lossy without accounting

Exa sells "10× more token-efficient" highlights; Parallel sells objective-conditioned Extract; Tavily sells context-window-optimized results; Anthropic's subagents "compress findings before returning"; context editing deletes tool results outright (−84% tokens). Every one of these discards evidence before the answering model sees it, and **none of the reviewed systems reports what was discarded or lets a downstream verifier recover it.** Compression is currently un-audited lossy transformation inside the provenance chain.

### F12. Breadth and depth are rationed against each other, and reranking has a hard throughput ceiling

Azure's published quotas make explicit what is implicit everywhere else: `minimal` reasoning effort allows **10** knowledge sources per knowledge base, `low` allows **3**, `medium` allows **5**. You cannot have both deep query planning and broad source coverage on the same knowledge base. Separately, the semantic ranker — invoked once per subquery, mandatorily — permits only **2–4 concurrent requests per search unit** with a **4–8 request queue**, rejecting beyond that. With ~3 subqueries per plan, agentic retrieval throughput is bounded by roughly *ranker concurrency ÷ fan-out*, and is additionally subject to "total available semantic ranker capacity in the region." Meanwhile the minimum indexer schedule is **5 minutes**, which is the platform's floor on pull-mode index freshness. None of these numbers appear in the agentic-retrieval overview; all three are decisive for a production design.

The generalization: **agentic retrieval's cost is not merely token cost, it is a three-way constraint between fan-out, rerank throughput, and freshness**, and no current framework represents that constraint explicitly.

### F13. Derived artifacts (graphs, contextualized chunks, caches) have lifecycles nobody manages

Bedrock GraphRAG is the cleanest illustration: the graph is built by a chosen foundation model whose extraction schema you cannot configure, cannot autoscale, is orphaned (and still billed) when the knowledge base is deleted, silently drops parent context when combined with hierarchical chunking, and becomes unreproducible when its construction model reaches end-of-life. The same class of problem applies to Anthropic-style contextualized chunks (regenerated by which model version?), semantic caches (invalidated by what dependency map?), and embeddings (Elastic's own guidance is to **pin `inference_id` in production to avoid model inconsistencies**). Every RAG system in production is a pipeline of derived artifacts with **no versioning, no lineage, and no rebuild determinism**.

### F14. MCP solved connector plumbing and thereby industrialized the injection surface

MCP's value proposition is explicitly N×M reduction. The security consequence is symmetric: a standard that makes it trivial to attach any data source to any agent makes it trivial to attach attacker-influenced data sources. Willison's affected-systems list includes **GitHub's official MCP server**. Connector *quantity* is now the dominant variable in both cost (fan-out, per Microsoft's own advice) and risk (trifecta leg 2). No reviewed platform exposes a per-source **trust level** that propagates into retrieval or tool-gating decisions.

---

## Open problems

Framed as first-principles gaps a new framework could address. Each is grounded in a specific observation above.

**O1. A reproducible-retrieval primitive.** Nothing in production offers "replay this retrieval exactly." Requirements: content-addressed corpus snapshots, pinned chunker/embedder/ranker versions, recorded query plans and merge order, and identity-scoped candidate sets recorded per principal. Microsoft's activity log is the closest existing artifact and is explicitly best-effort (F4).

**O2. Cost/latency/throughput as a declared contract rather than an emergent property.** Exa already exposes six latency tiers; Azure exposes a three-level reasoning-effort dial *and* rations knowledge sources against it (10/3/5 for minimal/low/medium); Anthropic measures 4×/15× token multipliers. Nobody lets a caller state a *budget* ("answer in ≤800 ms and ≤4k retrieved tokens, best effort") and have the planner, fan-out, rerank window, and iteration count solved against it. The framework-level object is a **retrieval budget allocator over a three-way constraint (fan-out × rerank throughput × freshness)**, not a top-k parameter (F3, F12, §10).

**O3. A trust-labelled corpus with propagation into tool gating.** Retrieved content should carry a provenance and trust label that (a) survives compression and summarization, (b) constrains which tools may be invoked after it enters context, and (c) is enforced structurally, not by a classifier. CaMeL shows capability enforcement costs ~7 utility points (77% vs 84%); the design patterns paper argues the same. Today no platform in Table A exposes per-source trust (F7, F14). The 2026 literature sharpens the requirement: **salience-induction and metadata-impersonation attacks contain no malicious instruction at all** (arXiv 2607.17535, 2606.09005), so a label must attach to the *source*, not be inferred from the *content*.

**O4. Access control as part of the retrieval algebra, not a filter bolted on.** Open sub-questions: pre- vs post-ranking filtering (and what recall guarantee a low-privilege user gets), ACL propagation SLA relative to content freshness, per-principal cache keying, and whether the answer itself needs an access-control label. Note the perverse incentive to fix: Bedrock ties document-level ACLs to the managed tier, so the most regulated customers lose them (F6); Kendra's formulation — the platform filters but "customers are responsible for authenticating and authorizing user access" — locates the bug class precisely at that seam. **SD-RAG (arXiv 2601.11199) is the closest existing prior art**: human-readable policy over a graph structure, enforced *during retrieval before data reaches the LM*, reporting ~58% privacy improvement over prompt-based enforcement. A framework should treat that as the baseline, not the frontier.

**O5. Poisoning resistance as an index property.** PoisonedRAG achieves ~90% ASR with **five** documents against millions, and evaluated defences failed. That means top-k similarity retrieval has no notion of *corroboration*. Candidate directions: require k independent sources for a claim, weight by source reputation, detect anomalous embedding clusters near frequent queries, and treat single-source claims as lower-confidence by construction. **CleanBase (arXiv 2605.00460) is the first serious detector** — similarity-graph cliques flag co-crafted malicious documents — but by construction it should be blind to the single-document jamming case, and **safety metrics do not currently detect jamming at all** (§11.2). GraphRAG raises the stakes rather than lowering them: LogicPoison (arXiv 2604.02954) corrupts graph topology to reroute reasoning while remaining textually plausible, so the derived graph needs its own integrity check.

**O6. Auditable compression.** Every production system compresses before answering (F11). A framework should make compression a recorded, reversible-by-reference transformation: what was dropped, by what policy, recoverable by a verifier. Anthropic's context editing (−84% tokens) and subagent compression are the highest-value places to instrument.

**O7. The right unit of retrieval.** Three independent parties concluded the fixed chunk is wrong (F1). Candidates visible in production: the LLM-contextualized chunk (Anthropic), the parsed semantic object (GroundX), the summary index alongside vector+keyword (Ragie), the document hierarchy navigated by progressive disclosure (Skills), and the raw file traversed by grep (Claude Code). Nobody has a principled account of when each applies. A framework that can *hold several units at once and route between them* matches the observed practice better than any single unit.

**O8. Comparable cost semantics across retrieval providers.** Table A's pricing row shows five mutually non-convertible units. Without a normalizing abstraction (e.g. cost per retrieved *useful* token, or per grounded claim), teams cannot make build-vs-buy or multi-vendor decisions, and papers cannot report efficiency comparably.

**O9. Query-side intelligence deserves first-class status.** Practitioners rank LLM query generation as the #1 ROI intervention (caveat in Stage 2: the academic ablations rank naive multi-query *negative* — the production win depends on keyword+semantic variety plus a downstream reranker) and Azure ships planning as a managed stage, yet frameworks still model retrieval as `retrieve(query, k)`. The right interface is closer to `retrieve(intent, budget, principal, trust_policy) -> evidence_set + plan_trace` (Stage 2, F4).

**O10. Staleness as a modelled property, not a cron job.** Google's index-time-only pricing rewards never reindexing; contextual retrieval makes reindexing cost real ($1.02/M tokens); semantic caches add a second staleness surface with no dependency map; ACL changes are a third. A framework needs a unified freshness model spanning content, derived context, cached answers, and permissions (§3, F9, F6).

**O11. A neutral production-RAG benchmark with adversarial and permission dimensions.** The public evidence base is vendor-run studies (GroundX, Parallel, Contextual AI) plus a self-described gameable summarization leaderboard (Vectara) plus an agent benchmark with a low clean baseline (AgentDojo: utility is already poor before attacks). A benchmark that jointly measures grounded accuracy, poisoning/jamming resistance, ACL correctness, cost, and latency does not exist (F5).

**O12. Lineage and rebuild determinism for derived retrieval artifacts.** Contextualized chunks, knowledge graphs, embeddings, and semantic caches are all *derived* from source content by a specific model version under a specific configuration, and none of the reviewed platforms versions them. Bedrock warns that graph-construction models reach end-of-life; Elastic tells you to pin `inference_id` "to avoid model inconsistencies"; Bedrock GraphRAG orphans and keeps billing a Neptune graph after the knowledge base is deleted. A framework needs: content-addressed inputs, pinned extractor/embedder versions, recorded configuration, an explicit dependency graph from derived artifact → sources, and a defined rebuild semantics when a producing model is deprecated (F13).

**O13. Retrieval architecture must survive the disappearance of the standalone index.** Kendra's closure to new customers, and its provisioned-index billing being replaced by consumption pricing, indicate that retrieval is being absorbed into model platforms. A framework whose central abstraction is "our index" is designing against the market; one whose central abstraction is "a policy-governed, budgeted evidence-acquisition interface over heterogeneous providers" is designing with it (§6a, Table A).

**O14. Silent-failure detection.** F2's core problem is that a fluent wrong grounded answer emits no error. Per-claim attribution with confidence, sufficiency signalling ("the corpus does not contain this"), and abstention as a first-class output are all partially present in products (Gemini's passage-level citations, Bedrock's sufficiency evaluation, Contextual AI's inline-citation GLM) but never composed into an end-to-end guarantee.

---

## Bibliography

All entries below were fetched during this session unless annotated otherwise.

**Vendor engineering / product documentation**

1. Anthropic — *Introducing Contextual Retrieval* (2024-09). https://www.anthropic.com/news/contextual-retrieval
2. Anthropic — *Introducing the Model Context Protocol* (2024-11-25). https://www.anthropic.com/news/model-context-protocol
3. Anthropic — *How we built our multi-agent research system* (2025). https://www.anthropic.com/engineering/multi-agent-research-system
4. Anthropic — *Equipping agents for the real world with Agent Skills*. https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
5. Claude platform blog — *Context management: memory tool and context editing*. https://claude.com/blog/context-management
6. OpenAI — *File search* guide, Responses API. https://developers.openai.com/api/docs/guides/tools-file-search
7. OpenAI — *API pricing* (file_search $2.50/1k calls, $0.10/GB-day; web search $10–25/1k calls). https://developers.openai.com/api/docs/pricing
8. Google — *Introducing the File Search Tool in the Gemini API* (2025-11-06). https://blog.google/technology/developers/file-search-gemini-api/
9. Google Cloud — *Vertex AI RAG Engine overview*. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview
10. AWS — *Retrieve data and generate AI responses with Amazon Bedrock Knowledge Bases*. https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
10a. AWS — *Build a knowledge base with Amazon Neptune Analytics graphs* (Bedrock GraphRAG limitations). https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html
10b. AWS — *What is Amazon Kendra?* (states Kendra "is no longer open to new customers"). https://docs.aws.amazon.com/kendra/latest/dg/what-is-kendra.html
11. Microsoft — *Agentic retrieval overview, Azure AI Search* (doc date 2026-06-02, updated 2026-07-02). https://learn.microsoft.com/en-us/azure/search/search-agentic-retrieval-concept
11a. Microsoft — *Service limits for tiers and SKUs, Azure AI Search* (doc date 2026-08-04, updated 2026-08-05; agentic-retrieval limits, semantic-ranker throttling, vector quotas). https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity
11b. Elastic — *Semantic search with semantic_text*. https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text
11c. Elastic — *`semantic_text` mapping reference* (`chunking_settings`: strategy / max_chunk_size / overlap). https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/semantic-text
11d. Glean — documentation home (product surface only; no architecture detail). https://docs.glean.com/
12. Exa — *API getting started / reference*. https://exa.ai/docs/reference/getting-started
13. Tavily — *About Tavily*. https://docs.tavily.com/documentation/about
14. Parallel — *Parallel Search API* (vendor benchmark claims). https://parallel.ai/blog/parallel-search-api
15. Firecrawl — GitHub repository README (161k stars, AGPL-3.0). https://github.com/firecrawl/firecrawl
16. Contextual AI — *Introducing RAG 2.0*. https://contextual.ai/introducing-rag2/
17. Contextual AI — *Introducing the Grounded Language Model* (2025-03-04). https://contextual.ai/blog/introducing-grounded-language-model/
18. EyeLevel / GroundX — *The most accurate RAG* (vendor-run study: 97.83% / 64.13% / 44.57%). https://www.eyelevel.ai/post/most-accurate-rag
19. Ragie — product site (managed RAG, summary index, MCP server, SOC 2 / GDPR / HIPAA). https://www.ragie.ai/
20. Vectara — *Hallucination leaderboard* (HHEM-2.3; snapshot May 2026). https://github.com/vectara/hallucination-leaderboard
21. Zilliz — *GPTCache* (semantic caching; 8.1k stars). https://github.com/zilliztech/GPTCache
22. Redis — *What is semantic caching?* (2026-01-20, updated 2026-06-01). https://redis.io/blog/what-is-semantic-caching/

**Practitioner writing and discourse**

23. Abdellatif — *Production RAG: what I learned from processing 5M+ documents* (HN 45645349: 551 points, 114 comments, 2025-10-20). https://blog.abdellatif.io/production-rag-processing-5m-documents
24. Bustamante — *The RAG Obituary: Killed by agents, buried by context windows* (HN item 45439997: 290 points, 179 comments, 2025-10-01). https://www.nicolasbustamante.com/p/the-rag-obituary-killed-by-agents — *page 404'd on every fetch attempt in this session; cited via HN metadata only.*
25. Willison — *The lethal trifecta for AI agents* (2025-06-16). https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
26. Hacker News Algolia API queries used for discourse metadata. https://hn.algolia.com/api/v1/search

**Security research (peer-reviewed where noted)**

27. Greshake, Abdelnabi, Mishra, Endres, Holz, Fritz — *Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection* — arXiv:2302.12173 (2023). https://arxiv.org/abs/2302.12173
28. Zou, Geng, Wang, Jia — *PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models* — arXiv:2402.07867 — **USENIX Security 2025**. https://arxiv.org/abs/2402.07867
29. Shafran, Schuster, Shmatikov — *Machine Against the RAG: Jamming Retrieval-Augmented Generation with Blocker Documents* — arXiv:2406.05870 — **USENIX Security 2025**. https://arxiv.org/abs/2406.05870
30. RoyChowdhury, Luo, Sahu, Banerjee, Tiwari — *ConfusedPilot: Confused Deputy Risks in RAG-based LLMs* — arXiv:2408.04870 (2024). https://arxiv.org/abs/2408.04870
31. Morris, Kuleshov, Shmatikov, Rush — *Text Embeddings Reveal (Almost) As Much As Text* — arXiv:2310.06816 — **EMNLP 2023**. https://arxiv.org/abs/2310.06816
32. Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr — *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents* — arXiv:2406.13352. https://arxiv.org/abs/2406.13352
33. Debenedetti, Shumailov, Fan, Hayes, Carlini, Fabian, Kern, Shi, Terzis, Tramèr — *Defeating Prompt Injections by Design* (CaMeL) — arXiv:2503.18813 (2025). https://arxiv.org/abs/2503.18813
34. Beurer-Kellner, Buesser, Creţu, Debenedetti, Dobos, Fabian, Fischer, Froelicher, Grosse, Naeff, Ozoani, Paverd, Tramèr, Volhejn — *Design Patterns for Securing LLM Agents against Prompt Injections* — arXiv:2506.08837 (2025). https://arxiv.org/abs/2506.08837
35. NVD — *CVE-2025-32711* (Microsoft 365 Copilot AI command injection, CWE-74; NVD 7.5 HIGH / Microsoft 9.3 CRITICAL; published 2025-06-11). https://nvd.nist.gov/vuln/detail/CVE-2025-32711
36. OWASP GenAI Security Project — *OWASP Top 10 for LLM Applications 2025*. https://genai.owasp.org/llm-top-10/

**2026 security literature — individually verified by fetching the abstract page**

37. Dehghantanha & Homayoun — *SoK: The Attack Surface of Agentic AI — Tools, and Autonomy* — arXiv:2603.22928 (2026-03-24). https://arxiv.org/abs/2603.22928
38. Jin, Wang, Zou, Jia, Gong — *CleanBase: Detecting Malicious Documents in RAG Knowledge Databases* — arXiv:2605.00460 (2026-05-01). https://arxiv.org/abs/2605.00460
39. Al Masoud, Arazzi, Nocera — *SD-RAG: A Prompt-Injection-Resilient Framework for Selective Disclosure in Retrieval-Augmented Generation* — arXiv:2601.11199 (2026-01-16). https://arxiv.org/abs/2601.11199
40. Zhou, Wang, Zhou, Xie, Zhou — *Salience Induction against Multi-Hop RAG Agents: Threat and Defense* — arXiv:2607.17535 (2026-07-20). https://arxiv.org/abs/2607.17535
41. Zhu — *Document-Authored Control-Signal Impersonation: A Low-Cost Indirect Prompt Attack on RAG Safety Boundaries* — arXiv:2606.09005 (2026-06-08). https://arxiv.org/abs/2606.09005
42. Xiao, Chen, Zhang, Zhang, Zhou, Yang, Ren, Yang, Huang — *LogicPoison: Logical Attacks on Graph Retrieval-Augmented Generation* — arXiv:2604.02954 (2026-04-03). https://arxiv.org/abs/2604.02954
43. Saleem, Ahmed, Zaman, Hassan — *A Layered Security Framework Against Prompt Injection in RAG-Based Chatbots* — arXiv:2606.19660 (2026-06-17). https://arxiv.org/abs/2606.19660

**2026 security literature — from the arXiv API listing, IDs/titles/first authors as returned, NOT individually verified.** The API-returned date column was internally inconsistent for several rows and the API-summarized numbers were not confirmed; verify each before citing. Query used: `http://export.arxiv.org/api/query?search_query=abs:"retrieval-augmented generation" AND abs:"prompt injection"&max_results=20&sortBy=submittedDate&sortOrder=descending`

44. Wang — *PIDP-Attack: Prompt Injection + Database Poisoning* — arXiv:2603.25164
45. Li — *TabooRAG: Exploiting Alignment Homogeneity* — arXiv:2603.03919
46. Alam — *Prompt Control-Flow Integrity (PCFI)* — arXiv:2603.18433
47. Lahjouji — *Agents That Know Too Much: Privacy in LLM Agents* — arXiv:2606.26627
48. Guo — *Hidden-in-Plain-Text: Social-Web Indirect Prompt Injection* — arXiv:2601.10923
49. Lee — *MPIB: Medical Prompt Injection Benchmark* — arXiv:2602.06268
50. Dhayalkar — *Overcoming Impedance Mismatch: Foundation Models + Knowledge Graphs* — arXiv:2606.15656
51. Singh — *MIRROR: Novelty-Constrained Memory-Guided MCTS Red-Teaming* — arXiv:2606.26793

**Total distinct sources catalogued: 57** (22 vendor/product + 5 supplementary vendor docs numbered 10a–11d + 4 practitioner/discourse + 10 pre-2026 security + 7 verified 2026 security + 8 listed-but-unverified 2026 security, minus overlap in numbering).

**Explicitly not verified in this session** (fetches returned 404/403 or lacked the relevant content; no claims about these were made from memory):

- **Glean's retrieval architecture and permissions model** — five URL attempts failed; the docs
  homepage confirms only the product surface. Largest remaining gap.
- **Elastic's RRF hybrid ranking and ELSER quality numbers**, and the *default* `semantic_text`
  chunking values (the 120/40 figures seen are from an example, not documented defaults).
- **ChatGPT memory and ChatGPT connectors** — openai.com/index/* and help.openai.com both returned
  HTTP 403. `developers.openai.com` works; consumer-product pages do not.
- **Cursor codebase-indexing internals** (Merkle-tree sync, server-side chunk embeddings, path
  obfuscation) — docs redirect to a landing page; the security page covers only SOC 2, infrastructure,
  disclosure, and Privacy Mode.
- **Aim Labs' EchoLeak writeup** — aim.security now redirects to catonetworks.com. The CVE-2025-32711
  material here comes from NVD only; the "RAG spraying" mechanism is marked PARTIALLY VERIFIED.
- **The RAG Obituary essay text** — 404 on three URL variants; cited via HN metadata only. The HN
  comment thread (item 45439997) could not be retrieved either (Algolia items endpoint returned 403),
  so no practitioner counter-arguments are quoted; the rebuttal in F10 is constructed from primary
  vendor sources instead.
- **Bedrock GraphRAG launch blog** (404) — superseded by the user-guide page, which is better sourcing
  anyway.

**Method note.** WebSearch was unavailable for this session (budget exhausted at start). Sourcing used direct fetches of primary pages plus two JSON APIs: the arXiv API (`export.arxiv.org/api/query`) and Hacker News Algolia search (`hn.algolia.com/api/v1/search`). A follow-up pass with working search should prioritize, in order: Glean architecture/permissions, Elastic hybrid ranking, ChatGPT memory & connectors mechanics, the EchoLeak/"RAG spraying" mechanism, and practitioner counter-arguments from the RAG-Obituary HN thread.
