# Multi-Tenant Architecture v6: Complete Redesign Proposal

**Version**: 6.0.0
**Date**: 2025-10-22
**Purpose**: Transform the Smart Parking Platform into a seamless, scalable multi-tenant SaaS solution

---

## Executive Summary

This proposal addresses all critical issues identified in the v5 architecture analysis and presents a comprehensive redesign that will:

1. **Establish direct tenant ownership** of all entities (devices, gateways, spaces)
2. **Unify the two-database architecture** with proper synchronization
3. **Implement true tenant isolation** with Row-Level Security (RLS)
4. **Create efficient data access patterns** reducing 3-hop joins to direct queries
5. **Provide clear device lifecycle management** with proper state transitions
6. **Enable seamless platform admin operations** across tenants

---

## 1. Core Architecture Principles

### 1.1 Tenant-First Design
Every entity in the system MUST have a direct `tenant_id` relationship:
- **Direct ownership**: All tables include `tenant_id` column
- **No orphans**: Every device belongs to exactly one tenant (even if unassigned to spaces)
- **Explicit platform pool**: Platform tenant owns shared resources

### 1.2 Single Source of Truth
- **Application database** (`parking_v6`) is authoritative for business logic
- **ChirpStack database** is authoritative for LoRaWAN infrastructure
- **Synchronization layer** maintains consistency between databases

### 1.3 Defense in Depth
Multiple layers of security ensure tenant isolation:
1. **Application layer**: FastAPI dependency injection with tenant context
2. **Database layer**: Row-Level Security (RLS) policies
3. **API layer**: Rate limiting and audit logging per tenant

---

## 2. Enhanced Database Schema

### 2.1 Core Schema Changes

```sql
-- ============================================
-- TENANT FOUNDATION
-- ============================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'customer', -- 'platform', 'customer', 'trial'
    
    -- Tenant Configuration
    config JSONB DEFAULT '{}',
    limits JSONB DEFAULT '{"max_devices": 100, "max_gateways": 10, "max_spaces": 500}',
    features JSONB DEFAULT '{"parking": true, "analytics": true, "api_access": true}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    subscription_tier VARCHAR(50) DEFAULT 'basic', -- 'basic', 'pro', 'enterprise'
    trial_ends_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT check_slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

-- Platform tenant has special UUID
INSERT INTO tenants (id, name, slug, type, subscription_tier)
VALUES ('00000000-0000-0000-0000-000000000000', 'Platform', 'platform', 'platform', 'enterprise');

-- ============================================
-- DEVICE MANAGEMENT WITH TENANT OWNERSHIP
-- ============================================

CREATE TABLE sensor_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    dev_eui VARCHAR(16) NOT NULL,
    
    -- Device Info
    name VARCHAR(255),
    device_type VARCHAR(50), -- 'parking_sensor', 'motion_sensor', etc.
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    
    -- Status Management
    status VARCHAR(50) NOT NULL DEFAULT 'unassigned',
    -- States: 'unassigned', 'assigned', 'active', 'inactive', 'maintenance', 'retired'
    
    lifecycle_state VARCHAR(50) NOT NULL DEFAULT 'provisioned',
    -- States: 'provisioned', 'commissioned', 'operational', 'decommissioned'
    
    -- Assignment Tracking
    assigned_space_id UUID REFERENCES spaces(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    
    -- Configuration
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    
    -- ChirpStack Sync
    chirpstack_device_id UUID,
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    -- Ensure globally unique DevEUI
    CONSTRAINT unique_dev_eui UNIQUE (dev_eui),
    -- Ensure DevEUI is uppercase
    CONSTRAINT check_dev_eui_uppercase CHECK (dev_eui = UPPER(dev_eui)),
    -- Index for tenant queries
    INDEX idx_sensor_devices_tenant (tenant_id, status),
    INDEX idx_sensor_devices_deveui (dev_eui),
    INDEX idx_sensor_devices_space (assigned_space_id)
);

-- Similar structure for display_devices
CREATE TABLE display_devices (
    -- Same columns as sensor_devices
    -- ...
);

-- ============================================
-- GATEWAY MANAGEMENT WITH TENANT OWNERSHIP
-- ============================================

CREATE TABLE gateways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    gateway_id VARCHAR(16) NOT NULL, -- EUI64
    
    -- Gateway Info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(100),
    
    -- Location
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    location_description TEXT,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'offline',
    -- States: 'online', 'offline', 'maintenance', 'error'
    
    last_seen_at TIMESTAMP,
    uptime_seconds BIGINT,
    
    -- Configuration
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    
    -- ChirpStack Sync
    chirpstack_gateway_id VARCHAR(16),
    chirpstack_sync_status VARCHAR(50) DEFAULT 'pending',
    chirpstack_last_sync TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_gateway_per_tenant UNIQUE (tenant_id, gateway_id),
    INDEX idx_gateways_tenant (tenant_id, status)
);

-- ============================================
-- ENHANCED SPACES WITH DEVICE LIFECYCLE
-- ============================================

CREATE TABLE spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    
    -- Space Identification
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    display_name VARCHAR(255),
    
    -- Device Assignments (Foreign Keys)
    sensor_device_id UUID REFERENCES sensor_devices(id) ON DELETE SET NULL,
    display_device_id UUID REFERENCES display_devices(id) ON DELETE SET NULL,
    
    -- State Management
    current_state VARCHAR(50) DEFAULT 'unknown',
    -- States: 'free', 'occupied', 'reserved', 'maintenance', 'unknown'
    
    sensor_state VARCHAR(50),
    display_state VARCHAR(50),
    state_changed_at TIMESTAMP,
    
    -- Configuration
    enabled BOOLEAN DEFAULT true,
    auto_release_minutes INTEGER,
    config JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,
    
    CONSTRAINT unique_space_code_per_site UNIQUE (site_id, code),
    INDEX idx_spaces_tenant (tenant_id, current_state),
    INDEX idx_spaces_devices (sensor_device_id, display_device_id)
);

-- ============================================
-- DEVICE ASSIGNMENT HISTORY
-- ============================================

CREATE TABLE device_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    -- Device Reference (polymorphic)
    device_type VARCHAR(50) NOT NULL, -- 'sensor' or 'display'
    device_id UUID NOT NULL,
    dev_eui VARCHAR(16) NOT NULL,
    
    -- Assignment Details
    space_id UUID REFERENCES spaces(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unassigned_at TIMESTAMP,
    assigned_by UUID REFERENCES users(id),
    unassigned_by UUID REFERENCES users(id),
    
    -- Reason Tracking
    assignment_reason TEXT,
    unassignment_reason TEXT,
    
    INDEX idx_device_assignments_tenant (tenant_id),
    INDEX idx_device_assignments_device (device_id, device_type),
    INDEX idx_device_assignments_space (space_id)
);

-- ============================================
-- CHIRPSTACK SYNCHRONIZATION
-- ============================================

CREATE TABLE chirpstack_sync (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    -- Entity Reference
    entity_type VARCHAR(50) NOT NULL, -- 'device' or 'gateway'
    entity_id UUID NOT NULL,
    chirpstack_id VARCHAR(255) NOT NULL,
    
    -- Sync Status
    sync_status VARCHAR(50) DEFAULT 'pending',
    -- States: 'pending', 'syncing', 'synced', 'error', 'conflict'
    
    sync_direction VARCHAR(50), -- 'push', 'pull', 'bidirectional'
    last_sync_at TIMESTAMP,
    next_sync_at TIMESTAMP,
    
    -- Sync Data
    local_data JSONB,
    remote_data JSONB,
    sync_errors JSONB DEFAULT '[]',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_chirpstack_entity UNIQUE (entity_type, entity_id),
    INDEX idx_chirpstack_sync_status (sync_status, next_sync_at)
);
```

### 2.2 Row-Level Security (RLS) Implementation

```sql
-- ============================================
-- ENABLE RLS ON ALL TENANT-SCOPED TABLES
-- ============================================

ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;

-- ============================================
-- RLS POLICIES
-- ============================================

-- Sensor Devices Policy
CREATE POLICY tenant_isolation_policy ON sensor_devices
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.is_platform_admin')::boolean = true
    );

-- Gateways Policy (with platform admin override)
CREATE POLICY tenant_isolation_policy ON gateways
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.is_platform_admin')::boolean = true
    );

-- Spaces Policy
CREATE POLICY tenant_isolation_policy ON spaces
    FOR ALL
    TO parking_user
    USING (
        tenant_id = current_setting('app.current_tenant_id')::uuid
        OR current_setting('app.is_platform_admin')::boolean = true
    );

-- Platform Admin Read-Only Access to ChirpStack Sync
CREATE POLICY platform_admin_readonly ON chirpstack_sync
    FOR SELECT
    TO parking_user
    USING (current_setting('app.is_platform_admin')::boolean = true);
```

---

## 3. Application Layer Improvements

### 3.1 Enhanced Tenant Context Management

```python
# src/core/tenant_context.py

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel
from enum import IntEnum

class TenantType(str, Enum):
    PLATFORM = "platform"
    CUSTOMER = "customer"
    TRIAL = "trial"

class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3
    OWNER = 4
    PLATFORM_ADMIN = 999

class TenantContext(BaseModel):
    """Enhanced tenant context with full tenant information"""
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    tenant_type: TenantType
    user_id: UUID
    username: str
    role: Role
    is_platform_admin: bool
    is_cross_tenant_access: bool  # True when platform admin accessing other tenant
    subscription_tier: str
    features: dict
    limits: dict
    
    @property
    def is_viewing_platform_tenant(self) -> bool:
        """Check if currently viewing the platform tenant"""
        return str(self.tenant_id) == "00000000-0000-0000-0000-000000000000"
    
    @property
    def can_manage_all_tenants(self) -> bool:
        """Check if user can manage all tenants"""
        return self.is_platform_admin and self.is_viewing_platform_tenant
    
    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """Check if user can access a specific tenant"""
        if self.is_platform_admin:
            return True
        return str(self.tenant_id) == str(target_tenant_id)

# src/core/database_context.py

import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator

class TenantAwareDatabase:
    """Database connection manager with automatic RLS context setting"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=10,
            max_size=20
        )
    
    @asynccontextmanager
    async def transaction(self, tenant_context: TenantContext) -> AsyncGenerator:
        """Execute queries within tenant context"""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Set RLS context
                await connection.execute(
                    "SET LOCAL app.current_tenant_id = $1",
                    str(tenant_context.tenant_id)
                )
                await connection.execute(
                    "SET LOCAL app.is_platform_admin = $1",
                    tenant_context.is_platform_admin
                )
                await connection.execute(
                    "SET LOCAL app.user_role = $1",
                    tenant_context.role.name
                )
                yield connection
```

### 3.2 Unified Device Service

```python
# src/services/device_service.py

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

class DeviceService:
    """Unified service for device management with proper tenant scoping"""
    
    def __init__(self, db: AsyncSession, tenant_context: TenantContext):
        self.db = db
        self.tenant = tenant_context
    
    async def list_devices(
        self,
        include_unassigned: bool = True,
        include_assigned: bool = True,
        device_type: Optional[str] = None
    ) -> List[DeviceDTO]:
        """
        List devices with proper tenant scoping
        Platform admins see all when viewing platform tenant
        """
        query = select(SensorDevice)
        
        # Tenant scoping
        if self.tenant.is_viewing_platform_tenant and self.tenant.is_platform_admin:
            # Platform admin viewing platform tenant: see ALL devices
            pass  # No tenant filter
        else:
            # Regular tenant view or platform admin viewing specific tenant
            query = query.where(SensorDevice.tenant_id == self.tenant.tenant_id)
        
        # Status filters
        status_filters = []
        if include_unassigned:
            status_filters.append(SensorDevice.status == 'unassigned')
        if include_assigned:
            status_filters.append(SensorDevice.status == 'assigned')
        
        if status_filters:
            query = query.where(or_(*status_filters))
        
        # Device type filter
        if device_type:
            query = query.where(SensorDevice.device_type == device_type)
        
        # Execute query
        result = await self.db.execute(query)
        devices = result.scalars().all()
        
        return [self._to_dto(device) for device in devices]
    
    async def assign_device_to_space(
        self,
        device_id: UUID,
        space_id: UUID,
        assignment_reason: str = None
    ) -> AssignmentResult:
        """Assign a device to a space with full history tracking"""
        
        # Verify device belongs to tenant (or platform admin)
        device = await self.db.get(SensorDevice, device_id)
        if not device:
            raise DeviceNotFoundError(device_id)
        
        if not self.tenant.can_access_tenant(device.tenant_id):
            raise TenantAccessError("Cannot access device from another tenant")
        
        # Verify space belongs to same tenant
        space = await self.db.get(Space, space_id)
        if not space:
            raise SpaceNotFoundError(space_id)
        
        if device.tenant_id != space.tenant_id:
            raise TenantMismatchError("Device and space must belong to same tenant")
        
        # Check if device is already assigned
        if device.status == 'assigned' and device.assigned_space_id:
            raise DeviceAlreadyAssignedError(
                f"Device {device.dev_eui} already assigned to space {device.assigned_space_id}"
            )
        
        # Update device
        device.status = 'assigned'
        device.assigned_space_id = space_id
        device.assigned_at = datetime.utcnow()
        
        # Update space
        space.sensor_device_id = device_id
        
        # Create assignment history record
        history = DeviceAssignment(
            tenant_id=device.tenant_id,
            device_type='sensor',
            device_id=device_id,
            dev_eui=device.dev_eui,
            space_id=space_id,
            assigned_by=self.tenant.user_id,
            assignment_reason=assignment_reason or "Manual assignment via API"
        )
        self.db.add(history)
        
        # Trigger ChirpStack sync
        await self._queue_chirpstack_sync(device_id, 'device')
        
        await self.db.commit()
        
        return AssignmentResult(
            success=True,
            device_id=device_id,
            space_id=space_id,
            message=f"Device {device.dev_eui} assigned to space {space.code}"
        )
    
    async def get_device_pool_stats(self) -> DevicePoolStats:
        """Get statistics about device pool (platform admin only)"""
        if not self.tenant.is_platform_admin:
            raise PermissionError("Only platform admins can view device pool stats")
        
        # Query all devices grouped by tenant and status
        query = """
            SELECT 
                t.name as tenant_name,
                sd.status,
                sd.device_type,
                COUNT(*) as count
            FROM sensor_devices sd
            JOIN tenants t ON t.id = sd.tenant_id
            GROUP BY t.name, sd.status, sd.device_type
            ORDER BY t.name, sd.status
        """
        
        result = await self.db.execute(query)
        
        return DevicePoolStats(
            total_devices=sum(row['count'] for row in result),
            by_tenant={
                tenant: {
                    'assigned': sum(r['count'] for r in result if r['tenant_name'] == tenant and r['status'] == 'assigned'),
                    'unassigned': sum(r['count'] for r in result if r['tenant_name'] == tenant and r['status'] == 'unassigned'),
                }
                for tenant in set(row['tenant_name'] for row in result)
            }
        )
```

### 3.3 ChirpStack Synchronization Service

```python
# src/services/chirpstack_sync.py

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import grpc
from chirpstack_api import api

class ChirpStackSyncService:
    """Service to synchronize devices and gateways with ChirpStack"""
    
    def __init__(self, chirpstack_url: str, api_token: str):
        self.channel = grpc.insecure_channel(chirpstack_url)
        self.device_stub = api.DeviceServiceStub(self.channel)
        self.gateway_stub = api.GatewayServiceStub(self.channel)
        self.auth_token = [("authorization", f"Bearer {api_token}")]
    
    async def sync_all_tenants(self):
        """Background job to sync all tenant devices with ChirpStack"""
        while True:
            try:
                await self._perform_sync()
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"ChirpStack sync failed: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute
    
    async def _perform_sync(self):
        """Perform actual synchronization"""
        # Get all pending sync items
        async with get_db() as db:
            pending_syncs = await db.fetch("""
                SELECT * FROM chirpstack_sync
                WHERE sync_status IN ('pending', 'error')
                AND (next_sync_at IS NULL OR next_sync_at <= NOW())
                ORDER BY created_at
                LIMIT 100
            """)
            
            for sync_item in pending_syncs:
                await self._sync_entity(sync_item)
    
    async def _sync_entity(self, sync_item: Dict[str, Any]):
        """Sync a single entity with ChirpStack"""
        try:
            if sync_item['entity_type'] == 'device':
                await self._sync_device(sync_item)
            elif sync_item['entity_type'] == 'gateway':
                await self._sync_gateway(sync_item)
            
            # Update sync status
            await self._update_sync_status(
                sync_item['id'],
                'synced',
                datetime.utcnow()
            )
        except Exception as e:
            # Log error and mark for retry
            await self._update_sync_status(
                sync_item['id'],
                'error',
                None,
                datetime.utcnow() + timedelta(minutes=15),
                str(e)
            )
    
    async def _sync_device(self, sync_item: Dict[str, Any]):
        """Sync device with ChirpStack"""
        # Get device from our database
        async with get_db() as db:
            device = await db.fetchrow("""
                SELECT * FROM sensor_devices
                WHERE id = $1
            """, sync_item['entity_id'])
            
            if not device:
                raise ValueError(f"Device {sync_item['entity_id']} not found")
            
            # Check if device exists in ChirpStack
            try:
                cs_device = self.device_stub.Get(
                    api.GetDeviceRequest(dev_eui=device['dev_eui']),
                    metadata=self.auth_token
                )
                
                # Update existing device
                cs_device.device.name = device['name']
                cs_device.device.description = f"Tenant: {device['tenant_id']}"
                
                self.device_stub.Update(
                    api.UpdateDeviceRequest(device=cs_device.device),
                    metadata=self.auth_token
                )
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.NOT_FOUND:
                    # Create new device in ChirpStack
                    # This would need proper device profile ID, application ID, etc.
                    pass
                else:
                    raise
    
    async def import_from_chirpstack(self, tenant_id: UUID):
        """Import all devices from ChirpStack for a tenant"""
        # List all devices from ChirpStack
        response = self.device_stub.List(
            api.ListDeviceRequest(limit=1000),
            metadata=self.auth_token
        )
        
        imported_count = 0
        async with get_db() as db:
            for cs_device in response.result:
                # Check if device already exists
                existing = await db.fetchrow("""
                    SELECT id FROM sensor_devices
                    WHERE dev_eui = $1
                """, cs_device.dev_eui.hex().upper())
                
                if not existing:
                    # Import device
                    await db.execute("""
                        INSERT INTO sensor_devices (
                            tenant_id, dev_eui, name, status,
                            chirpstack_device_id, chirpstack_sync_status
                        ) VALUES ($1, $2, $3, 'unassigned', $4, 'synced')
                    """, tenant_id, cs_device.dev_eui.hex().upper(),
                        cs_device.name, cs_device.dev_eui.hex())
                    imported_count += 1
        
        return imported_count
```

---

## 4. API Layer Enhancements

### 4.1 New RESTful Endpoints

```python
# src/routers/v6/devices.py

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

router = APIRouter(prefix="/api/v6/devices", tags=["devices-v6"])

@router.get("/")
async def list_devices(
    tenant: TenantContext = Depends(get_tenant_context),
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned_only: bool = Query(False, description="Show only assigned devices"),
    unassigned_only: bool = Query(False, description="Show only unassigned devices"),
    include_stats: bool = Query(False, description="Include usage statistics"),
    db: AsyncSession = Depends(get_db)
) -> DeviceListResponse:
    """
    List devices with proper tenant scoping
    
    Behavior:
    - Regular users: See only their tenant's devices
    - Platform admin on platform tenant: See ALL devices across ALL tenants
    - Platform admin on customer tenant: See only that tenant's devices
    """
    service = DeviceService(db, tenant)
    
    # Build filters
    filters = DeviceFilters(
        status=status,
        include_assigned=not unassigned_only,
        include_unassigned=not assigned_only
    )
    
    devices = await service.list_devices(filters)
    
    # Optionally include statistics
    stats = None
    if include_stats:
        stats = await service.get_device_stats()
    
    return DeviceListResponse(
        devices=devices,
        count=len(devices),
        stats=stats,
        tenant_scope=tenant.tenant_slug,
        is_cross_tenant=tenant.is_platform_admin and tenant.is_viewing_platform_tenant
    )

@router.post("/{device_id}/assign")
async def assign_device(
    device_id: UUID,
    request: AssignDeviceRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
) -> AssignmentResponse:
    """Assign a device to a space"""
    service = DeviceService(db, tenant)
    
    result = await service.assign_device_to_space(
        device_id=device_id,
        space_id=request.space_id,
        assignment_reason=request.reason
    )
    
    return AssignmentResponse(
        success=result.success,
        message=result.message,
        assignment_id=result.assignment_id
    )

@router.post("/{device_id}/unassign")
async def unassign_device(
    device_id: UUID,
    request: UnassignDeviceRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
) -> UnassignmentResponse:
    """Unassign a device from its current space"""
    service = DeviceService(db, tenant)
    
    result = await service.unassign_device(
        device_id=device_id,
        reason=request.reason
    )
    
    return UnassignmentResponse(
        success=result.success,
        message=result.message
    )

@router.get("/pool/stats")
async def get_device_pool_stats(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
) -> DevicePoolStatsResponse:
    """
    Get device pool statistics (Platform Admin only)
    Shows distribution of devices across all tenants
    """
    if not tenant.is_platform_admin:
        raise HTTPException(403, "Only platform admins can view pool statistics")
    
    service = DeviceService(db, tenant)
    stats = await service.get_device_pool_stats()
    
    return DevicePoolStatsResponse(
        total_devices=stats.total_devices,
        total_assigned=stats.total_assigned,
        total_unassigned=stats.total_unassigned,
        by_tenant=stats.by_tenant,
        by_status=stats.by_status,
        by_type=stats.by_type
    )

@router.post("/bulk/import")
async def bulk_import_devices(
    request: BulkImportRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
) -> BulkImportResponse:
    """Bulk import devices from ChirpStack or CSV"""
    service = DeviceService(db, tenant)
    
    if request.source == "chirpstack":
        sync_service = ChirpStackSyncService()
        imported = await sync_service.import_from_chirpstack(tenant.tenant_id)
    elif request.source == "csv":
        imported = await service.import_from_csv(request.csv_data)
    
    return BulkImportResponse(
        imported_count=imported,
        message=f"Successfully imported {imported} devices"
    )

# src/routers/v6/gateways.py

@router.get("/")
async def list_gateways(
    tenant: TenantContext = Depends(get_tenant_context),
    include_offline: bool = Query(True),
    site_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> GatewayListResponse:
    """
    List gateways with proper tenant scoping
    
    Key difference from v5: Gateways are now tenant-scoped
    """
    query = select(Gateway)
    
    # Tenant scoping
    if tenant.is_viewing_platform_tenant and tenant.is_platform_admin:
        # Platform admin viewing platform: see ALL gateways
        pass
    else:
        # Regular view: only tenant's gateways
        query = query.where(Gateway.tenant_id == tenant.tenant_id)
    
    # Status filter
    if not include_offline:
        query = query.where(Gateway.status == 'online')
    
    # Site filter
    if site_id:
        query = query.where(Gateway.site_id == site_id)
    
    result = await db.execute(query)
    gateways = result.scalars().all()
    
    return GatewayListResponse(
        gateways=[_gateway_to_dto(g) for g in gateways],
        count=len(gateways),
        tenant_scope=tenant.tenant_slug
    )

# src/routers/v6/dashboard.py

@router.get("/dashboard/data")
async def get_dashboard_data(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
) -> DashboardDataResponse:
    """
    Get all dashboard data in a single optimized request
    Reduces frontend API calls from 5+ to 1
    """
    # Use asyncio.gather for parallel queries
    results = await asyncio.gather(
        _get_device_summary(db, tenant),
        _get_gateway_summary(db, tenant),
        _get_space_summary(db, tenant),
        _get_recent_activity(db, tenant),
        _get_system_health(db, tenant)
    )
    
    return DashboardDataResponse(
        devices=results[0],
        gateways=results[1],
        spaces=results[2],
        recent_activity=results[3],
        system_health=results[4],
        generated_at=datetime.utcnow()
    )
```

### 4.2 GraphQL API Layer (Optional but Recommended)

```python
# src/graphql/schema.py

import strawberry
from typing import List, Optional
from datetime import datetime

@strawberry.type
class Device:
    id: strawberry.ID
    dev_eui: str
    name: str
    status: str
    tenant_id: strawberry.ID
    assigned_space: Optional["Space"] = None
    last_seen_at: Optional[datetime] = None
    
    @strawberry.field
    async def tenant(self, info) -> "Tenant":
        return await info.context.loaders.tenant.load(self.tenant_id)
    
    @strawberry.field
    async def activity_log(self, info, limit: int = 10) -> List["DeviceActivity"]:
        return await info.context.loaders.device_activity.load((self.id, limit))

@strawberry.type
class Space:
    id: strawberry.ID
    code: str
    name: str
    current_state: str
    sensor_device: Optional[Device] = None
    display_device: Optional[Device] = None

@strawberry.type
class Tenant:
    id: strawberry.ID
    name: str
    slug: str
    type: str
    
    @strawberry.field
    async def devices(self, info, status: Optional[str] = None) -> List[Device]:
        # Automatically scoped to tenant
        return await info.context.loaders.tenant_devices.load((self.id, status))
    
    @strawberry.field
    async def stats(self, info) -> "TenantStats":
        return await info.context.loaders.tenant_stats.load(self.id)

@strawberry.type
class Query:
    @strawberry.field
    async def current_tenant(self, info) -> Tenant:
        """Get the current tenant based on JWT context"""
        tenant_context = info.context.tenant_context
        return await info.context.loaders.tenant.load(tenant_context.tenant_id)
    
    @strawberry.field
    async def device(self, info, id: strawberry.ID) -> Optional[Device]:
        """Get a specific device if user has access"""
        device = await info.context.loaders.device.load(id)
        
        # Check tenant access
        if not info.context.tenant_context.can_access_tenant(device.tenant_id):
            raise PermissionError("Cannot access device from another tenant")
        
        return device
    
    @strawberry.field
    async def all_tenants(self, info) -> List[Tenant]:
        """List all tenants (Platform Admin only)"""
        if not info.context.tenant_context.is_platform_admin:
            raise PermissionError("Only platform admins can list all tenants")
        
        return await info.context.loaders.all_tenants.load(None)

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def assign_device_to_space(
        self,
        info,
        device_id: strawberry.ID,
        space_id: strawberry.ID,
        reason: Optional[str] = None
    ) -> "AssignmentResult":
        """Assign a device to a space"""
        service = DeviceService(info.context.db, info.context.tenant_context)
        result = await service.assign_device_to_space(
            device_id=device_id,
            space_id=space_id,
            assignment_reason=reason
        )
        return AssignmentResult(
            success=result.success,
            message=result.message,
            device=await info.context.loaders.device.load(device_id),
            space=await info.context.loaders.space.load(space_id)
        )

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

---

## 5. Frontend Improvements

### 5.1 Enhanced Data Fetching Strategy

```typescript
// src/services/api/v6/DeviceService.ts

import { ApiClient } from '../ApiClient';
import { TenantContext } from '../auth/TenantContext';

export class DeviceServiceV6 {
  private client: ApiClient;
  private cache: Map<string, CachedData>;
  
  constructor(client: ApiClient) {
    this.client = client;
    this.cache = new Map();
  }
  
  async listDevices(options?: ListDeviceOptions): Promise<DeviceListResponse> {
    const cacheKey = this.getCacheKey('devices', options);
    
    // Check cache
    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (cached && !this.isExpired(cached)) {
        return cached.data;
      }
    }
    
    // Fetch from API
    const response = await this.client.get<DeviceListResponse>(
      '/api/v6/devices',
      { params: options }
    );
    
    // Cache response
    this.cache.set(cacheKey, {
      data: response.data,
      timestamp: Date.now(),
      ttl: 30000 // 30 seconds
    });
    
    return response.data;
  }
  
  async getDashboardData(): Promise<DashboardData> {
    // Single API call for all dashboard data
    const response = await this.client.get<DashboardData>(
      '/api/v6/dashboard/data'
    );
    
    // Update multiple cache entries
    this.cache.set('dashboard', {
      data: response.data,
      timestamp: Date.now(),
      ttl: 60000 // 1 minute
    });
    
    // Also cache individual components
    if (response.data.devices) {
      this.cache.set('devices-summary', {
        data: response.data.devices,
        timestamp: Date.now(),
        ttl: 60000
      });
    }
    
    return response.data;
  }
  
  invalidateCache(pattern?: string): void {
    if (pattern) {
      // Invalidate matching keys
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key);
        }
      }
    } else {
      // Clear all cache
      this.cache.clear();
    }
  }
}

// src/hooks/useDevices.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useDeviceService } from './useDeviceService';

export function useDevices(options?: ListDeviceOptions) {
  const service = useDeviceService();
  
  return useQuery({
    queryKey: ['devices', options],
    queryFn: () => service.listDevices(options),
    staleTime: 30000, // Consider data stale after 30 seconds
    cacheTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    refetchOnWindowFocus: false,
  });
}

export function useAssignDevice() {
  const queryClient = useQueryClient();
  const service = useDeviceService();
  
  return useMutation({
    mutationFn: ({ deviceId, spaceId, reason }) =>
      service.assignDevice(deviceId, spaceId, reason),
    onSuccess: (data) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries(['devices']);
      queryClient.invalidateQueries(['spaces']);
      queryClient.invalidateQueries(['dashboard']);
      
      // Show success toast
      toast.success(`Device assigned successfully`);
    },
    onError: (error) => {
      // Show error toast with specific message
      const message = error.response?.data?.detail || 'Failed to assign device';
      toast.error(message);
    }
  });
}
```

### 5.2 Platform Admin UI Components

```typescript
// src/components/PlatformAdmin/TenantSwitcher.tsx

import React, { useState } from 'react';
import { useTenants, useCurrentTenant, useSwitchTenant } from '@/hooks/useTenants';

export function TenantSwitcher() {
  const { data: tenants } = useTenants();
  const { data: currentTenant } = useCurrentTenant();
  const switchTenant = useSwitchTenant();
  const [isOpen, setIsOpen] = useState(false);
  
  const handleSwitch = async (tenantId: string) => {
    try {
      await switchTenant.mutateAsync(tenantId);
      setIsOpen(false);
      
      // Invalidate all cached data
      queryClient.invalidateQueries();
      
      // Optionally reload the page for clean state
      if (tenantId === PLATFORM_TENANT_ID) {
        window.location.href = '/platform/dashboard';
      } else {
        window.location.href = '/dashboard';
      }
    } catch (error) {
      toast.error('Failed to switch tenant');
    }
  };
  
  // Only show for platform admins
  if (!currentTenant?.isPlatformAdmin) {
    return null;
  }
  
  return (
    <Dropdown open={isOpen} onOpenChange={setIsOpen}>
      <DropdownTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Building className="h-4 w-4" />
          {currentTenant.name}
          {currentTenant.id === PLATFORM_TENANT_ID && (
            <Badge variant="secondary">Platform</Badge>
          )}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownTrigger>
      
      <DropdownContent className="w-64">
        <DropdownLabel>Switch Tenant</DropdownLabel>
        <DropdownSeparator />
        
        {/* Platform Tenant Option */}
        <DropdownItem
          onClick={() => handleSwitch(PLATFORM_TENANT_ID)}
          className={currentTenant.id === PLATFORM_TENANT_ID ? 'bg-accent' : ''}
        >
          <Building className="mr-2 h-4 w-4" />
          Platform (All Tenants)
          {currentTenant.id === PLATFORM_TENANT_ID && (
            <Check className="ml-auto h-4 w-4" />
          )}
        </DropdownItem>
        
        <DropdownSeparator />
        
        {/* Customer Tenants */}
        {tenants
          ?.filter(t => t.id !== PLATFORM_TENANT_ID)
          ?.map(tenant => (
            <DropdownItem
              key={tenant.id}
              onClick={() => handleSwitch(tenant.id)}
              className={currentTenant.id === tenant.id ? 'bg-accent' : ''}
            >
              <User className="mr-2 h-4 w-4" />
              {tenant.name}
              <Badge variant="outline" className="ml-auto">
                {tenant.subscriptionTier}
              </Badge>
              {currentTenant.id === tenant.id && (
                <Check className="ml-2 h-4 w-4" />
              )}
            </DropdownItem>
          ))}
      </DropdownContent>
    </Dropdown>
  );
}

// src/components/PlatformAdmin/DevicePoolManager.tsx

export function DevicePoolManager() {
  const { data: stats, isLoading } = useDevicePoolStats();
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  
  if (isLoading) {
    return <Skeleton className="h-96" />;
  }
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Device Pool</CardTitle>
        <CardDescription>
          Manage device distribution across all tenants
        </CardDescription>
      </CardHeader>
      
      <CardContent>
        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Total Devices"
            value={stats?.totalDevices || 0}
            icon={<Cpu className="h-4 w-4" />}
          />
          <StatCard
            title="Assigned"
            value={stats?.totalAssigned || 0}
            percentage={(stats?.totalAssigned / stats?.totalDevices) * 100}
            icon={<Link className="h-4 w-4" />}
          />
          <StatCard
            title="Unassigned"
            value={stats?.totalUnassigned || 0}
            percentage={(stats?.totalUnassigned / stats?.totalDevices) * 100}
            icon={<Unlink className="h-4 w-4" />}
          />
          <StatCard
            title="Active Tenants"
            value={Object.keys(stats?.byTenant || {}).length}
            icon={<Users className="h-4 w-4" />}
          />
        </div>
        
        {/* Tenant Distribution Table */}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tenant</TableHead>
              <TableHead>Assigned</TableHead>
              <TableHead>Unassigned</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Usage</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(stats?.byTenant || {}).map(([tenantName, data]) => {
              const total = data.assigned + data.unassigned;
              const usage = (data.assigned / total) * 100;
              
              return (
                <TableRow key={tenantName}>
                  <TableCell className="font-medium">{tenantName}</TableCell>
                  <TableCell>{data.assigned}</TableCell>
                  <TableCell>{data.unassigned}</TableCell>
                  <TableCell>{total}</TableCell>
                  <TableCell>
                    <Progress value={usage} className="w-20" />
                    <span className="ml-2 text-sm text-muted-foreground">
                      {usage.toFixed(0)}%
                    </span>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedTenant(tenantName)}
                    >
                      Manage
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
```

---

## 6. Migration Strategy

### 6.1 Database Migration Script

```sql
-- ============================================
-- MIGRATION SCRIPT: v5 to v6
-- ============================================

BEGIN;

-- Step 1: Add tenant_id to device tables
ALTER TABLE sensor_devices 
ADD COLUMN tenant_id UUID,
ADD COLUMN lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN assigned_space_id UUID,
ADD COLUMN assigned_at TIMESTAMP,
ADD COLUMN chirpstack_device_id UUID,
ADD COLUMN chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

ALTER TABLE display_devices 
ADD COLUMN tenant_id UUID,
ADD COLUMN lifecycle_state VARCHAR(50) DEFAULT 'provisioned',
ADD COLUMN assigned_space_id UUID,
ADD COLUMN assigned_at TIMESTAMP,
ADD COLUMN chirpstack_device_id UUID,
ADD COLUMN chirpstack_sync_status VARCHAR(50) DEFAULT 'pending';

-- Step 2: Backfill tenant_id from space assignments
UPDATE sensor_devices sd
SET tenant_id = s.tenant_id,
    assigned_space_id = sp.id,
    assigned_at = sp.created_at
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.sensor_device_id = sd.id;

UPDATE display_devices dd
SET tenant_id = s.tenant_id,
    assigned_space_id = sp.id,
    assigned_at = sp.created_at
FROM spaces sp
JOIN sites s ON s.id = sp.site_id
WHERE sp.display_device_id = dd.id;

-- Step 3: Assign orphaned devices to platform tenant
UPDATE sensor_devices 
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

UPDATE display_devices 
SET tenant_id = '00000000-0000-0000-0000-000000000000'
WHERE tenant_id IS NULL;

-- Step 4: Make tenant_id NOT NULL and add foreign key
ALTER TABLE sensor_devices 
ALTER COLUMN tenant_id SET NOT NULL,
ADD CONSTRAINT fk_sensor_devices_tenant 
FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE display_devices 
ALTER COLUMN tenant_id SET NOT NULL,
ADD CONSTRAINT fk_display_devices_tenant 
FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- Step 5: Add indexes
CREATE INDEX idx_sensor_devices_tenant ON sensor_devices(tenant_id, status);
CREATE INDEX idx_sensor_devices_deveui ON sensor_devices(dev_eui);
CREATE INDEX idx_display_devices_tenant ON display_devices(tenant_id, status);
CREATE INDEX idx_display_devices_deveui ON display_devices(dev_eui);

-- Step 6: Create new tables
CREATE TABLE gateways (
    -- Table definition from earlier
);

CREATE TABLE device_assignments (
    -- Table definition from earlier
);

CREATE TABLE chirpstack_sync (
    -- Table definition from earlier
);

-- Step 7: Migrate gateway data from ChirpStack (manual step required)
-- This would need to be done via a script that reads from ChirpStack

-- Step 8: Enable Row-Level Security
ALTER TABLE sensor_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateways ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;

-- Step 9: Create RLS policies
-- Policies from earlier

-- Step 10: Update status values to new lifecycle states
UPDATE sensor_devices 
SET status = 'unassigned' 
WHERE status = 'orphan';

UPDATE sensor_devices 
SET status = 'assigned' 
WHERE assigned_space_id IS NOT NULL;

-- Step 11: Normalize all DevEUIs to uppercase
UPDATE sensor_devices 
SET dev_eui = UPPER(dev_eui);

UPDATE display_devices 
SET dev_eui = UPPER(dev_eui);

-- Step 12: Add check constraint for uppercase
ALTER TABLE sensor_devices 
ADD CONSTRAINT check_dev_eui_uppercase 
CHECK (dev_eui = UPPER(dev_eui));

ALTER TABLE display_devices 
ADD CONSTRAINT check_dev_eui_uppercase 
CHECK (dev_eui = UPPER(dev_eui));

COMMIT;
```

### 6.2 Rollback Plan

```sql
-- ============================================
-- ROLLBACK SCRIPT: v6 to v5
-- ============================================

BEGIN;

-- Disable RLS
ALTER TABLE sensor_devices DISABLE ROW LEVEL SECURITY;
ALTER TABLE display_devices DISABLE ROW LEVEL SECURITY;
ALTER TABLE spaces DISABLE ROW LEVEL SECURITY;

-- Drop new tables
DROP TABLE IF EXISTS gateways CASCADE;
DROP TABLE IF EXISTS device_assignments CASCADE;
DROP TABLE IF EXISTS chirpstack_sync CASCADE;

-- Remove columns from device tables
ALTER TABLE sensor_devices 
DROP COLUMN tenant_id,
DROP COLUMN lifecycle_state,
DROP COLUMN assigned_space_id,
DROP COLUMN assigned_at,
DROP COLUMN chirpstack_device_id,
DROP COLUMN chirpstack_sync_status;

ALTER TABLE display_devices 
DROP COLUMN tenant_id,
DROP COLUMN lifecycle_state,
DROP COLUMN assigned_space_id,
DROP COLUMN assigned_at,
DROP COLUMN chirpstack_device_id,
DROP COLUMN chirpstack_sync_status;

-- Restore original status values
UPDATE sensor_devices 
SET status = 'orphan' 
WHERE status = 'unassigned';

COMMIT;
```

---

## 7. Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create v6 database schema
- [ ] Implement migration scripts
- [ ] Add RLS policies
- [ ] Create ChirpStack sync table

### Phase 2: Backend Services (Weeks 3-4)
- [ ] Implement TenantContext enhancements
- [ ] Create DeviceService with proper scoping
- [ ] Build ChirpStackSyncService
- [ ] Add v6 API endpoints

### Phase 3: API Layer (Week 5)
- [ ] Create /api/v6/ endpoints
- [ ] Implement dashboard bundle endpoint
- [ ] Add device pool management APIs
- [ ] Set up GraphQL schema (optional)

### Phase 4: Frontend Updates (Weeks 6-7)
- [ ] Update DeviceService to use v6 APIs
- [ ] Create TenantSwitcher component
- [ ] Build DevicePoolManager for platform admins
- [ ] Implement efficient caching strategy

### Phase 5: Testing & Migration (Week 8)
- [ ] Integration tests for tenant isolation
- [ ] Performance testing with large datasets
- [ ] Migrate production data
- [ ] Monitor and optimize

---

## 8. Success Metrics

### Performance Metrics
- **API Response Time**: < 200ms for device list (from 800ms+ in v5)
- **Dashboard Load Time**: < 1 second (from 3+ seconds in v5)
- **Database Query Time**: < 50ms for tenant-scoped queries

### Data Integrity Metrics
- **Zero cross-tenant data leaks** verified by automated tests
- **100% device-tenant assignment** accuracy
- **< 1% ChirpStack sync failures**

### User Experience Metrics
- **Reduced support tickets** for "missing devices" issues
- **Platform admin efficiency**: < 10 seconds to switch tenants
- **Zero 500 errors** on production endpoints

---

## 9. Risk Mitigation

### Risk 1: Data Migration Failure
**Mitigation**: 
- Comprehensive backup before migration
- Tested rollback scripts
- Staged migration (dev → staging → production)

### Risk 2: Performance Degradation
**Mitigation**:
- Proper indexes on all foreign keys
- Query optimization with EXPLAIN ANALYZE
- Connection pooling and caching

### Risk 3: ChirpStack Integration Issues
**Mitigation**:
- Async sync with retry logic
- Manual override capabilities
- Detailed sync status tracking

---

## Conclusion

This v6 architecture addresses all critical issues identified in the v5 system:

1. ✅ **Direct tenant ownership** of all entities
2. ✅ **Efficient data access** with single-query patterns
3. ✅ **Clear device lifecycle** management
4. ✅ **Seamless platform admin** experience
5. ✅ **Robust tenant isolation** with RLS
6. ✅ **Optimized frontend** with smart caching

The migration path is clear, testable, and reversible, ensuring a smooth transition from v5 to v6.

---

**Document Version**: 1.0
**Created**: 2025-10-22
**Author**: Smart Parking Platform Architecture Team
