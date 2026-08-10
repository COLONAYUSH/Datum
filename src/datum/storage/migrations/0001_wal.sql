-- L1 WAL schema: the single append-only writer path into L2.
--
-- `id` is GENERATED ALWAYS AS IDENTITY (not a plain BIGSERIAL) so ordering
-- is a database-enforced monotonic identity column, not application
-- logic -- FRAMEWORK.md's L1 responsibility statement names this exactly
-- ("the single writer path; every insert, patch, delete, and ACL change is
-- a content-hashed, append-only transaction"). GENERATED ALWAYS additionally
-- refuses an application-supplied id outright (INSERT ... OVERRIDING SYSTEM
-- VALUE required to bypass it), closing off the one way a caller could
-- otherwise undermine the ordering guarantee by inserting an explicit id.
--
-- `namespace` is the coarse ACL partition FRAMEWORK.md's MVP scoping
-- describes for since() filtering (§MVP definition: "namespace-partition-
-- only" ACL at v1) -- a cheap equality check on a partition key, not a
-- predicate evaluation. The composite index below is what makes that
-- filtered tail scan an index range scan rather than a sequential scan
-- with a filter.
CREATE TABLE IF NOT EXISTS wal_entries (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    namespace   TEXT NOT NULL,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The primary key already gives tail_since(marker=None) an efficient
-- "id > X ORDER BY id" scan on the whole table. This composite index is
-- for the namespace-filtered case: WHERE namespace = ? AND id > ? ORDER BY
-- id, which the PK alone cannot serve efficiently once a deployment has
-- more than one namespace's worth of traffic interleaved in the table.
CREATE INDEX IF NOT EXISTS wal_entries_namespace_id_idx
    ON wal_entries (namespace, id);
