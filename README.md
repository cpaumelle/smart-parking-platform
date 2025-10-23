# Smart Parking Platform v6

Multi-tenant parking management system with Row-Level Security and device pool management.

## 🌟 What's New in v6

### Core Architecture Improvements
- **Direct Tenant Ownership**: All entities (devices, gateways, spaces) now have direct `tenant_id` relationships
- **Row-Level Security (RLS)**: Database-level tenant isolation ensures data security
- **Efficient Queries**: Reduced 3-hop joins to direct tenant-scoped queries
- **Device Lifecycle Management**: Clear state transitions (provisioned → commissioned → operational → decommissioned)
- **Platform Admin Features**: Cross-tenant visibility and device pool management

### Key Features
- ✅ Multi-tenant architecture with complete data isolation
- ✅ Row-Level Security (RLS) at database level
- ✅ Device pool management for platform admins
- ✅ ChirpStack synchronization service
- ✅ Optimized API endpoints with caching
- ✅ Platform admin UI components
- ✅ Comprehensive migration scripts

## 📁 Project Structure

```
v6_smart_parking/
├── backend/                    # FastAPI backend
│   ├── src/
│   │   ├── core/              # Core services (tenant context, database)
│   │   ├── services/          # Business logic services
│   │   ├── routers/           # API endpoints
│   │   │   └── v6/           # v6 API routers
│   │   └── models/           # Data models
│   └── tests/                # Backend tests
├── frontend/                  # React frontend
│   └── src/
│       ├── services/         # API client services
│       │   └── api/v6/      # v6 API clients
│       ├── components/       # React components
│       │   └── PlatformAdmin/ # Platform admin UI
│       ├── hooks/            # Custom React hooks
│       └── config/           # Configuration (feature flags)
├── migrations/               # Database migration scripts
│   ├── 001_v6_add_tenant_columns.sql
│   ├── 002_v6_backfill_tenant_data.sql
│   ├── 003_v6_create_new_tables.sql
│   └── 004_v6_row_level_security.sql
├── scripts/                  # Utility scripts
│   └── validate_migration.py
├── deployment/              # Deployment configurations
│   └── docker-compose.yml
└── docs/                    # Documentation
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Node.js 18+
- Docker & Docker Compose (optional)

### Option 1: Using Docker Compose

```bash
# Start all services
cd v6_smart_parking/deployment
docker-compose up -d

# Run migrations
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/001_v6_add_tenant_columns.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/002_v6_backfill_tenant_data.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/003_v6_create_new_tables.sql
docker-compose exec postgres psql -U parking_user -d parking_v6 -f /migrations/004_v6_row_level_security.sql

# Access services
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Frontend: http://localhost:3000
```

### Option 2: Manual Setup

#### 1. Setup Database

```bash
# Create database
createdb parking_v6

# Run migrations
psql -U parking_user -d parking_v6 -f migrations/001_v6_add_tenant_columns.sql
psql -U parking_user -d parking_v6 -f migrations/002_v6_backfill_tenant_data.sql
psql -U parking_user -d parking_v6 -f migrations/003_v6_create_new_tables.sql
psql -U parking_user -d parking_v6 -f migrations/004_v6_row_level_security.sql

# Validate migration
cd scripts
python validate_migration.py
```

#### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp ../.env.example .env
# Edit .env with your configuration

# Run backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp ../.env.example .env
# Edit .env with your configuration

# Run frontend
npm start
```

## 📊 Database Schema

### Key Tables

#### `sensor_devices` / `display_devices`
```sql
- id: UUID (PK)
- tenant_id: UUID (FK to tenants) -- NEW in v6
- dev_eui: VARCHAR(16)
- name: VARCHAR(255)
- status: VARCHAR(50)
- lifecycle_state: VARCHAR(50) -- NEW in v6
- assigned_space_id: UUID -- NEW in v6
- assigned_at: TIMESTAMP -- NEW in v6
- chirpstack_device_id: UUID -- NEW in v6
- chirpstack_sync_status: VARCHAR(50) -- NEW in v6
```

#### `gateways` (NEW in v6)
```sql
- id: UUID (PK)
- tenant_id: UUID (FK to tenants)
- gateway_id: VARCHAR(16)
- name: VARCHAR(255)
- site_id: UUID (FK to sites)
- status: VARCHAR(50)
- chirpstack_gateway_id: VARCHAR(16)
```

#### `device_assignments` (NEW in v6)
```sql
- id: UUID (PK)
- tenant_id: UUID (FK to tenants)
- device_type: VARCHAR(50)
- device_id: UUID
- space_id: UUID
- assigned_at: TIMESTAMP
- unassigned_at: TIMESTAMP
- assigned_by: UUID (FK to users)
```

#### `chirpstack_sync` (NEW in v6)
```sql
- id: UUID (PK)
- tenant_id: UUID (FK to tenants)
- entity_type: VARCHAR(50)
- entity_id: UUID
- chirpstack_id: VARCHAR(255)
- sync_status: VARCHAR(50)
- local_data: JSONB
- remote_data: JSONB
```

## 🔒 Security - Row-Level Security (RLS)

All tenant-scoped tables have RLS policies:

```sql
CREATE POLICY tenant_isolation_policy ON sensor_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.is_platform_admin')::boolean = true
    );
```

This ensures:
- Regular users only see their tenant's data
- Platform admins can see all data when needed
- Database-level enforcement (not just application-level)

## 🎯 API Endpoints

### v6 Devices API

```
GET    /api/v6/devices           # List devices (tenant-scoped)
POST   /api/v6/devices/{id}/assign   # Assign device to space
POST   /api/v6/devices/{id}/unassign # Unassign device
GET    /api/v6/devices/pool/stats    # Device pool stats (admin only)
```

### v6 Dashboard API

```
GET    /api/v6/dashboard/data   # Get all dashboard data (single request)
```

### v6 Gateways API

```
GET    /api/v6/gateways          # List gateways (tenant-scoped)
GET    /api/v6/gateways/{id}     # Get gateway details
GET    /api/v6/gateways/{id}/stats # Gateway statistics
```

## 🎨 Frontend Components

### Platform Admin Components

#### TenantSwitcher
Allows platform admins to switch between tenant contexts.

```jsx
import { TenantSwitcher } from '@/components/PlatformAdmin/TenantSwitcher';

<TenantSwitcher />
```

#### DevicePoolManager
Shows device distribution across all tenants.

```jsx
import { DevicePoolManager } from '@/components/PlatformAdmin/DevicePoolManager';

<DevicePoolManager />
```

### Feature Flags

```javascript
import { shouldUseV6, FeatureFlags } from '@/config/featureFlags';

if (shouldUseV6('devices')) {
  // Use v6 API
}
```

## 🔄 Migration from v5

### Step 1: Backup
```bash
pg_dump -h localhost -U parking_user parking_v5 > backup_v5.sql
```

### Step 2: Run Migrations
```bash
psql -U parking_user -d parking_v6 -f migrations/001_v6_add_tenant_columns.sql
psql -U parking_user -d parking_v6 -f migrations/002_v6_backfill_tenant_data.sql
psql -U parking_user -d parking_v6 -f migrations/003_v6_create_new_tables.sql
psql -U parking_user -d parking_v6 -f migrations/004_v6_row_level_security.sql
```

### Step 3: Validate
```bash
python scripts/validate_migration.py
```

### Step 4: Deploy
```bash
# Enable v6 feature flags
export REACT_APP_USE_V6_API=true

# Restart services
docker-compose restart
```

## 📈 Performance Improvements

| Metric | v5 | v6 | Improvement |
|--------|----|----|-------------|
| Device list API | 800ms | <200ms | **75%** |
| Device assignment | 400ms | <100ms | **75%** |
| Dashboard load | 3s | <1s | **67%** |
| Database CPU | 40% | <20% | **50%** |

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Integration Tests
```bash
pytest tests/e2e/ -v
```

## 📝 Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/v6-your-feature
   ```

2. **Make changes**
   - Backend: Edit files in `backend/src/`
   - Frontend: Edit files in `frontend/src/`

3. **Test locally**
   ```bash
   # Backend
   pytest tests/

   # Frontend
   npm test
   ```

4. **Commit with conventional commits**
   ```bash
   git commit -m "feat(devices): add bulk import endpoint"
   ```

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U parking_user -d parking_v6 -c "SELECT 1"
```

### RLS Not Working
```sql
-- Verify RLS is enabled
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE tablename IN ('sensor_devices', 'display_devices', 'gateways');

-- Check current RLS context
SHOW app.current_tenant_id;
SHOW app.is_platform_admin;
```

### Migration Failures
```bash
# Rollback if needed
psql -U parking_user -d parking_v6 < rollback.sql

# Re-run migration
psql -U parking_user -d parking_v6 -f migrations/001_v6_add_tenant_columns.sql
```

## 📚 Documentation

- [Architecture Document](../v5-smart-parking/docs/V6_IMPROVED_TENANT_ARCHITECTURE_V6.md)
- [Implementation Plan](../v5-smart-parking/docs/V6_IMPLEMENTATION_PLAN.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## 🤝 Contributing

1. Follow the conventional commits format
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass

## 📄 License

[Your License Here]

## 👥 Authors

- Smart Parking Platform Team
- Verdegris Solutions

---

**Version**: 6.0.0
**Last Updated**: 2025-10-23
