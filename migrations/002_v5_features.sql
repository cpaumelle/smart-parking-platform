-- ============================================
-- V5.3 Features: Display, Downlink, Webhooks
-- Migration 002: V5.3 Feature Tables
-- ============================================

BEGIN;

-- Display Policies (from V5.3)
CREATE TABLE IF NOT EXISTS display_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    policy_name VARCHAR(255) NOT NULL,
    description TEXT,
    
    display_codes JSONB NOT NULL DEFAULT '{
        "free": {"led_color": "green"},
        "occupied": {"led_color": "red"},
        "reserved": {"led_color": "blue"},
        "maintenance": {"led_color": "yellow"}
    }',
    
    transition_rules JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),
    
    CONSTRAINT unique_active_policy_per_tenant UNIQUE (tenant_id, is_active) WHERE is_active = true
);

-- Display State Cache (for Redis versioning)
CREATE TABLE IF NOT EXISTS display_state_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    space_id UUID NOT NULL REFERENCES spaces(id),
    
    current_state VARCHAR(50) NOT NULL,
    display_code VARCHAR(50),
    cache_version INTEGER DEFAULT 1,
    
    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_cache_per_space UNIQUE (space_id)
);

-- Sensor Debounce State (prevent duplicates)
CREATE TABLE IF NOT EXISTS sensor_debounce_state (
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    device_eui VARCHAR(16) NOT NULL,
    fcnt INTEGER NOT NULL,
    
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (tenant_id, device_eui, fcnt)
);

-- Webhook Secrets (per tenant)
CREATE TABLE IF NOT EXISTS webhook_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    secret_key VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    description TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    rotated_from UUID REFERENCES webhook_secrets(id),
    
    CONSTRAINT unique_active_secret_per_tenant UNIQUE (tenant_id, is_active) WHERE is_active = true
);

-- Downlink Queue (persisted for recovery)
CREATE TABLE IF NOT EXISTS downlink_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    device_eui VARCHAR(16) NOT NULL,
    gateway_id VARCHAR(16),
    
    command VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    fport INTEGER DEFAULT 1,
    confirmed BOOLEAN DEFAULT false,
    
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    
    content_hash VARCHAR(64), -- SHA256 for deduplication
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    failed_at TIMESTAMP,
    
    error_message TEXT
);

-- Indexes for downlink queue
CREATE INDEX IF NOT EXISTS idx_downlink_queue_status ON downlink_queue(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_downlink_queue_device ON downlink_queue(device_eui);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pending_command ON downlink_queue(device_eui, content_hash, status) WHERE status = 'pending';

-- API Keys with Scopes (enhanced from V5.3)
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS scopes TEXT[] DEFAULT ARRAY['read']::TEXT[];
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS rate_limit_override INTEGER;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS allowed_ips INET[];

-- Refresh Tokens (from V5.3)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP,
    
    ip_address INET,
    user_agent TEXT,
    
    revoked_at TIMESTAMP,
    revoked_by UUID REFERENCES users(id),
    revoke_reason TEXT
);

-- Indexes for refresh tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

COMMIT;
