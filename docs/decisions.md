# Datum implementation decisions

Every place this implementation deviates from, resolves an ambiguity in, or
extends `design/FRAMEWORK.md`, recorded here so nothing load-bearing lives
only in a chat transcript or a commit message. Decisions 1–5 were made in the
approved implementation plan; 6–9 during the kernel build and its first-principles audit; 10–16 during
the parallel-wave build and the adversarial review that followed it (12–16
each close, or record the deferral of, a reproduced review finding); 17–18
during the L2/L3/read-path build (span-identity and evidence-provenance
fields the integration required); 19–28 during the Milestone B hybrid-
retrieval build (19–20 close defects the new engine tests reproduced before
any new operator went live; 21–23 record the BM25 backend no-go, the rerank
semantics, and the derivation freshness/schema-ownership model; 24–28 adopt,
record, or schedule the outcomes of the two Milestone B adversarial reviews —
24–26 tenancy, 27 the deferred audit-trace gap, 28 score-contract/robustness);
29–30 during Milestone C (29 the abstention floor the eval gate surfaced; 30
the now-implemented unconditional audit trail that #27 deferred); 31 the
multi-format DoclingParser (task #30) and its environment-honest benchmark;
32 the Milestone D end-to-end MCP acceptance over the real transport; 33 the
MarkdownParser code-fence heading fix that Milestone D dogfooding surfaced; 34 the bge-m3 default embedder + per-deployment abstention floor from the PDF stress test; 35 the ocrmac OCR default (its picture-text/VLM-frontier conclusion later CORRECTED by 36); 36 the image-OCR composition that recovers picture/chart/facsimile/Devanagari text Docling's markdown export drops; 37 table-aware chunking (header-carrying row-groups) for large paginated tables; 38 the rerank-pool coverage guarantee that closes an RRF fusion blind spot, and the honest diagnosis of the remaining Docling heading-detection gap it does NOT fix; 39 stress test #2 (unseen document): script families (Arabic/Tamil), the embedded-image-object pass, per-crop plurality arbitration, PDF metadata ingestion, and the bge-reranker-v2-m3 default that matches the multilingual embedder; 40 the 20-family multilingual roster (readback-verified, 18 strong + 2 weak) with the sparse-gate + noise-floor that keep a broad default hallucination-free; 41 LLM-free contextual retrieval (section-path-prefixed view inputs) + the labeled NLLB ingest gloss — doc-2 44/44; 42 the first public-benchmark validation (BEIR SciFact nDCG@10 = 0.697 — above BM25/ColBERTv2, at SPLADE++ level, zero-shot through the full governed pipeline); 43 the VisionDescriber slot (pluggable picture understanding, provenance-labeled; local small VLMs measured unusable — the slot is the enterprise value); 44 the relevance-feedback loop (signed-token judgments, promotion-gated calibration, per-namespace overrides visible in EXPLAIN); 45 the repo-resident SciFact harness (scripts/beir_scifact.py) + the re-measured result (bge-large English profile, nDCG@10 0.714, above all named baselines) after the original scratchpad harness was lost. 46 the adversarial head-to-head (Datum 83/86 fresh vs LangChain 64, LlamaIndex 66, Haystack 67, LC+OCR 66 — parity models, shared reranker; bolt-on OCR nets ~zero; LlamaIndex default reader silently indexes raw PDF bytes).

## 1. `WriteOp` is a value type, not an executor Protocol

The spec's own two sketches conflict: one shows `WriteOp` as a Protocol with
executor methods (`assert_(...) -> RecordID`), the other has
`WritePolicy.ingest()` return `list[WriteOp]` built by appending
`WriteOp.assert_(...)` calls — which only type-checks if those calls
construct values. Resolved as a frozen dataclass with a `kind` discriminator
and classmethod constructors. The executor return types are realized in
`writepath.orchestrator.WriteOrchestrator.execute()`. Costs zero kernel
symbols versus +3 for an `AssertOp`/`SupersedeOp`/`ForgetOp` split.

## 2. `HitRegistry` is a stateless HMAC-signed token at v1

The spec's own named fallback for single-replica deployments with no shared
cache — which is exactly v1's infra footprint (Postgres + local filesystem).
Trades revocability for zero added infrastructure. A multi-replica deployment
later needs the shared-registry implementation behind the same interface.
(What the token may and may not carry is pinned separately in #12.)

## 3. `Policy.select(context) -> FusionDecision` is a first-draft interface

The spec names the plan-selection slot and its role but gives no method
signature. This shape is ours, minimal, and revisable until
`policy/rule_table.py` is built against it — after that it hardens.

## 4. BM25 backing is a go/no-go, not a pin

Try ParadeDB `pg_search` first; fall back to Postgres `tsvector`+GIN if
install friction is real. The conformance suite's score-contract case is
deliberately written as "monotonic in relevance," not "matches BM25's exact
formula," so the swap never requires rewriting tests.

## 5. FastCDC is hand-rolled and vendored, not a pip dependency

Chunk identity is record identity; an upstream chunker version bump silently
re-chunking the corpus is unacceptable. And the spec's boundary-constrained
merge (hash triggers reconciled with structural-IR boundaries) doesn't exist
in any off-the-shelf library, so generic library boundary logic would need
overriding anyway (see #15 for the exact merge semantics). Reference: Xia et
al., USENIX ATC 2016.

## 6. Top-level symbol budget: helpers demoted, exceptions added

Four purely-structural helper types that exist only as fields on budgeted
types (`StructuredBody`, `TableCell`, `PlanStep`, `LineageEdge`) are NOT
re-exported at top level; they remain importable from their owning submodule.
The five exception types (`DatumError` + 4 subclasses) ARE top-level despite
not being in the spec's 35-symbol count: catching a specific exception type
is part of a Python library's public contract, not incidental surface. Net
ceiling this build tracks: 35 + 5 = 40 exactly, with the four spec-deferred
symbols (`ConsolidationView`, `GovernedProfile`, `DriftMonitor`,
`PromptArtifact`) required to land within it — the budget is now exactly
full at Phase 2, which is itself worth knowing today.

## 7. A record's namespace derives from its writer at v1

`Record` (kernel and spec sketch alike) has no `namespace` field, but
namespace-partition ACL needs every record to belong to exactly one
namespace. v1 rule: a record's namespace IS `record.provenance.writer.namespace`
— the namespace of the principal that wrote it. The ground store (L2)
materializes this as a real column at write time so partition selection is
an indexed equality check, not a JSON traversal; the kernel type stays
unchanged. Known limitation, accepted deliberately: an admin ingesting on
behalf of another tenant needs a principal *in that tenant's namespace* at
v1. The proper fix (a policy registry mapping `policy_id` → namespace +
retention + trust rules) is Phase 1, alongside fine-grained predicate ACL.

## 8. `Plan.compile()` / `Plan.replay()` live on `Corpus`, not the class

Both need live runtime context (registered operators, the trace store); as
classmethods they would force module-global mutable state. They are
`corpus.compile_plan(...)` and `corpus.replay(plan_id, against=...)`.
`plan.execute()` and `plan.diff(other)` — the two instance methods the spec
sketch shows — exist on the kernel type faithfully: `execute()` delegates to
an executor bound by the planner at compile time (the kernel type carries
the callable, does no I/O itself, and raises with a pointed message on an
unbound/replayed plan), `diff()` is pure field comparison excluding identity
fields.

## 9. Postgres 16, Python ≥3.11, psycopg3 — floor versions, not ceilings

The dev environment runs Python 3.12 and a Postgres 16 container. Nothing
in v1 intentionally uses features newer than Python 3.11 / Postgres 15;
these floors are asserted here so a future contributor knows a failure on
older versions is a bug in this table, not in their setup.

## 10. MCP SDK v2 (`MCPServer`), not the v1 `FastMCP` line

The implementation plan chose the official SDK's v1 `FastMCP` API based on
mid-2026 research that described v2 as beta. Reality at install time:
`pip install "mcp>=1.2"` resolved 2.0.0, where `mcp.server.fastmcp.FastMCP`
no longer exists — the class is `mcp.server.mcpserver.MCPServer`, and its
`Tool` objects expose `input_schema`/`output_schema` (snake_case). The MCP
scaffold was built and verified against that real installed API (including
the full `call_tool` dispatch path), and the pyproject floor is now
`mcp>=2.0` so an environment where our import path doesn't exist can't
install as "satisfied." The plan's research wasn't wrong when written; it
aged out between planning and installation — which is exactly why the
scaffold task said "check the installed version's actual API rather than
assuming."

## 11. L1↔L2 transaction seam: the WAL append must join the ground store's transaction

Found while auditing the delivered `storage/wal.py` before building the
ground store. FRAMEWORK.md requires a supersede to close the old record's
`tx_to` and open the new record's `tx_from` "in the same WAL append," and
names the WAL append as "the single, sole commit point." The delivered WAL
holds its own `autocommit=True` connection, so a naive ground store would
mutate the `records` table on one connection and append to `wal_entries` on
another — two transactions, no atomicity, reintroducing exactly the
write-race the design exists to close (the Mem0 #4892 class; paper Figure 5).

Resolution, built in the groundstore phase (extends the WAL, does not rewrite
it): the ground store owns the transaction for any write that couples a WAL
entry to a record mutation. `WAL` gains an `append_in_txn(cursor, entry, *,
namespace) -> int` that appends on a caller-supplied psycopg cursor rather
than its own autocommit connection; the ground store's supersede then runs
`BEGIN; <append_in_txn>; <close old tx_to>; <insert new record>; COMMIT` on
one connection, so the WAL append and the record mutation commit together or
not at all. The existing autocommit `append()` stays for standalone WAL
entries not coupled to a record write (e.g. a future ACL-change log entry),
and the read path is unaffected. This is the cross-layer seam the
implementation plan reserved for "one consistent hand" to own at L2.

## 12. The stateless `hit_id` token carries a reference, never a trust judgment

Closes a reproduced review finding. The first-draft `HitRegistry.issue()`
embedded `trust_tier`/`authority_tier` in the token payload. `hmac`/`hashlib`
give integrity, not secrecy — the payload is base64-recoverable without the
signing key — so a prompt-injected model told to decode its own tool output
could read the exact trust metadata the out-of-band envelope exists to keep
away from it. FRAMEWORK.md's hot-path table specifies the stateless token as
encoding "`record_id`+snapshot version," deliberately not trust/authority.
Resolution: `issue(content_ref, *, version)` encodes only a reference
(`content_ref`, `version`, `issued_at`, `nonce`); trust/authority are
resolved server-side from the record itself at `resolve()` time, by the layer
that holds the records (`Corpus`, Milestone A). A regression test decodes the
token without the key and asserts no trust field is present. (Also removed a
docstring that misattributed a paper-§4.5 sentence as a FRAMEWORK.md quote.)

## 13. v1 namespace ACL is exact-equality, not a subtree/prefix grammar

Closes a reproduced review finding. A first-draft `security/acl.py` invented
a `:`-delimited subtree grammar (`tenant:acme` grants `tenant:acme:finance`
…). The storage layer filters a namespace partition by SQL equality (spec:
"a cheap equality check on a partition key"), so a subtree grant and an
equality filter disagree: a coarse principal is silently starved of records
it is authorized for, or the storage filter must become a prefix scan that
puts string-prefix logic back on the hot path — the CI-03 filter-as-ACL-
bypass shape this layer exists to prevent. Resolution: v1 grants access iff
`principal.namespace == record_namespace`, exactly — ACL and storage filter
provably agree, no hierarchy. Multi-level grants (a tenant admin spanning its
departments) are Phase 1, arriving with the fine-grained predicate path and a
namespace-*set* storage filter (a safe `IN (...)`, not a prefix match).

## 14. WAL read API: resumable `tail_since` requires a namespace; global reads are one-shot `scan()`

Closes a reproduced review finding. `GENERATED ALWAYS AS IDENTITY` allocates
an id before commit, so a resumable `WHERE id > marker` reader can permanently
skip an id that committed after a later one — the classic changefeed gap. The
review reproduced it losing 10 of 8000 entries on a resumable *global*
(all-namespace) tail under concurrent writers. Resolution: the API makes the
unsafe shape unspellable. `tail_since(marker, *, namespace=...)` — the
resumable changefeed, `since()`'s backing — requires a namespace, and is
loss-free under v1's single-committer-per-namespace invariant (which L3
maintains). The global read is a separate `scan(*, namespace=None)` with no
marker: one-shot, so it has no resume gap by construction (admin/rebuild use,
e.g. CI-07). There is deliberately no resumable global tail; the fully-
concurrent-per-namespace case needs a commit-visibility watermark that is
Phase 1 work.

## 15. `chunk_structured_body` takes protected regions, not a flat boundary list

Closes a reproduced review finding. FRAMEWORK.md ("Reconciling content-defined
boundaries with the structural IR") states two things about the merge:
candidate split points are "the *union* of {rolling-hash trigger positions,
structural-unit boundaries from the parser's IR (table start/end, section
start/end, page break)}", and "the actual boundary used is the nearest
structural boundary at or before each rolling-hash trigger — never inside a
table or across a header/body split." Read in isolation, the second clause
says *snap every trigger* to a structural boundary. The delivered function did
exactly that against a flat `structural_boundaries: list[int]`, which broke
the property the same paragraph promises: "prose reflows at fine CDC
granularity as designed." With a realistic sparse IR (one table inside long
prose) every prose trigger snapped back to the last structural boundary,
collapsing all prose between sparse boundaries into one chunk — a 10k-char-
prose + table + 10k-char-prose document produced three chunks
`[10000, 498, 10000]`, a chunk 2.4x over `max_size`, and a 1-char edit at
offset 0 invalidated the entire first 10,000-char chunk.

Resolution (a narrowing of the spec, not a contradiction of it): the input is
now `protected_regions: list[tuple[int, int]]` — the `(start, end)` char
extents of indivisible structural units. The candidate cut set is built as
the union the spec's first clause names: every raw CDC trigger in open prose
stands as-is (so prose keeps CDC's fine, shift-invariant granularity and its
`max_size` bound), each region's start and end are always cuts (so a unit is
its own chunk), and only a trigger landing *strictly inside* a region is
snapped to that region's start — the spec's second clause retained for
exactly the case it was written for, "never inside a table or across a
header/body split," rather than applied to every trigger. `max_size` now
bounds every prose chunk; a single protected region wider than `max_size`
remains the one documented case a chunk can exceed it.

Overlapping/nested regions are rejected (`ValueError`), not merged: silently
merging a table nested in a section would coarsen the whole section into one
chunk, reintroducing this same collapse. The caller must flatten IR extents
to their outermost protected unit before calling. Safe to change the
signature now — grep confirms no caller exists in `src/` yet (the write path,
L3, is unbuilt). Reference: FRAMEWORK.md §"Ingestion & derivation".

## 16. The MCP scaffold's `CorpusLike.fetch`/`.explain` are provisional until Milestone A

Records the deferral of a reproduced review finding rather than fixing it now.
The MCP scaffold's `CorpusLike` protocol has `fetch(hit_id) -> SearchHit` and
`explain(plan_id) -> str`, which diverge from FRAMEWORK.md §7's sketch
(`fetch(ref, span, ...) -> Evidence`; `explain -> Plan`). The scaffold was
built against a hand-rolled `FakeCorpus` because the real `Corpus` does not
exist yet. Rather than pin these signatures twice, they are reconciled to the
spec when the real `Corpus` is built and the server is wired to it at
Milestone A: `fetch` gains a span/granularity argument and returns `Evidence`;
`explain` returns a serialized `Plan`. Neither takes a `principal` parameter —
that comes from session context, and that part of the scaffold is already
correct and must be preserved through the reconciliation.

## 17. `WriteOp` carries `source_id` + `stable_key` (the CAS key)

Added building the ground store (L2). The uniqueness-CAS invariant is "at
most one live record per (source_id, stable_key)," and `find_span(source_id,
stable_key)` is a store method the spec's own `DocumentPolicy` sketch calls —
so both values must reach the store. FRAMEWORK.md's illustrative `assert_`
call does not show them (it also omits `kind`), so this is a faithful
extension of the op, not a contradiction. They live on the op rather than as
separate parameters to the store's write methods so a `WriteOp` remains a
complete, self-describing value: serialized into the WAL entry, it gives the
audit trail the exact span each write touched, and it stays replayable
without a side channel. `source_id`/`stable_key` are required kwargs on
`assert_`/`supersede` and `None` for `forget` (which targets a `record_id`
directly). No new kernel symbols — two fields on an existing budgeted type.

## 18. `EvidenceItem` carries `record_id`

Added building the composition root (Corpus). The agent-facing surface mints
an opaque `hit_id` per evidence item and `fetch(hit_id)` must resolve back to
the exact record to re-read it — so an `EvidenceItem` has to know which record
it came from. FRAMEWORK.md's EvidenceItem sketch lists provenance/trust/span
fields but not the record's own id; adding it is a faithful extension for a
provenance-first result (an evidence item that cannot be traced to its source
record is under-specified). It never crosses the MCP boundary — the surface
exposes only the opaque hit_id (HitRegistry, decisions.md #12) — so this is an
internal provenance anchor, not new model-visible metadata. No new kernel
symbol; one field on an existing budgeted type.

## 19. Span identity and record-id resolution are namespace-scoped

Closes a defect reproduced by the Milestone B derivation-engine tests before
BM25/ANN went live. The 0002 uniqueness-CAS index was UNIQUE (source_id,
stable_key) over live rows — GLOBAL across namespaces — while source_id and
stable_key are caller-chosen strings. Two tenants ingesting a document under
the same source id therefore collided on the same span: the second tenant's
assert was silently no-opped (identical content) or CONVERTED TO A SUPERSEDE
OF THE FIRST TENANT'S LIVE RECORD (different content). Cross-tenant write
interference through the write path — the CI-03 failure class on the write
side, and `require_writer_namespace` could not catch it because the op's own
provenance was honest; it was the span key that crossed the partition.

Resolution, applied at every layer that touches span or record identity:

- Migration 0005 rebuilds the invariant index as UNIQUE (namespace,
  source_id, stable_key) WHERE tx_to IS NULL. Strictly looser than the old
  index, so it applies safely to a populated database.
- `find_span` requires a `namespace` kwarg; `_apply_assert`'s span lookups,
  `_supersede_rows`' close-UPDATE, and the assert's ON CONFLICT target are
  all namespace-scoped. A supersede can no longer close a row outside the
  writer's partition (it now fails loudly instead).
- `forget` is scoped too, which matters because identical content in two
  tenants legitimately shares a record_id (content-addressing does not salt
  by tenant): `GroundStore.apply(op, namespace=...)` carries the acting
  partition (the orchestrator passes `principal.namespace`); a forget whose
  target is not live in that partition fails closed with the same error as a
  nonexistent record (no cross-partition probing); an UNSCOPED forget of a
  record_id live in several namespaces is refused as ambiguous rather than
  resolved arbitrarily.
- `get_live` accepts an optional `namespace` filter and `Corpus.fetch`
  passes the caller's, so a shared-content record_id resolves to the
  caller's own tenant's row, not an arbitrary one.

## 20. The WAL entry for a converted assert names what it superseded

Closes the second defect the same engine tests reproduced. When an assert
found a live span with different content and converted itself to a
supersede, the WAL entry — appended before the conflict was discovered —
still read as a plain assert with only the new record_id. The intent log
omitted the supersession it performed, so any WAL consumer (the derivation
engine first) never learned the old record's id and left its derived view
rows live: a superseded chunk stayed retrievable through BM25/ANN forever.

Resolution: `_apply_assert` pre-checks the span inside its transaction and
appends a payload that says what actually happened — a plain assert, an
idempotent re-assert, or `{"op": "assert", "converted": "supersede",
"record_id": ..., "old_id": ...}`. Under the v1 single-committer-per-
namespace invariant the pre-check is exact; the partial unique index still
arbitrates the out-of-invariant concurrent race at the database level, and
in that rare losing path the payload lacks old_id (recovery from an
out-of-invariant deployment is a view rebuild, not the incremental tail).
The derivation engine keys its delete-then-rederive on the record_ids named
in WAL payloads, which is why payload truthfulness is a correctness
requirement and not cosmetics.

## 21. BM25 go/no-go (decision #4) resolved: NO-GO — Postgres tsvector+GIN

Checked on this machine 2026-08-09: ParadeDB `pg_search` is not installed and
stock Postgres FTS is. Per #4's own terms the backing is the sanctioned
fallback: a tsvector+GIN lexical view (derivation/views/lexical.py) ranked by
`ts_rank_cd`, behind an operator whose `kind="bm25"` names the SLOT in the
plan vocabulary, not the formula. The conformance score contract was written
"monotonic in relevance" precisely so this backend passes the same gate; a
later swap to a true BM25 backend (pg_search built from source, or an
external engine) changes lexical.py/bm25_op.py internals and nothing above
them. Query-time honesty is kept in the trace: `score_method="ts_rank_cd"`,
never a claimed "bm25".

## 22. A real reranker's output IS the final candidate set, cut to its depth

The rerank slot (planner/reranker.py) re-scores the top `rerank_depth` fused
candidates with a cross-encoder (default BAAI/bge-reranker-base, lazy-loaded,
sigmoid-squashed scores) and returns ONLY that re-scored head. The tempting
alternative — reranked head plus RRF-scored tail in one CandidateSet — is
exactly the "silently mixed" score set the kernel type's own contract
forbids; monotone-in-preference scores of one declared method, cut at a
depth the dated rule table declares and EXPLAIN shows before execution, is
the honest shape. Under the IdentityReranker (no ML extras) the compiler
omits the rerank step from the plan entirely, so an EXPLAIN never claims a
rerank that will not happen. rerank_depth=16 is hand-declared in
policy/rule_table.py (version 2026-08-10) alongside equal fusion weights —
no tuning data exists yet, and Phase 2's promotion loop is what earns
changes to either.

## 23. View freshness: synchronous ingest-time refresh; views own their schema

Two derivation-engine resolutions the spec leaves open. (a) Freshness: v1
has no background derivation daemon. `Corpus.ingest` calls
`DerivationEngine.refresh(namespace)` synchronously after the write path
commits — read-your-writes for the ingesting caller, no concurrent writer
alongside the namespace's single committer (decisions.md #14), and exactly
the touched chunks re-derive because DocumentPolicy no-ops unchanged spans
so the WAL carries only real changes. The engine advances each per-(view,
namespace) cursor in the SAME transaction as the view writes it covers
(delete-then-rederive per touched record_id, so any re-run is idempotent).
An erasure receipt's `propagated_to` therefore reflects propagation at the
NEXT refresh, not the forget's own transaction. (b) Schema: view tables are
created by each ViewBuilder's `ensure_schema`, not by numbered migrations —
the dense table's `vector(<dim>)` column takes its dimension from the
configured embedder, which static SQL cannot express, and one consistent
rule beats one asymmetric exception. `CREATE EXTENSION vector` lives in the
dense view's ensure_schema for the same reason: core migrations must
succeed on a Postgres without pgvector (grep/BM25-only deployments never
need it). Migration 0004 carries only the view-agnostic substrate
(view_cursors, lineage_edges).

## 24. Compiler-side defense in depth: namespace backstop + per-operator dedup

Adopted from the Milestone B adversarial tenancy review, which confirmed the
core isolation properties hold (cross-namespace search/fetch, stale-view
after supersede/forget, the same-record_id-across-tenants collision, and
planted "lying" view rows were all defeated by the operator's records-join)
but found two gaps worth closing above the operator layer.

(a) The conformance gate runs every operator's `execute()` through the
shared probe path (operators/common.execute_conformance) when the fragment
carries synthetic `rows`, so it NEVER exercises an operator's real
`_execute_query` SQL — the line that filters `records.namespace`. A
hand-modified operator that drops that filter therefore passes registration.
Only reachable by code that wires a modified operator into an
OperatorRegistry (Corpus.open wires only the correct first-party ones, and
`datum.register_operator()` is still an unbuilt symbol), so it is not an
end-user-reachable leak — but the gate's advertised guarantee ("a
mistranslating backend cannot register") should not depend on the operator
being honest about the one property the gate exists to enforce.

(b) The fusion loop counted record OCCURRENCES across all operator result
lists, not DISTINCT operators, so a single operator returning the same
record_id twice inflated both its RRF rank and the cross-operator agreement
signal (which feeds the caller-visible sufficiency). Not reachable through
Corpus's public surface today (DocumentPolicy's positional stable_key makes
two live spans in one namespace unable to share a record_id), but latent.

Resolution, both in planner/compiler.py `_run`, applied to every operator's
output before it can influence fusion/EXPLAIN/evidence: a NAMESPACE BACKSTOP
drops any returned record whose `provenance.writer.namespace` is not the
caller's (the compiler never trusts an operator to have scoped itself), and
PER-OPERATOR DEDUP collapses repeat listings so RRF and agreement count
distinct operator kinds (`found_by` is now `dict[record_id, set[kind]]`).
Corpus.fetch already had this defense in depth (scoped get_live + a redundant
namespace check); this brings the search path to parity. The operator-level
SQL filter stays — this is a second layer, not a replacement.

## 25. `forget(record_id)` is content-scoped within a namespace, by design

The review noted that `_apply_forget` closes every live row matching
`(record_id, namespace)`, so forgetting one span also closes a DIFFERENT
span (distinct stable_key) that happens to hold identical content — because
record_id is a content hash, identical content IS the same record_id. This
is an availability/least-surprise wrinkle, not a leak (it is strictly
within one namespace; cross-tenant identical content stays isolated, decision
#19), and it is not reachable through Corpus (which exposes no forget verb
and whose DocumentPolicy cannot produce two same-record_id live spans in a
namespace anyway) — it needs a raw GroundStore.apply of a hand-built forget.

Kept as-is deliberately at v1: forget is an ERASURE primitive, and erasing
"this content" from a namespace by closing every live copy of it is a
defensible reading of erasure (GDPR-style "delete this datum" is about the
content, not one arbitrary copy of it). The span-scoped alternative (forget
exactly one row by row_id, leaving content-identical siblings live) is the
Phase-1 refinement that arrives with the crypto-shred erasure path, where
per-copy targeting matters because shredding a key is irreversible. Recorded
here so the choice is explicit rather than an accident of the WHERE clause.

## 26. The conformance suite stays synthetic; a LIVE tenancy tier lands in tests (plan step 7)

`ConformanceSuite.run` is called by `register_operator()` with no live
infrastructure, so it can only exercise an operator through the synthetic
probe path — it structurally cannot run the real `_execute_query` SQL where
`WHERE records.namespace = %s` lives, which is why the review could register
a hand-modified fail-open operator (#24). The approved plan's build-order
step 7 ("run the suite against real bm25_op/ann_op ... needs real
multi-tenant data") and `conformance/fixtures.py`'s
`TODO(scratch-namespace provisioning)` both reserve a LIVE tier for exactly
this; that multi-tenant data now exists.

Resolution: keep the in-package suite synthetic and infra-free (its job is to
gate registration anywhere, including a third party's CI, with no database),
and add the live physical-partition-isolation checks as
`tests/conformance/test_live_tenancy.py` — real records in two namespaces,
each real operator's real query path, plus the planted "lying view row" case
the review used. That exercises the SQL the synthetic gate cannot, codifies
the review's Attack 1 as a permanent regression, and closes the gap between
the plan (which scheduled step 7) and HANDOFF §9 (whose numbered list had
dropped it). The compiler namespace backstop (#24) is the runtime defense;
this is the test that proves the operators themselves stay honest.

## 27. Audit trace on a FAILED search is a known gap, deferred to Milestone C

The review noted that when an operator raises inside `PlanCompiler._run`, the
exception propagates out of `Plan.execute()` and `self._trace.persist` (which
runs only after successful fusion) never fires — so a search that errors
leaves no persisted trace, in tension with the MVP's "audit-trail logging
(the persisted Plan trace) is unconditional from v1." Failing closed with no
leak is correct; the gap is purely the missing audit record.

Deferred deliberately to Milestone C (eval gate + failure-mode hardening),
not silently: the honest fix needs a decision the trace schema does not yet
support — `EvidenceState.status` has no error member, and the failure happens
before any evidence exists to persist — so persisting a failure trace means
designing a typed failed-plan trace, which is hardening work, not a one-line
patch to bolt on at the end of the retrieval milestone. Recorded here so it
is a scheduled item, not a discovery, when Milestone C starts.

## 28. Score-contract / robustness review outcomes (Milestone B, second reviewer)

The second adversarial reviewer targeted the score contract, input
robustness, injection, and derivation correctness. SQL/tsquery injection,
ts_rank_cd tie-determinism, ANN cosine range, sufficiency bounds, the
>200-span batch seam, rerank output size, and single-operator plans all HELD
under real attack. Findings that were fixed (each with a regression test that
was verified to fail before the fix), grouped by public-API reachability:

Reachable through `Corpus` (the "it actually works when run" bar), fixed:
- **H1 — repeated section headings caused silent data loss.** Two `## Notes`
  sections keyed to the same stable_key, so the second superseded the first.
  `DocumentPolicy` now disambiguates the CAS key by occurrence within a
  document (first occurrence unchanged for corpus stability); section_path
  (the displayed provenance) is untouched.
- **M2 — hostile query text crashed `search()`.** A NUL byte and a
  huge-term-count query raised out of BM25. `bm25_op` now strips NUL and caps
  the term count before websearch_to_tsquery. (Injection itself was already
  held by the bound-param + websearch_to_tsquery design.)
- **M3 — `path_glob` reported pre-filter sufficiency.** The source filter is
  now a real `source_filter` plan step applied to the fused candidates BEFORE
  the sufficiency score (and shown in EXPLAIN), so the confidence reflects the
  hits actually returned. `Corpus.search` no longer post-filters.
- **L1 — a tiny token budget floor-divided to LIMIT 0**, returning nothing as
  if the corpus were empty. `limit` is now floored at 1.
- **L2 — an empty/whitespace query returned the whole namespace at status=ok.**
  Grep now returns empty for an empty query, matching BM25/ANN, so an empty
  search reports insufficient_evidence.

Defense-in-depth (not reachable via the shipped write path / embedder — the
chunker bounds chunks to 4096 chars and bge never emits a degenerate vector —
but the conformance gate cannot see the real query path, so guarded anyway):
- **H2 — an oversized L2 record could wedge the whole namespace's engine**
  (to_tsvector raises, the batch + WAL cursor roll back, every later refresh
  re-raises). `LexicalView` now caps the INDEXED text with `left(...)` at
  200k chars (far above any real chunk; the canonical L2 record is untouched),
  turning a permanent wedge into at worst reduced recall on one abnormal row.
- **M1 — a zero-norm dense vector yields a NaN cosine score.** `ann_op` drops
  rows whose distance is non-finite rather than surfacing NaN.
- **M4 — a NaN/short cross-encoder output** would scramble or silently
  truncate the ranking. `CrossEncoderReranker` now asserts one finite score
  per candidate, raising a DatumError otherwise.
- **L3 — a NaN agreement** would read as MAX through `max(0, min(1, nan))`.
  `estimate_sufficiency` clamps a non-finite agreement to 0.0.

**H3 — the conformance gate certifies the score contract only on the synthetic
probe path, never the real query SQL** — is the same structural blind spot as
#24/#26; the compiler's dedup + rank-based fusion already contain the
downstream damage (a duplicate or NaN operator score never reaches Evidence),
and `tests/test_milestone_b_hybrid.py` now asserts the score contract
(finite, 1:1, no duplicate ids) directly on each real operator's live path.

One item was NOT fixed and is scheduled: the audit-trace-on-failed-search gap
(decision #27), carried to Milestone C.

## 29. Abstention floor on dense similarity (surfaced by wiring the eval gate)

Wiring `eval/regression.py` to the real hybrid Corpus (Milestone C) made the
fixed set's three abstention cases FAIL: a query whose answer is not in the
corpus came back `status=ok`. Cause: dense retrieval always returns its
k-nearest neighbors, so an out-of-corpus query still yields hits — Milestone
A abstained only by accident (grep returns nothing on no term match). The
blended sufficiency score does NOT separate these cases (positives and
abstentions both land ~0.65–0.72, because RRF scores are rank-based); the one
signal that separates is the top dense cosine similarity (positives >= 0.669,
out-of-corpus <= 0.606 on the fixture).

Resolution: a `RuleTablePolicy._ABSTAIN_MIN_SIMILARITY` floor (0.63), carried
on the `Fusion` decision and applied by the compiler — where the raw ANN
cosine is visible, since `evidence/wrap.py` sees only RRF-flattened scores.
Below the floor the plan returns an empty set -> `insufficient_evidence`; an
`abstain_check` PlanStep makes it visible in EXPLAIN. The floor is set only
when a dense operator is registered (grep/BM25-only keeps empty-means-abstain).

Honest status of the NUMBER (this is not the same epistemic footing as the
declared fusion weights / rerank depth, which were fixed before any fixture
existed): 0.63 is READ OFF the eval fixture — 11 cases on 5 documents, a 0.06
separation gap. It is fixture-derived and uncalibrated; a held-out calibration
slice is Phase 1, exactly as the sufficiency score it complements is
`calibrated=False`. The margin is thin: the jargon-heavy circuit-breaker and
backoff queries (dense ~0.67) are the closest positives and will be the first
to abstain wrongly as the corpus grows — that is the signal calibration is
overdue, not a reason to widen the floor now. The eval gate's role is
therefore REGRESSION-LOCKING from this recorded baseline; a green gate is not
evidence that abstention is "solved." Non-vacuity was proven the same way the
review fixes were: dropping the floor to 0.0 makes exactly the three
abstention cases fail.

Also fixed while here: the walking-skeleton test fixture truncated
`records`/`wal_entries` but not `view_cursors`, leaving a stale cursor ahead
of the RESTART'd WAL so the derivation engine silently never re-derived —
ANN was effectively disabled for every test after the first, and the hybrid
assertions were passing through grep/BM25 alone. The fixture now resets the
view state too, so those tests exercise (and the abstention test now genuinely
proves) the dense path.

## 30. Audit trail is unconditional: see #27 (implemented in Milestone C)

Decision #27 recorded the deferral; Milestone C implemented it. The compiler's
executor now persists a terminal `status="error"` EvidenceState (empty items,
error type + message in `extra`) when a search raises mid-execution, then
re-raises — the failure is recorded, never swallowed, and `explain`/`replay`
work on the failed plan. `EvidenceStatus` gained an `"error"` member (a
compatible Literal widening; audit-only, never returned to a caller). Best-
effort persistence: a failure to write the audit record must not mask the
original exception.

## 31. Multi-format ingestion: Docling → markdown → the existing MarkdownParser

Task #30's DoclingParser (`writepath/policies/docling_parser.py`) is a `Parser`
that reads `DocumentInput.source_path` and lets any Docling-supported format
(docx, pptx, xlsx, html, csv, pdf, image, epub, audio, XML dialects) flow
through the SAME write path, CAS, derivation, and hybrid retrieval as plain
text — a `docling` WritePolicy registered beside `document`, reached by
`Corpus.ingest_file` and by `datum ingest` auto-routing on file extension.

Design: **Docling converts the file to markdown, then the existing tested
`MarkdownParser` sections that markdown** — one sectioning implementation, not
a second that could drift, and tables arrive as inlined markdown text
(searchable) under their heading. The honest v1 limit: structural provenance
is the heading-derived `section_path`; per-item PAGE/BBOX are NOT carried
(`export_to_markdown` drops them). That only matters for paged formats (pdf,
scanned images), which are blocked here anyway (below), so page/bbox mapping
via `iterate_items()` is the Phase-1 enrichment that lands with the PDF/image
pipeline — tested against the formats that actually carry it.

Environment coverage (surfaced, not silently downscoped — §11's rule). The
benchmark (`eval/multiformat_benchmark.py`, `datum benchmark`, and
`tests/eval/test_multiformat.py`) exercises the formats whose Docling backend
needs no downloaded model and passes them end to end: **md, txt, html, csv,
docx, pptx, xlsx** (7/7 ingest + retrieve). Three families are reported
skipped-with-reason, NOT quietly omitted:
  - **pdf, image/scanned** — need Docling's layout (and OCR) models, which
    download from HuggingFace on first use. That egress is unavailable in this
    environment: the models are not cached and HF's network HEAD calls hang
    (the same failure that stalled the test suite until `HF_HUB_OFFLINE=1`).
    The parser handles them unchanged once the models are staged (Artifactory
    `huggingfaceml` remote or a pre-seeded cache — HANDOFF §8's noted path).
  - **audio** — Whisper IS cached, but there is no honest way to synthesize
    speech with a KNOWN transcript to assert retrieval against without a TTS,
    so a fabricated-content audio case would be worse than none.
This is an environment limit on the BENCHMARK's coverage, not a limit of the
parser, and the skipped list makes the boundary explicit at run time.

## 32. Milestone D driven end-to-end over the real MCP transport (LLM-in-the-loop is the one human step)

The plan's final acceptance is "the Agent Tool Surface tested against a real
tool-calling model." The substantive, self-drivable core of that is realized
as `tests/mcp_server/test_serve_e2e.py`: a real `datum serve` SUBPROCESS (its
own process, its own `Corpus`, the actual bge embedder + cross-encoder), a
real `mcp.client` `ClientSession` over the real stdio JSON-RPC transport, the
`initialize` handshake, `list_tools` (exactly the five verbs), and every verb
called and decoded off the wire — search -> fetch(hit_id) -> explain(plan_id),
navigate, since — plus a second server bound to a different tenant proving
namespace fail-closed THROUGH the transport (resolved from the session
principal, never a tool argument). Confirmed on the way in: the kernel
dataclasses (`Evidence`, `SearchHit`, `StructureView`, `ChangeSet`) serialize
cleanly to MCP `structured_content` with no adapter — a real risk this test
existed to catch, since they are stdlib dataclasses, not pydantic models.

The ONE part not covered headlessly is a live LLM autonomously *deciding* to
call the verbs; the test emits exactly the tool calls such a model would, so
only the decision is stubbed, and this is stated plainly rather than claimed
as full model-in-the-loop coverage. The final human step (point an MCP
Code/Desktop MCP client at `datum serve` and use it) is documented in HANDOFF
§15 with a ready client config. This is the honest boundary between what a
headless build can prove and what needs a person with a GUI client attached.

## 33. MarkdownParser suspends heading detection inside fenced code blocks

Found by real MCP use (Milestone D dogfooding): `navigate` over FRAMEWORK.md
returned 11 sentence-fragment "sections" like "honest default per stance-
conflict resolution #4, not a placeholder." The cause — the ATX regex
`^#{1,6}\s+` matched Python `# comment` lines inside the doc's 17 ``` code
fences, so each comment became a heading and re-rooted the tree. This is not
cosmetic: `section_path` is the provenance the surface promises ("a citation
points at where an answer actually lives"), so a hallucinated heading anchors
a hit to a location that does not exist, and it happens in the parse layer
UPSTREAM of everything the conformance gate checks.

Fix: `MarkdownParser` tracks fenced-code state (a >=3 run of backticks or
tildes toggles it; a closing fence repeats the opener's char) and treats
every line inside a fence — and the fence lines themselves — as body, never a
heading candidate. Parser `version` bumped `markdown-v1` -> `markdown-v2` (the
CI-07 lineage tuple: a re-parse under the new logic is a detectable producer
change). Regression tests in `tests/writepath/test_markdown_parser.py` cover
`#`-comments in ``` and ~~~ fences, indented fences, and an unclosed fence
failing safe. The DoclingParser (decision #31) delegates to MarkdownParser,
so its output benefits from the same fix. Left as documented v1 behavior, not
changed here: `navigate`'s `depth` argument is advisory (the real reviewer
also noticed depth=1 did not prune) — deeper structural nesting is the Phase-1
enrichment the navigate docstring already names.

## 34. Default embedder is bge-m3 (multilingual); the abstention floor is per-deployment

Two coupled changes from the real-PDF stress test (a 19-page multilingual
report with 42 graded questions), both replacing v1 defaults that real content
showed were wrong.

(a) **Default embedder: BAAI/bge-small-en-v1.5 -> BAAI/bge-m3.** The stress
test's Japanese/German/Russian facts extracted cleanly but were unretrievable
by an English query — an English-only embedder cannot place a cross-lingual
query near a non-English passage. bge-m3 (1024-dim, 100+ languages, strong on
English too) fixed the multilingual bucket AND lifted overall retrieval
ranking (stress: 25 -> 30 of 42 on strict retrieval scoring). `Embedder` is a
Protocol and `SentenceTransformersEmbedder` is now parameterized
(model/dim/query-prefix), so the swap is one line and a deployment can still
choose the lighter English `bge_small_en()` or a hosted model. bge-m3 uses no
query-instruction prefix (bge-v1.5 did).

(b) **The abstention floor (#29) is now a per-deployment parameter, default
0.44, not one global 0.63 constant.** The stress test proved a single global
dense-cosine floor CANNOT work: absolute cosine SCALE is corpus-dependent
(the diverse report's genuine matches sit ~0.44-0.55; the small homogeneous
eval corpus's sit ~0.53-0.75), and no single threshold separates both — one
corpus's floor wrongly abstains the other's real answers. Measured
confirmation that cheaper "corpus-independent" signals also fail to separate:
the cross-encoder reranker scores weak-but-correct and off-topic BOTH ~0.50
(only slam-dunks reach ~0.71); the top1-vs-mean "peak" is non-discriminating
(an out-of-corpus query can have a sharper peak than an in-corpus one); and a
genuine inversion exists (a fact PRESENT but not semantically salient — a URL
on a cover page, 0.44 — scores below a topically-related but answer-absent
passage, 0.46). So abstention is set per corpus: `Corpus.open(
abstain_min_similarity=...)` overrides the recall-biased 0.44 default (the
eval gate uses 0.53 for its homogeneous corpus, `eval.gate.GATE_ABSTAIN_FLOOR`
— per-corpus calibration of a documented knob, the regression oracle
untouched). Recall bias is deliberate: for a substrate feeding an LLM, a false
abstention (refusing when the answer is present) is worse than returning weak
evidence the model can judge. Auto-deriving the floor from each namespace's
own similarity distribution is the Phase-1 replacement for hand-setting it.

## 35. OCR is ocrmac (multilingual, region-based) by default; picture-embedded text needs a VLM

> **CORRECTED by #36 (2026-08-10).** Two conclusions below were FALSIFIED by
> later measurement: "picture-embedded text needs a VLM" and "Hindi image OCR
> is a genuine platform limit." Both were artifacts of *how the text was being
> read*, not real limits. Picture/chart/diagram text and the Hindi facsimile
> are ALL recoverable with OCR (Apple Vision for the picture labels and chart
> values, EasyOCR for Devanagari) — the true blocker was that Docling's
> `export_to_markdown()` DROPS the text of layout-detected Picture clusters
> (proven: those tokens are in `export_to_dict()` yet absent from the markdown).
> The one still-true observation here — blanket full-page OCR degrades the
> clean text layer — is exactly why #36's fix is a *composition*, not a
> full-page pass. Read #36 for what shipped.

From the PDF stress test's vision questions. The DoclingParser now configures
Docling's OCR to **ocrmac** (Apple Vision) on macOS with a multilingual
recognition set, region-based (not full-page) so a digital PDF's clean text
layer is kept and OCR is applied only to image regions lacking text. Two
measured findings shaped this:

- **Language codes are validated against the installed Vision version.** An
  unsupported code does not raise — it is filtered out. This was learned the
  hard way: an unsupported `hi-IN` in the requested list made Docling raise
  mid-convert and silently cut a 48-record parse to 13. macOS Vision here has
  no Devanagari, so **Hindi image OCR (stress Q27) is a genuine platform
  limit**, honestly reported, not a Datum bug.
- **Full-page OCR is an opt-in, not the default, because it measurably did NOT
  help.** Tested on the stress PDF: `force_full_page_ocr=True` did not recover
  the diagram/org-chart labels (Module E, the Chief Engineer name — still
  absent) AND degraded the clean text layer (40.2k chars -> 36.9k). Apple
  Vision cannot read those stylized/vector picture labels at all, and OCRing
  the whole page loses more (good text) than it gains (nothing here). So
  text embedded in PICTURE regions (diagrams, org charts) and DATA locked in
  chart pixels (a bar's height, a line's annotation) are the honest frontier:
  they need a vision-language model that DESCRIBES pictures (Docling's SmolVLM/
  granite-docling pipeline), which is the scheduled next step, not OCR.
  `force_full_page_ocr` stays exposed for corpora where it does help.

## 36. Image-embedded text IS recoverable with OCR — Docling's markdown export drops it; recover via a region+facsimile+devanagari composition (`image_ocr=True`)

The vision limits recorded in #35 turned out to be false, and finding the true
cause changed the fix from "wait for a VLM" to "a few hundred lines of OCR
plumbing." The stress test's picture questions — chart-bar values (Q11 149,
Q12 2.4), diagram/org-chart labels (Q38 Module E, Q39 the Chief Engineer's
name), the Habitat berth count (Q42), the page-13 facsimile sounding sheet
(Q29) — are ALL recovered now. Stress score **30/42 → 36/42, zero regressions**
(two-way per-question diff, every win attributed to the recovered chunk, all
four contradiction traps still both-surfaced).

**Root cause (measured, not inferred).** Rendering resolution was never the
problem: `OcrMacOptions.scale` already defaults to 3.0, and full-page OCR at
scale 4 still produced no picture text in the markdown. The mechanism is that
Docling reads the picture-region text into its document model but
`export_to_markdown()` DROPS it — the text cells of a layout-detected Picture
cluster are emitted as a bare `<!-- image -->`. Proof: for every target token,
`in_docmodel=1 / in_markdown=0`. So no OCR tuning through Docling could ever
recover it; the text has to be pulled a different way. (And Hindi is not a
platform limit either — macOS Vision lacks Devanagari, but EasyOCR reads it
perfectly at high DPI. #35's Devanagari claim is retracted.)

**Why a COMPOSITION, not a full-page pass.** The first version OCR'd every page
whole and appended it. Measured result: it BACKFIRED. Re-capturing the clean
text layer (a) displaced clean chunks — a URL question (Q41) that passed at
baseline dropped out of top-k, a real regression — and (b) diluted specific
facts inside whole-page blobs (the Hindi sentence stopped surfacing). So
`image_ocr` adds OCR text ONLY where the clean layer offers nothing:
- **REGION** — each layout-detected Picture is cropped at high DPI (scale 4,
  ≈288 DPI; Docling picture bboxes are BOTTOMLEFT-origin — flip before
  cropping) and OCR'd with Apple Vision. Recovers chart values + diagram/
  org-chart labels. No body text.
- **FACSIMILE** — a page whose embedded text layer is < `_FACSIMILE_TEXT_LAYER_MAX`
  (150 chars) is a scan/paste with nothing to duplicate, so its whole page is
  OCR'd. Measured, not tuned: the one facsimile page had 0 chars, the next
  digital page 328 — any constant in that gap classifies identically.
- **DEVANAGARI** — on ordinary digital pages, only lines that are majority
  Devanagari script (≥ 8 letters AND ≥ 0.6 of the line) are kept, from EasyOCR
  (Vision can't read the script). A script-identity filter, so it cannot delete
  a chart's "149"/"2.4", and the count+fraction bounds drop EasyOCR's two
  false-Devanagari modes (long mostly-Latin misreads; tiny 2–4-glyph garbage).

Additive and OFF by default (`Corpus.open(image_ocr=True)`), so a text-native
corpus and the whole existing suite pay nothing and cannot regress; the clean
region-mode Docling markdown is never touched. Output is appended under a
`# Image OCR` anchor (fenced, so stray OCR '#'/'|' can't forge headings/tables)
with per-figure/per-page provenance in the section path. **Cost, stated because
§11 forbids silent downscope:** when a Devanagari language is requested the
Devanagari sweep runs EasyOCR (CPU) on every digital page — ≈6 min for the
19-page stress PDF. One-time, at ingest.

**Honest remaining non-wins, correctly attributed:** Q07/Q28 are large-table
specific-row lookups (extraction is fine; the row lands outside top-k — that is
task #17 table-aware chunking, untouched here). Q24/Q25/Q26 and **Q27** are
RETRIEVAL, not extraction: the content (incl. the Hindi sentence, confirmed a
live record) is in the corpus but an English query does not rank the
cross-lingual / specific chunk into top-k. Auto-derived per-namespace ranking /
a cross-lingual reranker is the lever there, not more OCR. Q42's "which figure
must NOT be used" is an adversarial provenance meta-question; the diagram chunk
now surfaces, and how the answer is used is the LLM's call, not the retriever's.

## 37. Table-aware chunking: large paginated tables become header-carrying row-groups

The last clearly-fixable stress miss (Q07: "for dive D-2025-018 state the
pilot, max depth, duration, samples"). Measured cause: plain FastCDC slices a
46-row dive-log table into ~1.6 KB byte-slabs, and the slab holding
`D-2025-018` carried neither the table header (so none of the column-name words
the query uses — "pilot", "max depth", "duration", "samples" — were in the
chunk) nor enough focus to embed as a unit. The row was extracted and live, but
its chunk never ranked into the top-k. This is a chunking problem, not an
extraction or ranking one, and it is general: paginated tables are everywhere.

Fix: `derivation.chunking.chunk_table_aware`, a thin layer OVER the untouched
FastCDC core (`chunk_structured_body`). A real markdown pipe-table — a run of
`|…|` rows whose SECOND line is a separator, so pipe-bearing prose like
`` `a | b | c` `` is never mistaken for one — is split into ROW-GROUPS, each
re-prefixed with the table's header + separator, so every group is a small,
self-describing, retrievable chunk. Groups are packed by CHARACTER BUDGET (rows
added until the group would exceed `avg_size`), NOT a tuned row count, so the
grouping is robust to row width and was not fitted to Q07. Prose is delegated
to the FastCDC core unchanged, and — the load-bearing property — a body with NO
table returns *exactly* that call's output, byte-for-byte, so every existing
document re-chunks identically and nothing that ingested before regresses
(verified: the 47 existing chunking/writepath tests stay green; 5 new unit
tests cover the table path and the byte-identical guarantee).

Span: all groups of one table share that table block's document char-range —
honest because a group's text is not a contiguous document substring (the
header is re-prefixed), so a single block-level span is the truthful provenance,
not a per-group slice. Result: stress **37 → 38/42, zero regressions**, Q07's
top hit both contains `D-2025-018` AND opens with the `| Dive ID | … | Max
depth | Duration | … |` header (attribution confirmed against hit CONTENT, not
just section name).

Known gap, recorded rather than papered over: a chunker/derivation-logic change
like this is NOT captured in the CI-07 `source_version` lineage tuple, which
tracks only the parser/embedder/extractor version — so re-ingesting an existing
corpus after a chunker change produces (correct) supersedes without a version
string marking why. A derivation-version anchor is the honest Phase-1 addition.

Separately (NOT a framework change, logged for honesty): the stress SCORER was
too literal on Q28 — it demanded "62 hour" while the document (and the chunk the
retriever correctly surfaced) says "62 h". Adding "62 h" as an accepted value
is a scorer-fidelity fix; it moved the tally 36 → 37 with the corpus unchanged.
The cause-labeled progression is therefore: 30 baseline → 36 image-OCR
extraction (#36) → 37 scorer fidelity (Q28) → 38 table chunking (#37). The four
remaining misses (Q24/Q25/Q26/Q27) are all RETRIEVAL RANKING, not extraction:
the content is present (the Hindi sentence is a live record), but an English
query does not rank the cross-lingual/specific chunk into top-k. A cross-lingual
reranker / auto-derived per-namespace ranking is that lever — not more OCR or
chunking.

## 38. Rerank pool guarantees each operator's own top-3, closing a fusion blind spot; the multilingual gap that remains is an upstream extraction defect, not a ranking one

The stress test's last 4 misses (Q24 German, Q25 French, Q26 Russian, Q27
Hindi) turned out to be TWO unrelated defects, found by instrumenting the
compiler directly (per-operator rank, fused rank, and post-rerank rank for
each query) rather than guessing from the symptom.

**Root cause 1 (fixed here): equal-weight RRF structurally buries a
single-operator #1 pick.** Q27's Hindi facsimile chunk was ANN's rank-0
candidate — the strongest possible dense signal — yet its FUSED rank was 37,
past the rerank step's depth-16 cut, because RRF sums contributions across
operators: several records that grep/BM25/ANN each mildly agreed on
accumulated more combined score than a record only one operator found, even
at that operator's top position. The cross-encoder never got a chance to
judge it on content, because it was cut before rerank ever ran.

Fix: `compiler._build_rerank_pool` feeds the reranker the fused top-`depth`
UNIONED with each operator's own top-`_COVERAGE_TOP_N` ranking, so a #1 (or
#2, #3) pick from any single operator always reaches the cross-encoder
regardless of how cross-operator summing ranks it overall — the reranker
still makes the final call. `rerank_depth` (16) is now a per-source cap, not
a single global cut (reranker.py docstring updated to match).

**The coverage width was tuned by measurement, and the first attempt
regressed something — caught by the two-way diff, not assumed safe.**
Guaranteeing each operator's own top-16 (matching `rerank_depth`) fixed Q27
but ALSO pushed an unrelated, previously-correct hit (Q11's chart-value
figure) out of the final top-5: a wider pool means more candidates compete
for the same top-k slots, and the cross-encoder's imperfect judgment got more
chances to make a mistake, not just fix one. `_COVERAGE_TOP_N = 3` (a small,
separate constant, decoupled from `rerank_depth`) fixed Q27 with ZERO
regressions on the full 42-question two-way diff — verified, not assumed,
exactly the discipline the session held throughout: a net-zero trade (one win
for one loss) was rejected even though the raw score was unchanged.

**Root cause 2 (diagnosed, NOT fixed — an honest limit): Docling failed to
promote sections 6, 7, and 7.1–7.4 to real headings.** The German/French/
Russian partner statements (Q24/25/26) are not separate sections at all —
Docling exported them as ONE run-on paragraph, misattributed to an unrelated
earlier heading ("5.1 CTD-9 acquisition service"), because the source PDF's
subsection markers ("7.2 Deutschland", "7.3 France", …) were never classified
as section headers by Docling's layout model (yet "7.5 India" a few lines
later WAS, for reasons internal to Docling's layout detection — an
inconsistency, not a rule). FastCDC then chunks that merged, misattributed
paragraph at arbitrary byte offsets, producing chunks that mix German, French,
and Russian text together — diluting the embedding badly enough that French
and Russian don't even reach ANN's top-50 candidates.

A markdown-regex heuristic to re-detect "N.M Title" outline markers and
promote them to synthetic headings was DESIGNED and explicitly REJECTED after
review: closing this gap safely requires six independent guards (exclude
matches inside existing headings/tables, cap the major number, require
minor-number sequences starting at 1, require 3+ occurrences) discovered one
at a time by hand on a SINGLE document, and one guard was found only after it
was shown to corrupt the already-correct "## 7.5 India" heading — the exact
section_path-shattering failure mode decision #33 exists to warn against.
`DoclingParser` is also the shared ingest path for docx/pptx/xlsx/html/csv, so
a heuristic validated on one PDF would ship to every format. The honest
record: this needs heading recovery from Docling's own layout/style signals
(font, weight, position), not a regex over already-exported markdown — a real
next lever, left as a stated limit rather than patched around.

**Final stress score: 30 baseline → 36 image-OCR (#36) → 37 scorer fidelity
(Q28, not a framework change) → 38 table-aware chunking (#37) → 39 rerank
coverage (#38, Q27) — every step zero regressions.** Q24/Q25/Q26 remain open,
correctly attributed to the Docling heading-detection gap above, not to
ranking or chunking.

## 39. Stress test #2 (unseen document): script families, the image-object pass, metadata ingestion, and the multilingual reranker

A second user-supplied stress PDF (18 pages, 44 questions, a deliberately
DIFFERENT trick set: three-column layout, rotated in-cell headers, nested
tables, Arabic RTL + Tamil facsimiles, a /Rotate-90 page, colour-only Gantt,
near-duplicate annex page, locale chaos, redaction probe, invisible-text and
metadata canaries, degraded fax). Method identical to #36-#38: baseline with
the framework AS-IS, then fix by measured cause, two-way diff at every step,
both corpora + full suite re-verified.

**Baseline 37/44 with zero document-specific tuning** — strong evidence #36/
#37 generalize: the map image, heatmap, stacked-area annotation, degraded fax
(facsimile path), rotated page, rotated headers, nested tables, both locale
traps (both-surfaced), the redaction notice, and the invisible white-text
canary all passed. The 7 misses attributed: Arabic ×3 (language not in the
OCR list), Tamil (no engine), metadata (never ingested), 2 ranking near-misses.

**Fixes, each general and measured (final: doc-2 40/44, doc-1 40/42):**
- **Script families** (`_SCRIPT_FAMILIES`) generalize #36's Devanagari-only
  pass: each family = script letter-regex + the engine that can read it +
  the same count/fraction line filter. Tamil -> Tesseract (`tam`), because
  this EasyOCR release's Tamil model is broken upstream (checkpoint/charset
  mismatch) while tesseract reads the shaped statement perfectly. Missing
  engine = loud warning, never silent.
- **Vision's language list is ORDER-SENSITIVE — measured, decisive:** with
  ar-SA last after six Latin/CJK codes, Vision returned ZERO characters from
  the perfectly legible Arabic statement crop; ar-SA first reads it flawlessly
  (shaped RTL, Arabic-Indic numerals). So Arabic is a family too (its own
  short Vision list), never a tail entry in one long list.
- **Embedded-image-object pass:** pypdfium2's page object list is ground truth
  for "a raster is pasted here", independent of Docling's layout model — the
  Tamil statement was never classified as a Picture. Objects >1.5% of page
  area, not overlapping a detected Picture (>50% area), are cropped and OCR'd.
- **Per-crop plurality arbitration:** an engine fed a foreign script
  HALLUCINATES its own (measured: Tesseract emitted plausible Tamil from the
  Arabic crop, and it passed the per-line filter because it genuinely IS
  Tamil script). On one crop, only the family with the most script letters
  survives (237 Arabic vs ~40 junk Tamil on the measured crop). Full pages
  are NOT arbitrated — a page can host two genuine scripts.
- **PDF document-info metadata** (`doc_metadata=True`, default on): Title/
  Author/Subject/Keywords as a fenced `# Document Metadata` section — the
  keyword canary lives ONLY there and nothing else in the pipeline reads it.
- **Default reranker bge-reranker-base -> bge-reranker-v2-m3**, matching the
  default embedder's multilinguality (same reasoning as #34's embedder swap).
  Measured: the Tamil statement was ANN's rank-0 candidate and reached the
  rerank pool (#38 coverage working as designed), but the English-centric
  base model scored it 0.002 and it lost the top-k to topical-English
  distractors; v2-m3 scores the same-shape Arabic pair 0.80 vs 0.001. CPU
  cost ~35 ms/pair (~0.7 s/query pool). This ALSO fixed doc-1's Q24 (German)
  and Q26 (Russian) — two of the three #38 left open — without touching the
  heading-detection gap itself (the chunks reach the pool via ANN; the
  multilingual reranker now ranks them).

**The one accepted trade, stated as a trade (not zero-regression):** with
v2-m3, doc-1 trap Q21's second value (the Table 6-1 total) sits at rank 5 —
one past the evaluation's top-5 convention (base had it at 2). Datum itself
still returns the chunk (the caller receives the full reranked pool); only
the 5-hit scoring cut counts it lost. +4 real cross-lingual wins against −1
boundary effect, accepted deliberately and recorded.

**Scorer-fidelity notes (not framework changes, logged for honesty):** Q14/
Q15's keys were extended to accept the Tamil-script equivalents the document
actually contains ("180 கிலோமீட்டர்" = 180 km; "இருமுறை நாகப்பட்டினம்" = twice
weekly, Nagapattinam) — the right chunk WAS rank-0; the scorer's Latin-only
literal couldn't see it. Same class as #37's "62 h".

**Honest remaining misses, attributed:** doc-2 Q08/Q09/Q10 (Arabic) are now
EXTRACTED but a purely-English query ranks the Arabic chunk 20-33 in dense
similarity — past every pool; the lever is query-side (multilingual query
expansion / translation gloss at ingest), not more OCR. Doc-2 Q06 is a
COMPARATIVE query ("which instrument is at ALPHA only") whose answer row
carries no "only" semantics — a class top-k chunk retrieval cannot answer
directly; Datum's navigate/fetch verbs are the affordance for it. Doc-1 Q25
(French) remains the #38 heading-detection gap. Doc-1 Q21 as above.

## 40. The multilingual roster: 20 script families, readback-verified, with the sparse-gate + noise-floor that make a broad default safe

"Multilingual" has to mean the DEFAULT configuration, not a hidden knob. The
image-OCR script roster grew from 3 families to 20 — arabic, thai, korean
(Vision, each with its own order-fixed language list per #39's lesson);
devanagari (EasyOCR); tamil, hebrew, greek, bengali, telugu, kannada,
malayalam, gujarati, gurmukhi, sinhala, myanmar, khmer, lao, georgian,
armenian, ethiopic (Tesseract, tessdata_best) — and every family's language
is in `_IMAGE_OCR_LANGS_DEFAULT`. The BM25 lexical channel's text-search
config is now a `Corpus.open(fts_config=...)` knob ('english' default;
'simple' or a language config for predominantly non-English corpora — dense
retrieval is language-agnostic either way).

**Verification is a render→OCR→readback probe, not a claim:** each family's
sample sentence is rendered by CoreText (the OS shaper — PIL's basic renderer
produces garbage for shaped scripts even with raqm present, which made every
engine "fail" until the probe itself was fixed) and read back through the
family's real engine path. **18/20 pass; gujarati and myanmar read their
scripts only weakly with tesseract on rendered text** — kept as best-
available, recorded as weak, never presented as verified-strong.

**The hard lesson: a broad blind roster hallucinates.** First full run on the
stress corpora polluted doc-1 with ~15 junk chunks: on a degraded 1-bit fax
page whose memo Vision read fine, ten tesseract families each emitted
hundreds of chars of plausible junk in their own scripts (every line passing
its own per-line filter), and a sparse chart crop crowned 'incest பலவாறு கறு'
as its arbitration winner. Two heuristic rescue attempts (distinct-letter
counts, mean word length) failed on measurement — Indic combining marks break
naive tokenization — and were ABANDONED rather than stacked (#38's
anti-pattern). The principled fix reuses the existing sparse-gate: expensive
engines run on a facsimile page, like on a crop, ONLY when Vision read ~
nothing there (a scan Vision reads well is a script it knows; blind engines
can only hallucinate over it), Vision families always run (cheap,
self-filtering); the image-object pass skips facsimile pages (the full-page
pass covers them — the object crop was double-ingesting the fax memo); and a
crop-arbitration winner must clear a measured noise floor
(`_MIN_CROP_SCRIPT_LETTERS = 24`: real statement crops carry 100–460 script
letters, every observed junk winner ≤ 25). Cost, also measured: the gates cut
the 20-family ingest from ~14 min back to ~6.5 min per document.

**Re-verified after the roster landed: doc-1 40/42 and doc-2 40/44 both
unchanged (zero new regressions), full suite 251 green.** The roster's
version stamp is `+scr20@` — growing it is a detectable producer change.

## 41. Contextual retrieval (LLM-free) + the ingest-time translation gloss — doc-2 reaches 44/44

Two research-backed levers, both implemented the honest way and verified on
both stress corpora with the two-way diff.

**Contextual retrieval, the LLM-free variant.** The most benchmark-backed
retrieval technique Datum lacked (published measurements: 35–49% retrieval-failure
reduction from prepending chunk context before embedding + BM25, 67% with a
reranker). Datum's chunks already CARRY their context — the heading-derived
`section_path` — so `views.base.contextual_text()` prepends
`"doc › section › subsection"` to the text each retrieval view derives from.
The STORED record is untouched (chunk identity, CAS, what a caller reads —
all exactly as before); only the derived, disposable view input changes,
stamped `dense-v2-ctx`/`lexical-v2-ctx` so the re-derive is a detectable
producer change. Measured effect: doc-2 Q06 — the comparative "installed at
ALPHA only" question previously classified as unanswerable-by-top-k — flipped
to PASS, because Table 2-1's row-groups now embed with their
"2 · Instrumentation" context. Zero regressions anywhere else; the eval
gate's floors held without recalibration.

**The ingest-time English gloss (NLLB-200-distilled-600M).** The last three
doc-2 misses (Arabic Q08/Q09/Q10) were extracted-but-unreachable: an English
query's dense similarity to pure-Arabic text ranked the statement 20–33,
below every retrieval pool — a QUERY-side language gap no amount of OCR
fixes. Each script family now carries an NLLB source code, and family OCR
text gets a machine translation appended IN the same section, explicitly
labeled ("Machine gloss (NLLB-200, arb_Arab→eng): …") so provenance stays
honest — a reader always knows which words the document actually contains,
and the original script text always comes first. Every channel (dense, BM25,
grep, reranker) gains an English handle. `translation_gloss=True` by default
with image_ocr; loud warning + scriptonly ingest when the model is
unavailable. Cost: ~2.4 s per glossed chunk, only on non-Latin family output.

**Result: doc-2 44/44 (from 37/44 baseline — every deliberately-planted trick
retrieved), doc-1 holds 40/42 (the two remaining are the recorded rank-5
trade #39 and the Docling heading gap #38), suite 251 green.** The scorer for
Q14/Q15 was ALSO corrected to accept the Tamil-script equivalents the
document actually contains — recorded as scorer fidelity, not framework gain.

## 42. First public-benchmark validation: BEIR SciFact, nDCG@10 = 0.697

Datum's quality now has a number comparable to published baselines, not just
the two private stress corpora. BEIR SciFact (5,183 scientific abstracts, 300
test queries, the standard zero-shot retrieval benchmark) was run END TO END
through the real system — every document through the full write path (WAL,
CAS, chunking, both views), every query through the real hybrid search +
rerank — with ONE disclosed config change: `abstain_min_similarity=0.0`
(the benchmark measures ranking; abstention would refuse to answer some
queries, which BEIR has no way to score).

**Result: nDCG@10 = 0.6968, recall-any@10 = 0.807** (300 queries, ~1.4 s per
query on CPU; harness `scratchpad/beir_scifact.py`, metric computed directly
from the official qrels). Published reference points (Thakur et al. 2021 and
the BEIR leaderboard): BM25 0.665, DPR 0.318, ANCE 0.507, ColBERTv2 0.693,
SPLADE++ 0.699. Datum lands ABOVE BM25 and ColBERTv2 and at SPLADE++ level —
zero-shot, no corpus-specific tuning, with tenancy, conformance, provenance,
and audit tracing all active in the measured path. Stated honestly: the
largest specialized retrievers (bge-large class, monoT5-3B rerankers) publish
0.72–0.76 on SciFact; Datum's 0.697 is competitive-with-strong-baselines,
not state-of-the-art — the credible claim, and the one the paper should make.

## 43. The VisionDescriber slot: picture understanding as a pluggable, provenance-labeled Protocol

OCR reads text in images; it cannot read a colour-coded Gantt bar or a trend
in a chart's pixels. That understanding needs a VLM — and WHICH VLM is a
deployment choice (frontier API for an enterprise, local model for an
air-gapped site, none for a text corpus). So, like the Embedder and Reranker
before it, it is a Protocol slot: `Corpus.open(vision_describer=…)` accepts
anything with `name`/`version`/`describe(image)->str`. The description lands
in the SAME section as the picture's OCR text, labeled in-text with the
producing model ("Vision description (model@version): …") — interpretation
visibly distinct from document text, the same honest-provenance pattern as
the NLLB gloss. A broken describer warns and never fails the parse (the
figure still ingests OCR-only). Default None: no model, no cost, no silent
behavior.

Measured on this machine, recorded honestly: the slot is proven end-to-end
with a real local model, but NO locally-runnable small VLM here is a usable
describer — granite-docling-258M (a document-conversion model) loops
degenerately on charts, and Qwen2-VL-2B-4bit emits hallucinated garbage
through this mlx_vlm version. `vision_describer.MLXVisionDescriber` ships as
the reference adapter with that caveat in its docstring; the enterprise value
is the socket: plug a frontier VLM into three members and every downstream
layer (chunking, embedding, BM25, rerank, provenance) benefits unchanged.

## 44. The relevance-feedback loop: judgments through signed hit tokens, promotion-gated calibration, per-namespace overrides

The learned relevance loop's MECHANISM, shipped so a deployment with real
traffic can benefit — with the discipline that keeps it from tuning itself
into noise. Three pieces, all tested end-to-end against real Postgres:

- **`Corpus.feedback(hit_id, useful, principal)`** + the sixth MCP verb
  `feedback`: a judgment can only reference a record the caller was actually
  served (the signed hit token resolves or raises) and only in the caller's
  own namespace (fail-closed like fetch — tested with a foreign-namespace
  replay). Every judgment stores the token's plan_id, so it stays attached to
  the persisted, replayable retrieval that produced it — a labeled example,
  never an orphaned thumbs-up. Agent traffic through MCP generates the
  training signal as a side effect of normal use.
- **`datum calibrate --namespace`** (`eval.calibrate.run_calibration`):
  re-executes the actually-judged queries (recovered from their plan traces)
  under a grid of fusion-weight/floor candidates, scores MRR of the
  useful-marked records, and PROMOTES only if the winner beats the current
  policy on a deterministic 80/20 holdout split. Refuses loudly below 8
  judged queries ("refusing to tune on noise") and refuses without holdout
  gain — both refusal paths tested. Deliberately a grid over the rule table's
  declared parameters, not a gradient ranker: honest about how much signal a
  few dozen judgments carry. Phase-2 replaces the SEARCH, not the discipline.
- **`policy_overrides`**: promoted parameters stored per namespace WITH their
  evidence basis (judged-query count, holdout scores), loaded at Corpus.open,
  applied by RuleTablePolicy per-namespace at plan selection — and visible in
  every plan's EXPLAIN (tested: a calibrated bm25 weight and floor appear in
  the explain output; an uncalibrated namespace keeps the declared defaults).

Suite 258 green; both stress corpora re-verified unchanged (doc-1 40/42,
doc-2 44/44) — the loop is strictly additive until feedback earns a change.

## 45. SciFact re-measured through the repo harness: 0.714 with the English embedder profile

The original BEIR SciFact harness (decision #42) lived in a session scratchpad
and was lost to temp cleanup along with its dataset copy — the paper cited a
script that no longer existed. Rebuilt as `scripts/beir_scifact.py` IN THE
REPO, with the official BEIR dataset download built in and the embedder
selectable by flag. Two runs, both end to end through the full governed
pipeline (write path, tenancy, conformance, rerank, audit trace; sufficiency
threshold zero, disclosed):

- **Reproduction of #42's config (bge-m3 default): nDCG@10 = 0.6936,
  recall-any@10 = 0.8033** — vs #42's recorded 0.6968/0.807. Delta ~0.003 is
  HNSW index-build variance (pgvector HNSW construction is stochastic);
  treat ±0.003 as the noise band for this benchmark at this corpus size.
- **English profile (bge-large-en-v1.5, dim 1024, bge-v1.5 query prefix):
  nDCG@10 = 0.7139, recall-any@10 = 0.840, 1.57 s/query CPU** — above every
  baseline named in the paper's table (BM25 0.665, ColBERTv2 0.693,
  SPLADE++ 0.699). Still below the 0.72–0.76 published by the largest
  specialized models; the paper keeps saying so.

The embedder choice is a deployment profile, not benchmark tuning: bge-large
is the documented stronger English retrieval model (public priors), chosen
because SciFact is English-only; bge-m3 stays the shipping default for
mixed-language corpora (decision #34 unchanged). Paper Table 2 / Figure 10 /
abstract updated to the measured 0.714. Raw results in `docs/bench/`.

Environment notes that cost real time, recorded so they never do again:
Zscaler TLS interception breaks huggingface_hub's certifi-based SSL — fix is
`SSL_CERT_FILE=/opt/homebrew/etc/openssl@3/cert.pem` (and REQUESTS_CA_BUNDLE),
which points it at the bundle that already trusts the corporate CA. Long runs
on a laptop stall when macOS sleeps — pin with `caffeinate -w <pid>`.

## 46. The adversarial head-to-head: Datum vs LangChain, LlamaIndex, Haystack

Both test documents were run through the three most widely used open-source
RAG frameworks under parity rules designed to isolate framework machinery
from model choice: bge-m3 embeddings everywhere, each system retrieves its
top 16, ONE shared external CrossEncoder (bge-reranker-v2-m3) cuts every
system's 16 to the 5 the validated scorer sees, queries verbatim, zero-shot,
each framework on its documented standard PDF pipeline. Scored by the
unmodified benchmarks/adversarial/score.py.

**Totals (doc A / doc B): Datum 40/42, 43/44 · LangChain 30, 34 ·
LlamaIndex 32, 34 · Haystack 32, 35 · LangChain + Unstructured hi_res OCR
32, 34.** Datum's fresh-index numbers are used (43 not 44 on doc B) because
every competitor also ran on a fresh index.

Two headline findings beyond the totals:
1. **Bolt-on OCR nets ~zero.** The hi_res config recovered 9 image/scan
   questions and broke 7 previously-passing footnote/list/table questions
   (element segmentation scrambles fine-grained text order). Extraction
   quality is compositional, not a flag.
2. **A framework can silently misparse its input.** LlamaIndex's default
   reader without its optional file package read raw PDF bytes as text
   (0/44, preserved as llamaindex-results-b-rawfallback.json) and crashed on
   the other document. Scored runs used its documented per-page PDF
   extractor. Haystack 3.0's core lacks its local embedder component; the
   identical SentenceTransformer call its wrapper makes was substituted,
   everything else pure Haystack.

Full grids, versions, timings, rerun commands, and preserved failure
artifacts: benchmarks/adversarial/competitors/RESULTS.md. Paper updated
(new Section 6.5, Table 3, Figure 11 = figures/fig12-head-to-head.svg;
old 6.5/6.6 -> 6.6/6.7, feedback figure -> Figure 12).

## 45. Distribution: a PyPI-ready package and a plain HTTP surface as the non-MCP way in

Making the framework usable by everyone means two different things, and this
closes both. First, packaging: the wheel and sdist now build cleanly through
the standard PEP 517 hooks with full metadata (urls, classifiers, keywords,
SPDX license), and the two things that silently break real wheel installs —
the PEP 561 `py.typed` marker and the runtime-loaded migration `.sql` files —
are verified present in the built artifact, not assumed. A `publish.yml`
workflow releases to PyPI on version tags via Trusted Publishing (no token
stored in the repo), and `ci.yml` runs the suite on a real pgvector Postgres
service container; the ML-dependent tests skip themselves loudly when the
extras are absent, which is the suite's designed degradation, so CI covers
the full core contract surface without a GPU or model downloads. The
distribution NAME may need to change at publish time (the bare name is
likely taken on the index, unverifiable from this network); only the one
`name =` line changes if so — the import stays `import datum` and the CLI
stays `datum`.

Second, access without MCP: `datum serve-http` (src/datum/http_api.py)
exposes the same six verbs over plain JSON-over-HTTP, standard library only,
so any language that can POST JSON can use the framework. The deliberate
constraints are part of the design, not gaps: a bearer token is REQUIRED
(constant-time compared; the server refuses to construct without one — no
anonymous mode exists to misconfigure), one namespace per server process with
the principal bound at startup (a client cannot reach another partition by
editing JSON; multi-tenant means one process per tenant or a real gateway),
localhost bind by default, and structured errors that never leak a stack
trace (a forged hit id is a 400, and failed searches still persist their
audit trace). Seven end-to-end tests drive it over real HTTP against a real
corpus, including both auth failures and the forged-hit case. Suite: 265.
