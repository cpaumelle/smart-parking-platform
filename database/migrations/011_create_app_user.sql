-- ════════════════════════════════════════════════════════════════════
-- Create Non-Superuser Application Role
-- ════════════════════════════════════════════════════════════════════
-- Migration: 011
-- Purpose: Create parking_app_user (non-superuser) for RLS enforcement
-- Date: 2025-10-15
--
-- parking_user remains as superuser/owner for migrations
-- parking_app_user is used by applications for RLS-enforced queries
-- ════════════════════════════════════════════════════════════════════

-- Create non-superuser application role
CREATE ROLE parking_app_user WITH LOGIN PASSWORD 'change_this_password_in_production';

-- Grant schema usage
GRANT USAGE ON SCHEMA core TO parking_app_user;
GRANT USAGE ON SCHEMA ingest TO parking_app_user;
GRANT USAGE ON SCHEMA transform TO parking_app_user;
GRANT USAGE ON SCHEMA parking_config TO parking_app_user;
GRANT USAGE ON SCHEMA parking_spaces TO parking_app_user;
GRANT USAGE ON SCHEMA parking_operations TO parking_app_user;
GRANT USAGE ON SCHEMA scheduler TO parking_app_user;
GRANT USAGE ON SCHEMA public TO parking_app_user;

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ingest TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA transform TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA parking_config TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA parking_spaces TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA parking_operations TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA scheduler TO parking_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO parking_app_user;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ingest TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA transform TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA parking_config TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA parking_spaces TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA parking_operations TO parking_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA scheduler TO parking_app_user;

-- Grant for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA ingest GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA transform GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_config GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_spaces GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_operations GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA scheduler GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO parking_app_user;

-- Verify user created
SELECT 
    rolname,
    rolsuper as is_superuser,
    rolbypassrls as bypass_rls,
    rolcanlogin as can_login
FROM pg_roles
WHERE rolname IN ('parking_user', 'parking_app_user')
ORDER BY rolname;

SELECT '✅ parking_app_user created (non-superuser for RLS enforcement)' as result;
