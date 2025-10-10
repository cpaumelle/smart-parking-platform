-- ════════════════════════════════════════════════════════════════════
-- Smart Parking Platform - IoT Services Database Schema
-- ════════════════════════════════════════════════════════════════════
-- Source: sensemy-iot-platform v4.0.2
-- Adapted for: Smart Parking unified PostgreSQL architecture
-- Database: parking_platform
-- Date: 2025-10-07
-- User: parking_user (unified database user)
--
-- Changes from original:
-- - Combined ingest + transform schemas into single database
-- - Changed user references: ingestuser → parking_user
-- - Changed user references: transform_user → parking_user
-- - Maintained original schema separation (ingest, transform)
-- ════════════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────────
-- EXTENSIONS
-- ───────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ═══════════════════════════════════════════════════════════════════
-- SCHEMA: ingest
-- Purpose: Raw LoRaWAN uplink storage from ChirpStack
-- ═══════════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS ingest;

-- ─── TABLE: ingest.raw_uplinks ────────────────────────────────────
-- Stores raw uplinks received from ChirpStack webhook
CREATE TABLE IF NOT EXISTS ingest.raw_uplinks (
    uplink_id           SERIAL PRIMARY KEY,
    deveui              TEXT NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fport               INTEGER,
    payload             TEXT,
    uplink_metadata     JSONB,
    source              TEXT NOT NULL DEFAULT 'chirpstack',
    processed           BOOLEAN DEFAULT FALSE,
    gateway_eui         VARCHAR(64)
);

-- Performance indexes (production verified)
CREATE INDEX IF NOT EXISTS idx_raw_uplinks_deveui
ON ingest.raw_uplinks (deveui);

CREATE INDEX IF NOT EXISTS idx_raw_uplinks_received_at
ON ingest.raw_uplinks (received_at);

CREATE INDEX IF NOT EXISTS idx_raw_uplinks_processed
ON ingest.raw_uplinks (processed);

-- Grant permissions to unified parking_user
GRANT USAGE ON SCHEMA ingest TO parking_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingest.raw_uplinks TO parking_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ingest TO parking_user;

-- ═══════════════════════════════════════════════════════════════════
-- SCHEMA: transform
-- Purpose: Data transformation, device context, and enrichment
-- ═══════════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS transform;

-- ─── TABLE: transform.device_types (1st - no dependencies) ────────
-- Sensor type definitions and payload decoders
CREATE TABLE IF NOT EXISTS transform.device_types (
    device_type_id      SERIAL PRIMARY KEY,
    device_type         VARCHAR(255) NOT NULL,
    description         TEXT,
    unpacker            VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at         TIMESTAMPTZ
);

-- ─── TABLE: transform.locations (2nd - self-referencing) ──────────
-- Hierarchical location structure: site > floor > room > zone
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

-- ─── TABLE: transform.device_context (3rd - depends on locations & device_types) ───
-- Device metadata, location assignments, and lifecycle tracking
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

-- Named foreign key constraints (matching production database)
ALTER TABLE transform.device_context
DROP CONSTRAINT IF EXISTS fk_device_context_site;
ALTER TABLE transform.device_context
ADD CONSTRAINT fk_device_context_site
FOREIGN KEY (site_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context
DROP CONSTRAINT IF EXISTS fk_device_context_floor;
ALTER TABLE transform.device_context
ADD CONSTRAINT fk_device_context_floor
FOREIGN KEY (floor_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context
DROP CONSTRAINT IF EXISTS fk_device_context_room;
ALTER TABLE transform.device_context
ADD CONSTRAINT fk_device_context_room
FOREIGN KEY (room_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.device_context
DROP CONSTRAINT IF EXISTS fk_device_context_zone;
ALTER TABLE transform.device_context
ADD CONSTRAINT fk_device_context_zone
FOREIGN KEY (zone_id) REFERENCES transform.locations(location_id);

-- ─── TABLE: transform.gateways (4th - depends on locations) ───────
-- LoRaWAN gateway registry and status tracking
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

-- ─── TABLE: transform.ingest_uplinks (5th - no foreign keys) ──────
-- Copy of raw uplinks from ingest schema for processing
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

-- ─── TABLE: transform.processed_uplinks (6th - depends on device_context & locations) ───
-- Decoded and enriched sensor data with full context
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

-- Named foreign key constraints (matching production database)
ALTER TABLE transform.processed_uplinks
DROP CONSTRAINT IF EXISTS fk_processed_site;
ALTER TABLE transform.processed_uplinks
ADD CONSTRAINT fk_processed_site
FOREIGN KEY (site_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks
DROP CONSTRAINT IF EXISTS fk_processed_floor;
ALTER TABLE transform.processed_uplinks
ADD CONSTRAINT fk_processed_floor
FOREIGN KEY (floor_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks
DROP CONSTRAINT IF EXISTS fk_processed_room;
ALTER TABLE transform.processed_uplinks
ADD CONSTRAINT fk_processed_room
FOREIGN KEY (room_id) REFERENCES transform.locations(location_id);

ALTER TABLE transform.processed_uplinks
DROP CONSTRAINT IF EXISTS fk_processed_zone;
ALTER TABLE transform.processed_uplinks
ADD CONSTRAINT fk_processed_zone
FOREIGN KEY (zone_id) REFERENCES transform.locations(location_id);

-- ─── TABLE: transform.enrichment_logs (7th - last table) ──────────
-- Processing logs for debugging and monitoring
CREATE TABLE IF NOT EXISTS transform.enrichment_logs (
    uplink_uuid         UUID,
    step                VARCHAR(100) CHECK (step IN (
        'ingestion_received', 'enrichment', 'context_enrichment', 'unpacking_init',
        'unpacking', 'analytics_forwarding', 'CONTEXT_ENRICHED', 'FAILED', 'UNPACKED', 'FAILED_UNPACK'
    )),
    detail              TEXT,
    status              VARCHAR(50) CHECK (status IN (
        'new', 'pending', 'success', 'error', 'fail', 'ready_for_unpacking',
        'SUCCESS', 'FAILED', 'PENDING', 'SKIPPED'
    )),
    timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    log_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4()
);

-- ───────────────────────────────────────────────────────────────────
-- INDEXES (matching production database exactly)
-- ───────────────────────────────────────────────────────────────────

-- Ingest uplinks indexes
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

-- ───────────────────────────────────────────────────────────────────
-- PERMISSIONS (unified parking_user)
-- ───────────────────────────────────────────────────────────────────

-- Grant schema usage
GRANT USAGE ON SCHEMA transform TO parking_user;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA transform TO parking_user;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA transform TO parking_user;

-- Grant permissions for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA transform
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA transform
GRANT USAGE, SELECT ON SEQUENCES TO parking_user;

-- ═══════════════════════════════════════════════════════════════════
-- SUMMARY
-- ═══════════════════════════════════════════════════════════════════
-- Schemas created: ingest, transform
-- Tables created: 8 total
--   - ingest.raw_uplinks
--   - transform.device_types
--   - transform.locations
--   - transform.device_context
--   - transform.gateways
--   - transform.ingest_uplinks
--   - transform.processed_uplinks
--   - transform.enrichment_logs
-- Indexes: 8 total (+ 7 automatic primary key indexes)
-- Foreign keys: 16 total
-- User: parking_user (full access to both schemas)
-- ═══════════════════════════════════════════════════════════════════
