-- Smart Parking v5.3 - Occupancy → Display State Machine
-- Implements policy-driven display control with priority rules and hysteresis
-- Date: 2025-10-20
-- Run after: 005_reservation_statuses.sql

-- ============================================================
-- Display Policy Table (Per-Tenant Configurable)
-- ============================================================

CREATE TABLE IF NOT EXISTS display_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Policy name and metadata
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,

    -- Timing thresholds
    reserved_soon_threshold_sec INTEGER NOT NULL DEFAULT 900,  -- 15 minutes
    sensor_unknown_timeout_sec INTEGER NOT NULL DEFAULT 60,    -- Hold last stable state for 60s
    debounce_window_sec INTEGER NOT NULL DEFAULT 10,           -- Require 2 readings within 10s

    -- Color mappings (hex RGB or device-specific codes)
    occupied_color VARCHAR(20) NOT NULL DEFAULT 'FF0000',      -- Red
    free_color VARCHAR(20) NOT NULL DEFAULT '00FF00',          -- Green
    reserved_color VARCHAR(20) NOT NULL DEFAULT 'FFA500',      -- Orange
    reserved_soon_color VARCHAR(20) NOT NULL DEFAULT 'FFFF00', -- Yellow
    blocked_color VARCHAR(20) NOT NULL DEFAULT '808080',       -- Gray
    out_of_service_color VARCHAR(20) NOT NULL DEFAULT '800080',-- Purple

    -- Display behaviors
    blink_reserved_soon BOOLEAN NOT NULL DEFAULT false,
    blink_pattern_ms INTEGER DEFAULT 500,  -- On/off cycle time

    -- Admin override options
    allow_sensor_override BOOLEAN NOT NULL DEFAULT true,       -- Can sensor override reservation?

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id),

    -- Constraint: one active policy per tenant (handled by partial unique index below)
);

-- Partial unique index: ONE active policy per tenant (enforced at DB level)
CREATE UNIQUE INDEX IF NOT EXISTS uq_display_policies_active_per_tenant
    ON display_policies(tenant_id)
    WHERE is_active = TRUE;

-- Performance index for tenant lookups
CREATE INDEX IF NOT EXISTS idx_display_policies_tenant
    ON display_policies(tenant_id, is_active);

COMMENT ON TABLE display_policies IS
    'Per-tenant display policies defining color mappings, thresholds, and behaviors for the occupancy display state machine';

COMMENT ON COLUMN display_policies.reserved_soon_threshold_sec IS
    'Show reserved_soon state this many seconds before reservation starts';

COMMENT ON COLUMN display_policies.debounce_window_sec IS
    'Require 2 consecutive identical sensor readings within this window to switch state';

-- ============================================================
-- Sensor Reading Debouncing Table
-- ============================================================

CREATE TABLE IF NOT EXISTS sensor_debounce_state (
    space_id UUID PRIMARY KEY REFERENCES spaces(id) ON DELETE CASCADE,

    -- Last sensor reading
    last_sensor_state VARCHAR(20),  -- 'occupied', 'vacant', 'unknown'
    last_sensor_timestamp TIMESTAMPTZ,
    last_sensor_rssi INTEGER,
    last_sensor_snr NUMERIC,

    -- Pending state (waiting for confirmation)
    pending_sensor_state VARCHAR(20),
    pending_since TIMESTAMPTZ,
    pending_count INTEGER DEFAULT 0,

    -- Stable state (confirmed after debouncing)
    stable_sensor_state VARCHAR(20),
    stable_since TIMESTAMPTZ,

    -- Last computed display state
    last_display_state VARCHAR(20),  -- 'FREE', 'OCCUPIED', 'RESERVED', 'MAINTENANCE', etc.
    last_display_color VARCHAR(20),
    last_display_blink BOOLEAN DEFAULT false,
    last_display_updated_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hot-path index for space lookups (PRIMARY KEY on space_id already covers this)
-- Additional index for monitoring pending debounce states
CREATE INDEX IF NOT EXISTS idx_sensor_debounce_pending
    ON sensor_debounce_state(pending_sensor_state, pending_since)
    WHERE pending_sensor_state IS NOT NULL;

COMMENT ON TABLE sensor_debounce_state IS
    'Tracks sensor reading history for debouncing logic. Requires 2 consecutive readings to confirm state change.';

-- ============================================================
-- Admin Override Table (Blocked/Out of Service)
-- ============================================================

CREATE TABLE IF NOT EXISTS space_admin_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Override type
    override_type VARCHAR(20) NOT NULL CHECK (override_type IN ('blocked', 'out_of_service')),

    -- Time range
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,  -- NULL = indefinite

    -- Metadata
    reason TEXT,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Active flag
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Performance indexes for hot-path queries with tenant scoping
CREATE INDEX IF NOT EXISTS idx_admin_overrides_tenant_space
    ON space_admin_overrides(tenant_id, space_id, is_active)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_admin_overrides_active_time
    ON space_admin_overrides(space_id, start_time, end_time)
    WHERE is_active = TRUE;

COMMENT ON TABLE space_admin_overrides IS
    'Admin overrides for parking spaces (blocked, out_of_service). Highest priority in state machine.';

-- ============================================================
-- State Machine Logic Function
-- ============================================================

CREATE OR REPLACE FUNCTION compute_display_state(
    p_space_id UUID,
    p_tenant_id UUID
)
RETURNS TABLE (
    display_state VARCHAR(20),
    display_color VARCHAR(20),
    display_blink BOOLEAN,
    priority_level INTEGER,
    reason TEXT
) AS $$
DECLARE
    v_policy RECORD;
    v_override RECORD;
    v_reservation RECORD;
    v_sensor RECORD;
    v_now TIMESTAMPTZ := NOW();
BEGIN
    -- 1. Get active display policy for tenant
    SELECT * INTO v_policy
    FROM display_policies
    WHERE tenant_id = p_tenant_id AND is_active = true
    LIMIT 1;

    IF NOT FOUND THEN
        -- Default policy if none configured
        v_policy := ROW(
            NULL, p_tenant_id, 'default', NULL, true,
            900, 60, 10,  -- thresholds
            'FF0000', '00FF00', 'FFA500', 'FFFF00', '808080', '800080',  -- colors
            false, 500, true,  -- behaviors
            v_now, NULL, NULL
        )::display_policies;
    END IF;

    -- 2. PRIORITY 1: Check admin overrides (out_of_service)
    SELECT * INTO v_override
    FROM space_admin_overrides
    WHERE space_id = p_space_id
      AND is_active = true
      AND override_type = 'out_of_service'
      AND start_time <= v_now
      AND (end_time IS NULL OR end_time > v_now)
    ORDER BY start_time DESC
    LIMIT 1;

    IF FOUND THEN
        RETURN QUERY SELECT
            'MAINTENANCE'::VARCHAR(20),
            v_policy.out_of_service_color,
            false,
            1,
            'Admin override: out_of_service'::TEXT;
        RETURN;
    END IF;

    -- 3. PRIORITY 2: Check admin overrides (blocked)
    SELECT * INTO v_override
    FROM space_admin_overrides
    WHERE space_id = p_space_id
      AND is_active = true
      AND override_type = 'blocked'
      AND start_time <= v_now
      AND (end_time IS NULL OR end_time > v_now)
    ORDER BY start_time DESC
    LIMIT 1;

    IF FOUND THEN
        RETURN QUERY SELECT
            'MAINTENANCE'::VARCHAR(20),
            v_policy.blocked_color,
            false,
            2,
            'Admin override: blocked'::TEXT;
        RETURN;
    END IF;

    -- 4. PRIORITY 3: Check active reservation (reserved_now)
    SELECT * INTO v_reservation
    FROM reservations
    WHERE space_id = p_space_id
      AND status IN ('pending', 'confirmed')
      AND start_time <= v_now
      AND end_time > v_now
    ORDER BY start_time ASC
    LIMIT 1;

    IF FOUND THEN
        RETURN QUERY SELECT
            'RESERVED'::VARCHAR(20),
            v_policy.reserved_color,
            false,
            3,
            'Active reservation'::TEXT;
        RETURN;
    END IF;

    -- 5. PRIORITY 4: Check upcoming reservation (reserved_soon)
    SELECT * INTO v_reservation
    FROM reservations
    WHERE space_id = p_space_id
      AND status IN ('pending', 'confirmed')
      AND start_time > v_now
      AND start_time <= (v_now + (v_policy.reserved_soon_threshold_sec || ' seconds')::INTERVAL)
    ORDER BY start_time ASC
    LIMIT 1;

    IF FOUND THEN
        RETURN QUERY SELECT
            'RESERVED'::VARCHAR(20),
            v_policy.reserved_soon_color,
            v_policy.blink_reserved_soon,
            4,
            format('Reservation starts in %s seconds',
                   EXTRACT(EPOCH FROM (v_reservation.start_time - v_now))::INTEGER)::TEXT;
        RETURN;
    END IF;

    -- 6. PRIORITY 5: Use sensor state (with debouncing)
    SELECT * INTO v_sensor
    FROM sensor_debounce_state
    WHERE space_id = p_space_id;

    IF FOUND THEN
        -- Check if sensor data is recent
        IF v_sensor.stable_since IS NOT NULL AND
           (v_now - v_sensor.stable_since) <= (v_policy.sensor_unknown_timeout_sec || ' seconds')::INTERVAL THEN

            -- Use stable sensor state
            IF v_sensor.stable_sensor_state = 'occupied' THEN
                RETURN QUERY SELECT
                    'OCCUPIED'::VARCHAR(20),
                    v_policy.occupied_color,
                    false,
                    5,
                    'Sensor: occupied'::TEXT;
                RETURN;
            ELSIF v_sensor.stable_sensor_state = 'vacant' THEN
                RETURN QUERY SELECT
                    'FREE'::VARCHAR(20),
                    v_policy.free_color,
                    false,
                    5,
                    'Sensor: vacant'::TEXT;
                RETURN;
            END IF;
        END IF;

        -- Sensor data stale - hold last stable state
        IF v_sensor.last_display_state IS NOT NULL THEN
            RETURN QUERY SELECT
                v_sensor.last_display_state::VARCHAR(20),
                v_sensor.last_display_color,
                v_sensor.last_display_blink,
                6,
                format('Holding last stable state (sensor timeout %ss)',
                       v_policy.sensor_unknown_timeout_sec)::TEXT;
            RETURN;
        END IF;
    END IF;

    -- 7. DEFAULT: Free (no data available)
    RETURN QUERY SELECT
        'FREE'::VARCHAR(20),
        v_policy.free_color,
        false,
        7,
        'Default: no sensor data'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION compute_display_state IS
    'Deterministic state machine that computes display state based on priority rules:
     1. out_of_service
     2. blocked
     3. reserved_now
     4. reserved_soon
     5. sensor (occupied/vacant)
     6. last stable state (sensor timeout)
     7. default (free)';

-- ============================================================
-- Default Policies for Existing Tenants
-- ============================================================

-- Create default policy for each existing tenant
INSERT INTO display_policies (tenant_id, name, description)
SELECT
    id,
    'Default Policy',
    'Auto-generated default display policy'
FROM tenants
ON CONFLICT DO NOTHING;

-- ============================================================
-- Views for Monitoring
-- ============================================================

CREATE OR REPLACE VIEW v_space_display_states AS
SELECT
    s.id as space_id,
    s.code as space_code,
    s.name as space_name,
    s.tenant_id,
    t.name as tenant_name,

    -- Current database state
    s.state as db_state,

    -- Computed display state
    ds.display_state,
    ds.display_color,
    ds.display_blink,
    ds.priority_level,
    ds.reason,

    -- Sensor info
    sds.stable_sensor_state,
    sds.stable_since,
    sds.last_display_updated_at,

    -- Active reservation
    (SELECT COUNT(*) FROM reservations r
     WHERE r.space_id = s.id
       AND r.status IN ('pending', 'confirmed')
       AND r.start_time <= NOW()
       AND r.end_time > NOW()) as has_active_reservation,

    -- Admin override
    (SELECT override_type FROM space_admin_overrides ao
     WHERE ao.space_id = s.id
       AND ao.is_active = true
       AND ao.start_time <= NOW()
       AND (ao.end_time IS NULL OR ao.end_time > NOW())
     LIMIT 1) as admin_override

FROM spaces s
JOIN tenants t ON t.id = s.tenant_id
LEFT JOIN LATERAL compute_display_state(s.id, s.tenant_id) ds ON true
LEFT JOIN sensor_debounce_state sds ON sds.space_id = s.id
WHERE s.deleted_at IS NULL
ORDER BY s.code;

COMMENT ON VIEW v_space_display_states IS
    'Real-time view of computed display states for all spaces using state machine logic';

-- ============================================================
-- Grants
-- ============================================================

GRANT ALL ON TABLE display_policies TO parking;
GRANT ALL ON TABLE sensor_debounce_state TO parking;
GRANT ALL ON TABLE space_admin_overrides TO parking;
GRANT EXECUTE ON FUNCTION compute_display_state(UUID, UUID) TO parking;

-- ============================================================
-- Verification
-- ============================================================

DO $$
DECLARE
    tables_created INTEGER;
    function_exists BOOLEAN;
    policies_created INTEGER;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO tables_created
    FROM information_schema.tables
    WHERE table_name IN ('display_policies', 'sensor_debounce_state', 'space_admin_overrides')
      AND table_schema = 'public';

    -- Check function
    SELECT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'compute_display_state'
    ) INTO function_exists;

    -- Count policies
    SELECT COUNT(*) INTO policies_created FROM display_policies;

    RAISE NOTICE 'Migration 006 verification:';
    RAISE NOTICE '  Tables created: %/3', tables_created;
    RAISE NOTICE '  State machine function: %', function_exists;
    RAISE NOTICE '  Default policies created: %', policies_created;

    IF tables_created < 3 OR NOT function_exists THEN
        RAISE EXCEPTION 'Migration 006 verification failed';
    END IF;
END $$;

SELECT 'Migration 006 completed successfully!' AS status;
