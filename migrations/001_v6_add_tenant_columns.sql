-- ============================================
-- Migration 001: Add tenant_id columns
-- Safe to run multiple times (idempotent)
-- ============================================

BEGIN;

-- Add tenant_id to sensor_devices (nullable initially)
ALTER TABLE sensor_devices
ADD COLUMN IF NOT EXISTS tenant_id UUID,
ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN IF NOT EXISTS assigned_space_id UUID,
ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS chirpstack_device_id UUID,
ADD COLUMN IF NOT EXISTS chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

-- Add tenant_id to display_devices
ALTER TABLE display_devices
ADD COLUMN IF NOT EXISTS tenant_id UUID,
ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN IF NOT EXISTS assigned_space_id UUID,
ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS chirpstack_device_id UUID,
ADD COLUMN IF NOT EXISTS chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

-- Add indexes (IF NOT EXISTS for safety)
CREATE INDEX IF NOT EXISTS idx_sensor_devices_tenant
    ON sensor_devices(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_display_devices_tenant
    ON display_devices(tenant_id, status);

COMMIT;
