# Production, Operations & Cost Failures — Cross-Framework Synthesis

> Dimension: **production-ops-cost** (taxonomy categories: `production-ops` + `performance-cost`).
> Synthesized 2026-08-05 from the 19-file framework-autopsy corpus in `research/02-frameworks/`
> and the landscape corpus in `research/01-landscape/` (primary files:
> `indexing-vector-databases.md`, `production-industry.md`, plus `02-frameworks/cross-cutting-gaps.md`).

## Method note

All 19 framework/platform autopsy files were read for their `production-ops` and
`performance-cost` sections (located via grep on the taxonomy headers, then read with
surrounding context). An issue is admitted as **common** only when evidenced in ≥3 independent
frameworks/platform cohorts, with **documented-recurring** evidence forming the spine;
single-anecdote and architectural-inference items are used only as supporting color and are
labeled as such in the evidence tables. The corpus-audit weak-evidence blacklist was enforced:
this synthesis does **not** rely on langchain-langgraph.md's SEO-farm quantified claims
(4× cost, $/query, 45%-never-production), lowcode-builders.md's "10x markdown chunking" claim
or NVD keyword CVE counts, ragflow.md's third-party corroboration layer,
vectordb-and-startup-platforms.md's Pinecone platform-risk claim, or microsoft-graphrag.md's
"$33,000 to index 5 GB" figure (Microsoft's own $20–50/M-token blog is used as directional
only). Where a blacklisted claim would otherwise have been the natural citation, the issue is
either supported from other files or explicitly downgraded to the Near-misses section.
Framework counts below count autopsy files (cohorts), not individual products inside a cohort.

---

## The common issues

### 1. Incremental sync is architecturally broken; freshness is a batch afterthought (`no-incremental-sync`)

**Definition.** No mainstream framework or managed platform treats "one document changed /
was deleted" as a first-class, cheap, verifiable operation; the living-corpus path
(upsert, dedup, delete-by-document, re-embed-on-change) is bolted on after the
one-shot-ingest happy path, and it fails silently or is priced as a full rebuild.

| Framework | Evidence (file + gist) |
|---|---|
| LlamaIndex | `llamaindex.md` P1 (critical, doc-recurring): docstore/vector-store split breaks `refresh_ref_docs` with external stores (#13604, #14057, #13860); `docstore.json` corruption (#19696) |
| LangChain | `langchain-langgraph.md` P1 (doc-recurring): Indexing API is the only sync path — subset-only store support (#11581), slow (#11935), exiled to `langchain-classic`; no CDC/TTL/re-embed orchestration |
| OpenAI/Azure managed | `managed-openai-azure.md` (critical/doc-recurring): OpenAI vector stores don't watch sources; Sept 2025 incident required customers to remove/re-add files; Azure deletion detection is opt-in, must precede first indexer run, and fails on one-to-many chunked indexes — exactly the RAG projection |
| AWS/Google managed | `managed-aws-google.md` (critical/doc-recurring): Bedrock syncs >30 min for 1 new file, stuck >24 h with delete-the-KB workaround, no stop-sync API; Gemini File Search documents are immutable once indexed |
| Microsoft GraphRAG | `microsoft-graphrag.md` (critical/doc-recurring): global artifacts invalidated by new data (#741, 35c); `update` shipped half-working (#1560, #1836); deletion out of scope |
| LightRAG family | `hkuds-lightrag-family.md` P4 (doc-recurring): deletion leaves inconsistent KG state (#985), orphan Neo4j nodes (#2567); "incremental" holds only for append |
| Low-code builders | `lowcode-builders.md` (doc-recurring): stale vectors after updates (Flowise #3570); embedding-model change silently invalidates the whole index |
| Data clouds | `datacloud-rag.md` DP-1 (arch-inference from documented mechanics): freshness knob *is* a billing knob (TARGET_LAG / continuous-sync cluster); default failure mode is a silently stale index |
| Haystack | `haystack.md` (arch-inference): OSS indexing is one-shot; change detection/re-index orchestration is the commercial Enterprise Platform seam |
| Vector DBs / NVIDIA | `vectordb-and-startup-platforms.md` (CDC left entirely to users — "the #1 unowned production problem"); `gpu-vendor-enterprise-rag.md` NeMo #966 re-ingests prior documents — no idempotent ingestion contract |

**Root cause.** Frameworks are demo-optimized: `from_documents()` is the funnel, and a living
corpus requires an orchestration layer (content hashing, doc→chunk lineage, tombstone
propagation, re-embed scheduling) that spans components no single team owns. On managed
platforms the incentive is worse than neglect: freshness is *monetized* (tighter lag = more
compute; Google's index-time-only pricing actively rewards never reindexing), so batch
staleness is a revenue-neutral default. Underneath, graph ANN indexes make deletes tombstones
and updates expensive, so vendors inherit a substrate where "cheap incremental" was never true.

**Research context.** The index layer was solved years before the frameworks: FreshDiskANN
(arXiv:2105.09613, 2021) and SPFresh (SOSP 2023) demonstrate streaming updates with stable
recall; DiskANN in-place updates followed (`indexing-vector-databases.md` §4). What research
did *not* solve — and what remains genuinely open — is the pipeline layer above: deletion
evaluation methodology only appeared Dec 2025 (arXiv:2512.06200), and no work addresses
document→chunk→embedding→derived-artifact change propagation (`production-industry.md` O10:
"staleness as a modelled property, not a cron job"). Frameworks ignore the solved half and
nobody has attacked the unsolved half.

**Next-gen requirement.** Incremental sync as the core contract: mutating or deleting one
document is O(changed content), propagates to chunks, vectors, caches, and derived artifacts,
and is verifiable. **Test:** mutate and delete 1 document in a 1M-document corpus; assert the
index reflects the change within a declared freshness SLO, no orphan chunks remain, and total
compute consumed is proportional to the changed content, not the corpus.

### 2. Platform mortality: abandonment, pivot, and strategic churn are the dominant operational risk (`platform-mortality`)

**Definition.** The single most likely production failure of a RAG stack in this corpus is not
a bug but the platform itself dying — archived, pivoted to enterprise/agents, frozen, or
rewritten incompatibly — stranding users' indexes and accumulated state.

| Framework | Evidence (file + gist) |
|---|---|
| OSS RAG platforms | `oss-rag-platforms.md` P1 (critical/doc-recurring): Verba archived, Cognita archived Mar 2026, R2R dormant with unpatched critical vulns, Kotaemon unanswered "still developed?", Morphik pivoted out of RAG entirely |
| Local-first / memory | `memory-and-localfirst.md` I9 (critical/doc-recurring): Quivr dormant, GPT4All frozen (730 open issues), PrivateGPT's 22-month dark period → re-emerged as a different product, Embedchain absorbed into Mem0 |
| Agent frameworks | `agent-framework-retrieval.md` P1 (critical/doc-recurring): AutoGen frozen with 976 open issues after a total rewrite and fork; SK memory rewritten twice with "no guidance" migration; retrieval code written 2024–25 rewritten twice |
| JVM/JS ecosystems | `jvm-js-ecosystems.md` P2 (critical/doc-recurring): LlamaIndex.TS deprecated with ~527K npm downloads/month still flowing, 109+ issues stranded, open-core redirect to LlamaCloud |
| Low-code builders | `lowcode-builders.md` (critical/doc-recurring): Flowise EOL Aug 2026 post-acquisition; OpenAI Agent Builder deprecated within its first year |
| LlamaIndex (Python) | `llamaindex.md` P3 (doc-recurring): company publicly deprioritizes the OSS framework ("frameworks aren't as central"); release cadence halved |
| Microsoft GraphRAG | `microsoft-graphrag.md`: official Azure accelerator archived; LazyGraphRAG announced Nov 2024, never shipped to OSS 20 months later while shipping in paid products |
| GPU/enterprise vendors | `gpu-vendor-enterprise-rag.md` P8 (doc-recurring): InstructLab archived after being marketed as *the* enterprise path; Watson-brand history |
| Research toolkits | `research-toolkits.md` (doc-recurring): RAGLab zero commits since Oct 2024; AutoRAG pivoted wholesale to an agent product |

**Root cause.** Three reinforcing economics. (i) **Open-core gravity**: VC-backed vendors
maintain OSS only while it feeds the managed platform; when the funnel moves (agents,
document processing), the framework is jettisoned (LlamaIndex.TS, R2R, Morphik). (ii) **No
revenue at the edges**: local-first/personal RAG users are definitionally non-paying, so those
projects pivot to enterprise or stop — destroying the privacy value proposition that acquired
the users. (iii) **Strategy churn at platform vendors**: Microsoft's agent-framework
consolidation and OpenAI's builder deprecation show even the largest vendors treat retrieval
plumbing as expendable. The blast radius is uniquely large because these systems hold
*accumulated stateful indexes*, not just code: abandonment strands the corpus.

**Research context.** Not a research problem, and research offers no mitigation — but the
landscape names the structural answer: `production-industry.md` O13 (design for the
disappearance of the standalone index; Kendra's closure is the market signal) and the
portability primitives that exist by accident: txtai's SQLite-first storage is inspectable
regardless of project fate (`memory-and-localfirst.md` I10), and Lance's versioned columnar
format is the closest thing to a framework-independent retrieval artifact
(`indexing-vector-databases.md` §3). No standard open on-disk format for
chunks+embeddings+lineage exists — genuinely unsolved, and nobody is incentivized to solve it.

**Next-gen requirement.** Survivable state: all persistent retrieval state (documents, chunks,
embeddings tagged with model+version, index config, lineage) lives in a documented, open,
framework-independent on-disk format with an exporter maintained as a conformance-tested
artifact. **Test:** with the framework's binaries deleted, a third party can rebuild a
retrieval-equivalent system (recall parity on a golden set) from the exported state alone.

### 3. Index-time LLM enrichment has unbounded, unestimated economics (`indexing-token-burn`)

**Definition.** The dominant 2024–26 quality recipe — LLM calls per chunk at index time
(entity extraction, contextualization, auto-keywords, community summaries) — multiplies
indexing cost by orders of magnitude over embedding-only, and no framework provides
pre-flight cost estimation, budget caps, or graceful degradation; several trigger full
re-enrichment silently.

| Framework | Evidence (file + gist) |
|---|---|
| Microsoft GraphRAG | `microsoft-graphrag.md` (critical/doc-recurring): per-TextUnit extraction + gleanings + per-community reports; Microsoft's own LazyGraphRAG marketing concedes full indexing is ~1000× a vector index and global search 700× the lazy alternative; day-one HN cost skepticism (HN 40857174). ($33k/5GB figure excluded per blacklist; $20–50/M tokens directional) |
| LightRAG family | `hkuds-lightrag-family.md` C1 (doc-recurring): every chunk through extraction + gleaning re-asks; "extremely slow" on local models (#174); compounds with rate limits at scale (#128, #1648) |
| RAGFlow | `ragflow.md` (doc-recurring): official docs advise disabling its own auto-keyword/auto-question defaults to make indexing affordable; KG chunking of an 875-page PDF exhausted 32 GB (#4668); one-by-one entity embedding (#16205) |
| Snowflake | `datacloud-rag.md` PC-2 (doc-recurring, vendor docs): schema change or `CREATE OR REPLACE` on the source table silently triggers full re-embedding of the entire corpus |
| IBM watsonx | `gpu-vendor-enterprise-rag.md` E5/C5: AutoAI itemizes 3,267,000 tokens for a 100-page/25-question experiment — the honorable exception that proves nobody else even counts |
| AWS Bedrock GraphRAG | `managed-aws-google.md` / `production-industry.md` §4a (vendor docs): a foundation model for graph construction is mandatory and "automatically enables contextual enrichment" — index-time LLM cost is coupled and non-optional |
| n8n / low-code | `lowcode-builders.md` (doc-recurring, mechanism): LLM-per-chunk contextual ingestion sends the whole document per chunk — cost is quadratic-ish in document size by construction |

**Root cause.** Quality benchmarks reward enrichment while cost never appears on the
leaderboard axis, so research artifacts (GraphRAG, LightRAG) ship extraction-maximal defaults;
frameworks productize the paper pipeline without productizing its budget. Vendors have the
opposite incentive to fix it: enrichment tokens are billable (Snowflake bills the silent
re-embed; Bedrock couples enrichment to the feature). Anthropic's contextual retrieval pricing
($1.02/M document tokens with caching, `production-industry.md` Stage 1) shows index-time LLM
calls *can* be made economically routine — but only via prompt-cache engineering no framework
automates.

**Research context.** Research has already produced the cheap alternatives frameworks ignore:
KET-RAG (arXiv:2502.09304) matches/beats GraphRAG at >10× lower indexing cost; E²GraphRAG
(arXiv:2505.24226) indexes 10× faster; MiniRAG (arXiv:2501.06713) needs 25% of the storage.
The most damning artifact is first-party: LazyGraphRAG (0.1% indexing cost) has shipped in
Microsoft's paid products but not the OSS library for 20 months (`microsoft-graphrag.md`,
roadmap-governance). The cost fix exists; distribution incentives block it.

**Next-gen requirement.** Indexing budgets as a typed input: every enrichment pipeline must
emit a pre-run cost/time estimate and accept a hard token/dollar cap, degrading tier-wise
(full enrichment → sampled enrichment → embedding-only) instead of failing or silently
overspending. **Test:** dry-run estimate within ±25% of actual on a reference corpus; with the
cap set to 10% of the estimate, indexing completes with a degraded-but-documented quality tier
and never exceeds the cap; no operation (schema change, re-parse) can trigger corpus-scale
re-enrichment without an explicit confirmation carrying its own estimate.

### 4. Query-time token multiplication with no budget primitive (`query-token-multiplication`)

**Definition.** Agentic/multi-call retrieval designs multiply per-query token cost by 10×–100×
over single-shot RAG — by design, not by bug — and no framework exposes a per-query budget,
cost preview, or cost/quality dial an operator can enforce.

| Framework | Evidence (file + gist) |
|---|---|
| Agent frameworks | `agent-framework-retrieval.md` C1 (doc-recurring): Anthropic's own numbers — naive MCP tool loops at 150k tokens vs 2k code-mediated (98.7% reduction); large tool results transit context twice |
| Azure agentic retrieval | `managed-openai-azure.md` (doc-recurring, vendor docs): planning tokens + rerank tokens on ~subqueries × 50 chunks × ~500 tokens + synthesis; Microsoft's worked example reranks 150M tokens for 2,000 queries; vendor's own advice is to spend less on it |
| LightRAG | `hkuds-lightrag-family.md` C2 (doc-recurring): GraphRAG-Bench (arXiv:2506.05690) measured ~100k-token average prompts vs ~900 for vanilla RAG — ~100× per-query overhead |
| Microsoft GraphRAG | `microsoft-graphrag.md` (doc-recurring): global search map-reduces over *all* community reports — per-query cost grows with corpus size; 700× the lazy alternative |
| Research toolkits | `research-toolkits.md` (doc-recurring): FlashRAG's explicit finding — loop/iterative methods cost multiples "with limited benefits for simpler tasks"; IRCoT/FLARE blow past context windows; no leaderboard reports cost |
| LangChain / LlamaIndex | `langchain-langgraph.md` C1 (docs-based mechanism only; practitioner $ figures blacklisted): agentic-RAG template adds grader+rewriter LLM calls per retrieval miss by design; `llamaindex.md` C1: refine-mode synthesis issues one call per retrieved chunk with hidden templates |
| DSPy | `dspy.md` PC-1/EO-2 (doc-recurring): optimizer runs make thousands of calls with no dry-run cost preview (#397 since 2023); budgets unpredictable ex ante |
| NVIDIA | `gpu-vendor-enterprise-rag.md` C5: agentic mode's cost acknowledged in docs but unquantified — no multiplier, no token accounting |

**Root cause.** Accuracy is bought with tokens because tokens are the only lever a framework
controls without touching the index; vendors bill those tokens, so the exchange rate is
nobody's problem but the customer's. The landscape names it precisely
(`production-industry.md` F3): both Anthropic (4×/15× multipliers; token usage explains 80% of
performance variance) and Microsoft ship agentic retrieval and then immediately publish advice
to use less of it. The missing abstraction is a budget: retrieval APIs are `retrieve(query,k)`,
so fan-out, iteration count, and rerank window are emergent, not declared.

**Research context.** Adaptive-retrieval research (self-routing, sufficiency checks, cheap-path
classifiers) exists and FlashRAG operationalized the cost measurements, but no benchmark
reports cost as a first-class axis, so "cost-optimal RAG" has no leaderboard to win.
`production-industry.md` O2 states the open problem: nobody lets a caller declare "≤800 ms and
≤4k retrieved tokens, best effort" and have the planner solve against it. Genuinely unsolved
at the interface level; the components (query routing, early termination — DARTH
arXiv:2505.19001) exist in isolation.

**Next-gen requirement.** `retrieve(intent, budget, principal) → evidence + cost trace`:
per-query token/latency/dollar budgets enforced by the planner (fan-out, iteration, rerank
window solved against the budget), with per-stage cost decomposition returned on every call.
**Test:** issue the same query with 3 budget levels; measured spend never exceeds each budget,
quality degrades monotonically and observably, and the returned trace attributes ≥95% of
actual billed tokens to named stages.

### 5. Memory leaks and unbounded resource growth in ingestion and serving (`memory-leaks`)

**Definition.** Long-running ingestion and serving processes across independent stacks exhibit
unbounded memory growth or leaks — the batch-ingest workload that production requires is
precisely the workload that OOM-kills the components — and the substrate compounds it because
graph ANN serving is a RAM-resident workload by vendor admission.

| Framework | Evidence (file + gist) |
|---|---|
| RAGFlow | `ragflow.md` (critical/doc-recurring): #4031 parse memory never released; #7995 idle 16 GB API-only deploy climbs to 100%; #11296 task executor idling at 12.8 GB; #11822 OOM with 62 GB RAM |
| NVIDIA / IBM (Docling) | `gpu-vendor-enterprise-rag.md` P1 (critical/doc-recurring): nv-ingest RAM "continuously increases and eventually fails" (#66); Docling 13 GB accumulation on a 0.41 MB PDF (#2209, open 11 months), OOM-killed (#2779, #2788); community guidance is manual sharding |
| LlamaIndex | `llamaindex.md` P2 (doc-recurring): `IngestionPipeline(num_workers>0)` suspected leak (#19712); workflow `Context` leak (#18107) |
| LangGraph | `langchain-langgraph.md` P2 (doc-recurring): checkpointer coroutine leak under default durability (#7094, open) + related fixes; unbounded blob growth (#8054) |
| Onyx (OSS platforms) | `oss-rag-platforms.md` P2 (doc-recurring): Vespa OOM-killed on a 64 GB host, closed "not planned" (#3427) |
| Weaviate/Qdrant | `vectordb-and-startup-platforms.md` (doc-recurring): gradual memory growth over time (weaviate#5071, OOM guardrail work); RAM not released after collection deletion (qdrant#4395, #5268) |
| LightRAG | `hkuds-lightrag-family.md` (doc-recurring): 875-page KG chunking exhausts 32 GB (#4668) |
| Haystack | `haystack.md` (supporting, release-notes concession): pre-3.0 lifecycle could "leak connections, GPU memory, or file handles" in long-running services |

**Root cause.** Ingestion is architected as a library loop, not a resource-governed job
runtime: no streaming with backpressure, no per-document memory ceilings, no checkpoint/resume,
no fail-fast health gates — so leaks that a batch job would amortize become fatal in the
always-on services production actually runs. On the serving side the capacity model is hidden:
Elasticsearch states flatly that for HNSW "all vector data must fit in the node's page cache"
(`cross-cutting-gaps.md` (g)) — vector serving is RAM-sized, and frameworks neither surface
residency as a monitored resource nor plan for eviction, so growth-until-OOM is the default
trajectory.

**Research context.** The index-side answer exists: disk- and object-storage-native designs
(DiskANN/SPANN lineage; turbopuffer-style LSM over object storage at ~$70/TB/mo vs ~$3,600
RAM-resident — `indexing-vector-databases.md` §3) and memory-adaptive edge designs (EdgeRAG,
arXiv:2412.21023) explicitly trade precomputation/residency for bounded memory. Frameworks
default to fully-resident in-process stores anyway. The ingestion-runtime half (bounded-memory
document processing) is unglamorous engineering with no research literature — unsolved by
neglect, not difficulty.

**Next-gen requirement.** A resource-governed ingestion runtime and residency-aware serving:
streaming ingestion with a configurable hard memory ceiling, checkpoint/resume, and per-stage
health gates; serving that monitors index residency and degrades predictably on pressure.
**Test:** ingest a 100 GB corpus under a 4 GB memory cap — completes without OOM, kill -9 at
any point resumes without reprocessing completed documents; RSS of a 7-day continuous
ingest+serve soak stays within a declared envelope.

### 6. Billing is decoupled from workload: idle floors, orphaned resources, non-convertible units (`billing-decoupled`)

**Definition.** Managed retrieval bills on provisioned capacity and proprietary units rather
than on work done: "serverless" products carry idle floors of hundreds of dollars/month,
deleting the visible resource does not delete its billed dependents, pricing units are
mutually non-convertible across vendors, and cost attribution/estimation tooling is absent.

| Framework | Evidence (file + gist) |
|---|---|
| AWS Bedrock KB | `managed-aws-google.md` (critical/doc-recurring): OpenSearch Serverless OCU minimums ≈ $200–$700/mo idle; deleting the KB deletes neither the OpenSearch collection (~$350/mo continues) nor the Neptune graph (AWS's own docs: "additional charges may be incurred until you explicitly delete the graph") |
| Databricks | `datacloud-rag.md` PC-1/AI-2 (doc-recurring): always-on Vector Search endpoints + continuously-billed sync cluster; Vector Search pricing not published ("request a quote"); cost attribution to projects impossible; "pay for idle or accept multi-minute cold starts" |
| Snowflake | `datacloud-rag.md` PC-2 (doc-recurring): Cortex Search bills 6.3 credits/GB-month of uncompressed data-at-rest "regardless of query volume" |
| Google Vertex | `managed-aws-google.md` (doc-recurring): always-on Vector Search endpoints; Vertex AI Search has two parallel metering systems and ≥8 SKUs with mutually incompatible data stores |
| OpenAI/Azure | `managed-openai-azure.md` (doc-recurring): storage billed on *processed* data that "can be much larger" than sources; Azure agentic retrieval requires hand-modeling subquery fan-out × chunk × rerank tokens to estimate cost |
| NVIDIA | `gpu-vendor-enterprise-rag.md` C3 (doc-recurring): NVAIE has no published price at all — TCO cannot be modeled from documentation |
| Cloudflare AutoRAG | `jvm-js-ecosystems.md` P3: simultaneously "available on all plans" and "open beta" — cost at scale unknowable 16 months post-launch |
| Mem0 / DSPy (supporting) | `memory-and-localfirst.md` I13: no token accounting in responses (#2820); `dspy.md` EO-2: no optimizer cost dry-run (#397) |

Cross-vendor non-convertibility is documented directly in `production-industry.md` (SOTA #3,
O8): OpenAI $2.50/1k tool calls + $0.10/GB-day, Google $0.15/M index-time tokens with free
queries, Azure variable retrieval-tokens — units that do not convert, making build-vs-buy and
multi-vendor comparison impossible in principle.

**Root cause.** Provisioned billing smooths vendor revenue and hides the true marginal cost of
retrieval (RAM residency, see issue 5); proprietary units prevent comparison shopping;
orphaned dependents persist because the platform's resource graph has no lifecycle contract —
the same absence of derived-artifact lineage that breaks reproducibility (F13) breaks
teardown. The one historical experiment in honest provisioned pricing — Kendra, billed "even
if empty" — was closed to new customers, showing consumption pricing wins, yet the
"serverless" successors re-created idle floors under a different name.

**Research context.** No research literature addresses retrieval cost semantics; the landscape
flags it as an open problem (`production-industry.md` O8: a normalizing abstraction such as
cost per retrieved useful token). Object-storage-native economics
(`indexing-vector-databases.md`: RAM/SSD/object ≈ 50:20:1) prove near-zero idle cost is
technically achievable — turbopuffer-style architectures bill cold namespaces at object-storage
rates. Genuinely unsolved as an abstraction; solved as infrastructure.

**Next-gen requirement.** Billing lifecycle coupled to resource lifecycle, and normalized cost
telemetry: teardown of a knowledge base enumerates and destroys (or explicitly transfers) every
billed dependent; idle corpora cost object-storage rates; every operation emits cost in a
common decomposition (tokens by stage + storage-hours + compute-seconds). **Test:** after the
single teardown call, the cloud bill shows zero recurring charges attributable to the stack
within one billing cycle; a month of mixed workload can be attributed ≥95% to named
indexes/queries/stages from framework telemetry alone.

### 7. Serving ceilings and tail-latency opacity (`tail-latency-opacity`)

**Definition.** Production retrieval SLOs are written against p99 under concurrent write and
filtered queries, but platforms ship hard low QPS ceilings, publish only relative or
recall-ambiguous latency numbers, and expose no capacity model — so the workload enterprises
actually run (continuous ingest + filtered, ACL'd queries) is the one nobody benchmarks or
guarantees.

| Framework | Evidence (file + gist) |
|---|---|
| Snowflake / Databricks | `datacloud-rag.md` PO-1 (doc-recurring): Cortex Search hard-throttles at 20 QPS per service; Databricks documents ~30 QPS plateaus and 429s requiring client backoff |
| Azure | `managed-openai-azure.md` / `production-industry.md` F12 (vendor docs): semantic ranker limited to 2–4 concurrent requests per search unit with a 4–8 queue; agentic QPS ≈ ranker concurrency ÷ fan-out; 5-minute indexer floor on freshness |
| OpenAI | `managed-openai-azure.md` (doc-recurring): slowest hosted retrieval measured — p50 ~1,358 ms vs ~400 ms for Azure/Bedrock/Vertex (retrievalci) |
| Vector DB vendors | `cross-cutting-gaps.md` (g) (doc-recurring): Qdrant publishes no numeric p95/p99 and concedes bias; Tiger's 28×→1.4× swing between recall operating points; ES kNN page-cache residency requirement; pgvector cold-cache cliff (#666); Milvus concurrent upsert+query staleness/latency spikes (#49435) |
| LightRAG | `hkuds-lightrag-family.md` P3 (doc-recurring): multi-second pipeline "very difficult to use for production" (#1471) |
| Onyx | `oss-rag-platforms.md` P3 (doc-recurring): ~1 doc/sec indexing, no ETA, closed as Stale |
| Dify | `lowcode-builders.md` (arch-inference + issue): knowledge-retrieval node "too slow, causing significant workflow latency" (#34264) |

**Root cause.** Benchmarks and marketing report static-corpus, unfiltered, in-distribution
median throughput because that is the workload graph indexes are best at; real enterprise RAG
(continuous ingest, ACL filters, OOD queries) is the workload they are worst at — and the gap
is not disclosed because nobody's incentive is to publish an absolute p99-at-stated-recall
number they might lose on. Frameworks expose `top_k` but not the capacity model behind it: no
admission control, no read/write isolation, no warmup/pinning, no recall-vs-latency operating
point declaration.

**Research context.** The benchmark community already moved: Big ANN NeurIPS'23
(arXiv:2409.17424) deliberately tested filtered/OOD/sparse/streaming variants;
Robustness-δ@K (arXiv:2507.00379) shows mean recall hides the tail that RAG cares about; DARTH
(arXiv:2505.19001) demonstrates declarative per-query termination. None of it has propagated
into vendor reporting or framework configuration — the measurement science exists, the
plumbing and the incentive don't. `cross-cutting-gaps.md` calls the absence of a neutral
p99-under-concurrent-write-at-stated-recall benchmark "the single largest measurement gap in
the survey."

**Next-gen requirement.** Tail latency as a declared SLO with a shipped harness: read/write
resource isolation, admission control, residency monitoring, and a built-in benchmark that
reports absolute p99 under concurrent write+query on filtered queries at a stated recall
operating point. **Test:** with ingestion running at the declared write rate, filtered-query
p99 stays within the declared SLO for 24 h, and the harness's published number reproduces
within 10% on independent hardware.

### 8. Persistent retrieval state does not survive upgrades, migrations, or restores (`upgrade-dr-fragility`)

**Definition.** Version upgrades, index migrations, backup/restore, and embedding-model
transitions routinely corrupt, strand, or silently invalidate the stored corpus/index; restore
paths are forward-only; and re-embedding — forced periodically by vendor model sunsets — is an
unorchestrated, all-at-once rebuild in every stack.

| Framework | Evidence (file + gist) |
|---|---|
| Vector substrates | `cross-cutting-gaps.md` (e) (doc-recurring): Elasticsearch restore is documented forward-only (no rollback path — regressions force re-ingest from source); Weaviate write-loss window during online migration (#12211) and post-migration empty-result serving (#12215); Milvus restore-hardening PR trail (#51527, #51641, #51908) |
| Low-code builders | `lowcode-builders.md` (doc-recurring): Dify knowledge unusable after 1.9.1→1.9.2 (#27291, 113 comments); Langflow's long tail of DB-migration-on-upgrade failures (#6870, #4698, #9395, #13157) |
| Agent frameworks | `agent-framework-retrieval.md` P2 (doc-recurring): CrewAI version bumps broke default memory storage (#1669, #1333); embedder swaps require manual storage resets |
| OSS platforms | `oss-rag-platforms.md` X1 (doc-recurring): AnythingLLM point release broke ChromaDB embedding (#4712); Onyx search settings disabled after upgrade (#8154) |
| LightRAG | `hkuds-lightrag-family.md` D1 (doc-recurring): regressions across 79 releases/22 months (#2525, #1031); embedding-model change requires manual schema surgery |
| Chroma/Weaviate clients | `vectordb-and-startup-platforms.md` (doc-recurring): DuckDB→SQLite storage migration (#400); 0.6→1.0 version-mixing `InternalError` (#4217); Weaviate v3→v4 client rewrite invalidated the tutorial corpus |
| Data clouds | `datacloud-rag.md` AD-2 (doc-recurring): self-managed→managed index conversion impossible; source schema change = index rebuild; no service cloning |
| AWS/Azure managed | `managed-aws-google.md` / `managed-openai-azure.md` (doc-recurring): Bedrock chunking is a one-way door (change = new KB + full paid re-ingest); Azure capacity is a creation-date lottery historically fixed only by recreate-and-reindex |
| Embedding sunsets | `cross-cutting-gaps.md` (d) (doc-recurring, production-ops): OpenAI hard-shutdown of 16 first-gen embedding models (2024-01-04); Cohere v2 retired 2026-04-04; Azure's 18-month non-extendable clock ending in `410 Gone` — each forcing a full, unorchestrated re-embed |

**Root cause.** Retrieval state is a *derived* artifact (chunks, vectors, graph structures)
whose derivation (parser version, embedder version, index parameters) is recorded nowhere, so
no system can migrate it — only rebuild it, and rebuilds are expensive enough that vendors and
frameworks ship one-way doors instead. HNSW/IVF structures are version- and parameter-specific,
making cross-version restore a rebuild by construction. Meanwhile the embedding model is an
external dependency that can be revoked on a vendor's clock, and no mainstream stack versions
vectors by model or supports dual-index cutover — so every sunset is a synchronized,
ecosystem-wide fire drill.

**Research context.** `production-industry.md` F13/O12 names the missing discipline: lineage
and rebuild determinism for derived artifacts (Bedrock GraphRAG's orphaned, unreproducible
graphs are the productized worst case; Elastic's pin-your-`inference_id` warning is the only
vendor acknowledgment). `indexing-vector-databases.md` open problem 5 states the unbuilt
primitive: embedding-space versioning with incremental re-embedding and dual-space search —
Lance's data versioning is the closest substrate; the search-layer counterpart doesn't exist.
Community adapters (EmbeddingAdapters, VectorAdmin — three independent tools across three
years, `cross-cutting-gaps.md` (d)) are users routing around the missing abstraction.

**Next-gen requirement.** Versioned, transactional migrations for all persistent state: every
derived artifact carries producer version + config lineage; upgrades and embedding-model
transitions run as rolling migrations with dual-read cutover, zero write-loss and zero
empty-result windows; restores are verified (checksum + recall reconciliation) and a
rebuild-from-source path is a tested command. **Test:** upgrade the framework two major
versions under live writes — no data loss, no empty-result window, rollback restores prior
behavior; retire the embedder and cut over to a new one with the corpus serving continuously
and per-query version routing during transition.

---

## Near-misses

Patterns real enough to note, kept out of the common list for evidence honesty:

- **GPU-tax entry floors.** NVIDIA's stack has a documented 3× (Docker) / 8× H100 (Helm)
  floor, +1 GPU per optional service, per-GPU licensing, and GPU-accelerated vector search
  gated behind enterprise access (`gpu-vendor-enterprise-rag.md` P4/C1/C2 — including the
  structural conflict: the entity defining SOTA retrieval cost is compensated per unit of that
  cost). Research toolkits assume 80 GB GPUs and break otherwise (`research-toolkits.md`);
  RAGFlow's DeepDoc is CPU-prohibitive with flaky GPU fallback (`ragflow.md`). Three cohorts,
  but the *structural* form (vendor rent on the whole pipeline) is one vendor's — reported as
  a concentrated risk, not an ecosystem-wide pattern.
- **Heavyweight multi-service deploy fragility.** RAGFlow (mandatory ES+MySQL+MinIO+Redis;
  "container status does not necessarily reflect service status"), NVIDIA's microservice mesh
  ("a dozen cooperating containers means a dozen new ways to be down"), Onyx (12 containers,
  10 GB RAM floor). Meets the 3-cohort bar but overlaps issues 3/5 and skews to the
  self-hosted-platform species; folded here to avoid double counting.
- **Cold-start floors.** ADK 8–20 s import latency, Databricks "scale-to-zero delays responses
  by several minutes," NVIDIA NeMo LLM 5–6 min per deployment start, 60–70 min first Helm
  deploy. Three cohorts, mostly minor severity individually.
- **Pinecone platform risk.** The sale-exploration claim is blacklisted (paywalled second-hand
  reporting); noted only that *if* substantiated it would join issue 2's pattern for
  closed managed stores whose indexes are non-exportable. Not used as evidence.
- **Practitioner cost-surprise magnitudes for LangChain.** The 4×-bill and per-query dollar
  figures trace to SEO content farms (blacklisted). Only the docs-verifiable multi-call
  mechanisms are used (issue 4).
- **Semantic-cache staleness/ACL bypass.** Strongly argued in the landscape
  (`production-industry.md` F9) but with no framework-autopsy incident evidence yet —
  a predicted, not observed, production failure.
- **Databricks free-preview→pay-as-you-go flip** ($6→$30 session, no budget blocking):
  official pricing change + one practitioner report (`datacloud-rag.md` PC-3) —
  single-anecdote on the failure side, folded into issue 6's color.

---

## Dimension synthesis

Production-ops and cost failures are where this corpus stops looking like a list of bugs and
starts looking like a market-structure diagnosis. Four observations:

1. **Every issue above is an incentive-compatible failure.** Freshness is monetized (issue 1),
   enrichment tokens are billable (3), agentic token burn is revenue (4), idle floors smooth
   vendor cashflow (6), tail numbers are withheld because publishing them loses deals (7), and
   one-way doors are lock-in (8). The recurring shape is not incompetence but a principal-agent
   problem: the party that designs the cost/ops model is the party paid by its inefficiency.
   Open-source frameworks don't fix it because their vendors monetize the gap too — sync,
   ACLs, eval, and serving are the open-core seams (Haystack, Onyx, LlamaIndex, LangSmith).

2. **The demo path and the production path are different products.** `from_documents()`,
   in-memory stores, one-shot ingest, unfiltered static-corpus benchmarks — versus living
   corpora, ACL'd filtered queries, continuous writes, upgrades, and teardown. Every framework
   optimizes the first and hopes about the second; the "demo-to-production cliff"
   (`production-industry.md` F2) is this dimension's master failure. Notably, the workloads
   production needs (streaming updates, filtered ANN, tail recall, deletion) are exactly the
   ones the research community *has* studied (FreshDiskANN, ACORN, Robustness-δ@K,
   arXiv:2512.06200) — the ecosystem is stuck not because the problems are unsolved but
   because no layer is accountable for composing the solutions.

3. **State is the liability nobody owns.** Issues 1, 2, 5, 6, and 8 are all facets of one
   omission: persistent retrieval state (chunks, vectors, graphs, caches) is a derived
   artifact with no lineage, no versioning, no portability, no lifecycle, and no owner. That is
   why abandonment strands users, why upgrades corrupt, why teardown keeps billing, why
   deletes tombstone forever, and why every embedder sunset is a fire drill. A
   next-generation framework's single highest-leverage move in this dimension is to make
   derived state first-class: content-addressed, version-tagged, exportable, migratable, and
   cheap to keep cold.

4. **Cost is unmeasured, therefore unmanaged.** No benchmark reports indexing or query cost;
   pricing units don't convert; frameworks don't meter themselves; estimates don't exist
   before spend. Four of the eight issues would be materially defused by one primitive:
   pre-flight estimation plus enforced budgets plus attributable telemetry in a common unit.
   Nothing gets fixed until it appears on an axis someone can lose on.

The testable requirements derived above — O(change) incremental sync, survivable open-format
state, indexing and query budgets with enforcement, a resource-governed ingestion runtime,
lifecycle-coupled billing with attributable telemetry, declared p99-at-recall SLOs with a
shipped harness, and transactional versioned migrations — are this dimension's contribution to
the next-generation framework spec.
