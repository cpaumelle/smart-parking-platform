# Phase 3 Implementation Guide: Multi-Tenant API Authentication

**Date**: 2025-10-15
**Platform**: Smart Parking Platform v1.4.0
**Status**: Implementation Guide - Ready for Execution

---

## Executive Summary

This guide provides step-by-step instructions for implementing Phase 3 of the multi-tenancy rollout: **activating tenant authentication on all API endpoints**.

**What's Already Built**:
- ✅ Database RLS policies (13 tables, 100% tested)
- ✅ Tenant authentication modules (`tenant_auth.py`, `tenant_context.py`)
- ✅ API key generation utilities
- ✅ Test data (2 tenants: Verdegris, ACME)
- ✅ Non-superuser role (`parking_app_user`)

**What Phase 3 Does**:
- ✅ Wire tenant authentication into all API endpoints
- ✅ Switch from unscoped to tenant-scoped database queries
- ✅ Change DATABASE_URL to enforce RLS
- ✅ Validate end-to-end tenant isolation

**Impact**: After Phase 3, all API requests MUST include a valid `X-API-Key` header, and all data will be automatically isolated by tenant.

---

## Table of Contents

1. [Overview of Changes](#overview-of-changes)
2. [Prerequisites](#prerequisites)
3. [Implementation Steps](#implementation-steps)
4. [Code Migration Examples](#code-migration-examples)
5. [Testing Procedures](#testing-procedures)
6. [Rollback Plan](#rollback-plan)
7. [Deployment Checklist](#deployment-checklist)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Security Validation](#security-validation)

---

## Overview of Changes

### Current Architecture (Pre-Phase 3)

```
User Request → API Endpoint → Database (no tenant filter) → All Data Returned
```

**Problems**:
- No authentication required
- All tenants see all data
- RLS policies exist but not enforced (superuser bypass)

### New Architecture (Phase 3)

```
User Request + X-API-Key → API Endpoint → Tenant Auth → Tenant-Scoped DB → Only Tenant Data Returned
```

**Benefits**:
- ✅ API key authentication required
- ✅ Automatic tenant isolation via RLS
- ✅ Database-enforced security (even SQL injection can't bypass)
- ✅ Audit trail of all access

---

## Prerequisites

### 1. Database Setup ✅ COMPLETE

Already done in Phase 2:
- Core schema with `tenants` and `api_keys` tables
- RLS policies on 13 tables
- `parking_app_user` role created

**Verify**:
```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
SELECT
    schemaname, tablename, policyname
FROM pg_policies
WHERE policyname = 'tenant_isolation_policy';"
```

Expected: 13 rows

### 2. API Keys Generated ✅ COMPLETE

Already done in testing:
- Verdegris: API key generated and tested
- ACME: API key generated and tested

**Verify**:
```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
SELECT tenant_slug, is_active, expires_at
FROM core.tenants
JOIN core.api_keys USING (tenant_id);"
```

### 3. Code Modules Ready ✅ COMPLETE

Already built:
- `app/utils/tenant_auth.py` - API key validation
- `app/utils/tenant_context.py` - Database context management
- `app/utils/api_keys.py` - Key generation utilities

**Verify**:
```bash
ls -la /opt/smart-parking/services/parking-display/app/utils/tenant_*.py
```

---

## Implementation Steps

### Step 1: Update Endpoint Imports

**File**: `/opt/smart-parking/services/parking-display/app/routers/*.py`

**Add imports** to all router files:
```python
from fastapi import APIRouter, Depends, HTTPException, Header
from app.utils.tenant_auth import verify_tenant_api_key, TenantAuthResult
from app.utils.tenant_context import get_tenant_db
from app.database import get_db_pool
```

**Remove old import**:
```python
# OLD - Remove this
from app.database import get_db_dependency
```

---

### Step 2: Update Endpoint Signatures

**Pattern**: Add tenant authentication and tenant-scoped database connection

**BEFORE** (No authentication):
```python
@router.get("/")
async def list_spaces(db = Depends(get_db_dependency)):
    # Queries return ALL tenant data (not isolated)
    results = await db.fetch("SELECT * FROM parking_spaces.spaces")
    return {"spaces": results}
```

**AFTER** (With tenant authentication):
```python
@router.get("/")
async def list_spaces(
    auth: TenantAuthResult = Depends(
        lambda x_api_key=Header(None, alias="X-API-Key"):
            verify_tenant_api_key(x_api_key, get_db_pool())
    )
):
    # Queries automatically filtered by tenant via RLS
    async with get_tenant_db(auth.tenant_id) as db:
        results = await db.fetch("SELECT * FROM parking_spaces.spaces")
        return {"spaces": results}
```

**Key Changes**:
1. Add `auth` parameter with `verify_tenant_api_key` dependency
2. Replace `db = Depends(get_db_dependency)` with `get_tenant_db(auth.tenant_id)`
3. Wrap database queries in `async with get_tenant_db(auth.tenant_id) as db:`

---

### Step 3: Create Dependency Helper

To simplify endpoint code, create a reusable dependency.

**File**: `/opt/smart-parking/services/parking-display/app/dependencies.py`

**Add this function**:
```python
"""
FastAPI Dependencies
====================
Reusable dependencies for tenant authentication and database access.
"""

from fastapi import Depends, Header
from typing import Optional
from app.utils.tenant_auth import verify_tenant_api_key, TenantAuthResult
from app.database import get_db_pool

async def get_authenticated_tenant(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> TenantAuthResult:
    """
    FastAPI dependency for tenant authentication.

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(auth = Depends(get_authenticated_tenant)):
            # auth.tenant_id contains authenticated tenant
            async with get_tenant_db(auth.tenant_id) as db:
                # ... database queries ...

    Returns:
        TenantAuthResult with tenant context

    Raises:
        HTTPException 401/403 if authentication fails
    """
    return await verify_tenant_api_key(x_api_key, get_db_pool())
```

**Now endpoints become simpler**:
```python
from app.dependencies import get_authenticated_tenant

@router.get("/")
async def list_spaces(auth = Depends(get_authenticated_tenant)):
    async with get_tenant_db(auth.tenant_id) as db:
        results = await db.fetch("SELECT * FROM parking_spaces.spaces")
        return {"spaces": results}
```

---

### Step 4: Update All Endpoints

**Files to update**:
- `app/routers/spaces.py` - All 6+ endpoints
- `app/routers/reservations.py` - All 5+ endpoints
- `app/routers/actuations.py` - All 4+ endpoints
- `app/routers/admin.py` - Admin endpoints (may need super-admin auth)

**For each endpoint**:
1. Add `auth = Depends(get_authenticated_tenant)` parameter
2. Replace `db = Depends(get_db_dependency)` with `async with get_tenant_db(auth.tenant_id) as db:`
3. Move database logic inside `async with` block
4. Test the endpoint

---

### Step 5: Update Background Tasks

Background tasks (reconciliation, reservation expiry) also need tenant context.

**File**: `app/tasks/reconciliation.py`

**BEFORE**:
```python
async def reconcile_display_states():
    async with get_db() as db:
        spaces = await db.fetch("SELECT * FROM parking_spaces.spaces")
        # ... reconciliation logic ...
```

**AFTER**:
```python
async def reconcile_display_states():
    # Get all tenants
    async with get_db() as db:
        tenants = await db.fetch("SELECT tenant_id FROM core.tenants WHERE is_active = TRUE")

    # Reconcile for each tenant
    for tenant in tenants:
        async with get_tenant_db(tenant['tenant_id']) as db:
            spaces = await db.fetch("SELECT * FROM parking_spaces.spaces")
            # ... reconciliation logic (automatically scoped to tenant) ...
```

**Files to update**:
- `app/tasks/reconciliation.py`
- `app/tasks/reservation_expiry.py`
- `app/scheduler/jobs.py`

---

### Step 6: Switch DATABASE_URL to Non-Superuser

**Critical**: This activates RLS enforcement.

**Current** (in docker-compose.yml):
```yaml
parking-display:
  environment:
    DATABASE_URL: postgresql://parking_user:${POSTGRES_PASSWORD}@postgres-primary:5432/parking_platform
```

**New** (RLS enforced):
```yaml
parking-display:
  environment:
    DATABASE_URL: postgresql://parking_app_user:${POSTGRES_APP_PASSWORD}@postgres-primary:5432/parking_platform
```

**Steps**:
1. Set password for `parking_app_user` in PostgreSQL
2. Add `POSTGRES_APP_PASSWORD` to `.env` file
3. Update `docker-compose.yml` to use `parking_app_user`
4. Restart parking-display service

**Set password**:
```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
ALTER ROLE parking_app_user WITH PASSWORD 'SECURE_PASSWORD_HERE';"
```

---

### Step 7: Update Health Check Endpoint

The `/health` endpoint should remain **unauthenticated** for monitoring.

**File**: `app/main.py`

**Keep health check as-is** (no tenant auth):
```python
@app.get("/health")
async def health_check(db = Depends(get_db_dependency)):
    # Health checks don't require tenant auth
    # But they also can't query tenant-specific data anymore
    # Only check database connectivity
    try:
        result = await db.fetchval("SELECT 1")
        return {"status": "healthy", "database": result == 1}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

**Alternative**: Make health check use superuser connection:
```python
# Create separate health check database dependency that uses parking_user
# This allows health checks to see aggregate stats across all tenants
```

---

## Code Migration Examples

### Example 1: Simple GET Endpoint

**BEFORE**:
```python
@router.get("/spaces/{space_id}")
async def get_space(space_id: str, db = Depends(get_db_dependency)):
    query = "SELECT * FROM parking_spaces.spaces WHERE space_id = $1"
    space = await db.fetchrow(query, space_id)

    if not space:
        raise HTTPException(404, "Space not found")

    return {"space": dict(space)}
```

**AFTER**:
```python
@router.get("/spaces/{space_id}")
async def get_space(
    space_id: str,
    auth = Depends(get_authenticated_tenant)
):
    async with get_tenant_db(auth.tenant_id) as db:
        query = "SELECT * FROM parking_spaces.spaces WHERE space_id = $1"
        space = await db.fetchrow(query, space_id)

        # If space not found, it could be:
        # 1. Space doesn't exist
        # 2. Space belongs to different tenant (RLS blocked it)
        # Both cases return 404 (correct behavior - don't leak info)
        if not space:
            raise HTTPException(404, "Space not found")

        return {"space": dict(space)}
```

**Changes**:
1. Added `auth` parameter
2. Wrapped database logic in `async with get_tenant_db(auth.tenant_id) as db:`
3. Removed `db = Depends(get_db_dependency)`

---

### Example 2: POST Endpoint (Create Resource)

**BEFORE**:
```python
@router.post("/spaces")
async def create_space(
    request: CreateSpaceRequest,
    db = Depends(get_db_dependency)
):
    query = """
        INSERT INTO parking_spaces.spaces
        (space_code, space_name, building, floor)
        VALUES ($1, $2, $3, $4)
        RETURNING space_id
    """
    result = await db.fetchrow(
        query,
        request.space_code,
        request.space_name,
        request.building,
        request.floor
    )

    return {"space_id": str(result["space_id"])}
```

**AFTER**:
```python
@router.post("/spaces")
async def create_space(
    request: CreateSpaceRequest,
    auth = Depends(get_authenticated_tenant)
):
    async with get_tenant_db(auth.tenant_id) as db:
        query = """
            INSERT INTO parking_spaces.spaces
            (space_code, space_name, building, floor)
            VALUES ($1, $2, $3, $4)
            RETURNING space_id
        """
        # Note: tenant_id column has a default value that uses app.current_tenant_id
        # So we don't need to explicitly insert tenant_id - it's automatic!
        result = await db.fetchrow(
            query,
            request.space_code,
            request.space_name,
            request.building,
            request.floor
        )

        return {"space_id": str(result["space_id"])}
```

**Key Point**: The `tenant_id` column has a DEFAULT that reads from `app.current_tenant_id`, so it's automatically populated. No code change needed!

---

### Example 3: Complex Query with Filters

**BEFORE**:
```python
@router.get("/spaces")
async def list_spaces(
    building: Optional[str] = None,
    floor: Optional[str] = None,
    db = Depends(get_db_dependency)
):
    conditions = []
    params = []

    if building:
        conditions.append(f"building = ${len(params) + 1}")
        params.append(building)

    if floor:
        conditions.append(f"floor = ${len(params) + 1}")
        params.append(floor)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"SELECT * FROM parking_spaces.spaces {where}"
    results = await db.fetch(query, *params)

    return {"spaces": [dict(r) for r in results]}
```

**AFTER**:
```python
@router.get("/spaces")
async def list_spaces(
    building: Optional[str] = None,
    floor: Optional[str] = None,
    auth = Depends(get_authenticated_tenant)
):
    async with get_tenant_db(auth.tenant_id) as db:
        conditions = []
        params = []

        if building:
            conditions.append(f"building = ${len(params) + 1}")
            params.append(building)

        if floor:
            conditions.append(f"floor = ${len(params) + 1}")
            params.append(floor)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # RLS automatically adds: AND tenant_id = '<auth.tenant_id>'
        query = f"SELECT * FROM parking_spaces.spaces {where}"
        results = await db.fetch(query, *params)

        return {"spaces": [dict(r) for r in results]}
```

**Key Point**: You don't need to manually filter by `tenant_id` - RLS does it automatically!

---

### Example 4: Background Task (Reconciliation)

**BEFORE**:
```python
async def reconcile_all_spaces():
    """Reconcile display states for all spaces"""
    async with get_db() as db:
        spaces = await db.fetch("""
            SELECT space_id, current_state, display_device_deveui
            FROM parking_spaces.spaces
            WHERE enabled = TRUE
        """)

        for space in spaces:
            await reconcile_single_space(db, space)
```

**AFTER**:
```python
async def reconcile_all_spaces():
    """Reconcile display states for all spaces (multi-tenant aware)"""

    # First, get all active tenants
    async with get_db() as db:
        tenants = await db.fetch("""
            SELECT tenant_id, tenant_slug
            FROM core.tenants
            WHERE is_active = TRUE
        """)

    # Reconcile each tenant's spaces
    for tenant in tenants:
        try:
            async with get_tenant_db(tenant['tenant_id']) as db:
                spaces = await db.fetch("""
                    SELECT space_id, current_state, display_device_deveui
                    FROM parking_spaces.spaces
                    WHERE enabled = TRUE
                """)

                logger.info(f"Reconciling {len(spaces)} spaces for tenant {tenant['tenant_slug']}")

                for space in spaces:
                    await reconcile_single_space(db, space)

        except Exception as e:
            logger.error(f"Reconciliation failed for tenant {tenant['tenant_slug']}: {e}")
            # Continue with other tenants
            continue
```

**Changes**:
1. Loop through tenants first
2. Use tenant-scoped connection for each tenant
3. Add error handling per tenant (don't let one tenant's error break others)

---

## Testing Procedures

### Pre-Deployment Testing (Development Environment)

#### Test 1: API Key Authentication

**Test valid API key**:
```bash
# Verdegris API key
VERDEGRIS_KEY="sp_live_xxxxxxxxxxxx"

curl -H "X-API-Key: $VERDEGRIS_KEY" \
  https://parking.verdegris.eu/v1/spaces | jq
```

**Expected**: 200 OK, spaces for Verdegris tenant

**Test invalid API key**:
```bash
curl -H "X-API-Key: invalid_key_12345" \
  https://parking.verdegris.eu/v1/spaces | jq
```

**Expected**: 403 Forbidden, error message

**Test missing API key**:
```bash
curl https://parking.verdegris.eu/v1/spaces | jq
```

**Expected**: 401 Unauthorized

---

#### Test 2: Tenant Isolation

**Setup**: Create test data for both tenants
```sql
-- As Verdegris
SET LOCAL app.current_tenant_id = 'ee20b258-7afc-4c98-a5e9-1c9eab37ea94';
INSERT INTO parking_spaces.spaces (space_code, space_name)
VALUES ('V-TEST-1', 'Verdegris Test Space');

-- As ACME
SET LOCAL app.current_tenant_id = 'c2507924-46e2-4d00-a3b2-550791e790bb';
INSERT INTO parking_spaces.spaces (space_code, space_name)
VALUES ('A-TEST-1', 'ACME Test Space');
```

**Test Verdegris can only see Verdegris data**:
```bash
VERDEGRIS_KEY="sp_live_xxxxxxxxxxxx"

curl -H "X-API-Key: $VERDEGRIS_KEY" \
  https://parking.verdegris.eu/v1/spaces | jq '.spaces[] | .space_code'
```

**Expected**: Only see `V-TEST-1` (not `A-TEST-1`)

**Test ACME can only see ACME data**:
```bash
ACME_KEY="sp_live_yyyyyyyyyyyy"

curl -H "X-API-Key: $ACME_KEY" \
  https://parking.verdegris.eu/v1/spaces | jq '.spaces[] | .space_code'
```

**Expected**: Only see `A-TEST-1` (not `V-TEST-1`)

---

#### Test 3: CRUD Operations Isolation

**Test CREATE (Verdegris)**:
```bash
curl -X POST https://parking.verdegris.eu/v1/spaces \
  -H "X-API-Key: $VERDEGRIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "space_code": "V-NEW-1",
    "space_name": "New Verdegris Space",
    "building": "A",
    "floor": "1"
  }' | jq
```

**Verify**: ACME cannot see `V-NEW-1`
```bash
curl -H "X-API-Key: $ACME_KEY" \
  https://parking.verdegris.eu/v1/spaces | jq '.spaces[] | select(.space_code == "V-NEW-1")'
```

**Expected**: Empty (no results)

---

#### Test 4: Background Tasks (Reconciliation)

**Check logs after reconciliation runs**:
```bash
sudo docker compose logs parking-display | grep -i reconcil
```

**Expected**:
```
Reconciling 6 spaces for tenant verdegris
Reconciling 1 spaces for tenant acme-corporation
```

---

#### Test 5: Health Check (Unauthenticated)

```bash
curl https://parking.verdegris.eu/health | jq
```

**Expected**: 200 OK, health status (no API key required)

---

### Post-Deployment Validation

#### Validation 1: Database Connection Using Correct Role

```bash
sudo docker compose exec parking-display env | grep DATABASE_URL
```

**Expected**: `postgresql://parking_app_user:...` (not `parking_user`)

---

#### Validation 2: RLS Policies Active

```bash
sudo docker compose exec postgres-primary psql -U parking_app_user -d parking_platform -c "
SELECT COUNT(*) FROM parking_spaces.spaces;"
```

**Expected**: Error or 0 rows (no tenant context set)

**With context**:
```bash
sudo docker compose exec postgres-primary psql -U parking_app_user -d parking_platform -c "
SET LOCAL app.current_tenant_id = 'ee20b258-7afc-4c98-a5e9-1c9eab37ea94';
SELECT COUNT(*) FROM parking_spaces.spaces;"
```

**Expected**: Returns Verdegris space count (e.g., 6)

---

#### Validation 3: API Key Last Used Tracking

```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
SELECT tenant_slug, last_used_at
FROM core.api_keys
JOIN core.tenants USING (tenant_id)
ORDER BY last_used_at DESC;"
```

**Expected**: Recent timestamps for tenants that made requests

---

#### Validation 4: Audit Trail

```bash
sudo docker compose logs parking-display | grep "Authenticated"
```

**Expected**:
```
✅ Authenticated: tenant=verdegris tier=professional key=sp_live_...
✅ Authenticated: tenant=acme-corporation tier=free key=sp_live_...
```

---

## Rollback Plan

### If Issues Detected After Deployment

#### Option 1: Quick Rollback (Disable Auth)

**Temporarily disable authentication** while debugging:

1. **Add optional auth** to endpoints:
```python
from app.utils.tenant_auth import optional_tenant_auth

@router.get("/spaces")
async def list_spaces(auth = Depends(optional_tenant_auth)):
    if auth:
        # Use tenant-scoped connection
        async with get_tenant_db(auth.tenant_id) as db:
            ...
    else:
        # Fallback to unscoped (superuser) connection
        async with get_db() as db:
            ...
```

2. **Revert DATABASE_URL** to superuser:
```yaml
DATABASE_URL: postgresql://parking_user:${POSTGRES_PASSWORD}@...
```

3. **Restart service**:
```bash
sudo docker compose restart parking-display
```

**Result**: API works without authentication (like before)

---

#### Option 2: Full Rollback (Restore Previous Version)

1. **Stop parking-display**:
```bash
sudo docker compose stop parking-display
```

2. **Restore code from git** (if committed):
```bash
cd /opt/smart-parking/services/parking-display
sudo git checkout HEAD~1 app/routers/*.py
sudo git checkout HEAD~1 app/main.py
```

3. **Revert DATABASE_URL** in docker-compose.yml

4. **Restart service**:
```bash
sudo docker compose up -d parking-display
```

---

#### Option 3: Database Rollback (Disable RLS)

**If RLS is causing issues**, temporarily disable:

```sql
-- Disable RLS on all tables
ALTER TABLE parking_spaces.spaces DISABLE ROW LEVEL SECURITY;
ALTER TABLE parking_spaces.reservations DISABLE ROW LEVEL SECURITY;
-- ... repeat for all 13 tables
```

**Re-enable when ready**:
```sql
ALTER TABLE parking_spaces.spaces ENABLE ROW LEVEL SECURITY;
-- ... etc
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] **Code Review**: Review all endpoint changes
- [ ] **Unit Tests**: Test authentication logic
- [ ] **Integration Tests**: Test tenant isolation
- [ ] **Backup Database**: `pg_dump` before deployment
- [ ] **Document API Keys**: Store Verdegris/ACME keys securely
- [ ] **Update API Docs**: Document `X-API-Key` header requirement

### Deployment Steps

- [ ] **Set parking_app_user password** in PostgreSQL
- [ ] **Add POSTGRES_APP_PASSWORD** to `.env` file
- [ ] **Update endpoints** (all routers)
- [ ] **Update background tasks** (reconciliation, expiry)
- [ ] **Update docker-compose.yml** (DATABASE_URL)
- [ ] **Commit changes** to git
- [ ] **Restart parking-display service**
- [ ] **Monitor logs** for errors

### Post-Deployment Validation

- [ ] **Health check passes** (`/health` returns 200)
- [ ] **API key auth works** (Verdegris key accepted)
- [ ] **Tenant isolation verified** (Verdegris can't see ACME data)
- [ ] **CRUD operations work** (create/read/update/delete)
- [ ] **Background tasks running** (reconciliation logs show both tenants)
- [ ] **No errors in logs** (check for auth failures)
- [ ] **API documentation updated** (Swagger/ReDoc shows auth)

### Rollback Triggers

Initiate rollback if:
- ❌ API requests failing (>5% error rate)
- ❌ Tenant seeing wrong data (cross-tenant leak)
- ❌ Background tasks crashing
- ❌ Database connection issues
- ❌ Performance degradation (>500ms avg response time)

---

## Troubleshooting Guide

### Issue 1: "Authentication service misconfigured"

**Symptoms**: 500 error, log shows "Database pool not provided"

**Cause**: `verify_tenant_api_key` not receiving database pool

**Solution**: Update dependency to pass pool:
```python
auth = Depends(
    lambda x_api_key=Header(None): verify_tenant_api_key(x_api_key, get_db_pool())
)
```

Or use the `get_authenticated_tenant` helper (recommended).

---

### Issue 2: "Tenant context not initialized"

**Symptoms**: Runtime error on startup

**Cause**: `init_tenant_context()` not called during startup

**Solution**: Verify `main.py` lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    init_tenant_context(get_db_pool())  # Must be called!
    yield
```

---

### Issue 3: RLS Not Blocking Cross-Tenant Queries

**Symptoms**: Verdegris can see ACME data

**Cause**: Still using superuser (`parking_user`) connection

**Solution**:
1. Verify DATABASE_URL uses `parking_app_user`
2. Restart service
3. Test with non-superuser:
```bash
sudo docker compose exec postgres-primary psql -U parking_app_user -d parking_platform
```

---

### Issue 4: Health Check Fails After Deployment

**Symptoms**: `/health` returns 500 error

**Cause**: Health check tries to query tenant-scoped tables without context

**Solution**: Update health check to only test connectivity:
```python
@app.get("/health")
async def health_check(db = Depends(get_db_dependency)):
    result = await db.fetchval("SELECT 1")
    return {"status": "healthy", "database": result == 1}
```

Don't query `parking_spaces.spaces` in health check (requires tenant context).

---

### Issue 5: Background Tasks Not Running

**Symptoms**: No reconciliation logs

**Cause**: Background tasks need to loop through tenants

**Solution**: Update task to handle multiple tenants (see Example 4 in Code Migration section).

---

### Issue 6: API Key Hash Mismatch

**Symptoms**: Valid API key rejected, log shows "Invalid API key"

**Cause**: API key not hashed with bcrypt before storing

**Solution**: Regenerate API key with hash:
```python
from app.utils.api_keys import generate_and_hash_api_key

api_key, key_hash = generate_and_hash_api_key("sp_live_")
print(f"API Key: {api_key}")
print(f"Hash: {key_hash}")

# Store key_hash in database
# Give api_key to tenant (show ONCE)
```

---

## Security Validation

### Validation 1: SQL Injection Cannot Bypass RLS

**Test**: Attempt SQL injection in query parameter
```bash
curl -H "X-API-Key: $VERDEGRIS_KEY" \
  "https://parking.verdegris.eu/v1/spaces?building=A' OR tenant_id='<ACME_TENANT_ID>" \
  | jq
```

**Expected**:
- Either syntax error (parameter properly escaped)
- Or returns only Verdegris data (RLS blocks ACME data)

**Never**: Returns ACME data

---

### Validation 2: Expired API Keys Rejected

**Test**: Use expired key
```bash
# First, expire a key in database
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
UPDATE core.api_keys
SET expires_at = NOW() - INTERVAL '1 day'
WHERE tenant_id = (SELECT tenant_id FROM core.tenants WHERE tenant_slug = 'test-tenant');"

# Try to use it
curl -H "X-API-Key: $EXPIRED_KEY" https://parking.verdegris.eu/v1/spaces
```

**Expected**: 403 Forbidden, "API key has expired"

---

### Validation 3: Inactive Tenant Blocked

**Test**: Deactivate tenant
```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
UPDATE core.tenants SET is_active = FALSE WHERE tenant_slug = 'test-tenant';"

curl -H "X-API-Key: $TEST_KEY" https://parking.verdegris.eu/v1/spaces
```

**Expected**: 403 Forbidden, "Tenant account is inactive"

---

### Validation 4: Revoked Keys Rejected

**Test**: Revoke API key
```bash
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
UPDATE core.api_keys SET is_active = FALSE WHERE tenant_id = <tenant_id>;"

curl -H "X-API-Key: $REVOKED_KEY" https://parking.verdegris.eu/v1/spaces
```

**Expected**: 403 Forbidden, "API key has been revoked"

---

## Next Steps After Phase 3

Once Phase 3 is complete and validated:

### Phase 4: Extend to Other Services
- Update ingest service (sensor data ingestion)
- Update transform service (data processing)
- Update downlink service (device control)

### Phase 5: Tenant Management API
- Create API for tenant self-service
- API key rotation
- Usage analytics per tenant
- Rate limiting per tenant

### Phase 6: Monitoring & Analytics
- Multi-tenant dashboards
- Per-tenant usage metrics
- Cost allocation reporting
- SLA monitoring

---

## Conclusion

Phase 3 activates the multi-tenancy security infrastructure built in Phase 2. After completion:

✅ **All API requests require authentication**
✅ **Tenant data automatically isolated at database level**
✅ **Zero-trust architecture** (even SQL injection can't bypass)
✅ **Production-ready multi-tenant SaaS platform**

**Estimated Implementation Time**: 4-6 hours
**Risk Level**: Medium (rollback plan available)
**Impact**: High (enables multi-tenant operations)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-15
**Author**: Smart Parking Platform Team
**Status**: Ready for Implementation

---

*End of Phase 3 Implementation Guide*
