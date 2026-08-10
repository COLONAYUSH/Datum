# RAG Foundations, Lineage & Major Surveys (through mid-2026)

Research dossier for the "Reimagining RAG" project. Dimension: **foundations-and-surveys**.
Compiled 2026-08-05 from primary sources (arXiv abstract pages, ACM DL, ACL Anthology entries, engineering blogs) — every citation below was directly observed in a search result or fetched page. Uncertain attributions are explicitly flagged.

---

## Scope

This document covers:

1. The **lineage** of retrieval-augmented generation: open-domain QA roots (DrQA, ORQA, REALM, DPR), the 2020 RAG/FiD papers, retrieval-in-the-architecture models (kNN-LM, RETRO, Atlas), the prompt-era "pipeline RAG" explosion (2023–24), and the agentic turn (2024–26).
2. The **survey literature** 2023–2026 and the taxonomies it introduced (Naive/Advanced/Modular; Modular-RAG operators; query-difficulty levels; agentic-RAG design patterns; context engineering).
3. The **position papers and debates**: "is RAG dead?", long-context vs. RAG, RAG vs. fine-tuning, cache-augmented generation (CAG), retrieval in the agent era.
4. The **canonical failure-point taxonomies** (Barnett et al.'s seven failure points, RGB's four capabilities, "sufficient context" analysis) and systemic critiques.
5. **Open problems** distilled for the design of a next-generation framework.

Out of scope (covered by sibling dossiers): retriever/embedding internals, GraphRAG specifics, agent-memory systems in depth, evaluation methodology in depth, production/systems engineering.

---

## Lineage & chronological development

### Phase 0 — Retriever-reader open-domain QA (2017–2019)

The modern RAG stack descends directly from open-domain QA, not from generation research.

- **DrQA** — "Reading Wikipedia to Answer Open-Domain Questions" — Danqi Chen et al. — ACL 2017 — [arXiv:1704.00051](https://arxiv.org/abs/1704.00051). Established the two-stage **retriever–reader** template: sparse retrieval (bigram hashing + TF-IDF) over Wikipedia, then a neural reader extracting an answer span. Essentially every RAG pipeline since is a descendant of this decomposition; the reader was later swapped for a generator. Limitation: retrieval and reading are trained separately; retrieval errors are unrecoverable — the ancestral form of what Barnett et al. later catalog as FP1/FP2.
- **ORQA** — "Latent Retrieval for Weakly Supervised Open Domain Question Answering" — Kenton Lee et al. — ACL 2019 — [arXiv:1906.00300](https://arxiv.org/abs/1906.00300). First to treat **evidence retrieval as a latent variable** learned end-to-end from QA pairs alone (no gold evidence, no IR system), showing learned dense retrieval can beat BM25 when users genuinely seek unknown answers. Introduced the Inverse Cloze Task for retriever pretraining.
- **kNN-LM** — "Generalization through Memorization: Nearest Neighbor Language Models" — Urvashi Khandelwal et al. — ICLR 2020 — [arXiv:1911.00172](https://arxiv.org/abs/1911.00172). Orthogonal lineage: interpolate an LM's next-token distribution with a k-NN lookup over a datastore of context embeddings. SOTA perplexity on Wikitext-103 with **no additional training**, and cheap domain adaptation by swapping datastores. It is the purest form of "external non-parametric memory," and its token-level granularity remains a road not taken by mainstream chunk-level RAG.

### Phase 1 — End-to-end retrieval-augmented pretraining and generation (2020–2022)

- **REALM** — "REALM: Retrieval-Augmented Language Model Pre-Training" — Kelvin Guu et al. — ICML 2020 — [arXiv:2002.08909](https://arxiv.org/abs/2002.08909). Augments masked-LM **pretraining** with a latent knowledge retriever, backpropagating through retrieval (with asynchronous index refresh). Demonstrated interpretability and modularity benefits. Critique visible in later literature: the async index-refresh machinery is expensive and did not scale culturally — the field abandoned joint training for frozen-component pipelines.
- **DPR** — "Dense Passage Retrieval for Open-Domain Question Answering" — Vladimir Karpukhin et al. — EMNLP 2020 — [arXiv:2004.04906](https://arxiv.org/abs/2004.04906). The dual-encoder dense retriever that made vector search the default substrate; outperformed BM25 and set SOTA on multiple QA benchmarks. Its dual-encoder dot-product scoring is the architectural assumption baked into essentially every vector DB.
- **RAG** — "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" — Patrick Lewis et al. — NeurIPS 2020 — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401). Coined the term. A seq2seq (BART) generator marginalizing over passages from a dense Wikipedia index (RAG-Sequence / RAG-Token), with parametric + non-parametric memory trained jointly. SOTA open-domain QA; more factual and specific generation than parametric-only baselines. Crucial historical note: **the original RAG was a jointly trained probabilistic model, not a prompt-stuffing pipeline** — the industry practice that later inherited the name shares almost none of its machinery.
- **FiD** — "Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering" — Gautier Izacard & Edouard Grave — 2020 — [arXiv:2007.01282](https://arxiv.org/abs/2007.01282). Fusion-in-Decoder: encode many passages independently, fuse in the decoder. Key finding: performance **improves monotonically with more retrieved passages** — generative readers aggregate evidence across sources far better than extractive ones. FiD quietly anticipated the long-context debate: scaling evidence helps, if the architecture fuses rather than concatenates.
- **RETRO** — "Improving language models by retrieving from trillions of tokens" — Sebastian Borgeaud et al. — DeepMind, ICML 2022 (PMLR v162) — [arXiv:2112.04426](https://arxiv.org/abs/2112.04426). Chunked cross-attention into a **trillion-token** datastore; comparable to GPT-3/Jurassic-1 on the Pile with **25× fewer parameters**. The strongest evidence that retrieval can substitute for parameters at pretraining scale. Follow-ups: "Shall We Pretrain Autoregressive Language Models with Retrieval? A Comprehensive Study" ([ACL Anthology, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.482/)) and **InstructRetro** ([arXiv:2310.07713](https://arxiv.org/abs/2310.07713)) extended this; but a critical replication, "On the Generalization Ability of Retrieval-Enhanced Transformers" ([arXiv:2302.12128](https://arxiv.org/abs/2302.12128)), questioned how much of RETRO's gain is genuine generalization vs. test-set overlap with the datastore. No frontier lab has publicly shipped a RETRO-style production model — architectural retrieval lost to in-context retrieval.
- **Atlas** — "Atlas: Few-shot Learning with Retrieval Augmented Language Models" — Gautier Izacard et al. (Meta) — 2022 — [arXiv:2208.03299](https://arxiv.org/abs/2208.03299). T5 + trained retriever, jointly tuned; strong few-shot performance on MMLU, KILT, NaturalQuestions with an updatable index. The high-water mark of *trained* retrieval-augmented models before the field pivoted to frozen LLM + frozen retriever pipelines.

### Phase 2 — The prompt-era "pipeline RAG" explosion (2023–2024)

With ChatGPT-class models, RAG was reinvented as an **inference-time pattern**: chunk → embed → vector-search → stuff prompt. No gradients anywhere. This is when "RAG" became a software-engineering term rather than a modeling term.

- **Gao et al. survey** — "Retrieval-Augmented Generation for Large Language Models: A Survey" — Yunfan Gao et al. — Dec 2023 (rev. Mar 2024) — [arXiv:2312.10997](https://arxiv.org/abs/2312.10997). The field-defining survey; codified the **Naive → Advanced → Modular** paradigm progression and the retrieval/generation/augmentation tripartite framing. The single most-cited RAG reference of the era.
- **Self-RAG** — "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection" — Akari Asai et al. — 2023 — [arXiv:2310.11511](https://arxiv.org/abs/2310.11511). Adaptive retrieval + self-critique via reflection tokens; the bridge from static pipelines toward decision-making retrieval, later generalized by agentic RAG.
- **RGB benchmark** — "Benchmarking Large Language Models in Retrieval-Augmented Generation" — Jiawei Chen et al. — AAAI 2024 — [arXiv:2309.01431](https://arxiv.org/abs/2309.01431). Defined the four RAG-specific LLM capabilities: **noise robustness, negative rejection, information integration, counterfactual robustness** — and showed consistent LLM weaknesses on all four.
- **Lost in the Middle** — Nelson F. Liu et al. — TACL 2024 (Vol. 12, pp. 157–173; arXiv preprint Jul 2023) — [arXiv:2307.03172](https://arxiv.org/abs/2307.03172). Performance degrades when relevant information sits mid-context. Became the standard empirical argument both *for* RAG (against context stuffing) and *against* naive RAG (ordering of retrieved chunks matters).
- **Seven Failure Points** — Scott Barnett et al. — CAIN 2024 (IEEE/ACM Conf. on AI Engineering) — [arXiv:2401.05856](https://arxiv.org/abs/2401.05856). The canonical engineering failure taxonomy (detailed below).
- **Modular RAG** — "Modular RAG: Transforming RAG Systems into LEGO-like Reconfigurable Frameworks" — Yunfan Gao et al. — 2024 — [arXiv:2407.21059](https://arxiv.org/abs/2407.21059). Decomposes RAG into modules/operators with **linear, conditional, branching, and looping** control-flow patterns — effectively an admission that "RAG" had become an orchestration problem, one step short of calling it an agent.
- **Best-practices empiricism** — "Searching for Best Practices in Retrieval-Augmented Generation" — Xiaohua Wang et al. — 2024 — [arXiv:2407.01219](https://arxiv.org/abs/2407.01219). Grid-searched pipeline configurations for performance/efficiency trade-offs; symptomatic of the era's combinatorial tuning burden.

### Phase 3 — The agentic turn and the dissolution of "RAG" as a fixed pipeline (2024–2026)

- **Agentic RAG survey** — "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG" — Aditi Singh, Abul Ehtesham, Saket Kumar, Tala Talaei Khoei — Jan 2025, v4 Apr 2026 — [arXiv:2501.09136](https://arxiv.org/abs/2501.09136); companion repo [asinghcsu/AgenticRAG-Survey](https://github.com/asinghcsu/AgenticRAG-Survey). Frames traditional RAG as "constrained by static workflows"; taxonomy of agentic architectures (single-agent, multi-agent, hierarchical, corrective, adaptive) built on the design patterns of reflection, planning, tool use, multi-agent collaboration. Preprint; broad but shallow on evaluation — it catalogs architectures faster than the field can validate them.
- **Context engineering** — "A Survey of Context Engineering for Large Language Models" — Lingrui Mei et al. — 2025 — [arXiv:2507.13334](https://arxiv.org/abs/2507.13334) (166 pp., 1,411 citations analyzed). Explicitly **subsumes RAG** as one of three architectural implementations of a broader discipline (alongside memory systems + tool-integrated reasoning, and multi-agent systems). Identifies a comprehension/generation asymmetry: models understand complex contexts far better than they produce equally sophisticated long-form outputs.
- **A-RAG** — "A-RAG: Scaling Agentic Retrieval-Augmented Generation via Hierarchical Retrieval Interfaces" — Mingxuan Du et al. — 2026 — [arXiv:2602.03442](https://arxiv.org/abs/2602.03442). Representative of the 2026 wave: the model is given **retrieval tools** (keyword search, semantic search, chunk read) and decides its own information-gathering strategy; outperforms fixed workflows at comparable retrieved-token budgets, with scaling analysis across model size and compute.
- **RL-trained agentic retrieval** — e.g., TreePS-RAG (process supervision for agentic RAG RL, [arXiv:2601.06922](https://arxiv.org/pdf/2601.06922)), RAGShaper (automated data synthesis for agentic RAG skills, [arXiv:2601.08699](https://arxiv.org/pdf/2601.08699)), and "Process vs. Outcome Reward: Which is Better for Agentic RAG Reinforcement Learning" ([arXiv:2505.14069](https://arxiv.org/pdf/2505.14069)) — the search-as-RL-environment thread (2025–26).
- **Practitioner counter-current** — the "grep is all you need" position: Claude Code and similar coding agents ship **without vector databases**, using lexical search + filesystem tools + long context (see AkitaOnRails, ["Is RAG Dead? Long Context, Grep, and the End of the Mandatory Vector DB"](https://akitaonrails.com/en/2026/04/06/rag-is-dead-long-context/), Apr 2026, which dissects Claude Code's markdown-index + grep memory consolidation). The inversion: **dumb retriever, smart reader** — high-recall/low-precision retrieval plus a capable model beats precision-engineered embedding pipelines in many settings.

---

## State of the art — mid-2026 snapshot

1. **"RAG" no longer names one thing.** The term now spans (a) the original jointly-trained model (rarely meant), (b) the frozen chunk-embed-retrieve-stuff pipeline (the 2023 default, now considered "naive"), (c) modular/orchestrated pipelines, and (d) agentic retrieval where an LLM wields search tools in a loop. Surveys have responded by rebranding upward: *modular RAG* → *agentic RAG* → *context engineering* → *context engine* (RAGFlow's 2025 year-end framing: RAG "evolves into a Context Engine supporting all context assembly needs" — [ragflow.io](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)).
2. **The long-context war ended in a cost-based truce.** LaRA-style controlled comparisons (2,326 test cases, 11 LLMs — reported in the RAGFlow review; arXiv ID not independently verified) find no silver bullet: task-, model-, and context-dependent. Li et al.'s Self-Route ([arXiv:2407.16833](https://arxiv.org/abs/2407.16833)) found long-context wins on quality when affordable, RAG wins on cost; OP-RAG ([arXiv:2409.01666](https://arxiv.org/abs/2409.01666)) showed an inverted-U in retrieved-chunk count. Practitioner consensus (LightOn, RAGFlow): targeted retrieval is roughly **8–82× cheaper** than context-stuffing at typical workloads; conversely, prompt caching pushes some workloads back toward long context (AkitaOnRails: ~$0.10 per follow-up on a cached 200k context).
3. **Retrieval is being re-cast as a tool interface, not a pipeline stage.** 2026 systems (A-RAG; Claude Code) expose hierarchies of retrieval primitives (grep/BM25, semantic search, chunk/file read) and let the model compose them. Agent workloads change retrieval requirements: 1–2 orders of magnitude higher query rates than human search, machine-generated queries, tight latency coupling to reasoning loops (RAGFlow).
4. **Training is coming back.** After two years of frozen pipelines, RL over retrieval trajectories (process-reward vs outcome-reward debates) and "RAG-considerate pretraining" scaling laws ("To Memorize or to Retrieve" — [arXiv:2604.00715](https://arxiv.org/pdf/2604.00715), 2026) are reviving the REALM/Atlas idea of optimizing the model *for* retrieval.
5. **Failure-mode literature has matured** from anecdote (Barnett's seven FPs) to instrumentation ("Sufficient Context" — [arXiv:2411.06037](https://arxiv.org/abs/2411.06037)) to systems-level robustness/sensitivity/stability analysis ([arXiv:2606.28337](https://arxiv.org/pdf/2606.28337), 2026) and security taxonomies ([arXiv:2604.08304](https://arxiv.org/pdf/2604.08304), 2026).
6. **Multimodal RAG remains an engineering bottleneck**, not a solved research problem: per-page multi-vector representations (ColPali-style, ~1024 tokens/page, ~512KB/page) drive TB-scale index costs; mitigation via tensor quantization and token pruning; M3Retrieve shows multimodal retrieval wins on visual QA but loses on text-dominant tasks (RAGFlow review).

---

## The survey landscape, 2023–2026 (detailed)

### Tier 1 — field-defining, heavily cited

| Survey | ID / venue | Year | Core taxonomy | Known critiques / gaps |
|---|---|---|---|---|
| Gao et al., "RAG for LLMs: A Survey" | [arXiv:2312.10997](https://arxiv.org/abs/2312.10997) | 2023/24 | Naive / Advanced / Modular; retrieval–generation–augmentation | Pipeline-centric; predates agentic era; taxonomy describes engineering fashion more than principled design space |
| Fan et al., "A Survey on RAG Meeting LLMs" (RA-LLMs) | KDD 2024, [ACM DL](https://dl.acm.org/doi/10.1145/3637528.3671470) | 2024 | Architecture / training strategy / application | Peer-reviewed (rare among RAG surveys); training-strategy axis thin because almost nothing was trained in 2024 |
| Huang et al., "A Survey on Retrieval-Augmented Text Generation for LLMs" | [arXiv:2404.10981](https://arxiv.org/abs/2404.10981) | 2024 | Pre-retrieval / retrieval / post-retrieval / generation | Stage taxonomy; same linear-pipeline assumption |
| Gao et al., "Modular RAG" | [arXiv:2407.21059](https://arxiv.org/abs/2407.21059) | 2024 | Modules + operators; linear/conditional/branching/looping flows | Position-paper-like; the "LEGO" metaphor concedes there is no theory of composition, only patterns |
| Zhao et al., "RAG and Beyond" (Microsoft) | [arXiv:2409.14924](https://arxiv.org/abs/2409.14924) | 2024 | **Four query levels**: explicit facts / implicit facts / interpretable rationales / hidden rationales | The most useful *task-difficulty* taxonomy; argues against one-size-fits-all RAG; still question-centric |
| Singh et al., "Agentic RAG Survey" | [arXiv:2501.09136](https://arxiv.org/abs/2501.09136), v4 2026 | 2025–26 | Agentic design patterns (reflection, planning, tool use, multi-agent) × architecture types | Preprint; enumerates architectures without comparative evaluation; taxonomy churn risk |
| Mei et al., "Context Engineering Survey" | [arXiv:2507.13334](https://arxiv.org/abs/2507.13334) | 2025 | Context retrieval/generation, processing, management → RAG, memory, tool-reasoning, multi-agent systems | 1,411 papers; positions RAG as a *component*; breadth over depth by design |

### Tier 2 — specialized and 2025–26 surveys

- **"Retrieval-Augmented Generation: A Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers"** — Chaitanya Sharma — 2025 — [arXiv:2506.00054](https://arxiv.org/abs/2506.00054). Taxonomy: retriever-centric / generator-centric / hybrid / **robustness-oriented** designs; foregrounds noise & adversarial robustness, grounding fidelity, privacy-preserving retrieval as frontiers. Preprint.
- **"A Survey on Knowledge-Oriented Retrieval-Augmented Generation"** — 2025 — [arXiv:2503.10677](https://arxiv.org/abs/2503.10677). Knowledge-source-centric view (documents, databases, structured data).
- **"Retrieval-Augmented Generation for Natural Language Processing: A Survey"** — 2024 — [arXiv:2407.13193](https://arxiv.org/abs/2407.13193).
- **"Evaluation of Retrieval-Augmented Generation: A Survey"** — Springer chapter + [Awesome-RAG-Evaluation repo](https://github.com/YHPeter/Awesome-RAG-Evaluation). Splits evaluation into reference-required vs reference-free; notes reference-free (RAGAS/ARES-style) evaluation is unreliable when retrieved information is itself low-quality, and that benchmarks over-index on QA.
- **Domain surveys (2025–26):** repository-level retrieval-augmented code generation ([arXiv:2510.04905](https://arxiv.org/abs/2510.04905)); multimodal RAG for document understanding ([arXiv:2510.15253](https://arxiv.org/pdf/2510.15253)); RAG security — "Securing Retrieval-Augmented Generation: A Taxonomy of Attacks, Defenses, and Future Directions" ([arXiv:2604.08304](https://arxiv.org/pdf/2604.08304), 2026).
- **Historical anchor:** "Retrieving and Reading: A Comprehensive Survey on Open-domain Question Answering" ([arXiv:2101.00774](https://arxiv.org/pdf/2101.00774)) documents the pre-RAG ODQA lineage; Lilian Weng's ["How to Build an Open-Domain Question Answering System?"](https://lilianweng.github.io/posts/2020-10-29-odqa/) (2020) remains the best tutorial-grade genealogy of DrQA→ORQA→REALM→DPR→RAG/FiD.

**Meta-observation on the survey literature:** taxonomy production has outpaced knowledge production. Between 2023 and 2026 the field generated at least five incompatible top-level taxonomies (paradigm-based, stage-based, module-based, agentic-pattern-based, context-engineering-based). None is predictive — no taxonomy tells you *which* configuration will work for a given workload; Zhao et al.'s query-level taxonomy comes closest by classifying the *problem* rather than the *solution*.

---

## Debates and position papers

### 1. "Is RAG dead?" / long-context vs. RAG

- **Pro-long-context:** Li et al. ([arXiv:2407.16833](https://arxiv.org/abs/2407.16833)) — LC beats RAG when resourced; propose Self-Route (model self-reflects to route query to RAG or LC), recovering LC quality at a fraction of cost.
- **Pro-RAG:** Yu et al., "In Defense of RAG in the Era of Long-Context Language Models" ([arXiv:2409.01666](https://arxiv.org/abs/2409.01666)) — LC models lose focus in extreme lengths; OP-RAG (order-preserving retrieval) beats LC with fewer tokens; answer quality vs #chunks is an inverted U.
- **Mechanistic ammunition for both sides:** Lost in the Middle ([arXiv:2307.03172](https://arxiv.org/abs/2307.03172)); "Beyond RAG vs. Long-Context: Learning Distraction-Aware Retrieval" ([arXiv:2509.21865](https://arxiv.org/pdf/2509.21865)).
- **Practitioner synthesis:** RAGFlow's 2025 review ([link](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)) and LightOn's ["RAG is Dead, Long Live RAG"](https://lighton.ai/lighton-blogs/rag-is-dead-long-live-rag-retrieval-in-the-age-of-agents): context-stuffing is brute force — attention scatter + non-linear cost; ~two orders of magnitude cost gap between full-context and full-RAG regimes; the real question is cost-optimal context assembly, not survival of an acronym. LightOn reframes agent-era retrieval as four decisions: **IF / WHAT / WHERE&HOW to retrieve, then generate with minimal faithful context**.
- **The grep counter-argument (2026):** AkitaOnRails ([link](https://akitaonrails.com/en/2026/04/06/rag-is-dead-long-context/)) — with 1M-token windows and prompt caching, the *mandatory vector DB* is dead: Claude Code uses a ~150-char/line markdown index, on-demand file reads, and grep over transcripts, with async memory consolidation ("a forked subagent running grep on text logs"). Concedes vector search still wins for: massive corpora, vocabulary mismatch, non-text modalities, hard latency budgets, compliance-auditable retrieval. Note this is a practitioner blog analyzing leaked source — directionally credible, not peer-reviewed.

**Disagreement to preserve:** Li et al. say LC > RAG on quality; Yu et al. say the opposite at lower cost; LaRA-style studies say "depends on task/model/length." These are not contradictory once cost and task type are conditioned on — but the literature rarely conditions on *corpus scale beyond context size*, which is where RAG is unavoidable.

### 2. RAG vs. fine-tuning

- Ovadia et al., "Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs" — EMNLP 2024 — [arXiv:2312.05934](https://arxiv.org/abs/2312.05934): RAG consistently beats unsupervised fine-tuning for both seen and novel knowledge; LLMs "struggle to learn new factual information through unsupervised fine-tuning."
- Soudani et al., "Fine Tuning vs. RAG for Less Popular Knowledge" — [arXiv:2403.01432](https://arxiv.org/abs/2403.01432): RAG's advantage is largest on tail/low-popularity facts.
- Consensus by 2026: fine-tuning for *behavior/format/skill*, retrieval for *knowledge*; hybrids best in some domains. Largely settled debate.

### 3. Cache-augmented generation (CAG)

- Chan et al., "Don't Do RAG: When Cache-Augmented Generation is All You Need for Knowledge Tasks" — WWW 2025 companion — [arXiv:2412.15605](https://arxiv.org/abs/2412.15605): preload the entire (bounded) knowledge base into context, cache the KV state, answer with zero retrieval — eliminating retrieval latency and retrieval error for small corpora. Honest scope limitation: only viable for constrained knowledge bases. The RAGFlow review's cost analysis places KV-cache approaches ≥1 order of magnitude more expensive than RAG at scale. **Read that multiplier as amortized/absolute, not marginal:** it counts the full-corpus prefill plus KV storage, re-paid on every corpus change, whereas the *per-query* cost once the cache is warm is near zero (which is why `memory-context-engineering.md` scores CAG as "very low marginal" in its cost table). Both ratings are correct; CAG's economics hinge on queries-per-cache-build and corpus staleness, not on a single cost multiple. CAG is best read not as RAG's replacement but as the limiting case of the retrieval-granularity spectrum (retrieve-nothing/cache-everything ↔ retrieve-token-level à la kNN-LM).

### 4. Retrieval as the future of LMs (position)

- Asai et al., "Reliable, Adaptable, and Attributable Language Models with Retrieval" — 2024 — [arXiv:2403.03187](https://arxiv.org/abs/2403.03187): argues retrieval-augmented LMs should *replace* parametric LMs as the default (verifiability, updatability, attribution), but identifies why they haven't: (a) retriever–LM interaction is too shallow (frozen top-k concatenation), (b) no infrastructure for datastore-scale training/serving. Roadmap: rethink datastores, deepen retriever–LM interaction, invest in open infrastructure. This paper is the best single first-principles motivation document for a next-gen framework.

### 5. How the meaning of "RAG" drifted

Chronology of the semantic drift, with citable anchors:
1. **2020:** RAG = a specific trained model architecture (Lewis et al.).
2. **2023:** RAG = the frozen chunk/embed/top-k/stuff pipeline ("Naive RAG" in Gao et al. 2312.10997) — the term's center of gravity moves from ML to software engineering.
3. **2024:** RAG = a configurable module graph (Modular RAG 2407.21059); "advanced RAG" tricks (query rewriting, reranking, HyDE-style expansion) become table stakes.
4. **2025:** RAG = one subsystem of context engineering (Mei et al. 2507.13334); agentic RAG surveys recast retrieval as agent tool-use (Singh et al. 2501.09136); memory systems split off as a sibling discipline sharing retrieval machinery but over interaction logs rather than static corpora (RAGFlow).
5. **2026:** "Context engine" framing — retrieval as an intelligent middle layer serving agents at machine query rates across domain knowledge, tool descriptions (tool retrieval), and memory (RAGFlow 2025 review); simultaneously, minimalists argue the vector-DB-centric stack was an artifact of short contexts and weak models (AkitaOnRails).

Implication for a new framework: any paper must define *which* RAG it is reimagining; the strongest framing is retrieval as a **first-class, cost-aware, composable interface between models and external state**, which subsumes all five meanings.

---

## Failure modes & critiques

### Barnett et al.'s seven failure points (canonical engineering taxonomy)

"Seven Failure Points When Engineering a Retrieval Augmented Generation System" — Barnett, Kurniawan, Thudumu, Brannelly, Abdelrazek — CAIN 2024 — [arXiv:2401.05856](https://arxiv.org/abs/2401.05856); FP list confirmed via [GM-RKB summary](https://www.gabormelli.com/RKB/Barnett_et_al.,_2024). Three case studies (research, education, biomedical). 

| FP | Name | Failure |
|---|---|---|
| FP1 | Missing Content | Answer not in the indexed corpus at all; system answers anyway |
| FP2 | Missed the Top Ranked Documents | Relevant doc exists but doesn't rank into top-k |
| FP3 | Not in Context — Consolidation | Retrieved but lost during context assembly/window packing |
| FP4 | Not Extracted | In context, but the LLM fails to pull the answer out (noise/conflict) |
| FP5 | Wrong Format | Output ignores required structure/format |
| FP6 | Incorrect Specificity | Answer too general or too specific for the need |
| FP7 | Incomplete Answers | Partial answer despite available evidence |

Key lessons (from the paper): "validation of a RAG system is only feasible during operation" and "robustness evolves rather than [being] designed in at the start." Critique of the taxonomy itself: it is symptom-level and QA-centric; FP1/FP2 are retrieval-quality issues, FP3 is an orchestration issue, FP4–FP7 are generation issues — the taxonomy does not localize *causes*, motivating instrumentation like sufficient-context classification.

### Capability-level failures (RGB)

RGB ([arXiv:2309.01431](https://arxiv.org/abs/2309.01431)): LLMs show consistent deficits in noise robustness, **negative rejection** (answering when they shouldn't), information integration across documents, and counterfactual robustness (detecting that retrieved "evidence" is wrong). These are model-side failures no retriever fix can solve.

### Causal attribution of failures (sufficient context)

Joren et al., "Sufficient Context" ([arXiv:2411.06037](https://arxiv.org/abs/2411.06037)): classify each instance by whether retrieved context *suffices* to answer, then stratify errors. Findings: **larger models hallucinate rather than abstain when context is insufficient; smaller models hallucinate even when it is sufficient.** This cleanly separates retrieval failure from grounding failure — a diagnostic primitive any new framework should build in natively.

### Systemic critiques (assembled across sources)

1. **The frozen-pipeline compromise.** The 2023–25 mainstream abandoned everything that made 2020-era RAG interesting (joint training, marginalization over evidence, learned retrieval) for operational convenience. Asai et al. (2403.03187) name the consequence: shallow retriever–LM interaction is the root cause of many grounding failures.
2. **Chunking is a lossy, untheorized primitive.** Fixed-size chunking destroys document structure; chunk-quality evaluation is itself an open problem (HOPE, [arXiv:2505.02171](https://arxiv.org/pdf/2505.02171)); hierarchical alternatives (TreeRAG's search-fine/retrieve-coarse decoupling, PageIndex TOC-based indexing — RAGFlow) are ad hoc responses.
3. **Single-vector semantic similarity ≠ relevance for reasoning.** The agentic-search movement (A-RAG's keyword+semantic+read hierarchy; Claude Code's grep) is an implicit indictment of embedding-only retrieval; vocabulary-mismatch is where embeddings still win (AkitaOnRails' concessions).
4. **Evaluation is circular and QA-biased.** Reference-free evaluators (RAGAS/ARES) use LLMs to judge LLMs and degrade with low-quality retrieval; benchmarks (RGB, [CRAG — arXiv:2406.04744](https://arxiv.org/pdf/2406.04744), [CRUD-RAG — ACM TOIS](https://dl.acm.org/doi/10.1145/3701228)) mostly measure QA, not agent workloads; RAGCap-Bench ([arXiv:2510.13910](https://arxiv.org/pdf/2510.13910)) begins addressing agentic-RAG capabilities.
5. **Robustness/security were bolted on.** Poisoned or adversarial corpora, privacy leakage from datastores ("The Good and The Bad" — [arXiv:2402.16893](https://arxiv.org/pdf/2402.16893)), and attack/defense taxonomies (2604.08304) arrived years after deployment at scale.
6. **Cost/latency were never first-class.** The entire is-RAG-dead debate is at bottom a cost-model argument (8–82× retrieval savings vs. prompt-caching economics), yet almost no academic RAG paper reports cost-normalized quality; the practitioner literature (LightOn, RAGFlow) leads here.
7. **Static-corpus assumption.** Benchmarks assume a fixed corpus; periodically updated corpora break index freshness and cache validity (DRAGOn, [arXiv:2507.05713](https://arxiv.org/pdf/2507.05713)); agent memory makes the corpus *self-written*, which no classical RAG evaluation contemplates.
8. **RETRO-style architectural retrieval quietly failed in practice** — datastore test-leak concerns (2302.12128) plus operational complexity; the field should be honest that the "trillions of tokens" result has not been production-replicated publicly.

---

## Comparison tables

### Foundational models (2017–2022)

| System | ID | Year | Retriever | Granularity | Trained jointly? | Enduring contribution |
|---|---|---|---|---|---|---|
| DrQA | 1704.00051 | 2017 | TF-IDF (sparse) | document/para | No | retriever–reader decomposition |
| ORQA | 1906.00300 | 2019 | learned dense | evidence block | Yes (latent) | retrieval as latent variable; ICT pretraining |
| kNN-LM | 1911.00172 | 2020 | k-NN over LM states | **token** | No (post-hoc) | non-parametric memory interpolation |
| REALM | 2002.08909 | 2020 | learned dense | passage | Yes (pretraining) | retrieval-augmented pretraining |
| DPR | 2004.04906 | 2020 | dual-encoder dense | passage | Retriever only | the vector-DB substrate |
| RAG | 2005.11401 | 2020 | DPR | passage | Yes (fine-tune) | the name; marginalizing generator |
| FiD | 2007.01282 | 2020 | BM25/DPR | passage | Reader only | evidence fusion scales with k |
| RETRO | 2112.04426 | 2021 | frozen BERT k-NN | chunk | Generator (CCA) | trillion-token datastore ≈ 25× params |
| Atlas | 2208.03299 | 2022 | Contriever (trained) | passage | Yes | few-shot knowledge tasks; updatable index |

### Knowledge-provision paradigms (mid-2026 view)

| Paradigm | Mechanism | Best regime | Cost (RAGFlow/LightOn estimates) | Killer weakness |
|---|---|---|---|---|
| Long-context stuffing | full corpus in prompt | corpus ≤ window; deep cross-doc reasoning | ~100× RAG | attention scatter; cost; corpus > window |
| CAG / KV-cache preload | cached KV of corpus | small static KB, repeated queries | ≥10× RAG *amortized* (prefill + KV storage, re-paid on corpus change); ~0 marginal per warm-cache query | corpus bounded; cache invalidation |
| Classic pipeline RAG | embed + top-k + stuff | large corpora, factoid queries | baseline (1×) | FP1–FP7; semantic-only matching |
| Agentic retrieval | model wields search tools in loop | complex/multi-hop; heterogeneous sources | variable (multi-call) | latency; compounding tool errors; eval immaturity |
| Lexical + long context ("grep era") | BM25/grep + big window | code, logs, agent memory | low infra, cache-friendly | vocabulary mismatch; non-text modalities |
| Fine-tuning | weights | style/skill/format | training cost | poor at facts, esp. tail knowledge (2312.05934, 2403.01432) |

### Failure taxonomies compared

| Taxonomy | Level | Localizes cause? | Covers agentic loops? |
|---|---|---|---|
| Barnett FP1–7 (2401.05856) | symptom / engineering | Partially (stage-wise) | No |
| RGB four capabilities (2309.01431) | model capability | Model-side only | No |
| Sufficient context (2411.06037) | causal (retrieval vs grounding) | Yes (binary) | No |
| Robustness surveys (2506.00054, 2606.28337) | systems (sensitivity/stability) | Statistically | Partially |
| Security taxonomies (2604.08304) | adversarial | Yes | Emerging |

---

## Open problems (seed material for a next-generation framework)

1. **No theory of context assembly.** We have taxonomies of modules but no principled objective for *what belongs in context* given a query, a token budget, and a cost model. The field optimizes proxies (similarity top-k) for an unformalized quantity (marginal utility of a context item to the answer). A framework that treats context assembly as budgeted decision-theoretic optimization — the IF/WHAT/WHERE-HOW decisions (LightOn) made explicit and learnable — would unify RAG, CAG, memory, and tool retrieval.
2. **Retriever–generator interaction is still shallow.** Asai et al.'s critique stands in 2026: top-k concatenation is the dominant interface. kNN-LM (token-level), FiD (decoder fusion), and RETRO (cross-attention) each demonstrated deeper couplings that the frozen-pipeline era discarded. Open question: what is the right *interface depth* now that generators are strong — logits? attention? tool calls? structured scratchpads?
3. **Granularity is unresolved.** Token (kNN-LM) ↔ chunk (RAG) ↔ document ↔ whole-corpus (CAG/long-context) is a spectrum; 2026 systems pick a point by folklore. A hierarchical interface (A-RAG; TreeRAG's search-fine/retrieve-coarse split) suggests the answer is *adaptive multi-granularity*, but nobody has formalized or learned the policy.
4. **Failure attribution is not built in.** Sufficient-context classification shows failures can be causally attributed at inference time; no mainstream framework instruments this natively (was it FP1 missing content, FP2 ranking, FP3 assembly, or FP4 grounding?). A next-gen design should emit *auditable retrieval provenance and abstention* as first-class outputs — also the compliance argument that keeps vector retrieval alive.
5. **Cost-normalized evaluation.** Quality-per-dollar / per-token / per-millisecond is the actual production objective; academic benchmarks ignore it, which is why the is-RAG-dead debate happened in blogs instead of papers. Benchmarks must condition on corpus scale > context window, corpus churn (DRAGOn), and agent-rate query loads.
6. **The self-writing corpus.** Agent memory means the datastore is produced by the same system that queries it — feedback loops (error reinforcement, memory poisoning) are unstudied in the RAG literature; memory and RAG share machinery but not evaluation (RAGFlow's static-knowledge vs interaction-log distinction is a start).
7. **Negative rejection / calibrated abstention remains unsolved** at the model level (RGB; sufficient-context finding that *bigger models abstain less*). Retrieval frameworks currently have no principled contract for "the corpus does not contain this."
8. **Retraining the stack.** RAG-considerate pretraining scaling laws (2604.00715) and RL over retrieval trajectories (process vs outcome reward, 2505.14069) reopen the joint-optimization question REALM/Atlas posed: how should parametric memorization and non-parametric retrieval be co-optimized under a compute budget? This is the most first-principles open problem — the memorize-vs-retrieve frontier — and it is where a "reimagined RAG" can claim genuine novelty over orchestration work.

---

## Bibliography

### Foundational models
- Chen et al., *Reading Wikipedia to Answer Open-Domain Questions* (DrQA), ACL 2017 — https://arxiv.org/abs/1704.00051
- Lee et al., *Latent Retrieval for Weakly Supervised Open Domain QA* (ORQA), ACL 2019 — https://arxiv.org/abs/1906.00300
- Khandelwal et al., *Generalization through Memorization: Nearest Neighbor Language Models* (kNN-LM), ICLR 2020 — https://arxiv.org/abs/1911.00172
- Guu et al., *REALM: Retrieval-Augmented Language Model Pre-Training*, ICML 2020 — https://arxiv.org/abs/2002.08909
- Karpukhin et al., *Dense Passage Retrieval for Open-Domain QA* (DPR), EMNLP 2020 — https://arxiv.org/abs/2004.04906
- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (RAG), NeurIPS 2020 — https://arxiv.org/abs/2005.11401
- Izacard & Grave, *Leveraging Passage Retrieval with Generative Models for Open Domain QA* (FiD), 2020 — https://arxiv.org/abs/2007.01282
- Borgeaud et al., *Improving Language Models by Retrieving from Trillions of Tokens* (RETRO), ICML 2022 — https://arxiv.org/abs/2112.04426 ; PMLR: https://proceedings.mlr.press/v162/borgeaud22a/borgeaud22a.pdf
- Izacard et al., *Atlas: Few-shot Learning with Retrieval Augmented Language Models*, 2022 — https://arxiv.org/abs/2208.03299
- Wang et al., *Shall We Pretrain Autoregressive Language Models with Retrieval? A Comprehensive Study*, EMNLP 2023 — https://aclanthology.org/2023.emnlp-main.482/
- *InstructRetro: Instruction Tuning post Retrieval-Augmented Pretraining* — https://arxiv.org/abs/2310.07713
- *On the Generalization Ability of Retrieval-Enhanced Transformers*, 2023 — https://arxiv.org/abs/2302.12128

### Surveys & taxonomies
- Gao et al., *RAG for Large Language Models: A Survey*, 2023/24 — https://arxiv.org/abs/2312.10997
- Fan et al., *A Survey on RAG Meeting LLMs*, KDD 2024 — https://dl.acm.org/doi/10.1145/3637528.3671470
- Huang et al., *A Survey on Retrieval-Augmented Text Generation for LLMs*, 2024 — https://arxiv.org/abs/2404.10981
- Gao et al., *Modular RAG: LEGO-like Reconfigurable Frameworks*, 2024 — https://arxiv.org/abs/2407.21059
- Zhao et al., *RAG and Beyond: How to Make your LLMs use External Data More Wisely*, 2024 — https://arxiv.org/abs/2409.14924
- Singh et al., *Agentic RAG: A Survey on Agentic RAG*, 2025 (v4 2026) — https://arxiv.org/abs/2501.09136 ; repo: https://github.com/asinghcsu/AgenticRAG-Survey
- Mei et al., *A Survey of Context Engineering for LLMs*, 2025 — https://arxiv.org/abs/2507.13334
- Sharma, *RAG: Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers*, 2025 — https://arxiv.org/abs/2506.00054
- *A Survey on Knowledge-Oriented RAG*, 2025 — https://arxiv.org/abs/2503.10677
- *RAG for NLP: A Survey*, 2024 — https://arxiv.org/abs/2407.13193
- *Evaluation of RAG: A Survey* — Springer — https://link.springer.com/chapter/10.1007/978-981-96-1024-2_8 ; repo: https://github.com/YHPeter/Awesome-RAG-Evaluation
- *Retrieval-Augmented Code Generation: Repository-Level Approaches*, 2025/26 — https://arxiv.org/abs/2510.04905
- *Multimodal RAG for Document Understanding: A Survey* — https://arxiv.org/pdf/2510.15253
- *Securing RAG: A Taxonomy of Attacks, Defenses, and Future Directions*, 2026 — https://arxiv.org/pdf/2604.08304
- *Retrieving and Reading: A Comprehensive Survey on Open-domain QA*, 2021 — https://arxiv.org/pdf/2101.00774
- Lilian Weng, *How to Build an Open-Domain Question Answering System?*, 2020 — https://lilianweng.github.io/posts/2020-10-29-odqa/

### Failure modes, robustness, evaluation
- Barnett et al., *Seven Failure Points When Engineering a RAG System*, CAIN 2024 — https://arxiv.org/abs/2401.05856 ; ACM: https://dl.acm.org/doi/10.1145/3644815.3644945 ; FP list: https://www.gabormelli.com/RKB/Barnett_et_al.,_2024
- Chen et al., *Benchmarking LLMs in RAG* (RGB), AAAI 2024 — https://arxiv.org/abs/2309.01431
- Liu et al., *Lost in the Middle*, TACL 2024, Vol. 12, pp. 157–173 (arXiv Jul 2023) — https://arxiv.org/abs/2307.03172 ; https://aclanthology.org/2024.tacl-1.9/
- Joren et al., *Sufficient Context: A New Lens on RAG Systems*, 2024 — https://arxiv.org/abs/2411.06037
- *CRAG — Comprehensive RAG Benchmark*, 2024 — https://arxiv.org/abs/2406.04744
- *CRUD-RAG*, ACM TOIS — https://dl.acm.org/doi/10.1145/3701228
- *A Systems-Level Analysis of Sensitivity, Robustness, and Stability in RAG*, 2026 — https://arxiv.org/pdf/2606.28337
- *The Good and The Bad: Privacy Issues in RAG*, 2024 — https://arxiv.org/pdf/2402.16893
- *A New HOPE: Domain-agnostic Automatic Evaluation of Text Chunking*, 2025 — https://arxiv.org/pdf/2505.02171
- *RAGCap-Bench: Benchmarking Capabilities of LLMs in Agentic RAG Systems*, 2025 — https://arxiv.org/pdf/2510.13910
- *DRAGOn: Designing RAG On Periodically Updated Corpus*, 2025 — https://arxiv.org/pdf/2507.05713
- Wang et al., *Searching for Best Practices in RAG*, 2024 — https://arxiv.org/abs/2407.01219

### Debates & positions
- Li et al., *RAG or Long-Context LLMs? A Comprehensive Study and Hybrid Approach* (Self-Route), 2024 — https://arxiv.org/abs/2407.16833
- Yu et al., *In Defense of RAG in the Era of Long-Context Language Models* (OP-RAG), 2024 — https://arxiv.org/abs/2409.01666
- Chan et al., *Don't Do RAG: When Cache-Augmented Generation is All You Need*, WWW'25 companion — https://arxiv.org/abs/2412.15605 ; ACM: https://dl.acm.org/doi/10.1145/3701716.3715490
- Asai et al., *Reliable, Adaptable, and Attributable Language Models with Retrieval* (position), 2024 — https://arxiv.org/abs/2403.03187
- Ovadia et al., *Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs*, EMNLP 2024 — https://arxiv.org/abs/2312.05934 ; https://aclanthology.org/2024.emnlp-main.15/
- Soudani et al., *Fine Tuning vs. RAG for Less Popular Knowledge*, 2024 — https://arxiv.org/abs/2403.01432
- *Beyond RAG vs. Long-Context: Distraction-Aware Retrieval*, 2025 — https://arxiv.org/pdf/2509.21865
- RAGFlow/InfiniFlow, *From RAG to Context — A 2025 Year-End Review of RAG* — https://ragflow.io/blog/rag-review-2025-from-rag-to-context
- LightOn, *RAG is Dead, Long Live RAG: Retrieval in the Age of Agents* — https://lighton.ai/lighton-blogs/rag-is-dead-long-live-rag-retrieval-in-the-age-of-agents
- AkitaOnRails, *Is RAG Dead? Long Context, Grep, and the End of the Mandatory Vector DB*, Apr 2026 — https://akitaonrails.com/en/2026/04/06/rag-is-dead-long-context/

### Agentic / 2026 frontier
- Asai et al., *Self-RAG*, 2023 — https://arxiv.org/abs/2310.11511
- Du et al., *A-RAG: Scaling Agentic RAG via Hierarchical Retrieval Interfaces*, 2026 — https://arxiv.org/abs/2602.03442
- *TreePS-RAG: Tree-based Process Supervision for RL in Agentic RAG*, 2026 — https://arxiv.org/pdf/2601.06922
- *RAGShaper: Eliciting Sophisticated Agentic RAG Skills via Automated Data Synthesis*, 2026 — https://arxiv.org/pdf/2601.08699
- *Process vs. Outcome Reward: Which is Better for Agentic RAG Reinforcement Learning*, 2025 — https://arxiv.org/pdf/2505.14069
- *To Memorize or to Retrieve: Scaling Laws for RAG-Considerate Pretraining*, 2026 — https://arxiv.org/pdf/2604.00715

**Uncertainty notes:** LaRA benchmark details (2,326 cases / 11 LLMs) are cited secondhand from the RAGFlow review — arXiv ID not independently verified. FiD's EACL 2021 venue and Self-RAG's ICLR 2024 acceptance are widely reported but were seen here only as arXiv preprints. 2026-numbered arXiv IDs (26xx.xxxxx) are preprints, not peer-reviewed. Blog sources (RAGFlow, LightOn, AkitaOnRails) are practitioner/vendor perspectives: RAGFlow and LightOn have commercial interests in RAG infrastructure; AkitaOnRails analyzes leaked, unverified source code.
