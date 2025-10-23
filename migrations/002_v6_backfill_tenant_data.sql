-- ============================================
-- Migration 002: Backfill tenant_id from space assignments
-- ============================================

BEGIN;

-- Backfill sensor_devices tenant_id from space assignments
UPDATE sensor_devices sd
SET
    tenant_id = COALESCE(sd.tenant_id, s.tenant_id),
    assigned_space_id = COALESCE(sd.assigned_space_id, sp.id),
    assigned_at = COALESCE(sd.assigned_at, sp.created_at),
    lifecycle_state = CASE
        WHEN sp.id IS NOT NULL THEN 'operational'
        ELSE 'provisioned'
    END
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.sensor_device_id = sd.id
  AND sd.tenant_id IS NULL;

-- Backfill display_devices tenant_id
UPDATE display_devices dd
SET
    tenant_id = COALESCE(dd.tenant_id, s.tenant_id),
    assigned_space_id = COALESCE(dd.assigned_space_id, sp.id),
    assigned_at = COALESCE(dd.assigned_at, sp.created_at),
    lifecycle_state = CASE
        WHEN sp.id IS NOT NULL THEN 'operational'
        ELSE 'provisioned'
    END
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.display_device_id = dd.id
  AND dd.tenant_id IS NULL;

-- Assign orphaned devices to platform tenant
UPDATE sensor_devices
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

UPDATE display_devices
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

COMMIT;
