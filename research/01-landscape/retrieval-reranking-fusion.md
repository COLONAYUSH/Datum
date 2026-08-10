# Retrieval, Reranking, Fusion & Context Selection — Research Landscape (as of August 2026)

## Scope

This document maps the middle of the RAG pipeline: everything between "a query exists" and
"tokens are placed in the LLM's context window." Concretely:

- **Fusion** of heterogeneous retrievers (dense + sparse + others): RRF, weighted/score-based,
  learned fusion, and their calibration problems.
- **Reranking**: cross-encoders (monoT5, BGE-reranker, mxbai-rerank, Cohere Rerank),
  LLM prompting rerankers (RankGPT, RankVicuna, RankZephyr; pointwise vs pairwise vs
  listwise vs setwise), late-interaction rerankers (ColBERT family), and the 2025–2026 wave of
  *reasoning* rerankers trained with test-time compute and RL (Rank1, Rank-R1, REARANK, Rank-K).
- **Diversity & redundancy control**: MMR and successors.
- **Context selection & ordering**: lost-in-the-middle, positional bias, retrieval depth (k),
  sufficient context, context rot, hard negatives.
- **Context compression/pruning**: RECOMP, LongLLMLingua, LLMLingua-2, xRAG, Provence/XProvence,
  attention-guided pruning.
- **Score calibration, thresholding, and answer/abstain decisions**; adaptive/cascading retrieval
  (when to retrieve, how much to retrieve, when to stop).

Emphasis is on failure modes, critiques, and open problems, per the goal of motivating a
next-generation RAG framework. Citation status is flagged: [PR] peer-reviewed / heavily cited,
[P] preprint, [V] vendor/industry technical report or blog.

---

## Lineage & chronological development

**Pre-neural foundations (1998–2009).**
- *MMR* — Carbonell & Goldstein, SIGIR 1998 [PR]. Greedy selection maximizing
  λ·relevance − (1−λ)·max-similarity-to-already-selected. Still the default diversity mechanism in
  LangChain/LlamaIndex vector-store retrievers in 2026, essentially unchanged in 28 years.
- *Reciprocal Rank Fusion (RRF)* — Cormack, Clarke & Buettcher, SIGIR 2009 [PR]. Rank-based fusion
  `score(d) = Σ 1/(k + rank_i(d))`, k≈60. Its virtue is that it needs no score calibration across
  heterogeneous retrievers; its vice is that it discards score magnitude entirely (see Failure modes).

**First neural wave (2019–2022).**
- *monoT5* — Nogueira et al., arXiv:2003.06713, 2020 [PR]. Seq2seq (T5) pointwise reranker
  generating "true"/"false" relevance tokens; beat BERT-classification rerankers especially in
  low-data regimes; the workhorse cross-encoder recipe for years.
- *ColBERT* — Khattab & Zaharia, arXiv:2004.12832, SIGIR 2020 [PR]. Late interaction: per-token
  embeddings + MaxSim, giving BERT-level effectiveness roughly two orders of magnitude faster than
  a full cross-encoder because document representations are precomputed. ColBERTv2 (Santhanam et
  al., 2021/2022 [PR]) added residual compression and is still widely used as a reranking stage in
  cascades in 2026.
- Learned sparse (SPLADE, Formal et al., SIGIR 2021 [PR]) established the modern "hybrid" triad:
  BM25 / learned-sparse / dense, fused by RRF or weighted sums.

**LLM-reranking wave (2023).**
- *RankGPT* — Sun et al., "Is ChatGPT Good at Search?", arXiv:2304.09542, EMNLP 2023 [PR].
  Canonical zero-shot *listwise* prompt with sliding windows over candidates; showed GPT-4-class
  models beat supervised rerankers zero-shot and that the capability distills into small models.
- *RankVicuna* — Pradeep et al., arXiv:2309.15088, 2023 [P] and *RankZephyr* — Pradeep et al.,
  arXiv:2312.02724, 2023 [P]: open-weight 7B listwise rerankers distilled from RankGPT-style
  supervision; RankZephyr ≈ matches GPT-4 RankGPT on TREC DL (≈72.4 vs 73.1 average in later
  empirical comparisons). *Rank-without-GPT* (Zhang et al., arXiv:2312.02969 [PR]) showed
  GPT-independent listwise training data works.
- *Setwise ranking* — Zhuang et al., arXiv:2310.09497, SIGIR 2024 [PR]. Compares small sets per
  call ("which of these is most relevant?") to interpolate the effectiveness/efficiency trade-off
  between pointwise and pairwise/listwise.
- *Lost in the Middle* — Liu et al., arXiv:2307.03172, TACL 2024 [PR]. U-shaped position curve:
  accuracy is highest when the answer-bearing passage is at the beginning or end of context and
  degrades in the middle — the founding result of "context ordering matters."
- *FLARE* — Jiang et al., arXiv:2305.06983, EMNLP 2023 [PR]. Active retrieval during generation,
  triggered when next-sentence token probabilities fall below a threshold — the ancestor of
  2025–2026 adaptive-retrieval gating.
- *RECOMP* — Xu, Shi & Choi, arXiv:2310.04408, ICLR 2024 [PR]. Extractive + abstractive
  compressors ahead of the LLM; compression to as low as 6% of tokens with minimal loss; can emit
  an empty string (selective augmentation) — an early answer/abstain signal at the context level.
- *LongLLMLingua* — Jiang et al., arXiv:2310.06839, ACL 2024 [PR]. Question-aware coarse-to-fine
  prompt compression + reordering; reported up to 21.4% quality gains with ~4x fewer tokens,
  explicitly marketed as a lost-in-the-middle mitigation.

**Consolidation and skepticism (2024).**
- *LLMLingua-2* — Pan et al., arXiv:2403.12968, ACL 2024 Findings [PR]. Reframes compression as
  token classification (XLM-RoBERTa encoder) trained by GPT-4 data distillation; task-agnostic,
  3–6x faster than LLM-perplexity-based compressors, better OOD behavior.
- *xRAG* — Cheng et al., arXiv:2405.13792, NeurIPS 2024 [PR]. "Extreme" compression: reuse the
  retriever's document embedding as a single soft token via a trained modality bridge (retriever
  and LLM frozen); 3.53x FLOP reduction. The strongest statement of "context as a modality,
  not text."
- *The Power of Noise* — Cuconasu et al., arXiv:2401.14887, SIGIR 2024 [PR]. Claimed random
  (unrelated) documents in the prompt can *improve* QA accuracy while related-but-non-answering
  "distracting" documents hurt — widely cited, and now substantially contested (see 2026).
- *BRIGHT* — Su et al., arXiv:2407.12883, 2024 [PR]. First reasoning-intensive retrieval benchmark
  (1,384 real queries — current v4 count; the Jul 2024 v1 abstract said 1,398 — from economics, math,
  code, etc., across 12 datasets); leading dense retrievers and rerankers
  collapse on it, motivating the reasoning-reranker wave.
- *Long-Context LLMs Meet RAG* — Jin et al., arXiv:2410.05983, 2024 [P]. Output quality rises then
  *falls* as retrieved-passage count grows; identifies retrieved **hard negatives** as the key
  contributor; shows *retrieval reordering* (put best passages at the edges) as a training-free fix
  plus RAG-specific fine-tuning.
- *Sufficient Context* — Joren et al. (Google), arXiv:2411.06037, ICLR 2025 [PR]. Introduces an
  autorater for "does the retrieved context suffice to answer?"; finds large models (Gemini 1.5
  Pro, GPT-4o, Claude 3.5) answer *incorrectly instead of abstaining* when context is insufficient,
  while small models hallucinate or abstain even with sufficient context; RAG can *reduce*
  abstention discipline. Their selective-generation intervention improves correct-answer fraction
  by 2–10%.

**Reasoning rerankers and context-budget science (2025).**
- *Rank1* — Weller et al., arXiv:2502.18418, CoLM 2025 [PR]. First reranker trained on distilled
  R1 reasoning traces (600k+ from MS MARCO); pointwise with test-time compute; SOTA on
  reasoning/instruction-following retrieval benchmarks; explainable chains.
- *Rank-R1* — Zhuang et al., arXiv:2503.06034, 2025 [P]. GRPO-style RL on a setwise reranker using
  only relevance labels (no reasoning supervision); matches SFT with ~18% of the data; large
  out-of-domain (BRIGHT) gains at 14B.
- *REARANK* — arXiv:2505.20046, EMNLP 2025 [PR]. Listwise reasoning reranking agent trained with
  RL + data augmentation from only 179 annotated samples; REARANK-7B ≈ GPT-4 in-domain and on
  BRIGHT.
- *Rank-K* — arXiv:2505.14432, 2025 [P]. Listwise test-time-reasoning reranker.
  *InsertRank* — arXiv:2506.14086, 2025 [P]: listwise rerankers reasoning over injected BM25
  scores. *R1-Ranker* — arXiv:2506.21638, 2025 [P]: incremental-elimination RL ranking.
- *Provence* — Chirkova et al. (Naver Labs), arXiv:2501.16214, ICLR 2025 [PR]. Context pruning as
  sequence labeling, *unified with the reranker* (one forward pass does both), trained on diverse
  data with dynamic pruning ratios; negligible-to-zero quality drop at high compression and
  sometimes gains (noise filtering, e.g., PopQA).
- *Context Rot* — Hong, Troynikov & Huber (Chroma), technical report, July 2025 [V]. 18 models
  (GPT-4.1, Claude 4, Gemini 2.5, Qwen3): non-uniform degradation with input length, sometimes
  30–50% before the advertised limit; lower needle–question similarity degrades faster; a single
  distractor measurably hurts; *coherent* haystacks hurt more than shuffled ones; Claude models
  abstain more, GPT models hallucinate more under distractors.
- *AttentionRAG* — arXiv:2503.10720, 2025 [P]. Attention-guided context pruning.
- *TARG* — "Retrieval as a Decision: Training-Free Adaptive Gating," arXiv:2511.09803, 2025 [P].
  Decide *whether* to retrieve from a short no-context draft's uncertainty (mean token entropy);
  on TriviaQA skips ~⅓ of retrievals at near always-RAG accuracy; near-always-retrieve on NQ/MS
  MARCO where closed-book accuracy is low.

**2026 developments.**
- *XProvence* — arXiv:2601.18886, 2026 [P]. Zero-cost multilingual context pruning inside the
  reranker.
- *The Powerless Noise* — Mazuryk et al., arXiv:2607.03615, 2026 [P]. Re-runs Power-of-Noise under
  modern RAG practice (better prompts, models, decoding); the random-noise benefit weakens or
  vanishes; attributes much of the original effect to truncation artifacts and malformed outputs.
  A caution for the whole "noise helps" literature.
- Positional-bias-in-listwise-reranking cluster: arXiv:2604.03642 (LLM listwise rerankers
  systematically under-promote passages late in the prompt) [P]; *Learning from Emptiness*
  (arXiv:2604.10150) — content-agnostic probability calibration to de-bias listwise rerankers [P];
  *One Pass, Any Order* (arXiv:2604.27599) — position-invariant listwise reranking [P];
  *Ranked by Position* (arXiv:2607.24869) — order sensitivity is an exploitable attack surface:
  adversaries can promote items into top-k purely by reordering candidates [P].
- Reproduction studies: *Lost in the Evidence?* (arXiv:2605.27105) reproduces
  position/context-size effects in RAG [P]; *Lost at the End* (arXiv:2606.16494) finds *primacy*
  bias in multimodal RAG QA — the bias profile is model- and modality-dependent, not universally
  U-shaped [P]; *Position Bias Correction is Insufficient for One-Pass Attention Sorting*
  (arXiv:2606.27793) [P].
- Calibration/budgeting: *Know Before You Fetch* — calibrated retrieval-budget allocation
  (arXiv:2606.29959) [P]; *When to Retrieve During Reasoning* (arXiv:2604.26649) — adaptive
  retrieval for large reasoning models [P]; *Uncertainty-Aware Hybrid Retrieval for Long-Document
  RAG* (arXiv:2606.13550) [P].
- Late interaction is institutionalizing: first *LIR workshop* on late interaction and
  multi-vector retrieval at ECIR 2026 (arXiv:2511.00444) [P]; MUVERA-style single-vector proxies +
  exact MaxSim rerank push ColBERT-quality retrieval to sub-millisecond query times vs ~73 ms
  PLAID baselines (reported in 2026 multi-vector systems work, e.g., arXiv:2602.12510) [P].

---

## State of the art — mid-2026 snapshot

The production-standard pipeline is a **cascade**: hybrid first stage (BM25 + dense, often +
learned sparse) fused by RRF or a tuned weighted sum → cross-encoder or late-interaction reranker
over top-50/100 → optional LLM/reasoning reranker over top-10/20 for hard queries → context
pruning (Provence-style, increasingly fused into the reranker) → ordering that respects position
bias (best evidence at the edges) → generation, ideally guarded by a sufficiency/abstention check.

- **Rerankers**: managed APIs (Cohere Rerank 3.5, and by 2026 Rerank v4 Pro/Fast; zerank-2 leads
  the Agentset ELO leaderboard at ~1638 vs Cohere v4 Pro ~1629 [V]) vs open weights
  (BGE-reranker-v2-m3, Apache-2.0, 100+ languages; mxbai-rerank-v2 0.5B/1.5B Qwen2.5-based,
  BEIR ~57.5 for large [V]). Cross-encoders remain the accuracy-per-dollar sweet spot;
  LLM listwise rerankers are used selectively due to latency and instability.
- **Reasoning rerankers** (Rank1, Rank-R1, REARANK, Rank-K) are SOTA on reasoning-intensive
  retrieval (BRIGHT) and instruction-following retrieval, at 10–100x the inference cost of a
  cross-encoder; adoption is mostly offline/high-value queries.
- **Context budget**: the empirical consensus is that RAG quality in k is *non-monotonic* — rises
  then falls, with inflection typically at k≈5–10 for QA (arXiv:2411.19463 and domain benchmarks,
  e.g., chemistry RAG best at k=3–5) — driven by hard negatives and attention dilution, not token
  limits. Google's sufficient-context line and Chroma's context-rot line converge on the same
  prescription from opposite directions: *feed the model less, but the right less, and know when
  it isn't enough*.
- **Compression**: pruning-in-the-reranker (Provence/XProvence) has effectively won over separate
  compressor models for extractive pruning (zero marginal cost); LLMLingua-2 remains the default
  task-agnostic token-level compressor; soft/embedding compression (xRAG-style) is promising but
  not production-mainstream.
- **Abstention**: shipped systems increasingly include a sufficiency/selective-generation gate
  (post-ICLR-2025 Google work) and uncertainty-gated retrieval (TARG-style), but calibrated
  end-to-end answer/abstain policies remain rare.

---

## Thematic deep-dives

### 1. Hybrid fusion: RRF, weighted, learned

- **RRF** (Cormack et al. 2009) dominates because it is calibration-free and ~3 lines of code;
  OpenSearch/Elasticsearch/Vespa/Weaviate all ship it [V]. Empirically hybrid-RRF consistently
  beats either retriever alone (e.g., a FIRE 2025 system reports +38% MAP@10 over BM25 via RRF;
  ceur-ws Vol-4173 [P]).
- **Critique**: rank-only fusion throws away score magnitude. A 2025–2026 benchmark thread
  (digitalapplied hybrid-search reference [V]) reports RRF ~3.86% *worse* NDCG@10 than
  score-based (normalized weighted) fusion across six datasets. So the field's default is known
  to be leaving accuracy on the table in exchange for robustness. Score-based fusion needs
  per-collection normalization (min-max/L2/z-score) that drifts as corpora and models change.
- **Learned/alternative fusion**: projection fusion with diversity reranking (arXiv:2604.13728
  [P]) and uncertainty-aware hybrid retrieval (arXiv:2606.13550 [P]) treat fusion weights as
  query-dependent quantities; convincing but not yet standardized. Notably absent from the
  literature: a principled probabilistic account of *what fused scores mean*, which blocks
  downstream thresholding (see §7).

### 2. Cross-encoder rerankers

- Lineage: monoBERT → monoT5 (arXiv:2003.06713) → modern multilingual cross-encoders
  (BGE-reranker-v2-m3; mxbai-rerank-v2; Cohere Rerank 3.5 at ~600 ms typical latency [V];
  zerank-2). Agentset maintains a pairwise-ELO leaderboard [V]; treat vendor numbers with care —
  most public comparisons of managed rerankers are marketing-adjacent.
- **Why they pay off**: full query–document cross-attention catches negation, qualifiers, and
  "X but not Y" that bi-encoders miss (ZeroEntropy and practitioner analyses [V]); they demote
  lexical near-misses the first stage over-ranked.
- **Structural limits**: (i) *recall ceiling* — a reranker can only reorder what stage one found;
  if the answer isn't in top-50/100, you pay latency to reorder garbage. (ii) Pointwise scores are
  **uncalibrated across queries**: a 0.7 for one query is not a 0.7 for another, so absolute
  thresholds for drop/abstain decisions are unreliable (motivates §7). (iii) Trained mostly on
  MS MARCO-style semantic relevance, they underperform on reasoning-dependent relevance (BRIGHT)
  and on instruction-conditioned relevance ("only official docs, exclude forums").

### 3. LLM rerankers: pointwise / pairwise / listwise / setwise

- **Taxonomy & trade-offs**: pointwise (score each doc; cheap, parallel, uncalibrated), pairwise
  (O(n²) or sorting-network comparisons; accurate, expensive), listwise (RankGPT sliding windows;
  best quality per token but order-sensitive), setwise (Zhuang et al., SIGIR 2024; the efficiency
  compromise). Empirical syntheses ("How Good are LLM-based Rerankers?", Findings of EMNLP 2025
  [PR]) find listwise > pointwise/pairwise in effectiveness, with setwise lagging pairwise in
  quality but far cheaper.
- **Positional bias & instability (a 2026 subfield of its own)**: listwise LLM rerankers
  systematically fail to promote passages that appear late in the prompt (arXiv:2604.03642);
  output rankings change under input permutation, which *Ranked by Position* (arXiv:2607.24869)
  shows is an exploitable attack surface — reordering candidates alone can promote an attacker's
  item into the top-k. Mitigations: permutation self-consistency (multiple shuffles + aggregate),
  content-agnostic prior calibration (arXiv:2604.10150), position-invariant one-pass designs
  (arXiv:2604.27599), RoToR order-invariant inputs (arXiv:2502.08662). All add cost; none is a
  full fix — arXiv:2606.27793 argues position-bias *correction* is insufficient for one-pass
  attention sorting.
- Sliding windows themselves are a patch for context limits and inherit lost-in-the-middle inside
  each window; repeated passes multiply latency (arXiv:2511.07555 works on making pairwise
  real-time instead).

### 4. Reasoning rerankers (2025–2026)

- Rank1 (distilled reasoning traces, pointwise), Rank-R1 (RL/GRPO setwise, label-only reward),
  REARANK (RL listwise agent, 179 labeled samples), Rank-K (test-time reasoning listwise),
  R1-Ranker, InsertRank (reasoning over BM25 scores). Common findings: reasoning helps most on
  BRIGHT-style reasoning-intensive relevance and OOD; RL with outcome rewards is dramatically more
  label-efficient than SFT; chains provide explainability.
- **Critiques**: token cost per candidate is 1–3 orders of magnitude above cross-encoders (Rank1
  generates a full reasoning trace per query–passage pair); latency is incompatible with
  interactive search unless cascaded; reasoning traces are plausibility-selected, not verified —
  no work yet shows the *chains* are faithful; evaluation concentrates on BRIGHT/TREC-DL, and
  gains on ordinary web/enterprise relevance are modest. Uncertain: whether RL rerankers
  hill-climb BRIGHT idiosyncrasies (limited benchmark diversity acknowledged even in Rank-R1's
  own scope).

### 5. Late interaction and cascading retrieval

- ColBERT/ColBERTv2 as reranker or retriever; PLAID indexing; 2024–2026 revival via RAGatouille,
  PyLate, Jina/answerai small ColBERTs, and multimodal ColPali/ColQwen. MUVERA-style fixed-dim
  proxies for MaxSim enable single-vector ANN speeds with exact late-interaction rerank on top-K
  (sub-ms vs ~73 ms PLAID in 2026 reports, arXiv:2602.12510 [P]). First dedicated venue: LIR @
  ECIR 2026 (arXiv:2511.00444).
- Cascades are the organizing pattern: cheap-high-recall → mid-cost rerank → expensive
  rerank on a shrinking candidate set. Best practice ties stages together (fine-tune the reranker
  on hard negatives mined *from the first stage it will sit behind*). **Critique**: cascade stages
  are trained and evaluated independently; errors are not propagated, and no stage knows the
  downstream generator's needs. There is no joint objective from query to final answer — each
  stage optimizes proxy relevance.

### 6. Diversity, MMR, and redundancy

- MMR (1998) is still the default; its λ is hand-set, its similarity penalty is embedding-cosine,
  and it is oblivious to *why* diversity is needed (multi-hop coverage vs de-duplication).
  Projection-fusion + diversity reranking (arXiv:2604.13728) and cluster-based adaptive retrieval
  (arXiv:2511.14769 — dynamic context selection via clustering) are the current refresh attempts.
- **Critique**: for multi-hop questions, what's needed is *complementarity* (evidence that jointly
  entails the answer), not geometric diversity; MMR can evict the second hop because it is
  "too similar" to the first. No widely adopted selector optimizes set-level answerability
  (sufficiency of the *set*) rather than summed per-passage relevance minus redundancy.

### 7. Context ordering, retrieval depth, and how much context is optimal

- **Position effects**: Liu et al.'s U-curve (TACL 2024) → training-free *retrieval reordering*
  (best docs at beginning and end; Jin et al. arXiv:2410.05983) is a cheap, reliable win.
  But 2026 reproductions complicate the picture: bias profiles differ by model and modality
  (primacy-only in multimodal RAG, arXiv:2606.16494), and correction methods undershoot
  (arXiv:2606.27793). Chroma's context-rot report adds the counterintuitive result that
  *coherent* filler harms retrieval-in-context more than shuffled filler — structure itself
  steers attention.
- **Retrieval depth (k)**: performance is non-monotonic in k, with typical optima at k∈[3,10] for
  QA (arXiv:2411.19463; chemistry RAG benchmark arXiv:2505.07671); harder multi-evidence tasks
  want larger k, easy tasks are hurt by it. Mechanisms: hard negatives (arXiv:2410.05983),
  distractor interference and attention dilution (Chroma [V]), context interference between
  passages. Practical k is also bounded by latency/cost.
- **Sufficient context (Google/ICLR 2025)**: separates retrieval failure from utilization failure;
  key numbers — strong models answer wrongly rather than abstain under insufficient context, and
  even with *sufficient* context models err in a nontrivial fraction of cases; selective
  generation lifts correct-among-answered by 2–10%. Implication: context selection should target
  *set sufficiency*, a property no ranker currently scores.
- **Noise controversy**: Power of Noise (SIGIR 2024) vs Powerless Noise (arXiv:2607.03615, 2026):
  the random-documents-help effect largely disappears under modern prompting/decoding; the robust
  residual findings are (a) *distracting* (related-non-answering) documents reliably hurt, and
  (b) RAG evaluations are alarmingly sensitive to prompt/truncation minutiae. Treat "noise helps"
  as unconfirmed.
- Also relevant: "Worse than Zero-shot?" (arXiv:2502.16101) — misleading retrievals can push RAG
  *below* the no-retrieval baseline on fact-checking, the sharpest statement that retrieval is not
  monotonically beneficial.

### 8. Context compression & pruning

- **Token/sentence-level extractive**: RECOMP (ICLR 2024), LongLLMLingua (ACL 2024; ~4x fewer
  tokens, up to +21.4%), LLMLingua-2 (ACL 2024 Findings; token classification, 3–6x faster,
  task-agnostic). Provence (ICLR 2025) collapses pruning into the reranker (sequence labeling,
  dynamic ratio) — effectively free at inference and robust across domains; XProvence
  (arXiv:2601.18886) extends multilingually; NAVER reports Provence beats LLMLingua-class methods
  at equal or higher compression [V/P]. AttentionRAG (arXiv:2503.10720) uses generator attention
  to guide pruning.
- **Soft/embedding compression**: xRAG (NeurIPS 2024) — one soft token per document via modality
  bridge; density-aware semi-dynamic soft compression (arXiv:2603.25926, 2026). Pros: extreme
  ratios, cheap. Cons: opaque (no auditable text), generator-coupled (bridge must be retrained per
  LLM), and faithfulness/attribution are essentially unverifiable — a serious problem for any
  application requiring citations.
- **Critiques of compression generally**: abstractive compressors hallucinate during compression;
  compression is query-conditioned so caches don't amortize across queries; aggressive pruning
  interacts badly with multi-hop questions (evidence for later hops looks irrelevant at pruning
  time); and every compressor is another model trained on proxy labels of "importance" with no
  guarantee aligned to the generator's actual needs.

### 9. Calibration, thresholding, and answer/abstain

- **When to retrieve**: FLARE (2023, token-probability trigger) → RetrievalQA
  (arXiv:2402.16457, benchmark for adaptive RAG) → TARG (arXiv:2511.09803; training-free
  entropy gating, threshold calibrated on a small dev set) → adaptive retrieval inside reasoning
  chains (arXiv:2604.26649) and calibrated retrieval-budget allocation (arXiv:2606.29959).
- **When to answer**: sufficient-context autorater + selective generation (Google, ICLR 2025);
  confidence-threshold abstention (abstain when confidence < τ, τ tuned per abstention-rate
  target). Chroma's report shows model-family asymmetry (Claude abstains, GPT hallucinates under
  distractors) — abstention behavior is a *model property*, not just a pipeline property.
- **Critiques**: retriever and reranker scores are uncalibrated across queries and collections, so
  fixed thresholds silently rot; RRF destroys magnitudes so fused pipelines have no usable score
  at all; TARG-style gates depend on closed-book competence estimates that shift with every model
  upgrade; and almost all abstention work is single-turn QA — nothing principled exists for
  multi-turn agentic loops where the retrieve/answer decision recurs with evolving state.

---

## Comparison tables

### LLM reranking paradigms

| Paradigm | Calls / n candidates | Quality (empirical consensus) | Key failure modes |
|---|---|---|---|
| Pointwise (monoT5, cross-encoders, Rank1) | n (parallel) | Good; SOTA-per-dollar | Cross-query score incomparability; no inter-doc context |
| Pairwise (PRP-style) | O(n log n)–O(n²) | High | Cost; intransitivity; latency (arXiv:2511.07555 tries to fix) |
| Listwise (RankGPT, RankZephyr, REARANK) | n/window, sliding | Highest | Positional bias, permutation instability, adversarial reordering (2604.03642, 2607.24869) |
| Setwise (Zhuang et al., Rank-R1) | between point & pair | Slightly < pairwise | Set-composition sensitivity |
| Reasoning/RL (Rank1, Rank-R1, REARANK, Rank-K) | as base paradigm × trace length | SOTA on BRIGHT/instr. | 10–100x token cost; unverified chains; benchmark concentration |

### Context compression methods

| Method | Type | Mechanism | Cost at inference | Main critique |
|---|---|---|---|---|
| RECOMP (2310.04408) | extractive+abstractive | trained summarizers | extra model, autoregressive (slow) | abstractive hallucination risk |
| LongLLMLingua (2310.06839) | token pruning | perplexity + question-aware | extra LLM pass | cost; brittleness OOD |
| LLMLingua-2 (2403.12968) | token classification | distilled encoder | small encoder pass | task-agnostic ≠ query-optimal |
| Provence (2501.16214) / XProvence (2601.18886) | sentence pruning | fused into reranker | ~zero marginal | extractive only; multi-hop blind spots |
| xRAG (2405.13792) | soft compression | doc embedding → 1 token | ~zero | unauditable; per-LLM bridge; no attribution |
| AttentionRAG (2503.10720) | attention-guided pruning | generator attention signal | moderate | needs generator access |

### Fusion approaches

| Approach | Calibration needed | Uses score magnitude | Notes |
|---|---|---|---|
| RRF | none | no | robust default; ~3.9% NDCG@10 below tuned score fusion in one 6-dataset benchmark [V] |
| Weighted score (min-max/z-norm) | yes, per collection | yes | best quality when tuned; drifts silently |
| Learned / query-dependent (2604.13728, 2606.13550) | trained | yes | promising, non-standard; extra model |

---

## Failure modes & critiques (consolidated)

1. **No end-to-end objective.** Every stage (fusion, rerank, prune, order) optimizes proxy
   relevance; none optimizes answer correctness of the final generation. Cascade errors compound
   invisibly; reranker gains routinely fail to translate into end-task gains.
2. **Recall ceiling.** Rerankers cannot recover documents stage one missed; on
   reasoning-intensive queries (BRIGHT) first-stage recall itself collapses, so the expensive
   stages polish an empty set.
3. **Uncalibrated scores everywhere.** Cross-encoder scores incomparable across queries; RRF
   discards magnitudes; hence thresholding, deduplication across sources, and abstention are built
   on sand. (Directly measured: RRF vs score-fusion NDCG gap; TARG's need for per-dataset τ.)
4. **Listwise LLM rerankers are unstable and attackable.** Position bias (2604.03642), permutation
   sensitivity, and content-free rank manipulation (2607.24869) mean the highest-quality paradigm
   is also the least trustworthy in adversarial or high-stakes settings.
5. **Context is non-monotonic in k and poisoned by hard negatives.** Quality peaks at k≈5–10 and
   declines (2411.19463, 2410.05983); related-but-wrong passages are the worst input class
   (2401.14887's robust half; 2502.16101 shows retrieval can be worse than zero-shot).
6. **Long context does not substitute for selection.** Context rot [V]: degradation begins far
   below advertised limits, is distractor- and structure-sensitive, and model-idiosyncratic.
   "Just stuff the window" fails empirically as of 2026.
7. **Models don't know when they don't know the context is enough.** Sufficient-context results:
   frontier models answer confidently from insufficient context; RAG *reduces* abstention.
   Sufficiency is a set-level property no component currently scores at selection time.
8. **Compression trades auditability for tokens.** Soft compression (xRAG) breaks
   attribution/citation; abstractive compression can hallucinate; extractive pruning can sever
   multi-hop chains.
9. **Diversity is geometric, not epistemic.** MMR-style selection optimizes embedding-space
   spread, not evidence complementarity or coverage of required reasoning hops.
10. **Reproducibility fragility.** Power-of-Noise vs Powerless-Noise shows headline RAG findings
    can hinge on prompt truncation and decoding details; positional-bias profiles flip across
    models/modalities. The evidence base for many "best practices" is thinner than adoption
    suggests.
11. **Reasoning rerankers' economics.** Test-time-compute rerankers cost 1–3 orders of magnitude
    more per candidate; their chains are unverified rationales; benchmark coverage (BRIGHT,
    TREC-DL) is narrow.
12. **Static pipelines vs agentic use.** Nearly all of the above science is single-shot QA.
    Agentic systems re-retrieve iteratively with evolving intents; per-step calibration,
    budget allocation, and stop-conditions are largely unstudied (early: 2604.26649, 2606.29959).

---

## Open problems (seeds for a next-generation framework)

1. **Set-level sufficiency as the selection objective.** Replace "top-k by summed relevance" with
   selecting the *minimal document set whose joint content is sufficient* to answer — combining
   the sufficient-context autorater idea with combinatorial selection. Nothing today scores
   candidate *sets*; everything scores passages independently (MMR's redundancy term is the only,
   crude, set-level signal).
2. **Calibrated, comparable relevance scores.** A probabilistic semantics for retrieval/rerank
   scores (P(doc is useful for answering q)) that survives fusion, transfers across queries and
   collections, and supports principled thresholds, abstention, and cost-aware cascade routing.
   Would obsolete both RRF's magnitude-blindness and per-dataset τ tuning.
3. **End-to-end credit assignment through the cascade.** Train fusion weights, rerankers, pruners
   and ordering jointly against final-answer reward (the RL machinery from Rank-R1/REARANK exists;
   applying it to the *pipeline* rather than one stage does not, at scale).
4. **Order-invariant, attack-resistant listwise ranking.** Guarantee (not merely mitigate)
   permutation invariance in LLM rerankers; current fixes (2604.10150, 2604.27599) are partial and
   2606.27793 shows correction is insufficient. Security framing (2607.24869) makes this urgent
   for open-corpus RAG.
5. **Adaptive k and budget as a decision problem.** Choose retrieval depth, rerank depth, and
   compression ratio per query from calibrated difficulty/uncertainty estimates (extending TARG
   and 2606.29959), with explicit cost–risk trade-offs, instead of global constants.
6. **Compression with attribution guarantees.** Soft/one-token compression that remains auditable —
   e.g., invertible or citation-preserving compression — closing xRAG's faithfulness gap.
7. **Complementarity-aware diversity.** Selectors that model inter-document entailment/coverage
   (which hops does this passage unlock?) rather than cosine spread; especially for multi-hop
   where MMR actively harms.
8. **Model-aware context shaping.** Position bias, distractor sensitivity, and abstention style
   are model-specific (Chroma; 2606.16494). Context assembly (ordering, filler structure,
   density) should be conditioned on measured generator characteristics, not fixed heuristics.
9. **Abstention in the loop.** Extend answer/abstain from single-turn QA to iterative agentic
   retrieval: when to stop retrieving, when to answer, when to declare the corpus insufficient —
   with calibrated guarantees rather than prompt-level hopes.
10. **Evaluation hygiene.** The Powerless-Noise episode argues for standardized,
    truncation-controlled, decoding-controlled RAG evaluation protocols; without them, framework
    comparisons (including any new framework's claims) are unreliable.

---

## Bibliography

Foundations
1. Carbonell & Goldstein — "The Use of MMR, Diversity-Based Reranking..." — SIGIR 1998. [PR]
2. Cormack, Clarke & Buettcher — "Reciprocal Rank Fusion outperforms Condorcet..." — SIGIR 2009. [PR]
3. Nogueira et al. — "Document Ranking with a Pretrained Sequence-to-Sequence Model" (monoT5) — arXiv:2003.06713 — 2020. [PR]
4. Khattab & Zaharia — "ColBERT" — arXiv:2004.12832 — SIGIR 2020. [PR]
5. Formal et al. — "SPLADE" — SIGIR 2021. [PR] (cited from lineage; no arXiv ID verified here)

LLM rerankers
6. Sun et al. — "Is ChatGPT Good at Search?" (RankGPT) — arXiv:2304.09542 — EMNLP 2023. [PR]
7. Pradeep et al. — "RankVicuna" — arXiv:2309.15088 — 2023. [P]
8. Pradeep et al. — "RankZephyr" — arXiv:2312.02724 — 2023. [P]
9. Zhang et al. — "Rank-without-GPT" — arXiv:2312.02969 — ECIR 2025. [PR]
10. Zhuang et al. — "A Setwise Approach for Effective and Highly Efficient Zero-shot Ranking" — arXiv:2310.09497 — SIGIR 2024. [PR]
11. "How Good are LLM-based Rerankers? An Empirical Study" — Findings of EMNLP 2025 (aclanthology 2025.findings-emnlp.305). [PR]
12. "LLM Optimization Unlocks Real-Time Pairwise Reranking" — arXiv:2511.07555 — 2025. [P]
13. "LLM-based Listwise Reranking under the Effect of Positional Bias" — arXiv:2604.03642 — 2026. [P]
14. "Learning from Emptiness: De-biasing Listwise Rerankers with Content-Agnostic Probability Calibration" — arXiv:2604.10150 — 2026. [P]
15. "One Pass, Any Order: Position-Invariant Listwise Reranking" — arXiv:2604.27599 — 2026. [P]
16. "Ranked by Position: Order Sensitivity as an Exploitable Attack Surface in LLM Listwise Recommenders" — arXiv:2607.24869 — 2026. [P]
17. "RoToR: Towards More Reliable Responses for Order-Invariant Inputs" — arXiv:2502.08662 — 2025. [P]

Reasoning / RL rerankers
18. Weller et al. — "Rank1: Test-Time Compute for Reranking" — arXiv:2502.18418 — CoLM 2025. [PR]
19. Zhuang et al. — "Rank-R1" — arXiv:2503.06034 — 2025. [P]
20. "REARANK: Reasoning Re-ranking Agent via Reinforcement Learning" — arXiv:2505.20046 — EMNLP 2025. [PR]
21. "Rank-K: Test-Time Reasoning for Listwise Reranking" — arXiv:2505.14432 — 2025. [P]
22. "InsertRank: LLMs can reason over BM25 scores" — arXiv:2506.14086 — 2025. [P]
23. "R1-Ranker: Teaching LLM Rankers to Reason" — arXiv:2506.21638 — 2025. [P]
24. Su et al. — "BRIGHT: A Realistic and Challenging Benchmark for Reasoning-Intensive Retrieval" — arXiv:2407.12883 — 2024. [PR]

Fusion & hybrid
25. OpenSearch — "Introducing reciprocal rank fusion for hybrid search" — opensearch.org blog. [V]
26. "Hybrid Search: BM25, Vector & Reranking Reference 2026" — digitalapplied.com. [V]
27. "RRF-Based Hybrid Dense–Sparse Retrieval" — ceur-ws.org/Vol-4173/T3-7.pdf — FIRE 2025. [P]
28. "Hybrid Retrieval for COVID-19 Literature: Rank Fusion vs Projection Fusion with Diversity Reranking" — arXiv:2604.13728 — 2026. [P]
29. "Uncertainty-Aware Hybrid Retrieval for Long-Document RAG" — arXiv:2606.13550 — 2026. [P]

Cross-encoders / leaderboards (vendor-adjacent)
30. Agentset reranker leaderboard & comparisons (zerank-2, Cohere Rerank 3.5/4, BGE-v2-m3) — agentset.ai/rerankers. [V]
31. mxbai-rerank-v2 (Mixedbread, Apache-2.0, Qwen2.5-based; BEIR ≈57.5 large) — vendor docs via comparisons. [V]

Late interaction & cascades
32. LIR Workshop @ ECIR 2026 — arXiv:2511.00444. [P]
33. "Visual RAG Toolkit: Scaling Multi-Vector Visual Retrieval" (MUVERA+rerank timings) — arXiv:2602.12510 — 2026. [P]
34. "ColBERT-Att: Late-Interaction Meets Attention" — arXiv:2603.25248 — 2026. [P]

Context position, depth, noise
35. Liu et al. — "Lost in the Middle" — arXiv:2307.03172 — TACL 2024. [PR]
36. Jin et al. — "Long-Context LLMs Meet RAG" — arXiv:2410.05983 — 2024. [P]
37. Cuconasu et al. — "The Power of Noise" — arXiv:2401.14887 — SIGIR 2024. [PR]
38. Mazuryk et al. — "The Powerless Noise" — arXiv:2607.03615 — 2026. [P]
39. "Lost in the Evidence? Reproducing Document Position and Context Size Effects in RAG" — arXiv:2605.27105 — 2026. [P]
40. "Lost at the End: Primacy Bias in Multimodal RAG QA" — arXiv:2606.16494 — 2026. [P]
41. "Position Bias Correction is Insufficient for One-Pass Attention Sorting" — arXiv:2606.27793 — 2026. [P]
42. "Understanding the Fundamental Design Decisions of RAG Systems" — arXiv:2411.19463 — 2024. [P]
43. "Benchmarking RAG for Chemistry" — arXiv:2505.07671 — 2025. [P]
44. "Worse than Zero-shot? Fact-Checking Dataset for RAG Robustness Against Misleading Retrievals" — arXiv:2502.16101 — 2025. [P]
45. "Cluster-based Adaptive Retrieval: Dynamic Context Selection for RAG" — arXiv:2511.14769 — 2025. [P]

Sufficiency, context rot, abstention, adaptive retrieval
46. Joren et al. — "Sufficient Context: A New Lens on RAG Systems" — arXiv:2411.06037 — ICLR 2025. [PR] (+ research.google blog; github.com/hljoren/sufficientcontext)
47. Hong, Troynikov & Huber — "Context Rot" — trychroma.com/research/context-rot — July 2025. [V] (replication toolkit: github.com/chroma-core/context-rot)
48. Jiang et al. — "Active Retrieval Augmented Generation" (FLARE) — arXiv:2305.06983 — EMNLP 2023. [PR]
49. "RetrievalQA: Assessing Adaptive RAG" — arXiv:2402.16457 — 2024. [P]
50. "Retrieval as a Decision: Training-Free Adaptive Gating for Efficient RAG" (TARG) — arXiv:2511.09803 — 2025. [P]
51. "When to Retrieve During Reasoning: Adaptive Retrieval for Large Reasoning Models" — arXiv:2604.26649 — 2026. [P]
52. "Know Before You Fetch: Calibrated Retrieval-Budget Allocation for RAG" — arXiv:2606.29959 — 2026. [P]

Compression / pruning
53. Xu, Shi & Choi — "RECOMP" — arXiv:2310.04408 — ICLR 2024. [PR]
54. Jiang et al. — "LongLLMLingua" — arXiv:2310.06839 — ACL 2024. [PR]
55. Pan et al. — "LLMLingua-2" — arXiv:2403.12968 — ACL 2024 Findings. [PR]
56. Cheng et al. — "xRAG: Extreme Context Compression with One Token" — arXiv:2405.13792 — NeurIPS 2024. [PR]
57. Chirkova et al. — "Provence: Efficient and Robust Context Pruning" — arXiv:2501.16214 — ICLR 2025. [PR] (+ NAVER LABS Europe blog)
58. "XProvence: Zero-Cost Multilingual Context Pruning" — arXiv:2601.18886 — 2026. [P]
59. "AttentionRAG: Attention-Guided Context Pruning" — arXiv:2503.10720 — 2025. [P]
60. "Density-aware Soft Context Compression with Semi-Dynamic Compression Ratio" — arXiv:2603.25926 — 2026. [P]

Surveys / context
61. "A Survey of Context Engineering for Large Language Models" — arXiv:2507.13334 — 2025. [P]
62. ZeroEntropy — bi-encoder vs cross-encoder & listwise concepts — zeroentropy.dev. [V]
