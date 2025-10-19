-- Smart Parking v2 - Initial Schema
-- Simple, clean, production-ready

-- ============================================================
-- Enable Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Main Tables
-- ============================================================

-- Parking spaces (the core entity)
CREATE TABLE spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) NOT NULL,

    -- Location
    building VARCHAR(100),
    floor VARCHAR(20),
    zone VARCHAR(50),
    gps_latitude DECIMAL(10, 8),
    gps_longitude DECIMAL(11, 8),

    -- Devices
    sensor_eui VARCHAR(16),
    display_eui VARCHAR(16),

    -- State
    state VARCHAR(20) NOT NULL DEFAULT 'FREE',

    -- Metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT unique_space_code UNIQUE (code),
    CONSTRAINT unique_sensor_eui UNIQUE (sensor_eui),
    CONSTRAINT valid_state CHECK (state IN ('FREE', 'OCCUPIED', 'RESERVED', 'MAINTENANCE')),
    CONSTRAINT valid_gps CHECK (
        (gps_latitude IS NULL AND gps_longitude IS NULL) OR
        (gps_latitude BETWEEN -90 AND 90 AND gps_longitude BETWEEN -180 AND 180)
    )
);

-- Indexes for common queries
CREATE INDEX idx_spaces_state ON spaces(state) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_sensor ON spaces(sensor_eui) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_building ON spaces(building) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_location ON spaces(building, floor, zone) WHERE deleted_at IS NULL;

-- Reservations
CREATE TABLE reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL,

    -- Time
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,

    -- User info
    user_email VARCHAR(255),
    user_phone VARCHAR(20),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active',

    -- Metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id),
    CONSTRAINT valid_status CHECK (status IN ('active', 'completed', 'cancelled', 'no_show')),
    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_duration CHECK (end_time - start_time <= INTERVAL '24 hours')
);

-- Indexes
CREATE INDEX idx_reservations_space ON reservations(space_id);
CREATE INDEX idx_reservations_status ON reservations(status) WHERE status = 'active';
CREATE INDEX idx_reservations_time ON reservations(start_time, end_time) WHERE status = 'active';

-- Sensor readings (time-series data)
CREATE TABLE sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    device_eui VARCHAR(16) NOT NULL,
    space_id UUID,

    -- Sensor data
    occupancy_state VARCHAR(20),
    battery DECIMAL(3, 2),
    temperature DECIMAL(4, 1),
    rssi INTEGER,
    snr DECIMAL(4, 1),

    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign key (optional - might have readings from unassigned sensors)
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id)
);

-- Optimize for time-series
CREATE INDEX idx_sensor_readings_device_time ON sensor_readings(device_eui, timestamp DESC);
CREATE INDEX idx_sensor_readings_space_time ON sensor_readings(space_id, timestamp DESC)
    WHERE space_id IS NOT NULL;
-- BRIN index for timestamp (very efficient for time-series)
CREATE INDEX idx_sensor_readings_timestamp_brin ON sensor_readings
    USING BRIN(timestamp);

-- State change audit log
CREATE TABLE state_changes (
    id BIGSERIAL PRIMARY KEY,
    space_id UUID NOT NULL,
    previous_state VARCHAR(20),
    new_state VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    request_id VARCHAR(50),
    metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign key
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id)
);

CREATE INDEX idx_state_changes_space ON state_changes(space_id, timestamp DESC);
CREATE INDEX idx_state_changes_timestamp_brin ON state_changes USING BRIN(timestamp);

-- Simple API keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash VARCHAR(255) NOT NULL,
    key_name VARCHAR(100),
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Use unique constraint for hash lookups
    CONSTRAINT unique_key_hash UNIQUE (key_hash)
);

CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;

-- ============================================================
-- Functions
-- ============================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER update_spaces_updated_at
    BEFORE UPDATE ON spaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_reservations_updated_at
    BEFORE UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Initial Data (Development)
-- ============================================================

-- Insert test API key (password: 'test-api-key-123')
-- This uses bcrypt with salt
INSERT INTO api_keys (key_hash, key_name) VALUES
('$2b$12$YourHashHere', 'Development Key');

-- Insert sample spaces
INSERT INTO spaces (name, code, building, floor, zone) VALUES
('Parking A-001', 'A001', 'Building A', 'Ground', 'North'),
('Parking A-002', 'A002', 'Building A', 'Ground', 'North'),
('Parking B-001', 'B001', 'Building B', 'Ground', 'South');

-- Grant permissions (adjust for your user)
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking;
