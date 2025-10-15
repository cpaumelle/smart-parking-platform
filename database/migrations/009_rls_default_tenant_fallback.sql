-- ════════════════════════════════════════════════════════════════════
-- RLS Default Tenant Fallback Migration
-- ════════════════════════════════════════════════════════════════════
-- Migration: 009
-- Purpose: Update RLS policies to allow Verdegris tenant as fallback
--          when session variable is not set (backwards compatibility)
-- Date: 2025-10-15
--
-- This allows existing code to continue working during gradual migration
-- to full multi-tenancy awareness.
-- ════════════════════════════════════════════════════════════════════

-- Get Verdegris tenant ID
DO $$
DECLARE
    verdegris_tenant_id UUID;
BEGIN
    SELECT tenant_id INTO verdegris_tenant_id 
    FROM core.tenants 
    WHERE tenant_slug = 'verdegris';
    
    -- Drop existing policies
    DROP POLICY IF EXISTS tenant_isolation_policy ON ingest.raw_uplinks;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.device_types;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.locations;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.device_context;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.gateways;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.ingest_uplinks;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.processed_uplinks;
    DROP POLICY IF EXISTS tenant_isolation_policy ON transform.enrichment_logs;
    DROP POLICY IF EXISTS tenant_isolation_policy ON parking_config.sensor_registry;
    DROP POLICY IF EXISTS tenant_isolation_policy ON parking_config.display_registry;
    DROP POLICY IF EXISTS tenant_isolation_policy ON parking_spaces.spaces;
    DROP POLICY IF EXISTS tenant_isolation_policy ON parking_spaces.reservations;
    DROP POLICY IF EXISTS tenant_isolation_policy ON parking_operations.actuations;
    
    -- Recreate policies with fallback to Verdegris tenant
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON ingest.raw_uplinks
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.device_types
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.locations
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.device_context
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.gateways
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.ingest_uplinks
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.processed_uplinks
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON transform.enrichment_logs
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON parking_config.sensor_registry
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON parking_config.display_registry
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON parking_spaces.spaces
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON parking_spaces.reservations
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    EXECUTE format('
        CREATE POLICY tenant_isolation_policy ON parking_operations.actuations
        FOR ALL
        USING (tenant_id = COALESCE(
            current_setting(''app.current_tenant_id'', TRUE)::UUID,
            %L::UUID
        ))', verdegris_tenant_id);
    
    RAISE NOTICE 'RLS policies updated with Verdegris fallback: %', verdegris_tenant_id;
END $$;

-- Set default for tenant_id columns to use Verdegris tenant
-- This allows INSERTs without explicit tenant_id to work
DO $$
DECLARE
    verdegris_tenant_id UUID;
BEGIN
    SELECT tenant_id INTO verdegris_tenant_id 
    FROM core.tenants 
    WHERE tenant_slug = 'verdegris';
    
    -- Add DEFAULT constraint to all tenant_id columns
    EXECUTE format('ALTER TABLE ingest.raw_uplinks ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.device_types ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.locations ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.device_context ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.gateways ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.ingest_uplinks ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.processed_uplinks ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE transform.enrichment_logs ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE parking_config.sensor_registry ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE parking_config.display_registry ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE parking_spaces.spaces ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE parking_spaces.reservations ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    EXECUTE format('ALTER TABLE parking_operations.actuations ALTER COLUMN tenant_id SET DEFAULT %L::UUID', verdegris_tenant_id);
    
    RAISE NOTICE 'Default tenant_id set to Verdegris: %', verdegris_tenant_id;
END $$;

-- ═══════════════════════════════════════════════════════════════════
-- Migration Complete
-- ═══════════════════════════════════════════════════════════════════
SELECT '✅ RLS policies updated with Verdegris tenant fallback' as result;
