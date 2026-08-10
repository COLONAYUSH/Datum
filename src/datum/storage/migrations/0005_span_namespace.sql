-- Span identity (the uniqueness-CAS key) becomes namespace-scoped.
--
-- Found by the Milestone B derivation-engine tests (decisions.md #19): the
-- 0002 index was UNIQUE (source_id, stable_key) WHERE tx_to IS NULL —
-- GLOBAL across namespaces. source_id/stable_key are caller-chosen, so two
-- tenants ingesting a document under the same source id collided on the
-- same span: the second tenant's assert was either silently no-opped
-- (identical content) or CONVERTED TO A SUPERSEDE OF THE FIRST TENANT'S
-- LIVE RECORD (different content) — cross-tenant write interference, the
-- CI-03 class of failure on the write side. A span is an identity WITHIN a
-- tenant's partition; the invariant is "at most one live record per
-- (namespace, source_id, stable_key)."
--
-- Loosening a unique index never conflicts with existing data, so this is
-- safe to apply to a populated database.

DROP INDEX IF EXISTS records_one_live_per_span;

CREATE UNIQUE INDEX IF NOT EXISTS records_one_live_per_span
    ON records (namespace, source_id, stable_key)
    WHERE tx_to IS NULL;
