-- ══════════════════════════════════════════════════════════════════════
-- ELECTION SYSTEM DATABASE SCHEMA
-- ══════════════════════════════════════════════════════════════════════
-- Supports voting for representatives organized by region and political party
-- Example: Abitibi region, CAQ party, candidate: Gabrielle Savois
-- ══════════════════════════════════════════════════════════════════════

-- Political Parties (CAQ, PLQ, PQ, QS, PCQ, etc.)
CREATE TABLE IF NOT EXISTS political_parties (
    id SERIAL PRIMARY KEY,
    party_code VARCHAR(10) UNIQUE NOT NULL,  -- e.g., 'CAQ', 'PLQ', 'PQ'
    party_name VARCHAR(100) NOT NULL,         -- e.g., 'Coalition Avenir Québec'
    party_color VARCHAR(7),                   -- Hex color for UI, e.g., '#0066CC'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Regions (Electoral districts/circonscriptions)
CREATE TABLE IF NOT EXISTS regions (
    id SERIAL PRIMARY KEY,
    region_code VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'ABITIBI-OUEST', 'MONTREAL-CENTRE'
    region_name VARCHAR(200) NOT NULL,        -- e.g., 'Abitibi-Ouest', 'Montréal-Centre'
    description TEXT,                         -- Optional description
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Elections (Can have multiple elections: provincial, municipal, etc.)
CREATE TABLE IF NOT EXISTS elections (
    id SERIAL PRIMARY KEY,
    election_code VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'PROV-2025', 'MUN-MTL-2025'
    election_name VARCHAR(200) NOT NULL,        -- e.g., 'Provincial Election 2025'
    election_type VARCHAR(50) NOT NULL,         -- 'provincial', 'municipal', 'federal'
    election_date DATE,
    status VARCHAR(20) DEFAULT 'draft',         -- 'draft', 'active', 'closed', 'results_published'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidates (Representatives running in elections)
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    region_id INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    party_id INTEGER REFERENCES political_parties(id) ON DELETE SET NULL,

    -- Candidate info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,

    -- Optional candidate details
    bio TEXT,
    photo_url VARCHAR(500),
    website_url VARCHAR(500),

    -- Status
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'withdrawn', 'disqualified'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one candidate per party per region per election
    UNIQUE(election_id, region_id, party_id)
);

-- Election Votes (Votes for candidates)
CREATE TABLE IF NOT EXISTS election_votes (
    id BIGSERIAL PRIMARY KEY,
    vote_hash VARCHAR(64) NOT NULL,          -- SHA256 of NAS+code (same as law voting)
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    region_id INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,

    -- Timestamps
    vote_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Metadata
    metadata JSONB
);

-- Election Results (Aggregated vote counts per candidate)
CREATE TABLE IF NOT EXISTS election_results (
    id SERIAL PRIMARY KEY,
    election_id INTEGER REFERENCES elections(id) ON DELETE CASCADE,
    region_id INTEGER REFERENCES regions(id) ON DELETE CASCADE,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,

    vote_count INTEGER DEFAULT 0,
    percentage DECIMAL(5,2),  -- Percentage of votes in region

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(election_id, region_id, candidate_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_candidates_election ON candidates(election_id);
CREATE INDEX IF NOT EXISTS idx_candidates_region ON candidates(region_id);
CREATE INDEX IF NOT EXISTS idx_candidates_party ON candidates(party_id);
CREATE INDEX IF NOT EXISTS idx_election_votes_hash ON election_votes(vote_hash);
CREATE INDEX IF NOT EXISTS idx_election_votes_election ON election_votes(election_id);
CREATE INDEX IF NOT EXISTS idx_election_votes_region ON election_votes(region_id);
CREATE INDEX IF NOT EXISTS idx_election_votes_candidate ON election_votes(candidate_id);
CREATE INDEX IF NOT EXISTS idx_election_results_election ON election_results(election_id);

-- ══════════════════════════════════════════════════════════════════════
-- SAMPLE DATA FOR TESTING
-- ══════════════════════════════════════════════════════════════════════

-- Insert sample political parties
INSERT INTO political_parties (party_code, party_name, party_color) VALUES
    ('CAQ', 'Coalition Avenir Québec', '#00A5E0'),
    ('PLQ', 'Parti Libéral du Québec', '#ED1B2F'),
    ('PQ', 'Parti Québécois', '#004B8D'),
    ('QS', 'Québec Solidaire', '#FF5605'),
    ('PCQ', 'Parti Conservateur du Québec', '#0C3B8D'),
    ('IND', 'Indépendant', '#808080')
ON CONFLICT (party_code) DO NOTHING;

-- Insert sample regions
INSERT INTO regions (region_code, region_name, description) VALUES
    ('ABITIBI-OUEST', 'Abitibi-Ouest', 'Région de l''Abitibi-Témiscamingue'),
    ('ABITIBI-EST', 'Abitibi-Est', 'Région de l''Abitibi-Témiscamingue'),
    ('MONTREAL-CENTRE', 'Montréal-Centre', 'Centre-ville de Montréal'),
    ('MONTREAL-NORD', 'Montréal-Nord', 'Nord de Montréal'),
    ('QUEBEC-CENTRE', 'Québec-Centre', 'Centre-ville de Québec'),
    ('SHERBROOKE', 'Sherbrooke', 'Région de l''Estrie')
ON CONFLICT (region_code) DO NOTHING;

-- Insert sample election
INSERT INTO elections (election_code, election_name, election_type, election_date, status) VALUES
    ('PROV-2025', 'Élection provinciale 2025', 'provincial', '2025-10-01', 'draft')
ON CONFLICT (election_code) DO NOTHING;

-- Insert sample candidates (based on your example)
INSERT INTO candidates (election_id, region_id, party_id, first_name, last_name, status)
SELECT
    e.id,
    r.id,
    p.id,
    'Gabrielle',
    'Savois',
    'active'
FROM elections e
CROSS JOIN regions r
CROSS JOIN political_parties p
WHERE e.election_code = 'PROV-2025'
    AND r.region_code = 'ABITIBI-OUEST'
    AND p.party_code = 'CAQ'
ON CONFLICT (election_id, region_id, party_id) DO NOTHING;

-- Add more sample candidates for different parties in Abitibi-Ouest
INSERT INTO candidates (election_id, region_id, party_id, first_name, last_name, status)
SELECT
    e.id,
    r.id,
    p.id,
    CASE p.party_code
        WHEN 'PLQ' THEN 'Jean'
        WHEN 'PQ' THEN 'Marie'
        WHEN 'QS' THEN 'Pierre'
        WHEN 'PCQ' THEN 'Sophie'
    END,
    CASE p.party_code
        WHEN 'PLQ' THEN 'Tremblay'
        WHEN 'PQ' THEN 'Gagnon'
        WHEN 'QS' THEN 'Côté'
        WHEN 'PCQ' THEN 'Roy'
    END,
    'active'
FROM elections e
CROSS JOIN regions r
CROSS JOIN political_parties p
WHERE e.election_code = 'PROV-2025'
    AND r.region_code = 'ABITIBI-OUEST'
    AND p.party_code IN ('PLQ', 'PQ', 'QS', 'PCQ')
ON CONFLICT (election_id, region_id, party_id) DO NOTHING;

COMMENT ON TABLE political_parties IS 'Political parties (CAQ, PLQ, PQ, etc.)';
COMMENT ON TABLE regions IS 'Electoral regions/circonscriptions';
COMMENT ON TABLE elections IS 'Elections (provincial, municipal, federal)';
COMMENT ON TABLE candidates IS 'Candidates running in elections, organized by region and party';
COMMENT ON TABLE election_votes IS 'Individual votes for candidates';
COMMENT ON TABLE election_results IS 'Aggregated vote counts per candidate';
