# Retriever Training Practice, Generative Retrieval & Corpus Curation — the Pre-2024 Foundations (Research Landscape, as of August 2026)

> Deep-research dossier for the "Reimagining RAG" project. Dimension: **retrieval-training-lineage** — the training practice that produced today's retrievers (hard-negative mining, distillation, retrieval-oriented pretraining, contrastive pretraining at scale), the generative-retrieval / differentiable-search-index paradigm and why it stalled, two decades of query performance prediction (QPP), and the corpus/datastore as a research object (scaling, dedup, quality, poisoning). This is deliberately the "pre-2024 foundations" file: the frontier systems covered in sibling dossiers are, to a striking degree, these recipes scaled up — and their failure modes are inherited from decisions documented here.
>
> Sourcing discipline: every entry marked **[verified]** had its arXiv abstract page (or an arXiv API record with abstract) fetched during this session. Entries marked **[listing-only]** were seen only as title + one-line gist in an arXiv API search result during this session. Classical IR works that predate arXiv-first publishing are marked **[classical — cited from field knowledge, not re-fetched]**. Peer-reviewed venues are named where known; otherwise treat as preprint. Note: this session's web-search budget was exhausted by sibling agents; all verification below was done via direct arXiv abstract fetches and arXiv API queries, which constrains coverage of blogs/model cards — those claims are flagged accordingly.

---

## Scope

Covered here:

1. **Dense-retriever training practice** (2020–2023 core, with the 2024–26 echoes): in-batch vs. hard negatives, ANCE-style asynchronous mining, RocketQA's denoising, curriculum/dynamic negatives (STAR/ADORE, CL-DRD), false-negative handling (NV-Retriever), cross-encoder→bi-encoder distillation (Margin-MSE, TAS-B, RocketQAv2 dynamic listwise distillation), domain adaptation without labels (GPL).
2. **Retrieval-oriented pretraining**: Condenser/coCondenser, RetroMAE (+RetroMAE-2), SimLM, LexMAE — the "bottleneck pretraining" family; contrastive pretraining at scale (Contriever, E5/CCPairs); what open model reports (C-Pack/BGE, Nomic-embed, Arctic-Embed) reveal about multi-stage data curricula.
3. **Generative retrieval (GR) / differentiable search index**: DSI, NCI, SEAL, DSI-QG, DSI++, the scale study (Pradeep et al.), the index-update problem, why GR stalled as a first-stage retriever, and the 2025–26 GR-on-LIMIT re-litigation.
4. **Query performance prediction (QPP)**: pre-retrieval predictors, Clarity/WIG/NQC, supervised & neural QPP, QPP for dense retrieval and for RAG/agentic RAG (2023–2026) — the mature field that "per-query difficulty estimation" open-problem lists keep reinventing.
5. **Corpus/datastore research**: MassiveDS trillion-token datastore scaling, CompactDS, retrieval scaling laws, SemDeDup and semantic dedup, corpus-composition→RAG-quality studies (Power of Noise, RAGGED), corpus poisoning (HotFlip-lineage, PoisonedRAG) vs. curation-as-defense.

Out of scope (owned by sibling dossiers): embedding-model architecture and representation classes (`embeddings-representation.md`), rerankers as a pipeline stage (`retrieval-reranking-fusion.md`), ANN indexes (`indexing-vector-databases.md`), agentic orchestration (`agentic-rag-deep-research.md`). Overlap is retained only where the *training/data* angle is the point.

---

## Lineage & key work

### 1. Hard negatives: the single most important lever in dense-retriever training

- **DPR** (Karpukhin et al., EMNLP 2020; arXiv 2004.04906) established the dual-encoder + in-batch-negatives template; its known weakness — in-batch negatives are mostly easy — set the agenda for the next three years. **[classical — cited from field knowledge; covered in sibling dossier]**
- **ANCE** — *Approximate Nearest Neighbor Negative Contrastive Learning for Dense Text Retrieval* (Xiong et al., 2020; arXiv 2007.00808; ICLR 2021) **[verified]**. Mines negatives from an ANN index over the *model's own evolving embeddings*, refreshed asynchronously during training. Framing that stuck: local (in-batch) negatives create a train/test distribution mismatch; globally hard negatives close it. Limitation: the periodic index refresh is expensive and the mined "hard negatives" are contaminated with unlabeled positives — the false-negative problem ANCE itself does not address.
- **RocketQA** (Qu et al., NAACL 2021; arXiv 2010.08191) **[verified]**. Three fixes that became canon: (i) *cross-batch negatives* (share negatives across GPUs to fake huge batch size), (ii) *denoised hard negatives* — use a cross-encoder to filter out mined negatives that are probably unlabeled positives, (iii) cross-encoder-driven *data augmentation* (pseudo-label unlabeled questions). The denoising step is the first mainstream acknowledgment that MS MARCO-style sparse labels make naive hard-negative mining self-defeating.
- **STAR / ADORE** — *Optimizing Dense Retrieval Model Training with Hard Negatives* (Zhan et al., SIGIR 2021; arXiv 2104.08051) **[verified]**. Theoretical treatment of *why* hard beats random negatives; shows static hard-negative sampling is risky (the model drifts away from the frozen negative distribution) and proposes STAR (stabilized static training) + ADORE (dynamic, query-side-only re-mining each step against a fixed document index). ADORE is the cheap, practical version of ANCE's asynchronous refresh.
- **Curriculum negatives** — *Curriculum Learning for Dense Retrieval Distillation* (CL-DRD; Zeng et al., 2022; arXiv 2204.13679, SIGIR 2022) **[verified via API listing + gist]**: progressively increase the difficulty of distillation data from a reranker teacher. The curriculum idea recurs in modern model reports as staged mining ("easy negatives in pretraining, mined hard negatives in fine-tuning").
- **False negatives, revisited at the frontier** — *NV-Retriever* (Moreira et al., NVIDIA, 2024; arXiv 2407.15831) **[verified]**: positive-aware mining that uses the positive's relevance score as an anchor threshold to discard probable false negatives; ablations credited for MTEB-Retrieval-topping performance. Fifteen years of IR pooling-bias literature compressed into one hyperparameter — evidence that the 2021 RocketQA insight was never structurally solved, only re-tuned.

**Takeaway:** negative *selection policy* — not encoder architecture — has been the dominant quality lever in dense retrieval since 2020, and every generation rediscovers that mined negatives are polluted by unlabeled positives because the underlying training collections (MS MARCO: ~1 shallow label per query) never got better labels.

### 2. Distillation: cross-encoder knowledge into bi-encoders

- **Margin-MSE** — *Improving Efficient Neural Ranking Models with Cross-Architecture Knowledge Distillation* (Hofstätter et al., 2020; arXiv 2010.02666) **[verified]**. Distill the *margin* between positive and negative scores from a cross-encoder (ensemble) teacher rather than absolute scores, since architectures score on different scales. Became the default distillation loss; the published teacher-score files for MS MARCO were reused by dozens of later models — a quiet single point of failure for the whole ecosystem's supervision quality.
- **TAS-B** — *Efficiently Teaching an Effective Dense Retriever with Balanced Topic Aware Sampling* (Hofstätter et al., SIGIR 2021; arXiv 2104.06967) **[verified]**. Cluster queries by topic, compose batches from few topics with balanced pairwise margins → informative in-batch negatives without giant batches; trainable on one consumer GPU in <48h. TAS-B distilled checkpoints were the workhorse BEIR-era dense baseline.
- **RocketQAv2** (Ren et al., EMNLP 2021; arXiv 2110.07367) **[verified]**. *Dynamic listwise distillation*: retriever and reranker trained jointly, each adapting to the other's relevance distribution, plus hybrid data augmentation. The retriever–reranker co-training idea resurfaces in 2024–26 "retriever learns from LLM feedback" work (e.g., FiGRet, arXiv 2411.03957 **[listing-only]**).
- **GPL** — *Generative Pseudo Labeling for Unsupervised Domain Adaptation of Dense Retrieval* (Wang et al., 2021; arXiv 2112.07577; NAACL 2022) **[verified]**. Synthetic queries (T5) over a target corpus + cross-encoder pseudo-margins → adapt a dense retriever to a new domain with zero labels. GPL is the direct ancestor of the 2024–26 synthetic-data flywheel (Gecko, E5-Mistral, Qwen3-Embedding — see sibling dossier): only the generator changed (T5 → frontier LLM).

**Takeaway:** the field converged on a *teacher hierarchy* — cross-encoder (now LLM) judges, bi-encoder learns — and on synthetic queries as the universal domain-adaptation tool. Both inherit the teacher's biases wholesale; nobody audits the teacher.

### 3. Retrieval-oriented pretraining: the bottleneck family

- **Condenser** (Gao & Callan, EMNLP 2021; arXiv 2104.08253) **[verified]**: standard MLM pretraining doesn't prepare the [CLS] token to aggregate; Condenser's head forces late-layer token predictions to condition on the early [CLS] — structurally pre-training an information bottleneck.
- **coCondenser** (Gao & Callan, ACL 2022; arXiv 2108.05540) **[verified]**: adds an unsupervised corpus-level contrastive loss (co-occurring spans as positives) to warm the embedding space; explicitly marketed as removing the need for RocketQA-style heavy engineering (augmentation, huge batches).
- **RetroMAE** (Xiao et al., EMNLP 2022; arXiv 2205.12035) **[verified]**: asymmetric masked auto-encoding — full encoder, one-layer decoder, aggressive decoder-side masking (50–90%) so reconstruction must flow through the sentence embedding. Basis of the BGE family's pretraining. **RetroMAE-2** (Xiao et al., ACL 2023; arXiv 2305.02564) **[verified via API]** extends to duplex masked auto-encoding ([CLS] + token embeddings).
- **SimLM** (Wang et al., ACL 2023; arXiv 2207.02578) **[verified]**: representation-bottleneck pretraining with an ELECTRA-style replaced-LM objective; Microsoft's entry in the same design space. **LexMAE** (Shen et al., 2022; arXiv 2208.14754) **[verified via API]** is the lexicon-bottleneck analogue for learned-sparse retrieval.
- **Contrastive pretraining at scale**: **Contriever** (Izacard et al., 2021; arXiv 2112.09118; TMLR 2022) **[verified]** — unsupervised contrastive learning (independent-cropping positives, MoCo-style negatives) beating BM25 on 11/15 BEIR datasets; **E5** (Wang et al., 2022; arXiv 2212.03533) **[verified]** — weakly-supervised contrastive pretraining on CCPairs (curated, consistency-filtered web pairs) then supervised fine-tune; the two-stage "weak pairs → labeled pairs + hard negatives (+ optional distillation)" recipe that every open embedding family since has followed.
- **What open model reports reveal about data curricula**: **C-Pack/BGE** (Xiao et al., SIGIR 2024; arXiv 2309.07597) **[verified]** — RetroMAE pretrain → mass weak-pair contrastive → high-quality fine-tune with mined + denoised hard negatives; **Nomic-embed** (Nussbaum et al., 2024; arXiv 2402.01613) **[verified]** — the first fully open (weights+data+code) reproduction of this curriculum at 8k context; **Arctic-Embed** (Merrick et al., Snowflake, 2024; arXiv 2405.05374) **[verified — abstract; ablation details in body not fetched]** — a "recipe" paper whose headline is that dataset construction and negative mining, not architecture, explain its wins. The pattern across all cards: **the curriculum is the moat**; architectures are commodity.

### 4. Generative retrieval / differentiable search index: rise, stall, re-litigation

- **DSI** — *Transformer Memory as a Differentiable Search Index* (Tay et al., NeurIPS 2022; arXiv 2202.06991) **[verified]**. Map queries directly to docids with a seq2seq model; the corpus lives in the parameters; no external index. Enormous conceptual appeal: retrieval becomes just another generation task, end-to-end differentiable with the rest of the LM.
- **SEAL** — *Autoregressive Search Engines: Generating Substrings as Document Identifiers* (Bevilacqua et al., NeurIPS 2022; arXiv 2204.10628) **[verified]**. Sidesteps arbitrary docids: generate corpus n-grams constrained by an FM-index; +10 points over established retrievers on KILT (paper's claim).
- **NCI** — *A Neural Corpus Indexer for Document Retrieval* (Wang et al., NeurIPS 2022; arXiv 2206.02743) **[verified]**. Semantic hierarchical docids, prefix-aware decoder, massive query-generation augmentation.
- **DSI-QG** (Zhuang et al., 2022; arXiv 2206.10128) **[verified]**. Diagnosis: DSI's indexing step (document text → docid) is distributionally mismatched with retrieval (query → docid); fix: index *generated queries* instead of documents. This finding quietly demoted "the model memorizes documents" to "the model memorizes a synthetic-query→id mapping" — i.e., GR ≈ a lossy, parameter-bound inversion of GPL.
- **DSI++** — *Updating Transformer Memory with New Documents* (Mehta et al., EMNLP 2023; arXiv 2212.09744) **[verified]**. Names the **index-update problem**: continually indexing new documents causes catastrophic forgetting of old docids; mitigations (flatter minima via SAM, generative replay of pseudo-queries) reduce but do not eliminate it. For any corpus that changes daily, this is the disqualifying cost: a dense index does an O(1) append; DSI does gradient updates over the whole model and still forgets.
- **The scale reckoning** — *How Does Generative Retrieval Scale to Millions of Passages?* (Pradeep et al., EMNLP 2023; arXiv 2305.11841) **[verified]**. First honest evaluation at MS MARCO scale (8.8M passages): synthetic queries are the only technique that matters; the architectural add-ons don't pay for their compute; scaling model parameters to 11B does **not** close the gap with dual encoders. "Scaling to millions of passages remains an important and unsolved challenge" — the sentence that effectively ended GR's claim to be a first-stage web-scale retriever, redirecting the technique to closed, mid-sized, slowly-changing corpora and to recommendation (semantic IDs — a thriving separate lineage, e.g. arXiv 2506.16683 **[listing-only]**).
- **Survey**: *From Matching to Generation: A Survey on Generative Information Retrieval* (Li et al., 2024; arXiv 2404.14851) **[verified]** — consolidates docid design, training, and dynamic-corpora threads.
- **The 2025–26 LIMIT re-litigation.** The LIMIT paper (*On the Theoretical Limitations of Embedding-Based Retrieval*, Weller et al., Google DeepMind, 2025; arXiv 2508.21038) **[verified]** proved single-vector retrieval has a dimension-bounded ceiling on representable top-k subsets. GR, with global normalization over docids and no fixed-rank score matrix, is a candidate escape hatch, producing a reaction literature:
  - *Does Generative Retrieval Overcome the Limitations of Dense Retrieval?* (Zhang et al., 2025; arXiv 2509.22116) **[verified]**: theory — GR's global normalization avoids DR's optimization drift on large corpora, and its capacity scales with parameters, unconstrained by the low-rank structure that binds dual encoders; empirics — GR still does *not* consistently beat DR in practice on NQ/MS MARCO.
  - *Generative Retrieval Overcomes Limitations of Dense Retrieval but Struggles with Identifier Ambiguity* (Bracher et al., 2026; arXiv 2604.05764) **[verified]**: on LIMIT, SEAL/MINDER hit 0.92–0.99 R@2 where dense embedders collapse — but adding hard negatives drops GR to ~0.51 R@2, traced to the decoder's inability to emit identifiers unique to relevant documents ("identifier ambiguity"). GR escapes the geometric ceiling and hits a decoding-precision ceiling instead.
  - Continual-GR work continues: *A Parametric Memory Head for Continual Generative Retrieval* (Mekonnen et al., 2026; arXiv 2604.23388) **[listing-only]**; production hybrids: EGR (arXiv 2607.23038) **[listing-only]**.

### 5. Query performance prediction: two decades of the thing RAG keeps reinventing

- **Classical pre-retrieval predictors** — query statistics computed *before* running the query: IDF/ICTF aggregates, query scope, term ambiguity (He & Ounis, ~2004–06; Hauff et al., CIKM 2008 survey) **[classical — cited from field knowledge, not re-fetched]**. Cheap, weakly correlated with performance, but exactly the signal an agent needs *before* deciding to retrieve.
- **Classical post-retrieval predictors** — computed from the retrieved list: **Clarity** (Cronen-Townsend, Zhou & Croft, SIGIR 2002 — KL divergence between the top-k language model and the corpus model), **WIG** (Zhou & Croft, SIGIR 2007 — weighted information gain of top docs over the corpus), **NQC** (Shtok, Kurland et al., TOIS 2012 — normalized standard deviation of top-k retrieval scores; high score variance ⇒ confident head ⇒ good query) **[all classical — cited from field knowledge, not re-fetched]**. NQC's insight — *score-distribution shape predicts quality* — is precisely what 2024–26 RAG systems reinvent as "retrieval confidence."
- **Supervised/neural QPP (2019–2023)**: Deep-QPP (Datta et al., 2022; arXiv 2202.07376) **[verified via API listing]**; groupwise BERT QPP (Chen et al., 2022; arXiv 2204.11489) **[listing-only]**; QPP for conversational search (Meng et al., 2023; arXiv 2305.10923) **[listing-only]**; coherence predictors for *dense* retrieval (Vlachou & Macdonald, 2023; arXiv 2310.11405) **[listing-only]**; evaluation-methodology critiques (pointwise vs. correlation evaluation — Datta et al., arXiv 2304.00310; variance analyses — Ganguly et al., arXiv 2202.06306) **[listing-only]**.
- **The sobering result**: *Query Performance Prediction for Neural IR: Are We There Yet?* (Faggioli et al., ECIR 2023; arXiv 2302.09947) **[verified]** — across 14 QPP methods, predictors are statistically significantly *worse* on neural/dense systems than on lexical ones, and fail hardest exactly where neural systems diverge from BM25. Follow-up: *Uncovering the Limitations of QPP* (Chifu et al., 2025; arXiv 2504.01101) **[verified via API listing]** — QPP fails to generalize across collections and retrieval architectures, undermining selective query processing.
- **QPP meets RAG (2024–2026)** — the convergence this dossier exists to flag:
  - **QPP-GenRE** (Meng et al., ACM TOIS 2025; arXiv 2404.01012) **[verified]**: decompose QPP into per-item relevance judgments generated by a fine-tuned open LLM → predict any IR metric, interpretably. QPP absorbed the LLM-judge toolkit.
  - *Am I on the Right Track?* (Tian et al., 2025; arXiv 2507.10411) **[verified]**: applies QPP inside agentic RAG (Search-R1, R1-Searcher): QPP estimates of agent-generated queries correlate positively with final answer quality — direct evidence QPP can steer an agent's search behaviour mid-trajectory.
  - *Predicting Retrieval Utility and Answer Quality in RAG* (Tian et al., 2026; arXiv 2601.14546) **[listing-only]**; **OpenDecoder** (Mo et al., 2026; arXiv 2601.09028) **[listing-only]** — feeds QPP scores into LLM decoding; *Can QPP Choose the Right Query Variant?* (Arabzadeh et al., 2026; arXiv 2604.22661) **[listing-only]** — QPP as the selector over query rewrites, replacing execute-and-compare; QPP-evaluation reform (Santra et al., 2026; arXiv 2601.17339, 2601.17359) **[listing-only]**.

### 6. Corpus & datastore as a first-class research object

- **MassiveDS** — *Scaling Retrieval-Based Language Models with a Trillion-Token Datastore* (Shao et al., NeurIPS 2024; arXiv 2407.12854) **[verified]**. 1.4T-token open datastore; datastore size scales downstream performance **monotonically, without observed saturation**; a small LM + big datastore beats a bigger LM without one at equal training compute. Establishes the datastore as a third scaling axis beside parameters and pretraining tokens.
- **CompactDS** — *Frustratingly Simple Retrieval Improves Challenging, Reasoning-Intensive Benchmarks* (Lyu et al., 2025; arXiv 2507.01297) **[verified via API listing]**: a curated web-scale datastore + minimal RAG pipeline improving even reasoning-heavy benchmarks (MMLU-Pro/GPQA-class) — curation quality substituting for pipeline complexity.
- **Retrieval scaling laws**: *Scaling Laws for Dense Retrieval* (Fang et al., SIGIR 2024 — best paper per community reports [uncertain]; arXiv 2403.18684) **[verified via API listing]** — power-law fits of retrieval quality in model size × annotation volume, enabling budget allocation between data and parameters; *Scaling Laws for Embedding Dimension in IR* (Killingback et al., 2026; arXiv 2602.05062) **[listing-only]**.
- **Semantic dedup** — **SemDeDup** (Abbas et al., 2023; arXiv 2303.09540) **[verified]**: embed, cluster, drop semantic near-duplicates; removing ~50% of LAION with minimal loss, faster training, better OOD performance. Written for *training* data but directly transplantable to *retrieval corpora*, where near-duplicates waste top-k slots and skew nearest-neighbor geometry; sibling-dossier chunking work confirms duplication is a top production complaint. [Transplantation to RAG datastores is practice/inference, not a claim of the paper.]
- **Corpus composition → RAG quality**: *The Power of Noise* (Cuconasu et al., SIGIR 2024; arXiv 2401.14887) **[verified]** — high-scoring-but-irrelevant retrieved documents actively hurt the reader, while *random* documents can improve accuracy (paper reports up to +35%) — retrieval score and reader utility are not the same axis; **RAGGED** (Hsia et al., 2024/2025; arXiv 2403.09040) **[verified]** — across configurations, *reader robustness to retrieved noise*, not retriever/reranker choice, is the key determinant of RAG stability; *RAG in the Wild* (Xu et al., 2025; arXiv 2507.20059) **[listing-only]** — mixture-of-knowledge datastores expose routing/effectiveness failures.
- **Poisoning vs. curation**: *Poisoning Retrieval Corpora by Injecting Adversarial Passages* (Zhong et al., EMNLP 2023; arXiv 2310.19156) **[verified]** — ~50 HotFlip-optimized passages mislead dense retrievers across unseen queries and *out-of-domain* corpora; **PoisonedRAG** (Zou et al., USENIX Security 2025; arXiv 2402.07867) **[verified]** — 5 injected texts per target question ⇒ ~90% attack success against RAG over million-document stores; follow-on attack efficiency (AGGD, arXiv 2406.05087; embedding-space attacks in <2 min/document, arXiv 2504.17884; HotFlip reproduction/speedup, arXiv 2501.04802; Vec2Text-inversion threat analysis, arXiv 2410.06628) and 2025–26 defenses (RAGPart/RAGMask retrieval-stage defenses, arXiv 2512.24268; TRACE token-influence attribution, arXiv 2606.25721; RAGuard layered defense, arXiv 2607.26339; LLM-retriever robustness audit across 30 datasets, arXiv 2604.16576) **[all listing-only]**. The asymmetry is stark: attacks are cheap, transferable and query-agnostic; defenses are heuristic and evaluated on narrow threat models.

---

## State of the art (mid-2026)

**Retriever training.** The canonical open recipe is unchanged in shape since 2022, only scaled: (1) retrieval-oriented or general contrastive pretraining on weak pairs (RetroMAE/Condenser-style bottlenecks for BERT-class models; large decoder backbones skip this), (2) contrastive fine-tuning with mined hard negatives, false-negative filtering thresholded against the positive (NV-Retriever-style), staged curricula, and (3) distillation from a stronger judge — where the cross-encoder teacher of 2021 has been replaced by a frontier LLM generating both queries and relevance margins (GPL's design with a bigger generator). Data curriculum, not architecture, is the differentiator every open model report emphasizes (C-Pack, Nomic, Arctic-Embed).

**Generative retrieval.** Dead as a general web-scale first-stage retriever (Pradeep et al.'s scale result stands unrefuted at 100M+ document scale [no counterexample seen this session]); alive in three niches: (a) recommendation/semantic-ID systems, (b) closed mid-size corpora where constrained decoding over an FM-index (SEAL-style) is competitive, (c) as a *theoretical* foil to dense retrieval post-LIMIT — GR provably escapes the single-vector dimensional ceiling but empirically trades it for identifier-ambiguity and continual-indexing ceilings (Zhang 2509.22116; Bracher 2604.05764; DSI++ 2212.09744).

**QPP.** Classical predictors are established to transfer poorly to dense retrieval (Faggioli 2302.09947; Chifu 2504.01101), and the field's center of gravity has moved to (i) LLM-generated relevance judgments as the predictor (QPP-GenRE) and (ii) QPP as a *control signal inside RAG/agentic loops* — predicting retrieval utility and answer quality, selecting query variants, steering agent search (Tian 2507.10411, 2601.14546; Arabzadeh 2604.22661; Mo 2601.09028). Evaluation methodology is itself being reformed (Santra 2601.17339/17359) because correlation-with-AP was never the downstream-relevant target.

**Corpus/datastore.** The datastore is now an acknowledged scaling axis (MassiveDS) with early scaling-law treatments; curation (CompactDS) demonstrably substitutes for pipeline complexity; composition studies (Power of Noise, RAGGED) show reader-side noise-robustness dominates retriever choice; and the poisoning literature has raced ahead of the defense literature. What does **not** yet exist [as of this session's coverage]: a unified account of corpus quality — dedup level, freshness, provenance, poisoning exposure — as a *predictable* input to RAG quality, i.e., "corpus performance prediction" as a sibling of QPP.

---

## Thematic deep-dives

### A timeline of the training canon

| Year | Negatives | Distillation | Pretraining | Supervision source |
|---|---|---|---|---|
| 2020 | in-batch (DPR) → ANN-mined, async refresh (ANCE) | Margin-MSE from cross-encoder ensembles | generic MLM | MS MARCO / NQ labels |
| 2021 | cross-batch + cross-encoder-denoised (RocketQA); dynamic query-side (ADORE); topic-balanced batches (TAS-B) | joint retriever–reranker (RocketQAv2) | Condenser/coCondenser bottlenecks | + cross-encoder pseudo-labels |
| 2022 | curriculum-scheduled distillation data (CL-DRD) | listwise distributions | RetroMAE, SimLM, LexMAE; unsupervised contrastive (Contriever) | + T5-generated queries (GPL), CCPairs weak pairs (E5) |
| 2023–24 | staged mining in model-report curricula (BGE, Nomic, Arctic) | LLM-as-teacher variants | largely dropped for decoder backbones | + frontier-LLM synthetic triples |
| 2024–26 | positive-anchored false-negative filtering (NV-Retriever) | LLM feedback loops (FiGRet-class) | — | predominantly LLM-synthesized |

Reading down any column shows the same phenomenon: mechanisms churn, but the *problem* each column addresses (sparse labels → polluted negatives → need for a judge → need for free supervision) is constant. That constancy is the strongest evidence the problems are data-structural, not method-shaped.

### The recipe canon, compressed (what a framework designer must internalize)

1. **Supervision is the bottleneck, permanently.** MS MARCO's ~1-judgment-per-query sparsity forced the entire hard-negative/denoising/distillation apparatus into existence. Modern LLM-synthesized supervision changes the *cost* of labels, not the pooling-bias structure: the LLM teacher is the new pooling.
2. **Every mined negative is Schrödinger's positive.** RocketQA (2021) and NV-Retriever (2024) are the same paper three years apart. Any system that fine-tunes retrievers online (e.g., from agent feedback) will re-encounter this within weeks.
3. **Distillation topology is stable**: expensive judge → cheap retriever. What changed is judge identity (BERT cross-encoder → LLM) and signal shape (margins → listwise distributions → generated judgments). A next-gen framework should treat "judge" as a first-class, swappable, *auditable* component.
4. **Bottleneck pretraining bought 1–3 nDCG points in 2021–23 and then was largely obsoleted** by scale + data curricula on decoder backbones — a cautionary tale about architecture-shaped solutions to data-shaped problems.
5. **Curricula are real but folkloric**: every model card describes stages (weak pairs → curated pairs → hard negatives), no paper isolates *why* stage ordering matters with the rigor of, say, the STAR/ADORE analysis. Curriculum design remains alchemy.

### Why generative retrieval stalled — a post-mortem

Worth spelling out, because "GR failed" is often asserted without mechanism, and because the 2025–26 revival papers only make sense against the specific failure anatomy:

1. **The memorization framing was a category error.** DSI's pitch — "the corpus lives in the parameters" — collided immediately with DSI-QG's finding (arXiv 2206.10128) that indexing raw documents is distributionally wrong and you must index *generated queries* instead. At that point GR is no longer "a differentiable index"; it is a seq2seq model memorizing a synthetic-query→docid lookup table, with capacity, not geometry, as the binding constraint.
2. **Scale broke it exactly where dense retrieval gets easy.** Pradeep et al. (arXiv 2305.11841): at 8.8M passages, none of the architectural innovations (semantic docids, prefix-aware decoding, etc.) survived a compute-matched comparison, and an 11B GR model still trailed dual encoders. Dense retrieval amortizes corpus growth into an ANN index (sub-linear query cost, O(1) appends); GR amortizes it into gradient updates (training cost linear-or-worse in corpus size, and see next point).
3. **The index-update problem is structural, not incidental.** DSI++ (arXiv 2212.09744) showed continual indexing causes catastrophic forgetting of earlier docids; the mitigations (flat-minima optimization, generative replay) are the standard continual-learning toolkit, which is to say: partial. Any agentic memory store — which mutates every session — is the worst-case workload for this paradigm.
4. **Constrained decoding was the survivable part.** SEAL's FM-index-constrained substring generation avoided arbitrary docids and remains competitive on closed corpora (KILT); it is telling that the GR components that survived into 2026 production systems are the ones closest to *classical index structures steered by an LM*, not parameter-bound memory.
5. **The LIMIT revival is a theory result, not a comeback.** Zhang et al. (arXiv 2509.22116) formalize real advantages — global normalization over docids avoids the dual-encoder low-rank ceiling — and Bracher et al. (arXiv 2604.05764) confirm GR aces LIMIT's construction (0.92–0.99 R@2) where embedders collapse. But hard negatives expose *identifier ambiguity* (0.51 R@2): the decoder cannot reliably emit ids unique to relevant documents. Net: GR is now best understood as evidence about *what representation ceilings exist*, guiding hybrid design, rather than as a deployable first stage.

**Framework moral:** the durable idea from five years of GR is *LM-steered traversal of a classical index* (constrained decoding over FM-indexes/tries, semantic IDs over small stable vocabularies) — not parametric corpora.

### QPP: the missing control theory of RAG

The convergence to watch: agentic RAG's core control decisions are QPP problems, and the QPP field has already published the null results the RAG community is about to rediscover.

| Agentic-RAG decision | QPP name for it | Known-good signals | Known failure |
|---|---|---|---|
| "Should I retrieve at all?" | pre-retrieval QPP | IDF/scope/ambiguity statistics [classical] | weak correlations; corpus-dependent |
| "Did that retrieval work?" | post-retrieval QPP | NQC score-variance, WIG, Clarity [classical]; coherence for dense (arXiv 2310.11405) | degrades significantly on neural systems (Faggioli, arXiv 2302.09947) |
| "Which query rewrite should I issue?" | QPP-guided variant selection | arXiv 2604.22661, 2604.27244 | evaluation reform still pending (arXiv 2601.17339) |
| "Should I stop searching / answer now?" | QPP inside agent loops | QPP–answer-quality correlation shown for Search-R1-class agents (arXiv 2507.10411) | early; single-family evidence |
| "How much should the reader trust this context?" | utility prediction | LLM-generated judgments (QPP-GenRE, arXiv 2404.01012); OpenDecoder-style decode-time quality signals (arXiv 2601.09028) | cost; judge circularity |

Two structural lessons from the classical literature that transfer directly: (i) *score-distribution shape is informative* — NQC's variance signal predates and anticipates every "retrieval confidence from similarity scores" heuristic in production RAG; (ii) *correlation-with-ranking-metric is the wrong target* — QPP evaluation is moving to downstream decision quality (arXiv 2601.17339/17359), which is exactly the form an agentic framework needs (was the *decision* to re-query right, not was AP predicted).

### Corpus curation vs. poisoning: the economics

Put the two literatures side by side and the asymmetry becomes a design constraint:

- **Attack cost:** ~50 unsupervised adversarial passages compromise dense retrieval across *out-of-domain* corpora (Zhong, arXiv 2310.19156); 5 targeted texts per question ⇒ ~90% ASR against RAG over millions of documents (PoisonedRAG, arXiv 2402.07867); 2025-era attacks generate an adversarial document in under two minutes without query knowledge (arXiv 2504.17884).
- **Defense cost:** detectors and consensus schemes (RAGPart/RAGMask, TRACE, RAGuard — all 2025–26, all [listing-only]) run per-query or per-ingest, address specific attack families, and have no certified coverage.
- **Curation as implicit defense:** the curation line (SemDeDup dedup, CompactDS quality filtering, provenance-aware stores like SILO) was built for *quality*, not security, but the two converge: a datastore with provenance, dedup, and outlier telemetry is both higher-quality and harder to poison. No paper seen this session unifies these two framings; that unification is a genuinely open (and cheap-to-claim) research position for a next-gen framework paper.
- **The self-poisoning corollary:** agentic systems that write summaries/memories back into their own datastore create an *internal* poisoning channel with no adversary needed — hallucinated writes are structurally identical to injected passages. The poisoning literature's detection machinery (influence attribution, consistency screens) is the right toolkit, unapplied so far [inference; no paper seen this session addresses self-poisoning directly].

---

## Failure modes & critiques

1. **Benchmark monoculture at the training layer.** Nearly the entire hard-negative/distillation canon was developed on MS MARCO + NQ; Margin-MSE teacher files and BEIR checkpoints propagated one supervision distribution into hundreds of downstream models. Contamination and label-bias critiques usually target *evaluation*; the deeper issue documented here is that the *training practice itself* is fitted to two 2019-era query distributions.
2. **False-negative denoising is circular.** The cross-encoder (or LLM) that filters negatives was itself trained on the sparse labels whose gaps it is supposed to fix. No result seen this session breaks this circularity; NV-Retriever's positive-anchored threshold is a heuristic patch.
3. **The synthetic-query flywheel launders teacher bias.** GPL → Gecko/E5-Mistral-style pipelines mean retrievers increasingly learn "what an LLM thinks a query for this passage looks like." Distribution shift to real agentic queries (multi-constraint, negation, tool-shaped) is unmeasured by construction, and LIMIT-style compositional failures are plausibly *amplified* by training on LLM-typical queries. [Inference from verified sources, flagged as analysis.]
4. **GR's three ceilings.** (a) Scale: no path past ~10M passages without synthetic-query indexing whose cost grows with the corpus (Pradeep 2305.11841); (b) dynamism: catastrophic forgetting under continual indexing — the index-update problem (DSI++); (c) precision: identifier ambiguity under hard negatives even where GR beats dense on LIMIT (Bracher 2604.05764). GR traded the geometry problem for a memorization problem.
5. **QPP does not transfer to the systems that need it.** Predictors were designed for lexical score distributions; on dense/neural systems they degrade significantly (Faggioli) and fail across collections/architectures (Chifu). Meanwhile RAG papers reinvent "retrieval confidence" without citing NQC/WIG/Clarity — wasting two decades of negative results about which signals *don't* work.
6. **Retrieval score ≠ reader utility.** Power of Noise: top-scoring irrelevant documents *harm* generation while random ones can help; RAGGED: reader noise-robustness, not retriever quality, governs system stability. The entire training canon in §1–3 optimizes ranking metrics that are, at best, loosely coupled to end-task utility — the deepest critique of retriever training practice in this file.
7. **Datastore scaling has no quality theory.** MassiveDS shows monotonic gains from *more* data and CompactDS shows gains from *better* data, but nothing predicts the interaction (when does adding tokens add duplicates, contradictions, or poison faster than knowledge?). SemDeDup-style dedup is tuned for training-loss efficiency, not retrieval-slot efficiency.
8. **Poisoning asymmetry.** ~50 unsupervised adversarial passages transfer across domains (Zhong); 5 targeted texts yield ~90% ASR against RAG (PoisonedRAG); 2025–26 attacks run in minutes per document. Defenses are post-hoc detectors on narrow threat models; no curation pipeline seen this session treats adversarial robustness as a first-class corpus-quality dimension alongside dedup and freshness.
9. **Verification gap in this dossier's own sources**: several 2026 items are API-listing-only; the Arctic-Embed ablation details and SIGIR-best-paper status of Fang et al. were not confirmed from primary text — treat marked items accordingly.

---

## Relevance to a next-generation agentic RAG framework

Concrete design implications, each traceable to the lineage above:

1. **Ship QPP as a first-class primitive, not a research afterthought.** An agent deciding *whether/what/where to retrieve* is doing pre-retrieval QPP; deciding *whether to trust results or re-query* is post-retrieval QPP. The framework should expose (a) cheap pre-retrieval predictors, (b) score-distribution predictors (NQC-style) over any retriever's output, (c) LLM-judgment predictors (QPP-GenRE-style) as a budgeted tier — and log predicted-vs-realized utility to close the loop. Evidence QPP steers agentic search already exists (Tian 2507.10411).
2. **Treat the datastore as a versioned, measurable artifact.** Datastore size is a scaling axis (MassiveDS); quality substitutes for pipeline complexity (CompactDS); duplication and poisoning are measurable hazards. The framework needs corpus telemetry: semantic-duplication rate (SemDeDup machinery repurposed), provenance/freshness metadata, injection-anomaly scores — i.e., invent "corpus performance prediction" deliberately instead of rediscovering it.
3. **Design for continual index update as the default, which rules GR out of the hot path.** DSI++ shows parameter-bound indexes forget; agentic memory churns continuously. Use external indexes for the mutable store; if GR-style components are used (semantic IDs for tool/memory routing over small stable vocabularies), constrain them to slowly-changing namespaces and budget for re-indexing.
4. **Make the teacher auditable and the negatives suspicious.** Any in-framework retriever fine-tuning (from agent trajectories, click-like signals) must ship with false-negative filtering (positive-anchored thresholds) and teacher-bias audits, or it will silently re-run the RocketQA failure on the user's own data.
5. **Optimize for reader utility, not rank metrics.** RAGGED and Power of Noise imply the framework's retrieval evaluation harness should score end-task answer quality under controlled noise injection — including the "does adding this document change the answer for the better" counterfactual — rather than nDCG proxies alone.
6. **Assume the corpus is partially adversarial.** Given PoisonedRAG-class ASRs, ingestion should include perplexity/embedding-outlier screens and retrieval should support k-partition/consensus schemes (RAGPart-style) natively; provenance-weighted retrieval is a curation defense the attack literature already motivates.
7. **Exploit the LIMIT lesson jointly with the GR lesson**: compositional/multi-constraint agent queries sit where single vectors provably fail and GR decodes ambiguously — the framework should route such queries to multi-vector/sparse/structured retrieval or decompose them, using pre-retrieval QPP as the router.

**A concrete component checklist this lineage implies for the framework paper:**

| Component | Grounding | What "next-generation" adds over current practice |
|---|---|---|
| Retrieval-confidence estimator (pre- & post-) | QPP literature §5; Tian 2507.10411 | shipped as a typed API on every retriever, logged against realized utility |
| Corpus telemetry & versioning | MassiveDS, CompactDS, SemDeDup | dedup rate / freshness / provenance / anomaly scores as queryable metadata |
| Online fine-tuning harness with negative hygiene | ANCE→NV-Retriever line | positive-anchored false-negative filters + teacher-audit reports by default |
| Utility-based eval harness | Power of Noise, RAGGED | counterfactual document-level utility, noise-injection stress tests |
| Poisoning screens (incl. self-writes) | Zhong, PoisonedRAG, RAGPart-class | ingest-time + memory-write-time screening as one mechanism |
| Query router across representation classes | LIMIT + GR post-mortem | QPP-driven, per-query, with decomposition fallback |

---

## Open problems

1. **Per-query routing with guarantees.** Unifying QPP with representation-class selection (dense vs. sparse vs. multi-vector vs. GR vs. SQL/structured) — Chifu shows current QPP can't even generalize across architectures; the router the field needs must.
2. **Corpus performance prediction.** No predictive theory maps (size, dedup level, freshness, domain mix, adversarial exposure) → RAG answer quality; MassiveDS/CompactDS/RAG-in-the-Wild are single points on an uncharacterized surface.
3. **Breaking the teacher circularity.** Supervision for retriever training that is not downstream of the same sparse pools or the same LLM family being evaluated — e.g., outcome-grounded labels from agent task success — remains unbuilt at scale.
4. **The index-update problem, generally.** Not just GR: embedding-model *upgrades* force full re-embedding of trillion-token stores (the economic cousin of DSI++'s forgetting). Incremental, backward-compatible index/embedding evolution is unsolved.
5. **Curriculum science.** Stage ordering, negative-hardness schedules, and synthetic-data mixing ratios drive frontier embedders but lack STAR/ADORE-grade theory; ablation-only knowledge does not transfer across scales.
6. **Poisoning-robust curation with certified bounds.** Current defenses are detectors; nothing offers even empirical worst-case guarantees for a datastore of given provenance mix — a prerequisite for agentic systems that write their own memories back into the store (self-poisoning risk).

---

## Bibliography

*Markers: [verified] = arXiv abstract page or API record with abstract fetched this session; [listing-only] = title+gist seen in arXiv API results only; [classical] = pre-arXiv-era canonical IR work cited from field knowledge. Peer-review status noted where known.*

### Dense-retriever training practice
- ANCE: *Approximate Nearest Neighbor Negative Contrastive Learning for Dense Text Retrieval* — Xiong et al. — arXiv 2007.00808 (ICLR 2021) — 2020. [verified]
- RocketQA — Qu et al. — arXiv 2010.08191 (NAACL 2021) — 2020. [verified]
- RocketQAv2 — Ren et al. — arXiv 2110.07367 (EMNLP 2021) — 2021. [verified]
- STAR/ADORE: *Optimizing Dense Retrieval Model Training with Hard Negatives* — Zhan et al. — arXiv 2104.08051 (SIGIR 2021) — 2021. [verified]
- Margin-MSE: *Improving Efficient Neural Ranking Models with Cross-Architecture Knowledge Distillation* — Hofstätter et al. — arXiv 2010.02666 (preprint) — 2020. [verified]
- TAS-B — Hofstätter et al. — arXiv 2104.06967 (SIGIR 2021) — 2021. [verified]
- CL-DRD: *Curriculum Learning for Dense Retrieval Distillation* — Zeng et al. — arXiv 2204.13679 (SIGIR 2022) — 2022. [verified via API]
- GPL — Wang et al. — arXiv 2112.07577 (NAACL 2022) — 2021. [verified]
- NV-Retriever — Moreira et al. — arXiv 2407.15831 (preprint) — 2024. [verified]
- FiGRet: LLM-feedback guidance for retrievers — Liu et al. — arXiv 2411.03957 — 2024. [listing-only]
- DPR — Karpukhin et al. — arXiv 2004.04906 (EMNLP 2020) — 2020. [classical; verified in sibling dossier]

### Retrieval-oriented & contrastive pretraining; model-report curricula
- Condenser — Gao & Callan — arXiv 2104.08253 (EMNLP 2021) — 2021. [verified]
- coCondenser — Gao & Callan — arXiv 2108.05540 (ACL 2022) — 2021. [verified]
- RetroMAE — Xiao et al. — arXiv 2205.12035 (EMNLP 2022) — 2022. [verified]
- RetroMAE-2 — Xiao et al. — arXiv 2305.02564 (ACL 2023) — 2023. [verified via API]
- SimLM — Wang et al. — arXiv 2207.02578 (ACL 2023) — 2022. [verified]
- LexMAE — Shen et al. — arXiv 2208.14754 — 2022. [verified via API]
- Contriever — Izacard et al. — arXiv 2112.09118 (TMLR 2022) — 2021. [verified]
- E5 — Wang et al. — arXiv 2212.03533 (preprint) — 2022. [verified]
- C-Pack / BGE — Xiao et al. — arXiv 2309.07597 (SIGIR 2024) — 2023. [verified]
- Nomic Embed — Nussbaum et al. — arXiv 2402.01613 (preprint) — 2024. [verified]
- Arctic-Embed — Merrick et al. — arXiv 2405.05374 (preprint) — 2024. [verified — abstract only]

### Generative retrieval / DSI
- DSI: *Transformer Memory as a Differentiable Search Index* — Tay et al. — arXiv 2202.06991 (NeurIPS 2022) — 2022. [verified]
- SEAL — Bevilacqua et al. — arXiv 2204.10628 (NeurIPS 2022) — 2022. [verified]
- NCI — Wang et al. — arXiv 2206.02743 (NeurIPS 2022) — 2022. [verified]
- DSI-QG — Zhuang et al. — arXiv 2206.10128 (preprint) — 2022. [verified]
- DSI++ — Mehta et al. — arXiv 2212.09744 (EMNLP 2023) — 2022. [verified]
- *How Does Generative Retrieval Scale to Millions of Passages?* — Pradeep et al. — arXiv 2305.11841 (EMNLP 2023) — 2023. [verified]
- GenIR survey: *From Matching to Generation* — Li et al. — arXiv 2404.14851 — 2024. [verified]
- *Does Generative Retrieval Overcome the Limitations of Dense Retrieval?* — Zhang et al. — arXiv 2509.22116 — 2025. [verified]
- *GR Overcomes Limitations of Dense Retrieval but Struggles with Identifier Ambiguity* — Bracher et al. — arXiv 2604.05764 — 2026. [verified]
- LIMIT: *On the Theoretical Limitations of Embedding-Based Retrieval* — Weller et al. — arXiv 2508.21038 — 2025. [verified]
- Continual GR memory head — Mekonnen et al. — arXiv 2604.23388 — 2026. [listing-only]
- EGR (production embedding-native GR) — Liu et al. — arXiv 2607.23038 — 2026. [listing-only]
- Business-value docids for GR — Ling et al. — arXiv 2607.11392 — 2026. [listing-only]
- Contrastive item tokenization (gen. recommendation) — Zhai et al. — arXiv 2506.16683 — 2025. [listing-only]

### Query performance prediction
- Clarity — Cronen-Townsend, Zhou & Croft — SIGIR 2002. [classical]
- WIG — Zhou & Croft — SIGIR 2007. [classical]
- NQC — Shtok, Kurland et al. — ACM TOIS 2012. [classical]
- Pre-retrieval predictors — He & Ounis (2004–06); survey: Hauff et al., CIKM 2008. [classical]
- Deep-QPP — Datta et al. — arXiv 2202.07376 (WSDM 2022) — 2022. [verified via API]
- Groupwise BERT QPP — Chen et al. — arXiv 2204.11489 — 2022. [listing-only]
- *QPP for Neural IR: Are We There Yet?* — Faggioli et al. — arXiv 2302.09947 (ECIR 2023) — 2023. [verified]
- QPP ad-hoc→conversational — Meng et al. — arXiv 2305.10923 — 2023. [listing-only]
- Coherence predictors for dense retrieval — Vlachou et al. — arXiv 2310.11405 — 2023. [listing-only]
- Pointwise QPP evaluation — Datta et al. — arXiv 2304.00310 — 2023. [listing-only]
- QPP effectiveness variance — Ganguly et al. — arXiv 2202.06306 — 2022. [listing-only]
- QPP-GenRE — Meng et al. — arXiv 2404.01012 (ACM TOIS 2025) — 2024. [verified]
- *Uncovering the Limitations of QPP* — Chifu et al. — arXiv 2504.01101 — 2025. [verified via API]
- *Am I on the Right Track?* (QPP for agentic RAG) — Tian et al. — arXiv 2507.10411 — 2025. [verified]
- *Predicting Retrieval Utility and Answer Quality in RAG* — Tian et al. — arXiv 2601.14546 — 2026. [listing-only]
- OpenDecoder (QPP scores in decoding) — Mo et al. — arXiv 2601.09028 — 2026. [listing-only]
- QPP for query-variant selection in RAG — Arabzadeh et al. — arXiv 2604.22661 — 2026. [listing-only]
- QPP evaluation reform — Santra et al. — arXiv 2601.17339 & 2601.17359 — 2026. [listing-only]
- RAQG-QPP — Tian et al. — arXiv 2604.27244 — 2026. [listing-only]

### Corpus / datastore
- MassiveDS — Shao et al. — arXiv 2407.12854 (NeurIPS 2024) — 2024. [verified]
- CompactDS: *Frustratingly Simple Retrieval…* — Lyu et al. — arXiv 2507.01297 — 2025. [verified via API]
- *Scaling Laws for Dense Retrieval* — Fang et al. — arXiv 2403.18684 (SIGIR 2024) — 2024. [verified via API]
- Embedding-dimension scaling laws — Killingback et al. — arXiv 2602.05062 — 2026. [listing-only]
- SemDeDup — Abbas et al. — arXiv 2303.09540 (preprint) — 2023. [verified]
- *The Power of Noise* — Cuconasu et al. — arXiv 2401.14887 (SIGIR 2024) — 2024. [verified]
- RAGGED — Hsia et al. — arXiv 2403.09040 — 2024/25. [verified]
- *RAG in the Wild* — Xu et al. — arXiv 2507.20059 — 2025. [listing-only]
- SILO (datastore for legal-risk isolation) — Min et al. — arXiv 2308.04430 — 2023. [listing-only]
- kNN-MT (datastore lineage origin) — Khandelwal et al. — arXiv 2010.00710 (ICLR 2021) — 2020. [listing-only]

### Poisoning & defenses
- *Poisoning Retrieval Corpora by Injecting Adversarial Passages* — Zhong et al. — arXiv 2310.19156 (EMNLP 2023) — 2023. [verified]
- PoisonedRAG — Zou et al. — arXiv 2402.07867 (USENIX Security 2025) — 2024. [verified]
- AGGD — Su et al. — arXiv 2406.05087 — 2024. [listing-only]
- Vec2Text poisoning threat — Zhuang et al. — arXiv 2410.06628 — 2024. [listing-only]
- HotFlip reproduction/speedup — Li et al. — arXiv 2501.04802 — 2025. [listing-only]
- Embedding-space unsupervised poisoning — Li et al. — arXiv 2504.17884 — 2025. [listing-only]
- RAGPart/RAGMask — Pathmanathan et al. — arXiv 2512.24268 — 2025. [listing-only]
- TRACE (token influence attribution) — Chen et al. — arXiv 2606.25721 — 2026. [listing-only]
- RAGuard — Kumar et al. — arXiv 2607.26339 — 2026. [listing-only]
- LLM-retriever robustness audit — Li et al. — arXiv 2604.16576 — 2026. [listing-only]
