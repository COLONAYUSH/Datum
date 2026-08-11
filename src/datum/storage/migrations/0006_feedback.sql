-- Relevance feedback (decisions.md #44): the raw material of the learned
-- relevance loop. Each row is one judgment — "this record was useful / not
-- useful for the search identified by plan_id" — written through
-- Corpus.feedback (which resolves the caller's signed hit token, so a row
-- can only ever reference a record the caller was actually served).
-- plan_id joins back to plan_traces, so the ORIGINAL query text and the full
-- retrieval decision that produced the hit are always recoverable: feedback
-- is never an orphaned thumbs-up, it is a labeled example attached to a
-- replayable retrieval. `datum calibrate` consumes these rows per namespace.
CREATE TABLE IF NOT EXISTS relevance_feedback (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    namespace   TEXT        NOT NULL,
    plan_id     TEXT        NOT NULL,
    record_id   TEXT        NOT NULL,
    useful      BOOLEAN     NOT NULL,
    principal_id TEXT       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS relevance_feedback_ns_idx
    ON relevance_feedback (namespace, created_at);

-- Per-namespace retrieval-policy overrides (decisions.md #44): the OUTPUT of
-- `datum calibrate`. One row per namespace; params is the calibrated
-- fusion-weight/floor set, promoted only after beating the current policy on
-- held-out feedback. Corpus.open loads these at wiring time; RuleTablePolicy
-- consults them per-namespace at plan-selection time. `basis` records what
-- the calibration saw (feedback rows, holdout score) — a policy change is
-- auditable back to its evidence, like every other decision in the system.
CREATE TABLE IF NOT EXISTS policy_overrides (
    namespace   TEXT PRIMARY KEY,
    params      JSONB       NOT NULL,
    basis       JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
