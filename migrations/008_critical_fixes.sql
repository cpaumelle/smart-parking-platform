-- Smart Parking v5.3 - Critical Database Fixes
-- Implements fixes from docs/20251021_fixes.md
-- Date: 2025-10-21
-- Run after: 007_audit_log.sql

-- ============================================================
-- A) CRITICAL FIXES
-- ============================================================

-- ==========================================================
-- 1. Fix email uniqueness (case-insensitive)
-- ==========================================================
-- Drop table-level UNIQUE constraint if present
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;

-- Enforce case-insensitive uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_ci ON users (lower(email));

COMMENT ON INDEX uq_users_email_ci IS
  'Ensures email uniqueness in case-insensitive manner (prevents user@example.com and USER@example.com)';


-- ==========================================================
-- 2. Unify actuation column naming (display_deveui -> display_eui)
-- ==========================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'actuations' AND column_name = 'display_deveui'
    ) THEN
        ALTER TABLE actuations RENAME COLUMN display_deveui TO display_eui;
    END IF;
END $$;

COMMENT ON COLUMN actuations.display_eui IS
  'Device EUI of the display that received the downlink (standardized naming)';


-- ==========================================================
-- 3. Display EUI uniqueness in spaces (mirror sensor_eui pattern)
-- ==========================================================
CREATE UNIQUE INDEX IF NOT EXISTS uq_spaces_display_eui
  ON spaces(display_eui)
  WHERE display_eui IS NOT NULL AND deleted_at IS NULL;

COMMENT ON INDEX uq_spaces_display_eui IS
  'Ensures one display can only be assigned to one active space (prevents conflicts)';


-- ==========================================================
-- 4. Reservation idempotency enforcement (per-tenant)
-- ==========================================================
CREATE UNIQUE INDEX IF NOT EXISTS uq_reservations_request_id
  ON reservations(tenant_id, request_id)
  WHERE request_id IS NOT NULL;

COMMENT ON INDEX uq_reservations_request_id IS
  'Enforces idempotent reservation creation - same request_id returns existing reservation (prevents double-booking on retry)';


-- ==========================================================
-- 5. Fix reservation status consistency in EXCLUDE constraint
-- ==========================================================
-- Ensure btree_gist extension is present (idempotent)
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Re-create EXCLUDE constraint with explicit status filter
-- Standard statuses: pending, confirmed, cancelled, expired
ALTER TABLE reservations DROP CONSTRAINT IF EXISTS uq_reservations_no_overlap;
ALTER TABLE reservations DROP CONSTRAINT IF EXISTS reservations_space_id_tstzrange_excl;

ALTER TABLE reservations
  ADD CONSTRAINT uq_reservations_no_overlap
  EXCLUDE USING gist (
    space_id WITH =,
    tstzrange(reserved_from, reserved_until, '[)') WITH &&
  )
  WHERE (status IN ('pending', 'confirmed'));

COMMENT ON CONSTRAINT uq_reservations_no_overlap ON reservations IS
  'Database-level overlap prevention - only active reservations (pending/confirmed) block new bookings';


-- ==========================================================
-- 6. Add fcnt + tenant_id to sensor_readings for dedup + RLS
-- ==========================================================
-- Add columns if not present
DO $$
BEGIN
    -- Add tenant_id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sensor_readings' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE sensor_readings ADD COLUMN tenant_id UUID;

        COMMENT ON COLUMN sensor_readings.tenant_id IS
          'Tenant ID (denormalized from space for RLS and fast querying)';
    END IF;

    -- Add fcnt column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sensor_readings' AND column_name = 'fcnt'
    ) THEN
        ALTER TABLE sensor_readings ADD COLUMN fcnt INTEGER;

        COMMENT ON COLUMN sensor_readings.fcnt IS
          'LoRaWAN frame counter - used for deduplication (prevents duplicate uplink processing)';
    END IF;
END $$;

-- Create trigger function to sync tenant_id from space
CREATE OR REPLACE FUNCTION sensor_readings_sync_tenant_id()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- Sync tenant_id from space when space_id is set
  IF NEW.space_id IS NOT NULL THEN
    SELECT s.tenant_id INTO NEW.tenant_id
    FROM spaces s
    WHERE s.id = NEW.space_id;
  END IF;
  RETURN NEW;
END$$;

-- Create trigger to auto-sync tenant_id
DROP TRIGGER IF EXISTS trg_sensor_readings_sync_tenant ON sensor_readings;
CREATE TRIGGER trg_sensor_readings_sync_tenant
  BEFORE INSERT OR UPDATE OF space_id
  ON sensor_readings
  FOR EACH ROW
  EXECUTE FUNCTION sensor_readings_sync_tenant_id();

-- De-duplication index on (tenant_id, device_eui, fcnt)
CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_device_fcnt
  ON sensor_readings(tenant_id, device_eui, fcnt)
  WHERE fcnt IS NOT NULL;

COMMENT ON INDEX uq_readings_device_fcnt IS
  'Prevents duplicate sensor readings from same device with same frame counter (idempotent webhook ingestion)';


-- ==========================================================
-- 7. EUI normalization and validation
-- ==========================================================
-- Function to enforce uppercase EUI formatting
CREATE OR REPLACE FUNCTION enforce_eui_upper()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- Normalize dev_eui to uppercase (for device tables)
  IF NEW.dev_eui IS NOT NULL THEN
    NEW.dev_eui := upper(NEW.dev_eui);
  END IF;

  -- Normalize sensor_eui and display_eui (for spaces table)
  IF TG_TABLE_NAME = 'spaces' THEN
    IF NEW.sensor_eui IS NOT NULL THEN
      NEW.sensor_eui := upper(NEW.sensor_eui);
    END IF;
    IF NEW.display_eui IS NOT NULL THEN
      NEW.display_eui := upper(NEW.display_eui);
    END IF;
  END IF;

  RETURN NEW;
END$$;

-- Apply triggers to device registries
DROP TRIGGER IF EXISTS trg_sensor_eui_upper ON sensor_devices;
CREATE TRIGGER trg_sensor_eui_upper
  BEFORE INSERT OR UPDATE ON sensor_devices
  FOR EACH ROW
  EXECUTE FUNCTION enforce_eui_upper();

DROP TRIGGER IF EXISTS trg_display_eui_upper ON display_devices;
CREATE TRIGGER trg_display_eui_upper
  BEFORE INSERT OR UPDATE ON display_devices
  FOR EACH ROW
  EXECUTE FUNCTION enforce_eui_upper();

DROP TRIGGER IF EXISTS trg_spaces_eui_upper ON spaces;
CREATE TRIGGER trg_spaces_eui_upper
  BEFORE INSERT OR UPDATE ON spaces
  FOR EACH ROW
  EXECUTE FUNCTION enforce_eui_upper();

-- CHECK constraints for hex format validation (16 hex characters)
ALTER TABLE sensor_devices DROP CONSTRAINT IF EXISTS chk_sensor_dev_eui_hex;
ALTER TABLE sensor_devices
  ADD CONSTRAINT chk_sensor_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE display_devices DROP CONSTRAINT IF EXISTS chk_display_dev_eui_hex;
ALTER TABLE display_devices
  ADD CONSTRAINT chk_display_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE spaces DROP CONSTRAINT IF EXISTS chk_spaces_eui_hex;
ALTER TABLE spaces
  ADD CONSTRAINT chk_spaces_eui_hex
  CHECK (
    (sensor_eui IS NULL OR sensor_eui ~ '^[0-9A-F]{16}$') AND
    (display_eui IS NULL OR display_eui ~ '^[0-9A-F]{16}$')
  );

COMMENT ON CONSTRAINT chk_sensor_dev_eui_hex ON sensor_devices IS
  'Ensures dev_eui is exactly 16 uppercase hex characters (LoRaWAN standard format)';

COMMENT ON CONSTRAINT chk_display_dev_eui_hex ON display_devices IS
  'Ensures dev_eui is exactly 16 uppercase hex characters (LoRaWAN standard format)';

COMMENT ON CONSTRAINT chk_spaces_eui_hex ON spaces IS
  'Ensures sensor_eui and display_eui are 16 uppercase hex characters when present';


-- ==========================================================
-- 8. Fix orphan_devices table vs view naming collision
-- ==========================================================
-- Rename the view to v_orphan_devices (table name remains orphan_devices)
DROP VIEW IF EXISTS orphan_devices CASCADE;

-- Recreate as v_orphan_devices
CREATE OR REPLACE VIEW v_orphan_devices AS
SELECT
    sd.id,
    sd.dev_eui,
    sd.device_model,
    sd.status,
    sd.type_code,
    dt.name AS device_type_name,
    sd.first_seen,
    sd.last_seen,
    sd.metadata,
    sd.created_at,
    'sensor' AS device_category
FROM sensor_devices sd
LEFT JOIN device_types dt ON sd.type_code = dt.type_code
WHERE sd.status = 'orphan'

UNION ALL

SELECT
    dd.id,
    dd.dev_eui,
    dd.device_model,
    dd.status,
    dd.type_code,
    dt.name AS device_type_name,
    dd.first_seen,
    dd.last_seen,
    dd.metadata,
    dd.created_at,
    'display' AS device_category
FROM display_devices dd
LEFT JOIN device_types dt ON dd.type_code = dt.type_code
WHERE dd.status = 'orphan';

COMMENT ON VIEW v_orphan_devices IS
  'View of all orphan devices (sensors + displays) awaiting assignment to spaces';


-- ==========================================================
-- 9. Row-Level Security (RLS) Setup
-- ==========================================================
-- Initialize app.current_tenant setting (for RLS policies)
DO $$
BEGIN
  PERFORM set_config('app.current_tenant', '00000000-0000-0000-0000-000000000000', true);
EXCEPTION WHEN OTHERS THEN
  -- Ignore, just ensures the setting exists
  NULL;
END$$;

-- Enable RLS on tenant-scoped tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;

ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites FORCE ROW LEVEL SECURITY;

ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces FORCE ROW LEVEL SECURITY;

ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations FORCE ROW LEVEL SECURITY;

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;

ALTER TABLE webhook_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_secrets FORCE ROW LEVEL SECURITY;

ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings FORCE ROW LEVEL SECURITY;

ALTER TABLE display_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_policies FORCE ROW LEVEL SECURITY;

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

-- Create RLS policies for tenant isolation
-- Pattern: USING and WITH CHECK both enforce tenant_id match

-- Tenants: users can only see their own tenant
DROP POLICY IF EXISTS p_tenants_isolation ON tenants;
CREATE POLICY p_tenants_isolation ON tenants
  USING (id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (id = current_setting('app.current_tenant', true)::uuid);

-- Sites: tenant-scoped
DROP POLICY IF EXISTS p_sites_tenant ON sites;
CREATE POLICY p_sites_tenant ON sites
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Spaces: tenant-scoped
DROP POLICY IF EXISTS p_spaces_tenant ON spaces;
CREATE POLICY p_spaces_tenant ON spaces
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Reservations: tenant-scoped
DROP POLICY IF EXISTS p_reservations_tenant ON reservations;
CREATE POLICY p_reservations_tenant ON reservations
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- API Keys: tenant-scoped
DROP POLICY IF EXISTS p_api_keys_tenant ON api_keys;
CREATE POLICY p_api_keys_tenant ON api_keys
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Webhook Secrets: tenant-scoped
DROP POLICY IF EXISTS p_webhook_secrets_tenant ON webhook_secrets;
CREATE POLICY p_webhook_secrets_tenant ON webhook_secrets
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Sensor Readings: tenant-scoped (now has tenant_id)
DROP POLICY IF EXISTS p_sensor_readings_tenant ON sensor_readings;
CREATE POLICY p_sensor_readings_tenant ON sensor_readings
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Display Policies: tenant-scoped
DROP POLICY IF EXISTS p_display_policies_tenant ON display_policies;
CREATE POLICY p_display_policies_tenant ON display_policies
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Audit Log: tenant-scoped
DROP POLICY IF EXISTS p_audit_log_tenant ON audit_log;
CREATE POLICY p_audit_log_tenant ON audit_log
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

COMMENT ON POLICY p_tenants_isolation ON tenants IS
  'RLS: Users can only access their own tenant data';

COMMENT ON POLICY p_spaces_tenant ON spaces IS
  'RLS: Spaces are strictly isolated by tenant_id using app.current_tenant setting';


-- ==========================================================
-- 10. Secure materialized view v_spaces
-- ==========================================================
-- Revoke public access to prevent cross-tenant leakage
REVOKE ALL ON MATERIALIZED VIEW v_spaces FROM PUBLIC;

-- Grant only to specific backend role (adjust role name as needed)
-- GRANT SELECT ON MATERIALIZED VIEW v_spaces TO parking_api_backend;

COMMENT ON MATERIALIZED VIEW v_spaces IS
  'Pre-joined tenant/site data - ACCESS RESTRICTED: Backend must filter by app.current_tenant to prevent cross-tenant data leakage';


-- ==========================================================
-- 11. Extension cleanup (use pgcrypto, not uuid-ossp)
-- ==========================================================
-- Ensure pgcrypto is present (for gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Drop uuid-ossp if present and unused
-- DROP EXTENSION IF EXISTS "uuid-ossp";


-- ============================================================
-- B) STRONG IMPROVEMENTS (Future-Proofing)
-- ============================================================

-- ==========================================================
-- Add tenant_id to operational tables for fast RLS
-- ==========================================================
-- state_changes: add tenant_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'state_changes' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE state_changes ADD COLUMN tenant_id UUID;

        COMMENT ON COLUMN state_changes.tenant_id IS
          'Tenant ID (denormalized for RLS performance)';
    END IF;
END $$;

-- actuations: add tenant_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'actuations' AND column_name = 'tenant_id'
    ) THEN
        ALTER TABLE actuations ADD COLUMN tenant_id UUID;

        COMMENT ON COLUMN actuations.tenant_id IS
          'Tenant ID (denormalized for RLS performance)';
    END IF;
END $$;

-- Trigger to sync tenant_id for state_changes
CREATE OR REPLACE FUNCTION state_changes_sync_tenant_id()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.space_id IS NOT NULL THEN
    SELECT s.tenant_id INTO NEW.tenant_id
    FROM spaces s
    WHERE s.id = NEW.space_id;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_state_changes_sync_tenant ON state_changes;
CREATE TRIGGER trg_state_changes_sync_tenant
  BEFORE INSERT OR UPDATE OF space_id
  ON state_changes
  FOR EACH ROW
  EXECUTE FUNCTION state_changes_sync_tenant_id();

-- Trigger to sync tenant_id for actuations
CREATE OR REPLACE FUNCTION actuations_sync_tenant_id()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.space_id IS NOT NULL THEN
    SELECT s.tenant_id INTO NEW.tenant_id
    FROM spaces s
    WHERE s.id = NEW.space_id;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_actuations_sync_tenant ON actuations;
CREATE TRIGGER trg_actuations_sync_tenant
  BEFORE INSERT OR UPDATE OF space_id
  ON actuations
  FOR EACH ROW
  EXECUTE FUNCTION actuations_sync_tenant_id();

-- Enable RLS on operational tables
ALTER TABLE state_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE state_changes FORCE ROW LEVEL SECURITY;

ALTER TABLE actuations ENABLE ROW LEVEL SECURITY;
ALTER TABLE actuations FORCE ROW LEVEL SECURITY;

-- Create RLS policies
DROP POLICY IF EXISTS p_state_changes_tenant ON state_changes;
CREATE POLICY p_state_changes_tenant ON state_changes
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

DROP POLICY IF EXISTS p_actuations_tenant ON actuations;
CREATE POLICY p_actuations_tenant ON actuations
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);


-- ============================================================
-- Verification & Summary
-- ============================================================

DO $$
DECLARE
    v_fixes_applied INTEGER := 0;
BEGIN
    RAISE NOTICE '=== Migration 008: Critical Fixes Complete ===';

    -- Verify critical fixes
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_users_email_ci') THEN
        RAISE NOTICE '✓ Email case-insensitive uniqueness enforced';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_spaces_display_eui') THEN
        RAISE NOTICE '✓ Display EUI uniqueness enforced';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_reservations_request_id') THEN
        RAISE NOTICE '✓ Reservation idempotency enforced';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_readings_device_fcnt') THEN
        RAISE NOTICE '✓ Sensor reading deduplication (fcnt) enforced';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_reservations_no_overlap') THEN
        RAISE NOTICE '✓ Reservation overlap prevention with status filter';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_orphan_devices') THEN
        RAISE NOTICE '✓ Orphan devices view renamed (table/view collision resolved)';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    -- Check RLS is enabled
    IF EXISTS (
        SELECT 1 FROM pg_tables
        WHERE tablename = 'spaces' AND rowsecurity = true
    ) THEN
        RAISE NOTICE '✓ Row-Level Security enabled on tenant tables';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    RAISE NOTICE '=== Applied % critical fixes ===', v_fixes_applied;
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Update application code to set app.current_tenant for each request';
    RAISE NOTICE '  2. Backfill tenant_id in sensor_readings, state_changes, actuations';
    RAISE NOTICE '  3. Review and adjust RLS policies for your security requirements';
    RAISE NOTICE '  4. Update views and queries to use v_orphan_devices (not orphan_devices)';
END $$;
