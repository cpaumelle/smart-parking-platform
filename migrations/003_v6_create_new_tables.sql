-- ============================================
-- Migration 003: Create new v6 tables
-- ============================================

BEGIN;

-- Gateways table (tenant-scoped)
CREATE TABLE IF NOT EXISTS gateways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway_id VARCHAR(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'offline',
    last_seen_at TIMESTAMP,
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    chirpstack_gateway_id VARCHAR(16),
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

-- ChirpStack synchronization tracking
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
CREATE INDEX IF NOT EXISTS idx_gateways_tenant ON gateways(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_device_assignments_tenant ON device_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_device_assignments_device ON device_assignments(device_id, device_type);
CREATE INDEX IF NOT EXISTS idx_chirpstack_sync_status ON chirpstack_sync(sync_status, next_sync_at);

COMMIT;
