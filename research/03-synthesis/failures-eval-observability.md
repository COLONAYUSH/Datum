# Evaluation & Observability Failures — Cross-Framework Synthesis

**Dimension:** eval-observability · **Compiled:** 2026-08-05 · **Corpus:** 18 framework/platform autopsies + cross-cutting-gaps.md in `research/02-frameworks/`, landscape files `evaluation-benchmarks.md`, `aigc-contamination-geo.md`, `retrieval-training-lineage.md` (QPP) in `research/01-landscape/`.

## Method note

The `### evaluation-observability` section of all 19 files in `02-frameworks/` was read in full, plus surrounding retrieval-quality/production-ops context where eval-relevant findings were filed under other taxonomy headings (e.g., FlashRAG's per-query net-negative-retrieval finding sits under retrieval-quality; the OpenAI silent regression sits under production-ops). Landscape files were read for the research-side view. Threshold for "common": documented evidence in ≥3 independent frameworks/platforms; documented-recurring items form the spine, single-anecdote and architectural-inference items are supporting color only and marked as such. Blacklisted weak-evidence claims (per corpus audit) were excluded: no Enterprise DNA/skywork quantified LangChain figures, no ragflow third-party review-site corroboration (GitHub issues/HN/vendor docs from that file are used instead), no Pinecone platform-risk claim, no "$33,000/5GB" GraphRAG figure, and "no independent replication found" search-negatives are treated as unverified absence, not evidence. Framework names below are the corpus file slugs.

One framing note: this dimension is unusual in that almost every issue is **an absence rather than a bug** — so the strongest evidence is often a vendor's own docs conceding the gap, a years-open feature request, or a third party building the missing piece. Where a claimed absence rests only on design review, it is labeled architectural-inference and weighted accordingly.

---

## Issue index

| # | Slug | One-liner | Frameworks |
|---|---|---|---|
| 1 | `no-eval-loop` | No framework ships closed-loop retrieval-quality evaluation in its core tier | 15 |
| 2 | `spans-not-stages` | Observability instruments LLM calls, never retrieval stages — bad answers unattributable | 11 |
| 3 | `self-graded-homework` | Headline quality claims are vendor-run on vendor-chosen data/metric/judge and shrink on re-run | 8 |
| 4 | `judge-monoculture` | The only shipped metrics are uncalibrated LLM-judge wrappers with no bias controls | 7 |
| 5 | `no-reproducible-run` | No pinned (model, corpus, config, index) tuple; paper/platform/OSS silently diverge | 6 |
| 6 | `open-loop-production` | Feedback never reaches the retriever; no drift detection; regressions ship unnoticed | 7 |
| 7 | `qpp-amnesia` | No calibrated per-query difficulty/sufficiency signal, two decades after QPP | 6 |
| 8 | `toy-target-autotuning` | Auto-optimizers select "production" configs against ≤25–107-example synthetic eval sets | 3 |

### Coverage matrix (● = documented in that file's dossier; ○ = supporting/inferred)

| Framework | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| langchain-langgraph | ● | ● | | | | ○ | ○ | |
| llamaindex | ● | ○ | | ● | ● | | | |
| haystack | ● | ● | | | | ○ | | |
| dspy | ● | ● | | | ● | ● | | ● |
| ragflow | ● | ● | ● | | | ● | ● | |
| hkuds-lightrag-family | ● | ● | ● | ● | ● | | | |
| microsoft-graphrag | ● | ● | ● | ● | | | | |
| research-toolkits | ● | | | ● | ● | | ● | ● |
| jvm-js-ecosystems | ● | ● | | ● | | | | |
| lowcode-builders | ● | ● | | | | ● | | |
| oss-rag-platforms | ● | | | | | ● | ● | |
| agent-framework-retrieval | ● | | ● | | | ○ | ● | |
| memory-and-localfirst | ● | | ● | ● | ● | | | |
| managed-openai-azure | ● | ● | | | ● | ● | ● | |
| managed-aws-google | ● | ● | | | | | | |
| datacloud-rag | ○ | | ● | | | | | |
| vectordb-and-startup-platforms | ● | | ● | | | ● | ● | |
| gpu-vendor-enterprise-rag | ○ | ● | ● | ● | | ● | | ● |

## The common issues

### 1. `no-eval-loop` — The missing evaluation loop

**Definition:** No mainstream framework or platform ships a closed-loop retrieval-quality evaluation capability — golden-set construction, regression testing across ingest/config changes, per-stage quality attribution — in its free/core tier; assessment is manual trial-and-error or outsourced to third parties.

This is the single most universal finding in the corpus: 15 of 18 dossiers document it independently, most as documented-recurring or vendor-conceded.

| Framework | Evidence pointer |
|---|---|
| langchain-langgraph | E1: OSS core ships no retrieval-quality evaluation (docs#4722 confirms no measurement guidance); evals/Insights are LangSmith commercial features central to the platform strategy (series-b blog) |
| llamaindex | E1: eval modules are LLM-judge wrappers with no dataset/versioned-run/regression workflow; docs push RAGAS/Arize/Langfuse; #17116 users can't even configure judges |
| haystack | RFC #11867 "Retrieval Diagnostics API for RAG Pipelines" + #10591 "RAG failure mode checklist" — components, not closed-loop tuning; evaluators mix errors into results (#7973, open since 2024) |
| dspy | EO-1 (critical): the eval loop is 100% user-supplied — value prop gated on a labeled trainset + automated metric most teams don't have |
| ragflow | Assessment = manual "retrieval test" UI; no golden-set/regression evals; eval tracking is a community request (#6155) |
| hkuds-lightrag-family | E4: no built-in eval loop; observability is log lines; Langfuse an unimplemented request (#2936) |
| microsoft-graphrag | No eval harness, no relevance/faithfulness metrics; users can't tell whether the expensive graph helps on their corpus — external studies (arXiv:2502.11371, 2503.04338) had to fill the gap |
| research-toolkits | Even reproducibility toolkits score with near-noise EM/F1 by default (see issue 4) and AutoRAG's "eval loop" optimizes 107 synthetic pairs (see issue 8) |
| jvm-js-ecosystems | E1/E2: LangChain4j ships no eval module (Langfuse tracing request #2328 open 20 months); across the cohort "nobody answers 'did retrieval return the right chunks?'" |
| lowcode-builders | No native eval harness in Dify/Flowise/Langflow/n8n; Dify hit-testing "measures nothing systematically" (#36268; HN 40121318 wishlist) |
| oss-rag-platforms | E1: none of seven ships an eval loop; AnythingLLM's official debugging advice for bad answers is manual knob-tweaking; R2R had the best story (request logging/analytics) and is dead |
| agent-framework-retrieval | E1 (critical, cohort-wide): none of ten agent frameworks expose retrieval/memory quality metrics; Letta's tracker admits "lacks any standardized benchmark or evaluation code" (letta#3115) |
| memory-and-localfirst | I2e: no eval story anywhere in the local-first cohort; "with no measurement, 'the answers are wrong' is unactionable" |
| managed-openai-azure | OpenAI: "no built-in way to test relevance before production"; Azure: no built-in relevance evaluation either |
| managed-aws-google | Neither Bedrock KB nor Gemini File Search ships golden-set retrieval metrics or regression testing as a first-class feature |
| vectordb-and-startup-platforms | No customer-side regression harness in Pinecone Assistant/Vectara/GroundX/Ragie; Chroma's Generative Benchmarking is "the exception that proves the rule" |

Supporting color (kept below the spine): the two-tier variants are telling. AWS's new retrieval traces (AgentCore Observability) are Managed-KB-only — the eval capability exists but is used to differentiate the higher-lock-in tier (managed-aws-google). And the closest thing to a counterexample, NVIDIA's published eval harness (`scripts/eval/`, seven public datasets, documented judge), is conceded by its own dossier to be methodologically circular (gpu-vendor, "more eval transparency than most OSS frameworks, even though the methodology is circular") — the exception ships the artifact but not the epistemics.

**Root cause.** Three reinforcing mechanisms. (a) **Open-core economics:** evaluation is the most monetizable seam in the stack — LangSmith, deepset's Enterprise Platform, Databricks MLflow/Agent Evaluation, LlamaCloud all gate eval/observability behind the paid tier, so the incentive gradient keeps measurement out of the OSS core permanently (langchain E1 states this as the structural diagnosis; haystack's dossier independently identifies the same "classic open-core seam" for the adjacent freshness subsystem). (b) **The metric-bootstrap problem:** at install time no ground truth exists, and frameworks have no mechanism to manufacture it from the user's corpus — so the honest default is "no eval," and DSPy shows what happens when you instead demand the user bring one: the addressable market collapses to eval-mature teams ("As soon as you move the goalposts you also have to update the dataset," HN 47490365). (c) **Demo-driven adoption:** stars and quickstarts reward five-minute time-to-first-answer; an eval harness adds friction to exactly that funnel and pays off only after adoption is already won. Note that (b) explains why the gap exists and (a) explains why it persists: any vendor that solved the bootstrap problem in OSS would be commoditizing its own paid tier.

**Research context.** This is a non-adoption failure, not a research gap. RAGAS/ARES/TruLens/RAGChecker/TRACe have existed since 2023–24; Chroma's generative benchmarking (2025) demonstrated that corpus-derived eval sets can be auto-built with aligned judges (46%→75.2% human alignment over 5 iterations); the Coverage Illusion study (arXiv:2605.27220) showed serving telemetry is the strongest eval signal and offline synthetic distributions misestimate operational quantities by >3× (90% predicted vs 27.8% actual augmentation need). The landscape's open problem O5 — production telemetry as a typed evaluation stream — names the architecture no framework has. What genuinely remains unsolved: judge-calibration label budgets (O3) and eval-set maintenance under corpus drift (F8).

**Next-gen requirement (testable):** The core OSS framework must ship a self-bootstrapping eval subsystem: given only the user's corpus, it generates a stratified, aligned-judge-filtered golden set; any change to chunker, embedder, index config, or corpus produces a before/after retrieval-quality report; a CI-style gate can fail on regression. Acceptance test: a user with zero labeled data gets a defensible retrieval-quality regression signal on their own corpus, offline, without any third-party service or paid tier.

---

### 2. `spans-not-stages` — Observability stops at LLM spans; retrieval is a runtime black box

**Definition:** Where observability exists at all, it instruments LLM calls (latency, tokens, spans) and logs *that* retrieval happened — never *what* retrieval did (which parser fired, which candidates were scored how, why a chunk entered the context) — so bad answers cannot be attributed to a pipeline stage.

| Framework | Evidence pointer |
|---|---|
| jvm-js-ecosystems | E2: Spring AI Micrometer measures latency/tokens/tool calls, "no recall/precision/groundedness instrumentation"; AI SDK telemetry = OTel spans of model calls |
| ragflow | Pipeline opacity: no per-stage inspection API (which parser, which template rule, why a boundary); FAQ prescribes grepping container logs; tracing only via third-party Langfuse |
| haystack | Tracing blind-spot cluster: multiple Langfuse traces per run (#1604), sub-pipelines not unified (#1605), LLM I/O not captured (#1423), #1154 open since 2024 — "bolt-on per-integration rather than first-class runtime concern" |
| managed-aws-google | Bedrock `RetrieveAndGenerate` returns empty `retrievedReferences` while generating source-mapped answers (SO 78433567); Gemini File Search "completely headless… you are often flying blind" — a third party built the missing UI |
| managed-openai-azure | Azure docs concede "precise reconstruction of a query or response isn't guaranteed" from the activity log; OpenAI: no per-stage traces |
| gpu-vendor-enterprise-rag | E3: agentic mode returns empty/missing response metadata — citation checking and audit break exactly in the mode you'd most want to audit; E4: watsonx ships a known issue literally titled "Observability", workaround: No |
| microsoft-graphrag | No query-time tracing of which entities/communities contributed to an answer beyond raw context dumps |
| hkuds-lightrag-family | E4: observability is log lines |
| lowcode-builders | Debugging opacity: no way to attribute a bad answer to chunking vs embedding vs top-k vs prompt; the abstraction hides the intermediate retrieval set |
| dspy | EO-2: optimizer runs are a black box — no cost dry-run (#397, from 2023), silent stalls (#1970, #1708) |
| langchain-langgraph | Tracing defaults are LangSmith env-var activation; the OSS path is print-debugging six-object dives |

**Root cause.** Observability tooling was imported wholesale from APM: OpenTelemetry gives you spans, and the LLM call is the only component with a standardized I/O vocabulary — so tools trace what is typed and skip what is not. Retrieval has **no standard intermediate representation**: there is no typed "candidate set with per-stage scores" artifact in any framework's API, so there is nothing for a tracer to hook. Secondary force: hosted trace dashboards are the paid tier (issue 1's economics recur), and vendors' managed offerings actively benefit from opacity — a headless service whose chunks can't be inspected also can't be benchmarked against a competitor.

**Research context.** The measurement science exists: TRACe (arXiv:2407.11005) and RAGChecker (arXiv:2408.08067) define per-stage, explainable diagnostics (utilization/relevance/adherence/completeness; joint retriever-generator attribution). This is an engineering-contract failure, not a science failure. The genuinely open part is process-level evaluation of *multi-step* retrieval (landscape F9/O6: no accepted way to score reformulation gain, stopping-rule regret, per-call marginal evidence value) — which is exactly the metadata that gpu-vendor E3 shows vendors dropping first.

**Next-gen requirement (testable):** Every retrieval — single-pass or agentic — must emit the same typed, persistent trace artifact: query, rewrites, per-stage candidate sets with scores, fusion weights, and final context with provenance, inspectable locally without a paid service. Acceptance test: metadata parity between single-pass and agentic execution paths (byte-identical schema), and a "why is this chunk in my context?" query answerable from the trace alone for 100% of served responses.

---

### 3. `self-graded-homework` — Vendor self-benchmarking fills the evaluation vacuum

**Definition:** Headline quality claims across the ecosystem are produced by the vendor, on the vendor's chosen data, metric, and judge — frequently with competitors configured naively — and routinely fail or shrink when independently re-run.

| Framework | Evidence pointer |
|---|---|
| vectordb-and-startup-platforms | "The segment's defining epistemic problem": EyeLevel/GroundX 97.83% vs LangChain 64.13% with competitors in "the most straightforward setup" while GroundX was optimized; Pinecone "up to 12%" internal; Ragie 99.4% self-run; Vectara self-run (all vendor primary pages) |
| gpu-vendor-enterprise-rag | E1 (critical): NVIDIA selects "the pipeline, the hardware, the metric, the judge model, and the judge-selection benchmark" — ablations only, no external baseline; E2: 15×/3×/35×/50% figures all vendor-measured against unnamed baselines |
| datacloud-rag | EO-1: Cortex Analyst "90%+ accuracy, ~2x GPT-4o" from "our comprehensive internal benchmark suite"; Databricks "best Text2SQL", "up to 10x lower cost" from internal evals; the two vendors benchmark against each other |
| memory-and-localfirst | I1 (critical): Mem0's LoCoMo SOTA claim — Zep's corrected rerun scored Zep 75.14% vs Mem0g ~68%, and a plain full-context baseline (~73%) beat Mem0's best; Letta independently got 74.0% with GPT-4o-mini + a filesystem |
| agent-framework-retrieval | E2: the same benchmark war from the agent side — MemGPT baseline mis-implemented; "they completely botched the implementation of their competitors" (HN 44883134) |
| hkuds-lightrag-family | E2: RAG-Anything's DocBench 63.4% claim re-run by a user at 40.5% (#235, no maintainer response); E3: GraphRAG-Bench (arXiv:2506.05690) measures LightRAG *below* vanilla RAG on fact retrieval while consuming ~100k prompt tokens vs ~900 |
| microsoft-graphrag | The founding paper's eval was LLM-judged win rates on 2 corpora with no ground-truth accuracy — "weak by 2026 standards"; independent studies found graph wins situational |
| ragflow | The inverse variant: zero published benchmarks for DeepDoc since launch despite demands from day one (HN 39896923) — "the quality-vs-marketing gap is unfalsifiable by design" |

Two calibrating nuances, both from the same files: the pattern admits honorable exceptions (Snowflake's Arctic-Embed numbers sit on the public MTEB leaderboard — datacloud EO-1 singles this out precisely because it is the exception), and it sometimes runs in reverse — Qdrant's own miniCOIL article concedes NDCG@10 gains of 0.007–0.018 over BM25 while the surrounding marketing claims to solve BM25's "meaning problem" (vectordb, vendor-admitted). Self-benchmarking is not always dishonest measurement; it is measurement whose framing is unconstrained.

**Root cause.** A market with no neutral referee converges on self-graded homework. Because buyers lack eval infrastructure (issue 1), marketing numbers face no falsification pressure; LLM-judge win rates make impressive-looking evaluation nearly free to manufacture and easy to (even unconsciously) tune; and the asymmetric-configuration pattern — optimize yours, default theirs — is undetectable without a published harness. The Big ANN NeurIPS'23 competition report (arXiv:2409.17424, via cross-cutting-gaps) sharpens it: the benchmark community moved to filtered/streaming/out-of-distribution workloads years ago, while vendor pages still report static-corpus, unfiltered, in-distribution numbers — vendors benchmark the workload they win, not the one customers run. There is also a structural reason the corrections come from competitors: they are the only actors with both the incentive and the eval capability to re-run a rival's numbers, which converts what should be neutral falsification into benchmark wars whose net effect on buyer trust is negative-sum (agent-framework E2).

**Research context.** The literature explains both the mechanism and the fix. Mechanism: judge-bias work (position, verbosity, self-preference — arXiv:2406.07791, 2410.21819) shows why win-rate self-evals inflate; MTEB gaming (Reimers: "you see a massive shift in the ranking… on private data") shows any leaderboard that matters gets Goodharted; Chroma reproduced held-out queries from 9/9 public datasets, so even honest public-benchmark claims measure memorization. Fix-shaped institutions exist — TREC RAG 2024/25 (NIST pooling), SIGIR LiveRAG, FreshStack-style renewable benchmarks — but no *product* category participates in them. The memory-benchmark war happened on LoCoMo, a benchmark all parties agree is broken (contexts fit in modern windows, missing ground truth) — the war itself was downstream of having no valid instrument.

**Next-gen requirement (testable):** All first-party quality claims must be replicable by construction: pinned configs for every compared system, a published one-command harness, disclosed judge + calibration data, and competitor configurations validated against those vendors' documented best practice. Acceptance test: a third party can reproduce the headline number within stated confidence bounds on public infrastructure, or the framework's own docs label the claim unverified.

---

### 4. `judge-monoculture` — Uncalibrated LLM-as-judge is the only shipped measurement

**Definition:** Where frameworks ship any quality metric at all, it is a prompted-LLM judge wrapper (RAGAS-style faithfulness/relevancy or pairwise win rates) with no calibration slice, no bias controls, and no reported agreement with humans — known-unreliable exactly where discrimination matters.

| Framework | Evidence pointer |
|---|---|
| llamaindex | E1: `FaithfulnessEvaluator`/`RelevancyEvaluator` are LLM-judge wrappers with no regression harness; #17116 (17 comments) users struggling to configure judge models coherently |
| jvm-js-ecosystems | Spring AI's `RelevancyEvaluator`/`FactCheckingEvaluator` — "themselves basic LLM-as-judge stubs" (E1) |
| hkuds-lightrag-family | E1: with the paper's own eval prompt, "answer 1 always wins before and after exchanging the order of answers" — textbook position bias, in the shipped eval (#288); repro asks closed unresolved (#1112) |
| microsoft-graphrag | Win-rate LLM-as-judge eval (comprehensiveness/diversity/empowerment), no ground-truth faithfulness — while 17 issues report hallucination pass-through |
| gpu-vendor-enterprise-rag | E1: judge model chosen via NVIDIA's own judge leaderboard; metric is "the NVIDIA Answer Accuracy metric from RAGAS"; E5: watsonx AutoAI judges patterns on ≤25 QA pairs |
| research-toolkits | AutoRAG node metrics are RAGAS context precision / G-Eval — "themselves LLM-judged and noisy"; the fallback is EM/F1, which BERGEN measured at 0.062 average correlation with GPT-4 judgments (near-noise; FlashRAG #74: EM 0.038 vs Acc 0.374 from parsing artifacts) |
| memory-and-localfirst | I1: the LoCoMo "J" scores at the center of the benchmark war are LLM-judged |

**Root cause.** LLM judges have zero annotation cost and zero calibration *requirement*, so they are the path of least resistance for a framework that must ship something. The calibration protocol requires human labels the framework cannot provide (the bootstrap problem again), so the wrapper ships without it — and its biases are invisible by construction: a position-biased judge still returns confident numbers. The alternative default, string-overlap metrics, is worse (near-noise for chatty models), so toolkits face a choice between a noisy metric and a biased one and ship whichever is cheaper.

**Research context.** Fully mapped, largely ignored. JudgeBench (arXiv:2410.12784): GPT-4o ≈ random on objectively-resolvable hard pairs. Position/verbosity/self-preference biases are systematic and strongest when candidates are close — exactly when you need the judge. The constructive results are equally clear: task-narrowed judges work (TREC support eval: GPT-4o agrees with humans as well as humans agree with each other on 3-level citation support); small fine-tuned evaluators beat prompted frontier judges (RAGBench's RoBERTa result, LettuceDetect, ARES); PPI-style correction against a ~150-example human slice gives confidence intervals. No framework in the corpus ships any of these; landscape verdict: "raw single-prompt GPT-judging is considered indefensible for paper-grade claims post-JudgeBench" — yet it is the industry default.

**Next-gen requirement (testable):** The framework refuses to report an uncalibrated judge score: every LLM-judged metric carries (a) a human-anchored calibration slice with reported judge-human AND human-human agreement, (b) an automatic bias audit (candidate-order swap test, length-control test) that must pass before results render, (c) confidence intervals via PPI-style correction. Acceptance test: swapping candidate order changes win rates by less than the reported CI; a deliberately position-biased judge configuration is auto-flagged and blocked.

---

### 5. `no-reproducible-run` — No reproducible-retrieval primitive; published numbers don't survive re-running

**Definition:** Retrieval quality is a joint property of (model version, corpus snapshot, chunker, index build, config), and no framework names, pins, or replays that tuple — so paper results diverge from OSS behavior, OSS diverges from hosted platforms, SaaS components mutate server-side, and even the toolkits built for reproducibility fail to reproduce their own tables.

| Framework | Evidence pointer |
|---|---|
| research-toolkits | Reproduction of the toolkits' own tables fails routinely: FlashRAG #40, #42, #85 (user got NQ 19.0 vs reported higher), #185, #44 ("which seed?"); seeds change nothing under vLLM (#79) — "even reproducibility toolkits have a reproducibility problem" |
| hkuds-lightrag-family | E1: #1112 "Has anyone reproduced the experimental results?" + #492/#97/#364/#2 all closed without substantive resolution; `reproduce/` scripts partial |
| memory-and-localfirst | I2: "Mem0" names three non-equivalent systems (paper's retired architecture, hosted platform with reranking stages, OSS library without them); #2800 "Unable to reproduce locomo eval scores locally" is the repo's most-reacted issue (25 comments) |
| llamaindex | LlamaParse is a remote, versioned SaaS: "behavior changes ship server-side without user control — a reproducibility hazard for regulated pipelines" |
| managed-openai-azure | Sept 2025: server-side mis-indexing silently degraded retrieval for ~6 days platform-wide; Responses v2 broke `file_search` parameters sequentially while docs lagged — the substrate mutates under the user |
| dspy | Benchmark results (Assertions, arXiv:2312.13382) describe an API removed two majors ago; official FAQ still teaches it; compiled artifacts are opaque and non-diffable (AD-1) |

**Root cause.** The ecosystem has no equivalent of a lockfile for a retrieval system. Research code treats the *pipeline class*, not the *run*, as the artifact — configs, corpus versions, and seeds are incidental. Commercial platforms have the opposite incentive: server-side mutability is the product (continuous improvement, no migration burden), and a pinnable, exportable run manifest would also be a benchmarkable, portable one — eroding lock-in. Paper/platform/OSS divergence (Mem0) is the open-core version: the published number advertises the paid pipeline while the OSS repo carries the citation.

**Research context.** The landscape names this precisely: F8 — "RAG quality is a joint property of (model, corpus, chunking, index, query distribution); benchmarks fix all but the model, so published numbers are non-portable," with FreshStack and generative benchmarking showing both absolute and ordinal instability. O2 calls for evaluation with a validity half-life and machine-readable provenance. The research documents the problem thoroughly; nobody ships the primitive.

**Next-gen requirement (testable):** A reproducible-run primitive: content-hashed corpus snapshot + pinned model/config manifest + recorded retrieval traces, with deterministic replay (or an explicit, quantified non-determinism declaration). Eval results bind to manifests, not to library versions. Acceptance test: replaying a recorded run against the same manifest reproduces identical candidate sets; any server-side change in a SaaS component surfaces as a manifest hash change before it surfaces as a quality mystery.

---

### 6. `open-loop-production` — No feedback-to-retriever loop and no drift detection

**Definition:** Production signals — user feedback, reformulations, corpus changes, silent quality regressions — never reach the retriever: feedback (where a widget exists at all) terminates in a dashboard, no framework updates ranking from outcomes, and no framework alarms when retrieval quality changes after an ingest or upstream event.

| Framework | Evidence pointer |
|---|---|
| cross-cutting-gaps | (b), documented-recurring: no framework closes the loop — "feedback" is thumbs-up telemetry to an offline dashboard, "a number a human reads, not a signal that updates retrieval." The intra-vendor asymmetry is the proof: Google Retail search *requires* ≥250k logged events to tune ranking, while the same vendor's RAG surfaces ship no user-event ingestion path at all |
| lowcode-builders | No drift detection despite documented silent regressions: retrieval degrades after adding content (Dify #21964); stale vectors keep being retrieved after updates (Flowise #3570, 29 comments) — "regressions ship unnoticed" |
| dspy | PO-3: nothing detects drift between compile-time trainset and serve-time corpus; optimized prompts silently rot |
| managed-openai-azure | During the Sept 2025 regression "customers had no signal except worse answers" — six days of degradation invisible to every downstream eval-less deployment |
| gpu-vendor-enterprise-rag | E4: watsonx "User feedback count is not updated when Thumbs up/Thumbs down is selected — Workaround available: No" — the feedback widget itself is a documented open defect |
| oss-rag-platforms | E1: no drift detection or per-stage attribution; A1: no calibrated relevance/coverage/freshness metadata an agent loop could branch on; R2R's freshness-signal request (#2300) landed in a dead repo |
| vectordb-and-startup-platforms | "Agentic" = LLM-planned querying; none of eight offers feedback into ranking or retrieval budgeting for loops |

Supporting color: the drift half of the loop is just as absent as the feedback half. Across all four low-code builders, switching the embedding model silently invalidates the entire index with no incremental/versioned re-embedding path, and ragflow's retrieval-test tunings silently fail to persist to assistants — production runs on defaults with no signal that anything is mis-set (lowcode-builders; ragflow retrieval-quality, docs-evidenced). Silent degradation is the default failure mode of an open-loop system.

**Root cause.** Classical search's closed loop (log → debias → retrain → ship → measure) needs three things RAG frameworks structurally lack: log ownership (libraries have no serving plane — there is nowhere for the loop to live), traffic volume (Google's own 250k-event floor exceeds most enterprise RAG deployments), and LTR expertise (the theory is IR, the builders are LLM engineers). Naive shortcuts actively harm — training on biased feedback degrades ranking (arXiv:2506.20501) — which raises the implementation bar high enough that everyone defers. And open-core economics again: telemetry that does flow lands in the paid dashboard as a chart, because a chart renews subscriptions and a self-tuning retriever does not. The cross-cutting file's summary is exact: the frameworks ship retrievers, rerankers, and (occasionally) eval harnesses, "and the wire between the last two and the first does not exist."

**Research context.** The strongest "solved elsewhere, ignored here" case in this dimension. Unbiased learning-to-rank from biased clicks has been settled theory since 2016 (Joachims et al., arXiv:1608.04468); the pitfalls of naive loops are mapped (two-tower confounding); the Coverage Illusion study shows escalation signals from a serving cascade function as online eval labels (+0.140 composite quality, −31.8% latency). Genuinely open: the low-traffic regime (below the event floor — pooling/transfer/synthetic-propensity approaches), and adversary-awareness, since a feedback channel is a poisoning channel (AgentPoison: <0.1% poisoning rates suffice).

**Next-gen requirement (testable):** Typed feedback events (accept/reject/reformulate/escalate/retrieval-empty) ingested by default and exportable with propensity metadata; a debiased update path (IPS-corrected or bandit) that explicitly refuses to activate below a stated traffic floor rather than learning garbage; drift monitors bound to the issue-1 golden set. Acceptance test: a corpus change that degrades a golden slice raises an alert within N queries without human dashboard-watching; recorded feedback replays into a measurable ranking improvement on a held-out slice.

---

### 7. `qpp-amnesia` — No per-query difficulty/sufficiency/confidence signal, two decades after QPP

**Definition:** No framework tells the caller — human or agent — how likely a given retrieval is to be good: scores are raw, uncalibrated similarities (sometimes from incompatible scoring regimes fused together), there is no per-query "this retrieval probably failed / sufficed" estimate, and retrieval that actively harms answers goes undetected per-query.

| Framework | Evidence pointer |
|---|---|
| research-toolkits | Retrieval is net-negative on whole datasets (BERGEN Fig. 3: TruthfulQA/ELI5/WoW degrade with retrieval; RAGLab MCQ regression) "and no toolkit's default pipeline detects this per-query"; FlashRAG's Judger component exists but is used by two methods and confuses users (#21) |
| ragflow | Two uncalibrated scoring regimes fused: KG-derived chunks scored by pure cosine while normal chunks use hybrid fusion — "results from the two paths are not calibrated against each other" (docs) |
| vectordb-and-startup-platforms | Agent loops get raw similarity; no calibrated relevance, no retrieval budgeting; score-fusion correctness bugs on top (qdrant#7889) |
| oss-rag-platforms | A1: "No platform returns calibrated relevance/coverage/freshness metadata that an agent loop could branch on" |
| managed-openai-azure | OpenAI file_search invoked non-deterministically with "prompt begging" as the fix; Azure agentic planning "can miss relevant angles with no feedback loop" |
| agent-framework-retrieval | E1: recall@k, groundedness, memory-hit usefulness — none exposed as first-class signals in any of ten frameworks |

**Root cause.** RAG grew out of the NLP/LLM community, not IR: query performance prediction — Clarity (SIGIR 2002), WIG (2007), NQC (TOIS 2012), twenty years of pre/post-retrieval predictors — is simply absent from framework authors' working knowledge, so production RAG keeps reinventing "retrieval confidence from similarity scores" (NQC's variance signal) from scratch, badly. There is also an honest technical headwind: classical QPP transfers poorly to dense retrieval (Faggioli et al., ECIR 2023: predictors significantly worse on neural systems; Chifu 2025: poor cross-collection generalization), so a naive port would underdeliver — but the field responded (LLM-judged QPP, QPP as agent control signal) and frameworks ship neither the old nor the new. Meanwhile raw cosine scores are not comparable across stores, models, or fusion paths, and vendors don't even normalize them (langchain's A2 bug class; ragflow's dual regimes).

**Research context.** The landscape file's own framing: QPP is "the mature field that per-query difficulty estimation open-problem lists keep reinventing." Every agentic-RAG control decision maps to a named QPP problem — should I retrieve (pre-retrieval QPP), did it work (NQC/WIG), which rewrite (QPP-guided variant selection, arXiv:2604.22661), should I stop (QPP inside agent loops — arXiv:2507.10411 shows QPP estimates of agent queries correlate with final answer quality). Sufficiency — the retrieval-side property RAG actually needs, distinct from topical relevance (landscape F3, SURE-RAG) — has no standardized metric yet; and "corpus performance prediction" (dedup/freshness/provenance as predictable inputs to quality) does not exist at all.

**Next-gen requirement (testable):** Every retrieval response carries a calibrated per-query confidence/sufficiency estimate with documented calibration methodology, exposed in the agent-facing API for branching (retrieve-more / reformulate / abstain / escalate). Acceptance test: the shipped confidence signal predicts downstream answer quality on held-out slices strictly better than raw top-1 similarity, and thresholding it trades coverage for accuracy along a published, monotone curve — including correctly flagging the queries where retrieval is net-negative and should be skipped.

---

### 8. `toy-target-autotuning` — Auto-optimization against statistically meaningless eval sets

**Definition:** Products that automate RAG configuration select chunkers, embedders, retrieval depth, and prompts by optimizing against eval sets far too small and too synthetic to distinguish configurations — then present the winner as production-grade.

| Framework | Evidence pointer |
|---|---|
| gpu-vendor-enterprise-rag | E5: watsonx AutoAI for RAG evaluates patterns on "up to 25 question and answer pairs" over sampled files and presents the winner as "an optimized, production-quality RAG pattern" — "an overfitting machine" (vendor docs) |
| research-toolkits | AutoRAG's flagship experiment selects a whole pipeline from 107 GPT-4-generated QA pairs, scored by noisy LLM-judged node metrics; greedy per-node optimization is structurally myopic (own paper's stated limitation, arXiv:2410.20878; empirically improved by AutoRAGTuner, arXiv:2605.02967) |
| dspy | EO-1/PC-1: optimization quality is bounded by the user-supplied trainset/metric; LLM-judge metrics become "a second optimization surface with their own drift"; MIPROv2 confirmed ignoring demo-count limits (#8508) |

**Root cause.** Auto-tuning is a product checkbox ("we optimize your RAG for you") whose statistical prerequisites — a large, stratified, corpus-representative eval set — are exactly what issue 1 says nobody can produce. So vendors ship point estimates on tiny synthetic targets, because the optimizer must have *something* to climb; and since the metric is usually LLM-judged (issue 4), the climb partly optimizes judge-pleasing. The result is a confident, specific, wrong answer to "what configuration should I run?" — worse than no answer, because it forecloses further inquiry.

**Research context.** The landscape quantifies the failure: synthetic sets rank retriever knobs acceptably but misrank generators (arXiv:2508.11758); synthetic query distributions misestimate operational quantities by >3× (Coverage Illusion); averages on unstratified sets conceal the tail slices where systems fail (CRAG strata; semantic stratification with formal coverage guarantees, arXiv:2604.20763). None of the shipped optimizers reports variance, CIs, or coverage.

**Next-gen requirement (testable):** Optimizers must report the statistical power of their target — n, confidence intervals, stratification coverage — and must refuse (or prominently flag) selections between configurations that are not statistically separable. Acceptance test: rerunning the optimizer on a resampled eval set of equal size must either select a configuration statistically indistinguishable in measured quality or surface the instability, rather than emitting a different "optimal pipeline" with equal confidence.

---

## Near-misses

Patterns real but under the 3-framework evidence bar, or evidenced mainly on the research side — kept honest here.

- **Contamination blindness.** Research-toolkits is the one framework cohort with direct evidence: frozen wiki-2018 default corpora that BERGEN itself concedes are in LLM pretraining data, "render[ing] retrieval obsolete" for some datasets and confounding all absolute numbers. The landscape side is overwhelming (Chroma reproduced queries from 9/9 public datasets; MTEB gaming; benchmark half-life ≈ one frontier-training cycle), and `aigc-contamination-geo.md` adds the forward threat: retrieval pipelines "quietly shift toward synthetic evidence" while accuracy metrics stay acceptable (arXiv:2602.16136 — 67% pool contamination → >80% exposure contamination), with neural rankers amplifying AIGC and perplexity-based filters losing their grip (GEO-Bench: fluent black-box rewrites now match gradient attacks). No framework tracks model-corpus contamination or AIGC share of its index. Framework-side evidence is currently thin only because nobody is measuring — which is itself the issue-1 pathology. A next-gen framework should carry corpus provenance/contamination metadata natively; flagged as a looming requirement rather than a documented common failure.
- **Issue-tracker theater distorting the ecosystem's ambient quality signal.** microsoft-graphrag (828 issues, 4 open, 96 closed via staleness, a data-loss bug "closed as not planned"); oss-rag-platforms X2 (Onyx's highest-signal ops complaints closed Stale); llamaindex E2 (dosubot conducts triage, inflating "answered" metrics while defects close as "standard behavior"). Three frameworks, but the mechanism is governance rather than eval architecture; noted because closed-issue counts are one of the few quality signals buyers actually consult, and they are being gamed.
- **Eval-asset churn.** datacloud-rag EO-2: Databricks deprecated Agent Evaluation into MLflow 3 mid-lifecycle — teams' eval suites are not stable ground even when they exist. Single-platform evidence; consistent with the platform-churn pattern in other dimensions.
- **Leaderboard conflict of interest.** Vectara's HF Hallucination Leaderboard ranks LLMs using Vectara's own proprietary judge, with materially shifting results between judge versions (vectordb file, single-anecdote). One case, but a clean illustration of issue 3 + issue 4 compounding into public-facing model rankings.
- **Illusory determinism controls.** FlashRAG #79 (seeds change nothing under vLLM) — single-anecdote, but it means small deltas in comparison tables across the whole toolkit ecosystem are uninterpretable, quietly amplifying issue 5.
- **Cost observability for multi-step retrieval.** Azure's agentic retrieval requires hand-modeling subquery fan-out × chunk tokens × reranking tokens to estimate cost (vendor-documented); Pinecone Assistant meters context tokens per hop "with no cost-attribution tooling" (architectural-inference); DSPy users asked for optimization cost dry-runs as early as issue #397. Two documented + one inferred — a plausible fourth-issue candidate for the performance-cost dimension's synthesis rather than a spine issue here, but note that cost and quality observability fail together: the same missing per-stage trace (issue 2) would carry both.
- **No memory-quality evaluation standard.** agent-framework-retrieval E1 and memory-and-localfirst I1 jointly show that when persistent memory *was* benchmarked (LoCoMo), the instrument itself was broken and no neutral harness existed; the landscape confirms no accepted RAG-integrated memory benchmark exists (F9/O7). Genuinely unsolved in research, not just unshipped — the honest classification is "open problem," not "ignored solution."

---

## Dimension synthesis

**Evaluation is the load-bearing absence of the RAG ecosystem.** Every other dimension's defects — bad chunking defaults, uncalibrated fusion weights, silent freshness bugs, security regressions — persist *because* this dimension is empty: without measurement, "the answers are wrong" is unactionable (memory-and-localfirst I2e states this verbatim), maintainers cannot tell whether a change helped, and buyers cannot tell vendors apart. The corpus shows the consequences compounding in a specific causal order:

1. **Open-core economics evacuates measurement from the core.** Eval/observability is the most reliably monetizable layer (LangSmith, deepset Enterprise, Databricks MLflow, LlamaCloud), so OSS cores are structurally, not accidentally, eval-free — the incentive gradient regenerates the gap even as individual tools improve.
2. **The vacuum is filled by self-graded homework.** With no customer-side falsification capability, vendor-run win rates and asymmetric-configuration benchmarks face no market penalty; the only corrections in the record came from competitors (Zep/Letta vs Mem0) or academics (GraphRAG-Bench vs LightRAG) — never from a framework's own shipped instruments.
3. **LLM judges make fake measurement nearly free**, so the ecosystem's measurement capacity fills with confident, biased numbers rather than staying honestly empty — position-biased win rates shipped in the eval scripts (LightRAG #288), 25-question "production-quality" auto-tuning (watsonx).
4. **Nothing is pinned, so nothing is checkable.** Without a reproducible-run primitive, paper/platform/OSS quietly become three different systems under one name, and server-side regressions (OpenAI, six days) are detectable only as vibes.
5. **The loop that would fix all of it is never wired.** The same industry runs closed-loop, feedback-trained ranking in commerce search — Google's Retail stack requires a quarter-million logged events — while its RAG products ship with no user-event ingestion path at all. The capability exists in the building; the product structure never connects it.

The issues also **compound pairwise** in ways single-issue fixes miss:

| Coupling | Mechanism |
|---|---|
| 1 → 3 | No customer eval capability ⇒ vendor claims face no falsification ⇒ marketing fills the vacuum |
| 4 → 3 | Cheap uncalibrated judges ⇒ impressive self-benchmarks are nearly free to manufacture |
| 4 → 8 | Noisy LLM-judged metrics ⇒ auto-tuners optimize judge-pleasing on toy targets |
| 5 → 3 | No pinned run manifest ⇒ disputed claims (Mem0/LightRAG) cannot be adjudicated, only re-fought |
| 2 → 6 | No per-stage trace ⇒ no substrate for drift detection or feedback attribution |
| 7 → 6 | No calibrated per-query signal ⇒ nothing for a feedback/escalation loop to branch on |
| 1 → all | Without measurement, every other dimension's defects (chunking, fusion, freshness) are invisible and permanent |

The deepest finding is the **asymmetry between the research shelf and the shipped default**. Almost nothing in this dimension is a genuinely open research problem: corpus-derived eval-set generation (Chroma), calibrated small-model judges (ARES/RAGBench/LettuceDetect), per-stage attribution (TRACe/RAGChecker), per-query confidence (twenty years of QPP, now agent-steering-grade), debiased online learning (settled since 2016). What's missing is the *packaging*: a framework whose architecture makes measurement the default artifact of every retrieval, rather than a paid add-on, a vendor claim, or a research afterthought. The genuinely unsolved residue is narrow and nameable — judge-calibration label budgets, process-level agentic eval, memory benchmarks, sufficiency metrics, corpus performance prediction — and a next-gen framework that shipped the solved 80% would make the unsolved 20% measurable for the first time.

**The one-sentence verdict:** the ecosystem is stuck because the layer that would reveal it is stuck is the layer nobody ships.
