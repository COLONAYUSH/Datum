# Agent Memory Systems & Context Engineering: Landscape, Failure Modes, and Open Problems (as of mid-2026)

## Scope

This document surveys the retrieval/memory component of agentic LLM systems through the lens of **context engineering**: the discipline of deciding which tokens occupy a model's context window at each inference step. It covers:

- The context-engineering framing (Anthropic, Karpathy/Lutke) and its relation to RAG.
- Empirical context failures: context rot, effective-context-length gaps (NoLiMa, RULER, LongBench v2).
- The long-context-vs-RAG debate (Self-Route, sufficient-context analysis, 2024–2026 follow-ups).
- KV-cache economics: prompt caching, CAG, CacheBlend/TurboRAG/RAGCache, cache-aware context management.
- Agent memory systems in depth: MemGPT/Letta (incl. sleep-time compute), Mem0/Mem0g, Zep/Graphiti, A-MEM, MemOS, MIRIX, LangMem, ChatGPT memory, Anthropic's memory tool + context editing.
- Memory taxonomies (working/episodic/semantic/procedural) and memory operations (consolidation, forgetting, etc.).
- Memory benchmarks (LoCoMo, LongMemEval) and the credibility crisis in memory-system evaluation.
- Compaction/summarization in production agents.
- The convergence thesis: memory and retrieval as one problem.

Sourcing discipline: every citation below was seen in a live search result or fetched page during this research pass (Aug 2026). Peer-review status, preprint status, and vendor provenance are flagged. Claims from vendor blogs are marked **[vendor]**. 2026 arXiv items seen only as search-result titles (not fetched) are marked **[title-only, details uncertain]**.

---

## Lineage & chronological development

**2023 — Memory as OS metaphor and memory-stream agents.**
- *Generative Agents: Interactive Simulacra of Human Behavior* — Park et al. — arXiv:2304.03442 — 2023. Introduced the memory-stream architecture: store all experiences as natural-language records, periodically synthesize them into higher-level **reflections**, and retrieve dynamically for planning. This reflection loop is the ancestor of nearly every "consolidation" mechanism in 2025–2026 memory products. Heavily cited; peer-reviewed (UIST 2023).
- *MemGPT: Towards LLMs as Operating Systems* — Packer et al. — arXiv:2310.08560 — 2023. Virtual context management inspired by OS memory hierarchies: the LLM self-pages information between a bounded "main context" and external storage, using function calls and interrupts. Established the OS framing that MemOS, Letta, and much of the field inherited. Limitation acknowledged by successors: the paging policy is itself LLM-driven and error-prone, and the original DMR evaluation proved too easy (see benchmarks section).

**2024 — Benchmarks expose the gap; long-context vs RAG becomes an empirical question.**
- *Evaluating Very Long-Term Conversational Memory of LLM Agents* (LoCoMo) — Maharana et al. — arXiv:2402.17753 — 2024. Machine-human pipeline generating multi-session dialogues grounded in personas and temporal event graphs; QA + event summarization tasks. Found LLMs struggle with long-range temporal reasoning even with long-context or RAG. Later became the field's de-facto memory benchmark — and the center of a validity dispute (below). **Two sets of size statistics circulate and both are correct at different scopes:** the paper describes its *original* release — "up to 35 sessions", ~300 turns and ~9K tokens per conversation on average (Tables 1/5: 50 conversations, 19.3 sessions, 304.9 turns, 9,209 tokens) — whereas the *publicly maintained benchmark* that memory papers now evaluate on is the later 10-conversation subset, which is longer per conversation (verified counts in §"Memory benchmarks and the evaluation crisis" below). Quote the 10-conversation numbers whenever discussing memory-system scores.
- *RULER: What's the Real Context Size of Your Long-Context Language Models?* — Hsieh et al. — arXiv:2404.06654 — 2024. 13 synthetic tasks incl. multi-hop tracing and aggregation. Key result: of models advertising ≥32K context, "only half of them can maintain satisfactory performance at the length of 32K"; near-perfect NIAH scores mask large drops on harder tasks (e.g., Yi-34B claiming 200K degrades sharply). Coined the claimed-vs-effective context-length distinction.
- *A Survey on the Memory Mechanism of Large Language Model based Agents* — Zhang et al. — arXiv:2404.13501 — 2024. First systematic survey of agent memory design and evaluation; frames memory as the substrate of agent self-evolution.
- KV-cache reuse line: *RAGCache* (arXiv:2404.12457, up to 4× TTFT / 2.1× throughput), *CacheBlend* (arXiv:2405.16444, selective recomputation to reuse non-prefix chunk caches), *TurboRAG* (arXiv:2410.07590, offline per-chunk KV precomputation, up to 9.4× TTFT reduction). All preprints/systems papers; numbers are authors' own.
- *Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach* (Self-Route) — arXiv:2407.16833 — 2024 (Google DeepMind / U. Michigan per secondary coverage). When resourced sufficiently, long-context beats RAG on average (+7.6% Gemini-1.5-Pro, +13.1% GPT-4, +3.6% GPT-3.5-Turbo), but RAG is far cheaper; Self-Route lets the model self-reflect per query on whether retrieved chunks suffice, matching LC performance at much lower cost. Known limitation: when retrieved chunks look superficially relevant, Self-Route prematurely declares RAG sufficient, failing on queries needing distributed reasoning over the whole document.
- *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory* — Wu et al. — arXiv:2410.10813 — 2024 (rev. 2025). 500 questions over ~40-session (~115K-token) histories; five abilities: information extraction, multi-session reasoning, temporal reasoning, knowledge updates, abstention. Commercial assistants and long-context LLMs show a **30% accuracy drop** (30–60% per ability) across sustained interactions. Also contributed a memory design space (indexing/retrieval/reading) with concrete wins: session decomposition, fact-augmented key expansion, time-aware query expansion.
- *Sufficient Context: A New Lens on RAG Systems* — Joren et al. — arXiv:2411.06037 — 2024 (rev. 2025). Defines "sufficient context" and shows a critical asymmetry: strong models (Gemini 1.5 Pro, GPT-4o, Claude 3.5) use sufficient context well but **confidently answer instead of abstaining when context is insufficient**; smaller models hallucinate or over-abstain regardless. Selective generation using sufficiency signals improves correct-answer rates 2–10%.
- *Don't Do RAG: When Cache-Augmented Generation is All You Need for Knowledge Tasks* (CAG) — Chan et al. — arXiv:2412.15605 — 2024. Preload the whole (small) knowledge base into extended context and cache the KV state; eliminates retrieval latency and retrieval errors for bounded corpora. Explicitly scoped to "knowledge bases of limited scope" — often over-generalized in secondary coverage.
- *LongBench v2* — Bai et al. — arXiv:2412.15204 — 2024. 503 hard multiple-choice questions, contexts 8K–2M words. Human experts: 53.7% (15-min constraint); best direct-answer model: 50.1%; o1-preview with test-time reasoning: 57.7%. Established that long-context *reasoning* (not just recall) is the bottleneck, and that inference-time compute partially substitutes for context handling.

**2025 — Productization of memory; context engineering named; context rot quantified.**
- *Zep: A Temporal Knowledge Graph Architecture for Agent Memory* — arXiv:2501.13956 — 2025. Graphiti engine: three subgraph layers (episodic raw sessions → semantic entities/typed edges with validity intervals → community aggregates); **bi-temporal** edges (valid time + transaction time) so facts can be invalidated rather than deleted. Reported 94.8% vs MemGPT's 93.4% on DMR and up to 18.5% improvement on LongMemEval with ~90% latency reduction vs full context. Preprint + commercial vendor; numbers are self-reported.
- *Long Context vs. RAG for LLMs: An Evaluation and Revisits* — arXiv:2501.01880 — 2025. Independent re-examination of the LC-vs-RAG question (seen in search results; adds nuance that the answer is task-dependent).
- *NoLiMa: Long-Context Evaluation Beyond Literal Matching* — Modarressi et al. — arXiv:2502.05167 — ICML 2025. Needles share minimal lexical overlap with queries, forcing one associative hop. At 32K tokens, **11 of 13 models fall below 50% of their short-context baselines**; GPT-4o drops 99.3% → 69.7%. Attributes degradation to attention's reliance on literal matching at long range. The strongest single piece of evidence that "128K context" is a marketing number for associative tasks.
- *A-MEM: Agentic Memory for LLM Agents* — Xu et al. — arXiv:2502.12110 — 2025. Zettelkasten-inspired: each memory is a structured note (context, keywords, tags); new notes trigger **memory evolution** — updates and link creation on existing notes — so the network self-organizes. Evaluated across six foundation models. Notable as the first widely-cited system where consolidation is bidirectional (new memories rewrite old ones).
- *LangMem SDK* — LangChain — launched Feb 18, 2025 **[vendor]**. Library-level primitives for semantic/procedural/episodic memory, prompt-optimization loops (procedural memory as evolving instructions), storage-agnostic.
- *Sleep-time Compute: Beyond Inference Scaling at Test-time* — Lin et al. (Letta/UC Berkeley) — arXiv:2504.13171 — 2025. Models "think" offline about context before queries arrive: ~5× reduction in test-time compute at equal accuracy; +13% on Stateful GSM-Symbolic, +18% on Stateful AIME when scaled; 2.5× cost amortization across related queries. In Letta the sleep-time agent asynchronously edits the primary agent's core memory (pattern abstraction, contradiction resolution). This is the clearest published instance of *memory consolidation as offline compute*.
- *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory* — arXiv:2504.19413 — 2025. Two-phase pipeline (extract salient facts → update store with ADD/UPDATE/DELETE/NOOP operations), plus Mem0g graph variant. Self-reported: 26% relative LLM-as-judge improvement over OpenAI's memory on LoCoMo, 91% lower p95 latency and >90% token savings vs full context; graph variant ~2% higher overall. Preprint + vendor; its LoCoMo evaluation methodology was directly disputed by Zep (below).
- *Rethinking Memory in LLM based Agents: Representations, Operations, and Emerging Topics* — Du et al. — arXiv:2505.00675 — 2025. Splits memory into **parametric** (weights) and **contextual** (external), and defines six core operations: **consolidation, updating, indexing, forgetting, retrieval, condensation**. The most useful operational taxonomy currently available; retrieval is one operation among six — an implicit argument for the convergence thesis.
- *MemOS: A Memory OS for AI System* — Li et al. (39 authors) — arXiv:2507.03724 — 2025. Unifies plaintext, activation (KV-cache), and parameter memories behind **MemCube** units carrying provenance/versioning metadata, with scheduling (MemScheduler) and lifecycle management; supports transformation between memory forms (e.g., hot plaintext memories promoted into KV-cache or weights). Reported SOTA across PreFEval, PersonaMem, LongMemEval, LoCoMo vs MIRIX/Mem0/Zep/etc. (self-reported, secondary coverage). Ambitious; the memory-form transformation idea is the most architecturally novel part.
- *MIRIX: Multi-Agent Memory System for LLM-Based Agents* — Wang & Chen — arXiv:2507.07957 — 2025. Six typed stores — core, episodic, semantic, procedural, resource, knowledge vault — each managed by a dedicated agent; a router dispatches queries. Self-reported: +35% over RAG baseline on ScreenshotVQA with 99.9% storage reduction; 85.4% on LoCoMo. Illustrates the "typed-store + router" design point (cost: many LLM calls per memory operation).
- *Context Rot: How Increasing Input Tokens Impacts LLM Performance* — Hong, Troynikov, Huber — Chroma technical report — July 14, 2025 **[vendor research, replicable: github.com/chroma-core/context-rot]**. 18 models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3...). Findings: performance degrades non-uniformly with input length even on trivial tasks; lower needle-question semantic similarity → faster degradation; a *single* distractor hurts; **coherent haystacks degrade performance more than shuffled ones**; on LongMemEval, focused ~300-token prompts strongly beat full ~113K prompts. Named the phenomenon the field now organizes around.
- *Effective Context Engineering for AI Agents* — Anthropic engineering blog — Sept 2025 **[vendor, influential]**. Defines context engineering as "the set of strategies for curating and maintaining the optimal set of tokens (information) during LLM inference"; introduces the **attention budget** framing (every token depletes it; n² pairwise relationships strain focus); prescribes compaction, structured note-taking to external memory, sub-agent architectures returning 1–2K-token distillates, and **just-in-time retrieval** (agents load data via tools at runtime) over pre-inference embedding retrieval. Karpathy's earlier formulation (via Simon Willison, June 27, 2025): "context engineering is the delicate art and science of filling the context window with just the right information"; Tobi Lutke: "the art of providing all the context for the task to be plausibly solvable by the LLM."
- *Anthropic context management launch* — Sept 29, 2025 **[vendor]**. Server-side **context editing** (auto-clearing stale tool calls/results, prompt-cache-aware) + file-based **memory tool** persisting across conversations. Reported: memory+editing **+39%** over baseline on agentic search, editing alone +29%; in a 100-turn web-search eval, editing enabled otherwise-failing workflows while cutting token consumption **84%**. Claude Code ships compaction ("microcompact") natively.
- ChatGPT memory analysis — Shlok Khemani, shloked.com — 2025 (independent reverse-engineering; uncertain completeness since based on observed behavior, not OpenAI documentation). ChatGPT memory = four components: interaction metadata, recent-conversation context (~last 40 conversations, user messages only), user-editable "Model Set Context," and hidden AI-generated "User Knowledge Memories." Crucially: "No extraction of individual memories. No vector databases. No knowledge graphs. No RAG." — everything is injected every query. The bet: "stronger models with more compute will obviate the need for clever engineering" (bitter-lesson argument).

**2026 — Second-generation critiques and re-framings (titles seen in search; most not yet fetched).**
- *Route Before Retrieve: Activating Latent Routing Abilities of LLMs for RAG vs. Long-Context Selection* — arXiv:2605.10235 — 2026. Successor to Self-Route moving the routing decision before retrieval.
- *Graph-based Agent Memory: Taxonomy, Techniques, and Applications* — arXiv:2602.05665 — 2026 **[title-only]**.
- *Memory is Reconstructed, Not Retrieved: Graph Memory for LLM Agents* — arXiv:2606.06036 — 2026 **[title-only]** — title signals a shift from lookup-metaphor to reconstruction-metaphor memory.
- *Diagnosing and Mitigating Context Rot in Long-horizon Search* — arXiv:2606.29718 — 2026 **[title-only]** — context rot now a named research target.
- *LOCA-bench: Benchmarking Language Agents Under Controllable and Extreme Context Growth* — arXiv:2602.07962 — 2026 **[title-only]**.
- 2026 practitioner comparisons (Vectorize, Atlan, Medium/DevGenius multi-system comparisons) **[vendor/secondary]** converge on: hybrid vector+graph architectures dominant; episodic/semantic/procedural scopes standard; no memory benchmark has consolidated as authoritative; newer evals include LongMemEval variants, MemoryArena, LoCoMo-Plus, Hindsight.

---

## State of the art — mid-2026 snapshot

1. **Framing**: "Context engineering" has displaced both "prompt engineering" and, partially, "RAG" as the organizing abstraction. The unit of design is the full context state (system prompt, tools, retrieved data, message history, memory injections) under an explicit attention budget.
2. **Models**: Frontier models ship 200K–1M+ nominal contexts, but effective associative context remains far smaller (NoLiMa-style tasks: often ≤2–8K for reliable latent-association retrieval; RULER/LongBench v2 show reasoning quality decays well before nominal limits). Context rot is accepted as an empirical law, not a bug to be patched.
3. **Production pattern**: agentic just-in-time retrieval (tool-driven file/search access) + compaction + external note-taking/memory files + server-side context editing. Anthropic's stack (context editing + memory tool + compaction) is the reference implementation; Claude Code and equivalents use it natively.
4. **Memory products**: Mem0, Zep/Graphiti, Letta, MemOS, MIRIX and a long tail. Architectural convergence: extraction pipeline → typed store (vector + graph, increasingly temporal/bi-temporal) → scoped retrieval at query time → background consolidation (sleep-time-style). OpenAI is the notable dissenter: ChatGPT memory injects everything, betting on the bitter lesson.
5. **Evaluation**: in crisis. LoCoMo is discredited for discriminating between systems (full-context baseline ≈73% beats several memory systems that market SOTA on it); LongMemEval is the more respected target; vendor self-reports dominate and directly contradict one another.
6. **Economics**: KV-cache reuse is the binding constraint shaping context layout. Prompt caching makes *append-only, stable-prefix* context cheap and *edited* context expensive; this is quietly dictating agent architecture (context editing was designed to be cache-preserving; CAG/TurboRAG/CacheBlend trade recomputation against cache reuse).

---

## Context failures: the empirical case against "just use long context"

Four independent lines of evidence, from different groups, with consistent conclusions:

- **RULER** (arXiv:2404.06654): claimed vs effective context; half of ≥32K-claiming models fail at 32K on non-trivial tasks.
- **NoLiMa** (arXiv:2502.05167, ICML 2025): remove lexical overlap between query and needle → 11/13 models below 50% of baseline at 32K; GPT-4o 99.3→69.7. Mechanistic claim: long-range attention leans on literal matching; associative retrieval collapses with distance.
- **LongBench v2** (arXiv:2412.15204): even at moderate lengths, deep-reasoning-over-context questions hold best models to ~50% (human 53.7%); test-time reasoning (o1) helps more than more context.
- **Chroma context rot** (technical report, 2025): degradation is non-uniform and appears on *trivially simple* tasks (repeated-word replication); one distractor hurts; and — the most theoretically interesting finding — **coherent context hurts more than shuffled context**, i.e., structure itself interacts pathologically with attention. The LongMemEval sub-experiment (focused 300-token prompt ≫ full 113K prompt) is the cleanest demonstration that *separating retrieval from reasoning* is worth real accuracy, which is the core empirical justification for RAG/memory systems in the long-context era.

Disagreement to note: model vendors' NIAH-based marketing (near-perfect recall to 1M tokens) vs all four sources above. The resolution is that NIAH with lexical overlap is the easiest possible probe; every harder probe shows early degradation.

## Long-context vs RAG

- Self-Route (arXiv:2407.16833): LC > RAG on quality when affordable; RAG >> LC on cost; per-query self-routing recovers most LC quality at ~RAG cost. Failure mode: superficially-relevant chunks trick the router on distributed-reasoning queries.
- Sufficient context (arXiv:2411.06037): reframes RAG failure as a 2×2 (context sufficient? × model correct?). Headline: strong models fail mostly by *not abstaining* on insufficient context — hallucination in RAG is often a calibration failure, not a retrieval failure. Design implication: sufficiency estimation is a first-class component, not an afterthought.
- arXiv:2501.01880 and Route Before Retrieve (arXiv:2605.10235, 2026) continue the line; the 2026 consensus in secondary literature is a hybrid: retrieval to select, long context to reason within the selection, routing to decide the mix — plus the observation (Chroma) that even *within* the long window you pay context-rot tax, so selection helps even when everything fits.

## KV-cache economics

- **Prompt caching** (all major APIs) makes the prefix the unit of economy: stable system prompts and append-only histories are ~10× cheaper. Consequence: naive context editing (deleting mid-context tokens) invalidates caches; Anthropic's context editing is explicitly designed to run "after prompt cache lookup" to stay cache-friendly (platform docs; NousResearch hermes-agent issue #526 discusses this integration).
- **CAG** (arXiv:2412.15605): for bounded corpora, preload + cache KV; no retrieval, no retrieval errors. Scope-limited by definition and by context rot (preloading 100K tokens re-imports the degradation the benchmarks above document).
- **CacheBlend** (arXiv:2405.16444): reuse per-chunk KV caches at *non-prefix* positions via selective recomputation of a small token subset — the key unlock for composable cached RAG contexts. **TurboRAG** (arXiv:2410.07590): offline per-chunk KV precomputation, up to 9.4× TTFT reduction. **RAGCache** (arXiv:2404.12457): 4× TTFT / 2.1× throughput via caching retrieved-document states. 2025–2026 follow-ups: CacheClip (arXiv:2510.10129), approximate caching (arXiv:2503.05530), grounded cache routing (arXiv:2605.27494) **[title-only]**.
- Synthesis: KV-cache reuse creates a *positional-independence requirement* (chunks must be useful regardless of position) that transformer attention does not natively satisfy; CacheBlend-style recomputation is a patch. A next-gen framework should treat cache layout as a first-class scheduling problem — MemOS's "activation memory" as a managed resource is the only published architecture that does.

## Agent memory systems in depth

| System | Core abstraction | Consolidation | Temporal model | Evidence status |
|---|---|---|---|---|
| MemGPT/Letta (2310.08560) | OS-style paged context; self-editing core memory | Sleep-time agent rewrites core memory offline (2504.13171) | none intrinsic | Peer-reviewed origins; sleep-time is preprint with strong numbers |
| Mem0/Mem0g (2504.19413) | Extract→update pipeline; ADD/UPDATE/DELETE ops; optional graph | LLM-adjudicated update at write time | timestamps on memories | Preprint + vendor; LoCoMo eval disputed |
| Zep/Graphiti (2501.13956) | Temporal KG; episodic→semantic→community layers | Edge invalidation, community summarization | **bi-temporal** (valid + transaction time) | Preprint + vendor; DMR/LongMemEval self-reported |
| A-MEM (2502.12110) | Zettelkasten notes with dynamic links | **Memory evolution**: new notes rewrite/relink old notes | none intrinsic | Preprint; 6-model eval |
| MemOS (2507.03724) | MemCube; unifies plaintext/activation/parameter memory | Lifecycle mgmt; cross-form promotion | versioning/provenance metadata | Preprint; broadest claims, self-reported SOTA |
| MIRIX (2507.07957) | Six typed stores, one manager-agent each + router | Per-store manager agents | episodic store timestamps | Preprint; multimodal focus |
| LangMem (LangChain, 2/2025) | SDK primitives; procedural memory = prompt optimization | Optimizer rewrites instructions | app-defined | Vendor SDK, no benchmark claims |
| ChatGPT memory (shloked.com analysis) | Inject-everything: 4 components, no retrieval | Periodic hidden summary regeneration | recency window (~40 convos) | Reverse-engineered; uncertain |
| Claude memory tool + context editing (9/2025) | Agent-managed memory *files*; server-side context pruning | Agent-driven note curation; compaction | none intrinsic | Vendor, with published eval deltas (+39%, −84% tokens) |

Key architectural divide (mid-2026): **extraction-based** memory (Mem0, Zep, MIRIX — an LLM decides at write time what a memory "is") vs **agent-curated files/notes** (Claude memory tool, Letta core memory — the agent itself writes/edits durable artifacts) vs **inject-everything** (ChatGPT — no write-time decisions at all). These embody different answers to *when intelligence is applied*: write time, read time, or never (defer to the model).

## Memory taxonomies

Two taxonomies dominate:
- **Cognitive-psychology scopes**: working (in-context), episodic (specific past interactions), semantic (facts/preferences), procedural (learned behaviors/instructions). Standardized across LangMem, MIRIX, and 2026 practitioner literature; MIRIX adds resource and knowledge-vault stores.
- **Operational taxonomy** (Du et al., arXiv:2505.00675): parametric vs contextual memory; six operations — consolidation, updating, indexing, forgetting, retrieval, condensation. This is more useful for framework design because it exposes that products differ mainly in *which operations they implement at all*: nearly all do indexing+retrieval; few do principled forgetting; consolidation is usually ad-hoc summarization; condensation (compaction) lives in a separate product category despite being the same operation.

Consolidation & forgetting specifics: Generative Agents' reflection (2304.03442) → A-MEM memory evolution (2502.12110) → Letta sleep-time compute (2504.13171) is the consolidation lineage; forgetting remains mostly TTL/supersede heuristics (Graphiti edge invalidation is the most principled: facts are invalidated, not deleted, preserving auditability). No published system implements interference-based or utility-based forgetting with demonstrated end-task gains — a gap.

## Memory benchmarks and the evaluation crisis

- **LoCoMo** (2402.17753): the released benchmark (`snap-research/locomo`, `locomo10.json`) is 10 dialogues, 19–32 sessions each (avg 27.2), 369–689 turns each (avg ~588), ~105–260 QA pairs each — counts computed directly from the distributed file. Token length ~16–26K per conversation (Zep's measurement; Mem0's paper says "~600 dialogues and 26000 tokens on average" — note a direct word count of the distributed file, ~8.0–16.2K words per conversation, is consistent only with the low end of that range, so treat the 26K figure as the upper bound rather than the average). This subset is *longer per conversation* than the averages in the paper's own tables (50 conversations, 19.3 sessions, 304.9 turns, 9.2K tokens), which is why the "up to 35 sessions / ~300 turns" figure from the abstract and the "~27 sessions / ~600 turns" figure here disagree: different releases, not conflicting measurements. Problems now well documented: (a) fits in modern context windows, so it doesn't stress memory — Zep's analysis shows a **naive full-context baseline scores ~73%, beating Mem0's best (~68%)** on the very benchmark used to claim SOTA; (b) no knowledge-update evaluation; (c) data-quality defects (category 5 unusable, speaker misattribution, ambiguous questions); (d) LLM-judge calibration issues noted by community audits.
- **The Mem0–Zep dispute** (Zep blog "Lies, Damn Lies & Statistics" + Mem0 responses) **[both vendors]**: Mem0's paper reported Zep at 65.99% on LoCoMo; Zep alleges misconfiguration (single-user graph applied to two speakers, timestamps appended to text instead of `created_at`, sequential search inflating latency) and reports 75.14%±0.17 when configured correctly. Mem0 separately corrected Zep's own earlier claim from 84% to 58.44% alleging category errors; Zep counter-claimed 75.14%. Takeaway for researchers: **every cross-vendor memory number published to date should be treated as unverified**; the benchmark is small enough and the harnesses opinionated enough that configuration choices swing results by 10–20 points.
- **LongMemEval** (2410.10813): 115K-token (S) and ~500-session (M) regimes; five abilities incl. knowledge updates and abstention that LoCoMo lacks; 30–60% drops for commercial systems. Currently the most respected target, but at 500 questions it is also saturating and vendor-tuned.
- 2026 additions (MemoryArena, LoCoMo-Plus, Hindsight, LOCA-bench, BEAM — seen in secondary coverage/titles): fragmentation without consolidation; none independently governed.
- Structural critique: memory benchmarks measure *conversational recall QA*, but production agent memory failures are about *behavioral* consequences (repeating mistakes, stale procedural knowledge, cross-task contamination). No benchmark measures whether memory makes an agent *act* better over weeks; LoCoMo/LongMemEval measure whether it can answer quiz questions about its history.

## Compaction and context management in production

- Anthropic's stack (Sept 2025): **context editing** (server-side removal of stale tool results, applied after cache lookup — cache-preserving), **memory tool** (agent-managed persistent files), **compaction** (server-side whole-conversation summarization near the window limit), plus Sonnet 4.5's built-in context awareness (model told its remaining token budget). Published deltas: +29% (editing), +39% (editing+memory), −84% tokens in a 100-turn eval. Claude Code layers "microcompact" logic on top (hyperdev.matsuoka.com analysis of protecting context).
- Anthropic's engineering guidance: compaction should preserve "architectural decisions, unresolved bugs, and implementation details"; sub-agents should return 1–2K-token distillates; prefer just-in-time tool-driven retrieval over pre-computed embedding retrieval for agentic work.
- Failure modes of compaction observed in practice/secondary literature: irreversibility (summarized-away details cannot be recovered), summary drift over repeated compactions, and loss of exact strings (paths, IDs) that agents need verbatim. The memory-tool pattern (write critical facts to files *before* compaction) exists precisely to patch this.

## The convergence thesis: memory ≡ retrieval

Evidence **for**: (1) Du et al.'s taxonomy places retrieval as one of six memory operations — RAG is a degenerate memory system with only indexing+retrieval, no write path. (2) Every serious memory product is architecturally a RAG stack with a write-time pipeline bolted on (extraction, dedup, temporal indexing) — Mem0, Zep, MIRIX all retrieve chunks/edges into context at query time. (3) Anthropic's just-in-time framing dissolves the boundary: an agent grep-ing its own memory files and grep-ing a codebase is the same operation. (4) MemOS explicitly unifies retrieval corpora, KV caches, and weights as memory forms of one substrate. (5) Chroma's LongMemEval experiment shows the *reason* both exist is identical: focused context beats full context, so both memory and RAG are context-selection mechanisms fighting context rot.

Evidence **against**: (1) Memory has a **write/consolidation problem** retrieval lacks: deciding what to store, updating/invalidating, resolving contradictions — LongMemEval's knowledge-update and abstention abilities have no RAG analogue, and extraction-time errors are a failure class RAG cannot exhibit. (2) Temporality: bi-temporal validity (Zep) is meaningless for a static corpus. (3) Provenance/trust asymmetry: memories are self-generated (hallucinations can be *stored and later retrieved as facts* — memory poisoning/contamination, cf. MemGuard arXiv:2605.28009 **[title-only]**), while RAG corpora are at least externally grounded. (4) ChatGPT's inject-everything design shows memory can be implemented with *no retrieval at all* at current personal-memory scales.

Synthesis for a next-gen framework: memory and retrieval share a read path (context selection under an attention budget) but differ on the write path (consolidation, invalidation, provenance). A unified framework should have one read abstraction and an explicit, first-class write/lifecycle abstraction — the read side is where RAG expertise transfers; the write side is where current systems are weakest.

---

## Comparison tables

### Long-context vs RAG vs memory-system positioning

| Approach | Quality (in-scope) | Cost/latency | Failure class | Scale ceiling |
|---|---|---|---|---|
| Full long context | Highest when fits & task is extractive (Self-Route) | Highest; mitigated by prompt caching | Context rot; non-abstention on distractors | Nominal window; effective window is 4–32K for associative tasks (NoLiMa) |
| Classic RAG | High if retrieval hits | Low | Retrieval misses; insufficient-context hallucination (Joren et al.) | Unbounded corpus |
| CAG (preloaded KV) | ≈LC for small corpora | Very low **marginal** per query; high amortized — see note below | Same as LC + staleness of cache | Small, static corpora only |
| Extraction memory (Mem0/Zep) | High on conversational recall (self-reported) | Low read cost; nontrivial write cost | Extraction errors, stale/contradictory memories, poisoning | Large, but write-pipeline LLM cost scales with traffic |
| Agent-curated files (Claude memory tool) | +10% over editing-only (Anthropic eval) | Low; agent-driven | Agent forgets to write; unstructured sprawl | Agent-manageable file trees |
| Inject-everything (ChatGPT) | Good at personal scale (uncertain—no public eval) | Fixed per-query overhead | Context-rot tax on every query; no selectivity | Bounded by window; won't scale to enterprise memory |

**Note on the CAG cost row (reconciles with `foundations-and-surveys.md`, which rates CAG at "≥10× RAG").** The two ratings measure different quantities and are not in conflict. *Marginal* cost per query is very low: once the corpus KV state is cached, a query pays no retrieval and no re-prefill, which is the economics this table is about. *Amortized/absolute* cost is high: you pay one full prefill over the entire corpus plus continuous KV storage, and you re-pay it on every corpus change — the basis for the RAGFlow-style analysis quoted in `foundations-and-surveys.md` (≥1 order of magnitude above RAG at scale). CAG therefore wins only where query volume per cache-build is high and the corpus is static; the crossover point, not the headline multiplier, is the real design question.

### Benchmark suitability

| Benchmark | Stresses | Doesn't stress | Status mid-2026 |
|---|---|---|---|
| DMR (MemGPT) | basic session recall | everything else | Saturated (93–95%) |
| LoCoMo (2402.17753) | multi-session QA, temporal event graphs | knowledge updates, true long-horizon (fits in context) | Discredited for system comparison; data-quality issues |
| LongMemEval (2410.10813) | 115K+ histories, updates, abstention, temporal reasoning | behavioral/agentic consequences of memory | Current default; saturating |
| NoLiMa / RULER / LongBench v2 | model-level context capacity | system-level memory design | Healthy; model-facing not system-facing |
| MemoryArena, LoCoMo-Plus, Hindsight, LOCA-bench (2026) | varied | — | Fragmented, none consolidated |

---

## Failure modes & critiques

1. **Context rot is universal and task-agnostic** (Chroma, NoLiMa, RULER): degradation begins far below nominal limits, is non-uniform, worsens with semantic distance and distractors, and — counterintuitively — with input *coherence*. Any framework that answers "add more context" is betting against measured model behavior.
2. **Non-abstention under insufficient context** (Joren et al.): the dominant RAG hallucination mode in strong models is answering anyway. Retrieval quality improvements don't fix a calibration failure.
3. **Write-time extraction errors**: extraction-based memories commit an LLM's interpretation at write time; errors are persistent and compounding (retrieved later as ground truth). Memory contamination/poisoning is an emerging security class (MemGuard, arXiv:2605.28009 [title-only]; persona drift, arXiv:2605.09863 [title-only]).
4. **Consolidation is lossy and irreversible**: compaction/summarization drops exact strings and minority details; repeated compaction drifts. Production mitigations (write-before-compact) are conventions, not guarantees.
5. **Temporal reasoning remains weak**: LoCoMo and LongMemEval both flag long-range temporal reasoning as the worst category; only Zep/Graphiti treats time bi-temporally, and even its gains are self-reported.
6. **Evaluation is vendor-captured**: the Mem0↔Zep dispute demonstrated that harness configuration swings LoCoMo scores by 10–20 points; every SOTA claim in the memory space is currently self-reported on benchmarks the claimants helped popularize. A full-context baseline beating dedicated memory systems on LoCoMo (~73% vs ~68%) is the single most damning datum.
7. **Benchmarks measure recall QA, not behavior**: no standard eval measures whether memory improves agent *actions* over long horizons (fewer repeated mistakes, better tool choices), which is the actual product claim.
8. **Router/typed-store overhead**: multi-agent memory managers (MIRIX) and per-write LLM adjudication (Mem0) impose LLM-call costs on every interaction; the economics at production traffic are rarely reported.
9. **Cache-hostility of dynamic context**: mid-context edits invalidate KV caches; most academic memory architectures ignore serving economics entirely (MemOS and Anthropic's context editing are exceptions).
10. **The bitter-lesson risk**: OpenAI's inject-everything design and each capability jump (o1 on LongBench v2 beating humans; Sonnet 4.5 context awareness) erode the value of engineered memory middleware. Frameworks whose value is "compensate for model weakness at length L" have a depreciating asset; frameworks whose value is "govern what the model should know, when, with provenance" do not.

## Open problems

1. **Sufficiency-aware context assembly.** No system closes the loop from Joren et al.: estimate context sufficiency *before* generation, and route (retrieve more / abstain / escalate to long context) on that estimate. Self-Route does this crudely post-retrieval; a principled sufficiency estimator integrated into assembly is open.
2. **A write-path theory.** Read-path (retrieval) is mature; the write path — what to store, at what granularity, when to update vs supersede vs forget, with what provenance — has no formal framework. Du et al.'s six operations name the space; nobody has cost models, consistency guarantees, or correctness criteria for them (e.g., when is it *safe* for a new memory to overwrite an old one, à la A-MEM evolution?).
3. **Reversible consolidation.** Compaction is lossy-irreversible. Open: hierarchical/lossless-underneath consolidation where summaries are views over retained ground truth with cheap drill-down — combining Graphiti's invalidate-don't-delete with compaction's token savings.
4. **Utility-based forgetting.** All deployed forgetting is TTL/supersede heuristics. Open: forgetting driven by measured retrieval utility and interference (does removing a memory improve downstream task success?), with any end-task evidence at all.
5. **Behavioral memory benchmarks.** Design evals where memory quality is measured by *agent action quality over weeks* (repeated-task efficiency, error non-repetition, procedural improvement), not conversational QA — and governed independently of vendors. LOCA-bench-style controlled context growth is a start.
6. **Cache-aware context scheduling.** Treat KV-cache layout, prompt-cache prefix stability, and context edits as a joint scheduling problem with an explicit cost model (tokens × recomputation × rot-tax). MemOS gestures at this; no open framework implements it.
7. **Memory provenance and trust.** Self-generated memories need typed provenance (observed vs inferred vs user-asserted), confidence decay, and contamination defenses. Currently only metadata fields (MemOS MemCubes, Graphiti transaction time) without enforcement semantics.
8. **Resolving the convergence question architecturally.** If memory = retrieval + write-path, a next-gen RAG framework should expose one read abstraction (context selection under attention budget, sufficiency-checked) over heterogeneous stores (corpus, episodic log, semantic graph, KV caches) and a first-class lifecycle layer (consolidate/update/forget with provenance). Testable prediction from this survey: such a system should beat both inject-everything (rot tax) and extraction-pipelines (write-time errors) on LongMemEval-M-scale workloads — no published system has demonstrated this across regimes.

---

## Bibliography

Peer-reviewed / heavily cited:
- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior*, arXiv:2304.03442 (2023, UIST).
- Packer et al., *MemGPT: Towards LLMs as Operating Systems*, arXiv:2310.08560 (2023).
- Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents* (LoCoMo), arXiv:2402.17753 (2024).
- Hsieh et al., *RULER: What's the Real Context Size of Your Long-Context Language Models?*, arXiv:2404.06654 (2024).
- Modarressi et al., *NoLiMa: Long-Context Evaluation Beyond Literal Matching*, arXiv:2502.05167 (ICML 2025).
- Bai et al., *LongBench v2*, arXiv:2412.15204 (2024).
- Wu et al., *LongMemEval*, arXiv:2410.10813 (2024).
- Joren et al., *Sufficient Context: A New Lens on RAG Systems*, arXiv:2411.06037 (2024).
- Zhang et al., *A Survey on the Memory Mechanism of LLM-based Agents*, arXiv:2404.13501 (2024).
- Du et al., *Rethinking Memory in LLM based Agents: Representations, Operations, and Emerging Topics*, arXiv:2505.00675 (2025).

Preprints (2024–2026):
- *Self-Route / RAG or Long-Context LLMs?*, arXiv:2407.16833 (2024).
- *Long Context vs. RAG for LLMs: An Evaluation and Revisits*, arXiv:2501.01880 (2025).
- *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, arXiv:2501.13956 (2025).
- Xu et al., *A-MEM: Agentic Memory for LLM Agents*, arXiv:2502.12110 (2025).
- Lin et al., *Sleep-time Compute: Beyond Inference Scaling at Test-time*, arXiv:2504.13171 (2025).
- *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv:2504.19413 (2025).
- Li et al., *MemOS: A Memory OS for AI System*, arXiv:2507.03724 (2025).
- Wang & Chen, *MIRIX: Multi-Agent Memory System for LLM-Based Agents*, arXiv:2507.07957 (2025).
- Chan et al., *Don't Do RAG: When Cache-Augmented Generation is All You Need*, arXiv:2412.15605 (2024).
- *CacheBlend*, arXiv:2405.16444 (2024); *RAGCache*, arXiv:2404.12457 (2024); *TurboRAG*, arXiv:2410.07590 (2024); *CacheClip*, arXiv:2510.10129 (2025); *Leveraging Approximate Caching for Faster RAG*, arXiv:2503.05530 (2025).
- 2026 [title-only, seen in search results]: *Route Before Retrieve*, arXiv:2605.10235; *Graph-based Agent Memory: Taxonomy*, arXiv:2602.05665; *Memory is Reconstructed, Not Retrieved*, arXiv:2606.06036; *Diagnosing and Mitigating Context Rot in Long-horizon Search*, arXiv:2606.29718; *LOCA-bench*, arXiv:2602.07962; *MemGuard*, arXiv:2605.28009; *Grounded Cache Routing for RAG*, arXiv:2605.27494.

Technical reports, docs, and vendor/analyst posts:
- Hong, Troynikov, Huber, *Context Rot* — Chroma technical report (July 2025) — https://www.trychroma.com/research/context-rot ; code: https://github.com/chroma-core/context-rot
- Anthropic, *Effective Context Engineering for AI Agents* (Sept 2025) — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic/Claude, *Context management* announcement (Sept 29, 2025) — https://claude.com/blog/context-management ; docs: https://platform.claude.com/docs/en/build-with-claude/context-editing and https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Letta, *Sleep-time Compute* blog — https://www.letta.com/blog/sleep-time-compute/ ; code: https://github.com/letta-ai/sleep-time-compute
- LangChain, *LangMem SDK launch* (Feb 18, 2025) — https://www.langchain.com/blog/langmem-sdk-launch
- Simon Willison, *Context engineering* (Jun 27, 2025; Karpathy & Lutke quotes) — https://simonwillison.net/2025/Jun/27/context-engineering/
- Shlok Khemani, *ChatGPT memory and the bitter lesson* — https://www.shloked.com/writing/chatgpt-memory-bitter-lesson
- Zep, *Lies, Damn Lies & Statistics: Is Mem0 Really SOTA in Agent Memory?* [vendor] — https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/
- Mem0 GitHub — https://github.com/mem0ai/mem0 ; Mem0 benchmark blog [vendor] — https://mem0.ai/blog/ai-memory-benchmarks-in-2026 ; https://mem0.ai/blog/state-of-ai-agent-memory-2026
- CAG reference implementation — https://github.com/hhhuang/CAG
- Secondary comparisons [vendor/analyst, use with caution]: Vectorize (https://vectorize.io/articles/best-ai-agent-memory-systems, https://vectorize.io/articles/mem0-vs-zep), Atlan (https://atlan.com/know/best-ai-agent-memory-frameworks-2026/, https://atlan.com/know/zep-vs-mem0/), DevGenius 2026 memory-systems comparison (https://blog.devgenius.io/ai-agent-memory-systems-in-2026-mem0-zep-hindsight-memvid-and-everything-in-between-compared-96e35b818da8), hyperdev.matsuoka.com on Claude Code context protection (https://hyperdev.matsuoka.com/p/how-claude-code-got-better-by-protecting), NousResearch hermes-agent issue #526 (context-editing API integration notes).
