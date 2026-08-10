# Agentic-Integration Failures: How RAG Frameworks Meet (and Fail) the Agent Loop

Synthesis date: 2026-08-05. Dimension: **agentic-integration** (+ memory-related data-processing).
Corpus: all 19 framework autopsies in `research/02-frameworks/` (issues sections read in full for the
agentic-integration category, plus memory-related data-processing, production-ops, and
security-governance issues where they concern agent memory), cross-checked against four landscape
dossiers (`agentic-rag-deep-research.md`, `memory-context-engineering.md`,
`advanced-rag-architectures.md`, `frontier-2025-2026.md`) and `cross-cutting-gaps.md`.

## Method note

- **Inclusion bar**: an issue is "common" only when evidenced in ≥3 independent frameworks/platforms,
  with documented-recurring evidence (GitHub issues, vendor docs, independent benchmarks) as the
  spine. Architectural-inference and single-anecdote items appear only as supporting color and are
  labeled as such in the tables.
- **Blacklist respected**: none of the audit-flagged weak claims (langchain SEO quantifications,
  lowcode "10x markdown chunking" and NVD keyword CVE counts, ragflow third-party corroboration
  layer, the Pinecone platform-risk claim, the GraphRAG "$33k/5GB" figure, multilingual arXiv-only
  vendor claims) is used anywhere below.
- Note on cohort files: `agent-framework-retrieval.md` covers ~10 distinct frameworks (OpenAI
  Agents SDK, Google ADK, CrewAI, AutoGen/SK, smolagents, Pydantic AI, Mastra, Letta, MCP servers,
  Claude Agent SDK); where several of those independently exhibit an issue, they are counted as
  independent evidence points even though they share one autopsy file.
- Evidence pointers are given as `file — issue gist (label)`.

---

## The common issues

### 1. Agents bolted beside, not beneath: the agentic path is a fork that loses capability

**Definition.** Frameworks add an "agentic" mode as a parallel subsystem next to the static
retrieval pipeline instead of re-founding retrieval beneath both; the result is that turning agents
*on* silently turns other capabilities *off* — or the retrieval product is simply a fixed node an
agent cannot iterate against.

| Framework | Evidence | Label |
|---|---|---|
| gpu-vendor-enterprise-rag (NVIDIA) | G2: agentic path drops Guardrails, Self-Reflection, Query Decomposition, VLM inference (vendor docs, verbatim); G1: plan has no DAG/depends-on, so dependent multi-hop is inexpressible; E3: response metadata "omitted or returned empty for Agentic RAG" | documented-recurring |
| managed-aws-google | Bedrock KB one-shot-only until Jun 2026; decomposition locked inside `RetrieveAndGenerate`, unavailable to agents via `Retrieve`; Gemini File Search cannot combine with Google Search/URL-context tools in one request | documented-recurring |
| microsoft-graphrag | Static batch pipeline: no tool/MCP surface, no memory API, no adaptive budget, fixed query modes; the agent-friendly successor (LazyGraphRAG budgeted iterative deepening) shipped into other Microsoft products, not the library | architectural-inference (major) |
| hkuds-lightrag-family | AG1: static pipeline, manual mode selection, no MCP upstream — ApeRAG's production rewrite added it, corroborating the gap | architectural-inference, corroborated |
| lowcode-builders (Dify et al.) | "Knowledge Retrieval" is a static node in a DAG, not a tool an agent can re-query iteratively | architectural-inference (major) |
| ragflow | Agent layer is a workflow DSL; retrieval is a node; memory arrived late (v0.24) as an API, not a substrate | architectural-inference (minor) |
| research-toolkits | Static-pipeline worldview baked into evaluation methodology itself (all six toolkits evaluate fixed pipelines on single-turn QA); AutoRAG's 2026 pivot to an agent product is the in-corpus admission | architectural-inference |
| datacloud-rag (Snowflake) | AI-1: "agents" are thin orchestration over two fixed tools, no loop monitoring | single-anecdote (color) |

**Root cause.** Every one of these systems was founded when the unit of design was the pipeline:
ingest → index → retrieve → generate. When the agent turn arrived (2025), the installed base and
the org chart both favored *adding a mode* over *re-founding the executor*: an "Agentic RAG"
checkbox ships in a quarter; making guardrails, decomposition, and observability into layers that
run beneath both single-shot and multi-step execution requires rewriting the core. The NVIDIA case
is the cleanest exhibit because the vendor documents the regression itself: the agentic path is a
different code path, so everything attached to the old path is lost. Static-node builders (Dify,
RAGFlow) have the same problem one level up — the visual DAG is the product, and an agent loop
cannot be drawn as a DAG node.

**Research context.** The research side settled the architectural question first: the Agentic RAG
survey (arXiv:2501.09136) codified agent-embedded retrieval in Jan 2025; LlamaIndex's own "RAG is
dead, long live agentic retrieval" (May 2025) declared agentic strategies "table stakes"; by
mid-2026 the frontier consensus is "retrieval is an agent behavior, not a pipeline stage"
(frontier-2025-2026.md §SOTA). This is not an unsolved research problem — it is an engineering
re-founding the framework layer has refused to pay for.

**Next-gen requirement (testable).** The agentic path must be a strict superset of the static
path: guardrails, query decomposition, provenance/metadata, and observability are substrate layers
exercised identically by single-shot and multi-step execution. Test: a feature-parity matrix across
{static, agentic} × {guardrails, decomposition, citations, response metadata, traces} must be
all-green, and multi-hop plans must express step-dependencies (a DAG/depends-on construct) —
verified on dependent multi-hop queries, precisely where measured accuracy is worst today.

---

### 2. Loops grafted onto DAG schedulers: agent control flow is second-class, and it breaks

**Definition.** Orchestration frameworks retrofitted iteration onto executors designed for acyclic
dataflow, producing a recurring class of loop-correctness bugs — non-exit, infinite loops,
dropped recursion limits, broken nested streaming — with termination enforced by crude caps rather
than semantics.

| Framework | Evidence | Label |
|---|---|---|
| haystack | Cycle engine P0-broken for ~9 months (#8024 → 2.7 rework); Agent silently fails to exit when the LLM emits parallel tool calls (#11392, "no exception, no warning… wasted LLM calls"); tool results reordered (#12010); duplicate identical tool calls not cached (#11588, open); checkpoint/replay still RFCs (#11836, #11266) | documented-recurring |
| langchain-langgraph | G1: agent infinite-loops to recursion limit (#6731, 26 comments); `merge_configs` silently drops explicitly-set recursion limits (#7314); streaming broken for agent-as-tool nesting (#5528, #4653, #6447) | documented-recurring |
| dspy | AG-1: per-module optimization presumes local credit assignment that agent loops violate ("ALL the prompts are relevant at ALL the steps"); "their out of the box agent loop has been a joke for the longest time" (HN); multi-hop "rarely works with real data" | documented-recurring |
| gpu-vendor-enterprise-rag | G1: flat one-level parallel plan, no dependency graph — the loop cannot express its own data flow | documented-recurring (vendor docs) |
| llamaindex | G2: orchestration thin relative to dedicated orchestrators (ZenML, dev.to assessments); early AgentWorkflow tool-use bugs (#17616); durable execution/HITL young | documented-recurring |
| lowcode-builders | Deterministic-graph vs probabilistic-agent mismatch named as the category's structural squeeze in the Flowise sunset thread | documented-recurring (minor) |

**Root cause.** A DAG scheduler assumes each node runs once and the graph is known ahead of time;
an agent loop is a runtime-decided cyclic program with state, budgets, and retries. Retrofitting
the latter onto the former means loop semantics live in fragile conventions (an "exit-condition
tool" that must be called first; a recursion-limit integer) rather than in the executor. Haystack's
own open RFCs (run recording & deterministic replay; transaction protocol) are an internal
diagnosis of exactly this. Deeper still: termination is enforced syntactically (max iterations)
because nothing in the loop carries the *semantic* stop condition — see issue 4.

**Research context.** Research treats the loop as the object of study: ReAct-lineage systems,
IterResearch/AgentFold treat the trajectory itself as a managed workspace; RL-trained agents learn
stop policies end-to-end (Search-R1 → Tongyi DR). Nothing in the literature suggests loops-on-DAGs
is viable; the field simply skipped that architecture. What research has *not* solved is exposing
the learned loop policy as a controllable, replayable artifact — Kimi-Researcher's 70+-search
trajectories embed the stopping rule invisibly (agentic-rag-deep-research.md §budgets).

**Next-gen requirement (testable).** The executor must be loop-native from day one: iteration,
per-loop budgets, checkpointing, and deterministic replay as runtime primitives. Test: (a) any
recorded agent run replays deterministically; (b) an agent whose exit-condition tool is emitted in
a parallel tool-call batch still exits; (c) loop termination is triggerable by a declared evidence
condition, not only by an iteration cap.

---

### 3. No budget contract: token/latency/dollar cost of the loop is unbounded and unaccounted

**Definition.** No framework lets a caller hand retrieval a resource contract (tokens, latency,
dollars) and get back enforcement, per-stage accounting, and graceful anytime degradation — even
though multi-step retrieval multiplies cost 4–15× and the cost is the dominant performance
variable.

| Framework | Evidence | Label |
|---|---|---|
| agent-framework-retrieval (cohort) | C1: naive MCP tool loops consume 150,000 tokens where code-mediated access needs 2,000 (Anthropic's own numbers); third parties built businesses on the gap (Semble: "98% fewer tokens than grep", HN 445 pts); C2: context rot penalizes inject-everything designs | documented-recurring |
| gpu-vendor-enterprise-rag | C5: agentic mode's cost "exceed[s] the standard chain" — acknowledged but unquantified; no multiplier, no token accounting | documented-recurring |
| managed-openai-azure | Token-billed agentic retrieval whose cost estimation "requires a spreadsheet" (Azure's own docs); practitioners advise classic hybrid for production while agentic matures; knowledge-source fan-out caps as the only budget knob | documented-recurring |
| microsoft-graphrag | No adaptive retrieval budget; index too expensive and stale to serve as agent memory; the budgeted successor (LazyGraphRAG) shipped elsewhere | architectural-inference |
| vectordb-and-startup-platforms | None of the eight platforms offer retrieval budgeting for multi-step loops; multi-step flows expose latency (practitioner report) | architectural-inference + single-anecdote |
| research-toolkits | Loop methods' 2–5× token/latency overhead for ~0 gain on most queries is invisible in every leaderboard the toolkits generate | documented (benchmark synthesis) |
| memory-and-localfirst (Mem0) | I13: no token-usage accounting in responses (#2820) — users cannot measure what the memory layer costs per turn | documented-recurring |
| datacloud-rag (Databricks) | AI-2: agent serving economics — pay for idle or accept multi-minute cold starts | single-anecdote (color) |

**Root cause.** Static-pipeline economics were per-query-constant, so cost accounting never became
a framework primitive; agent loops made cost a *policy variable* (each iteration is a spend
decision) while the abstractions still model retrieval as a free function call. There is also an
incentive asymmetry: frameworks are evaluated on answer-quality benchmarks where token spend is
invisible, and managed vendors bill by the token — neither side profits from making the meter
legible.

**Research context.** Research quantifies the problem precisely — token usage explains ~80% of
BrowseComp performance variance (Anthropic); single agents ≈4× and multi-agent ≈15× chat tokens;
budget-aware One-SHOT retrieval is competitive with iteration on shallow-wide needs (Fishing for
Answers, EMNLP 2025) — but "no published system offers principled anytime behavior… a declared
marginal-value-of-another-search estimate, or a deadline/cost contract"
(agentic-rag-deep-research.md O2). Budget-aware *evaluation* of active retrieval only appeared in
Jul 2026 (arXiv:2607.24010). So this is genuinely open on the research side *and* unshipped on the
framework side — the rare gap that is both.

**Next-gen requirement (testable).** Every retrieval/memory call accepts an explicit budget
contract `{max_tokens, max_latency, max_cost}`; the framework enforces it (never exceeded),
accounts it per stage (query → tool calls → tokens in/out → dollars), and degrades anytime
(best-evidence-so-far returned at budget exhaustion, flagged as truncated). Test: a conformance
suite where declared budgets are never exceeded across adversarial corpora, and per-query
quality-per-dollar is emitted by default.

---

### 4. Nothing to branch on: no calibrated scores, no sufficiency estimate, no abstention path

**Definition.** Retrieval returns an opaque top-k with uncalibrated similarity scores; no framework
returns machine-readable relevance/coverage/sufficiency/freshness signals an agent loop could
branch on, and none treats "the corpus cannot answer this" as a first-class result — so agents
cannot decide to re-query, escalate, or stop for principled reasons.

| Framework | Evidence | Label |
|---|---|---|
| oss-rag-platforms | A1: "No platform returns calibrated relevance/coverage/freshness metadata that an agent loop could branch on"; R2R freshness-signal request (#2300) died in a dead repo | architectural-inference with documented fragments |
| managed-openai-azure | retrievalci/EnterpriseRAG-Bench: all four managed platforms (Azure, Vertex, Bedrock, OpenAI) hallucinated on **100% of unanswerable questions** — abstention is nobody's retrieval outcome; Azure's LLM planning "can miss relevant angles with no feedback loop" | documented-recurring (independent benchmark) |
| agent-framework-retrieval (cohort) | G1: query formulation delegated to the model with *no feedback loop* — nothing measures whether the query was good; retrieval misses present as hallucinations; E1: no framework ships a retrieval/memory eval loop (Letta's tracker admits it, #3115) | architectural-inference + documented-recurring |
| ragflow | Absence of calibrated scores and chunk-metadata filters "makes fine-grained agentic retrieval control impossible without forking" | architectural-inference |
| hkuds-lightrag-family | AG1: mode selection is manual — the system exposes no signal by which an agent (or router) could choose vector vs graph vs hybrid per query | architectural-inference |
| research-toolkits | Per-query adaptivity beats offline pipeline selection across all six toolkits' own results, yet none exposes the decision signal | documented (benchmark synthesis) |

**Root cause.** Cosine similarity is not a probability, and calibrating it per-corpus is real
statistical work with no demo payoff — so frameworks pass raw scores through and let the LLM
"figure it out." Abstention is worse than uncalibrated: it is anti-demo. A framework whose default
behavior includes "no answer available" loses the bake-off against one that always generates
something. The result is structural: the agent loop's branch conditions have nothing trustworthy to
read, so loop control degenerates into vibes-based re-querying or premature answering.

**Research context.** This is the sharpest case of *frameworks ignoring solved-enough research*.
Sufficient Context (arXiv:2411.06037) showed RAG **reduces** abstention and that sufficiency-guided
selective generation recovers 2–10% correct-answer rates; Self-Route demonstrated per-query
sufficiency routing in 2024; Moskvoretskii et al. (arXiv:2501.12835) showed plain uncertainty
estimators match complex adaptive pipelines — i.e., the needed signal is *cheap*; the 2026
diagnostic literature (arXiv:2608.01913) finds agents "lack evidence-sufficiency stopping criteria"
and recommends exactly that; abstention-aware RL rewards exist (arXiv:2607.10738). The unsolved
part is calibration on RLHF'd models (advanced-rag-architectures.md F1); the shipped part — a
sufficiency autorater, uncertainty baselines, no-answer detection — has simply never been given a
framework API.

**Next-gen requirement (testable).** Retrieval returns a typed evidence-state, not a bare list:
calibrated relevance (with stated calibration method), coverage/sufficiency estimate, freshness,
and an explicit `insufficient_evidence` result type wired through to generation. Test: on a
benchmark with unanswerable questions, the system abstains or escalates on a measured majority of
them (versus the current 0%), and an agent loop can be written whose branches consume only
machine-readable retrieval signals — no prompt-parsing of scores.

---

### 5. Memory without transactional discipline: the write path silently loses, corrupts, and drifts

**Definition.** Agent memory subsystems ship without the durability contract every database has had
for decades — writes fail silently, concurrent writes corrupt state, compaction destroys
conversation state, recall is recency-flat, and memory semantics change without versioning.

| Framework | Evidence | Label |
|---|---|---|
| memory-and-localfirst (Mem0) | I3: silent memory loss — batch-embedding partial failures drop items with no exception, WARNING-log only (#5245, P1-high, open); I4: concurrent `AsyncMemory` writes corrupt the Qdrant HNSW index (#4892); I5b: signature ADD/UPDATE/DELETE/NOOP semantics retired unversioned — docs now describe ADD-only storage contradicting the cited paper | documented-recurring (I2b's 97.8%-junk audit, #4573, is single-anecdote color for the same write path) |
| agent-framework-retrieval (MCP `server-memory`) | D2: no atomic writes, quotas, redaction, or destructive-op guardrails (#4117, open) — and this is the template the MCP ecosystem copies | documented-recurring |
| agent-framework-retrieval (Letta) | P3: compaction set to evict 15% "performs a full context wipe"; summarization trims a tool call but not its paired response, crashing the client (#3270, #2605); R3: archival memory accumulates semantic duplicates, no consolidation (#3116) | documented-recurring |
| agent-framework-retrieval (Mastra, Pydantic AI, smolagents) | R3: `Memory.recall()` is flat-recency-only, branched conversations irrecoverable (#18943, production team "near-blocking"); G4: minimal frameworks externalize memory entirely — cross-run memory RFCs open for a year+ (pydantic-ai #4773, smolagents #1216/#901) | documented-recurring |
| oss-rag-platforms (AnythingLLM) | Agent state leaks across threads (#1349); agent memory management an open request (#4288) | documented fragments |
| haystack / lowcode / ragflow | No first-class memory subsystem (conversation `State` only); session/buffer-only memory; memory-as-API bolted on late | architectural-inference (supporting) |

**Root cause.** Memory systems were built by ML engineers as *pipelines* (extract → embed → store),
not by database engineers as *stores with invariants*. The write path performs read-modify-write
across multiple systems (vector store + history store) mediated by nondeterministic LLM calls, with
no transaction, no idempotency key, and no failure contract — so the bug class recurs structurally
(the Mem0 reporter of #5245 identified "a systemic pattern across multiple code locations").
Agentic workloads then maximize exposure: many parallel tool calls per turn is exactly the
concurrent-write case. And because the only job of a memory layer is *not forgetting*, silent loss
is disqualifying rather than degraded service.

**Research context.** The research literature has a mature *operations taxonomy* — consolidation,
updating, indexing, forgetting, retrieval, condensation (Du et al., arXiv:2505.00675) — but "the
write path… has no formal framework: no cost models, consistency guarantees, or correctness
criteria" (memory-context-engineering.md, open problem 2). Consolidation research (sleep-time
compute, A-MEM evolution) is active but lossy-irreversible in every published form; reversible
consolidation and utility-based forgetting are named open problems. So the transactional layer is
an engineering gap (databases solved it), while the consolidation-correctness layer is genuinely
open research.

**Next-gen requirement (testable).** Memory writes get database semantics: fail-loudly writes with
per-item error surfaces and metrics, idempotency keys, concurrency safety under parallel agent
turns, versioned memory semantics, and logged consolidation decisions with deterministic replay.
Test: an embedder failing every third call must produce raised errors and counters — zero silent
drops; N concurrent writers never corrupt the index; compaction provably preserves tool-call
pairing and honors declared eviction ratios; a store built under semantics vX is either readable
under vX+1 or migrated by tooling, never silently reinterpreted.

---

### 6. The provenance-free write: agent memory is an unguarded trust boundary

**Definition.** Nothing distinguishes *who wrote* a memory or retrieved chunk — user assertion,
tool output, injected prior memory, or attacker document — so memory is simultaneously a
prompt-injection channel into future turns, a poisoning target, and a self-reinforcing
hallucination loop; no framework ships provenance-tagged or trust-tiered memory.

| Framework | Evidence | Label |
|---|---|---|
| agent-framework-retrieval (CrewAI) | S1: retrieved memory concatenated directly into the system prompt — poisoned entries inject arbitrary instructions into future interactions (#5057, open; OWASP ASI-01) | documented-recurring |
| agent-framework-retrieval (Pydantic AI, MCP) | Parallel memory-poisoning reports (pydantic-ai #5424, OWASP ASI06); MCP memory server lacks redaction/guardrails (#4117); "No framework in the cohort ships provenance-tagged or trust-tiered memory" | documented-recurring |
| memory-and-localfirst (Mem0) | I2b mechanism: injected memories re-extracted as fresh facts ("Vim" hallucinated once, re-extracted 808×) — no provenance bit distinguishing "user said this" from "we previously stored this"; I11: PII exclusion is a natural-language prompt, not an access control | single-anecdote (mechanism) + documented pattern |
| gpu-vendor-enterprise-rag (NVIDIA AI-Q) | S7: agentic blueprint ships unauthenticated MCP, customer-supplied guardrails, no sandbox — the agent/memory boundary is open by default | documented-recurring (vendor README) |
| cross-cutting-gaps | AgentPoison (arXiv:2407.12784): backdooring agents by poisoning long-term memory/KB — >80% attack success at <0.1% poisoning rate; "agent memory is a corpus, therefore agent memory is a poisoning target" | documented-recurring (taxonomy: agentic-integration) |

**Root cause.** Memory entries and retrieved chunks arrive in the prompt as undifferentiated text
because the transformer context has no native data/instruction boundary, and frameworks replicated
that flatness in their storage schemas: a memory row has content and an embedding, but no
provenance type, no trust tier, no write-authority record. The feedback loop is then guaranteed by
construction in persistent agents: content injected from memory is indistinguishable from fresh
observation, so it is re-extracted and compounds. Fixing it requires typed writes and admission
control — schema work with no benchmark payoff, in a space where benchmarks measure recall QA.

**Research context.** Research is ahead and alarmed: AgentPoison quantified the attack in 2024;
Aug-2026 work shows self-evolution is a *persistence layer* for attacks (SkillJack backdoors),
benign experiences compose into harmful behavior, and source authority/permissions do not survive
consolidation ("Authority Collapse"; MemArena finds permission-aware access "fails universally") —
frontier-2025-2026.md's distilled implication is verbatim "memory writes are a trust boundary."
No framework implements any of it; no framework even runs the published poisoning benchmarks as a
pre-deployment gate (cross-cutting-gaps).

**Next-gen requirement (testable).** Every memory/corpus write carries typed provenance
(user-asserted / observed / tool-derived / inferred / injected-from-memory) and a trust tier;
injected-memory content is structurally non-extractable (feedback-loop prevention); writes pass
admission control with quarantine and rollback; provenance and ACLs survive consolidation. Test:
re-extraction rate of previously-injected memories = 0 in a looped-agent soak test; an
AgentPoison-style poisoning suite runs as a shipped pre-deployment gate; a MemArena-style
permission probe shows no cross-principal leakage after consolidation.

---

### 7. The tool seam is broken: provider lock, MCP immaturity, and model priors that distrust the tool

**Definition.** Retrieval-as-tool won as the integration pattern, but the seam it depends on is
immature at every layer: hosted retrieval tools are welded to one vendor's loop, MCP standardizes
transport but not retrieval quality/security/persistence, and models' RL-installed habits (grep,
re-reading) override whatever tool the framework offers.

| Framework | Evidence | Label |
|---|---|---|
| agent-framework-retrieval (cohort) | A1: `FileSearchTool` works only with OpenAI Responses-API models — "no provider yet supports fully swapping between models and their native tools" (#461, #1904); G2: "models are so heavily RL'd with grep that they do not trust results in other forms and will continually retry or reread, and all token savings vanish" (HN, multiple corroborating practitioners); MCP reference servers are demos by their own admission (#4117) | documented-recurring |
| managed-openai-azure (OpenAI) | Retrieval welded to one vendor's agent loop: file_search unusable from Chat Completions or non-OpenAI models; the model is the only orchestrator, so skipped searches and phantom "user uploads" are unfixable at the framework layer | documented-recurring |
| managed-aws-google (Gemini) | File Search cannot be combined with Google Search or URL-context tools in the same request and doesn't work with the Live API — blocking the canonical private-docs-plus-web agent pattern | documented-recurring |
| jvm-js-ecosystems (Spring AI) | G1: 9 of the 15 most-commented issues are MCP transport/auth/reconnection problems ("Authentication lost in tool execution" #2506; clients don't reconnect #2740) while core retrieval issues sit open 18+ months | architectural-inference (from issue distribution) |
| memory-and-localfirst (txtai, Mem0/OpenMemory) | MCP ecosystem churn (`mcpadapt` broken against latest `mcp`, txtai #1161); OpenMemory MCP launch-window setup-failure burst (#2695, #2690, #2712) | documented-recurring |
| gpu-vendor-enterprise-rag | S7: MCP surface shipped stateless and unauthenticated in an enterprise blueprint | documented-recurring |

**Root cause.** Three separately-owned layers must agree for retrieval-as-tool to work, and no one
owns the composition. (1) *Vendors* monetize the loop, so hosted retrieval tools are loyalty
devices, not portable components. (2) *MCP* deliberately standardized the cheapest layer —
transport and tool schemas — leaving quality, persistence, auth, and redaction as "the integrator's
problem," so the ecosystem is registry-scale but demo-deep. (3) *Model training* installs retrieval
habits (grep affordances, distrust of unfamiliar result shapes) that no framework controls; a tool
that fights the prior gets retried into token oblivion. Each party's local optimum reproduces the
broken seam.

**Research context.** Anthropic's tool-design guidance (consolidate operations, token-efficient
responses, semantically meaningful identifiers measurably improving retrieval precision) is the
only serious published treatment, and it is vendor engineering, not standards work. The landscape
verdict: "In the MCP era, a RAG system's public surface *is* a tool schema; most published RAG
research still ignores this layer entirely — a gap a new framework can own"
(agentic-rag-deep-research.md). The retrieval interface *contract* — what operations, what cost
model, what match-explanation an agent can plan over — is open problem O1; nobody has formalized
it.

**Next-gen requirement (testable).** A provider-agnostic retrieval-tool contract: `{query, filters,
token_budget, provenance, calibrated confidence}` in the signature, runnable unchanged across ≥3
model providers (hosted and local), with authn/z and persistence semantics specified rather than
disclaimed, and output affordances validated against model priors in agent loops (evidence-per-token
measured, grep-familiar result shapes). Test: the same tool schema passes an agent-loop conformance
suite on three providers; retry/re-read rates against the tool are measured and bounded relative to
a grep baseline.

---

### 8. The agent layer is the least stable layer in the stack

**Definition.** Frameworks have rewritten their agent APIs roughly every 12–18 months, each time as
a breaking change — agent definitions, memory schemas, and orchestration code are treated as
disposable rather than durable artifacts, so teams that adopted early rewrote twice.

| Framework | Evidence | Label |
|---|---|---|
| llamaindex | G1: three generations of agent APIs in 2.5 years, each migration breaking (v0.13.0 removed FunctionCallingAgent, ReActAgent, AgentRunner, OpenAIAgent…; llama-agents → AgentWorkflow → Workflows-as-package → LlamaAgents-as-cloud-product) | documented-recurring |
| agent-framework-retrieval (AutoGen/SK/Letta) | P1: AutoGen 0.2 → 0.4 total rewrite → AG2 fork → Microsoft Agent Framework, repo frozen with 976 open issues; SK memory broke SemanticTextMemory → MEVD → Agent Framework with "no guidance" on migration; Letta's 24k-star server is "legacy" per its own README | documented-recurring (critical) |
| ragflow | v0.20 agent rewrite broke all existing agents — "agent definitions are not treated as durable artifacts" | documented-recurring |
| haystack | Agent runtime arrived late and via breaking change: hooks/skills/HITL landed in 3.0 while simultaneously removing `ToolInvoker` and legacy generators | documented-recurring |
| research-toolkits (UltraRAG) | Three rewrites in two years; own 3.0 blog attacks the "black box" prior versions | documented |

**Root cause.** The agent abstraction was guessed before the workload existed, under competitive
pressure to ship "agents" quarterly; each guess (step workers, planners, typed graphs, workflows)
was falsified by real usage, and open-core economics make a clean break cheaper for the vendor than
compatibility engineering — the migration cost lands on users. The instability is *concentrated* at
the agent layer because it is the newest guess sitting on the fastest-moving substrate (model
capabilities changed under it every six months).

**Research context.** The research analogue is churn in patterns, not APIs — prompt-orchestrated
controllers (Self-RAG/FLARE/CRAG-style) were superseded by RL-trained policies within ~18 months
(frontier "hype ledger"), which partially *explains* framework churn: frameworks chased a moving
research frontier. But the durable lesson from the survivors is stability-by-smallness: protocols
outlive class hierarchies ("components any agent can call survive framework rewrites; pipeline
subclasses don't" — research-toolkits lessons), and the practitioner exodus to thin wrappers +
MCP servers is the market pricing this in.

**Next-gen requirement (testable).** Freeze a small retrieval/memory kernel and version everything
above it as durable, migratable artifacts: agent definitions, memory stores, and tool contracts
carry schema versions with automated migration paths. Test: artifacts created on version N load on
N+1 without edits; any breaking change ships with a working migrator exercised in CI; the kernel
API surface is provably additive-only across a major-version window.

---

## Near-misses (honest register: <3 frameworks, or weak evidence)

- **Safety layers don't survive the agentic path as a *distinct* issue.** NVIDIA's agentic path
  drops NeMo Guardrails (documented) and OpenAI's hosted `FileSearchTool` executed and billed
  despite a tripped input guardrail (openai-agents #889, single-anecdote). Two frameworks; folded
  into issues 1 and 7 rather than stood alone.
- **Agent serving economics** (Databricks slot-holding streams + cold starts; Snowflake agents
  gated on container runtime): two platforms, both single-anecdote. Real, but color for issue 3.
- **Write-time LLM extraction misfits agent transcripts** (Mem0's extractor designed for human
  chat meets boot-prompt/heartbeat/tool-chatter workloads; the 97.8%-junk audit's taxonomy). The
  mechanism is forensically detailed and consistent with the architecture, but it is one user's
  audit of one 32-day deployment on one framework — single-anecdote by the corpus's own labeling.
  Its five missing mechanisms (REJECT verdict, identity-aware extraction, TTL classes…) inform
  requirement 6 without being its spine.
- **Extraction assumes GPT-class instruction-following** (Mem0 structured-output failures on
  gemini-flash/Ollama-class models: #3410, #3391, #3918). Documented-recurring but one framework.
- **Per-module prompt optimization misfits agent loops** (DSPy AG-1: credit assignment is global
  in agents). One framework, though the underlying credit-assignment problem is corroborated by the
  RL literature (sparse trajectory rewards, arXiv:2605.29697).
- **Multi-agent context handoff loses evidence** (subagent findings compressed into the lead's
  context with no shared provenance store). Strongly documented on the research side (Anthropic's
  production pathology list; AgentFold/IterResearch), but the framework corpus shows it only
  obliquely (gpu-vendor G1's flat plan). Likely a real common issue that the autopsy corpus
  under-samples because few frameworks ship multi-agent research modes at all.
- **Memory and knowledge as non-communicating subsystems** (lowcode: "an agent cannot treat past
  conversation as a retrievable knowledge source without manual wiring"). Two-ish frameworks
  explicitly; the research convergence thesis (memory ≡ retrieval + write path) says this split is
  architecturally wrong, but framework-side evidence is thin.

---

## Dimension synthesis: what agentic-integration reveals about why the ecosystem is stuck

**1. The founding abstraction is the liability.** Every framework in this corpus was founded on the
pipeline/DAG/index triad, and every common issue above is a symptom of meeting a loop-shaped
workload with batch-shaped architecture: agents forked beside pipelines (issue 1), loops grafted
onto DAG schedulers (issue 2), per-query cost models that assume one query (issue 3), stores built
as pipelines instead of databases (issue 5). Installed-base economics make the rational vendor move
"add an agentic mode" rather than "re-found the executor" — so the fork pattern, and its capability
regressions, keep reappearing across independent teams.

**2. The missing things are contracts, not features.** What agents need from retrieval is a set of
enforceable promises — a budget honored (3), a calibrated signal returned (4), a write that either
commits or fails loudly (5), a provenance type that survives consolidation (6), a tool schema that
outlives the quarter (7, 8). Features demo well and ship quarterly; contracts constrain the vendor
and are invisible in a demo. An ecosystem funded on demo velocity systematically under-produces
contracts. This is the deepest structural reason the same gaps persist across otherwise unrelated
codebases.

**3. Benchmarks cannot see any of this, so nothing forces a fix.** Single-turn QA leaderboards are
blind to loop non-termination, token burn, silent memory loss, poisoning, and abstention — the
retrievalci finding (100% hallucination on unanswerables across all four managed platforms) and the
"cost invisible in every leaderboard" finding (research-toolkits) are the same fact from two sides.
Where measurement is absent, vendor benchmark wars fill the vacuum (Mem0/Zep/Letta), further
eroding the incentive to build honest signals. Evaluation misalignment is not a side issue in this
dimension; it is the enforcement mechanism that never existed.

**4. The intelligence moved into the model; the frameworks kept the furniture.** The research arc
of 2025–26 relocated query formulation, routing, stopping, and verification into trained policies
(Search-R1 → Tongyi DR), and models' RL'd priors now even determine which tools get trusted (issue
7). What remains for a framework is precisely what the model *cannot* internalize: enforceable
budgets, calibrated corpus-side signals, transactional and provenance-safe memory, a stable tool
contract, and replayable loop execution. The frameworks in this corpus are stuck because they are
still competing on the part that moved (orchestration cleverness) while leaving the part that
stayed (the substrate contract) unbuilt.

**5. Research and engineering are missing each other at a nameable seam.** Sufficiency estimation,
uncertainty baselines, budget-aware retrieval, poisoning benchmarks, and provenance-preserving
consolidation all exist in the literature — some for two+ years — and appear in no framework API.
Conversely, the problems frameworks actually hit (loop replay, MCP auth, memory transactions,
artifact migration) barely register as research topics. A next-generation framework's opportunity
is exactly this seam: turn the published primitives into contracts, and the operational pains into
research-visible benchmarks.

### Consolidated next-gen requirements (testable)

1. **Superset rule**: the agentic path runs every capability of the static path (guardrails,
   decomposition, metadata, traces) — verified by an all-green parity matrix, with step-dependency
   expression for multi-hop plans.
2. **Loop-native executor**: iteration, checkpointing, deterministic replay, and semantic
   (evidence-based) stop conditions as runtime primitives — recorded runs replay identically;
   parallel-tool-call exits work.
3. **Budget contract**: every retrieval/memory call accepts `{tokens, latency, dollars}`, enforces
   it, accounts per stage, and degrades anytime — conformance-tested; quality-per-dollar emitted by
   default.
4. **Branchable evidence-state**: calibrated relevance + coverage/sufficiency + freshness +
   first-class `insufficient_evidence` — measured abstention on unanswerable benchmarks replaces
   today's 100% hallucination.
5. **Transactional memory**: fail-loudly writes, idempotency, concurrency safety, versioned
   semantics, replayable consolidation decisions — zero silent drops under injected failure; no
   corruption under parallel writers.
6. **Provenance-typed trust boundary**: typed write provenance with trust tiers, feedback-loop
   prevention (injected memory non-extractable), admission control/quarantine/rollback, ACLs
   surviving consolidation — poisoning suites (AgentPoison-class) as shipped pre-deployment gates.
7. **Portable tool contract**: one retrieval-tool schema (query, filters, budget, provenance,
   confidence) running unchanged across ≥3 model providers, with specified auth/persistence and
   prior-compatible affordances — evidence-per-token benchmarked in agent loops.
8. **Durable artifacts on a frozen kernel**: versioned, migratable agent/memory/tool artifacts over
   a small additive-only core — N→N+1 compatibility exercised in CI.
