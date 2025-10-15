-- ════════════════════════════════════════════════════════════════════
-- Multi-Tenancy Migration Rollback Script
-- ════════════════════════════════════════════════════════════════════
-- Migration: 008
-- Purpose: Undo multi-tenancy changes (emergency rollback)
-- Date: 2025-10-15
--
-- WARNING: This script removes tenant_id columns and RLS policies
--          Only use if migration causes critical issues
--
-- Better option: Restore from backup
--   gunzip -c backup.sql.gz | psql -U parking_user parking_platform
--
-- ════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 1: DISABLE ROW-LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════

-- INGEST SCHEMA
ALTER TABLE ingest.raw_uplinks DISABLE ROW LEVEL SECURITY;

-- TRANSFORM SCHEMA
ALTER TABLE transform.device_types DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.locations DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.device_context DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.gateways DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.ingest_uplinks DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.processed_uplinks DISABLE ROW LEVEL SECURITY;
ALTER TABLE transform.enrichment_logs DISABLE ROW LEVEL SECURITY;

-- PARKING CONFIG SCHEMA
ALTER TABLE parking_config.sensor_registry DISABLE ROW LEVEL SECURITY;
ALTER TABLE parking_config.display_registry DISABLE ROW LEVEL SECURITY;

-- PARKING SPACES SCHEMA
ALTER TABLE parking_spaces.spaces DISABLE ROW LEVEL SECURITY;
ALTER TABLE parking_spaces.reservations DISABLE ROW LEVEL SECURITY;

-- PARKING OPERATIONS SCHEMA
ALTER TABLE parking_operations.actuations DISABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 2: DROP RLS POLICIES
-- ═══════════════════════════════════════════════════════════════════

-- INGEST SCHEMA
DROP POLICY IF EXISTS tenant_isolation_policy ON ingest.raw_uplinks;

-- TRANSFORM SCHEMA
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.device_types;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.locations;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.device_context;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.gateways;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.ingest_uplinks;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.processed_uplinks;
DROP POLICY IF EXISTS tenant_isolation_policy ON transform.enrichment_logs;

-- PARKING CONFIG SCHEMA
DROP POLICY IF EXISTS tenant_isolation_policy ON parking_config.sensor_registry;
DROP POLICY IF EXISTS tenant_isolation_policy ON parking_config.display_registry;

-- PARKING SPACES SCHEMA
DROP POLICY IF EXISTS tenant_isolation_policy ON parking_spaces.spaces;
DROP POLICY IF EXISTS tenant_isolation_policy ON parking_spaces.reservations;

-- PARKING OPERATIONS SCHEMA
DROP POLICY IF EXISTS tenant_isolation_policy ON parking_operations.actuations;

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 3: DROP INDEXES
-- ═══════════════════════════════════════════════════════════════════

-- INGEST SCHEMA
DROP INDEX IF EXISTS ingest.idx_raw_uplinks_tenant;
DROP INDEX IF EXISTS ingest.idx_raw_uplinks_tenant_deveui;

-- TRANSFORM SCHEMA
DROP INDEX IF EXISTS transform.idx_device_types_tenant;
DROP INDEX IF EXISTS transform.idx_locations_tenant;
DROP INDEX IF EXISTS transform.idx_device_context_tenant;
DROP INDEX IF EXISTS transform.idx_gateways_tenant;
DROP INDEX IF EXISTS transform.idx_ingest_uplinks_tenant;
DROP INDEX IF EXISTS transform.idx_processed_uplinks_tenant;
DROP INDEX IF EXISTS transform.idx_enrichment_logs_tenant;

-- PARKING CONFIG SCHEMA
DROP INDEX IF EXISTS parking_config.idx_sensor_registry_tenant;
DROP INDEX IF EXISTS parking_config.idx_display_registry_tenant;

-- PARKING SPACES SCHEMA
DROP INDEX IF EXISTS parking_spaces.idx_spaces_tenant;
DROP INDEX IF EXISTS parking_spaces.idx_reservations_tenant;

-- PARKING OPERATIONS SCHEMA
DROP INDEX IF EXISTS parking_operations.idx_actuations_tenant;

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 4: DROP tenant_id COLUMNS
-- ═══════════════════════════════════════════════════════════════════

-- INGEST SCHEMA
ALTER TABLE ingest.raw_uplinks DROP COLUMN IF EXISTS tenant_id;

-- TRANSFORM SCHEMA
ALTER TABLE transform.device_types DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.locations DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.device_context DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.gateways DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.ingest_uplinks DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.processed_uplinks DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE transform.enrichment_logs DROP COLUMN IF EXISTS tenant_id;

-- PARKING CONFIG SCHEMA
ALTER TABLE parking_config.sensor_registry DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE parking_config.display_registry DROP COLUMN IF EXISTS tenant_id;

-- PARKING SPACES SCHEMA
ALTER TABLE parking_spaces.spaces DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE parking_spaces.reservations DROP COLUMN IF EXISTS tenant_id;

-- PARKING OPERATIONS SCHEMA
ALTER TABLE parking_operations.actuations DROP COLUMN IF EXISTS tenant_id;

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 5: DROP CORE TABLES
-- ═══════════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS core.api_keys;
DROP TABLE IF EXISTS core.tenants;

-- ═══════════════════════════════════════════════════════════════════
-- SECTION 6: DROP CORE SCHEMA
-- ═══════════════════════════════════════════════════════════════════

DROP SCHEMA IF EXISTS core;

-- ═══════════════════════════════════════════════════════════════════
-- ROLLBACK COMPLETE
-- ═══════════════════════════════════════════════════════════════════

SELECT '✅ Multi-tenancy migration rolled back successfully' as result;

-- Verify RLS is disabled
SELECT 
    'RLS Status Check' as check_type,
    COUNT(*) as tables_with_rls
FROM pg_tables 
WHERE rowsecurity = true;

-- ═══════════════════════════════════════════════════════════════════
