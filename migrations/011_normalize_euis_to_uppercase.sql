--
-- Migration 011: Normalize all EUIs to UPPERCASE across entire database
--
-- Purpose: Fix case sensitivity issues by converting all DevEUI, Gateway EUI,
--          sensor_eui, and display_eui columns to UPPERCASE standard
--
-- Reason: ChirpStack sends lowercase EUIs, but our database standard is UPPERCASE.
--         This migration ensures consistency across all existing data.
--

BEGIN;

-- ============================================================
-- 1. Update spaces table (sensor_eui and display_eui)
-- ============================================================

UPDATE spaces
SET sensor_eui = UPPER(sensor_eui)
WHERE sensor_eui IS NOT NULL
  AND sensor_eui != UPPER(sensor_eui);

UPDATE spaces
SET display_eui = UPPER(display_eui)
WHERE display_eui IS NOT NULL
  AND display_eui != UPPER(display_eui);

-- ============================================================
-- 2. Update sensor_devices table (dev_eui)
-- ============================================================

UPDATE sensor_devices
SET dev_eui = UPPER(dev_eui)
WHERE dev_eui != UPPER(dev_eui);

-- ============================================================
-- 3. Update display_devices table (dev_eui)
-- ============================================================

UPDATE display_devices
SET dev_eui = UPPER(dev_eui)
WHERE dev_eui != UPPER(dev_eui);

-- ============================================================
-- 4. Update sensor_readings table (device_eui)
-- ============================================================

UPDATE sensor_readings
SET device_eui = UPPER(device_eui)
WHERE device_eui != UPPER(device_eui);

-- ============================================================
-- 5. Update actuations table (display_eui)
-- ============================================================

UPDATE actuations
SET display_eui = UPPER(display_eui)
WHERE display_eui IS NOT NULL
  AND display_eui != UPPER(display_eui);

-- ============================================================
-- 6. Update gateways table (gw_eui) if exists
-- ============================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'gateways') THEN
        UPDATE gateways
        SET gw_eui = UPPER(gw_eui)
        WHERE gw_eui != UPPER(gw_eui);
    END IF;
END $$;

-- ============================================================
-- 7. Add database triggers to enforce UPPERCASE on INSERT/UPDATE
-- ============================================================

-- Trigger function to enforce UPPERCASE EUIs
-- CRITICAL FIX: Use CASE statement to avoid field access errors
-- PostgreSQL evaluates field access before AND conditions can short-circuit,
-- so checking "IF TG_TABLE_NAME = 'X' AND NEW.field IS NOT NULL" fails when
-- the NEW record is from a different table that doesn't have that field.
CREATE OR REPLACE FUNCTION enforce_eui_uppercase()
RETURNS TRIGGER AS $$
BEGIN
    -- Use CASE to check table name FIRST, then access appropriate fields
    -- This prevents 'field does not exist' errors when NEW record is from different table
    CASE TG_TABLE_NAME
        WHEN 'sensor_devices' THEN
            -- Only access dev_eui (exists in sensor_devices)
            IF NEW.dev_eui IS NOT NULL THEN
                NEW.dev_eui := UPPER(NEW.dev_eui);
            END IF;

        WHEN 'display_devices' THEN
            -- Only access dev_eui (exists in display_devices)
            IF NEW.dev_eui IS NOT NULL THEN
                NEW.dev_eui := UPPER(NEW.dev_eui);
            END IF;

        WHEN 'spaces' THEN
            -- Only access sensor_eui and display_eui (exist in spaces)
            IF NEW.sensor_eui IS NOT NULL THEN
                NEW.sensor_eui := UPPER(NEW.sensor_eui);
            END IF;
            IF NEW.display_eui IS NOT NULL THEN
                NEW.display_eui := UPPER(NEW.display_eui);
            END IF;

        WHEN 'sensor_readings' THEN
            -- Only access device_eui (exists in sensor_readings)
            IF NEW.device_eui IS NOT NULL THEN
                NEW.device_eui := UPPER(NEW.device_eui);
            END IF;

        WHEN 'actuations' THEN
            -- Only access display_eui (exists in actuations)
            IF NEW.display_eui IS NOT NULL THEN
                NEW.display_eui := UPPER(NEW.display_eui);
            END IF;

        WHEN 'gateways' THEN
            -- Only access gw_eui (exists in gateways)
            IF NEW.gw_eui IS NOT NULL THEN
                NEW.gw_eui := UPPER(NEW.gw_eui);
            END IF;
    END CASE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS trigger_spaces_eui_uppercase ON spaces;
DROP TRIGGER IF EXISTS trigger_sensor_devices_eui_uppercase ON sensor_devices;
DROP TRIGGER IF EXISTS trigger_display_devices_eui_uppercase ON display_devices;
DROP TRIGGER IF EXISTS trigger_sensor_readings_eui_uppercase ON sensor_readings;
DROP TRIGGER IF EXISTS trigger_actuations_eui_uppercase ON actuations;
DROP TRIGGER IF EXISTS trigger_gateways_eui_uppercase ON gateways;

-- Create triggers for all tables with EUI columns
CREATE TRIGGER trigger_spaces_eui_uppercase
    BEFORE INSERT OR UPDATE ON spaces
    FOR EACH ROW
    EXECUTE FUNCTION enforce_eui_uppercase();

CREATE TRIGGER trigger_sensor_devices_eui_uppercase
    BEFORE INSERT OR UPDATE ON sensor_devices
    FOR EACH ROW
    EXECUTE FUNCTION enforce_eui_uppercase();

CREATE TRIGGER trigger_display_devices_eui_uppercase
    BEFORE INSERT OR UPDATE ON display_devices
    FOR EACH ROW
    EXECUTE FUNCTION enforce_eui_uppercase();

CREATE TRIGGER trigger_sensor_readings_eui_uppercase
    BEFORE INSERT OR UPDATE ON sensor_readings
    FOR EACH ROW
    EXECUTE FUNCTION enforce_eui_uppercase();

CREATE TRIGGER trigger_actuations_eui_uppercase
    BEFORE INSERT OR UPDATE ON actuations
    FOR EACH ROW
    EXECUTE FUNCTION enforce_eui_uppercase();

-- Create trigger for gateways if table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'gateways') THEN
        EXECUTE 'CREATE TRIGGER trigger_gateways_eui_uppercase
                 BEFORE INSERT OR UPDATE ON gateways
                 FOR EACH ROW
                 EXECUTE FUNCTION enforce_eui_uppercase()';
    END IF;
END $$;

-- ============================================================
-- 8. Verification - Count affected rows
-- ============================================================

DO $$
DECLARE
    spaces_sensor_count INT;
    spaces_display_count INT;
    sensor_devices_count INT;
    display_devices_count INT;
    sensor_readings_count INT;
    actuations_count INT;
BEGIN
    SELECT COUNT(*) INTO spaces_sensor_count FROM spaces WHERE sensor_eui IS NOT NULL;
    SELECT COUNT(*) INTO spaces_display_count FROM spaces WHERE display_eui IS NOT NULL;
    SELECT COUNT(*) INTO sensor_devices_count FROM sensor_devices;
    SELECT COUNT(*) INTO display_devices_count FROM display_devices;
    SELECT COUNT(*) INTO sensor_readings_count FROM sensor_readings;
    SELECT COUNT(*) INTO actuations_count FROM actuations WHERE display_eui IS NOT NULL;

    RAISE NOTICE '=== EUI Normalization Complete ===';
    RAISE NOTICE 'Updated EUIs to UPPERCASE:';
    RAISE NOTICE '  - spaces.sensor_eui: % rows', spaces_sensor_count;
    RAISE NOTICE '  - spaces.display_eui: % rows', spaces_display_count;
    RAISE NOTICE '  - sensor_devices.dev_eui: % rows', sensor_devices_count;
    RAISE NOTICE '  - display_devices.dev_eui: % rows', display_devices_count;
    RAISE NOTICE '  - sensor_readings.device_eui: % rows', sensor_readings_count;
    RAISE NOTICE '  - actuations.display_eui: % rows', actuations_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Database triggers created to enforce UPPERCASE on future INSERTs/UPDATEs';
END $$;

COMMIT;
