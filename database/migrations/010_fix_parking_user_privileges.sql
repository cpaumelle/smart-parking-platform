-- ════════════════════════════════════════════════════════════════════
-- Fix parking_user Privileges for RLS
-- ════════════════════════════════════════════════════════════════════
-- Migration: 010
-- Purpose: Remove SUPERUSER and BYPASSRLS from parking_user
--          so that RLS policies are actually enforced
-- Date: 2025-10-15
--
-- CRITICAL: This enables Row-Level Security enforcement
-- ════════════════════════════════════════════════════════════════════

-- Check current status
SELECT 
    'BEFORE: parking_user privileges' as status,
    rolsuper as is_superuser,
    rolbypassrls as bypass_rls
FROM pg_roles
WHERE rolname = 'parking_user';

-- Remove SUPERUSER privilege (superusers bypass ALL security)
ALTER ROLE parking_user NOSUPERUSER;

-- Remove BYPASSRLS privilege (explicitly bypass RLS)
ALTER ROLE parking_user NOBYPASSRLS;

-- Verify changes
SELECT 
    'AFTER: parking_user privileges' as status,
    rolsuper as is_superuser,
    rolbypassrls as bypass_rls
FROM pg_roles
WHERE rolname = 'parking_user';

-- Grant necessary permissions explicitly (since we removed SUPERUSER)
-- These grants ensure the user can still perform all normal operations

-- Core schema
GRANT ALL ON ALL TABLES IN SCHEMA core TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA core TO parking_user;

-- Ingest schema
GRANT ALL ON ALL TABLES IN SCHEMA ingest TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA ingest TO parking_user;

-- Transform schema
GRANT ALL ON ALL TABLES IN SCHEMA transform TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA transform TO parking_user;

-- Parking schemas
GRANT ALL ON ALL TABLES IN SCHEMA parking_config TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA parking_config TO parking_user;

GRANT ALL ON ALL TABLES IN SCHEMA parking_spaces TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA parking_spaces TO parking_user;

GRANT ALL ON ALL TABLES IN SCHEMA parking_operations TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA parking_operations TO parking_user;

-- Scheduler schema
GRANT ALL ON ALL TABLES IN SCHEMA scheduler TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA scheduler TO parking_user;

-- Public schema
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking_user;

-- Ensure future objects also have permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA ingest GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA transform GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_config GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_spaces GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_operations GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA scheduler GRANT ALL ON TABLES TO parking_user;

SELECT '✅ parking_user privileges fixed - RLS now enforced' as result;
