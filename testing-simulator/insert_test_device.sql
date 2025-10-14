-- Insert a real test device into ChirpStack
-- Device: 500_Tabs_Door_Window_11D35F
-- DevEUI: 58a0cb000011d35f (hex)

BEGIN;

-- Step 1: Insert the device
INSERT INTO device (
    dev_eui,
    application_id,
    device_profile_id,
    name,
    description,
    join_eui,
    enabled_class,
    skip_fcnt_check,
    is_disabled,
    external_power_source,
    tags,
    variables,
    app_layer_params,
    created_at,
    updated_at
) VALUES (
    decode('58a0cb000011d35f', 'hex'),                      -- dev_eui (8 bytes)
    '345b028b-9f0a-4c56-910c-6a05dc2dc22f',                -- application_id (Class A devices)
    '8a67cf91-daad-4910-b2d1-f3e4ae05e35a',                -- device_profile_id (Class A 1.0.3 Rev A EU868)
    '500_Tabs_Door_Window_11D35F',                          -- name
    'TESTING - Tabs door/window sensor - Can be deleted after testing',  -- description
    decode('58a0cb0001500000', 'hex'),                      -- join_eui (8 bytes, real AppEUI)
    'A',                                                     -- enabled_class (Class A)
    true,                                                    -- skip_fcnt_check (useful for simulator)
    false,                                                   -- is_disabled
    false,                                                   -- external_power_source
    '{"testing": "true", "device_type": "tabs_door_window"}'::jsonb,  -- tags
    '{}'::jsonb,                                            -- variables
    '{}'::jsonb,                                            -- app_layer_params
    NOW(),                                                   -- created_at
    NOW()                                                    -- updated_at
);

-- Step 2: Insert the device keys (OTAA)
INSERT INTO device_keys (
    dev_eui,
    nwk_key,
    app_key,
    gen_app_key,
    join_nonce,
    dev_nonces,
    created_at,
    updated_at
) VALUES (
    decode('58a0cb000011d35f', 'hex'),                      -- dev_eui
    decode('6c8c64d17bf85b8e3d21a6cd26d08c13', 'hex'),      -- nwk_key (16 bytes, real AppKey)
    decode('6c8c64d17bf85b8e3d21a6cd26d08c13', 'hex'),      -- app_key (16 bytes, same for LoRaWAN 1.0.x)
    decode('00000000000000000000000000000000', 'hex'),      -- gen_app_key (16 bytes, zeros)
    0,                                                       -- join_nonce
    '{}'::jsonb,                                            -- dev_nonces (empty array)
    NOW(),                                                   -- created_at
    NOW()                                                    -- updated_at
);

-- Verify the insert
SELECT 
    encode(d.dev_eui, 'hex') as dev_eui,
    d.name,
    d.description,
    d.enabled_class,
    d.skip_fcnt_check,
    d.is_disabled,
    encode(d.join_eui, 'hex') as join_eui,
    encode(dk.app_key, 'hex') as app_key,
    encode(dk.nwk_key, 'hex') as nwk_key
FROM device d
LEFT JOIN device_keys dk ON d.dev_eui = dk.dev_eui
WHERE d.dev_eui = decode('58a0cb000011d35f', 'hex');

COMMIT;

-- Print success message
\echo ''
\echo '✅ Device created successfully!'
\echo '   DevEUI: 58a0cb000011d35f'
\echo '   Name: 500_Tabs_Door_Window_11D35F'
\echo '   Application: Class A devices'
\echo '   JoinEUI: 58a0cb0001500000'
\echo ''
\echo 'Next steps:'
\echo '  1. Check ChirpStack UI: https://lorawan.verdegris.eu'
\echo '  2. Navigate to: Applications → Class A devices → Devices'
\echo '  3. You should see: 500_Tabs_Door_Window_11D35F'
\echo ''
