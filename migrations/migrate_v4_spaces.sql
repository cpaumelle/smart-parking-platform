-- Migrate parking spaces from v4 (parking_platform.parking_spaces) to v5 (parking_v2.public)
-- Run with: psql -U parking_user -d parking_v2 -f migrations/migrate_v4_spaces.sql

\echo '================================================================================'
\echo 'Parking Space Migration: v4 → v5'
\echo '================================================================================'

-- Show current v5 spaces
\echo ''
\echo 'Current v5 spaces (before migration):'
SELECT code, name, sensor_eui, display_eui, state FROM spaces ORDER BY code;

\echo ''
\echo 'Starting migration...'
\echo ''

-- Migrate active spaces from v4 to v5
INSERT INTO spaces (
    id,
    name,
    code,
    building,
    floor,
    zone,
    gps_latitude,
    gps_longitude,
    sensor_eui,
    display_eui,
    state,
    metadata,
    created_at,
    updated_at
)
SELECT
    v4.space_id,
    v4.space_name,
    v4.space_code,
    v4.building,
    v4.floor,
    v4.zone,
    v4.gps_latitude,
    v4.gps_longitude,
    v4.occupancy_sensor_deveui,
    v4.display_device_deveui,
    CASE
        WHEN v4.current_state = 'FREE' THEN 'FREE'::space_state
        WHEN v4.current_state = 'OCCUPIED' THEN 'OCCUPIED'::space_state
        WHEN v4.current_state = 'RESERVED' THEN 'RESERVED'::space_state
        ELSE 'FREE'::space_state
    END,
    jsonb_build_object(
        'migrated_from_v4', true,
        'v4_location_description', COALESCE(v4.location_description, ''),
        'v4_notes', COALESCE(v4.notes, ''),
        'maintenance_mode', COALESCE(v4.maintenance_mode, false)
    ) || COALESCE(v4.space_metadata, '{}'::jsonb),
    v4.created_at,
    v4.updated_at
FROM dblink(
    'host=localhost port=5432 dbname=parking_platform user=parking_user password=' || current_setting('my.password'),
    'SELECT
        space_id,
        space_name,
        space_code,
        building,
        floor,
        zone,
        gps_latitude,
        gps_longitude,
        occupancy_sensor_deveui,
        display_device_deveui,
        current_state,
        space_metadata,
        notes,
        location_description,
        maintenance_mode,
        created_at,
        updated_at
    FROM parking_spaces.spaces
    WHERE archived = false AND enabled = true
    ORDER BY space_code'
) AS v4(
    space_id uuid,
    space_name text,
    space_code text,
    building text,
    floor text,
    zone text,
    gps_latitude numeric,
    gps_longitude numeric,
    occupancy_sensor_deveui text,
    display_device_deveui text,
    current_state text,
    space_metadata jsonb,
    notes text,
    location_description text,
    maintenance_mode boolean,
    created_at timestamp,
    updated_at timestamp
)
WHERE NOT EXISTS (
    SELECT 1 FROM spaces WHERE spaces.code = v4.space_code
);

-- Show results
\echo ''
\echo 'Migration complete!'
\echo ''
\echo 'Final v5 spaces (after migration):'
SELECT code, name, sensor_eui, display_eui, state FROM spaces ORDER BY code;

\echo ''
\echo '================================================================================'
\echo 'Summary:'
SELECT COUNT(*) as total_spaces FROM spaces;
SELECT COUNT(*) as spaces_with_sensors FROM spaces WHERE sensor_eui IS NOT NULL;
SELECT COUNT(*) as spaces_with_displays FROM spaces WHERE display_eui IS NOT NULL;
\echo '================================================================================'
