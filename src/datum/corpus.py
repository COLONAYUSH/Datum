"""Corpus: the composition root.

Wires every layer together and is the only object a consumer (the MCP server,
the CLI, a Python caller) holds. It sits ABOVE all layers so each layer
package stays strictly one-directional and independently testable; putting
this wiring inside any one layer would force an import cycle (decisions.md #8).

It is where the two entry points the kernel `Plan` deliberately does not own
live — `compile_plan(...)` and `replay(...)` — because both need live runtime
context (registered operators, the trace store) that a classmethod would have
to reach for through module globals.

The agent-facing read verbs return `datum.kernel.surface` types (Evidence,
SearchHit, StructureView, ChangeSet), never `EvidenceState` directly: trust,
authority, and provenance stay server-side, and what crosses to a caller is
an opaque `hit_id` plus content. `fetch(hit_id)` resolves that opaque handle
back through the HitRegistry to the record — the out-of-band envelope in
practice.
"""

from __future__ import annotations

import importlib.util
import warnings
from datetime import datetime

from datum.derivation.engine import DerivationEngine
from datum.derivation.views.base import ViewBuilder
from datum.derivation.views.dense import DenseView, Embedder, SentenceTransformersEmbedder
from datum.derivation.views.lexical import LexicalView
from datum.evidence.wrap import build_evidence_state  # noqa: F401  (kept: documents the L7 seam Corpus owns)
from datum.groundstore.precondition import PreconditionRegistry
from datum.groundstore.store import GroundStore
from datum.kernel.evidence import EvidenceState
from datum.kernel.plan import Budget, Plan
from datum.kernel.principal import Principal
from datum.kernel.surface import (
    ChangeRecord,
    ChangeSet,
    Evidence,
    SearchHit,
    StructureNode,
    StructureView,
)
from datum.mcp_server.hit_registry import HitRegistry
from datum.operators.ann_op import ANNOperator
from datum.operators.bm25_op import BM25Operator
from datum.operators.grep_op import GrepOperator
from datum.operators.registry import OperatorRegistry
from datum.planner.compiler import PlanCompiler
from datum.planner.reranker import Reranker, default_reranker
from datum.policy.rule_table import RuleTablePolicy
from datum.planner.trace import TraceStore
from datum.storage.migrations import run_migrations
from datum.storage.wal import WAL
from datum.writepath.orchestrator import WriteOrchestrator
from datum.writepath.policies.docling_parser import DoclingParser
from datum.writepath.policies.document import DocumentInput, DocumentPolicy


class Corpus:
    def __init__(
        self,
        *,
        wal: WAL,
        store: GroundStore,
        trace: TraceStore,
        hits: HitRegistry,
        registry: OperatorRegistry,
        orchestrator: WriteOrchestrator,
        compiler: PlanCompiler,
        preconditions: PreconditionRegistry,
        engine: DerivationEngine,
        dsn: str = "",
    ) -> None:
        self._dsn = dsn
        self._wal = wal
        self._store = store
        self._trace = trace
        self._hits = hits
        self._registry = registry
        self._orchestrator = orchestrator
        self._compiler = compiler
        self._preconditions = preconditions
        self._engine = engine

    @classmethod
    def open(
        cls,
        dsn: str,
        *,
        hit_signing_key: bytes | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        abstain_min_similarity: float | None = None,
        ocr_full_page: bool = False,
        image_ocr: bool = False,
        image_ocr_langs: list[str] | None = None,
        fts_config: str = "english",
        vision_describer=None,
    ) -> "Corpus":
        """Migrate, wire every layer, and register every operator through the
        conformance gate. If any operator — Datum's own included — failed
        conformance this call would raise ConformanceError at startup: the
        "a mistranslating backend cannot register" guarantee has no
        exceptions for first-party code.

        The hybrid is grep + BM25 always; ANN joins when an embedder is
        available (one passed in, or the default when the `datum[embed]`
        extra is importable). A missing embedder DEGRADES LOUDLY — a
        UserWarning names exactly what is absent and what it costs — never
        silently (§11's no-silent-downscope rule). Reranking follows the same
        pattern via planner.reranker.default_reranker().
        """
        run_migrations(dsn)
        wal = WAL(dsn)
        store = GroundStore(dsn, wal)
        trace = TraceStore(dsn)
        hits = HitRegistry(signing_key=hit_signing_key)
        preconditions = PreconditionRegistry()

        if embedder is None and importlib.util.find_spec("sentence_transformers") is not None:
            embedder = SentenceTransformersEmbedder()
        # fts_config is the Postgres text-search config for the BM25 lexical
        # view AND its query side (they must match; both are stamped into the
        # producer version). 'english' (default) applies English stemming —
        # fine for mostly-English corpora, and non-English terms still match
        # verbatim; a predominantly non-English corpus can pass 'simple'
        # (no stemming, language-neutral) or a language config ('german',
        # 'french', ...). Dense retrieval (bge-m3) is language-agnostic either
        # way — this knob only tunes the lexical channel.
        views: list[ViewBuilder] = [LexicalView(fts_config=fts_config)]
        if embedder is not None:
            views.append(DenseView(embedder))
        else:
            warnings.warn(
                "datum: no embedder available (the 'sentence_transformers' package is not "
                "installed and none was passed to Corpus.open). Retrieval runs WITHOUT the "
                "dense/ANN operator — lexical (BM25) and grep only. Install the "
                "datum[embed] extra or pass embedder= to restore hybrid retrieval.",
                UserWarning,
                stacklevel=2,
            )
        engine = DerivationEngine(dsn, views)
        engine.ensure_schemas()

        registry = OperatorRegistry()
        registry.register(GrepOperator(store))  # every register() is gated by ConformanceSuite
        registry.register(BM25Operator(dsn, fts_config=fts_config))
        if embedder is not None:
            registry.register(ANNOperator(dsn, embedder))

        orchestrator = WriteOrchestrator(store, preconditions)
        orchestrator.register_policy("document", DocumentPolicy(store))
        # The multi-format feeder (task #30): same DocumentPolicy, but its
        # parser is Docling — so docx/pptx/xlsx/html/csv/pdf/… flow through the
        # identical write path, CAS, and derivation as plain text. Docling is
        # lazy-imported inside the parser, so registering this costs nothing
        # until a file is actually ingested through it.
        # image_ocr adds the supplementary high-DPI full-page OCR pass
        # (decisions.md #36) that recovers text Docling's markdown export drops
        # from picture clusters (chart values, diagram/org-chart labels) and
        # from raster regions Docling never classifies as pictures (a pasted
        # facsimile). Off by default — additive, and heavier at ingest — so a
        # text-native corpus pays nothing and nothing that ingested before can
        # regress.
        orchestrator.register_policy(
            "docling",
            DocumentPolicy(
                store,
                parser=DoclingParser(
                    force_full_page_ocr=ocr_full_page,
                    image_ocr=image_ocr,
                    image_ocr_langs=image_ocr_langs,
                    vision_describer=vision_describer,
                ),
            ),
        )

        # The dense-similarity abstention floor is per-deployment (decisions.md
        # #34): recall-biased default for a diverse corpus, raised for a
        # homogeneous one. None => the policy's default. Per-namespace
        # calibrated overrides (the OUTPUT of `datum calibrate`, decisions.md
        # #44) are loaded here so a namespace that has EARNED tuned parameters
        # through judged feedback gets them on every plan; all others keep the
        # hand-declared defaults.
        import psycopg as _psycopg

        with _psycopg.connect(dsn) as _conn:
            override_rows = _conn.execute(
                "SELECT namespace, params FROM policy_overrides"
            ).fetchall()
        policy = RuleTablePolicy(
            abstain_min_similarity=abstain_min_similarity,
            overrides={ns: params for ns, params in override_rows},
        )
        compiler = PlanCompiler(
            registry, store, trace, policy=policy, reranker=reranker or default_reranker()
        )
        return cls(
            wal=wal, store=store, trace=trace, hits=hits, registry=registry,
            orchestrator=orchestrator, compiler=compiler, preconditions=preconditions,
            engine=engine, dsn=dsn,
        )

    def close(self) -> None:
        self._registry.close()  # bm25/ann hold their own lazy connections
        self._engine.close()
        self._store.close()
        self._trace.close()
        self._wal.close()

    def __enter__(self) -> "Corpus":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- write side ---

    @property
    def precondition(self):
        """`@corpus.precondition` registers a reject-destructive-composition
        check (FRAMEWORK.md §Core abstractions #1's example), delegating to
        the shared PreconditionRegistry the write path consults.
        """
        return self._preconditions.precondition

    def ingest(
        self,
        source_id: str,
        text: str,
        principal: Principal,
        *,
        content_type: str = "text/markdown",
    ) -> int:
        """Ingest a document through the L3 write path, then bring the L4
        views current for the writer's namespace. Returns the number of
        write ops applied (asserts + supersedes; unchanged spans are no-ops).

        The refresh is synchronous and runs AFTER the write committed: the
        caller that just ingested reads its own writes through BM25/ANN, and
        the engine never runs concurrently with this namespace's committer
        (v1's single-committer invariant, decisions.md #14). Because
        DocumentPolicy no-ops unchanged spans, the refresh re-derives exactly
        the chunks this ingest touched.
        """
        raw = DocumentInput(
            source_id=source_id, policy_id="default-acl", text=text, content_type=content_type  # type: ignore[arg-type]
        )
        results = self._orchestrator.execute("document", raw, principal)
        self._engine.refresh(principal.namespace)
        return len(results)

    def ingest_file(
        self,
        path: str,
        principal: Principal,
        *,
        source_id: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> int:
        """Ingest a FILE of any Docling-supported format (docx, pptx, xlsx,
        html, csv, pdf, …) through the multi-format 'docling' policy, then
        refresh the L4 views. Same return contract as `ingest`. The file is
        read by Docling from `path`; `source_id` defaults to the file's stem.

        Binary/rich formats route here; plain text and markdown can use
        `ingest` (the dependency-free MarkdownParser) or here interchangeably.

        `source_id` defaults to the file's NAME (with extension), matching what
        `datum ingest` passes and the filename-as-source-id convention the text
        path uses — so the same file ingested via `ingest` and `ingest_file`
        shares a source_id (and thus supersedes) rather than forking into two
        independent record sets. `source_id` is half the CAS key.
        """
        from pathlib import Path

        resolved = Path(path)
        raw = DocumentInput(
            source_id=source_id or resolved.name,
            policy_id="default-acl",  # type: ignore[arg-type]
            text="",
            content_type=content_type,
            source_path=str(resolved),
        )
        results = self._orchestrator.execute("docling", raw, principal)
        self._engine.refresh(principal.namespace)
        return len(results)

    # --- read side (kernel Plan entry points that need live context) ---

    def compile_plan(
        self,
        query: str,
        principal: Principal,
        budget: Budget | None = None,
        *,
        path_glob: str | None = None,
    ) -> Plan:
        return self._compiler.compile(query, principal, budget, path_glob=path_glob)

    def replay(self, plan_id: str, *, against: str | None = None) -> EvidenceState:
        """Replay-by-record by default: return the EvidenceState the plan
        actually produced, reconstructed from its persisted trace, NOT
        recomputed — so it reproduces exactly even after the corpus changed.
        `against="current_champion"` instead re-executes the same query
        against today's corpus and policy (an explicit, different operation).
        """
        loaded = self._trace.load(plan_id)
        if loaded is None:
            raise KeyError(f"no persisted trace for plan_id {plan_id!r}")
        recorded_plan, recorded_evidence = loaded
        if against is None:
            return recorded_evidence
        if against == "current_champion":
            query = _query_from_plan(recorded_plan)
            # Recover the source filter too: the recorded plan may carry a
            # source_filter step, and a champion re-run that dropped it would
            # answer a BROADER question than the plan it claims to replay.
            path_glob = _path_glob_from_plan(recorded_plan)
            fresh_plan = self._compiler.compile(
                query, recorded_plan.principal, recorded_plan.budget, path_glob=path_glob
            )
            return fresh_plan.execute()
        raise ValueError(f"unknown replay target {against!r}; use None or 'current_champion'.")

    # --- agent-facing surface (returns kernel.surface types) ---

    def search(
        self,
        query: str,
        *,
        principal: Principal,
        path_glob: str | None = None,
        budget: Budget | None = None,
    ) -> Evidence:
        # path_glob is compiled INTO the plan (a real source_filter step), so
        # it applies to the fused candidates before the sufficiency score is
        # computed — the confidence returned reflects the filtered hits, not a
        # pre-filter set (review finding M3) — and it shows up in EXPLAIN.
        plan = self._compiler.compile(query, principal, budget, path_glob=path_glob)
        evidence = plan.execute()  # runs, and persists the trace for replay/explain
        items = evidence.items
        hits = tuple(
            SearchHit(
                hit_id=self._hits.issue(content_ref=item.record_id, version=plan.plan_id),
                content=item.content,
                source_path=item.section_path[0] if item.section_path else "",
                section_path=item.section_path,
                page=item.page,
                score=None,  # calibrated scoring is Phase 1; do not surface a raw number as if calibrated
            )
            for item in items
        )
        status = evidence.status if hits else "insufficient_evidence"
        return Evidence(
            hits=hits,
            status=status,
            sufficiency=evidence.sufficiency if hits else 0.0,
            plan_id=plan.plan_id,
        )

    def fetch(self, hit_id: str, *, principal: Principal) -> SearchHit | None:
        """Resolve an opaque hit_id back to its record's full content. Returns
        None if the hit resolves to a record no longer live (superseded or
        forgotten since it was surfaced), or one outside the caller's
        namespace (fail closed — a hit_id from another partition never
        yields content).
        """
        payload = self._hits.resolve(hit_id)  # raises HitIntegrityError on a bad/forged id
        # Namespace-scoped lookup: identical content in two tenants shares a
        # record_id (decisions.md #19), so an unscoped get_live could return
        # the OTHER tenant's row and wrongly fail this caller's fetch.
        record = self._store.get_live(payload["content_ref"], namespace=principal.namespace)
        if record is None:
            return None
        if record.provenance.writer.namespace != principal.namespace:
            return None  # fail closed across namespaces (redundant with the scoped lookup, kept)
        body = record.body
        section_path = body.section_path if hasattr(body, "section_path") else ()
        page = body.page if hasattr(body, "page") else None
        return SearchHit(
            hit_id=hit_id,
            content=record.body_text(),
            source_path=section_path[0] if section_path else "",
            section_path=section_path,
            page=page,
            score=None,
        )

    def feedback(self, hit_id: str, useful: bool, *, principal: Principal) -> bool:
        """Record a relevance judgment for a served hit (decisions.md #44):
        the raw material of the learned relevance loop. The hit token is
        resolved (forged ids raise), the record is looked up namespace-scoped
        (fail closed: feedback can only ever reference a record the caller was
        actually authorized to see), and the judgment is stored with the
        plan_id the token carries — so every judgment stays attached to the
        replayable retrieval that produced it. Returns False when the hit no
        longer resolves in the caller's namespace (superseded/foreign), True
        when recorded. `datum calibrate` consumes these rows.
        """
        payload = self._hits.resolve(hit_id)  # raises HitIntegrityError on a forged id
        record = self._store.get_live(payload["content_ref"], namespace=principal.namespace)
        if record is None or record.provenance.writer.namespace != principal.namespace:
            return False  # fail closed across namespaces, like fetch()
        import psycopg as _psycopg

        with _psycopg.connect(self._dsn) as conn:
            conn.execute(
                "INSERT INTO relevance_feedback (namespace, plan_id, record_id, useful, principal_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (principal.namespace, payload["version"], payload["content_ref"], useful, principal.id),
            )
            conn.commit()
        return True

    def navigate(
        self, ref: str, *, principal: Principal, depth: int | None = None
    ) -> StructureView:
        """Structure-first browse: the section tree of `ref` (a source id)
        within the caller's namespace, without materializing chunk text —
        the late-bound-granularity affordance (structure now, `fetch` for
        content). Leaves carry a hit_id so a caller can fetch them.

        `depth` is advisory at v1: the tree this builds is two levels
        (document -> its sections), so any depth >= 1 returns the same
        shape. Deeper nesting (sub-sections, tables) is a Phase 1 enrichment
        that arrives with the richer structural parse; the parameter exists
        now so the verb's signature does not change when it does.
        """
        del depth  # advisory at v1 — see docstring
        children: list[StructureNode] = []
        seen: set[tuple[str, ...]] = set()
        for record in self._store.live_in_namespace(principal.namespace):
            body = record.body
            path = body.section_path if hasattr(body, "section_path") else ()
            if not path or path[0] != ref or path in seen:
                continue
            seen.add(path)
            children.append(
                StructureNode(
                    path="/".join(path),
                    kind="section",
                    children=(),
                    hit_id=self._hits.issue(content_ref=record.id, version="navigate"),
                )
            )
        return StructureView(root=StructureNode(path=ref, kind="document", children=tuple(children)))

    def explain(self, plan_id: str, *, principal: Principal) -> str:
        """The EXPLAIN of a past plan, reconstructed from its trace. Distinct
        from running anything — this is the audit view of what a retrieval
        decided to do. Namespace fail-closed: a principal can only explain a
        plan that ran in its own namespace, so a plan_id from another
        partition yields the same not-found response as a nonexistent one
        (it never confirms the plan exists, let alone leaks its steps).
        """
        loaded = self._trace.load(plan_id)
        if loaded is None or loaded[0].principal.namespace != principal.namespace:
            return f"no persisted trace for plan_id {plan_id!r}"
        plan, _ = loaded
        return plan.explain()

    def since(self, marker: str | None, *, principal: Principal) -> ChangeSet:
        """The change feed for the caller's namespace since `marker` (an
        opaque WAL position from a prior call's `as_of_marker`). Backed
        directly by the WAL tail (storage.wal), namespace-scoped so it is
        loss-free under v1's single-committer invariant (decisions.md #14).
        """
        marker_int = int(marker) if marker not in (None, "") else None
        changes: list[ChangeRecord] = []
        as_of = marker_int or 0
        for entry in self._wal.tail_since(marker_int, namespace=principal.namespace):
            as_of = entry["tx_id"]
            payload = entry["payload"]
            op = payload.get("op")
            kind = {"assert": "created", "supersede": "created", "forget": "forgotten"}.get(op, "created")
            record_id = payload.get("record_id", "")
            changes.append(
                ChangeRecord(
                    hit_id=self._hits.issue(content_ref=record_id, version="since") if record_id else "",
                    change_kind=kind,  # type: ignore[arg-type]
                    occurred_at=entry["created_at"],
                )
            )
        return ChangeSet(
            changes=tuple(changes),
            since_marker=str(marker_int) if marker_int is not None else "",
            as_of_marker=str(as_of),
        )


def _query_from_plan(plan: Plan) -> str:
    """Recover the query text from a compiled plan's search step (for an
    explicit re-execution). The compiler records it in the search step params.
    """
    for step in plan.steps:
        if step.op_name == "search" and "query" in step.params:
            return str(step.params["query"])
    raise ValueError(f"plan {plan.plan_id!r} has no search step carrying a query to re-execute.")


def _path_glob_from_plan(plan: Plan) -> str | None:
    """Recover the source filter (if any) from a compiled plan's source_filter
    step, so a champion re-run applies the same narrowing the recorded plan
    did. None when the plan carried no filter.
    """
    for step in plan.steps:
        if step.op_name == "source_filter":
            value = step.params.get("path_glob")
            return str(value) if value is not None else None
    return None
