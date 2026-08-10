"""DerivationEngine (L4): incrementally maintains every registered view from
the WAL tail — the "only the touched chunk re-derives" property, realized.

The engine is the ONLY caller of a ViewBuilder's derive()/remove(). It tails
each namespace's WAL from a persisted per-(view, namespace) cursor
(view_cursors, migrations/0004), collects the record_ids each entry touched,
and applies a delete-then-rederive per touched record_id: remove every view
row for ANY version of that record_id, then derive every currently-live row.
That discipline is what makes a batch idempotent — a crash after commit
re-processes nothing, a crash before commit re-processes the whole batch to
the same end state — which in turn is what makes advancing the cursor IN THE
SAME TRANSACTION as the view writes safe (they commit together or not at
all, the same seam discipline as decisions.md #11).

Granularity note: an ingest that leaves a span unchanged writes no WAL entry
for it (DocumentPolicy no-ops unchanged spans), so an edited document
re-derives exactly its changed chunks — the WAL's own granularity is the
incremental property, the engine just follows it.

Cursors are per-view as well as per-namespace so a view added later (the
exact Milestone B shape: dense/lexical arriving after Milestone A data
already exists) backfills independently from the beginning of the WAL
without disturbing any other view's position. The resumable tail is
namespace-scoped per decisions.md #14; refresh(namespace) is called by the
write side after it commits (Corpus.ingest), which preserves v1's
single-committer-per-namespace invariant — the engine never runs as an
unsupervised background writer at v1.

Everything is namespace-scoped, including the record_id -> row lookups:
identical content ingested by two tenants legitimately hashes to the SAME
record_id in both namespaces (content-addressing does not salt by tenant),
so an unscoped lookup would let one tenant's refresh touch another tenant's
view rows. The WHERE namespace=%s on both queries below is a tenancy
boundary, not an optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import psycopg

from datum.derivation.lineage import write_lineage_edges
from datum.derivation.views.base import RecordRow, ViewBuilder
from datum.groundstore.store import record_from_row, record_select_columns
from datum.storage.wal import WAL

_BATCH_ENTRIES = 200


@dataclass(frozen=True)
class RefreshReport:
    """What one refresh(namespace) did, per view: WAL entries consumed, view
    rows written/deleted. A second refresh with no intervening writes reports
    zeros everywhere — the cheap way for a caller (or test) to see that
    incremental means incremental.
    """

    namespace: str
    entries: dict[str, int]
    derived: dict[str, int]
    removed: dict[str, int]


class DerivationEngine:
    """Owns one autocommit connection; every batch wraps itself in an explicit
    transaction (the GroundStore's own pattern). Not thread-safe, like every
    connection-holding object in this codebase.
    """

    def __init__(self, dsn: str, views: Sequence[ViewBuilder]) -> None:
        names = [view.name for view in views]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate view names in {names!r}; cursor state is keyed by name.")
        self._views = tuple(views)
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._wal = WAL(dsn)

    def close(self) -> None:
        self._wal.close()
        self._conn.close()

    def __enter__(self) -> "DerivationEngine":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def views(self) -> tuple[ViewBuilder, ...]:
        return self._views

    def ensure_schemas(self) -> None:
        """Create every view's schema. Called once at wiring time (Corpus.open),
        before any operator can query a view table.
        """
        for view in self._views:
            view.ensure_schema(self._conn)

    def refresh(self, namespace: str) -> RefreshReport:
        """Bring every view current with `namespace`'s WAL, incrementally."""
        entries = {view.name: 0 for view in self._views}
        derived = {view.name: 0 for view in self._views}
        removed = {view.name: 0 for view in self._views}
        for view in self._views:
            marker = self._cursor(view.name, namespace)
            batch: list[dict[str, Any]] = []
            for entry in self._wal.tail_since(marker, namespace=namespace):
                batch.append(entry)
                if len(batch) >= _BATCH_ENTRIES:
                    d, r = self._apply_batch(view, namespace, batch)
                    entries[view.name] += len(batch)
                    derived[view.name] += d
                    removed[view.name] += r
                    batch = []
            if batch:
                d, r = self._apply_batch(view, namespace, batch)
                entries[view.name] += len(batch)
                derived[view.name] += d
                removed[view.name] += r
        return RefreshReport(namespace=namespace, entries=entries, derived=derived, removed=removed)

    # --- internals ---

    def _cursor(self, view_name: str, namespace: str) -> int | None:
        row = self._conn.execute(
            "SELECT wal_position FROM view_cursors WHERE view_name=%s AND namespace=%s",
            (view_name, namespace),
        ).fetchone()
        return row[0] if row is not None else None

    def _apply_batch(
        self, view: ViewBuilder, namespace: str, batch: list[dict[str, Any]]
    ) -> tuple[int, int]:
        touched: set[str] = set()
        for entry in batch:
            payload = entry["payload"]
            for key in ("record_id", "old_id"):
                value = payload.get(key)
                if value:
                    touched.add(value)
        last_position = batch[-1]["tx_id"]

        with self._conn.transaction():
            cur = self._conn.cursor()
            ids = sorted(touched)
            all_row_ids: list[int] = []
            live_rows: list[RecordRow] = []
            if ids:
                all_row_ids = [
                    r[0]
                    for r in cur.execute(
                        "SELECT row_id FROM records WHERE namespace=%s AND record_id = ANY(%s)",
                        (namespace, ids),
                    ).fetchall()
                ]
                rows = cur.execute(
                    f"SELECT row_id, {record_select_columns('records')} FROM records "
                    "WHERE namespace=%s AND record_id = ANY(%s) AND tx_to IS NULL "
                    "ORDER BY row_id",
                    (namespace, ids),
                ).fetchall()
                live_rows = [RecordRow(row_id=r[0], record=record_from_row(r[1:])) for r in rows]

            n_removed = view.remove(cur, all_row_ids) if all_row_ids else 0
            n_derived = view.derive(cur, live_rows) if live_rows else 0
            if live_rows:
                write_lineage_edges(cur, view, live_rows)
            cur.execute(
                "INSERT INTO view_cursors (view_name, namespace, wal_position) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (view_name, namespace) DO UPDATE "
                "SET wal_position = EXCLUDED.wal_position, updated_at = now()",
                (view.name, namespace, last_position),
            )
        return n_derived, n_removed
