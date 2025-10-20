-- Smart Parking v5.3 - Reservation Status Update
-- Updates reservation statuses to match v5.3 spec: pending, confirmed, cancelled, expired
-- Date: 2025-10-20
-- Run after: 004_reservations_and_webhook_hardening.sql

-- ============================================================
-- Required Extensions (Idempotent)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ============================================================
-- Update Reservation Status Values
-- ============================================================

-- Drop old CHECK constraint if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_status'
        AND conrelid = 'reservations'::regclass
    ) THEN
        ALTER TABLE reservations DROP CONSTRAINT valid_status;
    END IF;
END $$;

-- Add new CHECK constraint with updated status values
-- Old: active, completed, cancelled, no_show
-- New: pending, confirmed, cancelled, expired
ALTER TABLE reservations
  ADD CONSTRAINT valid_reservation_status
  CHECK (status IN ('pending', 'confirmed', 'cancelled', 'expired',
                    'active', 'completed', 'no_show'));  -- Keep old values for migration

COMMENT ON CONSTRAINT valid_reservation_status ON reservations IS
  'Allowed reservation statuses. New API uses: pending, confirmed, cancelled, expired. Old values kept for backward compatibility during migration.';

-- Migrate existing data: active → confirmed, completed → expired
UPDATE reservations
SET status = CASE
    WHEN status = 'active' THEN 'confirmed'
    WHEN status = 'completed' THEN 'expired'
    WHEN status = 'no_show' THEN 'expired'
    ELSE status
END
WHERE status IN ('active', 'completed', 'no_show');

-- Update EXCLUDE constraint to use new status
-- Drop old constraint
ALTER TABLE reservations
  DROP CONSTRAINT IF EXISTS no_reservation_overlap;

-- Recreate with updated status filter
ALTER TABLE reservations
  ADD CONSTRAINT no_reservation_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    space_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
  )
  WHERE (status IN ('pending', 'confirmed'));  -- Only active/pending reservations block

COMMENT ON CONSTRAINT no_reservation_overlap ON reservations IS
  'Prevents overlapping pending/confirmed reservations. Cancelled and expired reservations do not block.';

-- ============================================================
-- Add Expiry Tracking
-- ============================================================

-- Add index for expiry job to find reservations needing expiry
CREATE INDEX IF NOT EXISTS idx_reservations_expiry
  ON reservations(end_time, status)
  WHERE status IN ('pending', 'confirmed');

COMMENT ON INDEX idx_reservations_expiry IS
  'Optimizes background job that expires reservations. Finds confirmed reservations past their end_time.';

-- ============================================================
-- Views for Monitoring
-- ============================================================

-- View: Reservations needing expiry
CREATE OR REPLACE VIEW reservations_to_expire AS
SELECT
    id,
    space_id,
    tenant_id,
    start_time,
    end_time,
    status,
    NOW() - end_time as overdue_duration,
    user_email
FROM reservations
WHERE status IN ('pending', 'confirmed')
  AND end_time < NOW()
ORDER BY end_time ASC;

COMMENT ON VIEW reservations_to_expire IS
  'Lists confirmed reservations that have passed their end_time and need to be expired by the background job.';

-- View: Active reservations by tenant
CREATE OR REPLACE VIEW active_reservations_by_tenant AS
SELECT
    tenant_id,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
    COUNT(*) FILTER (WHERE status = 'confirmed') as confirmed_count,
    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_count,
    COUNT(*) FILTER (WHERE status = 'expired') as expired_count,
    COUNT(*) as total_reservations
FROM reservations
GROUP BY tenant_id;

-- ============================================================
-- Function: Expire old reservations
-- ============================================================

CREATE OR REPLACE FUNCTION expire_old_reservations()
RETURNS TABLE (
    expired_count INTEGER,
    reservation_ids UUID[]
) AS $$
DECLARE
    expired_ids UUID[];
    count INTEGER;
BEGIN
    -- Update expired reservations
    WITH updated AS (
        UPDATE reservations
        SET status = 'expired',
            updated_at = NOW()
        WHERE status IN ('pending', 'confirmed')
          AND end_time < NOW()
        RETURNING id
    )
    SELECT ARRAY_AGG(id), COUNT(*) INTO expired_ids, count
    FROM updated;

    RETURN QUERY SELECT COALESCE(count, 0), COALESCE(expired_ids, ARRAY[]::UUID[]);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_old_reservations IS
  'Expires all confirmed/pending reservations past their end_time. Called by background job every minute.';

-- ============================================================
-- Verification
-- ============================================================

DO $$
DECLARE
    has_updated_constraint BOOLEAN;
    has_expiry_index BOOLEAN;
    has_expiry_function BOOLEAN;
    migrated_count INTEGER;
BEGIN
    -- Check constraint
    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_reservation_status'
    ) INTO has_updated_constraint;

    -- Check index
    SELECT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_reservations_expiry'
    ) INTO has_expiry_index;

    -- Check function
    SELECT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'expire_old_reservations'
    ) INTO has_expiry_function;

    -- Count migrated records
    SELECT COUNT(*) INTO migrated_count
    FROM reservations
    WHERE status IN ('pending', 'confirmed', 'cancelled', 'expired');

    RAISE NOTICE 'Migration 005 verification:';
    RAISE NOTICE '  Updated status constraint: %', has_updated_constraint;
    RAISE NOTICE '  Expiry index created: %', has_expiry_index;
    RAISE NOTICE '  Expiry function created: %', has_expiry_function;
    RAISE NOTICE '  Migrated reservations: %', migrated_count;

    IF NOT (has_updated_constraint AND has_expiry_index AND has_expiry_function) THEN
        RAISE EXCEPTION 'Migration 005 verification failed';
    END IF;
END $$;

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT EXECUTE ON FUNCTION expire_old_reservations() TO parking;

SELECT 'Migration 005 completed successfully!' AS status;
