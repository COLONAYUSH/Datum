# Private, Federated & Personalized Retrieval — Landscape Review (as of August 2026)

Research dossier for the "Reimagining RAG" project. Dimension: **private, federated & personalized retrieval** — the mechanisms that let a RAG/agentic system retrieve (a) without revealing queries or corpus contents to untrusted parties, (b) across administratively separate corpora that cannot be centralized, and (c) conditioned on an individual user, plus the copyright/licensing arguments that make a separable, governed datastore attractive. Emphasis on failure modes, critiques, and open problems, per project brief.

**Citation hygiene.** Every cited item was seen during this session either as a fetched abstract/landing page (unmarked) or in an arXiv API search-result listing whose full abstract was not separately fetched (**[listing-only]**). Items marked with a dagger (†) are foundational works cited from author knowledge and should be re-verified before publication. Preprints are flagged; peer-reviewed venues named where confirmed. Vendor material is labeled as such. Note: this session's web-search budget was exhausted by earlier pipeline stages; research was conducted via direct fetches of arXiv abstract pages, the arXiv API, IACR ePrint, and vendor pages — coverage of non-arXiv venues (SIGIR/TREC/industry) is therefore thinner than for sibling dossiers and flagged where it matters.

---

## Scope

Covered here:

- **Privacy-preserving retrieval mechanisms** (defenses, not just attacks): private information retrieval (PIR) lineage and practical single-server PIR 2023–2026; encrypted/secure vector search and homomorphic ANN; TEE-based retrieval; differential privacy (DP) for embeddings, similarity scores, and RAG outputs; split inference.
- **Federated search**: classic resource selection & results merging (CORI/ReDDE lineage) through modern federated RAG — cross-silo enterprise federation, routing, confidential federation.
- **Personalization**: LaMP/LongLaMP, retrieval-augmented personalization and its optimization, two-tower recsys retrieval lessons, the memory-based-personalization-vs-privacy tension.
- **On-device retrieval**: mobile/edge ANN and RAG pipelines, local-first search, device–cloud splits, Apple's Private Cloud Compute as the deployed reference design.
- **Copyright & licensing as retrieval motivation**: SILO-style legal-risk isolation in a datastore, attribution, and data-compensation economics.

Out of scope (sibling dossiers): retriever/embedding internals, vector-DB engineering, agent memory architectures per se, general RAG security/poisoning (touched only where it intersects privacy), evaluation methodology.

Why this dimension matters to the paper: mainstream RAG research quietly assumes a **single, trusted, centralized, user-agnostic corpus**. Every assumption in that phrase fails in enterprise, healthcare, consumer-assistant, and legal-exposure settings — and the literature that fixes each failure has developed in near-total isolation from the agentic-RAG literature.

---

## Lineage & key work

### A. Private information retrieval → private semantic search

- **PIR origins** — Chor, Goldreich, Kushilevitz, Sudan — FOCS 1995†; single-server computational PIR — Kushilevitz & Ostrovsky — FOCS 1997†. The core primitive: fetch record *i* from a server's database without the server learning *i*. For ~25 years dismissed as impractical (server must touch every database bit per query, or use heavy cryptography).
- **SimplePIR / DoublePIR** — Henzinger et al. — USENIX Security 2023 — IACR ePrint 2022/949. The practicality breakthrough: single-server PIR from LWE at **10 GB/s/core server throughput** ("approaches the memory bandwidth of the machine"; under one 32-bit multiply + add per database byte). DoublePIR trades throughput (7.4 GB/s/core) for only 16 MB of client hint. Demonstrated for Certificate Transparency auditing. Limitation: per-client hint download scales with database size; databases must be linearly scanned per query, so cost is O(N) regardless of relevance.
- **Tiptoe** — Henzinger, Dauterman, Corrigan-Gibbs, Zeldovich — SOSP 2023 — ePrint 2023/1438. The bridge from PIR to **semantic** retrieval: private nearest-neighbor search over embeddings using linearly homomorphic encryption. Searches 360M web pages with 145 core-seconds of server compute, 56.9 MiB communication, 2.7 s latency on a 45-server cluster. Quality cost is real: MS MARCO best-match rank 7.7 vs 2.3 for non-private neural search (worse than the 6.7 of classical tf-idf on this metric); weak at exact string matching. This is the canonical existence proof that "the server never sees your query" is achievable for web-scale semantic search — at roughly two orders of magnitude of overhead.
- **2024–2026 PIR refinements** (all preprints, from arXiv listings): ZipPIR — Akhavan Mahdavi et al. — arXiv 2603.09190 — high-throughput single-server PIR without client-side storage (LWE→Paillier ciphertext compression) [listing-only]; IVE — Kim et al. — arXiv 2512.01574 — hardware accelerator for HE-based single-server PIR [listing-only]; SPIDER — Dvir et al. — arXiv 2605.21857 [listing-only]; TreePIR single-server adaptation — arXiv 2510.04882 [listing-only]; and a sobering counterpoint, **lower bounds for PIR with preprocessing from blackbox crypto** — Hoover — arXiv 2607.06451 — 2026 [listing-only], indicating the cost floor is structural, not an artifact of immature engineering.
- **Secure ANN before the LLM era**: **SANNS** — Chen et al. — arXiv 1904.02033 — USENIX Security 2020† (venue from author knowledge) — secure k-NN at scale from HE + oblivious RAM [listing-only]; established both feasibility and the 10²–10⁴× overhead regime that later systems have been chipping away at.

### B. Encrypted vector search for RAG (2025–2026)

- **A Unified Benchmark for Privacy-preserving Vector Search** — Kermarrec, Pires, Randl, de Vos — arXiv 2608.01192 — Aug 2026 (preprint). The first head-to-head evaluation of cryptographic private-vector-search backends (SAP, EMVP, BNTM, Tiptoe) against plaintext. Headline: schemes form a **Pareto frontier over privacy/performance/recall** rather than a flat penalty — SAP ≈ plaintext speed (weakest guarantee), EMVP 4× CPU throughput cost for indistinguishability, BNTM 22× median latency for malicious-server verifiability, Tiptoe 190× per-query cost to hide cluster choice. Also: GPU acceleration helps plaintext/SAP but not the heavier schemes. This paper is the single best "cost of privacy" reference for the framework paper.
- **GoldenRetriever** — Gao et al. — arXiv 2607.29019 — 2026 — non-interactive HE retrieval for RAG via threshold-based encrypted selection without exposing rankings [listing-only, preprint].
- **Threshold-Protected Searchable Sharing** — Guo et al. — arXiv 2507.17199 — 2025 — privacy-preserving aggregated ANN over HNSW across distributed repositories for collaborative RAG [listing-only, preprint].
- **MESS** — Cui et al. — arXiv 2607.28999 — 2026 — private semantic search on multi-graph HNSW via binary codes + LSH + randomized response [listing-only, preprint]; and distance-comparison encryption for high-dimensional ANN — Liu et al. — arXiv 2508.10373 [listing-only, preprint]. Note that "lightweight" schemes in this family usually offer leakage-prone, non-cryptographic guarantees — leakage-abuse analysis is typically absent.
- **π-RAG** — arXiv 2606.22153 — 2026 [listing-only] — "oblivious retrieval via semantic quantization and transcendental addressing." Flagged deliberately: the abstract's framing ("transcendental entropy") reads as security-by-obscurity; treat with strong skepticism until independently analyzed. Symptomatic of a 2026 wave of unreviewed "private RAG" preprints with unvetted threat models.

### C. TEE-based retrieval

- **Fortify Your Foundations** — Chrapek et al. (ETH Zürich / Intel) — arXiv 2410.05930 — 2024 (preprint). Evaluates protections for cloud foundation-model deployments; finds TEEs the best security/usability/performance balance, with **<10% overhead vs bare metal for full Llama-2 7B/13B inference pipelines** in Intel SGX/TDX, explicitly covering RAG systems. TEEs are thus ~20–200× cheaper than cryptographic retrieval — but the trust model is entirely different (trust Intel/AMD/NVIDIA + attestation chain rather than mathematics).
- **C-FedRAG** — Addison et al. (NVIDIA and collaborators) — arXiv 2412.13163 — 2024 (preprint). Confidential-computing-based federated RAG: decentralized data providers contribute retrieval to a shared workflow inside TEEs, implemented on NVIDIA FLARE, evaluated with MedRAG/MIRAGE. The most concrete published blueprint for cross-silo enterprise RAG with confidentiality.
- **Apple Private Cloud Compute** — Apple Security Engineering blog — June 10, 2024 (vendor). The deployed reference design for "cloud AI with device-grade privacy": stateless computation (data deleted after each request), no privileged runtime access (no remote shell/debug paths), non-targetability, verifiable transparency (public tamper-proof log of production builds for researcher inspection). Not retrieval-specific, but it is the trust architecture into which consumer personalized retrieval is being fitted.
- **TEE counter-evidence**: **SNPeek** — Zhang et al. — arXiv 2506.15924 — 2025 [listing-only] — side-channel analysis of AMD SEV-SNP confidential VMs specifically on PIR workloads: memory-access side channels can undo the privacy the enclave was supposed to provide. TEE-based retrieval inherits the entire enclave side-channel literature; access-pattern leakage in ANN index traversal (which node of the HNSW graph you touched ≈ which cluster your query is in) is precisely the kind of signal side channels expose.

### D. Differential privacy for retrieval

- **Embedding leakage as motivation** — **Text Embeddings Reveal (Almost) As Much As Text** — Morris, Kuleshov, Shmatikov, Rush — EMNLP 2023 — arXiv 2310.06816. Iterative "vec2text" inversion recovers **92% of 32-token inputs exactly** from dense embeddings and recovers full names from clinical-note embeddings. Kills the folk belief that "we only store vectors, not text, so it's private." Follow-up: **Zero2Text** — Kim et al. — arXiv 2602.01757 — 2026 [listing-only] — training-free cross-domain inversion using LLM priors, reported to weaken DP-based defenses under adaptive attacks.
- **DP mechanisms for RAG (2025–2026 wave, all preprints)**: **Private-RAG / MURAG & MURAG-ADA** — Wu, Wang, Zhang, Wang — arXiv 2511.07637 — 2025 — the key conceptual advance: per-document individual privacy filters so accumulated privacy loss depends on how often each *document* is retrieved, not on total query count — making multi-query DP-RAG feasible at realistic budgets (ε≈10 over hundreds of queries). **DP-SynRAG** — Mori et al. — arXiv 2510.06719 — 2025 [listing-only] — generate a DP *synthetic* RAG database once, avoiding per-query noise entirely. **DP datastore generation via LSH + calibrated noise** — Abouelenein et al. — arXiv 2606.01413 [listing-only]. **DP-KSA** — Tang et al. — arXiv 2602.14374 — 2026 [listing-only] — propose-test-release extraction of DP keywords from retrieved contexts. **ScoreShield** — Razeghi et al. — arXiv 2607.25041 — 2026 [listing-only] — DP release of cosine-similarity scores to blunt membership inference. **Privacy-Aware Decoding** — Wang et al. — arXiv 2508.03098 — 2025 [listing-only] — calibrated logit noise with Rényi-DP accounting at generation time. **PA-HDP** — Zhang et al. — arXiv 2607.14811 — 2026 [listing-only] — argues static corpus-level DP is wrong; protection should adapt to query-specific risk.
- **RAG privacy attacks as the driver** — **The Good and The Bad** — Zeng et al. — arXiv 2402.16893 — 2024 (preprint). First systematic demonstration that RAG systems leak their private retrieval databases through crafted queries — while also *reducing* leakage of the LLM's training data (retrieval substitutes for memorization). This dual result is the cleanest motivation for datastore-centric privacy engineering. See also the KV-cache timing side channel extracting private prompt content in RAG — Sun et al. — arXiv 2606.21842 — 2026 [listing-only]; **GraphSteal** — Gu et al. — arXiv 2605.28645 — 2026 [listing-only] — black-box reconstruction of ~90% of a hidden GraphRAG knowledge graph via adaptive queries; **ContextLeak** — Choi et al. — arXiv 2512.16059 — 2025 [listing-only] — canary-based auditing showing "private in-context learning" methods leak more than claimed; and **Ghost Vectors** — Chakraborttii et al. — arXiv 2606.18497 — 2026 [listing-only] — soft-deleted embeddings remain reconstructible in HNSW vector databases, directly undermining deletion/right-to-be-forgotten claims of datastore approaches.
- **Split inference**: DP + communication-efficient LLM split inference — Gu et al. — arXiv 2602.11513 — 2026 [listing-only]. Sending intermediate activations/embeddings to a server is *not* private absent explicit protection (see vec2text above); this sub-literature adds quantization + noise at the split point.
- Surveys consolidating the space: **Security and Privacy in RAG** — Palanisamy et al. — arXiv 2606.25533 — 2026 [listing-only]; **Towards Secure RAG** — Mu et al. — arXiv 2603.21654 — 2026 [listing-only].

### E. Federated search: classic IR lineage → federated RAG

- **Classic distributed IR (all †, pre-arXiv era, cited from author knowledge)**: GlOSS — Gravano et al. — ~1994–1999†; **CORI** resource selection — Callan, Lu, Croft — SIGIR 1995† — pick which collections to query by treating each collection as a "big document"; **ReDDE** — Si & Callan — SIGIR 2003† — sample-based estimation of relevant-document counts per collection; semi-supervised results merging — Si & Callan†; consolidated in **Shokouhi & Si, "Federated Search," Foundations and Trends in IR, 2011**†. The three canonical subproblems — **resource representation, resource selection, results merging** — were defined here and every "which silo do I query" decision in 2026 federated RAG is a rediscovery of them. TREC **FedWeb** tracks (2013–2014) provided the standard testbeds (referenced as predating-RAG baselines on the FeB4RAG page, below).
- **FeB4RAG** — Wang, Khramtsova, Zhuang, Zuccon — arXiv 2402.11891 — 2024 (preprint). First benchmark re-posing federated search *for RAG*: 790 conversational information requests over 16 BEIR sub-collections; shows high-quality federated resource selection substantially improves downstream generation vs naive "query everything and merge." Explicitly motivated by FedWeb's obsolescence in the RAG era.
- **RAGRoute** — Dhasade, Guerraoui, Kermarrec, Petrescu, Pires, Randl, de Vos — arXiv 2502.19280 — EuroMLSys 2025 / DAIS 2026 (peer-reviewed). Lightweight neural per-source routing for federated RAG: up to **80.65% communication reduction and 52.50% latency reduction** at near-parity accuracy vs querying all sources. Modern resource selection, reborn as a learned classifier.
- **Federated RAG systematization**: **Federated RAG: A Systematic Mapping Study** — Chakraborty, Dahal, Gupta — arXiv 2505.18906 — 2025 (preprint) — maps 2020–2025 FL×RAG work; identifies privacy-preserving retrieval, cross-client heterogeneity, and evaluation limitations as the three open challenge areas. Framework-level entries: **FedRAG** (fine-tuning RAG across centralized/federated architectures) — Fajardo et al. — arXiv 2506.09200 — 2025 [listing-only]; **HyFedRAG** (edge–cloud federation over SQL/KG/document silos) — Qian et al. — arXiv 2509.06444 — 2025 [listing-only]; **FedMosaic** (parametric adapters aggregated instead of documents shared) — Liang et al. — arXiv 2602.05235 — 2026 [listing-only]; **Trans-RAG** (query-centric vector transformation isolating organizational embedding spaces) — Liu et al. — arXiv 2604.09541 — 2026 [listing-only]; cross-institutional RAG via scrambled distributed attention — Mao et al. — arXiv 2605.25716 — 2026 [listing-only].
- **Federated RAG attack surface**: **A Wolf in Sheep's Clothing** — Mu et al. — arXiv 2605.28112 — 2026 [listing-only] — malicious federation members forge semantic routing profiles to hijack query routing and poison evidence. Federation converts the retrieval trust question from "is my corpus clean" to "are my *partners* honest" — a Byzantine problem classic federated search never had to face because the queried engines were merely uncooperative, not adversarial participants in a shared protocol.

### F. Personalized retrieval

- **LaMP** — Salemi, Mysore, Bendersky, Zamani — arXiv 2304.11406 — 2023 (preprint; widely used). The canonical benchmark: 7 tasks (3 classification, 4 generation), each with per-user profiles; establishes **retrieval from the user profile** (term-matching, semantic, time-aware) as the standard personalization mechanism for LLMs. **LongLaMP** — Kumar et al. — arXiv 2407.11016 — 2024 (preprint) — extends to personalized *long-form* generation (emails, reviews).
- **Optimization for retrieval-augmented personalization** — Salemi, Kallumadi, Zamani — arXiv 2404.05970 — SIGIR 2024† (venue from author knowledge; abstract fetched). RL and distillation to train the *profile retriever* against downstream personalized-generation quality — personalization as a retrieval-optimization problem, not a prompting trick.
- **RAG vs PEFT for privacy-preserving personalization** — Salemi & Zamani — arXiv 2409.09510 — 2024 (preprint). First systematic comparison: over 7 LaMP datasets, RAG-based personalization +14.92%, PEFT +1.07%, combined +15.98% over non-personalized baselines; RAG wins for cold-start users, PEFT catches up as per-user data grows. Framing both as "privacy-preserving" (user data stays in user-controlled storage or user-specific adapters) is the key architectural claim for our purposes.
- **Personalization of LLMs: A Survey** — Zhang et al. — arXiv 2411.00027 — TMLR 2025 (peer-reviewed). Unifies personalized-generation and LLM-for-recsys literatures; taxonomies of granularity, technique, datasets, evaluation.
- **Two-tower recsys lineage (lessons for RAG)**: deep candidate retrieval at YouTube — Covington et al. — RecSys 2016†; sampling-bias-corrected two-tower training — Yi et al. — RecSys 2019†; **Embedding-based Retrieval in Facebook Search** — Huang et al. — KDD 2020 — arXiv 2006.11632 — personalization signals and social-graph context embedded directly in the query tower, with hard production lessons on hybrid Boolean+ANN serving, full-stack optimization, and A/B-validated gains. The transferable lessons: (1) personalization lives in the *query-side encoder*, not the corpus; (2) training data is logged interactions with severe sampling bias, requiring explicit correction; (3) embedding retrieval is deployed *alongside*, not instead of, term matching — all three lessons are routinely ignored in personalized-RAG papers that fine-tune on tiny per-user profiles.
- **Personalization–privacy tension**: **Can LLMs Keep a Secret? (ConfAIde)** — Mireshghallah et al. — ICLR 2024 spotlight — arXiv 2310.17884 — contextual-integrity benchmark: GPT-4 and ChatGPT reveal private information in contexts humans would not **39% / 57%** of the time, robust to privacy prompting and CoT. The implication for personalized RAG is direct: even if retrieval of personal context is perfectly access-controlled, the *generator* mishandles contextual flow norms. **Agents That Know Too Much** — Lahjouji & Colaco — arXiv 2606.26627 — 2026 (preprint) — data-centric survey of agent privacy: leakage via issued queries, intermediate results, memory writes, and inter-agent messages; finds only information-flow control covers compositional and cross-session inference leakage (the two least-protected risks), and that **no existing benchmark exercises an agent across all its data surfaces under one privacy policy**.

### G. On-device retrieval

- **Energy-Efficient On-Device RAG on a Mobile NPU** — Cheng et al. — arXiv 2606.11257 — 2026 [listing-only, preprint] — claimed first end-to-end RAG pipeline (embed, index, retrieve, generate) entirely on a Snapdragon X Elite NPU; ~4× energy/latency improvement vs CPU baselines.
- **As We May Search** — Zerhoudi et al. — arXiv 2606.29652 — 2026 [listing-only, preprint] — local-first IR architecture keeping indexes and inference on user devices; scales to ~1M documents on consumer hardware with minimal quality loss. **Little Brains, Big Feats** — Baturova et al. — arXiv 2606.30062 — 2026 [listing-only] — SLMs running RAG on-device without GPUs. **MAM-AI** — Ren et al. — arXiv 2606.29580 — 2026 [listing-only] — fully offline Android medical RAG for nurses/midwives in Zanzibar: on-device retrieval as an *availability* technology, not only a privacy one.
- **Device–cloud splits**: **CONCORD** — Hu et al. — arXiv 2606.15179 — 2026 [listing-only] — asynchronous sparse aggregation letting private on-device documents participate in generation alongside cloud knowledge under document isolation; mobile chunk selection — Chang et al. — arXiv 2608.03148 — 2026 [listing-only].
- Constraint summary [author synthesis]: on-device retrieval is bounded by RAM for the index (forcing product quantization/binary codes), NPU-friendly small embedders (quality gap vs 7B-class embedders unquantified in most of these papers), battery, and — most importantly — *corpus freshness*: a local index over personal data is easy; a local index over the live web is impossible, which is exactly what makes hybrid device–cloud designs (and hence split-inference privacy) unavoidable.

### H. Copyright & licensing as a retrieval motivation

- **SILO** — Min, Gururangan, Wallace, Shi, Hajishirzi, Smith, Zettlemoyer — ICLR 2024 spotlight — arXiv 2308.04430. The pivotal argument that the **datastore is a legal-risk isolation boundary**: train the parametric LM only on public-domain/permissively-licensed text (LM quality tanks out-of-domain), then recover **90% of the performance gap** at inference by retrieving from a nonparametric datastore of higher-risk text. The datastore supports sentence-level attribution and instant opt-out/removal — properties parametric weights cannot offer (machine unlearning remains unreliable). This is the strongest *non-privacy* argument for retrieval-centric architectures and deserves a central place in the framework paper's motivation.
- **Foundation Models and Fair Use** — Henderson, Li, Jurafsky, Hashimoto, Lemley, Liang — arXiv 2303.15715 — 2023 (preprint; law-review version exists†). Fair use may cover training but not outputs that substantially resemble sources; proposes technical mitigations. Read together with SILO: retrieval moves the risky content out of the weights and into a store where *per-item* license checks, attribution, and takedown are mechanically possible.
- **An Economic Solution to Copyright Challenges of Generative AI** — Wang, Deng, Chiba-Okabe, Barak, Su — arXiv 2404.13964 — 2024 (preprint). Cooperative-game-theoretic (Shapley-style) royalty distribution proportional to each source's contribution to generated output. For RAG the mapping is unusually clean: retrieval logs give a direct, auditable record of *which* licensed items contributed to *which* answer — a per-query metering substrate that parametric models fundamentally lack.
- Caveats [author synthesis]: courts have not ruled that RAG-time quotation is safer than training-time ingestion — retrieval that *reproduces* text verbatim at inference may be a **more** direct infringement than training, not less (the display/derivative question); SILO isolates *training* risk, not *serving* risk. Datastore licensing markets (per-retrieval compensation) remain proposals; no deployed scheme was verified this session [uncertain].

---

## State of the art (mid-2026)

- **Private semantic search is real but ~2 orders of magnitude expensive.** Tiptoe-class systems demonstrate web-scale query-private search; the Kermarrec et al. unified benchmark (arXiv 2608.01192) quantifies the frontier: ≈4× (weak indistinguishability) to 190× (cluster-hiding) per-query cost, with GPU acceleration not helping the heavier schemes. No cryptographic scheme yet supports the *iterative, adaptive, multi-hop* retrieval that agentic RAG performs — each additional hop multiplies the overhead and each adaptive query leaks through timing/choice patterns.
- **TEEs are the pragmatic winner and the deployed reality.** <10% overhead (Chrapek et al.), C-FedRAG for cross-silo federation, Apple PCC in consumer production. The open wound is side channels (SNPeek) and the concentration of trust in 2–3 hardware vendors.
- **DP-for-RAG has matured from single-query toys to multi-query systems** (MURAG's per-document privacy filters; DP-SynRAG's one-shot synthetic datastores), but reported utility at meaningful ε is task-dependent and adaptive-attack robustness is already contested (Zero2Text).
- **Federated RAG is where federated search was in ~1998**: benchmarks exist (FeB4RAG), routing works (RAGRoute), confidential variants exist (C-FedRAG), but results merging across heterogeneous, incomparably-scored silos is unsolved, evaluation is fragmented (Chakraborty et al.), and the Byzantine-participant threat model (routing hijack, arXiv 2605.28112) has no established defense.
- **Personalization is dominated by retrieval from user profiles** (LaMP lineage; RAG beats PEFT +14.92% vs +1.07% — Salemi & Zamani 2409.09510), which makes personalization *structurally identical to private RAG over a per-user corpus* — yet the personalization and privacy literatures barely cite each other, and ConfAIde shows generators leak contextually even when retrieval is perfect.
- **On-device end-to-end RAG became demonstrable in 2026** (NPU pipelines, 1M-doc local-first search) but only for personal-scale corpora; hybrid device–cloud is the operating point, and its privacy story (split inference, CONCORD-style isolation) is immature.
- **The copyright motivation is strengthening**: SILO's "risky data lives in a removable, attributable datastore" argument, plus contribution-metered compensation proposals, position next-gen RAG frameworks as *governance* infrastructure, not just accuracy infrastructure.

---

## Failure modes & critiques

1. **"Vectors are anonymous" is false.** vec2text recovers 92% of short inputs exactly from embeddings (Morris et al., EMNLP 2023); Zero2Text extends inversion cross-domain without training [listing-only]. Any design that ships raw embeddings to an untrusted vector DB or across a split-inference boundary leaks the underlying text.
2. **Deletion is weaker than claimed.** Ghost Vectors (arXiv 2606.18497 [listing-only]): soft-deleted embeddings remain reconstructible in HNSW indexes. The datastore's headline governance advantage over parametric memory — instant removal (SILO) — silently depends on index internals actually forgetting, which production ANN indexes do not do by default.
3. **The RAG pipeline leaks at every stage, not just the index.** Corpus extraction via crafted queries (Zeng et al. 2402.16893); KV-cache timing side channels (arXiv 2606.21842 [listing-only]); GraphRAG structure stealing (GraphSteal, ~90% graph reconstruction [listing-only]); similarity scores enabling membership inference (ScoreShield's motivation [listing-only]); agent queries/memory/inter-agent messages as leak surfaces (Lahjouji & Colaco). Point defenses at one stage are routinely bypassed at another.
4. **Cryptographic retrieval is incompatible with agentic iteration as currently practiced.** PIR/HE schemes price a *single* query at 4–190× plaintext (Kermarrec et al.); an agent that issues 20 adaptive queries per task multiplies that, and its *adaptivity itself* is a side channel (which sources it consults next reveals what it learned). Hoover's lower bounds [listing-only] suggest this is not merely an engineering gap.
5. **TEE trust is narrower than advertised.** SNPeek demonstrates side-channel recovery on SEV-SNP PIR workloads [listing-only]; access patterns over ANN graph indexes are semantically revealing even when memory is encrypted; and attestation reduces "trust no one" to "trust the CPU vendor, firmware chain, and cloud operator's physical security." Apple PCC's transparency-log approach is the strongest deployed mitigation but is vendor-specific and unverifiable end-to-end by outsiders in the strict sense (vendor claim).
6. **DP-RAG's utility accounting is fragile.** Per-query noising destroys long-tail retrieval; per-document filters (MURAG) and synthetic datastores (DP-SynRAG) help but published utility is on standard QA benchmarks at ε≈10 — a budget many privacy researchers consider weak — and PA-HDP [listing-only] argues static budgets misallocate protection across query risks. No study verified this session measures DP-RAG on *personalized* or *multi-hop agentic* workloads.
7. **Federated RAG rediscovers 1995 problems without their solutions.** Resource selection (CORI/ReDDE†) reappears as learned routing (RAGRoute), but **results merging** — calibrating relevance scores across silos with different embedders, corpus statistics, and score distributions — is mostly unaddressed; FeB4RAG shows naive merging measurably degrades generation. Cross-silo score incomparability is *worse* in the dense-embedding era than in the BM25 era because scores are model-specific and uncalibrated.
8. **Federation adds Byzantine participants.** Routing hijack via forged semantic profiles (arXiv 2605.28112 [listing-only]) shows a malicious silo can attract queries and inject evidence — poisoning with a built-in distribution channel. Classic federated search assumed *uncooperative* sources, not adversarial protocol participants; the defense literature is embryonic.
9. **Personalization and privacy are treated as separate papers, but they are the same tension.** The best personalization mechanism is retrieval over accumulated user data (LaMP lineage); the biggest agent-privacy risk is accumulated cross-session memory (Lahjouji & Colaco). ConfAIde shows models leak contextually 39–57% of the time even with the data in-context legitimately. Memory-based personalization without contextual-integrity enforcement is a privacy incident with good UX.
10. **Evaluation is systemically broken in this area.** No benchmark jointly measures retrieval quality *and* privacy leakage *and* cost (the 2608.01192 benchmark covers crypto schemes only; LaMP measures personalization only; ConfAIde measures leakage only; FeB4RAG measures federation only). Papers claim "privacy-preserving" for wildly different threat models — query privacy vs corpus privacy vs membership privacy vs contextual integrity — often without stating which. A large fraction of 2025–2026 "private RAG" arXiv output is unreviewed, with untested or incoherent threat models (π-RAG as an extreme case).
11. **Copyright motivation cuts both ways.** SILO isolates *training* risk, but serving retrieved copyrighted text verbatim may be more directly infringing than training on it (Henderson et al. flag the output-similarity problem); attribution and compensation schemes (Wang et al. 2404.13964) remain unimplemented proposals. A framework that touts the datastore as a licensing boundary must also implement output-side controls (quotation limits, attribution rendering, per-item license enforcement at serving time).

---

## Relevance to a next-generation agentic RAG framework

Concrete design implications for the framework paper:

1. **Make trust boundaries first-class in the retrieval abstraction.** Every retrieval call should carry (source silo, trust level of the index host, privacy mechanism in force, leakage budget consumed). Today's frameworks type a retriever as `query → docs`; this literature says the type must be `(query, principal, policy) → (docs, provenance, privacy-cost)`. C-FedRAG and PCC show deployed systems already need this; no OSS framework exposes it.
2. **Tiered privacy mechanisms behind one interface.** The Pareto frontier (plaintext / TEE ≈1.1× / EMVP ≈4× / Tiptoe ≈190×) means the framework should let *policy*, not code, choose the mechanism per corpus sensitivity — with TEE as the pragmatic default tier and cryptographic tiers reserved for query-privacy-critical sources. Design the retriever API so a PIR backend is a drop-in (single-shot, batched, non-adaptive-friendly) rather than an afterthought.
3. **Budget adaptive retrieval like DP budgets privacy.** Agentic loops multiply both cost and leakage. MURAG's per-document privacy filter is the right template: meter leakage per *datastore item* and per *session*, and let the agent's planner treat privacy budget as a resource alongside tokens and latency. This is a genuinely novel framework contribution nothing in the OSS landscape has.
4. **Federation = routing + merging + Byzantine defense.** Adopt learned resource selection (RAGRoute-style) but the paper should name **cross-silo score calibration** as an unsolved required component, and require authenticated, auditable source profiles to resist routing hijack. Classic IR (CORI/ReDDE lineage) provides the vocabulary and baselines; do not reinvent it.
5. **Personalization as a private per-user silo, not a prompt hack.** Model the user profile/memory as one more federated source with the *strictest* trust tier — retrieved via the same interface, governed by contextual-integrity policies (who/what/purpose) enforced at retrieval time *and* checked at generation time (ConfAIde-style probes as CI tests). RAG-based personalization wins over PEFT for cold-start (Salemi & Zamani), which fits this architecture natively.
6. **Device–cloud split as a routing decision.** On-device indexes for personal corpora (feasible at 1M docs), cloud for the world, with the router deciding placement-aware — and split-inference boundaries treated as leak surfaces (no raw embeddings across trust boundaries without DP/encryption).
7. **The datastore as a governance object.** Adopt SILO's framing: per-item license metadata, sentence-level attribution surfaced in outputs, verified-deletion (not soft-deletion — Ghost Vectors makes this a concrete engineering requirement on index design), and retrieval logs as the metering substrate for compensation (Wang et al.). This turns "next-gen RAG framework" from a performance story into a *legal-and-privacy-viability* story — arguably the strongest motivation available for the paper, since it is the one thing long-context parametric models cannot replicate.
8. **Joint evaluation harness.** Ship privacy probes (extraction attacks, membership inference, canary audits à la ContextLeak), leakage accounting, and cost curves alongside quality metrics — because no external benchmark does all three (finding 10 above), and a framework that measures what others don't is a publishable artifact in itself.

---

## Open problems

1. **Adaptive-query-private retrieval.** All practical PIR/HE schemes assume independent single-shot queries; agentic retrieval is adaptive and sequential, and the adaptivity leaks. No scheme, bound, or even formal definition of "private multi-hop retrieval" was found this session.
2. **Cross-silo score calibration / results merging for dense retrieval.** The federated-RAG literature routes well but merges naively; heterogeneous embedders make scores incomparable. A learned, sample-based merging layer (ReDDE's idea, modernized) is missing.
3. **Verified deletion in ANN indexes.** Ghost Vectors shows soft-deletion fails; nobody has a production HNSW/IVF design with cryptographic or auditable erasure guarantees — a prerequisite for both GDPR and SILO-style licensing claims.
4. **A unified threat-model taxonomy and joint benchmark** covering query privacy, corpus privacy, membership, contextual integrity, and Byzantine federation — measured together with quality and cost on agentic (multi-hop, multi-session) workloads. Closest existing pieces: 2608.01192 (crypto cost), ConfAIde (CI), Lahjouji & Colaco's observation that no benchmark spans an agent's data surfaces.
5. **DP semantics for personalization.** Per-user corpora are tiny; DP noise calibrated per-document destroys exactly the idiosyncratic items personalization needs. Whether meaningful (ε, δ) is achievable for LaMP-style tasks is open — the RAG-vs-PEFT comparison (2409.09510) is "privacy-preserving" only informally.
6. **Contextual-integrity enforcement at retrieval time.** ConfAIde shows generation-time leakage persists under prompting; enforcing "this memory may be used for scheduling but not shared with a shopping agent" requires information-flow control through the retrieval-generation-action pipeline — identified by the agent-privacy survey as the only mechanism covering compositional leakage, and implemented nowhere.
7. **Economic/legal machinery for retrieval-time licensing.** Per-retrieval compensation (Shapley-style attribution over retrieval logs), quotation-length controls, and the unresolved legal question of whether inference-time retrieval of licensed text is safer or *riskier* than training-time ingestion. Empirically and legally open [uncertain].
8. **TEE side-channel-resistant ANN.** Oblivious index traversal (ORAM-style HNSW) cheap enough for production, closing the gap SNPeek exposes, is unbuilt; its overhead relative to the <10% TEE baseline is unknown.

---

## Bibliography

Privacy-preserving retrieval mechanisms:
- Chor, Goldreich, Kushilevitz, Sudan. Private Information Retrieval. FOCS 1995. †
- Kushilevitz, Ostrovsky. Single-server computational PIR. FOCS 1997. †
- Henzinger et al. One Server for the Price of Two: SimplePIR/DoublePIR. USENIX Security 2023. IACR ePrint 2022/949.
- Henzinger, Dauterman, Corrigan-Gibbs, Zeldovich. Private Web Search with Tiptoe. SOSP 2023. ePrint 2023/1438.
- Akhavan Mahdavi et al. ZipPIR. arXiv 2603.09190, 2026. [listing-only]
- Kim et al. IVE: PIR accelerator. arXiv 2512.01574, 2025. [listing-only]
- Hoover. Lower Bounds for PIR with Preprocessing. arXiv 2607.06451, 2026. [listing-only]
- Chen et al. SANNS: Secure Approximate k-NN Search. arXiv 1904.02033; USENIX Security 2020†. [listing-only]
- Kermarrec, Pires, Randl, de Vos. A Unified Benchmark for Privacy-preserving Vector Search. arXiv 2608.01192, 2026. Preprint.
- Gao et al. GoldenRetriever: Non-Interactive HE Retrieval for RAG. arXiv 2607.29019, 2026. [listing-only]
- Guo et al. Threshold-Protected Searchable Sharing. arXiv 2507.17199, 2025. [listing-only]
- Cui et al. MESS: Private Semantic Search on Multi-Graph HNSW. arXiv 2607.28999, 2026. [listing-only]
- Liu et al. Privacy-Preserving ANN via Distance-Comparison Encryption. arXiv 2508.10373, 2025. [listing-only]
- Saeki et al. PQ-based FHE+TEE ANN. arXiv 2604.17816, 2026. [listing-only]
- Wattamwar et al. π-RAG. arXiv 2606.22153, 2026. [listing-only; rigor questionable]
- Chrapek et al. Fortify Your Foundations (TEE for FM/RAG, <10% overhead). arXiv 2410.05930, 2024. Preprint.
- Addison et al. C-FedRAG: Confidential Federated RAG (NVIDIA FLARE). arXiv 2412.13163, 2024. Preprint.
- Apple Security Engineering. Private Cloud Compute. security.apple.com blog, June 10, 2024. Vendor.
- Zhang et al. SNPeek: Side-Channels on SEV-SNP PIR workloads. arXiv 2506.15924, 2025. [listing-only]
- Morris, Kuleshov, Shmatikov, Rush. Text Embeddings Reveal (Almost) As Much As Text. EMNLP 2023. arXiv 2310.06816.
- Kim et al. Zero2Text: Zero-Training Embedding Inversion. arXiv 2602.01757, 2026. [listing-only]
- Wu, Wang, Zhang, Wang. Private-RAG (MURAG/MURAG-ADA). arXiv 2511.07637, 2025. Preprint.
- Mori et al. DP-SynRAG. arXiv 2510.06719, 2025. [listing-only]
- Abouelenein et al. DP Datastore Generation. arXiv 2606.01413, 2026. [listing-only]
- Tang et al. Differentially Private RAG (DP-KSA). arXiv 2602.14374, 2026. [listing-only]
- Razeghi et al. ScoreShield: DP Similarity Scores. arXiv 2607.25041, 2026. [listing-only]
- Wang et al. Privacy-Aware Decoding. arXiv 2508.03098, 2025. [listing-only]
- Zhang et al. PA-HDP: Prompt-Aware Hierarchical DP for RAG. arXiv 2607.14811, 2026. [listing-only]
- Gu et al. DP & Communication-Efficient LLM Split Inference. arXiv 2602.11513, 2026. [listing-only]
- Zeng et al. The Good and The Bad: Privacy Issues in RAG. arXiv 2402.16893, 2024. Preprint.
- Sun et al. Agent-Assisted KV-Cache Side-Channel Attacks in RAG. arXiv 2606.21842, 2026. [listing-only]
- Gu et al. GraphSteal. arXiv 2605.28645, 2026. [listing-only]
- Choi et al. ContextLeak. arXiv 2512.16059, 2025. [listing-only]
- Chakraborttii et al. Ghost Vectors: Soft-Deleted Embeddings in HNSW. arXiv 2606.18497, 2026. [listing-only]
- Palanisamy et al. Security and Privacy in RAG (survey). arXiv 2606.25533, 2026. [listing-only]
- Mu et al. Towards Secure RAG (review). arXiv 2603.21654, 2026. [listing-only]

Federated search & federated RAG:
- Callan, Lu, Croft. CORI. SIGIR 1995. †
- Si, Callan. ReDDE. SIGIR 2003. †
- Shokouhi, Si. Federated Search. Foundations and Trends in IR, 2011. †
- TREC FedWeb tracks 2013–2014 (referenced via FeB4RAG page). †
- Wang, Khramtsova, Zhuang, Zuccon. FeB4RAG. arXiv 2402.11891, 2024. Preprint.
- Dhasade et al. RAGRoute: Efficient Federated Search for RAG. arXiv 2502.19280. EuroMLSys 2025 / DAIS 2026.
- Chakraborty, Dahal, Gupta. Federated RAG: Systematic Mapping Study. arXiv 2505.18906, 2025. Preprint.
- Fajardo et al. FedRAG. arXiv 2506.09200, 2025. [listing-only]
- Qian et al. HyFedRAG. arXiv 2509.06444, 2025. [listing-only]
- Liang et al. FedMosaic. arXiv 2602.05235, 2026. [listing-only]
- Liu et al. Trans-RAG. arXiv 2604.09541, 2026. [listing-only]
- Mao et al. Cross-Institutional Collaborative RAG. arXiv 2605.25716, 2026. [listing-only]
- Mu et al. A Wolf in Sheep's Clothing: Routing Hijacking in Federated RAG. arXiv 2605.28112, 2026. [listing-only]

Personalization:
- Salemi, Mysore, Bendersky, Zamani. LaMP. arXiv 2304.11406, 2023. Preprint.
- Kumar et al. LongLaMP. arXiv 2407.11016, 2024. Preprint.
- Salemi, Kallumadi, Zamani. Optimization Methods for Personalizing LLMs through Retrieval Augmentation. arXiv 2404.05970. SIGIR 2024†.
- Salemi, Zamani. Comparing RAG and PEFT for Privacy-Preserving Personalization. arXiv 2409.09510, 2024. Preprint.
- Zhang et al. Personalization of LLMs: A Survey. arXiv 2411.00027. TMLR 2025.
- Covington et al. Deep Neural Networks for YouTube Recommendations. RecSys 2016. †
- Yi et al. Sampling-Bias-Corrected Two-Tower Retrieval. RecSys 2019. †
- Huang et al. Embedding-based Retrieval in Facebook Search. KDD 2020. arXiv 2006.11632.
- Mireshghallah et al. Can LLMs Keep a Secret? (ConfAIde). ICLR 2024 spotlight. arXiv 2310.17884.
- Lahjouji, Colaco. Agents That Know Too Much. arXiv 2606.26627, 2026. Preprint.

On-device:
- Cheng et al. Energy-Efficient On-Device RAG on a Mobile NPU. arXiv 2606.11257, 2026. [listing-only]
- Zerhoudi et al. As We May Search. arXiv 2606.29652, 2026. [listing-only]
- Baturova et al. Little Brains, Big Feats. arXiv 2606.30062, 2026. [listing-only]
- Ren et al. MAM-AI (offline medical RAG, Zanzibar). arXiv 2606.29580, 2026. [listing-only]
- Hu et al. CONCORD: Device-Cloud RAG under Document Isolation. arXiv 2606.15179, 2026. [listing-only]
- Chang et al. Lightweight Chunk Selection for Mobile RAG. arXiv 2608.03148, 2026. [listing-only]

Copyright & licensing:
- Min et al. SILO Language Models. ICLR 2024 spotlight. arXiv 2308.04430.
- Henderson et al. Foundation Models and Fair Use. arXiv 2303.15715, 2023. Preprint.
- Wang, Deng, Chiba-Okabe, Barak, Su. An Economic Solution to Copyright Challenges of Generative AI. arXiv 2404.13964, 2024. Preprint.
