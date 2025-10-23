# V6 Complete Implementation Plan: Feature Parity with V5.3

**Project**: Smart Parking Platform V6 - Full Implementation
**Duration**: 4-6 weeks (2 developers) or 8-10 weeks (1 developer)
**Goal**: Achieve 100% feature parity with V5.3 + V6 architectural improvements

---

## 📊 Feature Parity Checklist

### V5.3 Features to Maintain
- ✅ Multi-tenancy with RBAC (Owner/Admin/Operator/Viewer)
- ✅ JWT authentication + API keys with scopes
- ✅ Real-time occupancy tracking via LoRaWAN
- ✅ Reservation engine with DB-level overlap prevention
- ✅ Display state machine with policy-driven control
- ✅ Class-C downlink queue with Redis backing
- ✅ Webhook hardening (HMAC-SHA256, fcnt dedup)
- ✅ Comprehensive observability (30+ Prometheus metrics)
- ✅ Security hardening (audit log, refresh tokens)
- ✅ Complete test coverage (property, integration, load)
- ✅ ChirpStack integration
- ✅ ORPHAN device auto-discovery
- ✅ Admin device management API

### V6 Improvements to Add
- ✅ Direct tenant ownership (tenant_id on all entities)
- ✅ Row-Level Security (database-level isolation)
- ✅ Efficient queries (eliminate 3-hop joins)
- ✅ Device lifecycle management
- ✅ Platform admin features (cross-tenant view)
- ✅ ChirpStack synchronization service
- ✅ Enhanced caching strategy
- ✅ GraphQL API (optional)

---

## 🏗️ Phase 0: Project Setup (Day 1-2)

### Create Project Structure

```bash
#!/bin/bash
# setup_v6_project.sh

# Create directory structure
mkdir -p v6_smart_parking/{backend,frontend,migrations,scripts,deployment,docs,tests}
mkdir -p v6_smart_parking/backend/{src,tests,alembic}
mkdir -p v6_smart_parking/backend/src/{core,services,routers,models,utils}
mkdir -p v6_smart_parking/backend/src/routers/{v5_compat,v6}
mkdir -p v6_smart_parking/frontend/src/{components,services,hooks,utils}
mkdir -p v6_smart_parking/tests/{unit,integration,load,e2e}

cd v6_smart_parking
```

### Create Core Configuration Files

#### `.env.example`
```env
# Database
DATABASE_URL=postgresql://parking_user:parking_password@postgres:5432/parking_v6
DB_PASSWORD=parking_password
DB_POOL_SIZE=20
DB_POOL_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_POOL_SIZE=10

# ChirpStack
CHIRPSTACK_HOST=chirpstack
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=your-chirpstack-api-key
CHIRPSTACK_SYNC_INTERVAL=300

# Security
SECRET_KEY=generate-32-char-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# Platform Tenant
PLATFORM_TENANT_ID=00000000-0000-0000-0000-000000000000
PLATFORM_TENANT_NAME=Platform
PLATFORM_TENANT_SLUG=platform

# Application
APP_NAME=Smart Parking Platform V6
APP_VERSION=6.0.0
LOG_LEVEL=INFO
DEBUG=false
CORS_ORIGINS=http://localhost:3000,https://app.yourdomain.com

# Feature Flags
USE_V6_API=true
ENABLE_RLS=true
ENABLE_AUDIT_LOG=true
ENABLE_METRICS=true
ENABLE_GRAPHQL=false

# Monitoring
PROMETHEUS_ENABLED=true
SENTRY_DSN=
JAEGER_ENABLED=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_TENANT=100

# Webhook
WEBHOOK_SECRET_KEY=webhook-secret-here
WEBHOOK_SIGNATURE_HEADER=X-Webhook-Signature
WEBHOOK_SPOOL_DIR=/var/spool/parking-uplinks

# Downlink Queue
DOWNLINK_QUEUE_NAME=parking:downlinks
DOWNLINK_MAX_RETRIES=5
DOWNLINK_RETRY_BACKOFF_BASE=2
DOWNLINK_RATE_LIMIT_GATEWAY=30
DOWNLINK_RATE_LIMIT_TENANT=100
```

#### `backend/requirements.txt`
```txt
# Core
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.10.0
pydantic-settings==2.6.0
python-multipart==0.0.9

# Database
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.2
psycopg2-binary==2.9.9

# Redis
redis==5.0.8
hiredis==2.4.0

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dateutil==2.9.0

# ChirpStack
grpcio==1.65.5
grpcio-tools==1.65.5
chirpstack-api==4.9.0
protobuf==5.28.2

# HTTP Client
httpx==0.27.2
aiohttp==3.10.5

# Monitoring
prometheus-client==0.20.0
opentelemetry-api==1.27.0
opentelemetry-sdk==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==5.0.0
hypothesis==6.112.0
locust==2.32.2
faker==28.4.1

# Utilities
python-dotenv==1.0.1
tenacity==9.0.0
pytz==2024.2
croniter==3.0.3

# GraphQL (optional)
strawberry-graphql[fastapi]==0.242.0

# Development
black==24.8.0
ruff==0.6.8
mypy==1.11.2
ipython==8.27.0
```

#### `docker-compose.yml`
```yaml
version: '3.8'

networks:
  smart-parking:
    name: smart-parking-network
    driver: bridge

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  chirpstack_data:
    driver: local
  mosquitto_data:
    driver: local

services:
  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: parking-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: parking_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: parking_v6
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d:ro
      - ./scripts/postgres:/scripts:ro
    ports:
      - "5432:5432"
    networks:
      - smart-parking
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U parking_user -d parking_v6"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: parking-redis
    restart: unless-stopped
    command: >
      redis-server
      --appendonly yes
      --appendfsync everysec
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - smart-parking
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ChirpStack Network Server
  chirpstack:
    image: chirpstack/chirpstack:4
    container_name: parking-chirpstack
    restart: unless-stopped
    depends_on:
      - postgres
      - mosquitto
      - redis
    volumes:
      - ./config/chirpstack:/etc/chirpstack
      - chirpstack_data:/var/lib/chirpstack
    ports:
      - "8080:8080"
    networks:
      - smart-parking
    environment:
      DATABASE_URL: postgresql://parking_user:${DB_PASSWORD}@postgres:5432/chirpstack?sslmode=disable

  # Mosquitto MQTT Broker
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: parking-mosquitto
    restart: unless-stopped
    volumes:
      - ./config/mosquitto:/mosquitto/config
      - mosquitto_data:/mosquitto/data
    ports:
      - "1883:1883"
      - "9001:9001"
    networks:
      - smart-parking

  # ChirpStack Gateway Bridge
  gateway-bridge:
    image: chirpstack/chirpstack-gateway-bridge:4
    container_name: parking-gateway-bridge
    restart: unless-stopped
    depends_on:
      - mosquitto
    ports:
      - "1700:1700/udp"
    volumes:
      - ./config/gateway-bridge:/etc/chirpstack-gateway-bridge
    networks:
      - smart-parking

  # API Service (V6)
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: parking-api-v6
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      CHIRPSTACK_HOST: ${CHIRPSTACK_HOST}
      CHIRPSTACK_API_KEY: ${CHIRPSTACK_API_KEY}
      SECRET_KEY: ${SECRET_KEY}
      LOG_LEVEL: ${LOG_LEVEL}
      CORS_ORIGINS: ${CORS_ORIGINS}
      USE_V6_API: ${USE_V6_API}
      ENABLE_RLS: ${ENABLE_RLS}
    volumes:
      - ./backend:/app
      - /var/spool/parking-uplinks:/var/spool/parking-uplinks
    ports:
      - "8000:8000"
    networks:
      - smart-parking
    command: >
      sh -c "
        alembic upgrade head &&
        uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
      "

  # Frontend (React)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: parking-frontend-v6
    restart: unless-stopped
    environment:
      REACT_APP_API_URL: http://localhost:8000
      REACT_APP_USE_V6_API: true
      REACT_APP_ENABLE_PLATFORM_ADMIN: true
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    networks:
      - smart-parking
```

---

## 🗄️ Phase 1: Database Migration (Week 1)

### Day 1-2: Core Schema Migration

#### `migrations/001_v6_core_schema.sql`
```sql
-- ============================================
-- V6 Core Schema with V5.3 Features
-- ============================================

BEGIN;

-- Platform tenant (must exist first)
INSERT INTO tenants (id, name, slug, type, subscription_tier)
VALUES ('00000000-0000-0000-0000-000000000000', 'Platform', 'platform', 'platform', 'enterprise')
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- ENHANCED DEVICE TABLES WITH TENANT OWNERSHIP
-- ============================================

-- Sensor devices with direct tenant ownership
CREATE TABLE IF NOT EXISTS sensor_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dev_eui VARCHAR(16) NOT NULL,
    
    -- Device Info
    name VARCHAR(255),
    device_type VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    
    -- Status Management
    status VARCHAR(50) NOT NULL DEFAULT 'unassigned',
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'provisioned',
    
    -- Assignment Tracking
    assigned_space_id UUID REFERENCES spaces(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    
    -- Configuration
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    
    -- ChirpStack Sync
    chirpstack_device_id UUID,
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_dev_eui UNIQUE (dev_eui),
    CONSTRAINT check_dev_eui_uppercase CHECK (dev_eui = UPPER(dev_eui))
);

-- Display devices
CREATE TABLE IF NOT EXISTS display_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dev_eui VARCHAR(16) NOT NULL,
    
    -- Same structure as sensor_devices
    name VARCHAR(255),
    device_type VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'unassigned',
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'provisioned',
    assigned_space_id UUID REFERENCES spaces(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    chirpstack_device_id UUID,
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_display_dev_eui UNIQUE (dev_eui),
    CONSTRAINT check_display_dev_eui_uppercase CHECK (dev_eui = UPPER(dev_eui))
);

-- Gateways with tenant ownership
CREATE TABLE IF NOT EXISTS gateways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway_id VARCHAR(16) NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(100),
    
    -- Location
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    location_description TEXT,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'offline',
    last_seen_at TIMESTAMP,
    uptime_seconds BIGINT,
    
    -- Configuration
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    
    -- ChirpStack Sync
    chirpstack_gateway_id VARCHAR(16),
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
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
    unassignment_reason TEXT,
    
    INDEX idx_device_assignments_tenant (tenant_id),
    INDEX idx_device_assignments_device (device_id, device_type),
    INDEX idx_device_assignments_space (space_id)
);

-- ChirpStack synchronization
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
CREATE INDEX idx_sensor_devices_tenant ON sensor_devices(tenant_id, status);
CREATE INDEX idx_sensor_devices_deveui ON sensor_devices(dev_eui);
CREATE INDEX idx_sensor_devices_space ON sensor_devices(assigned_space_id);

CREATE INDEX idx_display_devices_tenant ON display_devices(tenant_id, status);
CREATE INDEX idx_display_devices_deveui ON display_devices(dev_eui);
CREATE INDEX idx_display_devices_space ON display_devices(assigned_space_id);

CREATE INDEX idx_gateways_tenant ON gateways(tenant_id, status);
CREATE INDEX idx_chirpstack_sync_status ON chirpstack_sync(sync_status, next_sync_at);

COMMIT;
```

### Day 3: V5.3 Feature Tables

#### `migrations/002_v5_features.sql`
```sql
-- ============================================
-- V5.3 Features: Display, Downlink, Webhooks
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
    
    error_message TEXT,
    
    INDEX idx_downlink_queue_status (status, scheduled_at),
    INDEX idx_downlink_queue_device (device_eui),
    CONSTRAINT unique_pending_command UNIQUE (device_eui, content_hash, status) WHERE status = 'pending'
);

-- API Keys with Scopes (enhanced from V5.3)
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS 
    scopes TEXT[] DEFAULT ARRAY['read']::TEXT[];
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS 
    rate_limit_override INTEGER;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS 
    allowed_ips INET[];

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
    revoke_reason TEXT,
    
    INDEX idx_refresh_tokens_user (user_id),
    INDEX idx_refresh_tokens_hash (token_hash)
);

COMMIT;
```

### Day 4: Security & Audit Tables

#### `migrations/003_security_audit.sql`
```sql
-- ============================================
-- Security: Audit Log, Permissions, Metrics
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Indexes
    INDEX idx_audit_log_tenant (tenant_id, created_at DESC),
    INDEX idx_audit_log_actor (actor_type, actor_id),
    INDEX idx_audit_log_resource (resource_type, resource_id),
    INDEX idx_audit_log_action (action, created_at DESC)
);

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
    
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_metrics_tenant (tenant_id, metric_name, timestamp DESC),
    INDEX idx_metrics_time (timestamp)
);

-- Rate Limiting State
CREATE TABLE IF NOT EXISTS rate_limit_state (
    key VARCHAR(255) PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    
    bucket_tokens INTEGER NOT NULL,
    last_refill TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    total_requests BIGINT DEFAULT 0,
    total_rejected BIGINT DEFAULT 0,
    
    INDEX idx_rate_limit_tenant (tenant_id)
);

COMMIT;
```

### Day 5: Row-Level Security

#### `migrations/004_row_level_security.sql`
```sql
-- ============================================
-- Row-Level Security Policies
-- ============================================

BEGIN;

-- Enable RLS on all tenant-scoped tables
ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensor_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Function to get current tenant context
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true)::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to check if platform admin
CREATE OR REPLACE FUNCTION is_platform_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN COALESCE(current_setting('app.is_platform_admin', true)::BOOLEAN, false);
END;
$$ LANGUAGE plpgsql STABLE;

-- Sensor Devices Policy
CREATE POLICY tenant_isolation ON sensor_devices
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Display Devices Policy
CREATE POLICY tenant_isolation ON display_devices
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Gateways Policy
CREATE POLICY tenant_isolation ON gateways
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Spaces Policy
CREATE POLICY tenant_isolation ON spaces
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Sites Policy
CREATE POLICY tenant_isolation ON sites
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Reservations Policy
CREATE POLICY tenant_isolation ON reservations
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Sensor Readings Policy
CREATE POLICY tenant_isolation ON sensor_readings
    FOR ALL
    USING (
        tenant_id = current_tenant_id() 
        OR is_platform_admin()
    );

-- Display Policies Policy
CREATE POLICY tenant_isolation ON display_policies
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Webhook Secrets Policy (more restrictive)
CREATE POLICY tenant_isolation ON webhook_secrets
    FOR SELECT
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

CREATE POLICY tenant_modification ON webhook_secrets
    FOR INSERT, UPDATE, DELETE
    USING (tenant_id = current_tenant_id());

-- API Keys Policy
CREATE POLICY tenant_isolation ON api_keys
    FOR ALL
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

-- Audit Log Policy (read-only for all)
CREATE POLICY tenant_read_only ON audit_log
    FOR SELECT
    USING (tenant_id = current_tenant_id() OR is_platform_admin());

CREATE POLICY audit_insert_only ON audit_log
    FOR INSERT
    WITH CHECK (true); -- System can always insert

COMMIT;
```

---

## 💻 Phase 2: Backend Implementation (Week 2-3)

### Day 1: Core Services

#### `backend/src/core/config.py`
```python
"""Configuration management using Pydantic Settings"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from functools import lru_cache
import os

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Application
    app_name: str = "Smart Parking Platform V6"
    app_version: str = "6.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database
    database_url: str
    db_pool_size: int = 20
    db_pool_max_overflow: int = 40
    enable_rls: bool = True
    
    # Redis
    redis_url: str
    redis_pool_size: int = 10
    
    # ChirpStack
    chirpstack_host: str = "chirpstack"
    chirpstack_port: int = 8080
    chirpstack_api_key: str
    chirpstack_sync_interval: int = 300
    
    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    refresh_token_expiry_days: int = 30
    
    # Platform Tenant
    platform_tenant_id: str = "00000000-0000-0000-0000-000000000000"
    platform_tenant_name: str = "Platform"
    platform_tenant_slug: str = "platform"
    
    # CORS
    cors_origins: List[str] = Field(default_factory=list)
    
    # Feature Flags
    use_v6_api: bool = True
    enable_audit_log: bool = True
    enable_metrics: bool = True
    enable_graphql: bool = False
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_tenant: int = 100
    
    # Webhook
    webhook_secret_key: str
    webhook_signature_header: str = "X-Webhook-Signature"
    webhook_spool_dir: str = "/var/spool/parking-uplinks"
    
    # Downlink Queue
    downlink_queue_name: str = "parking:downlinks"
    downlink_max_retries: int = 5
    downlink_retry_backoff_base: int = 2
    downlink_rate_limit_gateway: int = 30
    downlink_rate_limit_tenant: int = 100
    
    # Monitoring
    prometheus_enabled: bool = True
    sentry_dsn: Optional[str] = None
    jaeger_enabled: bool = False
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Create global settings instance
settings = get_settings()
```

#### `backend/src/core/database.py`
```python
"""Database connection with RLS support"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

class TenantAwareSession:
    """Database session with automatic RLS context"""
    
    def __init__(self, tenant_id: str, is_platform_admin: bool = False, user_role: str = "viewer"):
        self.tenant_id = tenant_id
        self.is_platform_admin = is_platform_admin
        self.user_role = user_role
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session with RLS context set"""
        async with AsyncSessionLocal() as session:
            try:
                if settings.enable_rls:
                    # Set RLS context
                    await session.execute(
                        text("SET LOCAL app.current_tenant_id = :tenant_id"),
                        {"tenant_id": self.tenant_id}
                    )
                    await session.execute(
                        text("SET LOCAL app.is_platform_admin = :is_admin"),
                        {"is_admin": str(self.is_platform_admin).lower()}
                    )
                    await session.execute(
                        text("SET LOCAL app.user_role = :role"),
                        {"role": self.user_role}
                    )
                
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database (create tables if needed)"""
    async with engine.begin() as conn:
        # Run any initialization needed
        logger.info("Database initialized")

async def close_db():
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")
```

#### `backend/src/core/tenant_context.py`
```python
"""Tenant context management for V6"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum, IntEnum
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db, TenantAwareSession
from .config import settings
from ..models.tenant import Tenant, UserMembership
from ..auth.dependencies import get_current_user

class TenantType(str, Enum):
    PLATFORM = "platform"
    CUSTOMER = "customer"
    TRIAL = "trial"

class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3
    OWNER = 4
    PLATFORM_ADMIN = 999

class TenantContext(BaseModel):
    """Enhanced tenant context for V6"""
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    tenant_type: TenantType
    user_id: UUID
    username: str
    email: str
    role: Role
    is_platform_admin: bool = False
    is_cross_tenant_access: bool = False
    subscription_tier: str = "basic"
    features: Dict[str, bool] = Field(default_factory=dict)
    limits: Dict[str, int] = Field(default_factory=dict)
    
    @property
    def is_viewing_platform_tenant(self) -> bool:
        """Check if currently viewing the platform tenant"""
        return str(self.tenant_id) == settings.platform_tenant_id
    
    @property
    def can_manage_all_tenants(self) -> bool:
        """Check if user can manage all tenants"""
        return self.is_platform_admin and self.is_viewing_platform_tenant
    
    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """Check if user can access a specific tenant"""
        if self.is_platform_admin:
            return True
        return str(self.tenant_id) == str(target_tenant_id)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        permission_map = {
            "read": [Role.VIEWER, Role.OPERATOR, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "write": [Role.OPERATOR, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "manage": [Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "admin": [Role.OWNER, Role.PLATFORM_ADMIN],
            "platform": [Role.PLATFORM_ADMIN]
        }
        
        allowed_roles = permission_map.get(permission, [])
        return self.role in allowed_roles
    
    def get_db_session(self) -> TenantAwareSession:
        """Get a database session with this tenant context"""
        return TenantAwareSession(
            tenant_id=str(self.tenant_id),
            is_platform_admin=self.is_platform_admin,
            user_role=self.role.name
        )

async def get_tenant_context(
    current_user: dict = Depends(get_current_user),
    tenant_slug: Optional[str] = None,  # Allow switching for platform admins
    db: AsyncSession = Depends(get_db)
) -> TenantContext:
    """Get tenant context for the current request"""
    
    # Get user's tenant membership
    query = select(UserMembership, Tenant).join(
        Tenant, UserMembership.tenant_id == Tenant.id
    ).where(
        UserMembership.user_id == current_user["id"]
    )
    
    # If tenant_slug provided and user is platform admin, use that tenant
    if tenant_slug and current_user.get("is_platform_admin"):
        query = query.where(Tenant.slug == tenant_slug)
    else:
        query = query.where(UserMembership.tenant_id == current_user["tenant_id"])
    
    result = await db.execute(query)
    membership, tenant = result.first()
    
    if not membership or not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No valid tenant membership found"
        )
    
    # Build tenant context
    context = TenantContext(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        tenant_slug=tenant.slug,
        tenant_type=TenantType(tenant.type),
        user_id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        role=Role[membership.role.upper()],
        is_platform_admin=membership.role == "platform_admin",
        is_cross_tenant_access=(
            membership.role == "platform_admin" and 
            tenant_slug and 
            tenant_slug != current_user.get("default_tenant_slug")
        ),
        subscription_tier=tenant.subscription_tier,
        features=tenant.features or {},
        limits=tenant.limits or {}
    )
    
    # Apply RLS context to the session
    if settings.enable_rls:
        await db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(context.tenant_id)}
        )
        await db.execute(
            text("SET LOCAL app.is_platform_admin = :is_admin"),
            {"is_admin": context.is_platform_admin}
        )
    
    return context

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant: TenantContext = kwargs.get("tenant")
            if not tenant or not tenant.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### Day 2-3: Service Layer

#### `backend/src/services/device_service_v6.py`
```python
"""Device management service with V6 tenant scoping"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..core.tenant_context import TenantContext
from ..models.device import SensorDevice, DisplayDevice, DeviceAssignment
from ..models.space import Space
from ..models.chirpstack import ChirpStackSync
from ..services.audit_service import AuditService
from ..services.cache_service import CacheService
from ..exceptions import (
    DeviceNotFoundError,
    TenantAccessError,
    DeviceAlreadyAssignedError,
    TenantMismatchError
)

logger = logging.getLogger(__name__)

class DeviceServiceV6:
    """Unified device management with tenant scoping"""
    
    def __init__(self, db: AsyncSession, tenant: TenantContext):
        self.db = db
        self.tenant = tenant
        self.audit = AuditService(db, tenant)
        self.cache = CacheService()
    
    async def list_devices(
        self,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        include_unassigned: bool = True,
        include_assigned: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List devices with proper V6 tenant scoping"""
        
        # Build base query
        query = select(SensorDevice)
        
        # Tenant scoping (RLS will also enforce this)
        if self.tenant.is_viewing_platform_tenant and self.tenant.is_platform_admin:
            # Platform admin viewing platform tenant: see ALL devices
            logger.info("Platform admin viewing all devices across tenants")
        else:
            # Regular tenant view or platform admin viewing specific tenant
            query = query.where(SensorDevice.tenant_id == self.tenant.tenant_id)
        
        # Status filters
        status_filters = []
        if status:
            query = query.where(SensorDevice.status == status)
        else:
            if include_unassigned:
                status_filters.append(SensorDevice.status == 'unassigned')
            if include_assigned:
                status_filters.append(SensorDevice.status == 'assigned')
            
            if status_filters:
                query = query.where(or_(*status_filters))
        
        # Device type filter
        if device_type:
            query = query.where(SensorDevice.device_type == device_type)
        
        # Add ordering and pagination
        query = query.order_by(SensorDevice.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await self.db.execute(query)
        devices = result.scalars().all()
        
        # Get total count
        count_query = select(func.count()).select_from(SensorDevice)
        if not (self.tenant.is_viewing_platform_tenant and self.tenant.is_platform_admin):
            count_query = count_query.where(SensorDevice.tenant_id == self.tenant.tenant_id)
        
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar()
        
        # Build response
        return {
            "devices": [self._device_to_dict(d) for d in devices],
            "count": len(devices),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "tenant_scope": str(self.tenant.tenant_id),
            "is_cross_tenant": self.tenant.is_platform_admin and self.tenant.is_viewing_platform_tenant
        }
    
    async def get_device(self, device_id: UUID) -> Dict[str, Any]:
        """Get a specific device with tenant access check"""
        device = await self.db.get(SensorDevice, device_id)
        
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        if not self.tenant.can_access_tenant(device.tenant_id):
            raise TenantAccessError("Cannot access device from another tenant")
        
        return self._device_to_dict(device)
    
    async def assign_device_to_space(
        self,
        device_id: UUID,
        space_id: UUID,
        assignment_reason: str = None
    ) -> Dict[str, Any]:
        """Assign a device to a space with full V6 validation"""
        
        # Get device
        device = await self.db.get(SensorDevice, device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        # Verify tenant access
        if not self.tenant.can_access_tenant(device.tenant_id):
            raise TenantAccessError("Cannot access device from another tenant")
        
        # Get space
        space = await self.db.get(Space, space_id)
        if not space:
            raise DeviceNotFoundError(f"Space {space_id} not found")
        
        # Verify same tenant
        if device.tenant_id != space.tenant_id:
            raise TenantMismatchError("Device and space must belong to same tenant")
        
        # Check if already assigned
        if device.status == 'assigned' and device.assigned_space_id:
            raise DeviceAlreadyAssignedError(
                f"Device {device.dev_eui} already assigned to space {device.assigned_space_id}"
            )
        
        # Update device
        old_values = {
            "status": device.status,
            "assigned_space_id": str(device.assigned_space_id) if device.assigned_space_id else None
        }
        
        device.status = 'assigned'
        device.assigned_space_id = space_id
        device.assigned_at = datetime.utcnow()
        device.lifecycle_state = 'operational'
        
        # Update space
        space.sensor_device_id = device_id
        
        # Create assignment history
        assignment = DeviceAssignment(
            tenant_id=device.tenant_id,
            device_type='sensor',
            device_id=device_id,
            dev_eui=device.dev_eui,
            space_id=space_id,
            assigned_by=self.tenant.user_id,
            assignment_reason=assignment_reason or "Manual assignment via API"
        )
        self.db.add(assignment)
        
        # Queue ChirpStack sync
        await self._queue_chirpstack_sync(device_id, 'device')
        
        # Audit log
        await self.audit.log_action(
            action="device.assign",
            resource_type="device",
            resource_id=str(device_id),
            old_values=old_values,
            new_values={
                "status": "assigned",
                "assigned_space_id": str(space_id)
            }
        )
        
        await self.db.commit()
        
        # Invalidate cache
        await self.cache.invalidate(f"device:{device_id}")
        await self.cache.invalidate(f"space:{space_id}")
        
        return {
            "success": True,
            "device_id": str(device_id),
            "space_id": str(space_id),
            "assignment_id": str(assignment.id),
            "message": f"Device {device.dev_eui} assigned to space {space.code}"
        }
    
    async def unassign_device(
        self,
        device_id: UUID,
        reason: str = None
    ) -> Dict[str, Any]:
        """Unassign a device from its space"""
        
        device = await self.db.get(SensorDevice, device_id)
        if not device:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        
        if not self.tenant.can_access_tenant(device.tenant_id):
            raise TenantAccessError("Cannot access device from another tenant")
        
        if device.status != 'assigned':
            return {
                "success": False,
                "message": "Device is not currently assigned"
            }
        
        # Find current assignment
        query = select(DeviceAssignment).where(
            and_(
                DeviceAssignment.device_id == device_id,
                DeviceAssignment.unassigned_at.is_(None)
            )
        )
        result = await self.db.execute(query)
        current_assignment = result.scalar_one_or_none()
        
        # Update assignment history
        if current_assignment:
            current_assignment.unassigned_at = datetime.utcnow()
            current_assignment.unassigned_by = self.tenant.user_id
            current_assignment.unassignment_reason = reason or "Manual unassignment via API"
        
        # Clear space reference
        if device.assigned_space_id:
            space = await self.db.get(Space, device.assigned_space_id)
            if space and space.sensor_device_id == device_id:
                space.sensor_device_id = None
        
        # Update device
        old_space_id = device.assigned_space_id
        device.status = 'unassigned'
        device.assigned_space_id = None
        device.lifecycle_state = 'commissioned'
        
        # Audit log
        await self.audit.log_action(
            action="device.unassign",
            resource_type="device",
            resource_id=str(device_id),
            old_values={"assigned_space_id": str(old_space_id)},
            new_values={"assigned_space_id": None}
        )
        
        await self.db.commit()
        
        return {
            "success": True,
            "device_id": str(device_id),
            "message": f"Device {device.dev_eui} unassigned successfully"
        }
    
    async def get_device_pool_stats(self) -> Dict[str, Any]:
        """Get device pool statistics (platform admin only)"""
        if not self.tenant.is_platform_admin:
            raise TenantAccessError("Only platform admins can view device pool stats")
        
        # Query all devices grouped by tenant and status
        query = """
            SELECT 
                t.name as tenant_name,
                t.id as tenant_id,
                sd.status,
                sd.device_type,
                COUNT(*) as count
            FROM sensor_devices sd
            JOIN tenants t ON t.id = sd.tenant_id
            GROUP BY t.id, t.name, sd.status, sd.device_type
            ORDER BY t.name, sd.status
        """
        
        result = await self.db.execute(text(query))
        rows = result.fetchall()
        
        # Process results
        by_tenant = {}
        total_devices = 0
        total_assigned = 0
        total_unassigned = 0
        
        for row in rows:
            tenant_name = row.tenant_name
            if tenant_name not in by_tenant:
                by_tenant[tenant_name] = {
                    "tenant_id": str(row.tenant_id),
                    "total": 0,
                    "assigned": 0,
                    "unassigned": 0,
                    "by_type": {}
                }
            
            by_tenant[tenant_name]["total"] += row.count
            total_devices += row.count
            
            if row.status == 'assigned':
                by_tenant[tenant_name]["assigned"] += row.count
                total_assigned += row.count
            elif row.status == 'unassigned':
                by_tenant[tenant_name]["unassigned"] += row.count
                total_unassigned += row.count
            
            # Track by device type
            if row.device_type not in by_tenant[tenant_name]["by_type"]:
                by_tenant[tenant_name]["by_type"][row.device_type] = 0
            by_tenant[tenant_name]["by_type"][row.device_type] += row.count
        
        return {
            "total_devices": total_devices,
            "total_assigned": total_assigned,
            "total_unassigned": total_unassigned,
            "by_tenant": by_tenant,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _queue_chirpstack_sync(self, device_id: UUID, entity_type: str):
        """Queue a device for ChirpStack synchronization"""
        sync = ChirpStackSync(
            tenant_id=self.tenant.tenant_id,
            entity_type=entity_type,
            entity_id=device_id,
            chirpstack_id=str(device_id),  # Will be updated by sync service
            sync_status='pending',
            sync_direction='push'
        )
        self.db.add(sync)
    
    def _device_to_dict(self, device) -> Dict[str, Any]:
        """Convert device model to dictionary"""
        return {
            "id": str(device.id),
            "tenant_id": str(device.tenant_id),
            "dev_eui": device.dev_eui,
            "name": device.name,
            "device_type": device.device_type,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "status": device.status,
            "lifecycle_state": device.lifecycle_state,
            "assigned_space_id": str(device.assigned_space_id) if device.assigned_space_id else None,
            "assigned_at": device.assigned_at.isoformat() if device.assigned_at else None,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
            "enabled": device.enabled,
            "config": device.config,
            "created_at": device.created_at.isoformat(),
            "updated_at": device.updated_at.isoformat()
        }
```

### Day 4-5: V5.3 Feature Services

#### `backend/src/services/reservation_service.py`
```python
"""Reservation service with idempotency and overlap prevention"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import logging

from ..core.tenant_context import TenantContext
from ..models.reservation import Reservation
from ..models.space import Space
from ..exceptions import (
    SpaceNotFoundError,
    ReservationOverlapError,
    InvalidTimeRangeError
)

logger = logging.getLogger(__name__)

class ReservationService:
    """Reservation management with V5.3 features"""
    
    def __init__(self, db: AsyncSession, tenant: TenantContext):
        self.db = db
        self.tenant = tenant
    
    async def create_reservation(
        self,
        space_id: UUID,
        start_time: datetime,
        end_time: datetime,
        user_email: str,
        user_phone: Optional[str] = None,
        request_id: Optional[UUID] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create reservation with idempotency and overlap prevention"""
        
        # Validate time range
        if end_time <= start_time:
            raise InvalidTimeRangeError("End time must be after start time")
        
        if end_time - start_time > timedelta(hours=24):
            raise InvalidTimeRangeError("Maximum reservation duration is 24 hours")
        
        # Check if idempotent request
        if request_id:
            existing = await self.db.execute(
                select(Reservation).where(
                    and_(
                        Reservation.request_id == request_id,
                        Reservation.tenant_id == self.tenant.tenant_id
                    )
                )
            )
            if existing_reservation := existing.scalar_one_or_none():
                # Return existing reservation (idempotency)
                return self._reservation_to_dict(existing_reservation)
        
        # Verify space exists and belongs to tenant
        space = await self.db.get(Space, space_id)
        if not space:
            raise SpaceNotFoundError(f"Space {space_id} not found")
        
        if space.tenant_id != self.tenant.tenant_id:
            raise TenantAccessError("Cannot reserve space from another tenant")
        
        # Create reservation (DB constraint will prevent overlaps)
        reservation = Reservation(
            tenant_id=self.tenant.tenant_id,
            space_id=space_id,
            start_time=start_time,
            end_time=end_time,
            user_email=user_email,
            user_phone=user_phone,
            request_id=request_id,
            status='confirmed',
            metadata=metadata or {}
        )
        
        try:
            self.db.add(reservation)
            await self.db.commit()
            
            # Update space state if reservation is current
            now = datetime.utcnow()
            if start_time <= now <= end_time:
                space.current_state = 'reserved'
                await self.db.commit()
            
            return self._reservation_to_dict(reservation)
            
        except IntegrityError as e:
            await self.db.rollback()
            if 'reservations_no_overlap' in str(e):
                raise ReservationOverlapError(
                    "Time slot overlaps with existing reservation"
                )
            raise
    
    async def check_availability(
        self,
        space_id: UUID,
        from_time: datetime,
        to_time: datetime
    ) -> Dict[str, Any]:
        """Check space availability for time range"""
        
        # Verify space
        space = await self.db.get(Space, space_id)
        if not space:
            raise SpaceNotFoundError(f"Space {space_id} not found")
        
        # Find overlapping reservations
        query = select(Reservation).where(
            and_(
                Reservation.space_id == space_id,
                Reservation.status.in_(['pending', 'confirmed']),
                or_(
                    and_(
                        Reservation.start_time <= from_time,
                        Reservation.end_time > from_time
                    ),
                    and_(
                        Reservation.start_time < to_time,
                        Reservation.end_time >= to_time
                    ),
                    and_(
                        Reservation.start_time >= from_time,
                        Reservation.end_time <= to_time
                    )
                )
            )
        )
        
        result = await self.db.execute(query)
        overlapping = result.scalars().all()
        
        return {
            "space_id": str(space_id),
            "space_code": space.code,
            "space_name": space.name,
            "query_start": from_time.isoformat(),
            "query_end": to_time.isoformat(),
            "is_available": len(overlapping) == 0,
            "reservations": [self._reservation_to_dict(r) for r in overlapping],
            "current_state": space.current_state
        }
    
    async def expire_old_reservations(self):
        """Background job to expire old reservations"""
        now = datetime.utcnow()
        
        query = select(Reservation).where(
            and_(
                Reservation.end_time < now,
                Reservation.status == 'confirmed'
            )
        )
        
        result = await self.db.execute(query)
        expired = result.scalars().all()
        
        for reservation in expired:
            reservation.status = 'expired'
            
            # Update space state if it was reserved
            space = await self.db.get(Space, reservation.space_id)
            if space and space.current_state == 'reserved':
                # Check if there's another active reservation
                active_query = select(Reservation).where(
                    and_(
                        Reservation.space_id == reservation.space_id,
                        Reservation.status == 'confirmed',
                        Reservation.start_time <= now,
                        Reservation.end_time > now
                    )
                )
                active_result = await self.db.execute(active_query)
                
                if not active_result.scalar_one_or_none():
                    # No active reservation, set to free
                    space.current_state = 'free'
        
        await self.db.commit()
        
        logger.info(f"Expired {len(expired)} reservations")
        return len(expired)
    
    def _reservation_to_dict(self, reservation) -> Dict[str, Any]:
        """Convert reservation to dictionary"""
        return {
            "id": str(reservation.id),
            "tenant_id": str(reservation.tenant_id),
            "space_id": str(reservation.space_id),
            "start_time": reservation.start_time.isoformat(),
            "end_time": reservation.end_time.isoformat(),
            "user_email": reservation.user_email,
            "user_phone": reservation.user_phone,
            "status": reservation.status,
            "request_id": str(reservation.request_id) if reservation.request_id else None,
            "metadata": reservation.metadata,
            "created_at": reservation.created_at.isoformat()
        }
```

---

## 🌐 Phase 3: API Implementation (Week 3-4)

### Day 1: Main Application

#### `backend/src/main.py`
```python
"""Main FastAPI application with V6 and V5 compatibility"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn
from prometheus_client import make_asgi_app

from .core.config import settings
from .core.database import init_db, close_db
from .middleware.tenant import TenantMiddleware
from .middleware.request_id import RequestIDMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routers.v6 import devices, gateways, dashboard, spaces, reservations
from .routers.v5_compat import (
    devices as v5_devices,
    spaces as v5_spaces,
    reservations as v5_reservations,
    uplink as v5_uplink
)
from .routers.auth import auth_router
from .routers.health import health_router
from .services.background_tasks import start_background_tasks, stop_background_tasks

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    await start_background_tasks()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await stop_background_tasks()
    await close_db()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(TenantMiddleware)

if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# Mount Prometheus metrics
if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# Register routers

# Authentication & Health
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(health_router, tags=["health"])

# V6 API endpoints
if settings.use_v6_api:
    app.include_router(devices.router, prefix="/api/v6", tags=["devices-v6"])
    app.include_router(gateways.router, prefix="/api/v6", tags=["gateways-v6"])
    app.include_router(dashboard.router, prefix="/api/v6", tags=["dashboard-v6"])
    app.include_router(spaces.router, prefix="/api/v6", tags=["spaces-v6"])
    app.include_router(reservations.router, prefix="/api/v6", tags=["reservations-v6"])

# V5 compatibility endpoints
app.include_router(v5_devices.router, prefix="/api/v1", tags=["devices-v5"])
app.include_router(v5_spaces.router, prefix="/api/v1", tags=["spaces-v5"])
app.include_router(v5_reservations.router, prefix="/api/v1", tags=["reservations-v5"])
app.include_router(v5_uplink.router, prefix="/api/v1", tags=["webhook-v5"])

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None
        }
    )

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_versions": ["v6", "v1"] if settings.use_v6_api else ["v1"],
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
```

### Day 2: V6 API Routers

#### `backend/src/routers/v6/devices.py`
```python
"""V6 Device management endpoints"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.tenant_context import get_tenant_context, TenantContext, require_permission
from ...services.device_service_v6 import DeviceServiceV6
from ...schemas.device import (
    DeviceResponse,
    DeviceListResponse,
    AssignDeviceRequest,
    DevicePoolStatsResponse
)

router = APIRouter(prefix="/devices")

@router.get("/", response_model=DeviceListResponse)
async def list_devices(
    status: Optional[str] = Query(None, description="Filter by status"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    assigned_only: bool = Query(False, description="Show only assigned devices"),
    unassigned_only: bool = Query(False, description="Show only unassigned devices"),
    include_stats: bool = Query(False, description="Include usage statistics"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    List devices with V6 tenant scoping
    
    Behavior:
    - Regular users: See only their tenant's devices
    - Platform admin on platform tenant: See ALL devices across ALL tenants
    - Platform admin on customer tenant: See only that tenant's devices
    """
    service = DeviceServiceV6(db, tenant)
    
    result = await service.list_devices(
        device_type=device_type,
        status=status,
        include_assigned=not unassigned_only,
        include_unassigned=not assigned_only,
        limit=limit,
        offset=offset
    )
    
    return DeviceListResponse(**result)

@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Get device details"""
    service = DeviceServiceV6(db, tenant)
    device = await service.get_device(device_id)
    return DeviceResponse(**device)

@router.post("/{device_id}/assign")
async def assign_device(
    device_id: UUID,
    request: AssignDeviceRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Assign device to space"""
    if not tenant.has_permission("manage"):
        raise HTTPException(403, "Insufficient permissions")
    
    service = DeviceServiceV6(db, tenant)
    
    try:
        result = await service.assign_device_to_space(
            device_id=device_id,
            space_id=request.space_id,
            assignment_reason=request.reason
        )
        return result
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/{device_id}/unassign")
async def unassign_device(
    device_id: UUID,
    reason: Optional[str] = None,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """Unassign device from space"""
    if not tenant.has_permission("manage"):
        raise HTTPException(403, "Insufficient permissions")
    
    service = DeviceServiceV6(db, tenant)
    
    try:
        result = await service.unassign_device(
            device_id=device_id,
            reason=reason
        )
        return result
    except Exception as e:
        raise HTTPException(400, str(e))

@router.get("/pool/stats", response_model=DevicePoolStatsResponse)
async def get_device_pool_stats(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Get device pool statistics (Platform Admin only)
    Shows distribution of devices across all tenants
    """
    if not tenant.is_platform_admin:
        raise HTTPException(403, "Only platform admins can view pool statistics")
    
    service = DeviceServiceV6(db, tenant)
    stats = await service.get_device_pool_stats()
    
    return DevicePoolStatsResponse(**stats)
```

---

## 🧪 Phase 4: Testing & Integration (Week 4)

### Testing Strategy

#### `tests/unit/test_device_service.py`
```python
"""Unit tests for device service"""

import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from src.services.device_service_v6 import DeviceServiceV6
from src.core.tenant_context import TenantContext, Role

@pytest.fixture
def mock_tenant():
    return TenantContext(
        tenant_id=uuid4(),
        tenant_name="Test Tenant",
        tenant_slug="test",
        tenant_type="customer",
        user_id=uuid4(),
        username="testuser",
        email="test@example.com",
        role=Role.ADMIN,
        is_platform_admin=False
    )

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_list_devices_tenant_scoped(mock_db, mock_tenant):
    """Test that regular users only see their tenant's devices"""
    service = DeviceServiceV6(mock_db, mock_tenant)
    
    # Mock database response
    mock_devices = [Mock(tenant_id=mock_tenant.tenant_id) for _ in range(3)]
    mock_db.execute.return_value.scalars.return_value.all.return_value = mock_devices
    mock_db.execute.return_value.scalar.return_value = 3
    
    result = await service.list_devices()
    
    assert result["count"] == 3
    assert result["tenant_scope"] == str(mock_tenant.tenant_id)
    assert not result["is_cross_tenant"]

@pytest.mark.asyncio
async def test_assign_device_validates_tenant(mock_db, mock_tenant):
    """Test that device assignment validates tenant ownership"""
    service = DeviceServiceV6(mock_db, mock_tenant)
    
    device_id = uuid4()
    space_id = uuid4()
    
    # Mock device with different tenant
    mock_device = Mock(
        id=device_id,
        tenant_id=uuid4(),  # Different tenant
        status="unassigned"
    )
    mock_db.get.return_value = mock_device
    
    with pytest.raises(TenantAccessError):
        await service.assign_device_to_space(device_id, space_id)
```

---

## 📊 Phase 5: Deployment & Migration (Week 5)

### Deployment Configuration

#### `deployment/docker-compose.prod.yml`
```yaml
version: '3.8'

services:
  api:
    image: parking-v6:latest
    environment:
      - DATABASE_URL=postgresql://parking_user:${DB_PASSWORD}@postgres:5432/parking_v6
      - USE_V6_API=true
      - ENABLE_RLS=true
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

### Migration Script

#### `scripts/migrate_v5_to_v6.sh`
```bash
#!/bin/bash

echo "Starting V5 to V6 migration..."

# Backup V5 database
echo "Creating backup..."
pg_dump -h localhost -U parking_user parking_v5 > backup_v5_$(date +%Y%m%d).sql

# Run migrations
echo "Running migrations..."
for migration in migrations/*.sql; do
    echo "Applying $migration..."
    psql -h localhost -U parking_user -d parking_v6 -f $migration
done

# Validate migration
echo "Validating migration..."
python scripts/validate_migration.py

echo "Migration complete!"
```

---

## 📈 Success Metrics & Monitoring

### Key Performance Indicators

| Metric | V5.3 Baseline | V6 Target | Measurement |
|--------|---------------|-----------|-------------|
| Device List API Response | 800ms | <200ms | p95 latency |
| Device Assignment | 400ms | <100ms | p95 latency |
| Dashboard Load | 3s | <1s | Time to interactive |
| Database CPU Usage | 40% | <20% | Average CPU |
| Tenant Isolation Violations | N/A | 0 | Security audit |
| Cross-tenant Query Time | 2s | <500ms | Platform admin |

### Monitoring Dashboard

```python
# backend/src/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge
import time

# Request metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])

# Device metrics
device_operations = Counter('device_operations_total', 'Device operations', ['operation', 'status'])
device_pool_size = Gauge('device_pool_size', 'Total devices in pool', ['tenant', 'status'])

# Tenant metrics
active_tenants = Gauge('active_tenants_total', 'Number of active tenants')
tenant_api_calls = Counter('tenant_api_calls_total', 'API calls per tenant', ['tenant_id', 'endpoint'])

# Database metrics
db_pool_size = Gauge('db_connection_pool_size', 'Database connection pool size')
db_pool_used = Gauge('db_connection_pool_used', 'Used database connections')
```

---

## 🚀 Go-Live Checklist

### Pre-Production
- [ ] All migrations tested on staging
- [ ] Load testing completed (1000+ concurrent users)
- [ ] Security audit passed
- [ ] Backup procedures tested
- [ ] Rollback plan validated
- [ ] Documentation updated
- [ ] Team training completed

### Production Deployment
- [ ] Database backup created
- [ ] Feature flags configured
- [ ] Monitoring alerts set up
- [ ] Health checks passing
- [ ] V5 compatibility verified
- [ ] Platform admin UI tested
- [ ] Tenant isolation verified

### Post-Deployment
- [ ] Monitor error rates (target <0.1%)
- [ ] Check performance metrics
- [ ] Verify tenant data isolation
- [ ] Test V5 endpoint compatibility
- [ ] Review audit logs
- [ ] Update status page

---

## 📝 Summary

This complete implementation plan provides:

1. **Full feature parity with V5.3** - All 60+ endpoints, authentication, reservations, webhooks, etc.
2. **V6 architectural improvements** - Direct tenant ownership, RLS, efficient queries
3. **Backward compatibility** - V5 endpoints remain functional during migration
4. **Comprehensive testing** - Unit, integration, load, and security tests
5. **Production-ready deployment** - Docker, monitoring, rollback procedures

The plan is executable immediately and will result in a fully functional V6 system that exceeds V5.3 capabilities while maintaining all existing features.

**Total Estimated Effort**: 
- 2 developers: 4-6 weeks
- 1 developer: 8-10 weeks

**Next Steps**:
1. Set up the project structure
2. Run database migrations
3. Implement core services
4. Deploy to staging
5. Gradual production rollout
