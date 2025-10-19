# Multi-Tenancy Deployment Guide

## Current Status
✅ All code is complete and committed to branch `feature/multi-tenancy-v5.3`
❌ Not yet deployed (running API uses old `src.main:app`)
❌ Database migrations not yet run

## Deployment Steps

### 1. Run Database Migrations

```bash
# Access the postgres container
docker exec -it parking-postgres bash

# Inside the container, run as postgres superuser
psql -U parking -d parking -f /path/to/migrations/002_multi_tenancy_rbac.sql
psql -U parking -d parking -f /path/to/migrations/003_multi_tenancy_hardening.sql
psql -U parking -d parking -f /path/to/migrations/004_reservations_and_webhook_hardening.sql
```

**OR** copy migrations into container first:

```bash
# Copy migrations to postgres container
docker cp migrations/002_multi_tenancy_rbac.sql parking-postgres:/tmp/
docker cp migrations/003_multi_tenancy_hardening.sql parking-postgres:/tmp/
docker cp migrations/004_reservations_and_webhook_hardening.sql parking-postgres:/tmp/

# Run migrations
docker exec -i parking-postgres psql -U parking -d parking < /tmp/002_multi_tenancy_rbac.sql
docker exec -i parking-postgres psql -U parking -d parking < /tmp/003_multi_tenancy_hardening.sql
docker exec -i parking-postgres psql -U parking -d parking < /tmp/004_reservations_and_webhook_hardening.sql
```

### 2. Update Dockerfile to Use Multi-Tenancy Main

Edit `Dockerfile` line 47:

```dockerfile
# OLD:
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# NEW:
CMD ["python", "-m", "uvicorn", "src.main_tenanted:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Rebuild and Restart API Container

```bash
# Rebuild the API container
docker compose build api

# Restart the API service
docker compose up -d api

# Check logs
docker compose logs -f api
```

### 4. Verify Deployment

```bash
# Check if multi-tenancy endpoints exist
docker exec parking-api curl -s http://localhost:8000/docs | grep "auth/register"

# Or test registration directly
docker exec parking-api curl -s http://localhost:8000/api/v1/auth/register \
  -X POST -H "Content-Type: application/json" \
  -d '{"user":{"email":"test@acme.com","name":"Test User","password":"password123"},"tenant":{"name":"Acme Corp","slug":"acme"}}'
```

### 5. Run Smoke Tests

```bash
# Update smoke test to use container network
docker exec parking-api bash /app/tests/smoke_test_tenancy.sh

# Or run from outside pointing to Traefik
BASE_URL=http://localhost /opt/v5-smart-parking/tests/smoke_test_tenancy.sh
```

## Alternative: Quick Test Without Rebuilding

If you want to test without modifying Dockerfile:

```bash
# Stop current API
docker compose stop api

# Run new API manually with main_tenanted
docker compose run --rm --service-ports api \
  python -m uvicorn src.main_tenanted:app --host 0.0.0.0 --port 8000
```

## Rollback Plan

If you need to rollback:

```bash
# 1. Revert Dockerfile change
git checkout HEAD -- Dockerfile

# 2. Rebuild API
docker compose build api

# 3. Restart
docker compose up -d api

# 4. Database rollback (if needed)
# You would need to create rollback migrations or restore from backup
```

## Post-Deployment Verification

### Check Database Tables

```bash
docker exec -i parking-postgres psql -U parking -d parking -c "
SELECT
  (SELECT COUNT(*) FROM tenants) as tenants,
  (SELECT COUNT(*) FROM sites) as sites,
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM api_keys) as api_keys;
"
```

### Check API Endpoints

```bash
# List all endpoints
docker exec parking-api curl -s http://localhost:8000/openapi.json | \
  jq '.paths | keys[]' | grep -E "tenants|sites|webhook|orphan"
```

### Run Full Test Suite

```bash
# Unit tests
docker exec parking-api pytest tests/test_tenancy_rbac.py -v

# Smoke tests
docker exec parking-api bash tests/smoke_test_tenancy.sh
```

## Troubleshooting

### Migrations Fail

- Check if tables already exist: `\dt` in psql
- Check migration order (002 → 003 → 004)
- Check database user permissions

### API Won't Start

- Check logs: `docker compose logs api`
- Check if main_tenanted.py imports correctly
- Verify JWT_SECRET_KEY is set in environment

### Endpoints Not Found

- Verify Dockerfile was updated
- Verify container was rebuilt (not just restarted)
- Check `docker exec parking-api cat Dockerfile` to confirm changes

### Smoke Tests Fail

- Ensure migrations ran successfully
- Check API is accessible: `docker exec parking-api curl http://localhost:8000/health`
- Verify JWT_SECRET_KEY is configured
- Check database connectivity from API container
