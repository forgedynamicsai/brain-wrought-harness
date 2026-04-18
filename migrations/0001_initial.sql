-- =============================================================================
-- Brain-Wrought: Initial schema
-- BW-005: brain_wrought Supabase schema with RLS, indexes, and leaderboard
--
-- Idempotent: safe to re-run on a fresh Supabase project via IF NOT EXISTS
-- guards throughout.  The migration was first applied to the shared wroughtai
-- project (ref: dtvdkuhteckxiwdjiikf) and must be re-applied when a dedicated
-- project is provisioned.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS brain_wrought;

-- ---------------------------------------------------------------------------
-- Table: submissions
-- One row per submitted Docker image.  Composite score and per-axis JSONB
-- scores are written back by the harness after evaluation completes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brain_wrought.submissions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT            NOT NULL,
    submitter_github    TEXT,
    source_url          TEXT,
    model_family        TEXT,
    -- SHA-256 of (Docker image digest || harness version)
    submission_hash     TEXT            NOT NULL UNIQUE,
    harness_version     TEXT            NOT NULL,
    qrel_version        TEXT            NOT NULL DEFAULT 'pending',
    evaluation_seed     INTEGER         NOT NULL DEFAULT 0,
    -- Per-axis score payloads written back after evaluation
    retrieval_score     JSONB,
    ingestion_score     JSONB,
    assistant_score     JSONB,
    composite_score     NUMERIC(6,4),
    status              TEXT            NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','running','evaluated','failed','delisted')),
    submitted_at        TIMESTAMPTZ     NOT NULL DEFAULT now(),
    evaluated_at        TIMESTAMPTZ
);

COMMENT ON TABLE brain_wrought.submissions IS
    'One row per submitted Docker image.  Composite and per-axis scores are '
    'written back by the harness once evaluation completes.';

COMMENT ON COLUMN brain_wrought.submissions.submission_hash IS
    'SHA-256 digest of (Docker image digest || harness version string). '
    'Unique constraint prevents duplicate submissions.';
COMMENT ON COLUMN brain_wrought.submissions.qrel_version IS
    'Version tag of the sealed qrel set used during evaluation.';
COMMENT ON COLUMN brain_wrought.submissions.evaluation_seed IS
    'Integer seed threaded through every stochastic operation in the harness.';
COMMENT ON COLUMN brain_wrought.submissions.status IS
    'Lifecycle state: pending → running → evaluated | failed; '
    'delisted for withdrawn entries.';

-- ---------------------------------------------------------------------------
-- Table: runs
-- One row per evaluation attempt against a submission.  A submission may
-- accumulate multiple runs (e.g., retries after transient failures).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brain_wrought.runs (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id       UUID            NOT NULL
                            REFERENCES brain_wrought.submissions(id)
                            ON DELETE CASCADE,
    harness_version     TEXT            NOT NULL,
    docker_image_digest TEXT,
    judge_panel_hash    TEXT,
    started_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    status              TEXT            NOT NULL DEFAULT 'running',
    error               TEXT
);

COMMENT ON TABLE brain_wrought.runs IS
    'One row per evaluation attempt per submission.  A single submission may '
    'have multiple runs (retries, re-evaluations after harness updates).';

COMMENT ON COLUMN brain_wrought.runs.docker_image_digest IS
    'Exact digest of the Docker image pulled for this run.';
COMMENT ON COLUMN brain_wrought.runs.judge_panel_hash IS
    'Fingerprint of the judge model / rubric configuration in effect.';
COMMENT ON COLUMN brain_wrought.runs.error IS
    'Non-null when status = ''failed''; contains the error message or '
    'exception traceback excerpt.';

-- ---------------------------------------------------------------------------
-- Table: scores
-- Axis-level numeric scores produced by a run.  One row per axis per run.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brain_wrought.scores (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID            NOT NULL
                        REFERENCES brain_wrought.runs(id)
                        ON DELETE CASCADE,
    axis            TEXT            NOT NULL
                        CHECK (axis IN ('retrieval','ingestion','assistant','composite')),
    score           NUMERIC(6,4),
    detail          JSONB,
    qrel_version    TEXT            NOT NULL,
    scored_at       TIMESTAMPTZ     NOT NULL DEFAULT now()
);

COMMENT ON TABLE brain_wrought.scores IS
    'Axis-level scores produced by a single evaluation run.  '
    'One row per axis (retrieval, ingestion, assistant, composite).';

COMMENT ON COLUMN brain_wrought.scores.axis IS
    'Scoring dimension: retrieval | ingestion | assistant | composite.';
COMMENT ON COLUMN brain_wrought.scores.detail IS
    'Structured breakdown: per-query scores, judge votes, confidence bands, etc.';
COMMENT ON COLUMN brain_wrought.scores.qrel_version IS
    'Version of the sealed qrel set applied to produce this score.';

-- ---------------------------------------------------------------------------
-- Table: audit_log
-- Append-only event log for the harness.  Rows are never updated or deleted.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brain_wrought.audit_log (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT            NOT NULL,
    submission_id   UUID            REFERENCES brain_wrought.submissions(id)
                        ON DELETE SET NULL,
    run_id          UUID            REFERENCES brain_wrought.runs(id)
                        ON DELETE SET NULL,
    details         JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
);

COMMENT ON TABLE brain_wrought.audit_log IS
    'Append-only event log.  Rows are never modified after insert.  '
    'Records harness lifecycle events, policy decisions, and anomalies.';

COMMENT ON COLUMN brain_wrought.audit_log.event_type IS
    'Free-form event classifier, e.g. submission_received, run_started, '
    'run_failed, score_written, submission_delisted.';
COMMENT ON COLUMN brain_wrought.audit_log.details IS
    'Arbitrary structured payload relevant to the event.';

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- submissions: filter by lifecycle state (worker queue queries)
CREATE INDEX IF NOT EXISTS idx_submissions_status
    ON brain_wrought.submissions (status);

-- submissions: leaderboard / ranked listing queries
CREATE INDEX IF NOT EXISTS idx_submissions_composite_score
    ON brain_wrought.submissions (composite_score DESC NULLS LAST);

-- runs: look up all runs for a given submission
CREATE INDEX IF NOT EXISTS idx_runs_submission_id
    ON brain_wrought.runs (submission_id);

-- scores: look up all axis scores for a given run
CREATE INDEX IF NOT EXISTS idx_scores_run_id
    ON brain_wrought.scores (run_id);

-- audit_log: look up events for a given submission
CREATE INDEX IF NOT EXISTS idx_audit_log_submission_id
    ON brain_wrought.audit_log (submission_id);

-- audit_log: recent-events queries (descending by creation time)
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON brain_wrought.audit_log (created_at DESC);

-- ---------------------------------------------------------------------------
-- Materialized view: leaderboard
-- Public-facing ranked view over evaluated submissions.
-- Requires a unique index for REFRESH CONCURRENTLY.
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS brain_wrought.leaderboard AS
SELECT
    s.id,
    s.name,
    s.submitter_github,
    s.source_url,
    s.model_family,
    s.harness_version,
    s.qrel_version,
    s.composite_score,
    s.retrieval_score,
    s.ingestion_score,
    s.assistant_score,
    s.evaluated_at
FROM brain_wrought.submissions s
WHERE s.status = 'evaluated'
ORDER BY s.composite_score DESC NULLS LAST;

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_leaderboard_id
    ON brain_wrought.leaderboard (id);

-- ---------------------------------------------------------------------------
-- Function: refresh_leaderboard
-- Called by the harness (via service role) after each run completes to keep
-- the public leaderboard up to date without locking reads.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION brain_wrought.refresh_leaderboard()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = brain_wrought, public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY brain_wrought.leaderboard;
END;
$$;

COMMENT ON FUNCTION brain_wrought.refresh_leaderboard() IS
    'Refreshes the brain_wrought.leaderboard materialized view concurrently '
    '(non-blocking).  Call this from the harness after each run completes.';

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE brain_wrought.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.scores      ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.audit_log   ENABLE ROW LEVEL SECURITY;

-- Anonymous users may read submissions (public benchmark leaderboard)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'brain_wrought'
          AND tablename  = 'submissions'
          AND policyname = 'anon_read_submissions'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY anon_read_submissions
                ON brain_wrought.submissions
                FOR SELECT
                TO anon
                USING (true)
        $policy$;
    END IF;
END;
$$;

-- Service role has full write access to all tables
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'brain_wrought'
          AND tablename  = 'submissions'
          AND policyname = 'service_role_write_submissions'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY service_role_write_submissions
                ON brain_wrought.submissions
                FOR ALL
                TO service_role
                USING (true)
                WITH CHECK (true)
        $policy$;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'brain_wrought'
          AND tablename  = 'runs'
          AND policyname = 'service_role_write_runs'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY service_role_write_runs
                ON brain_wrought.runs
                FOR ALL
                TO service_role
                USING (true)
                WITH CHECK (true)
        $policy$;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'brain_wrought'
          AND tablename  = 'scores'
          AND policyname = 'service_role_write_scores'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY service_role_write_scores
                ON brain_wrought.scores
                FOR ALL
                TO service_role
                USING (true)
                WITH CHECK (true)
        $policy$;
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'brain_wrought'
          AND tablename  = 'audit_log'
          AND policyname = 'service_role_write_audit_log'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY service_role_write_audit_log
                ON brain_wrought.audit_log
                FOR ALL
                TO service_role
                USING (true)
                WITH CHECK (true)
        $policy$;
    END IF;
END;
$$;

-- leaderboard is a materialized view; grant SELECT to anon directly
GRANT USAGE  ON SCHEMA brain_wrought TO anon;
GRANT SELECT ON brain_wrought.leaderboard TO anon;
GRANT SELECT ON brain_wrought.submissions TO anon;
