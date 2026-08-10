# Data-Cloud Native RAG: Databricks Mosaic AI & Snowflake Cortex Search

An evidence-based autopsy of the "RAG inside the data platform" pattern, as embodied by
Databricks Mosaic AI (Vector Search, Agent Framework/Evaluation, Agent Bricks, AI/BI Genie)
and Snowflake Cortex (Cortex Search, Cortex Analyst, Cortex Agents). Both vendors sell the
same core promise: your enterprise data already lives here, so retrieval, governance, and
agents should live here too — no ETL, no second security model, no separate vector database.
This report steelmans that promise, then dissects where it breaks.

Research method note: this autopsy was compiled from official documentation, vendor
engineering blogs, arXiv papers, Hacker News (Algolia API), Reddit (r/databricks,
r/snowflake, r/dataengineering via PullPush archive), StackOverflow, and the Databricks
community forum. Both platforms are closed-source managed services, so there is no public
issue tracker; failure evidence necessarily leans on forums, docs-documented constraints,
and architectural inference — each issue below is labeled accordingly.

---

## Identity & adoption

### Databricks Mosaic AI
- **Maintainer:** Databricks, Inc. Closed-source managed platform (some adjacent OSS: MLflow, arctic-* is Snowflake's; Databricks' DBRX model weights were open).
- **Provenance:** MosaicML acquired June 2023 for ~$1.3B; "Mosaic AI" is the resulting GenAI product line. Vector Search GA'd 2024; Agent Framework + Agent Evaluation GA'd late 2024; **Agent Bricks** launched in beta June 11, 2025 ([Databricks blog](https://www.databricks.com/blog/introducing-agent-bricks)).
- **Funding/momentum:** Series K announced August 2025 at **>$100B valuation** ([press release](https://www.databricks.com/company/newsroom/press-releases/databricks-raising-series-k-investment-100-billion-valuation), 182-point HN story). Aggressive 2024–2026 acquisition streak (Tabular, Neon, etc.). AI products moved from free previews to pay-as-you-go token billing in July 2026 (see Issues).
- **Adoption signal:** Vector Search is the default retrieval layer for the large Databricks installed base; the pitch "your data is already here" is repeated verbatim by community advocates ([r/databricks: Mosaic vector search vs Qdrant](https://www.reddit.com/r/databricks/comments/1fekspu/databricks_mosaic_vector_search_vs_qdrant/)).

### Snowflake Cortex
- **Maintainer:** Snowflake Inc. Closed-source managed service; the **Arctic Embed** models are open (Apache-2.0).
- **Provenance:** Cortex Search is directly descended from the **Neeva acquisition** (May 2023, [Snowflake blog](https://www.snowflake.com/blog/snowflake-acquires-neeva-to-accelerate-search-in-the-data-cloud-through-generative-ai/)); Neeva founder Sridhar Ramaswamy became Snowflake CEO in Feb 2024 ([Businesswire](https://www.businesswire.com/news/home/20240228398564/en/)). Cortex Search GA'd 2024; Cortex Analyst (text-to-SQL) GA'd 2024–25; Cortex Agents GA'd 2025 with MCP connectors added by 2026.
- **Research output:** Arctic-Embed ([arXiv 2405.05374](https://arxiv.org/abs/2405.05374)) and Arctic-Embed 2.0 ([arXiv 2412.04506](https://arxiv.org/abs/2412.04506)) are credible, widely used open embedding models.
- **Adoption signal:** Cortex features are the centerpiece of Snowflake's "AI Data Cloud" repositioning; community traction is real but shallower than the marketing — see sentiment section.

**Why enterprises default to this pattern:** data gravity (documents and tables already
governed in the platform), single security/audit model (Unity Catalog / Snowflake RBAC +
row policies inherited by retrieval), no ETL to a separate vector store, procurement
simplicity (one vendor, one bill), and compliance residency. These are genuine advantages —
and also the mechanism of lock-in.

---

## Retrieval-pipeline architecture

### Databricks Mosaic AI Vector Search
Per the [official docs](https://docs.databricks.com/aws/en/generative-ai/vector-search):
- **Index types:** (1) Delta Sync index with Databricks-managed embeddings; (2) Delta Sync index with self-managed (precomputed) embeddings; (3) Direct Vector Access index (manual upserts via REST); (4) full-text (BM25) index, beta, on storage-optimized endpoints only.
- **Sync model:** Delta Sync indexes track a source Delta table via **Change Data Feed**. *Continuous* sync gives "seconds of latency" but "a compute cluster is provisioned to run the continuous sync streaming pipeline" (billed continuously); *triggered* sync is on-demand. Storage-optimized endpoints support triggered sync only and partially rebuild the index each sync ([create-query docs](https://docs.databricks.com/aws/en/generative-ai/create-query-vector-search)).
- **ANN engine:** HNSW over L2 distance (cosine requires pre-normalized vectors). Hybrid = ANN + BM25 merged via **Reciprocal Rank Fusion with a fixed k=60** — not tunable.
- **Scale/limits (docs):** ~320M vectors @768d on standard endpoints; 1B+ on storage-optimized; 100KB max row; 10,000 max ANN results but only **200 max results for hybrid/full-text**; no column-level permissions on indexes.
- **Serving:** dedicated always-on "vector search endpoints"; docs advise standard endpoints deliver 20–50ms at 30–200+ QPS, storage-optimized 300–500ms, with QPS plateaus and 429s near capacity ([best practices](https://docs.databricks.com/aws/en/generative-ai/vector-search-best-practices)).
- **Governance:** Unity Catalog objects; index ACLs follow catalog permissions; encryption in transit/at rest.
- **No managed chunking/parsing:** ingestion, parsing, and chunking are user-built Spark/DLT pipelines; Vector Search starts at the (chunked) Delta table.

### Snowflake Cortex Search
Per the [overview docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) and the [engineering blog](https://www.snowflake.com/engineering-blog/cortex-search-and-retrieval-enterprise-ai/):
- **Retrieval stack (managed, opinionated):** vector search (Arctic Embed m-v1.5 768d, l-v2.0 1024d/8k-context, or Voyage multilingual; precomputed vectors also allowed) + lexical keyword search with query expansion + **cross-encoder semantic reranking** + optional signal boosts (recency/popularity). Multilevel scoring (cheap in-memory pass, then heavyweight scoring from storage).
- **Freshness model:** the index is a materialized construct following **Dynamic Table semantics with TARGET_LAG** (e.g. '1 hour', '1 day'); incremental refresh only if a primary key/change tracking is defined; refreshes run on the customer's virtual warehouse.
- **Serving:** separate multi-tenant serving compute, "low-latency, high-throughput" — but throttled at **20 QPS per service** with a **400M-row materialization cap** (docs).
- **Single search column:** a service indexes exactly one text column; multi-field search requires concatenating columns into one ([r/snowflake workaround thread](https://www.reddit.com/r/snowflake/comments/1k68tsm/looking_for_fast_fuzzy_native_search_on_snowflake/morq3ii/)).
- **Chunking is the user's problem:** community guidance is "use something like langchain for chunking" in Python UDFs ([r/dataengineering](https://www.reddit.com/r/dataengineering/comments/1eqqdx0/snowflake_genai_pipeline_pricing/lhvdi2p/)).
- **Cost model** ([costs docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs)): serving billed **6.3 credits per GB/month of uncompressed indexed data** (accrues regardless of query volume), + EMBED_TEXT token charges, + warehouse compute for refreshes, + storage, + cloud-services change detection. Docs example: 10M rows ≈ 256.5 credits/month serving for one index; two indexes ≈ 448 credits/month.

### Text-to-SQL / structured retrieval
- **Snowflake Cortex Analyst:** multi-agent pipeline (classification → feature extraction → context enrichment → parallel SQL-generation LLMs → compiler-backed error correction → synthesizer) over a hand-authored **semantic model** (YAML or Semantic Views) ([engineering blog](https://www.snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes/)). Claims 90%+ accuracy, ~2x GPT-4o-on-raw-schema — internal benchmarks (see Issues). Priced per message. Can invoke Cortex Search to resolve high-cardinality literals.
- **Databricks AI/BI Genie:** the analogous text-to-SQL "space" abstraction over curated table sets; marketed with equally self-referential superlatives ("The best Text2SQL AI System", [Databricks-hosted talk](https://www.reddit.com/r/databricks/comments/1efskio/databricks_aibi_genie_the_best_text2sql_ai_system/)).

---

## Agentic integration

- **Databricks:** Mosaic AI Agent Framework (author agents in code, deploy on Model Serving, tools as Unity Catalog functions), Agent Evaluation (LLM judges, review app, synthetic eval generation — now being folded into MLflow 3, [docs](https://docs.databricks.com/aws/en/generative-ai/agent-evaluation/)), and **Agent Bricks** (declare task in natural language → auto-generated benchmarks + LLM judges → automated optimization via prompt search, fine-tuning, TAO; "up to 10x lower cost" claimed — internal benchmarks; beta). Retrievers are exposed as tools; MCP support arrived across 2025–26.
- **Snowflake:** **Cortex Agents** orchestrate Cortex Analyst (structured) + Cortex Search (unstructured) + code execution + custom tools (stored procedures/UDFs), with REST API, threads, MCP connectors (Jira, Salesforce), Teams integration, and model choice across Claude/GPT/Grok/Gemini with an "auto" selector; three-step plan→tool→reflect loop ([docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)).
- **Reality check:** early users found Cortex Agents to be thin sequencing rather than real agency — "It's just a Cortex Analyst and a Cortex Search being used one at a time... calling this 'agents' doesn't seem like the right term" ([r/snowflake](https://www.reddit.com/r/snowflake/comments/1ioo679/snowflake_cortex_agents_anybody_is_using_it/mcnyvvu/)). On Databricks, agents are more programmable but bound to Model Serving endpoints, whose concurrency/cold-start economics worry users building streaming chat ([r/databricks](https://www.reddit.com/r/databricks/comments/1i624w8/databricks_for_building_agents/)). Both platforms' retrieval services are consumable from external agent stacks via REST/MCP, but then you pay egress, latency, and per-service throttles (20 QPS on Cortex Search) — the platform is designed to keep the agent *inside*.

---

## Strengths (steelman)

1. **Governance inheritance is real and unmatched.** Retrieval objects are first-class governed objects (Unity Catalog / Snowflake RBAC); ACLs, audit, lineage, encryption, and residency come for free. For regulated enterprises this eliminates the single hardest part of shipping RAG. ("Every customer request... is logically isolated, authenticated, and authorized" — Databricks docs.)
2. **Zero-ETL freshness from the system of record.** Delta Sync (CDF-based incremental sync, seconds-latency continuous mode) and Cortex Search's dynamic-table refresh keep indexes derived from canonical tables without a bespoke pipeline — genuinely better than the copy-to-Pinecone status quo for warehouse-resident data.
3. **Cortex Search's default retrieval stack is opinionated and good:** hybrid vector+lexical with query expansion, cross-encoder reranking, and signal boosts *by default* — a stronger out-of-box stack than most DIY RAG. Internal figures: NDCG@10 0.22 (lexical) → 0.59 (hybrid+reranker) ([engineering blog](https://www.snowflake.com/engineering-blog/cortex-search-and-retrieval-enterprise-ai/)).
4. **Credible open research.** Arctic-Embed models are Apache-2.0, small, and were SOTA-for-size on MTEB Retrieval ([arXiv 2405.05374](https://arxiv.org/abs/2405.05374)); Databricks' long-context RAG study (2,000+ experiments, 13 LLMs) is one of the more useful public RAG evaluations ([blog](https://www.databricks.com/blog/long-context-rag-performance-llms)).
5. **Evaluation is a first-class product on Databricks.** Agent Evaluation / MLflow 3 judges, review app, synthetic eval sets, and Agent Bricks' auto-generated task-specific benchmarks push eval-driven development further than any general-purpose OSS RAG framework does.
6. **Enterprise scale envelopes:** 320M–1B+ vectors per endpoint (Databricks), 400M rows per service (Snowflake), serving isolated from analytical compute (Snowflake's multi-tenant serving tier).

---

## Issues & failure modes

### performance-cost

**PC-1. Always-on retrieval infrastructure billing + opaque cost attribution (Databricks).** — **Severity: major** — **Label: documented-recurring**
Vector Search endpoints are provisioned, always-on units; continuous sync additionally provisions a streaming cluster billed continuously (docs: "higher costs since a compute cluster is provisioned to run the continuous sync streaming pipeline"). Community forum threads report unexpected vector-search spend ("Cost Analysis for Databricks Compute", Aug 2024) and inability to attribute Vector Search / Model Serving costs to projects ([community forum search](https://community.databricks.com/t5/forums/searchpage/tab/message?q=vector+search+cost); [r/databricks cost-attribution thread](https://www.reddit.com/r/databricks/comments/1k4yqhg/best_practice_for_unified_cloud_cost_attribution/)). Public pricing for Vector Search is not even published on the pricing page — "Request a pricing quote" ([pricing page](https://www.databricks.com/product/pricing)).

**PC-2. Cortex Search charges for data-at-rest, not queries — 6.3 credits/GB-month serving.** — **Severity: major** — **Label: documented-recurring**
Serving cost accrues "whenever the service is running, regardless of query volume" at 6.3 credits per GB/month of *uncompressed* indexed data (docs example: 10M modest rows ≈ 256.5 credits/mo ≈ $500–$1,000+/mo at list credit prices, before warehouse/embedding/storage costs). Cost gotchas documented by Snowflake itself: schema changes and `CREATE OR REPLACE` on the source table silently trigger **full re-embedding of the entire corpus** ([costs docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs)).

**PC-3. AI features flipped from free preview to pay-as-you-go tokens with weak spend controls (Databricks, July 2026).** — **Severity: major** — **Label: single-anecdote** (pricing change itself is official; the failure report is one practitioner)
On July 8, 2026 Genie products moved to token-based DBU billing. A practitioner documented a test session escalating from $6 to $30+ unexpectedly, notes Databricks acknowledges delayed usage reporting, and that budget *blocking* (vs alerting) was unavailable ([Medium/Dev Genius, July 2026](https://medium.com/dev-genius/databricks-ai-agent-genie-code-is-no-longer-free-now-you-have-to-pay-as-you-go-1d40bf8a4aad); [HN](https://news.ycombinator.com/item?id=48880078)). Pattern risk: the data-cloud RAG value proposition was seeded on free previews whose steady-state economics only appear post-adoption.

### abstraction-design

**AD-1. The managed pipeline starts *after* the hard part: parsing and chunking are DIY on both platforms.** — **Severity: major** — **Label: documented-recurring**
Neither Vector Search nor Cortex Search offers managed document parsing/chunking control as part of the index; Snowflake community answer: "you would use something like langchain for chunking" in UDFs ([r/dataengineering](https://www.reddit.com/r/dataengineering/comments/1eqqdx0/snowflake_genai_pipeline_pricing/lhvdi2p/)); Databricks requires user-built Spark/DLT chunking pipelines feeding a Delta table. The platforms manage embedding+index+serving but leave the largest retrieval-quality lever (chunking strategy) outside the abstraction — while marketing "no pipeline to create and maintain."

**AD-2. Rigid index abstractions: one-way doors and single-column scope.** — **Severity: major** — **Label: documented-recurring**
Databricks: "It is not possible to convert a self-managed embedding index to a Databricks-managed index"; source-table schema changes are "not supported unless you rebuild the index" ([docs](https://docs.databricks.com/aws/en/generative-ai/vector-search)). Snowflake: one search column per service (concatenation workaround pushed onto users, [r/snowflake](https://www.reddit.com/r/snowflake/comments/1k68tsm/looking_for_fast_fuzzy_native_search_on_snowflake/morq3ii/)); no cloning of services; zero-data-retention tables prohibited as sources (docs).

**AD-3. Text-to-SQL accuracy is bought with a hand-curated semantic-model tax that does not scale to real schemas.** — **Severity: major** — **Label: documented-recurring**
Cortex Analyst's 90%+ claim is conditional on well-built semantic models with verified queries (Snowflake's own AMA: "accuracy... relies on well-defined semantic models", [r/snowflake AMA](https://www.reddit.com/r/snowflake/comments/1iuvt80/snowflake_official_ama_march_13_w_dash_desai_ama/mhmp831/)). A practitioner on Databricks Genie: works on "~20 tables and a well thought out and documented data model... I have hundreds of tables designed by several different teams... if I had a nice, organized data model I wouldn't need an AI assistant" ([HN comment](https://news.ycombinator.com/item?id=45738481)). Docs-documented Analyst limits: no access to previous query results in multi-turn; degrades on long conversations and intent shifts ([Analyst docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)).

### retrieval-quality

**RQ-1. Fixed, untunable fusion and missing reranking on Databricks.** — **Severity: major** — **Label: architectural-inference** (from documented constants)
Hybrid search fuses BM25+ANN with a hard-coded RRF k=60; hybrid queries cap at 200 results; there is no built-in cross-encoder reranker (users must bolt on their own via model serving). Docs also steer users *away* from hybrid for cost ("hybrid search consumes roughly twice as many resources as ANN") ([overview](https://docs.databricks.com/aws/en/generative-ai/vector-search), [best practices](https://docs.databricks.com/aws/en/generative-ai/vector-search-best-practices)). Compared with Cortex Search's default reranked hybrid stack, Databricks ships a weaker out-of-box relevance pipeline whose knobs are welded shut.

**RQ-2. Black-box relevance with no user-visible scoring control (Snowflake).** — **Severity: minor** — **Label: single-anecdote**
Cortex Search exposes no tunable fusion weights, no score-threshold semantics, and the reranker is opaque; a StackOverflow user reports the service "returning things with 0 relevance" with no way to diagnose or gate results ([SO 79896505](https://stackoverflow.com/questions/79896505/cortex-search-returning-thing-with-0-relevance), score 3, unanswered). Custom ranking signals (e.g. popularity boosts) required non-obvious workarounds ([SO 79524584](https://stackoverflow.com/questions/79524584/)).

### data-processing

**DP-1. Index freshness is coupled to cost, not truth: TARGET_LAG and triggered-sync gaps.** — **Severity: major** — **Label: architectural-inference** (from documented mechanics)
Snowflake freshness follows dynamic-table refresh economics — tighter TARGET_LAG means more warehouse spend; incremental refresh only with primary keys, otherwise full re-materialization. Databricks continuous sync means paying for an always-running streaming cluster; the cheap option (triggered sync) makes staleness an operational decision. On storage-optimized endpoints each sync "partially rebuilds the index." In both systems, the sync knob is fundamentally a billing knob, and the default failure mode is a silently stale index.

### production-ops

**PO-1. Hard serving ceilings: 20 QPS per Cortex Search service; QPS plateaus and 429s on Databricks endpoints.** — **Severity: major** — **Label: documented-recurring**
Cortex Search throttles at 20 QPS per service ([overview docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)) — fine for internal chatbots, disqualifying for customer-facing search without sharding across services. Databricks documents throughput plateauing (~30 QPS as indexes span multiple vector search units) and 429 errors near capacity requiring client backoff logic ([best practices](https://docs.databricks.com/aws/en/generative-ai/vector-search-best-practices)). Batch/offline retrieval is also awkward: a user doing 50k similarity lookups found no sane batch path that returns scores ([r/databricks](https://www.reddit.com/r/databricks/comments/1k79wse/vector_index_batch_similarity_search/)).

**PO-2. Deep lock-in: indexes, embeddings, eval assets, and agents are non-portable platform objects.** — **Severity: major** — **Label: architectural-inference**
Neither platform's index is exportable; embeddings are recomputable but sync machinery, ACL model, semantic models (Snowflake YAML/Semantic Views vs Databricks Genie spaces — mutually incompatible), eval suites (Agent Evaluation/MLflow judges vs Cortex-internal), and agent definitions are all platform-shaped. Regional availability adds a second bind: Cortex Analyst is native in only ~9 regions, with "cross-region inference" (data leaving region) as the escape hatch — quietly contradicting the data-sovereignty pitch ([Analyst docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)).

### evaluation-observability

**EO-1. Benchmark claims are almost entirely self-reported, and the two vendors benchmark against each other.** — **Severity: major** — **Label: documented-recurring**
Cortex Analyst's "90%+ accuracy, ~2x GPT-4o, +14% vs competing text-to-SQL" comes from "our comprehensive internal benchmark suite" ([Snowflake engineering blog](https://www.snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes/)); Cortex Search's NDCG numbers are internal with no published datasets; Databricks markets Genie as "The best Text2SQL AI System" and Agent Bricks' "up to 10x lower cost" from internal evals ([Agent Bricks blog](https://www.databricks.com/blog/introducing-agent-bricks)). Arctic-Embed MTEB numbers are the honorable exception (public leaderboard). No credible independent head-to-head of Cortex Search vs Vector Search vs specialized stacks was found in this research — a striking evidence vacuum for products this widely deployed.

**EO-2. Eval tooling churn on Databricks: Agent Evaluation deprecated into MLflow 3 mid-lifecycle.** — **Severity: minor** — **Label: documented-recurring**
Teams that built on Agent Evaluation (GA'd ~2024) are now pointed at migration guides: "Databricks recommends using MLflow 3 for evaluating and monitoring AI apps," with MLflow-2-based Agent Evaluation superseded ([docs](https://docs.databricks.com/aws/en/generative-ai/agent-evaluation/)). Typical of the platform's preview→GA→reorg cadence; eval assets are not stable ground.

### agentic-integration

**AI-1. "Agents" are thin orchestration over two fixed tools (Snowflake); production monitoring for the loop is missing.** — **Severity: major** — **Label: single-anecdote** (multiple corroborating anecdotes, small n)
Early adopters: "I tried what they provided in their quickstart... it's really not good... It's just a Cortex Analyst and a Cortex Search being used one at a time"; another: Agents can't work well until Analyst has production UI/monitoring to refine semantic models — "the out of the box Streamlit apps aren't there yet to support performance monitoring" ([r/snowflake thread](https://www.reddit.com/r/snowflake/comments/1ioo679/snowflake_cortex_agents_anybody_is_using_it/)). Docs also restrict where agents can be called from (no warehouse-runtime Streamlit; container runtime required) ([Cortex Agents docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)).

**AI-2. Agent serving economics constrain agentic patterns (Databricks).** — **Severity: minor** — **Label: single-anecdote**
Agents deploy on Model Serving endpoints sized by concurrency; a user notes streaming responses hold slots so "I don't want a super expensive model serving compute that can only stream to 64 persons at the same time," while docs simultaneously warn to "avoid model endpoints that scale to zero" because cold starts "delay responses by several minutes" ([r/databricks](https://www.reddit.com/r/databricks/comments/1i624w8/databricks_for_building_agents/), [best practices](https://docs.databricks.com/aws/en/generative-ai/vector-search-best-practices)). Result: pay for idle or accept multi-minute cold starts.

### security-governance

**SG-1. Governance granularity stops at the table/index: no column-level permissions on Databricks vector indexes; document-level ACL filtering is app-layer DIY.** — **Severity: major** — **Label: documented-recurring**
Databricks docs state column-level permissions are unavailable on Vector Search and that applications with ACL requirements must implement them at the application layer ([docs](https://docs.databricks.com/aws/en/generative-ai/vector-search)). The core sales pitch is "governance for free," but per-document/per-user retrieval authorization — the thing RAG actually needs — is the customer's problem on both platforms (Cortex Search offers metadata filters, but mapping user entitlements to filters is user-built).

### dx-docs

**DX-1. Capability sprawl and preview-quality surface area.** — **Severity: minor** — **Label: documented-recurring**
Snowflake's own community had to disambiguate "Cortex" (Search vs Analyst vs Agents vs Code) ([HN](https://news.ycombinator.com/item?id=47428972)); Cortex Search initially couldn't index staged documents at all ("support for stages isn't available quite yet" — Snowflake employee, [r/snowflake](https://www.reddit.com/r/snowflake/comments/1fe7dy3/cortex_search_service/lnrk9je/)); Databricks' SQL `vector_search()` function shipped without returning similarity scores (later added), forcing users back to the REST path ([r/databricks](https://www.reddit.com/r/databricks/comments/1k79wse/vector_index_batch_similarity_search/)). Both platforms ship RAG features as rolling previews with region gaps.

---

## Community sentiment over time

- **2023–early 2024 (honeymoon):** enthusiasm about eliminating the vector-DB sidecar; "Why use a vector DB when Snowflake can remove that headache for you?" ([r/snowflake](https://www.reddit.com/r/snowflake/comments/1hkwylt/thoughts_on_my_setup_for_rag_using_snowflake_as_a/m3iohaz/)); Databricks advocates pitch "no pipeline to create and maintain" ([r/databricks](https://www.reddit.com/r/databricks/comments/1fekspu/databricks_mosaic_vector_search_vs_qdrant/)).
- **2024–2025 (friction surfaces):** cost-analysis and cost-attribution threads on the Databricks forum; Cortex Analyst praised for accuracy but flagged as "pretty expensive at 67 credits/1000 questions" with users pointed to Genie as the cheaper rival ([r/snowflake](https://www.reddit.com/r/snowflake/comments/1iwb7jl/whats_your_experience_with_cortex_analyst/)); Cortex Agents quickstarts judged "really not good" by early testers; batch and filtering gaps drive workaround threads.
- **2025–2026 (monetization + consolidation):** Agent Bricks (June 2025) reframes Databricks around auto-optimized agents; Snowflake pushes Cortex Agents + MCP + "Snowflake Intelligence." July 2026: Databricks ends free Genie usage, and the first cost-surprise postmortems appear ([Medium](https://medium.com/dev-genius/databricks-ai-agent-genie-code-is-no-longer-free-now-you-have-to-pay-as-you-go-1d40bf8a4aad)). Notably, **HN discussion of both vendors' RAG stacks is thin** (single-digit-point stories) — sentiment lives in vendor-adjacent forums, which skews visible feedback positive.

---

## Benchmarks & third-party evaluations

- **Arctic-Embed / 2.0** ([2405.05374](https://arxiv.org/abs/2405.05374), [2412.04506](https://arxiv.org/abs/2412.04506)): self-reported but on the public MTEB leaderboard — the most verifiable claim in either stack. Apache-2.0 models from 22M–334M params claiming SOTA-for-size retrieval; 2.0 adds multilingual + MRL compression.
- **Cortex Search internal evals** ([engineering blog](https://www.snowflake.com/engineering-blog/cortex-search-and-retrieval-enterprise-ai/)): NDCG@10 0.22 → 0.49 (vector) → 0.53 (hybrid) → 0.59 (hybrid+reranker); customer hit-rate 0.79→0.86 with signals. No datasets released, no competitor comparison — internal only.
- **Cortex Analyst** ([behind the scenes](https://www.snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes/)): 90%+ accuracy, ~2x GPT-4o-raw-schema, +14% vs competing text-to-SQL — explicitly "our comprehensive internal benchmark suite." One rare independent datapoint: a Finnish bachelor's thesis evaluated Cortex Analyst positively but flagged cost (67 credits/1k questions) ([Theseus record via r/snowflake](https://www.theseus.fi/handle/10024/873561)) — low-weight evidence, cited as such.
- **Databricks long-context RAG study** ([blog](https://www.databricks.com/blog/long-context-rag-performance-llms)): 2,000+ experiments, 13 LLMs, 4 datasets; found generation quality peaks well before recall saturates (Llama-3.1-405b degrades past 32k, GPT-4-0125 past 64k) with model-specific failure modes — genuinely useful, though it evaluates LLMs, not Databricks' own retrieval product.
- **Agent Bricks** ([launch blog](https://www.databricks.com/blog/introducing-agent-bricks)): "higher quality and up to 10x lower cost" vs prompt-optimized proprietary LLMs — internal, launch-marketing evidence tier.
- **Gap:** no credible independent, reproducible benchmark of Cortex Search or Mosaic Vector Search retrieval quality vs specialized stacks (Vespa, Elastic, Turbopuffer, pgvector, Pinecone) was located. For platforms holding this much enterprise RAG traffic, the third-party evaluation vacuum is itself a finding.

---

## Lessons for a next-generation framework

1. **Governance inheritance is the killer feature to replicate, but at document granularity.** Both platforms win deals on inherited ACLs, then punt per-document/per-user authorization to the app layer. A next-gen framework should make entitlement-aware retrieval (user → allowed-docs predicate pushdown) a first-class primitive, not a metadata-filter exercise.
2. **Sync-from-source beats copy-to-sidecar — keep it, but decouple freshness from billing.** CDF/dynamic-table incremental sync is the right model; the failure is that freshness is priced as always-on streaming compute (Databricks) or warehouse refresh spend (Snowflake), so teams choose staleness. Freshness SLOs should be declarative and cheap by architecture (log-tailing, not cluster-parking).
3. **Own the whole pipeline or don't claim to.** Both stacks manage embed→index→serve but leave parsing/chunking DIY — the step with the highest quality leverage. A next-gen framework must treat chunking/parsing as versioned, evaluable pipeline stages inside the abstraction.
4. **Opinionated defaults + open knobs.** Cortex Search proves reranked hybrid-by-default lifts quality massively (0.22→0.59 NDCG internal); Databricks proves welded-shut knobs (fixed RRF k=60, no reranker) frustrate experts; Snowflake's opacity (unexplainable 0-relevance results) frustrates everyone. Ship the strong default *and* the tuning surface *and* score transparency.
5. **Retrieval must serve both online (high QPS, low latency) and offline/batch (50k joins) modes.** Hard 20 QPS throttles and no batch API are artifacts of serving-tier design, not of retrieval itself. A next-gen framework should compile the same index to both an online endpoint and a set-oriented batch operator.
6. **Evaluation claims need public, reproducible grounding.** The entire category runs on internal benchmarks. Auto-generated task evals (Agent Bricks' real innovation) plus published, replayable benchmark artifacts would be a differentiator — and a trust requirement.
7. **Portability is the unpriced risk.** Indexes, semantic models, eval suites, and agents are all platform-shaped and non-exportable, and pricing flipped after adoption (Genie, July 2026). Next-gen designs should keep index formats, semantic layers, and eval assets in open, exportable representations so retrieval quality isn't hostage to a billing-model change.
8. **Text-to-SQL and text-to-docs converge on the same lesson: the semantic layer is the product.** Both vendors' accuracy depends on hand-curated semantic models that don't scale to hundreds of messy tables. Automating semantic-model construction and maintenance from usage/lineage is the open problem worth solving.

---

## Sources

Official documentation:
- https://docs.databricks.com/aws/en/generative-ai/vector-search — Mosaic AI Vector Search overview (index types, HNSW, RRF k=60, limits, no column-level perms)
- https://docs.databricks.com/aws/en/generative-ai/create-query-vector-search — Delta Sync modes, continuous-sync streaming cluster, schema-change rebuild
- https://docs.databricks.com/aws/en/generative-ai/vector-search-best-practices — latency/QPS envelopes, 429s, hybrid 2x cost, scale-to-zero warning
- https://docs.databricks.com/aws/en/generative-ai/agent-evaluation/ — Agent Evaluation, MLflow 3 migration
- https://www.databricks.com/product/pricing — no published Vector Search rates
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview — hybrid architecture, TARGET_LAG, 400M rows, 20 QPS
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs — 6.3 credits/GB-mo serving, full re-embed gotchas
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst — semantic views, multi-turn limits, 9-region availability
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents — orchestration, MCP, runtime restrictions, pricing components

Vendor engineering/research:
- https://www.snowflake.com/engineering-blog/cortex-search-and-retrieval-enterprise-ai/ — Cortex Search internals + internal NDCG numbers
- https://www.snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes/ — Analyst multi-agent pipeline + internal accuracy claims
- https://www.databricks.com/blog/introducing-agent-bricks — Agent Bricks launch (June 11, 2025)
- https://www.databricks.com/blog/long-context-rag-performance-llms — long-context RAG study
- https://arxiv.org/abs/2405.05374 — Arctic-Embed
- https://arxiv.org/abs/2412.04506 — Arctic-Embed 2.0
- https://www.snowflake.com/blog/snowflake-acquires-neeva-to-accelerate-search-in-the-data-cloud-through-generative-ai/ — Neeva acquisition (May 2023)
- https://www.databricks.com/company/newsroom/press-releases/databricks-raising-series-k-investment-100-billion-valuation — Series K >$100B (Aug 2025)

Community / independent:
- https://www.reddit.com/r/databricks/comments/1k79wse/vector_index_batch_similarity_search/ — batch retrieval friction, SQL function score gap
- https://www.reddit.com/r/databricks/comments/1fekspu/databricks_mosaic_vector_search_vs_qdrant/ — data-gravity default rationale
- https://www.reddit.com/r/databricks/comments/1k4yqhg/best_practice_for_unified_cloud_cost_attribution/ — cost attribution pain
- https://www.reddit.com/r/databricks/comments/1i624w8/databricks_for_building_agents/ — model-serving concurrency/cold-start economics
- https://www.reddit.com/r/snowflake/comments/1iwb7jl/whats_your_experience_with_cortex_analyst/ — Analyst cost (67 credits/1k questions), Theseus thesis pointer
- https://www.reddit.com/r/snowflake/comments/1ioo679/snowflake_cortex_agents_anybody_is_using_it/ — "wouldn't call that agents"
- https://www.reddit.com/r/snowflake/comments/1k68tsm/looking_for_fast_fuzzy_native_search_on_snowflake/ — single-search-column limitation
- https://www.reddit.com/r/snowflake/comments/1fe7dy3/cortex_search_service/ — no staged-document support at launch
- https://www.reddit.com/r/dataengineering/comments/1eqqdx0/snowflake_genai_pipeline_pricing/ — DIY chunking guidance
- https://community.databricks.com/t5/forums/searchpage/tab/message?q=vector+search+cost — forum cost threads
- https://stackoverflow.com/questions/79896505/cortex-search-returning-thing-with-0-relevance — 0-relevance results, unanswered
- https://news.ycombinator.com/item?id=45738481 — Genie vs realistic enterprise schemas
- https://news.ycombinator.com/item?id=48880078 — Genie pricing change discussion
- https://medium.com/dev-genius/databricks-ai-agent-genie-code-is-no-longer-free-now-you-have-to-pay-as-you-go-1d40bf8a4aad — Genie pay-as-you-go postmortem (July 2026; single-practitioner source)
- https://www.theseus.fi/handle/10024/873561 — independent bachelor's thesis on Cortex Analyst (low-weight, cited via Reddit; direct fetch 403)
- https://www.businesswire.com/news/home/20240228398564/en/ — Ramaswamy named Snowflake CEO
