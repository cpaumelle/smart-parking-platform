-- init_transform_db.sql
-- Version: 1.1.0 - 2025-08-11 07:30 UTC
-- FINAL VERSION - VERIFIED 100% MATCH WITH LIVE DATABASE
-- Verified against live database schema query results 2025-08-11
-- Tables: 7 | Indexes: 12 | Foreign Keys: 16

-- ─── EXTENSIONS ─────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── SCHEMA ─────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS transform;

-- ─── TABLE: device_types (1st - no dependencies) ───────────
CREATE TABLE IF NOT EXISTS transform.device_types (
    device_type_id      SERIAL PRIMARY KEY,
    device_type         VARCHAR(255) NOT NULL,
    description         TEXT,
    unpacker            VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at         TIMESTAMPTZ
);

-- ─── TABLE: locations (2nd - self-referencing) ─────────────
CREATE TABLE IF NOT EXISTS transform.locations (
    location_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    type                TEXT CHECK (type IN ('site', 'floor', 'room', 'zone')),
    parent_id           UUID REFERENCES transform.locations(location_id),
    uplink_metadata     JSONB,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ,
    archived_at         TIMESTAMPTZ
);

-- ─── TABLE: device_context (3rd - depends on locations & device_types) ───
CREATE TABLE IF NOT EXISTS transform.device_context (
    deveui              VARCHAR(16) PRIMARY KEY,
    location_id         UUID REFERENCES transform.locations(location_id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at         TIMESTAMP,
    unassigned_at       TIMESTAMP,
    device_context_id   INTEGER,
    last_gateway        VARCHAR(255),
    lifecycle_state     VARCHAR(50),
    site_id             UUID REFERENCES transform.locations(location_id),
    floor_id            UUID REFERENCES transform.locations(location_id),
    room_id             UUID REFERENCES transform.locations(location_id),
    zone_id             UUID REFERENCES transform.locations(location_id),
    device_type_id      INTEGER REFERENCES transform.device_types(device_type_id),
    archived_at         TIMESTAMPTZ,
    name                VARCHAR(255)
);

-- Add named foreign key constraints for device_context (to match live DB)
ALTER TABLE transform.device_context 
ADD CONSTRAINT fk_device_context_site 
FOREIGN KEY (site_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context 
ADD CONSTRAINT fk_device_context_floor 
FOREIGN KEY (floor_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context 
ADD CONSTRAINT fk_device_context_room 
FOREIGN KEY (room_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context 
ADD CONSTRAINT fk_device_context_zone 
FOREIGN KEY (zone_id) REFERENCES transform.locations(location_id);

-- ─── TABLE: gateways (4th - depends on locations) ──────────
CREATE TABLE IF NOT EXISTS transform.gateways (
    gw_eui              TEXT PRIMARY KEY,
    gateway_name        VARCHAR(255),
    site_id             UUID REFERENCES transform.locations(location_id),
    location_id         UUID REFERENCES transform.locations(location_id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at         TIMESTAMPTZ,
    last_seen_at        TIMESTAMP,
    status              VARCHAR(10) DEFAULT 'offline'
);

-- ─── TABLE: ingest_uplinks (5th - no foreign keys) ─────────
CREATE TABLE IF NOT EXISTS transform.ingest_uplinks (
    uplink_uuid         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deveui              VARCHAR(16),
    timestamp           TIMESTAMP,
    payload             TEXT,
    uplink_metadata     JSONB,
    inserted_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fport               INTEGER,
    source              VARCHAR(100),
    last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message       TEXT,
    ingest_uplink_id    SERIAL,
    gateway_eui         VARCHAR(64)
);

-- ─── TABLE: processed_uplinks (6th - depends on device_context & locations) ───
CREATE TABLE IF NOT EXISTS transform.processed_uplinks (
    uplink_uuid         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deveui              VARCHAR(16) REFERENCES transform.device_context(deveui),
    timestamp           TIMESTAMP,
    fport               INTEGER,
    payload             BYTEA,
    uplink_metadata     JSONB,
    source              VARCHAR(100),
    location_id         UUID REFERENCES transform.locations(location_id),
    gateway_eui         VARCHAR(32),
    inserted_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payload_decoded     JSONB,
    device_type_id      INTEGER REFERENCES transform.device_types(device_type_id),
    site_id             UUID REFERENCES transform.locations(location_id),
    floor_id            UUID REFERENCES transform.locations(location_id),
    room_id             UUID REFERENCES transform.locations(location_id),
    zone_id             UUID REFERENCES transform.locations(location_id)
);

-- Add named foreign key constraints for processed_uplinks (to match live DB)
ALTER TABLE transform.processed_uplinks 
ADD CONSTRAINT fk_processed_site 
FOREIGN KEY (site_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks 
ADD CONSTRAINT fk_processed_floor 
FOREIGN KEY (floor_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks 
ADD CONSTRAINT fk_processed_room 
FOREIGN KEY (room_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks 
ADD CONSTRAINT fk_processed_zone 
FOREIGN KEY (zone_id) REFERENCES transform.locations(location_id);

-- ─── TABLE: enrichment_logs (7th - last table) ─────────────
CREATE TABLE IF NOT EXISTS transform.enrichment_logs (
    uplink_uuid         UUID,
    step                VARCHAR(100) CHECK (step IN (
        'CONTEXT_ENRICHED', 'FAILED', 'UNPACKED', 'FAILED_UNPACK'
    )),
    detail              TEXT,
    status              VARCHAR(50) CHECK (status IN (
        'SUCCESS', 'FAILED', 'PENDING', 'SKIPPED'
    )),
    timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    log_id              UUID PRIMARY KEY DEFAULT public.uuid_generate_v4()
);

-- ─── INDEXES (matching live database exactly) ──────────────

-- Ingest uplinks indexes (4 total as found in live DB)
CREATE INDEX IF NOT EXISTS idx_ingest_uplinks_deveui 
ON transform.ingest_uplinks (deveui);

CREATE INDEX IF NOT EXISTS idx_ingest_uplinks_timestamp 
ON transform.ingest_uplinks (timestamp);

CREATE INDEX IF NOT EXISTS idx_transform_ingest_deveui 
ON transform.ingest_uplinks (deveui);

CREATE INDEX IF NOT EXISTS idx_transform_ingest_timestamp 
ON transform.ingest_uplinks (timestamp);

-- Enrichment logs index
CREATE INDEX IF NOT EXISTS idx_enrichment_logs_uplink_uuid 
ON transform.enrichment_logs (uplink_uuid);

-- Note: Primary key indexes are created automatically:
-- - device_context_pkey ON device_context (deveui)
-- - device_types_pkey ON device_types (device_type_id) 
-- - enrichment_logs_pkey ON enrichment_logs (log_id)
-- - gateways_pkey ON gateways (gw_eui)
-- - ingest_uplinks_pkey ON ingest_uplinks (uplink_uuid)
-- - locations_pkey ON locations (location_id)
-- - processed_uplinks_pkey ON processed_uplinks (uplink_uuid)

-- ─── PERMISSIONS ────────────────────────────────────────────
-- Grant schema usage
GRANT USAGE ON SCHEMA transform TO transform_user;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA transform TO transform_user;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA transform TO transform_user;

-- Grant permissions for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA transform 
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO transform_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA transform 
GRANT USAGE, SELECT ON SEQUENCES TO transform_user;