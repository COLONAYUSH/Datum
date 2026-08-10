# Knowledge Conflicts, Attribution Methods & RAG Interpretability — Landscape Review (as of August 2026)

Research dossier for the "Reimagining RAG" project. Dimension: **knowledge conflicts, generation-side attribution methods, prompt-format sensitivity, and mechanistic interpretability of retrieval use** — i.e., what happens *inside the generator* after retrieval returns: does the model believe the context or its weights, can it say where its claims came from, how fragile is that behavior to surface form, and what circuits implement it. Emphasis on failure modes, critiques, and open problems, per project brief.

Citation hygiene: every source below appeared in a fetched arXiv abstract page, a fetched arXiv API result, or a fetched primary page during this session. Items whose full abstract page was **not** fetched (seen only in an arXiv API result listing with a machine-summarized abstract) are marked **[listing-only]**. Venue attributions that could not be confirmed from the fetched page are marked **[uncertain]**. Preprints are flagged; peer-reviewed venues named where confirmed.

---

## Scope

Covered here:

- **Knowledge-conflict literature**: the founding entity-substitution result (Longpre et al. 2021), the Xu et al. taxonomy survey, behavioral studies (Adaptive Chameleon, ClashEval, Kortukov et al., ConflictBank), context-faithfulness vs. parametric-prior tension, conflict *detection* and *arbitration* strategies (prompting, contrastive decoding, head/neuron-level interventions, system-level designs like Astute RAG), temporal conflicts (outdated corpus vs. fresh model and vice versa).
- **Generation-side attribution METHODS** (evaluation benchmarks are covered by the sibling evaluation dossier; this file covers *how citations get produced*): the AIS conceptual framework, post-hoc attribution & revision (RARR, CiteFix, VeriCite), citation-trained generation (AGREE, LongCite, SelfCite), "According to…" prompting, fine-grained/sub-sentence citation formats, plan-based citation.
- **Prompt-format sensitivity of RAG**: template/serialization/ordering sensitivity (FormatSpread, plain-text vs. Markdown vs. JSON vs. YAML studies), position effects beyond lost-in-the-middle, the 2025–2026 re-litigation of whether positional bias matters under realistic retrieval noise, structural-format attention effects.
- **Mechanistic interpretability of retrieval use**: induction heads, retrieval heads and their 2025–2026 descendants, memory-heads-vs-context-heads analyses of why models ignore context, neuron-level accounts, SAE-based steering, circuit tracing / attribution graphs applied to factual recall and hallucination, mechanistic detection of citation hallucination.

Out of scope (sibling dossiers): retriever internals, chunking, rerankers, corrective/adaptive RAG *architectures* (Astute RAG appears in both, treated here strictly as a conflict-arbitration design), attribution *evaluation* benchmarks (ALCE, LongBench-Cite scoring details), agent memory.

---

## Lineage & key work

The arc of this area: **context-vs-memory conflict discovered as a QA pathology (2021) → behavioral characterization at LLM scale (2023–2024) → mitigation at every level of the stack: prompt, decoding, weights, heads, neurons, system (2023–2026) → mechanistic explanation of the same phenomenon (2023–2026), converging with the attribution problem (2026)**. Attribution has a parallel arc: **human-evaluable definition (AIS, 2021) → post-hoc revision (RARR, 2022) → citation-trained generation (2023–2024) → self-supervised, fine-grained, plan-based citation (2024–2025) → paradigm comparisons and mechanistic accounts of citation failure (2025–2026)**.

### Phase 0 — The founding context-vs-memory results (2021–2022)

- **Entity-Based Knowledge Conflicts in Question Answering** — Longpre et al. — EMNLP 2021 — arXiv:2109.05052. The founding result: substitute the answer entity in a gold passage and see whether the QA model reads the passage or answers from memory. Finds over-reliance on memorized answers ("memorization" over "reading"), identifies factors that intensify it, and shows a substitution-augmentation mitigation improving OOD generalization 4–7%. Everything below is downstream of this experimental design. Limitation (established by later work): entity substitution creates *unrealistic* conflicts; models behave differently on naturally occurring contradictions (see Kortukov et al. 2024).
- **DisentQA** — Neeman et al. — arXiv:2211.05655 — 2022 (ACL 2023 [uncertain]). Trains QA models to emit *two* answers — one contextual, one parametric — via counterfactual data augmentation, arguing entanglement of the two knowledge sources harms "trust, interpretability and factuality." The earliest "make the conflict explicit in the output" design; direct ancestor of 2025–2026 transparent-conflict systems.
- **AIS: Measuring Attribution in Natural Language Generation Models** — Rashkin et al. (Google) — arXiv:2112.12870 — 2021 (later published in Computational Linguistics [uncertain]). Defines "Attributable to Identified Sources": an output sentence is attributable iff an annotator can verify it from a citable source, operationalized via a two-stage human-annotation pipeline across conversational QA, summarization, table-to-text. The conceptual foundation for all citation work; deliberately a *human* evaluation framework, which is why the field then spent four years building automatic proxies of varying fidelity (covered in the evaluation dossier).

### Phase 1 — Behavioral characterization at LLM scale (2023–2024)

- **Adaptive Chameleon or Stubborn Sloth** — Xie et al. — ICLR 2024 (spotlight) — arXiv:2305.13300. Elicits high-quality parametric memory from the LLM itself and constructs coherent counter-memory. Two findings that structure the field: (1) LLMs are *highly receptive* to conflicting external evidence if it is coherent and persuasive — even when it is wrong; (2) with mixed evidence, LLMs show strong **confirmation bias** toward evidence agreeing with their parametric prior. I.e., the failure is bidirectional: gullibility and stubbornness coexist.
- **Resolving Knowledge Conflicts in Large Language Models** — Wang et al. — COLM 2024 — arXiv:2310.00935. Proposes three desiderata: detect the conflict, pinpoint the conflicting segments, generate distinct answers per source. Finds LLMs can *detect that* a conflict exists but "struggle to determine the specific conflicting knowledge and produce a response with distinct answers" — i.e., detection ≫ localization ≫ resolution. Instruction-based interventions help, but the authors state robust conflict response "remains an open research question."
- **ClashEval** — Wu, Wu & Zou (Stanford) — arXiv:2404.10198 — 2024 (NeurIPS 2024 D&B [uncertain]). 1,200+ questions across six domains with answers perturbed from subtle to absurd. Headline numbers: LLMs adopt incorrect retrieved content, overriding their own *correct* prior, **over 60% of the time**; adoption probability falls as the perturbation becomes more blatant; token-probability confidence predicts deference. Frames the problem as a calibrated tug-of-war: the model should defer to context exactly when the context is more likely correct than its prior — and currently cannot.
- **Studying LLM Behaviors Under Context-Memory Conflicts With Real Documents** — Kortukov et al. — arXiv:2404.16032 — 2024. Replaces entity-substitution with *naturally occurring* contradictory documents; finds incorrect parametric knowledge still leaks into answers during knowledge updating. Important corrective to the synthetic-conflict tradition [listing-only for details beyond the fetched API summary].
- **Knowledge Conflicts for LLMs: A Survey** — Xu et al. — arXiv:2403.08319 — 2024 (EMNLP 2024 [uncertain]). The organizing taxonomy: **context–memory** conflict (retrieved evidence vs. weights), **inter-context** conflict (retrieved documents contradict each other), **intra-memory** conflict (the weights contradict themselves across phrasings). Surveys causes, behaviors, mitigations. Critique: most cited empirical work is short-form QA with synthetic conflicts; the survey's categories are cleaner than the evidence behind them.
- **ConflictBank** — Su et al. — arXiv:2408.12076 — 2024 (preprint). Largest-scale conflict benchmark: 7,453,853 claim–evidence pairs, 553,117 QA pairs, covering misinformation, temporal, and semantic conflict causes across 12 LLMs; analyzes effects of model scale, conflict cause, conflict type.
- **RAGTruth** — Niu et al. — arXiv:2401.00396 — 2024. ~18,000 naturally generated RAG responses with *word-level* hallucination annotation. Establishes that RAG reduces but does not eliminate unsupported claims, and that small fine-tuned detectors can match GPT-4 prompting for hallucination detection. Bridges the conflict and attribution threads: word-level "which span is unsupported" annotation is exactly the granularity attribution methods must produce.

### Phase 2 — Mitigation at every level of the stack (2023–2026)

Prompting: **Context-faithful Prompting** — Zhou et al. — EMNLP 2023 Findings — arXiv:2303.11315 — opinion-based reframing ("what does the narrator claim?") plus counterfactual demonstrations significantly improve context-faithfulness with no training. Decoding: **Context-Aware Decoding (CAD)** — Shi et al. — arXiv:2305.14739 — 2023 (NAACL 2024 [uncertain]) — contrasts output distributions with and without context to amplify contextual signal; +14.3% factuality for LLaMA on summarization, training-free. Weights: **SI-FACT** (arXiv:2509.10208, 2025) self-generates contrastive training data for faithfulness [listing-only]. Heads/neurons/representations: PH3, IRCAN, SpARE (§ Mechanistic interpretability). System: **Astute RAG** — Wang et al. (USC/Google Cloud AI) — ACL 2025 — arXiv:2410.07176 — shows imperfect retrieval is "inevitable, common, and harmful," then adaptively elicits internal knowledge, iteratively consolidates it with external passages *with source tracking*, and answers from the reliability-assessed consolidation; the only method in its comparison matching or beating no-RAG LLMs in the worst-case retrieval regime.

### Attribution-methods lineage (2022–2026)

- **RARR: Researching and Revising What Language Models Say** — Gao et al. — ACL 2023 — arXiv:2210.08726. Post-hoc: given any LM output, find supporting web evidence, then minimally *revise* unsupported content while preserving intent; needs only few-shot prompting and web search. The canonical "attribute after the fact" design. Known limitation class (established in later comparisons): post-hoc revision is bounded by the draft's structure — it repairs sentences but cannot re-plan an answer built on an unsupported skeleton, and the editor itself can introduce errors.
- **"According to…" prompting** — Weller et al. — EACL 2024 — arXiv:2305.13252. Prompting models to ground against a named corpus ("According to Wikipedia…") measurably increases verbatim overlap with that corpus (QUIP-Score, based on n-gram membership) and often improves accuracy; anti-grounding prompts decrease it. Cheap, steerable grounding — but quoting-from-pretraining is attribution to a *corpus*, not to an inspectable retrieved document, and QUIP measures overlap, not support.
- **AGREE** — Ye et al. — NAACL 2024 — arXiv:2311.09533. Citation-trained generation: fine-tune the LLM to self-ground claims with citations (training data auto-constructed from unlabeled queries via an NLI-style grounding check), plus test-time adaptation that retrieves additional passages for still-ungrounded claims. Beats both prompting-based and post-hoc citing baselines — early evidence that citation must be *learned*, not prompted.
- **Attribute First, then Generate** — Slobodkin et al. — arXiv:2403.17104 — 2024 (NAACL 2024 [uncertain]). Decomposes generation into content selection → sentence planning → sentence-by-sentence generation conditioned on pre-selected source segments, yielding *locally attributable* output (each sentence carries its evidence by construction) and reduced human fact-checking time. The cleanest "citation as architecture, not decoration" design.
- **Learning to Plan and Generate Text with Citations** — Fierro et al. — arXiv:2404.03381 — 2024 (ACL 2024 [uncertain]). Blueprint models: plan = sequence of questions (abstractive or extractive) that the answer will address; planning consistently improves citation quality over vanilla pipelines on long-form QA.
- **LongCite** — Zhang et al. (Tsinghua/Zhipu) — arXiv:2409.02897 — 2024 (preprint). Fine-grained *sentence-level* citations in long-context QA: CoF pipeline auto-generates 45k SFT instances with precise citations; LongCite-8B/9B surpass GPT-4o on citation quality (LongBench-Cite). Shows span-precise citation is trainable with synthetic supervision.
- **SelfCite** — Chuang et al. (MIT/Meta) — ICML 2025 — arXiv:2502.09604. Self-supervised citation reward via **context ablation**: a citation is good iff removing the cited sentences changes the response and keeping only them preserves it (necessity + sufficiency). Used for best-of-N sampling and preference optimization; +5.3 F1 on LongBench-Cite without human citation labels. Conceptually important: defines citation quality *counterfactually and causally* rather than by NLI proxy.
- **Generation-Time vs. Post-hoc Citation: A Holistic Evaluation** — Saxena et al. — arXiv:2509.21557 — 2025 (preprint). Direct paradigm comparison: post-hoc (P-Cite) wins on coverage with comparable correctness and moderate latency; generation-time (G-Cite) is precision-leaning but sacrifices coverage and speed; **retrieval quality is the main driver of attribution quality in both paradigms**. Recommends retrieval-centric P-Cite-first for high-stakes domains.
- Post-hoc correction & verification in production RAG: **CiteFix** (arXiv:2504.15629, 2025) post-processing citation correction; **VeriCite** (arXiv:2510.11394, 2025) three-stage citation verification; **sub-sentence citations** balancing conciseness and sufficiency (Chen et al., arXiv:2509.20859, 2025); **ScholarCopilot** (arXiv:2504.00824, 2025) citation-trained academic writing; **Context-Prior Augmented Citation Generation** (Shen et al., arXiv:2504.14856, 2025) — makes models cite *which knowledge source* (internal vs. external) each claim used, merging the conflict and attribution threads. All [listing-only].
- **A Survey of Large Language Models Attribution** — Li et al. — arXiv:2311.03731 — 2023 (preprint). Early field survey; flags unclear knowledge sources, bias, and *over-citation* as standing problems.

---

## State of the art (mid-2026)

**Knowledge conflicts.** No deployed resolution; the frontier is *calibrated arbitration with provenance*. Best-known system-level result remains Astute RAG (ACL 2025): consolidate internal + external knowledge with source tracking, answer by reliability. 2026 work pushes three directions: (1) **explicit, observable conflict handling** — Context-Driven Decomposition (Chen et al., arXiv:2605.14473) elicits contextual and prior answers separately, isolates the conflicting premise, and records a perturbable resolution trace; standard RAG drops to **15% accuracy** under adversarial-misconception retrieval, while explicit decomposition lifts entity-swap robustness 79.3→88.0%; the authors frame conflict handling as "fundamentally an observability problem." (2) **Detection-then-routing**: ConflictRAG (arXiv:2605.17301) couples lightweight conflict detection with credibility assessment [listing-only]; regime-aware specialization routes by conflict type (arXiv:2606.30518) [listing-only]. (3) **Activation-level control**: SHIFT gate-modulated steering (arXiv:2606.27786), conflict-aware contrastive decoding (arXiv:2606.10298), dynamic cognitive reconciliation decoding (arXiv:2605.12185) — all 2026 preprints, all [listing-only], none independently reproduced.

**Attribution.** Sentence-level citation is now trainable to beyond-GPT-4o quality on benchmark metrics (LongCite) and improvable without human labels via counterfactual ablation rewards (SelfCite, ICML 2025). The honest 2025 paradigm comparison (Saxena et al.) says the bottleneck is *retrieval*, not the citing mechanism, and that generation-time citation trades coverage for precision. 2026 opens the mechanistic front: FACTUM (arXiv:2601.05866) detects citation hallucination from internal signals.

**Format sensitivity.** Established at ICLR 2024 (FormatSpread: up to 76 accuracy points from formatting alone) and extended to serialization (plain/Markdown/JSON/YAML: up to 40% swings for GPT-3.5; GPT-4 more robust — He et al., arXiv:2411.10541). For RAG specifically, 2025–2026 delivered a genuine dialectic: positional bias is real in clean settings (Lost in the Middle) but **marginal under realistic retrieval noise**, where reordering strategies do no better than random shuffling (Cuconasu et al. 2025); meanwhile *structural* format effects (KG triples soaking up 2–3× per-token attention regardless of relevance) are newly documented (arXiv:2606.11198).

**Mechanistic interpretability.** Retrieval heads (Wu et al. 2024) spawned an entire applied subfield: KV-cache compression (RazorAttention, CompressKV), hallucination-mitigating decoding (DeCoRe), faithfulness training (RHIO), reranking (QRHead, CoRe heads), multi-document QA (CAFE) — all [listing-only]. 2026 complicates the picture: retrieval heads are *dynamic* across decoding steps (arXiv:2602.11162) and literal-copy detection misses non-literal synthesis heads (LOCOS, arXiv:2607.01002). Anthropic's attribution-graphs program ("On the Biology of a Large Language Model," transformer-circuits.pub, March 2025) gives circuit-level accounts of known-entity vs. can't-answer circuits whose misfiring produces hallucination — directly relevant to when a model trusts context vs. confabulates.

---

## Knowledge conflicts: behavioral findings that matter for system design

1. **Deference is miscalibrated in both directions.** ClashEval: correct priors overridden by wrong context >60% of the time; Xie et al.: coherent wrong evidence is persuasive, while mixed evidence triggers confirmation bias. A RAG system cannot assume "context wins" is safe (poisoning, stale corpora) or that "prior wins" is safe (that defeats the purpose of retrieval).
2. **Confidence signals carry usable information.** ClashEval shows token-probability confidence predicts when models defer; simple calibration adjustments improve arbitration. This is the cheapest exploitable lever and remains underused in frameworks.
3. **Detection ≠ localization ≠ resolution.** Wang et al. (COLM 2024): models detect conflicts but cannot pinpoint or answer-per-source. Framework implication: conflict handling must be an explicit pipeline stage with structured output, not an emergent LLM behavior.
4. **Synthetic conflicts overstate/mis-state the phenomenon.** Kortukov et al.: behavior on real contradictory documents differs from entity-substitution behavior. Benchmarks built on substitution (including parts of ClashEval and ConflictBank) may mis-rank mitigation methods.
5. **Instruction tuning can make context reliance *worse*.** **Context-Parametric Inversion** — Goyal et al. — ICLR 2025 (oral) — arXiv:2410.10796: context reliance rises early in instruction finetuning then *decays* while benchmark scores keep improving, driven by finetuning examples where context agrees with parametric knowledge. This is a structural indictment: the standard post-training recipe silently degrades the property RAG depends on, and proposed mitigations give "limited but insightful gains."
6. **Task type modulates conflict behavior.** "Task Matters" (Sun et al., arXiv:2506.06485): how conflicts resolve depends on the task's knowledge requirements [listing-only]. "Whose Facts Win?" (arXiv:2601.03746): models show institutional-source preferences that can be *reversed by repetition* of the competing claim [listing-only] — an attack surface.
7. **Temporal conflicts are the common production case.** FreshLLMs (Vu et al., arXiv:2310.03214, 2023): all models, regardless of size, fail on fast-changing knowledge and false premises; FreshQA is maintained as a living benchmark; evidence quantity/ordering materially affect accuracy. The dual failure exists too: fresh model vs. stale corpus — "When LLMs Lag Behind" studies deprecated-API conflicts in code generation (arXiv:2604.09515) [listing-only], and "That's Deprecated!" (arXiv:2510.19116) detects and steers deprecation conflicts via activations [listing-only]. Domain-specific conflict benchmarks arrive 2025–2026 (HealthContradict, arXiv:2512.02299 [listing-only]).
8. **Inter-context conflict (doc vs. doc) is the least-solved category.** The Xu et al. taxonomy names it; ConflictBank instantiates it at scale; but arbitration research overwhelmingly targets context-vs-memory. In multi-source agentic retrieval, doc-vs-doc contradiction is arguably the dominant real-world case.

---

## Temporal conflicts: the two staleness regimes

Temporal conflict deserves separate treatment because it is the *benign, guaranteed* conflict case — no adversary, no noise, just time — and it runs in both directions:

**Regime A — stale model, fresh corpus (retrieval should win).**
- **FreshLLMs / FreshQA** — Vu et al. — arXiv:2310.03214 — 2023 (preprint; maintained as a living benchmark). All models, regardless of scale, fail on fast-changing knowledge and false premises; FreshPrompt (search-result augmentation) beats Self-Ask-style baselines, and — importantly for this dossier — the *number, ordering, and verbosity* of inserted evidence measurably shift accuracy and hallucination, tying the temporal thread back to format sensitivity.
- The context-parametric inversion result (Goyal et al., ICLR 2025) makes this regime worse over time: each instruction-tuning cycle biases the model back toward its (stale) prior.

**Regime B — fresh model, stale corpus (retrieval should lose).**
- Private corpora age. The clearest studied instance is code: **"When LLMs Lag Behind"** (arXiv:2604.09515, 2026) studies conflicts between evolving API specifications and outdated parametric knowledge [listing-only]; **"That's Deprecated!"** (arXiv:2510.19116, 2025) shows deprecation conflicts are detectable and steerable at the activation level [listing-only]. The same logic applies in reverse when the retrieved document describes a deprecated API and the model knows the newer one — no published method distinguishes these two cases at inference time [uncertain — no such method surfaced in this session's searches].
- ConflictBank explicitly includes temporal-discrepancy conflicts among its three causes (Su et al. 2024), but temporal metadata is *not* consumed by any arbitration method surveyed here.

Design consequence: temporal arbitration is nearly free relative to semantic arbitration — documents have timestamps, models have cutoffs, corpora have ingestion dates — yet no method in the strategy taxonomy below exploits this metadata. This is the single largest gap between what the conflict literature studies and what a production framework could actually implement cheaply.

---

## Conflict detection & arbitration: a strategy taxonomy

Where in the stack each intervention lives, what it assumes, and what breaks it. (Representative works; all discussed above or in the bibliography.)

| Level | Representative methods | Mechanism | Key assumption | Known failure mode |
|---|---|---|---|---|
| Prompt | Context-faithful prompting (Zhou et al. 2023); "According to…" (Weller et al. 2024) | Reframe context as narrator's opinion; name a trusted corpus | Instruction following transfers to conflict cases | Globally biases toward context; helpless against persuasive misinformation (Xie et al.); effect size varies by model |
| Decoding | CAD (Shi et al. 2023); conflict-aware contrastive decoding (arXiv:2606.10298, 2026 [listing-only]); DeCoRe (arXiv:2410.18860 [listing-only]) | Contrast with-context vs. without-context (or retrieval-head-masked) distributions | Divergence between distributions localizes the contextual signal | Doubles inference cost; global context bias again; 2026 work adds *dynamic* authority allocation precisely because static contrast miscalibrates |
| Weights | DisentQA (2022); SI-FACT (2025 [listing-only]); RHIO (2025 [listing-only]); AGREE (2024) | Counterfactual/contrastive finetuning for faithfulness or dual answers | Training distribution of conflicts matches deployment | Context-parametric inversion shows finetuning itself can erode context reliance; synthetic conflict training data ≠ real conflicts (Kortukov) |
| Heads/neurons/features | PH3 (2024); IRCAN (NeurIPS 2024); SpARE (2024); entropy neurons (2025 [listing-only]); SHIFT (2026 [listing-only]) | Locate memory-vs-context components; prune, reweight, or steer at inference | Conflict circuitry is localized, static, and transferable | Mostly ≤13B models; retrieval-head dynamism (2026) undermines static component sets; sets a global preference, not per-instance arbitration |
| System / orchestration | Astute RAG (ACL 2025); CDD (2026); ConflictRAG (2026 [listing-only]); regime-aware routing (2026 [listing-only]) | Elicit both knowledge sources explicitly, track provenance, consolidate by reliability | The LLM can compare sources when forced to externalize them | Adds latency and calls; reliability assessment is itself an LLM judgment vulnerable to fluency/repetition attacks; no reproductions yet for the 2026 systems |
| Signals only (no intervention) | ClashEval confidence calibration; SpARE conflict features; FACTUM pathway signatures | Detect that a conflict/unsupported citation is occurring; hand off to policy | Internal signals are observable (open weights) or proxied by logprobs (APIs) | Detection without a resolution policy; frontier-API deployments only get logprobs, if that |

Cross-cutting observations:

- Every level above "system" encodes a **global** context-vs-memory preference; ClashEval's central finding is that the right preference is per-instance. Only the system level (and DisentQA's dual-answer output format) can express "both answers, flagged."
- **Temporal arbitration is absent from all rows.** No method in this table conditions on document timestamps or model knowledge cutoff, despite temporal conflict being the most common benign production case (FreshQA; deprecated-API studies).
- **Inter-context conflict** appears only in the system row, and even there as an aggregate reliability judgment, not pairwise adjudication between contradicting retrieved documents.

---

## Prompt-format sensitivity of RAG

- **FormatSpread** — Sclar et al. — ICLR 2024 — arXiv:2310.11324. Semantically equivalent formatting choices (separators, casing, spacing) cause up to **76-point** accuracy differences (LLaMA-2-13B); sensitivity persists with scale, more shots, and instruction tuning; format performance correlates only weakly *across models*, so a template tuned for one model does not transfer. Proposes reporting performance ranges over format distributions.
- **Does Prompt Formatting Have Any Impact on LLM Performance?** — He et al. (Microsoft) — arXiv:2411.10541 — 2024 (NAACL 2025 industry track [uncertain]). Plain text vs. Markdown vs. JSON vs. YAML: up to 40% swings for GPT-3.5-turbo on code translation; GPT-4 markedly more robust. Direct implication for RAG context serialization: the choice of how chunks are wrapped (JSON fields vs. markdown blocks) is a first-class hyperparameter, and its optimum is model-specific.
- **Lost in the Middle** — Liu et al. — TACL 2024 — arXiv:2307.03172. The canonical U-shaped position effect in multi-document QA and KV retrieval.
- **The Power of Noise** — Cuconasu et al. — arXiv:2401.14887 — 2024 (SIGIR 2024 [uncertain]). High-scoring but answer-free "distracting" passages hurt; bizarrely, *random* irrelevant documents can improve accuracy by up to 35%. Whatever the mechanism, it demonstrates the generator's response to context composition is not a monotone function of relevance — undermining the assumption behind "retrieve better, generate better."
- **Do RAG Systems Really Suffer From Positional Bias?** — Cuconasu et al. — arXiv:2505.15561 — 2025. The corrective: in realistic retrieval, >60% of queries carry at least one highly distracting passage in the top-10, relevant and distracting passages co-occupy prominent positions, and positional effects become **marginal**; LLM-preference-aware reordering does no better than random shuffling. Lesson for framework designers: position-shuffling heuristics popular in 2024 engineering folklore are likely dead weight; distractor *filtering* dominates position *ordering*.
- **Eliminating Position Bias of Language Models: A Mechanistic Approach** — Wang et al. — arXiv:2407.01100 — 2024. Training-free bidirectional-attention intervention removing order dependence [listing-only]. **Stable-RAG** (arXiv:2601.02993, 2026) targets retrieval-permutation-induced hallucination by aggregating hidden states across permutations [listing-only] — evidence that order sensitivity is now treated as a *hallucination source*, not just an accuracy nuisance.
- **The Structural Attention Tax** — Zhang & Di Zhang — arXiv:2606.11198 — 2026 (preprint). KG-triple-formatted context absorbs 2–3× more attention per token than semantically equivalent natural language (attention share ~0.70 vs ~0.25), *independent of relevance*; relational delimiters and repeated patterns compress attention available to demonstrations by up to 42%. First formal decomposition of attention into semantic vs. structural components for retrieved context; tested on Mistral-7B and Llama-3-8B. Caveat: small open models only; unknown whether frontier models pay the same tax.
- Gaps in this literature (relevant to us): there is still **no systematic 2023–2026 study of chunk-delimiter conventions** (e.g., `<doc id=…>` vs. markdown headers vs. numbered lists) on RAG faithfulness/citation accuracy in frontier models — the He et al. and Sclar et al. results are task-general, and the Structural Attention Tax paper covers KG triples only. Few-shot format variance inside RAG prompts is similarly uncharacterized. This is an open measurement problem, not a settled one.

---

## Mechanistic interpretability of retrieval use

### Copying circuits: induction heads → retrieval heads

- **In-context Learning and Induction Heads** — Olsson et al. (Anthropic) — arXiv:2209.11895 / transformer-circuits.pub — 2022. Attention heads implementing [A][B]…[A]→[B] pattern completion; emergence coincides with the phase change in in-context learning ability; causal evidence in small attention-only models, correlational at scale. The ancestral mechanism of all in-context lookup.
- **Retrieval Head Mechanistically Explains Long-Context Factuality** — Wu et al. — arXiv:2404.15574 — 2024 (ICLR 2025 [uncertain]). Retrieval heads copy tokens from context: **universal** across long-context models, **sparse** (<5% of heads; ~12 consistently active in Llama-2-7B), **intrinsic** (present after short-context pretraining, preserved through context extension), **dynamically activated**, and **causal** — pruning them induces hallucination and needle-retrieval failure while pruning random heads does not; strong effect on CoT that references context, weak effect on parametric generation. This is the closest thing the field has to a mechanistic definition of "the model is actually reading the context."
- The applied wave (all [listing-only], seen in fetched API listings): **RazorAttention** (arXiv:2407.15891) — 70% KV-cache reduction by keeping full cache only for retrieval heads; **CompressKV** (arXiv:2508.02401); **DeCoRe** (Gema et al., arXiv:2410.18860) — decode by contrasting the base model against a retrieval-head-masked copy to suppress hallucination; **RHIO** (Huang et al., arXiv:2501.13573) — trains faithfulness by contrasting with retrieval-head-masked negatives; **QRHead** (arXiv:2506.09944) — query-focused retrieval heads improve re-ranking and long-context reasoning; **CAFE** (arXiv:2505.10063) — coarse-to-fine multi-doc QA; **Understanding Synthetic Context Extension via Retrieval Heads** (Zhao et al., arXiv:2410.22316) — retrieval-head overlap predicts whether synthetic long-context finetuning transfers.
- The 2026 corrections (both [listing-only]): **Retrieval Heads are Dynamic** (Lin et al., arXiv:2602.11162) — head identity varies across generation timesteps, so static head sets mis-specify the mechanism; **LOCOS** (Gema et al., arXiv:2607.01002) — needle-in-haystack detection finds only *literal copy* heads and misses heads doing non-literal synthesis. Also RoPE interactions with retrieval heads across families (arXiv:2606.21249) [listing-only]. Critique that follows: most 2024–2025 applications assume a static, literal-copying head set; both assumptions are now empirically shaky.

### Why models ignore context: the memory-vs-context competition

- **Characterizing Mechanisms for Factual Recall** — Yu, Merullo & Pavlick — arXiv:2310.15910 — 2023 (EMNLP 2023 [uncertain]). On world-capital counterfactuals: pretraining *frequency* of the fact predicts whether the in-context or memorized answer wins; head attribution isolates promoting heads; scaling a **single head's** value vector pushes in-context answer rate to 88%. The conflict outcome is (a) predictable from data statistics and (b) localized.
- **Cutting Off the Head Ends the Conflict (PH3)** — Jin et al. — arXiv:2402.18154 — 2024 (ACL 2024 Findings [uncertain]). Identifies **memory heads** and **context heads** in later layers; path-patching-based pruning of either steers behavior without weight updates: ~44% improvement when favoring memory, ~38.5% favoring context, generalizing across eight models. Conflict resolution is an interpretable, interventable competition between two head populations.
- **Competition of Mechanisms** — Ortu et al. — ACL 2024 — arXiv:2402.11655. Logit inspection + attention modification tracing how the factual-recall and copy mechanisms compete; a few attention positions control which mechanism wins.
- **IRCAN** — Shi et al. — NeurIPS 2024 — arXiv:2406.18406. Neuron-level: integrated-gradients attribution finds *context-aware neurons*; reweighting them up makes generation context-sensitive; plug-and-play across models.
- **SpARE** — Zhao et al. — arXiv:2410.15999 — 2024 (NAACL 2025 [uncertain]). Sparse-autoencoder features detect **conflict signals in mid-layers at inference time** and steer knowledge selection (context vs. parametric) training-free; ~10% over prior representation engineering and better than contrastive decoding on ODQA. Key claim for us: *the model internally represents "I am in a conflict" before it answers* — a detectable signal a framework could consume.
- **Entropy neurons modulate context copying** — Tighidet et al. — arXiv:2509.10663 — 2025 [listing-only]. **CoRect** — logit-contrast rectification of FFN-level parametric suppression (arXiv:2602.08221, 2026) [listing-only]. **Where Knowledge Collides** (arXiv:2601.09445, 2026) — first mechanistic account of *intra-memory* conflict, resolving in final layers via per-fact circuits [listing-only]. Multimodal extensions: perception-vs-knowledge conflict circuits in VLMs (arXiv:2606.28273) [listing-only]; linearly separable conflict encoding in multimodal long-chain reasoning (arXiv:2602.14518) [listing-only].

### Circuit tracing & attribution graphs (2025–2026)

- **On the Biology of a Large Language Model** — Lindsey, Gurnee, Ameisen et al. (Anthropic) — transformer-circuits.pub — March 2025 (not peer-reviewed; vendor research publication). Cross-layer transcoders replace neurons with ~30M sparse interpretable features; **attribution graphs** map causal feature→feature paths for individual prompts on Claude 3.5 Haiku, validated by activation/inhibition interventions. Findings relevant here: a default "can't answer" circuit is suppressed by "known answer/known entity" features, and **hallucination occurs when the known-entity features misfire** for entities the model does not actually know; factual recall runs memorized shortcut paths *in parallel with* genuine multi-hop paths; the model's self-explanations of its own procedure diverge from its actual internal computation (metacognitive unfaithfulness). Authors' own caveat: graphs are hypotheses requiring perturbation validation. Not yet applied to full RAG prompts with retrieved passages in the published work [uncertain whether internal follow-ups exist].
- **FACTUM** — Dassen et al. — arXiv:2601.05866 — 2026 (preprint). Mechanistic *detection* of citation hallucination in long-form RAG: correct citations show coordinated attention-pathway (reading) and FFN-pathway (recalling) activity — higher parametric-force scores and greater attention-sink use during synthesis; the coordination signature is scale-dependent (8B models use orthogonal pathway information). Reframes citation hallucination as an attention/FFN *coordination failure* rather than simple parametric override — and implies internal signals can flag unsupported citations before any external verifier runs.
- **Do Models Know Why They Changed Their Mind?** — arXiv:2605.27773 — 2026 [listing-only]. CoT explanations of conflict resolution are unfaithful to the underlying mechanism — echoing Anthropic's metacognition finding; a warning against trusting model-verbalized conflict rationales as provenance.
- Probing work links hallucination and internal conflict representations (arXiv:2606.08705, 2026) [listing-only].

---

## Failure modes & critiques

1. **The sycophancy–stubbornness dilemma has no principled solution.** Every arbitration knob (CAD, PH3, IRCAN, SpARE, prompting) sets a *global* preference for context or memory; ClashEval shows the correct preference is *instance-specific* and depends on relative reliability, which neither side exposes. Steering methods demonstrate control, not correctness.
2. **Post-training actively erodes context reliance.** Context-parametric inversion (ICLR 2025 oral) means every instruction-tuned checkpoint drifts toward its prior over finetuning — RAG frameworks inherit a generator whose faithfulness silently regresses across model updates, invisible to standard benchmarks.
3. **Citations systematically overclaim.** RAGTruth documents word-level unsupported spans surviving RAG; the Saxena et al. paradigm study shows generation-time citation buys precision by *dropping coverage*; SelfCite's counterfactual criterion exposes that NLI-style "supported" judgments accept citations that are neither necessary nor sufficient. Meanwhile FACTUM shows citation tokens can be emitted from parametric pathways with no reading signature — a *plausible* citation is not evidence the model used the source. Post-hoc verifiers (VeriCite, CiteFix) treat symptoms downstream.
4. **Attribution ≠ faithfulness ≠ provenance.** The AIS definition is about verifiability *by a human*; a model can produce AIS-perfect output that it actually generated from memory (accidental support). No deployed method certifies the *causal* provenance of a claim; SelfCite's ablation test and FACTUM's internal signatures are the only causal-flavored attempts, both partial.
5. **Format sensitivity invalidates single-format conclusions.** FormatSpread's 76-point swings and weak cross-model format correlation mean any RAG ablation run under one prompt template (i.e., nearly all of them) has an unquantified error bar; serialization effects (40% swings) compound this. Almost no RAG paper reports format ranges.
6. **The position-bias literature partially chased an artifact.** The 2025 Cuconasu re-analysis shows re-ordering strategies built on lost-in-the-middle do not beat random shuffling under realistic distractor prevalence. Engineering effort flowed to ordering when the binding constraint was distractor contamination.
7. **Mechanistic findings are small-model findings.** Retrieval heads, PH3, Yu et al., SpARE, Structural Attention Tax: predominantly ≤13B open models. The 2026 dynamic-heads and non-literal-heads results already overturned static-head assumptions; frontier-model validity is unknown, and Anthropic's circuit tracing — the only frontier-adjacent effort — is vendor-published, un-reviewed, and not yet run on retrieval-augmented prompts.
8. **Conflict benchmarks are mostly synthetic short-form QA.** Entity substitution (Longpre) and perturbation (ClashEval) dominate; Kortukov et al. showed real-document behavior differs. Long-form, multi-document, inter-context, and temporal conflicts are under-benchmarked relative to their production frequency; the 2026 conflict-mitigation wave (SHIFT, ConflictRAG, CoRect, …) is preprint-only, evaluated on these same synthetic sets, with no independent reproductions.
9. **Explanations of conflict resolution are unfaithful.** Both Anthropic's metacognition result and the 2026 CoT-under-conflict study indicate models cannot reliably report *why* they preferred context or memory — so "ask the model to explain its arbitration" is not a valid transparency mechanism.
10. **Source-preference is manipulable.** Repetition reverses institutional source preference (Whose Facts Win, 2026 [listing-only]); coherent fake evidence is persuasive (Xie et al.). Conflict arbitration that keys on surface authority or fluency is an adversarial attack surface for corpus poisoning.

---

## Relevance to a next-generation agentic RAG framework

Concrete design commitments this literature justifies:

1. **Conflict handling as a first-class pipeline stage with structured output.** Following Wang et al.'s detect/localize/resolve decomposition and CDD's observability framing: the generator should emit (a) a contextual answer, (b) a parametric answer when they diverge (DisentQA pattern), (c) the conflicting premise, and (d) a machine-readable resolution trace. Agent loops can then *act* on conflicts (re-retrieve, escalate, abstain) instead of silently absorbing them.
2. **Per-source reliability plumbing.** Astute RAG's source-tracked consolidation and the temporal-conflict evidence argue every retrieved chunk should carry provenance metadata (source authority, timestamp, corpus freshness vs. model cutoff) that the arbitration stage consumes — arbitration by evidence metadata, not by the LLM's fluency-swayed judgment.
3. **Exploit internal conflict signals.** SpARE (mid-layer SAE conflict features), FACTUM (reading-vs-recalling pathway signatures), and retrieval-head activity are all inference-time-observable signals that a white-box deployment could surface as: "the model is in conflict," "this citation was emitted without a reading signature," "no retrieval head attended to the cited chunk." A next-gen framework targeting open-weight models can ship these as cheap runtime monitors; for API models, token-probability calibration (ClashEval) is the fallback.
4. **Citation by construction, verified counterfactually.** Prefer plan-based/attribute-first generation (Slobodkin et al., Fierro et al.) so each sentence is conditioned on pre-selected evidence, then audit with SelfCite-style ablation (necessity/sufficiency) rather than NLI-only checks; keep a post-hoc P-Cite pass for coverage per Saxena et al. Attribution becomes an architectural invariant plus a causal test, not a formatting request.
5. **Treat context serialization as a tuned, versioned artifact.** FormatSpread + He et al. + Structural Attention Tax imply: benchmark chunk wrappers/delimiters per model, re-benchmark on every model upgrade (format optima don't transfer), avoid gratuitous structural markup (KG-triple-style serialization taxes attention), and report evaluation ranges over formats. Stop investing in position-reordering heuristics; invest in distractor filtering (Cuconasu 2025).
6. **Regression-test context reliance across model updates.** Context-parametric inversion means the framework should own a faithfulness canary suite (real-document conflicts, Kortukov-style) run on every new checkpoint, because vendors' instruction tuning can degrade context reliance without touching headline capability metrics.
7. **Adversarial conflict testing.** Given repetition/persuasion attacks on source preference, red-team the arbitration stage with poisoned-but-coherent evidence (Xie et al. counter-memory generation is a ready-made attack generator; ClashEval perturbation tiers give severity calibration).

---

## Open problems

1. **Calibrated instance-level arbitration.** No method decides *per claim* whether context or prior is more reliable using both the model's calibrated self-confidence and evidence metadata; ClashEval's confidence heuristics and 2026 steering knobs are the entire toolbox. A decision-theoretic formulation (defer iff P(context correct) > P(prior correct)) with measurable calibration is unbuilt.
2. **Inter-context conflict resolution.** Doc-vs-doc contradiction — the dominant case in multi-source agentic retrieval — lacks dedicated methods beyond credibility heuristics; nothing arbitrates between two retrieved sources with a principled trust model, and temporal ordering across sources (which document is *newer about this fact*) is unsolved.
3. **Causal provenance certification.** Can a system *prove* (not merely assert) that a claim was generated from a cited passage? SelfCite's ablation test and FACTUM's pathway signatures are partial; a composable, model-agnostic provenance certificate — usable in regulated domains — is open. Related: distinguishing "accidental support" from genuine use.
4. **Frontier-scale mechanistic validation.** Do retrieval heads, memory/context head competition, and conflict features exist in the same form in 100B+ instruction-tuned models? Dynamic-head and non-literal-head results (2026) suggest the 7B-scale picture is incomplete; attribution-graph methods have not been publicly applied to RAG prompts at all.
5. **A format-robustness standard for RAG evaluation.** No benchmark reports FormatSpread-style ranges for RAG configurations; chunk-delimiter and few-shot-format sensitivity within RAG prompts is essentially unmeasured for frontier models. Until it is, cross-paper RAG comparisons carry unknown format-induced error bars.
6. **Fixing post-training, not patching inference.** Context-parametric inversion identifies the cause (finetuning on context-agrees-with-prior examples) but mitigation gains are "limited"; a training recipe that preserves benchmark quality *and* context reliance — and a theory of when grounding should be learned vs. steered — remains open.

---

## Bibliography

Peer-reviewed (venue confirmed from fetched page unless marked [uncertain]):

- Longpre et al., "Entity-Based Knowledge Conflicts in Question Answering," EMNLP 2021, arXiv:2109.05052.
- Rashkin et al., "Measuring Attribution in Natural Language Generation Models" (AIS), arXiv:2112.12870, 2021 (Computational Linguistics 2023 [uncertain]).
- Olsson et al., "In-context Learning and Induction Heads," Anthropic / transformer-circuits.pub, arXiv:2209.11895, 2022.
- Neeman et al., "DisentQA," arXiv:2211.05655, 2022 (ACL 2023 [uncertain]).
- Gao et al., "RARR: Researching and Revising What Language Models Say," ACL 2023, arXiv:2210.08726.
- Zhou et al., "Context-faithful Prompting for Large Language Models," EMNLP 2023 Findings, arXiv:2303.11315.
- Xie et al., "Adaptive Chameleon or Stubborn Sloth," ICLR 2024 (spotlight), arXiv:2305.13300.
- Weller et al., "'According to…': Prompting Language Models Improves Quoting from Pre-Training Data," EACL 2024, arXiv:2305.13252.
- Shi et al., "Trusting Your Evidence: Context-aware Decoding," arXiv:2305.14739, 2023 (NAACL 2024 [uncertain]).
- Liu et al., "Lost in the Middle," TACL 2024, arXiv:2307.03172.
- Vu et al., "FreshLLMs / FreshQA," arXiv:2310.03214, 2023 (preprint).
- Wang et al., "Resolving Knowledge Conflicts in Large Language Models," COLM 2024, arXiv:2310.00935.
- Sclar et al., "Quantifying LMs' Sensitivity to Spurious Features in Prompt Design" (FormatSpread), ICLR 2024, arXiv:2310.11324.
- Yu, Merullo & Pavlick, "Characterizing Mechanisms for Factual Recall," arXiv:2310.15910, 2023 (EMNLP 2023 [uncertain]).
- Li et al., "A Survey of Large Language Models Attribution," arXiv:2311.03731, 2023 (preprint).
- Ye et al., "AGREE: Effective LLM Adaptation for Improved Grounding and Citation Generation," NAACL 2024, arXiv:2311.09533.
- Niu et al., "RAGTruth," arXiv:2401.00396, 2024 (ACL 2024 [uncertain]).
- Cuconasu et al., "The Power of Noise," arXiv:2401.14887, 2024 (SIGIR 2024 [uncertain]).
- Ortu et al., "Competition of Mechanisms," ACL 2024, arXiv:2402.11655.
- Jin et al., "Cutting Off the Head Ends the Conflict (PH3)," arXiv:2402.18154, 2024 (ACL 2024 Findings [uncertain]).
- Xu et al., "Knowledge Conflicts for LLMs: A Survey," arXiv:2403.08319, 2024 (EMNLP 2024 [uncertain]).
- Slobodkin et al., "Attribute First, then Generate," arXiv:2403.17104, 2024 (NAACL 2024 [uncertain]).
- Fierro et al., "Learning to Plan and Generate Text with Citations," arXiv:2404.03381, 2024 (ACL 2024 [uncertain]).
- Wu, Wu & Zou, "ClashEval," arXiv:2404.10198, 2024 (NeurIPS 2024 D&B [uncertain]).
- Kortukov et al., "Studying LLM Behaviors Under Context-Memory Conflicts With Real Documents," arXiv:2404.16032, 2024 (COLM 2024 [uncertain]).
- Wu et al., "Retrieval Head Mechanistically Explains Long-Context Factuality," arXiv:2404.15574, 2024 (ICLR 2025 [uncertain]).
- Shi et al., "IRCAN," NeurIPS 2024, arXiv:2406.18406.
- Su et al., "ConflictBank," arXiv:2408.12076, 2024 (preprint).
- Zhang et al., "LongCite," arXiv:2409.02897, 2024 (preprint).
- Goyal et al., "Context-Parametric Inversion," ICLR 2025 (oral), arXiv:2410.10796.
- Wang et al., "Astute RAG," ACL 2025, arXiv:2410.07176.
- Zhao et al., "SpARE: Steering Knowledge Selection via SAE-Based Representation Engineering," arXiv:2410.15999, 2024 (NAACL 2025 [uncertain]).
- He et al., "Does Prompt Formatting Have Any Impact on LLM Performance?," arXiv:2411.10541, 2024 (NAACL 2025 industry [uncertain]).
- Chuang et al., "SelfCite," ICML 2025, arXiv:2502.09604.
- Lindsey, Gurnee, Ameisen et al., "On the Biology of a Large Language Model," transformer-circuits.pub, Anthropic, March 2025 (vendor research publication, not peer-reviewed).
- Cuconasu et al., "Do RAG Systems Really Suffer From Positional Bias?," arXiv:2505.15561, 2025 (preprint).
- Saxena et al., "Generation-Time vs. Post-hoc Citation," arXiv:2509.21557, 2025 (preprint).
- Dassen et al., "FACTUM: Mechanistic Detection of Citation Hallucination in Long-Form RAG," arXiv:2601.05866, 2026 (preprint).
- Chen et al., "Does RAG Know When Retrieval Is Wrong? (CDD)," arXiv:2605.14473, 2026 (preprint).
- Zhang & Zhang, "The Structural Attention Tax," arXiv:2606.11198, 2026 (preprint).

Preprints cited [listing-only] (title/first author/date/one-line abstract summary seen in fetched arXiv API result listings; full abstract pages not individually fetched):

Retrieval-head follow-on work:
- Wang et al., "Eliminating Position Bias of Language Models: A Mechanistic Approach," arXiv:2407.01100, 2024.
- Tang et al., "RazorAttention: Efficient KV Cache Compression Through Retrieval Heads," arXiv:2407.15891, 2024.
- Gema et al., "DeCoRe: Decoding by Contrasting Retrieval Heads to Mitigate Hallucinations," arXiv:2410.18860, 2024.
- Zhao et al., "Understanding Synthetic Context Extension via Retrieval Heads," arXiv:2410.22316, 2024.
- Huang et al., "RHIO: Improving Contextual Faithfulness via Retrieval Heads-Induced Optimization," arXiv:2501.13573, 2025.
- Peng et al., "CAFE: Retrieval Head-based Coarse-to-Fine Information Seeking," arXiv:2505.10063, 2025.
- Zhang et al., "QRHead: Query-Focused Retrieval Heads Improve Long-Context Reasoning and Re-ranking," arXiv:2506.09944, 2025.
- Lin et al., "CompressKV: Semantic Retrieval Heads Know What Tokens are Not Important," arXiv:2508.02401, 2025.
- Tran et al., "Contrastive Retrieval Heads Improve Attention-Based Re-Ranking (CoRe)," arXiv:2510.02219, 2025.
- Ma et al., "From Interpretability to Performance: Optimizing Retrieval Heads (RetMask)," arXiv:2601.11020, 2026.
- Lin et al., "Retrieval Heads are Dynamic," arXiv:2602.11162, 2026.
- Bayram et al., "Does RoPE Prevent or Degrade Retrieval Heads? A Mechanistic Analysis Across Model Families," arXiv:2606.21249, 2026.
- Gema et al., "Logit-Contribution Scoring Identifies Non-Literal Retrieval Heads (LOCOS)," arXiv:2607.01002, 2026.

Conflict mitigation, detection, and characterization (2025–2026 wave):
- Lee et al., "CORD: Balancing COnsistency and Rank Distillation for Robust RAG," arXiv:2412.14581, 2024.
- Sun et al., "Task Matters: Knowledge Requirements Shape LLM Responses to Context-Memory Conflict," arXiv:2506.06485, 2025.
- Fu et al., "SI-FACT: Self-Improving Faithfulness-Aware Contrastive Tuning," arXiv:2509.10208, 2025.
- Tighidet et al., "Context Copying Modulation: The Role of Entropy Neurons," arXiv:2509.10663, 2025.
- Bae et al., "That's Deprecated! Understanding, Detecting, and Steering Knowledge Conflicts in Code Generation," arXiv:2510.19116, 2025.
- Zhang et al., "HealthContradict: Evaluating Biomedical Knowledge Conflicts," arXiv:2512.02299, 2025.
- Zhang et al., "Stable-RAG: Mitigating Retrieval-Permutation-Induced Hallucinations," arXiv:2601.02993, 2026.
- Schuster et al., "Whose Facts Win? LLM Source Preferences under Knowledge Conflicts," arXiv:2601.03746, 2026.
- Ye et al., "Seeing through the Conflict: Transparent Knowledge Conflict Handling in RAG," arXiv:2601.06842, 2026.
- Pham et al., "Where Knowledge Collides: A Mechanistic Study of Intra-Memory Knowledge Conflict," arXiv:2601.09445, 2026.
- Ma et al., "CoRect: Context-Aware Logit Contrast for Hidden State Rectification," arXiv:2602.08221, 2026.
- Tang et al., "Diagnosing Knowledge Conflict in Multimodal Long-Chain Reasoning," arXiv:2602.14518, 2026.
- Ashik et al., "When LLMs Lag Behind: Knowledge Conflicts from Evolving APIs in Code Generation," arXiv:2604.09515, 2026.
- Zhao et al., "Exploring Knowledge Conflicts for Faithful LLM Reasoning: Benchmark and Method," arXiv:2604.11209, 2026.
- Cheng et al., "The Override Gap: Knowledge Conflict Failure in Hypernetwork-Based Adaptation," arXiv:2604.23750, 2026.
- Zhou et al., "Mitigating Context-Memory Conflicts through Dynamic Cognitive Reconciliation Decoding," arXiv:2605.12185, 2026.
- Wang et al., "ConflictRAG: Detecting and Resolving Knowledge Conflicts in RAG," arXiv:2605.17301, 2026.
- Jeripity Venkata et al., "Do Models Know Why They Changed Their Mind? CoT Faithfulness Under Knowledge Conflict," arXiv:2605.27773, 2026.
- Laraspata et al., "Analyzing the Correlation Between Hallucinations and Knowledge Conflicts," arXiv:2606.08705, 2026.
- Jiang et al., "From Context-Aware to Conflict-Aware: Generalizing Contrastive Decoding for Knowledge Conflict," arXiv:2606.10298, 2026.
- Peng et al., "Navigating Unreliable Parametric and Contextual Knowledge: Explicit Knowledge Conflict Resolution," arXiv:2606.20245, 2026.
- Li et al., "SHIFT: Gate-Modulated Activation Steering for Knowledge Conflict Mitigation in RAG," arXiv:2606.27786, 2026.
- Lietzow et al., "Vision-Default, Prior-Override: Causal Mechanisms of Perception-Knowledge Conflict in VLMs," arXiv:2606.28273, 2026.
- Wang et al., "Regime-Aware Peer Specialization for Robust RAG under Heterogeneous Knowledge Conflicts," arXiv:2606.30518, 2026.

Attribution/citation methods and applications:
- Xu et al., "CiteCheck: Towards Accurate Citation Faithfulness Detection," arXiv:2502.10881, 2025.
- Wang et al., "ScholarCopilot: Training LLMs for Academic Writing with Accurate Citations," arXiv:2504.00824, 2025.
- Shen et al., "Transparentize Internal and External Knowledge Utilization with Trustworthy Citation (Context-Prior Augmented Citation Generation)," arXiv:2504.14856, 2025.
- Maheshwari et al., "CiteFix: Enhancing RAG Accuracy Through Post-Processing Citation Correction," arXiv:2504.15629, 2025.
- Chen et al., "Concise and Sufficient Sub-Sentence Citations for RAG," arXiv:2509.20859, 2025.
- Qian et al., "VeriCite: Reliable Citations in RAG via Rigorous Verification," arXiv:2510.11394, 2025.
- Vishwakarma et al., "What Gets Cited: Competitive GEO in AI Answer Engines," arXiv:2605.25517, 2026.
- Elganayni et al., "Re-Ranking Through an Attribution Lens for Citation Quality in Legal QA," arXiv:2606.03728, 2026.

Note on coverage: sibling dossiers hold the attribution *evaluation* literature (ALCE, LongBench-Cite metric design, CiteME etc.), the corrective/adaptive architecture line (CRAG, Self-RAG, CoVe), and long-context-vs-RAG position studies beyond the format-sensitivity results cited here.
