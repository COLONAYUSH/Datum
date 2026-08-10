# Evaluation of RAG & Retrieval — Benchmarks, Frameworks, and the Eval Crisis

**Dimension:** evaluation-benchmarks | **Compiled:** 2026-08-05 | **Audience:** ML-systems researchers designing a next-generation RAG framework

---

## Scope

This document catalogues and critiques the evaluation ecosystem for retrieval-augmented generation (RAG) and the retrieval/memory layer of agentic LLM systems, as of mid-2026. It covers:

- Retrieval benchmarks (BEIR, MTEB/MMTEB, LoTTE, BRIGHT, LIMIT, FreshStack) and their saturation/contamination pathologies.
- End-to-end RAG benchmarks (CRAG, RGB, MultiHop-RAG, RAGBench, OmniEval, FreshQA, FinanceBench, LegalBench-RAG) and shared-task efforts (TREC RAG 2024/2025, SIGIR LiveRAG).
- Automated evaluation frameworks (RAGAS, ARES, TruLens, RAGChecker, TRACe) and their measured reliability.
- Groundedness/faithfulness measurement (RAGTruth, FActScore, ALCE, Vectara HHEM → FaithJudge, FaithBench, HalluLens).
- LLM-as-judge reliability (position/verbosity/self-preference biases, JudgeBench, TREC support-evaluation studies).
- Agentic retrieval evaluation (GAIA, BrowseComp, DeepResearch Bench).
- Production evaluation practice and the offline-online gap (Chroma's generative benchmarking, synthetic eval-set pitfalls, the "coverage illusion").

The organizing thesis, supported by the evidence below: **RAG evaluation is in a legitimacy crisis.** The field's dominant instruments measure the wrong distribution (clean public queries vs. messy production traffic), with the wrong judges (biased LLM evaluators), on the wrong units (aggregate averages vs. per-slice coverage), against corpora the models have already memorized. A next-generation RAG framework must treat evaluation as a first-class architectural concern, not an afterthought.

---

## Lineage & chronological development

### Phase 1 — IR metrics inherited wholesale (pre-2021)
Classical IR evaluation (Cranfield paradigm: pooled relevance judgments, nDCG/MAP/Recall@k, TREC-style tracks) predates RAG by decades. Early RAG work (2020–2021) simply reused open-domain QA exact-match/F1 plus retrieval Recall@k, implicitly assuming retrieval metrics compose with generation quality. That assumption is now known to be false in both directions (see §Failure modes).

### Phase 2 — Zero-shot retrieval benchmarks (2021–2023)
- **BEIR** — Thakur et al. — arXiv:2104.08663 — 2021. 18 heterogeneous datasets for zero-shot IR evaluation across 10 model classes. Key original findings: "BM25 is a robust baseline"; dense/sparse bi-encoders "often underperform" out of domain; re-ranking and late-interaction models are strongest zero-shot but computationally expensive. BEIR became the de facto retrieval leaderboard — and later the canonical example of benchmark saturation via overfitting.
- **LoTTE** (Long-Tail Topic-stratified Evaluation) — introduced alongside **ColBERTv2** — Santhanam et al. — arXiv:2112.01488 — 2021/2022. StackExchange-derived long-tail queries designed to escape MS MARCO's head-query distribution. (Note: LoTTE is described in the paper body, not the abstract; attribution verified against the ColBERTv2 paper page.)
- **MTEB** — Muennighoff et al. — arXiv:2210.07316 — 2022. Unified embedding benchmark spanning retrieval, clustering, classification, STS. Became the single most influential — and most gamed — leaderboard in the embedding ecosystem (see §Contamination).

### Phase 3 — RAG-specific behavioral benchmarks (2023–2024)
- **RGB** — Chen et al. — arXiv:2309.01431 — AAAI 2024. First benchmark to decompose RAG-relevant *LLM competencies*: noise robustness, negative rejection (declining to answer when evidence is absent), information integration, and counterfactual robustness. Finding: LLMs show "a certain degree of noise robustness" but "struggle significantly in terms of negative rejection, information integration, and dealing with false information."
- **FreshQA / FreshLLMs** — Vu et al. — arXiv:2310.03214 — 2023. Dynamic QA benchmark for fast-changing and false-premise questions; >50k human judgments; all tested models struggled on rapidly-changing knowledge and false premises. Maintained as a living benchmark — an early acknowledgment that static eval sets rot.
- **RAGAS** — Es et al. — arXiv:2309.15217 — 2023. Reference-free LLM-judged metrics (faithfulness, answer relevance, context precision/recall). Enormously popular in industry due to zero annotation cost; reliability heavily critiqued later (see §Frameworks).
- **ARES** — Saad-Falcon et al. — NAACL 2024 (aclanthology.org/2024.naacl-long.20). Fine-tuned lightweight judges calibrated with ~150 human-annotated examples + prediction-powered inference (PPI) confidence intervals. Reported higher Kendall's-tau ranking agreement than RAGAS (per its evaluation: +0.065 context relevance, +0.132 answer relevance on average across datasets).
- **FActScore** — Min et al. — arXiv:2305.14251 — EMNLP 2023. Decomposes long-form output into atomic facts, scores fraction supported by a source; ChatGPT scored ~58% on biography generation; automated estimator within ~2% of human evaluation. Limitation: depends on the reliability/coverage of the reference knowledge source.
- **ALCE** — Gao et al. — arXiv:2305.14627 — EMNLP 2023. First automatic citation-quality benchmark (fluency, correctness, citation recall/precision). Finding: "even the best models lack complete citation support 50% of the time" on ELI5.
- **RAGTruth** — Niu et al. — arXiv:2401.00396 — ACL 2024. ~18k naturally-generated RAG responses with *word/span-level* human hallucination annotations across QA, data-to-text, and summarization. The reference corpus for training and meta-evaluating hallucination detectors.
- **MultiHop-RAG** — Tang & Yang — arXiv:2401.15391 — 2024. News-corpus benchmark of multi-hop queries with ground-truth evidence chains; "existing RAG methods perform unsatisfactorily in retrieving and answering multi-hop queries" (GPT-4, PaLM, Llama2-70B all tested).
- **CRAG** — Yang et al. (Meta) — arXiv:2406.04744 — NeurIPS 2024 D&B; KDD Cup 2024 official benchmark. 4,409 QA pairs, 5 domains, 8 question types, mock web + KG search APIs, explicit stratification by entity popularity (head→tail) and temporal dynamism (years→seconds). Landmark negative results: advanced LLMs alone ≤34% accuracy; naive RAG only 44%; best industry systems answer only 63% without hallucination; hallucination rates 16–25%. Accuracy drops sharply for dynamic facts, torso/tail entities, and complex questions.
- **RAGBench + TRACe** — Friel et al. — arXiv:2407.11005 — 2024. 100k examples across five industry domains; formalizes TRACe (uTilization, Relevance, Adherence, Completeness) as explainable, actionable metrics. Provocative finding: "LLM-based RAG evaluation methods struggle to compete with a finetuned RoBERTa model on the RAG evaluation task."
- **RAGChecker** — Ru et al. (AWS) — arXiv:2408.08067 — NeurIPS 2024. Claim-level entailment metrics jointly diagnosing retriever and generator; meta-evaluation showed "significantly better correlations with human judgments" than TruLens, RAGAS, ARES, CRUD-RAG baselines.
- **FinanceBench** — Islam et al. — arXiv:2311.11944 — 2023. 10,231 questions on public-company filings. GPT-4-Turbo *with a retrieval system* "incorrectly answered or refused to answer 81% of questions" — the canonical domain-benchmark demonstration that generic RAG collapses on real enterprise workloads.
- **LegalBench-RAG** — Pipitone & Alami — arXiv:2408.10343 — 2024. First retrieval-focused legal benchmark: 6,858 query-answer pairs over a 79M-character corpus, expert-annotated at *minimal-span* granularity — evaluating precise snippet extraction, not whole-document retrieval.
- **BRIGHT** — Su et al. — arXiv:2407.12883 — ICLR 2025. 1,384 reasoning-intensive queries from 12 sources (StackExchange verticals, LeetCode, AoPS/TheoremQA) where relevance requires inference, not lexical/semantic match. Headline: a leading embedder scoring nDCG@10 ≈ 59 on BEIR collapses to ≈ 18.3 on BRIGHT. Reframed "retrieval quality" as a reasoning problem. *(Query-count note: the arXiv v1 abstract of Jul 2024 said 1,398; the current version — v4, Mar 2025 — states 1,384. Cite 1,384 and treat 1,398 as the superseded v1 figure. The "12 sources/datasets" count is unchanged.)*
- **OmniEval** — Wang et al. — arXiv:2412.13018 — 2024. Financial-domain RAG benchmark: matrix of 5 task classes × 16 topics; auto-generated + human-verified instances (87.47% human acceptance); multi-stage evaluation of retriever and generator with rule-based and fine-tuned LLM-judge metrics.

### Phase 4 — Institutional evaluation and the judge question (2024–2025)
- **TREC RAG Track 2024** — 3 tasks (Retrieval, Augmented Generation, full RAG), 301 queries, answers ≤400 words (trec-rag.github.io). Two automated methodologies:
  - **AutoNuggetizer** — Pradeep et al. — arXiv:2411.09607 — 2024. LLM-based revival of 2003 QA-track nugget evaluation: LLMs create nuggets and assign them to answers. Initial results over 45 runs / 21 topics: "strong correlation between scores derived from a fully automatic nugget evaluation and a (mostly) manual nugget evaluation by human assessors."
  - **Support evaluation** — Thakur et al. — arXiv:2504.15205 / SIGIR 2025 (dl.acm.org/doi/10.1145/3726302.3730165). GPT-4o vs. human judges on citation-support over 45 submissions × 36 topics: 56% exact three-level agreement from scratch, 72% under post-editing; strikingly, *independent human judges correlated better with GPT-4o than with each other* — simultaneously an endorsement of LLM judging and an indictment of human ground truth.
- **TREC RAG Track 2025** — Overview (trec.nist.gov/pubs/trec34/papers/Overview_rag.pdf): second edition; NIST received 46 retrieval-only runs from 12 groups; continued nugget + support methodology; nugget-based and support-based views "sometimes highlighted different system strengths" — i.e., informativeness and groundedness are partially orthogonal axes.
- **SIGIR 2025 LiveRAG Challenge** — arXiv:2507.04942 — live shared-task RAG evaluation over a fixed corpus, another institutional response to static-benchmark rot.
- **MIRAGE-Bench** — Thakur et al. — arXiv:2410.13716 — 2024/2025. Multilingual RAG arena using a learned surrogate judge to approximate expensive pairwise LLM-judge tournaments.
- **JudgeBench** — Tan et al. — arXiv:2410.12784 — ICLR 2025. Benchmarks the judges themselves on response pairs with objectively correct answers (knowledge, reasoning, math, coding). Headline: GPT-4o performs "just slightly better than random guessing" — judges fail precisely where factual correctness diverges from plausible style.
- **Judge-bias literature** — "Judging the Judges" — Shi et al.(*) — arXiv:2406.07791 — systematic position-bias study: 15 judges, MT-Bench + DevBench, 22 tasks, ~40 answer models, >150k instances; position bias is judge- and task-dependent, driven strongly by the quality gap between candidates, not random noise. **Self-preference bias** — Wataoka et al. — arXiv:2410.21819 — 2024: judges over-score their own outputs; the paper reports (measured via perplexity analysis) that judges favor low-perplexity (self-like) text; bias not strongly correlated with judge capability. Secondary syntheses (e.g., Adaline's 2025/2026 review, adaline.ai) catalogue 12+ distinct judge biases via the CALM framework, including verbosity, authority, and self-enhancement. A 2026 follow-up, "Judging the Judges: A Systematic Evaluation of Bias Mitigation Strategies in LLM-as-a-Judge Pipelines" (arXiv:2604.23178), evaluates mitigation strategies systematically.
- **Vectara hallucination leaderboard → FaithJudge** — Tamber et al. — arXiv:2505.04847 — EMNLP 2025 Industry. Public HHEM-based leaderboard (grounded summarization of ~7,700 short articles) ran since 2023; acknowledged critiques that the task was too short/clean to reflect enterprise RAG. Late-2025 refresh: documents to 32K tokens across law/medicine/finance/tech/education; detector upgraded from the HHEM classifier to **FaithJudge**, a few-shot LLM-judge guided by pooled human annotations from **FaithBench** (arXiv:2410.13210). Measured hallucination rates are *higher* under the harder benchmark — the easy benchmark had been flattering models.
- **HalluLens** — arXiv:2504.17550 — 2025 — taxonomized hallucination benchmark separating extrinsic/intrinsic hallucination; **LettuceDetect** — arXiv:2502.17125 — 2025 — lightweight RAGTruth-trained span-level hallucination detector (ModernBERT-based), part of a wave showing small encoders rival LLM judges at grounding checks.

### Phase 5 — The reckoning: contamination, theory, and production reality (2025–2026)
- **MMTEB / MTEB v2** — Enevoldsen et al. — arXiv:2502.13595 — ICLR 2025. Community rebuild: 500+ tasks, 250+ languages, explicit **zero-shot** annotations (which training sets a model saw), correlation-based task downsampling. A direct institutional response to leaderboard gaming; notable finding: 560M-param multilingual-e5-large-instruct beat much larger models on several splits.
- **LIMIT / theoretical limits of embeddings** — Weller, Boratko, Naim, Lee (Google DeepMind) — arXiv:2508.21038 — ICLR 2026. Proves via learning-theory (sign-rank) arguments that the number of top-k document subsets a single-vector embedding can realize is bounded by embedding dimension; constructs the deliberately trivial LIMIT dataset on which "state-of-the-art models fail... despite the simple nature of the task." Consequence for evaluation: some retrieval failures measured on benchmarks are *architectural impossibilities*, not training deficiencies — no amount of leaderboard hill-climbing on BEIR/MTEB fixes them.
- **FreshStack** — Thakur et al. — arXiv:2504.13128 — 2025. Automated framework for building *fresh, niche, technical* retrieval benchmarks from recent code/docs + community questions; SOTA retrievers "significantly underperform oracle approaches on all five topics," and rerankers failed to help on 2/5 — evidence that on genuinely unseen corpora, the model ranking and the absolute numbers both look nothing like BEIR.
- **Chroma generative benchmarking** — Hong & Huber — trychroma.com/research/generative-benchmarking — 2025. Practitioner-facing methodology + evidence: (a) public benchmarks are generic, artificially clean, and memorized — LLMs reproduced or nearly reproduced test queries for all 9 public datasets probed, indicating training exposure; (b) aligned-judge document filtering (46% → 75.2% human alignment over 5 iterations on Weights & Biases data) + steered query generation builds custom evals from your own corpus; (c) ranking inversion in the wild: jina-embeddings-v3 beat text-embedding-3-large "across all MTEB English tasks" but *underperformed it* on the real WandBot workload.
- **Synthetic-eval validity studies** — van Elburg et al., "Can we Evaluate RAGs with Synthetic Data?" — arXiv:2508.11758 — 2025: synthetic benchmarks reliably rank *retriever configurations* but "do not consistently produce reliable RAG rankings when comparing generator architectures" (task misalignment + stylistic bias). Complementary: "Generating Leakage-Free Benchmarks for Robust RAG Evaluation" (arXiv:2605.08838, 2026); RIKER's "coherent simulated universe" approach to leakage-proof knowledge-retrieval eval (arXiv:2601.08847, 2026); Red Hat's practitioner guidance on synthetic RAG eval data (developers.redhat.com, Feb 2026).
- **Production post-mortems** — "The Coverage Illusion" — Hussain et al. — arXiv:2605.27220 — 2026. Danish National Encyclopedia production RAG: offline synthetic evaluation predicted >90% of queries needed LLM query augmentation; production traffic needed it 27.8% of the time; pre-retrieval routing was shown unlearnable before index contact (four ML approaches failed); a post-retrieval escalation cascade delivered +0.140 composite quality and −31.8% latency. The cleanest published demonstration that synthetic query distributions ≠ user query distributions.
- **Coverage over averages** — Klearman et al. — arXiv:2604.20763 — 2026. Argues average-based retrieval metrics on biased query sets are untrustworthy; proposes semantic stratification (entity-clustered corpus space, systematic query generation for underrepresented strata) with formal coverage guarantees — evaluation as coverage measurement rather than mean-score reporting.
- **Agentic evaluation** — **GAIA** — Mialon et al. — arXiv:2311.12983 — 2023: 466 tool-use/web questions; humans 92% vs. GPT-4+plugins 15%; became the standard agent benchmark (and by 2025–26 substantially climbed, reducing headroom). **BrowseComp** — Wei et al. — arXiv:2504.12516 — 2025: 1,266 hard-to-find, easy-to-verify web-browsing questions stressing persistence/creativity in retrieval (authors' affiliation reported inconsistently by our tooling; the paper is widely attributed to OpenAI — flagged as minor uncertainty). **DeepResearch Bench** — Du et al. — arXiv:2506.11763 — 2025: 100 PhD-level research tasks across 22 fields; dual evaluation of report quality (reference-based, human-aligned) and *citation accuracy* — importing groundedness evaluation into long-horizon agentic retrieval. Judge-reliability concerns recur here too (e.g., AgentProp-Bench on judge reliability and error propagation in tool-using agent evaluation, arXiv:2604.16706, 2026).
- **Surveys consolidating the field** — Gan et al., "RAG Evaluation in the Era of LLMs" — arXiv:2504.14891 — 2025 (taxonomy over system performance / factuality / safety / efficiency; notes conventional eval cannot handle dynamic knowledge sources); systematic literature review of 128 highly-cited RAG studies 2020–2025 — arXiv:2508.06401 — finds "overlap metrics still dominate" while LLM-judge usage peaked in 2024H2–2025H1; survey of reasoning-intensive retrieval — arXiv:2605.00063 — 2026.

---

## State of the art — mid-2026 snapshot

**What careful teams actually do now (converged best practice):**
1. **Custom, corpus-derived eval sets** over public benchmarks: generative benchmarking (Chroma-style) with aligned LLM filtering and query-style steering from real user queries; public leaderboards (MTEB/BEIR) used only as a coarse prior, never for final model selection.
2. **Claim/nugget-level decomposition** as the unit of measurement: AutoNuggetizer at TREC, RAGChecker claims, FActScore atomic facts, span-level hallucination detection (RAGTruth-trained encoders, FaithJudge). Whole-answer Likert scoring is understood to be noise-dominated.
3. **Two-axis reporting**: informativeness/coverage (nuggets, recall of gold claims) and groundedness/support (citation-level entailment) reported separately, because TREC 2024/2025 showed they rank systems differently.
4. **Calibrated judges, not raw judges**: few-shot judges anchored to pooled human annotations (FaithJudge), fine-tuned small evaluators (ARES, RAGBench's RoBERTa result, LettuceDetect), PPI-style statistical correction against a small human-labeled slice; raw single-prompt GPT-judging is considered indefensible for paper-grade claims post-JudgeBench.
5. **Contamination hygiene**: MTEB v2/MMTEB zero-shot flags; fresh/rolling benchmarks (FreshQA, FreshStack, LiveRAG) for anything involving model-training-era corpora.
6. **Stratified, slice-level reporting** (entity popularity, temporal dynamism, hop count, query realism) following CRAG's design and semantic-stratification proposals — averages hide the failure modes that matter.
7. **Online/production loops**: offline evals as regression gates only; production telemetry (retrieval-miss escalation signals, user feedback, post-retrieval cascades per the Coverage Illusion study) as the ground truth for query-distribution questions.

**What remains unsolved:** end-to-end metrics still correlate weakly with each other and with humans; generator comparison via synthetic data is unreliable; agentic multi-step retrieval has no accepted process-level (vs. outcome-level) evaluation; there is no standard for evaluating *memory* (persistent, cross-session retrieval state) at all; and the community lacks any benchmark whose score is a validated predictor of production quality.

---

## Detailed thematic analysis

### 1. The retrieval-metrics vs. end-to-end disconnect

Retrieval metrics (nDCG@k, Recall@k on pooled judgments) and end-to-end answer quality are only loosely coupled, in both directions:

- **Good retrieval ≠ good answers.** RGB (arXiv:2309.01431) showed generators fail at negative rejection and integration even given adequate context; CRAG found straightforward RAG lifted accuracy only from ≤34% to 44% while leaving 16–25% hallucination; TREC 2024/2025 found nugget scores (informativeness) and support scores (groundedness) rank systems differently.
- **"Bad" retrieval ≠ bad answers.** Relevance judgments are query-document; generators exploit partially-relevant or redundant context, and answer-level metrics can be insensitive to which of several sufficient documents was retrieved. FreshStack's oracle-context experiments quantify the gap: oracle context greatly improves answers, but retriever rankings did not predict answer-quality rankings uniformly (rerankers helped on only 3/5 topics).
- **Sufficiency is the missing concept.** Work such as SURE-RAG (arXiv:2605.03534, 2026) pushes evidence *sufficiency/uncertainty* verification as the retrieval-side target rather than topical relevance — an implicit admission that nDCG measures the wrong property for RAG.
- **Structural implication:** LIMIT (arXiv:2508.21038) shows single-vector retrieval has representational ceilings invisible to standard benchmarks (which don't construct adversarial top-k combinatorics). A retrieval eval that never probes the combinatorial structure of "which sets of documents can co-rank" will systematically overstate embedding-based systems.

### 2. Automated RAG evaluation frameworks — measured reliability

| Framework | Mechanism | Human-annotation need | Measured reliability | Key critiques |
|---|---|---|---|---|
| RAGAS (arXiv:2309.15217) | Prompted LLM judges; faithfulness, answer relevance, context precision/recall | None (reference-free) | One 2025 methodological study reports harmonic-mean correlation with humans of only ~0.55 (reported in arXiv:2510.00001's framing; treat magnitude as single-study evidence) | Inherits all LLM-judge biases; metric definitions drift across library versions; no confidence intervals |
| ARES (NAACL 2024) | Fine-tuned lightweight judges + PPI confidence intervals | ~150 labeled examples | Beat RAGAS on Kendall's tau (+0.065 context rel., +0.132 answer rel., per ARES's own eval) | Calibration set must match domain; synthetic training queries inherit generation biases |
| TruLens (trulens.org) | "RAG triad": context relevance, groundedness, answer relevance; tracing + judge scoring per step | None by default; supports custom-aligned judges | Used as baseline in RAGChecker meta-eval (outperformed by it) | Product-grade instrumentation, but metric validity rests on the same raw-LLM-judge foundation |
| RAGChecker (arXiv:2408.08067) | Claim-level entailment against context and gold answers; joint retriever/generator diagnostics | Gold answers needed | "Significantly better correlations with human judgments" than TruLens/RAGAS/ARES/CRUD-RAG in its meta-eval | Claim extraction itself is an LLM step (error compounding); expensive |
| TRACe/RAGBench (arXiv:2407.11005) | Utilization/Relevance/Adherence/Completeness on 100k labeled examples | Dataset provides labels | Fine-tuned RoBERTa beat LLM-judge methods on RAG eval | Labels partly LLM-derived; domain coverage fixed |
| OmniEval (arXiv:2412.13018) | Matrix (5 tasks × 16 topics) auto+human instances; rule-based + fine-tuned judges | Human verification pass (87.47% acceptance) | Finance-specific | Domain-limited; generation pipeline biases |

**Meta-point:** every framework in this table uses a model to grade a model. The RAGBench RoBERTa result, LettuceDetect, and ARES all point the same direction: *small, task-fine-tuned evaluators anchored to human labels beat prompted frontier-LLM judges* on grounding-style checks — an inversion of the "bigger judge is better" folk assumption.

### 3. Groundedness, faithfulness, and citation evaluation

- **RAGTruth** (arXiv:2401.00396) remains the anchor corpus: word-level hallucination spans on ~18k natural RAG outputs, enabling detector training (LettuceDetect, arXiv:2502.17125) and honest meta-evaluation.
- **FActScore** (arXiv:2305.14251): atomic-fact precision against a reference source; strong for long-form factuality; limited by reference-source coverage and by measuring *precision only* (a maximally terse answer scores perfectly).
- **ALCE** (arXiv:2305.14627): citation recall/precision; even best 2023 models lacked full citation support ~50% of the time on ELI5. DeepResearch Bench (2025) carries this into agentic long reports.
- **Vectara HHEM → FaithJudge** (arXiv:2505.04847; vectara.com/blog): the leaderboard's own evolution is the best public admission of eval-difficulty inflation — short clean summarization understated hallucination; the 32K-token multi-domain refresh with FaithBench-anchored FaithJudge yields *higher* measured hallucination and better model separation.
- **Open tension:** "groundedness" conflates (a) entailment by cited span, (b) entailment by any retrieved context, and (c) truthfulness. TREC support evaluation targets (a); HHEM-style targets (b); FActScore targets (c) relative to a reference corpus. Systems game whichever one is measured (e.g., citing everything to maximize (b) while degrading (a)-precision).

### 4. LLM-as-judge reliability — the recursive problem

- **Position bias**: arXiv:2406.07791 (15 judges, >150k instances) — repeatable, judge- and task-specific, strongest when candidate quality gap is small — i.e., exactly when you need the judge most.
- **Verbosity & self-preference**: arXiv:2410.21819 — judges systematically favor low-perplexity (self-like) and longer outputs; self-preference is not cured by judge capability.
- **JudgeBench** (arXiv:2410.12784, ICLR 2025): on objectively-resolvable pairs, GPT-4o ≈ random. Style-substance conflation is the mechanism: judges reward plausibility, which correlates with correctness only on easy instances.
- **TREC support studies** (arXiv:2504.15205): the constructive counterpoint — for *narrow, well-operationalized* tasks (three-level citation support), GPT-4o matches humans about as well as humans match each other (56% exact from scratch, 72% post-edited). Lesson: judge reliability is a function of task decomposition, not of the judge alone. Narrow entailment questions: usable. Holistic answer quality: not.
- 2026 work systematizes mitigation (arXiv:2604.23178; CyclicJudge arXiv:2603.01865; rubric-based position-bias analysis arXiv:2602.02219) and questions whether judge meta-benchmarks themselves are measuring the right thing ("Are We on the Right Way to Assessing LLM-as-a-Judge?", arXiv:2512.16041).

### 5. Contamination, saturation, and leaderboard gaming

- **BEIR saturation**: leaderboards saturate "via subtle overfitting" (zeroentropy.dev analysis); BEIR corpora are in the pre-training data of post-2023 models, so "zero-shot" is no longer zero-shot.
- **MTEB gaming**: Nils Reimers (MTEB/SBERT author) publicly: training on MTEB training splits for leaderboard submissions "was never intended... It was a big mistake to publish these training splits"; crawled training sets have "significant overlap to the test set"; on private data "you see a massive shift in the ranking and how bad many of the 'top MTEB models' actually perform" (x.com/Nils_Reimers, Dec 2024). Practitioner consensus by 2025: the top of the MTEB retrieval leaderboard measured overfitting aggressiveness, not generalization.
- **Direct memorization evidence**: Chroma reproduced or near-reproduced held-out queries from all 9 public datasets tested via LLM prompting — the test sets are *in the models*.
- **Institutional responses**: MMTEB zero-shot annotations & task refresh (arXiv:2502.13595); fresh/rolling benchmarks (FreshQA, FreshStack, LiveRAG); private/held-out tracks (TREC pooling with NIST assessors); leakage-free synthetic universes (arXiv:2605.08838, arXiv:2601.08847).
- **Residual problem**: every static public benchmark begins decaying the day it is released; the decay rate now (frontier-lab crawl cadence) is months, not years. Evaluation validity has a half-life, and almost no published result reports its benchmark's age-adjusted credibility.

### 6. Agentic retrieval & deep-research evaluation

- **GAIA** (arXiv:2311.12983): 466 questions; human 92% vs GPT-4+plugins 15% at release — by 2025–26 top agent systems have closed much of the gap (headroom collapse), and its fixed answers make it contamination-prone.
- **BrowseComp** (arXiv:2504.12516): 1,266 "hard to find, easy to verify" questions; deliberately inverts GAIA's problem by making answers short/verifiable; measures retrieval persistence, not synthesis quality — the authors frame it as intentionally incomplete.
- **DeepResearch Bench** (arXiv:2506.11763): 100 expert-written PhD-level tasks, 22 fields; RACE (reference-anchored report quality) + FACT (citation trustworthiness) style dual evaluation. Open issues: reference-based grading penalizes legitimate novel syntheses; judge biases recur at report scale.
- **Gap:** all three are *outcome* evaluations. No accepted benchmark scores the retrieval *process* of an agent (query reformulation quality, stopping criteria, evidence-conflict handling, cost-quality frontier), even though process failures are what production teams debug. AgentProp-Bench (arXiv:2604.16706) begins to study judge reliability and error cascades in tool-use evaluation.

### 7. Production evaluation & the offline-online gap

Converging evidence that offline scores do not predict production quality:

1. **Query-distribution mismatch.** Synthetic/public queries are verbose, grammatical, contextually complete; real queries are short, sparse-vocabulary, ambiguous (Chroma; Red Hat 2026; Coverage Illusion). The Coverage Illusion study quantifies it: offline predicted >90% augmentation need; production showed 27.8%.
2. **Ranking inversions.** Chroma's WandBot case: model ordering on MTEB inverted on the real workload. Nils Reimers reports the same for "top MTEB models" generally. FreshStack shows both absolute collapse and reordering on fresh technical corpora.
3. **Generator comparisons via synthetic evals are unreliable** (arXiv:2508.11758) — synthetic sets are fine for retriever knob-tuning, biased for generator selection.
4. **Averages hide slices.** CRAG's popularity/dynamism stratification and semantic stratification (arXiv:2604.20763) both show aggregate scores mask the tail slices where systems actually fail; production traffic is disproportionately tail.
5. **What works in practice**: build evals from your own corpus + real query logs (generative benchmarking with aligned judges); run cheap-first retrieval cascades and treat *escalation signals as online eval labels* (Coverage Illusion); maintain small, human-verified golden sets for judge calibration (ARES-style PPI); re-benchmark on every corpus update because RAG quality is corpus-coupled, not just model-coupled.

---

## Comparison tables

### Retrieval benchmarks

| Benchmark | Year | Unit | What it stresses | Status mid-2026 |
|---|---|---|---|---|
| BEIR (2104.08663) | 2021 | 18 datasets, nDCG@10 | Zero-shot domain transfer | Saturated/contaminated; historical baseline only |
| LoTTE (w/ ColBERTv2, 2112.01488) | 2022 | StackExchange long-tail | Out-of-MARCO distribution | Aged; partially contaminated |
| MTEB (2210.07316) | 2022 | Embedding tasks incl. retrieval | Breadth | Gamed; superseded |
| MMTEB / MTEB v2 (2502.13595) | 2025 | 500+ tasks, 250+ langs, zero-shot flags | Breadth + contamination hygiene | Current default leaderboard |
| BRIGHT (2407.12883) | 2024/25 | 1,384 reasoning queries (v1: 1,398) | Inference-mediated relevance | Active; discriminative (59→18 nDCG collapse) |
| LIMIT (2508.21038) | 2025/26 | Adversarial combinatorial top-k | Theoretical capacity of single vectors | Active; architectural diagnostic |
| FreshStack (2504.13128) | 2025 | Auto-built niche/technical sets | Freshness, contamination-resistance | Active; framework more than fixed set |

### End-to-end / RAG behavioral benchmarks

| Benchmark | Year | Scale | Distinctive design | Headline finding |
|---|---|---|---|---|
| RGB (2309.01431) | 2023 | 4 competencies, 6 LLMs | Controlled context perturbation | Negative rejection & integration fail |
| FreshQA (2310.03214) | 2023 | Dynamic, living | Fast-changing + false-premise Qs | All models fail on fast-changing facts |
| MultiHop-RAG (2401.15391) | 2024 | News multi-hop | Evidence-chain ground truth | Multi-hop retrieval+answering unsatisfactory |
| CRAG (2406.04744) | 2024 | 4,409 QA, 5 domains | Popularity × dynamism strata; mock APIs | Best industry: 63% hallucination-free |
| RAGBench (2407.11005) | 2024 | 100k, 5 industries | TRACe explainable labels | RoBERTa > LLM judges |
| FinanceBench (2311.11944) | 2023 | 10,231 Qs | Real filings, evidence-provided | GPT-4T+retrieval wrong/refusing 81% |
| LegalBench-RAG (2408.10343) | 2024 | 6,858 pairs / 79M chars | Minimal-span retrieval targets | Precise-span retrieval is the bottleneck |
| OmniEval (2412.13018) | 2024 | 5×16 matrix | Auto+human financial matrix | Vertical RAG needs matrix eval |
| TREC RAG (trec.nist.gov) | 2024–25 | 301 topics ('24) | NIST pooling; nuggets + support | Auto nugget eval ≈ manual; nugget ≠ support rankings |

---

## Failure modes & critiques

**F1. Benchmark contamination is the default, not the exception.** BEIR/MTEB corpora and even query sets are demonstrably inside model weights (Reimers; Chroma's 9/9 query-reproduction result). Any RAG paper selecting embedders by MTEB rank is, with high probability, measuring memorization. Half-life of a public benchmark ≈ one frontier-training cycle.

**F2. The judge is part of the system under test.** Prompted LLM judges fail on hard instances (JudgeBench ≈ random for GPT-4o), prefer their own style (self-preference), and are position/verbosity-biased precisely when candidates are close. Since most RAG metrics (RAGAS, TruLens triad, FaithJudge, nugget assignment) are LLM-mediated, headline metric improvements can be judge-pleasing artifacts. Mitigations exist (task narrowing, human-anchored few-shot judges, fine-tuned small evaluators, PPI correction) but are unevenly adopted.

**F3. Retrieval metrics measure relevance; RAG needs sufficiency.** nDCG/Recall@k over graded topical relevance neither guarantees the retrieved set *suffices* to answer (multi-hop, aggregation) nor penalizes distracting near-relevant text that induces hallucination (RGB noise results). The retrieval-metric → answer-quality mapping is non-monotonic, invalidating component-wise optimization as a proxy for system optimization.

**F4. Aggregate averages conceal the operative failure distribution.** CRAG strata (tail entities, fast-changing facts) and semantic-stratification results show per-slice collapse under healthy means. Production traffic concentrates in exactly the slices where means are least informative. Almost no leaderboard reports variance, slices, or coverage.

**F5. Synthetic eval sets inherit the generator's priors.** Synthetic queries are longer, cleaner, and stylistically LLM-flavored; they rank retrievers acceptably but misrank generators (2508.11758) and wildly misestimate operational quantities (Coverage Illusion: 90% predicted vs 27.8% actual augmentation need). Naive "generate Q from chunk" pipelines also leak answer phrasing into queries, inflating recall.

**F6. Groundedness is three different properties, and systems game whichever is measured.** Citation-support (ALCE/TREC), context-entailment (HHEM), and world-truthfulness (FActScore) diverge; optimizing one degrades others (cite-everything, terse-answer, and copy-context pathologies respectively). Easy groundedness benchmarks (short clean summarization) understated hallucination for two years until Vectara's own refresh raised measured rates.

**F7. Human ground truth is weaker than assumed.** TREC 2024: independent human assessors agreed with GPT-4o more than with each other on support judgments. "Correlation with human labels" as the gold standard has an unexamined ceiling; inter-annotator agreement is rarely reported in RAG eval papers.

**F8. End-to-end scores don't transfer across corpora, versions, or time.** RAG quality is a joint property of (model, corpus, chunking, index, query distribution); benchmarks fix all but the model, so published numbers are non-portable. FreshStack and generative-benchmarking results show both absolute and ordinal instability. Meanwhile corpora and models version weekly in production; no standard exists for eval-set maintenance under corpus drift.

**F9. Agentic retrieval evaluation is outcome-only.** GAIA/BrowseComp/DeepResearch Bench score final answers/reports; none scores search-process quality (reformulation, stopping, conflict resolution, cost). Multi-step judge error also compounds (AgentProp-Bench). Memory — persistent cross-session retrieval — has no accepted benchmark at all in the RAG context.

**F10. The field's dominant practice lags its own findings.** The 2020–2025 systematic review (arXiv:2508.06401) finds overlap metrics (EM/F1/ROUGE) *still dominate* published RAG papers even as the specialist literature demonstrated their inadequacy years earlier. There is a multi-year gap between eval research and eval practice.

---

## Open problems (framework-design seeds)

**O1. Sufficiency-oriented retrieval measurement.** Define and standardize a retrieval metric whose target is "minimal evidence set sufficient to support the correct answer" (set-level, not document-level), with distractor-penalty terms. LegalBench-RAG's minimal-span design and SURE-RAG's sufficiency verification are starting points; nothing is standardized. A next-gen framework could make sufficiency-labeled traces a native artifact of the retrieval loop.

**O2. Evaluation with a validity half-life.** No benchmark today carries machine-readable contamination metadata (corpus release date vs. model cutoff, zero-shot flags beyond MMTEB's). Design evals as *renewable processes* (FreshStack-style generators + LiveRAG-style rolling corpora) with versioned decay estimates, rather than static artifacts.

**O3. Judge calibration as a measurable, budgeted quantity.** Standardize the ARES/PPI pattern: every LLM-judged metric ships with (a) a small human-anchored calibration slice, (b) reported judge-human agreement *and* human-human agreement, (c) bias audits (position/verbosity/self-preference) — and the framework refuses to report uncalibrated judge scores. Open question: minimal calibration-label budget per (domain × metric) for stable rankings.

**O4. Coverage-guaranteed, slice-first reporting.** Replace mean-score leaderboards with stratified coverage reports (entity popularity, temporal dynamism, hop depth, query realism, corpus region — per CRAG and arXiv:2604.20763). Open: a principled, corpus-agnostic stratification that composes with automatic query generation and provides formal coverage guarantees.

**O5. Closing the offline-online loop architecturally.** The Coverage Illusion result suggests the strongest eval signal is *emitted by the serving system itself* (cascade escalations, retrieval-empty events, user reformulations). Design the RAG framework so that production telemetry is a typed evaluation stream — online labels continuously re-weighting/refreshing the offline eval set — rather than a separate observability afterthought. Open: label-noise handling and feedback-loop bias (the system shapes the traffic it is evaluated on).

**O6. Process-level agentic retrieval evaluation.** Define scoreable units for multi-step search: reformulation gain, marginal-evidence value per tool call, stopping-rule regret, conflict-resolution correctness, cost-normalized quality. Nugget methodology (AutoNuggetizer) extended over *trajectories* is a plausible route; nothing published does this end-to-end.

**O7. Memory evaluation.** Cross-session persistent memory (what agentic frameworks increasingly bolt onto RAG) lacks benchmarks for retention/interference/staleness/selective forgetting under corpus and preference drift. Adjacent LLM-memory surveys exist (e.g., arXiv:2509.18868) but no RAG-integrated standard.

**O8. Architecture-aware evaluation.** LIMIT shows some failures are representational impossibilities of single-vector retrieval. Evals should *attribute* failures to architecture class (embedding capacity, chunking granularity, index approximation, reranker ceiling, generator integration) so scores are actionable. Today's benchmarks return one number for a five-stage pipeline; RAGChecker's retriever/generator decomposition is the most advanced published attempt and still only two-way.

**O9. Groundedness unification.** A single reported "faithfulness" number should decompose into citation-support precision/recall, context-entailment, and reference-corpus truthfulness, with the gaming pathologies of each (cite-everything, terse-answer, copy-context) explicitly penalized. Nobody has published a gaming-resistant composite.

**O10. Generator-comparison validity under synthetic data.** Since synthetic sets misrank generators (2508.11758), either (a) characterize and correct the stylistic bias, or (b) restrict synthetic evals to retriever decisions and route generator decisions to calibrated-judge + human slices. The decision boundary is unmapped.

---

## Bibliography

Peer-reviewed / major-venue (verified via abstract page or venue record):

- BEIR — Thakur et al. — NeurIPS 2021 D&B — arXiv:2104.08663
- ColBERTv2 (+LoTTE) — Santhanam et al. — NAACL 2022 — arXiv:2112.01488
- MTEB — Muennighoff et al. — EACL 2023 — arXiv:2210.07316
- FActScore — Min et al. — EMNLP 2023 — arXiv:2305.14251
- ALCE — Gao et al. — EMNLP 2023 — arXiv:2305.14627
- RGB — Chen et al. — AAAI 2024 — arXiv:2309.01431
- RAGAS — Es et al. — EACL 2024 demo — arXiv:2309.15217
- FreshLLMs/FreshQA — Vu et al. — 2023 — arXiv:2310.03214
- FinanceBench — Islam et al. — 2023 — arXiv:2311.11944
- GAIA — Mialon et al. — 2023 — arXiv:2311.12983
- ARES — Saad-Falcon et al. — NAACL 2024 — https://aclanthology.org/2024.naacl-long.20.pdf
- RAGTruth — Niu et al. — ACL 2024 — arXiv:2401.00396
- MultiHop-RAG — Tang & Yang — 2024 — arXiv:2401.15391
- CRAG — Yang et al. (Meta) — NeurIPS 2024 D&B / KDD Cup 2024 — arXiv:2406.04744
- Judging the Judges (position bias) — arXiv:2406.07791 — 2024
- BRIGHT — Su et al. — ICLR 2025 — arXiv:2407.12883
- RAGBench/TRACe — Friel et al. — 2024 — arXiv:2407.11005
- RAGChecker — Ru et al. — NeurIPS 2024 — arXiv:2408.08067
- LegalBench-RAG — Pipitone & Alami — 2024 — arXiv:2408.10343
- JudgeBench — Tan et al. — ICLR 2025 — arXiv:2410.12784
- FaithBench — 2024 — arXiv:2410.13210
- MIRAGE-Bench — 2024 — arXiv:2410.13716
- Self-Preference Bias in LLM-as-a-Judge — Wataoka et al. — 2024 — arXiv:2410.21819
- AutoNuggetizer (TREC 2024 RAG) — Pradeep et al. — 2024 — arXiv:2411.09607
- OmniEval — Wang et al. — 2024 — arXiv:2412.13018
- MMTEB — Enevoldsen et al. — ICLR 2025 — arXiv:2502.13595
- LettuceDetect — 2025 — arXiv:2502.17125
- Support Evaluation TREC 2024 RAG — Thakur et al. — SIGIR 2025 — arXiv:2504.15205; https://dl.acm.org/doi/10.1145/3726302.3730165
- BrowseComp — Wei et al. — 2025 — arXiv:2504.12516
- FreshStack — Thakur et al. — 2025 — arXiv:2504.13128
- RAG Evaluation in the Era of LLMs (survey) — Gan et al. — 2025 — arXiv:2504.14891
- HalluLens — 2025 — arXiv:2504.17550
- Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards (HHEM/FaithJudge) — Tamber et al. — EMNLP 2025 Industry — arXiv:2505.04847
- DeepResearch Bench — Du et al. — 2025 — arXiv:2506.11763
- SIGIR 2025 LiveRAG Challenge Report — arXiv:2507.04942
- Can we Evaluate RAGs with Synthetic Data? — van Elburg et al. — 2025 — arXiv:2508.11758
- Systematic literature review of RAG (2020–2025) — 2025 — arXiv:2508.06401
- On the Theoretical Limitations of Embedding-Based Retrieval (LIMIT) — Weller et al. (Google DeepMind) — ICLR 2026 — arXiv:2508.21038
- Memory in LLMs: Mechanisms, Evaluation and Evolution — 2025 — arXiv:2509.18868
- TREC 2025 RAG Track Overview — NIST — https://trec.nist.gov/pubs/trec34/papers/Overview_rag.pdf
- TREC 2024 RAG Track Guidelines — https://trec-rag.github.io/annoucements/2024-track-guidelines/

Preprints, 2026 (seen in search; content verified only where noted):

- Coverage, Not Averages: Semantic Stratification for Trustworthy Retrieval Evaluation — Klearman et al. — arXiv:2604.20763 (verified via abstract)
- The Coverage Illusion (production RAG case study) — Hussain et al. — arXiv:2605.27220 (verified via abstract)
- Generating Leakage-Free Benchmarks for Robust RAG Evaluation — arXiv:2605.08838 (title-level)
- RIKER: Coherent Simulated Universe for retrieval eval — arXiv:2601.08847 (title-level)
- Survey of Reasoning-Intensive Retrieval — arXiv:2605.00063 (title-level)
- Judging the Judges: Bias Mitigation Strategies — arXiv:2604.23178 (title-level)
- CyclicJudge — arXiv:2603.01865; rubric position bias — arXiv:2602.02219; judge meta-eval critique — arXiv:2512.16041; language bias in pairwise judging — arXiv:2601.13649 (title-level)
- AgentProp-Bench (tool-agent judge reliability/cascades) — arXiv:2604.16706 (title-level)
- SURE-RAG (sufficiency-aware evidence verification) — arXiv:2605.03534 (title-level)
- Methodological Framework for Quantifying Semantic Test Coverage in RAG — arXiv:2510.00001 (source of the RAGAS ~0.55 human-correlation figure per search snippet; single-study, treat as uncertain)
- Secure RAG survey — arXiv:2603.21654; Deepchecks RAG eval — arXiv:2605.14488; FAB-Bench — arXiv:2605.26476 (title-level)

Vendor / practitioner sources (marked as non-peer-reviewed):

- Chroma, "Generative Benchmarking" — https://www.trychroma.com/research/generative-benchmarking (verified via fetch; W&B case-study numbers therein)
- TruLens docs — https://www.trulens.org/ (verified via fetch)
- Vectara blog, "Next Generation of Vectara's Hallucination Leaderboard" — https://www.vectara.com/blog/introducing-the-next-generation-of-vectaras-hallucination-leaderboard
- Nils Reimers on MTEB overfitting — https://x.com/Nils_Reimers/status/1870812625505849849
- ZeroEntropy analyses of BEIR/MTEB saturation — https://zeroentropy.dev/concepts/beir-benchmark/ ; https://zeroentropy.dev/concepts/mteb/
- Adaline, "LLM-as-a-Judge: Why Frontier Models Fail 50%+ Bias Tests" (CALM bias taxonomy summary) — https://www.adaline.ai/blog/llm-as-a-judge-reliability-bias
- Red Hat Developer, "Synthetic data for RAG evaluation" (Feb 2026) — https://developers.redhat.com/articles/2026/02/23/synthetic-data-rag-evaluation-why-your-rag-system-needs-better-testing
- Hacker News discussion of generative benchmarking — https://news.ycombinator.com/item?id=43616027 (fetch rate-limited; cited as discussion pointer only)
- Qdrant, "Best Practices in RAG Evaluation" — https://qdrant.tech/blog/rag-evaluation-guide/
- EvalScope RAG evaluation survey — https://evalscope.readthedocs.io/en/latest/blog/RAG/RAG_Evaluation.html

Uncertainty notes: (1) BrowseComp author affiliation reported inconsistently by our fetch tooling (paper widely attributed to OpenAI; Jason Wei first author). (2) The RAGAS ~0.55 human-correlation harmonic mean comes from a single methodological study surfaced in search snippets. (3) LoTTE attribution to the ColBERTv2 paper body (not abstract) per standard citation practice. (4) ARES-vs-RAGAS Kendall-tau deltas are from ARES's own evaluation, not an independent replication.
