# Multi-Tenancy Implementation Plan

**Smart Parking Platform - Customer Data Isolation**  
**Version:** 1.0  
**Date:** 2025-10-13  
**Priority:** HIGH - Foundation for SaaS business model  
**Duration:** 8-10 weeks  

---

## Executive Summary

### Goal
Enable **multiple customers** to use the same Smart Parking Platform instance while ensuring **100% data isolation** - **ZERO risk** of cross-customer data access.

### Architecture Approach: **Row-Level Security (RLS) + Tenant Context**

We will implement **PostgreSQL Row-Level Security (RLS)** combined with **tenant-scoped API authentication** to guarantee data isolation at the database level, not just application level.

### Security Guarantee

✅ **Database-enforced isolation** - PostgreSQL prevents cross-tenant queries  
✅ **Zero-trust architecture** - Even if application has bugs, database blocks cross-tenant access  
✅ **Auditable access** - Every query logged with tenant ID  
✅ **Compliance-ready** - GDPR data separation guaranteed  

---

## Current State vs Target State

### Current State (Single Tenant)

```
┌─────────────────────────────────────┐
│    Smart Parking Platform           │
│                                      │
│  All Data Shared:                   │
│  - parking_spaces.spaces (all)      │
│  - devices.sensors (all)            │
│  - reservations (all)               │
│  - analytics (all)                  │
└─────────────────────────────────────┘
```

### Target State (Multi-Tenant)

```
┌─────────────────────────────────────────────────┐
│          Smart Parking Platform                 │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐│
│  │  Tenant A   │  │  Tenant B   │  │ Tenant C ││
│  │             │  │             │  │          ││
│  │ Spaces: 50  │  │ Spaces: 120 │  │ Spaces:30││
│  │ Devices: 75 │  │ Devices: 180│  │ Dev: 45  ││
│  └─────────────┘  └─────────────┘  └──────────┘│
│                                                  │
│  ✅ PostgreSQL RLS enforces isolation           │
│  ✅ Application validates tenant context         │
│  ✅ API keys scoped to tenant                    │
└─────────────────────────────────────────────────┘
```

---

## Multi-Tenancy Strategy

### Option 1: Database-per-Tenant ❌ NOT RECOMMENDED
- **Pros:** Perfect isolation
- **Cons:** 
  - Expensive (100 customers = 100 databases)
  - Complex deployments
  - Schema migrations nightmare
  - Resource waste

### Option 2: Schema-per-Tenant ⚠️ MEDIUM OPTION
- **Pros:** Good isolation, easier than database-per-tenant
- **Cons:**
  - Still complex migrations
  - Connection pool per schema
  - Limited scalability

### Option 3: Row-Level Security (RLS) ✅ **RECOMMENDED**
- **Pros:**
  - Single database, easy management
  - PostgreSQL-enforced isolation (NOT application-level)
  - Scalable to 1000+ tenants
  - Simple migrations
  - Cost-effective
- **Cons:**
  - Requires PostgreSQL 9.5+ (we have 16 ✅)
  - Must set tenant context on every connection

---

## Architecture Design

### Database Schema Changes

#### Step 1: Add tenant_id to All Tables

**Affected tables:**
- `parking_spaces.spaces`
- `parking_spaces.reservations`
- `parking_config.sensor_registry`
- `parking_config.display_registry`
- `devices.sensors`
- `devices.gateways`
- `analytics.measurements`
- `ingest.raw_uplinks`
- `parking_operations.actuations`

**Migration:**
```sql
-- 1. Create tenants table
CREATE TABLE core.tenants (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_name VARCHAR(255) NOT NULL UNIQUE,
    tenant_slug VARCHAR(100) NOT NULL UNIQUE,
    contact_email VARCHAR(255) NOT NULL,
    
    -- Subscription details
    subscription_tier VARCHAR(50) DEFAULT 'basic',
    max_parking_spaces INT DEFAULT 100,
    max_devices INT DEFAULT 200,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Metadata
    tenant_metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_tenants_slug ON core.tenants(tenant_slug);
CREATE INDEX idx_tenants_active ON core.tenants(is_active);

-- 2. Add tenant_id to parking_spaces.spaces
ALTER TABLE parking_spaces.spaces 
ADD COLUMN tenant_id UUID REFERENCES core.tenants(tenant_id);

-- For existing data, create default tenant
INSERT INTO core.tenants (tenant_name, tenant_slug, contact_email)
VALUES ('Default Organization', 'default', 'admin@verdegris.eu')
RETURNING tenant_id;

-- Assign existing data to default tenant
UPDATE parking_spaces.spaces 
SET tenant_id = (SELECT tenant_id FROM core.tenants WHERE tenant_slug = 'default');

-- Make tenant_id NOT NULL after backfill
ALTER TABLE parking_spaces.spaces 
ALTER COLUMN tenant_id SET NOT NULL;

-- Add composite indexes (tenant_id + primary key)
CREATE INDEX idx_spaces_tenant_id ON parking_spaces.spaces(tenant_id, space_id);

-- 3. Repeat for all tables
-- (reservations, sensors, devices, measurements, etc.)
```

#### Step 2: Enable Row-Level Security

**Critical concept:** RLS policies are enforced **at the database level**, even if application code has bugs.

```sql
-- Enable RLS on parking_spaces.spaces
ALTER TABLE parking_spaces.spaces ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see rows for their tenant
CREATE POLICY tenant_isolation_policy ON parking_spaces.spaces
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Policy: Superusers can see all (for admin/support)
CREATE POLICY admin_all_access_policy ON parking_spaces.spaces
    FOR ALL
    TO admin_role
    USING (true);

-- Repeat for all multi-tenant tables
ALTER TABLE parking_spaces.reservations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON parking_spaces.reservations
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

ALTER TABLE parking_config.sensor_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON parking_config.sensor_registry
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ... repeat for all tables ...
```

#### Step 3: Set Tenant Context on Connection

**This is the KEY security mechanism:**

```python
# shared/database/tenant_context.py
import asyncpg
from contextlib import asynccontextmanager
import logging
from uuid import UUID

logger = logging.getLogger("tenant_context")

class TenantContext:
    """
    Manages tenant context for database connections
    
    SECURITY: This sets PostgreSQL session variable that RLS policies use
    """
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    @asynccontextmanager
    async def with_tenant(self, tenant_id: UUID):
        """
        Acquire connection and set tenant context
        
        Usage:
            async with tenant_context.with_tenant(tenant_id) as conn:
                # All queries on this connection are scoped to tenant_id
                result = await conn.fetch("SELECT * FROM parking_spaces.spaces")
                # RLS ensures only tenant_id's rows are returned
        """
        async with self.pool.acquire() as conn:
            try:
                # Set tenant context (CRITICAL FOR SECURITY)
                await conn.execute(
                    "SET LOCAL app.current_tenant_id = $1",
                    str(tenant_id)
                )
                
                logger.debug(f"✅ Tenant context set: {tenant_id}")
                
                yield conn
                
            except Exception as e:
                logger.error(f"❌ Error in tenant context: {e}")
                raise
            finally:
                # Context is automatically cleared when connection returns to pool
                pass
```

---

## API Authentication Changes

### Tenant-Scoped API Keys

**Current:** Single API key for entire platform  
**Target:** Each tenant has unique API key(s)

#### Database Schema for API Keys

```sql
CREATE TABLE core.api_keys (
    api_key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES core.tenants(tenant_id) ON DELETE CASCADE,
    
    -- Key details
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- bcrypt hash
    key_prefix VARCHAR(16) NOT NULL,  -- First 8 chars for identification
    key_name VARCHAR(100) NOT NULL,  -- "Production API Key", "Development Key"
    
    -- Permissions
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    rate_limit_per_minute INT DEFAULT 60,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_by VARCHAR(255),
    revoked_reason TEXT,
    
    -- Metadata
    key_metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_api_keys_tenant ON core.api_keys(tenant_id);
CREATE INDEX idx_api_keys_hash ON core.api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON core.api_keys(is_active);

-- Example: Create API key
INSERT INTO core.api_keys (tenant_id, key_hash, key_prefix, key_name)
VALUES (
    '123e4567-e89b-12d3-a456-426614174000',
    '$2b$12$...',  -- bcrypt hash of actual key
    'sp_live_',
    'Production API Key'
);
```

#### Updated Authentication Middleware

```python
# shared/auth/tenant_auth.py
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import secrets
import logging
from uuid import UUID
from shared.database.pool import db_pool

logger = logging.getLogger("tenant_auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

class TenantAuthResult:
    """Result of tenant authentication"""
    def __init__(self, tenant_id: UUID, tenant_slug: str, api_key_id: UUID, scopes: list):
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.api_key_id = api_key_id
        self.scopes = scopes

async def verify_tenant_api_key(
    api_key: str = Security(API_KEY_HEADER)
) -> TenantAuthResult:
    """
    Verify API key and return tenant context
    
    SECURITY CRITICAL:
    1. Looks up API key in database
    2. Validates key is active and not expired
    3. Returns tenant_id for RLS context
    4. Logs access for audit trail
    """
    
    if not api_key or len(api_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )
    
    # Extract key prefix for logging (first 8 chars)
    key_prefix = api_key[:8]
    
    # Query database for API key (using bcrypt comparison)
    query = """
        SELECT 
            ak.api_key_id,
            ak.tenant_id,
            t.tenant_slug,
            ak.scopes,
            ak.is_active,
            ak.expires_at,
            t.is_active as tenant_active
        FROM core.api_keys ak
        JOIN core.tenants t ON ak.tenant_id = t.tenant_id
        WHERE ak.key_hash = crypt($1, ak.key_hash)  -- bcrypt comparison
        LIMIT 1
    """
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, api_key)
    
    if not row:
        logger.warning(f"❌ Invalid API key attempt: {key_prefix}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    # Check if key is active
    if not row['is_active']:
        logger.warning(f"❌ Revoked API key used: {key_prefix}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has been revoked"
        )
    
    # Check if tenant is active
    if not row['tenant_active']:
        logger.warning(f"❌ Inactive tenant access attempt: {row['tenant_slug']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive"
        )
    
    # Check if key is expired
    if row['expires_at'] and row['expires_at'] < datetime.utcnow():
        logger.warning(f"❌ Expired API key used: {key_prefix}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has expired"
        )
    
    # Update last_used_at (fire and forget)
    asyncio.create_task(_update_key_last_used(row['api_key_id']))
    
    logger.info(f"✅ Authenticated: tenant={row['tenant_slug']} key={key_prefix}...")
    
    return TenantAuthResult(
        tenant_id=row['tenant_id'],
        tenant_slug=row['tenant_slug'],
        api_key_id=row['api_key_id'],
        scopes=row['scopes']
    )

async def _update_key_last_used(api_key_id: UUID):
    """Update last_used_at timestamp (background task)"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE core.api_keys 
                SET last_used_at = NOW() 
                WHERE api_key_id = $1
            """, api_key_id)
    except Exception as e:
        logger.warning(f"Failed to update last_used_at: {e}")
```

#### Tenant-Scoped Database Dependency

```python
# shared/database/tenant_db.py
from fastapi import Depends
from shared.auth.tenant_auth import verify_tenant_api_key, TenantAuthResult
from shared.database.tenant_context import TenantContext
from shared.database.pool import db_pool
from contextlib import asynccontextmanager

tenant_context = TenantContext(db_pool._pool)

@asynccontextmanager
async def get_tenant_db(
    auth: TenantAuthResult = Depends(verify_tenant_api_key)
):
    """
    FastAPI dependency: Returns database connection with tenant context
    
    Usage:
        @app.get("/v1/spaces")
        async def list_spaces(db = Depends(get_tenant_db)):
            # This query is automatically scoped to authenticated tenant
            spaces = await db.fetch("SELECT * FROM parking_spaces.spaces")
            # RLS ensures only tenant's spaces are returned
            return spaces
    
    SECURITY: Even if you write "SELECT * FROM spaces WHERE 1=1",
              PostgreSQL RLS will add "AND tenant_id = <current_tenant_id>"
    """
    async with tenant_context.with_tenant(auth.tenant_id) as conn:
        # Connection is now scoped to tenant
        yield conn
```

---

## Updated API Endpoints

### Example: List Parking Spaces (Tenant-Scoped)

**Before (Single Tenant):**
```python
@app.get("/v1/spaces")
async def list_spaces(db = Depends(get_db)):
    # Returns ALL spaces in database
    spaces = await db.fetch("SELECT * FROM parking_spaces.spaces")
    return {"spaces": spaces}
```

**After (Multi-Tenant):**
```python
from shared.database.tenant_db import get_tenant_db
from shared.auth.tenant_auth import verify_tenant_api_key, TenantAuthResult

@app.get("/v1/spaces")
async def list_spaces(
    auth: TenantAuthResult = Depends(verify_tenant_api_key),
    db = Depends(get_tenant_db)
):
    # RLS automatically filters to auth.tenant_id
    # Even though query doesn't mention tenant_id, RLS adds it
    spaces = await db.fetch("""
        SELECT 
            space_id, space_name, space_code, 
            building, floor, zone, current_state
        FROM parking_spaces.spaces
        WHERE enabled = TRUE
        ORDER BY space_name
    """)
    # PostgreSQL RLS adds: AND tenant_id = '<auth.tenant_id>'
    
    return {
        "tenant": auth.tenant_slug,
        "spaces": spaces,
        "count": len(spaces)
    }
```

### Example: Create Parking Space (Tenant-Scoped)

```python
@app.post("/v1/spaces")
async def create_space(
    space_data: SpaceCreateRequest,
    auth: TenantAuthResult = Depends(verify_tenant_api_key),
    db = Depends(get_tenant_db)
):
    # Insert with tenant_id from auth context
    space_id = await db.fetchval("""
        INSERT INTO parking_spaces.spaces (
            tenant_id, space_name, space_code, building, floor, zone
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING space_id
    """, 
        auth.tenant_id,  # ✅ Explicitly set tenant_id
        space_data.space_name,
        space_data.space_code,
        space_data.building,
        space_data.floor,
        space_data.zone
    )
    
    return {
        "status": "created",
        "space_id": space_id,
        "tenant": auth.tenant_slug
    }
```

---

## Testing Data Isolation

### Test Plan: Verify ZERO Cross-Tenant Access

#### Test 1: Cannot Read Other Tenant's Data

```python
# test_tenant_isolation.py
import pytest
import asyncpg
from uuid import uuid4

@pytest.mark.asyncio
async def test_cannot_read_other_tenant_data():
    """Verify RLS prevents cross-tenant reads"""
    
    # Setup: Create two tenants
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    
    async with db_pool.acquire() as conn:
        # Create tenant A
        await conn.execute("""
            INSERT INTO core.tenants (tenant_id, tenant_name, tenant_slug, contact_email)
            VALUES ($1, 'Tenant A', 'tenant-a', 'a@example.com')
        """, tenant_a_id)
        
        # Create tenant B
        await conn.execute("""
            INSERT INTO core.tenants (tenant_id, tenant_name, tenant_slug, contact_email)
            VALUES ($1, 'Tenant B', 'tenant-b', 'b@example.com')
        """, tenant_b_id)
        
        # Create space for tenant A
        await conn.execute("""
            INSERT INTO parking_spaces.spaces (tenant_id, space_name, space_code)
            VALUES ($1, 'Space A1', 'A1')
        """, tenant_a_id)
        
        # Create space for tenant B
        await conn.execute("""
            INSERT INTO parking_spaces.spaces (tenant_id, space_name, space_code)
            VALUES ($1, 'Space B1', 'B1')
        """, tenant_b_id)
    
    # Test: Tenant A tries to read data
    async with tenant_context.with_tenant(tenant_a_id) as conn:
        spaces = await conn.fetch("SELECT * FROM parking_spaces.spaces")
        
        # Should only see tenant A's space
        assert len(spaces) == 1
        assert spaces[0]['space_name'] == 'Space A1'
        # ✅ Cannot see 'Space B1' - RLS blocks it
    
    # Test: Tenant B tries to read data
    async with tenant_context.with_tenant(tenant_b_id) as conn:
        spaces = await conn.fetch("SELECT * FROM parking_spaces.spaces")
        
        # Should only see tenant B's space
        assert len(spaces) == 1
        assert spaces[0]['space_name'] == 'Space B1'
        # ✅ Cannot see 'Space A1' - RLS blocks it
    
    # Test: Try to bypass RLS (should fail)
    async with tenant_context.with_tenant(tenant_a_id) as conn:
        # Even if we try to explicitly query tenant B's data
        spaces = await conn.fetch("""
            SELECT * FROM parking_spaces.spaces 
            WHERE tenant_id = $1
        """, tenant_b_id)
        
        # RLS overrides our WHERE clause
        assert len(spaces) == 0  # ✅ Zero results - RLS wins
```

#### Test 2: Cannot Update Other Tenant's Data

```python
@pytest.mark.asyncio
async def test_cannot_update_other_tenant_data():
    """Verify RLS prevents cross-tenant updates"""
    
    # Setup: Tenant A's space
    space_id = await create_test_space(tenant_a_id, "Space A1")
    
    # Test: Tenant B tries to update tenant A's space
    async with tenant_context.with_tenant(tenant_b_id) as conn:
        result = await conn.execute("""
            UPDATE parking_spaces.spaces
            SET space_name = 'HACKED'
            WHERE space_id = $1
        """, space_id)
        
        # RLS prevents update - "UPDATE 0" (zero rows affected)
        assert "UPDATE 0" in result
    
    # Verify: Space still has original name
    async with tenant_context.with_tenant(tenant_a_id) as conn:
        space = await conn.fetchrow("""
            SELECT space_name FROM parking_spaces.spaces WHERE space_id = $1
        """, space_id)
        
        assert space['space_name'] == 'Space A1'  # ✅ Not changed
```

#### Test 3: Cannot Delete Other Tenant's Data

```python
@pytest.mark.asyncio
async def test_cannot_delete_other_tenant_data():
    """Verify RLS prevents cross-tenant deletes"""
    
    # Setup: Tenant A's space
    space_id = await create_test_space(tenant_a_id, "Space A1")
    
    # Test: Tenant B tries to delete tenant A's space
    async with tenant_context.with_tenant(tenant_b_id) as conn:
        result = await conn.execute("""
            DELETE FROM parking_spaces.spaces WHERE space_id = $1
        """, space_id)
        
        # RLS prevents delete - "DELETE 0"
        assert "DELETE 0" in result
    
    # Verify: Space still exists
    async with tenant_context.with_tenant(tenant_a_id) as conn:
        space = await conn.fetchrow("""
            SELECT * FROM parking_spaces.spaces WHERE space_id = $1
        """, space_id)
        
        assert space is not None  # ✅ Still exists
```

---

## Tenant Management API

### Admin-Only Endpoints

```python
# routers/admin/tenants.py
from fastapi import APIRouter, Depends, HTTPException
from shared.auth.rbac import require_role, Role
from shared.database.pool import db_pool
from uuid import UUID, uuid4
import secrets

router = APIRouter(prefix="/admin/tenants", tags=["admin"])

@router.post("/", dependencies=[Depends(require_role(Role.ADMIN))])
async def create_tenant(tenant_data: TenantCreateRequest):
    """Create new tenant (admin only)"""
    
    tenant_id = uuid4()
    
    # Generate API key for tenant
    api_key = f"sp_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(api_key)  # bcrypt
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # Create tenant
            await conn.execute("""
                INSERT INTO core.tenants 
                (tenant_id, tenant_name, tenant_slug, contact_email, subscription_tier)
                VALUES ($1, $2, $3, $4, $5)
            """, tenant_id, tenant_data.name, tenant_data.slug, 
                tenant_data.email, tenant_data.subscription_tier)
            
            # Create API key
            await conn.execute("""
                INSERT INTO core.api_keys 
                (tenant_id, key_hash, key_prefix, key_name)
                VALUES ($1, $2, $3, $4)
            """, tenant_id, key_hash, api_key[:8], "Primary API Key")
    
    return {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_data.slug,
        "api_key": api_key,  # ⚠️ Only shown once!
        "message": "Save API key securely - it won't be shown again"
    }

@router.get("/")
async def list_tenants(admin: Role = Depends(require_role(Role.ADMIN))):
    """List all tenants (admin only)"""
    
    async with db_pool.acquire() as conn:
        tenants = await conn.fetch("""
            SELECT 
                tenant_id, tenant_name, tenant_slug,
                contact_email, subscription_tier,
                is_active, created_at,
                (SELECT COUNT(*) FROM parking_spaces.spaces s 
                 WHERE s.tenant_id = t.tenant_id) as space_count,
                (SELECT COUNT(*) FROM core.api_keys ak 
                 WHERE ak.tenant_id = t.tenant_id AND ak.is_active = TRUE) as active_keys
            FROM core.tenants t
            ORDER BY created_at DESC
        """)
    
    return {"tenants": tenants, "count": len(tenants)}

@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    admin: Role = Depends(require_role(Role.ADMIN))
):
    """Get tenant details (admin only)"""
    
    async with db_pool.acquire() as conn:
        tenant = await conn.fetchrow("""
            SELECT * FROM core.tenants WHERE tenant_id = $1
        """, tenant_id)
        
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get usage statistics
        stats = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM parking_spaces.spaces 
                 WHERE tenant_id = $1) as total_spaces,
                (SELECT COUNT(*) FROM parking_spaces.reservations 
                 WHERE tenant_id = $1 AND status = 'active') as active_reservations,
                (SELECT COUNT(*) FROM devices.sensors 
                 WHERE tenant_id = $1) as total_sensors
        """, tenant_id)
        
        return {**dict(tenant), "usage_stats": dict(stats)}

@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: UUID,
    updates: TenantUpdateRequest,
    admin: Role = Depends(require_role(Role.ADMIN))
):
    """Update tenant (admin only)"""
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE core.tenants
            SET 
                tenant_name = COALESCE($2, tenant_name),
                subscription_tier = COALESCE($3, subscription_tier),
                max_parking_spaces = COALESCE($4, max_parking_spaces),
                is_active = COALESCE($5, is_active),
                updated_at = NOW()
            WHERE tenant_id = $1
        """, tenant_id, updates.name, updates.subscription_tier,
            updates.max_spaces, updates.is_active)
    
    return {"status": "updated", "tenant_id": tenant_id}
```

---

## Implementation Timeline

### Phase 1: Database Schema (Week 1-2)

- [ ] Create `core.tenants` table
- [ ] Create `core.api_keys` table
- [ ] Add `tenant_id` to all tables
- [ ] Backfill existing data to default tenant
- [ ] Create indexes
- [ ] Enable RLS on all tables
- [ ] Create RLS policies
- [ ] Test RLS policies

### Phase 2: Authentication (Week 3-4)

- [ ] Implement tenant-scoped API key system
- [ ] Create `TenantAuthResult` class
- [ ] Create `verify_tenant_api_key` middleware
- [ ] Create `get_tenant_db` dependency
- [ ] Update all endpoints to use tenant dependencies
- [ ] Test authentication flow

### Phase 3: API Migration (Week 5-6)

- [ ] Update parking-display service
- [ ] Update transform service
- [ ] Update ingest service (tenant-scoped uplinks)
- [ ] Update downlink service
- [ ] Test all endpoints

### Phase 4: Admin Features (Week 7)

- [ ] Create tenant management API
- [ ] Create API key management API
- [ ] Build admin UI for tenant management
- [ ] Test admin features

### Phase 5: Testing & Security (Week 8)

- [ ] Comprehensive isolation testing
- [ ] Penetration testing (attempt cross-tenant access)
- [ ] Performance testing (100+ tenants)
- [ ] Load testing
- [ ] Security audit

### Phase 6: Documentation (Week 9-10)

- [ ] API documentation updates
- [ ] Multi-tenancy architecture guide
- [ ] Tenant onboarding guide
- [ ] Migration guide for existing deployments

---

## Security Guarantees

### 1. Database-Level Isolation ✅

**PostgreSQL RLS enforces isolation:**
```sql
-- Tenant A connection
SET app.current_tenant_id = 'tenant-a-uuid';
SELECT * FROM parking_spaces.spaces;
-- Returns: Only tenant A's spaces (RLS filters automatically)

-- Even if attacker tries:
SELECT * FROM parking_spaces.spaces WHERE tenant_id = 'tenant-b-uuid';
-- Returns: Empty result (RLS overrides WHERE clause)
```

### 2. Zero Application-Level Trust ✅

**Even if application has SQL injection, RLS protects:**
```python
# Vulnerable code (hypothetical)
query = f"SELECT * FROM spaces WHERE name = '{user_input}'"
# If user_input = "' OR '1'='1"
# Query becomes: SELECT * FROM spaces WHERE name = '' OR '1'='1'

# BUT: RLS adds tenant filter
# Actual query: SELECT * FROM spaces WHERE name = '' OR '1'='1' 
#               AND tenant_id = '<current_tenant_id>'
# ✅ Still only returns current tenant's data
```

### 3. Audit Trail ✅

**Every API call logs tenant:**
```json
{
  "timestamp": "2025-10-13T14:30:00Z",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "tenant_slug": "acme-corp",
  "api_key_id": "key_abc123",
  "endpoint": "/v1/spaces",
  "method": "GET",
  "ip_address": "203.0.113.42"
}
```

### 4. API Key Scoping ✅

**API keys are cryptographically bound to tenant:**
- Each tenant has unique API key(s)
- Keys stored as bcrypt hashes
- Keys include tenant_id lookup
- Invalid key = no tenant context = no data access

---

## Performance Considerations

### Impact of RLS

**Query performance:**
- RLS adds `AND tenant_id = '...'` to every query
- With proper indexes, overhead is < 1ms
- No noticeable performance impact

**Index strategy:**
```sql
-- Composite indexes: (tenant_id, primary_key)
CREATE INDEX idx_spaces_tenant ON parking_spaces.spaces(tenant_id, space_id);
CREATE INDEX idx_reservations_tenant ON parking_spaces.reservations(tenant_id, reservation_id);

-- Query plan uses index efficiently
EXPLAIN SELECT * FROM parking_spaces.spaces WHERE tenant_id = '...';
-- Result: Index Scan using idx_spaces_tenant (cost=0.15..8.17 rows=1)
```

### Connection Pool

**Current:** Single pool for entire platform  
**Multi-tenant:** Same pool, set context per connection

```python
# No additional connection overhead
async with db_pool.acquire() as conn:
    await conn.execute("SET LOCAL app.current_tenant_id = $1", tenant_id)
    # ... queries ...
# Context cleared when connection returns to pool
```

---

## Migration Path for Existing Deployment

### Step 1: Add Schema (No Downtime)

```bash
# Run migration
psql -U parking_user -d parking_platform -f migrations/001_add_multi_tenancy.sql

# Backfill default tenant
psql -U parking_user -d parking_platform << 'SQL'
INSERT INTO core.tenants (tenant_name, tenant_slug, contact_email)
VALUES ('Verdegris', 'verdegris', 'admin@verdegris.eu');

UPDATE parking_spaces.spaces 
SET tenant_id = (SELECT tenant_id FROM core.tenants WHERE tenant_slug = 'verdegris');
SQL
```

### Step 2: Deploy Updated Services (Rolling)

```bash
# Deploy one service at a time
sudo docker compose build parking-display-service
sudo docker compose up -d parking-display-service

# Test
curl -H "X-API-Key: $VERDEGRIS_API_KEY" https://parking.verdegris.eu/v1/spaces

# If successful, deploy next service
sudo docker compose build transform-service
sudo docker compose up -d transform-service
```

### Step 3: Enable RLS (Maintenance Window)

```sql
-- Enable RLS on all tables
ALTER TABLE parking_spaces.spaces ENABLE ROW LEVEL SECURITY;
-- ... repeat for all tables ...

-- Create policies
CREATE POLICY tenant_isolation_policy ON parking_spaces.spaces
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### Step 4: Create Additional Tenants

```bash
# Via admin API
curl -X POST https://parking.verdegris.eu/admin/tenants \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ACME Corporation",
    "slug": "acme-corp",
    "email": "admin@acme.com",
    "subscription_tier": "enterprise"
  }'

# Response includes API key (save securely!)
{
  "tenant_id": "...",
  "api_key": "sp_live_abc123...",
  "message": "Save API key - won't be shown again"
}
```

---

## Cost Analysis

### Single Tenant vs Multi-Tenant

| Metric | Single Tenant (Current) | Multi-Tenant (1 instance, 100 customers) |
|--------|------------------------|-------------------------------------------|
| **Servers** | 1 VPS @ €50/month | 1 VPS @ €150/month (scaled up) |
| **Databases** | 1 PostgreSQL | 1 PostgreSQL (shared) |
| **Maintenance** | 1 deployment | 1 deployment (all customers updated) |
| **Cost per customer** | €50 | €1.50 |
| **Margin improvement** | - | 97% cost reduction per customer |

### SaaS Pricing Model

**Subscription Tiers:**
- **Basic:** €49/month - Up to 50 spaces, 75 devices
- **Professional:** €149/month - Up to 200 spaces, 300 devices
- **Enterprise:** €499/month - Unlimited spaces, priority support

**With 100 customers:**
- Revenue: €10,000 - €50,000/month
- Infrastructure: €150/month
- Margin: 99%+ after development amortization

---

## Compliance Benefits

### GDPR Data Residency

**Multi-tenant with RLS enables:**
- Tenant-specific data exports (GDPR Art. 20)
- Tenant-specific data deletion (GDPR Art. 17)
- Data portability per tenant
- Tenant-scoped audit logs

```sql
-- Export all data for tenant (GDPR compliance)
SELECT * FROM parking_spaces.spaces WHERE tenant_id = '<tenant_id>';
SELECT * FROM parking_spaces.reservations WHERE tenant_id = '<tenant_id>';
-- etc.

-- Delete all data for tenant
DELETE FROM parking_spaces.spaces WHERE tenant_id = '<tenant_id>';
DELETE FROM parking_spaces.reservations WHERE tenant_id = '<tenant_id>';
-- etc.
```

---

## Success Criteria

### Functional Requirements

- [ ] ✅ Can create 100+ tenants
- [ ] ✅ Each tenant has unique API key(s)
- [ ] ✅ Zero cross-tenant data access (proven by tests)
- [ ] ✅ Admin can view all tenants
- [ ] ✅ Tenants can only view their own data

### Performance Requirements

- [ ] ✅ RLS overhead < 5ms per query
- [ ] ✅ Support 1000+ concurrent API requests
- [ ] ✅ Query performance unchanged (with indexes)

### Security Requirements

- [ ] ✅ Pass penetration testing (no cross-tenant access)
- [ ] ✅ Audit logs capture all tenant actions
- [ ] ✅ API keys stored securely (bcrypt)
- [ ] ✅ RLS policies prevent bypass

---

## Next Steps

1. **Review this plan** with team
2. **Approve database schema** changes
3. **Schedule implementation** (8-10 weeks)
4. **Assign resources** (1 senior engineer full-time)
5. **Begin Phase 1** (database migration)

---

**Questions? Contact:**
- Technical Lead: [email]
- Product Manager: [email]
- Security Team: [email]

---

*End of Multi-Tenancy Implementation Plan*
