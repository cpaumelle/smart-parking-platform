-- Add admin flag to API keys table

ALTER TABLE api_keys
ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false;

-- Add index for active admin keys
CREATE INDEX IF NOT EXISTS idx_api_keys_admin ON api_keys(is_admin) WHERE is_active = true AND is_admin = true;

-- Update comments
COMMENT ON COLUMN api_keys.is_admin IS 'Whether this key has admin privileges for sensitive operations';
