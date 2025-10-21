-- Migration 009: Create Non-Superuser Application Role for RLS
-- Purpose: Create parking_app role (non-superuser) for Row-Level Security enforcement
--
-- IMPORTANT: Superusers bypass RLS policies in PostgreSQL!
-- The application MUST use a non-superuser role for RLS to work.

-- ==========================================================
-- 1. Create Application Role (Non-Superuser)
-- ==========================================================

-- Create the role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parking_app') THEN
        CREATE ROLE parking_app WITH LOGIN PASSWORD 'parking_app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
        RAISE NOTICE 'Created parking_app role';
    ELSE
        RAISE NOTICE 'parking_app role already exists';
    END IF;
END$$;

COMMENT ON ROLE parking_app IS
  'Application role for Row-Level Security enforcement. Non-superuser to ensure RLS policies are applied.';

-- ==========================================================
-- 2. Grant Database and Schema Permissions
-- ==========================================================

-- Grant database connection
GRANT CONNECT ON DATABASE parking_v5 TO parking_app;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO parking_app;

-- ==========================================================
-- 3. Grant Table Permissions
-- ==========================================================

-- Grant SELECT, INSERT, UPDATE, DELETE on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO parking_app;

-- Grant EXECUTE on all functions (for triggers, etc.)
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO parking_app;

-- Grant USAGE and SELECT on all sequences (for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO parking_app;

-- ==========================================================
-- 4. Grant Future Permissions (for tables created by future migrations)
-- ==========================================================

-- Grant permissions on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app;

-- Grant permissions on future sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO parking_app;

-- Grant permissions on future functions
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO parking_app;

-- ==========================================================
-- 5. Verification
-- ==========================================================

DO $$
DECLARE
    v_is_superuser BOOLEAN;
    v_can_login BOOLEAN;
    v_table_count INTEGER;
BEGIN
    -- Check role attributes
    SELECT rolsuper, rolcanlogin
    INTO v_is_superuser, v_can_login
    FROM pg_roles
    WHERE rolname = 'parking_app';

    -- Count granted table privileges
    SELECT COUNT(DISTINCT table_name)
    INTO v_table_count
    FROM information_schema.table_privileges
    WHERE grantee = 'parking_app'
    AND table_schema = 'public';

    RAISE NOTICE '=== Migration 009: Application Role Creation Complete ===';
    RAISE NOTICE 'Role: parking_app';
    RAISE NOTICE 'Superuser: % (MUST be false for RLS)', v_is_superuser;
    RAISE NOTICE 'Can Login: % (MUST be true)', v_can_login;
    RAISE NOTICE 'Tables with permissions: %', v_table_count;

    IF NOT v_is_superuser AND v_can_login AND v_table_count > 0 THEN
        RAISE NOTICE '✅ SUCCESS: parking_app role ready for production use';
        RAISE NOTICE '✅ RLS will be enforced for this role';
    ELSE
        RAISE WARNING '❌ PROBLEM: Check role configuration';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE 'NEXT STEPS:';
    RAISE NOTICE '1. Update DATABASE_URL to use parking_app role:';
    RAISE NOTICE '   DATABASE_URL=postgresql://parking_app:parking_app_password@postgres:5432/parking_v5';
    RAISE NOTICE '2. Restart application to use new role';
    RAISE NOTICE '3. Test RLS with: python3 test_rls.py';
    RAISE NOTICE '4. Verify RLS is working (tenants see only their own data)';
END$$;
