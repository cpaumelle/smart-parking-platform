# Row-Level Security (RLS) Deployment Guide

## Overview

This guide explains how to deploy the Smart Parking Platform with Row-Level Security (RLS) enabled for multi-tenant data isolation.

**Key Point:** PostgreSQL superusers ALWAYS bypass RLS policies, even with `FORCE ROW LEVEL SECURITY`. Therefore, the application **MUST** use a non-superuser database role for RLS to work.

## Architecture

### How RLS Works

1. **Authentication** - User logs in with JWT or uses API key
2. **Middleware** - Extracts `tenant_id` from JWT/API key (automatic)
3. **Database Connection** - Sets `app.current_tenant = '<tenant_id>'` (automatic)
4. **RLS Policies** - PostgreSQL filters all queries by `tenant_id` (automatic)
5. **Response** - User only sees their own tenant's data (automatic)

### Security Benefits

- **Defense in depth:** Database enforces isolation even if application code has bugs
- **Zero-trust:** Every query validated by PostgreSQL, not just application logic
- **No manual filtering:** No need for `WHERE tenant_id = ...` in every query
- **Prevents privilege escalation:** Users cannot bypass tenant isolation

## Prerequisites

- PostgreSQL 12+ (RLS support)
- Migration 008 applied (RLS policies created)
- Application code updated with RLS middleware (completed)

## Step 1: Create Application Role

Run migration 009 to create the `parking_app` non-superuser role:

```bash
# Using docker-compose
docker compose exec postgres psql -U parking_user -d parking_v5 -f /opt/v5-smart-parking/migrations/009_create_app_role.sql

# Or copy the migration file first
docker compose cp migrations/009_create_app_role.sql postgres:/tmp/009.sql
docker compose exec postgres psql -U parking_user -d parking_v5 -f /tmp/009.sql
```

**Expected output:**
```
NOTICE:  Created parking_app role
NOTICE:  === Migration 009: Application Role Creation Complete ===
NOTICE:  Role: parking_app
NOTICE:  Superuser: f (MUST be false for RLS)
NOTICE:  Can Login: t (MUST be true)
NOTICE:  Tables with permissions: 25
NOTICE:  ✅ SUCCESS: parking_app role ready for production use
NOTICE:  ✅ RLS will be enforced for this role
```

### What This Migration Does

1. Creates `parking_app` role with `NOSUPERUSER` attribute
2. Grants `CONNECT` on database
3. Grants `SELECT`, `INSERT`, `UPDATE`, `DELETE` on all tables
4. Grants `USAGE`, `SELECT` on all sequences (for auto-increment)
5. Grants `EXECUTE` on all functions (for triggers)
6. Sets default privileges for future tables/sequences/functions

## Step 2: Update DATABASE_URL

Update your `.env` file to use the `parking_app` role:

```bash
# OLD (superuser - RLS bypassed!)
DATABASE_URL=postgresql://parking_user:fd9-kyLwTx@postgres:5432/parking_v5

# NEW (non-superuser - RLS enforced!)
DATABASE_URL=postgresql://parking_app:parking_app_password@postgres:5432/parking_v5
```

**For production:** Change the password immediately after deployment:

```sql
ALTER ROLE parking_app WITH PASSWORD 'your-strong-password-here';
```

## Step 3: Restart Application

Restart the application to use the new database role:

```bash
docker compose restart api

# Verify logs
docker compose logs api --tail 50
```

**Look for:**
```
[OK] Database pool initialized
[OK] Multi-tenancy authentication initialized
```

## Step 4: Test RLS

Run the RLS verification test:

```bash
# Copy test script to API container
docker compose cp test_rls.py api:/app/test_rls.py

# Run test
docker compose exec api python3 test_rls.py
```

**Expected output (SUCCESS):**
```
======================================================================
Testing Row-Level Security (RLS) for Multi-Tenant Isolation
======================================================================

Tenant A: Default Organization (00000000-0000-0000-0000-000000000001)
Tenant B: Acme Corp (91ed162d-66e2-4a19-a89e-f4934764e9f7)

----------------------------------------------------------------------
TEST 2: Query WITH RLS as Tenant A (Default Organization)
----------------------------------------------------------------------
Spaces visible to Tenant A: 2

----------------------------------------------------------------------
TEST 3: Query WITH RLS as Tenant B (Acme Corp)
----------------------------------------------------------------------
Spaces visible to Tenant B: 3

======================================================================
RLS ISOLATION VERIFICATION
======================================================================

✓ Total spaces: 5
✓ Tenant A spaces: 2
✓ Tenant B spaces: 3
✓ Sum of tenant spaces: 5

✅ PASS: RLS is working! Tenants see isolated data.
```

## Step 5: Verify API Endpoints

Test that API endpoints respect tenant isolation:

### Test with JWT Token (User Authentication)

```bash
# Login as Tenant A user
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@default.org",
    "password": "password"
  }'

# Save the access_token from response
TOKEN_A="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Get spaces (should only see Tenant A's spaces)
curl -X GET http://localhost:8000/api/v1/spaces \
  -H "Authorization: Bearer $TOKEN_A"
```

### Test with API Key (Service Authentication)

```bash
# Get API key for Tenant A
API_KEY_A="your-tenant-a-api-key"

# Get spaces (should only see Tenant A's spaces)
curl -X GET http://localhost:8000/api/v1/spaces \
  -H "X-API-Key: $API_KEY_A"
```

## Step 6: Monitor RLS

### Check Which Role Application Is Using

```sql
SELECT current_user, session_user;
```

**Must show:** `parking_app` (not `parking_user`)

### Verify RLS is Enabled

```sql
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('spaces', 'sensor_readings', 'reservations')
ORDER BY tablename;
```

**All should show:** `rowsecurity = t`

### Check Current Tenant Setting

```sql
BEGIN;
SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000001';
SELECT current_setting('app.current_tenant', true);
SELECT COUNT(*) FROM spaces;
COMMIT;
```

## Troubleshooting

### RLS Not Working (All Tenants See All Data)

**Symptom:** All tenants see all data regardless of authentication

**Causes:**
1. **Using superuser role** - Check with `SELECT usesuper FROM pg_user WHERE usename = current_user;`
   - **Fix:** Switch to `parking_app` role in DATABASE_URL
2. **RLS not enabled** - Check with query in Step 6
   - **Fix:** Run migration 008
3. **app.current_tenant not set** - Check application logs for RLS middleware
   - **Fix:** Verify RLS middleware is running

### Permission Denied Errors

**Symptom:** `ERROR: permission denied for table spaces`

**Causes:**
1. **parking_app lacks permissions** - Re-run migration 009
2. **New tables created without grants** - Check default privileges
   - **Fix:** Run `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO parking_app;`

### Superuser Detection

If you must verify whether a role is a superuser:

```sql
SELECT rolname, rolsuper
FROM pg_roles
WHERE rolname IN ('parking_user', 'parking_app');
```

**Expected:**
```
   rolname    | rolsuper
--------------+----------
 parking_user | t        (bypass RLS)
 parking_app  | f        (enforce RLS) ✅
```

## Production Checklist

- [ ] Migration 008 applied (RLS policies created)
- [ ] Migration 009 applied (parking_app role created)
- [ ] DATABASE_URL updated to use `parking_app`
- [ ] Password changed from default (`parking_app_password`)
- [ ] Application restarted with new DATABASE_URL
- [ ] RLS test passed (test_rls.py)
- [ ] API endpoints tested with multiple tenants
- [ ] Monitoring configured (check `parking_app` is used)
- [ ] Backup of current database taken
- [ ] Rollback plan documented

## Security Notes

### Why RLS is Critical

Without RLS, tenant isolation depends ONLY on application code. If there's a bug in the code (e.g., missing `WHERE tenant_id = ...` clause), cross-tenant data leakage occurs.

With RLS, the database enforces isolation EVEN IF the application has bugs. This is **defense in depth**.

### Superuser Bypass Behavior

This is by design in PostgreSQL:
- Superusers need to bypass RLS for administrative tasks (backups, migrations, debugging)
- Applications should NEVER use superuser roles
- Use `parking_user` (superuser) only for migrations and admin tasks
- Use `parking_app` (non-superuser) for all application queries

### RLS Performance

RLS policies are very efficient:
- Evaluated at planning time (not per-row)
- Uses indexes on `tenant_id` columns
- No measurable performance impact for most queries

For high-throughput operations, tenant denormalization (already implemented) ensures fast filtering without joins.

## Additional Resources

- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [V5_DATABASE_SCHEMA.md](./V5_DATABASE_SCHEMA.md) - Complete schema with RLS section
- [SECURITY_TENANCY.md](./SECURITY_TENANCY.md) - Security architecture
- [test_rls.py](../test_rls.py) - Automated RLS verification script

## Support

If RLS is not working after following this guide:
1. Run `test_rls.py` and share output
2. Check application logs for RLS middleware errors
3. Verify `SELECT current_user;` returns `parking_app` (not `parking_user`)
4. Confirm migration 008 and 009 were applied successfully
