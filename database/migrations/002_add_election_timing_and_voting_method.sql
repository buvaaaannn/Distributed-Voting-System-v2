-- ══════════════════════════════════════════════════════════════════════
-- Migration: Add Election Timing and Voting Method
-- ══════════════════════════════════════════════════════════════════════
-- Adds start/end datetime fields and voting method to elections table
-- Allows for time-based vote acceptance and ranked-choice voting support
-- ══════════════════════════════════════════════════════════════════════

-- Add start_datetime and end_datetime columns
ALTER TABLE elections
ADD COLUMN IF NOT EXISTS start_datetime TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS end_datetime TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS voting_method VARCHAR(20) DEFAULT 'single_choice';

-- Add comments
COMMENT ON COLUMN elections.start_datetime IS 'When voting opens for this election';
COMMENT ON COLUMN elections.end_datetime IS 'When voting closes for this election (no new votes accepted after this time)';
COMMENT ON COLUMN elections.voting_method IS 'Voting method: single_choice or ranked_choice';

-- Update existing elections to have reasonable defaults
-- Set start_datetime to election_date at 00:00:00
-- Set end_datetime to election_date at 23:59:59
UPDATE elections
SET start_datetime = election_date::timestamp AT TIME ZONE 'America/Toronto',
    end_datetime = (election_date::timestamp + INTERVAL '23 hours 59 minutes 59 seconds') AT TIME ZONE 'America/Toronto',
    voting_method = 'single_choice'
WHERE start_datetime IS NULL OR end_datetime IS NULL;

-- Add check constraint to ensure end_datetime is after start_datetime
ALTER TABLE elections
ADD CONSTRAINT check_election_datetime
CHECK (end_datetime > start_datetime);
