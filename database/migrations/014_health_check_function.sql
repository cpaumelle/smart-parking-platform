-- Migration 014: Health Check Function
-- Created: 2025-10-15
-- Purpose: Create SECURITY DEFINER function for health checks that bypasses RLS

\c smart_parking parking_user;

-- Create health check function that runs as parking_user (bypasses RLS)
CREATE OR REPLACE FUNCTION public.get_health_check_stats()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN json_build_object(
        'spaces_count', (SELECT COUNT(*) FROM parking_spaces.spaces WHERE enabled = TRUE),
        'active_reservations', (SELECT COUNT(*) FROM parking_spaces.reservations WHERE status = 'active'),
        'last_actuation', (SELECT MAX(created_at) FROM parking_operations.actuations),
        'active_tenants', (SELECT COUNT(*) FROM core.tenants WHERE is_active = TRUE),
        'active_api_keys', (SELECT COUNT(*) FROM core.api_keys WHERE is_active = TRUE)
    );
END;
$$;

-- Grant execute to parking_app_user
GRANT EXECUTE ON FUNCTION public.get_health_check_stats() TO parking_app_user;

COMMENT ON FUNCTION public.get_health_check_stats() IS
'Returns aggregate statistics for health check. Runs as parking_user to bypass RLS.';

