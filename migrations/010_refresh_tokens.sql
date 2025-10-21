-- Migration 010: Refresh Tokens for JWT Authentication
-- Description: Add refresh_tokens table for secure token rotation
-- Date: 2025-10-21
-- Related: src/refresh_token_service.py, src/api_tenants.py

-- ============================================================
-- Refresh Tokens Table
-- ============================================================

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash of refresh token
    device_fingerprint VARCHAR(255),  -- Optional device identifier for reuse detection
    ip_address INET,  -- Client IP address for security monitoring
    user_agent TEXT,  -- Client User-Agent header
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- Token expiry (30 days from creation)
    revoked_at TIMESTAMPTZ,  -- NULL = active, set = revoked
    last_used_at TIMESTAMPTZ  -- Track token usage
);

-- Index for fast lookups by token hash (primary lookup path)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- Index for user's active tokens (for revoking all tokens)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active ON refresh_tokens(user_id, revoked_at, expires_at)
    WHERE revoked_at IS NULL;

-- Index for cleanup of expired tokens (background job)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expired ON refresh_tokens(expires_at)
    WHERE revoked_at IS NULL;

-- Index for reuse detection (by user + device fingerprint)
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_device ON refresh_tokens(user_id, device_fingerprint)
    WHERE revoked_at IS NULL;

-- ============================================================
-- Comments
-- ============================================================

COMMENT ON TABLE refresh_tokens IS 'Refresh tokens for JWT authentication with rotation and reuse detection';
COMMENT ON COLUMN refresh_tokens.token_hash IS 'SHA-256 hash of refresh token (never store plaintext)';
COMMENT ON COLUMN refresh_tokens.device_fingerprint IS 'Optional device identifier for reuse detection and security monitoring';
COMMENT ON COLUMN refresh_tokens.ip_address IS 'Client IP address for security audit trail';
COMMENT ON COLUMN refresh_tokens.user_agent IS 'Client User-Agent header for device tracking';
COMMENT ON COLUMN refresh_tokens.expires_at IS 'Token expiry timestamp (30 days from creation)';
COMMENT ON COLUMN refresh_tokens.revoked_at IS 'Token revocation timestamp (NULL = active, set = revoked)';
COMMENT ON COLUMN refresh_tokens.last_used_at IS 'Last time token was used (for tracking)';

-- ============================================================
-- Security Features
-- ============================================================

-- Token Rotation:
--   - Every refresh generates a new token and revokes the old one
--   - Prevents long-lived token compromise

-- Reuse Detection:
--   - If a revoked token is reused, all tokens for that user+device are revoked
--   - Indicates potential token theft
--   - 5-minute grace period for race conditions

-- Device Fingerprinting:
--   - Optional X-Device-Fingerprint header from client
--   - Tracks token usage across devices
--   - Alerts on device changes (potential theft)

-- Automatic Cleanup:
--   - Background job periodically deletes expired tokens
--   - Keeps table size manageable

-- ============================================================
-- Migration Verification
-- ============================================================

-- Verify table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'refresh_tokens') THEN
        RAISE EXCEPTION 'Migration failed: refresh_tokens table not created';
    END IF;
END $$;

-- Verify indexes exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_refresh_tokens_token_hash') THEN
        RAISE EXCEPTION 'Migration failed: idx_refresh_tokens_token_hash index not created';
    END IF;
END $$;

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 010: refresh_tokens table created successfully';
    RAISE NOTICE '  - Table: refresh_tokens with 10 columns';
    RAISE NOTICE '  - Indexes: 4 indexes created';
    RAISE NOTICE '  - Security: Token rotation, reuse detection, device fingerprinting';
    RAISE NOTICE '  - Features: 30-day expiry, automatic cleanup, audit trail';
END $$;
