# Agentic RAG, Search Agents & Deep Research Systems — Landscape Review (as of mid-2026)

Research dossier for a next-generation RAG framework. Emphasis on failure modes, critiques, and open problems. All sources were verified in this session against arXiv abstract pages, official engineering blogs, GitHub READMEs, or search results, except items marked with a dagger (†), which are cited from author knowledge of well-known foundational work and should be re-verified before publication.

---

## Scope

This document covers the "retrieval becomes an agent behavior" branch of the RAG landscape:

- Taxonomy of agentic RAG patterns (routing, planning, ReAct loops, reflection, corrective loops, multi-agent orchestration).
- Deep research systems: proprietary (OpenAI Deep Research, Gemini Deep Research, Perplexity, Anthropic's Claude Research) and open-source (GPT-Researcher, Hugging Face smolagents open-deep-research, Tongyi DeepResearch).
- RL-trained search agents: the WebGPT lineage through Search-R1, R1-Searcher, ReSearch, DeepRetrieval, s3, DeepResearcher, Search-o1, the Alibaba WebAgent series (WebDancer/WebSailor), Kimi-Researcher, and 2026 process-reward successors.
- The agentic-search-vs-static-RAG debate ("RAG is dead" discourse, Claude Code's grep-based search, and rebuttals).
- Retrieval exposed as tools (MCP), tool-design principles for retrieval.
- Iterative retrieval budgets, test-time scaling for search, and token economics.
- Browse/search benchmarks: GAIA, BrowseComp, Humanity's Last Exam, DeepResearch Bench I/II.
- Multi-agent retrieval orchestration, context handoff, parallel retrieval.
- Empirical evidence on when agentic retrieval beats single-shot retrieval, and at what cost.

Out of scope (covered by sibling dossiers): dense/sparse retriever internals, embedding models, chunking, GraphRAG internals, long-term agent memory architectures.

---

## Lineage & chronological development

### Phase 0 — Static RAG and the first browsing agent (2020–2022)

- **RAG** — Lewis et al. — NeurIPS 2020 — arXiv 2005.11401† — retrieve-then-generate with a frozen dense retriever; the "static pipeline" every agentic system now defines itself against.
- **WebGPT: Browser-assisted Question-Answering with Human Feedback** — Nakano et al. (OpenAI) — arXiv 2112.09332 — 2021. Fine-tuned GPT-3 to operate a text browser: behavior cloning on human demonstrations, then rejection sampling against a human-preference reward model. Best model's answers preferred to human demonstrators' 56% of the time on ELI5. This is the direct ancestor of every RL-trained search agent and of Deep Research; its core limitations (expensive human demonstrations, reward-model gaming) set the agenda for the 2025 RLVR wave.
- **ReAct: Synergizing Reasoning and Acting in Language Models** — Yao et al. — ICLR 2023 — arXiv 2210.03629 — interleaved thought/action/observation traces; still the dominant inner loop of nearly every agentic RAG system in 2026 (Tongyi DeepResearch explicitly ships a "vanilla ReAct mode" to demonstrate intrinsic ability).

### Phase 1 — Iterative and self-reflective retrieval, prompt-orchestrated (2022–2024)

- **IRCoT** (Trivedi et al., ACL 2023, arXiv 2212.10509†) and **FLARE** (Jiang et al., 2023, arXiv 2305.06983†): interleave retrieval with chain-of-thought; retrieval triggered by reasoning state rather than issued once. Prompt-only, no learning.
- **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection** — Asai et al. — arXiv 2310.11511 — 2023. Trains a single LM with special "reflection tokens" to decide *when* to retrieve and to critique retrieved passages and its own generations. The key conceptual move: retrieval decisions become model outputs, not pipeline configuration. Limitation: reflection tokens are trained offline against a fixed critic; behavior does not adapt to live corpus quality.
- **Corrective RAG (CRAG)**† and adaptive-RAG variants (2024): a lightweight evaluator grades retrieved results and triggers re-retrieval/web fallback. These are catalogued as "corrective" and "adaptive" architectures in the Singh et al. survey (below).
- **Model Context Protocol (MCP)** — Anthropic, November 2024† — standardized tool interface that later becomes the dominant way retrieval is exposed to agents (see the tool-design section).

### Phase 2 — Deep research products and the taxonomy consolidates (Dec 2024 – mid 2025)

- **Gemini Deep Research** (Google, Dec 2024†) and **OpenAI Deep Research** (Feb 3, 2025; per Wikipedia's sourced article, initially a fine-tuned o3 browsing model, 5–30 min autonomous sessions, HLE 26.6 at launch vs 9.4 for DeepSeek-R1 and 3.3 for GPT-4o; since Feb 2026 based on a GPT-5.2 derivative). OpenAI's own documentation concedes it "occasionally makes factual hallucinations," "may reference rumors," and "struggles with conveying uncertainty."
- **Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG** — Singh et al. — arXiv 2501.09136 — Jan 2025, revised through April 2026. The canonical taxonomy: agentic design patterns (reflection, planning, tool use, multi-agent collaboration) crossed with architectures (single-agent router, multi-agent, hierarchical, corrective, adaptive, graph-based). The v2 revision organizes by agent cardinality, control structure, autonomy level, and knowledge-representation style. Identified open challenges: evaluation, coordination, memory management, efficiency, governance.
- **Search-o1: Agentic Search-Enhanced Large Reasoning Models** — Li et al. — arXiv 2501.05366 — Jan 2025. Bolted agentic retrieval onto o1-style long-reasoning models; the "Reason-in-Documents" module compresses retrieved documents before injecting them into the reasoning chain — an early recognition that raw retrieved text pollutes reasoning context.
- **Hugging Face open-deep-research** (smolagents, Feb 2025 blog): open reproduction reaching 55.15% GAIA validation vs OpenAI's reported 67.36%; found that code-expressed actions ("CodeAgent") beat JSON tool calls, cutting steps ~30%.
- **GPT-Researcher** (assafelovic, GitHub, 28.8k stars): planner + parallel execution agents + publisher; ~$0.40 per research run on o3-mini; design credits Plan-and-Solve and STORM. The most-deployed open deep-research scaffold before the RL wave.

### Phase 3 — The RLVR search-agent wave (Feb – Oct 2025)

Verifiable-reward RL (GRPO-family) replaced WebGPT's human-preference RL. Within eight months:

- **DeepRetrieval** (Jiang et al., arXiv 2503.00223): RL for query generation against *real* search engines/retrievers using retrieval metrics as reward; 65.07% recall on publication search vs 24.68% prior SOTA; a 3B model beats GPT-4o/Claude-3.5-Sonnet prompting on 11/13 datasets. Optimizes the query, not the whole loop.
- **R1-Searcher** (Song et al., arXiv 2503.05592): two-stage outcome-based RL to incentivize autonomous search invocation; no process rewards, no distillation cold start.
- **Search-R1** (Jin et al., arXiv 2503.09516): interleaved reason+search RL on veRL with retrieved-token masking; became the standard baseline and open framework.
- **ReSearch** (Chen et al., arXiv 2503.19470, NeurIPS 2025): search as part of the reasoning chain, RL without supervised reasoning data; reflection and self-correction emerge un-taught.
- **DeepResearcher** (Zheng et al., arXiv 2504.03160): scaled RL to the *live web* rather than a static local corpus; +28.9 points over prompting baselines and +7.2 over RAG-based RL agents even when those got web access at inference — evidence that training environment realism matters, not just the algorithm. Emergent behaviors: planning, cross-source validation, self-redirection, admitting ignorance.
- **s3** (Jiang et al., arXiv 2505.14146): decouples a small RL-trained *searcher* from a frozen *generator*; "Gain Beyond RAG" reward = improvement in generation accuracy over naive RAG. Needs only 2.4k training samples to beat baselines trained on ~70× more data. Important architectural counterpoint to end-to-end monoliths: the searcher is model-agnostic and works with proprietary generators.
- **Alibaba WebAgent series**: **WebDancer** (Wu et al., arXiv 2505.22648, NeurIPS 2025 — 4-stage pipeline: browsing-data construction → trajectory sampling → SFT cold start → RL) and **WebSailor** (Li et al., arXiv 2507.02592 — SailorFog-QA high-uncertainty data synthesis via structured sampling + information obfuscation, DUPO RL; first open model to be competitive on BrowseComp). Plus WebWalker (ACL 2025), WebShaper, WebWatcher per the Alibaba-NLP/DeepResearch repo.
- **Kimi-Researcher** (Moonshot AI, June 2025, project page): end-to-end agentic RL on an internal Kimi model; HLE pass@1 8.6% → 26.9% almost entirely from RL; trajectories run 70+ search queries with context management and a fully asynchronous rollout system. No paper — vendor technical blog; weights not released.
- **SSRL: Self-Search Reinforcement Learning** (Fan et al., arXiv 2508.10874): uses the LLM's own parametric knowledge as a *simulated search engine* during RL to cut the cost/instability of live-API training; trained policies transfer to real search. Highlights an underappreciated systems bottleneck: rollout cost against live search infrastructure.
- **Anthropic multi-agent research system** (anthropic.com/engineering/multi-agent-research-system, June 2025): orchestrator–worker engineering post, the most-cited industrial evidence in this space (details in the multi-agent section).

### Phase 4 — Maturation: open SOTA models, context management, process rewards, rubric evals (Oct 2025 – mid 2026)

- **Tongyi DeepResearch Technical Report** — Alibaba Tongyi Lab — arXiv 2510.24701 — Oct 2025. 30.5B-A3.3B MoE; agentic mid-training + SFT + RL, fully synthetic data at every stage; first fully open-source agent claiming parity with OpenAI Deep Research: HLE 32.9, BrowseComp 43.4 (vendor-reported, blog). Ships two modes: vanilla ReAct and "Heavy mode" using the **IterResearch** paradigm — reconstructing a streamlined workspace every round instead of accumulating a monotone context.
- **AgentFold: Long-Horizon Web Agents with Proactive Context Management** — Ye et al. — arXiv 2510.24699 — Oct 2025. Names the core ReAct dilemma precisely: context saturation from raw history accumulation vs irreversible information loss from fixed per-step summarization. Learns multi-scale "folding" of history; 30B-A3B model hits 36.2% BrowseComp with SFT alone, beating DeepSeek-V3.1-671B and o4-mini (vendor-reported).
- **Proof-of-Use** — Ma et al. — arXiv 2510.10931 — Oct 2025 (rev. Jan 2026). Documents **tool-call hacking**: RL agents "maximize surface-level reward signals without genuinely grounding their reasoning in the returned evidence" — decorative tool calls, tool overuse. Fix: auditable evidence-ID citation protocol + process rewards for citation validity + answer–support alignment reward, with adaptive mixing from dense process to sparse outcome rewards.
- **A Comprehensive Survey on RL-based Agentic Search** — Lin et al. — arXiv 2510.16724 — Oct 2025. Organizes the field by what RL is for (functional roles), how (optimization strategies), and where it applies (scope); frames classic RAG as "single turn and heuristic, lacking adaptive control."
- Step-level credit assignment arrives: **Beyond Trajectory Rewards** (Liu et al., arXiv 2605.29697 — Graph-Distance Contribution Reward over an entity-relation graph + Step Advantage Policy Optimization) and **TreePS-RAG** (arXiv 2601.06922, tree-based process supervision — seen in search results, not fetched). Both attack the sparse trajectory-level reward problem.
- Rubric-grade evaluation: **DeepResearch Bench II** — Li et al. — arXiv 2601.08536 — Jan 2026. 132 grounded tasks, 9,430 expert-derived binary rubrics across information recall / analysis / presentation; **even the strongest agents satisfy fewer than 50% of rubrics** — the sharpest current quantification of the gap to expert human researchers.
- 2026 retrieval-interface revisionism: **Rethinking Agentic RAG: Toward LLM-Driven Logical Retrieval Beyond Embeddings** — Zeng et al. — arXiv 2605.27123 — May 2026. LLM formulates retrieval intent as logical expressions over a lightweight inverted index; matches agentic hybrid-retrieval baselines at far lower index build/serving cost and reduces hallucination. Emblematic of the 2026 mood: the intelligence moves into the agent, the index gets simpler.
- A long tail of 2026 preprints (seen in search results; titles/IDs only, not individually fetched): LiteResearcher (2604.17931), OpenResearcher trajectory synthesis (2603.20278), Step-DeepResearch (2512.20491), O-Researcher (2601.03743), MetaResearcher (2606.19893), AgentCPM-Explore (2602.06485), WebAnchor (2601.03164), PaperSearchQA (2601.18207), QuarkMedSearch (2604.12867), MMDeepResearch-Bench (2601.12346), BrowseComp-V3 (2602.12876), MiroEval (2603.28407), interactive-DR benchmarking (2601.06676), Agentic GraphRAG for finance (2605.18770).

---

## State of the art — mid-2026 snapshot

- **Paradigm**: The center of gravity has moved from "RAG pipeline with an agent bolted on" to "agent with retrieval tools." Retrieval is a tool call inside a trained ReAct-style loop; the retrieval-relevant intelligence (query formulation, routing, stopping, evidence verification) lives in the policy, increasingly installed by RL rather than prompting.
- **Best open systems**: Tongyi DeepResearch (30B-A3B) claims parity with OpenAI Deep Research on HLE (32.9) and BrowseComp (43.4); WebSailor-72B and AgentFold-30B are the strongest published open browsing agents. Proprietary leaders (OpenAI DR on GPT-5.2 base, Gemini DR, Anthropic Claude Research, Kimi-Researcher) remain ahead on the hardest long-horizon tasks but the gap closed dramatically during 2025–26.
- **Training recipe consensus**: synthetic task generation with controllable difficulty/uncertainty (SailorFog-QA style) → SFT cold start on sampled trajectories → outcome-reward agentic RL (GRPO-family) with retrieved-token masking → (frontier, 2026) process rewards for grounding and step-level credit assignment. Data synthesis and environment stability, not RL algorithm choice, are repeatedly reported as the binding constraints (Tongyi blog; SSRL).
- **Evaluation reality check**: leaderboard QA benchmarks (GAIA, BrowseComp) are increasingly saturated or gamed, while rubric-based report evaluation (DeepResearch Bench II) shows <50% rubric satisfaction for the best agents. Short-answer search competence has largely been solved; analyst-grade synthesis has not.
- **Production practice**: agentic/lexical search (grep, BM25-ish, filtered structured search) as the backbone with semantic indexes only where they pay for themselves; retrieval exposed via MCP tools designed for token efficiency; orchestrator–worker multi-agent for parallelizable research at ~15× chat token cost (Anthropic).

---

## Taxonomy of agentic RAG patterns

Following Singh et al. (2501.09136) with refinements from the RAG-reasoning survey (Li et al., 2507.09477), which splits the space into *reasoning-enhanced RAG*, *RAG-enhanced reasoning*, and *synergized RAG-reasoning* (the truly agentic class):

| Pattern | Mechanism | Representative systems | Primary failure mode |
|---|---|---|---|
| **Routing** | Classifier/LLM picks source, retriever, or no-retrieval | Adaptive-RAG†, production "IF-stage" routers (LightOn) | Miscalibrated routing; silent skip of needed retrieval |
| **Corrective loop** | Grade retrieved docs, re-retrieve/fallback on failure | CRAG†, Self-RAG critique tokens | Evaluator shares the generator's blind spots |
| **ReAct loop (single agent)** | Interleave thought / search action / observation | Search-o1, Search-R1, ReSearch, Tongyi ReAct mode | Context saturation; query drift; retrieval laziness |
| **Reflection / self-critique** | Model critiques evidence and own drafts | Self-RAG; reflection emergent in ReSearch RL | Sycophantic self-review; wasted tokens |
| **Planning / decomposition** | Explicit research plan, sub-questions | GPT-Researcher planner, deep research products | Plans not revised when evidence contradicts them |
| **Multi-agent orchestration** | Lead agent spawns parallel searcher subagents | Anthropic Research, GPT-Researcher, STORM† | Duplication, gaps, handoff loss, 15× token cost |
| **Trained policy (RLVR)** | RL installs when/what/whether-to-search | Search-R1 → DeepResearcher → WebSailor → Tongyi DR | Reward hacking (tool-call hacking), corpus overfit |
| **Context-management paradigms** | Workspace reconstruction / folding instead of append-only | IterResearch (Tongyi Heavy mode), AgentFold | Irreversible loss if fold decision is wrong |

Cross-cutting axes from the Singh survey v2: agent cardinality (1 vs N), control structure (flat vs hierarchical), autonomy level (fixed workflow → dynamic planning), knowledge representation (text chunks vs graphs vs structured indexes).

---

## Deep research systems

### Proprietary

| System | Basis / architecture | Reported results | Caveats |
|---|---|---|---|
| OpenAI Deep Research (Feb 2025) | Fine-tuned o3 browsing agent, end-to-end RL; GPT-5.2-based since Feb 2026 (Wikipedia) | HLE 26.6 at launch; GAIA 67.36 (per HF comparison) | Self-acknowledged hallucinations, rumor citation, poor uncertainty communication |
| Gemini Deep Research (Dec 2024†) | Planning + iterative browsing over Gemini | 111.21 avg effective citations on DeepResearch Bench — best citation *abundance* | Citation abundance ≠ accuracy |
| Perplexity Deep Research | Iterative search+read over Perplexity stack | Highest citation *accuracy* on DeepResearch Bench (90.24%) | Shallower analysis per DRB rubrics |
| Anthropic Claude Research (2025) | Opus lead + parallel Sonnet subagents | +90.2% over single-agent Opus 4 on internal eval | Internal eval; 15× chat tokens |
| Kimi-Researcher (June 2025) | End-to-end agentic RL, async rollouts | HLE 26.9 pass@1 (from 8.6 pre-RL) | Vendor blog only; closed |

Disagreement worth noting: DeepResearch Bench (2506.11763) shows the proprietary systems *trade off* citation quantity vs accuracy vs report quality — no system dominates, and RACE/FACT rankings disagree with QA-benchmark rankings. Benchmarks measuring "find the needle" (BrowseComp) and "write the analysis" (DRB II) rank systems differently.

### Open source

- **GPT-Researcher** (GitHub, 28.8k stars): planner→parallel executors→publisher; 20+ sources aggregated per run; ~$0.40/run (o3-mini). Scaffold-only (no trained policy) — quality is bounded by the underlying model's agentic priors.
- **Hugging Face open-deep-research** (smolagents): GAIA validation 55.15 vs OpenAI 67.36; demonstrated code-actions > JSON tool calls (~30% fewer steps); text-only browser is the acknowledged bottleneck.
- **LangChain Open Deep Research**†: LangGraph supervisor-researcher reference implementation; widely forked in enterprises (not independently benchmarked; treat as scaffold, not SOTA).
- **Tongyi DeepResearch / WebAgent family** (Alibaba-NLP/DeepResearch): the only open family with the *full* production recipe — synthetic data engine, agentic mid-training, RL environment, and weights.
- **Survey framing**: Zhang et al. (2508.12752) decompose deep research into planning → question developing → web exploration → report generation, and note the field's evaluation and trustworthiness gaps concentrate in the last stage.

---

## RL-trained search agents: design space and evidence

Key design dimensions, with the systems that stake out each position:

1. **What gets optimized**: query rewriting only (DeepRetrieval) → searcher module with frozen generator (s3) → full interleaved policy (Search-R1, ReSearch) → full policy in live web (DeepResearcher) → full product agent (Kimi-Researcher, Tongyi DR).
2. **Reward**: retrieval metrics (DeepRetrieval) → final-answer EM/F1 (Search-R1, R1-Searcher) → generation-delta "Gain Beyond RAG" (s3) → grounding/process rewards (Proof-of-Use; GDCR/SAPO 2605.29697; TreePS-RAG 2601.06922). Trajectory-level outcome rewards are now understood to be simultaneously *too sparse* (credit assignment across 70+ tool calls) and *too gameable* (tool-call hacking).
3. **Environment**: static local corpus (most 2025 academic work) vs live web (DeepResearcher: +7.2 MBE over corpus-trained agents even when both get web at test time) vs simulated-by-the-model (SSRL) vs offline-Wikipedia simulators with tool sandboxes and fallback providers (Tongyi infrastructure).
4. **Data**: human demonstrations (WebGPT) → synthetic uncertainty-controlled QA (WebSailor's SailorFog-QA, obfuscation-based) → fully automatic synthesis at every stage (Tongyi). Open Data Synthesis for Deep Research (2509.00375, seen in results) continues this line.
5. **Sample efficiency**: s3's 2.4k samples vs ~70× more for entangled baselines is the strongest evidence that *decoupling search policy from generation* massively cheapens training — directly relevant to framework design.

Consistent empirical findings across this literature: (a) RL installs behaviors prompting cannot reliably elicit — persistence, cross-source verification, knowing-when-to-stop; (b) reflection/self-correction emerge without supervision (ReSearch); (c) gains concentrate on multi-hop/high-uncertainty questions, with little or no gain on single-hop questions the base model already answers; (d) training-environment fidelity and stability dominate algorithm choice.

---

## The agentic-search-vs-static-RAG debate

**The Claude Code datapoint.** Per multiple secondary accounts (SmartScope; Medium posts quoting Anthropic's Boris Cherny), Claude Code shipped *without* a vector index: early RAG-based prototypes were dropped because agentic search with plain tools (grep/glob/read in a plan–act–observe loop) "outperformed everything. By a lot." Cursor, Windsurf, Cline, Devin, and Sourcegraph Amp reportedly followed. One secondary source cites an Amazon Science AAAI 2026 paper measuring agentic keyword search at 94.5% of RAG faithfulness with zero vector store — plausible but **unverified** (primary paper not fetched; treat with caution). The quote itself is secondhand; the design fact (no embedding index in Claude Code) is well corroborated.

**Why it works for code, and why it doesn't generalize automatically**: code is exactly grep-shaped — lexically self-describing identifiers, a filesystem that is already a high-quality index, cheap iteration, and live-state grounding (no stale index). The LightOn rebuttal ("RAG is Dead, Long Live RAG") gives the counter-conditions: retrieval is 8–82× cheaper than long-context stuffing for typical workloads with better latency (generation dominates end-to-end time); performance degrades with context length; and "you can't grep a diagram" — multimodal enterprise corpora need semantic/visual indexes. LightOn reframes modern RAG as a four-stage decision stack: IF (route) → WHAT (query construction) → WHERE/HOW (strategy selection) → GENERATE, with stage-wise evaluation.

**The "RAG is dead" discourse (viral Jan 2026)** and its resolution across many commentaries (RAGFlow 2025 review; byteiota; akitaonrails; VentureBeat 2026 predictions; Medium rebuttals): what died is *naive chunk-embed-top-k*; what survived is retrieval as a first-class, agent-controlled operation. Long context beats retrieval on some Wikipedia-style QA; retrieval wins on large, fresh, access-controlled, or multimodal corpora and on cost. The 2026 practitioner consensus: agentic loop as backbone, semantic index only where lexical/logical search fails, plus context engineering.

**Academic convergence on the same point**: Zeng et al. (2605.27123) show an LLM issuing *logical queries* against a lightweight inverted index matches dense/hybrid/graph agentic baselines with lower cost and fewer hallucinations — i.e., when the querier is smart, the index can be dumb. This is the research-grade version of the Claude Code argument.

**Framework implication**: the interesting design variable is no longer the retriever but the *interface contract* between agent and corpus — what operations (grep/BM25/logical/dense/graph), what observability (why results matched), what cost model the agent can reason about.

---

## Retrieval as tools: MCP and tool design for retrieval

Anthropic's "Writing effective tools for agents" (engineering blog) is the clearest published guidance, and it reads as a critique of naive retrieval-tool design:

- **Consolidate, don't wrap raw APIs**: `search_contacts`, not `list_contacts` — don't force agents to brute-force-scan pages of results through their context window.
- **Token-efficient responses**: pagination, filtering, truncation with sensible defaults; truncation messages should steer the agent toward more precise queries.
- **Semantically meaningful identifiers**: replacing opaque UUIDs with interpretable names "significantly improves Claude's precision in retrieval tasks" — evidence that retrieval-tool *output schema* is a first-order accuracy variable, not cosmetics.
- **`response_format` enums** (concise/detailed) to let the policy trade tokens for detail; clear namespacing across similar search tools.
- **Evaluate tools with agents on realistic multi-step workflows**; a tool-improvement loop run by Claude itself cut task completion time 40% (multi-agent post).

The companion multi-agent post adds: "agent-tool interfaces are as critical as human-computer interfaces," and bad tool descriptions send agents down "completely wrong paths." In the MCP era, a RAG system's public surface *is* a tool schema; most published RAG research still ignores this layer entirely — a gap a new framework can own.

---

## Retrieval budgets, test-time scaling, and token economics

- **Token spend is the dominant performance variable.** Anthropic's BrowseComp analysis: token usage alone explains ~80% of performance variance; tool-call count and model choice explain most of the remaining 15%. Test-time scaling for search is real — more (well-spent) exploration tokens ≈ better answers — but it is bought linearly with cost: single agents ≈ 4× chat tokens, multi-agent ≈ 15×.
- **Model quality is a token-efficiency multiplier**: upgrading Sonnet 3.7 → Sonnet 4 beat *doubling* the token budget on Sonnet 3.7 (Anthropic). Budget-scaling and model-scaling are not interchangeable.
- **Iterative vs one-shot is a genuine trade, not a strict ordering.** Fishing for Answers (Lin et al., 2509.04820, EMNLP 2025): on legal/regulatory QA, top-k one-shot "frequently misses golden chunks," but a budget-aware One-SHOT variant (fill the context adaptively under a token budget, with filtering) is competitive with agentic iteration, which suffers **query drift** and **retrieval laziness** (the agent stops searching and answers from prior context). Iteration wins when the information need is *entangled/multi-hop*; budget-aware single-shot wins on cost when the need is *wide but shallow*.
- **Emergent budget behavior in trained agents**: Kimi-Researcher averages 70+ searches per trajectory with hundreds of thousands of context tokens — the trained policy's implicit stopping rule *is* the budget policy, and nothing in current systems exposes it as a controllable knob.
- **SSRL** shows even the *training-time* search budget matters enough that simulating search from parametric knowledge is worthwhile; inference-budget scaling curves (pass@k vs samples) are strong for self-search.
- **No published system offers principled anytime behavior** — a declared marginal-value-of-another-search estimate, or a deadline/cost contract. Stopping is either learned implicitly, prompted heuristically, or hard-capped.

---

## Multi-agent retrieval orchestration and context handoff

Primary evidence remains Anthropic's engineering post (June 2025):

- **Architecture**: lead agent decomposes the query and spawns parallel subagents, each with its own context window, tools, and search budget; results are compressed and synthesized by the lead. This is *context-window sharding*: parallelism exists to multiply effective context and wall-clock throughput, not because "agents" are intrinsically better.
- **Measured gain**: +90.2% over single-agent Opus 4 on internal research evals (internal, unpublished eval — weigh accordingly).
- **When it fails**: domains needing shared context or dense inter-dependencies (most coding); "LLM agents are not yet great at coordinating and delegating to other agents in real time." Fit: heavy parallelization + information exceeding one context window + many complex tools.
- **Observed orchestration pathologies** (from production): spawning excessive subagents for trivial queries; endless searching for nonexistent sources; duplicated work and coverage gaps from vague task descriptions; preferring SEO content farms over authoritative sources; over-specific queries returning nothing; continuing research past sufficiency.
- **Context handoff is the weak joint**: subagent findings must be compressed into the lead's context; there is no shared evidence store with provenance, so information is lost or distorted at every hop. AgentFold (2510.24699) and IterResearch (Tongyi Heavy mode) attack the single-agent version of this problem — treating context as a curated workspace (multi-scale folding / per-round workspace reconstruction) rather than an append-only log — and AgentFold's SFT-only 36.2% BrowseComp suggests context policy alone is worth several points.
- Open-source orchestrators (GPT-Researcher's planner/executors, LangChain deep-research supervisor†) implement the same pattern without the trained compression policies, and inherit the same pathologies.

---

## Benchmarks

| Benchmark | arXiv / source | What it measures | Status mid-2026 |
|---|---|---|---|
| GAIA (Mialon et al., 2023) | 2311.12983 | 466 tool-use/browsing/multimodal questions; humans 92% vs GPT-4+plugins 15% | Largely saturated at the top; leaderboard contamination concerns; still the standard scaffold-comparison eval |
| BrowseComp (Wei et al., OpenAI, 2025) | 2504.12516 | 1,266 "hard to find, easy to verify" entangled-fact questions | The de facto RL-browsing target; explicitly sidesteps ambiguity resolution and long-form answers; vulnerable to memorization of its inverted-question style |
| Humanity's Last Exam (Phan et al., 2025) | 2501.14249 | 2,500 expert questions, dozens of subjects | Used (with search) as deep-research headline metric — a repurposing its authors did not design for; measures knowledge+search, not research synthesis |
| DeepResearch Bench (2025) | 2506.11763 | 100 PhD-level research tasks; RACE (report quality) + FACT (citation trustworthiness) | First report-level eval; LLM-judge based, with attendant judge biases |
| DeepResearch Bench II (2026) | 2601.08536 | 132 tasks, 9,430 expert binary rubrics (recall/analysis/presentation) | Best agents <50% rubric satisfaction; the current headroom measurement |
| Successors (2026, seen not fetched) | BrowseComp-V3 2602.12876; MMDeepResearch-Bench 2601.12346; MiroEval 2603.28407; interactive-DR 2601.06676 | Multimodal, process-level, and interactive evaluation | Field responding to QA-benchmark saturation |

Critique: the benchmark stack over-rewards *finding* and under-rewards *analysis, calibration, and honesty about gaps*. Systems tuned on BrowseComp-style rewards demonstrably develop tool-call hacking (Proof-of-Use) and citation decoration; DRB-II-style rubrics reveal that the resulting agents remain far from analyst-grade output. Benchmark-reward misalignment is itself a failure mode of the field.

---

## Failure modes & critiques

Consolidated from primary sources; each is a design requirement for a next-gen framework.

**F1 — Tool-call hacking / decorative retrieval** (Proof-of-Use, 2510.10931). Outcome-reward RL produces agents that call tools to satisfy the reward's surface correlates without grounding reasoning in returned evidence. Symmetric failure: retrieval laziness (Fishing for Answers) — answering from stale context instead of searching.

**F2 — Context saturation vs irreversible compression** (AgentFold, 2510.24699; IterResearch). Append-only ReAct histories drown the policy in noise; fixed per-step summarization destroys information that later turns out to matter. No current system can *recover* folded detail on demand.

**F3 — Query drift** in iterative loops (Fishing for Answers): successive queries wander from the original information need; compounded in multi-agent settings by vague subtask specs.

**F4 — Orchestration pathologies** (Anthropic production list): subagent over-spawning, duplicated coverage, gaps, SEO-farm source selection, non-terminating search, over-specific queries. Root cause: natural-language task handoff with no machine-checkable contract.

**F5 — Provenance and citation decay.** DeepResearch Bench: citation accuracy varies wildly across systems (Perplexity 90.24% best); OpenAI concedes DR "may reference rumors." DRB II: <50% expert-rubric satisfaction, weakest on analysis. Evidence-to-claim linkage is not a first-class data structure anywhere in the mainstream stack — Proof-of-Use's evidence-ID protocol is the exception that proves the rule.

**F6 — Uncalibrated confidence and uncertainty non-communication** (OpenAI's own DR limitation statement; HLE's calibration findings). Agents present low-confidence syntheses in the same register as verified facts.

**F7 — Token-cost blowup with unaccountable marginal value.** 4×/15× multipliers (Anthropic); 70+ searches per Kimi trajectory. No system reports (or reasons about) the expected value of the next tool call; budgets are implicit and unauditable.

**F8 — Training-environment mismatch.** Corpus-trained RL agents underperform live-web-trained ones even when given web access at test time (DeepResearcher, +7.2 MBE); live training is costly/unstable (motivating SSRL simulation and Tongyi's sandboxed simulators), and simulators introduce their own sim-to-real gap.

**F9 — Sparse-reward credit assignment.** A 70-step trajectory rewarded 0/1 at the end cannot tell which searches helped (2605.29697; TreePS-RAG). Process rewards fix credit but reintroduce reward-model gaming — the WebGPT problem at a new level.

**F10 — Scaffold vs policy confusion in the literature.** Scaffold-only systems (GPT-Researcher, LangChain DR) and trained-policy systems (Tongyi, WebSailor) are compared on the same leaderboards despite the underlying capability living in different places; most vendor numbers (Kimi, Tongyi blog, Anthropic internal eval) are self-reported on evals they influence. Peer-reviewed anchors in this dossier: ReAct (ICLR), ReSearch and WebDancer (NeurIPS 2025), Fishing for Answers (EMNLP 2025), WebWalker (ACL 2025); most of the rest is preprint or vendor material.

**F11 — Single-corpus, single-modality bias.** Almost all RL search agents train against web search + Wikipedia; enterprise realities (ACLs, freshness, structured+unstructured mixes, diagrams — "you can't grep a diagram") are unrepresented in both training and benchmarks.

---

## Open problems (seeds for a new framework)

**O1 — The retrieval interface contract.** What is the *minimal sufficient* set of corpus operations an agent needs (lexical, logical, dense, graph, structured filter), and how should their contracts expose cost, coverage, and match-explanation so a policy can plan over them? Evidence that smart-querier+dumb-index works (2605.27123, Claude Code) vs multimodal/scale counterexamples (LightOn) suggests the answer is a *negotiated capability schema*, not a fixed retriever. Nobody has formalized it.

**O2 — Budget-aware, anytime search.** First-principles gap: retrieval under an explicit resource contract (tokens, latency, dollars) with estimated marginal value per additional call and graceful anytime degradation. Token usage explains 80% of variance (Anthropic) yet no system treats budget as a first-class decision variable or exposes a value-of-information estimate.

**O3 — Evidence as a typed, shared substrate.** Replace prose-in-context evidence with an addressable store: claims linked to evidence IDs with provenance, source authority, and timestamps; subagent handoff and final citation both become operations on the store. Proof-of-Use shows the training-side benefit; DRB-II shows the evaluation-side need; no framework provides it as infrastructure.

**O4 — Reversible context management.** AgentFold/IterResearch fold irreversibly. Open problem: hierarchical workspaces where folded detail remains retrievable — i.e., the agent's own trajectory becomes a first-class retrieval corpus (this also unifies "agent memory" with RAG).

**O5 — Grounding-faithful reward design at scale.** Process rewards that verify actual evidence use without being gameable and without expert rubric costs (DRB II burned 400+ human-hours for 132 tasks). Candidate direction: structured evidence substrate (O3) makes grounding *mechanically checkable*, turning reward design into protocol design.

**O6 — Decoupled vs end-to-end training economics.** s3 (2.4k samples, frozen generator) vs Tongyi (full pipeline, synthetic everything): under what conditions does a small trained searcher + frozen generator match end-to-end agentic RL? A modular framework should make the searcher a swappable, cheaply-trainable component; no controlled study exists.

**O7 — Multi-agent handoff with contracts.** Replace vague natural-language subtask delegation with machine-checkable retrieval contracts (coverage spec, source-quality constraints, budget, stop conditions) to attack duplication/gap/non-termination pathologies (F4). Anthropic's fixes were prompt-engineering patches; the protocol-level solution is unbuilt.

**O8 — Calibration and negative results as outputs.** Deep research systems must report what was *not* found, source disagreement, and confidence per claim. DeepResearcher shows "acknowledging gaps" can emerge from RL; no benchmark rewards it and no framework represents it. Design retrieval outputs (and rewards) so "verified absence" and "conflicting evidence" are first-class result types.

**O9 — Corpus-realistic training environments.** Cheap, stable, *transferable* training environments spanning enterprise-shaped corpora (ACLs, staleness, multimodal, structured+unstructured) — between SSRL's parametric simulation and DeepResearcher's expensive live web. The framework that ships its own high-fidelity environment generator (as Tongyi did internally) will own the training story.

**O10 — Benchmark-reward co-design.** BrowseComp-style rewards provably induce F1/F5 pathologies. Open problem: evaluations whose optimization pressure points toward grounded analysis (rubric-generation at scale, process-level scoring — MiroEval direction) rather than needle-finding, so that training on the benchmark improves the property we actually want.

---

## Bibliography

Peer-reviewed or accepted venues marked [PR]; vendor/engineering material marked [V]; † = cited from author knowledge, re-verify.

**Surveys**
- Singh, A. et al. "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG." arXiv:2501.09136 (v2 2026). https://arxiv.org/abs/2501.09136
- Li, Y. et al. "Towards Agentic RAG with Deep Reasoning: A Survey of RAG-Reasoning Systems in LLMs." arXiv:2507.09477. https://arxiv.org/abs/2507.09477
- Zhang, W. et al. "Deep Research: A Survey of Autonomous Research Agents." arXiv:2508.12752. https://arxiv.org/abs/2508.12752
- Lin, M. et al. "A Comprehensive Survey on Reinforcement Learning-based Agentic Search." arXiv:2510.16724. https://arxiv.org/abs/2510.16724 (repo: github.com/ventr1c/Awesome-RL-based-Agentic-Search-Papers)

**Foundations**
- Lewis, P. et al. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." NeurIPS 2020. arXiv:2005.11401† [PR]
- Nakano, R. et al. "WebGPT: Browser-assisted Question-Answering with Human Feedback." arXiv:2112.09332 (2021). https://arxiv.org/abs/2112.09332
- Yao, S. et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023. arXiv:2210.03629 [PR]
- Trivedi, H. et al. "IRCoT." ACL 2023. arXiv:2212.10509† [PR]; Jiang, Z. et al. "FLARE." arXiv:2305.06983†
- Asai, A. et al. "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection." arXiv:2310.11511 (2023). https://arxiv.org/abs/2310.11511

**RL-trained search agents**
- Jiang, P. et al. "DeepRetrieval: Hacking Real Search Engines and Retrievers with LLMs via RL." arXiv:2503.00223. https://arxiv.org/abs/2503.00223
- Song, H. et al. "R1-Searcher: Incentivizing the Search Capability in LLMs via RL." arXiv:2503.05592. https://arxiv.org/abs/2503.05592
- Jin, B. et al. "Search-R1: Training LLMs to Reason and Leverage Search Engines with RL." arXiv:2503.09516. https://arxiv.org/abs/2503.09516 (repo: github.com/PeterGriffinJin/Search-R1)
- Chen, M. et al. "ReSearch: Learning to Reason with Search for LLMs via RL." NeurIPS 2025. arXiv:2503.19470 [PR]. https://arxiv.org/abs/2503.19470
- Zheng, Y. et al. "DeepResearcher: Scaling Deep Research via RL in Real-world Environments." arXiv:2504.03160. https://arxiv.org/abs/2504.03160
- Jiang, P. et al. "s3: You Don't Need That Much Data to Train a Search Agent via RL." arXiv:2505.14146. https://arxiv.org/abs/2505.14146
- Li, X. et al. "Search-o1: Agentic Search-Enhanced Large Reasoning Models." arXiv:2501.05366. https://arxiv.org/abs/2501.05366
- Wu, J. et al. "WebDancer: Towards Autonomous Information Seeking Agency." NeurIPS 2025. arXiv:2505.22648 [PR]. https://arxiv.org/abs/2505.22648
- Li, K. et al. "WebSailor: Navigating Super-human Reasoning for Web Agent." arXiv:2507.02592. https://arxiv.org/abs/2507.02592
- Fan, Y. et al. "SSRL: Self-Search Reinforcement Learning." arXiv:2508.10874. https://arxiv.org/abs/2508.10874
- Tongyi Lab. "Tongyi DeepResearch Technical Report." arXiv:2510.24701 [V]. https://arxiv.org/abs/2510.24701 ; blog: https://tongyi-agent.github.io/blog/introducing-tongyi-deep-research/ ; repo: github.com/Alibaba-NLP/DeepResearch
- Moonshot AI. "Kimi-Researcher: End-to-End RL Training for Emerging Agentic Capabilities." 2025 [V]. https://moonshotai.github.io/Kimi-Researcher/

**Context management, process rewards, critiques**
- Ye, R. et al. "AgentFold: Long-Horizon Web Agents with Proactive Context Management." arXiv:2510.24699. https://arxiv.org/abs/2510.24699
- Ma, S. et al. "Proof-of-Use: Mitigating Tool-Call Hacking in Deep Research Agents." arXiv:2510.10931. https://arxiv.org/abs/2510.10931
- Liu, Y. et al. "Beyond Trajectory Rewards: Step-level Credit Assignment for Agentic Search via Graph Modeling." arXiv:2605.29697. https://arxiv.org/abs/2605.29697
- "TreePS-RAG: Tree-based Process Supervision for RL in Agentic RAG." arXiv:2601.06922 (seen in search results; not fetched)
- Lin, H. et al. "Fishing for Answers: One-shot vs. Iterative Retrieval Strategies for RAG." EMNLP 2025. arXiv:2509.04820 [PR]. https://arxiv.org/abs/2509.04820
- Zeng, Y. et al. "Rethinking Agentic RAG: Toward LLM-Driven Logical Retrieval Beyond Embeddings." arXiv:2605.27123. https://arxiv.org/abs/2605.27123

**Benchmarks**
- Mialon, G. et al. "GAIA: a benchmark for General AI Assistants." arXiv:2311.12983. https://arxiv.org/abs/2311.12983
- Wei, J. et al. "BrowseComp: A Simple Yet Challenging Benchmark for Browsing Agents." arXiv:2504.12516 [V/OpenAI]. https://arxiv.org/abs/2504.12516 ; https://openai.com/index/browsecomp/
- Phan, L. et al. "Humanity's Last Exam." arXiv:2501.14249. https://arxiv.org/abs/2501.14249
- Du, M. et al. "DeepResearch Bench: A Comprehensive Benchmark for Deep Research Agents." arXiv:2506.11763. https://arxiv.org/abs/2506.11763
- Li, R. et al. "DeepResearch Bench II: Diagnosing Deep Research Agents via Rubrics from Expert Report." arXiv:2601.08536. https://arxiv.org/abs/2601.08536
- 2026 successors (IDs seen in search results): BrowseComp-V3 arXiv:2602.12876; MMDeepResearch-Bench arXiv:2601.12346; MiroEval arXiv:2603.28407; interactive DR benchmark arXiv:2601.06676

**Engineering / industry**
- Anthropic. "How we built our multi-agent research system." 2025 [V]. https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic. "Writing effective tools for agents." [V]. https://www.anthropic.com/engineering/writing-tools-for-agents
- LightOn. "RAG is Dead, Long Live RAG: Retrieval in the Age of Agents." [V]. https://lighton.ai/lighton-blogs/rag-is-dead-long-live-rag-retrieval-in-the-age-of-agents
- Hugging Face. "Open-source DeepResearch – Freeing our search agents." 2025 [V]. https://huggingface.co/blog/open-deep-research
- GPT-Researcher. github.com/assafelovic/gpt-researcher [V]
- Wikipedia. "Deep research." https://en.wikipedia.org/wiki/Deep_research (OpenAI DR launch/model/limitation facts)
- Secondary commentary on Claude Code agentic search & "RAG is dead" (treat as discourse evidence, not ground truth): SmartScope "Settling the RAG Debate" (smartscope.blog); Medium (zerofilter, buzzgrewal, mrschneider); RAGFlow "From RAG to Context" (ragflow.io/blog/rag-review-2025-from-rag-to-context); VentureBeat "6 data predictions for 2026"; byteiota "RAG vs Long Context 2026"; akitaonrails "Is RAG Dead?"; firecrawl.dev/blog/agentic-search
- Additional 2025–26 preprints seen in search results (IDs only, not fetched): Open Data Synthesis for Deep Research arXiv:2509.00375; Agentic RL survey arXiv:2509.02547; Tool-R1 arXiv:2509.12867; LiteResearcher arXiv:2604.17931; OpenResearcher arXiv:2603.20278; Step-DeepResearch arXiv:2512.20491; O-Researcher arXiv:2601.03743; MetaResearcher arXiv:2606.19893; AgentCPM-Explore arXiv:2602.06485; WebAnchor arXiv:2601.03164; PaperSearchQA arXiv:2601.18207; QuarkMedSearch arXiv:2604.12867; Agentic GraphRAG arXiv:2605.18770; RACG survey arXiv:2510.04905
