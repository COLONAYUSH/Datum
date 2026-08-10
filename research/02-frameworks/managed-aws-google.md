# Managed RAG platforms: AWS Bedrock Knowledge Bases & Google Vertex/Gemini retrieval

> Framework-autopsy dossier, compiled 2026-08-05. Covers: **Amazon Bedrock Knowledge Bases**
> (customer-managed + the June-2026 "Managed Knowledge Base" tier, GraphRAG/Neptune, structured
> text-to-SQL, Kendra legacy) and **Google's retrieval stack** (Vertex AI Search / "Agent Search",
> Vertex AI RAG Engine, Vertex AI Vector Search, Gemini API File Search tool, Grounding with
> Google Search). Evidence labels: `documented-recurring` / `single-anecdote` /
> `architectural-inference`.

---

## Identity & adoption

### AWS Bedrock Knowledge Bases (KB)
- **Maintainer/license:** Amazon Web Services; fully proprietary managed service (no repo, no stars —
  adoption is proxied by AWS re:Post/StackOverflow volume and the aws-samples cookbook repos).
- **Timeline:** GA at re:Invent Nov 2023. July 2024: advanced parsing (FM parsing), semantic &
  hierarchical chunking, custom-Lambda transforms, query reformulation
  ([AWS what's-new](https://aws.amazon.com/about-aws/whats-new/2024/07/knowledge-bases-amazon-bedrock-advanced-rag-capabilities)).
  Dec 2024: GraphRAG with Neptune Analytics, structured-data (text-to-SQL) KBs, reranking APIs.
  2025: S3 Vectors store (cheap, preview), Bedrock Data Automation parsing. **June 2026:
  "Amazon Bedrock Managed Knowledge Base"** — a second, higher-abstraction tier where AWS owns the
  vector store, adds SaaS connectors (SharePoint, Confluence, Google Drive, OneDrive, Web Crawler),
  ACL-aware retrieval, "Smart Parsing", agentic multi-hop retrieval, and native MCP exposure via
  AgentCore Gateway ([AWS blog](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-managed-knowledge-base-for-faster-more-accurate-enterprise-ai-applications/)).
  The docs now *recommend the Managed tier over the original product* ("For optimized retrieval
  accuracy and a managed experience, we recommend Amazon Bedrock Managed Knowledge Base" —
  [KB user guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)) — an
  implicit admission that the original DIY-vector-store design was too hard to hold correctly.
- **Legacy:** Amazon Kendra (2019 "ML-powered enterprise search") survives as the "Kendra GenAI
  index" KB type. Kendra's reputation is poor (see Issues) and its pricing floor
  (~$1,800/mo at launch) throttled adoption ([HN](https://news.ycombinator.com/item?id=21695643)).

### Google Vertex/Gemini retrieval
- **Maintainer/license:** Google Cloud / Google DeepMind; proprietary managed services.
- **Portfolio (a spectrum, per Google's own community writers)**
  ([GCP RAG Spectrum, Medium/Google Cloud Community](https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a)):
  1. **Vertex AI Vector Search** (ex-Matching Engine, ScaNN-based) — raw ANN index, DIY everything.
  2. **Vertex AI RAG Engine** (2024; originally launched as "LlamaIndex on Vertex AI") — managed
     corpus/ingestion/retrieval framework with pluggable vector DBs (RagManagedDb, Vector Search,
     Feature Store, Pinecone, Weaviate) ([docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview)).
  3. **Vertex AI Search** — turnkey "Google-quality" enterprise search. Naming churn:
     Gen App Builder (2023) → Vertex AI Search & Conversation → Vertex AI Agent Builder (2024) →
     AI Applications (2025) → now billed as **"Agent Search"** under Gemini Enterprise
     ([pricing page](https://cloud.google.com/generative-ai-app-builder/pricing)).
  4. **Gemini API File Search tool** (public preview Nov 2025; multimodal early 2026) — fully
     managed RAG inside the Gemini API: free storage & query-time embeddings, pay only
     $0.15/M tokens at indexing ([Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/file-search-gemini-api/),
     [docs](https://ai.google.dev/gemini-api/docs/file-search)).
  5. **Grounding with Google Search** — web grounding at $35/1k grounded requests past the free
     daily tier ([pricing](https://cloud.google.com/generative-ai-app-builder/pricing)).
- **Momentum (2026):** File Search multimodal launch made HN front page
  ([156 pts, 46 comments](https://news.ycombinator.com/item?id=48080702)); Google is also pushing
  displaced Programmable Search Engine users toward Vertex AI Search after capping PSE at 50
  domains ([HN discussion](https://news.ycombinator.com/item?id=46730436)). Both clouds now bundle
  retrieval into their agent platforms (AgentCore / Gemini Enterprise) — retrieval-as-a-tool is the
  2026 direction on both sides.

---

## Retrieval-pipeline architecture

### AWS Bedrock Knowledge Bases (customer-managed tier)

| Stage | How it's modeled | Defaults & extensibility |
|---|---|---|
| **Ingestion** | Pull-based "data source → sync job" model. S3 primary; Confluence/SharePoint/Salesforce/Web Crawler connectors (many stuck in preview for a long time). `IngestKnowledgeBaseDocuments` direct API added later (10 concurrent req/account). Sidecar `*.metadata.json` files carry per-document metadata. | Sync is batch, manual or scheduled; KB tracks deltas. Limits: ~50 MB/file, per-job file caps (e.g. 1,000 files for FM-parsing/BDA jobs) ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)). |
| **Parsing** | Three parsers: default text extractor; **foundation-model parsing** (Claude/Nova prompt-parses PDFs, tables, images — billed per token); **Bedrock Data Automation**. | FM parsing markedly slows syncs and adds surprise token cost (see Issues). |
| **Chunking** | Fixed-size (default ≈300 tokens, sentence-respecting), semantic, hierarchical (parent/child), none, or **custom transform Lambda** (chunk + chunk-level metadata written back to S3) ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-custom-transformation.html)). | **Chunking strategy is immutable after KB creation** — changing it means recreating/re-syncing ([retrieval-quality engineering writeup](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)). Semantic chunking hard-fails on bodies >1,000,000 chars (re:Post logs below). |
| **Embedding/Indexing** | Bring-your-own vector store: OpenSearch Serverless (quick-create default), OpenSearch Managed, **S3 Vectors** (cheap, sub-second, 1 KB/35-key metadata cap), Aurora pgvector, Neptune Analytics (GraphRAG), Pinecone, Redis, MongoDB Atlas ([setup docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)). Titan/Cohere embeddings. | Feature support is a per-store matrix: binary vectors only on OpenSearch; hybrid only on OSS/Aurora/Mongo; Mongo metadata filtering "doesn't work by default"; Aurora needs hand-built GIN indexes and `hnsw.iterative_scan` tuning; OpenSearch custom filter fields need `keyword` subfields or queries fail with a "Rewrite first" error — all straight from AWS's own docs. |
| **Query handling** | `Retrieve` (chunks only) and `RetrieveAndGenerate` (managed prompt+synthesis+citations). Query reformulation/decomposition exists but **only** in `RetrieveAndGenerate`. | Semantic-only search is the default; `HYBRID` must be requested and **silently falls back to semantic** on unsupported stores ([hidekazu-konishi](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)). |
| **Rerank** | Amazon Rerank 1.0 and Cohere Rerank 3.5 as separate Bedrock models wired into KB queries. | Patchy region coverage (Amazon Rerank absent from us-east-1 for a long stretch); requires separate model-access grants. |
| **Synthesis** | `RetrieveAndGenerate` orchestrates FM + citations; or DIY with `Retrieve` + your own prompt. | Session-based; citation payloads (`retrievedReferences`) can arrive empty even when generation clearly used sources ([SO 78433567](https://stackoverflow.com/questions/78433567/why-is-retrieveandgenerate-api-response-is-giving-empty-list-for-retrievedrefere)). |
| **GraphRAG** | Neptune Analytics graph auto-built at ingest (entity/relationship extraction via a chosen FM), vector search then graph traversal expansion. | Limits: S3-only source, 1,000 files/data source default, no graph-build customization, no autoscaling, hierarchical chunking returns only child chunks, graph must be deleted separately or it keeps billing ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html)). |
| **Structured data** | KB type that NL→SQLs against Redshift (and Glue/S3 tables via Redshift); standalone `GenerateQuery` API ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-structured.html)). | Redshift-centric; no direct Aurora/RDS OLTP targets — most teams' operational DBs need an ETL hop first (architectural-inference). |

The June-2026 **Managed KB** collapses this matrix: AWS-owned storage that auto-scales,
"Smart Parsing" that picks a parsing strategy per document type (PDF/PPTX/audio/video/scans),
consumption pricing (per GB indexed + per retrieval), ACL propagation from SaaS connectors, and an
**agentic retriever** doing query decomposition and multi-hop retrieval across KBs
([announcement](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-managed-knowledge-base-for-faster-more-accurate-enterprise-ai-applications/)).

### Google retrieval stack

- **Vertex AI Search / Agent Search** — black-box pipeline: managed ETL + OCR + parsing +
  "intelligent chunking" + embeddings + hybrid retrieval + Google ranking + optional generative
  answers, exposed as data stores + engines over the Discovery Engine API. Component APIs
  (ranking API, grounded-generation API, check-grounding API) are separately billable à la carte.
  Customization of core retrieval/embedding internals is explicitly not offered
  ([GCP RAG Spectrum](https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a)).
- **Vertex AI RAG Engine** — 6-stage managed pipeline (ingestion from local/GCS/Drive →
  transformation/chunking (`chunk_size`/`chunk_overlap`) → embedding → corpus indexing → retrieval →
  generation), pluggable vector DBs incl. Pinecone/Weaviate, defaults to `RagManagedDb`
  ([docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview)).
  The "corpus" abstraction couples you to GCP even with a third-party store.
- **Vertex AI Vector Search** — provisioned ANN (ScaNN). Index build/deploy latency is tens of
  minutes to ~an hour ([SO 77474624](https://stackoverflow.com/questions/77474624/why-is-the-creation-of-an-vertex-ai-vector-search-index-formally-known-as-match));
  always-on index endpoints bill regardless of query volume.
- **Gemini File Search** — "FileSearchStore" containers; upload → auto chunk (whitespace chunker;
  overridable `max_tokens_per_chunk`/`max_overlap_tokens`) → gemini-embedding-001/-2 → managed index;
  at generation time the tool injects retrieved chunks and returns grounding-metadata citations
  (page numbers for PDFs). Pricing: $0.15/M tokens at indexing only; storage and query-time
  embeddings free; tiered store caps (1 GB free → 1 TB tier 3; ≤20 GB/store recommended for
  latency); 10 stores/project; 100 MB/file; documents immutable once indexed (delete + re-upload to
  update); cannot be combined with Google Search/URL-context tools in one request
  ([docs](https://ai.google.dev/gemini-api/docs/file-search), [Schmid tutorial](https://www.philschmid.de/gemini-file-search-javascript)).
- **Grounding with Google Search** — retrieval outsourced to Google's web index; no corpus control;
  $35/1k grounded requests beyond the free daily allotment.

---

## Agentic integration

- **AWS:** The original KB was a *static tool* — agents (Bedrock Agents, LangChain, etc.) call
  `Retrieve` per turn; no loop, no memory, decomposition locked inside `RetrieveAndGenerate`.
  The 2026 Managed KB is explicitly agent-shaped: **agentic retrieval** (decompose → iterative
  multi-KB retrieval → sufficiency check) and first-class **MCP exposure through AgentCore
  Gateway** so "any MCP-compatible agent framework can discover and invoke your Knowledge Base as a
  tool without custom code", plus retrieval/agentic traces in AgentCore Observability
  ([docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)). Memory remains
  a separate AgentCore primitive, not part of KB.
- **Google:** ADK/Agent Builder treat Vertex AI Search and RAG Engine as retrieval tools; File
  Search is a native Gemini tool call. But File Search's mutual exclusion with other grounding
  tools breaks the common agent pattern "check my docs, else search the web" in a single call
  ([docs](https://ai.google.dev/gemini-api/docs/file-search)), and none of the Google offerings give
  the agent control over retrieval internals (k, ranker, candidate inspection) beyond coarse config
  — the agent can't adaptively re-retrieve with different parameters (architectural-inference).

---

## Strengths (steelman)

1. **Zero-to-RAG speed with enterprise plumbing.** IAM/KMS/VPC/PrivateLink (AWS), VPC-SC/CMEK
   (Google) come for free; nothing in OSS frameworks matches Managed KB's ACL propagation from
   SharePoint/Confluence/Drive at retrieval time, or Vertex AI Search's managed OCR→ranking chain.
2. **Genuinely advanced stages available managed:** FM-based PDF/table parsing, semantic +
   hierarchical chunking, custom Lambda transforms, hybrid+rerank, GraphRAG over Neptune, text-to-SQL
   — all as configuration, not code (AWS docs above). Google's ranking stack really does inherit
   Google search-quality signals that OSS rerankers approximate.
3. **Gemini File Search's pricing model is the most developer-friendly in the industry** — free
   storage and free query-time embeddings, pay once at indexing ($0.15/M tokens), with page-level
   citations built in ([Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/file-search-gemini-api/)).
   It collapses the RAG stack into one API call.
4. **Both vendors are correcting known failure modes in-place:** S3 Vectors and Aurora pgvector
   address the OpenSearch cost floor; Managed KB addresses config sprawl, freshness, agents, ACLs;
   RAG Engine's pluggable stores address lock-in fears. The platforms iterate fast because the
   failure modes below became public and loud.
5. **Operational surface**: retrieval traces (AgentCore Observability), per-KB metrics, citation
   payloads and check-grounding APIs give more built-in attribution than most DIY stacks ship with.

---

## Issues & failure modes

### performance-cost

- **"Serverless" RAG with a ~$200–$700/month idle floor.** Bedrock KB's quick-create path
  provisions OpenSearch Serverless, whose OCU minimums bill continuously: ~$350/mo idle for a
  prod-redundant collection, ~$700/mo floors reported in eu-west-1, ~$200/mo dev configs; a user
  embedding <2 GB of PDFs with ~10 queries "already racked up" charges from indexing+search OCU
  hours alone. Evidence: [ercan.ai migration writeup](https://ercan.ai/cutting-amazon-bedrock-knowledge-base-costs-by-90-migrating-from-opensearch-serverless-to-aurora-serverless-v2-with-pgvector/)
  (~90% cost cut moving to Aurora pgvector), ["Why AWS Bedrock RAG's Serverless Model Isn't Truly
  Pay-Per-Use"](https://maruai.medium.com/why-aws-bedrock-rags-serverless-model-isn-t-truly-pay-per-us-e738ac10ebdb),
  [HN comment](https://news.ycombinator.com/item?id=41513425) ("costs at minimum $200ish/month bc
  it doesn't scale to zero"), [re:Post: unpredictable Search OCU allocation that doesn't correlate
  with activity](https://repost.aws/questions/QUVPl-znFxTuWTzU5ryqM0pQ/bedrock-opensearch-serverless-collection-unpredictable-search-ocu-costs).
  **Severity: critical (for small/medium workloads). Label: documented-recurring.**
- **Vertex pricing sprawl and compounding add-ons.** Vertex AI Search bills per query per edition
  ($1.50/1k Standard, $4/1k Enterprise) **plus** +$4/1k for Advanced Generative Answers, +$5/GiB/mo
  index storage past 10 GiB, $2.50/1k grounded-generation, $35/1k Google-Search grounding, $20/1k
  healthcare queries, and a *parallel* subscription model (QPM + storage-hour SKUs + $0.75/1k
  semantic add-on + $1.50/GB/mo embeddings) whose data stores are incompatible across pricing
  models. One product, two metering systems, ≥8 SKUs. Evidence: [official pricing page](https://cloud.google.com/generative-ai-app-builder/pricing).
  **Severity: major. Label: documented-recurring (the page itself; cost-estimation complaints echo it).**
- **Vertex AI Vector Search always-on endpoints** make sporadic workloads uneconomical and index
  deploys take up to ~1 hour, hurting iteration. Evidence: [SO 77474624](https://stackoverflow.com/questions/77474624/why-is-the-creation-of-an-vertex-ai-vector-search-index-formally-known-as-match),
  [GCP RAG Spectrum](https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a).
  **Severity: major. Label: documented-recurring.**

### production-ops

- **Orphaned-resource billing traps.** Deleting a Bedrock KB does **not** delete the OpenSearch
  Serverless collection (keeps billing ~$350/mo) nor the Neptune Analytics graph ("Additional
  charges may be incurred until you explicitly delete the graph" — [AWS's own GraphRAG docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html)).
  Evidence: [ercan.ai](https://ercan.ai/cutting-amazon-bedrock-knowledge-base-costs-by-90-migrating-from-opensearch-serverless-to-aurora-serverless-v2-with-pgvector/) + AWS docs.
  **Severity: major. Label: documented-recurring.**
- **Sync/freshness pain: slow, stuck, unstoppable ingestion jobs.** A 183-file KB (Nova-parser +
  semantic chunking) took >30 min per sync for one new file, with a hard error
  "File body text exceeds size limit of 1000000 for semantic chunking"
  ([re:Post QUZVrf](https://repost.aws/questions/QUZVrfUcufT36bCyRNVcEwww/amazon-bedrock-knowledgebase-sync-takes-more-than-30min-without-finishing-even-for-1-new-file));
  other threads report syncs stuck >24h with delete-the-KB as the workaround
  ([re:Post QU6yx6](https://repost.aws/questions/QU6yx6fXqaQOeHUr5oT1DsFA/bedrock-knowledge-base-sync-stuck)),
  sync failures ([SO 78912309](https://stackoverflow.com/questions/78912309/aws-bedrock-rag-unable-to-sync-data-source-in-a-knowledge-base)),
  and **no API to stop a running sync job**
  ([SO 78773082](https://stackoverflow.com/questions/78773082/unable-to-stop-running-sync-job-in-aws-bedrock-knowledge-base)).
  Direct-ingest is capped at 10 concurrent requests/account. Batch-sync as the freshness model is
  fundamentally at odds with near-real-time knowledge. **Severity: critical. Label: documented-recurring.**
- **Quota/limit walls at modest scale:** ~50 MB/file, per-sync-job file caps (1,000 files for
  FM-parsing/BDA paths), GraphRAG 1,000 files/data source (10k max by request), S3 Vectors 1 KB /
  35-key metadata per vector — hierarchical chunking can blow the metadata cap and abort ingestion
  ([setup docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html),
  [GraphRAG docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html)).
  **Severity: major. Label: documented-recurring (in docs).**

### data-processing

- **Chunking is a one-way door.** Bedrock KB chunking strategy cannot be changed after creation;
  experimentation means new KB + full re-ingest + re-embed (paid again). Evidence:
  [retrieval-quality engineering analysis](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html);
  AWS docs. Gemini File Search has the mirror problem: **documents are immutable once indexed** —
  updates are delete-and-reupload, and chunking config only applies at upload
  ([Schmid](https://www.philschmid.de/gemini-file-search-javascript)). **Severity: major.
  Label: documented-recurring.**
- **Naive default chunking + parsing quality cliffs.** Bedrock defaults to ~300-token fixed chunks
  that "can split a table, a list, or a tightly-coupled argument down the middle"; good parsing
  (FM/BDA) costs tokens and slows syncs; CSV/tabular sources retrieve poorly out of the box
  ([SO 79591405](https://stackoverflow.com/questions/79591405/how-to-get-correct-answers-from-a-csv-knowledge-base-in-aws-bedrock),
  [hidekazu-konishi](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)).
  **Severity: major. Label: documented-recurring.**
- **Metadata must be designed up front** (sidecar `*.metadata.json` at ingestion; filters can't be
  added retroactively without re-ingest), and operator support (`startsWith`, `stringContains`)
  varies by store ([hidekazu-konishi](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)).
  **Severity: minor. Label: documented-recurring.**

### retrieval-quality

- **Semantic-only defaults and silent hybrid fallback.** Bedrock defaults to vector-only search;
  requesting `HYBRID` on a store that doesn't support it **silently degrades to semantic-only**
  rather than erroring — retrieval quality bugs that never surface as failures
  ([hidekazu-konishi](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)).
  Reranking needs separate model-access grants and had gap regions (Amazon Rerank absent from
  us-east-1). **Severity: major. Label: documented-recurring.**
- **Kendra, the cautionary predecessor:** "Point it at an S3 bucket… and you're done" was the same
  pitch in 2019; a practitioner: *"Amazon Kendra is one of the worst products I've ever used, and we
  ripped it out as quickly as possible. AWS has a long history of over promising and under
  delivering when it comes to anything AI / ML"*
  ([HN](https://news.ycombinator.com/item?id=35555359)); launch pricing ~$1,800/mo for 10k docs
  ([HN](https://news.ycombinator.com/item?id=21695643)). Out-of-box relevance claims by managed
  vendors deserve skepticism by default. **Severity: context/major. Label: documented-recurring.**
- **Google's "Google-quality search" claim is unfalsifiable from outside**: core retrieval
  algorithms, chunkers and embedddings in Vertex AI Search are not adjustable or inspectable, so
  when relevance is bad there is no tuning path except add-on rankers or leaving the product
  ([GCP RAG Spectrum](https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a)).
  **Severity: major. Label: architectural-inference (limits documented; quality variance anecdotal).**

### abstraction-design

- **Customer-managed Bedrock KB leaks its abstraction badly.** AWS's own setup docs require users
  to know: faiss-vs-nmslib engine choice, `keyword` subfields (else filter queries fail with a
  bare **"Rewrite first"** error), GIN indexes on jsonb, `hnsw.iterative_scan = 'relaxed_order'`
  tuning (else selective metadata filters silently return too few results), per-store binary-vector
  and hybrid support matrices, and MongoDB metadata filtering that "doesn't work by default"
  ([setup docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)).
  This is a managed service delegating its hardest correctness problems to the user.
  **Severity: major. Label: documented-recurring (vendor docs + re:Post traffic).**
- **Two-tier product bifurcation (2026)** — Managed KB gets connectors, ACLs, agentic retrieval,
  MCP; customer-managed KBs don't, so control and capability are now traded against each other
  inside one product name ([KB docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)).
  **Severity: minor. Label: documented (docs).**

### evaluation-observability

- **Debugging opacity in the black-box tiers.** `RetrieveAndGenerate` returning **empty
  `retrievedReferences`** while still generating source-mapped answers
  ([SO 78433567](https://stackoverflow.com/questions/78433567/why-is-retrieveandgenerate-api-response-is-giving-empty-list-for-retrievedrefere));
  Gemini File Search is "completely headless… no console to view your files… you are often flying
  blind. You create a 'Store,' upload a file, and hope it processed correctly" — no way to inspect
  chunks or test retrieval without throwaway scripts, which is why a third party built the missing
  UI ([dev.to](https://dev.to/prashant_rohilla_60997096/i-built-the-missing-ui-for-geminis-file-search-managed-rag-api-ge7)).
  Neither platform ships an evaluation loop (golden-set retrieval metrics, regression testing) as a
  first-class feature; AWS's new retrieval traces (AgentCore Observability) are Managed-KB-only.
  **Severity: major. Label: documented-recurring.**

### agentic-integration

- **Static pipeline heritage.** Until June 2026, Bedrock KB offered one-shot retrieval only;
  decomposition was locked inside `RetrieveAndGenerate` and unavailable to agents using `Retrieve`
  ([hidekazu-konishi](https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html)).
  Gemini File Search **cannot be combined with Google Search or URL-context tools in the same
  request** and doesn't work with the Live API — blocking the canonical agent pattern of
  private-docs-plus-web fallback in one call ([docs](https://ai.google.dev/gemini-api/docs/file-search)).
  **Severity: major. Label: documented-recurring (docs) + architectural-inference (agent-loop fit).**

### security-governance

- **ACL-aware retrieval arrived late and unevenly.** Document-level permission filtering exists
  only in the 2026 Managed KB (and excludes the Web Crawler connector); customer-managed KBs must
  hand-roll multi-tenancy via metadata filters — the same filters with per-store gaps and silent
  fallbacks above ([KB docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)).
  Gemini File Search has no per-user ACL story at all (stores are project-scoped; tenancy =
  metadata filters or store-per-tenant against a 10-store cap). **Severity: major.
  Label: documented (docs) / architectural-inference.**

### dx-docs

- **Naming/branding churn as a real integration cost (Google).** Gen App Builder → Search &
  Conversation → Agent Builder → AI Applications → Agent Search/Gemini Enterprise in ~3 years;
  RAG Engine launched as "LlamaIndex on Vertex AI"; the underlying API remains `discoveryengine`.
  Docs, SDK namespaces and StackOverflow answers rot fast
  (e.g. [404s creating "enterprise search" data stores via REST](https://stackoverflow.com/questions/77156462/gettting-404-method-not-found-when-using-rest-api-to-create-enterprise-search-da),
  [permission confusion at data-store creation](https://stackoverflow.com/questions/77564180/when-attempting-to-create-a-data-store-for-gcps-search-conversaion-storage)).
  Forced migration of Programmable Search users (50-domain cap, "contact us" for full-web) pushed
  more churn toward Vertex AI Search ([HN](https://news.ycombinator.com/item?id=46730436)).
  **Severity: major. Label: documented-recurring.**
- **AWS-side setup friction**: opaque `Access denied when calling Bedrock` errors around model
  access/IAM are the highest-voted Bedrock questions on StackOverflow
  ([SO 77674389](https://stackoverflow.com/questions/77674389/amazon-bedrock-agent-access-denied-when-calling-bedrock-check-your-request-pe)).
  **Severity: minor. Label: documented-recurring.**

---

## Community sentiment over time

- **2019–2022 (Kendra era):** enthusiasm at "managed intelligent search", quickly soured by price
  floor ($1,800/mo) and relevance disappointment; "ripped it out as quickly as possible"
  ([HN 2023](https://news.ycombinator.com/item?id=35555359), [HN 2019](https://news.ycombinator.com/item?id=21695643)).
- **2023–2024 (Bedrock KB v1):** positive "RAG in an afternoon" first-looks; then a steady drumbeat
  of OpenSearch Serverless bill shock and sync complaints on re:Post/Reddit/Medium; community
  playbook converges on "swap in Aurora pgvector or S3 Vectors, use hierarchical chunking + hybrid +
  rerank, never trust defaults" ([ercan.ai](https://ercan.ai/cutting-amazon-bedrock-knowledge-base-costs-by-90-migrating-from-opensearch-serverless-to-aurora-serverless-v2-with-pgvector/),
  [maruai](https://maruai.medium.com/why-aws-bedrock-rags-serverless-model-isn-t-truly-pay-per-us-e738ac10ebdb),
  [Terraform advanced-RAG guide, 2026](https://dev.to/suhas_mallesh/bedrock-knowledge-base-advanced-rag-with-terraform-chunking-hybrid-search-and-reranking-4m3d) —
  which opens by conceding basic KBs give "mediocre retrieval quality").
- **2024–2025 (Google):** respect for Vertex AI Search capability, persistent grumbling about
  naming churn, pricing opacity and lack of tuning control; RAG Engine seen as the pragmatic
  middle but "less opinionated… requires more configuration decisions"
  ([GCP RAG Spectrum](https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a)).
- **Nov 2025–2026 (File Search):** genuine excitement ("the end of DIY RAG" takes; front-page HN),
  tempered by headless-API/observability complaints ([dev.to](https://dev.to/prashant_rohilla_60997096/i-built-the-missing-ui-for-geminis-file-search-managed-rag-api-ge7))
  and — in the HN multimodal thread — a broader Google-product-execution skepticism dominating the
  discussion ([HN 48080702](https://news.ycombinator.com/item?id=48080702)).
- **Mid-2026:** AWS's Managed KB launch reads as a direct response to every recurring complaint
  above (cost floor, config sprawl, freshness, ACLs, agents) — the vendor's own roadmap is the best
  confirmation of the failure modes.

## Benchmarks & third-party evaluations

Independent, rigorous public benchmarks of these managed pipelines are notably **scarce** — a
finding in itself:
- No peer-reviewed end-to-end benchmark of Bedrock KB or Vertex AI Search retrieval quality was
  found in this pass; vendors publish claims ("Google-quality", "faster, more accurate") without
  reproducible eval suites; the [build-google-quality-rag codelab](https://codelabs.developers.google.com/build-google-quality-rag)
  is a demo, not an eval.
- Practitioner quasi-evals exist: the Terraform advanced-RAG guide documents default-config
  Bedrock KBs missing relevant chunks on complex queries ([dev.to](https://dev.to/suhas_mallesh/bedrock-knowledge-base-advanced-rag-with-terraform-chunking-hybrid-search-and-reranking-4m3d));
  hands-on File Search walkthroughs ([DataCamp](https://www.datacamp.com/tutorial/google-file-search-tool),
  [Schmid](https://www.philschmid.de/gemini-file-search-javascript)) verify citation behavior and
  latency qualitatively only.
- Because chunking/embedding/ranking internals are closed (Vertex AI Search, File Search) or
  immutable post-creation (Bedrock), **apples-to-apples benchmarking is structurally hard** —
  managed RAG resists the eval discipline the field now expects (architectural-inference).

## Lessons for a next-generation framework

1. **True scale-to-zero retrieval or don't call it serverless.** The OpenSearch OCU floor did more
   brand damage to Bedrock KB than any relevance issue; S3-Vectors-style storage/compute separation
   should be the default, with the index a cache, not a billing anchor.
2. **Chunking/embedding must be re-configurable in place.** One-way doors (Bedrock immutable
   strategies, File Search immutable documents) make the single highest-leverage RAG knob
   untunable. Store canonical parsed documents; treat chunk/embed as re-runnable derived views.
3. **Never degrade silently.** Hybrid falling back to semantic-only, filters returning partial
   results after HNSW scans, empty citation arrays — silent degradation converts config gaps into
   invisible quality bugs. Fail loudly or surface capability matrices at plan time.
4. **Freshness is a streaming problem.** Batch "sync jobs" that can take 30+ minutes for one file,
   can't be cancelled, and get stuck are unacceptable; ingestion should be incremental,
   observable per-document, and interruptible.
5. **Observability is part of the retrieval contract**: chunk inspection, retrieval traces, and a
   built-in eval loop (golden queries, regression deltas on re-chunk/re-embed) — the absence of
   these is why third parties build "the missing UI".
6. **Lifecycle symmetry:** creating a KB creates resources; deleting it must delete (or at least
   loudly enumerate) them. Orphaned $350/mo collections and Neptune graphs are governance bugs.
7. **Design for the agent loop, not the pipeline**: retrieval as a composable MCP-style tool with
   agent-controllable parameters (k, filters, ranker, decomposition), combinable with other tools
   in one call — both vendors converged here (AgentCore MCP; File-Search-as-tool) but with
   restrictions that a new framework should not inherit.
8. **ACLs are table stakes**, not a premium-tier feature: permission-aware retrieval must work for
   any store, propagated from source systems.
9. **Pricing must be estimable in one sitting.** Vertex's editions × add-ons × two metering models
   is a warning: complexity in pricing reflects (and hides) complexity in architecture.

## Sources

- AWS Bedrock KB user guide (incl. Managed KB pitch): https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
- Managed KB announcement (June 2026): https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-managed-knowledge-base-for-faster-more-accurate-enterprise-ai-applications/
- Custom transform Lambda: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-custom-transformation.html
- Advanced RAG capabilities (July 2024): https://aws.amazon.com/about-aws/whats-new/2024/07/knowledge-bases-amazon-bedrock-advanced-rag-capabilities
- Vector-store setup (per-store foot-guns): https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html
- GraphRAG with Neptune (limits, orphaned-graph billing): https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs.html
- Structured-data KB / GenerateQuery: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-structured.html
- Retrieval-quality engineering deep dive: https://hidekazu-konishi.com/entry/amazon_bedrock_knowledge_bases_retrieval_quality_engineering.html
- OpenSearch Serverless cost floor & migration: https://ercan.ai/cutting-amazon-bedrock-knowledge-base-costs-by-90-migrating-from-opensearch-serverless-to-aurora-serverless-v2-with-pgvector/
- "Not truly pay-per-use": https://maruai.medium.com/why-aws-bedrock-rags-serverless-model-isn-t-truly-pay-per-us-e738ac10ebdb
- re:Post — unpredictable Search OCUs: https://repost.aws/questions/QUVPl-znFxTuWTzU5ryqM0pQ/bedrock-opensearch-serverless-collection-unpredictable-search-ocu-costs
- re:Post — 30-min sync for one file / semantic-chunking size error: https://repost.aws/questions/QUZVrfUcufT36bCyRNVcEwww/amazon-bedrock-knowledgebase-sync-takes-more-than-30min-without-finishing-even-for-1-new-file
- re:Post — sync stuck: https://repost.aws/questions/QU6yx6fXqaQOeHUr5oT1DsFA/bedrock-knowledge-base-sync-stuck
- SO — empty retrievedReferences: https://stackoverflow.com/questions/78433567/
- SO — can't stop sync job: https://stackoverflow.com/questions/78773082/
- SO — sync failures: https://stackoverflow.com/questions/78912309/
- SO — CSV KB quality: https://stackoverflow.com/questions/79591405/
- SO — Bedrock access-denied friction: https://stackoverflow.com/questions/77674389/
- HN — Kendra critique: https://news.ycombinator.com/item?id=35555359 ; Kendra launch pricing: https://news.ycombinator.com/item?id=21695643
- HN — OpenSearch min cost: https://news.ycombinator.com/item?id=41513425
- Bedrock advanced-RAG-with-Terraform (default quality concession): https://dev.to/suhas_mallesh/bedrock-knowledge-base-advanced-rag-with-terraform-chunking-hybrid-search-and-reranking-4m3d
- Vertex AI RAG Engine overview: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview
- GCP RAG Spectrum (tradeoffs): https://medium.com/google-cloud/the-gcp-rag-spectrum-vertex-ai-search-rag-engine-and-vector-search-which-one-should-you-use-f56d50720d5a
- Vertex AI Search / grounding pricing: https://cloud.google.com/generative-ai-app-builder/pricing
- SO — Vector Search index creation slow: https://stackoverflow.com/questions/77474624/
- SO — Discovery Engine API churn: https://stackoverflow.com/questions/77156462/ ; https://stackoverflow.com/questions/77564180/
- Gemini File Search docs: https://ai.google.dev/gemini-api/docs/file-search
- File Search launch: https://blog.google/innovation-and-ai/technology/developers-tools/file-search-gemini-api/
- File Search tutorial (limits, immutability): https://www.philschmid.de/gemini-file-search-javascript
- File Search "missing UI" critique: https://dev.to/prashant_rohilla_60997096/i-built-the-missing-ui-for-geminis-file-search-managed-rag-api-ge7
- HN — File Search multimodal thread: https://news.ycombinator.com/item?id=48080702
- HN — Programmable Search wind-down pushing users to Vertex AI Search: https://news.ycombinator.com/item?id=46730436
- DataCamp File Search tutorial: https://www.datacamp.com/tutorial/google-file-search-tool
