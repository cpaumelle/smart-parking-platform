# V6 Multi-Tenant Architecture Implementation Plan

**Project**: Smart Parking Platform v6 Migration
**Duration**: 6 weeks (with 2 developers) or 10 weeks (with 1 developer)
**Start Date**: [TO BE FILLED]
**Risk Level**: Low-Medium (incremental migration approach)

---

## 📋 Pre-Implementation Checklist

### Week 0: Preparation & Planning

#### Environment Setup
- [ ] Create `v6-development` branch from main
- [ ] Set up v6 development database (copy of production)
- [ ] Create v6 staging environment
- [ ] Set up feature flags in frontend and backend
- [ ] Document current v5 API endpoints and responses
- [ ] Create rollback plan document

#### Team Preparation
- [ ] Review this implementation plan with team
- [ ] Assign primary owners for each phase
- [ ] Set up daily standup schedule
- [ ] Create Slack channel #v6-migration
- [ ] Schedule weekly stakeholder updates

#### Backup & Safety
- [ ] Full database backup of production
- [ ] Document current production metrics (response times, query times)
- [ ] Set up monitoring dashboards for v5 vs v6 comparison
- [ ] Create automated backup script for dev database

```bash
#!/bin/bash
# backup_before_migration.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U parking_user parking_v5 > backups/pre_v6_migration_$DATE.sql
echo "Backup created: backups/pre_v6_migration_$DATE.sql"
```

---

## Phase 1: Database Foundation (Week 1)

### Day 1-2: Schema Migration Development

#### Task 1.1: Create Migration Scripts

Create file: `migrations/001_v6_add_tenant_columns.sql`

```sql
-- ============================================
-- Migration 001: Add tenant_id columns
-- Safe to run multiple times (idempotent)
-- ============================================

BEGIN;

-- Add tenant_id to sensor_devices (nullable initially)
ALTER TABLE sensor_devices 
ADD COLUMN IF NOT EXISTS tenant_id UUID,
ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN IF NOT EXISTS assigned_space_id UUID,
ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS chirpstack_device_id UUID,
ADD COLUMN IF NOT EXISTS chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

-- Add tenant_id to display_devices
ALTER TABLE display_devices 
ADD COLUMN IF NOT EXISTS tenant_id UUID,
ADD COLUMN IF NOT EXISTS lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN IF NOT EXISTS assigned_space_id UUID,
ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS chirpstack_device_id UUID,
ADD COLUMN IF NOT EXISTS chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

-- Add indexes (IF NOT EXISTS for safety)
CREATE INDEX IF NOT EXISTS idx_sensor_devices_tenant 
    ON sensor_devices(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_display_devices_tenant 
    ON display_devices(tenant_id, status);

COMMIT;
```

Create file: `migrations/002_v6_backfill_tenant_data.sql`

```sql
-- ============================================
-- Migration 002: Backfill tenant_id from space assignments
-- ============================================

BEGIN;

-- Backfill sensor_devices tenant_id from space assignments
UPDATE sensor_devices sd
SET 
    tenant_id = COALESCE(sd.tenant_id, s.tenant_id),
    assigned_space_id = COALESCE(sd.assigned_space_id, sp.id),
    assigned_at = COALESCE(sd.assigned_at, sp.created_at),
    lifecycle_state = CASE 
        WHEN sp.id IS NOT NULL THEN 'operational'
        ELSE 'provisioned'
    END
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.sensor_device_id = sd.id
  AND sd.tenant_id IS NULL;

-- Backfill display_devices tenant_id
UPDATE display_devices dd
SET 
    tenant_id = COALESCE(dd.tenant_id, s.tenant_id),
    assigned_space_id = COALESCE(dd.assigned_space_id, sp.id),
    assigned_at = COALESCE(dd.assigned_at, sp.created_at),
    lifecycle_state = CASE 
        WHEN sp.id IS NOT NULL THEN 'operational'
        ELSE 'provisioned'
    END
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.display_device_id = dd.id
  AND dd.tenant_id IS NULL;

-- Assign orphaned devices to platform tenant
UPDATE sensor_devices 
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

UPDATE display_devices 
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

COMMIT;
```

Create file: `migrations/003_v6_create_new_tables.sql`

```sql
-- ============================================
-- Migration 003: Create new v6 tables
-- ============================================

BEGIN;

-- Gateways table (tenant-scoped)
CREATE TABLE IF NOT EXISTS gateways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway_id VARCHAR(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'offline',
    last_seen_at TIMESTAMP,
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    chirpstack_gateway_id VARCHAR(16),
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    unassignment_reason TEXT
);

-- ChirpStack synchronization tracking
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
CREATE INDEX IF NOT EXISTS idx_gateways_tenant ON gateways(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_device_assignments_tenant ON device_assignments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_device_assignments_device ON device_assignments(device_id, device_type);
CREATE INDEX IF NOT EXISTS idx_chirpstack_sync_status ON chirpstack_sync(sync_status, next_sync_at);

COMMIT;
```

#### Task 1.2: Test Migrations on Development

```bash
# Run migrations on development database
psql -h localhost -U parking_user -d parking_v6_dev -f migrations/001_v6_add_tenant_columns.sql
psql -h localhost -U parking_user -d parking_v6_dev -f migrations/002_v6_backfill_tenant_data.sql
psql -h localhost -U parking_user -d parking_v6_dev -f migrations/003_v6_create_new_tables.sql

# Verify migrations
psql -h localhost -U parking_user -d parking_v6_dev -c "\d sensor_devices"
psql -h localhost -U parking_user -d parking_v6_dev -c "SELECT COUNT(*), tenant_id FROM sensor_devices GROUP BY tenant_id"
```

### Day 3: Row-Level Security Implementation

Create file: `migrations/004_v6_row_level_security.sql`

```sql
-- ============================================
-- Migration 004: Enable Row-Level Security
-- ============================================

BEGIN;

-- Enable RLS on tables
ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY tenant_isolation_policy ON sensor_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON display_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON spaces
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

CREATE POLICY tenant_isolation_policy ON gateways
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id', true)::uuid
        OR current_setting('app.is_platform_admin', true)::boolean = true
    );

COMMIT;
```

### Day 4-5: Data Validation & Testing

#### Validation Script

Create file: `scripts/validate_migration.py`

```python
#!/usr/bin/env python3
"""
Validate v6 migration data integrity
"""

import asyncio
import asyncpg
from datetime import datetime

async def validate_migration():
    # Connect to database
    conn = await asyncpg.connect(
        host='localhost',
        database='parking_v6_dev',
        user='parking_user',
        password='your_password'
    )
    
    print("🔍 Validating v6 Migration...")
    print("=" * 50)
    
    # Test 1: Check all devices have tenant_id
    orphans = await conn.fetchval("""
        SELECT COUNT(*) FROM sensor_devices WHERE tenant_id IS NULL
    """)
    
    if orphans > 0:
        print(f"❌ Found {orphans} sensor devices without tenant_id")
    else:
        print("✅ All sensor devices have tenant_id")
    
    # Test 2: Verify tenant assignments match spaces
    mismatches = await conn.fetch("""
        SELECT sd.dev_eui, sd.tenant_id as device_tenant, s.tenant_id as space_tenant
        FROM sensor_devices sd
        JOIN spaces sp ON sp.sensor_device_id = sd.id
        JOIN sites s ON s.id = sp.site_id
        WHERE sd.tenant_id != s.tenant_id
    """)
    
    if mismatches:
        print(f"❌ Found {len(mismatches)} tenant mismatches")
        for m in mismatches[:5]:
            print(f"   Device {m['dev_eui']}: {m['device_tenant']} != {m['space_tenant']}")
    else:
        print("✅ All device-space tenant assignments match")
    
    # Test 3: Check indexes exist
    indexes = await conn.fetch("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename IN ('sensor_devices', 'display_devices', 'gateways')
        AND indexname LIKE 'idx_%tenant%'
    """)
    
    print(f"✅ Created {len(indexes)} tenant-related indexes")
    
    # Test 4: Test RLS with tenant context
    await conn.execute("SET app.current_tenant_id = '00000000-0000-0000-0000-000000000000'")
    await conn.execute("SET app.is_platform_admin = false")
    
    platform_devices = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
    print(f"✅ Platform tenant sees {platform_devices} devices")
    
    # Test with different tenant
    test_tenant = await conn.fetchrow("SELECT id FROM tenants WHERE slug = 'acme' LIMIT 1")
    if test_tenant:
        await conn.execute(f"SET app.current_tenant_id = '{test_tenant['id']}'")
        tenant_devices = await conn.fetchval("SELECT COUNT(*) FROM sensor_devices")
        print(f"✅ Acme tenant sees {tenant_devices} devices")
    
    await conn.close()
    print("=" * 50)
    print("✅ Migration validation complete!")

if __name__ == "__main__":
    asyncio.run(validate_migration())
```

### Week 1 Checkpoint

- [ ] All migration scripts created and tested
- [ ] Data integrity validated
- [ ] RLS policies working correctly
- [ ] Development database fully migrated
- [ ] Rollback script tested

---

## Phase 2: Backend API Development (Week 2-3)

### Week 2, Day 1-2: Core Service Updates

#### Task 2.1: Enhanced Tenant Context

Create file: `src/core/tenant_context_v6.py`

```python
# src/core/tenant_context_v6.py

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.auth import get_current_user

class TenantContextV6:
    """Enhanced tenant context for v6"""
    
    def __init__(self, tenant_id: UUID, user_id: UUID, role: str, is_platform_admin: bool):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role
        self.is_platform_admin = is_platform_admin
        self.is_viewing_platform_tenant = str(tenant_id) == "00000000-0000-0000-0000-000000000000"
    
    async def apply_to_db(self, db: AsyncSession):
        """Apply tenant context to database session for RLS"""
        await db.execute(
            "SET LOCAL app.current_tenant_id = :tenant_id",
            {"tenant_id": str(self.tenant_id)}
        )
        await db.execute(
            "SET LOCAL app.is_platform_admin = :is_admin",
            {"is_admin": self.is_platform_admin}
        )
    
    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """Check if user can access a specific tenant"""
        if self.is_platform_admin:
            return True
        return str(self.tenant_id) == str(target_tenant_id)

async def get_tenant_context_v6(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TenantContextV6:
    """Dependency to get enhanced tenant context"""
    
    # Get user's tenant and role
    result = await db.execute("""
        SELECT t.id, um.role, 
               (um.role = 'platform_admin') as is_platform_admin
        FROM tenants t
        JOIN user_memberships um ON um.tenant_id = t.id
        WHERE um.user_id = :user_id
        AND um.tenant_id = :tenant_id
    """, {
        "user_id": current_user.id,
        "tenant_id": current_user.tenant_id
    })
    
    tenant_info = result.fetchone()
    if not tenant_info:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No valid tenant membership"
        )
    
    context = TenantContextV6(
        tenant_id=tenant_info.id,
        user_id=current_user.id,
        role=tenant_info.role,
        is_platform_admin=tenant_info.is_platform_admin
    )
    
    # Apply RLS context to database session
    await context.apply_to_db(db)
    
    return context
```

#### Task 2.2: Device Service V6

Create file: `src/services/device_service_v6.py`

```python
# src/services/device_service_v6.py

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import SensorDevice, DisplayDevice, Space, DeviceAssignment
from src.core.tenant_context_v6 import TenantContextV6

class DeviceServiceV6:
    """Device service with proper tenant scoping"""
    
    def __init__(self, db: AsyncSession, tenant_context: TenantContextV6):
        self.db = db
        self.tenant = tenant_context
    
    async def list_devices(
        self, 
        status: Optional[str] = None,
        include_stats: bool = False
    ) -> dict:
        """List devices with v6 tenant scoping"""
        
        # Build base query
        query = select(SensorDevice)
        
        # Apply tenant filter (RLS will also enforce this)
        if not (self.tenant.is_platform_admin and self.tenant.is_viewing_platform_tenant):
            query = query.where(SensorDevice.tenant_id == self.tenant.tenant_id)
        
        # Apply status filter
        if status:
            query = query.where(SensorDevice.status == status)
        
        # Execute query
        result = await self.db.execute(query)
        devices = result.scalars().all()
        
        # Build response
        response = {
            "devices": [self._device_to_dict(d) for d in devices],
            "count": len(devices),
            "tenant_scope": str(self.tenant.tenant_id),
            "is_cross_tenant": self.tenant.is_platform_admin and self.tenant.is_viewing_platform_tenant
        }
        
        # Add statistics if requested
        if include_stats:
            response["stats"] = await self._get_device_stats()
        
        return response
    
    async def assign_device_to_space(
        self,
        device_id: UUID,
        space_id: UUID,
        reason: str = "Manual assignment"
    ) -> dict:
        """Assign device to space with v6 validation"""
        
        # Get device
        device = await self.db.get(SensorDevice, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")
        
        # Verify tenant access
        if not self.tenant.can_access_tenant(device.tenant_id):
            raise PermissionError("Cannot access device from another tenant")
        
        # Get space
        space = await self.db.get(Space, space_id)
        if not space:
            raise ValueError(f"Space {space_id} not found")
        
        # Verify same tenant
        if device.tenant_id != space.tenant_id:
            raise ValueError("Device and space must belong to same tenant")
        
        # Check if already assigned
        if device.status == 'assigned' and device.assigned_space_id:
            raise ValueError(f"Device already assigned to space {device.assigned_space_id}")
        
        # Update device
        device.status = 'assigned'
        device.assigned_space_id = space_id
        device.assigned_at = datetime.utcnow()
        device.lifecycle_state = 'operational'
        
        # Update space
        space.sensor_device_id = device_id
        
        # Create assignment history
        history = DeviceAssignment(
            tenant_id=device.tenant_id,
            device_type='sensor',
            device_id=device_id,
            dev_eui=device.dev_eui,
            space_id=space_id,
            assigned_by=self.tenant.user_id,
            assignment_reason=reason
        )
        self.db.add(history)
        
        await self.db.commit()
        
        return {
            "success": True,
            "device_id": str(device_id),
            "space_id": str(space_id),
            "message": f"Device {device.dev_eui} assigned to space {space.code}"
        }
    
    def _device_to_dict(self, device) -> dict:
        """Convert device model to dictionary"""
        return {
            "id": str(device.id),
            "dev_eui": device.dev_eui,
            "name": device.name,
            "tenant_id": str(device.tenant_id),
            "status": device.status,
            "lifecycle_state": device.lifecycle_state,
            "assigned_space_id": str(device.assigned_space_id) if device.assigned_space_id else None,
            "assigned_at": device.assigned_at.isoformat() if device.assigned_at else None,
            "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None
        }
```

### Week 2, Day 3-5: API Endpoints

#### Task 2.3: V6 Router Implementation

Create file: `src/routers/v6/devices.py`

```python
# src/routers/v6/devices.py

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.core.tenant_context_v6 import get_tenant_context_v6, TenantContextV6
from src.services.device_service_v6 import DeviceServiceV6

router = APIRouter(prefix="/api/v6/devices", tags=["devices-v6"])

@router.get("/")
async def list_devices(
    status: Optional[str] = Query(None),
    include_stats: bool = Query(False),
    tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    db: AsyncSession = Depends(get_db)
):
    """List devices with v6 tenant scoping"""
    service = DeviceServiceV6(db, tenant)
    return await service.list_devices(status=status, include_stats=include_stats)

@router.post("/{device_id}/assign")
async def assign_device(
    device_id: UUID,
    space_id: UUID,
    reason: str = "Manual assignment via API",
    tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    db: AsyncSession = Depends(get_db)
):
    """Assign device to space"""
    service = DeviceServiceV6(db, tenant)
    try:
        return await service.assign_device_to_space(
            device_id=device_id,
            space_id=space_id,
            reason=reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/pool/stats")
async def get_device_pool_stats(
    tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    db: AsyncSession = Depends(get_db)
):
    """Get device pool statistics (platform admin only)"""
    if not tenant.is_platform_admin:
        raise HTTPException(403, "Only platform admins can view pool statistics")
    
    # Get statistics across all tenants
    result = await db.execute("""
        SELECT 
            t.name as tenant_name,
            COUNT(sd.id) as device_count,
            COUNT(sd.id) FILTER (WHERE sd.status = 'assigned') as assigned_count,
            COUNT(sd.id) FILTER (WHERE sd.status = 'unassigned') as unassigned_count
        FROM tenants t
        LEFT JOIN sensor_devices sd ON sd.tenant_id = t.id
        GROUP BY t.id, t.name
        ORDER BY t.name
    """)
    
    stats = result.fetchall()
    
    return {
        "tenants": [
            {
                "name": s.tenant_name,
                "total": s.device_count,
                "assigned": s.assigned_count,
                "unassigned": s.unassigned_count
            }
            for s in stats
        ],
        "total_devices": sum(s.device_count for s in stats),
        "total_assigned": sum(s.assigned_count for s in stats),
        "total_unassigned": sum(s.unassigned_count for s in stats)
    }
```

### Week 3: Integration & Testing

#### Task 2.4: Integration with Main Application

Update file: `src/main.py`

```python
# src/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import both v5 and v6 routers
from src.routers import devices as devices_v5
from src.routers.v6 import devices as devices_v6
from src.routers.v6 import dashboard as dashboard_v6
from src.routers.v6 import gateways as gateways_v6

app = FastAPI(title="Smart Parking Platform", version="5.8.0/6.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register v5 endpoints (keep for backwards compatibility)
app.include_router(devices_v5.router, prefix="/api/v1", tags=["v5"])

# Register v6 endpoints
app.include_router(devices_v6.router, tags=["v6"])
app.include_router(dashboard_v6.router, tags=["v6"])
app.include_router(gateways_v6.router, tags=["v6"])

# Health check that reports both versions
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "v5_api": "active",
        "v6_api": "active",
        "migration_mode": True
    }
```

#### Task 2.5: Backend Testing

Create file: `tests/test_v6_tenant_isolation.py`

```python
# tests/test_v6_tenant_isolation.py

import pytest
from httpx import AsyncClient
from uuid import uuid4

@pytest.mark.asyncio
async def test_tenant_isolation():
    """Test that tenants cannot see each other's devices"""
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login as Acme tenant user
        acme_token = await login_as_tenant(client, "acme")
        
        # Get Acme devices
        response = await client.get(
            "/api/v6/devices",
            headers={"Authorization": f"Bearer {acme_token}"}
        )
        assert response.status_code == 200
        acme_devices = response.json()["devices"]
        
        # Login as TechStart tenant user
        techstart_token = await login_as_tenant(client, "techstart")
        
        # Get TechStart devices
        response = await client.get(
            "/api/v6/devices",
            headers={"Authorization": f"Bearer {techstart_token}"}
        )
        assert response.status_code == 200
        techstart_devices = response.json()["devices"]
        
        # Verify no overlap in device IDs
        acme_ids = {d["id"] for d in acme_devices}
        techstart_ids = {d["id"] for d in techstart_devices}
        assert len(acme_ids & techstart_ids) == 0, "Tenant isolation breach!"

@pytest.mark.asyncio
async def test_platform_admin_access():
    """Test platform admin can see all devices"""
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Login as platform admin
        admin_token = await login_as_platform_admin(client)
        
        # Get all devices
        response = await client.get(
            "/api/v6/devices",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        all_devices = response.json()
        
        # Verify cross-tenant flag
        assert all_devices["is_cross_tenant"] == True
        
        # Get pool stats (platform admin only)
        response = await client.get(
            "/api/v6/devices/pool/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
```

### Week 2-3 Checkpoint

- [ ] All v6 backend services implemented
- [ ] V6 API endpoints working alongside v5
- [ ] Tenant isolation verified through tests
- [ ] Platform admin features working
- [ ] Backend integration tests passing

---

## Phase 3: Frontend Implementation (Week 4-5)

### Week 4, Day 1-2: Service Layer Updates

#### Task 3.1: API Client Updates

Create file: `frontend/src/services/api/v6/DeviceServiceV6.js`

```javascript
// frontend/src/services/api/v6/DeviceServiceV6.js

import { apiClient } from '../apiClient';

class DeviceServiceV6 {
  constructor() {
    this.baseUrl = '/api/v6/devices';
    this.cache = new Map();
  }

  async listDevices(options = {}) {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.includeStats) params.append('include_stats', 'true');
    
    const response = await apiClient.get(`${this.baseUrl}?${params}`);
    return response.data;
  }

  async assignDevice(deviceId, spaceId, reason) {
    const response = await apiClient.post(
      `${this.baseUrl}/${deviceId}/assign`,
      { space_id: spaceId, reason }
    );
    return response.data;
  }

  async getPoolStats() {
    const response = await apiClient.get(`${this.baseUrl}/pool/stats`);
    return response.data;
  }
}

export default new DeviceServiceV6();
```

#### Task 3.2: Feature Flag Implementation

Create file: `frontend/src/config/featureFlags.js`

```javascript
// frontend/src/config/featureFlags.js

export const FeatureFlags = {
  USE_V6_API: process.env.REACT_APP_USE_V6_API === 'true',
  SHOW_PLATFORM_ADMIN_UI: process.env.REACT_APP_SHOW_PLATFORM_ADMIN === 'true',
  ENABLE_DEVICE_POOL: process.env.REACT_APP_ENABLE_DEVICE_POOL === 'true',
};

// Gradual rollout configuration
export const V6_ROLLOUT = {
  devices: FeatureFlags.USE_V6_API,
  gateways: false, // Still on v5
  spaces: false,    // Still on v5
  dashboard: FeatureFlags.USE_V6_API,
};

export function shouldUseV6(feature) {
  return V6_ROLLOUT[feature] || false;
}
```

### Week 4, Day 3-5: Component Updates

#### Task 3.3: Update Device List Component

Update file: `frontend/src/components/Devices/DeviceList.jsx`

```javascript
// frontend/src/components/Devices/DeviceList.jsx

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { shouldUseV6 } from '../../config/featureFlags';
import DeviceServiceV5 from '../../services/api/DeviceService';
import DeviceServiceV6 from '../../services/api/v6/DeviceServiceV6';

export function DeviceList() {
  // Choose API version based on feature flag
  const deviceService = shouldUseV6('devices') ? DeviceServiceV6 : DeviceServiceV5;
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['devices', { version: shouldUseV6('devices') ? 'v6' : 'v5' }],
    queryFn: () => deviceService.listDevices({ includeStats: true }),
    staleTime: 30000,
  });

  if (isLoading) return <DeviceListSkeleton />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div className="space-y-4">
      {/* Show migration indicator during transition */}
      {shouldUseV6('devices') && (
        <Alert>
          <InfoIcon className="h-4 w-4" />
          <AlertDescription>
            Using new v6 API with improved performance
          </AlertDescription>
        </Alert>
      )}

      <DeviceTable devices={data.devices} />
      
      {data.stats && (
        <DeviceStats stats={data.stats} />
      )}
    </div>
  );
}
```

### Week 5: Platform Admin UI

#### Task 3.4: Tenant Switcher Component

Create file: `frontend/src/components/PlatformAdmin/TenantSwitcher.jsx`

```javascript
// frontend/src/components/PlatformAdmin/TenantSwitcher.jsx

import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Menu } from '@headlessui/react';
import { ChevronDownIcon, BuildingOfficeIcon } from '@heroicons/react/20/solid';
import { switchTenant, getCurrentTenant, listTenants } from '../../services/api/v6/TenantService';

export function TenantSwitcher() {
  const { data: currentTenant } = useQuery(['currentTenant'], getCurrentTenant);
  const { data: tenants } = useQuery(['tenants'], listTenants);
  const switchMutation = useMutation(switchTenant);

  const handleSwitch = async (tenantId) => {
    try {
      await switchMutation.mutateAsync(tenantId);
      // Reload to refresh all data with new tenant context
      window.location.reload();
    } catch (error) {
      console.error('Failed to switch tenant:', error);
    }
  };

  // Only show for platform admins
  if (!currentTenant?.isPlatformAdmin) {
    return null;
  }

  return (
    <Menu as="div" className="relative inline-block text-left">
      <Menu.Button className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">
        <BuildingOfficeIcon className="mr-2 h-5 w-5" />
        {currentTenant.name}
        <ChevronDownIcon className="ml-2 h-5 w-5" />
      </Menu.Button>

      <Menu.Items className="absolute right-0 mt-2 w-56 rounded-md bg-white shadow-lg">
        <div className="py-1">
          <Menu.Item>
            <button
              onClick={() => handleSwitch('00000000-0000-0000-0000-000000000000')}
              className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
            >
              Platform (All Tenants)
            </button>
          </Menu.Item>
          
          <div className="border-t border-gray-100" />
          
          {tenants?.map(tenant => (
            <Menu.Item key={tenant.id}>
              <button
                onClick={() => handleSwitch(tenant.id)}
                className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
              >
                {tenant.name}
                {tenant.id === currentTenant.id && ' ✓'}
              </button>
            </Menu.Item>
          ))}
        </div>
      </Menu.Items>
    </Menu>
  );
}
```

### Week 4-5 Checkpoint

- [ ] Frontend service layer updated with v6 clients
- [ ] Feature flags configured and working
- [ ] Components updated to use v6 APIs
- [ ] Platform admin UI components built
- [ ] Frontend integration tests passing

---

## Phase 4: Integration & Testing (Week 6)

### Day 1-2: End-to-End Testing

#### Task 4.1: Integration Test Suite

Create file: `tests/e2e/test_v6_integration.py`

```python
# tests/e2e/test_v6_integration.py

import pytest
from playwright.sync_api import sync_playwright

def test_full_device_lifecycle():
    """Test complete device lifecycle in v6"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Login
        page.goto("http://localhost:3000")
        page.fill("#username", "admin@acme.com")
        page.fill("#password", "password")
        page.click("button[type='submit']")
        
        # Navigate to devices (should use v6)
        page.click("a[href='/devices']")
        page.wait_for_selector(".device-list")
        
        # Verify v6 indicator
        assert page.query_selector(".v6-indicator") is not None
        
        # Test device assignment
        page.click("button.assign-device")
        page.select("#space-select", "space-001")
        page.click("button.confirm-assign")
        
        # Verify success
        page.wait_for_selector(".success-toast")
        
        browser.close()
```

### Day 3: Performance Testing

#### Task 4.2: Load Testing

Create file: `tests/performance/load_test.js`

```javascript
// tests/performance/load_test.js
// Using k6 for load testing

import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 20 },  // Ramp up
    { duration: '1m', target: 20 },   // Stay at 20 users
    { duration: '30s', target: 0 },   // Ramp down
  ],
};

export default function() {
  // Test v5 endpoint
  let v5Response = http.get('http://localhost:8000/api/v1/devices');
  check(v5Response, {
    'v5 status is 200': (r) => r.status === 200,
    'v5 response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);

  // Test v6 endpoint
  let v6Response = http.get('http://localhost:8000/api/v6/devices');
  check(v6Response, {
    'v6 status is 200': (r) => r.status === 200,
    'v6 response time < 200ms': (r) => r.timings.duration < 200,
    'v6 faster than v5': (r) => r.timings.duration < v5Response.timings.duration,
  });

  sleep(1);
}
```

### Day 4-5: Production Preparation

#### Task 4.3: Deployment Configuration

Create file: `deployment/v6_rollout.yaml`

```yaml
# deployment/v6_rollout.yaml
# Kubernetes deployment with gradual rollout

apiVersion: v1
kind: ConfigMap
metadata:
  name: v6-feature-flags
data:
  USE_V6_API: "false"  # Start with v5
  V6_ROLLOUT_PERCENTAGE: "0"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: parking-api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: api
        image: parking-platform:v6.0.0
        env:
        - name: ENABLE_V6_API
          valueFrom:
            configMapKeyRef:
              name: v6-feature-flags
              key: USE_V6_API
        - name: V6_ROLLOUT_PERCENTAGE
          valueFrom:
            configMapKeyRef:
              name: v6-feature-flags
              key: V6_ROLLOUT_PERCENTAGE
```

### Week 6 Checkpoint

- [ ] End-to-end tests passing
- [ ] Performance benchmarks meet targets
- [ ] Deployment scripts ready
- [ ] Monitoring dashboards configured
- [ ] Documentation updated

---

## Phase 5: Production Rollout

### Stage 1: Canary Deployment (Day 1)

```bash
# Deploy v6 to staging
kubectl apply -f deployment/v6_rollout.yaml --namespace=staging

# Run smoke tests
pytest tests/e2e/test_v6_integration.py --env=staging

# Enable v6 for 10% of traffic
kubectl patch configmap v6-feature-flags -p '{"data":{"V6_ROLLOUT_PERCENTAGE":"10"}}'
```

### Stage 2: Progressive Rollout (Day 2-3)

```bash
# Day 2: Increase to 25%
kubectl patch configmap v6-feature-flags -p '{"data":{"V6_ROLLOUT_PERCENTAGE":"25"}}'

# Monitor metrics
curl http://metrics.example.com/v6_performance

# Day 3: Increase to 50%
kubectl patch configmap v6-feature-flags -p '{"data":{"V6_ROLLOUT_PERCENTAGE":"50"}}'
```

### Stage 3: Full Rollout (Day 4)

```bash
# Enable v6 for all users
kubectl patch configmap v6-feature-flags -p '{"data":{"USE_V6_API":"true","V6_ROLLOUT_PERCENTAGE":"100"}}'

# Monitor for 24 hours
watch -n 60 'curl http://metrics.example.com/v6_status'
```

### Stage 4: Cleanup (Day 5)

```bash
# Remove v5 endpoints (after 1 week of stability)
# This is done in code by removing v5 router registrations
```

---

## 📊 Success Metrics

### Performance Targets

| Metric | v5 Baseline | v6 Target | Acceptable |
|--------|-------------|-----------|------------|
| Device list API | 800ms | <200ms | <300ms |
| Device assignment | 400ms | <100ms | <150ms |
| Dashboard load | 3s | <1s | <1.5s |
| Database CPU | 40% | <20% | <25% |

### Quality Gates

- [ ] Zero tenant isolation violations in tests
- [ ] All v5 tests pass with v6 endpoints
- [ ] Performance improvement >60%
- [ ] Zero 500 errors in 24-hour test
- [ ] Platform admin features working

---

## 🚨 Rollback Procedures

### API Rollback

```bash
# Immediate rollback to v5
kubectl patch configmap v6-feature-flags -p '{"data":{"USE_V6_API":"false"}}'

# Verify rollback
curl http://api.example.com/health
```

### Database Rollback

```sql
-- Only if absolutely necessary
-- This removes v6 columns but preserves data
BEGIN;
ALTER TABLE sensor_devices DISABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices DISABLE ROW LEVEL SECURITY;
-- DO NOT drop columns, just disable v6 features
COMMIT;
```

---

## 📋 Daily Standup Template

```markdown
### Date: [DATE]

**Yesterday:**
- Completed: [Tasks]
- Blockers: [Issues]

**Today:**
- [ ] Task 1
- [ ] Task 2

**Metrics:**
- v6 endpoints working: X/Y
- Tests passing: X/Y
- Performance improvement: X%

**Risks:**
- [Risk 1]
- [Risk 2]
```

---

## 📚 Documentation Updates

### Week 6: Documentation

- [ ] Update API documentation with v6 endpoints
- [ ] Create migration guide for other deployments
- [ ] Update developer onboarding docs
- [ ] Record architecture decision records (ADRs)
- [ ] Create troubleshooting guide

---

## ✅ Final Checklist

### Pre-Production

- [ ] All migrations tested on staging
- [ ] Performance benchmarks documented
- [ ] Rollback procedures tested
- [ ] Monitoring dashboards ready
- [ ] Team trained on v6 architecture

### Post-Production

- [ ] v6 stable for 1 week
- [ ] Remove v5 endpoints
- [ ] Archive v5 code branch
- [ ] Celebrate! 🎉

---

**Implementation Plan Version**: 1.0
**Created**: 2025-10-22
**Owner**: Platform Architecture Team
**Status**: Ready for Execution
