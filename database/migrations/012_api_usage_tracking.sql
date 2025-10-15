-- ============================================================================
-- Migration 012: API Usage Tracking (Phase 3.2)
-- ============================================================================
-- Creates table and functions for tracking per-tenant API usage
-- for monitoring, billing, and rate limiting purposes.
--
-- Author: Claude Code (Verdegris)
-- Date: 2025-10-15
-- Version: 1.5.1
-- ============================================================================

\c parking_platform;

-- Create API usage tracking table
CREATE TABLE IF NOT EXISTS core.api_usage_log (
    usage_id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES core.api_keys(api_key_id) ON DELETE SET NULL,
    endpoint VARCHAR(255) NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    request_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for fast tenant-based queries
CREATE INDEX IF NOT EXISTS idx_api_usage_tenant ON core.api_usage_log(tenant_id, request_timestamp DESC);

-- Index for endpoint analytics
CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON core.api_usage_log(endpoint, request_timestamp DESC);

-- Index for rate limiting (recent requests per tenant)
CREATE INDEX IF NOT EXISTS idx_api_usage_recent ON core.api_usage_log(tenant_id, request_timestamp) 
WHERE request_timestamp > NOW() - INTERVAL '1 hour';

-- Index for API key usage tracking
CREATE INDEX IF NOT EXISTS idx_api_usage_key ON core.api_usage_log(api_key_id, request_timestamp DESC);

-- Enable RLS on api_usage_log
ALTER TABLE core.api_usage_log ENABLE ROW LEVEL SECURITY;

-- RLS policy: tenants can only see their own usage logs
CREATE POLICY tenant_isolation_api_usage ON core.api_usage_log
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);

-- Grant permissions to parking_app_user
GRANT SELECT, INSERT ON core.api_usage_log TO parking_app_user;
GRANT USAGE, SELECT ON SEQUENCE core.api_usage_log_usage_id_seq TO parking_app_user;

-- ============================================================================
-- Function: Record API Usage
-- ============================================================================
CREATE OR REPLACE FUNCTION core.record_api_usage(
    p_tenant_id UUID,
    p_api_key_id UUID,
    p_endpoint VARCHAR,
    p_http_method VARCHAR,
    p_status_code INTEGER,
    p_response_time_ms INTEGER DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_usage_id BIGINT;
BEGIN
    INSERT INTO core.api_usage_log (
        tenant_id,
        api_key_id,
        endpoint,
        http_method,
        status_code,
        response_time_ms,
        ip_address,
        user_agent,
        request_timestamp
    ) VALUES (
        p_tenant_id,
        p_api_key_id,
        p_endpoint,
        p_http_method,
        p_status_code,
        p_response_time_ms,
        p_ip_address,
        p_user_agent,
        NOW()
    ) RETURNING usage_id INTO v_usage_id;
    
    RETURN v_usage_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.record_api_usage TO parking_app_user;

-- ============================================================================
-- Function: Get Tenant Usage Summary
-- ============================================================================
CREATE OR REPLACE FUNCTION core.get_tenant_usage_summary(
    p_tenant_id UUID,
    p_hours INTEGER DEFAULT 24
) RETURNS TABLE (
    total_requests BIGINT,
    successful_requests BIGINT,
    failed_requests BIGINT,
    avg_response_time_ms NUMERIC,
    requests_per_endpoint JSONB,
    requests_per_hour JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_requests,
        COUNT(*) FILTER (WHERE status_code < 400)::BIGINT as successful_requests,
        COUNT(*) FILTER (WHERE status_code >= 400)::BIGINT as failed_requests,
        ROUND(AVG(response_time_ms)::NUMERIC, 2) as avg_response_time_ms,
        
        -- Requests per endpoint
        (
            SELECT jsonb_object_agg(endpoint, request_count)
            FROM (
                SELECT endpoint, COUNT(*) as request_count
                FROM core.api_usage_log
                WHERE tenant_id = p_tenant_id
                  AND request_timestamp > NOW() - (p_hours || ' hours')::INTERVAL
                GROUP BY endpoint
                ORDER BY request_count DESC
                LIMIT 20
            ) endpoint_stats
        ) as requests_per_endpoint,
        
        -- Requests per hour
        (
            SELECT jsonb_object_agg(hour_bucket, request_count)
            FROM (
                SELECT 
                    date_trunc('hour', request_timestamp) as hour_bucket,
                    COUNT(*) as request_count
                FROM core.api_usage_log
                WHERE tenant_id = p_tenant_id
                  AND request_timestamp > NOW() - (p_hours || ' hours')::INTERVAL
                GROUP BY hour_bucket
                ORDER BY hour_bucket DESC
            ) hourly_stats
        ) as requests_per_hour
        
    FROM core.api_usage_log
    WHERE tenant_id = p_tenant_id
      AND request_timestamp > NOW() - (p_hours || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.get_tenant_usage_summary TO parking_app_user;

-- ============================================================================
-- Function: Get Rate Limit Check
-- ============================================================================
CREATE OR REPLACE FUNCTION core.check_rate_limit(
    p_tenant_id UUID,
    p_window_minutes INTEGER DEFAULT 60,
    p_max_requests INTEGER DEFAULT 1000
) RETURNS TABLE (
    request_count BIGINT,
    limit_exceeded BOOLEAN,
    window_start TIMESTAMP WITH TIME ZONE,
    window_end TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_window_start TIMESTAMP WITH TIME ZONE;
    v_window_end TIMESTAMP WITH TIME ZONE;
    v_request_count BIGINT;
BEGIN
    v_window_end := NOW();
    v_window_start := v_window_end - (p_window_minutes || ' minutes')::INTERVAL;
    
    SELECT COUNT(*) INTO v_request_count
    FROM core.api_usage_log
    WHERE tenant_id = p_tenant_id
      AND request_timestamp BETWEEN v_window_start AND v_window_end;
    
    RETURN QUERY SELECT 
        v_request_count,
        v_request_count >= p_max_requests,
        v_window_start,
        v_window_end;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.check_rate_limit TO parking_app_user;

-- ============================================================================
-- Add comment
-- ============================================================================
COMMENT ON TABLE core.api_usage_log IS 'Per-tenant API usage tracking for monitoring, billing, and rate limiting (Phase 3.2)';

\echo '✅ Migration 012: API usage tracking table created';
