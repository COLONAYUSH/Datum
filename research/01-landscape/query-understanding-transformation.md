# Query Understanding & Transformation in RAG and Agentic Retrieval — Research Landscape (as of August 2026)

## Scope

This document catalogues the research lineage, state of the art, failure modes, and open problems for the **query side** of retrieval-augmented generation (RAG) and agentic LLM systems: everything that happens between a raw user utterance (or an agent's internal information need) and the string/vector/structured request that actually hits a retrieval engine. Covered:

- **Rewriting** — reformulating a query for a frozen retriever (Rewrite-Retrieve-Read and descendants, RL-trained rewriters).
- **Expansion** — enriching the query with generated pseudo-content (HyDE, query2doc, GenQREnsemble).
- **Decomposition** — splitting complex/multi-hop questions into sub-queries (least-to-most, IRCoT, RQ-RAG, bandit-based decomposition).
- **Abstraction** — step-back prompting and concept-level querying.
- **Multi-query + fusion** — issuing several reformulations and merging ranked lists (RAG-Fusion, DMQR-RAG).
- **Conversational rewriting** — resolving anaphora, ellipsis, and topic shift in multi-turn settings.
- **Structured/self-query** — extracting metadata filters and structured constraints from natural language.
- **Routing & intent classification** — deciding *whether* and *how* to retrieve (Adaptive-RAG, semantic-router, RAGRouter-Bench).
- **Ambiguity & clarification** — ambiguous factoid questions (ASQA) and clarify-vs-guess decisions.
- **Reasoning-intensive queries** — where relevance itself requires inference (BRIGHT, BRIGHT-Pro).
- **Learned/RL query optimization (2025–2026)** — DeepRetrieval, Search-R1/R1-Searcher, s3, RL-QR, and the surveys that systematize them.

Excluded (covered by sibling dimensions): index construction, chunking, embedding models, rerankers, generation-side grounding, and memory architectures — except where they interact directly with query formulation.

Sourcing note: every citation below was seen directly in a web search result or fetched page during this research pass. Peer-review status is noted where known; several 2025–2026 items are preprints and are flagged as such. arXiv IDs beginning `26xx` are 2026 submissions.

---

## Lineage & chronological development

### Pre-LLM roots (context, brief)

Query transformation predates RAG by decades: classical IR relied on pseudo-relevance feedback (PRF), thesaurus/synonym expansion, and spelling/intent normalization in web search. The LLM era's contribution is replacing statistical expansion with *generative* expansion and replacing hand-built intent taxonomies with promptable or trainable classifiers. The recurring theme — a vocabulary/intent mismatch between how users ask and how corpora are written — is the same problem PRF attacked in the 1990s; what changed is the tool.

### 2022 — generative expansion and interleaved retrieval emerge

- **HyDE** — Gao, Ma, Lin, Callan — arXiv:2212.10496 — Dec 2022. Zero-shot dense retrieval by generating a *hypothetical document* answering the query, then embedding that document and searching for real neighbors. Key claim: the dense encoder's bottleneck filters out hallucinated specifics while preserving relevance structure; significantly outperformed unsupervised Contriever. Foundational and heavily cited.
- **IRCoT** — Trivedi et al. — arXiv:2212.10509 — Dec 2022. Interleaves retrieval with chain-of-thought steps for multi-hop QA: each CoT sentence seeds the next retrieval, and retrieved text conditions the next CoT step. Improved retrieval by up to 21 points and downstream QA by up to 15 points on HotpotQA, 2WikiMultihopQA, MuSiQue, IIRC; also reduced hallucination in the CoT. Establishes the core insight that *what to retrieve next depends on what has been derived so far* — the intellectual ancestor of 2025's RL search agents.
- **Least-to-most prompting** — Zhou et al. — arXiv:2205.10625 — ICLR 2023. Decompose a complex problem into ordered subproblems and solve sequentially, each conditioned on prior answers (99%+ on SCAN vs 16% for CoT). Not retrieval-specific, but the canonical template for query decomposition in RAG pipelines.
- **ASQA** — Stelmakh, Luan, Dhingra, Chang — arXiv:2204.06092 — 2022. Dataset of *ambiguous factoid questions* requiring long-form answers that cover all valid interpretations; showed a large human–machine gap. Still the reference benchmark for the ambiguity problem that clarification/disambiguation modules target.

### 2023 — rewriting becomes a trainable module

- **Rewrite-Retrieve-Read** — Ma et al. — arXiv:2305.14283 — 2023. Reframes the pipeline from retrieve-then-read to *rewrite*-retrieve-read; a small trainable rewriter LM is tuned via RL using feedback from the frozen black-box reader LLM. The first widely-adopted formulation of query rewriting as a learnable component optimized against downstream answer quality rather than retrieval labels. Direct ancestor of the 2025 RL wave.
- **query2doc** — Wang, Yang, Wei — arXiv:2303.07678 — EMNLP 2023. Few-shot-prompt an LLM to write a pseudo-document, concatenate with the original query; +3–15% for BM25 on MS MARCO/TREC DL without fine-tuning, gains for dense retrievers too. The sparse-retrieval counterpart to HyDE.
- **Step-back prompting** — Zheng et al. (Google DeepMind) — arXiv:2310.06117 — 2023. Prompt the model to first derive a higher-level concept/principle ("step-back question"), retrieve/reason at that abstraction, then answer the specific question. +7–11% MMLU physics/chemistry, +27% TimeQA, +7% MuSiQue on PaLM-2L. Canonical *query abstraction* technique.
- **Conversational rewriting matures on TREC CAsT**: LLM-instructed rewriting of conversational utterances (Galimzhanova et al., arXiv:2410.07797, work published 2023, IEEE/WIC) showed instruction-tuned LLMs beat prior neural rewriters by 25.2% MRR / 31.7% P@1 / 27% nDCG@3 on CAsT. Mixed-initiative rewriting (arXiv:2307.08803) combines system-asked clarifying questions with rewriting. The field's framing: conversational queries suffer from anaphora, ellipsis, implied context from prior answers, and topic shifts; rewriting into standalone form is the dominant fix (see Mo et al., "A Survey of Conversational Search," arXiv:2410.15576, later ACM TOIS).

### 2024 — decomposition/refinement gets end-to-end training; routing gets a benchmark identity

- **Adaptive-RAG** — Jeong et al. — arXiv:2403.14403 — NAACL 2024. Trains a small classifier (T5-Large) on automatically derived complexity labels to route each query to {no retrieval, single-step retrieval, iterative retrieval}. Matches always-iterate accuracy at much lower cost. The reference point for complexity routing; labels are derived from which strategy happens to answer correctly, which is also its main weakness (noisy, model/dataset-specific labels).
- **RQ-RAG** — Chan et al. — arXiv:2404.00610 — COLM 2024. Fine-tunes a 7B model end-to-end to emit explicit *rewrite / decompose / disambiguate* operations with special tokens, using ChatGPT-generated supervision; ~+1.9% average over SOTA on single-hop QA plus multi-hop gains. Notable as the first unified learned "query refinement policy" over multiple operation types.
- **GenQREnsemble** — Dhole & Agichtein — arXiv:2404.03746 — ECIR 2024. Ensemble of paraphrased zero-shot reformulation instructions generates multiple keyword sets; up to +18% nDCG@10, +24% MAP over prior zero-shot reformulators; a PRF variant (GenQREnsembleRF) adds further gains. Shows reformulation quality is highly prompt-sensitive — averaging over instruction paraphrases beats any single prompt.
- **RAG-Fusion** — Rackauckas — arXiv:2402.03367 — 2024 (case study; also Raudaschl's original GitHub implementation). Multi-query generation + Reciprocal Rank Fusion (RRF). Found answers improved on comprehensiveness but "some answers strayed off topic when the generated queries' relevance to the original query is insufficient" — the earliest widely-cited documentation of multi-query drift.
- **DMQR-RAG** — Li et al. — arXiv:2411.13154 — Nov 2024 (preprint). Diverse multi-query rewriting at four information levels plus an adaptive selector that minimizes the number of rewrites; motivated by noise/intent-deviation in user queries and redundancy among naive multi-queries.
- **BRIGHT** — Su et al. — arXiv:2407.12883 — ICLR 2025 (released July 2024). 1,384 real queries across 12 datasets (StackExchange, coding, theorem subsets) where relevance requires *reasoning*, not surface match — 1,384 is the current v4 count; the Jul 2024 v1 abstract reported 1,398. The top MTEB embedder at the time (SFR-Embedding-Mistral, 59.0 nDCG@10 on MTEB) scored **18.3 nDCG@10** on BRIGHT. Adding explicit CoT reasoning to queries improved retrieval by up to 12.2 points. BRIGHT reframed query transformation as *the* lever for reasoning-intensive retrieval and became the standard benchmark for it.
- **ARAGOG** — Eibich, Nagpal, Fred-Ojala — arXiv:2404.01037 — 2024 (preprint, small-scale). Empirical grading of advanced RAG techniques: HyDE and LLM reranking improved retrieval precision; **multi-query approaches underperformed**; MMR and Cohere rerank showed no notable advantage over naive RAG. An early empirical warning that popular query-side tricks do not compose or transfer for free.
- **A Survey of Query Optimization in LLMs** — Song & Zheng — arXiv:2412.17558 — Dec 2024 (v3 Mar 2026). Systematizes the field into four core operations — **expansion, decomposition, disambiguation, abstraction** — plus a query-complexity taxonomy (explicit/implicit evidence × single/multiple evidence) and a five-stage lifecycle (intent recognition → transformation → retrieval → evidence integration → response synthesis). Open problems it flags: process reward models for query optimization, efficiency, multimodal queries, weak evaluation methodology.

### 2025 — the RL turn: query generation as a trained policy against real engines

- **DeepRetrieval** — Jiang et al. — arXiv:2503.00223 — COLM 2025. Trains an LLM (3B) with RL (DeepSeek-R1-style, `<think>` then `<answer>` query) using *actual retrieval metrics as reward*, no supervised reference queries. Recall on literature search: 65.07% vs prior SOTA 24.68% (publications), 63.18% vs 32.11% (clinical trials); beats GPT-4o and Claude-3.5-Sonnet prompting on 11/13 datasets. Demonstrates that prompted frontier models are far from optimal query writers and that a small policy tuned on engine feedback wins. The title's "hacking real search engines" is apt: the policy learns engine-specific query syntax/quirks.
- **Search-R1** — Jin et al. — arXiv:2503.09516 — 2025. RL trains an LLM to interleave reasoning with autonomous multi-turn search-query generation; retrieved-token masking stabilizes training; outcome-based reward. +41% (Qwen2.5-7B) / +20% (3B) over RAG baselines on seven QA datasets. Sibling work **R1-Searcher** (arXiv:2503.05592) incentivizes search capability via RL similarly. These collapse "query understanding" into the agent's policy — there is no separate rewriter module.
- **s3** — Jiang et al. — arXiv:2505.14146 — EMNLP 2025. Decouples a small *searcher* policy from a frozen generator; trains the searcher with a **Gain-Beyond-RAG (GBR)** reward = improvement in generation accuracy over naive-RAG retrieval. Needs only 2.4k training examples (~70× less than prior work) and transfers across generators. The cleanest existing formulation of "query/search policy optimized for downstream utility, generator-agnostic."
- **RL-QR** — Cha et al. — arXiv:2507.23242 — 2025 (preprint). Annotation-free RL query rewriting using verifiable search rewards from index-aligned synthetic queries; works for lexical, semantic, and multimodal (ViDoRe) indices; retriever-specific rewriters. Notably reports that RL rewriting *failed to improve some lexical-retriever settings* in their proprietary data — evidence that rewriting gains are retriever- and corpus-dependent (uncertain: this failure detail is from the abstract-level summary; verify against full text).
- **Query decomposition as bandit learning** — Petcu et al. — arXiv:2510.18633 — Oct 2025 (preprint). Frames sub-query selection as exploration–exploitation: not all sub-queries deserve retrieval budget; bandit methods dynamically choose which sub-queries to pursue. First-principles treatment of decomposition *cost control*, which prompt-based decomposition ignores.
- **Surveys consolidate the agentic view**: "Reasoning RAG via System 1 or System 2" (Liang et al., arXiv:2506.10408) splits the field into predefined-pipeline reasoning vs agentic reasoning; "A Comprehensive Survey on RL-based Agentic Search" (Lin et al., arXiv:2510.16724) organizes what RL optimizes (query formulation among them), how, and where; "Doing More with Less" (arXiv:2502.00409) surveys routing for resource optimization. Also MARAG-R1 (arXiv:2510.27569): RL-learned coordination of *multiple retrieval tools*, extending query optimization to tool choice.

### 2026 — routing benchmarks, aspect-aware evaluation, and post-query-rewriting critiques

- **RAGRouter-Bench** — Wang et al. — arXiv:2602.00296 — Jan 2026 (v2 Apr 2026). A dedicated dataset/benchmark for adaptive-RAG routing across domains, addressing the fact that Adaptive-RAG-style routers were previously evaluated only on QA sets with derived labels. Its 7,727 queries span **four knowledge domains** and are each labelled with one of **three canonical query types** (factual / reasoning / summarization) — the "3 types" and "4 domains" figures quoted elsewhere in this corpus are both correct facets of the same set, not competing counts.
- **Lightweight Query Routing for Adaptive RAG** — Bansal & Agarwal — arXiv:2604.03455 — 2026 (preprint). On RAGRouter-Bench (7,727 queries, 4 domains): TF-IDF + SVM hits 93.2% routing accuracy and ~28% token savings vs always-expensive; **lexical TF-IDF features beat sentence-embedding features by 3.1 macro-F1** — surface keyword patterns predict complexity better than semantics, a humbling result for embedding-based routers. Medical queries hardest to route, legal easiest.
- **BRIGHT-Pro / Rethinking Reasoning-Intensive Retrieval** — Zhao et al. — arXiv:2605.04018 — 2026 (preprint). Critiques BRIGHT itself: narrow gold sets, retrievers evaluated in isolation. Expands queries with multi-aspect evidence, evaluates under static *and* agentic protocols; finds "aspect-aware and agentic evaluation expose behaviors hidden by standard metrics." Trains RTriever-4B on aspect-decomposed synthetic data.
- **Beyond Semantic Similarity (direct corpus interaction)** — Li et al. — arXiv:2605.05242 — 2026 (preprint). Radical critique: the *fixed similarity interface* (single top-k call) is itself the bottleneck for agentic search — evidence discarded at retrieval time "cannot be recovered by stronger downstream reasoning." Proposes bypassing embedding retrieval with terminal-style direct corpus tools (grep-like exact match, local context inspection, iterative refinement). If this line holds up, much of "query transformation" dissolves into "corpus interaction policy."
- Adjacent 2026 threads seen in searches (not fetched in full; cite with care): tier-based adaptive query routing for financial/legal/medical hybrid retrieval (arXiv:2604.14222); natural-language-query→retrieval-agent-configuration (arXiv:2605.27361); what makes training data valuable for agentic search (arXiv:2604.08124).

---

## State of the art — mid-2026 snapshot

1. **For static pipelines** (single-shot RAG over a fixed corpus), the strongest evidence-backed defaults are: complexity routing before retrieval (Adaptive-RAG-style; on RAGRouter-Bench even TF-IDF+SVM suffices), HyDE/query2doc-style expansion for zero-shot dense/sparse retrieval when the corpus is answer-shaped, and reasoning-augmented queries (CoT-expanded, à la BRIGHT +12.2 points) for reasoning-intensive corpora. Multi-query + RRF is popular in practice but empirically shaky (ARAGOG found it underperforming; RAG-Fusion documents drift; DMQR-RAG shows naive diversity is redundant).
2. **For agentic systems**, the field has largely moved from *transforming a query* to *training a search policy*: Search-R1/R1-Searcher fold query generation into the reasoning policy; DeepRetrieval shows a 3B RL policy beats frontier-model prompting at query writing; s3 shows a decoupled searcher trained on Gain-Beyond-RAG is data-efficient and generator-agnostic. As of mid-2026 the decoupled-searcher design (s3-style) is arguably the best cost/benefit point: modular, small, cheap to train, transferable.
3. **Evaluation is in flux**: BRIGHT is the standard for reasoning-intensive retrieval but is being superseded/critiqued by BRIGHT-Pro's aspect-aware, agentic protocols; routing now has RAGRouter-Bench; conversational rewriting still leans on TREC CAsT-era data, which predates modern agentic use.
4. **An emerging counter-thesis** (arXiv:2605.05242) holds that the single-shot top-k similarity interface — the thing query transformation exists to serve — should itself be replaced by direct, iterative corpus interaction. This is the sharpest first-principles challenge to the whole sub-field.

---

## Thematic deep-dives

### 1. Query rewriting (single-query reformulation)

**Canonical form**: Rewrite-Retrieve-Read (arXiv:2305.14283) — a trainable small rewriter LM, RL-tuned from the frozen reader's feedback, in front of a web search engine. Descendants split by training signal:

| Signal | Representative | Notes |
|---|---|---|
| Reader answer correctness (RL) | Rewrite-Retrieve-Read (2305.14283) | Original; reward sparse and reader-specific |
| Retrieval metric (RL, no labels) | DeepRetrieval (2503.00223) | Reward = recall/nDCG from the *real* engine; learns engine idiosyncrasies |
| Verifiable synthetic reward | RL-QR (2507.23242) | Index-aligned synthetic queries → annotation-free, retriever-specific rewriters |
| Downstream generation gain | s3 (2505.14146) | GBR reward; searcher decoupled from generator |
| Supervised distillation | RQ-RAG (2404.00610) | GPT-generated rewrite/decompose/disambiguate supervision |

**Key empirical facts**: prompted frontier LLMs are mediocre query writers relative to small tuned policies (DeepRetrieval beats GPT-4o/Claude-3.5 on 11/13 datasets); rewriting quality is domain-knowledge-bound — a withdrawn-but-instructive 2025 preprint (arXiv:2507.00477, "Read the Docs Before Rewriting," later withdrawn) argued rewriters need continual pre-training on domain docs because they lack the vocabulary to bridge query–document phrasing gaps in professional fields.

**Critiques**: rewrites optimized for one retriever/index do not transfer (RL-QR trains *per-retriever* rewriters — an ops burden); RL rewriters can reward-hack engine quirks, making them brittle to engine updates (implied by DeepRetrieval's own "hacking" framing); latency of an extra LLM call in front of every retrieval.

### 2. Query expansion (generative pseudo-content)

- **HyDE** (2212.10496): query → hypothetical answer document → embed → search. Strengths: zero-shot, no training. Documented weaknesses (from the paper and practitioner analyses, e.g., Zilliz/Behitek write-ups seen in search): hypothetical docs hallucinate; in sensitive domains a wrong hypothesis can systematically steer retrieval to plausible-but-wrong regions; each query costs an LLM generation (latency/cost); performance degrades when the model knows nothing about the topic — precisely the case where RAG is most needed. This last point is the central irony of generative expansion: *it works best when retrieval is least necessary*.
- **query2doc** (2303.07678): same idea for sparse+dense, concatenating pseudo-doc with query; +3–15% BM25. Same failure profile.
- **GenQREnsemble** (2404.03746): ensembles of instruction paraphrases; large zero-shot gains (+18% nDCG@10) but reveals prompt fragility — the fact that averaging over prompt paraphrases helps this much means any single-prompt expansion result is partly prompt lottery.
- **ARAGOG** (2404.01037) found HyDE among the few techniques with consistent precision gains — but on a small corpus/eval; treat as weak evidence.

### 3. Decomposition & interleaved retrieval

- **Least-to-most** (2205.10625) supplies the decomposition template; **IRCoT** (2212.10509) supplies the interleaving insight (retrieval targets are *path-dependent*).
- **RQ-RAG** (2404.00610) makes decomposition a learned token-level operation; **bandit decomposition** (2510.18633) adds budget rationality: sub-queries have unequal utility and retrieval should be allocated sequentially, not uniformly. An ACL 2025 SRW paper on question decomposition for RAG (aclanthology 2025.acl-srw.32, seen in search) works the same vein.
- **Failure profile**: over-decomposition of simple queries (cost, noise injection); error propagation — a wrong first-hop answer poisons all later sub-queries (inherited from least-to-most's sequential dependency); decomposition granularity has no principled stopping criterion; sub-answers must be re-composed, and composition errors are unmeasured by retrieval metrics.

### 4. Abstraction (step-back)

Step-back prompting (2310.06117) is the main entry; the Song & Zheng survey (2412.17558) elevates *abstraction* to one of its four core operations. Under-explored relative to expansion/decomposition: no learned/RL step-back policies were found in this pass; abstraction level is chosen by prompt, not by corpus statistics. Open question whether abstraction helps or hurts on BRIGHT-style tasks where the needed generalization is domain-specific (uncertain — no direct evaluation seen).

### 5. Multi-query + fusion

- RAG-Fusion (2402.03367, GitHub Raudaschl/rag-fusion): generate N query variants, retrieve per-variant, merge via RRF. Documented failure: off-topic drift when generated variants deviate from intent; RRF weights all variants equally, so one bad variant dilutes precision (motivates confidence-weighted RRF variants seen in follow-up work).
- DMQR-RAG (2411.13154): diversity must be *engineered* (four information levels) and *selected* (adaptive rewrite-count minimization) — naive "give me 4 paraphrases" yields near-duplicates.
- ARAGOG (2404.01037): multi-query underperformed baseline in their eval. Net assessment: multi-query is the most cargo-culted technique in practitioner RAG stacks relative to its evidence base.
- **Cross-reference — production reports the opposite ranking.** `production-industry.md` records a 5M-document production RAG deployment that ranks LLM multi-query generation as its **#1-ROI intervention**. Keep both views: the disagreement tracks the configuration, not the technique's name. The production variant emits *semantic + keyword* variants from the full conversation thread and feeds the merged pool through a cross-encoder reranker (50 → 15) over a heterogeneous enterprise corpus; the reranker absorbs the equal-weight-RRF dilution documented above, so broadening recall is nearly free. The negative results here are naive paraphrase variants fused by unweighted RRF, no reranker, on small homogeneous corpora, where a bad variant directly costs precision. The defensible synthesis: multi-query buys recall and is worth its cost **only when a precision stage follows it and the corpus is heterogeneous enough that one query view under-covers** — which is also why controlled ablations that hold the reranker out will keep reporting it as negative.

### 6. Conversational query rewriting

Multi-turn queries exhibit anaphora, ellipsis, references to prior *answers*, and topic shift (Mo et al. survey, 2410.15576 / ACM TOIS). Instructed LLMs now dominate rewriting on TREC CAsT (2410.07797: +25.2% MRR over prior methods); mixed-initiative systems (2307.08803) interleave clarifying questions with rewriting. Gaps: CAsT-era benchmarks are pre-agentic; rewriting to a single standalone query loses information when the turn genuinely depends on retrieved context from earlier turns; topic-shift detection remains brittle (survey-level claim); and in agent frameworks the "conversation" now includes tool outputs, which no conversational-rewriting benchmark models.

### 7. Self-query / structured filter extraction

The pattern (popularized by LangChain's self-querying retriever; the specific docs page has moved and was not retrievable in this pass — uncertain on current API details) is: LLM parses the natural-language query into a semantic query string *plus* structured metadata filters (date ranges, authors, categories) executed against the vector store's filter language. 2026 work generalizes this to full retrieval-agent *configuration* from natural language (arXiv:2605.27361, seen in search). Known practical issues (practitioner consensus, not benchmarked rigorously as far as this pass found): schema hallucination (filtering on nonexistent fields), over-filtering to empty result sets with no recovery path, and injection risk when filter syntax is generated by the LLM. This area is conspicuously under-benchmarked relative to its production ubiquity.

### 8. Routing & intent classification

- **Adaptive-RAG** (2403.14403): three-way complexity routing; labels auto-derived from strategy outcomes. Weaknesses: label noise, dataset-specificity, and a coarse 3-class ontology.
- **semantic-router** (aurelio-labs, GitHub, 3.8k stars): production-grade embedding-space route matching against exemplar utterances — no LLM call, sub-second. Represents the industry default for intent gating; its weakness is exemplar coverage: routes are only as good as the utterance sets, and out-of-distribution intents fall through to `None`.
- **RAGRouter-Bench** (2602.00296) + baseline study (2604.03455): the striking finding that **TF-IDF beats embeddings for complexity routing** (93.2% acc, ~28% token savings) suggests query "complexity" as currently defined is largely a surface-lexical property — which in turn suggests current complexity taxonomies are shallow proxies, not measurements of reasoning depth.
- **Routing surveys**: 2502.00409 (resource-optimisation routing across LLM systems).

### 9. Ambiguity & clarification

ASQA (2204.06092) established that ambiguous factoid questions need answers covering multiple interpretations, with a persistent human–machine gap. RQ-RAG includes disambiguation as a learned operation; mixed-initiative conversational work (2307.08803) asks clarifying questions. What's missing (no strong 2025–2026 result found in this pass): a principled *decision policy* for clarify-vs-diversify-vs-answer — current systems either always answer (covering interpretations à la ASQA) or hand-tune when to ask. This remains mostly heuristic.

### 10. Reasoning-intensive queries

BRIGHT (2407.12883, ICLR 2025): SOTA embedders collapse from 59.0 → 18.3 nDCG@10 when relevance requires reasoning; CoT-augmented queries recover up to +12.2. Follow-ons: BRIGHT-Pro (2605.04018) fixes narrow gold sets and adds agentic protocols; MRMR (2510.09510, seen in search) extends to multimodal expert domains; reasoning-aware rerankers and listwise LLM ranking over BM25 scores (InsertRank, 2506.14086, seen in search) attack the same gap from the ranking side. The consistent message: for reasoning-intensive needs, *query-side reasoning is currently worth more than better encoders*.

### 11. RL/learned query optimization (2025–2026) — the current frontier

Three architectural stances now compete:

1. **Integrated policy** (Search-R1, R1-Searcher): the generator itself learns when/what to search. Max capability, max coupling — retraining the whole model per deployment; reward is end-task only.
2. **Decoupled searcher** (s3, DeepRetrieval, RL-QR): a small policy specializes in query generation/search orchestration; generator frozen. Data-efficient (s3: 2.4k samples), transferable across generators, but capped by the fixed retrieval interface.
3. **Interface replacement** (2605.05242): abandon similarity search for direct corpus tools; the "query" becomes a sequence of exact-match/browse operations. Newest and least validated.

Surveys 2510.16724 (RL agentic search) and 2506.10408 (reasoning agentic RAG) both flag reliability, reproducibility of RL training, and reward design as unresolved.

---

## Comparison tables

### Technique family × evidence quality × chief failure mode

| Family | Exemplars | Evidence quality (mid-2026) | Chief failure mode |
|---|---|---|---|
| Generative expansion | HyDE, query2doc, GenQREnsemble | Strong for zero-shot IR benchmarks; peer-reviewed | Hallucinated expansion steers retrieval wrong exactly when model lacks knowledge; latency/cost per query |
| Learned rewriting (SFT) | RQ-RAG | Moderate (COLM 2024) | Distills teacher-LLM biases; frozen operation taxonomy |
| Learned rewriting (RL) | Rewrite-Retrieve-Read, DeepRetrieval, RL-QR | Strong recent results (COLM'25) | Per-engine/retriever specialization; reward hacking; brittle to index changes |
| Decomposition | least-to-most, IRCoT, bandit decomposition | Strong for multi-hop QA | Error propagation across hops; no stopping criterion; cost blowup |
| Abstraction | step-back | Moderate (single main paper) | Abstraction level unprincipled; untested on reasoning-intensive retrieval |
| Multi-query + fusion | RAG-Fusion, DMQR-RAG | Weak/contested (ARAGOG negative) | Query drift; equal-weight RRF dilution; near-duplicate variants |
| Conversational rewriting | CAsT-era LLM rewriters | Strong on CAsT; benchmarks aging | Loses answer-dependent context; topic-shift brittleness; no agentic benchmark |
| Self-query / structured | LangChain self-query pattern | Anecdotal/production only | Schema hallucination; empty-result dead ends; unbenchmarked |
| Routing | Adaptive-RAG, semantic-router, RAGRouter-Bench | Growing; new benchmark 2026 | Noisy auto-labels; complexity ≈ lexical surface features; coarse ontologies |
| RL search agents | Search-R1, s3 | Strong (EMNLP'25 etc.) but young | Reward design; training instability; generalization beyond QA-style rewards |

### The three 2025–2026 RL stances

| | Integrated (Search-R1) | Decoupled searcher (s3) | Interface replacement (2605.05242) |
|---|---|---|---|
| What is learned | Whole reasoning+search policy | Small searcher only | Corpus-interaction tool policy |
| Reward | Outcome (answer EM/F1) | Gain-Beyond-RAG | Task outcome via tool traces |
| Data need | Large | 2.4k samples | Unclear (new) |
| Generator coupling | Total | None (frozen) | None |
| Retrieval interface | Fixed top-k | Fixed top-k | Replaced (grep/browse/verify) |
| Main risk | Retrain per model; cost | Capped by interface | Unproven at scale; latency of many tool calls |

---

## Failure modes & critiques

Ranked roughly by how damaging they are to the standard "transform-then-retrieve" paradigm:

1. **The interface ceiling.** Every transformation technique ultimately funnels into one (or a few) top-k similarity calls. arXiv:2605.05242's critique: evidence pruned by that interface is unrecoverable downstream, and needs like exact lexical constraints, weak-clue combination, and local verification are *unexpressible* as embedding queries no matter how the query is rewritten. Query transformation may be optimizing the wrong variable.
2. **Expansion's knowledge paradox.** HyDE/query2doc gains come from the LLM already knowing roughly what the answer document looks like. On out-of-knowledge queries — the raison d'être of RAG — hypothetical documents are confidently wrong and *systematically* bias retrieval toward the model's prior (HyDE paper acknowledges "unreal... false details"; practitioner analyses document production latency/cost/safety issues). No mainstream technique detects when expansion should be *disabled*.
3. **Transformation without verification.** Rewrites, sub-queries, and step-back abstractions are almost never checked against the original intent before retrieval. RAG-Fusion's off-topic drift and DMQR-RAG's noise findings are symptoms; the Song & Zheng survey's call for *process reward models* is the diagnosis: the field optimizes end metrics with no per-step supervision of whether a transformation preserved intent.
4. **Evaluation myopia.** BRIGHT-Pro (2605.04018) shows BRIGHT-style narrow gold sets and isolated-retriever protocols hide behaviors that matter in agentic use (multi-aspect evidence, interactive querying). ARAGOG shows technique rankings flip across corpora/evals. Most query-transformation papers report a couple of QA datasets with EM/F1 — a signal now known to be unreliable for composed systems.
5. **Routing labels are circular and shallow.** Adaptive-RAG derives complexity labels from which pipeline happened to answer correctly (model- and dataset-dependent); RAGRouter-Bench baselines show TF-IDF beats embeddings, implying "complexity" as labeled is a lexical artifact. Routers trained this way encode yesterday's pipeline behavior, not query semantics.
6. **RL rewriters overfit their engine.** DeepRetrieval's framing ("hacking real search engines") is honest: the learned policy exploits engine-specific behaviors; RL-QR needs retriever-specific rewriters. Index refresh, engine update, or corpus drift silently invalidates the policy. No published monitoring/adaptation story found.
7. **Decomposition lacks economics.** Prompt-based decomposition has no cost model; the bandit paper (2510.18633) is the first to treat sub-query budget allocation as a decision problem. Everything before it retrieves for every sub-query uniformly — noise and token cost scale linearly with decomposition enthusiasm, and error propagation compounds multiplicatively.
8. **Conversational rewriting collapses history into one string.** When a turn depends on a previously *retrieved* passage or a tool output, no standalone rewrite can carry that state; benchmarks (CAsT lineage) predate tool-using agents entirely.
9. **Multi-query's evidence deficit.** The most widely deployed technique (multi-query + RRF) has the weakest evidence: negative in ARAGOG, drift-prone per its own case study (2402.03367), redundant per DMQR-RAG. Equal-weight RRF is provably indifferent to variant quality.
10. **Pipeline composition is untested.** Real stacks chain routing → rewriting → expansion → decomposition → fusion. Interactions (e.g., HyDE applied to a decomposed sub-query, or routing decisions made on rewritten rather than raw queries) are essentially unstudied; each paper evaluates its module in isolation. No paper found in this pass evaluates the *joint* transformation pipeline as a system.
11. **Latency/cost accounting is absent.** Nearly every technique adds ≥1 LLM call per query (expansion, rewriting, decomposition each add more). Few papers report end-to-end latency; the routing literature (2604.03455's 28% token savings) is the exception, not the rule.
12. **Domain knowledge gap in rewriters.** General-purpose rewriters lack specialist vocabulary (motivation of the withdrawn 2507.00477); RL and SFT rewriters trained on open-domain QA transfer poorly to professional corpora (consistent with RL-QR's mixed lexical-retriever results; flagged as partially uncertain).

**Disagreements worth noting explicitly**:
- ARAGOG says multi-query underperforms; RAG-Fusion/DMQR-RAG report gains — plausibly reconciled by query-variant quality control, but the contradiction is unresolved in the literature.
- BRIGHT says CoT query expansion adds up to +12.2 nDCG; the 2026 direct-corpus-interaction line argues query-side fixes cannot overcome the interface — these are competing bets on where the bottleneck is.
- RAGRouter-Bench baselines (lexical features win) sit awkwardly against the semantic-router industry pattern (embedding features) — likely task-definition differences (complexity routing vs intent routing), but nobody has unified them.

---

## Open problems (seeds for a next-generation framework)

1. **Intent as a first-class, persistent object.** Every current technique transforms *strings*. There is no shared, inspectable representation of the user's information need (entities, constraints, ambiguity set, evidence requirements, budget) that survives across rewrites, sub-queries, turns, and tool calls — and against which any transformation can be *verified* before execution. The Song & Zheng lifecycle names "intent recognition" as stage one but no system reifies it.
2. **When NOT to transform.** No published method decides per-query whether expansion/rewriting will help or hurt (the HyDE knowledge paradox). A calibrated "transformation gate" — estimating the model's knowledge coverage of the query topic and the retriever's likely failure mode — is unbuilt. Routing (Adaptive-RAG) decides *how much retrieval*, never *which transformation*.
3. **Process-level reward for query operations.** End-task RL (Search-R1, s3) gives one bit per episode; the survey literature explicitly calls for process reward models over transformation steps. What is the per-step supervision signal for "this rewrite preserved intent" or "this decomposition is complete and minimal"? Nothing credible exists.
4. **Transformation under a budget.** Extend the bandit view (2510.18633) from sub-query selection to the *whole* transformation space: given a token/latency budget, choose among {no-op, rewrite, expand, decompose×k, multi-query×n, clarify} as a sequential decision problem with corpus- and engine-conditioned value estimates.
5. **Engine/corpus drift robustness for learned rewriters.** RL rewriters are engine-specific by construction. Needed: continual/self-supervised adaptation (RL-QR's index-aligned synthetic queries hint at a mechanism) plus drift detection that flags when a rewriting policy has gone stale.
6. **Clarify-vs-diversify-vs-answer as a decision policy.** ASQA-style coverage, mixed-initiative clarification, and multi-query diversification are three responses to the same underlying ambiguity; no framework chooses among them based on estimated interpretation entropy, user cost of a clarifying turn, and corpus support per interpretation.
7. **Query transformation for non-QA needs.** Nearly all training signals (EM/F1, GBR) assume factoid-style answers. Agent memory lookups, code-context retrieval, exploratory search, and multi-document synthesis have no equivalent of Gain-Beyond-RAG. Defining verifiable rewards for these is open.
8. **Rethinking the query as an interaction program.** If 2605.05242 is right that the top-k interface is the bottleneck, the successor abstraction is a *retrieval program* — a typed plan mixing semantic search, exact match, metadata filters (self-query), local browsing, and verification steps — with the "query understanding" module compiling intent into that program. Today's techniques (HyDE, decomposition, self-query, routing) become instructions in that language rather than competing pipelines; nobody has built or benchmarked the compiler.

---

## Bibliography

Peer-reviewed / venue-accepted:

- HyDE: Precise Zero-Shot Dense Retrieval without Relevance Labels — Gao et al. — arXiv:2212.10496 (2022) — https://arxiv.org/abs/2212.10496
- Interleaving Retrieval with Chain-of-Thought Reasoning (IRCoT) — Trivedi et al. — arXiv:2212.10509 (2022) — https://arxiv.org/abs/2212.10509
- Least-to-Most Prompting — Zhou et al. — arXiv:2205.10625 — ICLR 2023 — https://arxiv.org/abs/2205.10625
- Query Rewriting for Retrieval-Augmented LLMs (Rewrite-Retrieve-Read) — Ma et al. — arXiv:2305.14283 (2023) — https://arxiv.org/abs/2305.14283 — code: https://github.com/xbmxb/RAG-query-rewriting
- Query2doc: Query Expansion with LLMs — Wang, Yang, Wei — arXiv:2303.07678 — EMNLP 2023 — https://arxiv.org/abs/2303.07678
- Take a Step Back: Evoking Reasoning via Abstraction — Zheng et al. (Google DeepMind) — arXiv:2310.06117 (2023) — https://arxiv.org/abs/2310.06117
- ASQA: Factoid Questions Meet Long-Form Answers — Stelmakh et al. — arXiv:2204.06092 (2022) — https://arxiv.org/abs/2204.06092
- Adaptive-RAG — Jeong et al. — arXiv:2403.14403 — NAACL 2024 — https://arxiv.org/abs/2403.14403
- RQ-RAG: Learning to Refine Queries for RAG — Chan et al. — arXiv:2404.00610 — COLM 2024 — https://arxiv.org/abs/2404.00610 — code: https://github.com/chanchimin/RQ-RAG
- GenQREnsemble — Dhole & Agichtein — arXiv:2404.03746 — ECIR 2024 — https://arxiv.org/abs/2404.03746
- BRIGHT benchmark — Su et al. — arXiv:2407.12883 — ICLR 2025 — https://arxiv.org/abs/2407.12883 — code: https://github.com/xlang-ai/BRIGHT
- DeepRetrieval — arXiv:2503.00223 — COLM 2025 — https://arxiv.org/abs/2503.00223 — code: https://github.com/pat-jj/DeepRetrieval
- s3: You Don't Need That Much Data to Train a Search Agent via RL — arXiv:2505.14146 — EMNLP 2025 — https://arxiv.org/abs/2505.14146 — https://aclanthology.org/2025.emnlp-main.1095/
- Search-R1 — Jin et al. — arXiv:2503.09516 (2025) — https://arxiv.org/abs/2503.09516 — code: https://github.com/PeterGriffinJin/Search-R1
- Rewriting Conversational Utterances with Instructed LLMs — Galimzhanova et al. — arXiv:2410.07797 (IEEE/WIC 2023) — https://arxiv.org/abs/2410.07797
- A Survey of Conversational Search — Mo et al. — arXiv:2410.15576 — ACM TOIS — https://arxiv.org/abs/2410.15576 / https://dl.acm.org/doi/10.1145/3759453
- Question Decomposition for RAG — ACL 2025 SRW — https://aclanthology.org/2025.acl-srw.32.pdf

Preprints (arXiv, not yet known to be peer-reviewed):

- RAG-Fusion: A New Take on Retrieval-Augmented Generation — Rackauckas — arXiv:2402.03367 (2024) — https://arxiv.org/abs/2402.03367 — original implementation: https://github.com/Raudaschl/rag-fusion
- ARAGOG: Advanced RAG Output Grading — Eibich et al. — arXiv:2404.01037 (2024) — https://arxiv.org/abs/2404.01037
- DMQR-RAG: Diverse Multi-Query Rewriting — Li et al. — arXiv:2411.13154 (2024) — https://arxiv.org/abs/2411.13154
- A Survey of Query Optimization in Large Language Models — Song & Zheng — arXiv:2412.17558 (2024; v3 2026) — https://arxiv.org/abs/2412.17558
- R1-Searcher — arXiv:2503.05592 (2025) — https://arxiv.org/abs/2503.05592
- RL-QR: Annotation-Free RL Query Rewriting via Verifiable Search Reward — Cha et al. — arXiv:2507.23242 (2025) — https://arxiv.org/abs/2507.23242
- Query Decomposition for RAG: Balancing Exploration-Exploitation — Petcu et al. — arXiv:2510.18633 (2025) — https://arxiv.org/abs/2510.18633
- Reasoning RAG via System 1 or System 2 (survey) — Liang et al. — arXiv:2506.10408 (2025) — https://arxiv.org/abs/2506.10408
- A Comprehensive Survey on RL-based Agentic Search — Lin et al. — arXiv:2510.16724 (2025) — https://arxiv.org/abs/2510.16724
- Doing More with Less: Routing Strategies survey — arXiv:2502.00409 (2025) — https://arxiv.org/abs/2502.00409
- MARAG-R1: RL multi-tool agentic retrieval — arXiv:2510.27569 (2025) — https://arxiv.org/abs/2510.27569
- MRMR: multidisciplinary reasoning-intensive multimodal retrieval benchmark — arXiv:2510.09510 (2025) — https://arxiv.org/abs/2510.09510
- InsertRank: LLM reranking over BM25 scores — arXiv:2506.14086 (2025) — https://arxiv.org/abs/2506.14086
- HawkBench: stratified information-seeking resilience — arXiv:2502.13465 (2025) — https://arxiv.org/abs/2502.13465
- Query Optimization for Parametric Knowledge Refinement — arXiv:2411.07820 (2024) — https://arxiv.org/abs/2411.07820
- Mixed-initiative Query Rewriting in Conversational Passage Retrieval — arXiv:2307.08803 (2023) — https://arxiv.org/abs/2307.08803
- Read the Docs Before Rewriting (continual pre-training for rewriters) — arXiv:2507.00477 (2025) — **withdrawn Nov 2025**; cited only for its problem statement — https://arxiv.org/abs/2507.00477

2026 preprints:

- RAGRouter-Bench: dataset & benchmark for adaptive RAG routing — arXiv:2602.00296 (2026) — https://arxiv.org/abs/2602.00296
- Lightweight Query Routing for Adaptive RAG (RAGRouter-Bench baselines) — Bansal & Agarwal — arXiv:2604.03455 (2026) — https://arxiv.org/abs/2604.03455
- Rethinking Reasoning-Intensive Retrieval (BRIGHT-Pro, RTriever) — Zhao et al. — arXiv:2605.04018 (2026) — https://arxiv.org/abs/2605.04018
- Beyond Semantic Similarity: Direct Corpus Interaction for Agentic Search — Li et al. — arXiv:2605.05242 (2026) — https://arxiv.org/abs/2605.05242
- Adaptive Query Routing: Tier-Based Hybrid Retrieval (finance/legal/medical) — arXiv:2604.14222 (2026) — https://arxiv.org/abs/2604.14222
- Natural Language Query to Configuration for Retrieval Agents — arXiv:2605.27361 (2026) — https://arxiv.org/abs/2605.27361
- Beyond Stochastic Exploration: training data value for agentic search — arXiv:2604.08124 (2026) — https://arxiv.org/abs/2604.08124

Software / practitioner sources:

- semantic-router — aurelio-labs — https://github.com/aurelio-labs/semantic-router — embedding-space intent routing, ~3.8k stars (fetched Aug 2026)
- rag-fusion — Raudaschl — https://github.com/Raudaschl/rag-fusion — multi-query + RRF reference implementation with NFCorpus/BEIR eval harness
- Practitioner analyses of HyDE limitations: Zilliz Learn (https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings), Behitek "Inverted HyDE" (https://behitek.com/blog/inverted-hyde/), Haystack docs (https://docs.haystack.deepset.ai/docs/hypothetical-document-embeddings-hyde)
- LangChain self-querying retriever pattern — docs page relocated during this pass (python.langchain.com → docs.langchain.com redirect); cited as the canonical structured-filter-extraction pattern, details uncertain as of fetch date.
