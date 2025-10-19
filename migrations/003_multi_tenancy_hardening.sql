-- Smart Parking v5.3 - Multi-Tenancy Hardening & Improvements
-- Adds API key scopes, hardens triggers, and improves data integrity
-- Date: 2025-10-19
-- Run after: 002_multi_tenancy_rbac.sql

-- ============================================================
-- API Key Scopes for Least-Privilege Access
-- ============================================================

-- Add scopes column to api_keys
ALTER TABLE api_keys
  ADD COLUMN IF NOT EXISTS scopes text[] NOT NULL DEFAULT ARRAY['spaces:read', 'devices:read'];

-- Create index for scope lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_scopes ON api_keys USING GIN(scopes);

-- Update existing keys to have full access (backward compatibility)
UPDATE api_keys
SET scopes = ARRAY[
    'spaces:read', 'spaces:write',
    'devices:read', 'devices:write',
    'reservations:read', 'reservations:write',
    'webhook:ingest'
]
WHERE scopes = ARRAY['spaces:read', 'devices:read'];

COMMENT ON COLUMN api_keys.scopes IS 'API key scopes for least-privilege access. Common scopes: spaces:read, spaces:write, devices:read, devices:write, reservations:read, reservations:write, webhook:ingest, telemetry:read';

-- ============================================================
-- Harden Tenant Sync Trigger
-- ============================================================

-- Drop old trigger function
DROP TRIGGER IF EXISTS spaces_sync_tenant_id ON spaces;
DROP FUNCTION IF EXISTS sync_space_tenant_id();

-- Create hardened trigger function with validation
CREATE OR REPLACE FUNCTION spaces_sync_tenant_id()
RETURNS TRIGGER AS $$
DECLARE
    site_tenant_id UUID;
BEGIN
    -- Skip validation if site_id is NULL (will fail constraint anyway)
    IF NEW.site_id IS NULL THEN
        RAISE EXCEPTION 'site_id cannot be NULL';
    END IF;

    -- Get tenant_id from site
    SELECT tenant_id INTO site_tenant_id
    FROM sites
    WHERE id = NEW.site_id AND is_active = true;

    -- Site must exist
    IF site_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Site % not found or inactive', NEW.site_id;
    END IF;

    -- Enforce consistency: if tenant_id is already set, it must match site's tenant
    IF NEW.tenant_id IS NOT NULL AND NEW.tenant_id <> site_tenant_id THEN
        RAISE EXCEPTION 'Tenant mismatch: space.tenant_id=%, site.tenant_id=%', NEW.tenant_id, site_tenant_id;
    END IF;

    -- Sync tenant_id from site
    NEW.tenant_id := site_tenant_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
CREATE TRIGGER trg_spaces_sync_tenant_id
    BEFORE INSERT OR UPDATE OF site_id, tenant_id ON spaces
    FOR EACH ROW
    EXECUTE FUNCTION spaces_sync_tenant_id();

COMMENT ON FUNCTION spaces_sync_tenant_id() IS 'Hardened trigger to sync and validate tenant_id from site_id with mismatch detection';

-- ============================================================
-- Composite Unique Index for Space Codes
-- ============================================================

-- Ensure space codes are unique within tenant+site (not globally)
-- This allows different tenants to use the same space codes

-- Drop old global unique constraint if it exists
DROP INDEX IF EXISTS unique_space_code;
ALTER TABLE spaces DROP CONSTRAINT IF EXISTS unique_space_code;

-- Create composite unique index (tenant + site + code)
CREATE UNIQUE INDEX IF NOT EXISTS unique_tenant_site_space_code
    ON spaces(tenant_id, site_id, code)
    WHERE deleted_at IS NULL;

COMMENT ON INDEX unique_tenant_site_space_code IS 'Ensures space codes are unique within tenant+site, but allows reuse across tenants';

-- ============================================================
-- Tenanted Spaces View
-- ============================================================

-- Create view that joins spaces with sites and tenants
-- Reduces app-side mistakes and simplifies queries
CREATE OR REPLACE VIEW v_spaces AS
SELECT
    s.id,
    s.name,
    s.code,
    s.building,
    s.floor,
    s.zone,
    s.state,
    s.sensor_eui,
    s.display_eui,
    s.gps_latitude,
    s.gps_longitude,
    s.metadata,
    s.created_at,
    s.updated_at,
    s.deleted_at,
    -- Site info
    s.site_id,
    si.name AS site_name,
    si.timezone AS site_timezone,
    -- Tenant info
    s.tenant_id,
    t.name AS tenant_name,
    t.slug AS tenant_slug,
    t.is_active AS tenant_active
FROM spaces s
INNER JOIN sites si ON si.id = s.site_id
INNER JOIN tenants t ON t.id = s.tenant_id
WHERE s.deleted_at IS NULL;

COMMENT ON VIEW v_spaces IS 'Spaces with site and tenant info pre-joined for convenience and safety';

-- Grant select on view
GRANT SELECT ON v_spaces TO parking;

-- ============================================================
-- Enhanced Tenant Summary View
-- ============================================================

-- Drop and recreate tenant_summary with API key scopes info
DROP VIEW IF EXISTS tenant_summary;

CREATE VIEW tenant_summary AS
SELECT
    t.id,
    t.name,
    t.slug,
    t.is_active,
    t.created_at,
    COUNT(DISTINCT s.id) as site_count,
    COUNT(DISTINCT um.user_id) as user_count,
    COUNT(DISTINCT ak.id) as api_key_count,
    COUNT(DISTINCT sp.id) as space_count,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.state = 'FREE') as free_spaces,
    COUNT(DISTINCT sp.id) FILTER (WHERE sp.state = 'OCCUPIED') as occupied_spaces
FROM tenants t
LEFT JOIN sites s ON t.id = s.tenant_id AND s.is_active = true
LEFT JOIN user_memberships um ON t.id = um.tenant_id AND um.is_active = true
LEFT JOIN api_keys ak ON t.id = ak.tenant_id AND ak.is_active = true
LEFT JOIN spaces sp ON t.id = sp.tenant_id AND sp.deleted_at IS NULL
WHERE t.is_active = true
GROUP BY t.id, t.name, t.slug, t.is_active, t.created_at;

COMMENT ON VIEW tenant_summary IS 'Enhanced tenant statistics including space state counts';

-- ============================================================
-- Verification Queries
-- ============================================================

-- Query to verify migration success
-- Expected output: t|t|t
DO $$
DECLARE
    has_scopes BOOLEAN;
    has_trigger BOOLEAN;
    has_unique_idx BOOLEAN;
    has_view BOOLEAN;
BEGIN
    -- Check scopes column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'scopes'
    ) INTO has_scopes;

    -- Check trigger exists
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_spaces_sync_tenant_id'
    ) INTO has_trigger;

    -- Check unique index exists
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'unique_tenant_site_space_code'
    ) INTO has_unique_idx;

    -- Check view exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.views
        WHERE table_name = 'v_spaces'
    ) INTO has_view;

    -- Log results
    RAISE NOTICE 'Migration 003 verification:';
    RAISE NOTICE '  API key scopes: %', has_scopes;
    RAISE NOTICE '  Hardened trigger: %', has_trigger;
    RAISE NOTICE '  Unique index: %', has_unique_idx;
    RAISE NOTICE '  Spaces view: %', has_view;

    IF NOT (has_scopes AND has_trigger AND has_unique_idx AND has_view) THEN
        RAISE EXCEPTION 'Migration 003 verification failed';
    END IF;
END $$;

-- ============================================================
-- Sample Scope Configurations
-- ============================================================

-- Examples of how to set scopes for different use cases:

-- Webhook ingestion only (ChirpStack)
-- UPDATE api_keys SET scopes = ARRAY['webhook:ingest'] WHERE key_name = 'ChirpStack Webhook';

-- Read-only telemetry access
-- UPDATE api_keys SET scopes = ARRAY['spaces:read', 'devices:read', 'telemetry:read'] WHERE key_name = 'Analytics Dashboard';

-- Reservation system
-- UPDATE api_keys SET scopes = ARRAY['spaces:read', 'reservations:read', 'reservations:write'] WHERE key_name = 'Booking App';

-- Full admin access
-- UPDATE api_keys SET scopes = ARRAY['spaces:read', 'spaces:write', 'devices:read', 'devices:write', 'reservations:read', 'reservations:write', 'webhook:ingest', 'telemetry:read'] WHERE key_name = 'Admin Key';

-- ============================================================
-- Rollback Instructions
-- ============================================================

-- To rollback this migration:
/*
DROP VIEW IF EXISTS v_spaces;
DROP VIEW IF EXISTS tenant_summary;
DROP TRIGGER IF EXISTS trg_spaces_sync_tenant_id ON spaces;
DROP FUNCTION IF EXISTS spaces_sync_tenant_id();
DROP INDEX IF EXISTS unique_tenant_site_space_code;
DROP INDEX IF EXISTS idx_api_keys_scopes;
ALTER TABLE api_keys DROP COLUMN IF EXISTS scopes;

-- Recreate old tenant_summary view (see 002_multi_tenancy_rbac.sql)
*/

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking;

-- Migration complete
SELECT 'Migration 003 completed successfully!' AS status;
