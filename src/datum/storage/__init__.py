"""datum.storage: L0 object storage and L1 write-ahead log.

Two independent, layered concerns live here, both load-bearing for the
L0/L2 seam invariant FRAMEWORK.md names explicitly (§The architecture,
"The L0/L2 seam, named and closed, not assumed"):

- `blobstore`: L0, durable byte-level storage of raw source material.
  Content-addressed (sha256 of the bytes is the key), so a retried or
  duplicated write is idempotent by construction — writing the same bytes
  twice is a no-op, never a duplicate object or an error.
- `wal`: L1, the single writer path into L2 (Ground Store). Every insert,
  patch, delete, and ACL change is a content-hashed, append-only
  transaction, ordered by the database's own monotonic identity column,
  not by application logic.
- `migrations`: the hand-rolled, numbered SQL migration runner that stands
  up `wal`'s schema. No ORM — FRAMEWORK.md's adoption path (§Adoption
  path) is explicit that Datum's own storage layer stays boring and
  inspectable.

The invariant that ties the two together, enforced by construction rather
than by convention: a blob must be durable in L0 *before* any WAL entry in
L1 references its content hash, never the reverse. Nothing in this package
enforces that ordering across the two calls for its caller — this package
only guarantees that each half, taken on its own, is durable and idempotent
individually (LocalFilesystemBlobStore.put() does not return until its
fsync sequence completes; WAL.append() does not return until Postgres has
committed). Calling blob-then-append, not append-then-blob, is a
requirement this package places on whichever layer sequences the two
(writepath/L3, once it exists) — a caller that honors that ordering never
observes a half-written blob or an ambiguous append; this package cannot
itself detect or prevent a caller that gets the order wrong, since put()
and append() are independent calls with no shared transaction between
them.

Neither module is part of the budgeted kernel surface (datum/__init__.py's
`__all__`) — they are internal plumbing the writepath and groundstore
layers call, not agent-facing types. `WAL` and `LocalFilesystemBlobStore`
are storage-layer implementation classes, not kernel Protocols; nothing
here is re-exported from datum.kernel or datum's top level.
"""
