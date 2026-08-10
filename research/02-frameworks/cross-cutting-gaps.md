# Cross-Cutting Failure Categories Missing From RAG-Framework Autopsies

*A survey-style companion to the per-framework autopsies. Where the framework files ask "what is wrong with LangChain / LlamaIndex / Pinecone / Vespa," this file asks the orthogonal question: **which failure categories are systemic to retrieval-augmented systems and under-covered because no single framework "owns" them.** Organized by the eight gap categories (a)–(h). Every concrete issue carries evidence (link + gist/quote), a severity, exactly one taxonomy label, and an evidence label (documented-recurring / single-anecdote / architectural-inference).*

---

## Scope, method & evidence ledger

### Methodology note (read this before quoting any number)

The `WebSearch` budget for this session was **fully exhausted (200/200) before a single query could run**. No keyword web search was possible. Evidence was therefore gathered by direct primary-source `WebFetch`, using three search substitutes that do not consume the WebSearch budget:

1. **the arXiv Atom API** (`export.arxiv.org/api/query?search_query=...`) — a genuine full-text search channel over arXiv metadata. Every arXiv ID cited below was **resolved through this API and confirmed to match the claimed title**; no ID in this file was written from recall alone. As a final integrity check, all twelve IDs not obtained from a keyword search were re-resolved in a single batch `id_list=` query and every one returned the title claimed for it here.
2. **the Hacker News Algolia API** (`hn.algolia.com/api/v1/search`) — returns title, points, comment count and creation date, which is exactly what the "community sentiment over time" section needs, with dates attached.
3. **direct fetches of vendor documentation, GitHub issue/PR search pages, NVD, and OWASP.**

Consequences to be honest about:
- Quantities attributed to arXiv were read from the abstract via a summarizer and are marked "abstract reports X." They should be checked against the PDF before being quoted in the paper.
- A handful of fetches failed (OpenAI's GPT-4-GA blog returned 403; the Azure model-*schedule* page 404'd; MSRC's advisory page is JS-rendered; Qdrant's optimizer page would not render). Where a fetch failed, the claim is either dropped or explicitly downgraded. Nothing is asserted from a page I could not read.
- **Negative evidence is treated as weak.** Several "nobody is talking about this" observations below rest on empty search results. An empty result can be a query artifact rather than a real absence, so these are labelled `architectural-inference` and never carry a quantified claim.
- Categories **(b)** and **(h)** are thin in the literature *and* in every framework. That thinness is itself the finding, not a gap in this survey — but (h) is thinner in *frameworks* than in *research*, which turns out to be an important distinction (see below).

### Who "owns" these categories? (the adoption signal that matters here)

A per-framework autopsy can name a maintainer, a license, and a star count. A cross-cutting survey has to answer a different adoption question: **which body, vendor, or project has taken responsibility for each category?** The answer is the finding.

| Gap category | Who has taken ownership | Standard/spec exists? | Framework primitive exists? |
| --- | --- | --- | --- |
| (a) Adversarial ML on retrieval substrate | Academia (dense, 2023–2026) + **OWASP GenAI** (LLM08:2025) | Yes — OWASP LLM08 names it | **No** |
| (b) Relevance feedback / online learning | Classical IR (2016–) + commerce-search products | No RAG-side spec | **No** |
| (c) Regulatory & data lifecycle | Regulators (GDPR Art. 17, EU AI Act) | Yes — law, not tooling | **No** |
| (d) Embedding deprecation | Vendors set the clock unilaterally | Vendor lifecycle policies only | **No** |
| (e) Index backup / DR / migration | Individual vector-DB teams, reactively | No | Partial (per-DB snapshot APIs) |
| (f) Multilingual retrieval | Benchmark community (MIRACL, MMTEB) | Benchmarks, yes; tooling, no | Partial (analyzers, unguided) |
| (g) Tail latency & capacity | Vector-DB vendors (marketing-shaped) | No standard tail-latency harness | Partial (per-DB knobs) |
| (h) On-device / air-gapped | Academia (2024–2026) + embedded stores | No | Partial (embedded stores only) |

The pattern: **for six of eight categories a standard or a body of research exists and the framework layer has simply not implemented it.** This is not a research gap. It is an engineering-responsibility gap, and it is precisely the space a next-generation framework can occupy.

---

## Why these eight, and why they fall through the cracks

Per-framework autopsies converge on the same surface: chunking, abstraction bloat, retriever quality, agent glue, docs. They rarely reach the categories below because each one lives at a **seam**:

- (a) between ML security and infrastructure
- (b) between search science and product analytics
- (c) between engineering and legal/compliance
- (d) between your application and a vendor's roadmap
- (e) between the happy path and disaster recovery
- (f) between English benchmarks and the other ~7,000 languages
- (g) between median-case demos and p99 under concurrent load
- (h) between cloud assumptions and the edge

Frameworks optimize the demo. These categories only bite in production, at scale, under adversaries, or under audit — and each one crosses a boundary that no single framework's maintainers consider theirs.

---

## (a) Adversarial ML on the retrieval substrate

The retriever is an attack surface with four distinct threat classes: **corpus poisoning** (adversarial write into the index), **inversion/membership** (read data back out of vectors), **injection/exfiltration chains** (weaponize retrieved content), and **retrieval denial-of-service** (block legitimate answers). The 2023–2026 literature is dense, real incidents now exist in flagship products, and framework-level defenses are close to absent.

### The category is now formally recognized

- **OWASP LLM08:2025 — "Vector and Embedding Weaknesses."** The OWASP GenAI Top 10 for 2025 has a dedicated entry: *"Vectors and embeddings vulnerabilities present significant security risks in systems utilizing Retrieval Augmented Generation (RAG) with Large Language Models."* It enumerates unauthorized access/data leakage, **cross-context leaks in multi-tenant environments** (embeddings from one group *"inadvertently retrieved in response to queries from another group's LLM"*), **embedding inversion** (*"attackers can exploit vulnerabilities to invert embeddings and recover significant amounts of source information"*), data poisoning, and behavior alteration. ([OWASP LLM08:2025](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/))
  *Severity: high (as a framing claim). Taxonomy: security-governance. Label: documented-recurring.*
  **Why this matters for the paper:** the retrieval substrate being an attack surface is no longer a research opinion; it is in the industry-standard risk register. Frameworks nonetheless ship no mitigation for any of the five sub-risks OWASP lists.

### Corpus / knowledge-base poisoning

- **PoisonedRAG** — arXiv [2402.07867](https://arxiv.org/abs/2402.07867) (USENIX Security 2025; Zou, Geng, Wang, Jia). Fetched abstract reports *"a 90% attack success rate when injecting five malicious texts for each target question"* into a knowledge database containing **millions of texts**, in both black-box and white-box settings, and states that evaluated defenses *"are insufficient."*
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  The economics are the story: five documents against millions is a ~1e-6 poisoning ratio. There is no plausible manual-review defense at that ratio.

- **AgentPoison** — arXiv [2407.12784](https://arxiv.org/abs/2407.12784) (Chen, Xiang, Xiao, Song, Li). Backdoors LLM **agents** by poisoning long-term memory or the RAG knowledge base; trigger optimization is posed as a constrained problem so malicious demonstrations are retrieved when the instruction contains the trigger. Abstract reports **average attack success rate >80% with a poisoning rate of <0.1% and <1% impact on benign performance**, across RAG-based autonomous driving, knowledge-intensive QA, and the healthcare EHRAgent.
  *Severity: high. Taxonomy: agentic-integration. Label: documented-recurring.*
  This is the crucial bridge between (a) and agentic RAG: **agent memory is a corpus, therefore agent memory is a poisoning target**, and "no model retraining required" means the attack is available to anyone who can write a document.

- **Corpus poisoning by adversarial passages** — arXiv [2310.19156](https://arxiv.org/abs/2310.19156) (EMNLP 2023). Abstract reports **50 passages optimized on Natural Questions "can mislead >94% of questions"** in *unrelated* domains (finance, forums), and that the dense retrievers tested *"can all be successfully attacked."* Establishes **cross-domain transferability** — the attacker need not know the target queries.
  *Severity: high. Taxonomy: retrieval-quality. Label: documented-recurring.*

- **Phantom: General Backdoor Attacks on Retrieval Augmented Language Generation** — arXiv [2405.20485](https://arxiv.org/abs/2405.20485). A **single** poisoned document that is retrieved only when a *"naturally occurring trigger sequence of tokens appears in the victim's queries,"* then induces refusal, reputation damage, privacy violation, or harmful output. Demonstrated across Gemma, Vicuna, Llama, GPT-3.5/4, and against NVIDIA's production "Chat with RTX."
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  Trigger-conditioned retrieval defeats sampling-based review: the poisoned document looks inert to every query except the attacker's.

### Retrieval denial-of-service (the class nobody defends against)

- **Machine Against the RAG: Jamming RAG with Blocker Documents** — arXiv [2406.05870](https://arxiv.org/abs/2406.05870) (Shafran, Schuster, Shmatikov; USENIX Security 2025). A single injected *"blocker document"* causes the RAG system to **refuse to answer** specific queries. Uses black-box optimization, and requires *"no instruction injection, embedding knowledge, or auxiliary LLM."* The authors state explicitly that existing LLM safety metrics *"do not capture their vulnerability to jamming."*
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  **This is availability, not confidentiality or integrity** — the third leg of the CIA triad, and the one no RAG evaluation harness measures. A competitor or disgruntled insider who can write one document can make your assistant silently stop answering about a chosen topic, and your eval suite will not notice because refusals often score as "safe."

### Embedding inversion & membership inference (reading data back out)

- **Text Embeddings Reveal (Almost) As Much As Text** (vec2text) — arXiv [2310.06816](https://arxiv.org/abs/2310.06816) (EMNLP 2023). Abstract reports an iterative correct-and-re-embed method that *"recover[s] 92% of 32-token text inputs exactly,"* and can *"recover important personal information (full names) from a dataset of clinical notes."*
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  **Direct implication: a stolen vector index is a stolen, nearly-plaintext corpus.** Vectors are routinely handled as if they were opaque hashes — shipped to third-party managed services, logged, cached, replicated across regions — under a security model that treats them as non-sensitive derived data. They are not. OWASP LLM08 now says the same thing.

- **The Good and The Bad: Exploring Privacy Issues in RAG** — arXiv [2402.16893](https://arxiv.org/abs/2402.16893) (Zeng et al.). Demonstrates attacks that expose private *retrieval databases*, noting *"RAG technique could potentially reshape the inherent behaviors of LLM generation, posing new privacy issues."* Notably nuanced: the same work finds RAG can *reduce* leakage of the LLM's **training** data — i.e. RAG moves the privacy risk from the model's weights to the retrieval datastore rather than eliminating it.
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  The follow-up, **SAGE** (arXiv [2406.14773](https://arxiv.org/abs/2406.14773)), mitigates via pure synthetic data — evidence that the field's current best answer is "don't put the real data in the index," which is not an answer most enterprises can accept.

- **"Is My Data in Your Retrieval Database? Membership Inference Attacks Against Retrieval Augmented Generation"** — arXiv [2405.20446](https://arxiv.org/abs/2405.20446) (ICISSP 2025). An attacker *"can infer whether a certain text passage appears in the retrieval database by observing the outputs,"* in black-box and gray-box settings via crafted prompts.
  *Severity: medium-high. Taxonomy: security-governance. Label: documented-recurring.*
  Set membership is itself confidential in most regulated domains: "is this patient in the oncology index," "is this company in the M&A diligence corpus," "is this employee in the HR-investigation set."

### Injection & exfiltration chains — now with a CVE in a flagship product

- **EchoLeak — CVE-2025-32711, Microsoft 365 Copilot, zero-click data exfiltration.** NVD describes it as *"Ai command injection in M365 Copilot allows an unauthorized attacker to disclose information over a network,"* **published 2025-06-11**, scored **7.5 HIGH by NIST and 9.3 CRITICAL by Microsoft (CVSS 3.1)**. ([NVD CVE-2025-32711](https://nvd.nist.gov/vuln/detail/CVE-2025-32711)) The disclosure by Aim Labs reached **228 points / 86 comments on Hacker News on 2025-06-11** ([HN 44250774](https://news.ycombinator.com/item?id=44250774) → [Aim Labs writeup](https://www.aim.security/lp/aim-labs-echoleak-blogpost)), with parallel coverage in [BleepingComputer](https://www.bleepingcomputer.com/news/security/zero-click-ai-data-leak-flaw-uncovered-in-microsoft-365-copilot/) and [Fortune](https://fortune.com/2025/06/11/microsoft-copilot-vulnerability-ai-agents-echoleak-hacking/).
  *Severity: critical. Taxonomy: security-governance. Label: documented-recurring.*
  **This is the single most important citation in this file.** It converts (a) from "academics can attack toy RAG systems" to "a CVE with a 9.3 vendor score existed in the most widely deployed enterprise RAG product on earth, exploitable with no user click." Any argument that retrieval-substrate security is a theoretical concern dies here. Note: I could not fetch MSRC's advisory (JS-rendered), so Microsoft's own remediation language is not quoted; the CVSS figures come from NVD, which I did read.

- **Slack AI data exfiltration via indirect prompt injection** — PromptArmor, disclosed [Aug 2024](https://promptarmor.substack.com/p/data-exfiltration-from-slack-ai-via). An attacker posts instructions in a public channel they alone occupy; when a victim later queries Slack AI, both the legitimate private data and the malicious message are retrieved into context, and the model renders an exfiltration link — *"the citation [does] not refer to the attacker's channel,"* making attribution hard. Slack's response was that the behavior was **"intended"** and the evidence *"insufficient."*
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring (single disclosed incident, widely reproduced pattern).*
  The vendor's "intended" response is the governance finding: when retrieval scope and instruction-following are both working as designed, the *composition* is the vulnerability, and no component owner accepts it as a bug.

- **ConfusedPilot: Confused Deputy Risks in RAG-based LLMs** — arXiv [2408.04870](https://arxiv.org/abs/2408.04870). The title names the correct security abstraction: RAG retrieval is a **confused-deputy** problem — the retriever acts with the *user's* authority on content supplied by an *attacker*. Studies enterprise RAG of the Microsoft 365 Copilot class: malicious text in a retrieved document *"corrupt[s] the responses,"* and a second vulnerability *"leaks secret data, [leveraging] the caching mechanism during retrieval."* Root cause named directly: an LLM *"cannot distinguish between the 'system prompt' ... and the rest of the context."*
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  The caching channel is under-appreciated: retrieval caches are a *second* data store with a *different* (usually weaker) access-control model than the index they front.

- **The pattern persists into 2025–2026 across vendors.** HN discussion of *"Google Antigravity exfiltrates data via indirect prompt injection"* (2025-11-25) contains the mechanism stated plainly by a commenter: *"poisoning your database...then bringing that into context via RAG"* enables injection even when the system prompt forbids exfiltration ([HN comment 46051614](https://news.ycombinator.com/item?id=46051614)). simonw described the same base64-encode-then-social-engineer chain back on 2023-12-07 ([HN comment 38563214](https://news.ycombinator.com/item?id=38563214)).
  *Severity: medium (as corroboration). Taxonomy: security-governance. Label: documented-recurring.*
  Two years, multiple vendors, unchanged mechanism. That is the definition of a systemic architectural failure rather than a bug.

### What frameworks do today

Essentially nothing at the substrate. Prompt-injection guards, where they exist, sit at the **LLM boundary**, not the retriever. No mainstream framework signs provenance on chunks, assigns per-source trust tiers, encrypts vectors against inversion, rate-limits membership probing, detects jamming/blocker documents, or scores candidate passages for poisoning before they enter the prompt. Ingestion pipelines universally treat documents as trusted inert data — but **adding a document to a corpus is a privileged write to model behavior.**

### Next-gen requirement

Treat the corpus as an **untrusted, adversarial-write medium**: provenance-signed chunks with per-source trust tiers; retrieval-time poisoning/jamming/anomaly detection on candidate sets; vector-at-rest confidentiality designed on the assumption that inversion succeeds; membership-inference throttling; cache access-control parity with the index; and a **structural** data/instruction boundary so retrieved text can never be interpreted as instructions. Availability (jamming) must be a measured property, not an unmonitored one.

---

## (b) Relevance feedback & online learning — the discipline RAG dropped

Classical web search spent 25 years building a closed loop: log clicks/dwell → debias → retrain learning-to-rank → ship → measure. **RAG threw that loop away.** In every mainstream framework the retriever is *frozen at ingestion*: embeddings and rankers never learn from whether the user was actually satisfied.

### The discipline exists and is well-formalized

- **Unbiased Learning-to-Rank with Biased Feedback** — arXiv [1608.04468](https://arxiv.org/abs/1608.04468) (Joachims, Swaminathan, Schnabel, 2016). Provides *"a counterfactual inference framework that provides the theoretical basis for unbiased LTR via Empirical Risk Minimization despite biased data,"* with a Propensity-Weighted Ranking SVM that uses click models for debiasing, works when queries do not repeat, and is robust to noise and model misspecification.
  *Severity: high (as the "solved elsewhere" anchor). Taxonomy: retrieval-quality. Label: documented-recurring.*
  **The theory has been settled for a decade.** RAG's failure here is not a research gap; it is non-adoption.

- **Naive feedback learning actively degrades ranking.** *"Unidentified and Confounded? Understanding Two-Tower Models for Unbiased Learning to Rank"* — arXiv [2506.20501](https://arxiv.org/abs/2506.20501) studies two-tower learning-to-rank trained on production feedback and finds training *"on biased user feedback ... leads to degraded ranking performance,"* attributed to confounding logging policies and model-identifiability problems.
  *Severity: high. Taxonomy: retrieval-quality. Label: documented-recurring.*
  This is why "just log thumbs-up and fine-tune on it" is not a plan. Position bias and logging-policy confounding make the naive loop worse than no loop.

### The loop demonstrably ships — just not in RAG products

This is the strongest available evidence, because it is an **intra-vendor asymmetry**:

- **Google's commerce search *requires* a closed feedback loop.** Google's AI Commerce Search / Retail docs state the system *"uses real-time user events to generate recommendations and search results,"* prioritizing `SEARCH`, `DETAIL_PAGE_VIEW`, `ADD_TO_CART`, and `PURCHASE_COMPLETE`. It imposes hard data minimums — *"at least 250,000 events in the last 90 days"* and *"at least 500,000 events"* of search-attributable detail-page views within 30 days — and warns that *"synthetic or duplicate events negatively impact model quality and often prevent successful model training,"* and that the product-ID list in search events *"must match the list of products shown to the user in its entirety."* ([Google Retail user events](https://docs.cloud.google.com/retail/docs/user-events))
  *Severity: high. Taxonomy: evaluation-observability. Label: documented-recurring.*
  **Read the asymmetry carefully.** The *same vendor* that requires a quarter-million logged interaction events to tune retail search ranking ships RAG/grounding surfaces with **no user-event ingestion path at all**. The engineering capability is in the building. It was simply never wired to the generative-retrieval product. The 250k-event floor also quantifies the real barrier: closed-loop ranking needs traffic volume most enterprise RAG deployments never reach — which is an argument for pooled/transfer approaches, not for abandoning the loop.

- **Practitioner-visible absence.** A GitHub issue search on LangChain for relevance-feedback / learn-from-user-feedback / online-ranking returns no matching results ([langchain issue search](https://github.com/langchain-ai/langchain/issues?q=relevance+feedback+re-ranking+user+feedback)). **Caveat, stated plainly:** this query ANDs several multi-word terms, so an empty result is a weak signal and would occur even in a repo that did ship the feature. It is offered only as corroboration of the vendor asymmetry above, never as standalone proof.
  *Severity: low (as evidence). Taxonomy: dx-docs. Label: architectural-inference.*

- **Feedback-loop poisoning is the adversarial mirror.** If a RAG system *did* learn naively from clicks, the (a) poisoning attacks extend into the ranker: adversaries manufacture engagement to promote malicious passages, and AgentPoison's <0.1%-poisoning-rate result suggests the required effort is small. Any online-learning design must be adversary-aware from day one — the reason classical search shops guard their query logs as tightly as their index.
  *Severity: high. Taxonomy: security-governance. Label: architectural-inference.*

### What frameworks do today

None close the loop. "Feedback" in these tools means thumbs-up telemetry flowing to an **offline eval dashboard** — a number a human reads, not a signal that updates retrieval. The frameworks ship retrievers, rerankers, and eval harnesses, and the wire between the last two and the first does not exist.

### Next-gen requirement

A first-class, **debiased, adversary-aware** relevance-feedback loop: counterfactual/IPS-corrected click models or contextual bandits over retrievers and rerankers; drift monitoring on learned rankings; poisoning defenses on the feedback channel itself; and a low-traffic story (pooling, transfer, or synthetic-propensity priors) so deployments below Google's 250k-event floor can still learn. RAG must re-import the online-learning discipline classical search never lost.

---

## (c) Regulatory & data lifecycle: right-to-erasure vs the vector index

GDPR Art. 17 (erasure) and analogous rules assume you can *delete a record*. Vector indexes make that structurally hard, and embeddings create a second, inversion-readable "memory" of the deleted content.

### The regulatory clock has already run out

- **The EU AI Act's main body became applicable three days ago.** Per the implementation timeline, on **2 August 2026** *"the remainder of the AI Act starts to apply, except Article 6(1)"* — following prohibitions and AI-literacy duties (2 Feb 2025) and GPAI/governance/penalties (2 Aug 2025), with Art. 6(1) following on 2 Aug 2027. Operators of high-risk systems placed on market before 2 Aug 2026 must comply *"if subject to significant changes in their designs from this date onwards."* ([AI Act implementation timeline](https://artificialintelligenceact.eu/implementation-timeline/))
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  **Framing for the paper:** as of today (5 Aug 2026) the audit, documentation, and data-governance obligations are live, and the retrieval layer of every high-risk RAG deployment must satisfy them using framework primitives that do not exist. The grandfather clause is also a trap: "significant changes in design" is exactly what re-embedding after a vendor deprecation (d) looks like to a regulator.

### Deletion is a tombstone, in every substrate

- **Lucene/Elasticsearch: deletes are soft until segment merge.** Elasticsearch's own force-merge documentation states that on delete or update *"the old version is not immediately removed but instead soft-deleted and marked with a 'tombstone'. These soft-deleted documents are automatically cleaned up during regular segment merges."* It further warns that force-merging a write-active index can produce >5 GB segments ineligible for regular merges, after which *"the number of soft-deleted documents can then grow rapidly, resulting in higher disk usage and worse search performance,"* and *"can also make snapshots more expensive, since the new documents can't be backed up incrementally."* ([ES force merge](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-forcemerge.html))
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  This is a vendor-documented statement that **deleted data physically persists for an unbounded, merge-policy-dependent period** — and that the only way to force it out degrades the index and inflates snapshots. An erasure SLA cannot be built on this without explicit engineering.

- **HNSW deletion is a tombstone too.** hnswlib — the reference HNSW implementation beneath many vector DBs — exposes `markDelete`, a **soft delete** that leaves the vector in the graph. The canonical request, [hnswlib #4](https://github.com/nmslib/hnswlib/issues/4) *"add ability to delete elements from HNSW graph,"* was opened by ThomasDelteil on **2018-04-04**; the fetched page shows the request without a resolution in view. The surrounding issue tracker ([hnswlib issues](https://github.com/nmslib/hnswlib/issues?q=delete)) shows **#652** asking for an optional `no_deleted` flag to *filter out* deleted IDs from results (i.e. they can still be returned), **#541** fixing `addPoint` for `replace_deleted` (deleted slots are reused only on new inserts), and **#645/#650** on memory not being reclaimed on delete. Hard removal of a vector from an HNSW graph generally requires a **rebuild**, not an O(1) delete.
  *Severity: high. Taxonomy: security-governance. Label: documented-recurring.*
  An eight-year-old open request for true deletion in the substrate under much of the industry is a striking artifact. Caveat: I read the issue body, not the full comment thread, so I do not characterize maintainer intent.

- **Soft-deleted points also corrupt search correctness, not just compliance.** Qdrant's indexing documentation notes that when strict filters combine *or* **many soft-deleted points exist**, *"a combination of two or more strict filters might still lead to disconnected graph components."* ([Qdrant indexing](https://qdrant.tech/documentation/concepts/indexing/))
  *Severity: high. Taxonomy: retrieval-quality. Label: documented-recurring.*
  This is an underrated coupling: **accumulated tombstones degrade recall.** Deletion debt is simultaneously a compliance liability and a retrieval-quality regression, which means high-churn corpora (exactly the regulated ones with erasure requests) silently get worse retrieval over time.

- **Eventual consistency makes "deleted" a promise, not a state.** Pinecone's docs: *"Pinecone is eventually consistent, so there can be a slight delay before new or changed records are visible to queries"* ([Pinecone delete-data](https://docs.pinecone.io/guides/manage-data/delete-data)). Combine eventual consistency + soft deletes + replicas + snapshots (see (e)) and *proving* erasure becomes the hard part.
  *Severity: medium-high. Taxonomy: production-ops. Label: documented-recurring.*

### The embedding-memory problem, and the research response

- **Erasure must propagate to derived artifacts.** Even after a source document is deleted, its embedding may persist in caches, backups, replicas, and derived artifacts — and per (a)/vec2text that embedding is ~plaintext, recovering 92% of short inputs exactly. Erasure that deletes the row but not every derived vector is incomplete in a way that is *demonstrably* reversible, not theoretically so.
  *Severity: high. Taxonomy: security-governance. Label: architectural-inference (composed from two documented findings).*

- **The literature has started here, and it points at the corpus.** *When Machine Unlearning Meets RAG* — arXiv [2410.15267](https://arxiv.org/abs/2410.15267) — proposes *"a lightweight behavioral unlearning framework based on Retrieval-Augmented Generation"* that achieves forgetting by **modifying the external knowledge base rather than the model**, framed as constrained optimization, and works even for closed-source systems (ChatGPT, Gemini).
  *Severity: medium. Taxonomy: security-governance. Label: single-anecdote (one paper).*
  Notable inversion: RAG is proposed as the *mechanism* for unlearning, while the retrieval index is itself the thing that cannot be reliably unlearned. Nobody has closed that circle.

### What frameworks do today

Vector DBs expose `delete` APIs and document neither erasure guarantees nor graph-rebuild semantics. RAG frameworks expose **no** HIPAA/SOC2/audit-trail primitives — no first-class record of *who retrieved which documents, when, under which consent basis* — despite that being precisely what an EU AI Act or HIPAA audit asks for. Data residency is left to whichever region the vector DB happens to run in, with no per-record residency enforcement.

### Next-gen requirement

Erasure as a first-class, **verifiable** operation: crypto-shredding or index-rebuild-on-erasure with completion proofs; propagation across index, cache, snapshot, replica, and any derived/fine-tuned artifact; tombstone-debt monitoring (compliance *and* recall); residency-aware sharding with per-record policy; and a built-in retrieval audit trail (query → documents surfaced → consent basis → who saw it) sufficient for GDPR, HIPAA, SOC2, and the now-live EU AI Act.

---

## (d) Vendor-forced embedding deprecation & the re-embedding economics gap

A hosted embedding model is a **dependency that can be revoked**, and revocation forces a full corpus re-embed, because embeddings from different models are not comparable. This is documented and recurring across every major vendor.

### Documented sunsets

- **OpenAI first-generation embeddings: hard shutdown 4 January 2024.** The deprecations page lists **16 first-generation embedding/search/similarity models** — `text-similarity-{ada,babbage,curie,davinci}-001`, `text-search-{ada,babbage,curie,davinci}-{doc,query}-001`, `code-search-{ada,babbage}-{code,text}-001` — all with shutdown date **2024-01-04** ([OpenAI deprecations](https://developers.openai.com/api/docs/deprecations), model list fetched and confirmed). Every index built on any of those models had to be fully re-embedded.
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*

- **Cohere embed v2 retired 4 April 2026.** `embed-english-v2.0`, `embed-english-light-v2.0`, and `embed-multilingual-v2.0` retire effective **2026-04-04**, with v3.0 / embed-v4.0 as migration targets ([Cohere deprecations](https://docs.cohere.com/docs/deprecations)).
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*
  Four months ago as of this writing — this is a live, current migration, not history.

- **Azure/Microsoft Foundry: an 18-month clock, non-negotiable, ending in `410 Gone`.** The Foundry model-lifecycle policy states GA models have a retirement date *"set programmatically"* at **18 months** from launch; at retirement *"all inference returns `410 Gone`"*; notice is *"at least 60 days"*; the replacement model is only declared *"approximately 90–120 days before"* retirement; and on extensions: **"No. Retirement dates aren't extendable."** Microsoft also reserves the right to an *"emergency retirement with shortened notice"* for compliance/security issues. Embeddings are noted to have *"extended timelines and are handled differently from inference models."* ([Foundry model lifecycle](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/model-retirements))
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*
  Three fetched details deserve emphasis. **(i)** You may learn your replacement model only 90–120 days before your current one dies — you cannot plan a large re-embed further ahead than that. **(ii)** "Retirement dates aren't extendable" removes the enterprise escape hatch of negotiating an extension. **(iii)** *Provisioned deployments are not auto-upgraded* — the highest-commitment, most-enterprise tier bears the most manual migration work. I could not fetch the per-model schedule page (404), so **no specific `text-embedding-ada-002` date is asserted here**; the policy shape is the finding.

- (Google Vertex has a comparable legacy-embedding lifecycle for the `textembedding-gecko` family, but repeated attempts to fetch the specific per-model discontinuation rows failed, so **no Vertex date is asserted**. OpenAI, Cohere, and Azure independently establish the pattern.)

### The economics and tooling gap

- **Vendors have acknowledged re-embedding is a real cost — by paying it.** Two HN comments on OpenAI's GPT-4-GA announcement (2023-07-06, [36621598](https://news.ycombinator.com/item?id=36621598), [36623617](https://news.ycombinator.com/item?id=36623617)) report OpenAI committing to *"cover the financial cost of users re-embedding content with these new models."*
  *Severity: medium. Taxonomy: performance-cost. Label: single-anecdote — and flagged as secondary.* The originating OpenAI blog returned **403** on fetch, and the deprecations page I *did* read contains **no** such statement. So: treat "OpenAI paid for re-embedding" as reported-via-HN, not verified primary. The load-bearing inference is weaker but safe: a vendor offering to subsidize re-embedding is an admission that forced re-embedding is a material customer cost.

- **The tooling gap is visible in what practitioners build to route around it.** Community projects exist specifically to avoid re-embedding: *"EmbeddingAdapters"* offers *"cross-model retrieval, routing, interoperability, and migration without re-embedding an existing corpus"* (2026-03-11, [HN 47331142](https://news.ycombinator.com/item?id=47331142)); Retake noted that *"moving vectors often requires re-embedding the entire data source"* (2023-08-10, [HN 37079053](https://news.ycombinator.com/item?id=37079053), 88 pts); VectorAdmin pitched migration *"without paying for re-embedding"* (2023-10-11, [HN 37846029](https://news.ycombinator.com/item?id=37846029)).
  *Severity: high. Taxonomy: abstraction-design. Label: documented-recurring.*
  Three independent tools across three years exist to solve a problem the frameworks do not acknowledge. That is a textbook missing primitive: users are building adapters *because* no framework versions its embeddings.

- **Nothing in the mainstream stack versions the embedding.** No mainstream framework ships: embedding-model+version tags on stored vectors; background/rolling re-embedding with dual-read during cutover; re-embed cost/time estimation; or drift detection between model versions. A naive migration therefore requires re-embedding **everything at once**, because old and new vectors are not comparable and cannot coexist in one index.
  *Severity: high. Taxonomy: abstraction-design. Label: architectural-inference.*
  Note the collision with (h): if your embedder is a hosted API, you cannot be air-gapped *and* you cannot control your own migration clock.

### Next-gen requirement

Treat the embedding model as a **versioned, replaceable component**: vectors tagged with model + version + dimensionality; first-class rolling re-embed with dual-index/dual-read cutover and query-time version routing; migration cost/time estimators; cross-version drift detection so quality regressions are caught during cutover; and an abstraction that survives a provider sunsetting a model on 60 days' notice with a replacement named 90 days out.

---

## (e) Index backup, DR & migration ops

Vector stores are young databases; their backup/restore/migration paths are correspondingly immature. Several citations below are **PRs fixing** a failure mode — cited as evidence the failure mode existed and mattered enough to fix.

- **Cross-version restore is constrained by vendor policy, not just by bugs.** Elasticsearch's snapshot-restore documentation states plainly: *"You can't restore a snapshot to an earlier version of Elasticsearch"* and *"You can't restore an index to an earlier version of Elasticsearch"* — e.g. an 8.18.0-created index cannot go to an 8.15.0 cluster. A compatibility table governs which index versions restore into which cluster versions (a 6.8-created index restores into 9.0.0–9.5.0 but not 7.0–7.1), and older indices *"may require additional steps like using archive indices or searchable snapshots."* ([ES snapshot restore](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html))
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*
  **This upgrades a common inference into a documented constraint.** Restore is *forward-only*. There is no rollback path: if you upgrade a cluster and the new version has a retrieval regression, you cannot restore yesterday's snapshot into yesterday's version and carry on — you re-ingest and re-index from source. Every RAG DR plan built on "we have snapshots" is incomplete unless it also preserves the ability to rebuild from primary documents.

- **Weaviate — a write-loss window during online migration.** PR [#12211](https://github.com/weaviate/weaviate/issues?q=data+loss+corruption+recovery), *"cover the post-swap pre-flip write-loss window of enable-\* migrations,"* fixes a window during `enable-*` reindex migrations where concurrent writes could be **lost**. Companion PRs: **#12006** recovers from *corrupt chunk headers* instead of failing to load; **#12215** fixes empty range results served after an `enable-rangeable` reindex; **#12221** backfills null/length sidecars and BM25 tallies for pre-existing objects; **#11373** was an abandoned shard self-recovery effort.
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*
  Note **#12215** specifically: a migration that completes "successfully" and then serves **empty results** is the worst failure shape in retrieval — silent, not loud. A RAG app on top of it degrades to confident answers from zero context.

- **Milvus — recovery and restore under active hardening.** Issue [#52005](https://github.com/milvus-io/milvus/issues?q=data+loss+after+restart) reports *"bounded count(\*) returns incomplete result after StreamingNode recovery"*; **#51435** reports a delegator skipping schema propagation on `LoadSegments` reopen; PRs **#51527** (*"harden copy-segment restore pipeline against partial failures"*), **#51641** (*"guard copy-segment state transitions against stale snapshots"*), and **#51908** (*"stop dropping queued writes on pool reconfig"*) are restore/DR hardening fixes.
  *Severity: high. Taxonomy: production-ops. Label: documented-recurring.*

- **Force-merge inflates snapshot cost — the (c)/(e) coupling.** Per the ES force-merge docs quoted in (c), forcing tombstone reclamation *"can also make snapshots more expensive, since the new documents can't be backed up incrementally."*
  *Severity: medium. Taxonomy: production-ops. Label: documented-recurring.*
  Complying with an erasure request can therefore break your incremental-backup economics. Two "solved" subsystems, composed, produce a new problem — the recurring shape of this entire survey.

- **The cross-version / re-shard problem is structural.** Because HNSW/IVF structures are version- and parameter-specific, cross-version restore and re-shard are frequently **rebuilds**, not copies — expensive, slow, and error-prone, which is exactly where the bugs above concentrate. There is no framework-level abstraction for "back up my retrieval state and restore it *verifiably* on a new cluster or version."
  *Severity: high. Taxonomy: production-ops. Label: architectural-inference (supported by the ES policy above).*

### Next-gen requirement

DR as a **designed property**: consistent, verifiable snapshots with restore integrity checks (checksums, row-count and recall reconciliation); safe online reindex/migration with no write-loss window and no empty-result window; tested cross-version restore *plus* an explicit rebuild-from-source path since restore is forward-only; re-shard tooling that cannot silently drop segments; and DR drills as a framework-provided command rather than a runbook nobody has rehearsed.

---

## (f) Multilingual & non-English retrieval

English benchmarks hide a large per-language quality spread, and the cost of non-English retrieval is quantifiably higher. Both gaps are measured; neither is managed.

- **MIRACL — 18 languages, ~3× spread within a single method.** arXiv [2210.09984](https://arxiv.org/abs/2210.09984); results read from the [ar5iv body](https://ar5iv.labs.arxiv.org/abs/2210.09984). Dev-set nDCG@10 as summarized from Table 2: **BM25 ranges ~0.180 (French/Chinese) to ~0.551 (Finnish)**; **mDPR ranges ~0.272 (Indonesian) to ~0.512 (Chinese)**. Rankings differ sharply between lexical and dense methods — no single retriever is uniformly strong across languages, and Chinese is precisely where BM25 collapses while dense does well.
  *Severity: high. Taxonomy: retrieval-quality. Label: documented-recurring.*
  The operational consequence: **the hybrid-search weights you tuned on English are wrong for your other languages, in a direction that flips by language.** A single global `alpha` for sparse/dense fusion — what every framework offers — is guaranteed to be mis-set for most of a multilingual corpus.

- **MMTEB — 250+ languages, coverage skewed to high-resource.** arXiv [2502.13595](https://arxiv.org/abs/2502.13595) / [ar5iv body](https://ar5iv.labs.arxiv.org/abs/2502.13595). Covers *"over 500 quality-controlled evaluation tasks across 250+ languages,"* but the authors note the *"distribution is skewed toward high-resource languages,"* with low-resource languages appearing mainly in bitext-mining/classification rather than retrieval. Concrete inversion: on **MTEB(Indic)**, multilingual-e5-large-instruct (560M) scores **70.2 vs GritLM-7B's 60.2** — a 10-point gap in favor of the 12×-smaller model — while on MTEB(Europe) the larger model wins. Most models show a *"narrow multilingual focus ... disproportionally higher performance on ... European ones."*
  *Severity: high. Taxonomy: retrieval-quality. Label: documented-recurring.*
  **Pretraining language coverage dominates parameter count.** This breaks the default procurement heuristic ("pick the biggest/highest-MTEB-average embedder"), and no framework surfaces per-language scores at model-selection time.

- **Tokenization inequity is quantified: up to 15×.** *Language Model Tokenizers Introduce Unfairness Between Languages* — arXiv [2305.15425](https://arxiv.org/abs/2305.15425) (Petrov, La Malfa, Torr, Bibi). Abstract: *"The same text translated into different languages can have drastically different tokenization lengths, with differences up to 15 times in some cases. These disparities persist even for tokenizers that are intentionally trained for multilingual support."* Character- and byte-level models still show *"over 4 times the difference."* The paper names the consequences directly: unfairness *"in regard to the cost of accessing commercial language services, the processing time and latency, as well as the amount of content that can be provided as context."*
  *Severity: high. Taxonomy: performance-cost. Label: documented-recurring.*
  **This was previously an inference in this survey; it is now a cited 15× number.** For RAG specifically it compounds three ways at once: embedding cost per document, retrieval latency, and — most damagingly — **effective context budget**, meaning a fixed `top_k × chunk_size` configuration delivers materially less information per query in a high-fragmentation language than in English. Non-English users get a worse product at a higher price from the same configuration.

- **Even the CJK analyzer defaults are hedged by their own vendors.** Elasticsearch's language-analyzer documentation says of its built-in CJK support: *"You may find that `icu_analyzer` in the ICU analysis plugin works better for CJK text than the `cjk` analyzer,"* and advises users to experiment. ([ES language analyzers](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-lang-analyzer.html))
  *Severity: medium-high. Taxonomy: data-processing. Label: documented-recurring.*
  The default is documented as possibly-inferior, the better option requires installing a plugin, and the choice is left to a user who has no per-language metric to evaluate it with. That is the (f) failure in miniature: the knob exists, the guidance is "try it," and the measurement that would let you decide is absent.

- **Community silence.** HN Algolia returned **0 hits** for a multilingual-retrieval-quality query. Offered only as a weak signal that this is an under-discussed category among (largely anglophone) practitioners, not as evidence of absence — the query may simply be poorly matched.
  *Severity: low (as evidence). Taxonomy: dx-docs. Label: architectural-inference.*

### What frameworks do today

Default to English-centric analyzers/tokenizers and a single global embedding model; expose no per-language quality telemetry; do not treat CJK/RTL analyzer selection as a first-class, measured knob; and offer one global hybrid-fusion weight where MIRACL shows the correct weight inverts by language. Cross-lingual retrieval (query in language A, documents in language B) is delegated entirely to whatever the embedding model happens to do, unmeasured.

### Next-gen requirement

**Language-aware retrieval as a default, not a configuration project:** per-language analyzer/tokenizer selection with documented defaults; per-language retrieval-quality telemetry surfaced to the operator (so the MMTEB inversion is discoverable in *your* corpus); per-language hybrid-fusion weights; explicit, tested cross-lingual retrieval; token-budget accounting that normalizes for the 15× fragmentation gap so context allocation is fair; and model-selection tooling that reports per-language rather than average scores.

---

## (g) Tail latency & capacity engineering

Demos report median latency; SLOs are written against p99 under concurrent load. Published **absolute** p99 numbers for ANN indexes are scarce — and that scarcity is itself a finding.

- **Vendors publish relative, not absolute, tail numbers.** Qdrant's benchmark page claims *"highest RPS and lowest latencies in almost all scenarios"* and up to *"4x RPS,"* but publishes **no numeric p95/p99** (interactive charts only) and concedes bias (*"Probably, yes"*) ([qdrant benchmarks](https://qdrant.tech/benchmarks/); [repo](https://github.com/qdrant/vector-db-benchmark)). Timescale/Tiger's pgvector-vs-Pinecone writeup reports pgvectorscale at *"28x lower p95"* and 16× higher throughput vs Pinecone s1 **at 99% recall**, but only *"1.4x lower p95"* / 1.5× throughput vs Pinecone p2 **at 90% recall** — with **no absolute ms or QPS** ([tigerdata blog](https://www.tigerdata.com/blog/pgvector-vs-pinecone)).
  *Severity: medium-high. Taxonomy: performance-cost. Label: documented-recurring.*
  The 28× → 1.4× swing between two recall operating points is the whole lesson: **a latency number without a stated recall is meaningless**, and the industry's published numbers are overwhelmingly relative, self-run, and recall-ambiguous. There is no neutral, absolute, tail-latency-under-load leaderboard for retrieval.

- **HNSW requires full memory residency — stated by the vendor.** Elasticsearch's kNN documentation: *"for HNSW, all vector data must fit in the node's page cache for efficient performance."*  ([ES kNN search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html))
  *Severity: high. Taxonomy: performance-cost. Label: documented-recurring.*
  This is the cleanest possible statement of the RAG capacity model: **vector search is a memory-sized workload, and the cost curve is RAM, not disk.** It also explains cold-start cliffs mechanically — any restart, eviction, failover, autoscale event, or noisy neighbor that evicts the graph from page cache moves you onto the disk path, which is where p99 goes non-linear.

- **Cold-cache penalties, observed.** pgvector issue [#666](https://github.com/pgvector/pgvector/issues?q=slow+query) — *"search too slow when I clean the cache"* — is the user-facing form of the residency requirement above. pgvector **#259** documents the HNSW+filtering interaction where restrictive `WHERE` clauses degrade recall and latency.
  *Severity: high. Taxonomy: performance-cost. Label: documented-recurring.*

- **Filtered ANN is a documented structural hazard, with vendor-side mitigations that carry footguns.** Qdrant documents that *"a payload index and a vector index cannot completely address the challenges of filtered search,"* extends HNSW with *"additional edges based on indexed payload values,"* and still warns that combining strict filters (or accumulating soft-deleted points) *"might still lead to disconnected graph components"* — mitigated by an ACORN traversal that explores neighbors-of-neighbors. A `full_scan_threshold_kb` switches the planner to brute force when the filtered set is small. Critically: *"Payload indexes should be created before ingesting data,"* because the filterable HNSW index *"only benefits from additional filter-aware edges when it is generated after the payload indexes have been created."* ([Qdrant indexing](https://qdrant.tech/documentation/concepts/indexing/))
  *Severity: high. Taxonomy: performance-cost. Label: documented-recurring.*
  Two findings here. First, **filtered ANN — which is what every multi-tenant, ACL'd, date-scoped enterprise RAG query actually is — is the least benchmarked and most fragile path.** Second, an ordering requirement between payload-index creation and ingestion is a silent, unrecoverable-without-reindex performance footgun: get it wrong and you pay forever with no error message.

- **Concurrent write + query degrades tails.** Milvus issue [#49435](https://github.com/milvus-io/milvus/issues?q=latency+spike+compaction) — *"Query Timestamp lag too large during concurrent Strong count(\*) query with upsert"* — is direct evidence that mixing upserts with reads spikes query staleness/latency. HNSW/IVF were designed for read-mostly workloads; concurrent indexing, compaction, and segment flush contend with queries.
  *Severity: high. Taxonomy: performance-cost. Label: documented-recurring.*
  Continuously-ingesting RAG (the normal enterprise case: documents arrive all day) is therefore running the workload these indexes are *least* suited to, and benchmarking the one they are best at.

- **The research community moved to realistic workloads; the marketing did not.** *Results of the Big ANN: NeurIPS'23 competition* — arXiv [2409.17424](https://arxiv.org/abs/2409.17424) (Simhadri et al.) — states the competition deliberately *"addressed filtered search, out-of-distribution data, sparse and streaming variants of ANNS"* on new standard datasets *"with constrained computational resources,"* explicitly *"unlike prior challenges that emphasized scaling up classical ANN search."*
  *Severity: medium. Taxonomy: evaluation-observability. Label: documented-recurring.*
  The benchmark community already knows that filtered, streaming, and OOD retrieval are the real workloads. Vendor benchmark pages still overwhelmingly report static-corpus, unfiltered, in-distribution throughput.

### What frameworks do today

Expose no SLO-oriented primitives: no admission control or load shedding, no read/write resource isolation, no warmup or pin-in-memory operation, no p99-aware autoscaling signal, no recall-vs-latency operating-point declaration, and no honest tail-latency-under-concurrent-write harness. The `top_k` knob is exposed; the capacity model behind it is not.

### Next-gen requirement

Tail latency as a **declared SLO**: read/write resource isolation so ingestion cannot eat query latency; admission control and graceful load shedding; explicit warmup/cache-pinning with residency as a first-class, monitored resource; filtered-ANN that degrades predictably (and refuses to be silently mis-configured by index-creation ordering); a stated recall operating point attached to every latency number; and benchmark tooling that reports **absolute p99 under concurrent write+query at a stated recall** on filtered queries.

---

## (h) On-device & air-gapped retrieval

Genuinely under-served — but the interesting finding is an asymmetry: **the research literature has moved here faster than the frameworks have.**

### The research is no longer a single paper

- **EdgeRAG: Online-Indexed RAG for Edge Devices** — arXiv [2412.21023](https://arxiv.org/abs/2412.21023). Frames the constraints: edge devices have *"limited memory and processing power,"* and full precomputation of embeddings for large clusters is infeasible. EdgeRAG prunes within-cluster embeddings, generates them **on-demand at retrieval time**, and precomputes only large "tail clusters" with adaptive caching — reducing latency versus a baseline IVF index while fitting evaluated (BEIR) datasets in memory.
  *Severity: medium. Taxonomy: performance-cost. Label: documented-recurring.*

- **A cluster of 2025–2026 work, located via the arXiv API** (IDs returned by search, not recalled):
  - **MiniRAG** — arXiv [2501.06713](https://arxiv.org/abs/2501.06713): lightweight graph-based indexing matching heavier LLM-based pipelines while *"requiring only 25% of the storage space."*
  - **Efficient Distributed RAG** — arXiv [2504.11197](https://arxiv.org/abs/2504.11197): cloud-device split retrieval reporting *"1.9x greater gains"* over standalone with minimal first-token latency overhead.
  - **A Unified Model and Document Representation for On-Device RAG** — arXiv [2604.14403](https://arxiv.org/abs/2604.14403) (Killingback, Meshi, Li, Zamani, Karimzadehgan): reports parity with traditional RAG using *"1/10 of the context."*
  - **FD-RAG** — arXiv [2605.27432](https://arxiv.org/abs/2605.27432): federated dual-system RAG reporting latency reduced *"8.4× compared with strong local and federated baselines."*
  - **Real-Time Hybrid Retrieval in Hyperbolic Space for RAG on Edge Devices** — arXiv [2608.01450](https://arxiv.org/abs/2608.01450): interactive latencies over tens of thousands of documents without fine-tuned encoders.
  *Severity: medium. Taxonomy: performance-cost. Label: documented-recurring (five independent works).*
  Common thread across all five: **the binding constraint is memory and storage, and the winning move is trading precomputation for on-demand compute** — the exact inverse of the cloud RAG design assumption (precompute everything, keep it all resident, see (g)). A framework whose core abstractions assume a fully-materialized resident index cannot express any of these designs.

### The substrate exists; the framework story does not

- **Embedded vector stores are real and adopted.** `sqlite-vec` is *"an extremely small, fast vector search SQLite extension written in pure C with no dependencies"* that *"runs anywhere SQLite runs (Linux/MacOS/Windows, in the browser with WASM, Raspberry Pis, etc.)"* — **~8,000 GitHub stars, dual Apache-2.0/MIT**, but self-described as *"pre-v1, so expect breaking changes"* ([sqlite-vec](https://github.com/asg017/sqlite-vec)).
  *Severity: medium. Taxonomy: production-ops. Label: documented-recurring.*
  Note the trade being made: the on-device store that actually ships is brute-force-oriented and pre-v1. Meanwhile HN shows sustained appetite for in-process stores — *"Zvec: A lightweight, fast, in-process vector database"* (Alibaba) hit **226 points on 2026-02-13** ([HN 47000535](https://news.ycombinator.com/item?id=47000535)), and *"VectorVFS, your filesystem as a vector database"* took **279 points on 2025-05-05** ([HN 43896011](https://news.ycombinator.com/item?id=43896011)).

- **Air-gapped RAG is a governance requirement with no framework story.** Regulated, defense, and clinical deployments require the entire stack — embedder, index, LLM — to run with no external calls. This collides head-on with (d): **if your embedding model is a hosted API you cannot be air-gapped**, and re-embedding on-prem means shipping, versioning, and storing open-weight embedders yourself. No mainstream framework treats "fully offline, no-egress" as a supported, tested deployment mode with a bundled open-weight embedder and a verifiable no-egress guarantee.
  *Severity: medium-high. Taxonomy: production-ops. Label: architectural-inference.*
  There is also an under-appreciated **security upside** that no framework markets: an air-gapped deployment structurally eliminates the (a) exfiltration chains, because the outbound channel EchoLeak and the Slack AI attack both depend on does not exist. "No egress" is a retrieval-security primitive, not just a compliance checkbox.

### Next-gen requirement

Offline-first as a **supported, tested mode**: bundled open-weight embedders (removing the (d) vendor dependency entirely); memory-adaptive indexing that can trade precomputation for on-demand compute (EdgeRAG/MiniRAG-style) rather than assuming a resident materialized index; a verifiable no-egress guarantee enforced at the framework boundary; and the same erasure and audit properties (c) demands, since air-gapped deployments are disproportionately the regulated ones.

---

## Cross-category interactions: where the real incidents live

The most important structural claim in this file is that these categories **compound**, and compound failures are invisible to per-category owners. Documented couplings found above:

| Coupling | Mechanism | Evidence basis |
| --- | --- | --- |
| (c) → (g) | Accumulated soft-deleted points cause HNSW graph components to disconnect, degrading recall | Qdrant indexing docs |
| (c) → (e) | Force-merging to reclaim tombstones breaks incremental snapshots and inflates backup cost | ES force-merge docs |
| (d) → (c) | A forced re-embed is plausibly a "significant change in design," re-triggering EU AI Act high-risk obligations for grandfathered systems | AI Act timeline + vendor deprecations |
| (d) → (h) | A hosted embedder makes air-gapping impossible and surrenders the migration clock | Azure lifecycle + air-gap requirement |
| (a) → (b) | Any naive click-feedback loop becomes a poisoning channel; AgentPoison shows <0.1% suffices | AgentPoison + biased-feedback LTR |
| (a) → (h) | No-egress deployment structurally kills the exfiltration chains EchoLeak/Slack AI depend on | CVE-2025-32711 + PromptArmor |
| (f) → (g) | 15× tokenization fragmentation inflates latency and cost per query in non-English languages | Petrov et al. |
| (e) → (g) | "Successful" migrations that serve empty results look like a quality bug, not an ops bug | Weaviate #12215 |

*Severity: high. Taxonomy: abstraction-design. Label: architectural-inference (each coupling composed from documented endpoints).*

**This table is the strongest argument for a unified next-generation framework rather than eight point solutions.** Every coupling crosses an ownership boundary: the vector-DB team owns tombstones but not recall SLOs; the compliance team owns erasure but not backup economics; the security team owns egress but not embedder procurement. A framework is the only layer positioned to see both ends.

---

## Community sentiment over time

Sentiment was reconstructed from the HN Algolia API (points/comments/dates are as returned). The arc is legible.

**2021–2022 — curiosity.** *"A gentle introduction to vector databases"* (133 pts, 2022-02-22); *"Embeddinghub: a vector database built for ML embeddings"* (118 pts, 2021-09-16). Framing is educational; no production discourse.

**2023 — the boom, and immediate skepticism about the category.** *"What is a Vector Database?"* (409 pts, 2023-05-05), *"Vector database built for scalable similarity search"* / Milvus (184 pts, 2023-03-25), Qdrant's $28M Series A (131 pts / **167 comments**, 2024-01-23). But the pushback is *simultaneous*, not later: *"Do you need a vector database?"* (201 pts, 2023-04-13), *"Do we really need a specialized vector database?"* (147 pts, 2023-08-12), *"Every database will become a vector database sooner or later"* (232 pts, 2023-10-03), *"Vector databases: analyzing the trade-offs"* (170 pts, 2023-08-19). **The "just use Postgres" argument is as old as the category itself.**

**2024 — consolidation skepticism peaks.** *"Are we at peak vector database?"* (235 pts / 142 comments, 2024-01-24) and *"Vector databases are the wrong abstraction"* (493 pts / 90 comments, 2024-10-29) — the latter one of the highest-scoring critical posts in the space, and notably an *abstraction* critique, aligning with the framework autopsies' central complaint.

**2025 — production disillusionment, security shock, and infra re-platforming.** *"Are we pretending RAG is ready, when it's barely out of demo phase?"* (2025-07-27, [44701172](https://news.ycombinator.com/item?id=44701172)) captures the mood precisely: *"Most setups still feel like glorified notebooks stitched together with hope and vector search,"* citing irrelevant chunks, hallucinations, brittle evaluations, and breakage under real conditions. **EchoLeak lands at 228 pts / 86 comments (2025-06-11)** — the security category's arrival in mainstream practitioner consciousness. *"Will Amazon S3 Vectors kill vector databases or save them?"* (280 pts / 122 comments, 2025-09-08) marks the commoditization question. Vectara reports enterprises citing hallucinations as *"one of the top items preventing them from deploying RAG applications in production"* (2024-08-06).

**2026 — pragmatic embedded/local turn, and workarounds for missing primitives.** *"Zvec: a lightweight, fast, in-process vector database"* (226 pts, 2026-02-13); *"GibRAM – in-memory ephemeral GraphRAG runtime"* (60 pts, 2026-01-18) motivated by flat RAG that *"often fail[s] to retrieve related articles together"* in regulation-heavy documents; *"EmbeddingAdapters"* for migration *"without re-embedding an existing corpus"* (2026-03-11). Security tooling appears bottom-up: *"LLM AuthZ Audit"* flags *"RAG retrievals without document-level access controls"* (2026-02-16); a red-teaming methodology states *"indirect injection is underappreciated"* for RAG systems (2026-02-17).

**Two honest observations about what is *absent* from community discourse.** HN Algolia returned **0 hits** for both GDPR-erasure-vs-embeddings and multilingual-retrieval-quality queries. These are weak signals (query-phrasing artifacts are entirely possible) but they are consistent with the survey's core thesis: (c) and (f) are the two categories with the strongest *formal* evidence (statute; benchmark numbers) and the weakest *practitioner* discourse. **The categories that bite hardest in regulated, non-anglophone production are the ones the anglophone open-source community discusses least** — which is exactly how they end up missing from framework roadmaps.

---

## Benchmarks & third-party evaluations

What exists, and what conspicuously does not.

**Adversarial (a) — benchmarks exist, are not used as gates.** PoisonedRAG (90% ASR at 5 docs), AgentPoison (>80% ASR at <0.1% poisoning), adversarial passages (>94% misled at 50 passages), jamming/blocker documents, vec2text (92% exact recovery at 32 tokens), and membership inference all publish quantified results. **No RAG framework ships any of these as a pre-deployment test.** The jamming authors state the gap explicitly: existing LLM safety metrics *"do not capture their vulnerability to jamming."*

**Multilingual (f) — the best-instrumented category.** MIRACL (18 languages) and MMTEB (250+ languages, 500+ tasks) provide per-language retrieval numbers, and MMTEB documents the parameter-count-vs-language-coverage inversion (multilingual-e5-large-instruct 70.2 vs GritLM-7B 60.2 on MTEB(Indic)). Petrov et al. quantify tokenization inequity at up to 15×. **The measurement problem is solved; the plumbing to surface it per-deployment is missing.**

**Tail latency (g) — actively obscured.** Vendor benchmarks are self-run, relative, and recall-ambiguous (Qdrant publishes no numeric p95/p99 and concedes bias; Tiger's 28×→1.4× swing is entirely explained by moving from 99% to 90% recall). The Big ANN NeurIPS'23 competition did test filtered/OOD/sparse/streaming variants under constrained resources — the right workloads — but its findings have not propagated into how vendors report or how frameworks configure. **There is no neutral absolute-p99-under-concurrent-write-at-stated-recall benchmark for retrieval. This is the single largest measurement gap in the survey.**

**On-device (h) — emerging, incomparable.** Five works report improvements against their own baselines (1/10 context, 25% storage, 8.4× latency, 1.9× gains) with no shared benchmark, so cross-paper comparison is impossible.

**(b), (c), (d), (e) — no benchmarks at all.** There is no standard evaluation for: whether a system learns from feedback; whether erasure completes verifiably; what a forced re-embed costs in money, time, and quality drift; or whether a snapshot restores correctly across versions. **Four of eight categories are entirely unmeasured, which is the most direct explanation for why they are unmanaged.** You cannot put an unmeasured property on a roadmap.

---

## Lessons for a next-generation framework

1. **The corpus is an adversarial write surface** (a). Provenance-signed chunks, per-source trust tiers, retrieval-time poisoning *and jamming* detection, vector-at-rest confidentiality assuming inversion succeeds, cache/index ACL parity, and a structural data-instruction boundary. Evidence floor: 5 documents in millions → 90% ASR; <0.1% poisoning → >80% agent ASR; CVE-2025-32711 at CVSS 9.3 in the largest deployed enterprise RAG product. **Availability (jamming) must be measured, not assumed.**
2. **Retrieval must learn, safely** (b). A debiased, adversary-aware feedback loop — IPS/counterfactual click models or bandits over retrievers and rerankers — plus a plan for deployments far below the 250k-events/90-days floor that Google's own commerce search requires. The capability exists inside these vendors; it was never wired to the generative product.
3. **Erasure and audit are first-class verifiable operations** (c). Not a best-effort delete against a tombstoned graph. Completion proofs, propagation to caches/snapshots/replicas/derived artifacts, tombstone-debt monitoring (it degrades recall as well as compliance), residency-aware sharding, and a retrieval audit trail. The EU AI Act's main body became applicable **three days before this was written**.
4. **The embedding model is a versioned, replaceable dependency** (d). Model+version tags on vectors, rolling re-embed with dual-read cutover, cost/time estimation, drift detection. Design for a 60-day retirement notice with the replacement named only 90 days out, no possibility of extension, and `410 Gone` at the end.
5. **DR is a designed property** (e). Verifiable snapshots with recall reconciliation, no write-loss *and no empty-result* window during online migration, and — because vendor restore is documented forward-only — an explicit rebuild-from-source path as a first-class capability rather than a runbook.
6. **Retrieval is multilingual by default** (f). Per-language analyzers, per-language quality telemetry, per-language hybrid-fusion weights (MIRACL shows the correct weighting inverts by language), tested cross-lingual retrieval, and token-budget normalization against a documented 15× fragmentation gap.
7. **p99 under concurrent write on filtered queries is the real SLO** (g). Read/write isolation, admission control, memory residency as a monitored first-class resource, filtered-ANN that cannot be silently mis-configured, and every latency number carrying its recall operating point.
8. **Offline-first is a supported mode** (h). Bundled open-weight embedders, memory-adaptive indexing that trades precomputation for on-demand compute, and a verifiable no-egress boundary — which doubles as the strongest available exfiltration defense.
9. **Design for the couplings, not the categories** (cross-cutting). The interaction table above shows eight documented couplings, each crossing an ownership boundary that guarantees no component team will fix it. A framework is the only layer that sees both ends. **This, more than any single category, is the argument for a unified next-generation framework.**
10. **Measure the four unmeasured categories** (b, c, d, e). Ship benchmarks for feedback-loop efficacy, erasure verifiability, re-embed cost/drift, and restore correctness. Nothing gets managed until it gets measured, and the ordering of this survey's evidence quality maps almost perfectly onto the ordering of framework attention.

The through-line: **every mainstream RAG framework optimizes the ingest-then-demo happy path.** These eight categories are where production, adversaries, regulators, vendors, scale, and the edge break that path — and they break *across* framework boundaries, which is precisely why no per-framework autopsy catches them.

---

## Sources

*All URLs below were fetched in this session unless marked. Fetch failures are noted so no claim rests on an unread page.*

**Standards & regulation**
- OWASP LLM08:2025 Vector and Embedding Weaknesses — https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/
- EU AI Act implementation timeline (2 Aug 2026 general application) — https://artificialintelligenceact.eu/implementation-timeline/

**Adversarial ML on the retrieval substrate (a)**
- PoisonedRAG (USENIX Sec 2025) — https://arxiv.org/abs/2402.07867
- AgentPoison (poisoning agent memory / KB) — https://arxiv.org/abs/2407.12784
- Poisoning Retrieval Corpora by Injecting Adversarial Passages (EMNLP 2023) — https://arxiv.org/abs/2310.19156
- Phantom (trigger-conditioned backdoor on RAG) — https://arxiv.org/abs/2405.20485
- Machine Against the RAG: jamming with blocker documents (USENIX Sec 2025) — https://arxiv.org/abs/2406.05870
- vec2text / Text Embeddings Reveal (Almost) As Much As Text (EMNLP 2023) — https://arxiv.org/abs/2310.06816
- The Good and The Bad: Privacy Issues in RAG — https://arxiv.org/abs/2402.16893
- SAGE: mitigating RAG privacy via pure synthetic data — https://arxiv.org/abs/2406.14773
- Membership Inference Attacks Against RAG Systems (ICISSP 2025) — https://arxiv.org/abs/2405.20446
- CVE-2025-32711 (EchoLeak, M365 Copilot; NIST 7.5 / Microsoft 9.3) — https://nvd.nist.gov/vuln/detail/CVE-2025-32711
- EchoLeak disclosure (Aim Labs) via HN 44250774 — https://www.aim.security/lp/aim-labs-echoleak-blogpost
- EchoLeak coverage — https://www.bleepingcomputer.com/news/security/zero-click-ai-data-leak-flaw-uncovered-in-microsoft-365-copilot/ · https://fortune.com/2025/06/11/microsoft-copilot-vulnerability-ai-agents-echoleak-hacking/
- Slack AI data exfiltration (PromptArmor, Aug 2024) — https://promptarmor.substack.com/p/data-exfiltration-from-slack-ai-via
- ConfusedPilot (enterprise RAG corruption + cache leak) — https://arxiv.org/abs/2408.04870
- Google Antigravity indirect-injection discussion — https://news.ycombinator.com/item?id=46051614
- *Fetch failed:* MSRC advisory for CVE-2025-32711 (JS-rendered) — Microsoft's own remediation language is therefore not quoted.

**Relevance feedback & online learning (b)**
- Unbiased Learning-to-Rank with Biased Feedback (Joachims et al., 2016) — https://arxiv.org/abs/1608.04468
- Two-tower LTR degraded by biased production feedback — https://arxiv.org/abs/2506.20501
- Google AI Commerce Search / Retail user events (250k events / 90 days minimum) — https://docs.cloud.google.com/retail/docs/user-events
- LangChain issue search, no relevance-feedback results (weak negative evidence) — https://github.com/langchain-ai/langchain/issues?q=relevance+feedback+re-ranking+user+feedback

**Regulatory & data lifecycle (c)**
- Elasticsearch force merge — tombstones, cleanup only on segment merge, snapshot cost — https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-forcemerge.html
- hnswlib #4, "add ability to delete elements from HNSW graph" (opened 2018-04-04) — https://github.com/nmslib/hnswlib/issues/4
- hnswlib deletion issues (#652, #541, #645, #650) — https://github.com/nmslib/hnswlib/issues?q=delete
- Qdrant indexing — soft-deleted points and disconnected graph components — https://qdrant.tech/documentation/concepts/indexing/
- Pinecone delete-data / eventual consistency — https://docs.pinecone.io/guides/manage-data/delete-data
- When Machine Unlearning Meets RAG — https://arxiv.org/abs/2410.15267

**Vendor embedding deprecation (d)**
- OpenAI deprecations — 16 first-gen embedding models, shutdown 2024-01-04 (model list confirmed) — https://developers.openai.com/api/docs/deprecations
- Cohere deprecations — embed v2.0 retired 2026-04-04 — https://docs.cohere.com/docs/deprecations
- Microsoft Foundry model lifecycle — 18-month GA clock, `410 Gone`, 60-day notice, non-extendable, provisioned not auto-upgraded — https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/model-retirements
- Re-embedding-avoidance tooling: EmbeddingAdapters (https://news.ycombinator.com/item?id=47331142), Retake (https://news.ycombinator.com/item?id=37079053), VectorAdmin (https://news.ycombinator.com/item?id=37846029)
- OpenAI covering re-embedding cost — reported only via HN comments 36621598 / 36623617; **originating blog returned 403 and the deprecations page contains no such statement.**
- *Fetch failed:* Azure per-model retirement schedule (404) — no `text-embedding-ada-002` date asserted. Google Vertex `textembedding-gecko` rows — no Vertex date asserted.

**Index backup, DR & migration (e)**
- Elasticsearch snapshot/restore version compatibility — restore is forward-only — https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html
- Weaviate migration/corruption PRs (#12211, #12006, #12215, #12221, #11373) — https://github.com/weaviate/weaviate/issues?q=data+loss+corruption+recovery
- Milvus recovery/restore issues + PRs (#52005, #51435, #51527, #51641, #51908) — https://github.com/milvus-io/milvus/issues?q=data+loss+after+restart

**Multilingual & non-English retrieval (f)**
- MIRACL (18 languages) — https://arxiv.org/abs/2210.09984 · body: https://ar5iv.labs.arxiv.org/abs/2210.09984
- MMTEB (250+ languages) — https://arxiv.org/abs/2502.13595 · body: https://ar5iv.labs.arxiv.org/abs/2502.13595
- Language Model Tokenizers Introduce Unfairness Between Languages (up to 15×) — https://arxiv.org/abs/2305.15425
- Elasticsearch language analyzers — ICU may work better than built-in `cjk` — https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-lang-analyzer.html

**Tail latency & capacity engineering (g)**
- Elasticsearch kNN — "all vector data must fit in the node's page cache" — https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html
- Qdrant indexing — filterable HNSW, ACORN, `full_scan_threshold_kb`, payload-index ordering requirement — https://qdrant.tech/documentation/concepts/indexing/
- Qdrant benchmarks (no absolute p95/p99 published; bias conceded) — https://qdrant.tech/benchmarks/ · repo: https://github.com/qdrant/vector-db-benchmark
- Timescale/Tiger pgvector vs Pinecone (relative p95, recall-dependent 28×→1.4×) — https://www.tigerdata.com/blog/pgvector-vs-pinecone
- Milvus concurrent upsert+query timestamp lag (#49435) — https://github.com/milvus-io/milvus/issues?q=latency+spike+compaction
- pgvector cold-cache slowdown (#666), HNSW+filtering (#259) — https://github.com/pgvector/pgvector/issues?q=slow+query
- Results of the Big ANN: NeurIPS'23 competition (filtered/OOD/sparse/streaming tracks) — https://arxiv.org/abs/2409.17424

**On-device & air-gapped (h)**
- EdgeRAG — https://arxiv.org/abs/2412.21023
- MiniRAG — https://arxiv.org/abs/2501.06713
- Efficient Distributed RAG — https://arxiv.org/abs/2504.11197
- A Unified Model and Document Representation for On-Device RAG — https://arxiv.org/abs/2604.14403
- FD-RAG (federated dual-system RAG) — https://arxiv.org/abs/2605.27432
- Real-Time Hybrid Retrieval in Hyperbolic Space for RAG on Edge Devices — https://arxiv.org/abs/2608.01450
- sqlite-vec (~8k stars, Apache-2.0/MIT, pre-v1) — https://github.com/asg017/sqlite-vec

**Community sentiment (HN Algolia API; points/comments/dates as returned)**
- "Vector databases are the wrong abstraction" (493 pts, 2024-10-29) — https://news.ycombinator.com/item?id=41985176
- "Are we at peak vector database?" (235 pts / 142 comments, 2024-01-24) — https://news.ycombinator.com/item?id=39119198
- "Will Amazon S3 Vectors kill vector databases or save them?" (280 pts, 2025-09-08) — https://news.ycombinator.com/item?id=45169624
- "Do you need a vector database?" (201 pts, 2023-04-13) — https://news.ycombinator.com/item?id=35550567
- "Every database will become a vector database sooner or later" (232 pts, 2023-10-03) — https://news.ycombinator.com/item?id=37747534
- "Are we pretending RAG is ready, when it's barely out of demo phase?" (2025-07-27) — https://news.ycombinator.com/item?id=44701172
- "Zvec: a lightweight, fast, in-process vector database" (226 pts, 2026-02-13) — https://news.ycombinator.com/item?id=47000535
- "VectorVFS, your filesystem as a vector database" (279 pts, 2025-05-05) — https://news.ycombinator.com/item?id=43896011
- "GibRAM – in-memory ephemeral GraphRAG runtime" (60 pts, 2026-01-18) — https://news.ycombinator.com/item?id=46665393
- "LLM AuthZ Audit" — flags RAG retrieval without document-level ACLs (2026-02-16) — https://news.ycombinator.com/item?id=47031695
