-- ============================================
-- Row-Level Security Policies
-- Migration 004: Enable RLS
-- ============================================

BEGIN;

-- Enable RLS on all tenant-scoped tables
ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Function to get current tenant context
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN COALESCE(current_setting('app.current_tenant_id', true)::UUID, '00000000-0000-0000-0000-000000000000'::UUID);
EXCEPTION
    WHEN OTHERS THEN
        RETURN '00000000-0000-0000-0000-000000000000'::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to check if platform admin
CREATE OR REPLACE FUNCTION is_platform_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN COALESCE(current_setting('app.is_platform_admin', true)::BOOLEAN, false);
EXCEPTION
    WHEN OTHERS THEN
        RETURN false;
END;
$$ LANGUAGE plpgsql STABLE;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation ON sensor_devices;
DROP POLICY IF EXISTS tenant_isolation ON display_devices;
DROP POLICY IF EXISTS tenant_isolation ON gateways;
DROP POLICY IF EXISTS tenant_isolation ON spaces;
DROP POLICY IF EXISTS tenant_isolation ON sites;
DROP POLICY IF EXISTS tenant_isolation ON reservations;
DROP POLICY IF EXISTS tenant_isolation ON sensor_readings;
DROP POLICY IF EXISTS tenant_isolation ON display_policies;
DROP POLICY IF EXISTS tenant_isolation ON webhook_secrets;
DROP POLICY IF EXISTS tenant_modification ON webhook_secrets;
DROP POLICY IF EXISTS tenant_isolation ON api_keys;
DROP POLICY IF EXISTS tenant_read_only ON audit_log;
DROP POLICY IF EXISTS audit_insert_only ON audit_log;

-- Sensor Devices Policy
CREATE POLICY tenant_isolation ON sensor_devices
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Display Devices Policy
CREATE POLICY tenant_isolation ON display_devices
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Gateways Policy
CREATE POLICY tenant_isolation ON gateways
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Spaces Policy
CREATE POLICY tenant_isolation ON spaces
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Sites Policy
CREATE POLICY tenant_isolation ON sites
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Reservations Policy
CREATE POLICY tenant_isolation ON reservations
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Sensor Readings Policy
CREATE POLICY tenant_isolation ON sensor_readings
    FOR ALL
    USING (
        tenant_id = current_tenant_id() 
        OR is_platform_admin()
    );

-- Display Policies Policy
CREATE POLICY tenant_isolation ON display_policies
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Webhook Secrets Policy (more restrictive)
CREATE POLICY tenant_isolation ON webhook_secrets
    FOR SELECT
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

CREATE POLICY tenant_modification ON webhook_secrets
    FOR INSERT, UPDATE, DELETE
    USING (tenant_id = current_tenant_id());

-- API Keys Policy
CREATE POLICY tenant_isolation ON api_keys
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Audit Log Policy (read-only for all)
CREATE POLICY tenant_read_only ON audit_log
    FOR SELECT
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

CREATE POLICY audit_insert_only ON audit_log
    FOR INSERT
    WITH CHECK (true); -- System can always insert

COMMIT;
