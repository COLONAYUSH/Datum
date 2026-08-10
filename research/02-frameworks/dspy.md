# DSPy (and the program-optimization school)

> Autopsy date: 2026-08-05. Target: DSPy ("programming — not prompting — language models"), Stanford NLP lineage, plus the surrounding program-optimization school (MIPROv2, GEPA, SIMBA, GRPO/Arbor; sibling projects ColBERT and STORM). All claims below carry evidence pointers; each issue is labeled `documented-recurring`, `single-anecdote`, or `architectural-inference`.

---

## Identity & adoption

| Signal | Value (as of Aug 2026) | Source |
|---|---|---|
| Maintainer | Stanford NLP group (Omar Khattab et al.); heavy Databricks involvement (Khattab affiliation, Databricks blog/adoption) | github.com/stanfordnlp/dspy; databricks.com/blog/dspy-databricks |
| License | MIT | GitHub API |
| Created | Jan 2023 (evolved from the earlier DSP "Demonstrate-Search-Predict" library) | GitHub API (`created_at: 2023-01-09`) |
| Stars / forks / open issues | 36,635 / 3,167 / 647 open issues | GitHub API, 2026-08-05 |
| Contributors / downloads | 439+ contributors, 7.5M+ monthly PyPI downloads | dspy.ai front page |
| Current version | 3.3.0 (2026-08-03); 3.0.0 landed 2025-08-12 | GitHub releases API |
| Named production adopters | Databricks, Shopify, Dropbox, AWS, JetBlue, Replit, Nous Research | dspy.ai front page |
| Research momentum | GEPA optimizer paper accepted ICLR 2026 (oral); RLM (Recursive Language Models) research Dec 2025 | arxiv.org/abs/2507.19457; dspy.ai |
| Sibling projects | ColBERT/ColBERTv2 (late-interaction retrieval, same lab); STORM (30.8k stars, DSPy-powered report writer, last pushed Sep 2025) | GitHub API for stanford-oval/storm |

Adoption paradox, stated by its own advocates: ~4.7M monthly downloads vs LangChain's ~222M at the time of the widely-discussed post "If DSPy is so great, why isn't anyone using it?" (227 points, 120 comments on HN, Mar 2026) — real but niche adoption despite three years of strong word-of-mouth. (skylarbpayne.com/posts/dspy-engineering-patterns/; news.ycombinator.com/item?id=47490365)

DSPy is not primarily a RAG framework: it is a **program-and-optimize framework** in which RAG is one workload. That framing is essential to both its strengths and its failure modes below.

---

## Retrieval-pipeline architecture

DSPy models an LLM system as a **Program** = composition of **Modules**, each parameterized by a **Signature** (typed input→output contract, e.g. `"context, question -> answer"`), executed through an **Adapter** (ChatAdapter/JSONAdapter/XMLAdapter/BAMLAdapter) against an **LM** (a LiteLLM-backed client), and improved offline by an **Optimizer** ("teleprompter") against a **Metric** over a trainset. The prompt itself is a compiled artifact you are not supposed to hand-edit.

Stage-by-stage for RAG:

- **Ingestion / parsing / chunking: absent by design.** DSPy has no document loaders, no parsers, no chunkers, no metadata model. The official RAG tutorial downloads a *pre-chunked* corpus from HuggingFace and truncates each document to 6,000 characters (`text[:max_characters]`) as its entire "ingestion" step. (dspy.ai/tutorials/rag/)
- **Embedding / indexing:** `dspy.Embedder` (any LiteLLM embedding model) + `dspy.retrievers.Embeddings`, an **in-memory** index (FAISS if installed, brute-force below a threshold). No persistence, incremental update, or freshness story; it is a teaching/eval utility, not an index. (dspy.ai/tutorials/rag/)
- **Retriever integrations: removed.** DSPy 2.x shipped `dspy.Retrieve` plus ~14 community retrieval clients (ChromadbRM, QdrantRM, MilvusRM, FaissRM, Neo4jRM, AzureAISearchRM, SnowflakeRM, LancedbRM, RAGatouilleRM, WatsonDiscovery, etc.). All were deleted in PR #8073 (merged 2025-06-11, shipped in 3.0) "due to the challenges of maintaining them reliably"; official guidance is "migrate to custom code (or use Tool/MCP integrations)". Retrieval is now explicitly **bring-your-own**: "As far as DSPy is concerned, you can plug in any Python code for calling tools or retrievers." (github.com/stanfordnlp/dspy/pull/8073; 3.0.0 release notes; dspy.ai/tutorials/rag/)
- **Query handling:** where DSPy genuinely differentiates. Query formulation is itself a Module (e.g. a `ChainOfThought("context, question -> search_query")` per hop in multi-hop RAG), so the optimizer can rewrite the *query-generation prompt* and its few-shot demos against a downstream answer metric. Multi-hop composition is user-written Python in `forward()`.
- **Rerank:** nothing built in. ColBERTv2 (same lab) exists as a hosted demo client (`dspy.ColBERTv2(url='http://20.102.90.50:2017/wiki17_abstracts')`) — a raw-IP demo server with a long history of outages (see Issues). RAGatouille integration was removed with the other RMs.
- **Synthesis:** `dspy.Predict` / `ChainOfThought` / `ReAct` / `Refine` / `BestOfN` under adapters that enforce structured outputs, with fallback to native provider structured-output modes.
- **Optimization (the actual product):** LabeledFewShot, BootstrapFewShot(+RandomSearch), COPRO, MIPROv2 (Bayesian search over instructions + bootstrapped demos), SIMBA, **GEPA** (2025, reflective/genetic-Pareto prompt evolution), BootstrapFinetune and GRPO via the Arbor RL library, Ensemble/BetterTogether. (dspy.ai; 3.0.0 release notes)
- **Observability:** native MLflow 3.0 integration (tracing, optimizer tracking) added in the 2.6→3.0 arc; usage tracking, callbacks, streaming. (3.0.0 release notes)

Net: DSPy owns the **prompt/program layer** of RAG (query generation, synthesis, and their joint optimization) and deliberately abandons the **data layer** (ingestion, indexing, retrieval infrastructure, freshness, ACLs).

---

## Agentic integration

- Built-in agent modules: `dspy.ReAct` (tool loop), `dspy.CodeAct`, `dspy.PythonInterpreter`; `dspy.ToolCalls` with native tool-calling; MCP servers and LangChain tools supported out of the box since 3.0; async + `Module.batch` for concurrency; RLM (Recursive Language Models, Dec 2025) for exploring large contexts with code. (3.0.0 release notes; dspy.ai)
- The optimizer story extends to agents: GEPA/SIMBA are pitched for "agentic/long-horizon tasks" where per-step labels don't exist and feedback is textual. (3.0.0 release notes)
- **Friction:** practitioners report the agent loop is the weakest module. "Their out of the box agent loop has been a joke for the longest time… it's night and day when trying to get something done with pydantic-ai" (HN user ndr, thread 47490365). Issue #10072 documents ReAct making an unconditional extra `extract` LLM call after `finish()` (N+1 round-trip overhead). Memory/session state is not a first-class concept (users bring `dspy.History` or external stores).
- **Deeper architectural critique** (Ben Anderson, "Contra DSPy and GEPA", Dec 2025): DSPy's optimizer machinery presumes *module locality* — you can improve one module by inspecting its local I/O. In agent loops "ALL the prompts are relevant at ALL the steps" (system prompt + every tool description influence every decision), so per-module prompt optimization "combines things that didn't really go together"; he suggests whole-trajectory feedback instead. (benanderson.work/blog/contra-dspy-gepa/)

---

## Strengths (steelman)

1. **The right thesis, stated first and clearly.** Prompt strings are untyped, brittle, model-coupled parameters; DSPy replaces them with typed Signatures + compiled prompts. Even critics concede teams reinvent this: "most complex AI systems contain an ad hoc, informally-specified, bug-ridden implementation of half of DSPy" ("Khattab's Law", skylarbpayne.com). HN thread 47490365 is full of people admitting they built half-baked internal DSPys.
2. **Evidenced optimizer gains, improving over time.** MIPROv2 produces measurable lifts on labeled benchmarks; GEPA (ICLR 2026 oral) reports +10% average over MIPROv2, +6% (up to 20%) over GRPO with up to 35× fewer rollouts — a real answer to the "optimization is too expensive" critique. (arxiv.org/abs/2507.19457)
3. **Model portability.** Compiled programs re-optimize per model, decoupling task definition from any one LLM's prompt dialect — repeatedly cited by adopters as the concrete win (e.g. dbreunig.com "Let the Model Write the Prompt"; JetBlue/Databricks usage).
4. **Eval-first discipline.** DSPy structurally forces a trainset + metric before you ship — the single practice most RAG teams skip; its advocates argue this, not the optimizer, is the durable value.
5. **Research pipeline into practice.** Same lab produced ColBERT/ColBERTv2 (late-interaction retrieval standard), STORM (30.8k stars), Assertions (arXiv 2312.13382), GRPO-for-programs (Arbor), RLM. Few frameworks have this cadence.
6. **Honest scope-cutting.** Deleting unmaintained community retrievers (PR #8073) and betting on MCP/tools is arguably correct long-term — better no integration than a bitrotted one.

---

## Issues & failure modes

### data-processing

- **[DP-1] No ingestion/parsing/chunking layer at all; the data half of RAG is out of scope.** The flagship RAG tutorial's ingestion is downloading a pre-chunked HF corpus and truncating documents at 6,000 chars. Structure loss, tables, PDFs, metadata, document boundaries — all the user's problem. Severity: **critical** for anyone evaluating DSPy *as* a RAG framework. Label: **architectural-inference** (from official docs, so effectively documented). Evidence: dspy.ai/tutorials/rag/; issue #494 "dspy pdf input?" (closed, out of scope).

### retrieval-quality

- **[RQ-1] Retrieval integrations were deleted wholesale in 3.0; retrieval is now 100% BYO.** PR #8073 (merged 2025-06-11) removed 14 retriever clients (Chromadb, Qdrant, Milvus, FAISS, Neo4j, AzureAISearch, Snowflake, LanceDB, RAGatouille, Watson, You, MyScale, Clarifai, Falkordb) "due to the challenges of maintaining them reliably." Anyone on `QdrantRM` etc. was told to "migrate to custom code." Out-of-box retrieval today is an in-memory embeddings toy or a flaky demo ColBERT server. Severity: **major**. Label: **documented-recurring** (PR #8073, 3.0.0 release notes, issue #1739 "dspy.RM/retrieve refactor" still open).
- **[RQ-2] The default docs/quickstart retriever is a hosted ColBERTv2 demo at a raw IP that is chronically down or overloaded**, so tutorials and first-run experiences fail. Severity: **minor** (demo infra) but disproportionate first-impression damage. Label: **documented-recurring**. Evidence: issues #8946 "[Bug] ColBERT is down" (open), #7966 "wiki17_abstracts is overloaded", #9116, #9178 `KeyError: 'topk'`, #633.
- **[RQ-3] No reranking, hybrid search, or retrieval-quality defaults.** DSPy optimizes the prompts *around* retrieval but ships no lexical+dense hybrid, no reranker, no retrieval eval helpers — ironic given the lab invented ColBERT. Severity: **major**. Label: **architectural-inference**.

### abstraction-design

- **[AD-1] Compiled prompts are opaque and hard to extract, creating lock-in fear.** "When I discovered that none of my actual optimized prompts were extractable, I got cold feet and went a different route… treating the underlying output prompt as an opaque blob doesn't [make sense]" (HN 47490365, TheTaytay; blog author sbpayne: "one of my biggest gripes… takes 'the prompt is a parameter' concept a bit too far"). Recurring GitHub asks: #8952 "Is there a way to recover the prompt generated by DSPy?", #9713 "[Feature] Cleaner API specifically for getting generated prompt", #1308 "How to view the optimized prompt?". A community plugin (dspy-community/dspy-template-adapter) exists to bridge the gap. The rival `promptolution` framework (arXiv 2512.02840) markets "framework-agnostic prompt strings" as its differentiator — an implicit indictment. Severity: **major**. Label: **documented-recurring**.
- **[AD-2] Convoluted / unfamiliar abstractions; framework wants to own your control flow.** "Non-sensical, convoluted abstractions… reminds me very much of LangChain" (HN 41214178, NeutralCrane); "DSPy seems unnecessarily convoluted, inelegant or am I just stupid?" (HN 42350799); "they try to do 'too much' by taking over the control flow of your code and running autotuning everywhere… hard to find scenarios where its potential benefits outweigh its costs" (HN 40556135, lmeyerov, enterprise platform builder). Even a sympathetic core contributor conceded "the abstractions could be cleaner… due to the evolution it has undergone" (HN 41214178, curious_cat_163). Ergonomics: "you have to bundle input+output signatures and everything is dynamically typed… annoying in codebases that have type annotations everywhere" (HN 47490365, ndr). Severity: **major**. Label: **documented-recurring**.
- **[AD-3] Hard coupling to LiteLLM imports its churn and bugs.** The 2.5 rewrite moved all model access onto LiteLLM; provider quirks now surface as DSPy bugs (issue #8958 "Responses API always falls back to JSON mode which breaks with web search"; #1539 35-comment thread of adapter/parse failures "Expected dict_keys(['answer']) but got dict_keys([])"; #1570 LiteLLM router gaps). Severity: **minor-to-major**. Label: **documented-recurring**.

### evaluation-observability

- **[EO-1] The whole value proposition is gated on having a labeled trainset + automated metric — which most product teams don't have and can't keep current.** "The magic sauce seems to be, at every turn, '…if you have some well defined metric to optimize on.' And that's not really a given, in reality" (HN 41214178, isoprophlex). "You have to really think carefully to build up a training and evaluation dataset… As soon as you move the goalposts you also have to update the dataset. This can actually get in the way of moving fast" (HN 47490365, memothon). For open-ended RAG/chat, metric design is the hard unsolved part, and DSPy pushes it entirely onto the user (LLM-as-judge metrics then become a second optimization surface with their own drift). Severity: **critical** (it bounds applicability). Label: **documented-recurring**.
- **[EO-2] Optimizer runs are a black box with no cost/dry-run preview.** Users asked for optimization dry-runs to estimate spend as early as issue #397; MIPRO runs can silently stall (#1970 "consistently gets stuck during the first trial", #1708 "Compile freezes silently with async metric"). Severity: **major**. Label: **documented-recurring**.

### production-ops

- **[PO-1] No serving/runtime story: compile offline, then you're on your own.** DSPy produces a serialized program; gateway, rate limits, retries, cost tracking, guardrails, PII handling are all external. "There's no gateway, no observability runtime, no inline guardrails… engineers write their own FastAPI wrapper, logging, retry policy, and cost tracking" (futureagi.com/blog/best-dspy-alternatives-2026/ — vendor blog, discount accordingly, but consistent with HN threads and with the MLflow-integration push in 3.0 as the official mitigation). Deployment questions date to issue #249 (2023). Severity: **major**. Label: **documented-recurring**.
- **[PO-2] State management bugs bite at exactly the save/load boundary production depends on.** Issue #9589 "Module.load_state silently corrupts modules on partial failure (non-transactional)"; #617 confusion over saving/loading optimized programs (16 comments). Severity: **major**. Label: **single-anecdote** (each specific bug) trending recurring as a class.
- **[PO-3] No index freshness/incremental-sync concept** — inherent to BYO retrieval; DSPy-optimized query prompts can silently degrade when the underlying corpus/index shifts, and nothing in the framework detects drift between compile-time trainset and serve-time data. Severity: **major**. Label: **architectural-inference**.

### dx-docs

- **[DX-1] Breaking-change cadence across 2.5 → 2.6 → 3.0 repeatedly stranded users.** 2.5 deprecated all legacy LM clients (LiteLLM migration, release notes 2.5.0 "deprecation warning for old clients"); 2.6 removed Assertions (`dspy.Assert`/`assert_transform_module` gone — issues #7805, #8453) in favor of `Refine`/`BestOfN`; 3.0 removed the 14 community retrievers, `dspy.Program` alias, and Python 3.9. Migration docs lag: issue #9940 "Document Refine migration requirements" (Jun 2026); as of Aug 2026 the official FAQ *still documents* `dspy.Assert`/`dspy.Suggest` as current API two majors after removal (verified dspy.ai/faqs/ 2026-08-05). Severity: **major**. Label: **documented-recurring**.
- **[DX-2] Unpinned fast-moving dependencies break all users at once.** Issue #8581: a HuggingFace `tokenizers` release "caused a breaking change to all DSPy users, because DSPy pulls the latest tokenizers version" (open). Severity: **minor**. Label: **single-anecdote**.
- **[DX-3] Steep learning curve is the consensus adoption blocker, even among fans.** "It's hard. The abstractions are unfamiliar and force you to think a little bit differently" (skylarbpayne.com); "You need to do some up-front work to set up the optimizers which a lot of people are averse to" (HN 47490365, CuriouslyC); adopting teams report roughly a quarter of ramp time (futureagi vendor blog). Python-only, no TS/Go. Severity: **major**. Label: **documented-recurring**.

### performance-cost

- **[PC-1] Optimization compute cost and instability.** MIPRO/GEPA runs make thousands of LLM calls; failure modes include hangs (#1970, #1708), GEPA multimodal runs that "use a lot of memory and halt / never finish" (#8848), and MIPROv2 ignoring `max_bootstrapped_demos=0`/`max_labeled_demos=0` and generating few-shot demos anyway (#8508, confirmed bug, closed). GEPA's 35× rollout-efficiency claim is the mitigation, but budgets remain unpredictable ex ante. Severity: **major**. Label: **documented-recurring**.
- **[PC-2] Runtime overhead from module design.** ReAct fires an unconditional extra extraction LLM call after `finish()` (#10072, open, "N+1 round-trip overhead"); the old Assertions serialized execution (#1215 "Dspy Assertions make execution sequential"). Severity: **minor**. Label: **single-anecdote** each.

### agentic-integration

- **[AG-1] Module-locality assumption misfits agent loops.** Per-module prompt optimization presumes local credit assignment; in agents "ALL the prompts are relevant at ALL the steps," and GEPA-style per-component optimization produced metric gains that "felt like combining… mushrooms and cotton candy" (benanderson.work/blog/contra-dspy-gepa/). Corroborated ergonomically: "their out of the box agent loop has been a joke for the longest time" (HN 47490365, ndr); older report: "Multi-hop reasoning rarely works with real data… No async support [then]" (HN 41213561, thatsadude). Severity: **major**. Label: **documented-recurring** (two independent critiques + issue trail).

### security-governance

- **[SG-1] Input-handling foot-guns and no governance layer.** `dspy.Audio` "auto-downloads from any http(s) string with no timeout and no SSRF guard" (issue #9993, open). Because retrieval is BYO, DSPy has no concept of document ACLs, multi-tenancy, or per-user filtering — compiled few-shot demos can also bake trainset text (potentially sensitive) into every production prompt, with no redaction tooling. Severity: **major** (for enterprise RAG). Label: **single-anecdote** (#9993) + **architectural-inference** (ACL/demo-leakage).

---

## Community sentiment over time

- **2023 (launch):** curiosity + confusion. HN 37417698 (141 pts): intrigued by "compiling" prompts, unclear what it does.
- **2024 (trough of skepticism):** "The more I've looked at DSPy, the less impressed I am… I've yet to see someone actually using it for something other than a toy example" (HN 41214178); "mostly a very complicated way to optimize few-shot prompts… hardly whatever magical blackbox optimizer they market it as" (qeternity, 41213561); "fancy prompt chains under the hood" (Der_Einzige); "utterly useless… grandiose claims" (42407410). Counter-voices cite Databricks/JetBlue and STORM.
- **2025 (renaissance):** 3.0 (Aug 2025) shipped adapters, async, MLflow observability, GEPA; tone shifts — "I tried DSPy and now I get why everyone won't shut up about it" (HN 44993668); a wave of positive practitioner posts (dbreunig, kmad.ai +20% structured-extraction with GEPA, Raspberry-Pi GEPA runs). Dec 2025 brings the sharpest technical critique ("Contra DSPy and GEPA").
- **2026 (adoption paradox):** "If DSPy is so great, why isn't anyone using it?" (227 pts, Mar 2026) — the community's own diagnosis: opaque prompts, upfront metric/dataset work, framework-commitment fear, ergonomics vs pydantic-ai/ADK; while conceding teams keep reinventing its ideas. Momentum is real (7.5M downloads/mo, 3.3.0, RLM) but concentrated among eval-mature teams.

---

## Benchmarks & third-party evaluations

- **DSPy paper** (arXiv 2310.03714, ICLR 2024): compiled multi-stage programs beat expert-written prompts on GSM8K/HotPotQA with small LMs — the founding evidence, on academic QA with clean metrics.
- **DSPy Assertions** (arXiv 2312.13382): constraint-driven self-refinement gains; the mechanism was later removed/replaced (Refine/BestOfN), so results describe a deprecated API.
- **MIPROv2** (arXiv 2406.11695): instruction+demo Bayesian optimization; gains vary by task; the same lab's later GEPA paper reports MIPROv2 being beaten by >10% on average — first-party evidence that earlier first-party numbers left headroom.
- **GEPA** (arXiv 2507.19457, ICLR 2026 oral): +10% avg vs MIPROv2, +6% avg (≤20%) vs GRPO with ≤35× fewer rollouts across 6 tasks. First-party; independent replications on small tasks (kmad.ai, leebutterman.com) report positive but smaller, task-dependent gains.
- **promptolution** (arXiv 2512.02840): independent unified prompt-optimization benchmark framework; its stated raison d'être — returning "framework-agnostic prompt strings for seamless integration" — is a direct response to DSPy's opaque-artifact problem.
- **Notable gap:** there is no strong independent benchmark of DSPy *as a RAG framework* (retrieval quality end-to-end vs LlamaIndex/Haystack pipelines) — because DSPy doesn't own retrieval, evaluations reduce to "prompt optimization on top of whatever retriever you brought."

---

## Lessons for a next-generation framework

1. **Keep the compiler, expose the artifact.** DSPy's signature/module/optimizer split is the most-validated abstraction in the space (teams reinvent it), but compiled prompts must be first-class, exportable, diffable artifacts — opacity is the single most-cited adoption killer (AD-1).
2. **The data layer cannot be someone else's problem.** A RAG framework that optimizes query/synthesis prompts while treating ingestion, chunking, indexing, freshness, and ACLs as out-of-scope (DP-1, PO-3, SG-1) optimizes the easy half. Next-gen: co-optimize chunking/retrieval parameters and prompts under one metric.
3. **Own integrations or don't ship them.** The 14-retriever purge (RQ-1) shows community-contributed connectors bitrot; a thin, versioned retrieval *protocol* (as MCP is for tools) beats a pile of vendor clients — but must come with at least one production-grade default, not a flaky demo server (RQ-2).
4. **Solve the metric bootstrap problem.** Requiring labeled data + automated metric before delivering any value (EO-1) caps the addressable market; next-gen frameworks need zero-label cold-start (trajectory-level reflective feedback à la GEPA, implicit user signals, synthetic evals) with graduated rigor.
5. **Optimize trajectories, not just modules, for agents.** Module-local credit assignment breaks in agent loops (AG-1); optimization units must include whole-trajectory and shared-context (system prompt + tool descriptions) parameters.
6. **Budget-bounded, resumable, observable optimization.** Cost dry-runs (#397), hang detection (#1970/#1708), and transactional program state (#9589) are table stakes for treating optimization as CI.
7. **Deprecate with docs.** Shipping majors that remove APIs while official FAQs still teach them (DX-1) converts enthusiasts into churn statistics.

---

## Sources

- Repo & API data: github.com/stanfordnlp/dspy (stars/forks/issues/releases via GitHub API, 2026-08-05); PR #8073 (retriever removal); issues #249, #397, #494, #617, #633, #1215, #1308, #1539, #1570, #1708, #1739, #1970, #7805, #7966, #8453, #8508, #8581, #8848, #8946, #8952, #8958, #9116, #9178, #9589, #9713, #9940, #9993, #10072; releases 2.5.0, 3.0.0, 3.3.0.
- Official docs: dspy.ai (front page, adopters, optimizer list); dspy.ai/tutorials/rag/; dspy.ai/faqs/ (stale Assertions docs, verified 2026-08-05).
- HN threads: news.ycombinator.com/item?id=37417698; 40556135; 41213561; 41214178; 42350799; 42407410; 44993668; 47490365 (full comment trees via hn.algolia.com API).
- Critiques/blogs: benanderson.work/blog/contra-dspy-gepa/; skylarbpayne.com/posts/dspy-engineering-patterns/; futureagi.com/blog/best-dspy-alternatives-2026/ (vendor — used only for claims corroborated elsewhere); dbreunig.com/2025/06/10/let-the-model-write-the-prompt.html; kmad.ai/DSPy-Optimization; leebutterman.com/2025/11/01/prompt-optimization-on-a-raspberry-pi.html; blog.isaacmiller.dev/posts/dspy; databricks.com/blog/dspy-databricks.
- Papers: arXiv 2310.03714 (DSPy); 2312.13382 (Assertions); 2406.11695 (MIPROv2); 2507.19457 (GEPA, ICLR 2026); 2512.02840 (promptolution).
- Sibling projects: github.com/stanford-oval/storm; dspy-community/dspy-template-adapter.
