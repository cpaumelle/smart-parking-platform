-- ============================================================================
-- Migration 012: Performance Optimization Indexes
-- ============================================================================
-- Description: Add indexes for high-traffic query patterns
-- Author: Smart Parking Platform Team
-- Created: 2025-10-22
-- Version: v5.8.0
--
-- Impact: Read performance improvement, minimal write overhead
-- Estimated Time: 5-10 minutes (uses CONCURRENTLY to avoid blocking)
-- Note: CONCURRENTLY cannot be used inside a transaction block
-- ============================================================================

-- ============================================================================
-- 1. ACTUATIONS TABLE - Critical for display update queries
-- ============================================================================

-- Most recent actuations per tenant/space (dashboard queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_created_at
  ON actuations(created_at DESC);

-- Tenant-specific actuation history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_tenant_space
  ON actuations(tenant_id, space_id, created_at DESC)
  WHERE tenant_id IS NOT NULL;

-- Display device actuation lookup (downlink audit trail)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_display_eui
  ON actuations(display_eui, created_at DESC)
  WHERE downlink_sent = TRUE AND display_eui IS NOT NULL;

-- Trigger type analysis (sensor_uplink vs system_cleanup vs manual)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_trigger_type
  ON actuations(trigger_type, created_at DESC);

-- ============================================================================
-- 2. RESERVATIONS TABLE - Availability and overlap queries
-- ============================================================================

-- Active reservations per tenant (most common query)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reservations_tenant_status_time
  ON reservations(tenant_id, status, start_time, end_time)
  WHERE status IN ('pending', 'confirmed');

-- Overlap detection for availability checks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reservations_space_overlap
  ON reservations(space_id, start_time, end_time)
  WHERE status IN ('pending', 'confirmed');

-- User reservation history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reservations_user_email
  ON reservations(user_email, start_time DESC)
  WHERE user_email IS NOT NULL;

-- ============================================================================
-- 3. API KEYS TABLE - Authentication queries (partial index)
-- ============================================================================

-- Active API key lookup (only index non-revoked keys)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_active
  ON api_keys(tenant_id, key_hash)
  WHERE is_active = TRUE;

-- API key usage tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_last_used
  ON api_keys(last_used_at DESC)
  WHERE is_active = TRUE;

-- ============================================================================
-- 4. SENSOR_READINGS TABLE - Telemetry queries
-- ============================================================================

-- Latest readings per device
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sensor_readings_device_time
  ON sensor_readings(device_eui, timestamp DESC);

-- Space-specific sensor history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sensor_readings_space_time
  ON sensor_readings(space_id, timestamp DESC)
  WHERE space_id IS NOT NULL;

-- Tenant telemetry dashboard
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sensor_readings_tenant_time
  ON sensor_readings(tenant_id, timestamp DESC)
  WHERE tenant_id IS NOT NULL;

-- ============================================================================
-- 5. SPACES TABLE - Common lookup patterns
-- ============================================================================

-- Tenant's spaces grouped by site
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_tenant_site
  ON spaces(tenant_id, site_id, code)
  WHERE deleted_at IS NULL;

-- Sensor EUI lookup (reverse lookup from uplink)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_sensor_eui
  ON spaces(sensor_eui)
  WHERE sensor_eui IS NOT NULL AND deleted_at IS NULL;

-- Display EUI lookup (for actuation)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_display_eui
  ON spaces(display_eui)
  WHERE display_eui IS NOT NULL AND deleted_at IS NULL;

-- State-based filtering (e.g., show all occupied spaces)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_state
  ON spaces(tenant_id, state, code)
  WHERE deleted_at IS NULL;

-- ============================================================================
-- 6. STATE_CHANGES TABLE - Audit and analytics
-- ============================================================================

-- State change history per space
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_state_changes_space_time
  ON state_changes(space_id, timestamp DESC);

-- Tenant state change analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_state_changes_tenant_time
  ON state_changes(tenant_id, timestamp DESC)
  WHERE tenant_id IS NOT NULL;

-- ============================================================================
-- 7. SITES TABLE - Tenant site management
-- ============================================================================

-- Active sites per tenant
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sites_tenant_active
  ON sites(tenant_id, name)
  WHERE is_active = TRUE;

-- ============================================================================
-- 8. USER_MEMBERSHIPS TABLE - RBAC lookups
-- ============================================================================

-- User's tenant memberships
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memberships_user_active
  ON user_memberships(user_id, tenant_id)
  WHERE is_active = TRUE;

-- Tenant's member list
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_memberships_tenant_active
  ON user_memberships(tenant_id, role, created_at DESC)
  WHERE is_active = TRUE;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Run these queries to verify index usage:

-- Example 1: Recent actuations for a space
-- EXPLAIN ANALYZE
-- SELECT * FROM actuations
-- WHERE tenant_id = 'xxx' AND space_id = 'yyy'
-- ORDER BY created_at DESC LIMIT 10;
-- Expected: Index Scan using idx_actuations_tenant_space

-- Example 2: Check reservation availability
-- EXPLAIN ANALYZE
-- SELECT * FROM reservations
-- WHERE space_id = 'xxx'
--   AND status IN ('pending', 'confirmed')
--   AND (
--     (start_time <= '2025-10-22 10:00' AND end_time > '2025-10-22 10:00')
--     OR (start_time < '2025-10-22 12:00' AND end_time >= '2025-10-22 12:00')
--   );
-- Expected: Index Scan using idx_reservations_space_overlap

-- Example 3: Active API key lookup
-- EXPLAIN ANALYZE
-- SELECT * FROM api_keys
-- WHERE tenant_id = 'xxx' AND key_hash = 'hash' AND is_active = TRUE;
-- Expected: Index Scan using idx_api_keys_active

-- ============================================================================
-- POST-MIGRATION STATISTICS UPDATE
-- ============================================================================

-- Update table statistics for query planner
ANALYZE actuations;
ANALYZE reservations;
ANALYZE api_keys;
ANALYZE sensor_readings;
ANALYZE spaces;
ANALYZE state_changes;
ANALYZE sites;
ANALYZE user_memberships;

-- ============================================================================
-- INDEX SIZE MONITORING
-- ============================================================================

-- Check index sizes:
-- SELECT
--     schemaname,
--     tablename,
--     indexname,
--     pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
-- FROM pg_stat_user_indexes
-- WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
-- ORDER BY pg_relation_size(indexrelid) DESC;
