"""ViewBuilder: the L4 view-maintenance contract the DerivationEngine drives.

A view is a derived, disposable index over canonical L2 records — it can
always be rebuilt from the ground store, and nothing in it is ever the source
of truth (FRAMEWORK.md §The architecture, "L4 — Derivation"). This module
pins the seam between the engine (which decides WHAT changed, by tailing the
WAL) and each view (which decides HOW a record is projected into its own
table): the engine hands a view live record rows to derive and closed row_ids
to remove, inside a transaction the ENGINE owns, so a view's rows and the
engine's WAL cursor always advance together or not at all.

Transaction ownership is the load-bearing rule here: `derive`/`remove` take a
caller-supplied cursor and must neither commit nor roll back (the same
discipline as WAL.append_in_txn, decisions.md #11). `ensure_schema` is the
one exception — it takes the connection and may run its own DDL transactions,
because schema setup happens once at wiring time, not inside the refresh
loop. Views own their schema (CREATE TABLE in ensure_schema, not in a
numbered migration) because the dense view's column type depends on the
configured embedder's dimension — DDL that cannot be a static .sql file —
and one asymmetric exception would be worse than one consistent rule.

View tables key rows by `records.row_id` (the surrogate PK), NOT by
`record_id`: the same content hash can legitimately recur across historical
versions and spans (migrations/0002 explains why record_id is not unique),
while row_id names exactly one physical row. A view row must answer "which
exact stored row was this derived from," and only row_id does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import psycopg

from datum.kernel.record import Record


@dataclass(frozen=True)
class RecordRow:
    """One live ground-store row as a view sees it: the surrogate `row_id`
    (the view row's key, see module docstring) plus the full kernel Record.
    """

    row_id: int
    record: Record


class ViewBuilder(Protocol):
    """What the DerivationEngine requires of every view. `name` keys the
    view's WAL cursor (view_cursors, migrations/0004) and its lineage edges;
    `producer_version` is stamped on every derived row and lineage edge so a
    reindex after a producer change is detectable (the CI-07 lineage tuple).
    """

    name: str
    producer_version: str

    def ensure_schema(self, conn: psycopg.Connection[Any]) -> None:
        """Create this view's table(s)/index(es) if absent; raise (never
        silently adapt) if an existing table is incompatible with the
        configured producer — e.g. a dense table whose vector dimension
        does not match the configured embedder.
        """
        ...

    def derive(self, cur: psycopg.Cursor[Any], rows: Sequence[RecordRow]) -> int:
        """Project `rows` (live records) into this view's table on the
        caller's cursor, inside the caller's transaction. Rows previously
        derived for the same row_id may be assumed already removed by the
        engine's delete-then-rederive discipline. Returns rows written.
        """
        ...

    def remove(self, cur: psycopg.Cursor[Any], row_ids: Sequence[int]) -> int:
        """Delete this view's rows for `row_ids` on the caller's cursor,
        inside the caller's transaction. Missing rows are not an error
        (idempotent, so a crashed batch can re-run). Returns rows deleted.
        """
        ...
