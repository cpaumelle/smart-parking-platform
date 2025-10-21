-- Migration 008 Hotfix - Fix column names and normalize existing EUIs
-- This fixes issues found when running migration 008 on actual database

-- ==========================================================
-- 1. Fix reservation overlap constraint (use correct column names)
-- ==========================================================
ALTER TABLE reservations DROP CONSTRAINT IF EXISTS no_reservation_overlap;
ALTER TABLE reservations
  ADD CONSTRAINT uq_reservations_no_overlap
  EXCLUDE USING gist (
    space_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
  )
  WHERE (status IN ('pending', 'confirmed'));

COMMENT ON CONSTRAINT uq_reservations_no_overlap ON reservations IS
  'Database-level overlap prevention - only active reservations (pending/confirmed) block new bookings';

-- ==========================================================
-- 2. Normalize existing EUIs to uppercase before adding CHECK constraints
-- ==========================================================

-- Normalize sensor_devices
UPDATE sensor_devices SET dev_eui = UPPER(dev_eui) WHERE dev_eui ~ '[a-f]';

-- Normalize display_devices
UPDATE display_devices SET dev_eui = UPPER(dev_eui) WHERE dev_eui ~ '[a-f]';

-- Normalize spaces
UPDATE spaces SET sensor_eui = UPPER(sensor_eui) WHERE sensor_eui IS NOT NULL AND sensor_eui ~ '[a-f]';
UPDATE spaces SET display_eui = UPPER(display_eui) WHERE display_eui IS NOT NULL AND display_eui ~ '[a-f]';

-- Now add CHECK constraints (data is clean)
ALTER TABLE sensor_devices
  ADD CONSTRAINT chk_sensor_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE display_devices
  ADD CONSTRAINT chk_display_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE spaces
  ADD CONSTRAINT chk_spaces_eui_hex
  CHECK (
    (sensor_eui IS NULL OR sensor_eui ~ '^[0-9A-F]{16}$') AND
    (display_eui IS NULL OR display_eui ~ '^[0-9A-F]{16}$')
  );

COMMENT ON CONSTRAINT chk_sensor_dev_eui_hex ON sensor_devices IS
  'Ensures dev_eui is exactly 16 uppercase hex characters (LoRaWAN standard format)';

COMMENT ON CONSTRAINT chk_display_dev_eui_hex ON display_devices IS
  'Ensures dev_eui is exactly 16 uppercase hex characters (LoRaWAN standard format)';

COMMENT ON CONSTRAINT chk_spaces_eui_hex ON spaces IS
  'Ensures sensor_eui and display_eui are 16 uppercase hex characters when present';

-- ==========================================================
-- 3. Fix v_orphan_devices view (check if device_types.type_code exists)
-- ==========================================================

-- Check if sensor_devices has type_code column
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sensor_devices' AND column_name = 'type_code'
    ) THEN
        -- Create view with type_code join
        DROP VIEW IF EXISTS v_orphan_devices CASCADE;
        CREATE OR REPLACE VIEW v_orphan_devices AS
        SELECT
            sd.id,
            sd.dev_eui,
            sd.device_model,
            sd.status,
            sd.type_code,
            dt.name AS device_type_name,
            sd.first_seen,
            sd.last_seen,
            sd.metadata,
            sd.created_at,
            'sensor' AS device_category
        FROM sensor_devices sd
        LEFT JOIN device_types dt ON sd.type_code = dt.type_code
        WHERE sd.status = 'orphan'
        UNION ALL
        SELECT
            dd.id,
            dd.dev_eui,
            dd.device_model,
            dd.status,
            dd.type_code,
            dt.name AS device_type_name,
            dd.first_seen,
            dd.last_seen,
            dd.metadata,
            dd.created_at,
            'display' AS device_category
        FROM display_devices dd
        LEFT JOIN device_types dt ON dd.type_code = dt.type_code
        WHERE dd.status = 'orphan';
    ELSE
        -- Create simplified view without type_code
        DROP VIEW IF EXISTS v_orphan_devices CASCADE;
        CREATE OR REPLACE VIEW v_orphan_devices AS
        SELECT
            sd.id,
            sd.dev_eui,
            sd.device_model,
            sd.status,
            sd.device_type AS type_code,
            sd.last_seen_at AS last_seen,
            sd.created_at,
            'sensor' AS device_category
        FROM sensor_devices sd
        WHERE sd.status = 'orphan'
        UNION ALL
        SELECT
            dd.id,
            dd.dev_eui,
            dd.device_model,
            dd.status,
            dd.device_type AS type_code,
            dd.last_seen_at AS last_seen,
            dd.created_at,
            'display' AS device_category
        FROM display_devices dd
        WHERE dd.status = 'orphan';
    END IF;
END $$;

COMMENT ON VIEW v_orphan_devices IS
  'View of all orphan devices (sensors + displays) awaiting assignment to spaces';

-- ==========================================================
-- 4. Fix v_spaces access (it's a regular view, not materialized)
-- ==========================================================
-- Skip materialized view commands since v_spaces is a regular view
-- REVOKE ALL ON VIEW v_spaces FROM PUBLIC;

-- ==========================================================
-- Verification
-- ==========================================================
DO $$
DECLARE
    v_fixes_applied INTEGER := 0;
BEGIN
    RAISE NOTICE '=== Migration 008 Hotfix Complete ===';

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_reservations_no_overlap') THEN
        RAISE NOTICE '✓ Reservation overlap constraint fixed (using start_time/end_time)';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sensor_dev_eui_hex') THEN
        RAISE NOTICE '✓ Sensor device EUI CHECK constraint added';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_display_dev_eui_hex') THEN
        RAISE NOTICE '✓ Display device EUI CHECK constraint added';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_spaces_eui_hex') THEN
        RAISE NOTICE '✓ Spaces EUI CHECK constraint added';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'v_orphan_devices') THEN
        RAISE NOTICE '✓ v_orphan_devices view created';
        v_fixes_applied := v_fixes_applied + 1;
    END IF;

    RAISE NOTICE '=== Applied % hotfixes ===', v_fixes_applied;
END $$;
