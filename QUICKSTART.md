# Smart Parking Platform v6 - Quick Start Guide

This guide will help you get the v6 platform running in 10 minutes.

## ⚡ Quick Start (Using Existing Database)

### Step 1: Verify Current Setup (1 min)

```bash
# Check if you're in the right directory
cd /opt/v6_smart_parking

# Check existing database connection
psql -h localhost -U parking_user -d parking_v5 -c "SELECT COUNT(*) FROM tenants;"
```

### Step 2: Run Database Migrations (2 min)

```bash
# Run all v6 migrations on your existing database
# Note: These are SAFE migrations that ADD columns, they don't remove anything

# Migration 1: Add tenant_id columns
sudo psql -h localhost -U parking_user -d parking_v5 -f migrations/001_v6_add_tenant_columns.sql

# Migration 2: Backfill tenant data
sudo psql -h localhost -U parking_user -d parking_v5 -f migrations/002_v6_backfill_tenant_data.sql

# Migration 3: Create new tables
sudo psql -h localhost -U parking_user -d parking_v5 -f migrations/003_v6_create_new_tables.sql

# Migration 4: Enable Row-Level Security
sudo psql -h localhost -U parking_user -d parking_v5 -f migrations/004_v6_row_level_security.sql
```

### Step 3: Validate Migration (1 min)

```bash
# Install Python dependencies for validation
cd scripts
pip3 install asyncpg

# Set environment variables
export DB_HOST=localhost
export DB_NAME=parking_v5
export DB_USER=parking_user
export DB_PASSWORD=your_password

# Run validation
python3 validate_migration.py
```

Expected output:
```
🔍 Validating v6 Migration...
==================================================
✅ All sensor devices have tenant_id
✅ All device-space tenant assignments match
✅ Created 4 tenant-related indexes
✅ Platform tenant sees XXX devices
✅ Migration validation complete!
```

### Step 4: Setup Backend (3 min)

```bash
cd /opt/v6_smart_parking/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'ENVFILE'
DATABASE_URL=postgresql://parking_user:your_password@localhost:5432/parking_v5
ENV=development
DEBUG=true
ENABLE_V6_API=true
ENABLE_ROW_LEVEL_SECURITY=true
ENVFILE

# Start backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Test API (1 min)

Open a new terminal:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "6.0.0",
#   "api": "v6",
#   "features": {
#     "multi_tenant": true,
#     "row_level_security": true,
#     "device_pool_management": true,
#     "chirpstack_sync": true
#   }
# }

# Test devices endpoint
curl http://localhost:8000/api/v6/devices

# View API documentation
open http://localhost:8000/docs
```

### Step 6: Setup Frontend (Optional, 2 min)

```bash
cd /opt/v6_smart_parking/frontend

# Install dependencies
npm install

# Create .env file
cat > .env << 'ENVFILE'
REACT_APP_API_URL=http://localhost:8000
REACT_APP_USE_V6_API=true
REACT_APP_SHOW_PLATFORM_ADMIN=true
ENVFILE

# Start frontend
npm start
```

Visit: http://localhost:3000

---

## 🐳 Quick Start (Using Docker)

Even faster with Docker Compose:

```bash
cd /opt/v6_smart_parking/deployment

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/001_v6_add_tenant_columns.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/002_v6_backfill_tenant_data.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/003_v6_create_new_tables.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/004_v6_row_level_security.sql

# Check logs
docker-compose logs -f backend

# Access services
# Backend API: http://localhost:8000/docs
# Frontend: http://localhost:3000
```

---

## 🧪 Quick Test Scenarios

### Test 1: List Devices (Tenant-Scoped)

```bash
# This should only show devices for the current tenant
curl http://localhost:8000/api/v6/devices?include_stats=true
```

### Test 2: Assign Device to Space

```bash
# Replace UUIDs with actual values from your database
curl -X POST http://localhost:8000/api/v6/devices/{device-id}/assign \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": "{space-id}",
    "reason": "Testing v6 assignment"
  }'
```

### Test 3: Get Dashboard Data

```bash
# Single request for all dashboard data
curl http://localhost:8000/api/v6/dashboard/data
```

### Test 4: Platform Admin - Device Pool Stats

```bash
# Platform admin only - shows all tenants
curl http://localhost:8000/api/v6/devices/pool/stats
```

---

## 🔍 Troubleshooting

### Issue: "Permission denied" during migration

**Solution:**
```bash
# Use sudo for all psql commands
sudo psql -h localhost -U parking_user -d parking_v5 -f migrations/001_v6_add_tenant_columns.sql
```

### Issue: "Connection refused" to database

**Solution:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start if needed
sudo systemctl start postgresql
```

### Issue: Backend won't start

**Solution:**
```bash
# Check Python version (need 3.11+)
python3 --version

# Activate virtual environment
source venv/bin/activate

# Install dependencies again
pip install -r requirements.txt
```

### Issue: RLS not working

**Solution:**
```sql
-- Check if RLS is enabled
sudo psql -h localhost -U parking_user -d parking_v5 -c "
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE tablename = 'sensor_devices';
"

-- Should show: rowsecurity = t (true)
```

---

## 📊 What Changed in v6?

### Database Changes
- ✅ Added `tenant_id` to all devices
- ✅ Added device lifecycle tracking
- ✅ Created `gateways` table
- ✅ Created `device_assignments` history table
- ✅ Created `chirpstack_sync` table
- ✅ Enabled Row-Level Security

### API Changes
- ✅ New `/api/v6/*` endpoints
- ✅ Tenant-scoped queries (automatic via RLS)
- ✅ Device pool management for admins
- ✅ Optimized dashboard endpoint

### Frontend Changes
- ✅ Feature flags for gradual rollout
- ✅ Tenant switcher for platform admins
- ✅ Device pool manager
- ✅ Cached API requests

---

## 🎯 Next Steps

1. **Test with your data**: Try the API endpoints with real device IDs
2. **Configure authentication**: Integrate with your auth system
3. **Set up ChirpStack sync**: If you're using ChirpStack
4. **Deploy to staging**: Test in staging environment
5. **Monitor performance**: Check if you hit the performance targets

---

## 📞 Need Help?

- Check the full README: `/opt/v6_smart_parking/README.md`
- Implementation status: `/opt/v6_smart_parking/IMPLEMENTATION_STATUS.md`
- Architecture docs: `/opt/v5-smart-parking/docs/V6_IMPROVED_TENANT_ARCHITECTURE_V6.md`

---

**Time to get started**: ~10 minutes
**Time to full production**: 4-6 weeks with proper testing
