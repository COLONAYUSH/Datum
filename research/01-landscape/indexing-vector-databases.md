# ANN Indexing & Vector Data Infrastructure: Landscape, Failure Modes, and Open Problems (as of mid-2026)

*Research dossier for a next-generation RAG framework. Compiled 2026-08-05. All sources verified via web search/fetch during compilation unless explicitly marked "[from prior knowledge — ID/venue not re-verified in this pass]". Vendor blogs are labeled as such and treated as claims, not peer-reviewed results.*

---

## Scope

This document covers the storage and indexing substrate underneath RAG and agentic-memory systems:

- **Index algorithms**: graph-based (HNSW, Vamana/DiskANN, CAGRA), partition-based (IVF, SPANN/SPFresh, ScaNN/SOAR), and quantization (PQ/OPQ, anisotropic VQ, binary/scalar quantization, RaBitQ and Extended RaBitQ).
- **Storage architectures**: memory-resident, SSD-resident (DiskANN family, Starling-style layouts), and object-storage-native (turbopuffer, LanceDB/Lance, Amazon S3 Vectors).
- **Operational dimensions**: streaming inserts/deletes, filtered (predicate/ACL) search, multi-tenancy, hybrid lexical+vector retrieval, GPU acceleration.
- **The system landscape**: dedicated vector DBs vs. extended general-purpose engines (Postgres/pgvector family, Elasticsearch/OpenSearch, Redis, MongoDB) and the 2024–2026 convergence of search + vector + SQL.
- **Evaluation**: ann-benchmarks, big-ann-benchmarks, VIBE, VDBBench, and the growing critique literature (average-recall pathologies, OOD queries, deletion evaluation, task-level metrics).

Out of scope here (covered by sibling dossiers): embedding models, rerankers, chunking, agent memory semantics. This file focuses on *what the retrieval substrate can and cannot physically do*, because framework-level design choices (freshness guarantees, filter semantics, cost envelopes, tail-recall SLOs) are constrained from below.

---

## Lineage & chronological development

### Phase 1 — Quantization and inverted files (2010–2016)

- **Product Quantization (PQ)** — Jégou, Douze, Schmid — TPAMI 2011 [from prior knowledge — canonical]. Decompose vectors into subspaces, quantize each with a small codebook; enables asymmetric distance computation (ADC) against compressed codes. Paired with **IVF** (inverted file over coarse centroids) it defined billion-scale ANN for a decade (IVFADC). **OPQ** (Ge et al., CVPR 2013 [prior knowledge]) added a learned rotation to balance subspace variances. Limitation: reconstruction-error objective is misaligned with ranking error, and codebook training assumes a static distribution.

### Phase 2 — Graph indexes take over in memory (2016–2019)

- **HNSW** — Malkov & Yashunin — arXiv:1603.09320, TPAMI 2018 [prior knowledge — canonical]. Multi-layer navigable small-world graph; greedy beam search; became the default in nearly every vector DB. Strengths: excellent recall/QPS in RAM, incremental inserts. Structural weaknesses (documented across the 2024–2026 literature, see Failure Modes): no true delete, memory-resident assumption, local-optima entrapment from random insertion order, and no accuracy guarantees. Recent patch-work research: MN-RU for update-induced unreachable points ([emergentmind topic survey](https://www.emergentmind.com/topics/hnsw-algorithm)); dual-branch HNSW with skip bridges and LID-driven insertion (arXiv:2501.13992); HNSW with accuracy guarantees via graph spanners (arXiv:2607.02338).
- **DiskANN / Vamana** — Subramanya, Devvrit, Simhadri, Krishnaswamy, Kadekodi — NeurIPS 2019 ([Microsoft DiskANN wiki](https://github.com/microsoft/DiskANN/wiki/DiskANN-Project-and-Research-Overview-(2018%E2%80%90present))). Flat graph (Vamana) with RobustPrune and α-relaxed pruning tuned so a beam search does few, large SSD reads; billion vectors on one 64 GB machine. First credible break from the RAM-resident assumption; ~10× vector capacity per node.

### Phase 3 — Learned/anisotropic quantization; disk & streaming (2020–2023)

- **ScaNN / anisotropic vector quantization** — Guo et al. — ICML 2020, arXiv:1908.10396 ([Google Research blog](https://research.google/blog/announcing-scann-efficient-vector-similarity-search/)). Loss function weights the component of quantization error parallel to the datapoint (which corrupts inner products) more than the orthogonal component. Big MIPS accuracy gains over reconstruction-loss PQ.
- **SPANN** — Chen et al. — NeurIPS 2021, arXiv:2111.08566 [prior knowledge; corroborated by citations in fetched papers]. Memory/disk hybrid *inverted index*: centroids in RAM, postings on SSD, with closure-based duplication of boundary vectors. Beat DiskANN on some billion-scale workloads with simpler I/O (one posting read vs. multi-hop graph walk). Notably does not natively support metadata predicates (post-filtering only, per the GateANN paper's related-work discussion, arXiv:2603.21466).
- **FreshDiskANN** — Singh, Subramanya, Krishnaswamy, Simhadri — arXiv:2105.09613 (2021). First graph index with a principled streaming merge for inserts+deletes maintaining stable recall over long update streams. Deletes still cost a background rebuild-ish merge.
- **Filtered-DiskANN** — Gollapudi et al. — WWW 2023, [DOI 10.1145/3543507.3583552](https://dl.acm.org/doi/10.1145/3543507.3583552). Graph edges chosen jointly on geometry *and* label sets; ~2 orders of magnitude faster filtered queries than post-filtering. Hard limitation: supports only single-label (or small fixed label-set) predicates — noted explicitly by follow-up work ([NaviX, arXiv:2506.23397](https://arxiv.org/pdf/2506.23397)).
- **SPFresh** — SOSP 2023 [venue from prior knowledge]; in-place incremental rebalancing (LIRE protocol) of an SPANN-style cluster index under updates; adopted as the base of turbopuffer's ANN ([turbopuffer docs](https://turbopuffer.com/docs/architecture)).
- **SOAR** — Sun, Guo et al. — NeurIPS 2023 ([Google Research blog](https://research.google/blog/soar-new-algorithms-for-even-faster-vector-search-with-scann/)). Assign each vector to *multiple* IVF partitions with orthogonality-amplified residuals so that the redundant assignment is anti-correlated with the failure mode of the primary. Kept ScaNN at/near the top of ann-benchmarks CPU leaderboards with the smallest memory footprint.
- **CAGRA** — Ootomo et al. — ICDE 2024, arXiv:2308.15136 [ID from prior knowledge]. GPU-native graph (built via IVF-PQ or NN-descent kNN graph, then pruned); 10–30× faster builds than CPU HNSW, 33–77× higher throughput at 90–95% recall ([NVIDIA cuVS blog](https://developer.nvidia.com/blog/optimizing-vector-search-for-indexing-and-real-time-retrieval-with-nvidia-cuvs/), [Spheron 2026 guide](https://www.spheron.network/blog/deploy-nvidia-cuvs-cagra-gpu-vector-search-indexing/)).
- **ACORN** — Patel, Kraft, Guestrin, Zaharia — SIGMOD 2024, arXiv:2403.04871. Predicate-*agnostic* filtered ANN: a denser HNSW variant traversed with predicate-aware pruning at query time; handles arbitrary, high-cardinality, unbounded predicate sets; 2–1,000× throughput over pre/post-filtering baselines at fixed recall.

### Phase 4 — Extreme quantization, object storage, and consolidation (2024–mid-2026)

- **RaBitQ** — Gao & Long — SIGMOD 2024 ([repo](https://github.com/gaoj0017/RaBitQ), now [RaBitQ-Library](https://github.com/VectorDB-NTU/RaBitQ-Library)). Randomized 1-bit-per-dimension quantization with a *sharp theoretical error bound* on distance estimates — the first practical quantizer with a proven bound; beats PQ variants on accuracy-efficiency.
- **Extended RaBitQ** — Gao et al. — SIGMOD 2025, arXiv:2409.09913 ([repo](https://github.com/VectorDB-NTU/Extended-RaBitQ)). Generalizes to arbitrary B bits/dim, "practical and asymptotically optimal"; dominant accuracy at 2–6 bits, often obviating reranking. Adopted rapidly: Elasticsearch "BBQ", VectorChord, LanceDB (10B-scale tier), turbopuffer ANN v3.
- **Object-storage-native engines**: turbopuffer (2023–, SPFresh+RaBitQ on S3/GCS, [architecture](https://turbopuffer.com/docs/architecture)); LanceDB / Lance format ([GitHub](https://github.com/lance-format/lance)); **Amazon S3 Vectors** (preview July 2025, GA December 2025 — [AWS](https://aws.amazon.com/s3/features/vectors/)) — the strongest possible signal that vector search is becoming a *storage feature*, not a database category.
- **GPU mainstreaming**: NVIDIA cuVS integrated into FAISS ([wiki](https://github.com/facebookresearch/faiss/wiki/GPU-Faiss-with-cuVS)), Milvus, Lucene, Elasticsearch ([Elastic blog](https://www.elastic.co/search-labs/blog/elasticsearch-gpu-accelerated-vector-indexing-nvidia)), OpenSearch ([blog](https://opensearch.org/blog/gpu-accelerated-vector-search-opensearch-new-frontier/)), AlloyDB/Vertex AI. Dominant pattern: *build on GPU (CAGRA), convert to HNSW, serve on CPU*.
- **2026-era research wave** (preprints, mostly unreviewed): GateANN — I/O-efficient filtered search on SSDs (arXiv:2603.21466); OctopusANN — systematic design-space study of disk-graph I/O (arXiv:2602.21514); NaviX — predicate-agnostic vector index inside a graph DBMS (arXiv:2506.23397); HAKES — scalable disaggregated embedding-search service (arXiv:2505.12524); IVF-TQ — calibration-free streaming quantization (arXiv:2605.17415); DARTH — declarative recall targets via early termination (arXiv:2505.19001); Fantasy — GPU-cluster search with GPUDirect Async (arXiv:2512.02278); TRIM — triangle-inequality pruning (arXiv:2508.17828); TaCo — subspace-collision ANN (arXiv:2603.24919); learning-based filtered-ANN query planning (arXiv:2602.17914); "To GPU or Not to GPU" for relational+vector engines (arXiv:2605.15957); the SIGMOD 2026 tutorial/survey "Vector Search for the Future" (Song, Zhou, Jensen, Xu — arXiv:2601.01937) which canonizes the memory → heterogeneous-storage → cloud-native progression.
- **Evaluation reform wave**: VIBE (arXiv:2505.17810), Robustness-δ@K (arXiv:2507.00379), "Recall What Matters" (arXiv:2606.04522), deletion-evaluation methodology (arXiv:2512.06200). See Benchmarks section.

---

## State of the art — mid-2026 snapshot

**In-memory, CPU, single node**: HNSW remains the deployed default everywhere; ScaNN+SOAR remains the best speed/memory trade on classic CPU benchmarks (Google Research claims; consistent with ann-benchmarks history). RaBitQ-family quantization (1–8 bit) layered under either graph or IVF indexes is the biggest practical accuracy-per-byte advance since PQ, and is now shipping in Elasticsearch (BBQ), VectorChord, LanceDB, and turbopuffer.

**Billion-scale, cost-sensitive**: SSD-graph (DiskANN lineage) and cluster/posting (SPANN/SPFresh lineage) designs are both production-proven. A practitioner writeup ([wilsonl.in](https://blog.wilsonl.in/diskann/)) reports replacing a 3 TB-RAM sharded HNSW cluster with a single 96 GB DiskANN machine (~40× cheaper). I/O is 70–90% of query latency in SSD systems (OctopusANN, arXiv:2602.21514), so page layout and beam scheduling — not distance math — is the battleground.

**Trillion-scale / cheapest tier**: object-storage-native. turbopuffer ANN v3 reports 100B vectors (≈200 TiB), 200 ms p99 warm, ~$70/TB/mo vs ~$3,600/TB/mo for RAM-resident designs ([blog](https://turbopuffer.com/blog/ann-v3), vendor numbers). Amazon S3 Vectors GA (Dec 2025): 2B vectors/index, ~100 ms warm / sub-second cold, "up to 90%" cost reduction (AWS marketing). The tiering pattern — object storage as source of truth, stateless compute, NVMe/RAM cache — is the consensus architecture for new systems (SIGMOD 2026 survey, arXiv:2601.01937).

**GPU**: index *construction* on GPU is now mainstream (CAGRA via cuVS in FAISS/Milvus/Lucene/Elasticsearch/OpenSearch); GPU *serving* remains niche because host↔device transfer and small-batch, high-QPS serving economics favor CPU (arXiv:2605.15957 finds relational operators benefit from GPU more than the ANN search itself unless index+embeddings are reorganized to fit device memory).

**Filtered search**: recognized as the #1 gap between benchmarks and production ("most production search queries have a WHERE condition" — [turbopuffer](https://turbopuffer.com/blog/native-filtering)). ACORN-style predicate-agnostic traversal, Filtered-DiskANN-style label-aware graphs, and cluster-level filter pushdown (turbopuffer native filtering) coexist; no approach dominates across selectivity regimes, and a 2026 systems analysis (arXiv:2602.11443) plus learned query planners (arXiv:2602.17914) treat filter-strategy *selection* as an open query-optimization problem.

**Landscape**: the standalone-vector-DB category is fragmenting/commoditizing rather than consolidating around a winner ([Actian Q2-2026 state-of](https://www.actian.com/blog/developer/state-of-vector-databases-q2-2026/), [digitalapplied 2026 comparison](https://www.digitalapplied.com/blog/vector-databases-for-ai-agents-pinecone-qdrant-2026)). Default choice is increasingly "whatever engine you already run" — pgvector for Postgres shops (competitive to ~10–50M vectors), Elasticsearch/OpenSearch for search shops, S3 Vectors for cold AWS-native tiers — with dedicated engines (Milvus, Qdrant, Weaviate, Pinecone, turbopuffer, Vespa, LanceDB, Chroma) differentiating on scale, filtering, hybrid search, or cost.

---

## Thematic deep-dives

### 1. Graph indexes: strengths and structural debt

HNSW's dominance is an artifact of the RAM era. Its documented structural problems:

1. **Deletion is unsolved in the core algorithm.** hnswlib "still has no such API" for true deletes; tombstoning accumulates graph garbage that queries must traverse and discard ([wilsonl.in](https://blog.wilsonl.in/diskann/)). Deletion algorithms trade query latency, recall, or deletion time against each other; repeated insert/delete cycles create *unreachable points* (MN-RU line of work). A NeurIPS 2025 workshop paper (arXiv:2512.06200) had to *establish the evaluation methodology* for deletions — in 2025 — because no practical standard existed; it proposes Deletion Control, dynamically choosing among masking/repair strategies per accuracy target.
2. **No guarantees.** Beam search on a heuristic graph gives no per-query bound. Graph-spanner-based construction with accuracy guarantees is a 2026 research direction (arXiv:2607.02338), not practice.
3. **Local optima from insertion order.** Random insertion yields disconnected regions and weak inter-cluster connectivity (arXiv:2501.13992).
4. **RAM economics.** The whole graph plus vectors must be memory-resident; random SSD reads are ~200× slower than RAM and break the algorithm's access pattern (wilsonl.in). At 1B×1536-d fp32 this is TBs of RAM.

DiskANN/Vamana fixes (2) partially via α-pruning's long-range edges and (4) by design; RobustPrune gives a defensible in-place delete. The DiskANN project itself now frames its 2025 work as "in-place updates" replacing FreshDiskANN's merge-based approach, plus DistributedANN ([MS wiki](https://github.com/microsoft/DiskANN/wiki/DiskANN-Project-and-Research-Overview-(2018%E2%80%90present))). Deployment: Bing, Ads, M365, Windows, Azure DBs; re-implementations in pgvectorscale (StreamingDiskANN), JVector (DataStax/IBM), Intel SVS, Redis, Milvus, Pinecone, Weaviate.

The disk-graph design space is now being mapped systematically: OctopusANN (arXiv:2602.21514) decomposes it into memory layout × disk layout × search algorithm, finds I/O is 70–90% of latency, that memory-resident navigation graphs and dynamic beam width are the highest-value techniques, and that composed optimizations beat DiskANN by 87–149% and Starling by 4–38% at matched accuracy. Takeaway for framework design: disk-ANN performance is a *composition* problem, and single-technique papers overstate their standalone value.

### 2. Partition/cluster indexes and the quantization renaissance

IVF's revival is driven by three properties graphs lack: **O(1) bounded I/O per query** (read a posting list, not a path), **cheap updates** (append to a posting; SPFresh rebalances incrementally), and **natural filter pushdown** (skip clusters with no matching docs). This is why the object-storage generation (turbopuffer, S3 Vectors presumably, LanceDB IVF-PQ) is cluster-based, not graph-based: a graph walk needs "a dozen or more roundtrips" to object storage vs ≤2–3 for a clustered layout ([turbopuffer docs](https://turbopuffer.com/docs/concepts), [architecture](https://turbopuffer.com/docs/architecture)).

Quantization progression:
- PQ/OPQ (2011/2013): reconstruction-loss codebooks; needs training; drifts as data distribution shifts.
- Anisotropic VQ (ScaNN, ICML 2020, arXiv:1908.10396): score-aware loss for MIPS.
- SOAR (NeurIPS 2023): redundancy with orthogonality-amplified residuals — multi-assignment designed so the backup partition succeeds precisely when the primary fails.
- RaBitQ (SIGMOD 2024) / Extended RaBitQ (SIGMOD 2025, arXiv:2409.09913): codebook-light randomized quantization with *provable* error bounds; arbitrary bits/dim; SIMD/bitwise distance estimation. Enables the "binary quantize + tiny rerank set" pattern: turbopuffer ANN v3 reranks only ~1% of candidates in full precision ([blog](https://turbopuffer.com/blog/ann-v3)).
- IVF-TQ (arXiv:2605.17415, 2026 preprint): codebook-*free* residual layer targeting the remaining weakness — streaming settings where trained codebooks/calibration go stale.

A notable second-order effect reported by turbopuffer: with 1-bit codes, ANN becomes **compute-bound, not bandwidth-bound** (64× arithmetic-intensity increase), moving the bottleneck to SIMD instruction efficiency (AVX-512). Quantization has effectively inverted the classic "ANN is memory-bound" assumption at the top of the hierarchy.

### 3. Disk and object-storage architectures

Three tiers are now distinct (SIGMOD 2026 survey taxonomy, arXiv:2601.01937):

1. **Memory-resident** (HNSW/ScaNN in FAISS, Qdrant, etc.): ~$3,600/TB/mo (turbopuffer's estimate), p50 <10 ms, best for hot high-QPS.
2. **SSD-resident** (DiskANN, SPANN, Starling, OctopusANN; pgvectorscale, VectorChord): ~$1,600/TB/mo with replication (vendor estimate) down to commodity single-node; I/O-dominated latency.
3. **Object-storage-native** (turbopuffer, LanceDB, S3 Vectors, and "vecpuff"-style hobby builds — [blog](https://blog.karanjanthe.me/posts/vecpuff/)): ~$70/TB/mo; object storage is the *source of truth* in an LSM; compute nodes stateless; cold p90 250–450 ms, warm 10–18 ms (turbopuffer numbers). Write path: WAL commit to object storage → async index build.

S3 Vectors' GA constraints are instructive as a floor of what "vector search as a storage primitive" means ([design-decision guide](https://hidekazu-konishi.com/entry/amazon_s3_vectors_design_decision_guide.html)): 2B vectors/index; dims ≤4,096 and *immutable* per index; cosine/Euclidean only; topK ≤100; filterable metadata ≤2 KB per vector (ACL-heavy workloads exhaust this fast); 2,500 vectors/s write ceiling per index; no hybrid lexical search; latency is access-frequency-dependent. AWS explicitly positions it as the cold tier under OpenSearch as the hot tier — tiered vector storage is now a first-party AWS pattern.

Lance/LanceDB represents the "lakehouse" variant: a columnar format with fast random access (claimed 100× vs Parquet), versioned data, and indexes (IVF-PQ, HNSW, inverted text, bitmap) living *next to the data* in object storage ([lance GitHub](https://github.com/lance-format/lance)). This collapses the embedding-pipeline/vector-DB boundary: the training/eval corpus and the searchable index are the same artifact. There is an open request to add CAGRA GPU indexing to Lance ([issue #6534](https://github.com/lance-format/lance/issues/6534)).

### 4. Streaming updates, deletions, freshness

The static-index assumption is the deepest legacy problem for agentic-memory workloads (frequent writes, per-session data, right-to-be-forgotten deletes):

- FreshDiskANN (arXiv:2105.09613): merge-based streaming with stable recall; deletes amortized in background merges.
- SPFresh (SOSP 2023): in-place cluster splits/merges (LIRE), avoiding whole-index rebuilds; basis of turbopuffer.
- DiskANN "in-place updates" (2025, MS wiki): graph edits without merges.
- Insert-throughput reality check in Postgres land ([VectorChord blog, vendor benchmark](https://blog.vectorchord.ai/vector-search-over-postgresql-a-comparative-analysis-of-memory-and-disk-solutions)): VectorChord (IVF+RaBitQ) 1,565 inserts/s vs pgvector HNSW 246/s vs pgvectorscale 107/s — an ~6–15× penalty for graph maintenance. Cluster indexes structurally win on write throughput.
- Deletion evaluation was only formalized in Dec 2025 (arXiv:2512.06200): three deletion-strategy families, no prior comprehensive methodology, and a controller that switches strategy per accuracy requirement. Under high-frequency modification, HNSW recall degrades and unreachable-point growth must be actively suppressed (MN-RU).

Implication: any framework promising "agent memory with instant forget" is writing checks the index layer struggles to cash — either you tombstone (recall/latency rot), repair (write amplification), or rebuild (staleness window).

### 5. Filtered ANN, ACLs, hybrid search, multi-tenancy

Filtering is where benchmark-world and production-world diverge hardest:

- **Post-filtering**: fast, recall can be ~0% under selective predicates (measured 20 ms @ 0% recall in turbopuffer's example).
- **Pre-filtering**: exact but O(dims × matches) brute force (10 s in the same example).
- **Native/integrated**: Filtered-DiskANN (label-aware edges; limited to single-label predicates), ACORN (predicate-agnostic dense-graph traversal, 2–1,000× over baselines, arbitrary predicates), cluster-pushdown (turbopuffer: route to nearest clusters *containing at least one match*), NaviX (predicate-agnostic inside a graph DBMS, arXiv:2506.23397), GateANN (I/O-efficient filtered SSD search, arXiv:2603.21466), and windowed/timestamp filters (ICDE 2025 work on temporal ANN, [slides](https://www.hufudb.com/static/slides/2025/ICDE25-wang.pdf)).
- A 2026 system-design analysis of filtered ANN across vector DBs (arXiv:2602.11443) and learned filter-strategy planners (arXiv:2602.17914) both conclude the optimal strategy depends on predicate selectivity and correlation between filter and vector distribution — i.e., this is a *query optimization* problem the current generation of vector DBs mostly solves with static heuristics.
- **ACL/multi-tenancy**: the common production patterns are (a) namespace-per-tenant (turbopuffer's model — cheap because cold namespaces cost only object storage), (b) filter-based ACLs (hits metadata budgets — S3 Vectors' 2 KB filterable cap is quickly exhausted by ACL lists), (c) partition-per-tenant in shared indexes (Qdrant/Weaviate/Milvus multi-tenancy features). No peer-reviewed treatment of ACL-filtered recall behavior surfaced in this pass; this is an evaluation gap.
- **Hybrid lexical+vector**: BM25 remains non-negotiable for exact-match/rare-token queries. Engines: Lucene (Elasticsearch/OpenSearch — now with reciprocal-rank-fusion pipelines and cuVS-accelerated vector segments), Tantivy (Rust Lucene-alike; used by Quickwit and several vector DBs) [prior knowledge — not re-verified this pass], BM25S (fast eager-scoring Python BM25) [prior knowledge — not re-verified this pass]. Vespa and recent GPU research (all-in-one graph-based hybrid indexing on GPUs, arXiv:2511.00855) push fused single-index hybrid retrieval. Weaviate's differentiation is native hybrid; Elasticsearch/OpenSearch treat vector as another field type in a mature lexical engine — arguably the strongest convergence force in the landscape.

### 6. GPU indexing and serving

- CAGRA (cuVS): build 10–30× faster than CPU HNSW (H100 builds a 100M-scale index in <30 min per NVIDIA/partner blogs); serve at 33–77× CPU throughput at 90–95% recall *if* you serve on GPU.
- The pragmatic pattern is **GPU-build → CPU-serve**: cuVS converts CAGRA graphs to HNSW-compatible format ([FAISS wiki](https://github.com/facebookresearch/faiss/wiki/GPU-Faiss-with-cuVS)); Elasticsearch and OpenSearch both shipped GPU-accelerated *indexing* (not serving) in 2025–2026.
- "To GPU or Not to GPU" (arXiv:2605.15957, Alonso group): in relational+vector engines, the *relational* operators gain more from GPUs than ANN does; GPU vector search loses whenever index+embeddings must shuttle across PCIe; they propose index reorganizations to shrink device-resident state. Fantasy (arXiv:2512.02278) scales to GPU clusters with GPUDirect Async.
- Framework takeaway: GPUs solved the *index build/rebuild* cost problem (which changes the calculus for freshness — cheap rebuilds compete with clever incremental updates), not the serving-economics problem.

### 7. The 2026 vector DB landscape and convergence

Distinct strategic positions (community stats from [digitalapplied](https://www.digitalapplied.com/blog/vector-databases-for-ai-agents-pinecone-qdrant-2026); GitHub stars mid-2026: Milvus 44k+, Qdrant 32k+, Chroma 28k+, Weaviate 16k+, LanceDB 10k+ but fastest mindshare growth):

- **Dedicated engines**: Milvus (distributed billion-scale, GPU support), Qdrant (Rust, fast filtering/JSON payloads; one 2026 comparison claims 10–25% faster than Weaviate/Milvus on common workloads — vendor-adjacent, treat cautiously), Weaviate (native hybrid + integrated embedding), Pinecone (managed; Timescale's benchmark showed pgvector+pgvectorscale beating Pinecone s1 by 28× p95 latency at 99% recall — [Tiger Data blog](https://www.tigerdata.com/blog/pgvector-is-now-as-fast-as-pinecone-at-75-less-cost), vendor benchmark), Chroma (developer-first, now on a distributed Rust core), turbopuffer (object-storage economics; used by Cursor/Notion per their site), LanceDB (lakehouse/multimodal), Vespa (mature fused ranking engine).
- **Extended incumbents**: pgvector (HNSW since 0.5.0; "matches or beats dedicated DBs at 1M scale" per Supabase-cited benchmarks) + pgvectorscale (StreamingDiskANN + statistical binary quantization) + VectorChord (RaBitQ+IVF; highest insert throughput and high-recall QPS among the Postgres trio per its own benchmarks); Elasticsearch/OpenSearch (BBQ quantization, GPU indexing, S3-tiering via s3vector engine); Redis, MongoDB Atlas, ElastiCache vector search (Oct 2025), SQL-engine integrations (AlloyDB + cuVS).
- **Convergence thesis** (supported across [Actian](https://www.actian.com/blog/developer/state-of-vector-databases-q2-2026/), landscape posts, and the S3 Vectors launch): vector search is becoming a *feature of every data system* rather than a category; selection criteria have shifted from raw ANN performance to platform gravity (existing Postgres/AWS/Elastic estate), filtering/hybrid capability, and cost tier. The counter-trend: specialized engines survive at the extremes — extreme scale (Milvus, turbopuffer), extreme cheapness (S3 Vectors), extreme integration (LanceDB with training pipelines).

### 8. Benchmarks and their pathologies

- **ann-benchmarks** (Aumüller, Bernhardsson, Faithfull; [GitHub](https://github.com/erikbern/ann-benchmarks)): the canonical recall-vs-QPS harness; single-core CPU; now effectively **unmaintained** and its datasets (SIFT/GloVe-era) unrepresentative of modern embedding workloads.
- **big-ann-benchmarks** (NeurIPS'21/23 challenge tracks): billion-scale, added filtered/streaming/OOD/sparse tracks [prior knowledge; corroborated by VIBE's discussion].
- **VDBBench / VectorDBBench** (Zilliz): full-system (not library) benchmarking — ingestion, filtering, concurrency ([Milvus reference](https://milvus.io/ai-quick-reference/what-role-do-tools-like-annbenchmark-for-algorithmlevel-comparison-and-vectordbbench-for-full-database-benchmarking-play-and-how-does-each-assist-in-evaluating-different-aspects-of-performance)); vendor-run, so results need independent replication.
- **VIBE** (arXiv:2505.17810; VecDB@VLDB2026): 22 index implementations × 19 datasets from modern embedding models, including 8 OOD datasets (query and corpus from different distributions/modalities — the norm in RAG, cross-modal retrieval, and approximate-attention MIPS). Directly indicts ann-benchmarks' dataset validity.
- **Robustness-δ@K** (arXiv:2507.00379; MSR-affiliated authors): average recall masks a long tail of hard queries; indexes with identical mean recall differ substantially in the *fraction of queries above a recall threshold*, and the more robust index yields better downstream RAG quality. Tail recall, not mean recall, is the RAG-relevant metric.
- **"Recall What Matters"** (arXiv:2606.04522): argues Recall@k itself is the wrong target — 1/Ratio@k (distance-approximation ratio) tracks downstream task quality (classification, LLM-graded answer quality) better, and optimizing for it reaches operational quality at much lower cost. Tension with the robustness paper: one says mean-recall hides tail failures; the other says recall overstates the cost of approximation. Both agree the field's headline metric is broken; they disagree on the fix (distributional recall vs. distance-ratio). A next-gen framework should probably measure *task-conditioned tail quality*.
- **Deletion evaluation** (arXiv:2512.06200): no established methodology existed before late 2025; prior work used unrealistic setups.
- **Pitfall summary**: static workloads (no updates/deletes), no filters, in-distribution queries, mean-recall-only, single-core CPU rules that ignore SIMD/GPU realities, vendor self-benchmarks (Timescale vs Pinecone, VectorChord vs pgvectorscale, Qdrant comparisons — every one of these favors its author), and cost never appearing on the axes despite being the actual decision variable at scale.

---

## Comparison tables

### Index-family tradeoffs

| Family | Exemplars | Recall/QPS (RAM) | I/O per query (cold) | Insert cost | Delete story | Filter pushdown | Guarantees |
|---|---|---|---|---|---|---|---|
| Graph (RAM) | HNSW, NSG | Excellent | Poor fit (many random reads) | High (graph edits); ~250 ins/s in pgvector | Tombstones; unreachable-point rot | Bolt-on (ACORN) | None |
| Graph (SSD) | DiskANN/Vamana, Starling, OctopusANN | Very good | Few beam-batched reads; I/O = 70–90% latency | Merge- or in-place repair | RobustPrune / FreshDiskANN merges | Filtered-DiskANN (single label) | None |
| Cluster/IVF | SPANN, SPFresh, ScaNN+SOAR, VectorChord | Good (needs quantization + rerank) | ≤2–3 roundtrips (object-storage-friendly) | Cheap append + rebalance; ~1,565 ins/s VectorChord | Natural (drop from posting) | Natural (skip non-matching clusters) | RaBitQ distance-error bounds |
| GPU graph | CAGRA/cuVS | 33–77× CPU throughput (on GPU) | device-memory bound | Rebuild is cheap (10–30× faster builds) | Rebuild-oriented | Immature | None |

### Storage-tier economics (turbopuffer-published estimates; vendor numbers)

| Tier | Cost | Warm latency | Cold latency | Freshness | Exemplars |
|---|---|---|---|---|---|
| RAM-resident | ~$3,600/TB/mo | <10 ms | — | Immediate | FAISS/HNSW services, Qdrant, Redis |
| SSD (replicated) | ~$1,600/TB/mo | ~10–50 ms | — | Merge windows | DiskANN deployments, pgvectorscale |
| Object storage + cache | ~$70/TB/mo | 10–18 ms p90 | 250–450 ms p90 | WAL-committed, async-indexed | turbopuffer, LanceDB, S3 Vectors |

### Filtered-search strategies

| Strategy | Recall under selective filter | Latency | Predicate generality |
|---|---|---|---|
| Post-filter | Can be ~0% | Best | Any |
| Pre-filter (brute force) | 100% | O(dims × matches); worst | Any |
| Label-aware graph (Filtered-DiskANN) | High | Good | Single/small label sets only |
| Predicate-agnostic graph (ACORN, NaviX) | High | 2–1,000× over baselines | Arbitrary, unbounded |
| Cluster pushdown (turbopuffer) | ~90%+ target | Good, bounded I/O | Attribute indexes; planner-dependent |

---

## Failure modes & critiques

1. **Mean recall is a lie for RAG.** Identical average recall can hide badly different tail behavior (Robustness-δ@K, arXiv:2507.00379); the hard queries that fail are plausibly correlated with exactly the queries where the LLM needs retrieval most. Meanwhile recall itself may overstate approximation harm (arXiv:2606.04522). The field optimizes a metric that neither bounds worst-case behavior nor tracks task utility.
2. **OOD queries break tuned indexes.** Modern RAG queries (short questions vs long-document corpus, cross-modal, instruction-prefixed embeddings) are out-of-distribution w.r.t. the indexed set; ann-benchmarks never tested this; VIBE shows it matters; OOD-DiskANN exists precisely because Microsoft hit it in production.
3. **Filters are an afterthought with catastrophic edge cases.** Post-filtering → 0% recall cliffs; Filtered-DiskANN limited to single labels; strategy choice depends on selectivity/correlation and is mostly hard-coded heuristics (arXiv:2602.11443, arXiv:2602.17914). ACL filtering (every enterprise RAG deployment) stresses metadata budgets (S3 Vectors: 2 KB) and has essentially no public recall-behavior literature.
4. **Deletes rot indexes.** Tombstoning degrades recall and latency; repair costs writes; the community lacked even an agreed evaluation methodology until arXiv:2512.06200. "Forget this document" — a legal requirement — is an unsolved index-maintenance problem in the default (HNSW) index of nearly every deployed system.
5. **Static-index assumption vs. agentic write rates.** Graph inserts are 6–15× slower than cluster inserts (VectorChord benchmarks); trained quantizers (PQ codebooks, RaBitQ calibration to a lesser degree) go stale under distribution drift; IVF-TQ-style calibration-free designs are still preprints.
6. **Benchmarks reward the wrong hardware and workloads.** Single-core CPU rules, no update/delete/filter mixes, no cost axis, unmaintained harnesses; vendor benchmarks are systematically self-favoring (Timescale, VectorChord, Qdrant, Zilliz all publish comparisons they win).
7. **Embedding-model coupling.** Index immutability (S3 Vectors fixes dimension and metric at creation) means every embedding-model upgrade is a full re-embed + re-index of the corpus. No mainstream system versions embeddings or supports incremental migration between embedding spaces.
8. **Graph indexes and object storage are architecturally incompatible.** Multi-hop traversal ⇒ many high-latency roundtrips; the cheapest storage tier structurally forces cluster-style indexes, which need aggressive quantization + rerank to match graph recall — a coupled design constraint, not a free choice.
9. **GPU serving economics don't close.** Transfer overheads make GPU ANN uncompetitive in mixed relational/vector engines unless the resident state is restructured (arXiv:2605.15957); GPU value concentrates in builds.
10. **Recall targets are declarative nowhere.** Users must tune efSearch/nprobe per index/dataset; DARTH (arXiv:2505.19001) and adaptive early termination are research, not product. Systems expose knobs, not SLOs.

---

## Open problems (seeds for a next-generation framework)

1. **Tail-recall SLOs as a first-class contract.** No system today lets a caller say "≥0.9 recall for ≥99% of queries, and tell me when you can't." Combining Robustness-δ@K-style measurement, DARTH-style declarative early termination, and per-query difficulty estimation into an *SLO-bearing retrieval API* is unclaimed territory — and exactly what an agent needs to decide whether to trust, re-query, or escalate to exhaustive search.
2. **Retrieval with error bars.** RaBitQ gives per-distance error bounds — the first primitive from which per-query *confidence* could be derived and surfaced to the RAG layer. Nobody propagates index-level uncertainty to the generator.
3. **A native mutable-corpus index.** Agentic memory implies high write/delete rates, per-session namespaces, and instant forget. Candidate synthesis: cluster-based layout (cheap updates, bounded I/O, filter pushdown) + calibration-free quantization (IVF-TQ direction) + formalized deletion control (arXiv:2512.06200) + GPU-cheap periodic rebuilds as the compaction mechanism. No shipping system combines these.
4. **Filters as query optimization.** Selectivity- and correlation-aware planning across pre/post/native strategies (arXiv:2602.17914 direction), with ACL predicates as the primary benchmark workload rather than an afterthought; requires a public ACL-filtered ANN benchmark, which does not exist.
5. **Embedding-space versioning and migration.** Treat embeddings like schema: versioned, with incremental re-embedding, dual-space search during migration, and compatibility mapping between model versions. Lance's data-versioning is the closest primitive; no one has built the search-layer counterpart.
6. **Task-level evaluation.** Neither Recall@k nor 1/Ratio@k is validated as *the* proxy for RAG answer quality; the two 2026 metric papers disagree. An end-to-end benchmark that scores index configurations by downstream answer quality under realistic (filtered, OOD, updating) workloads would immediately reorder the leaderboards.
7. **Cost as a query parameter.** The three-tier cost structure (RAM/SSD/object ≈ 50:20:1) is static placement today. Per-query cost/latency/recall negotiation — "spend up to X ms and Y roundtrips for this query" — across tiers is open; S3 Vectors + OpenSearch tiering is a manual, coarse version.
8. **Hybrid retrieval as one index, not two glued engines.** BM25 + vector + structured predicates currently means two scoring systems fused by RRF heuristics; fused single-structure designs (Vespa's, arXiv:2511.00855 on GPUs) hint that a unified index over sparse+dense+attribute signals is feasible, which would eliminate an entire class of fusion-tuning failure modes.

---

## Bibliography

**Peer-reviewed / established:**
- Jégou, Douze, Schmid. *Product Quantization for Nearest Neighbor Search.* TPAMI 2011. [prior knowledge — canonical]
- Ge et al. *Optimized Product Quantization.* CVPR 2013. [prior knowledge — canonical]
- Malkov & Yashunin. *HNSW.* arXiv:1603.09320, TPAMI 2018. [prior knowledge — canonical]
- Subramanya et al. *DiskANN.* NeurIPS 2019 — via https://github.com/microsoft/DiskANN/wiki/DiskANN-Project-and-Research-Overview-(2018%E2%80%90present)
- Guo et al. *Accelerating Large-Scale Inference with Anisotropic Vector Quantization.* ICML 2020, arXiv:1908.10396 — https://www.alphaxiv.org/overview/1908.10396v5 ; blog: https://research.google/blog/announcing-scann-efficient-vector-similarity-search/
- Chen et al. *SPANN.* NeurIPS 2021, arXiv:2111.08566. [ID from prior knowledge]
- Singh et al. *FreshDiskANN.* arXiv:2105.09613 — https://arxiv.org/pdf/2105.09613
- Gollapudi et al. *Filtered-DiskANN.* WWW 2023 — https://dl.acm.org/doi/10.1145/3543507.3583552
- SPFresh (in-place cluster index updates). SOSP 2023. [venue from prior knowledge; usage confirmed at https://turbopuffer.com/docs/architecture]
- Sun, Guo et al. *SOAR.* NeurIPS 2023 — https://research.google/blog/soar-new-algorithms-for-even-faster-vector-search-with-scann/
- Ootomo et al. *CAGRA.* ICDE 2024, arXiv:2308.15136. [ID from prior knowledge; corroborated by NVIDIA/partner blogs]
- Patel, Kraft, Guestrin, Zaharia. *ACORN.* SIGMOD 2024 — https://arxiv.org/abs/2403.04871 ; https://dl.acm.org/doi/10.1145/3654923
- Gao & Long. *RaBitQ.* SIGMOD 2024 — https://github.com/gaoj0017/RaBitQ (now https://github.com/VectorDB-NTU/RaBitQ-Library)
- Gao et al. *Extended RaBitQ.* SIGMOD 2025, arXiv:2409.09913 — https://github.com/VectorDB-NTU/Extended-RaBitQ
- Song, Zhou, Jensen, Xu. *Vector Search for the Future.* SIGMOD 2026 tutorial — https://arxiv.org/abs/2601.01937
- Jääsaari, Hyvönen, Ceccarello, Roos, Aumüller. *VIBE.* VecDB@VLDB2026 — https://arxiv.org/abs/2505.17810
- Yamashita, Amagata, Matsui. *How Should We Evaluate Data Deletion in Graph-Based ANN Indexes?* NeurIPS 2025 ML-for-Systems wkshp — https://arxiv.org/abs/2512.06200
- Sandanayake(?) et al. — *Efficient Data Access Paths for Mixed Vector-Relational Search.* arXiv:2403.15807 [authors not verified]

**Preprints (2025–2026, unreviewed unless noted):**
- Wang, Zhang, Lu, Chen, Tan. *Towards Robustness: A Critique of Current Vector Database Assessments.* arXiv:2507.00379
- Dimitropoulos & Mamoulis. *ANN Search: Recall What Matters.* arXiv:2606.04522
- Mageirakos, André, Kabić, Wu, Chronis, Alonso. *To GPU or Not to GPU: Vector Search in Relational Engines.* arXiv:2605.15957
- Li, Gong, Yang, Wang, Wu. *I/O Optimizations for Graph-Based Disk-Resident ANN (OctopusANN).* arXiv:2602.21514
- *GateANN: I/O-Efficient Filtered Vector Search on SSDs.* arXiv:2603.21466
- *NaviX: Native Vector Index for Graph DBMSs with Predicate-Agnostic Search.* arXiv:2506.23397
- *HAKES: Scalable Vector Database for Embedding Search Service.* arXiv:2505.12524
- *IVF-TQ: Calibration-Free Streaming Vector Search.* arXiv:2605.17415
- *DARTH: Declarative Recall Through Early Termination.* arXiv:2505.19001
- *Fantasy: Large-scale Vector Search on GPU Clusters with GPUDirect Async.* arXiv:2512.02278
- *All-in-one Graph-based Indexing for Hybrid Search on GPUs.* arXiv:2511.00855
- *Filtered ANN Search in Vector Databases: System Design and Performance Analysis.* arXiv:2602.11443
- *Efficient Filtered-ANN via Learning-based Query Planning.* arXiv:2602.17914
- *TRIM: Triangle-Inequality-Based Pruning.* arXiv:2508.17828 ; *TaCo.* arXiv:2603.24919 ; *Dual-Branch HNSW.* arXiv:2501.13992 ; *HNSW with Accuracy Guarantees Using Graph Spanners.* arXiv:2607.02338

**Engineering blogs / docs / vendor sources (claims, not peer review):**
- turbopuffer: https://turbopuffer.com/blog/turbopuffer ; https://turbopuffer.com/blog/ann-v3 ; https://turbopuffer.com/blog/native-filtering ; https://turbopuffer.com/docs/architecture ; https://turbopuffer.com/docs/concepts
- Wilson Lin. *From 3 TB RAM to 96 GB: superseding billion-vector HNSW with 40× cheaper DiskANN.* https://blog.wilsonl.in/diskann/
- AWS S3 Vectors: https://aws.amazon.com/s3/features/vectors/ ; preview announcement (Jul 2025) https://aws.amazon.com/about-aws/whats-new/2025/07/amazon-s3-vectors-preview-native-support-storing-querying-vectors/ ; GA (Dec 2025) https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/ ; design guide: https://hidekazu-konishi.com/entry/amazon_s3_vectors_design_decision_guide.html ; GA coverage: https://www.hpcwire.com/bigdatawire/this-just-in/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance/
- NVIDIA cuVS: https://developer.nvidia.com/blog/optimizing-vector-search-for-indexing-and-real-time-retrieval-with-nvidia-cuvs/ ; FAISS+cuVS: https://github.com/facebookresearch/faiss/wiki/GPU-Faiss-with-cuVS ; Elastic GPU indexing: https://www.elastic.co/search-labs/blog/elasticsearch-gpu-accelerated-vector-indexing-nvidia ; OpenSearch GPU: https://opensearch.org/blog/gpu-accelerated-vector-search-opensearch-new-frontier/ ; Spheron cuVS guide: https://www.spheron.network/blog/deploy-nvidia-cuvs-cagra-gpu-vector-search-indexing/
- Lance / LanceDB: https://github.com/lance-format/lance ; https://www.lancedb.com/ ; https://docs.lancedb.com/indexing ; CAGRA request: https://github.com/lance-format/lance/issues/6534
- Postgres ecosystem: pgvectorscale https://github.com/timescale/pgvectorscale/blob/main/README.md ; Timescale-vs-Pinecone https://www.tigerdata.com/blog/pgvector-is-now-as-fast-as-pinecone-at-75-less-cost ; VectorChord comparison https://blog.vectorchord.ai/vector-search-over-postgresql-a-comparative-analysis-of-memory-and-disk-solutions ; https://docs.vectorchord.ai/vectorchord/benchmark/pgvectorscale.html
- Landscape 2026: https://www.actian.com/blog/developer/state-of-vector-databases-q2-2026/ ; https://www.digitalapplied.com/blog/vector-databases-for-ai-agents-pinecone-qdrant-2026 ; https://encore.dev/articles/best-vector-databases ; https://www.firecrawl.dev/blog/best-vector-databases
- Benchmarks: ann-benchmarks https://github.com/erikbern/ann-benchmarks ; VectorDBBench role https://milvus.io/ai-quick-reference/what-role-do-tools-like-annbenchmark-for-algorithmlevel-comparison-and-vectordbbench-for-full-database-benchmarking-play-and-how-does-each-assist-in-evaluating-different-aspects-of-performance ; Zilliz ANN-benchmarks explainer https://zilliz.com/glossary/ann-benchmarks
- Misc: infinilabs Rust DiskANN https://github.com/infinilabs/diskann ; MS DiskANN https://github.com/microsoft/DiskANN ; object-storage build writeup https://blog.karanjanthe.me/posts/vecpuff/ ; ICDE'25 temporal ANN slides https://www.hufudb.com/static/slides/2025/ICDE25-wang.pdf ; ScaNN README https://github.com/google-research/google-research/blob/master/scann/README.md ; emergentmind HNSW survey https://www.emergentmind.com/topics/hnsw-algorithm ; ElastiCache vector search https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-elasticache-vector-search/

**From prior knowledge only (not verified in this pass — verify before citing in the paper):** Tantivy (Rust FTS engine), BM25S (Lù, 2024), Starling (SIGMOD 2024 disk-graph layout), OOD-DiskANN (arXiv preprint), big-ann-benchmarks harness (Simhadri et al.), Aumüller et al. ann-benchmarks paper (Information Systems 2020).
