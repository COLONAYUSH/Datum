# Strata — one substrate, two write policies, a bitemporal ledger underneath both

*Design proposal for the Reimagining-RAG synthesis. Stance: memory-OS. Author pass: 2026-08-06.*

## Design axioms

1. **The write path is the failure surface, not the read path.** Read-path IR — ANN indexing, hybrid search, rerankers — is decades-mature (`research/01-landscape/indexing-vector-databases.md`, Phase 1–4 lineage: PQ→HNSW→DiskANN→RaBitQ is forty years of continuous, replicated progress). Every catastrophic failure in the taxonomy — silent drops, concurrent corruption, authority collapse, unverifiable erasure — lives on the write path (`common-issues.md` CI-04, CI-05, CI-06, CI-07, CI-12c). `memory-context-engineering.md` §"Open problems" #2 states it as a field-level gap: *"Read-path (retrieval) is mature; the write path... has no formal framework."* Strata is a write-path framework first and a retrieval framework second.

2. **Corpus and memory share one read path but need distinct, typed write policies per source class — not one write model.** `memory-context-engineering.md` §"The convergence thesis" lists real evidence *against* full unification: bi-temporal validity is "meaningless for a static corpus" *in isolation*, and memories are self-generated while corpora are externally grounded — these are different write disciplines, not the same one. Its own synthesis is the design to build: *"memory and retrieval share a read path... A unified framework should have one read abstraction and an explicit, first-class write/lifecycle abstraction."* Strata takes that literally: one `retrieve()`, one `WriteOp` algebra, and source-specific write **policies** (parse-and-supersede for documents, extract-and-consolidate for conversation) plugged into the same transactional machinery.

3. **Every write is a transaction with named, typed semantics — never an implicit side effect of "the LLM decided to remember."** Mem0 #5245 (silent drop on partial embedding failure) and #4892 (concurrent `AsyncMemory` writes corrupting the Qdrant HNSW index) are exactly what "extract → store" produces without transactional discipline (`common-issues.md` CI-12c; `research/02-frameworks/memory-and-localfirst.md` §Lessons #1: *"Silent drops... and concurrent-write corruption... are disqualifying in a system whose only job is not forgetting."*).

4. **Bitemporal validity (valid-time + transaction-time) is a base-representation property, not a vendor add-on.** Exactly one system in the entire corpus treats time as first-class — Zep/Graphiti — and it is scoped to conversational edges and self-reported (`memory-context-engineering.md`, comparison table). CI-07's defect — no framework records which vectors/facts came from which version, when — is a temporal-modeling gap wearing a lineage costume. Valid-time is what makes *supersession* expressible: "guideline v2 replaces v1 as of date D" is the enterprise-document case, not a conversational nicety, and it is exactly what CI-07 asks for and nobody ships.

5. **Consolidation is a reversible, drill-down-able view over retained ground truth — summaries are indexes, never replacements.** "Consolidation is lossy and irreversible" is named failure mode #4 in `memory-context-engineering.md`; CI-06's next-gen requirement demands derived artifacts stay traceable to source, not compacted away.

6. **Provenance and policy propagate through every derivation by construction; no transform may silently drop them.** CI-04's mechanism is precisely "no per-source trust label that survives chunking, reranking, compression"; CI-02's fix is "cross-stage contract validation rejecting destructive compositions." Same defect, same fix, applied to trust and to structure alike.

7. **Forgetting is a cryptographic guarantee, not an index operation.** Ghost Vectors (`research/01-landscape/private-federated-personalized.md` §Failure modes #2) shows soft-deleted embeddings remain reconstructible in HNSW; CI-06 names "verified erasure in ANN indexes" an unsolved open problem. Strata does not solve that problem — it makes it irrelevant: encrypt every record at the ground layer, shred the key on `forget`, and the index becomes noise regardless of what the ANN algorithm internally retains.

8. **Retrieval is a typed, budgeted, principal-scoped tool call shaped like the tools models already trust — not a hand-wired pipeline stage.** Non-negotiable per the brief: agent policies consume retrieval via tools, and models' training priors distrust custom tools. `research/02-frameworks/agent-framework-retrieval.md` §Lessons #6: *"Retrieval tools compete with grep in the model's learned habits... interfaces should mimic familiar affordances."*

## The core insight

The field built two stacks — "RAG" for documents, "memory" for conversations — and staffed them with two different kinds of engineers. RAG teams came from information retrieval and spent a decade maturing the read path: quantization, graph indexes, hybrid fusion, rerankers. Memory teams came from applied ML and spent two years building extraction pipelines: an LLM reads a conversation, decides what's worth keeping, and writes it to a vector store. Neither team built a *write path* in the database-engineering sense — write-ahead durability, atomic supersession, idempotency, versioned schema migration, verifiable deletion. RAG didn't need one because its founding assumption was a mostly-immutable corpus, batch-ingested once (`common-issues.md` CI-06 root cause: *"every layer assumed an immutable corpus because every layer was built from an immutable-corpus demo"*). Memory didn't build one because its founding assumption was that an LLM deciding what's true *is* the transaction (CI-12 root cause: *"memory systems were built by ML engineers... not by database engineers"*).

Both assumptions are false in production, and they fail in the same shape: silently. A stale vector keeps getting retrieved after its source document is edited (Flowise #3570, CI-06). A hallucinated preference gets re-extracted as ground truth 808 times because nothing distinguishes "the user said this" from "we previously guessed this" (Mem0 forensic audit, CI-04). A community summary in a knowledge graph merges two entities and nothing downstream can tell (`research/01-landscape/graph-structured-rag.md` §"The KG-quality problem": *"a bad merge or missed merge silently corrupts every downstream traversal, unlike a bad chunk which affects one retrieval"*). These are not three defects; they are one defect — **no write path exists that treats provenance, authorization, and time as load-bearing** — expressed in three product categories that never talked to each other.

The compounding failure is what the brief calls **Authority Collapse**: consolidation is the one write operation every serious memory and every serious graph-RAG system performs (summarize the week, cluster the communities, merge the entities), and it is also the one operation the corpus proves strips provenance and ACLs *simultaneously* — because both are metadata bolted onto a flat string, and summarization keeps the string and drops the metadata. `common-issues.md`'s own causal map names this exactly: *"the flat-text cascade (CI-02 → CI-04 → CI-26)... nothing can distinguish 'user said this' from 'attacker planted this' from 'we hallucinated this last week' — which is why memory poisoning compounds."* Consolidation isn't adjacent to the trust boundary; it *is* where the trust boundary is currently being erased.

So the fix is not "merge RAG and memory into one undifferentiated blob" — the corpus's own convergence-thesis evidence *against* unification (static corpora don't need bi-temporal edges; memories are self-generated, corpora are externally grounded) is correct and should not be argued past. The fix is narrower and load-bearing: **build the write-path machinery once — a transactional ledger with typed operations, bitemporal versioning, inherited provenance, and cryptographic forgetting — and let each source class plug in its own write *policy*** (a document's policy is parse → chunk → supersede-on-edit; a conversation's policy is extract → consolidate → promote-on-confirmation). One read path serves both, because by the time a fact is in the ground store, "was it a Slack message or a PDF" is provenance metadata, not a different query language. This is exactly the shape `memory-context-engineering.md`'s own synthesis converges on independently of this project's stance — which is the strongest available evidence that it's the right cut, not merely a house style.

Nobody ships this today for a specific, structural reason: it's invisible in a demo (`common-issues.md`'s root-engine #2 — "the demo as objective function" — selected batch one-shot ingest, frozen defaults, and abstention-free retrieval precisely because production discipline has no five-minute payoff), and it's the opposite of what open-core economics rewards (root-engine #1 — evaluation, authorization, and lifecycle discipline are the paywalled tier everywhere they exist at all). A write-path-first framework is a bet that the agentic era — where a *population* of agents writes to a shared, mutating, permissioned substrate continuously, not a human clicking "ingest" once — makes this bet pay off for the first time.

## Architecture

```
                              AGENT / AGENT POPULATION
                                        |
                            (typed tool calls only — §Core abstractions #6)
                                        v
+-------------------------------------------------------------------------+
| L6  AGENT TOOL SURFACE                                                  |
|     recall() remember() forget() supersede() ask_sufficiency()          |
|     grep/file-shaped: snippets-with-context, path-like record ids       |
+-------------------------------------------------------------------------+
                    |  retrieve(intent, principal, policy, budget)
                    v
+-------------------------------------------------------------------------+
| L5  READ PATH  (one path, corpus + memory alike)                        |
|     router -> {point-lookup, lexical, vector, graph*, agentic-multihop} |
|     -> principal-scope NAMESPACE selection (partition, not predicate)   |
|     -> budget-tiered escalation -> EvidenceState (typed, calibrated)    |
+-------------------------------------------------------------------------+
        ^ serves from generation pointer               | every call emits
        |  (O(1) dereference, no per-row time predicate) a typed trace ->[EVAL/OBS]
+-------------------------------------------------------------------------+
| L4  DERIVED VIEWS — generation-partitioned, disposable, rebuildable,    |
|     lineage-tagged                                                      |
|     vector index | lexical (BM25) index | *optional* graph view |       |
|     ConsolidationView (drill-down pointer back into L2, zero-cost       |
|     unless followed)                                                    |
+-------------------------------------------------------------------------+
        ^ async, versioned, replayable derivation jobs
+-------------------------------------------------------------------------+
| L3  WRITE ORCHESTRATOR                                                  |
|     admission control (schema + precondition check, quarantine)         |
|     -> WriteOp{assert, supersede, invalidate, consolidate, forget}      |
|     -> per-source-class WRITE POLICY                                    |
|        (doc: parse/chunk/supersede-on-edit | convo: extract/consolidate)|
+-------------------------------------------------------------------------+
        | commits atomically
        v
+-------------------------------------------------------------------------+
| L2  GROUND STORE — canonical, bitemporal Records                        |
|     content-addressed id, envelope-encrypted per policy scope, MVCC     |
|     (new version; old record's tx_to closed in the same transaction)    |
|     the ONLY layer that is "mutable," and only by supersession          |
+-------------------------------------------------------------------------+
        | appends
        v
+-------------------------------------------------------------------------+
| L1  WAL — append-only, content-hashed event log                         |
|     {op, payload, principal, valid_time, source, causal-parent}         |
+-------------------------------------------------------------------------+
                                        |
                          L0  OBJECT STORAGE (source of truth)

  cross-cutting: LINEAGE MANIFEST tracks L2 -> L4 derivations for
  rebuild-from-scratch (CI-07) and forget-propagation (CI-06)

  cross-cutting: EVAL/OBSERVABILITY taps L1 (writes), L3 (admission
  decisions), L5 (per-stage traces) to run a self-bootstrapping
  regression loop as a default artifact, not a paid tier (CI-01, CI-11)
```

*Graph view is optional and off by default — see anti-scope.

**Why "fast enough for agent loops" isn't an adjective here.** The three historically-slow ingredients of a governed substrate — temporal predicates, provenance checks, and reversible consolidation — are each moved off the hot path by construction, not by hoping the implementation is clever:

- **Bitemporal reads don't evaluate a predicate at read time.** Writes are assigned to a monotonically increasing *generation*. Every derived view (L4) is built once per generation and tagged with the tx-range it's valid for; the tx-range is a property of the *partition* (which generation's view you're reading), not a per-row column. A "now" read — the overwhelming majority of agent-loop queries — dereferences the current generation pointer, an O(1) lookup, and never touches `valid_from <= t < valid_to` per record. An "as of last quarter's guideline" read routes to a named prior generation's frozen view instead of live-evaluating temporal logic; it is deliberately allowed to be slower, because it is the rare path.
- **Drill-down costs nothing unless followed.** A `ConsolidationView`'s pointer back to the ground records it summarizes (§Core abstractions #4) is a stored reference, not a materialized join — resolving it is an explicit, opt-in operation, so consolidated retrieval pays no tax for auditability it didn't ask for.
- **Provenance and ACL are O(records), not O(tokens).** The `ProvenanceCapsule` (§Core abstractions #1) is a fixed-size struct that rides as index metadata alongside a vector or graph edge — six or seven scalar/short-string fields, checked once per candidate, independent of chunk length. This is the same shape RaBitQ uses for per-distance error bounds (`indexing-vector-databases.md` §1, Open problem #2): a compact, constant-size annotation attached at the index level, not recomputed per query.
- **Authorization is a partition, not a predicate, in the default configuration.** See the ACL decision below; this removes the CI-03 filter-translation failure class from the hot path rather than hardening it.
- **Read-your-writes is a declared property, not an accident of timing.** L4 views are built asynchronously from L2 commits, so an agent that calls `remember()` and immediately `recall()`s could miss its own write if every tier were served from L4 alone. Strata's point-lookup tier resolves directly against L2 (read-your-writes guaranteed, at the cost of skipping vector/lexical ranking), while the vector/lexical tiers carry a declared staleness bound surfaced in `EvidenceState.cost` — callers who need their own write visible immediately use the cheap tier; callers who need ranked recall accept a bounded async lag.
- **The economics are already proven at the storage layer**, just not combined this way: object-storage-native engines (turbopuffer, S3 Vectors) already run the "WAL commit → async index build, object storage as source of truth, stateless compute" pattern Strata's L1/L2/L4 boundary borrows directly, at ~$70/TB/mo with 10–18 ms warm / 250–450 ms cold p90 (`indexing-vector-databases.md` §3, storage-tier table) — an order of magnitude cheaper than RAM-resident (~$3,600/TB/mo) for the cold/episodic tiers where most memory lives, with hot working-memory promoted to the RAM tier under the same tiering discipline. Strata adds governance to a pattern the storage layer already validated for cost and latency; it does not invent a new performance regime.

**The one real fork: how is ACL enforced?** If a pluggable vector-store backend receives a security predicate as a metadata filter, CI-03's entire finding applies — filter translation fails open (LangChain4j #2513: `.isNotIn` matches everything; Spring AI #3577: missing parentheses invert boolean precedence) — and a relevance construct with graceful-degradation semantics is being asked to behave like a security construct with fail-closed semantics. Strata's default is **namespace-per-principal-scope partitioning**: a principal's retrievable universe is a set of physical namespaces, and cross-scope queries fan out and merge at the read-path router — the backend is never sent an ACL predicate to evaluate, because there is no cross-namespace query for it to get wrong. This is turbopuffer's multi-tenancy model (`indexing-vector-databases.md` §5), repurposed as the *default* authorization mechanism rather than a cost optimization. It is not free: it multiplies namespaces (cost is proportional to distinct scope combinations, not documents), complicates cross-scope recall (a principal entitled to five overlapping scopes pays a five-way fan-out), and shifts risk to **post-filter starvation** — a low-privilege principal's fan-out returning fewer results than an equivalent unscoped query, silently, with no CI-05-flagged benchmark measuring it anywhere in the corpus (`common-issues.md` CI-05: *"nobody publishes low-privilege recall"*). Strata's eval plan (below) makes this an explicitly measured first-class metric rather than an unmeasured assumption, precisely because CI-05 flags its absence as universal.

## Core abstractions & API

### 1. `Record` — the typed substrate entity

```python
@dataclass(frozen=True)
class Record:
    id: RecordID                        # content hash of (body, structure) at this version
    kind: Literal["document", "chunk", "memory", "fact", "enrichment"]
    body: str | StructuredBody          # StructuredBody: section_path, table_cells+header, bbox, page
    valid_from: Timestamp               # when this became true in the world
    valid_to: Timestamp | None          # None = still valid
    tx_from: Timestamp                  # when the system learned it (transaction time)
    tx_to: Timestamp | None
    provenance: ProvenanceCapsule       # fixed-size, O(1) per record — see Architecture
    policy_id: PolicyID                 # ACL / retention / trust policy reference
    parser_confidence: float | None     # per-span; CI-02's acceptance criterion
    supersedes: RecordID | None         # explicit lineage pointer, never an implicit overwrite

@dataclass(frozen=True)
class ProvenanceCapsule:
    writer: Principal
    ingestion_path: str                 # loader/extractor identity + version
    authority_tier: Literal["primary", "corroborated", "inferred", "user-asserted"]
    trust_class: Literal["trusted", "untrusted", "quarantined"]
    source_version: str                 # embedder/extractor/parser version that produced this
```

**Day-1 — ingesting a PDF, table intact:**

```python
store.write(WriteOp.assert_(
    body=StructuredBody(text=page.text, section_path=["4.2", "Dosage"],
                         table_cells=page.tables, bbox=page.bbox, page=4),
    valid_from=today, provenance=ProvenanceCapsule(writer=ingest_pipeline_id,
        ingestion_path="pdf-parser@2.3", authority_tier="primary", trust_class="trusted",
        source_version="pdf-parser@2.3"),
    policy_id="dept-oncology-default"))
```

This is the literal shape of CI-02's acceptance test: every retrieved chunk traces to page + bounding region, and a retrieved table row carries its header because `table_cells` retains the header association as structure, not as a hopeful convention.

**Expert — rejecting the Haystack #8491 composition before it ships:**

```python
@store.precondition
def reject_delimiter_stripping(old: Record, new: Record) -> bool:
    """A cleaner must not strip the delimiter its own declared chunker needs.
    This is the exact Haystack #8491 defect (default DocumentCleaner strips
    the '\\n\\n' that split_by='passage' requires) — caught at write time,
    not discovered as one giant chunk in production."""
    required = new.provenance.ingestion_path.declared_delimiter()
    return required is None or required in new.body.text
```

### 2. `WriteOp` — the transactional write path

```python
class WriteOp(Protocol):
    def assert_(body, valid_from, provenance, policy_id, idempotency_key=None) -> RecordID: ...
    def supersede(old_id: RecordID, body, valid_from, provenance, idempotency_key=None) -> RecordID: ...
    def invalidate(id: RecordID, valid_to: Timestamp, reason: str) -> None: ...
    def consolidate(source_ids: list[RecordID], summary_body, policy) -> "ConsolidationView": ...
    def forget(id: RecordID, mode: Literal["tombstone", "crypto_shred"]) -> "ErasureReceipt": ...
```

Semantics, briefly: `assert_` with a repeated `idempotency_key` is a no-op returning the original `RecordID` — this is what defangs Mem0 #5245-class silent-duplicate-or-drop under retry. `supersede` closes the old record's `tx_to` and opens the new record's `tx_from` in the *same* WAL append, so there is never a window where both or neither is visible to a concurrent reader — this is what #4892's concurrent-write corruption needed and didn't have. `forget(mode="crypto_shred")` is the only mode that satisfies CI-06's unrecoverability acceptance criterion; `tombstone` is retained for reversible staging/test use and is documented as explicitly **not** meeting the erasure bar.

**Day-1:**

```python
memory.write(WriteOp.assert_(body="user prefers vim",
    provenance=ProvenanceCapsule(writer=current_user, ingestion_path="chat-extract@1",
        authority_tier="user-asserted", trust_class="trusted", source_version="claude-extract@1"),
    policy_id="personal-default"))
```

**Expert — concurrency-safe guideline update, the #4892 case:**

```python
receipt = store.write(WriteOp.supersede(old_id=dosage_fact_id,
    body=new_guideline_text, valid_from=guideline_v2_effective_date,
    provenance=ProvenanceCapsule(writer=ingest_pipeline_id, ingestion_path="pdf-parser@2.4",
        authority_tier="corroborated", trust_class="trusted", source_version="pdf-parser@2.4"),
    idempotency_key=request_id))
# A second concurrent writer using the same idempotency_key gets back the
# first writer's RecordID — not two half-committed facts and a corrupted index.
```

### 3. `retrieve()` / `EvidenceState` — the one read path

```python
def retrieve(intent: str, principal: Principal, policy: Policy, budget: Budget) -> "EvidenceState": ...

@dataclass
class EvidenceState:
    records: list[ScoredRecord]         # each carries provenance + trust_class
    sufficiency: float                  # calibrated signal, not raw cosine similarity
    coverage_gaps: list[str] | None
    insufficient_evidence: bool         # first-class abstention result, not a caller-side threshold
    cost: CostTrace                     # tokens / latency / $ actually spent, attributed per stage
    trace: RetrievalTrace               # typed, per-stage — CI-11's default artifact, not an add-on
```

**Day-1:**

```python
ev = retrieve("current dosage guideline for drug X",
              principal=current_user, policy=default_policy,
              budget=Budget(max_tokens=4000, max_latency_ms=800))
if ev.insufficient_evidence:
    escalate_or_say_i_dont_know()
```

**Expert — explicit budget-tiered escalation (CI-09's acceptance shape: spend never exceeds budget, quality degrades monotonically):**

```python
ev = retrieve(q, principal, policy, budget=Budget(tier="point_lookup"))
if ev.sufficiency < 0.6:
    ev = retrieve(q, principal, policy, budget=Budget(tier="vector_rerank"))
if ev.sufficiency < 0.6 and budget.allows("graph"):
    ev = retrieve(q, principal, policy, budget=Budget(tier="graph_traversal"))
```

### 4. `ConsolidationView` — reversible summaries

```python
@dataclass(frozen=True)
class ConsolidationView:
    id: ViewID
    summary_body: str
    source_range: list[RecordID]        # exact ground records summarized — never deleted by this op
    producer: str                       # policy + model version that wrote the summary
    drill_down: Callable[[], list[Record]]   # zero-cost until called — see Architecture
```

**Day-1 (sleep-time-compute-style async rollup, cf. `memory-context-engineering.md`'s Letta/sleep-time lineage):**

```python
view = memory.write(WriteOp.consolidate(source_ids=this_weeks_episodic_ids,
                                          summary_body=weekly_rollup_text,
                                          policy="weekly-semantic-rollup"))
```

**Expert — auditing a rollup back to ground truth before trusting it:**

```python
for r in view.drill_down():
    assert r.provenance.trust_class != "quarantined"
    assert r.provenance.authority_tier in ("primary", "corroborated")
```

### 5. `LineageManifest` — rebuild-from-scratch and forget-propagation

```python
class LineageManifest:
    def derivations_of(self, record_id: RecordID) -> list["DerivedViewRef"]: ...

    def rebuild(self, view_kind: str, backend: str) -> None:
        """CI-07's corrected acceptance target: rebuild any vendor index —
        including a closed managed backend — from framework-owned state
        alone, with no dependency on the vendor's in-place migration tooling."""

    def propagate_forget(self, record_id: RecordID) -> "ErasureReceipt":
        """Walks derivations_of() and invalidates or rebuilds every affected
        derived view; returns a completion proof enumerating what was shredded,
        not a fire-and-forget delete call."""
```

**Day-1:** `manifest.rebuild("vector_index", backend="pinecone")` after an embedder-model migration — dual-read during cutover, drop the old view once overlap is verified.

**Expert:** `manifest.propagate_forget(scope=departing_user_id)` on a GDPR erasure request — the receipt lists every derived view invalidated and the crypto-shred confirmation for each, which is what an audit needs and a soft delete cannot produce.

### 6. Agent tool surface — grep/file-shaped, not bespoke

```python
TOOLS = [
    Tool("recall",
         "Search memory and documents. Returns snippets with surrounding "
         "context and a path-like id (scope/kind/record_id#section) — like grep.",
         fn=lambda query, k=8: retrieve(query, principal, policy, budget).records[:k]),
    Tool("remember",
         "Store a fact you were told or concluded. A reason (source) is required.",
         fn=lambda text, reason: memory.write(WriteOp.assert_(body=text,
             provenance=ProvenanceCapsule(writer=agent_id, ingestion_path=reason,
                 authority_tier="inferred", trust_class="untrusted", source_version=model_id),
             policy_id=session_policy))),
    Tool("supersede",
         "Replace an outdated fact with an updated one; history stays queryable.",
         fn=lambda old_path, new_text, reason: memory.write(WriteOp.supersede(
             old_id=parse_path(old_path), body=new_text, valid_from=now(),
             provenance=ProvenanceCapsule(writer=agent_id, ingestion_path=reason,
                 authority_tier="inferred", trust_class="untrusted", source_version=model_id)))),
    Tool("forget", "Erase a memory permanently and verifiably.",
         fn=lambda record_path: manifest.propagate_forget(parse_path(record_path))),
    Tool("ask_sufficiency", "Check whether current evidence is enough before answering.",
         fn=lambda: current_evidence.sufficiency),
]
```

Justification for the shape, not just the existence, of this list: `research/02-frameworks/agent-framework-retrieval.md` §Lessons #6 — *"Retrieval tools compete with grep in the model's learned habits... interfaces should mimic familiar affordances (file paths, snippets-with-context)."* Note `remember` writes with `trust_class="untrusted"` by default — an agent's own inferred write does not inherit the trust of the sources it read, which is the specific gap that let Mem0's hallucinated "Vim" preference re-extract itself 808 times as ground truth (CI-04).

### 7. `WritePolicy` — the source-specific half of axiom 2

Axiom 2 promises "distinct, typed write policies per source class," not one write model — this is the abstraction that keeps that promise concrete rather than rhetorical. A `WritePolicy` is a small, named, versioned function that decides *how* a given source class turns raw input into `WriteOp` calls; the transactional machinery underneath (idempotency, atomic supersession, admission control) is identical regardless of which policy is running.

```python
class WritePolicy(Protocol):
    name: str
    version: str
    def ingest(self, raw: RawInput, principal: Principal) -> list[WriteOp]: ...

class DocumentPolicy(WritePolicy):
    """Documents: parse -> chunk -> supersede-on-edit, per span, not per document.
    A re-ingested 100-page PDF where one paragraph changed must supersede only
    that paragraph's record and no-op on every unchanged span — this is what
    CI-06's acceptance test ("only affected chunks re-embed") actually requires."""
    name, version = "document-v1", "1.0"
    def ingest(self, raw, principal):
        parsed = self.parser.parse(raw)                          # typed StructuredBody
        prior_by_span = self.store.find_spans_by_source_id(raw.source_id)  # {stable_key: Record}
        ops = []
        for span in parsed.spans:
            record = self._to_record(span, principal)             # record.id is the content hash
            prior = prior_by_span.get(span.stable_key)             # section_path+offset, not ordinal
            if prior is None:
                ops.append(WriteOp.assert_(body=record.body, valid_from=raw.observed_at,
                    provenance=record.provenance, policy_id=raw.policy_id,
                    idempotency_key=record.id))
            elif prior.id != record.id:                            # content actually changed
                ops.append(WriteOp.supersede(old_id=prior.id, body=record.body,
                    valid_from=raw.observed_at, provenance=record.provenance))
            # else: unchanged span, no op — nothing re-embeds, nothing re-supersedes
        return ops

class ConversationPolicy(WritePolicy):
    """Conversation: extract candidate facts, write them untrusted, and let a
    separate, auditable consolidation pass (not this policy) promote them."""
    name, version = "conversation-extract-v1", "1.0"
    def ingest(self, raw, principal):
        candidates = self.extractor.extract(raw.transcript)   # LLM call, isolated here
        return [WriteOp.assert_(body=c.text,
                    provenance=ProvenanceCapsule(writer=principal, ingestion_path=self.name,
                        authority_tier="inferred", trust_class="untrusted",
                        source_version=self.extractor.version),
                    policy_id=raw.policy_id, idempotency_key=c.dedup_key)
                for c in candidates]
```

**Day-1:** register a policy per source type once; every subsequent write for that source class routes through it automatically —

```python
orchestrator.register_policy(source_type="pdf_upload", policy=DocumentPolicy(parser=my_parser))
orchestrator.register_policy(source_type="chat_session", policy=ConversationPolicy(extractor=fact_extractor))
```

**Expert — a temporal ("as of") query, the enterprise-document case axiom 4 is built for:**

```python
# What did we believe about dosage before the v2 guideline superseded it?
past = retrieve("dosage guideline for drug X", principal, policy,
                 budget=Budget(as_of=guideline_v1_effective_date))
# Routes to the frozen generation valid at that date (§Architecture) —
# an explicitly slower, audit-only path, never the default "now" read.
```

This is the concrete difference between "corpus and memory are the same blob" (which the convergence-thesis evidence-against column correctly kills) and "corpus and memory share write-path machinery with different policies" (which this abstraction is): a document's policy supersedes on re-ingestion because documents have one canonical current version; a conversation's policy never supersedes at extraction time because a conversational utterance doesn't get *replaced* by a later one — it gets *consolidated* alongside it, days later, through the separate, auditable `consolidate` operation in §2. Same `WriteOp` algebra underneath, two different decisions about when to call which operation — which is exactly what a single write *model* could not express and a shared write *path* with pluggable *policies* can.

### A worked lifecycle, end to end

The seven abstractions above are easiest to judge assembled, not one at a time. A single scenario touching all of them: a hospital's oncology corpus, a dosage guideline that gets superseded, and a departing employee's right to be forgotten.

```python
# 1. Ingest — DocumentPolicy turns a PDF into typed, provenance-carrying Records.
orchestrator.ingest(RawInput(source_id="guideline-v1.pdf", policy_id="oncology-default",
                              observed_at=t0), source_type="pdf_upload")
# -> WriteOp.assert_ per section; dosage fact lands as record `fact_dosage_v1`.

# 2. Agent recall — grep-shaped, principal-scoped, budgeted.
ev = retrieve("current dosage for drug X", principal=dr_lee, policy=oncology_policy,
              budget=Budget(max_tokens=2000, max_latency_ms=500))
# ev.records[0].id == "fact_dosage_v1"; ev.records[0].provenance.authority_tier == "primary"

# 3. Six months later, a new guideline supersedes the old one — DocumentPolicy's
#    supersede branch fires automatically on re-ingestion because source_id matches
#    and the content hash changed:
orchestrator.ingest(RawInput(source_id="guideline-v1.pdf", policy_id="oncology-default",
                              observed_at=t1), source_type="pdf_upload")
# -> WriteOp.supersede(old_id="fact_dosage_v1", ...) closes v1's tx_to and opens
#    "fact_dosage_v2" in the same WAL append (§2) — no window where a concurrent
#    reader sees both or neither.

# 4. A "now" read after t1 sees only v2, at the O(1) generation-pointer cost
#    described in §Architecture. An audit read explicitly asks for history:
audit = retrieve("dosage for drug X", principal=compliance_officer, policy=audit_policy,
                  budget=Budget(as_of=t0))
assert audit.records[0].id == "fact_dosage_v1"   # queryable, not deleted, not silently gone

# 5. The employee who authored the original ingestion pipeline's session notes
#    leaves. Their personal working-memory scope must be verifiably erased —
#    the *document* facts they ingested (dosage guidelines) are unaffected,
#    because provenance separates "who operated the pipeline" from "what the
#    guideline says":
receipt = manifest.propagate_forget(scope=departing_employee_session_scope)
# -> walks LineageManifest.derivations_of() for that scope only, crypto-shreds
#    the scope's envelope key, invalidates/rebuilds the affected vector and
#    lexical views, and returns an ErasureReceipt naming every view touched.
# fact_dosage_v1 and fact_dosage_v2 are untouched: they belong to policy_id
# "oncology-default", not the departing employee's personal scope.
```

Three things this walkthrough is meant to make legible that a component-by-component reading can't: supersession and forgetting are *different operations reachable through the same audit trail* (step 3 vs step 5) — this is what "provenance and ACL inherit through every derivation" (axiom 6) buys operationally, not just conceptually. The audit read in step 4 and the "now" read in step 2 hit the same `retrieve()` signature with a different `Budget.as_of`, not a different API — this is axiom 2's "one read path" made literal. And step 5's forgetting is scoped by provenance, not by document — it is possible to forget *who touched the pipeline* without forgetting *what the pipeline produced*, which is the distinction Authority-Collapse-by-consolidation destroys everywhere else in the corpus (CI-04, CI-26).

## Issue-coverage traceability

Every row cites the *restated* claim and acceptance criterion from `common-issues.md`, not the headline name. `§` points to the section above that carries the mechanism.

| CI | Verdict | Why |
|---|---|---|
| CI-01 | mitigated | Self-bootstrapping eval taps L1/L3/L5 as a core artifact (§Architecture), but eval-set maintenance under corpus drift is named genuinely open by the taxonomy itself — not solved by shipping the harness once. |
| CI-02 | mitigated | `Record.StructuredBody` carries section path/table headers/bbox/parser confidence by construction; `WriteOp` preconditions reject destructive compositions (§1) — but parsing fidelity itself (OCR/structure extraction) is unimproved by this design. |
| CI-03 | mitigated | ACL is enforced by namespace partition, not a smuggled filter predicate (§Architecture "the one real fork") — removes the structural conflation but a per-backend conformance suite is still required for any relevance-filter feature that remains. |
| CI-04 | mitigated | `ProvenanceCapsule` + default `trust_class="untrusted"` on agent-inferred writes (§6) close the Mem0 re-extraction loop; structural non-extractability of retrieved text (CI-04's named research frontier) is not attempted. |
| CI-05 | mitigated | `retrieve()` does not compile without `principal`+`policy` (§3); the expensive half — identity mapping, group-membership sync — is explicitly deferred to an external IdP integration, per anti-scope. |
| CI-06 | solved | `forget(mode="crypto_shred")` (§2) sidesteps "verified erasure in ANN indexes" (a named open problem) by moving unrecoverability to the key layer; `LineageManifest.propagate_forget` (§5) gives a completion proof CI-06 says no framework offers. |
| CI-07 | solved | Framework-owned `Record` ground store + `LineageManifest.rebuild` (§5) meets the corrected acceptance target exactly: rebuild any vendor index from Strata's own state, no vendor migration tooling required. |
| CI-08 | mitigated | A semver-stable kernel (`Record`/`WriteOp`/`retrieve`) with churn quarantined to the tool/policy layer is a design commitment, not a provable property until the framework survives multiple years in the wild. |
| CI-09 | mitigated | `Budget` + tiered escalation (§3 expert usage) makes cost an enforced typed input with monotonic degradation; empirical validation of "never exceeds, degrades gracefully" at scale is unproven. |
| CI-10 | mitigated | `insufficient_evidence` is a first-class `EvidenceState` field (§3), not a caller-side threshold; the calibration method behind `sufficiency` is engineering-plus-research, not solved by the type alone. |
| CI-11 | mitigated | Every `retrieve()` emits a typed per-stage trace by default (§3) — but Haystack and Spring AI are existing partial counter-witnesses, so this is convergence with best practice, not a first, and prompt-registry parity with the agentic path is unbuilt. |
| CI-12 | mitigated | Leg (c) only: `WriteOp` idempotency keys and atomic supersession (§2) give memory writes database semantics. Legs (a) and (b) — agentic capability regression, loop-correctness — are explicitly out of scope; Strata is not an executor. |
| CI-13 | mitigated | Parameterized `WriteOp`/`retrieve` calls, no string-interpolated ACL predicates, closes the filter-injection/SQLi-via-filter-key class; SSTI in prompt templates and sandboxing of code-execution nodes are generation/agent-layer concerns Strata does not own. |
| CI-14 | mitigated | Read-path default profile (hybrid + rerank, versioned/dated) is a design commitment; needs real benchmark validation over time to earn "solved." |
| CI-15 | mitigated | Self-bootstrapping eval reduces reliance on vendor self-benchmarks, but an uncalibrated auto-judge is its own CI-15 risk (see Risks) — mitigated, not eliminated. |
| CI-16 | mitigated | Typed trace + audit substrate (§3, §Architecture) is what a feedback loop needs to attach to; the learned re-ranking loop itself is not shipped in the design as specified. |
| CI-17 | mitigated | Semver-stable kernel reduces churn-driven doc rot as a side effect of axiom 8's discipline, not a dedicated feature. |
| CI-18 | mitigated | Anti-scope commits every built-in stage to being reimplementable from the public `WriteOp`/`retrieve` API; requires ongoing enforcement discipline to keep true. |
| CI-19 | mitigated | Write orchestrator (§Architecture L3) is specified as a bounded streaming job with backpressure/checkpoint, not a library loop — but this is a runtime-engineering commitment, not yet load-tested. |
| CI-20 | unaddressed | Vendor billing-floor hygiene (idle managed-service cost, orphaned dependents) is outside a client-side framework's control; `CostTrace` gives visibility only. |
| CI-21 | unaddressed | Declarative tail-recall SLOs are named "unclaimed territory" by `indexing-vector-databases.md` itself (§Open problems #1) — Strata's tiered `Budget` leaves a slot for this but does not implement it, because the underlying research does not yet exist. |
| CI-22 | unaddressed | Per-language analyzers, fusion-weight calibration, and per-language telemetry are real requirements this design does not attempt; flagged as necessary follow-on work, not a core-design claim. |
| CI-23 | mitigated | The admission-control gate in the write orchestrator (§Architecture L3) generalizes to a policy manifest that could refuse to start without required controls, but this extension is not built out in the design as specified. |
| CI-24 | mitigated | Agent tool surface (§6) is deliberately grep/file-shaped per the model-priors constraint; a cross-provider conformance suite for the tool contract itself is not yet specified. |
| CI-25 | mitigated | Content-hashed WAL + versioned `LineageManifest` (§Architecture L1, §5) gives reproducible snapshots and pinned manifests; determinism of the LLM calls that produce embeddings/extractions is not guaranteed by this alone. |
| CI-26 | mitigated | Admission control (§Architecture L3) can gate low-confidence enrichment before it commits; automatic graph-vs-vector ablation tooling per query class is future engineering, not shipped. |
| CI-27 | mitigated | A policy manifest can express a no-egress deployment profile via the same admission-control mechanism; this is not the design's primary focus and needs explicit build-out. |

**Tally: 2 solved (CI-06, CI-07), 22 mitigated, 3 unaddressed (CI-20, CI-21, CI-22) — 27 total.**

## What this framework deliberately does NOT do

- **No graph extraction in core.** Entity/relation extraction and Leiden-style community structure are an optional, off-by-default derived view (L4), not a founding abstraction — even though this proposal's stance is graph-friendly (bitemporal edges, lineage). `research/01-landscape/graph-structured-rag.md`'s own comparative evidence is the reason: GraphRAG-Bench (arXiv:2506.05690) finds graphs "frequently underperform vanilla RAG" on fact retrieval at 40–60× the index cost, and RAGSearch (arXiv:2604.09666) shows agentic multi-round retrieval over a plain index closes most of the multi-hop gap graphs used to own. Shipping a graph engine in core would repeat GraphRAG's own cost mistake inside a framework that exists to avoid it. This is the one anti-scope item that costs something real, since a bitemporal-ledger stance invites "just build the temporal graph" — and the discipline is refusing to, by default.
- **No agent execution engine.** No DAG scheduler, no loop controller, no planner. Strata is a substrate a LangGraph-style executor calls into via `retrieve()`/`WriteOp`, not a competitor to one. CI-12 legs (a)/(b) are explicitly not this framework's problem.
- **No prompt/chain abstraction layer.** No `PromptTemplate`, no chain composition DSL. This is the specific abstraction depth that produced CI-11's "opening six objects to find the rendered prompt" (Octomind's LangChain postmortem) and the LangChain over-abstraction spiral the brief names by name.
- **No proprietary embedding model, LLM, or parser.** Embedders, extractors, and generators are versioned, swappable dependencies referenced by `source_version` in the `ProvenanceCapsule` — never vendored.
- **No cryptographic PIR/HE retrieval by default.** `research/01-landscape/private-federated-personalized.md` prices this at 4–190× per-query overhead (Kermarrec et al., arXiv:2608.01192) with no support for adaptive multi-hop queries — incompatible with an agent loop by construction. TEE is the default elevated-privacy tier (<10% overhead, Chrapek et al.); PIR/HE remain an opt-in tier for single-shot, latency-insensitive queries only.
- **No in-framework identity/ACL-sync machinery.** Strata defines the `principal`/`policy` type and its enforcement point; it does not build a connector layer that mirrors Okta/AD/OpenFGA group membership. CI-05's steelman is explicit that this "expensive 95%" is a different, largely solved problem (Glean-style connector machinery) that a retrieval substrate should consume, not rebuild.
- **No universal multi-modal parser.** Docling-, LlamaParse-, or vendor-grade parsers plug in underneath the `StructuredBody` contract; Strata enforces the contract's *shape*, not the extraction's *fidelity*.
- **No managed-tier feature gating.** Authorization, eval, and lifecycle stability are core, not paywalled — a direct reversal of CI-01's, CI-05's, and CI-08's shared open-core root cause, not a feature list.

## Novelty vs prior art

- **vs. Zep/Graphiti** (`memory-context-engineering.md`, `graph-structured-rag.md` §Temporal KGs): Graphiti pioneered bi-temporal edges for agent memory — the single closest prior-art idea to axiom 4 — but scoped it to conversational entity graphs, vendor-evaluated, with no unification with document RAG, no formal write-path algebra beyond edge invalidation, no crypto-shred forgetting, and no cost/budget primitive. Strata generalizes bi-temporality from "a property of graph edges" to "a property of the base record type," independent of whether a graph view exists at all.
- **vs. Mem0** (`memory-and-localfirst.md`): an extraction pipeline with LLM-arbitrated ADD/UPDATE/DELETE/NOOP and no transactional guarantees — exactly the gap #5245 and #4892 expose. `WriteOp`'s idempotency keys and atomic supersession are the missing database-engineering layer underneath the same conceptual operations Mem0 already names but doesn't enforce.
- **vs. MemOS** (`memory-context-engineering.md`): the `MemCube`'s cross-form promotion (plaintext ↔ activation ↔ parameter memory) is the closest published analog to Strata's tiered promotion policy, and its provenance/versioning metadata gestures at axiom 6 — but MemOS is self-reported/preprint, has no bitemporal validity model, no ACL inheritance, and no verifiable-forgetting mechanism; it unifies memory *forms*, not memory and corpus *governance*.
- **vs. LlamaIndex's typed node model / Docling's structural IR** (`common-issues.md` CI-02 Steelman): both are real, adopted existence proofs that typed structure survives ingestion — Strata's `Record`/`StructuredBody` generalizes them by adding bitemporal fields, an inherited ACL/provenance capsule, and cross-stage precondition enforcement that neither ships (LlamaIndex's node relationships are unenforced conventions, per CI-02's restated claim).
- **vs. Databricks Delta Sync / Lance** (`indexing-vector-databases.md` §3, `common-issues.md` CI-06 Steelman): Delta Sync is the corpus's own counter-example of solved incremental sync (CDF-based, seconds-latency) and Lance is the closest published substrate combining versioned data with co-located indexes. Strata borrows the WAL-then-async-derived-view pattern directly but adds the governance layer neither offers: bitemporal *supersession semantics* (not just row versioning), inherited ACL/provenance, and crypto-shred forgetting.
- **vs. SILO** (`private-federated-personalized.md` §H): SILO's argument that a datastore is a legal-risk-isolation boundary — with attribution and instant opt-out as its headline advantages over parametric weights — motivates Strata's provenance requirement directly, but SILO is a static training-risk isolation scheme with no write-path model for a live, mutating, multi-writer substrate.
- **vs. CaMeL-style typed-value defenses** (`memory-context-engineering.md`'s adjacent security literature, CI-04): Strata adopts the "typed value carrying provenance" idea for its capsule, but does not claim to solve full data/instruction separation — CI-04 itself names structural non-extractability a research frontier, and this design reports it honestly as unaddressed rather than papering over it with a provenance field that only mitigates, not prevents, the failure.
- **vs. turbopuffer / S3 Vectors** (`indexing-vector-databases.md` §3, §5): both validated the object-storage-native, WAL-then-async-index, namespace-per-tenant pattern for cost and multi-tenancy. Strata is the first design in this corpus to repurpose that pattern as the *default authorization mechanism* (not merely a cost optimization) and to layer bitemporal governance semantics on top of it.

## Feasibility

**MVP.** Single-tenant or small-multi-tenant deployment. Ground store on Postgres (enterprise) or SQLite (local-first, per `memory-and-localfirst.md`'s lesson that boring, inspectable on-disk formats survive maintainer mortality). One vector index using a cluster/IVF+RaBitQ family rather than HNSW — chosen specifically because cluster indexes give natural filter/namespace pushdown, cheap incremental updates, and bounded I/O (`indexing-vector-databases.md` §2, §5), all properties the namespace-partitioned ACL model and the mutation-heavy write path need and HNSW structurally lacks. One lexical (BM25) index. `WriteOp` ships with three operations at MVP — `assert_`, `supersede`, `forget` — deferring `invalidate`'s and `consolidate`'s full policy surface to post-MVP. `retrieve()` ships with `principal`+`budget` and a threshold-based (not fully calibrated) sufficiency signal. Crypto-shred ships at per-scope granularity (one key per policy scope) rather than per-record, trading some forgetting precision for a shippable MVP. The agent tool surface (`recall`/`remember`/`forget`/`supersede`/`ask_sufficiency`) is tested directly against tool-calling models, not assumed to work from the type signature alone.

**Hard.** A cross-backend filter/score conformance suite (CI-03's honest fix) is expensive per additional backend supported — this creates real tension with the "small stable core" anti-scope discipline: every backend added is a new conformance-suite surface, not just a new adapter. A calibrated sufficiency signal that reliably predicts downstream answer quality — not just a better cosine threshold — is genuinely hard; cheap uncertainty estimators exist in the literature (`memory-context-engineering.md` §Open problems #1, arXiv:2501.12835) as a starting point, not a finished answer. Reversible consolidation at multi-year scale, where drill-down must stay cheap without ground-truth storage bloating indefinitely, is a real engineering problem this design gestures at (tiered storage, per Architecture) but does not fully solve. First-class, revisable entity resolution for the optional graph view is named as unbuilt anywhere in the corpus (`graph-structured-rag.md` §Open problems #3) and Strata does not claim otherwise.

**Depends on research that doesn't exist yet.** Eval-set maintenance under corpus drift (CI-01's genuinely open half, per the taxonomy's own verification). Tail-recall SLO-bearing retrieval APIs (`indexing-vector-databases.md` §Open problems #1: "unclaimed territory"). Provable structural instruction/data separation beyond CaMeL's ~7-utility-point cost (CI-04's named research frontier). Utility-based forgetting — nobody has shown that removing a memory measurably improves downstream task success (`memory-context-engineering.md` §Open problems #4). Strata's design leaves typed slots for all four (a `Budget` field for SLOs, an `insufficient_evidence` flag as a home for sufficiency research, a `trust_class` field as a home for structural separation research, a `forget` receipt as a home for utility measurement) without pretending to have filled them.

## Risks & open questions

- **The performance answer needs empirical validation, not just a mechanical argument.** §Architecture's generation-partitioning trick removes temporal predicates from the hot path *in principle*; whether the amortization actually holds under a real agent loop's query mix — frequent point-lookups interleaved with occasional as-of-the-past audits — is untested. This is the brief's named confrontation, and a mechanical argument is not the same as a benchmark.
- **Crypto-shred-by-default creates a new single point of failure: key management.** Lose the KMS, lose everything provably and permanently — which is the intended behavior for a *deliberate* forget, and a catastrophic one for an *accidental* key-store failure. A robust KMS design (envelope encryption, key rotation, scoped blast radius) is load-bearing infrastructure this proposal assumes rather than designs.
- **Reversible consolidation risks unbounded storage cost if ground truth is never truly released.** Without a tiered hot/cold/archival policy (borrowing the RAM/SSD/object-storage economics from `indexing-vector-databases.md` §3) and an explicit legal-hold-then-release lifecycle, "never delete, only supersede" becomes "never delete, period."
- **The conformance-suite-per-backend cost is in direct tension with the small-core anti-scope discipline.** Strata can either support few backends deeply (conformance-tested, CI-03-safe) or many backends shallowly (integration-count growth, CI-03's actual root cause) — it cannot honestly do both, and the design as specified has not picked a number.
- **The `principal`/`policy` type is theater if the identity mapping behind it is weak.** CI-05's own steelman applies directly to Strata: a typed slot for a principal enforces nothing without correct group-membership sync feeding it, and that machinery is explicitly out of scope (anti-scope). Garbage identity in, garbage authorization out.
- **The self-bootstrapping eval harness is at risk of becoming its own CI-15 measurement theater** — an auto-generated golden set scored by an uncalibrated LLM judge is exactly the failure pattern the taxonomy documents elsewhere (LightRAG's own eval prompt showing textbook position bias). Bias-audited judges and disclosed configuration are a day-one requirement for the harness, not a later hardening pass.
- **Bitemporal queryability creates a confused-deputy risk of its own.** If "what did we believe on date X" is queryable, an attacker (or a careless prompt) could resurface a superseded-but-not-yet-shredded false fact by framing a query as historical rather than current. The policy layer needs an explicit distinction between "queryable history" (audit-only, requires elevated principal) and "actionable current belief" (the default `retrieve()` path) — this is designed at the type level (`valid_to`/generation routing) but the *policy* enforcing which principals may cross that line is not yet specified.

## Evaluation plan

**Benchmarks.** LongMemEval for memory-side quality (currently the field's most respected target per `memory-context-engineering.md`); a corpus-mutation soak test measuring recall decay and tombstone debt directly against CI-06's acceptance criteria (edit one paragraph → only affected chunks re-embed; delete → zero retrievable chunks within a declared SLA); a filter/namespace conformance suite with golden queries returning identical result sets across every supported backend (CI-03's acceptance test, adapted to a namespace model); an ACL entitlement fuzzer specifically measuring **low-privilege recall** (CI-05's flagged-as-unmeasured gap) under the namespace-partition model to quantify post-filter-starvation risk; an erasure-verification test that crypto-shreds a scope and then attempts vec2text-style embedding inversion against every derived view to confirm unrecoverability, not just non-return; Robustness-δ@K tail-recall measurement (`indexing-vector-databases.md` §Benchmarks) rather than mean recall alone; a budget-compliance test at three budget levels confirming spend never exceeds budget and quality degrades monotonically (CI-09's acceptance test verbatim); an abstention-rate measurement on an unanswerable-question set, disambiguated from the discredited `retrievalci` anecdote and aligned instead with EnterpriseRAG-Bench's (arXiv:2605.05253) more credible absent-information category (CI-10).

**Ablations.** With/without reversible consolidation, measuring whether focused drill-down beats full-context injection on long-horizon tasks (replicating Chroma's LongMemEval finding that a focused 300-token prompt beats a full 113K-token one, `memory-context-engineering.md` §Context failures). With/without bitemporal fields, measuring the generation-partitioning claim directly: p50/p99 latency for "now" reads with and without per-row temporal predicates, at increasing corpus mutation rates. With/without the `ProvenanceCapsule`, measuring injection resistance via PoisonedRAG and AgentPoison suites (CI-04's named pre-deployment gates) — with and without `trust_class="untrusted"` defaulting on agent-inferred writes, to isolate exactly how much the Mem0-style re-extraction loop closes.

**Production metrics.** A "kill-the-vendor" drill: delete Strata's binaries, rebuild a retrieval-equivalent system from exported `LineageManifest` artifacts alone, and measure recall parity on a golden set (CI-08's acceptance test verbatim). Recall-overlap reporting across an embedder migration with dual-read cutover (CI-07's acceptance test). Junk-rate, duplication-rate, contradiction-count, and extraction-yield as first-class memory-quality metrics emitted continuously, not discovered by a 32-day hand audit (`memory-and-localfirst.md` §Lessons #10). Finally, the brief's own core requirement — that the system get measurably better from production feedback — is tracked as a single closed-loop metric: retrieval-quality-on-golden-set before vs. after N production sessions with feedback wired through the typed trace substrate (§Architecture), which is the concrete, falsifiable form of "learns from feedback" rather than an aspiration.
