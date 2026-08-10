-- Plan trace store: the persisted record behind EXPLAIN-after-the-fact and
-- replay-by-record (FRAMEWORK.md §Core abstractions #5). Every executed plan
-- writes one row here holding the compiled plan AND the exact EvidenceState
-- it produced, serialized in full — so a replay reconstructs what actually
-- happened from this row, never by recomputing against a live corpus that may
-- since have changed. That is the whole point of replay-by-record: "what did
-- the system do" is answerable verbatim, distinct from "what would it do now."
--
-- The audit trail (this table) ships unconditionally from v1 (§MVP definition,
-- "Security default: audit-trail logging ships unconditionally"), not behind
-- any profile flag.

CREATE TABLE IF NOT EXISTS plan_traces (
    plan_id        TEXT PRIMARY KEY,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    namespace      TEXT NOT NULL,
    plan_selector  TEXT NOT NULL,
    propensity     DOUBLE PRECISION NOT NULL,
    -- The compiled plan (steps, budget, the principal it ran as) and the full
    -- EvidenceState it produced, each serialized so a replay is a
    -- reconstruction, not a recomputation.
    plan_json      JSONB NOT NULL,
    evidence_json  JSONB NOT NULL
);

-- Replay is by plan_id (the PK, already indexed). This index serves the audit
-- query "what did this principal's namespace retrieve, in order" without a
-- sequential scan.
CREATE INDEX IF NOT EXISTS plan_traces_namespace_created_idx
    ON plan_traces (namespace, created_at);
