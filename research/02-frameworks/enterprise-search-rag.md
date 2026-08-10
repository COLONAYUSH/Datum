# Enterprise Search Incumbents as RAG Platforms: Glean, Amazon Q Business, Elastic/OpenSearch (+ Coveo, Sinequa, Lucidworks)

Autopsy date: 2026-08-05. Method: primary docs (Glean developer docs, AWS docs, Elastic docs/search-labs, OpenSearch repos/forums), GitHub issue mining via `gh`, HN Algolia API, Discourse forum search JSON, vendor press pages. Web-search budget was exhausted by the pipeline, so all evidence below comes from directly fetched primary pages and APIs; each claim carries its source. Vendor-published claims and vendor-adjacent critiques are labeled as such.

Core research question addressed throughout: **what does permission-aware retrieval (per-user ACL trimming at query time, connector permission mirroring, freshness) actually cost in complexity, latency, and money?**

---

## Identity & adoption

### Glean
- Founded January 2019 (Arvind Jain — ex-Google Distinguished Engineer, Rubrik co-founder; plus ex-Google/Meta/Microsoft founders). Palo Alto. Closed-source SaaS. ([glean.com/press](https://www.glean.com/press))
- **$7.2B valuation; surpassed $300M ARR (May 2026), up from $200M ARR (Dec 2025) — "tripled revenue in 15 months."** Investors: Sequoia, Kleiner Perkins, Lightspeed, General Catalyst, ICONIQ, SoftBank Vision Fund 2, DST, Coatue, Altimeter, IVP, Sapphire, Craft. ([glean.com/press](https://www.glean.com/press))
- Claims **"275+ out-of-the-box connectors"** in four flavors: Native, MCP, Push API, Web history. ([glean.com/connectors](https://www.glean.com/connectors))
- Pricing is not public. Vendr marketplace data (third-party, medium credibility): **median buyer pays ~$98,890/year** across 174 observed purchases; contracts observed $29,880–$208,897; **minimum commitments typically ~100–250 users**. ([vendr.com/marketplace/glean](https://www.vendr.com/marketplace/glean))
- The de-facto reference architecture for permission-aware enterprise RAG; Gartner "Market Shaper" in the 2026 Emerging Market Quadrant for No-Code Agent Builders; AWS Agentic AI Specialization (Dec 2025). ([glean.com/press](https://www.glean.com/press))

### Amazon Q Business
- AWS's managed enterprise RAG assistant (GA April 2024), built on Bedrock, retrieval lineage from Amazon Kendra. Pricing: **Lite $3/user/mo, Pro $20/user/mo**, plus index capacity: Starter index $0.140/hr/unit, Enterprise index $0.264/hr/unit; each unit = **20,000 documents or 200 MB extracted text** + 100 connector-hours/month. ([aws.amazon.com/q/business/pricing](https://aws.amazon.com/q/business/pricing/))
- **As of 2026, "Amazon Q Business is no longer open to new customers." AWS provides only bug fixes/security updates; "new feature requests will no longer be considered."** Customers are told to migrate to "Amazon Quick." ([AWS docs: availability change](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html))
- This makes Q Business a completed natural experiment: a hyperscaler's ~2-year attempt at turnkey permission-aware RAG that was folded into a BI-adjacent product.

### Elastic (Elasticsearch) native RAG
- Public company (NYSE: ESTC), Elasticsearch under AGPL/ELv2/SSPL triple license since 8.16. The incumbent lexical engine that added: **ELSER** (learned sparse retrieval), **semantic_text** field, **retrievers API** (8.16+), **Elastic Rerank** cross-encoder (tech preview), **BBQ** binary quantization (8.16, Nov 2024), **Playground** RAG UI (deprecated 9.4 → Agent Builder).
- **Deprecated its own turnkey enterprise-search products**: "we're deprecating the Enterprise Search product line (including App Search and Workplace Search) in version 9.0" — maintained until Jan 15, 2027, supported until July 15, 2027. New customers get raw Elasticsearch + connectors. ([Enterprise Search FAQ](https://www.elastic.co/resources/search/enterprise-search-faq))

### OpenSearch
- Linux Foundation project (Apache-2.0), AWS-originated Elasticsearch fork. Neural search plugin (dense + neural-sparse), hybrid query with normalization/score-combination search pipelines, Seismic sparse-ANN work in 2025–26 ([RFC #1335](https://github.com/opensearch-project/neural-search/issues/1335)).

### Brief: Coveo, Sinequa, Lucidworks
- **Coveo**: public (TSX: CVO; raised US$172M at $1B+ valuation pre-IPO, 2019 — [TechCrunch](https://techcrunch.com/2019/11/06/coveo-raises-227m-at-1b-valuation-for-ai-based-enterprise-search-and-personalization/)). Pivoted its relevance platform into "Relevance Generative Answering" (RAG on top of its permission-filtered index), strongest in commerce/service, not general workplace search.
- **Sinequa**: French enterprise-search veteran, now absorbed into **ChapsVision** — 2025 releases branded "Sinequa," 2026 releases branded "ChapsVision"; product now marketed as "Advanced RAG" + "Agentic AI Orchestration" ([sinequa.com/company/press](https://www.sinequa.com/company/press/)). Loss of independent identity for a 20-year search specialist.
- **Lucidworks** (Solr/Fusion lineage): repositioned Fusion toward AI/RAG use cases; no significant independent momentum signals surfaced in 2025–26 sources fetched here (weak signal, noted as such).

Adoption signal summary: independent permission-aware RAG (Glean) is growing explosively; hyperscaler turnkey RAG (Q Business) failed; infrastructure incumbents (Elastic/OpenSearch) retreated from the application layer to sell RAG primitives; legacy specialists consolidated (Sinequa) or pivoted (Coveo, Lucidworks).

---

## Retrieval-pipeline architecture

### Glean (reference architecture for permission-aware RAG)
Pipeline, per Glean's own engineering posts ([indexing/context post](https://www.glean.com/blog/enterprise-ai-indexing-context), [context graph post](https://www.glean.com/blog/how-do-you-build-a-context-graph)):
1. **Connectors (275+)** crawl/push content; "source permissions are mirrored, and updates, permission changes, and deletions are reflected as the underlying systems change."
2. **Specialized indexes** — "specialized indexes for company data, code, experts, profiles, tools, and calendars," combining "semantic, lexical, and structured retrieval suited to different kinds of information." Semantic and lexical indexes are **trained on the customer's corpus** ("learning acronyms, product names, team names, industry terms").
3. **Knowledge graph** — ML pipeline "to infer higher-level entities like projects, customers, products, teams, and people," relationship mapping across systems, entity disambiguation via activity signals (views/edits/comments).
4. **Learned ranking** — "authorship, views, edits, comments, freshness, and relationships" as ranking features, with per-user ACL trimming applied so "every result is both relevant and properly secured."
5. **Generation layer** (Glean Assistant/Agents) consumes the ranked, permission-trimmed context.

What permission mirroring actually takes (from [Glean's Indexing API docs](https://developers.glean.com/)): a datasource author must (a) index all users first (`/indexuser`, `/bulkindexusers`), (b) pick an identity keying scheme (`isUserReferencedByEmail` vs `datasourceUserId`), (c) index groups and memberships (`/indexgroup`, `/indexmembership`, nested groups supported), (d) attach a `permissions` object per document (`allowedUsers`, `allowedGroups`, `allowAnonymousAccess`, `allowAllDatasourceUsersAccess`), and (e) debug with `/checkdocumentaccess`. The docs warn: **"permissions and memberships are processed asynchronously, there might be a small delay"** before enforcement matches source-of-truth. That is the honest fine print behind the marketing claim that permissions are "reflected immediately in results."

### Amazon Q Business
- **Managed index tiers** (Starter = 1 AZ, Enterprise = 3 AZ) storing extracted text; retrieval via native retriever or an existing Kendra index; generation via Bedrock models with citation and "hallucination mitigation" post-checks. ([What is Q Business](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/what-is.html))
- **Connectors index document ACLs alongside content** (user email, local group, federated group), stored in a central **User Store**; an **identity crawler** maps local users/groups to federated identities "to filter chat responses based on the end user's access to documents," explicitly to "speed up chat responses by reducing ACL information retrieval time during chat requests" — i.e., AWS concedes query-time ACL resolution is a latency problem you must pre-compute around. ([connector concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html))
- **ACL freshness is sync-bound**: "An Amazon Q Business connector updates any changes in ACLs each time that your data source content is crawled. To capture ACL changes ... re-sync your data source regularly." Sync schedules bottom out at hourly.
- A **Document deletion safeguard** (max-deletion-percentage circuit breaker) exists specifically to prevent "accidental excessive deletion ... due to issues such as crawler failures and temporary data source unavailability" — a tell that connector-driven index wipes were a real failure mode.
- Kendra, the retrieval substrate lineage: Basic Enterprise **$1,008/month base** (100k docs, 0.1 QPS included), Developer $810/month, newer GenAI index $230.40/month for 20k docs; connector sync billed separately. ([Kendra pricing](https://aws.amazon.com/kendra/pricing/))

### Elastic native RAG
- **ELSER** (sparse learned retrieval): needs a **≥4 GB dedicated ML node**; "ELSER encodes the first 512 tokens of a field"; **English-only** (E5 recommended otherwise). ([ELSER docs](https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser))
- **semantic_text** field: inference at ingest with "sensible defaults"; docs warn "the default endpoint can change across versions and deployment types, which can lead to indices with mixed embedding models and cause ranking issues in multi-index searches," and connector/crawler indices need **full re-syncs** to re-embed. ([semantic_text docs](https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text))
- **Retrievers API** (8.16+): composable retriever tree in one `_search` call — standard, knn, rrf, linear, rule, rescorer, text_similarity_reranker, diversify (MMR, preview); replaced the deprecated `sub_searches`. ([retrievers overview](https://www.elastic.co/docs/solutions/search/retrievers-overview))
- **BBQ**: ~95% vector-memory reduction (example: 535 GB float32 → ~19 GB), >90% recall with 3x oversampling on CohereV3, "20–30x less quantization time [than PQ]" — genuinely strong engineering. ([search-labs BBQ post](https://www.elastic.co/search-labs/blog/better-binary-quantization-lucene-elasticsearch))
- **Document-level security** is per-connector DLS (ACL sync into control indices + query-time filters) — available for some connectors only (~25 GA connectors overall, several key ones still Preview/Beta: Slack, Teams, Zoom, Box). ([connectors reference](https://www.elastic.co/docs/reference/search-connectors/))
- **Playground** (RAG prototyping UI): "deprecated as of version 9.4," users pointed to Agent Builder. ([Playground docs](https://www.elastic.co/docs/solutions/search/rag/playground))

### OpenSearch neural/hybrid
- Dense neural search + neural-sparse; **hybrid query** executes lexical and vector sub-queries and fuses them in a search-pipeline **normalization processor** (min-max/L2 + arithmetic/geometric/harmonic mean; design in [RFC #126](https://github.com/opensearch-project/neural-search/issues/126)). Score fusion is a post-processing step bolted onto the distributed query path — the issue history below shows the seams.

---

## Agentic integration

- **Glean** is the furthest along: hosted **MCP server** (`developers.glean.com/mcp`, integrations documented for Claude Code, Cursor, Codex, VS Code, JetBrains), Agents API interoperating with LangChain/CrewAI/OpenAI SDK/Google ADK, and an "Agent identity" model ("scoped credentials, persistent presence, and audit trail") so agents act as first-class principals rather than borrowed user tokens. ([developers.glean.com](https://developers.glean.com/), [agent identity post](https://www.glean.com/blog/introducing-agent-identity)) Glean's own content argues indexed retrieval beats query-time MCP federation on "accuracy, latency, and token efficiency" — self-serving but directionally consistent with the latency arithmetic of fan-out federation. ([indexing post](https://www.glean.com/blog/enterprise-ai-indexing-context))
- **Amazon Q Business → Quick**: Q Business had plugins/actions; the successor Quick supports MCP integrations but with hard limits: **"operations have a fixed 60-second timeout"; "tool lists remain static after initial registration, requiring you to delete and recreate the integration"; and MCP integrations "cannot be used as knowledge base data sources for document indexing."** Agentic connectivity and retrieval are architecturally separate silos. ([migration guide](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html))
- **Elastic**: pivoting from Playground to **Agent Builder** (9.4+); retrievers/ES|QL are agent-friendly primitives but permission-aware, multi-source agentic retrieval remains DIY.
- **OpenSearch**: agentic features (agents/tools framework, ML-commons) exist but none of the fetched evidence shows production-grade permission-aware agentic retrieval out of the box.

---

## Strengths (steelman)

1. **They solve the problem everyone else hand-waves: per-user ACL trimming at scale.** Glean's users/groups/memberships/permissions indexing model and Q Business's User Store + identity crawler are complete, thought-through designs for cross-system identity mapping — LangChain/LlamaIndex-class frameworks have nothing comparable.
2. **Pre-computed permission joins for latency.** Q Business docs are explicit that identity mapping exists to cut "ACL information retrieval time during chat requests"; Glean trims at ranking time against a mirrored ACL store. This is the correct engineering answer versus per-query source-system permission checks.
3. **Ranking beyond cosine similarity.** Glean's learned ranking over authorship/views/edits/freshness/graph relationships, trained per-tenant corpus embeddings, and entity knowledge graph is a materially richer relevance model than embed-and-retrieve; practitioner sentiment agrees (HN: "downright magical" — [comment 41896552](https://news.ycombinator.com/item?id=41896552)).
4. **Elastic/OpenSearch operational maturity + real vector economics.** BBQ's ~95% memory reduction with >90% recall, and the retrievers API collapsing multi-stage hybrid+rerank pipelines into one server-side call, are genuine infrastructure advances; ELSER gives zero-fine-tuning semantic lift on the engine ops teams already run.
5. **Connector breadth as a moat.** Glean's 275+ connectors and Q Business's connector catalog encode years of per-SaaS ACL/metadata edge cases (e.g., SharePoint + Entra federated groups) that no greenfield framework replicates quickly.
6. **Guardrails/governance as product features**: Q Business topic-level guardrails, response-scope controls, hallucination mitigation checks; Glean's audit trails and agent identity — enterprise governance is first-class, not an afterthought.

---

## Issues & failure modes

### production-ops
- **[critical | documented-recurring] A hyperscaler's flagship enterprise RAG product was killed ~2 years after GA.** "Amazon Q Business is no longer open to new customers... new feature requests will no longer be considered," with a forced migration to Amazon Quick ([availability change](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html)). Buying closed managed RAG carries platform-mortality risk even from AWS. Corroborating context: HN preview-era report "Amazon's Q has severe hallucinations and leaks data," 34 pts ([HN 38495146](https://news.ycombinator.com/item?id=38495146) → Platformer), and sentiment like "I can't say I understand AWS's product vision, it often seems a day late" ([HN comment 45533669](https://news.ycombinator.com/item?id=45533669)).
- **[major | documented-recurring] Connector sync is fragile enough that AWS shipped a mass-deletion circuit breaker.** The "Document deletion safeguard" exists because "crawler failures and temporary data source unavailability" could otherwise silently delete large fractions of the index during a sync ([connector concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html)).
- **[major | documented-recurring] Elastic killed its own turnkey layer twice.** Enterprise Search (App Search + Workplace Search) deprecated at 9.0 ([FAQ](https://www.elastic.co/resources/search/enterprise-search-faq)); Playground deprecated at 9.4 ([docs](https://www.elastic.co/docs/solutions/search/rag/playground)). Teams that built on the incumbent's "easy" layer must rebuild on raw primitives or Agent Builder.

### security-governance
- **[critical | documented-recurring] Permission models don't survive platform migration.** In Quick's non-IDC mode, "all Amazon Quick users automatically receive access to connected Q Business indexes... you lose the per-user and per-group access distinctions that Q Business enforced," with the workaround being manual content segmentation into separate knowledge bases plus custom scripts; Q Business guardrails "will not transfer"; Quick's native document ACLs cover only S3, Confluence Cloud, SharePoint, Google Drive; and the ACL-on/off choice is **permanent at knowledge-base creation**. ([migration guide](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html))
- **[critical | documented-recurring] Inconsistent secure-by-default postures within one vendor.** Q Business "grants all users access to S3 prefixes that do not appear in the ACL file," while Quick "does not ingest documents that lack an associated ACL entry" — opposite defaults for the same data, documented in the same migration guide. Default-open ACL fallback in a RAG index is an over-sharing incident waiting to happen.
- **[major | documented-recurring] Mirrored ACL stores are themselves a privileged, error-prone system.** AWS's own warning: "Inadvertent mistakes when you update the User Store's user, group, group membership, and mapping information can result in unintentional and unacceptable changes in the accessibility of documents"; deleting/recreating a group with the same name corrupts document ACLs; a re-used employee email silently **denies all API calls** for the new user; ACL/identity crawling "once ... enabled ... you won't be able to turn them off." ([connector concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html))
- **[major | documented-recurring] Permission freshness is bounded by crawl cadence.** Q Business: ACL changes are only captured "each time that your data source content is crawled... re-sync your data source regularly" (hourly at best) — a revoked user can retrieve content until the next sync. Glean's docs likewise admit asynchronous permission processing delay ([Glean indexing docs](https://developers.glean.com/)), against marketing that claims permissions are "reflected immediately" ([glean.com/connectors](https://www.glean.com/connectors)).
- **[major | documented-recurring] The Amazon Q product family shipped serious supply-chain/prompt-injection failures.** July 2025: a hacker's PR added a data-wiping prompt to the Q Developer VS Code extension, which AWS released ([ZDNet via HN 44675557](https://news.ycombinator.com/item?id=44675557), [Corey Quinn via HN 44663016](https://news.ycombinator.com/item?id=44663016), [AWS bulletin AWS-2025-015](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/)); 2025–26 researcher reports of prompt-injection RCE and DNS exfiltration (embracethered, [HN 44958663](https://news.ycombinator.com/item?id=44958663)); June 2026 Register report of booby-trapped repos stealing cloud creds ([HN 48691319](https://news.ycombinator.com/item?id=48691319)). Q Developer ≠ Q Business, but it is the same product family, org, and trust boundary.
- **[major | architectural-inference, vendor-adjacent source] The centralized-mirror architecture concentrates risk.** Glean-style systems hold a full copy of everything plus mirrored ACLs and admin-scoped API tokens into every SaaS. Competitor Atolio (biased source, labeled as such) frames the risks as "data theft, corporate IP leakage... violations of data sovereignty" and sells private/air-gapped deployment against it ([atolio.com Series A post](https://www.atolio.com/blog/atolio-raises-series-a-to-bring-secure-enterprise-search-to-the-world)). Bias aside, the attack-surface math (one tenant containing the union of all sensitive corpora and credentials) is straightforwardly true.

### performance-cost
- **[major | documented-recurring] Permission-aware managed RAG has a steep cost floor.** Kendra Basic Enterprise: **$1,008/month base** before a single user query beyond 0.1 QPS; +$0.7/hr per extra 0.1 QPS query unit ([Kendra pricing](https://aws.amazon.com/kendra/pricing/)). Q Business: $3–$20/user/mo **plus** $0.264/hr/unit enterprise index where a unit is only 20k docs/200MB, plus per-image/audio/video processing fees ([Q pricing](https://aws.amazon.com/q/business/pricing/)). Glean: ~$99k/yr median contract, 100–250-seat minimums (Vendr, third-party estimate). Permission mirroring + managed index is priced like the heavy infrastructure it is.
- **[major | documented-recurring] ELSER inference is the bottleneck of Elastic's semantic story.** Official guidance: dedicated ≥4 GB ML node; observed throughput **~26 docs/sec on a 16-vCPU ML node** (Elastic staff figure), with forum reports of 40k docs taking 35 minutes and stalled deployments at higher allocation counts ([discuss #352636](https://discuss.elastic.co/t/how-to-improve-elserv2-ingest-throughput/352636)); OOM killing nodes on very large documents ([elasticsearch #116022](https://github.com/elastic/elasticsearch/issues/116022)); re-indexing degrades live semantic query latency ([discuss #362468](https://discuss.elastic.co/t/362468)). Semantic search on the incumbent = paying for a permanent ML-node fleet sized to your ingest peaks.

### retrieval-quality
- **[major | documented-recurring] OpenSearch hybrid-score fusion has structural anomalies.** Hybrid relevance depends on how many results you request ("Hybrid search scoring is dependent on number of results requested," [neural-search #325](https://github.com/opensearch-project/neural-search/issues/325)); min-max normalization + arithmetic mean produces "unexpected ranking behavior" ([#910](https://github.com/opensearch-project/neural-search/issues/910)); pagination for hybrid queries didn't exist initially ([#280](https://github.com/opensearch-project/neural-search/issues/280)); hybrid breaks with nested fields, collapse, inner_hits, request_cache NPEs ([#466](https://github.com/opensearch-project/neural-search/issues/466), [#665](https://github.com/opensearch-project/neural-search/issues/665), [#718](https://github.com/opensearch-project/neural-search/issues/718), [#1415](https://github.com/opensearch-project/neural-search/issues/1415)). Score fusion retrofitted onto a sharded lexical engine leaks its seams into relevance itself.
- **[major | documented-recurring] ELSER truncates at 512 tokens and is English-only** — "ELSER encodes the first 512 tokens of a field"; chunking is pushed onto the user, and non-English corpora need a different model with different behavior ([ELSER docs](https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser)).
- **[major | single-anecdote (multiple independent anecdotes)] Glean's ceiling is the customer's data hygiene.** HN practitioner: "the issue is data quality. If your Google Docs and wikis contain obsolete [content]..." ([HN 41901466](https://news.ycombinator.com/item?id=41901466)); another: Glean's people/expertise graph "is mostly org chart and document co-occurrence data. It doesn't capture who people actually trust... or who the real subject matter experts are" ([HN 47409517](https://news.ycombinator.com/item?id=47409517)). Indexing + ranking cannot fix stale or wrong sources; no incumbent offers content-quality/contradiction detection as a first-class pipeline stage.

### abstraction-design
- **[major | documented-recurring] Elastic's "sensible defaults" can silently change your embedding space.** semantic_text's "default endpoint can change across versions and deployment types, which can lead to indices with mixed embedding models and cause ranking issues in multi-index searches" (official docs); plus upgraded indices that couldn't use semantic_text at all ([#132551](https://github.com/elastic/elasticsearch/issues/132551)), semantic queries crashing when `size: 0` ([#116083](https://github.com/elastic/elasticsearch/issues/116083)), IllegalStateException in SemanticQueryBuilder ([#116106](https://github.com/elastic/elasticsearch/issues/116106), 36 comments), and non-unit-length vectors from some inference providers corrupting similarity ([#153028](https://github.com/elastic/elasticsearch/issues/153028), open). Hiding model identity behind a field type trades correctness for convenience.
- **[major | documented-recurring] Abstraction churn across the segment.** Elastic: `sub_searches` → retrievers; Playground → Agent Builder; Enterprise Search → gone. AWS: Kendra → Q Business → Quick in ~4 years, each hop with breaking permission/feature semantics. Applications built on any of these strata got re-platformed at least once.
- **[major | architectural-inference] "Mirror the enterprise" is duplicated, bespoke work per platform.** Glean, Q Business, Coveo, and Sinequa each re-implement the same connector + identity + ACL-mirror + freshness machinery as proprietary, non-portable infrastructure. There is no shared standard for exchanging document ACLs/identity mappings (MCP notably does NOT cover this — see below), so the hardest 80% of enterprise RAG is rebuilt N times and locked in each time.

### agentic-integration
- **[major | documented-recurring] Retrieval and agentic connectivity are divorcing in the incumbent stacks.** Amazon Quick: MCP integrations "cannot be used as knowledge base data sources for document indexing," have "a fixed 60-second timeout," "custom HTTP headers are not supported," and "tool lists remain static after initial registration" ([migration guide](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html)). MCP gives agents actions but not permission-aware knowledge — the two halves of the problem don't compose.
- **[minor | architectural-inference] Glean's MCP/agent surface funnels everything through Glean's tenancy** — an agent ecosystem where the index, the identity model, the ranking, and now agent identity/audit are all one vendor's closed system; the "Platform APIs" are still labeled Experimental ([developers.glean.com](https://developers.glean.com/)).

### evaluation-observability
- **[major | architectural-inference] No credible third-party retrieval-quality benchmarks exist for the closed platforms.** Glean publishes only self-run preference studies ("Glean results preferred ~2x more than ChatGPT, 1.6x more than Claude" — vendor benchmark, [blog](https://www.glean.com/blog/enterprise-search-evaluation-2026)); Q Business published none. Because per-tenant corpora and ACLs make external replication impossible, buyers cannot compare permission-aware retrieval quality across vendors at all — an evaluation vacuum unique to this segment.

### dx-docs
- **[minor | documented-recurring] Permission indexing DX is intricate and full of sharp edges** even in the best-in-class version: Glean requires a strict ordering (users → groups → memberships → documents), a global identity-keying decision per datasource, group names that "cannot start with the prefix 'scio'", and async debugging via `/checkdocumentaccess` ([Glean indexing docs](https://developers.glean.com/)).

### data-processing
- **[minor | documented-recurring] Managed index capacity units are coarse and truncating.** Q Business: 20k docs/200MB per unit forces stepwise overprovisioning; all metadata fields truncate at 2,048 chars pre-ingestion ([connector concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html)); Kendra GenAI index caps at 0.1 QPS before extra query units.

---

## Community sentiment over time

- **2021–2023 (Glean emergence)**: positive novelty — Forbes stealth-exit coverage ([HN 28541598](https://news.ycombinator.com/item?id=28541598)); "Glean Chat: first enterprise-grade ChatGPT for work" (2023).
- **2023 (Q preview)**: immediate skepticism — "Amazon's Q has hallucinations and leaks data in public preview, employees warn" ([HN 38495146](https://news.ycombinator.com/item?id=38495146)).
- **2024–2025**: Glean praised by users ("downright magical," [HN 41896552](https://news.ycombinator.com/item?id=41896552)) with the recurring caveat that value is bounded by corpus quality ([HN 41901466](https://news.ycombinator.com/item?id=41901466)). Q family reputation damaged by the July 2025 malicious-PR wiper incident (75 & 63-pt HN threads). Elastic quietly sunsets Enterprise Search.
- **2025–2026 (commoditization anxiety)**: open-source Onyx's Launch HN (254 pts) draws "why choose Onyx over Glean and Elastic?" ([HN 46045987](https://news.ycombinator.com/item?id=46045987)); agent-native competitors (Airweave: "Glean is enterprise search for humans," [HN comment 45429358](https://news.ycombinator.com/item?id=45429358)) and private-deploy competitors (Atolio) position directly against the centralized-SaaS model; on Anthropic's Claude Tag launch a top comment reads "**RIP to Glean? For enterprises already with an Anthropic MSA, hard to see the argument to purchase a third party**" ([HN 48651251](https://news.ycombinator.com/item?id=48651251)). 2026: AWS closes Q Business to new customers. Sentiment arc: "permissions moat" → "the model vendors and open source are coming for the moat."

---

## Benchmarks & third-party evaluations

- **Glean / Q Business / Coveo / Sinequa: no independent, reproducible retrieval benchmarks found.** The only quantitative quality claims located are vendor-run (Glean's 2026 preference eval vs ChatGPT/Claude; SPARK Matrix analyst quadrants for ChapsVision/Sinequa — analyst placements, not measurements).
- **Elastic**: BBQ numbers (95% memory reduction; recall 74%@1-bit E5-small, >90% with 3x oversampling CohereV3) are vendor-published but methodology-transparent on named public datasets ([search-labs](https://www.elastic.co/search-labs/blog/better-binary-quantization-lucene-elasticsearch)); Elastic Rerank claims BEIR uplift in a two-part series, with the honest caveat that reranking "will not be able to fix" first-stage recall blindspots ([search-labs part 1](https://www.elastic.co/search-labs/blog/elastic-semantic-reranker-part-1)). ELSER throughput reference: ~26 docs/sec per 16-vCPU ML node (Elastic staff on discuss).
- **OpenSearch**: hybrid/normalization design and its failure modes are traceable in public RFCs/issues (#126, #325, #910), which is itself a form of third-party evaluability the closed platforms lack.
- **Structural finding**: permission-aware enterprise RAG is an evaluation dead zone — corpora are private, ACLs are tenant-specific, and vendors are closed, so the segment's central claims (retrieval quality under permission trimming; permission freshness SLAs) are unverifiable by construction.

---

## Lessons for a next-generation framework

1. **Permissions are the product, and they need a standard.** Every serious player independently rebuilt users/groups/memberships mirroring, identity mapping, and query-time ACL trimming — and none of it is portable (Q Business → Quick lost per-user ACLs in non-IDC mode). A next-gen framework should define a **portable, source-agnostic ACL/identity interchange schema** (the missing sibling of MCP) so permission mirroring is written once per source, not once per platform.
2. **Treat permission freshness as a measurable SLA, not a crawl side-effect.** Incumbents bound revocation latency by sync cadence (hourly at best) and admit async delays. Next-gen: event-driven permission deltas with a queryable staleness metric, and fail-closed defaults everywhere (the Q Business default-open S3-prefix behavior is the anti-pattern).
3. **Pre-compute the permission join, but version it.** AWS's identity crawler exists because query-time ACL resolution is too slow; the User Store warnings show that a mutable, hand-editable mirror is dangerous. The fix is an immutable, versioned, auditable ACL snapshot store with diffable changes — git semantics for permissions.
4. **Ranking signals beyond embeddings are the real quality moat.** Glean's edge is authorship/activity/freshness/graph features and per-tenant trained indexes, not a better vector DB. Open frameworks that stop at "hybrid + rerank" concede this entire layer.
5. **Never hide model identity inside a field type.** Elastic's semantic_text default-endpoint drift (mixed embedding spaces breaking ranking) shows embedding-model identity must be an explicit, pinned, migration-managed artifact.
6. **Score fusion must be a first-class, testable relevance component.** OpenSearch's result-size-dependent hybrid scores and normalization anomalies show what happens when fusion is a post-processor bolted onto a sharded engine.
7. **Design for platform mortality.** Q Business (dead in ~2 years), Workplace Search (dead), Playground (dead), Sinequa (absorbed): enterprise RAG assets — indexes, ACL mirrors, connector configs, agents — need an exportable, open representation, or customers rebuild from zero at each vendor pivot.
8. **Unify agentic actions and permission-aware retrieval.** The Quick design (MCP for actions, proprietary index for knowledge, no crossover) fractures the agent's world model. A next-gen framework should expose retrieval *and* actions through one permission-aware, agent-identity-aware interface — Glean's agent-identity concept (scoped credentials + audit for agents as principals) is the right direction and shouldn't be vendor-locked.
9. **Budget honestly: this layer is expensive for structural reasons.** $1,008/mo index floors (Kendra), dedicated ML-node fleets at ~26 docs/sec/node (ELSER), ~$99k median contracts (Glean), per-unit index metering (Q) all reflect real costs of mirroring + inference + identity infrastructure. A next-gen framework wins by making the costs *inspectable and incremental* (pay per source/per freshness tier), not by pretending they don't exist.
10. **Make evaluation possible.** The segment's biggest epistemic failure: zero reproducible benchmarks for permission-aware retrieval. Ship a synthetic multi-tenant, ACL-rich benchmark corpus (documents + identities + permission changes over time) so "correct and fresh under ACL trimming" becomes a testable claim, and content-quality/staleness detection becomes part of the pipeline rather than the customer's problem.

---

## Sources

Primary vendor docs
- https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/what-is.html
- https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html (closure + Quick migration + ACL degradation details)
- https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html (ACL crawling, User Store warnings, deletion safeguard, sync modes)
- https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/supported-connectors.html
- https://aws.amazon.com/q/business/pricing/ ; https://aws.amazon.com/kendra/pricing/
- https://developers.glean.com/ (indexing API, permissions model, MCP, agents)
- https://www.glean.com/connectors ; https://www.glean.com/press ; https://www.glean.com/blog/enterprise-ai-indexing-context ; https://www.glean.com/blog/how-do-you-build-a-context-graph ; https://www.glean.com/blog/introducing-agent-identity
- https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser
- https://www.elastic.co/docs/solutions/search/semantic-search/semantic-search-semantic-text
- https://www.elastic.co/docs/solutions/search/retrievers-overview
- https://www.elastic.co/docs/solutions/search/rag/playground (deprecation)
- https://www.elastic.co/resources/search/enterprise-search-faq (Enterprise Search EOL)
- https://www.elastic.co/docs/reference/search-connectors/
- https://www.elastic.co/search-labs/blog/better-binary-quantization-lucene-elasticsearch
- https://www.elastic.co/search-labs/blog/elastic-semantic-reranker-part-1
- https://www.sinequa.com/company/press/ (ChapsVision branding)

GitHub issues (fetched via gh CLI)
- elastic/elasticsearch: #116106, #116022, #116083, #132551, #153028, #124653
- opensearch-project/neural-search: #126, #280, #299, #325, #466, #497, #665, #718, #910, #1335, #1415

Forums / community (fetched via Discourse/HN Algolia JSON APIs)
- https://discuss.elastic.co/t/how-to-improve-elserv2-ingest-throughput/352636 (26 docs/sec figure)
- discuss.elastic.co topics 362468, 351411 (re-indexing slowdown, bulk timeouts)
- HN: 38495146 (Q hallucinations preview), 44675557 & 44663016 (Q Developer wiper PR), 44958663 & 48691319 (Q prompt-injection/RCE), 41896552 & 41901466 (Glean praise/data-quality), 47409517 (Glean graph gap), 48651251 (Claude Tag "RIP to Glean?"), 46045987 (Onyx Launch HN), 45429358 (Airweave), 45533669 (AWS product-vision skepticism)

Third-party / vendor-adjacent (labeled)
- https://www.vendr.com/marketplace/glean (pricing estimates — third-party marketplace data)
- https://www.atolio.com/blog/atolio-raises-series-a-to-bring-secure-enterprise-search-to-the-world (competitor critique — biased source)
- https://techcrunch.com/2019/11/06/coveo-raises-227m-at-1b-valuation-for-ai-based-enterprise-search-and-personalization/
- https://aws.amazon.com/security/security-bulletins/AWS-2025-015/
