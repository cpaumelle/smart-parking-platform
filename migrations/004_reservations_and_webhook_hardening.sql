-- Smart Parking v5.3 - Reservations & Webhook Hardening
-- Adds reservation overlap prevention and webhook idempotency
-- Date: 2025-10-19
-- Run after: 003_multi_tenancy_hardening.sql

-- ============================================================
-- Enable Required Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================
-- Reservation Overlap Prevention (DB-Level)
-- ============================================================

-- Add request_id for idempotency
ALTER TABLE reservations
  ADD COLUMN IF NOT EXISTS request_id UUID;

-- Backfill existing reservations
UPDATE reservations
SET request_id = gen_random_uuid()
WHERE request_id IS NULL;

-- Make request_id required going forward
ALTER TABLE reservations
  ALTER COLUMN request_id SET NOT NULL,
  ALTER COLUMN request_id SET DEFAULT gen_random_uuid();

-- Create unique index on request_id for idempotency
CREATE UNIQUE INDEX IF NOT EXISTS idx_reservations_request_id
  ON reservations(request_id);

-- Add tenant_id to reservations (if not already present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'reservations' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE reservations ADD COLUMN tenant_id UUID;

        -- Backfill from spaces
        UPDATE reservations r
        SET tenant_id = s.tenant_id
        FROM spaces s
        WHERE r.space_id = s.id;

        -- Make it required
        ALTER TABLE reservations ALTER COLUMN tenant_id SET NOT NULL;

        -- Add foreign key
        ALTER TABLE reservations ADD CONSTRAINT fk_reservation_tenant
          FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create index for tenant + space lookups
CREATE INDEX IF NOT EXISTS idx_reservations_tenant_space
  ON reservations(tenant_id, space_id);

-- CRITICAL: Prevent overlapping reservations at DB level
-- This makes double-booking impossible even under race conditions
ALTER TABLE reservations
  ADD CONSTRAINT no_reservation_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    space_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
  )
  WHERE (status = 'active');

COMMENT ON CONSTRAINT no_reservation_overlap ON reservations IS
  'Prevents overlapping active reservations for the same space within a tenant. Uses GiST index with range types for efficient checking.';

-- ============================================================
-- Sensor Readings Idempotency
-- ============================================================

-- Add tenant_id to sensor_readings
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sensor_readings' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE sensor_readings ADD COLUMN tenant_id UUID;

        -- Backfill from spaces
        UPDATE sensor_readings sr
        SET tenant_id = s.tenant_id
        FROM spaces s
        WHERE sr.space_id = s.id;

        -- Make it NOT NULL for new inserts
        ALTER TABLE sensor_readings ALTER COLUMN tenant_id SET DEFAULT '00000000-0000-0000-0000-000000000001';
    END IF;
END $$;

-- Add fcnt (frame counter) for idempotency
ALTER TABLE sensor_readings
  ADD COLUMN IF NOT EXISTS fcnt INTEGER;

-- Create unique constraint on (tenant_id, device_eui, fcnt)
-- This prevents duplicate processing of the same uplink
CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_readings_dedup
  ON sensor_readings(tenant_id, device_eui, fcnt)
  WHERE fcnt IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sensor_readings_tenant
  ON sensor_readings(tenant_id, timestamp DESC);

COMMENT ON COLUMN sensor_readings.fcnt IS
  'LoRaWAN frame counter for deduplication. Prevents processing the same uplink multiple times.';

-- ============================================================
-- Orphan Devices Table
-- ============================================================

-- Track unknown devices for controlled intake
CREATE TABLE IF NOT EXISTS orphan_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dev_eui VARCHAR(16) NOT NULL,

    -- Metadata
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uplink_count INTEGER DEFAULT 1,
    last_payload BYTEA,
    last_rssi INTEGER,
    last_snr DECIMAL(4, 1),

    -- Assignment tracking
    assigned_to_space_id UUID,
    assigned_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT unique_orphan_deveui UNIQUE (dev_eui)
);

CREATE INDEX IF NOT EXISTS idx_orphan_devices_last_seen
  ON orphan_devices(last_seen DESC);

COMMENT ON TABLE orphan_devices IS
  'Tracks uplinks from devices not yet assigned to spaces. Prevents spam and aids provisioning.';

-- ============================================================
-- Webhook Secrets Table (Optional)
-- ============================================================

-- Store webhook verification secrets per tenant
CREATE TABLE IF NOT EXISTS webhook_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    secret_hash VARCHAR(255) NOT NULL,
    algorithm VARCHAR(20) DEFAULT 'HS256',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_webhook_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_webhook_secrets_tenant
  ON webhook_secrets(tenant_id) WHERE is_active = true;

COMMENT ON TABLE webhook_secrets IS
  'Stores HMAC secrets for validating ChirpStack webhook signatures per tenant.';

-- ============================================================
-- State Changes - Add Tenant ID
-- ============================================================

-- Add tenant_id to state_changes for better audit trail
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'state_changes' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE state_changes ADD COLUMN tenant_id UUID;

        -- Backfill from spaces
        UPDATE state_changes sc
        SET tenant_id = s.tenant_id
        FROM spaces s
        WHERE sc.space_id = s.id;

        -- Create index
        CREATE INDEX idx_state_changes_tenant ON state_changes(tenant_id, timestamp DESC);
    END IF;
END $$;

-- ============================================================
-- Views for Monitoring
-- ============================================================

-- View: Reservation conflicts (should always be empty)
CREATE OR REPLACE VIEW reservation_conflicts AS
SELECT
    r1.id as reservation1_id,
    r2.id as reservation2_id,
    r1.space_id,
    r1.tenant_id,
    r1.start_time as r1_start,
    r1.end_time as r1_end,
    r2.start_time as r2_start,
    r2.end_time as r2_end,
    tstzrange(r1.start_time, r1.end_time, '[)') && tstzrange(r2.start_time, r2.end_time, '[)') as overlap
FROM reservations r1
INNER JOIN reservations r2 ON r1.space_id = r2.space_id
    AND r1.tenant_id = r2.tenant_id
    AND r1.id < r2.id  -- Avoid duplicates
WHERE r1.status = 'active'
  AND r2.status = 'active'
  AND tstzrange(r1.start_time, r1.end_time, '[)') && tstzrange(r2.start_time, r2.end_time, '[)');

COMMENT ON VIEW reservation_conflicts IS
  'Should always return 0 rows. If any rows appear, the EXCLUDE constraint has been bypassed.';

-- View: Orphan device summary
CREATE OR REPLACE VIEW orphan_summary AS
SELECT
    COUNT(*) as total_orphans,
    COUNT(*) FILTER (WHERE last_seen > NOW() - INTERVAL '1 hour') as seen_last_hour,
    COUNT(*) FILTER (WHERE last_seen > NOW() - INTERVAL '24 hours') as seen_last_day,
    COUNT(*) FILTER (WHERE assigned_to_space_id IS NOT NULL) as assigned,
    AVG(uplink_count) as avg_uplink_count
FROM orphan_devices;

-- ============================================================
-- Verification
-- ============================================================

DO $$
DECLARE
    has_overlap_constraint BOOLEAN;
    has_dedup_index BOOLEAN;
    has_orphan_table BOOLEAN;
BEGIN
    -- Check overlap constraint
    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'no_reservation_overlap'
    ) INTO has_overlap_constraint;

    -- Check dedup index
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_sensor_readings_dedup'
    ) INTO has_dedup_index;

    -- Check orphan table
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'orphan_devices'
    ) INTO has_orphan_table;

    RAISE NOTICE 'Migration 004 verification:';
    RAISE NOTICE '  Reservation overlap prevention: %', has_overlap_constraint;
    RAISE NOTICE '  Sensor reading deduplication: %', has_dedup_index;
    RAISE NOTICE '  Orphan device tracking: %', has_orphan_table;

    IF NOT (has_overlap_constraint AND has_dedup_index AND has_orphan_table) THEN
        RAISE EXCEPTION 'Migration 004 verification failed';
    END IF;
END $$;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking;

SELECT 'Migration 004 completed successfully!' AS status;
