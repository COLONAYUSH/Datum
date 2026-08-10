-- L2 Ground Store schema: the canonical, bitemporal, content-addressed record
-- store. Every retrievable fact lives here as one or more versioned rows;
-- nothing is edited in place (FRAMEWORK.md §The architecture, "L2 — Ground
-- Store": "the only layer that is mutable, and only by supersession, never by
-- overwrite").
--
-- Bitemporality (two independent time axes, FRAMEWORK.md's "bitemporal
-- COLUMNS on Record"):
--   valid_from / valid_to  -- when the fact is true in the world
--   tx_from   / tx_to      -- when the SYSTEM knew it (transaction time)
-- A NULL tx_to means the row is LIVE (currently believed); a non-NULL tx_to
-- means it was superseded/forgotten at that transaction instant but is kept
-- for history. v1 ships these as columns without the as-of QUERY surface
-- (deferred to Phase 1 per §MVP definition) -- the columns exist now so
-- adding as-of reads later is not a one-way-door schema migration.

CREATE TABLE IF NOT EXISTS records (
    -- Internal surrogate PK. `record_id` (the content hash) is NOT the PK
    -- because the same (body, structure) can legitimately recur as distinct
    -- historical versions of a span, and identical content can appear under
    -- different spans; a surrogate keeps those distinct without overloading
    -- the content hash with uniqueness it does not have.
    row_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Content hash of (body, structure, kind) -- the kernel RecordID. Used
    -- for idempotent re-ingest: the same span with the same content produces
    -- the same record_id, so a re-assert is a detectable no-op.
    record_id         TEXT NOT NULL,
    kind              TEXT NOT NULL,

    -- The uniqueness-CAS key (decisions.md #17): source_id names the source
    -- document, stable_key the span within it. The partial unique index below
    -- enforces "at most one live row per (source_id, stable_key)."
    source_id         TEXT NOT NULL,
    stable_key        TEXT NOT NULL,

    -- body holds the full kernel Record.body (a plain string OR a
    -- StructuredBody, JSON-encoded with a discriminator so it round-trips to
    -- exactly the type it was). body_text is the flattened text, duplicated
    -- out as a real column so grep/BM25 and quick reads never have to parse
    -- JSON to get at the text.
    body              JSONB NOT NULL,
    body_text         TEXT NOT NULL,

    -- = provenance.writer.namespace (decisions.md #7): the coarse ACL
    -- partition, materialized as a real indexed column so namespace-partition
    -- ACL selection is an equality index probe, not a JSONB traversal.
    namespace         TEXT NOT NULL,

    valid_from        TIMESTAMPTZ NOT NULL,
    valid_to          TIMESTAMPTZ,
    tx_from           TIMESTAMPTZ NOT NULL,
    tx_to             TIMESTAMPTZ,

    provenance        JSONB NOT NULL,
    policy_id         TEXT NOT NULL,
    parser_confidence DOUBLE PRECISION,
    supersedes        TEXT,   -- record_id of the version this one replaced (NULL for a first assert)

    -- The WAL transaction id this record row committed together with
    -- (storage/wal.py append_in_txn, decisions.md #11): the audit link tying
    -- a record mutation to its single, atomic commit point.
    wal_tx_id         BIGINT NOT NULL
);

-- THE invariant. A partial unique index over live rows only: at most one row
-- with tx_to IS NULL per (source_id, stable_key). This is the compare-and-swap
-- the ground store relies on — a second concurrent assert for the same live
-- span violates THIS index at the database level (not in application code
-- that could race), and the store converts the loser into a supersede. It is
-- also the exact structural fix for the Mem0 #4892 class (paper Figure 5):
-- two writers cannot both create a live record for the same span.
CREATE UNIQUE INDEX IF NOT EXISTS records_one_live_per_span
    ON records (source_id, stable_key)
    WHERE tx_to IS NULL;

-- Namespace-partition ACL selection over live rows (the coarse equality
-- filter §MVP definition names; matches security/acl.py's exact-equality
-- grant, decisions.md #13).
CREATE INDEX IF NOT EXISTS records_live_namespace_idx
    ON records (namespace)
    WHERE tx_to IS NULL;

-- record_id lookups (idempotency check, supersede-by-id, fetch-by-id).
CREATE INDEX IF NOT EXISTS records_record_id_idx
    ON records (record_id);

-- All versions of a given source, history included (append/refresh paths).
CREATE INDEX IF NOT EXISTS records_source_idx
    ON records (source_id);
