# Retrieval Inside Agent Frameworks
### OpenAI Agents SDK · Claude Agent SDK/MCP · CrewAI · AutoGen/AG2 · Semantic Kernel · Google ADK · smolagents · Letta · Mastra · Pydantic AI

> Autopsy scope: not standalone RAG frameworks, but how the 2024–2026 generation of *agent* frameworks
> models retrieval and memory — and what breaks. The dominant pattern shift of this period:
> **retrieval-as-tool + memory-as-service** displacing framework-owned RAG pipelines, with agentic
> (just-in-time) search increasingly displacing pre-built embedding indexes.
>
> Research date: 2026-08-05. Session WebSearch budget was exhausted at start; evidence was gathered via
> the GitHub API/`gh` CLI (issues, source code, READMEs), WebFetch of official docs and engineering
> blogs, and the HN Algolia API. All GitHub issue numbers below were verified against live trackers.

---

## Identity & adoption (as of 2026-08-05, via GitHub API)

| Framework | Maintainer / backing | License | Stars | Open issues | Last push | Retrieval/memory posture |
|---|---|---|---|---|---|---|
| OpenAI Agents SDK (`openai-agents-python`) | OpenAI | MIT | 28,401 | 24 | 2026-08-05 | Hosted `FileSearchTool` → managed Vector Stores; Sessions for turn memory |
| Claude Agent SDK + MCP | Anthropic | MIT (SDK) | 7,806 (py SDK); 89,233 (`modelcontextprotocol/servers`) | 414 / 491 | 2026-08-04 | No embedded RAG: agentic grep/filesystem search, Skills progressive disclosure, file-based memory tool, MCP retrieval servers |
| CrewAI | CrewAI Inc. ($18M Series A, Insight Partners, 2024) | MIT | 56,649 | 760 | 2026-08-05 | Framework-owned: `Knowledge` sources + `memory=True` RAG over ChromaDB |
| AutoGen | Microsoft Research | CC-BY-4.0 | 60,247 | 976 | **2026-04-15 (frozen)** | 0.2 `RetrieveChat` + Teachability; 0.4 `Memory` protocol; superseded by MS Agent Framework |
| AG2 (community AutoGen fork) | ag2ai | Apache-2.0 | 4,832 | 30 | 2026-08-05 | Inherited RetrieveChat lineage from AutoGen 0.2 |
| Semantic Kernel (+ Kernel Memory) | Microsoft | MIT | 28,421 / 2,174 | 257 / 0 | 2026-08-05 / 2026-06-08 | Memory connectors → MEVD Vector Store abstractions; Kernel Memory as separate ingestion service; converging into MS Agent Framework |
| Google ADK (`adk-python`) | Google | Apache-2.0 | 21,012 | 602 | 2026-08-05 | `MemoryService` interface: InMemory (keyword), VertexAiRagMemoryService, VertexAiMemoryBankService |
| smolagents | Hugging Face | Apache-2.0 | 28,681 | 744 | 2026-07-21 | Deliberately BYO: user-written `RetrieverTool`; no built-in retrieval or persistent memory |
| Letta (ex-MemGPT) | Letta (~$10M seed, Felicis, 2024) | Apache-2.0 | 24,100 | 49 | 2026-08-01 | Memory-first: core memory blocks, archival/recall memory, self-editing tools, sleep-time compute; 2026 pivot to Letta Code |
| Mastra | Mastra (YC W25, ex-Gatsby founders) | Elastic-style (NOASSERTION) | 26,943 | 642 | 2026-08-05 | Full-stack TS: `MDocument` chunking → vector stores → `createVectorQueryTool`; `Memory` with semantic recall |
| Pydantic AI | Pydantic Services | MIT | 19,070 | 640 | 2026-08-05 | Deliberately minimal: no built-in RAG or cross-run memory; embeddings API recent; memory layer an open RFC |

Momentum signals worth recording:

- `modelcontextprotocol/servers` (89.2k stars) dwarfs every individual framework repo. The
  ecosystem's centre of gravity moved from framework-internal retrieval to protocol-level
  retrieval tools.
- AutoGen's repo has not been pushed since 2026-04-15 and carries 976 open issues — effectively
  frozen after Microsoft publicly converged AutoGen + Semantic Kernel into the
  "Microsoft Agent Framework" ([Azure announcement](https://azure.microsoft.com/en-us/blog/introducing-microsoft-agent-framework/)).
- Letta's own README now flags its 24k-star repo as "the legacy Letta server... Active development
  has moved to the Letta Agent repo (letta-code)" — the memory-framework company itself pivoted to
  a Claude-Code-style filesystem agent with skills and subagents.

---

## Retrieval-pipeline architecture

### The two macro-patterns

1. **Framework-owned pipeline** (CrewAI Knowledge, AutoGen RetrieveChat, SK memory connectors,
   Mastra RAG, Letta archival memory): the framework ships ingestion → chunking → embedding →
   vector store → top-k injection. In effect a miniature LangChain embedded inside an agent
   framework, usually with weaker defaults than dedicated RAG stacks.
2. **Retrieval-as-tool / memory-as-service** (OpenAI FileSearchTool, Claude/MCP, ADK MemoryService,
   smolagents, Pydantic AI): the framework owns *none* of the pipeline. Retrieval is a tool the
   model calls, backed by a hosted service, an MCP server, or user code. The agent loop supplies
   query formulation, iteration, and synthesis.

Anthropic's engineering guidance crystallized the second pattern: agents should hold "lightweight
identifiers (file paths, stored queries, web links)" and load context just-in-time via tools,
because "as the number of tokens in the context window increases, the model's ability to accurately
recall information from that context decreases" (context rot) —
[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
Claude Code's creator was explicit on HN: **"Claude Code doesn't use RAG currently. In our testing
we found that agentic search out-performed RAG for the kinds of things people use Code for"**
([bcherny, HN 43164253](https://news.ycombinator.com/item?id=43164253)).

### OpenAI Agents SDK — hosted FileSearchTool

- **Ingestion/parsing**: upload files (23 supported formats) into managed Vector Stores; parsing is
  a black box. Limits: 512 MB and 5,000,000 tokens per file
  ([retrieval guide](https://developers.openai.com/api/docs/guides/retrieval)).
- **Chunking**: fixed defaults `max_chunk_size_tokens=800`, `chunk_overlap_tokens=400` (50%
  overlap). These two knobs are the *only* chunking controls. No structure-aware, semantic, or
  per-format chunking.
- **Embedding/indexing**: OpenAI-managed embeddings (model not even documented); storage priced at
  $0.10/GB/day beyond 1 GB free.
- **Query handling**: optional server-side query rewriting (`rewrite_query`); ranker options
  `auto` / `default-2024-08-21`; `max_num_results` default 10 (max 50); attribute filtering with up
  to 16 metadata keys per file.
- **Retrieval → synthesis**: results injected as tool output into the Responses-API agent loop.
  The SDK class is a thin declaration (`FileSearchTool(vector_store_ids=..., max_num_results=...)`);
  everything else happens server-side and is unobservable.
- **Memory**: Sessions/Conversations persist turn history; no semantic memory layer.
- **Notable documented caveat**: "Removing files from a vector store is eventually consistent, and
  search results may still include content from a removed file for a short period" (official docs).

### Claude Agent SDK / MCP — no pipeline at all

- The "index" is the filesystem plus the model's tool loop: Grep/Glob/Read, subagents for scoped
  exploration with isolated context windows.
- **Skills** implement *progressive disclosure*: only name+description loaded upfront; full
  instructions and resources pulled on demand — an anti-context-rot retrieval discipline.
- **Memory tool** (public beta): "a file-based system" letting agents "build up knowledge bases
  over time, maintain project state across sessions, and reference previous work without keeping
  everything in context" (Anthropic context-engineering post). **Compaction** summarizes a nearly
  full conversation and restarts the window with the summary.
- External retrieval arrives via **MCP servers** (vector-DB vendors, Elastic, filesystem, the
  knowledge-graph `server-memory`). The official servers repo explicitly disclaims: reference
  servers are "educational examples... **not production-ready solutions**"
  ([README](https://github.com/modelcontextprotocol/servers)).
- Anthropic's own [code-execution-with-MCP post](https://www.anthropic.com/engineering/code-execution-with-mcp)
  concedes the token economics of naive tool loops: agents connected to many MCP tools "process
  hundreds of thousands of tokens before reading a request"; intermediate results flow through
  context twice (a 2-hour transcript ≈ an extra 50,000 tokens); moving to code-mediated tool access
  cut one workflow "from 150,000 tokens to 2,000 tokens — a time and cost saving of 98.7%."

### CrewAI — embedded mini-RAG

- **Knowledge**: sources (raw text, PDF, CSV, Excel, JSON, custom `BaseKnowledgeSource`) → chunks →
  ChromaDB (Qdrant optional), stored in a hidden per-platform app-data directory
  (`~/Library/Application Support/CrewAI/...` on macOS).
- **Defaults** ([knowledge docs](https://docs.crewai.com/en/concepts/knowledge)):
  `results_limit=3`, `score_threshold=0.35`, embedder `text-embedding-3-small` — *regardless of the
  crew's LLM provider*. Docs warn that switching embedders requires a manual storage reset to avoid
  dimension-mismatch errors, and that large sources are re-embedded on every `kickoff()` unless
  pre-initialized.
- **Query handling**: task prompts are automatically rewritten into search queries (non-optional,
  minimally observable via knowledge events).
- **Memory** (`memory=True`): short-term/entity RAG storage (also Chroma) whose retrieved contents
  are concatenated into future agent prompts.

### AutoGen 0.2 → AG2 → 0.4 — three retrieval generations

- **0.2 `RetrieveUserProxyAgent`** (defaults verified in
  [0.2 branch source](https://github.com/microsoft/autogen/blob/0.2/autogen/agentchat/contrib/retrieve_user_proxy_agent.py)):
  docs → chunks (`chunk_token_size = max_tokens * 0.4`, `chunk_mode="multi_lines"`,
  `must_break_at_empty_line=True`) → ChromaDB (`collection_name="autogen-docs"`) → context stuffed
  up to `context_max_tokens = max_tokens * 0.8`. Iteration protocol: the LLM is instructed to reply
  *exactly* `UPDATE CONTEXT` to trigger re-retrieval — string-matching as a control channel.
- **Teachability** (0.2 capability): user-fact "memos" persisted in a MemoStore and injected into
  future prompts.
- **0.4 rewrite**: a from-scratch API replacing RetrieveChat with a `Memory` protocol
  (`query` / `add` / `update_context`) and `autogen-ext` vector memories (e.g.
  `ChromaDBVectorMemory`). RetrieveChat's lineage continued only in the AG2 community fork.
- The official [RAG roadmap issue #1657](https://github.com/microsoft/autogen/issues/1657)
  documents ambitions (multi-vector-DB support, better chunking) that were abandoned mid-flight by
  the 0.4 rewrite and then the Microsoft Agent Framework merger.

### Semantic Kernel / Kernel Memory

- **Gen 1**: `SemanticTextMemory` + `TextMemoryPlugin` (semantic "recall" inside prompt templates)
  over per-DB memory connectors.
- **Gen 2**: Microsoft.Extensions.VectorData (MEVD) Vector Store abstractions — a redesign with
  breaking DI-registration changes ([#10549](https://github.com/microsoft/semantic-kernel/issues/10549)).
- **Kernel Memory** is a *separate* repo/service implementing the ingestion pipeline
  (extract → partition → embed → save) with citations, callable from SK as a plugin — an
  acknowledgment that the in-framework memory was insufficient.
- **Context management**: `ChatHistoryReducer`s (truncation/summarization). Users report the
  summarization reducer silently not engaging: "It still passes the complete chat history to llm
  api call" ([#12303](https://github.com/microsoft/semantic-kernel/issues/12303), open).
- **Gen 3**: the Agent Framework convergence (with Elastic as a named retrieval connector), again
  with no published migration path in the announcement.

### Google ADK

- Clean tripartite model ([memory docs](https://adk.dev/sessions/memory/)): `Session` (event log) /
  `State` (scratch keys) / `MemoryService` (cross-session searchable store).
- **Ingestion**: `add_session_to_memory()` at session end; Memory Bank optionally does LLM
  extraction and consolidation ("consolidates new memories with existing ones to prevent
  redundancy").
- **Retrieval**: two prebuilt tools — `load_memory` (reactive; the agent decides to search) and
  `preload_memory` (proactive; retrieves every turn) — both call `search_memory(query)`; custom
  tools can call `tool_context.search_memory()`.
- **Defaults**: `InMemoryMemoryService` does basic keyword matching with no persistence. The
  production path is GCP-only: VertexAiRagMemoryService (raw-transcript vector search over RAG
  Engine / Knowledge Engine) or VertexAiMemoryBankService (managed, LLM-extracted memories).
- **Constraint**: one configured memory service per runner (`--memory_service_uri`).

### smolagents

- Nothing built in, by design. The official tutorial has users hand-write a `RetrieverTool`
  wrapping LangChain's `BM25Retriever` (k=10) over `RecursiveCharacterTextSplitter` chunks
  (500 chars / 50 overlap), with the tool docstring coaching the model to phrase queries "in the
  affirmative form rather than a question"
  ([Agentic RAG docs](https://huggingface.co/docs/smolagents/examples/rag)).
- The docs argue agentic RAG natively subsumes HyDE and self-query refinement (multi-step retrieval,
  query reformulation, self-critique) — the clearest published statement of the
  retrieval-as-tool thesis.
- Agent memory is the in-run step log; cross-run persistence and consolidation are unfinished
  (open feature requests, see issues below).

### Letta (MemGPT)

- The most opinionated memory architecture in the cohort:
  - **Core memory blocks** (persona/human/custom) living *in* the context window, self-edited by
    the agent via `memory_replace` / `memory_insert` / `rethink_memory`;
  - **Recall memory**: searchable conversation history;
  - **Archival memory**: embedding-indexed passages via `archival_memory_insert/search`;
  - **Summarization/compaction** on context overflow; **sleep-time agents** that reorganize memory
    between interactions (offline consolidation compute);
  - Server-based: agents are database rows; every message persists (agents-as-a-service).
- 2026 pivot: the company refocused on **Letta Code** and the Letta Agent SDK with
  filesystem-first memory and skills. Its own benchmark work concluded that "agents are better
  equipped to use familiar filesystem operations than complex alternatives like knowledge graphs"
  ([Letta blog](https://www.letta.com/blog/benchmarking-ai-agent-memory)).

### Mastra

- TS-native owned pipeline ([RAG docs](https://mastra.ai/docs/rag/overview)):
  `MDocument.chunk()` (recursive, sliding-window, etc.; e.g. 512-token chunks / 50 overlap) →
  `embedMany` (Vercel AI SDK embedders) → vector stores (pgvector, Pinecone, Qdrant, MongoDB,
  LibSQL, Lance...) → exposed to agents via `createVectorQueryTool`; optional rerank and
  graph-RAG helpers.
- **Memory**: `lastMessages` recency window + *semantic recall* (vector search over past thread
  messages) + *working memory* (a persistent structured block), namespaced by thread/resource IDs.

### Pydantic AI

- Explicitly not a RAG framework. The official RAG example builds embeddings with the raw OpenAI
  SDK + pgvector; the founder-filed issue [#58](https://github.com/pydantic/pydantic-ai/issues/58)
  ("Currently we don't have anything") tracked a first-party embeddings API for over a year before
  a WIP implementation (PR #3252) — with Guido van Rossum among the commenters requesting it.
- Context handling via message-history processors
  ([#1901](https://github.com/pydantic/pydantic-ai/issues/1901) added history collapsing).
- Cross-run memory remains an open RFC for an `AbstractMemoryStore`
  ([#4773](https://github.com/pydantic/pydantic-ai/issues/4773)): "Every call to `agent.run()`
  starts with a blank slate... error-prone, repetitive boilerplate that every production
  [team rebuilds]."

---

## Agentic integration

- **Retrieval-as-tool is the convergent design**: FileSearchTool, ADK `load_memory`, Mastra
  `createVectorQueryTool`, smolagents `RetrieverTool`, Letta `archival_memory_search`, MCP servers.
  The model owns query formulation, iteration, and stop conditions — inheriting agentic-RAG
  strengths (multi-query, self-refinement, HyDE-for-free) and weaknesses (no guaranteed retrieval,
  no relevance feedback signal, token-expensive loops).
- **Memory-as-service is the second convergent design**: Letta server, ADK MemoryService / Vertex
  Memory Bank, Mastra Memory, CrewAI memory, MCP `server-memory`. Both the write path (what to
  store, consolidation) and read path (recall into prompt) are framework-mediated and mostly
  invisible to the developer.
- **Anthropic's counter-position** — no index at all: agentic filesystem search + progressive
  disclosure (Skills) + file-based memory + compaction — was the most influential idea of 2025–26,
  validated by Letta's pivot and LoCoMo results, but it trades one-time indexing cost for per-query
  token cost and depends on models' RL'd search habits.
- **MCP retrieval-server ecosystem, 2026 state**: registry-scale (the README now points to a
  separate MCP Registry for the thousands of community servers; the official repo houses only
  steering-group reference servers) but shallow — reference servers are demos by their own
  admission; persistence, quotas, redaction, and security are the integrator's problem
  ([servers #4117](https://github.com/modelcontextprotocol/servers/issues/4117)). The protocol
  standardizes *transport and tool schemas*, not retrieval *quality*.

---

## Strengths (steelman)

1. **Right altitude for agents.** Retrieval-as-tool lets the model decide *when/what/how much* to
   retrieve, natively implementing query rewriting and iterative refinement that static pipelines
   need bolt-ons for (smolagents docs; OpenAI `rewrite_query`; ADK reactive `load_memory`).
2. **Evidence that agentic search works.** Claude Code shipped category-defining code assistance
   with zero embedding infrastructure (bcherny, HN 43164253); Letta hit 74.0% on LoCoMo with
   GPT-4o-mini *and plain filesystem tools*, above dedicated memory products (Letta blog).
3. **Zero-ops managed options.** OpenAI Vector Stores (parsing, chunking, embedding, reranking,
   metadata filtering, query rewriting all server-side) and Vertex Memory Bank (LLM-extracted,
   consolidated memories) remove the ingestion pipeline entirely for the 80% case.
4. **Letta's memory model is genuinely novel.** Self-editing in-context blocks + tiered
   archival/recall memory + sleep-time consolidation is the closest thing to an OS for agent
   memory — inspectable, persistent, and multi-agent-shareable (memory blocks attachable to
   multiple agents).
5. **Separation of concerns via MCP.** Retrieval servers are swappable across Claude, OpenAI, ADK,
   and Mastra hosts — the first real decoupling of retrieval infrastructure from agent frameworks.
6. **ADK's session/state/memory taxonomy** is the cleanest conceptual model in the cohort and maps
   directly onto the short-term/long-term memory literature; proactive vs reactive recall as two
   prebuilt tools is a good pattern.

---

## Issues & failure modes

### abstraction-design

**A1. Hosted retrieval tools are provider-locked, breaking the model-agnostic promise.**
- `FileSearchTool` works only with OpenAI Responses-API models; swap in Claude or Gemini via
  LiteLLM and hosted retrieval silently isn't available.
- Evidence: [openai-agents-python #461](https://github.com/openai/openai-agents-python/issues/461)
  — "no provider yet supports fully swapping between models and their native tools"; also
  [#1904](https://github.com/openai/openai-agents-python/issues/1904) asking how to do RAG at all
  outside OpenAI's stack.
- Severity: **major**. Label: **documented-recurring**.

**A2. Black-box retrieval stages make relevance debugging impossible.**
- OpenAI's parsing/embedding/ranking are unobservable (docs expose only chunk size, k, filters, and
  a ranker name — the embedding model isn't even documented); CrewAI's automatic query rewriting
  and memory injection surface no traces; Vertex Memory Bank's LLM extraction is opaque. When
  retrieval is wrong there is no stage to inspect.
- Evidence: OpenAI [retrieval guide](https://developers.openai.com/api/docs/guides/retrieval)
  parameter surface; CrewAI knowledge docs.
- Severity: **major**. Label: **architectural-inference** (grounded in documented API surfaces).

**A3. Extension points are bolted on, not designed.**
- ADK's `adk web` debugger hardwired three memory-service URL prefixes, leaving "no space for
  injecting a customized memory service of the user's design"
  ([google/adk-python #2865](https://github.com/google/adk-python/issues/2865)).
- CrewAI requires filesystem surgery (`CREWAI_STORAGE_DIR`, manual storage resets) to change
  embedders (docs).
- Severity: minor. Label: **documented-recurring**.

**A4. "Abstraction soup" drives production teams off frameworks entirely.**
- HN, 2026: "the 'abstraction soup' makes debugging a nightmare in production. I'm seeing more
  people just using the OpenAI/Anthropic SDKs directly or very thin wrappers"
  ([HN 47132187](https://news.ycombinator.com/item?id=47132187), thread: "Does anyone use CrewAI or
  LangChain anymore?"; top reply: "No. They suck.").
- The market response is visible in-cohort: smolagents (~1k LOC core) and Pydantic AI both position
  as thin anti-frameworks.
- Severity: **major**. Label: **documented-recurring**.

### retrieval-quality

**R1. Naive, silently-poor defaults in framework-owned pipelines.**
- CrewAI: top-3 chunks at 0.35 threshold from ChromaDB, `text-embedding-3-small` hardcoded even for
  non-OpenAI crews ([docs](https://docs.crewai.com/en/concepts/knowledge)); historically demanded an
  OpenAI key even when Ollama was configured ([#21](https://github.com/crewAIInc/crewAI/issues/21),
  [#439](https://github.com/crewAIInc/crewAI/issues/439)).
- ADK's default memory service is keyword matching, no persistence (docs).
- AutoGen 0.2 chunked at `0.4 × max_tokens` with line-based splitting (source).
- None of the owned pipelines ship hybrid search, reranking, or eval hooks by default.
- Severity: **major**. Label: **documented-recurring**.

**R2. One-size-fits-all chunking in the hosted path.**
- OpenAI file search: 800-token chunks / 400 overlap, exactly two tunables; no structure-aware or
  semantic chunking; query rewriting had to be requested by users
  ([openai-agents #1728](https://github.com/openai/openai-agents-python/issues/1728)); the file tool
  rejected `.md` files ([#2186](https://github.com/openai/openai-agents-python/issues/2186)).
- Mastra users filed for semantic chunking: retrieval quality "directly links to" chunk quality
  ([mastra #3605](https://github.com/mastra-ai/mastra/issues/3605)).
- Severity: **major**. Label: **documented-recurring**.

**R3. Memory recall is recency-flat and structure-blind.**
- Mastra `Memory.recall()` "builds the agent's history by flat recency only," making
  branched/forked conversations irrecoverable; a production team (Zynda) called it
  "important / near-blocking" ([mastra #18943](https://github.com/mastra-ai/mastra/issues/18943), open).
- Letta archival memory accumulates "redundant passages" and "semantic duplicates" with no
  consolidation mechanism ([letta #3116](https://github.com/letta-ai/letta/issues/3116), open).
- Severity: **major**. Label: **documented-recurring**.

**R4. Iterative-retrieval control channels are brittle.**
- AutoGen's protocol required the LLM to "reply exactly `UPDATE CONTEXT`" to re-retrieve; users hit
  contexts not updating after the first query
  ([autogen #2276](https://github.com/microsoft/autogen/issues/2276)) and assistants ignoring
  provided context ([#3535](https://github.com/microsoft/autogen/issues/3535)).
- Severity: minor (pattern now deprecated — itself evidence of a failed design generation).
  Label: **documented-recurring**.

### data-processing

**D1. Ingestion paths crash or corrupt on realistic inputs.**
- CrewAI `memory=True` crashed on large inputs because content was embedded without
  chunking/truncation — "30k+ tokens vs. an 8k token limit"
  ([crewAI #2753](https://github.com/crewAIInc/crewAI/issues/2753)).
- Default-config memory RAG storage broke outright on upgrade
  ([#1669](https://github.com/crewAIInc/crewAI/issues/1669)); knowledge upserts failed with
  protocol/collection errors ([#2746](https://github.com/crewAIInc/crewAI/issues/2746),
  [#2055](https://github.com/crewAIInc/crewAI/issues/2055)).
- Severity: **major**. Label: **documented-recurring**.

**D2. Reference memory infrastructure has unsafe persistence.**
- `@modelcontextprotocol/server-memory`: no atomic writes, quotas, redaction, or
  destructive-operation guardrails ([servers #4117](https://github.com/modelcontextprotocol/servers/issues/4117), open);
  ignores custom storage path ([#692](https://github.com/modelcontextprotocol/servers/issues/692));
  env vars not respected ([#1018](https://github.com/modelcontextprotocol/servers/issues/1018)).
- These are the templates the MCP ecosystem copies.
- Severity: **major**. Label: **documented-recurring**.

**D3. Deletes are eventually consistent in hosted stores.**
- OpenAI docs: "search results may still include content from a removed file for a short period" —
  a GDPR/compliance problem stated as a footnote.
- Severity: minor. Label: **documented-recurring** (official docs).

### evaluation-observability

**E1. No framework ships a retrieval/memory eval loop.**
- Letta's own tracker admitted the framework "lacks any standardized benchmark or evaluation code
  to measure memory system performance," making it impossible to "quantify improvements" or
  "compare with alternatives" ([letta #3115](https://github.com/letta-ai/letta/issues/3115)).
- None of the ten expose retrieval-quality metrics (recall@k, groundedness, memory-hit usefulness)
  as first-class citizens; CrewAI's knowledge events and Mastra's OTel spans log *that* retrieval
  happened, not whether it was *right*.
- Severity: **critical** (cohort-wide). Label: **documented-recurring**.

**E2. Vendor benchmark wars fill the eval vacuum.**
- Mem0's paper ([arXiv 2504.19413](https://arxiv.org/abs/2504.19413)) claimed LOCOMO SOTA (26%
  LLM-judge improvement over OpenAI memory, 91% lower p95 latency vs full-context).
- Letta showed the MemGPT baseline was mis-implemented ("unable to determine a way to backfill
  LoCoMo data into MemGPT/Letta without significant refactoring"; Letta scored 74.0% vs Mem0's
  reported 68.5% — [Letta blog](https://www.letta.com/blog/benchmarking-ai-agent-memory)).
- HN: "turns out they completely botched the implementation of their competitors... When Letta and
  Zep actually ran the benchmarks correctly, they both hit a 10% higher score than Mem0's best"
  ([HN 44883134](https://news.ycombinator.com/item?id=44883134)).
- Severity: **major**. Label: **documented-recurring**.

**E3. Context-management components fail silently.**
- SK's `ChatHistorySummarizationReducer` with `auto_reduce=True` "still passes the complete chat
  history to llm api call" with no error
  ([semantic-kernel #12303](https://github.com/microsoft/semantic-kernel/issues/12303), open) —
  discovered via token bills, not telemetry.
- Severity: **major**. Label: **single-anecdote** (but emblematic: reducers have no observability
  contract anywhere in the cohort).

### production-ops

**P1. Strategic churn/abandonment is the cohort's biggest operational risk.**
- AutoGen: 0.2 → 0.4 total rewrite → community AG2 fork → Microsoft Agent Framework convergence;
  repo frozen since 2026-04 with 976 open issues (GitHub API).
- Semantic Kernel memory: SemanticTextMemory → MEVD breaking changes
  ([#10549](https://github.com/microsoft/semantic-kernel/issues/10549)) → Agent Framework, with the
  convergence announcement offering "no guidance" on migration (Azure blog, checked).
- Letta's 24k-star server is "legacy" per its own README.
- Retrieval/memory code written against any of these in 2024–25 has been rewritten twice.
- Severity: **critical**. Label: **documented-recurring**.

**P2. Upgrade fragility in embedded stores.**
- CrewAI version bumps broke default memory storage
  ([#1669](https://github.com/crewAIInc/crewAI/issues/1669),
  [#1333](https://github.com/crewAIInc/crewAI/issues/1333)); embedder swaps require manual storage
  resets (docs). Hidden app-data directories make state drift invisible to deploys.
- Severity: **major**. Label: **documented-recurring**.

**P3. Compaction/summarization corrupt agent state under load.**
- Letta: sliding-window compaction set to evict 15% "performs a full context wipe instead of
  partial eviction — all conversation history is gone"
  ([letta #3270](https://github.com/letta-ai/letta/issues/3270), open).
- Letta: summarization trimmed a tool call but not its paired response, crashing the OpenAI client
  ([#2605](https://github.com/letta-ai/letta/issues/2605)).
- These are the exact mechanisms long-running agents depend on for unbounded operation.
- Severity: **major**. Label: **documented-recurring**.

**P4. Cold-start and bundle weight.**
- ADK imports add 8–20s cold-start latency
  ([adk-python #2433](https://github.com/google/adk-python/issues/2433), open).
- Mastra +17MB bundle regression blocked Cloudflare Workers deployments
  ([mastra #3309](https://github.com/mastra-ai/mastra/issues/3309)).
- Severity: minor. Label: **documented-recurring**.

### agentic-integration

**G1. Query formulation is delegated to the model with no feedback loop.**
- In retrieval-as-tool, nothing measures whether the model's query was good; frameworks coach via
  docstrings ("use the affirmative form rather than a question" — smolagents official tool
  description). Retrieval misses present as hallucinations.
- Severity: **major**. Label: **architectural-inference** (core property of the pattern, visible in
  every cohort member's tool design).

**G2. Models are RL'd on grep and distrust custom retrieval tools.**
- Practitioners: "the models are so heavily RL'd with grep that they do not trust results in other
  forms and will continually retry or reread, and all token savi[ngs vanish]"
  ([HN 48169874](https://news.ycombinator.com/item?id=48169874), Semble thread; multiple
  corroborating commenters describing agents ignoring LSP/RTK tools).
- Retrieval-tool effectiveness is hostage to model training priors no framework controls.
- Severity: **major**. Label: **documented-recurring**.

**G3. Guardrails and hosted retrieval compose badly.**
- `FileSearchTool` executed (and billed) despite an input guardrail tripwire, because hosted tools
  run server-side before guardrail resolution
  ([openai-agents #889](https://github.com/openai/openai-agents-python/issues/889)).
- Severity: minor. Label: **single-anecdote**.

**G4. Minimal frameworks externalize memory entirely — and the gap stays open.**
- Pydantic AI: no cross-run memory ([#4773](https://github.com/pydantic/pydantic-ai/issues/4773)
  RFC open); embeddings took a year+ from
  [#58](https://github.com/pydantic/pydantic-ai/issues/58) to a WIP PR.
- smolagents: save/load agent memory
  ([#1216](https://github.com/huggingface/smolagents/issues/1216)) and memory consolidation
  ([#901](https://github.com/huggingface/smolagents/issues/901)) remain open feature requests.
- "Bring your own" in practice means every production team rebuilds session persistence, recall,
  and consolidation from scratch.
- Severity: **major**. Label: **documented-recurring**.

### security-governance

**S1. Memory is an unsanitized prompt-injection channel.**
- CrewAI concatenates retrieved memory directly into the system prompt: "If memory entries have
  been poisoned (e.g., via indirect prompt injection through tool outputs), an attacker can inject
  arbitrary instructions into the system prompt of future agent interactions"
  ([crewAI #5057](https://github.com/crewAIInc/crewAI/issues/5057), open; OWASP ASI-01).
- Parallel memory-poisoning reports: Pydantic AI
  ([#5424](https://github.com/pydantic/pydantic-ai/issues/5424), OWASP ASI06) and MCP memory
  ([servers #4117](https://github.com/modelcontextprotocol/servers/issues/4117) requests redaction
  and destructive-op guardrails).
- No framework in the cohort ships provenance-tagged or trust-tiered memory.
- Severity: **critical**. Label: **documented-recurring**.

**S2. No ACL / multi-tenancy story in retrieval-as-tool.**
- Hosted vector stores support attribute filters, but frameworks don't model per-user document
  permissions; MCP reference servers explicitly disclaim production security posture (repo README);
  Mastra thread/resource IDs are namespaces, not authorization.
- Severity: **major**. Label: **architectural-inference** (grounded in documented API surfaces and
  the README disclaimer).

### performance-cost

**C1. Agentic search trades index cost for per-query token burn.**
- Anthropic's own numbers: naive MCP tool loops can consume 150,000 tokens where code-mediated
  access needs 2,000 (98.7% reduction); large tool results transit context twice (2-hour
  transcript ≈ +50k tokens) ([code-execution post](https://www.anthropic.com/engineering/code-execution-with-mcp)).
- Third parties built businesses on the gap: "Code search for agents that uses 98% fewer tokens
  than grep" ([Semble, HN 48169874](https://news.ycombinator.com/item?id=48169874), 445 points;
  premise: Claude Code "falls back to grep, reading full files or launching subagents. This uses a
  lot of tokens, and often still misses the relevant code").
- Severity: **major**. Label: **documented-recurring**.

**C2. Context rot penalizes stuff-everything designs.**
- Anthropic documents recall degradation as context grows (context-engineering post). Frameworks
  that inject memory + knowledge + full history every turn (CrewAI, SK with silently-broken
  reducers per E3, ADK `preload_memory`) pay both dollar and accuracy costs.
- Severity: **major**. Label: **documented-recurring** (vendor-documented phenomenon plus the
  E3/D1 cost incidents).

---

## Community sentiment over time

- **2023–24 — pipeline era.** AutoGen RetrieveChat and CrewAI memory greeted enthusiastically;
  early issues were plumbing (OpenAI-key coupling crewAI #21; chromadb/sqlite breakage
  autogen #251). MemGPT's HN debut was a hit (363 points,
  [HN 37901902](https://news.ycombinator.com/item?id=37901902)).
- **2025 — disillusionment and the agentic-search turn.** bcherny's "Claude Code doesn't use RAG"
  (Feb 2025) became the most-cited datapoint in the RAG-vs-agentic-search debate; Microsoft's
  framework churn and the Mem0-vs-Letta/Zep benchmark fight eroded trust in vendor claims;
  "why we moved off <framework>" posts proliferated.
- **2026 — thin-wrapper consolidation.** "Does anyone use CrewAI or LangChain anymore?"
  ([HN 47132187](https://news.ycombinator.com/item?id=47132187)) — representative answers: "No.
  They suck" / "abstraction soup... It's better to own your prompts." Community energy moved to MCP
  servers, token-efficient code-search tools (Semble, RTK, LSP plugins for Claude Code), and
  harness-style agents (Claude Code, Letta Code). Counter-current: practitioners quantify the
  grep-loop token tax and are re-introducing *indexes as tools* — retrieval infrastructure is
  returning, but agent-shaped and framework-external.

---

## Benchmarks & third-party evaluations

- **LOCOMO / LoCoMo** (long-conversation QA): Mem0's paper
  ([arXiv 2504.19413](https://arxiv.org/abs/2504.19413)) claimed SOTA (+26% LLM-judge over OpenAI
  memory; −90% token cost and −91% p95 latency vs full-context). Letta's rebuttal: 74.0% with
  GPT-4o-mini and plain filesystem tools vs Mem0's reported 68.5%, plus documentation that the
  paper's MemGPT baseline could not have been run as described
  ([Letta blog](https://www.letta.com/blog/benchmarking-ai-agent-memory)); Zep published a similar
  rebuttal (per [HN 44883134](https://news.ycombinator.com/item?id=44883134)).
  **Net community takeaway: simple file tools ≥ specialized memory frameworks on this benchmark —
  and the benchmark itself is contested.**
- **Letta later added LOCOMO/LongMemEval/MemBench-style evaluation** after community pressure
  ([letta #3115](https://github.com/letta-ai/letta/issues/3115), closed) and runs a public
  model-memory leaderboard (leaderboard.letta.com) — the only cohort member with first-party
  memory evals.
- **Code-retrieval-for-agents**: Semble's NDCG-per-token benchmark vs ripgrep/BM25
  ([HN 48169874](https://news.ycombinator.com/item?id=48169874)) exemplifies the emergent
  evaluation style: retrieval quality *per token spent, inside an agent loop* — a metric no
  framework in this cohort reports. Commenters immediately flagged the gap between one-shot
  retrieval NDCG and end-to-end agent outcomes; the authors conceded end-to-end evaluation was
  "on the roadmap."
- **Notably absent**: no independent academic evaluation compares retrieval quality of CrewAI
  Knowledge vs ADK MemoryService vs OpenAI file search on shared corpora. Agent benchmarks (GAIA,
  SWE-bench, Terminal-Bench) measure end-task success, leaving each framework's retrieval
  contribution unattributed.

---

## Lessons for a next-generation framework

1. **Retrieval-as-tool won; now give it a contract.** Standardize a retrieval-tool interface
   (query, filters, token budget, provenance, confidence) so hosted/local/MCP retrievers are
   swappable across model providers — fixing A1 — and instrument it end-to-end so
   query → results → downstream usefulness is traceable (fixing A2/E1).
2. **Budget-aware by construction.** Every retrieval/memory call should declare and account for
   its context cost; the framework should optimize *evidence per token* (C1/C2), including
   code-mediated access for bulk results and progressive disclosure for large corpora.
3. **Memory needs provenance and trust tiers, not just vectors.** Tag every memory entry with
   source, writer, and trust level; sanitize/quarantine before prompt injection (S1); scope by
   principal for multi-tenancy (S2).
4. **Ship the eval loop, not just the pipeline.** First-party retrieval/memory metrics (recall@k,
   groundedness, memory-hit usefulness) with replayable traces, plus neutral harnesses so buyers
   aren't arbitrating vendor benchmark wars (E1/E2).
5. **Defaults must be production-shaped.** Hybrid retrieval + reranking out of the box;
   structure-aware chunking; chunk-safe ingestion (D1); atomic, quota'd, redactable memory
   persistence (D2); consistent deletes (D3); compaction that provably preserves tool-call pairing
   and honors eviction ratios (P3).
6. **Design for model priors.** Retrieval tools compete with grep in the model's learned habits
   (G2); interfaces should mimic familiar affordances (file paths, snippets-with-context) and be
   validated in agent loops, not just on one-shot retrieval metrics.
7. **Stability is a feature.** The cohort's worst failure is churn (P1). Freeze a small
   retrieval/memory kernel; push innovation to the tool/server layer, MCP-style, where swaps don't
   force rewrites.
8. **Hybridize the philosophies.** Just-in-time agentic navigation for fresh/structured/local data
   plus owned indexes for scale and cost, with the agent choosing per query — the emerging
   practitioner consensus (Semble/HN threads; Letta's filesystem pivot; Anthropic's
   JIT-search-plus-memory-tool stack).

---

## Sources

**Vendor engineering & docs**
- Anthropic — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- OpenAI — [File search tool docs](https://developers.openai.com/api/docs/guides/tools-file-search); [Retrieval guide](https://developers.openai.com/api/docs/guides/retrieval)
- CrewAI — [Knowledge docs](https://docs.crewai.com/en/concepts/knowledge)
- Google ADK — [Memory docs](https://adk.dev/sessions/memory/)
- smolagents — [Agentic RAG docs](https://huggingface.co/docs/smolagents/examples/rag)
- Mastra — [RAG docs](https://mastra.ai/docs/rag/overview)
- Microsoft — [Introducing Microsoft Agent Framework](https://azure.microsoft.com/en-us/blog/introducing-microsoft-agent-framework/)
- Letta — [README (legacy-server notice)](https://github.com/letta-ai/letta); [Benchmarking AI agent memory (LoCoMo)](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- MCP — [servers repo README (reference/archived servers, production disclaimer)](https://github.com/modelcontextprotocol/servers)

**GitHub issues (verified live, 2026-08-05)**
- openai/openai-agents-python: [#461](https://github.com/openai/openai-agents-python/issues/461), [#889](https://github.com/openai/openai-agents-python/issues/889), [#1728](https://github.com/openai/openai-agents-python/issues/1728), [#1904](https://github.com/openai/openai-agents-python/issues/1904), [#2186](https://github.com/openai/openai-agents-python/issues/2186)
- crewAIInc/crewAI: [#21](https://github.com/crewAIInc/crewAI/issues/21), [#439](https://github.com/crewAIInc/crewAI/issues/439), [#1333](https://github.com/crewAIInc/crewAI/issues/1333), [#1669](https://github.com/crewAIInc/crewAI/issues/1669), [#2055](https://github.com/crewAIInc/crewAI/issues/2055), [#2746](https://github.com/crewAIInc/crewAI/issues/2746), [#2753](https://github.com/crewAIInc/crewAI/issues/2753), [#5057](https://github.com/crewAIInc/crewAI/issues/5057)
- microsoft/autogen: [#1657](https://github.com/microsoft/autogen/issues/1657), [#2276](https://github.com/microsoft/autogen/issues/2276), [#3535](https://github.com/microsoft/autogen/issues/3535); 0.2 `retrieve_user_proxy_agent.py` source (chunking/UPDATE-CONTEXT defaults verified)
- microsoft/semantic-kernel: [#10549](https://github.com/microsoft/semantic-kernel/issues/10549), [#12303](https://github.com/microsoft/semantic-kernel/issues/12303)
- google/adk-python: [#2433](https://github.com/google/adk-python/issues/2433), [#2865](https://github.com/google/adk-python/issues/2865)
- huggingface/smolagents: [#901](https://github.com/huggingface/smolagents/issues/901), [#1216](https://github.com/huggingface/smolagents/issues/1216)
- letta-ai/letta: [#2605](https://github.com/letta-ai/letta/issues/2605), [#3115](https://github.com/letta-ai/letta/issues/3115), [#3116](https://github.com/letta-ai/letta/issues/3116), [#3270](https://github.com/letta-ai/letta/issues/3270)
- mastra-ai/mastra: [#3309](https://github.com/mastra-ai/mastra/issues/3309), [#3605](https://github.com/mastra-ai/mastra/issues/3605), [#18943](https://github.com/mastra-ai/mastra/issues/18943)
- pydantic/pydantic-ai: [#58](https://github.com/pydantic/pydantic-ai/issues/58), [#1901](https://github.com/pydantic/pydantic-ai/issues/1901), [#4773](https://github.com/pydantic/pydantic-ai/issues/4773), [#5424](https://github.com/pydantic/pydantic-ai/issues/5424)
- modelcontextprotocol/servers: [#692](https://github.com/modelcontextprotocol/servers/issues/692), [#1018](https://github.com/modelcontextprotocol/servers/issues/1018), [#4117](https://github.com/modelcontextprotocol/servers/issues/4117)

**Community & benchmarks**
- [HN 43164253](https://news.ycombinator.com/item?id=43164253) — bcherny: Claude Code uses no RAG; agentic search outperformed
- [HN 47132187](https://news.ycombinator.com/item?id=47132187) — "Does anyone use CrewAI or LangChain anymore?" (abstraction-soup sentiment)
- [HN 48169874](https://news.ycombinator.com/item?id=48169874) — Semble: grep token costs; models RL'd on grep distrust other retrieval tools
- [HN 44883134](https://news.ycombinator.com/item?id=44883134) — Mem0 LOCOMO benchmark dispute (Letta/Zep rebuttals)
- [HN 37901902](https://news.ycombinator.com/item?id=37901902) — MemGPT launch reception
- [arXiv 2504.19413](https://arxiv.org/abs/2504.19413) — Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory

**Adoption stats** — GitHub API, retrieved 2026-08-05 (star counts, licenses, last-push dates, open-issue counts as tabulated in Identity & adoption).
