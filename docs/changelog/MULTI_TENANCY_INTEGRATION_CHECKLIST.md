## Multi-Tenancy Integration Checklist

**Status:** Core implementation complete ✅
**Integration:** In progress 🔧
**Date:** 2025-10-19

---

## Quick Start (Paste & Go)

### 1. Environment Setup

```bash
# Add to .env file
JWT_SECRET_KEY=$(openssl rand -hex 32)
REDIS_URL=redis://redis:6379/0
CORS_ALLOWED_ORIGINS=*

# Optional tuning
ACCESS_TOKEN_EXPIRE_MINUTES=1440
BCRYPT_ROUNDS=12
```

### 2. Run Database Migration

```bash
# Backup first!
docker compose exec postgres pg_dump -U parking -d parking_v5 -Fc \
  -f /backup/pre-multi-tenancy-$(date +%Y%m%d).dump

# Run migration
docker compose exec postgres psql -U parking -d parking_v5 \
  -f /migrations/002_multi_tenancy_rbac.sql

# Verify (single atomic query)
docker compose exec postgres psql -U parking -d parking_v5 -X -A -t -c "
SELECT
  (SELECT count(*)=1 FROM tenants WHERE slug='default')  AS has_default_tenant,
  (SELECT count(*)=1 FROM sites WHERE name='Default Site') AS has_default_site,
  (SELECT count(*)=0 FROM spaces WHERE site_id IS NULL OR tenant_id IS NULL) AS no_orphan_spaces;
"
```

Expected output: `t|t|t`

### 3. Integrate main.py

**Option A: Use the new version (recommended)**

```bash
# Backup current main.py
cp src/main.py src/main_backup.py

# Use the tenanted version
cp src/main_tenanted.py src/main.py
```

**Option B: Manual integration**

Add to your existing `src/main.py`:

```python
# After imports, add:
from .tenant_auth import set_db_pool as set_tenant_auth_db_pool, set_jwt_secret
from .rate_limit import RateLimiter, set_rate_limiter
from .api_tenants import router as tenants_router

# In lifespan() after db_pool initialization:
set_tenant_auth_db_pool(db_pool.pool)
set_jwt_secret(os.getenv("JWT_SECRET_KEY", settings.secret_key))
logger.info("[OK] Multi-tenancy authentication initialized")

# Initialize rate limiter
rate_limiter = RateLimiter(settings.redis_url)
await rate_limiter.initialize()
set_rate_limiter(rate_limiter)
app.state.rate_limiter = rate_limiter
logger.info("[OK] Rate limiter initialized")

# In shutdown section:
if hasattr(app.state, 'rate_limiter'):
    await app.state.rate_limiter.close()

# Add router:
app.include_router(tenants_router)
```

### 4. Update Existing Routers

**spaces.py** → Use `src/routers/spaces_tenanted.py` as template

Key changes for ALL routers:
```python
from ..tenant_auth import get_current_tenant, require_viewer, require_admin
from ..models import TenantContext

# Change from:
async def list_resources(request: Request):
    query = "SELECT * FROM resources WHERE deleted_at IS NULL"

# To:
async def list_resources(
    request: Request,
    tenant: TenantContext = Depends(require_viewer)
):
    query = "SELECT * FROM resources WHERE tenant_id = $1 AND deleted_at IS NULL"
    results = await db_pool.fetch(query, tenant.tenant_id)
```

### 5. Update Webhook Handlers

For webhook endpoints (ChirpStack uplink processing):

```python
@app.post("/api/v1/uplink")
async def process_uplink(uplink_data: dict, db: Pool = Depends(get_db)):
    device_eui = uplink_data["deviceInfo"]["devEui"]

    # Resolve tenant from space
    space = await db.fetchrow("""
        SELECT id, tenant_id, site_id, state
        FROM spaces
        WHERE sensor_eui = $1 AND deleted_at IS NULL
    """, device_eui)

    if not space:
        # Handle ORPHAN device...
        return {"status": "orphan", "device_eui": device_eui}

    # Apply per-tenant rate limiting
    from src.rate_limit import get_rate_limiter
    rate_limiter = get_rate_limiter()

    allowed, headers = await rate_limiter.check_tenant_rate_limit(
        tenant_id=str(space['tenant_id']),
        limit_type='webhook',
        requests_per_minute=600  # 10 QPS
    )

    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Process uplink with tenant context...
```

### 6. Restart and Test

```bash
# Rebuild and restart API (recommended after code changes)
docker compose up -d --build api

# Watch logs for startup
docker compose logs -f api | head -120

# Check health (in another terminal)
curl -f http://localhost:8000/health/ready
curl -f http://localhost:8000/health/live
```

---

## Integration Checklist

### ✅ Core Components (Complete)
- [x] Database migration script
- [x] Pydantic models (Tenant, Site, User, UserMembership, TenantContext)
- [x] JWT authentication system
- [x] Password hashing (bcrypt)
- [x] Tenant resolution (JWT + API key)
- [x] RBAC role checks (OWNER, ADMIN, OPERATOR, VIEWER)
- [x] Per-tenant rate limiting
- [x] Authentication endpoints (/auth/login, /auth/register)
- [x] Tenant management endpoints
- [x] API key management endpoints
- [x] Example tenanted router (spaces)

### 🔧 Integration Tasks (In Progress)

#### High Priority
- [ ] Run database migration
- [ ] Add JWT_SECRET_KEY to .env
- [ ] Update main.py with tenant auth initialization
- [ ] Update spaces router with tenant scoping
- [ ] Update uplink webhook with tenant resolution
- [ ] Test basic authentication flow

#### Medium Priority
- [ ] Update reservations router with tenant scoping
- [ ] Update devices router with tenant scoping
- [ ] Add tenant rate limiting to webhooks
- [ ] Add tenant rate limiting to downlinks
- [ ] Add tenant rate limiting to reservations
- [ ] Test tenant isolation (see test file)
- [ ] Test RBAC enforcement (see test file)

#### Low Priority
- [ ] Add audit logging for admin actions
- [ ] Add user invitation system (email invites)
- [ ] Add SSO support (optional)
- [ ] Add billing integration (optional)
- [ ] Add metrics/observability hooks
- [ ] Comprehensive test suite

---

## Testing Guide

### Manual Testing

```bash
# 1. Register a new user and tenant (FIXED: nested JSON structure)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "email": "admin@acme.com",
      "name": "Admin User",
      "password": "securepassword123"
    },
    "tenant": {
      "name": "Acme Corp",
      "slug": "acme",
      "metadata": {},
      "settings": {}
    }
  }'

# 2. Login and save token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"securepassword123"}' | jq -r .access_token)

echo "Access token: $TOKEN"

# 3. Get current tenant
curl http://localhost:8000/api/v1/tenants/current \
  -H "Authorization: Bearer $TOKEN"

# 4. List sites
SITE_ID=$(curl -s http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

echo "Site ID: $SITE_ID"

# 5. Create a space
curl -X POST http://localhost:8000/api/v1/spaces \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Bay A-001\",
    \"code\": \"A-001\",
    \"site_id\": \"$SITE_ID\",
    \"building\": \"Main Building\",
    \"floor\": \"Ground\",
    \"zone\": \"North\"
  }"

# 6. Create API key with scopes
TENANT_ID=$(curl -s http://localhost:8000/api/v1/tenants/current \
  -H "Authorization: Bearer $TOKEN" | jq -r '.id')

API_KEY=$(curl -s -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Production Key\",
    \"tenant_id\": \"$TENANT_ID\",
    \"scopes\": [\"spaces:read\", \"spaces:write\", \"devices:read\"]
  }" | jq -r '.key')

echo "API Key (save this!): $API_KEY"

# 7. Use API key
curl http://localhost:8000/api/v1/spaces \
  -H "X-API-Key: $API_KEY"
```

### Automated Testing

```bash
# Quick smoke test (recommended)
./tests/smoke_test_tenancy.sh

# Or run unit tests
pytest tests/test_tenancy_rbac.py -v

# Set up test data manually if needed
python -c "
import asyncio
from tests.test_tenancy_rbac import setup_test_tenants_and_users
asyncio.run(setup_test_tenants_and_users())
"
```

---

## Security Checklist

### Before Production
- [ ] JWT_SECRET_KEY is 32+ characters and random (rotate quarterly)
- [ ] All endpoints have tenant_id predicates
- [ ] No queries can leak cross-tenant data
- [ ] Rate limiting is active and tested
- [ ] API keys are scoped (least-privilege principle)
- [ ] API keys are revocable
- [ ] Admin actions are logged
- [ ] Sensitive endpoints require OWNER/ADMIN roles
- [ ] Password requirements are enforced (12+ chars recommended, consider zxcvbn)
- [ ] HTTPS is enforced (Traefik)
- [ ] CORS origins are properly configured (NOT wildcard `*` in production)

### Audit Items
- [ ] Review all `SELECT` queries for tenant_id predicates
- [ ] Review all `INSERT` queries for tenant_id values
- [ ] Review all `UPDATE` queries for tenant_id predicates
- [ ] Search codebase for "spaces WHERE" without "tenant_id"
- [ ] Search codebase for "reservations WHERE" without "tenant_id"
- [ ] Search codebase for "sensor_readings WHERE" without tenant context

---

## Common Gotchas

### 1. Tenant Leakage via Queries

❌ **WRONG:**
```python
query = "SELECT * FROM spaces WHERE code = $1"
result = await db.fetch(query, space_code)
```

✅ **CORRECT:**
```python
query = "SELECT * FROM spaces WHERE tenant_id = $1 AND code = $2"
result = await db.fetch(query, tenant.tenant_id, space_code)
```

### 2. Inserts Without Tenant ID

❌ **WRONG:**
```python
query = "INSERT INTO spaces (name, code) VALUES ($1, $2)"
```

✅ **CORRECT:**
```python
# Tenant ID will be auto-synced from site_id by trigger, but verify site belongs to tenant first!
site_check = await db.fetchrow(
    "SELECT id FROM sites WHERE id = $1 AND tenant_id = $2",
    site_id, tenant.tenant_id
)
if not site_check:
    raise HTTPException(400, "Site not found")

query = "INSERT INTO spaces (name, code, site_id) VALUES ($1, $2, $3)"
```

### 3. Webhook Processing Without Tenant Context

❌ **WRONG:**
```python
@app.post("/api/v1/uplink")
async def process_uplink(data: dict):
    # Process without knowing which tenant this device belongs to
```

✅ **CORRECT:**
```python
@app.post("/api/v1/uplink")
async def process_uplink(data: dict, db: Pool = Depends(get_db)):
    # Resolve tenant from device
    space = await db.fetchrow(
        "SELECT tenant_id FROM spaces WHERE sensor_eui = $1",
        device_eui
    )
    # Apply per-tenant rate limiting...
```

### 4. Unique Constraints

Old unique constraint on `code` would prevent Tenant A and Tenant B from using "A-001".

✅ **CORRECT:** Use composite unique index:
```sql
CREATE UNIQUE INDEX unique_tenant_site_space_code
ON spaces(tenant_id, site_id, code)
WHERE deleted_at IS NULL;
```

---

## Rollback Plan

If you need to rollback:

```bash
# Stop API
docker compose stop api

# Restore database
docker compose exec postgres pg_restore -U parking -d parking_v5 -c \
  /backup/pre-multi-tenancy-YYYYMMDD.dump

# Revert code
git checkout HEAD~1 src/main.py
# Or restore from backup: cp src/main_backup.py src/main.py

# Restart
docker compose up -d api
```

---

## Performance Considerations

### Indexes
The migration adds these indexes for tenant queries:
```sql
CREATE INDEX idx_spaces_tenant ON spaces(tenant_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id) WHERE is_active = true;
CREATE INDEX idx_sites_tenant ON sites(tenant_id) WHERE is_active = true;
```

### Query Patterns
All tenant-scoped queries will use these indexes efficiently:
```sql
EXPLAIN ANALYZE
SELECT * FROM spaces WHERE tenant_id = 'xxx' AND state = 'FREE';

-- Should show: Index Scan using idx_spaces_tenant
```

### Rate Limiter
Redis token bucket algorithm is O(1) per check.
Key cardinality: ~(tenants × 3) for webhook/downlink/booking limits.

---

## Monitoring

### Key Metrics to Track

```python
# In src/metrics.py or similar
from prometheus_client import Counter, Histogram

auth_failures = Counter("auth_failures_total", "Authentication failures", ["method", "reason"])
tenant_requests = Counter("tenant_requests_total", "Requests per tenant", ["tenant_id"])
rate_limit_hits = Counter("rate_limit_denied_total", "Rate limit denials", ["tenant_id", "scope"])
```

### Log Patterns

All tenant-scoped operations log:
```
[Tenant:TENANT_ID] Operation: description
```

Search logs:
```bash
# Find all Tenant A activity
docker compose logs api | grep "\[Tenant:YOUR_TENANT_ID\]"

# Find rate limit denials
docker compose logs api | grep "Rate limit exceeded"

# Find authentication failures
docker compose logs api | grep "Invalid API key\|Invalid password"
```

---

## Support

### Troubleshooting

**"Authentication required" error**
- Check JWT token is valid: `jwt.io` decoder
- Verify Bearer format: `Authorization: Bearer <token>`
- Or check API key: `X-API-Key: <key>`

**"Insufficient permissions" error**
- Check user role: `GET /api/v1/tenants/current`
- Review endpoint role requirement
- API keys have ADMIN-level access

**"Space not found" but I know it exists**
- Likely cross-tenant access attempt
- Verify space belongs to your tenant
- Check `tenant_id` in database

**Rate limit hit unexpectedly**
- Check Redis for rate limit keys: `KEYS rate_limit:*`
- Review `RateLimitConfig` in code
- Adjust limits if legitimate traffic

---

## Next Steps

1. ✅ Complete integration checklist (above)
2. ✅ Run manual tests
3. ✅ Run automated tests
4. ✅ Review security checklist
5. ✅ Deploy to staging
6. ✅ Monitor for 24 hours
7. ✅ Deploy to production
8. ✅ Update API documentation
9. ✅ Train users on new authentication

---

**Last Updated:** 2025-10-19
**Status:** Ready for integration
**Risk Level:** Medium (requires careful testing of tenant isolation)

