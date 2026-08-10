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
multi-format DoclingParser (task #30) and its environment-honest benchmark.

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
