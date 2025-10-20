-- Smart Parking v5.3 - Audit Log System
-- Append-only audit trail for all tenant actions
-- Date: 2025-10-20
-- Run after: 006_display_state_machine.sql

-- ============================================================
-- Audit Log Table
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- When
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Who
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL if API key or system
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,  -- NULL if user JWT
    actor_type VARCHAR(20) NOT NULL,  -- 'user', 'api_key', 'system', 'webhook'
    actor_name VARCHAR(255),  -- User email, API key name, or system identifier

    -- What
    action VARCHAR(100) NOT NULL,  -- 'space.create', 'reservation.delete', etc.
    resource_type VARCHAR(50) NOT NULL,  -- 'space', 'reservation', 'device', etc.
    resource_id UUID,  -- ID of the affected resource

    -- Where
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(36),  -- Correlation ID for tracing

    -- Details
    old_values JSONB,  -- Previous state (for updates/deletes)
    new_values JSONB,  -- New state (for creates/updates)
    metadata JSONB,  -- Additional context

    -- Result
    success BOOLEAN NOT NULL DEFAULT true,
    error_message TEXT,

    -- Constraints
    CHECK (actor_type IN ('user', 'api_key', 'system', 'webhook'))
);

-- Indexes for common queries
CREATE INDEX idx_audit_log_tenant_created ON audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_audit_log_action ON audit_log(action, created_at DESC);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id, created_at DESC);
CREATE INDEX idx_audit_log_request ON audit_log(request_id) WHERE request_id IS NOT NULL;

-- Prevent updates and deletes (append-only)
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        RAISE EXCEPTION 'Audit log records cannot be modified';
    END IF;

    IF (TG_OP = 'DELETE') THEN
        RAISE EXCEPTION 'Audit log records cannot be deleted';
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();

COMMENT ON TABLE audit_log IS
  'Append-only audit trail for all tenant actions. Records who did what, when, and on which tenant.';

COMMENT ON COLUMN audit_log.actor_type IS
  'Type of actor: user (JWT), api_key (service), system (background job), webhook (external)';

COMMENT ON COLUMN audit_log.action IS
  'Action performed, format: resource.verb (e.g., space.create, reservation.update, device.delete)';

COMMENT ON COLUMN audit_log.old_values IS
  'Previous state of resource (for updates/deletes), NULL for creates';

COMMENT ON COLUMN audit_log.new_values IS
  'New state of resource (for creates/updates), NULL for deletes';

-- ============================================================
-- Audit Helper Function
-- ============================================================

CREATE OR REPLACE FUNCTION log_audit_event(
    p_tenant_id UUID,
    p_user_id UUID,
    p_api_key_id UUID,
    p_actor_type VARCHAR,
    p_actor_name VARCHAR,
    p_action VARCHAR,
    p_resource_type VARCHAR,
    p_resource_id UUID,
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_request_id VARCHAR DEFAULT NULL,
    p_success BOOLEAN DEFAULT true,
    p_error_message TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_audit_id UUID;
BEGIN
    INSERT INTO audit_log (
        tenant_id, user_id, api_key_id, actor_type, actor_name,
        action, resource_type, resource_id,
        old_values, new_values, metadata,
        ip_address, user_agent, request_id,
        success, error_message
    ) VALUES (
        p_tenant_id, p_user_id, p_api_key_id, p_actor_type, p_actor_name,
        p_action, p_resource_type, p_resource_id,
        p_old_values, p_new_values, p_metadata,
        p_ip_address, p_user_agent, p_request_id,
        p_success, p_error_message
    )
    RETURNING id INTO v_audit_id;

    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Refresh Tokens Table (for JWT rotation)
-- ============================================================

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Token
    token_hash VARCHAR(128) NOT NULL UNIQUE,  -- SHA-256 hash of refresh token

    -- Lifecycle
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    device_fingerprint VARCHAR(255),  -- Browser/device identifier
    ip_address INET,
    user_agent TEXT,

    -- Constraints
    CHECK (expires_at > created_at)
);

-- Indexes
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id, expires_at DESC);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash) WHERE revoked_at IS NULL;
CREATE INDEX idx_refresh_tokens_expiry ON refresh_tokens(expires_at) WHERE revoked_at IS NULL;

COMMENT ON TABLE refresh_tokens IS
  'Refresh tokens for JWT rotation. Long-lived tokens (30 days) used to issue new short-lived access tokens.';

-- ============================================================
-- API Key Revocation
-- ============================================================

-- Add revoked_at column to existing api_keys table (if not present)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'revoked_at'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE;

        COMMENT ON COLUMN api_keys.revoked_at IS
          'When the API key was revoked. NULL = active, NOT NULL = revoked.';

        -- Index for active key checks
        CREATE INDEX idx_api_keys_active ON api_keys(key_hash)
          WHERE revoked_at IS NULL;
    END IF;
END $$;

-- Add revoked_by column to track who revoked it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'revoked_by'
    ) THEN
        ALTER TABLE api_keys ADD COLUMN revoked_by UUID REFERENCES users(id) ON DELETE SET NULL;

        COMMENT ON COLUMN api_keys.revoked_by IS
          'User who revoked this API key.';
    END IF;
END $$;

-- ============================================================
-- Verification Function
-- ============================================================

DO $$
DECLARE
    has_audit_table BOOLEAN;
    has_audit_immutable_trigger BOOLEAN;
    has_refresh_tokens BOOLEAN;
    has_api_key_revocation BOOLEAN;
BEGIN
    -- Check audit_log table
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'audit_log'
    ) INTO has_audit_table;

    -- Check immutable trigger
    SELECT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'audit_log_immutable'
    ) INTO has_audit_immutable_trigger;

    -- Check refresh_tokens table
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'refresh_tokens'
    ) INTO has_refresh_tokens;

    -- Check API key revocation columns
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'api_keys' AND column_name = 'revoked_at'
    ) INTO has_api_key_revocation;

    RAISE NOTICE '=== Migration 007: Audit Log & Security ===';
    RAISE NOTICE '  Audit log table: %', has_audit_table;
    RAISE NOTICE '  Immutable trigger: %', has_audit_immutable_trigger;
    RAISE NOTICE '  Refresh tokens: %', has_refresh_tokens;
    RAISE NOTICE '  API key revocation: %', has_api_key_revocation;

    IF NOT (has_audit_table AND has_audit_immutable_trigger AND has_refresh_tokens AND has_api_key_revocation) THEN
        RAISE WARNING 'Some security features not fully deployed!';
    ELSE
        RAISE NOTICE '✓ All security features deployed successfully';
    END IF;
END $$;
