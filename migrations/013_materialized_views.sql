-- Migration 013: Materialized Views for Analytics Performance
-- Provides pre-aggregated data for dashboard queries
-- Created: 2025-10-22

BEGIN;

-- ============================================================================
-- Daily Space Utilization Summary
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS space_utilization_daily AS
SELECT
    sc.tenant_id,
    sc.space_id,
    s.code as space_code,
    s.name as space_name,
    s.site_id,
    sites.name as site_name,
    DATE(sc.timestamp) as date,
    -- Occupancy metrics
    COUNT(*) FILTER (WHERE sc.new_state = 'OCCUPIED') as occupancy_count,
    COUNT(*) FILTER (WHERE sc.new_state = 'FREE') as vacancy_count,
    COUNT(DISTINCT sc.request_id) as total_state_changes,
    -- Duration calculation (average time in OCCUPIED state)
    AVG(
        EXTRACT(EPOCH FROM (
            LEAD(sc.timestamp) OVER (PARTITION BY sc.space_id ORDER BY sc.timestamp)
            - sc.timestamp
        ))
    ) FILTER (WHERE sc.new_state = 'OCCUPIED') as avg_occupancy_duration_seconds,
    -- First and last events of the day
    MIN(sc.timestamp) as first_event_time,
    MAX(sc.timestamp) as last_event_time
FROM state_changes sc
JOIN spaces s ON sc.space_id = s.id
LEFT JOIN sites ON s.site_id = sites.id
WHERE sc.timestamp >= CURRENT_DATE - INTERVAL '90 days'  -- Keep 90 days of history
GROUP BY sc.tenant_id, sc.space_id, s.code, s.name, s.site_id, sites.name, DATE(sc.timestamp);

-- Indexes for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_space_utilization_daily_unique
    ON space_utilization_daily(tenant_id, space_id, date);
CREATE INDEX IF NOT EXISTS idx_space_utilization_daily_tenant_date
    ON space_utilization_daily(tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_space_utilization_daily_site
    ON space_utilization_daily(site_id, date DESC);

COMMENT ON MATERIALIZED VIEW space_utilization_daily IS
'Daily aggregation of space occupancy metrics for analytics dashboards. Refreshed hourly.';

-- ============================================================================
-- Hourly API Usage Summary
-- ============================================================================

-- Note: This view assumes api_usage table exists (may need to create it first)
-- If api_usage table doesn't exist yet, this view creation will be skipped

DO $$
BEGIN
    -- Check if api_usage table exists
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'api_usage') THEN
        -- Create the materialized view
        CREATE MATERIALIZED VIEW IF NOT EXISTS api_usage_hourly AS
        SELECT
            tenant_id,
            DATE_TRUNC('hour', timestamp) as hour,
            endpoint,
            method,
            -- Request metrics
            COUNT(*) as request_count,
            COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 300) as success_count,
            COUNT(*) FILTER (WHERE status_code >= 400 AND status_code < 500) as client_error_count,
            COUNT(*) FILTER (WHERE status_code >= 500) as server_error_count,
            -- Performance metrics
            AVG(response_time_ms) as avg_response_time_ms,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_time_ms) as p50_response_time_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_time_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99_response_time_ms,
            MAX(response_time_ms) as max_response_time_ms
        FROM api_usage
        WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'  -- Keep 30 days of history
        GROUP BY tenant_id, DATE_TRUNC('hour', timestamp), endpoint, method;

        -- Indexes for fast lookups
        CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_hourly_unique
            ON api_usage_hourly(tenant_id, hour, endpoint, method);
        CREATE INDEX IF NOT EXISTS idx_api_usage_hourly_tenant_hour
            ON api_usage_hourly(tenant_id, hour DESC);

        COMMENT ON MATERIALIZED VIEW api_usage_hourly IS
        'Hourly aggregation of API usage metrics for monitoring dashboards. Refreshed hourly.';
    END IF;
END $$;

-- ============================================================================
-- Reservation Statistics by Site
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS reservation_stats_daily AS
SELECT
    r.tenant_id,
    s.site_id,
    sites.name as site_name,
    DATE(r.start_time) as date,
    -- Reservation counts by status
    COUNT(*) as total_reservations,
    COUNT(*) FILTER (WHERE r.status = 'confirmed') as confirmed_count,
    COUNT(*) FILTER (WHERE r.status = 'cancelled') as cancelled_count,
    COUNT(*) FILTER (WHERE r.status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE r.status = 'no_show') as no_show_count,
    -- Duration metrics
    AVG(EXTRACT(EPOCH FROM (r.end_time - r.start_time)) / 3600.0) as avg_duration_hours,
    -- Unique users
    COUNT(DISTINCT r.user_email) FILTER (WHERE r.user_email IS NOT NULL) as unique_users
FROM reservations r
JOIN spaces s ON r.space_id = s.id
LEFT JOIN sites ON s.site_id = sites.id
WHERE r.created_at >= CURRENT_DATE - INTERVAL '90 days'  -- Keep 90 days of history
GROUP BY r.tenant_id, s.site_id, sites.name, DATE(r.start_time);

-- Indexes for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_reservation_stats_daily_unique
    ON reservation_stats_daily(tenant_id, site_id, date);
CREATE INDEX IF NOT EXISTS idx_reservation_stats_daily_tenant_date
    ON reservation_stats_daily(tenant_id, date DESC);

COMMENT ON MATERIALIZED VIEW reservation_stats_daily IS
'Daily aggregation of reservation statistics by site for analytics. Refreshed hourly.';

-- ============================================================================
-- Device Health Summary
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS device_health_summary AS
SELECT
    s.tenant_id,
    s.site_id,
    sites.name as site_name,
    -- Sensor devices
    COUNT(DISTINCT s.sensor_eui) FILTER (WHERE s.sensor_eui IS NOT NULL) as total_sensors,
    COUNT(DISTINCT s.sensor_eui) FILTER (
        WHERE s.sensor_eui IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM sensor_readings sr
            WHERE sr.space_id = s.id
            AND sr.timestamp > NOW() - INTERVAL '24 hours'
        )
    ) as active_sensors_24h,
    -- Display devices
    COUNT(DISTINCT s.display_eui) FILTER (WHERE s.display_eui IS NOT NULL) as total_displays,
    COUNT(DISTINCT s.display_eui) FILTER (
        WHERE s.display_eui IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM actuations a
            WHERE a.space_id = s.id
            AND a.created_at > NOW() - INTERVAL '24 hours'
        )
    ) as active_displays_24h,
    -- Health score (percentage of devices active in last 24h)
    CASE
        WHEN COUNT(DISTINCT s.sensor_eui) + COUNT(DISTINCT s.display_eui) > 0
        THEN ROUND(
            (COUNT(DISTINCT s.sensor_eui) FILTER (WHERE EXISTS (SELECT 1 FROM sensor_readings sr WHERE sr.space_id = s.id AND sr.timestamp > NOW() - INTERVAL '24 hours')) +
             COUNT(DISTINCT s.display_eui) FILTER (WHERE EXISTS (SELECT 1 FROM actuations a WHERE a.space_id = s.id AND a.created_at > NOW() - INTERVAL '24 hours'))
            )::numeric /
            (COUNT(DISTINCT s.sensor_eui) + COUNT(DISTINCT s.display_eui))::numeric * 100,
            2
        )
        ELSE 0
    END as health_score_percent,
    NOW() as last_refreshed
FROM spaces s
LEFT JOIN sites ON s.site_id = sites.id
WHERE s.deleted_at IS NULL
GROUP BY s.tenant_id, s.site_id, sites.name;

-- Indexes for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_device_health_summary_unique
    ON device_health_summary(tenant_id, site_id);
CREATE INDEX IF NOT EXISTS idx_device_health_summary_tenant
    ON device_health_summary(tenant_id);

COMMENT ON MATERIALIZED VIEW device_health_summary IS
'Real-time device health metrics by site for monitoring dashboards. Refreshed every 15 minutes.';

-- ============================================================================
-- Refresh Schedule Notes
-- ============================================================================

-- These materialized views should be refreshed on the following schedule:
--
-- space_utilization_daily:    Every 1 hour  (REFRESH MATERIALIZED VIEW CONCURRENTLY)
-- api_usage_hourly:            Every 1 hour  (REFRESH MATERIALIZED VIEW CONCURRENTLY)
-- reservation_stats_daily:     Every 1 hour  (REFRESH MATERIALIZED VIEW CONCURRENTLY)
-- device_health_summary:       Every 15 min  (REFRESH MATERIALIZED VIEW CONCURRENTLY)
--
-- Use CONCURRENTLY to avoid blocking reads during refresh.
-- Implement refresh logic in src/background_tasks.py using APScheduler.
--
-- Example refresh command:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY space_utilization_daily;

COMMIT;
