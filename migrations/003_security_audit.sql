-- ============================================
-- Security: Audit Log, Permissions, Metrics
-- Migration 003: Security & Audit
-- ============================================

BEGIN;

-- Audit Log (immutable)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    
    -- Actor information
    actor_type VARCHAR(50) NOT NULL, -- 'user', 'api_key', 'system', 'webhook'
    actor_id VARCHAR(255),
    actor_details JSONB DEFAULT '{}',
    
    -- Action information
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    
    -- Change tracking
    old_values JSONB,
    new_values JSONB,
    
    -- Request context
    request_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    
    -- Timestamp (immutable)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for audit log
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_type, actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action, created_at DESC);

-- Trigger to prevent updates/deletes on audit log
CREATE OR REPLACE FUNCTION prevent_audit_log_changes()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_log_changes();

-- Metrics Storage (for Prometheus)
CREATE TABLE IF NOT EXISTS metrics_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    metric_labels JSONB DEFAULT '{}',
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for metrics
CREATE INDEX IF NOT EXISTS idx_metrics_tenant ON metrics_snapshot(tenant_id, metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics_snapshot(timestamp);

-- Rate Limiting State
CREATE TABLE IF NOT EXISTS rate_limit_state (
    key VARCHAR(255) PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    
    bucket_tokens INTEGER NOT NULL,
    last_refill TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    total_requests BIGINT DEFAULT 0,
    total_rejected BIGINT DEFAULT 0
);

-- Index for rate limiting
CREATE INDEX IF NOT EXISTS idx_rate_limit_tenant ON rate_limit_state(tenant_id);

COMMIT;
