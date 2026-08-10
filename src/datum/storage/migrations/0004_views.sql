-- L4 derivation substrate: the view-agnostic bookkeeping tables the
-- DerivationEngine needs. The view tables THEMSELVES (view_lexical,
-- view_dense) are deliberately NOT created here: each ViewBuilder owns its
-- schema in ensure_schema() (derivation/views/base.py explains why — the
-- dense table's vector dimension comes from the configured embedder, so its
-- DDL cannot be a static file, and the views follow one consistent rule).
-- Likewise CREATE EXTENSION vector lives in the dense view's ensure_schema,
-- not here: core migrations must succeed on a Postgres without pgvector,
-- because the core system (grep-only retrieval) does not need it.

-- One WAL position per (view, namespace): how far each view's derivation has
-- consumed that namespace's WAL tail. Advancing this cursor happens in the
-- SAME transaction as the view writes it covers (derivation/engine.py), so a
-- crash between batches re-derives — never skips — and the delete-then-
-- rederive discipline makes the re-run idempotent. Per-namespace because the
-- resumable WAL tail is per-namespace (decisions.md #14).
CREATE TABLE IF NOT EXISTS view_cursors (
    view_name    TEXT NOT NULL,
    namespace    TEXT NOT NULL,
    wal_position BIGINT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (view_name, namespace)
);

-- L2 -> L4 lineage: which stored record row was projected into which view,
-- by which producer version, when (FRAMEWORK.md's lineage requirement; the
-- CI-07 rebuild/audit tuple). Append-only; a re-derivation appends a new
-- edge rather than updating an old one, so lineage history survives
-- reindexing the same way record history survives supersession.
CREATE TABLE IF NOT EXISTS lineage_edges (
    edge_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_row_id    BIGINT NOT NULL,
    record_id        TEXT NOT NULL,
    view_name        TEXT NOT NULL,
    producer_version TEXT NOT NULL,
    derived_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lineage_edges_record_row_idx
    ON lineage_edges (record_row_id);

CREATE INDEX IF NOT EXISTS lineage_edges_view_idx
    ON lineage_edges (view_name);
