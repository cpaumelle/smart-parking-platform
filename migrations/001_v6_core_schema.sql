-- ============================================
-- V6 Core Schema with V5.3 Features
-- Migration 001: Core Schema
-- ============================================

BEGIN;

-- Platform tenant (must exist first)
INSERT INTO tenants (id, name, slug, type, subscription_tier)
VALUES ('00000000-0000-0000-0000-000000000000', 'Platform', 'platform', 'platform', 'enterprise')
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- ENHANCED DEVICE TABLES WITH TENANT OWNERSHIP
-- ============================================

-- Sensor devices with direct tenant ownership
CREATE TABLE IF NOT EXISTS sensor_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dev_eui VARCHAR(16) NOT NULL,
    
    -- Device Info
    name VARCHAR(255),
    device_type VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    
    -- Status Management
    status VARCHAR(50) NOT NULL DEFAULT 'unassigned',
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'provisioned',
    
    -- Assignment Tracking
    assigned_space_id UUID REFERENCES spaces(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    
    -- Configuration
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    
    -- ChirpStack Sync
    chirpstack_device_id UUID,
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_dev_eui UNIQUE (dev_eui),
    CONSTRAINT check_dev_eui_uppercase CHECK (dev_eui = UPPER(dev_eui))
);

-- Display devices
CREATE TABLE IF NOT EXISTS display_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dev_eui VARCHAR(16) NOT NULL,
    
    name VARCHAR(255),
    device_type VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'unassigned',
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'provisioned',
    assigned_space_id UUID REFERENCES spaces(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    chirpstack_device_id UUID,
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_display_dev_eui UNIQUE (dev_eui),
    CONSTRAINT check_display_dev_eui_uppercase CHECK (dev_eui = UPPER(dev_eui))
);

-- Gateways with tenant ownership
CREATE TABLE IF NOT EXISTS gateways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway_id VARCHAR(16) NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(100),
    
    -- Location
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    location_description TEXT,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'offline',
    last_seen_at TIMESTAMP,
    uptime_seconds BIGINT,
    
    -- Configuration
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    
    -- ChirpStack Sync
    chirpstack_gateway_id VARCHAR(16),
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_gateway_per_tenant UNIQUE (tenant_id, gateway_id)
);

-- Device assignment history
CREATE TABLE IF NOT EXISTS device_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    device_type VARCHAR(50) NOT NULL,
    device_id UUID NOT NULL,
    dev_eui VARCHAR(16) NOT NULL,
    
    space_id UUID REFERENCES spaces(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unassigned_at TIMESTAMP,
    assigned_by UUID REFERENCES users(id),
    unassigned_by UUID REFERENCES users(id),
    
    assignment_reason TEXT,
    unassignment_reason TEXT
);

-- ChirpStack synchronization
CREATE TABLE IF NOT EXISTS chirpstack_sync (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    chirpstack_id VARCHAR(255) NOT NULL,
    
    sync_status VARCHAR(50) DEFAULT 'pending',
    sync_direction VARCHAR(50),
    last_sync_at TIMESTAMP,
    next_sync_at TIMESTAMP,
    
    local_data JSONB,
    remote_data JSONB,
    sync_errors JSONB DEFAULT '[]',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_chirpstack_entity UNIQUE (entity_type, entity_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sensor_devices_tenant ON sensor_devices(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_sensor_devices_deveui ON sensor_devices(dev_eui);
CREATE INDEX IF NOT EXISTS idx_sensor_devices_space ON sensor_devices(assigned_space_id);

CREATE INDEX IF NOT EXISTS idx_display_devices_tenant ON display_devices(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_display_devices_deveui ON display_devices(dev_eui);
CREATE INDEX IF NOT EXISTS idx_display_devices_space ON display_devices(assigned_space_id);

CREATE INDEX IF NOT EXISTS idx_gateways_tenant ON gateways(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_device_assignments_tenant ON device_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_device_assignments_device ON device_assignments(device_id, device_type);
CREATE INDEX IF NOT EXISTS idx_device_assignments_space ON device_assignments(space_id);
CREATE INDEX IF NOT EXISTS idx_chirpstack_sync_status ON chirpstack_sync(sync_status, next_sync_at);

COMMIT;
