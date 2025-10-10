-- init_ingest_db.sql
-- Version: 2025-08-10 09:30 UTC
-- Ingest Database schema, ingest schema (verified production version)
-- Last Verified: 2025-08-10 against live database
-- Row Count: 18,973 uplinks | Storage: 30 MB

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS ingest;

-- Create main uplinks table
CREATE TABLE ingest.raw_uplinks (
    uplink_id           SERIAL PRIMARY KEY,
    deveui              TEXT NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fport               INTEGER,
    payload             TEXT,
    uplink_metadata     JSONB,
    source              TEXT NOT NULL DEFAULT 'unknown',
    processed           BOOLEAN DEFAULT FALSE,
    gateway_eui         VARCHAR(64)
);

-- Performance indexes (production verified)
CREATE INDEX idx_raw_uplinks_deveui ON ingest.raw_uplinks (deveui);
CREATE INDEX idx_raw_uplinks_received_at ON ingest.raw_uplinks (received_at);
CREATE INDEX idx_raw_uplinks_processed ON ingest.raw_uplinks (processed);

-- User permissions (verified working configuration)
GRANT USAGE ON SCHEMA ingest TO ingestuser;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingest.raw_uplinks TO ingestuser;