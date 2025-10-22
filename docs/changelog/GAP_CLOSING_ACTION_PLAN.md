# Gap-Closing Action Plan
**Project:** Smart Parking Platform v5.3
**Date:** 2025-10-21
**Status:** 🚀 Ready to Execute

## Overview

This document provides a **practical, bite-sized action plan** to close the gaps identified in the spec compliance review. All tasks are prioritized and broken down into achievable chunks.

---

## A. Spec & SDKs (Unblocks Partners)

**Goal:** Update OpenAPI spec to match implementation and generate client SDKs

### A1. Update OpenAPI Spec ✅ READY TO IMPLEMENT

**Priority:** 🔴 **CRITICAL** (blocks partner integration)
**Effort:** 4-6 hours
**Dependencies:** None

#### Tasks:

1. **Remove explicit tenant_id from paths** (2 hours)
   ```yaml
   # Before
   /api/v1/tenants/{tenant_id}/display-policies:

   # After
   /api/v1/display-policies:
   ```

   **Files to update:**
   - `docs/api/smart-parking-openapi.yaml`

   **Paths to change:**
   - `/api/v1/tenants/{tenant_id}/display-policies` → `/api/v1/display-policies`
   - `/api/v1/tenants/{tenant_id}/display-policies/{policy_id}/activate` → `/api/v1/display-policies/{policy_id}/activate`
   - `/api/v1/tenants/{tenant_id}` → `/api/v1/tenants/current`
   - `/api/v1/tenants/{tenant_id}/users` → `/api/v1/users`

2. **Add missing implementation endpoints** (2 hours)

   Add these endpoints to the spec:
   - `POST /api/v1/auth/register` - User registration
   - `GET /api/v1/tenants/current` - Get current tenant
   - `PATCH /api/v1/tenants/current` - Update current tenant
   - `GET /api/v1/sites` - List sites
   - `POST /api/v1/sites` - Create site
   - `GET /api/v1/sites/{site_id}` - Get site
   - `PATCH /api/v1/sites/{site_id}` - Update site
   - `GET /api/v1/users` - List users
   - `GET /api/v1/api-keys` - List API keys
   - `POST /api/v1/api-keys` - Create API key
   - `DELETE /api/v1/api-keys/{key_id}` - Revoke API key
   - `POST /api/v1/webhook-secret` - Create webhook secret
   - `POST /api/v1/webhook-secret/rotate` - Rotate webhook secret
   - `GET /api/v1/orphan-devices` - List orphan devices
   - `POST /api/v1/orphan-devices/{device_eui}/assign` - Assign device
   - `DELETE /api/v1/orphan-devices/{device_eui}` - Delete device
   - `GET /api/v1/gateways` - List gateways
   - `GET /api/v1/gateways/{gw_eui}` - Get gateway
   - `GET /health/live` - Liveness probe
   - All display policy management endpoints
   - All device management endpoints

3. **Add authentication section** (1 hour)

   Document in spec:
   ```yaml
   # Add to description
   ## Authentication & Tenant Scoping

   This API uses implicit tenant scoping. The tenant context is extracted from:
   - JWT Bearer token (for user authentication)
   - X-API-Key header (for service authentication)

   All tenant-scoped endpoints automatically filter by the authenticated user's tenant.
   No explicit tenant_id in paths is required.
   ```

4. **Validate spec** (30 min)
   ```bash
   npm i -g @stoplight/spectral-cli
   cd docs/api
   spectral lint smart-parking-openapi.yaml -r spectral.yaml
   ```

**Acceptance Criteria:**
- [ ] All implemented endpoints documented
- [ ] No explicit tenant_id in paths
- [ ] Authentication section added
- [ ] Spec validates without errors
- [ ] JSON version generated

---

### A2. Generate Client SDKs 📦

**Priority:** 🟡 **HIGH** (enables partner integration)
**Effort:** 2-3 hours
**Dependencies:** A1 (spec must be updated first)

#### Tasks:

1. **Generate TypeScript/JavaScript SDK** (1 hour)
   ```bash
   cd docs/api
   docker pull openapitools/openapi-generator-cli:7.6.0

   # Generate TypeScript client
   docker run --rm \
     -v ${PWD}:/local \
     openapitools/openapi-generator-cli:7.6.0 generate \
     -i /local/smart-parking-openapi.yaml \
     -g typescript-axios \
     -o /local/clients/typescript \
     -c /local/openapi-config-typescript.yaml
   ```

2. **Generate Python SDK** (1 hour)
   ```bash
   # Generate Python client
   docker run --rm \
     -v ${PWD}:/local \
     openapitools/openapi-generator-cli:7.6.0 generate \
     -i /local/smart-parking-openapi.yaml \
     -g python \
     -o /local/clients/python \
     -c /local/openapi-config-python.yaml
   ```

3. **Test generated SDKs** (1 hour)

   **TypeScript:**
   ```typescript
   import { SmartParkingAPI } from './clients/typescript';

   const api = new SmartParkingAPI({
     baseURL: 'https://api.verdegris.eu',
     headers: { 'Authorization': 'Bearer <token>' }
   });

   // Test authentication
   const login = await api.auth.login({ email, password });

   // Test spaces
   const spaces = await api.spaces.list();
   ```

   **Python:**
   ```python
   from smart_parking_api import SmartParkingAPI, Configuration

   config = Configuration(
       host="https://api.verdegris.eu",
       access_token="<token>"
   )
   api = SmartParkingAPI(config)

   # Test authentication
   login = api.auth.login(email=email, password=password)

   # Test spaces
   spaces = api.spaces.list()
   ```

4. **Publish SDKs** (30 min)

   **npm (TypeScript):**
   ```bash
   cd clients/typescript
   npm publish --access public
   # Package name: @verdegris/smart-parking-api
   ```

   **PyPI (Python):**
   ```bash
   cd clients/python
   python setup.py sdist bdist_wheel
   twine upload dist/*
   # Package name: smart-parking-api
   ```

**Acceptance Criteria:**
- [ ] TypeScript SDK generated and tested
- [ ] Python SDK generated and tested
- [ ] SDKs published to npm and PyPI
- [ ] README with usage examples
- [ ] Version tagged (v5.3.0)

---

## B. Auth Polish

**Goal:** Implement refresh token flow and user profile endpoints

### B1. Implement Refresh Token Flow 🔐

**Priority:** 🟡 **HIGH** (security best practice)
**Effort:** 6-8 hours
**Dependencies:** None

#### Current State:
- JWTs are long-lived (24 hours)
- No refresh token mechanism
- Database has `refresh_tokens` table (migration 007) but unused

#### Target State:
- Short-lived access tokens (15 min)
- Long-lived refresh tokens (30 days)
- Refresh token rotation with reuse detection
- Automatic cleanup of expired tokens

#### Tasks:

1. **Update JWT settings** (30 min)

   **File:** `src/config.py`
   ```python
   # JWT Configuration
   JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
   JWT_ALGORITHM: str = "HS256"
   ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Changed from 1440 (24h)
   REFRESH_TOKEN_EXPIRE_DAYS: int = 30
   ```

2. **Create refresh token service** (2 hours)

   **File:** `src/refresh_token_service.py` (NEW)
   ```python
   """
   Refresh Token Service
   Handles refresh token creation, validation, rotation, and reuse detection
   """
   import secrets
   import hashlib
   from datetime import datetime, timedelta
   from uuid import UUID
   from typing import Optional, Tuple

   class RefreshTokenService:
       """Manages refresh tokens with rotation and reuse detection"""

       @staticmethod
       def generate_token() -> str:
           """Generate cryptographically secure refresh token"""
           return secrets.token_urlsafe(32)

       @staticmethod
       def hash_token(token: str) -> str:
           """Hash token for storage (SHA-256)"""
           return hashlib.sha256(token.encode()).hexdigest()

       async def create_refresh_token(
           self,
           db,
           user_id: UUID,
           device_fingerprint: Optional[str] = None,
           ip_address: Optional[str] = None,
           user_agent: Optional[str] = None
       ) -> str:
           """Create and store refresh token"""
           token = self.generate_token()
           token_hash = self.hash_token(token)

           expires_at = datetime.utcnow() + timedelta(days=30)

           await db.execute("""
               INSERT INTO refresh_tokens (
                   token_hash, user_id, expires_at,
                   device_fingerprint, ip_address, user_agent
               ) VALUES ($1, $2, $3, $4, $5, $6)
           """, token_hash, user_id, expires_at,
                device_fingerprint, ip_address, user_agent)

           return token

       async def validate_and_rotate(
           self,
           db,
           token: str,
           device_fingerprint: Optional[str] = None
       ) -> Tuple[Optional[UUID], Optional[str]]:
           """
           Validate refresh token and rotate it
           Returns (user_id, new_token) or (None, None) if invalid

           Implements reuse detection:
           - If token is revoked but recently used, revoke entire family
           - Prevents token replay attacks
           """
           token_hash = self.hash_token(token)

           # Check if token exists and is valid
           row = await db.fetchrow("""
               SELECT id, user_id, expires_at, revoked_at, last_used_at
               FROM refresh_tokens
               WHERE token_hash = $1
           """, token_hash)

           if not row:
               return None, None

           # Reuse detection: if token was already revoked recently, revoke family
           if row['revoked_at']:
               if row['last_used_at']:
                   time_since_use = datetime.utcnow() - row['last_used_at']
                   if time_since_use.total_seconds() < 300:  # 5 minutes
                       # Token reuse detected! Revoke all tokens for this user
                       await db.execute("""
                           UPDATE refresh_tokens
                           SET revoked_at = NOW()
                           WHERE user_id = $1 AND revoked_at IS NULL
                       """, row['user_id'])
                       return None, None
               return None, None

           # Check expiration
           if row['expires_at'] < datetime.utcnow():
               return None, None

           # Revoke old token
           await db.execute("""
               UPDATE refresh_tokens
               SET revoked_at = NOW(), last_used_at = NOW()
               WHERE id = $1
           """, row['id'])

           # Create new token (rotation)
           new_token = await self.create_refresh_token(
               db, row['user_id'], device_fingerprint
           )

           return row['user_id'], new_token
   ```

3. **Update login endpoint** (1 hour)

   **File:** `src/api_tenants.py` (modify existing `login` endpoint)
   ```python
   @router.post("/auth/login", response_model=LoginResponse)
   async def login(
       request: Request,
       login_req: LoginRequest,
       db: Pool = Depends(get_db)
   ):
       # ... existing authentication logic ...

       # Create access token (15 min)
       access_token = create_access_token(
           user_id=user_row['id'],
           tenant_id=primary_tenant['id'],
           role=UserRole(primary_tenant['role'])
       )

       # Create refresh token (30 days)
       refresh_service = RefreshTokenService()
       refresh_token = await refresh_service.create_refresh_token(
           db,
           user_id=user_row['id'],
           device_fingerprint=request.headers.get('X-Device-Fingerprint'),
           ip_address=request.client.host,
           user_agent=request.headers.get('User-Agent')
       )

       return LoginResponse(
           access_token=access_token,
           refresh_token=refresh_token,  # NEW
           token_type="bearer",
           expires_in=15 * 60,  # 15 minutes
           user=...,
           tenants=...
       )
   ```

4. **Implement refresh endpoint** (2 hours)

   **File:** `src/api_tenants.py` (NEW endpoint)
   ```python
   class RefreshRequest(BaseModel):
       refresh_token: str = Field(..., description="Refresh token from login")
       device_fingerprint: Optional[str] = None

   @router.post("/auth/refresh", response_model=LoginResponse)
   async def refresh_token(
       request: Request,
       refresh_req: RefreshRequest,
       db: Pool = Depends(get_db)
   ):
       """
       Refresh JWT access token using refresh token

       - Validates refresh token
       - Rotates refresh token (invalidates old, issues new)
       - Detects token reuse (security)
       - Returns new access token + new refresh token
       """
       refresh_service = RefreshTokenService()

       user_id, new_refresh_token = await refresh_service.validate_and_rotate(
           db,
           refresh_req.refresh_token,
           refresh_req.device_fingerprint
       )

       if not user_id:
           raise HTTPException(
               status_code=status.HTTP_401_UNAUTHORIZED,
               detail="Invalid or expired refresh token"
           )

       # Get user and tenant info
       user_row = await db.fetchrow("""
           SELECT id, email, name, is_active, email_verified
           FROM users WHERE id = $1
       """, user_id)

       if not user_row or not user_row['is_active']:
           raise HTTPException(
               status_code=status.HTTP_403_FORBIDDEN,
               detail="Account is inactive"
           )

       # Get user's primary tenant
       tenant_row = await db.fetchrow("""
           SELECT t.id, t.name, t.slug, um.role
           FROM user_memberships um
           JOIN tenants t ON um.tenant_id = t.id
           WHERE um.user_id = $1 AND um.is_active = true
           ORDER BY um.created_at ASC
           LIMIT 1
       """, user_id)

       if not tenant_row:
           raise HTTPException(
               status_code=status.HTTP_403_FORBIDDEN,
               detail="No active tenant membership"
           )

       # Create new access token
       access_token = create_access_token(
           user_id=user_id,
           tenant_id=tenant_row['id'],
           role=UserRole(tenant_row['role'])
       )

       return LoginResponse(
           access_token=access_token,
           refresh_token=new_refresh_token,
           token_type="bearer",
           expires_in=15 * 60,
           user=User(**user_row),
           tenants=[{
               "id": str(tenant_row['id']),
               "name": tenant_row['name'],
               "slug": tenant_row['slug'],
               "role": tenant_row['role']
           }]
       )
   ```

5. **Add cleanup background task** (1 hour)

   **File:** `src/background_tasks.py` (add to existing)
   ```python
   async def cleanup_expired_refresh_tokens(db_pool):
       """Delete expired refresh tokens (runs every 6 hours)"""
       while True:
           try:
               async with db_pool.acquire() as conn:
                   result = await conn.execute("""
                       DELETE FROM refresh_tokens
                       WHERE expires_at < NOW() - INTERVAL '7 days'
                   """)

                   deleted = int(result.split()[-1])
                   if deleted > 0:
                       logger.info(f"Cleaned up {deleted} expired refresh tokens")

               await asyncio.sleep(6 * 3600)  # 6 hours
           except Exception as e:
               logger.error(f"Refresh token cleanup error: {e}")
               await asyncio.sleep(60)
   ```

6. **Update response model** (30 min)

   **File:** `src/models.py`
   ```python
   class LoginResponse(BaseModel):
       access_token: str
       refresh_token: str  # NEW
       token_type: str = "bearer"
       expires_in: int  # seconds
       user: User
       tenants: List[Dict[str, Any]]
   ```

**Acceptance Criteria:**
- [ ] Access tokens expire in 15 minutes
- [ ] Refresh tokens expire in 30 days
- [ ] Refresh endpoint works (`POST /api/v1/auth/refresh`)
- [ ] Token rotation implemented (old token invalidated)
- [ ] Reuse detection works (revokes family on replay)
- [ ] Background cleanup task running
- [ ] Tests added for refresh flow

**Testing:**
```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"password"}'
# Save: access_token, refresh_token

# 2. Wait 16 minutes (access token expires)

# 3. Refresh token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<saved_refresh_token>"}'
# Receive: new access_token, new refresh_token

# 4. Try to reuse old refresh token (should fail)
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<old_refresh_token>"}'
# Should return 401 Unauthorized
```

---

### B2. Implement User Profile Endpoints 👤

**Priority:** 🟡 **HIGH** (partner requirement)
**Effort:** 2-3 hours
**Dependencies:** None

#### Tasks:

1. **Implement /api/v1/me endpoint** (1.5 hours)

   **File:** `src/api_tenants.py` (NEW endpoint)
   ```python
   @router.get("/me", response_model=Dict[str, Any])
   async def get_current_user(
       request: Request,
       tenant: TenantContext = Depends(get_current_tenant),
       db: Pool = Depends(get_db)
   ):
       """
       Get current user profile

       Returns user info, active tenant, role, and permissions
       """
       user_row = await db.fetchrow("""
           SELECT id, email, name, is_active, email_verified, created_at, last_login_at
           FROM users
           WHERE id = $1
       """, tenant.user_id)

       if not user_row:
           raise HTTPException(status_code=404, detail="User not found")

       # Get all tenant memberships
       memberships = await db.fetch("""
           SELECT
               t.id as tenant_id,
               t.name as tenant_name,
               t.slug as tenant_slug,
               um.role,
               um.is_active,
               um.created_at as joined_at
           FROM user_memberships um
           JOIN tenants t ON um.tenant_id = t.id
           WHERE um.user_id = $1
           ORDER BY um.created_at ASC
       """, tenant.user_id)

       # Get API keys for current tenant
       api_keys = await db.fetch("""
           SELECT id, name, scopes, created_at, last_used_at
           FROM api_keys
           WHERE user_id = $1 AND tenant_id = $2 AND revoked_at IS NULL
       """, tenant.user_id, tenant.tenant_id)

       return {
           "id": str(user_row['id']),
           "email": user_row['email'],
           "name": user_row['name'],
           "is_active": user_row['is_active'],
           "email_verified": user_row['email_verified'],
           "created_at": user_row['created_at'].isoformat(),
           "last_login_at": user_row['last_login_at'].isoformat() if user_row['last_login_at'] else None,
           "current_tenant": {
               "id": str(tenant.tenant_id),
               "role": tenant.role.value,
               "permissions": tenant.role.get_permissions()
           },
           "tenants": [
               {
                   "id": str(m['tenant_id']),
                   "name": m['tenant_name'],
                   "slug": m['tenant_slug'],
                   "role": m['role'],
                   "is_active": m['is_active'],
                   "joined_at": m['joined_at'].isoformat()
               }
               for m in memberships
           ],
           "api_keys": [
               {
                   "id": str(k['id']),
                   "name": k['name'],
                   "scopes": k['scopes'],
                   "created_at": k['created_at'].isoformat(),
                   "last_used_at": k['last_used_at'].isoformat() if k['last_used_at'] else None
               }
               for k in api_keys
           ]
       }
   ```

2. **Implement /api/v1/me/limits endpoint** (1.5 hours)

   **File:** `src/api_tenants.py` (NEW endpoint)
   ```python
   @router.get("/me/limits", response_model=Dict[str, Any])
   async def get_current_user_limits(
       request: Request,
       tenant: TenantContext = Depends(get_current_tenant)
   ):
       """
       Get current user's rate limits and usage

       Returns rate limit status for API requests
       """
       rate_limiter = request.app.state.rate_limiter

       # Get rate limit config for tenant
       rate_limit_key = f"rate_limit:{tenant.tenant_id}"

       # Get current usage from Redis
       current_count = await rate_limiter.redis_client.get(rate_limit_key)
       current_count = int(current_count) if current_count else 0

       # Get rate limit config from tenant settings
       tenant_limits = await db.fetchrow("""
           SELECT
               rate_limit_per_minute,
               rate_limit_per_hour,
               rate_limit_per_day
           FROM tenants
           WHERE id = $1
       """, tenant.tenant_id)

       if not tenant_limits:
           tenant_limits = {
               'rate_limit_per_minute': 100,
               'rate_limit_per_hour': 5000,
               'rate_limit_per_day': 100000
           }

       # Calculate remaining
       remaining = max(0, tenant_limits['rate_limit_per_minute'] - current_count)

       # Get reset time (next minute boundary)
       now = datetime.utcnow()
       reset_at = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

       return {
           "rate_limits": {
               "per_minute": tenant_limits['rate_limit_per_minute'],
               "per_hour": tenant_limits['rate_limit_per_hour'],
               "per_day": tenant_limits['rate_limit_per_day']
           },
           "current_usage": {
               "requests_this_minute": current_count,
               "remaining_this_minute": remaining,
               "reset_at": reset_at.isoformat()
           },
           "tenant": {
               "id": str(tenant.tenant_id),
               "role": tenant.role.value
           }
       }
   ```

**Acceptance Criteria:**
- [ ] `GET /api/v1/me` returns user profile
- [ ] Includes all tenant memberships
- [ ] Includes current tenant and role
- [ ] `GET /api/v1/me/limits` returns rate limit status
- [ ] Shows current usage and remaining quota
- [ ] Tests added

**Testing:**
```bash
# Get current user profile
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/me

# Get rate limits
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/me/limits
```

---

## C. Ops & Resilience

**Goal:** Improve operational resilience and monitoring

### C1. Redis High Availability 🔴

**Priority:** 🔴 **CRITICAL** (production readiness)
**Effort:** 4-6 hours
**Dependencies:** None

#### Tasks:

1. **Enable Redis AOF (Append-Only File)** (1 hour)

   **File:** `docker-compose.yml`
   ```yaml
   redis:
     image: redis:7-alpine
     command: >
       redis-server
       --appendonly yes
       --appendfsync everysec
       --auto-aof-rewrite-percentage 100
       --auto-aof-rewrite-min-size 64mb
       --maxmemory 512mb
       --maxmemory-policy allkeys-lru
     volumes:
       - redis_data:/data
     healthcheck:
       test: ["CMD", "redis-cli", "ping"]
       interval: 10s
       timeout: 3s
       retries: 3
   ```

2. **Add Redis Sentinel for HA** (3 hours)

   **File:** `docker-compose.yml` (add sentinel services)
   ```yaml
   redis-sentinel-1:
     image: redis:7-alpine
     command: >
       redis-sentinel /etc/redis/sentinel.conf
       --sentinel announce-ip redis-sentinel-1
     volumes:
       - ./config/redis/sentinel.conf:/etc/redis/sentinel.conf
     depends_on:
       - redis

   redis-sentinel-2:
     image: redis:7-alpine
     command: >
       redis-sentinel /etc/redis/sentinel.conf
       --sentinel announce-ip redis-sentinel-2
     volumes:
       - ./config/redis/sentinel.conf:/etc/redis/sentinel.conf
     depends_on:
       - redis

   redis-sentinel-3:
     image: redis:7-alpine
     command: >
       redis-sentinel /etc/redis/sentinel.conf
       --sentinel announce-ip redis-sentinel-3
     volumes:
       - ./config/redis/sentinel.conf:/etc/redis/sentinel.conf
     depends_on:
       - redis
   ```

   **File:** `config/redis/sentinel.conf` (NEW)
   ```
   sentinel monitor mymaster redis 6379 2
   sentinel down-after-milliseconds mymaster 5000
   sentinel parallel-syncs mymaster 1
   sentinel failover-timeout mymaster 10000
   ```

3. **Update Redis client for Sentinel** (2 hours)

   **File:** `src/config.py`
   ```python
   REDIS_SENTINEL_HOSTS: List[str] = os.getenv(
       "REDIS_SENTINEL_HOSTS",
       "redis-sentinel-1:26379,redis-sentinel-2:26379,redis-sentinel-3:26379"
   ).split(",")
   REDIS_MASTER_NAME: str = "mymaster"
   ```

   **File:** `src/database.py` (update Redis connection)
   ```python
   from redis.sentinel import Sentinel

   # Create Sentinel connection
   sentinel = Sentinel(
       [(host.split(':')[0], int(host.split(':')[1]))
        for host in settings.REDIS_SENTINEL_HOSTS],
       socket_timeout=0.5
   )

   # Get master
   redis_client = sentinel.master_for(
       settings.REDIS_MASTER_NAME,
       socket_timeout=1.0,
       socket_connect_timeout=1.0
   )
   ```

**Acceptance Criteria:**
- [ ] Redis AOF enabled
- [ ] 3 Sentinel instances running
- [ ] Automatic failover tested
- [ ] Application reconnects after failover
- [ ] No data loss during failover

---

### C2. Database Connection Pooling & Timeouts ⚡

**Priority:** 🟡 **HIGH** (prevents connection leaks)
**Effort:** 2-3 hours
**Dependencies:** None

#### Tasks:

1. **Add connection timeouts** (1 hour)

   **File:** `src/config.py`
   ```python
   # Database Configuration
   DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
   DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
   DB_COMMAND_TIMEOUT: int = int(os.getenv("DB_COMMAND_TIMEOUT", "30"))  # NEW
   DB_CONNECT_TIMEOUT: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))  # NEW
   DB_IDLE_TIMEOUT: int = int(os.getenv("DB_IDLE_TIMEOUT", "300"))  # NEW (5 min)
   ```

   **File:** `src/database.py`
   ```python
   self.pool = await asyncpg.create_pool(
       dsn=settings.database_url,
       min_size=settings.DB_POOL_MIN_SIZE,
       max_size=settings.DB_POOL_MAX_SIZE,
       command_timeout=settings.DB_COMMAND_TIMEOUT,  # NEW
       timeout=settings.DB_CONNECT_TIMEOUT,  # NEW
       max_inactive_connection_lifetime=settings.DB_IDLE_TIMEOUT  # NEW
   )
   ```

2. **Add connection health checks** (1 hour)

   **File:** `src/database.py`
   ```python
   async def _connection_init(conn):
       """Initialize connection with custom settings"""
       # Set statement timeout
       await conn.execute("SET statement_timeout = '30s'")
       # Set application name for monitoring
       await conn.execute("SET application_name = 'parking-api'")

   self.pool = await asyncpg.create_pool(
       dsn=settings.database_url,
       min_size=settings.DB_POOL_MIN_SIZE,
       max_size=settings.DB_POOL_MAX_SIZE,
       command_timeout=settings.DB_COMMAND_TIMEOUT,
       timeout=settings.DB_CONNECT_TIMEOUT,
       max_inactive_connection_lifetime=settings.DB_IDLE_TIMEOUT,
       init=_connection_init  # NEW
   )
   ```

3. **Add pool monitoring** (1 hour)

   **File:** `src/database.py`
   ```python
   def get_pool_stats(self) -> Dict[str, Any]:
       """Get connection pool statistics"""
       if not self.pool:
           return {}

       return {
           "size": self.pool.get_size(),
           "min_size": self.pool.get_min_size(),
           "max_size": self.pool.get_max_size(),
           "free_connections": self.pool.get_idle_size(),
           "used_connections": self.pool.get_size() - self.pool.get_idle_size()
       }
   ```

   **Expose in health endpoint:**
   ```python
   @app.get("/health")
   async def health_check(request: Request):
       db_pool = request.app.state.db_pool
       pool_stats = db_pool.get_pool_stats()

       # Alert if pool is exhausted
       if pool_stats.get('free_connections', 0) == 0:
           overall_status = "degraded"
   ```

**Acceptance Criteria:**
- [ ] Connection timeouts configured
- [ ] Idle connection cleanup working
- [ ] Pool statistics exposed in /health
- [ ] Alerts triggered on pool exhaustion
- [ ] No connection leaks under load

---

### C3. Webhook Replay Protection 🛡️

**Priority:** 🟡 **HIGH** (security)
**Effort:** 2-3 hours
**Dependencies:** None

#### Tasks:

1. **Add replay window validation** (2 hours)

   **File:** `src/webhook_validation.py` (enhance existing)
   ```python
   import hmac
   import hashlib
   from datetime import datetime, timedelta

   WEBHOOK_REPLAY_WINDOW_SECONDS = 300  # 5 minutes

   def validate_webhook_signature(
       payload: bytes,
       signature_header: str,
       timestamp_header: str,
       nonce_header: str,
       secret: str
   ) -> bool:
       """
       Validate webhook signature with replay protection

       Checks:
       1. Signature is valid (HMAC-SHA256)
       2. Timestamp is within replay window (5 min)
       3. Nonce has not been seen before (Redis cache)
       """
       # Parse signature
       if not signature_header.startswith('sha256='):
           raise ValueError("Invalid signature format")

       provided_signature = signature_header[7:]  # Remove 'sha256=' prefix

       # Parse timestamp
       try:
           timestamp = datetime.fromisoformat(timestamp_header.replace('Z', '+00:00'))
       except ValueError:
           raise ValueError("Invalid timestamp format")

       # Check replay window
       now = datetime.utcnow()
       age = (now - timestamp).total_seconds()

       if age < 0:
           raise ValueError("Timestamp is in the future")

       if age > WEBHOOK_REPLAY_WINDOW_SECONDS:
           raise ValueError(f"Webhook is too old ({age:.0f}s, max {WEBHOOK_REPLAY_WINDOW_SECONDS}s)")

       # Compute expected signature
       signed_payload = f"{timestamp_header}.{nonce_header}.{payload.decode('utf-8')}"
       expected_signature = hmac.new(
           secret.encode(),
           signed_payload.encode(),
           hashlib.sha256
       ).hexdigest()

       # Constant-time comparison
       if not hmac.compare_digest(provided_signature, expected_signature):
           raise ValueError("Signature mismatch")

       return True

   async def check_nonce_replay(redis_client, nonce: str) -> bool:
       """
       Check if nonce has been used before (replay attack)

       Returns True if nonce is new (safe), False if replay detected
       """
       key = f"webhook_nonce:{nonce}"

       # Try to set with NX (only if not exists)
       was_set = await redis_client.set(
           key,
           "1",
           nx=True,
           ex=WEBHOOK_REPLAY_WINDOW_SECONDS + 60  # Keep for window + buffer
       )

       return was_set  # True if new, False if replay
   ```

2. **Update webhook endpoint** (1 hour)

   **File:** `src/main_tenanted.py` or webhook router
   ```python
   @app.post("/webhooks/uplink")
   async def handle_uplink_webhook(
       request: Request,
       signature: str = Header(..., alias="X-Chirpstack-Signature"),
       timestamp: str = Header(..., alias="X-Timestamp"),
       nonce: str = Header(..., alias="X-Nonce")
   ):
       redis_client = request.app.state.rate_limiter.redis_client

       # Read body
       body = await request.body()

       # Check nonce replay
       is_new_nonce = await check_nonce_replay(redis_client, nonce)
       if not is_new_nonce:
           logger.warning(f"Webhook replay detected: nonce={nonce}")
           raise HTTPException(
               status_code=status.HTTP_409_CONFLICT,
               detail="Duplicate webhook (nonce replay detected)"
           )

       # Validate signature with replay window
       try:
           validate_webhook_signature(
               body, signature, timestamp, nonce, webhook_secret
           )
       except ValueError as e:
           logger.warning(f"Webhook validation failed: {e}")
           raise HTTPException(
               status_code=status.HTTP_401_UNAUTHORIZED,
               detail=str(e)
           )

       # Process webhook
       # ...
   ```

**Acceptance Criteria:**
- [ ] Webhooks older than 5 minutes rejected
- [ ] Nonce replay detected and rejected
- [ ] Redis used for nonce deduplication
- [ ] Metrics track replay attempts
- [ ] Tests added

---

### C4. Alerting & SLO Monitoring 📊

**Priority:** 🟡 **HIGH** (observability)
**Effort:** 3-4 hours
**Dependencies:** Prometheus metrics (already implemented)

#### Tasks:

1. **Add Prometheus alert rules** (2 hours)

   **File:** `monitoring/prometheus/alerts.yml` (NEW)
   ```yaml
   groups:
     - name: parking_api_alerts
       interval: 30s
       rules:
         # High error rate
         - alert: HighErrorRate
           expr: rate(uplink_requests_total{status="error"}[5m]) > 0.01
           for: 5m
           labels:
             severity: warning
           annotations:
             summary: "High error rate detected"
             description: "Error rate is {{ $value }} requests/sec"

         # Downlink queue backing up
         - alert: DownlinkQueueBacklog
           expr: downlink_queue_depth > 100
           for: 10m
           labels:
             severity: warning
           annotations:
             summary: "Downlink queue has {{ $value }} pending commands"

         # Dead letter queue accumulating
         - alert: DeadLetterQueueGrowing
           expr: downlink_dead_letter_depth > 10
           for: 5m
           labels:
             severity: critical
           annotations:
             summary: "Dead letter queue has {{ $value }} failed commands"

         # Actuation SLO breach (p95 > 5s)
         - alert: ActuationLatencySLOBreach
           expr: histogram_quantile(0.95, rate(actuation_latency_seconds_bucket[5m])) > 5
           for: 10m
           labels:
             severity: warning
           annotations:
             summary: "Actuation latency p95 is {{ $value }}s (SLO: 5s)"

         # Database pool exhaustion
         - alert: DatabasePoolExhausted
           expr: db_connection_pool_free == 0
           for: 2m
           labels:
             severity: critical
           annotations:
             summary: "Database connection pool exhausted"

         # Redis connection issues
         - alert: RedisDown
           expr: up{job="redis"} == 0
           for: 1m
           labels:
             severity: critical
           annotations:
             summary: "Redis is down"

         # ChirpStack unreachable
         - alert: ChirpStackDown
           expr: chirpstack_api_latency_seconds{status="error"} > 0
           for: 5m
           labels:
             severity: critical
           annotations:
             summary: "ChirpStack API is unreachable"
   ```

2. **Add Grafana dashboards** (2 hours)

   **File:** `monitoring/grafana/dashboards/parking-api.json` (NEW)
   ```json
   {
     "dashboard": {
       "title": "Smart Parking API",
       "panels": [
         {
           "title": "Request Rate",
           "targets": [{
             "expr": "rate(uplink_requests_total[5m])"
           }]
         },
         {
           "title": "Actuation Latency (p95)",
           "targets": [{
             "expr": "histogram_quantile(0.95, rate(actuation_latency_seconds_bucket[5m]))"
           }]
         },
         {
           "title": "Downlink Queue Depth",
           "targets": [{
             "expr": "downlink_queue_depth"
           }]
         },
         {
           "title": "Database Pool Usage",
           "targets": [{
             "expr": "db_connection_pool_size - db_connection_pool_free"
           }]
         }
       ]
     }
   }
   ```

**Acceptance Criteria:**
- [ ] Alert rules defined
- [ ] Grafana dashboards created
- [ ] Alerts integrated with PagerDuty/Slack
- [ ] SLO tracking dashboard visible
- [ ] On-call runbook linked

---

## D. Device Management Convenience Endpoints

**Priority:** 🟢 **MEDIUM** (spec compliance)
**Effort:** 2-3 hours
**Dependencies:** None

### Tasks:

1. **Add device assignment endpoints** (2 hours)

   **File:** `src/routers/spaces_tenanted.py` (add to existing)
   ```python
   @router.post("/{space_id}/sensor", status_code=201)
   async def assign_sensor_to_space(
       space_id: UUID,
       request: Request,
       device_eui: str = Body(..., embed=True),
       tenant: TenantContext = Depends(require_admin),
       db: Pool = Depends(get_db)
   ):
       """Assign sensor device to space"""
       # Validate sensor exists
       sensor = await db.fetchrow("""
           SELECT id FROM sensor_devices WHERE dev_eui = $1
       """, device_eui.upper())

       if not sensor:
           raise HTTPException(404, "Sensor not found")

       # Update space
       await db.execute("""
           UPDATE spaces
           SET sensor_eui = $1, updated_at = NOW()
           WHERE id = $2 AND tenant_id = $3 AND deleted_at IS NULL
       """, device_eui.upper(), space_id, tenant.tenant_id)

       return {"message": "Sensor assigned", "space_id": str(space_id), "sensor_eui": device_eui.upper()}

   @router.delete("/{space_id}/sensor", status_code=204)
   async def unassign_sensor_from_space(
       space_id: UUID,
       tenant: TenantContext = Depends(require_admin),
       db: Pool = Depends(get_db)
   ):
       """Remove sensor from space"""
       await db.execute("""
           UPDATE spaces
           SET sensor_eui = NULL, updated_at = NOW()
           WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
       """, space_id, tenant.tenant_id)

   @router.post("/{space_id}/display", status_code=201)
   async def assign_display_to_space(
       space_id: UUID,
       request: Request,
       device_eui: str = Body(..., embed=True),
       tenant: TenantContext = Depends(require_admin),
       db: Pool = Depends(get_db)
   ):
       """Assign display device to space"""
       # Similar to sensor assignment
       # ...

   @router.delete("/{space_id}/display", status_code=204)
   async def unassign_display_from_space(
       space_id: UUID,
       tenant: TenantContext = Depends(require_admin),
       db: Pool = Depends(get_db)
   ):
       """Remove display from space"""
       # ...
   ```

**Acceptance Criteria:**
- [ ] POST /api/v1/spaces/{space_id}/sensor works
- [ ] DELETE /api/v1/spaces/{space_id}/sensor works
- [ ] POST /api/v1/spaces/{space_id}/display works
- [ ] DELETE /api/v1/spaces/{space_id}/display works
- [ ] Tests added

---

## E. Manual Actuation Endpoint

**Priority:** 🟢 **LOW** (operational convenience)
**Effort:** 1-2 hours
**Dependencies:** None

### Tasks:

1. **Implement manual actuation** (1.5 hours)

   **File:** `src/routers/spaces_tenanted.py`
   ```python
   @router.post("/{space_id}/actuate", status_code=202)
   async def manually_actuate_display(
       space_id: UUID,
       request: Request,
       force_state: Optional[str] = Body(None),
       tenant: TenantContext = Depends(require_admin),
       db: Pool = Depends(get_db)
   ):
       """
       Manually trigger display update for a space

       Useful for:
       - Testing display devices
       - Forcing state refresh
       - Debugging state machine issues
       """
       # Get space with display
       space = await db.fetchrow("""
           SELECT id, code, name, display_eui, state
           FROM spaces
           WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
       """, space_id, tenant.tenant_id)

       if not space:
           raise HTTPException(404, "Space not found")

       if not space['display_eui']:
           raise HTTPException(400, "Space has no display assigned")

       # Get state manager
       state_manager = request.app.state.state_manager

       # Determine state to show
       if force_state:
           # Admin override
           display_state = force_state.upper()
       else:
           # Compute current state via state machine
           display_state = await state_manager.compute_display_state(
               space_id, tenant.tenant_id
           )

       # Enqueue downlink
       downlink_queue = request.app.state.downlink_queue
       await downlink_queue.enqueue_display_update(
           display_eui=space['display_eui'],
           state=display_state,
           space_id=space_id,
           tenant_id=tenant.tenant_id
       )

       return {
           "message": "Display actuation queued",
           "space_id": str(space_id),
           "display_eui": space['display_eui'],
           "state": display_state,
           "queued_at": datetime.utcnow().isoformat()
       }
   ```

**Acceptance Criteria:**
- [ ] POST /api/v1/spaces/{space_id}/actuate works
- [ ] Optional force_state parameter
- [ ] Returns 202 Accepted (async)
- [ ] Logged in audit trail
- [ ] Tests added

---

## Implementation Timeline

### Week 1 (High Priority)
- **Day 1-2:** Refresh token flow (B1) - 8 hours
- **Day 3:** User profile endpoints (B2) - 3 hours
- **Day 4:** Update OpenAPI spec (A1) - 4 hours
- **Day 5:** Generate & test SDKs (A2) - 3 hours

### Week 2 (Ops & Resilience)
- **Day 1-2:** Redis HA setup (C1) - 6 hours
- **Day 3:** Database timeouts & pooling (C2) - 3 hours
- **Day 4:** Webhook replay protection (C3) - 3 hours
- **Day 5:** Alerting & monitoring (C4) - 4 hours

### Week 3 (Polish)
- **Day 1:** Device assignment endpoints (D) - 2 hours
- **Day 2:** Manual actuation endpoint (E) - 2 hours
- **Day 3-4:** Testing & documentation
- **Day 5:** Deploy to production

---

## Success Metrics

### Before Implementation
- ❌ JWT access tokens: 24 hours (too long)
- ❌ No refresh token flow
- ❌ No user profile endpoints
- ❌ OpenAPI spec: 75% compliance
- ❌ Redis: Single instance (no HA)
- ❌ No webhook replay protection
- ❌ Manual alerting

### After Implementation
- ✅ JWT access tokens: 15 minutes
- ✅ Refresh tokens: 30 days with rotation
- ✅ User profile endpoints working
- ✅ OpenAPI spec: 100% compliance
- ✅ SDKs published (npm + PyPI)
- ✅ Redis: Sentinel HA with AOF
- ✅ Webhook replay window enforced
- ✅ Automated alerting on SLO breaches

---

## Risk Mitigation

### High-Risk Changes
1. **Refresh token flow** - Breaking change for existing clients
   - **Mitigation:** Deploy with backward compatibility (support both 24h and 15min tokens during transition)
   - **Rollback:** Revert JWT expiry to 24h

2. **Redis Sentinel** - Complex deployment
   - **Mitigation:** Test failover thoroughly in staging
   - **Rollback:** Fall back to single Redis instance

3. **Access token TTL change** - May break existing sessions
   - **Mitigation:** Gradual rollout (1h → 30m → 15m)
   - **Rollback:** Increase TTL if error rate spikes

### Testing Strategy
- **Unit tests:** All new endpoints
- **Integration tests:** Full auth flow
- **Load tests:** Verify performance
- **Chaos tests:** Redis failover, DB timeout scenarios

---

## Done Criteria

**A. Spec & SDKs:**
- [ ] OpenAPI spec updated to 100% compliance
- [ ] TypeScript SDK published to npm
- [ ] Python SDK published to PyPI
- [ ] SDK documentation complete

**B. Auth Polish:**
- [ ] Refresh token flow working
- [ ] Access token TTL: 15 minutes
- [ ] /api/v1/me endpoint working
- [ ] /api/v1/me/limits endpoint working

**C. Ops & Resilience:**
- [ ] Redis Sentinel HA deployed
- [ ] AOF persistence enabled
- [ ] Database timeouts configured
- [ ] Webhook replay protection active
- [ ] Prometheus alerts configured
- [ ] Grafana dashboards deployed

**D. Device Management:**
- [ ] All 4 device assignment endpoints working

**E. Manual Actuation:**
- [ ] Manual actuation endpoint working

---

## Support & Questions

For questions or issues during implementation:
1. Check this action plan first
2. Review implementation guides in `docs/`
3. Test in staging environment
4. Coordinate breaking changes with partners

**Status:** 🚀 READY TO IMPLEMENT
