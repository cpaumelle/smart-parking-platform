-- ============================================
-- Migration 004: Enable Row-Level Security
-- ============================================

BEGIN;

-- Enable RLS on tables
ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation_policy ON sensor_devices;
DROP POLICY IF EXISTS tenant_isolation_policy ON display_devices;
DROP POLICY IF EXISTS tenant_isolation_policy ON spaces;
DROP POLICY IF EXISTS tenant_isolation_policy ON gateways;

-- Create RLS policies
CREATE POLICY tenant_isolation_policy ON sensor_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON display_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON spaces
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON gateways
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

COMMIT;
