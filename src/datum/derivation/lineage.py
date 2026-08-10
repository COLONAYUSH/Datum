"""L2 -> L4 lineage edges: which stored record row was projected into which
view, by which producer version (FRAMEWORK.md's lineage requirement; the
CI-07 rebuild/audit tuple — source doc version x parser version x producer
version, answerable after the fact).

Append-only by design, mirroring how record history survives supersession: a
re-derivation appends a new edge rather than updating the old one, so "this
row was derived by dense-v1/modelA, then re-derived by dense-v1/modelB after
the embedder swap" stays reconstructable. The engine writes edges in the SAME
transaction as the view rows they describe (the caller's cursor, no commit
here — the append_in_txn discipline, decisions.md #11), so an edge never
exists for a view row that failed to commit, and vice versa.
"""

from __future__ import annotations

from typing import Any, Sequence

import psycopg

from datum.derivation.views.base import RecordRow, ViewBuilder

_INSERT_SQL = (
    "INSERT INTO lineage_edges (record_row_id, record_id, view_name, producer_version) "
    "VALUES (%s, %s, %s, %s)"
)


def write_lineage_edges(
    cur: psycopg.Cursor[Any], view: ViewBuilder, rows: Sequence[RecordRow]
) -> int:
    """Append one edge per just-derived row, on the caller's cursor, inside
    the caller's transaction. Returns edges written.
    """
    if not rows:
        return 0
    cur.executemany(
        _INSERT_SQL,
        [(row.row_id, str(row.record.id), view.name, view.producer_version) for row in rows],
    )
    return len(rows)
