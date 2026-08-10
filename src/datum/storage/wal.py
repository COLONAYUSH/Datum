"""WAL: L1, the single writer path into L2 (Ground Store).

FRAMEWORK.md (§The architecture, "L1 — WAL") pins the responsibility: "the
single writer path; every insert, patch, delete, and ACL change is a
content-hashed, append-only transaction... nothing above L2 writes except by
appending here." This module is the concrete Postgres-backed implementation.

Ordering is a database property, not an application one: `id` is `GENERATED
ALWAYS AS IDENTITY` (see migrations/0001_wal.sql), so the order transactions
become visible in is the order Postgres assigns and enforces via the primary
key index — no application-level sequencing sits between `append()` and the
guarantee `tail_since()` relies on.

--- The changefeed-gap hazard, and how this module's API forecloses it ---

`GENERATED ALWAYS AS IDENTITY` allocates an id at INSERT time, before that
transaction commits. Two concurrent writers can therefore commit out of
allocation order: a transaction allocated id 6 can become visible *after* a
transaction allocated id 7 already did. A resumable `WHERE id > last_seen`
reader that observes 7 and advances its marker to 7 permanently skips 6 once
it finally commits — the classic changefeed gap. An adversarial review
reproduced this: two namespaces, one writer each, a reader resuming a GLOBAL
(all-namespace) tail by marker, lost 10 of 8000 committed entries.

This module forecloses the gap by API shape rather than merely warning about
it, splitting the two genuinely different read use cases so the unsafe one
cannot be spelled:

- `tail_since(marker, *, namespace=...)` — the RESUMABLE changefeed (the
  backing for the `since()` MCP verb). `namespace` is REQUIRED. Its
  resume-safety depends on there being a single committer per namespace,
  which is exactly the invariant FRAMEWORK.md's v1 write path maintains (L3
  funnels all writes for a namespace through one Write Orchestrator
  invocation, §The architecture). Under that invariant a per-namespace tail
  has one committer and no allocation/commit inversion, so marker-resume is
  loss-free. Violating the invariant (two concurrent writers to ONE
  namespace) reintroduces the gap; closing that fully-concurrent case needs a
  commit-visibility watermark that is Phase 1 work, named here, not bolted on
  silently under this signature.
- `scan(*, namespace=None)` — a ONE-SHOT full read from the beginning, no
  marker, optionally across all namespaces. Because it never persists a
  resume marker, it has no resume gap by construction: it reads what is
  committed at scan time; a concurrent writer's in-flight entry is simply
  included or not, and a *later* scan starts from the beginning again. This
  is the admin/rebuild reader (e.g. CI-07's rebuild-from-scratch), not a
  changefeed.

There is deliberately no resumable global tail: that is the one combination
the review showed is unsafe, and it is now unspellable.

--- The L1<->L2 transaction seam (decisions.md #11) ---

FRAMEWORK.md requires a supersede to close the old record's tx_to and open
the new record's tx_from "in the same WAL append," with the WAL append as
"the single, sole commit point." A ground store that mutated its records
table on one connection and appended here on this module's own autocommit
connection would be two transactions — no atomicity, reintroducing the
write-race the design exists to close. `append_in_txn(cur, ...)` appends on a
caller-supplied cursor inside the caller's transaction (and does NOT commit),
so the ground store can append the WAL entry and mutate the record rows
together, committing once. The autocommit `append()` remains for standalone
entries not coupled to a record write.

This object holds one connection and is not thread-safe (standard for a
psycopg-connection-holding object); concurrent use wants separate `WAL`
instances or a pool drawn from `psycopg[binary,pool]` (already a dependency),
behind this same interface.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

DEFAULT_DSN = "postgresql://localhost/datum"

_INSERT_SQL = "INSERT INTO wal_entries (namespace, payload) VALUES (%s, %s) RETURNING id"


class WAL:
    """A Postgres-backed append-only log over the `wal_entries` table
    (see migrations/0001_wal.sql).
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("DATUM_PG_DSN", DEFAULT_DSN)
        self._conn = psycopg.connect(self._dsn, autocommit=True)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "WAL":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- write path ---

    def append(self, entry: dict[str, Any], *, namespace: str) -> int:
        """Append `entry` as a JSONB payload under `namespace`, on this WAL's
        own autocommit connection, and return its assigned transaction id.

        Use this for a WAL entry NOT coupled to a same-transaction record
        mutation (e.g. a future standalone ACL-change log entry). For the
        coupled case — a supersede that must be atomic with its record-table
        writes — use `append_in_txn` on the ground store's own cursor.

        `namespace` is a required keyword: every caller states which ACL
        partition (FRAMEWORK.md §MVP definition's namespace-partition ACL)
        the entry belongs to, rather than this module guessing a key inside
        an opaque payload dict.
        """
        row = self._conn.execute(_INSERT_SQL, (namespace, Jsonb(entry))).fetchone()
        if row is None:  # unreachable: INSERT ... RETURNING yields one row per inserted row
            raise RuntimeError("INSERT ... RETURNING id returned no row")
        return row[0]

    def append_in_txn(
        self, cur: psycopg.Cursor[Any], entry: dict[str, Any], *, namespace: str
    ) -> int:
        """Append `entry` on a caller-supplied cursor, inside the caller's
        transaction, and return its assigned id WITHOUT committing.

        This is the L1<->L2 transaction seam (module docstring / decisions.md
        #11): the ground store passes a cursor from its own open transaction
        so the WAL append and the record-table mutation commit together or
        not at all. The caller owns the transaction lifecycle; this method
        neither begins nor commits nor rolls back.
        """
        row = cur.execute(_INSERT_SQL, (namespace, Jsonb(entry))).fetchone()
        if row is None:
            raise RuntimeError("INSERT ... RETURNING id returned no row")
        return row[0]

    # --- read path ---

    def tail_since(
        self,
        marker: int | None,
        *,
        namespace: str,
        batch_size: int = 500,
    ) -> Iterator[dict[str, Any]]:
        """Yield one dict per entry in `namespace` with `tx_id > marker`, in
        tx_id order: `{"tx_id", "namespace", "payload", "created_at"}`.
        `marker=None` starts from the beginning of that namespace's log; each
        yielded `tx_id` doubles as the next call's `marker`.

        `namespace` is REQUIRED (module docstring): a resumable tail is only
        loss-free per-namespace under v1's single-committer-per-namespace
        invariant, so this API does not offer a resumable all-namespace tail.
        For a one-shot global read use `scan()`.

        Keyset pagination (`WHERE ... id > ? ORDER BY id LIMIT ?`, advancing
        the marker per batch) rather than a server-side cursor, so the
        generator holds no transaction/snapshot open across whatever the
        caller does between iterations; each batch is an index range scan on
        the primary key.
        """
        yield from self._read(marker, namespace=namespace, batch_size=batch_size)

    def scan(
        self, *, namespace: str | None = None, batch_size: int = 500
    ) -> Iterator[dict[str, Any]]:
        """One-shot read from the beginning of the log, optionally across all
        namespaces (`namespace=None`). No marker, not resumable — the
        admin/rebuild reader (module docstring). Same yielded dict shape as
        `tail_since`.
        """
        yield from self._read(None, namespace=namespace, batch_size=batch_size)

    def _read(
        self, marker: int | None, *, namespace: str | None, batch_size: int
    ) -> Iterator[dict[str, Any]]:
        current = marker if marker is not None else 0
        while True:
            if namespace is None:
                rows = self._conn.execute(
                    "SELECT id, namespace, payload, created_at FROM wal_entries "
                    "WHERE id > %s ORDER BY id ASC LIMIT %s",
                    (current, batch_size),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, namespace, payload, created_at FROM wal_entries "
                    "WHERE namespace = %s AND id > %s ORDER BY id ASC LIMIT %s",
                    (namespace, current, batch_size),
                ).fetchall()

            if not rows:
                return

            for row_id, row_namespace, payload, created_at in rows:
                current = row_id
                yield {
                    "tx_id": row_id,
                    "namespace": row_namespace,
                    "payload": payload,
                    "created_at": created_at,
                }

            if len(rows) < batch_size:
                return
