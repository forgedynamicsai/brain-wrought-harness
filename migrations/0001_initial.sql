-- Brain-Wrought initial schema
-- BW-005: Supabase brain_wrought schema with RLS
-- Stub — full implementation in Phase 1

CREATE SCHEMA IF NOT EXISTS brain_wrought;

-- submissions: one row per submitted Docker image
CREATE TABLE brain_wrought.submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    submitter_github TEXT,
    source_url TEXT,
    model_family TEXT,
    submission_hash TEXT NOT NULL,
    harness_version TEXT NOT NULL,
    retrieval_score JSONB,
    ingestion_score JSONB,
    assistant_score JSONB,
    composite_score NUMERIC,
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ DEFAULT now(),
    evaluated_at TIMESTAMPTZ,
    evaluation_seed INTEGER NOT NULL DEFAULT 0,
    qrel_version TEXT NOT NULL DEFAULT 'pending',
    config JSONB DEFAULT '{}'
);

-- runs: one row per eval attempt per submission
CREATE TABLE brain_wrought.runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES brain_wrought.submissions(id),
    harness_version TEXT NOT NULL,
    docker_image_digest TEXT,
    judge_panel_hash TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT
);

-- scores: axis-level scores per run
CREATE TABLE brain_wrought.scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES brain_wrought.runs(id),
    axis TEXT NOT NULL CHECK (axis IN ('retrieval', 'ingestion', 'assistant', 'composite')),
    score NUMERIC,
    detail JSONB,
    qrel_version TEXT NOT NULL,
    scored_at TIMESTAMPTZ DEFAULT now()
);

-- audit_log: append-only eval event log
CREATE TABLE brain_wrought.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    submission_id UUID REFERENCES brain_wrought.submissions(id),
    run_id UUID REFERENCES brain_wrought.runs(id),
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- leaderboard: materialized view (refreshed on run completion)
CREATE MATERIALIZED VIEW brain_wrought.leaderboard AS
SELECT
    s.id,
    s.name,
    s.submitter_github,
    s.source_url,
    s.composite_score,
    s.retrieval_score,
    s.ingestion_score,
    s.assistant_score,
    s.evaluated_at,
    s.qrel_version
FROM brain_wrought.submissions s
WHERE s.status = 'evaluated'
ORDER BY s.composite_score DESC NULLS LAST;

-- RLS policies
ALTER TABLE brain_wrought.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_wrought.audit_log ENABLE ROW LEVEL SECURITY;

-- Anonymous read access to submissions and leaderboard (public benchmark)
CREATE POLICY "public read submissions"
    ON brain_wrought.submissions FOR SELECT
    TO anon USING (true);

-- Service role has full write access
CREATE POLICY "service write submissions"
    ON brain_wrought.submissions FOR ALL
    TO service_role USING (true);

CREATE POLICY "service write runs"
    ON brain_wrought.runs FOR ALL
    TO service_role USING (true);

CREATE POLICY "service write scores"
    ON brain_wrought.scores FOR ALL
    TO service_role USING (true);

CREATE POLICY "service write audit_log"
    ON brain_wrought.audit_log FOR ALL
    TO service_role USING (true);
