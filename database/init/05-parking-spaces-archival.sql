-- Parking Spaces Archival Enhancement
-- Adds proper archival tracking for historical analytics support

-- Add archival columns to parking_spaces.spaces
ALTER TABLE parking_spaces.spaces
ADD COLUMN archived BOOLEAN DEFAULT FALSE,
ADD COLUMN archived_at TIMESTAMP,
ADD COLUMN archived_by VARCHAR(255),
ADD COLUMN archived_reason TEXT;

-- Update constraint to allow archived spaces without sensor/display validation
ALTER TABLE parking_spaces.spaces
DROP CONSTRAINT IF EXISTS sensor_display_required;

ALTER TABLE parking_spaces.spaces
ADD CONSTRAINT sensor_display_required CHECK (
    archived = TRUE OR (
        (occupancy_sensor_deveui IS NOT NULL OR maintenance_mode = TRUE) AND
        display_device_deveui IS NOT NULL
    )
);

-- Create index for active (non-archived) spaces
CREATE INDEX idx_spaces_active ON parking_spaces.spaces(space_id, enabled, archived)
WHERE enabled = TRUE AND archived = FALSE;

-- Create index for archived spaces (for historical queries)
CREATE INDEX idx_spaces_archived ON parking_spaces.spaces(archived_at)
WHERE archived = TRUE;

-- Add comment explaining archival semantics
COMMENT ON COLUMN parking_spaces.spaces.enabled IS 'Operational status: FALSE = temporarily disabled (maintenance), archived must be FALSE';
COMMENT ON COLUMN parking_spaces.spaces.archived IS 'Archival status: TRUE = permanently removed from service, preserves historical data for analytics';
COMMENT ON COLUMN parking_spaces.spaces.archived_at IS 'Timestamp when space was archived';
COMMENT ON COLUMN parking_spaces.spaces.archived_by IS 'User/system that archived the space';
COMMENT ON COLUMN parking_spaces.spaces.archived_reason IS 'Reason for archiving (e.g., "Building demolished", "Space reconfigured")';
