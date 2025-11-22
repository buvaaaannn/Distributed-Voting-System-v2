-- Database schema for election vote aggregation system

-- Main vote results table (aggregated counts)
CREATE TABLE IF NOT EXISTS vote_results (
    law_id VARCHAR(50) PRIMARY KEY,
    oui_count BIGINT DEFAULT 0 CHECK (oui_count >= 0),
    non_count BIGINT DEFAULT 0 CHECK (non_count >= 0),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for faster queries on updated_at
CREATE INDEX IF NOT EXISTS idx_vote_results_updated
ON vote_results(updated_at DESC);

-- Index for total counts (for analytics)
CREATE INDEX IF NOT EXISTS idx_vote_results_totals
ON vote_results((oui_count + non_count) DESC);


-- Vote audit log (individual votes for auditing)
CREATE TABLE IF NOT EXISTS vote_audit (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) NOT NULL UNIQUE,
    citizen_id VARCHAR(100) NOT NULL,
    law_id VARCHAR(50) NOT NULL,
    choice VARCHAR(10) NOT NULL CHECK (choice IN ('oui', 'non')),
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB
);

-- Indexes for vote_audit
CREATE INDEX IF NOT EXISTS idx_vote_audit_vote_hash
ON vote_audit(vote_hash);

CREATE INDEX IF NOT EXISTS idx_vote_audit_citizen_law
ON vote_audit(citizen_id, law_id);

CREATE INDEX IF NOT EXISTS idx_vote_audit_law_id
ON vote_audit(law_id);

CREATE INDEX IF NOT EXISTS idx_vote_audit_timestamp
ON vote_audit(timestamp DESC);


-- Duplicate vote attempts tracking
CREATE TABLE IF NOT EXISTS duplicate_attempts (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) NOT NULL,
    citizen_id VARCHAR(100) NOT NULL,
    law_id VARCHAR(50) NOT NULL,
    choice VARCHAR(10) NOT NULL,
    attempt_timestamp TIMESTAMP DEFAULT NOW(),
    reason TEXT,
    ip_address INET,
    FOREIGN KEY (vote_hash) REFERENCES vote_audit(vote_hash)
);

-- Index for duplicate_attempts
CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_vote_hash
ON duplicate_attempts(vote_hash);

CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_citizen_law
ON duplicate_attempts(citizen_id, law_id);

CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_timestamp
ON duplicate_attempts(attempt_timestamp DESC);


-- Law metadata table (optional, for reference)
CREATE TABLE IF NOT EXISTS laws (
    law_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'closed', 'draft')),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for laws
CREATE INDEX IF NOT EXISTS idx_laws_status
ON laws(status);

CREATE INDEX IF NOT EXISTS idx_laws_dates
ON laws(start_date, end_date);


-- Aggregation statistics table (for monitoring)
CREATE TABLE IF NOT EXISTS aggregation_stats (
    id BIGSERIAL PRIMARY KEY,
    batch_size INTEGER NOT NULL,
    processing_duration_ms INTEGER NOT NULL,
    votes_processed INTEGER NOT NULL,
    errors_count INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Index for aggregation_stats
CREATE INDEX IF NOT EXISTS idx_aggregation_stats_timestamp
ON aggregation_stats(timestamp DESC);


-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for vote_results
DROP TRIGGER IF EXISTS update_vote_results_updated_at ON vote_results;
CREATE TRIGGER update_vote_results_updated_at
    BEFORE UPDATE ON vote_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for laws
DROP TRIGGER IF EXISTS update_laws_updated_at ON laws;
CREATE TRIGGER update_laws_updated_at
    BEFORE UPDATE ON laws
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- View for vote statistics by law
CREATE OR REPLACE VIEW vote_statistics AS
SELECT
    vr.law_id,
    vr.oui_count,
    vr.non_count,
    (vr.oui_count + vr.non_count) AS total_votes,
    CASE
        WHEN (vr.oui_count + vr.non_count) > 0
        THEN ROUND((vr.oui_count::NUMERIC / (vr.oui_count + vr.non_count)::NUMERIC) * 100, 2)
        ELSE 0
    END AS oui_percentage,
    CASE
        WHEN (vr.oui_count + vr.non_count) > 0
        THEN ROUND((vr.non_count::NUMERIC / (vr.oui_count + vr.non_count)::NUMERIC) * 100, 2)
        ELSE 0
    END AS non_percentage,
    vr.updated_at
FROM vote_results vr
ORDER BY total_votes DESC;


-- View for duplicate detection summary
CREATE OR REPLACE VIEW duplicate_summary AS
SELECT
    law_id,
    COUNT(*) AS duplicate_count,
    COUNT(DISTINCT citizen_id) AS unique_citizens,
    MIN(attempt_timestamp) AS first_attempt,
    MAX(attempt_timestamp) AS last_attempt
FROM duplicate_attempts
GROUP BY law_id
ORDER BY duplicate_count DESC;


-- Initial data: Sample laws (optional)
INSERT INTO laws (law_id, title, description, category, status, start_date)
VALUES
    ('law-001', 'Loi sur la transition énergétique', 'Mesures pour accélérer la transition vers les énergies renouvelables', 'Environnement', 'active', NOW()),
    ('law-002', 'Réforme du système de santé', 'Amélioration de l''accès aux soins et modernisation des hôpitaux', 'Santé', 'active', NOW()),
    ('law-003', 'Loi sur l''éducation numérique', 'Intégration des technologies dans l''enseignement', 'Éducation', 'active', NOW())
ON CONFLICT (law_id) DO NOTHING;


-- Grant permissions (adjust as needed for your environment)
-- GRANT SELECT, INSERT, UPDATE ON vote_results TO aggregation_service;
-- GRANT SELECT, INSERT ON vote_audit TO aggregation_service;
-- GRANT SELECT, INSERT ON duplicate_attempts TO aggregation_service;
-- GRANT SELECT ON laws TO aggregation_service;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aggregation_service;

-- Helpful queries for monitoring

-- Get vote counts for all laws
-- SELECT * FROM vote_statistics;

-- Find laws with most votes
-- SELECT law_id, total_votes FROM vote_statistics ORDER BY total_votes DESC LIMIT 10;

-- Check for duplicate attempts
-- SELECT * FROM duplicate_summary WHERE duplicate_count > 10;

-- Recent aggregation performance
-- SELECT
--     DATE_TRUNC('minute', timestamp) AS minute,
--     AVG(processing_duration_ms) AS avg_duration_ms,
--     SUM(votes_processed) AS total_votes,
--     SUM(errors_count) AS total_errors
-- FROM aggregation_stats
-- WHERE timestamp > NOW() - INTERVAL '1 hour'
-- GROUP BY minute
-- ORDER BY minute DESC;
