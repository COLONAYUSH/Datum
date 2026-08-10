"""BlobStore: L0 object storage — durable byte-level storage of raw source
material (PDFs, exports, transcripts).

FRAMEWORK.md (§The architecture, "L0 — Object storage") pins the
responsibility and deliberately leaves the interface generic: "none
Datum-specific — any S3-compatible or filesystem blob store." `BlobStore`
below is that generic seam; `LocalFilesystemBlobStore` is the concrete v1
implementation, sufficient for the MVP's single-node deployment story
(§MVP definition) without foreclosing an S3-backed implementation later —
anything satisfying this Protocol slots in unchanged above this module.

Content-addressing (sha256 of the bytes, never an arbitrary counter or
caller-supplied name) is what makes the L0/L2 seam invariant hold without
distributed-transaction machinery (§The architecture, "The L0/L2 seam,
named and closed, not assumed"): the same bytes always produce the same
key, so a retried or duplicated write is a no-op by construction, and a
crash between an L0 write and the L1 append that references it leaves at
worst an orphaned, harmless, garbage-collectable object — never a WAL entry
pointing at content that was never durably written.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

from datum.kernel.errors import DatumError

# Bare lowercase hex sha256 digest, 64 characters. Chosen over a
# "sha256:"-prefixed form (as e.g. OCI/Docker uses) to keep the key a
# valid, unambiguous filesystem path component and Postgres text value with
# no algorithm-tagging logic anywhere downstream — v1 has exactly one
# hashing algorithm, so there is nothing yet worth a prefix's flexibility.
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class InvalidContentHashError(DatumError):
    """Raised when a caller passes something that is not a well-formed
    sha256 hex digest to get()/exists(). Content hashes become filesystem
    path components in LocalFilesystemBlobStore; rejecting anything that
    doesn't match the expected shape before it touches the filesystem is
    what keeps a malformed or hostile hash (e.g. "../../../etc/passwd")
    from ever becoming a path-traversal primitive.
    """


def content_hash(data: bytes) -> str:
    """The one hashing function every BlobStore implementation must agree
    on, factored out so a caller can compute a key without writing first
    (e.g. to check `exists()` before spending bytes on a network call to a
    remote implementation).
    """
    return hashlib.sha256(data).hexdigest()


class BlobStore(Protocol):
    """The L0 interface every implementation (local filesystem now, S3 or
    equivalent later) satisfies. Three operations only — no delete, no
    list, no update. L0 objects are content-addressed and immutable by
    construction; there is nothing to update, and garbage collection of
    unreferenced objects is a LineageManifest-driven maintenance task
    (Phase 1), not part of this seam's request path.
    """

    def put(self, data: bytes) -> str:
        """Write `data` durably and return its content hash. Idempotent:
        writing the same bytes twice is a no-op, never an error and never
        a second object.
        """
        ...

    def get(self, hash: str) -> bytes:
        """Return the bytes previously stored under `hash`. Raises
        FileNotFoundError if no such object exists.
        """
        ...

    def exists(self, hash: str) -> bool:
        """Whether `hash` is already durable in this store — the check a
        caller makes before deciding it needs to `put()` at all.
        """
        ...


class LocalFilesystemBlobStore:
    """Content-addressed blob store rooted at a local directory.

    Objects are sharded by the first two hex characters of their hash
    (`<root>/<aa>/<hash>`) so a large corpus never produces one flat
    directory with millions of entries — the same fan-out scheme content-
    addressed stores (git's `.git/objects`, npm's local cache) use, and for
    the same reason: most filesystems degrade on directory listing and
    lookup well before a single directory reaches six-figure entry counts.

    Durability sequencing inside `put()` is the load-bearing part of this
    class, not an implementation detail: bytes are written to a temp file
    in the *same* shard directory (so the final `os.replace` is same-
    filesystem and atomic), fsynced, then atomically renamed onto the final
    path, and the shard directory's own fd is fsynced after the rename.
    Without that sequence, a crash between "file created" and "file fully
    written" could leave a truncated object at the final path — exactly
    the failure FRAMEWORK.md's L0/L2 seam invariant requires L0 to have
    already ruled out before any WAL entry references the hash. If the
    final path already exists, `put()` returns early without writing
    anything: never re-write over a good, already-durable object.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _shard_dir(self, hash: str) -> Path:
        return self._root / hash[:2]

    def _path(self, hash: str) -> Path:
        return self._shard_dir(hash) / hash

    @staticmethod
    def _validate(hash: str) -> None:
        if not _HASH_RE.match(hash):
            raise InvalidContentHashError(
                f"{hash!r} is not a well-formed sha256 hex digest "
                "(expected 64 lowercase hex characters)"
            )

    def put(self, data: bytes) -> str:
        hash = content_hash(data)
        shard = self._shard_dir(hash)
        shard.mkdir(parents=True, exist_ok=True)
        final_path = self._path(hash)

        if final_path.exists():
            # Idempotent no-op: same bytes, same hash, same object already
            # durable. Writing it again would be redundant I/O at best and
            # a race against a concurrent writer at worst.
            return hash

        fd, tmp_name = tempfile.mkstemp(dir=shard, prefix=f".{hash}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, final_path)
        except BaseException:
            # Best-effort cleanup of the temp file on any failure path
            # (including KeyboardInterrupt) — an orphaned .tmp file is
            # harmless and never referenced by anything, but there is no
            # reason to leave it lying around when we can clean up now.
            Path(tmp_name).unlink(missing_ok=True)
            raise

        # fsync the shard directory too: on POSIX, fsyncing the file alone
        # durably persists its *contents* but the directory entry created
        # by os.replace's rename is metadata that lives in the directory's
        # own inode. Skipping this step can, on a crash, leave the rename
        # itself unpersisted even though the file's bytes are safely on
        # disk — the object would simply not exist yet, which is the same
        # "orphaned write, never a dangling reference" failure mode the
        # seam invariant already tolerates, but closing it costs one
        # syscall and removes the ambiguity.
        dir_fd = os.open(shard, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        return hash

    def get(self, hash: str) -> bytes:
        self._validate(hash)
        return self._path(hash).read_bytes()

    def exists(self, hash: str) -> bool:
        self._validate(hash)
        return self._path(hash).is_file()
