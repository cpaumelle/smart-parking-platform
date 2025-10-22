# Security & Tenancy Isolation - v5.3

**Purpose:** Documentation of security controls, tenant isolation, and operational security practices.

**Last Updated:** 2025-10-20

**Requirements:** `docs/v5.3-07-security-tenancy.md`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Authorization & Scopes](#authorization--scopes)
3. [Tenant Isolation](#tenant-isolation)
4. [Audit Logging](#audit-logging)
5. [API Key Management](#api-key-management)
6. [Secret Management](#secret-management)
7. [Security Best Practices](#security-best-practices)
8. [Penetration Testing](#penetration-testing)

---

## Authentication

### User Authentication (JWT)

**Implementation:** `src/tenant_auth.py`

#### Access Tokens (Short-Lived)

- **Algorithm:** HS256 (HMAC-SHA256)
- **Expiry:** 24 hours (configurable)
- **Payload:**
  ```json
  {
    "user_id": "uuid",
    "tenant_id": "uuid",
    "role": "owner|admin|operator|viewer",
    "exp": 1234567890,
    "iat": 1234567890
  }
  ```

#### Refresh Tokens (Long-Lived)

**Implementation:** `migrations/007_audit_log.sql` (`refresh_tokens` table)

- **Storage:** Database (SHA-256 hashed)
- **Expiry:** 30 days
- **Features:**
  - Device fingerprinting
  - IP address tracking
  - Last used timestamp
  - Revocation support

**Rotation Flow:**

```
1. Client sends refresh token to POST /auth/refresh
2. Server validates token (hash lookup, expiry check, revoked_at = NULL)
3. Server issues new access token (24h expiry)
4. Server updates refresh_token.last_used_at
5. Client stores new access token
```

#### Password Hashing

**Current:** bcrypt (implemented in `src/tenant_auth.py`)
**Recommended Upgrade:** Argon2 (industry best practice)

```python
# TODO: Migrate to Argon2
from argon2 import PasswordHasher
ph = PasswordHasher()
hash = ph.hash(password)
ph.verify(hash, password)
```

### Service Authentication (API Keys)

**Implementation:** `src/auth.py`, `src/api_scopes.py`

- **Format:** 32-byte random token (64 hex characters)
- **Storage:** SHA-256 hash in `api_keys` table
- **Binding:** Scoped to `tenant_id` (cannot cross tenants)
- **Scopes:** Least-privilege access control

**API Key Header:**
```
X-API-Key: <64-char-hex-string>
```

---

## Authorization & Scopes

### Role-Based Access Control (RBAC)

**Roles:** (highest to lowest privilege)

1. **Owner** - Full control, can delete tenant
2. **Admin** - Manage users, spaces, devices, reservations
3. **Operator** - Manage spaces and reservations (read-only on users/devices)
4. **Viewer** - Read-only access

**Implementation:** `src/models.py` (`UserRole` enum)

### Scoped API Keys

**Scope Format:** `resource:permission`

**Available Scopes:**

| Scope | Permissions Granted |
|-------|---------------------|
| `spaces:read` | View spaces |
| `spaces:write` | Create/update spaces (includes read) |
| `devices:read` | View devices |
| `devices:write` | Manage devices (includes read) |
| `reservations:read` | View reservations |
| `reservations:write` | Create/cancel reservations (includes read) |
| `telemetry:read` | Access sensor telemetry |
| `webhook:ingest` | Submit uplinks (webhook-only) |
| `admin:*` | Full access (use sparingly) |

**Scope Enforcement:** `src/api_scopes.py:check_scopes()`

**Example:**

```python
from src.api_scopes import require_scopes

@router.post("/spaces")
@require_scopes({"spaces:write"})
async def create_space(tenant: TenantContext = Depends(get_current_tenant)):
    # Only API keys with spaces:write scope can access
    pass
```

---

## Tenant Isolation

### Database-Level Isolation

**All tables include `tenant_id` column** (enforced by foreign key to `tenants` table)

#### Tenant-Scoped Tables

- `users` - User belongs to one tenant
- `sites` - Site belongs to one tenant
- `spaces` - Space belongs to one tenant (via site)
- `devices` - Device assigned to space (scoped by tenant)
- `reservations` - Reservation scoped to space/tenant
- `display_policies` - One active policy per tenant
- `api_keys` - API key bound to tenant_id

#### Cross-Tenant Protection

**Repository Layer Checks:** All database queries include `tenant_id` filter

```python
# Good - Tenant-scoped query
spaces = await db.fetch("""
    SELECT * FROM spaces
    WHERE tenant_id = $1 AND deleted_at IS NULL
""", tenant_id)

# Bad - Missing tenant_id filter (cross-tenant leak!)
spaces = await db.fetch("SELECT * FROM spaces WHERE deleted_at IS NULL")
```

**Defensive Checks:**

Every repository method MUST:
1. Accept `tenant_id` parameter
2. Include `WHERE tenant_id = $1` in SQL
3. Validate resource belongs to tenant before update/delete

**Example:**

```python
async def get_space(self, space_id: UUID, tenant_id: UUID):
    """Get space - tenant-scoped"""
    space = await self.db.fetchrow("""
        SELECT * FROM spaces
        WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
    """, space_id, tenant_id)

    if not space:
        raise SpaceNotFoundError(f"Space {space_id} not found for tenant {tenant_id}")

    return space
```

### API-Level Isolation

**Tenant Context Injection:**

Every authenticated request has `TenantContext`:

```python
class TenantContext:
    tenant_id: UUID
    user_id: Optional[UUID]
    role: Optional[UserRole]
    api_key_id: Optional[UUID]
    api_key_scopes: Optional[Set[str]]
    source: str  # 'jwt' or 'api_key'
```

**Enforcement:**

```python
from src.tenant_auth import get_current_tenant

@router.get("/spaces")
async def list_spaces(tenant: TenantContext = Depends(get_current_tenant)):
    # tenant.tenant_id is guaranteed to be the authenticated tenant
    spaces = await db.get_spaces(tenant_id=tenant.tenant_id)
    return spaces
```

---

## Audit Logging

### Implementation

**Database:** `migrations/007_audit_log.sql`
**Service:** `src/audit.py`

### Features

- **Append-Only:** Database trigger prevents UPDATE/DELETE
- **Tenant-Scoped:** All logs include `tenant_id`
- **Actor Tracking:** Records who (user, API key, system, webhook)
- **Change Tracking:** Stores old_values → new_values for updates
- **Request Correlation:** `request_id` for distributed tracing

### Schema

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE,

    -- Who
    tenant_id UUID NOT NULL,
    user_id UUID,
    api_key_id UUID,
    actor_type VARCHAR(20),  -- 'user', 'api_key', 'system', 'webhook'
    actor_name VARCHAR(255),

    -- What
    action VARCHAR(100),  -- 'space.create', 'reservation.delete'
    resource_type VARCHAR(50),
    resource_id UUID,

    -- Details
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,

    -- Context
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(36),

    -- Result
    success BOOLEAN,
    error_message TEXT
);
```

### Usage

```python
from src.audit import get_audit_logger

audit = get_audit_logger()

# Log user action
await audit.log_user_action(
    tenant_id=tenant_id,
    user_id=user_id,
    user_email=user_email,
    action="space.create",
    resource_type="space",
    resource_id=space_id,
    new_values={"code": "A-101", "state": "free"}
)

# Log API key action
await audit.log_api_key_action(
    tenant_id=tenant_id,
    api_key_id=api_key_id,
    api_key_name="Webhook Ingester",
    action="reservation.create",
    resource_type="reservation",
    resource_id=reservation_id
)

# Log system action
await audit.log_system_action(
    tenant_id=tenant_id,
    action="space.state_transition",
    resource_type="space",
    system_name="state_manager",
    resource_id=space_id,
    metadata={"from": "free", "to": "occupied"}
)
```

### Querying Audit Log

```python
# Get audit log for tenant
logs = await audit.get_tenant_audit_log(
    tenant_id=tenant_id,
    limit=100,
    action_filter="space.delete",
    user_id_filter=user_id
)
```

### Audit Actions (Standard Naming)

**Format:** `resource.verb`

**Examples:**
- `space.create`, `space.update`, `space.delete`
- `reservation.create`, `reservation.cancel`
- `device.assign`, `device.unassign`
- `user.create`, `user.update_role`, `user.delete`
- `api_key.create`, `api_key.revoke`
- `display_policy.activate`

---

## API Key Management

### Creating API Keys

```python
# Via API (admin only)
POST /api/v1/tenants/{tenant_id}/api-keys
{
  "name": "Webhook Ingester",
  "scopes": ["webhook:ingest"],
  "expires_at": "2026-01-01T00:00:00Z"
}

# Response (key shown ONCE only)
{
  "id": "uuid",
  "name": "Webhook Ingester",
  "key": "<64-char-hex-string>",  # Store securely!
  "scopes": ["webhook:ingest"],
  "created_at": "2025-10-20T12:00:00Z",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

### Revoking API Keys

**Implementation:** `migrations/007_audit_log.sql` (adds `revoked_at`, `revoked_by` columns)

```python
# Via API
DELETE /api/v1/tenants/{tenant_id}/api-keys/{key_id}

# Via SQL
UPDATE api_keys
SET revoked_at = NOW(), revoked_by = $1
WHERE id = $2 AND tenant_id = $3;
```

**Effective Immediately:**
- Revoked keys fail authentication on next request
- No grace period (prevent compromised key usage)

### Key Rotation

**Process:**

1. Create new API key with same scopes
2. Update clients to use new key
3. Verify new key works
4. Revoke old key
5. Audit log records both actions

**Recommended Frequency:** Quarterly (every 90 days)

### Key Inventory

```sql
-- List all active API keys for tenant
SELECT
    id, name, scopes, created_at, expires_at, last_used_at
FROM api_keys
WHERE tenant_id = $1
AND revoked_at IS NULL
AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY created_at DESC;
```

---

## Secret Management

### Environment Variables

**Never commit secrets to git!**

Use `.env` file (gitignored):

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/parking
JWT_SECRET_KEY=<64-char-hex-string>
CHIRPSTACK_API_KEY=<api-key>
REDIS_URL=redis://localhost:6379
```

### Secret Manager (Recommended for Production)

**Options:**
- **1Password Secrets Automation**
- **HashiCorp Vault**
- **AWS Secrets Manager**
- **Azure Key Vault**

**Integration Example (1Password):**

```bash
# Install 1Password CLI
brew install 1password-cli

# Load secrets into environment
eval $(op run --env-file=.env.tpl -- env)

# Run app
uvicorn src.main:app
```

### Webhook Secret Rotation

**Frequency:** Quarterly

**Process:**

```python
# 1. Generate new secret
from src.webhook_validation import rotate_webhook_secret

new_secret = await rotate_webhook_secret(tenant_id, db)

# 2. Update ChirpStack webhook configuration
# (Manual step - paste new secret into ChirpStack UI)

# 3. Old secret is deactivated (is_active = false)

# 4. Audit log records rotation
```

---

## Security Best Practices

### 1. Principle of Least Privilege

- Users: Assign lowest role necessary (prefer Operator over Admin)
- API Keys: Grant minimal scopes (prefer `spaces:read` over `admin:*`)

### 2. JWT Best Practices

- ✅ Short-lived access tokens (24 hours)
- ✅ Long-lived refresh tokens (30 days)
- ✅ HTTPS only (never HTTP)
- ✅ Secure, HttpOnly cookies for refresh tokens (web apps)
- ✅ Token revocation via refresh token deletion

### 3. API Key Best Practices

- ✅ Store keys in secret manager (not plaintext)
- ✅ Rotate quarterly
- ✅ Revoke immediately on suspected compromise
- ✅ Monitor `last_used_at` for unused keys (clean up)
- ✅ Set expiry dates (`expires_at`)

### 4. Password Requirements

- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- No common passwords (use zxcvbn library)
- Enforce via API validation

### 5. Rate Limiting

- Per-tenant limits (prevent abuse)
- Per-IP limits (prevent DDoS)
- Webhook signature validation (prevent spoofing)

### 6. TLS/HTTPS Everywhere

- API: TLS 1.3 (via Traefik)
- Database: SSL mode (sslmode=require)
- Redis: TLS (if exposed externally)

### 7. IP Allowlisting (Optional)

For high-security tenants:

```python
# Check client IP against allowlist
if client_ip not in tenant.allowed_ips:
    raise HTTPException(403, "IP not allowed")
```

---

## Penetration Testing

### Acceptance Criteria

**Per `docs/v5.3-07-security-tenancy.md`:**

✅ **Pen tests cannot cross tenant boundaries**

**Test Cases:**

1. **Tenant A tries to access Tenant B's spaces:**
   ```bash
   # Authenticated as Tenant A
   GET /api/v1/spaces/{tenant_b_space_id}
   # Expected: 404 Not Found (not 403, to prevent info disclosure)
   ```

2. **API key from Tenant A tries to create space in Tenant B:**
   ```bash
   # API key bound to Tenant A
   POST /api/v1/tenants/{tenant_b_id}/spaces
   # Expected: 403 Forbidden
   ```

3. **SQL injection attempt to bypass tenant_id:**
   ```bash
   GET /api/v1/spaces?code=A-101' OR tenant_id != tenant_id --
   # Expected: Sanitized query, no cross-tenant access
   ```

✅ **Revoking an API key is effective immediately**

**Test Case:**

```bash
# 1. Create API key, use it successfully
POST /api/v1/spaces  (with X-API-Key header) → 201 Created

# 2. Revoke key
DELETE /api/v1/api-keys/{key_id} → 200 OK

# 3. Try to use revoked key
POST /api/v1/spaces  (with same X-API-Key) → 401 Unauthorized
```

✅ **All admin actions are traceable in audit log**

**Test Case:**

```sql
-- Admin deletes a space
DELETE FROM spaces WHERE id = $1;

-- Audit log captures action
SELECT * FROM audit_log
WHERE action = 'space.delete'
AND resource_id = $1;

-- Audit record shows:
-- - actor_type = 'user'
-- - actor_name = 'admin@example.com'
-- - old_values = {previous space data}
-- - success = true
```

### Vulnerability Scanning

**Tools:**
- **OWASP ZAP** - Web application scanner
- **SQLMap** - SQL injection testing
- **Burp Suite** - Manual testing

**Schedule:** Quarterly + before major releases

---

## Compliance Considerations

### GDPR (EU)

- ✅ Audit log tracks data access ("who accessed what")
- ✅ Data deletion (tenant soft-delete with `deleted_at`)
- ✅ Right to access (audit log export)
- ⚠️ **TODO:** Right to erasure (hard-delete user data)

### SOC 2

- ✅ Access controls (RBAC, API key scopes)
- ✅ Audit logging (immutable trail)
- ✅ Encryption in transit (TLS)
- ⚠️ **TODO:** Encryption at rest (database-level)

---

## Security Incident Response

### Suspected API Key Compromise

1. **Revoke key immediately:**
   ```sql
   UPDATE api_keys SET revoked_at = NOW() WHERE id = $1;
   ```

2. **Check audit log for malicious activity:**
   ```sql
   SELECT * FROM audit_log
   WHERE api_key_id = $1
   ORDER BY created_at DESC;
   ```

3. **Generate new key for legitimate client**

4. **Document incident** in security log

### Suspected Account Compromise

1. **Reset password**
2. **Revoke all refresh tokens:**
   ```sql
   UPDATE refresh_tokens
   SET revoked_at = NOW()
   WHERE user_id = $1;
   ```

3. **Review audit log for suspicious actions**
4. **Notify user via email**

---

## Future Enhancements

- [ ] Argon2 password hashing (upgrade from bcrypt)
- [ ] 2FA/MFA support (TOTP via authenticator app)
- [ ] IP allowlisting per tenant
- [ ] Encryption at rest (database-level)
- [ ] Automated key rotation reminders
- [ ] Anomaly detection (unusual API usage patterns)
- [ ] SIEM integration (forward audit logs to Splunk/ELK)

---

**Last Reviewed:** 2025-10-20
**Next Review:** 2026-01-20
**Approved By:** Engineering Team
