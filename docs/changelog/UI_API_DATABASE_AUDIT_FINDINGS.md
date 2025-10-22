# UI/API/Database Alignment Audit - v5.3 Multi-Tenant Parking System
**Date**: 2025-10-21
**Build**: 20251021.7
**Status**: CRITICAL MISALIGNMENT FOUND

---

## Executive Summary

**CRITICAL FINDING**: The frontend UI has been incorrectly updated to call `/api/v1/sites` which **DOES NOT EXIST** in the backend API. The v5.3 system has a **two-tier architecture**: Sites → Spaces, not just flat spaces.

---

## Database Schema Analysis

### ✅ Actual Database Tables

#### 1. `sites` Table
```sql
CREATE TABLE sites (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    location JSONB,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, name)
);
```
**Purpose**: Physical locations/buildings/campuses owned by a tenant

#### 2. `spaces` Table
```sql
CREATE TABLE spaces (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    site_id UUID NOT NULL REFERENCES sites(id),  -- FK to sites!
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    building VARCHAR(100),
    floor VARCHAR(20),
    zone VARCHAR(50),
    state VARCHAR(20) NOT NULL DEFAULT 'FREE',
    sensor_eui VARCHAR(16),
    display_eui VARCHAR(16),
    gps_latitude NUMERIC(10,8),
    gps_longitude NUMERIC(11,8),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    UNIQUE(tenant_id, site_id, code) WHERE deleted_at IS NULL
);
```
**Purpose**: Individual parking spaces within a site

### ✅ Data Model Hierarchy

```
Tenants
  └── Sites (buildings/locations)
        └── Spaces (parking spaces)
              ├── sensor_eui (IoT sensor)
              ├── display_eui (e-ink display)
              ├── state (FREE/OCCUPIED/RESERVED/MAINTENANCE)
              └── location fields (building, floor, zone)
```

**Key Insight**: Sites and Spaces are **separate entities** with a parent-child relationship.

---

## API Endpoint Reality Check

### ❌ MISSING: Sites API Endpoints

**Expected but NOT IMPLEMENTED**:
- `GET /api/v1/sites` - Does not exist
- `POST /api/v1/sites` - Does not exist
- `PATCH /api/v1/sites/{id}` - Does not exist
- `DELETE /api/v1/sites/{id}` - Does not exist

**Evidence**:
1. No `sites.py` router file in `/opt/v5-smart-parking/src/routers/`
2. No sites router registered in `main.py`
3. OpenAPI spec shows `/api/v1/sites` but it's not implemented

### ✅ EXISTS: Spaces API Endpoints

**Implemented in `spaces_tenanted.py`**:
- `GET /api/v1/spaces/` - List spaces (with site_id filter)
- `POST /api/v1/spaces/` - Create space
- `GET /api/v1/spaces/{space_id}` - Get space
- `PATCH /api/v1/spaces/{space_id}` - Update space
- `DELETE /api/v1/spaces/{space_id}` - Delete space
- `POST /api/v1/spaces/{space_id}/assign-sensor` - Assign sensor
- `POST /api/v1/spaces/{space_id}/assign-display` - Assign display

**Spaces API Response Fields**:
```json
{
  "id": "uuid",
  "code": "A-101",
  "name": "Parking Space A-101",
  "building": "Building A",
  "floor": "1",
  "zone": "North",
  "state": "FREE",
  "site_id": "uuid",  // <-- FK to sites table
  "tenant_id": "uuid",
  "sensor_eui": "1234567890ABCDEF",
  "display_eui": "FEDCBA0987654321",
  "gps_latitude": 37.7749,
  "gps_longitude": -122.4194,
  "created_at": "2025-10-21T10:00:00Z",
  "updated_at": "2025-10-21T10:00:00Z"
}
```

**CRITICAL**: Spaces API returns `site_id` (UUID) but **NOT** `site_name` (string).

---

## Frontend Service Layer Issues

### ❌ BROKEN: locationService.js

**Current State** (Build 20251021.7):
```javascript
async getLocations(params = {}) {
  const response = await apiClient.get('/api/v1/spaces/', { params });
  const spaces = response.data?.spaces || response.data || [];
  return spaces;  // Returns spaces as "locations"
}
```

**Problem**:
1. Calls `/api/v1/spaces/` but pretends they are "locations"
2. No way to get actual sites (buildings)
3. Frontend thinks spaces ARE locations (wrong)

### ❌ BROKEN: useLocations.js Hook

**Current State**:
```javascript
const response = await apiClient.get(`/api/v1/spaces/`, {
  signal: abortRef.current.signal,
  params: { includeArchived: archived === "true" }
});
const spaces = response.data?.spaces || response.data || [];
setTree(Array.isArray(spaces) ? spaces : []);
```

**Problem**: Returns flat array of parking spaces, not a hierarchical tree of sites.

### ❌ BROKEN: DeviceConfigurationModal.tsx

**Current State**:
```typescript
const { spaces } = await parkingSpacesService.getSpaces();
const uniqueSites = [...new Set(spaces.map(s => s.site_name).filter(Boolean))];
```

**Problem**: Spaces API doesn't return `site_name` field! This code will fail.

---

## UI Page Confusion

### Duplicate/Conflicting Pages

**Navigation Menu**:
- "Locations" (Locations.jsx → LocationManager.jsx)
- "Parking Spaces" (ParkingSpaces.jsx)

**Problem**: Users see TWO menu items that should display the same data

**Current Behavior**:
- **Locations page**: Tries to show hierarchical location tree (doesn't work)
- **Parking Spaces page**: Shows parking spaces in table/card view

---

## Root Cause Analysis

### How Did This Happen?

1. **Initial Assumption (WRONG)**: "In v5.3, there is no separate locations hierarchy - just spaces"
2. **Reality (CORRECT)**: v5.3 has TWO-TIER hierarchy: Sites → Spaces
3. **Missing API**: Sites CRUD endpoints were never implemented
4. **Workaround Attempts**: Frontend tried to use `/api/v1/spaces/` as if they were "locations"

### Why `/api/v1/sites` Appeared in OpenAPI Spec

The OpenAPI spec at `docs/api/smart-parking-openapi.yaml` includes `/api/v1/sites` endpoints, but:
- These were **planned** but never **implemented**
- The spec is out of sync with the actual codebase
- No `sites.py` router exists

---

## Impact Assessment

### 🔴 CRITICAL Issues

1. **Locations Page Broken**: Tries to call non-existent `/api/v1/sites` → 404/CORS errors
2. **DeviceConfigurationModal Broken**: References `s.site_name` which doesn't exist → runtime error
3. **No Way to Manage Sites**: Users cannot create/edit/delete sites (buildings)
4. **Confusing UX**: Two menu items ("Locations" and "Parking Spaces") for unclear purposes

### 🟡 MODERATE Issues

1. **Inconsistent Terminology**: Code mixes "sites", "locations", and "spaces"
2. **Missing Site Data**: Can't show which site a parking space belongs to (only site_id UUID)
3. **No Site Management UI**: No way to create a site before creating spaces

### 🟢 MINOR Issues

1. **Documentation Out of Sync**: OpenAPI spec includes non-existent endpoints
2. **Error Messages**: Still some legacy "Transform API" references

---

## Correct Architecture Understanding

### What Each Entity IS

| Entity | Purpose | Example |
|--------|---------|---------|
| **Site** | Physical location/building/campus | "Building A", "Downtown Parking Garage" |
| **Space** | Individual parking spot within a site | "A-101", "B-245", "VIP-05" |
| **Sensor** | IoT device detecting car presence | EUI: `1234567890ABCDEF` |
| **Display** | E-ink display showing space status | EUI: `FEDCBA0987654321` |

### Relationships

```
Tenant (e.g., "City of San Francisco")
  └── Site (e.g., "City Hall Parking Garage")
        ├── Metadata: timezone, GPS location
        └── Spaces (e.g., 200 parking spaces)
              ├── Space A-101 (sensor_eui=..., state=FREE)
              ├── Space A-102 (sensor_eui=..., state=OCCUPIED)
              └── Space A-103 (sensor_eui=..., state=RESERVED)
```

---

## Required Fixes

### Priority 1: Implement Sites API (Backend)

**Create `/opt/v5-smart-parking/src/routers/sites.py`**:
```python
from fastapi import APIRouter, Depends
from ..dependencies import get_tenant_context, require_admin

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])

@router.get("/")
async def list_sites(tenant: TenantContext = Depends(get_tenant_context)):
    # Query sites table filtered by tenant_id
    pass

@router.post("/", dependencies=[Depends(require_admin)])
async def create_site(site: SiteCreate, tenant: TenantContext = Depends(get_tenant_context)):
    # Create site in sites table
    pass

@router.get("/{site_id}")
async def get_site(site_id: UUID, tenant: TenantContext = Depends(get_tenant_context)):
    # Get single site
    pass

@router.patch("/{site_id}", dependencies=[Depends(require_admin)])
async def update_site(site_id: UUID, updates: SiteUpdate, tenant: TenantContext = Depends(get_tenant_context)):
    # Update site
    pass

@router.delete("/{site_id}", dependencies=[Depends(require_admin)])
async def delete_site(site_id: UUID, tenant: TenantContext = Depends(get_tenant_context)):
    # Soft delete site (set is_active=false)
    pass
```

**Register in main.py**:
```python
from .routers.sites import router as sites_router
app.include_router(sites_router)
```

### Priority 2: Fix Spaces API to Include site_name

**Modify spaces_tenanted.py**:
```sql
SELECT
    s.id, s.code, s.name, s.building, s.floor, s.zone,
    s.state, s.site_id, s.tenant_id,
    sites.name AS site_name,  -- JOIN to get site name
    s.sensor_eui, s.display_eui,
    s.created_at, s.updated_at
FROM spaces s
LEFT JOIN sites ON s.site_id = sites.id
WHERE s.tenant_id = $1 AND s.deleted_at IS NULL
```

### Priority 3: Create Sites Management UI

**New Page**: `src/pages/Sites.jsx`
- List all sites for current tenant
- Create/Edit/Delete sites
- Show spaces count per site

**Update Navigation**:
```typescript
const navigationItems = [
  { id: 'dashboard', label: 'Dashboard', icon: Home },
  { id: 'sites', label: 'Sites', icon: Building },  // NEW
  { id: 'spaces', label: 'Parking Spaces', icon: Car },  // Renamed from "parking"
  { id: 'devices', label: 'Devices', icon: Wifi },
  { id: 'gateways', label: 'Gateways', icon: Settings },
  // REMOVE "Locations" - it's redundant
];
```

### Priority 4: Fix locationService.js

**Rename to siteService.js**:
```javascript
export const siteService = {
  async getSites(params = {}) {
    const response = await apiClient.get('/api/v1/sites', { params });
    return response.data;
  },
  // ... CRUD methods for sites
};
```

### Priority 5: Update Terminology Throughout

**Find and Replace**:
- `locationService` → `siteService` (for site management)
- Keep `parkingSpacesService` for spaces
- Remove "Transform API" references
- Update all user-facing labels

---

## Recommended Terminology

| Old (Confusing) | New (Clear) |
|----------------|-------------|
| "Locations" | "Sites" (for buildings) |
| "Locations" | "Parking Spaces" (for spots) |
| "Transform API" | "Parking API" |
| `locationService` | `siteService` |
| `/api/v1/sites` | Implement this! |

---

## Next Steps

1. **Backend**: Implement Sites API router
2. **Backend**: Add site_name to Spaces API responses
3. **Frontend**: Create Sites management page
4. **Frontend**: Update navigation menu (remove "Locations", add "Sites")
5. **Frontend**: Fix all service files
6. **Frontend**: Update all UI labels
7. **Documentation**: Update OpenAPI spec to match reality
8. **Testing**: Verify full flow (create site → create spaces → assign devices)

---

## Conclusion

The v5.3 system architecture is **CORRECT** in the database (Sites → Spaces), but the **API is incomplete** (missing Sites endpoints), causing the **frontend to break** when trying to manage the hierarchy.

**Fix Strategy**: Implement the missing Sites API layer, then update the frontend to properly distinguish between Sites (buildings) and Spaces (parking spots).
