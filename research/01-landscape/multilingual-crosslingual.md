# Multilingual & Cross-Lingual Retrieval and RAG — Landscape Review (as of August 2026)

Research dossier for the "Reimagining RAG" project. Dimension: **multilingual and cross-lingual retrieval and RAG** — what happens to every layer of the RAG stack (tokenization, analyzers, embeddings, retrieval, reranking, generation, evaluation) when queries, corpora, and answers are not all in English. Emphasis on failure modes, critiques, and open problems, per project brief.

Citation hygiene: every source in the bibliography was seen in this research session, either as a fetched arXiv abstract page / documentation page (**verified**) or as an entry in an arXiv API listing whose abstract was not separately fetched (**[listing-only]**). Claims from author background knowledge that could not be verified this session are explicitly marked **[uncertain]**. Vendor-reported numbers are flagged as such. Note: this session's discovery relied on the arXiv API rather than general web search (search budget exhausted upstream), so grey-literature/production coverage leans on practitioner knowledge and is flagged accordingly.

---

## Scope

Covered here:

- **Benchmarks and datasets**: MKQA, TyDi QA lineage, Mr.TyDi, mMARCO, XOR-TyDi QA, AfriQA, MIRACL, NoMIRACL (and its relevance-assessment/hallucination findings), MIRAGE-Bench, XRAG, Futurepedia, BordIRLines, MMTEB, code-switching benchmarks (CSR-L/CS-MTEB, MiLQ).
- **Multilingual embedding models and their quality gaps**: BGE-M3, multilingual-E5, Arctic-Embed 2.0, Qwen3-Embedding; where quality actually collapses (low-resource languages, code-switching, cross-script matching, domain shift).
- **Cross-lingual RAG behavior**: retrieve-in-L1/answer-in-L2, language preference and "linguistic nepotism," language drift/collapse at decode time, code-switching artifacts.
- **Translation-based vs native multilingual pipelines** (translate-query, translate-document, Translate-Train, Translate-Distill, CrossRAG-style common-language pivoting).
- **Tokenization & analysis**: token-cost inequity across languages; CJK/RTL segmentation and analyzer failures in production search engines.
- **Evaluation**: non-English LLM-judge reliability (Hada et al., MM-Eval), MIRAGE-Bench's surrogate-judge design.
- **Multilingual hallucination in and around RAG**: NoMIRACL, realistic multilingual hallucination estimation.
- **Low-resource language retrieval**: AfriQA, CIRAL/African-language CLIR, XOR QA framing.
- **Production practice** for non-English corpora (search-engine analyzers, embedding-model selection, judge selection) — flagged where based on practitioner knowledge rather than fetched sources.

Out of scope (sibling dossiers): monolingual-English embedding internals, general evaluation methodology, agentic loop architectures, multimodal RAG, vector-database infrastructure.

Why this dimension matters for the paper: multilingual behavior is the single largest *silent* distribution shift in deployed RAG. Nearly every result in the mainstream landscape files was established on English data; the evidence below shows that many of those results simply do not transfer, and that the failure is distributed across *every* pipeline stage rather than localized in one component.

---

## Lineage & key work

### Phase 0 — Classical CLIR and multilingual QA datasets (pre-2021)

Cross-lingual IR (CLIR) long predates RAG: translate the query, translate the documents, or map both into a shared space. The neural era re-founded the field on new datasets:

- **MKQA** — Longpre et al. — arXiv:2007.15207 — 2020. 10k QA pairs aligned across **26 typologically diverse languages** (260k pairs total), with answers grounded in a curated language-independent representation so results are comparable across languages. Finding: "challenging even in English, but especially in low-resource languages." Limitation: answer-alignment via a language-independent representation biases toward entity/short answers and Western-centric Wikipedia-style knowledge.
- **TyDi QA** — Clark et al. — TACL 2020 — information-seeking QA in 11 typologically diverse languages, written natively (not translated), the substrate for most later multilingual retrieval benchmarks. [listing-only — cited via its role in the fetched Mr.TyDi and XOR QA abstracts]
- **XOR-TyDi QA (XOR QA)** — Asai et al. — NAACL-HLT 2021 — arXiv:2010.11856. Founded **cross-lingual open-retrieval QA**: 40k information-seeking questions in 7 non-English languages, built from TyDi QA questions that had *no same-language answer* — explicitly modeling **information scarcity** (the L1 web is too small) and **information asymmetry** (the concept is documented in another language). Three task variants over multilingual and English resources. This is the canonical formulation of "retrieve in L2, answer in L1."

### Phase 1 — Multilingual dense retrieval benchmarks (2021–2023)

- **Mr.TyDi** — Zhang et al. — MRL Workshop @ EMNLP 2021 — arXiv:2108.08787. Monolingual retrieval in 11 typologically diverse languages. Key sobering finding: multilingual DPR (mDPR) effectiveness "is much lower than BM25" although dense signals help in hybrid — i.e., as of 2021, *lexical BM25 beat dense retrieval outside English*, the inverse of the English narrative of the time.
- **mMARCO** — Bonifacio et al. — arXiv:2108.13897 — 2021/2022. MS MARCO machine-translated into 13 languages. Models trained on translated data beat English-only training zero-shot on Mr.TyDi, and retrieval effectiveness correlated positively with translation quality. Limitation: "translationese" training data — queries and passages carry MT artifacts, and the benchmark inherits MS MARCO's shallow, sparse relevance judgments in every language.
- **MIRACL** — Zhang, Thakur et al. — TACL / WSDM 2023 Cup — arXiv:2210.09984 — 2022. The reference multilingual retrieval benchmark: **18 languages (>3B native speakers), ~77k queries, >700k relevance judgments over Wikipedia, annotated by native speakers**. Deliberately spans high- and low-resource typologies. Limitations: Wikipedia-only corpora (masks domain shift), monolingual task formulation (query and corpus same language), and — as later NoMIRACL work showed — the "first-stage retrieval is solved" assumption it encouraged is false for the non-relevant case.
- **AfriQA** — Ogundepo et al. — arXiv:2305.06897 — 2023. First cross-lingual open-retrieval QA dataset for **10 African languages** (12k+ examples), for languages where cross-lingual retrieval is the *only* viable option because in-language digital content barely exists. Finding: automatic translation and multilingual dense retrieval both performed inadequately; SOTA QA models struggle. This is the strongest existing evidence that "multilingual" models are effectively *high-resource-multilingual* models.
- **Translate-Train → Translate-Distill for CLIR** — Yang et al. — ECIR 2024 — arXiv:2401.04810. Distills a (mono- or multilingual) cross-encoder teacher into a CLIR dual-encoder student via translation, letting the teacher run in its optimal language setting while the student trains directly for cross-language retrieval. Also: HLTCOE's extension of Translate-Train ColBERT-X to African-language CLIR at FIRE 2023 (arXiv:2404.08134, Yang et al.) [listing-only]. Critique: the whole line depends on MT quality in exactly the languages where MT is weakest.

### Phase 2 — Multilingual embeddings mature (2024–2025)

- **BGE M3-Embedding** — Chen et al. (BAAI) — arXiv:2402.03216 — 2024. "Multi-Linguality, Multi-Functionality, Multi-Granularity": 100+ languages, simultaneous dense / sparse / multi-vector retrieval from one model, 8,192-token inputs, self-knowledge-distillation across the three retrieval heads. De facto open-weight default for multilingual RAG through 2025.
- **Multilingual-E5** — Wang et al. (Microsoft) — arXiv:2402.05672 — 2024. Contrastive pre-training on ~1B multilingual text pairs + labeled fine-tuning; the instruction-tuned variant matches English-only SOTA of similar size. Later crowned by MMTEB (below) as the best *public* model overall at only 560M parameters — embarrassing several 7B-class competitors.
- **Arctic-Embed 2.0** — Yu et al. (Snowflake) — arXiv:2412.04506 — 2024. Explicitly targets the **"multilingual tax"**: prior multilingual embedders degraded English quality; Arctic 2.0 claims competitive multilingual *and* English retrieval, plus MRL truncation. The framing itself is evidence that, through 2024, adding languages was empirically a trade-off, not free.
- **Qwen3-Embedding** — Zhang et al. (Alibaba) — arXiv:2506.05176 — 2025. 0.6B/4B/8B embedders + rerankers built on the Qwen3 backbone, LLM-synthesized multilingual training data, model-merging for robustness; SOTA on MTEB-multilingual and strong cross-lingual retrieval. Marks the shift to LLM-backbone embedders with *synthetic* multilingual supervision — with the attendant risk that synthetic data recycles the backbone's own language biases into the retriever.
- **MMTEB** — Enevoldsen et al. — ICLR 2025 — arXiv:2502.13595. Community-built expansion of MTEB: **500+ tasks, 250+ languages**. Headline reality check: multi-billion-parameter LLM embedders win on some subsets, but **multilingual-e5-large-instruct (560M) is the best-performing public model overall** — scale does not straightforwardly buy multilingual quality. Also contributes task-correlation-based downsampling so the benchmark is runnable. Critique: task quality and judgment depth are highly uneven across the long tail of languages; leaderboard aggregation can hide per-language collapse.

### Phase 3 — RAG goes multilingual, and its behavior gets audited (2023–2026)

- **NoMIRACL** — Thakur et al. — Findings of EMNLP 2024 — arXiv:2312.11361. Human-annotated **relevance-assessment** dataset in 18 languages with a *non-relevant* subset (top-k contains no answer) and a *relevant* subset. Findings: LLaMA-2/Orca-2 hallucinate an answer from irrelevant multilingual passages **>88%** of the time; conservative models (Mistral, LLaMA-3) instead wrongly abstain with **up to 74.9% error rate on the relevant subset**; GPT-4 merely best-balanced, not good. This is the key result that grounding failure in multilingual RAG is a *first-class, measured* phenomenon, not an anecdote.
- **mRAG baseline** — Chirkova et al. (Naver Labs Europe) — arXiv:2407.01463 — 2024. Builds a 13-language RAG pipeline and audits each component. Findings: even with good multilingual retrievers/generators, **task-specific prompt engineering is required just to make the model answer in the user's language**; standard metrics break on named-entity spelling variants; residual failures include **code-switching in non-Latin scripts, fluency loss, document misinterpretation, and retrieval errors**.
- **Futurepedia** — Wu et al. — arXiv:2410.21970 — 2024. Parallel-document benchmark across 8 languages isolating three inequalities: monolingual extraction (high-resource ≫ low-resource), cross-lingual transfer (Indo-European favored), and knowledge selection, where "**English speaks louder**": RALMs preferentially select English evidence in mixed-language contexts.
- **XRAG** — Liu et al. — arXiv:2505.10089 — 2025. Cross-lingual RAG benchmark from recent news (post-cutoff), monolingual and multilingual retrieval settings, with relevance annotations. Findings: in monolingual-retrieval/cross-lingual-answer settings, **all evaluated models struggle with response-language correctness**; in multilingual retrieval, the bottleneck is **reasoning across languages**, not non-English text generation.
- **Cross-lingual cost in enterprise corpora** — Amiraz et al. — ArabicNLP 2025 — arXiv:2507.07543. On real corporate Arabic–English corpora (not Wikipedia), **retrieval is the bottleneck**: large drops whenever query language ≠ document language, traced to the retriever's inability to *rank across languages* (calibration, not recall). Simple mitigations — per-language balanced retrieval and query translation — recover much of the loss. Important critique of Wikipedia-centric benchmarks, which mask this via pretraining overlap.
- **Linguistic Nepotism** — Ki et al. — ICML 2026 (Spotlight) — arXiv:2509.13930. Controlled mechanistic study across 8 languages / 6 open-weight models: with relevance held constant, **models preferentially cite English sources when queried in English, amplified for lower-resource languages and mid-context documents, sometimes trading relevance for language** — i.e., language preference is a *citation-behavior bias measurable in model internals*, not just a retrieval artifact.
- **Language Drift + Soft Constrained Decoding** — Li et al. — arXiv:2511.09984 — 2025. Characterizes RAG **language drift**: with multilingual context, generation collapses into an unintended language (usually English), worse under CoT. Localizes the failure at the **decoder** (English as "semantic attractor" via dominant token distributions), not comprehension; proposes training-free soft constrained decoding penalizing non-target-language tokens.
- **Mitigation wave (2025–2026)** [all listing-only]: DKM-RAG (Park et al., arXiv:2502.11175) and DELTA (Park et al., arXiv:2601.02956) — translated-passage fusion and debiased query fusion against language preference; CrossRAG (Ranaldi et al., arXiv:2504.03616) — translate all retrieved docs into one pivot language before generation; QTT-RAG (Moon et al., arXiv:2510.23070) — attach translation-quality metadata instead of trusting translations; LAURA (Wang et al., arXiv:2604.20199, **verified abstract**) — reranker alignment to downstream generative utility after showing rerankers systematically favor English + query-native documents; LAMAR (Hong et al., arXiv:2607.22042) — language-aware reranking; language-coupled RL for mRAG (Qi et al., arXiv:2601.14896) and teacher-regularized RL against drift in English-evidence cross-lingual RAG (Zhou et al., arXiv:2607.02966); CORAL (Lee et al., arXiv:2604.25676) — culturally-aligned adaptive retrieval; X-MADAM-RAG (Kang et al., arXiv:2606.12903) — diagnosing Chinese–English evidence conflict.

---

## State of the art (mid-2026)

- **Retrieval (monolingual per language)**: BGE-M3, multilingual-E5-large-instruct, Arctic-Embed 2.0, Qwen3-Embedding 8B, plus strong closed models, make *high-resource monolingual* retrieval roughly competitive with English. Hybrid dense+lexical remains the safe default; the Mr.TyDi-era "BM25 beats mDPR" gap has closed for high-resource languages but not for the long tail (AfriQA, MMTEB long-tail subsets).
- **Retrieval (cross-lingual)**: unsolved in domain-specific settings. Amiraz et al. show cross-language *ranking calibration* is the bottleneck; embedding-similarity scores are not comparable across languages, so a single ANN cut-off silently starves one language. Best current practice is embarrassingly non-neural: translate the query and/or enforce per-language quotas.
- **Generation**: response-language correctness is *still* not guaranteed (XRAG; Chirkova et al.); language drift under multilingual context is characterized and only partially mitigated (decoding constraints, RL). English evidence bias is now measured at the citation level (Linguistic Nepotism) and reranker level (LAURA).
- **Evaluation**: MIRAGE-Bench (Thakur et al., arXiv:2410.13716) provides an 18-language RAG arena using a learned surrogate judge over heuristic features; MM-Eval (Son et al., arXiv:2410.17578) shows LLM judges themselves degrade off-English. Net: the field can now *measure* multilingual RAG, but the measuring instruments (LLM judges) are known-biased in exactly the languages that need auditing most.
- **The stack-level picture**: every stage has a documented language-dependent failure — tokenizer (2–15× cost inflation), analyzer (CJK segmentation), embedder (long-tail collapse, code-switch fragility), retriever (cross-language calibration), reranker (English favoritism), generator (drift, nepotism, hallucination on irrelevant context), judge (score inflation off-English). No published framework treats language as a first-class routing/calibration variable across all stages. [uncertain — absence claim, based on this session's coverage]

---

## Benchmarks & datasets — what they actually measure

| Benchmark | Languages | Task shape | Key caveat |
|---|---|---|---|
| MKQA (2020) | 26 | open-domain QA, aligned answers | entity-biased answers; no in-language retrieval corpus |
| XOR-TyDi QA (2021) | 7 + En | cross-lingual open-retrieval QA | Wikipedia answers; English as the pivot resource |
| Mr.TyDi (2021) | 11 | monolingual dense retrieval | shallow judgments inherited from TyDi QA |
| mMARCO (2021) | 13 | passage ranking | machine-translated (translationese) queries and passages |
| AfriQA (2023) | 10 African | XOR QA | small; exposes rather than solves low-resource retrieval |
| MIRACL (2022) | 18 | monolingual retrieval, native judgments | Wikipedia-only; monolingual formulation |
| NoMIRACL (2023) | 18 | relevance assessment / abstention | binary answerable-or-not; doesn't score answer quality |
| MIRAGE-Bench (2024) | 18 | RAG arena, surrogate judge | judge trained on heuristic features; inherits judge bias |
| XRAG (2025) | several (news) | cross-lingual RAG, L(query)≠L(docs) | news domain; freshness decays |
| Futurepedia (2024) | 8 | parallel docs, controlled | synthetic "future" facts; artificial parallelism |
| MMTEB (2025) | 250+ | 500+ embedding tasks | uneven task quality in long tail |
| CSR-L / CS-MTEB (2026) | mixed/CS | code-switched retrieval | new; limited domain coverage |
| MiLQ (2025) | Ko-En focus | mixed-language queries | bilingual web search framing [listing-only] |

Structural critiques of the benchmark ecosystem:

1. **Wikipedia monoculture.** MIRACL, XOR-TyDi, MKQA, Futurepedia all sit on Wikipedia or Wikipedia-like text. Amiraz et al. demonstrate that this *specifically masks* the cross-lingual ranking failure that dominates enterprise corpora, because multilingual Wikipedia is heavily represented in pretraining and is topically parallel across languages.
2. **Monolingual task formulation.** MIRACL and MMTEB retrieval mostly evaluate query and corpus in the same language; the deployed reality (mixed-language corpora, cross-lingual needs, code-switched queries) is the setting where models fail hardest (CSR-L: up to 27% degradation; Amiraz et al.: "substantial" drops).
3. **Translationese contamination.** mMARCO-style MT-generated training/eval data rewards models for matching MT artifacts; mMARCO's own finding that retrieval quality tracks translation quality cuts both ways.
4. **Answerability blind spot.** Only NoMIRACL directly tests the non-relevant case per language — and the results (>88% hallucination for some models) suggest every multilingual RAG number computed on answerable-only benchmarks is an overestimate of deployed reliability.

---

## Multilingual embeddings — where quality actually collapses

Verified findings and well-supported generalizations:

- **The "multilingual tax" was real through 2024**: Arctic-Embed 2.0's stated design goal was avoiding the English-quality degradation that "plagued earlier approaches" — vendor framing, but consistent with MMTEB observations.
- **Scale ≠ multilingual quality**: MMTEB's best public model is a 560M-parameter encoder (multilingual-e5-large-instruct), beating multi-billion-parameter LLM embedders on aggregate. Rankings shift markedly per language subset — aggregate leaderboard position is a poor predictor of quality in *your* language. 
- **Long-tail collapse**: AfriQA shows multilingual dense retrieval "inadequate" for African languages; MKQA flags low-resource languages as the hardest slice. The ~100-language coverage claims of BGE-M3/mE5 mean *tokenizer coverage and some training data*, not uniform quality; quality falls off roughly with pretraining-data volume and script rarity. [partly uncertain — per-language curves not fetched this session]
- **Code-switching is an embedding-space failure**: CSR-L/CS-MTEB (Zeng et al., arXiv:2604.17632) measure up to **27% degradation** across sparse, dense, and late-interaction retrievers on code-switched queries, traced to "substantial divergence in embedding space between pure and code-switched text"; vocabulary expansion does not fix it. Earlier, Litschko et al. (arXiv:2305.05295) [listing-only] showed *training on artificially code-switched data* buys +5.1 MRR@10 in CLIR — a cheap mitigation few production embedders adopt.
- **Cross-lingual score incomparability**: the Amiraz et al. bottleneck — scores for L1-query/L1-doc vs L1-query/L2-doc pairs live on different scales, so top-k over a mixed corpus systematically under-retrieves cross-language evidence. This is a *calibration* failure invisible to per-language benchmarks.
- **Synthetic-data circularity risk** (Qwen3-Embedding and successors): embedders trained on LLM-synthesized multilingual pairs inherit the generator LLM's language distribution and biases; no published audit of this circularity was found this session. [uncertain — absence claim]

---

## Cross-lingual RAG behavior: preference, drift, code-switching

The 2024–2026 literature converges on a three-part behavioral pathology:

1. **Input-side language preference ("English speaks louder").** Futurepedia: RALMs select English evidence over equally-informative parallel evidence. LAURA paper: rerankers *systematically* favor English and query-native documents, suppressing decisive evidence in other languages. Linguistic Nepotism: citation attribution prefers English at constant relevance, worse for low-resource query languages and mid-context positions (a language-bias × lost-in-the-middle interaction).
2. **Output-side language drift.** Li et al.: decoder-level collapse toward English under multilingual context, aggravated by CoT — meaning *agentic* multi-step RAG, which reasons at length between retrievals, is structurally more exposed to drift than single-shot RAG. XRAG independently finds response-language correctness failures across all evaluated models. Chirkova et al. found even *getting the answer in the user's language* requires deliberate prompt engineering.
3. **Surface-level code-switching artifacts.** Chirkova et al.: frequent code-switching in non-Latin-script generation (Latin fragments embedded in e.g. Hindi/Russian/Thai output); named-entity script inconsistency breaks exact-match metrics. On the query side, real users code-switch (MiLQ, SwitchLingua, dziribot for Algerian Arabic [all listing-only]) and retrievers degrade on exactly those queries (CSR-L).

Interpretation for framework design: these are three *different* mechanisms (reranker scoring bias, decoder token-distribution collapse, tokenizer/script fragmentation) that current systems conflate under "multilingual is flaky." They require three different interventions — utility-aligned reranking, constrained/steered decoding, and script-aware normalization — none of which mainstream RAG frameworks expose as configuration.

---

## Translation-based vs native multilingual pipelines

The oldest CLIR question, still unresolved in 2026:

- **Translate-query**: cheap, effective when MT is good (Amiraz et al. recover most cross-lingual loss this way); fails silently on names, domain terms, and low-resource MT; adds latency and a second failure point.
- **Translate-document / pivot-language generation**: CrossRAG [listing-only] reports gains from translating all retrieved evidence into one language before generation — effectively conceding that the generator cannot reason multilingually (consistent with XRAG's finding that *cross-language reasoning*, not generation, is the bottleneck). Cost scales with corpus/context size; translation errors become uninspectable ground truth. QTT-RAG's response — attach translation-quality scores as metadata and let the generator weigh them — is the most framework-relevant idea here [listing-only].
- **Translate-train / translate-distill**: mMARCO and Translate-Distill show MT-generated supervision works surprisingly well for *training* retrievers, with quality tracking MT quality; this is now standard for building CLIR models where no native data exists.
- **Native multilingual end-to-end**: the aspiration of BGE-M3/mE5/Qwen3-class stacks. Works increasingly well for high-resource monolingual; the evidence above (drift, nepotism, calibration) shows it does *not* yet deliver reliable cross-lingual behavior without translation crutches.
- **The uncomfortable empirical summary**: for low-resource languages, a translation-centric cascade (e.g., the Bengali agricultural advisory case study, arXiv:2601.02065 [listing-only]) frequently beats "native" multilingual pipelines, at the cost of importing MT's own hallucinations and cultural flattening. Aman Gupta et al. (arXiv:2507.22923 [listing-only]) find the *placement* of translation in the prompt pipeline materially changes outcomes — an under-specified degree of freedom in every framework.

---

## Tokenization cost inequity and CJK/RTL analyzer failures

**Token inequity (verified):**

- Petrov et al. — NeurIPS 2023 — arXiv:2305.15425: same text, different languages → up to **15× tokenization-length difference**; even byte/character-level tokenizers show >4× for some pairs. Consequences: higher API cost, higher latency, and **reduced effective context window** for non-English users — which for RAG directly means *fewer retrieved passages fit* per request in Burmese or Amharic than in English.
- Ahia et al. — 2023 — arXiv:2305.13707 ("Do All Languages Cost the Same?"): across 22 languages on a commercial API, many language communities are simultaneously **overcharged and underserved** (more tokens, worse output), compounding affordability gaps.
- RAG-specific corollary (analysis, not a fetched source): every token-budgeted design decision in mainstream RAG — chunk size in tokens, top-k under a context budget, context-compression ratios, cost-based routing — silently encodes English tokenizer economics. A 512-token chunk of Tamil holds a fraction of the information of a 512-token English chunk; fixed-token chunking therefore fragments non-English documents more, degrading both embedding quality and answer grounding. [analysis]

**Analyzer/segmentation failures (production layer):**

- CJK languages have no whitespace word boundaries; lexical retrieval (BM25) depends entirely on the analyzer. Elasticsearch/Lucene require language-specific plugins — kuromoji for Japanese (verified against Elastic plugin docs, which cover little beyond installation), nori for Korean, smartcn for Chinese [uncertain — plugin names from practitioner knowledge; only kuromoji docs fetched]. Default/`standard` analyzers fall back to unigram/bigram CJK behavior, inflating false matches and destroying phrase semantics; dictionary-based segmenters fail on neologisms, product names, and compound nouns. [uncertain — practitioner knowledge]
- RTL scripts (Arabic, Hebrew) stress normalization (diacritics, orthographic variation, rich morphology): Arabic dialect orthography defeats exact lexical matching (dziribot [listing-only] reports handling Algerian-Arabic orthographic variation plus French code-switching as core difficulties). Morphologically rich languages (Turkish, Finnish) need stemming/lemmatization that BM25 defaults don't provide. [partly uncertain]
- Net effect: the *hybrid dense+sparse* recipe that sibling dossiers recommend as best practice quietly assumes a competent analyzer; in many non-English deployments the sparse leg is broken at the analyzer level and hybrid fusion just adds noise. [analysis]

---

## Evaluating multilingual RAG: the judge is also on trial

- **Hada et al.** — Findings of EACL 2024 — arXiv:2309.07462: GPT-4-as-judge, calibrated against 20k human judgments across 8 languages / 3 tasks, shows **systematic upward score bias**, diverging most from native-speaker judgment for low-resource and non-Latin-script languages. Conclusion: LLM judges cannot be deployed off-English without per-language human calibration.
- **MM-Eval** — Son et al. — arXiv:2410.17578 — 2024/2025: meta-evaluation across 5 subsets / 18 languages plus a 122-language Language Consistency subset; evaluator LLMs that excel in English have "considerable room for improvement" off-English and are *unfair and inconsistent* for lower-resource languages — including in absolute-score calibration, which is what most RAG eval harnesses (RAGAS-style 1–5 scoring) rely on.
- **MIRAGE-Bench** — Thakur et al. — arXiv:2410.13716: sidesteps per-query LLM judging by training a **surrogate judge** (learning-to-rank on heuristic RAG features) to produce an 18-language arena leaderboard; clever and cheap, but the surrogate inherits both the heuristics' blind spots and any bias in the bootstrap judgments.
- **Compounding effect** (analysis): multilingual RAG evaluations typically use an English-centric LLM to judge non-English answers grounded in non-English evidence — stacking judge bias on top of generator bias on top of retriever bias, with each layer biased *in the same direction* (favoring English/high-resource). Reported multilingual RAG quality is therefore likely overestimated, and cross-language comparisons are least trustworthy exactly where they matter. Serkan Ballı (arXiv:2607.13707 [listing-only]) documents a related structural failure in *synthetic* multilingual LLM-judge corpora (the test-oracle problem).

---

## Multilingual hallucination in RAG

- **NoMIRACL** (verified, detailed above): hallucination-on-irrelevant-context is the headline multilingual RAG failure — >88% for LLaMA-2/Orca-2 class models; the "fix" (conservatism) produces up to 74.9% false abstention. Neither failure mode is acceptable in deployment; per-language rates vary substantially [per-language breakdown not fetched — uncertain].
- **Islam et al.** — arXiv:2502.12769 — 2025/2026 ("How Much Do LLMs Hallucinate across Languages?"): 30 languages, 6 open model families, in-the-wild estimation. Counterintuitive findings: length-normalized hallucination rates are **uncorrelated with a language's digital footprint**, and **models with broader language support hallucinate more** — i.e., naively widening language coverage worsens per-language reliability. (Free-generation setting, not RAG-conditioned, but directly relevant to RAG fallback behavior when retrieval fails.)
- Detection is racing to catch up: MultiHaluDet (hidden-state probing, cross-resource-level transfer, arXiv:2605.24919), BenHalluEval for Bengali (arXiv:2605.31483), HalluScore for Arabic (arXiv:2605.17007) [all listing-only]. The pattern — new per-language hallucination benchmarks appearing monthly through 2026 — indicates the field does not believe English hallucination results transfer.

---

## What production systems do (and fail to do)

Flagged: this section leans on practitioner knowledge plus vendor-adjacent sources; the session's web-search budget precluded fetching engineering blogs. [uncertain applies broadly]

- **Common pattern 1 — pretend it's English**: one embedding model, one fixed-token chunker, English prompts, English LLM judge, `standard` analyzer. All failure modes above apply and none are monitored, because dashboards aggregate across languages.
- **Common pattern 2 — translate everything at the edge**: detect language → MT to English → English RAG → MT back. Robust for low-resource languages (cf. AfriQA, Bengali case study) but loses names/terminology, doubles latency/cost, and caps quality at MT quality; answer-language correctness is delegated to the last MT hop.
- **Common pattern 3 — per-language silos**: separate indices/analyzers per language with language-detection routing. Handles monolingual well; *structurally cannot* answer cross-lingual questions (the XOR QA scenario), which enterprise mixed-language corpora (Amiraz et al.'s setting) make common.
- Vendor embedding APIs advertise ~100-language support (Cohere embed-multilingual, OpenAI text-embedding-3 — OpenAI reported a large MIRACL jump over ada-002 [uncertain, vendor-reported, not fetched]); none publish per-language quality floors, cross-lingual score-calibration guarantees, or code-switching behavior.
- Almost no production stack implements: per-language retrieval quotas / cross-language score calibration (Amiraz et al.'s fix), language-constrained decoding (Li et al.), translation-quality metadata (QTT-RAG), or per-language judge calibration (Hada et al.). These are all published, cheap, and ignored — a framework-level packaging gap rather than a research gap. [analysis]

---

## Failure modes & critiques (consolidated)

1. **Cross-language score incalibration** — embedding similarity scores are not comparable across languages; mixed-corpus top-k starves cross-language evidence (Amiraz et al.). *Masked by Wikipedia benchmarks.*
2. **Reranker language favoritism** — rerankers suppress decisive non-English/non-query-language evidence (LAURA), independent of retriever recall.
3. **Generator linguistic nepotism** — citation/selection bias toward English at constant relevance, worst for low-resource queries and mid-context evidence (Ki et al.; Wu et al.).
4. **Decoder language drift** — output collapses into English under multilingual context, aggravated by CoT — a direct threat to agentic RAG loops (Li et al.; XRAG).
5. **Hallucination/abstention scissors** — >88% hallucination on irrelevant context vs up to 74.9% false abstention on relevant context; no model resolves both (NoMIRACL).
6. **Code-switch fragility** — up to 27% retrieval degradation on real mixed-language queries; embedding-space divergence not fixed by vocab expansion (CSR-L).
7. **Token-economics inequity** — up to 15× token inflation → cost, latency, and effective-context penalties baked into every token-budgeted RAG design decision (Petrov; Ahia).
8. **Analyzer breakage for CJK/RTL/morphologically-rich languages** — the sparse leg of "best-practice" hybrid retrieval silently fails without language-specific analysis. [partly uncertain]
9. **Judge unreliability off-English** — upward-biased, inconsistent, unfair for low-resource/non-Latin languages (Hada; MM-Eval); multilingual RAG metrics are systematically inflated.
10. **Benchmark monoculture** — Wikipedia-parallel, monolingual-formulated, answerable-only benchmarks overstate real-world multilingual readiness (critique synthesized from Amiraz, NoMIRACL, CSR-L).
11. **Low-resource cliff** — "100+ languages supported" ≠ usable quality; African-language retrieval remains inadequate (AfriQA); broader language support correlates with *more* hallucination (Islam et al.).
12. **Mitigations exist but are unpackaged** — balanced retrieval, query translation, constrained decoding, utility-aligned reranking, translation-quality tagging, judge calibration are all published point solutions with no framework integration. 

---

## Relevance to a next-generation agentic RAG framework

Concrete design implications, each traceable to evidence above:

1. **Language as a first-class pipeline variable.** The framework should carry `(query_language, evidence_language(s), answer_language)` as explicit, inspectable state through every stage — enabling per-stage policies instead of today's implicit "hope the model copes." XOR QA / XRAG define the target contract: *answer language is a user-specified invariant, independent of evidence language.*
2. **Calibrated cross-language retrieval.** Never rank raw similarity scores across languages. Support per-language score normalization, per-language quotas / balanced retrieval, and optional query translation as declarative retrieval policies (direct productization of Amiraz et al.).
3. **Utility-aligned, language-debiased reranking.** Adopt LAURA-style reranker alignment or at minimum expose language-composition diagnostics of the reranked set, so English favoritism is visible before generation.
4. **Decode-time language guards.** Ship language-identification on generated output with soft constrained decoding or regenerate-on-drift (Li et al.) as a built-in guardrail — especially inside agentic loops, where CoT amplifies drift.
5. **Answerability gating per language.** NoMIRACL demonstrates that "no relevant evidence" handling must be an explicit, per-language-tuned component (the hallucination/abstention operating point differs by model and language), not an emergent LLM behavior.
6. **Translation as a managed, quality-tagged operation.** When translation is used (query, document, or pivot), attach MT-quality metadata to the context (QTT-RAG pattern) so the generator and the audit trail can discount low-quality translations; make translation placement (where in the pipeline) configurable, since it measurably matters (Gupta et al.).
7. **Language-aware chunking and budgeting.** Token budgets, chunk sizes, and cost models must be computed in language-normalized units (e.g., characters/information density or per-language token multipliers), or low-token-efficiency languages get systematically fewer, more-fragmented evidence passages (Petrov; Ahia).
8. **Analyzer competence checks.** For hybrid retrieval, the framework should verify (or provision) language-appropriate analyzers for the sparse index and degrade to dense-only with a warning otherwise — turning a silent failure into a configuration error.
9. **Per-language evaluation with calibrated judges.** Reported metrics must be per-language, never aggregate-only (MMTEB lesson); LLM-judge scores off-English require calibration offsets or native-judge validation (Hada; MM-Eval); MIRAGE-Bench-style surrogate judging is a cost-effective monitoring pattern worth building in.
10. **Code-switch robustness as a test surface.** Include code-switched query perturbation (CSR-L-style) in the framework's built-in evaluation harness; consider code-switched hard negatives when fine-tuning retrievers (Litschko et al.).
11. **Agentic-specific risk**: an agent that plans in English (as most do) will formulate English sub-queries against non-English corpora, importing the entire cross-lingual failure stack *even for monolingual non-English deployments*. Sub-query language selection should be an explicit agent action with a policy, not a side effect of the planning language. [analysis grounded in drift + nepotism evidence]

---

## Open problems

1. **Cross-language relevance calibration.** No principled method makes dense scores comparable across languages in one index; balanced retrieval is a quota hack. Is calibration achievable in the embedding geometry itself, or does it require learned per-language-pair transforms?
2. **Reasoning across languages.** XRAG isolates cross-language *synthesis* (not generation) as the bottleneck; there is no training recipe or architecture demonstrated to close it. Does pivot-translation (CrossRAG) remain the ceiling?
3. **The hallucination–abstention frontier per language.** NoMIRACL defines the trade-off but no work characterizes (let alone optimizes) the per-language Pareto frontier, or how retrieval-quality signals should shift the operating point.
4. **Fair tokenization vs installed base.** Petrov et al.'s call for multilingually fair tokenizers conflicts with frozen production models; can serving-layer remedies (language-normalized pricing/budgeting, compression) restore equity without retraining?
5. **Judge calibration transfer.** Per-language human calibration (Hada) doesn't scale to 100+ languages; MM-Eval measures the problem. Can calibration learned on 10 languages transfer to the long tail — and how would we know, given the same judges validate the transfer?
6. **Low-resource retrieval beyond translation.** AfriQA shows both native multilingual and MT pipelines inadequate; whether synthetic-data flywheels (Qwen3-style) help or merely launder high-resource bias into low-resource retrievers is untested. The circularity of LLM-synthesized multilingual training data has no published audit. [uncertain — absence claim]
7. **Language dynamics in agentic loops.** Drift, nepotism, and token inequity have only been studied in single-shot RAG; their compounding over multi-step agent trajectories (each step re-encoding, re-retrieving, re-summarizing) is unmeasured. A multilingual BrowseComp/GAIA equivalent does not exist. [uncertain — absence claim]
8. **Mixed-language corpora as the default.** Benchmarks assume language-pure corpora; enterprises have code-switched documents, bilingual glossaries, translated near-duplicates (evidence-conflict across translations — X-MADAM-RAG is an early probe). Dedup, conflict resolution, and provenance across translation variants are open.

---

## Bibliography

**Verified this session (arXiv abstract page or docs page fetched):**

- MIRACL — Zhang, Thakur et al. — WSDM 2023 Cup / TACL — arXiv:2210.09984 — 2022.
- NoMIRACL — Thakur et al. — Findings of EMNLP 2024 — arXiv:2312.11361 — 2023.
- Mr.TyDi — Zhang et al. — MRL@EMNLP 2021 — arXiv:2108.08787 — 2021.
- mMARCO — Bonifacio et al. — arXiv:2108.13897 — 2021/2022 (preprint).
- XOR QA (XOR-TyDi) — Asai et al. — NAACL-HLT 2021 — arXiv:2010.11856 — 2020.
- MKQA — Longpre et al. — TACL — arXiv:2007.15207 — 2020/2021.
- AfriQA — Ogundepo et al. — arXiv:2305.06897 — 2023 (preprint; Findings of ACL 2023 [uncertain]).
- M3-Embedding (BGE-M3) — Chen et al. — arXiv:2402.03216 — 2024 (preprint).
- Multilingual E5 — Wang et al. — arXiv:2402.05672 — 2024 (technical report).
- Arctic-Embed 2.0 — Yu et al. — arXiv:2412.04506 — 2024 (preprint).
- Qwen3-Embedding — Zhang et al. — arXiv:2506.05176 — 2025 (preprint).
- MMTEB — Enevoldsen et al. — ICLR 2025 — arXiv:2502.13595 — 2025.
- Tokenizer unfairness — Petrov et al. — NeurIPS 2023 — arXiv:2305.15425 — 2023.
- "Do All Languages Cost the Same?" — Ahia et al. — arXiv:2305.13707 — 2023 (EMNLP 2023 [uncertain]).
- Translate-Distill — Yang et al. — ECIR 2024 — arXiv:2401.04810 — 2024.
- mRAG in multilingual settings — Chirkova et al. (Naver Labs Europe) — arXiv:2407.01463 — 2024 (preprint).
- Futurepedia / "Not All Languages are Equal in mRAG" — Wu et al. — arXiv:2410.21970 — 2024 (preprint).
- MIRAGE-Bench — Thakur et al. — arXiv:2410.13716 — 2024 (NAACL 2025 [uncertain]). [abstract seen via API listing with summary]
- XRAG — Liu et al. — arXiv:2505.10089 — 2025 (preprint).
- Cross-lingual cost in Arabic–English RAG — Amiraz et al. — ArabicNLP 2025 — arXiv:2507.07543 — 2025.
- Linguistic Nepotism — Ki et al. — ICML 2026 Spotlight — arXiv:2509.13930 — 2025/2026.
- Language Drift in mRAG + Soft Constrained Decoding — Li et al. — arXiv:2511.09984 — 2025 (preprint).
- LLM evaluators for multilingual evaluation — Hada et al. — Findings of EACL 2024 — arXiv:2309.07462 — 2023.
- MM-Eval — Son et al. — arXiv:2410.17578 — 2024/2025 (preprint).
- Code-Switching IR (CSR-L / CS-MTEB) — Zeng et al. — arXiv:2604.17632 — 2026 (preprint).
- "All Languages Matter" / LAURA — Wang et al. — arXiv:2604.20199 — 2026 (preprint).
- Multilingual hallucination in the wild — Islam et al. — arXiv:2502.12769 — 2025/2026 (preprint).
- Elasticsearch kuromoji analysis plugin — Elastic documentation (fetched; installation-level content only).

**[listing-only] — seen in arXiv API listings this session, abstracts not separately fetched:**

- TyDi QA — Clark et al. — TACL 2020 (via fetched Mr.TyDi/XOR QA abstracts).
- LAMAR language-aware reranker — Hong et al. — arXiv:2607.22042 — 2026.
- CORAL culturally-aligned mRAG — Lee et al. — arXiv:2604.25676 — 2026.
- Language-coupled RL for mRAG — Qi et al. — arXiv:2601.14896 — 2026.
- DELTA debiased query fusion — Park et al. — arXiv:2601.02956 — 2026.
- QTT-RAG quality-aware translation tagging — Moon et al. — arXiv:2510.23070 — 2025.
- "How and Where to Translate?" — Gupta et al. — arXiv:2507.22923 — 2025.
- CrossRAG — Ranaldi et al. — arXiv:2504.03616 — 2025.
- DKM-RAG / language preference of mRAG — Park et al. — arXiv:2502.11175 — 2025.
- BordIRLines culturally-sensitive mRAG — Li et al. — arXiv:2410.01171 — 2024.
- Teacher-regularized RL for cross-lingual RAG — Zhou et al. — arXiv:2607.02966 — 2026.
- Bengali agricultural cross-lingual RAG case study — Hossain et al. — arXiv:2601.02065 — 2026.
- Hybrid mRAG for historical documents — Mudet et al. — arXiv:2512.12694 — 2025.
- MiLQ mixed-language query IR — Kim et al. — arXiv:2505.16631 — 2025.
- SwitchLingua — Xie et al. — arXiv:2506.00087 — 2025.
- MINERS 200+-language retrieval benchmark — Winata et al. — arXiv:2406.07424 — 2024.
- Code-switching for cross-lingual semantic retrieval — Maimaiti et al. — arXiv:2403.01364 — 2024.
- Artificially code-switched training for CLIR — Litschko et al. — arXiv:2305.05295 — 2023.
- Multilingual IR with monolingual KB — Zhuang et al. — arXiv:2506.02527 — 2025.
- ColBERT-X translate-train for African CLIR — Yang et al. — arXiv:2404.08134 — 2024.
- X-MADAM-RAG Chinese–English evidence conflict — Kang et al. — arXiv:2606.12903 — 2026.
- MultiHaluDet — Alvi et al. — arXiv:2605.24919 — 2026.
- BenHalluEval (Bengali) — Adib et al. — arXiv:2605.31483 — 2026.
- HalluScore (Arabic) — Alansari et al. — arXiv:2605.17007 — 2026.
- Test-oracle problem in synthetic LLM-judge corpora — Ballı — arXiv:2607.13707 — 2026.
- dziribot Algerian-Arabic RAG — Bechiri et al. — arXiv:2602.02270 — 2026.
