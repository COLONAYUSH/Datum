"""GroundStore: L2, the canonical bitemporal record store.

The single safety-critical module in v1. It owns two invariants FRAMEWORK.md
makes load-bearing:

1. **At most one live record per (source_id, stable_key).** Enforced by the
   partial unique index `records_one_live_per_span` (migrations/0002), not by
   application-level check-then-insert (which has a TOCTOU race). An assert
   for a span that already has a live record is resolved by the database's
   own `ON CONFLICT` on that index — never by a Python read-then-write that
   two writers could interleave. This is the structural fix for the Mem0
   #4892 write-race class (paper Figure 5).

2. **Supersede is atomic with its WAL append.** Closing the old row's tx_to
   and inserting the new row happen in ONE transaction that also appends the
   WAL entry (via storage.wal.WAL.append_in_txn on this store's own cursor —
   decisions.md #11), so no reader ever sees both versions live or neither.
   The WAL append is the single commit point: if it or any record mutation
   fails, the whole write rolls back.

The store's connection runs autocommit=True; every write wraps itself in an
explicit `with conn.transaction()` block (which issues BEGIN/COMMIT around
it even under autocommit), so reads never hold a transaction/snapshot open
between calls while writes are still strictly atomic. This object is not
thread-safe (one psycopg connection); concurrent writers use separate
GroundStore instances, which is exactly how the v1 single-committer-per-
namespace invariant is realized and how the concurrency test drives it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg

from datum.kernel.errors import AdmissionError, DatumError
from datum.kernel.ids import PolicyID, RecordID
from datum.kernel.principal import Principal
from datum.kernel.record import (
    BoundingBox,
    ProvenanceCapsule,
    Record,
    Span,
    StructuredBody,
    TableCell,
)
from datum.kernel.writeop import ErasureReceipt, WriteOp
from datum.storage.wal import WAL


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- body <-> JSON (round-trips str | StructuredBody exactly) ---


def _serialize_body(body: str | StructuredBody) -> tuple[dict[str, Any], str]:
    """Return (json-encodable body dict, flattened text). The discriminator
    `t` records whether the original was a bare string or a StructuredBody so
    deserialization reconstructs exactly the type the kernel Record carried.
    """
    if isinstance(body, str):
        return {"t": "s", "text": body}, body
    bbox = None
    if body.bbox is not None:
        bbox = {
            "page": body.bbox.page,
            "x0": body.bbox.x0,
            "y0": body.bbox.y0,
            "x1": body.bbox.x1,
            "y1": body.bbox.y1,
        }
    cells = None
    if body.table_cells is not None:
        cells = [
            {"row": c.row, "col": c.col, "text": c.text, "is_header": c.is_header}
            for c in body.table_cells
        ]
    span = {"start": body.span.start, "end": body.span.end} if body.span is not None else None
    return (
        {
            "t": "struct",
            "text": body.text,
            "section_path": list(body.section_path),
            "page": body.page,
            "bbox": bbox,
            "table_cells": cells,
            "span": span,
        },
        body.text,
    )


def _deserialize_body(data: dict[str, Any]) -> str | StructuredBody:
    if data.get("t") == "s":
        return data["text"]
    bbox = None
    if data.get("bbox") is not None:
        b = data["bbox"]
        bbox = BoundingBox(page=b["page"], x0=b["x0"], y0=b["y0"], x1=b["x1"], y1=b["y1"])
    cells = None
    if data.get("table_cells") is not None:
        cells = tuple(
            TableCell(row=c["row"], col=c["col"], text=c["text"], is_header=c["is_header"])
            for c in data["table_cells"]
        )
    span = None
    if data.get("span") is not None:
        span = Span(start=data["span"]["start"], end=data["span"]["end"])
    return StructuredBody(
        text=data["text"],
        section_path=tuple(data.get("section_path", ())),
        page=data.get("page"),
        bbox=bbox,
        table_cells=cells,
        span=span,
    )


def _serialize_provenance(p: ProvenanceCapsule) -> dict[str, Any]:
    return {
        "writer": {
            "id": p.writer.id,
            "namespace": p.writer.namespace,
            "capabilities": sorted(p.writer.capabilities),
        },
        "ingestion_path": p.ingestion_path,
        "authority_tier": p.authority_tier,
        "trust_class": p.trust_class,
        "source_version": p.source_version,
    }


def _deserialize_provenance(data: dict[str, Any]) -> ProvenanceCapsule:
    w = data["writer"]
    return ProvenanceCapsule(
        writer=Principal(
            id=w["id"], namespace=w["namespace"], capabilities=frozenset(w["capabilities"])
        ),
        ingestion_path=data["ingestion_path"],
        authority_tier=data["authority_tier"],
        trust_class=data["trust_class"],
        source_version=data["source_version"],
    )


def compute_record_id(body: str | StructuredBody, kind: str) -> RecordID:
    """The content-addressed RecordID: a hash of (body, structure, kind).

    Structure is included (via the serialized StructuredBody, which carries
    section_path/page/span), so the same text in two different sections
    hashes differently — which is what makes `record_id` a sound idempotency
    key per span rather than colliding identical prose across the corpus.
    """
    body_json, _ = _serialize_body(body)
    canonical = json.dumps({"body": body_json, "kind": kind}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return RecordID(f"rec_{digest}")


_SELECT_COLUMNS = (
    "record_id, kind, body, valid_from, valid_to, tx_from, tx_to, "
    "provenance, policy_id, parser_confidence, supersedes"
)

# The public face of the two internals above/below, for L5 operators that
# SELECT record columns through a view-table join (bm25_op, ann_op) and must
# decode them to kernel Records IDENTICALLY to how this store does — one
# decoding implementation, not per-operator copies that can drift. The
# column list is relative to the records table; qualify with an alias
# (e.g. "r.") via record_select_columns() when joining.
RECORD_SELECT_COLUMNS = _SELECT_COLUMNS


def record_select_columns(alias: str) -> str:
    """The records column list qualified with a table alias, for joins."""
    return ", ".join(f"{alias}.{col.strip()}" for col in _SELECT_COLUMNS.split(","))


def record_from_row(row: tuple[Any, ...]) -> Record:
    """Decode one row of RECORD_SELECT_COLUMNS into a kernel Record."""
    return _row_to_record(row)


def _row_to_record(row: tuple[Any, ...]) -> Record:
    (
        record_id,
        kind,
        body_json,
        valid_from,
        valid_to,
        tx_from,
        tx_to,
        provenance_json,
        policy_id,
        parser_confidence,
        supersedes,
    ) = row
    return Record(
        id=RecordID(record_id),
        kind=kind,
        body=_deserialize_body(body_json),
        valid_from=valid_from,
        valid_to=valid_to,
        tx_from=tx_from,
        tx_to=tx_to,
        provenance=_deserialize_provenance(provenance_json),
        policy_id=PolicyID(policy_id),
        parser_confidence=parser_confidence,
        supersedes=RecordID(supersedes) if supersedes is not None else None,
    )


class GroundStore:
    def __init__(self, dsn: str, wal: WAL) -> None:
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._wal = wal

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "GroundStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- write path ---

    def apply(self, op: WriteOp, *, namespace: str | None = None) -> RecordID | ErasureReceipt:
        """Apply a single WriteOp atomically (record mutation + WAL append in
        one transaction). Returns the resulting live RecordID for
        assert/supersede, or an ErasureReceipt for forget.

        `namespace` is the acting partition. assert/supersede already carry it
        in their provenance (decisions.md #7); passing it here additionally
        asserts the two agree (defense in depth at the L2/L3 seam). forget
        carries no provenance, so `namespace` is how a caller scopes it —
        without it, a forget whose target is live in more than one namespace
        is refused as ambiguous rather than resolved arbitrarily
        (decisions.md #19).
        """
        if op.kind in ("assert", "supersede"):
            if (
                namespace is not None
                and op.provenance is not None
                and op.provenance.writer.namespace != namespace
            ):
                raise AdmissionError(
                    f"op provenance namespace {op.provenance.writer.namespace!r} does not "
                    f"match the acting namespace {namespace!r}."
                )
            if op.kind == "assert":
                return self._apply_assert(op)
            return self._apply_supersede(op)
        if op.kind == "forget":
            return self._apply_forget(op, namespace)
        raise DatumError(f"unknown WriteOp.kind {op.kind!r}")

    def _apply_assert(self, op: WriteOp) -> RecordID:
        assert op.body is not None and op.provenance is not None
        assert op.source_id is not None and op.stable_key is not None and op.policy_id is not None
        namespace = op.provenance.writer.namespace
        record_id = compute_record_id(op.body, kind="chunk")
        body_json, body_text = _serialize_body(op.body)
        prov_json = _serialize_provenance(op.provenance)
        tx_now = _now()

        with self._conn.transaction():
            cur = self._conn.cursor()
            # Pre-check the span INSIDE the transaction so the WAL entry can
            # record what this write actually did — a plain assert, an
            # idempotent no-op, or an assert converted to a supersede (in
            # which case old_id must be in the payload: the derivation engine
            # removes the superseded record's view rows off exactly that
            # field, and an intent log that omits the supersession it
            # performed is wrong on its own terms). Under v1's single-
            # committer-per-namespace invariant this pre-check is exact; the
            # partial unique index below still arbitrates the out-of-
            # invariant concurrent case at the database level.
            existing = cur.execute(
                "SELECT record_id FROM records "
                "WHERE namespace=%s AND source_id=%s AND stable_key=%s AND tx_to IS NULL",
                (namespace, op.source_id, op.stable_key),
            ).fetchone()

            if existing is not None and existing[0] == record_id:
                # Identical content re-asserted: idempotent no-op. The WAL
                # entry records the (redundant) intent; the records table is
                # unchanged. The WAL is an intent log, the table is state.
                self._wal.append_in_txn(
                    cur,
                    {
                        "op": "assert",
                        "record_id": record_id,
                        "source_id": op.source_id,
                        "stable_key": op.stable_key,
                    },
                    namespace=namespace,
                )
                return record_id

            if existing is not None:
                # Different content for a span that already has a live
                # version: the caller asserted believing none existed (a
                # policy that skipped find_span). Convert to a supersede of
                # the live version, in this same transaction, and say so in
                # the WAL.
                wal_tx_id = self._wal.append_in_txn(
                    cur,
                    {
                        "op": "assert",
                        "converted": "supersede",
                        "record_id": record_id,
                        "old_id": existing[0],
                        "source_id": op.source_id,
                        "stable_key": op.stable_key,
                    },
                    namespace=namespace,
                )
                self._supersede_rows(
                    cur, old_record_id=existing[0], op=op, record_id=record_id,
                    body_json=body_json, body_text=body_text, namespace=namespace,
                    prov_json=prov_json, tx_now=tx_now, wal_tx_id=wal_tx_id,
                )
                return record_id

            wal_tx_id = self._wal.append_in_txn(
                cur,
                {
                    "op": "assert",
                    "record_id": record_id,
                    "source_id": op.source_id,
                    "stable_key": op.stable_key,
                },
                namespace=namespace,
            )
            # The CAS: insert only if no live row exists for this span. The
            # partial unique index arbitrates concurrent inserts at the DB
            # level; ON CONFLICT DO NOTHING turns "someone else won" into an
            # empty RETURNING rather than an aborting error.
            inserted = cur.execute(
                f"""
                INSERT INTO records (
                    record_id, kind, source_id, stable_key, body, body_text,
                    namespace, valid_from, valid_to, tx_from, tx_to,
                    provenance, policy_id, parser_confidence, supersedes, wal_tx_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,%s,%s,%s,NULL,%s)
                ON CONFLICT (namespace, source_id, stable_key) WHERE tx_to IS NULL DO NOTHING
                RETURNING record_id
                """,
                (
                    record_id, "chunk", op.source_id, op.stable_key,
                    psycopg.types.json.Jsonb(body_json), body_text, namespace,
                    op.valid_from, tx_now,
                    psycopg.types.json.Jsonb(prov_json), op.policy_id, op.parser_confidence,
                    wal_tx_id,
                ),
            ).fetchone()

            if inserted is not None:
                return record_id  # clean first assert for this span

            # The pre-check saw no live row but the index says one exists now:
            # a concurrent writer to the SAME namespace+span won the race.
            # That shape violates the single-committer-per-namespace invariant
            # (the concurrency regression test drives it on purpose); resolve
            # exactly as before — idempotent no-op on identical content,
            # otherwise convert to a supersede of the winner. The WAL payload
            # for this rare path lacks old_id; the engine's next full rebuild,
            # not the incremental tail, is the recovery story out of an
            # out-of-invariant deployment.
            raced = cur.execute(
                "SELECT record_id FROM records "
                "WHERE namespace=%s AND source_id=%s AND stable_key=%s AND tx_to IS NULL",
                (namespace, op.source_id, op.stable_key),
            ).fetchone()
            assert raced is not None  # the conflict proves a live row is there
            if raced[0] == record_id:
                return record_id
            self._supersede_rows(
                cur, old_record_id=raced[0], op=op, record_id=record_id,
                body_json=body_json, body_text=body_text, namespace=namespace,
                prov_json=prov_json, tx_now=tx_now, wal_tx_id=wal_tx_id,
            )
            return record_id

    def _apply_supersede(self, op: WriteOp) -> RecordID:
        assert op.body is not None and op.provenance is not None and op.old_id is not None
        assert op.source_id is not None and op.stable_key is not None
        namespace = op.provenance.writer.namespace
        record_id = compute_record_id(op.body, kind="chunk")
        body_json, body_text = _serialize_body(op.body)
        prov_json = _serialize_provenance(op.provenance)
        tx_now = _now()

        with self._conn.transaction():
            cur = self._conn.cursor()
            wal_tx_id = self._wal.append_in_txn(
                cur,
                {
                    "op": "supersede",
                    "old_id": op.old_id,
                    "record_id": record_id,
                    "source_id": op.source_id,
                    "stable_key": op.stable_key,
                },
                namespace=namespace,
            )
            self._supersede_rows(
                cur, old_record_id=op.old_id, op=op, record_id=record_id,
                body_json=body_json, body_text=body_text, namespace=namespace,
                prov_json=prov_json, tx_now=tx_now, wal_tx_id=wal_tx_id,
            )
        return record_id

    def _supersede_rows(
        self,
        cur: psycopg.Cursor[Any],
        *,
        old_record_id: str,
        op: WriteOp,
        record_id: RecordID,
        body_json: dict[str, Any],
        body_text: str,
        namespace: str,
        prov_json: dict[str, Any],
        tx_now: datetime,
        wal_tx_id: int,
    ) -> None:
        """Close the old live row and insert the new one, in the caller's
        open transaction. Order matters: close first (freeing the partial
        unique index), then insert, so the new row does not collide with the
        row it replaces.
        """
        closed = cur.execute(
            "UPDATE records SET tx_to=%s WHERE record_id=%s "
            "AND namespace=%s AND source_id=%s AND stable_key=%s AND tx_to IS NULL "
            "RETURNING policy_id",
            (tx_now, old_record_id, namespace, op.source_id, op.stable_key),
        ).fetchone()
        if closed is None:
            # The old record was not live for this span IN THIS NAMESPACE.
            # Either a policy bug (superseding a non-live record) or a
            # cross-namespace supersede attempt (the namespace predicate above
            # is a tenancy boundary: a writer can only close rows in its own
            # partition — decisions.md #19). Fail loudly rather than insert a
            # second live row and silently violate the one-live invariant.
            raise DatumError(
                f"supersede target {old_record_id!r} is not a live record for span "
                f"({op.source_id!r}, {op.stable_key!r}) in namespace {namespace!r}; "
                f"refusing to create a second live version. Under the v1 "
                f"single-writer-per-namespace invariant this is a write-path bug or a "
                f"cross-namespace write attempt, not an expected race."
            )
        # A superseding version keeps the span's policy unless the op names a
        # new one. An explicit WriteOp.supersede carries no policy_id (a
        # content revision does not re-govern the span), so inherit the
        # closed row's; an assert-converted-to-supersede does carry one.
        policy_id = op.policy_id if op.policy_id is not None else closed[0]
        cur.execute(
            f"""
            INSERT INTO records (
                record_id, kind, source_id, stable_key, body, body_text,
                namespace, valid_from, valid_to, tx_from, tx_to,
                provenance, policy_id, parser_confidence, supersedes, wal_tx_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,%s,%s,%s,%s,%s)
            """,
            (
                record_id, "chunk", op.source_id, op.stable_key,
                psycopg.types.json.Jsonb(body_json), body_text, namespace,
                op.valid_from, tx_now,
                psycopg.types.json.Jsonb(prov_json), policy_id, op.parser_confidence,
                old_record_id, wal_tx_id,
            ),
        )

    def _apply_forget(self, op: WriteOp, acting_namespace: str | None) -> ErasureReceipt:
        assert op.target_id is not None
        tx_now = _now()
        with self._conn.transaction():
            cur = self._conn.cursor()
            # Tombstone: close every live row carrying this record_id WITHIN
            # ONE namespace. v1 is tombstone-only (WriteOp.forget already
            # refuses crypto_shred); the row stays for history, it is simply
            # no longer live. Namespace scoping matters because identical
            # content in two tenants legitimately shares a record_id
            # (content-addressing does not salt by tenant): an unscoped
            # forget would tombstone the OTHER tenant's record too
            # (decisions.md #19).
            rows = cur.execute(
                "SELECT DISTINCT namespace FROM records WHERE record_id=%s AND tx_to IS NULL",
                (op.target_id,),
            ).fetchall()
            if not rows:
                raise DatumError(
                    f"forget target {op.target_id!r} is not a live record; nothing to tombstone."
                )
            live_namespaces = {row[0] for row in rows}
            if acting_namespace is not None:
                if acting_namespace not in live_namespaces:
                    # Fail closed: not distinguishable (to the caller) from a
                    # record that does not exist — a forget can neither probe
                    # nor mutate another partition.
                    raise DatumError(
                        f"forget target {op.target_id!r} is not a live record; "
                        "nothing to tombstone."
                    )
                namespace = acting_namespace
            elif len(live_namespaces) == 1:
                namespace = next(iter(live_namespaces))
            else:
                raise DatumError(
                    f"forget target {op.target_id!r} is live in {len(live_namespaces)} "
                    "namespaces; refusing an ambiguous cross-tenant tombstone. Pass the "
                    "acting namespace (GroundStore.apply(op, namespace=...))."
                )
            self._wal.append_in_txn(
                cur, {"op": "forget", "record_id": op.target_id, "mode": "tombstone"},
                namespace=namespace,
            )
            cur.execute(
                "UPDATE records SET tx_to=%s WHERE record_id=%s AND namespace=%s AND tx_to IS NULL",
                (tx_now, op.target_id, namespace),
            )
        return ErasureReceipt(
            record_id=op.target_id,
            mode="tombstone",
            propagated_to=frozenset(),  # L4 removal happens at the next engine refresh
            completed_at=tx_now,
            key_shredded_at=None,
        )

    # --- read path (autocommit: no lingering transaction held between calls) ---

    def find_span(self, source_id: str, stable_key: str, *, namespace: str) -> Record | None:
        """The live record for a span in one namespace partition, or None.
        Backs a WritePolicy's assert-vs-supersede decision (FRAMEWORK.md's
        DocumentPolicy sketch). `namespace` is required: span identity is
        namespace-scoped (decisions.md #19) — an unscoped lookup would let one
        tenant's write path see, and then supersede against, another tenant's
        record whenever their caller-chosen source ids collide.
        """
        row = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM records "
            "WHERE namespace=%s AND source_id=%s AND stable_key=%s AND tx_to IS NULL",
            (namespace, source_id, stable_key),
        ).fetchone()
        return _row_to_record(row) if row is not None else None

    def get_live(self, record_id: str, *, namespace: str | None = None) -> Record | None:
        """The live record carrying `record_id`, or None. Pass `namespace`
        whenever the caller acts for a principal: identical content in two
        tenants shares a record_id, and an unscoped lookup returns an
        arbitrary one of them — the read-side counterpart of the span-scoping
        rule (decisions.md #19).
        """
        if namespace is None:
            row = self._conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM records "
                "WHERE record_id=%s AND tx_to IS NULL LIMIT 1",
                (record_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM records "
                "WHERE record_id=%s AND namespace=%s AND tx_to IS NULL LIMIT 1",
                (record_id, namespace),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def live_in_namespace(
        self, namespace: str, *, batch_size: int = 500
    ) -> Iterator[Record]:
        """Every live record in a namespace partition, in insertion order.
        The grep operator (L5) reads canonical content through this. The
        namespace filter is the v1 ACL partition (exact-equality, decisions.md
        #13) — an index probe on `records_live_namespace_idx`.
        """
        last_row_id = 0
        while True:
            rows = self._conn.execute(
                f"SELECT row_id, {_SELECT_COLUMNS} FROM records "
                "WHERE namespace=%s AND tx_to IS NULL AND row_id > %s "
                "ORDER BY row_id ASC LIMIT %s",
                (namespace, last_row_id, batch_size),
            ).fetchall()
            if not rows:
                return
            for row in rows:
                last_row_id = row[0]
                yield _row_to_record(row[1:])
            if len(rows) < batch_size:
                return


def require_writer_namespace(op: WriteOp, principal: Principal) -> None:
    """Guard that an op's provenance writer matches the acting principal's
    namespace — the write-side complement of read-side ACL. A write whose
    provenance claims a different namespace than the principal performing it
    is refused (a principal cannot write records into another partition).
    """
    if op.provenance is None:
        return
    if op.provenance.writer.namespace != principal.namespace:
        raise AdmissionError(
            f"principal {principal.id!r} (namespace {principal.namespace!r}) may not "
            f"write a record into namespace {op.provenance.writer.namespace!r}."
        )
