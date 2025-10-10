-- Parking Display Service Schema
-- Creates schemas and tables for parking space management, reservations, and actuation history

-- Configuration schema for device registries
CREATE SCHEMA IF NOT EXISTS parking_config;

-- Spaces schema for parking space definitions
CREATE SCHEMA IF NOT EXISTS parking_spaces;

-- Operations schema for logs and monitoring
CREATE SCHEMA IF NOT EXISTS parking_operations;

-- Grant permissions
GRANT USAGE ON SCHEMA parking_config TO parking_user;
GRANT USAGE ON SCHEMA parking_spaces TO parking_user;
GRANT USAGE ON SCHEMA parking_operations TO parking_user;

GRANT ALL ON ALL TABLES IN SCHEMA parking_config TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA parking_spaces TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA parking_operations TO parking_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA parking_config GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_spaces GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_operations GRANT ALL ON TABLES TO parking_user;

-- Sensor device registry
CREATE TABLE parking_config.sensor_registry (
    sensor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dev_eui VARCHAR(16) NOT NULL UNIQUE,
    sensor_type VARCHAR(50) NOT NULL, -- 'occupancy', 'environment', 'door'
    device_model VARCHAR(100),
    manufacturer VARCHAR(100),
    is_parking_related BOOLEAN DEFAULT FALSE, -- KEY: Ingest service filtering
    payload_decoder VARCHAR(100), -- Function name for payload decoding

    -- Metadata
    device_metadata JSONB DEFAULT '{}',
    commissioning_notes TEXT,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Display device registry
CREATE TABLE parking_config.display_registry (
    display_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dev_eui VARCHAR(16) NOT NULL UNIQUE,
    display_type VARCHAR(50) NOT NULL, -- 'led_matrix', 'e_paper', 'lcd'
    device_model VARCHAR(100),
    manufacturer VARCHAR(100),

    -- Display codes configuration
    display_codes JSONB DEFAULT '{
        "FREE": "01",
        "OCCUPIED": "02",
        "RESERVED": "03",
        "OUT_OF_ORDER": "04",
        "MAINTENANCE": "05"
    }',

    -- Technical specs
    fport INTEGER DEFAULT 1,
    confirmed_downlinks BOOLEAN DEFAULT FALSE,
    max_payload_size INTEGER DEFAULT 51,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_sensor_registry_parking ON parking_config.sensor_registry(dev_eui, is_parking_related)
WHERE is_parking_related = TRUE;

CREATE INDEX idx_display_registry_deveui ON parking_config.display_registry(dev_eui, enabled)
WHERE enabled = TRUE;

-- Core parking spaces with sensor→display pairing
CREATE TABLE parking_spaces.spaces (
    space_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_name VARCHAR(100) NOT NULL UNIQUE,
    space_code VARCHAR(20), -- Short code like "A1-001"
    location_description TEXT,

    -- Geographic location
    building VARCHAR(100),
    floor VARCHAR(50),
    zone VARCHAR(50),
    gps_latitude DECIMAL(10,8),
    gps_longitude DECIMAL(11,8),

    -- DEVICE PAIRING - The core relationships
    occupancy_sensor_id UUID REFERENCES parking_config.sensor_registry(sensor_id),
    display_device_id UUID REFERENCES parking_config.display_registry(display_id),

    -- DevEUI copies for fast lookup (denormalized for performance)
    occupancy_sensor_deveui VARCHAR(16),
    display_device_deveui VARCHAR(16),

    -- Current state tracking
    current_state VARCHAR(20) DEFAULT 'FREE', -- FREE, OCCUPIED, RESERVED, OUT_OF_ORDER
    sensor_state VARCHAR(20) DEFAULT 'FREE',  -- Last known sensor reading
    display_state VARCHAR(20) DEFAULT 'FREE', -- Last state sent to display

    -- Timing information
    last_sensor_update TIMESTAMP,
    last_display_update TIMESTAMP,
    state_changed_at TIMESTAMP DEFAULT NOW(),

    -- Configuration
    auto_actuation BOOLEAN DEFAULT TRUE, -- Enable/disable automatic sensor→display
    reservation_priority BOOLEAN DEFAULT TRUE, -- Reservations override sensor

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    maintenance_mode BOOLEAN DEFAULT FALSE,

    -- Metadata
    space_metadata JSONB DEFAULT '{}',
    notes TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_states CHECK (current_state IN ('FREE', 'OCCUPIED', 'RESERVED', 'OUT_OF_ORDER', 'MAINTENANCE')),
    CONSTRAINT sensor_display_required CHECK (
        (occupancy_sensor_deveui IS NOT NULL OR maintenance_mode = TRUE) AND
        display_device_deveui IS NOT NULL
    )
);

-- Performance indexes
CREATE INDEX idx_spaces_sensor_lookup ON parking_spaces.spaces(occupancy_sensor_deveui, enabled)
WHERE enabled = TRUE;

CREATE INDEX idx_spaces_display_lookup ON parking_spaces.spaces(display_device_deveui, enabled)
WHERE enabled = TRUE;

CREATE INDEX idx_spaces_location ON parking_spaces.spaces(building, floor, zone);
CREATE INDEX idx_spaces_state ON parking_spaces.spaces(current_state, enabled);

-- Reservations table for API-driven state overrides
CREATE TABLE parking_spaces.reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES parking_spaces.spaces(space_id) ON DELETE CASCADE,

    -- Reservation time window
    reserved_from TIMESTAMP NOT NULL,
    reserved_until TIMESTAMP NOT NULL,

    -- External system integration
    external_booking_id VARCHAR(255),
    external_system VARCHAR(100) DEFAULT 'api',
    external_user_id VARCHAR(255),

    -- Reservation details
    booking_metadata JSONB DEFAULT '{}', -- Customer info, vehicle details, etc.
    reservation_type VARCHAR(50) DEFAULT 'standard', -- standard, vip, maintenance, event

    -- Status tracking
    status VARCHAR(20) DEFAULT 'active', -- active, cancelled, completed, expired, no_show

    -- Grace period for no-shows
    grace_period_minutes INTEGER DEFAULT 15,
    no_show_detected_at TIMESTAMP,

    -- Lifecycle timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,

    -- Constraints
    CONSTRAINT valid_time_range CHECK (reserved_until > reserved_from),
    CONSTRAINT valid_status CHECK (status IN ('active', 'cancelled', 'completed', 'expired', 'no_show'))
);

-- Actuation log for complete audit trail
CREATE TABLE parking_operations.actuations (
    actuation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES parking_spaces.spaces(space_id),

    -- Trigger information
    trigger_type VARCHAR(30) NOT NULL, -- sensor_uplink, api_reservation, manual_override, system_cleanup
    trigger_source VARCHAR(100), -- sensor DevEUI, API client ID, user ID, system process
    trigger_data JSONB, -- Raw trigger data for debugging

    -- State transition
    previous_state VARCHAR(20),
    new_state VARCHAR(20) NOT NULL,
    state_reason VARCHAR(100), -- Why this state was chosen

    -- Display actuation details
    display_deveui VARCHAR(16) NOT NULL,
    display_code VARCHAR(10) NOT NULL,
    fport INTEGER DEFAULT 1,
    confirmed BOOLEAN DEFAULT FALSE,

    -- Execution tracking
    downlink_sent BOOLEAN DEFAULT FALSE,
    downlink_confirmed BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,

    -- Error handling
    downlink_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    confirmed_at TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_trigger_type CHECK (trigger_type IN (
        'sensor_uplink', 'api_reservation', 'manual_override', 'system_cleanup', 'reservation_expired'
    ))
);

-- Reservation indexes
CREATE INDEX idx_reservations_active ON parking_spaces.reservations(space_id, status, reserved_from, reserved_until)
WHERE status = 'active';

CREATE INDEX idx_reservations_timerange ON parking_spaces.reservations(reserved_from, reserved_until);
CREATE INDEX idx_reservations_external ON parking_spaces.reservations(external_system, external_booking_id);

-- Actuation indexes
CREATE INDEX idx_actuations_space_time ON parking_operations.actuations(space_id, created_at DESC);
CREATE INDEX idx_actuations_trigger ON parking_operations.actuations(trigger_type, created_at DESC);
CREATE INDEX idx_actuations_errors ON parking_operations.actuations(downlink_sent, downlink_error)
WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL;
