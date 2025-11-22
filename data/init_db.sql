-- Database Initialization Script for Distributed Voting System
--
-- This script creates the necessary tables and indexes for the voting system.
-- It is automatically executed when PostgreSQL container starts.
--
-- Tables:
--   - vote_results: Aggregated vote counts per law
--   - vote_audit: Detailed audit trail of all votes
--   - duplicate_attempts: Track duplicate voting attempts
--   - system_stats: System-wide statistics

-- Enable UUID extension (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search optimization (optional)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- TABLE: vote_results
-- Stores aggregated vote counts for each law
-- ============================================================================
CREATE TABLE IF NOT EXISTS vote_results (
    id SERIAL PRIMARY KEY,
    law_id VARCHAR(50) NOT NULL UNIQUE,
    oui_count INTEGER NOT NULL DEFAULT 0,
    non_count INTEGER NOT NULL DEFAULT 0,
    total_votes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT vote_results_law_id_check CHECK (law_id != ''),
    CONSTRAINT vote_results_oui_count_check CHECK (oui_count >= 0),
    CONSTRAINT vote_results_non_count_check CHECK (non_count >= 0),
    CONSTRAINT vote_results_total_check CHECK (total_votes = oui_count + non_count)
);

-- Indexes for vote_results
CREATE INDEX IF NOT EXISTS idx_vote_results_law_id ON vote_results(law_id);
CREATE INDEX IF NOT EXISTS idx_vote_results_updated_at ON vote_results(updated_at DESC);

-- ============================================================================
-- TABLE: vote_audit
-- Detailed audit trail of all vote submissions
-- ============================================================================
CREATE TABLE IF NOT EXISTS vote_audit (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) NOT NULL,
    law_id VARCHAR(50) NOT NULL,
    vote VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    metadata JSONB,

    -- Constraints
    CONSTRAINT vote_audit_hash_check CHECK (length(vote_hash) = 64),
    CONSTRAINT vote_audit_vote_check CHECK (vote IN ('oui', 'non')),
    CONSTRAINT vote_audit_status_check CHECK (status IN ('pending', 'validated', 'duplicate', 'invalid', 'aggregated'))
);

-- Indexes for vote_audit
CREATE INDEX IF NOT EXISTS idx_vote_audit_hash ON vote_audit(vote_hash);
CREATE INDEX IF NOT EXISTS idx_vote_audit_law_id ON vote_audit(law_id);
CREATE INDEX IF NOT EXISTS idx_vote_audit_status ON vote_audit(status);
CREATE INDEX IF NOT EXISTS idx_vote_audit_timestamp ON vote_audit(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_vote_audit_processed_at ON vote_audit(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vote_audit_hash_law ON vote_audit(vote_hash, law_id);

-- GIN index for JSONB metadata queries
CREATE INDEX IF NOT EXISTS idx_vote_audit_metadata ON vote_audit USING GIN (metadata);

-- ============================================================================
-- TABLE: duplicate_attempts
-- Track duplicate voting attempts for security monitoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS duplicate_attempts (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) NOT NULL,
    law_id VARCHAR(50) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    first_attempt_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_attempt_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_addresses JSONB,
    user_agents JSONB,

    -- Constraints
    CONSTRAINT duplicate_attempts_hash_check CHECK (length(vote_hash) = 64),
    CONSTRAINT duplicate_attempts_count_check CHECK (attempt_count > 0),
    CONSTRAINT duplicate_attempts_unique_hash_law UNIQUE (vote_hash, law_id)
);

-- Indexes for duplicate_attempts
CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_hash ON duplicate_attempts(vote_hash);
CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_count ON duplicate_attempts(attempt_count DESC);
CREATE INDEX IF NOT EXISTS idx_duplicate_attempts_last_at ON duplicate_attempts(last_attempt_at DESC);

-- ============================================================================
-- TABLE: system_stats
-- System-wide statistics and metrics
-- ============================================================================
CREATE TABLE IF NOT EXISTS system_stats (
    id SERIAL PRIMARY KEY,
    stat_key VARCHAR(100) NOT NULL UNIQUE,
    stat_value BIGINT NOT NULL DEFAULT 0,
    stat_type VARCHAR(50) NOT NULL DEFAULT 'counter',
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT system_stats_key_check CHECK (stat_key != ''),
    CONSTRAINT system_stats_type_check CHECK (stat_type IN ('counter', 'gauge', 'histogram'))
);

-- Index for system_stats
CREATE INDEX IF NOT EXISTS idx_system_stats_key ON system_stats(stat_key);

-- ============================================================================
-- TABLE: processing_queue_stats
-- Track queue processing statistics over time
-- ============================================================================
CREATE TABLE IF NOT EXISTS processing_queue_stats (
    id BIGSERIAL PRIMARY KEY,
    queue_name VARCHAR(50) NOT NULL,
    messages_count INTEGER NOT NULL DEFAULT 0,
    consumers_count INTEGER NOT NULL DEFAULT 0,
    messages_rate DECIMAL(10, 2),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT queue_stats_name_check CHECK (queue_name IN ('validation', 'aggregation', 'review'))
);

-- Indexes for processing_queue_stats
CREATE INDEX IF NOT EXISTS idx_queue_stats_queue ON processing_queue_stats(queue_name);
CREATE INDEX IF NOT EXISTS idx_queue_stats_timestamp ON processing_queue_stats(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_queue_stats_queue_time ON processing_queue_stats(queue_name, timestamp DESC);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for vote_results
CREATE TRIGGER update_vote_results_updated_at
    BEFORE UPDATE ON vote_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for system_stats
CREATE TRIGGER update_system_stats_updated_at
    BEFORE UPDATE ON system_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Initialize system statistics counters
INSERT INTO system_stats (stat_key, stat_value, stat_type, description) VALUES
    ('total_votes_received', 0, 'counter', 'Total number of votes received'),
    ('total_votes_validated', 0, 'counter', 'Total number of votes validated'),
    ('total_votes_aggregated', 0, 'counter', 'Total number of votes aggregated'),
    ('total_duplicates', 0, 'counter', 'Total number of duplicate attempts'),
    ('total_invalid', 0, 'counter', 'Total number of invalid votes'),
    ('peak_votes_per_second', 0, 'gauge', 'Peak votes per second'),
    ('current_validation_queue_depth', 0, 'gauge', 'Current validation queue depth'),
    ('current_aggregation_queue_depth', 0, 'gauge', 'Current aggregation queue depth')
ON CONFLICT (stat_key) DO NOTHING;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for vote summary
CREATE OR REPLACE VIEW vote_summary AS
SELECT
    law_id,
    oui_count,
    non_count,
    total_votes,
    CASE
        WHEN total_votes > 0 THEN ROUND((oui_count::DECIMAL / total_votes * 100), 2)
        ELSE 0
    END AS oui_percentage,
    CASE
        WHEN total_votes > 0 THEN ROUND((non_count::DECIMAL / total_votes * 100), 2)
        ELSE 0
    END AS non_percentage,
    updated_at AS last_vote_at
FROM vote_results
ORDER BY total_votes DESC;

-- View for recent audit entries
CREATE OR REPLACE VIEW recent_audit_entries AS
SELECT
    id,
    vote_hash,
    law_id,
    vote,
    status,
    timestamp,
    processed_at,
    error_message
FROM vote_audit
ORDER BY processed_at DESC
LIMIT 1000;

-- View for top duplicate attempts
CREATE OR REPLACE VIEW top_duplicate_attempts AS
SELECT
    vote_hash,
    law_id,
    attempt_count,
    first_attempt_at,
    last_attempt_at,
    (last_attempt_at - first_attempt_at) AS duration
FROM duplicate_attempts
WHERE attempt_count > 1
ORDER BY attempt_count DESC
LIMIT 100;

-- ============================================================================
-- PARTITIONING SETUP (for production scale)
-- ============================================================================

-- Note: For systems expecting millions of audit records, consider partitioning
-- the vote_audit table by timestamp. Example for monthly partitioning:
--
-- CREATE TABLE vote_audit_2024_01 PARTITION OF vote_audit
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- CREATE TABLE vote_audit_2024_02 PARTITION OF vote_audit
--     FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- etc.

-- ============================================================================
-- GRANTS (adjust based on your security requirements)
-- ============================================================================

-- Grant permissions to voting_user (created in docker-compose environment)
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO voting_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO voting_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO voting_user;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete!';
    RAISE NOTICE 'Tables created: vote_results, vote_audit, duplicate_attempts, system_stats, processing_queue_stats';
    RAISE NOTICE 'Views created: vote_summary, recent_audit_entries, top_duplicate_attempts';
END $$;
