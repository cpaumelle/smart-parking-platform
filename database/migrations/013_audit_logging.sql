-- ============================================================================
-- Migration 013: Audit Logging (Phase 3.2)
-- ============================================================================
-- Creates audit trail for security-critical events
-- Tracks: authentication, API key operations, access violations, admin actions
--
-- Author: Claude Code (Verdegris)
-- Date: 2025-10-15
-- Version: 1.5.1
-- ============================================================================

\c parking_platform;

-- Create audit event types enum
CREATE TYPE core.audit_event_type AS ENUM (
    'auth_success',
    'auth_failure',
    'api_key_created',
    'api_key_revoked',
    'api_key_rotated',
    'tenant_isolation_violation',
    'admin_action',
    'config_change',
    'security_alert'
);

-- Create audit severity enum
CREATE TYPE core.audit_severity AS ENUM (
    'info',
    'warning',
    'error',
    'critical'
);

-- Create audit log table
CREATE TABLE IF NOT EXISTS core.audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    event_type core.audit_event_type NOT NULL,
    severity core.audit_severity NOT NULL DEFAULT 'info',
    tenant_id UUID REFERENCES core.tenants(tenant_id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES core.api_keys(api_key_id) ON DELETE SET NULL,
    user_identifier VARCHAR(255),  -- Email, username, or "system"
    event_description TEXT NOT NULL,
    event_details JSONB,  -- Additional structured data
    ip_address INET,
    user_agent TEXT,
    resource_type VARCHAR(100),  -- e.g., "api_key", "reservation", "space"
    resource_id VARCHAR(255),     -- UUID or identifier of affected resource
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for audit log queries
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON core.audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON core.audit_log(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON core.audit_log(severity, created_at DESC) WHERE severity IN ('error', 'critical');
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON core.audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON core.audit_log(resource_type, resource_id);

-- Enable RLS on audit_log (tenants can only see their own audit logs)
ALTER TABLE core.audit_log ENABLE ROW LEVEL SECURITY;

-- RLS policy: tenants can only see their own audit logs
CREATE POLICY tenant_isolation_audit_log ON core.audit_log
    FOR SELECT
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID
        OR current_user = 'parking_user'  -- System admin can see all
    );

-- Grant permissions
GRANT SELECT, INSERT ON core.audit_log TO parking_app_user;
GRANT USAGE, SELECT ON SEQUENCE core.audit_log_audit_id_seq TO parking_app_user;

-- ============================================================================
-- Function: Record Audit Event
-- ============================================================================
CREATE OR REPLACE FUNCTION core.record_audit_event(
    p_event_type core.audit_event_type,
    p_severity core.audit_severity,
    p_tenant_id UUID,
    p_api_key_id UUID DEFAULT NULL,
    p_user_identifier VARCHAR DEFAULT NULL,
    p_event_description TEXT DEFAULT '',
    p_event_details JSONB DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_resource_type VARCHAR DEFAULT NULL,
    p_resource_id VARCHAR DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_audit_id BIGINT;
BEGIN
    INSERT INTO core.audit_log (
        event_type,
        severity,
        tenant_id,
        api_key_id,
        user_identifier,
        event_description,
        event_details,
        ip_address,
        user_agent,
        resource_type,
        resource_id
    ) VALUES (
        p_event_type,
        p_severity,
        p_tenant_id,
        p_api_key_id,
        p_user_identifier,
        p_event_description,
        p_event_details,
        p_ip_address,
        p_user_agent,
        p_resource_type,
        p_resource_id
    ) RETURNING audit_id INTO v_audit_id;
    
    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.record_audit_event TO parking_app_user;

-- ============================================================================
-- Function: Get Recent Security Events
-- ============================================================================
CREATE OR REPLACE FUNCTION core.get_recent_security_events(
    p_tenant_id UUID,
    p_hours INTEGER DEFAULT 24,
    p_severity core.audit_severity DEFAULT NULL
) RETURNS TABLE (
    audit_id BIGINT,
    event_type core.audit_event_type,
    severity core.audit_severity,
    event_description TEXT,
    event_details JSONB,
    ip_address INET,
    resource_type VARCHAR,
    resource_id VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.audit_id,
        a.event_type,
        a.severity,
        a.event_description,
        a.event_details,
        a.ip_address,
        a.resource_type,
        a.resource_id,
        a.created_at
    FROM core.audit_log a
    WHERE a.tenant_id = p_tenant_id
      AND a.created_at > NOW() - (p_hours || ' hours')::INTERVAL
      AND (p_severity IS NULL OR a.severity = p_severity)
    ORDER BY a.created_at DESC
    LIMIT 1000;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.get_recent_security_events TO parking_app_user;

-- ============================================================================
-- Function: Get Audit Statistics
-- ============================================================================
CREATE OR REPLACE FUNCTION core.get_audit_statistics(
    p_tenant_id UUID,
    p_hours INTEGER DEFAULT 24
) RETURNS TABLE (
    total_events BIGINT,
    auth_failures BIGINT,
    security_alerts BIGINT,
    api_key_changes BIGINT,
    events_by_type JSONB,
    events_by_severity JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_events,
        COUNT(*) FILTER (WHERE event_type = 'auth_failure')::BIGINT as auth_failures,
        COUNT(*) FILTER (WHERE event_type = 'security_alert')::BIGINT as security_alerts,
        COUNT(*) FILTER (WHERE event_type IN ('api_key_created', 'api_key_revoked', 'api_key_rotated'))::BIGINT as api_key_changes,
        
        -- Events by type
        (
            SELECT jsonb_object_agg(event_type, event_count)
            FROM (
                SELECT event_type::TEXT, COUNT(*) as event_count
                FROM core.audit_log
                WHERE tenant_id = p_tenant_id
                  AND created_at > NOW() - (p_hours || ' hours')::INTERVAL
                GROUP BY event_type
            ) type_stats
        ) as events_by_type,
        
        -- Events by severity
        (
            SELECT jsonb_object_agg(severity, event_count)
            FROM (
                SELECT severity::TEXT, COUNT(*) as event_count
                FROM core.audit_log
                WHERE tenant_id = p_tenant_id
                  AND created_at > NOW() - (p_hours || ' hours')::INTERVAL
                GROUP BY severity
            ) severity_stats
        ) as events_by_severity
        
    FROM core.audit_log
    WHERE tenant_id = p_tenant_id
      AND created_at > NOW() - (p_hours || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION core.get_audit_statistics TO parking_app_user;

-- ============================================================================
-- Add comment
-- ============================================================================
COMMENT ON TABLE core.audit_log IS 'Security audit trail for authentication, access control, and administrative actions (Phase 3.2)';

\echo '✅ Migration 013: Audit logging created';
