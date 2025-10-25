# Smart Parking Platform - UI Architecture Documentation v5.4

**Last Updated:** 2025-10-25
**Version:** 5.4.0
**Frontend Stack:** React + TypeScript/JavaScript

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [Platform Admin UI](#platform-admin-ui)
4. [Device Manager Application](#device-manager-application)
5. [API Integration Patterns](#api-integration-patterns)
6. [State Management](#state-management)
7. [Component Library](#component-library)
8. [Authentication Flow](#authentication-flow)

---

## Overview

The Smart Parking Platform UI is designed as a **multi-tenant, platform-admin-enabled** web application with two primary interfaces:

1. **Platform Admin UI** (`/frontend/src`) - Tenant management and system-wide oversight
2. **Device Manager** (`/frontend/device-manager`) - Operational IoT device and parking management

### Key Design Goals

- **Multi-tenancy first**: Every UI component respects tenant context
- **Platform admin superpowers**: Seamless switching between tenant views
- **Progressive enhancement**: Feature flags enable gradual rollout
- **API-driven**: All data operations via REST API (v5.3)
- **Responsive design**: Mobile-first with Tailwind CSS

---

## Architecture Principles

### 1. Tenant-Aware Components

Every component receives tenant context either through:
- **Auth Context** - Global authentication state with current tenant
- **API calls** - Tenant ID automatically included in requests
- **URL params** - Tenant selection persisted in route

```javascript
// Example: Component with tenant awareness
import { useAuth } from '../contexts/AuthContext';

function SpaceList() {
  const { currentTenant, user } = useAuth();

  // API automatically scopes to currentTenant
  const { data: spaces } = useSpaces();

  return (
    <div>
      <h2>{currentTenant.name} - Parking Spaces</h2>
      {/* ... */}
    </div>
  );
}
```

### 2. Feature Flag System

Progressive feature rollout using environment variables:

```javascript
// frontend/src/config/featureFlags.js
export const FeatureFlags = {
  USE_V6_API: process.env.REACT_APP_USE_V6_API === 'true',
  SHOW_PLATFORM_ADMIN_UI: process.env.REACT_APP_SHOW_PLATFORM_ADMIN === 'true',
  ENABLE_DEVICE_POOL: process.env.REACT_APP_ENABLE_DEVICE_POOL === 'true',
};

// Gradual rollout per feature
export const V6_ROLLOUT = {
  devices: FeatureFlags.USE_V6_API,
  gateways: false, // Still on v5
  spaces: false,   // Still on v5
};
```

**Usage:**
```javascript
if (FeatureFlags.SHOW_PLATFORM_ADMIN_UI && user.isPlatformAdmin) {
  return <PlatformAdminDashboard />;
}
```

### 3. Loose Coupling (Devices ↔ Spaces)

UI reflects the database design - devices exist independently:

```
┌─────────────────┐      ┌──────────────────┐
│   Device List   │      │   Space List     │
│                 │      │                  │
│ • View all      │      │ • View all       │
│ • Edit metadata │      │ • Assign device  │
│ • Archive       │      │ • Unassign       │
└─────────────────┘      └──────────────────┘
         │                        │
         └────────────────────────┘
                    │
              ┌──────────┐
              │   API    │
              │ /devices │
              │ /spaces  │
              └──────────┘
```

---

## Platform Admin UI

Located in `/frontend/src/components/PlatformAdmin/`

### TenantSwitcher Component

**Purpose:** Allow platform admins to switch tenant context instantly

**File:** `frontend/src/components/PlatformAdmin/TenantSwitcher.jsx`

**API Integration:**
```javascript
// Fetches accessible tenants
GET /api/v1/me/tenants
Response: {
  is_platform_admin: true,
  current_tenant_id: "uuid",
  tenants: [
    { id: "platform", name: "Platform Admin (All Tenants)", ... },
    { id: "uuid-1", name: "Acme Corp", role: "owner", is_current: true },
    { id: "uuid-2", name: "Beta Inc", role: "admin", is_current: false }
  ]
}

// Switches tenant context
POST /api/v1/auth/switch-tenant?tenant_id=target-uuid
Response: {
  access_token: "new-jwt-with-tenant-context",
  refresh_token: "...",
  user: {...},
  tenants: [...],
  is_platform_admin: true
}
```

**User Flow:**
1. Platform admin sees dropdown in navbar
2. Click shows all accessible tenants + "Platform (All Tenants)" option
3. Selecting tenant calls API, receives new JWT
4. UI redirects to appropriate dashboard
5. All subsequent API calls use new tenant context

**UI Features:**
- Current tenant highlighted with checkmark
- Platform mode shows special badge
- Subscription tier displayed per tenant
- Auto-close on mobile after selection

### DevicePoolManager Component

**Purpose:** System-wide view of device distribution across all tenants

**File:** `frontend/src/components/PlatformAdmin/DevicePoolManager.jsx`

**API Integration:**
```javascript
// Platform admin fetches all tenants with device stats
GET /api/v1/admin/tenants
Response: {
  tenants: [
    {
      id: "uuid",
      name: "Acme Corp",
      stats: {
        spaces_count: 50,
        sensor_devices_count: 48,
        display_devices_count: 50,
        total_devices_count: 98,
        active_reservations: 12,
        users_count: 5
      }
    }
  ]
}
```

**Features:**
- **Summary Cards:**
  - Total devices across platform
  - Assigned vs. unassigned ratio
  - Active tenant count

- **Tenant Table:**
  - Device counts per tenant
  - Usage percentage (assigned/total)
  - Quick "Manage" button to switch tenant

**Use Case:** Platform admin monitoring device allocation efficiency

---

## Device Manager Application

Located in `/frontend/device-manager/src/`

### Main Platform Component

**File:** `frontend/device-manager/src/components/SenseMyIoTPlatform.tsx`

**Architecture:**
```
┌──────────────────────────────────────────────┐
│           SenseMyIoTPlatform                 │
│  ┌────────────┐  ┌──────────────────────┐   │
│  │  Sidebar   │  │   Content Area       │   │
│  │            │  │                      │   │
│  │ • Dashboard│  │  ┌────────────────┐ │   │
│  │ • Sites    │  │  │   Dashboard    │ │   │
│  │ • Spaces   │  │  │   or           │ │   │
│  │ • Devices  │  │  │   Sites        │ │   │
│  │ • Gateways │  │  │   or           │ │   │
│  │ • Analytics│  │  │   Devices      │ │   │
│  └────────────┘  │  │   (Dynamic)    │ │   │
│                  │  └────────────────┘ │   │
│                  └──────────────────────┘   │
└──────────────────────────────────────────────┘
```

**Navigation Items:**
```javascript
const navigationItems = [
  { id: 'dashboard', label: 'Dashboard', icon: Home },
  { id: 'sites', label: 'Sites', icon: Building2 },
  { id: 'parking', label: 'Parking Spaces', icon: Car },
  { id: 'devices', label: 'Devices', icon: Wifi },
  { id: 'gateways', label: 'Gateways', icon: Settings },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'users', label: 'Users', icon: Users, disabled: true }
];
```

**State Management:**
- `activeTab` - Current page
- `pageFilters` - Passed from dashboard (e.g., "show occupied spaces")
- `sidebar.isOpen` - Persisted to localStorage
- `user` & `currentTenant` - From AuthContext

**API Integration:**
All pages fetch data scoped to `currentTenant.id`:

```javascript
// Example: Devices page
function Devices({ initialFilters }) {
  const { currentTenant } = useAuth();

  // API call automatically includes tenant context
  const { data: devices } = useQuery(
    ['devices', currentTenant.id],
    () => fetch('/api/v1/devices').then(r => r.json())
  );

  return <DeviceTable devices={devices} />;
}
```

### Pages

#### 1. Dashboard (`pages/Dashboard.jsx`)

**API Calls:**
```javascript
GET /api/v1/spaces/stats/summary
Response: { FREE: 125, OCCUPIED: 45, RESERVED: 12, MAINTENANCE: 3, total: 185 }

GET /api/v1/spaces?limit=100
Response: { spaces: [...], total: 185 }
```

**Features:**
- Space occupancy overview cards
- Quick stats: Free, Occupied, Reserved counts
- Navigation shortcuts (clicking "45 Occupied" → filters spaces page)
- Real-time updates via polling/WebSocket (TODO)

#### 2. Sites (`pages/Sites.jsx`)

**API Calls:**
```javascript
GET /api/v1/tenants/{tenant_id}/sites
Response: {
  sites: [
    {
      id: "uuid",
      name: "Downtown Parking Garage",
      space_count: 125,
      occupied_count: 45,
      occupancy_rate: 0.36
    }
  ]
}

POST /api/v1/tenants/{tenant_id}/sites
Body: { name, address, timezone, gps_latitude, gps_longitude }
Response: { id, name, created_at, ... }
```

**Features:**
- Hierarchical view: Tenant → Sites
- Create new site modal
- Site statistics summary
- Navigate to spaces within site

#### 3. Parking Spaces (`pages/ParkingSpaces.jsx`)

**API Calls:**
```javascript
GET /api/v1/spaces?site_id={uuid}&floor=1&state=free
Response: {
  spaces: [
    {
      id: "uuid",
      code: "A-101",
      name: "Space A-101",
      state: "FREE",
      sensor_eui: "0004A30B001A2B3C",
      display_eui: "2020203907290902",
      last_sensor_reading_at: "2025-10-25T14:25:00Z"
    }
  ],
  total: 185
}

PATCH /api/v1/spaces/{space_id}
Body: { state: "MAINTENANCE", sensor_eui: "..." }
Response: { id, state, updated_at, ... }

POST /api/v1/spaces/{space_id}/assign-sensor?sensor_eui=ABC123
Response: { id, sensor_eui, display_eui, state, updated_at }
```

**Features:**
- **Filtering:**
  - By site, floor, zone
  - By state (FREE, OCCUPIED, RESERVED, MAINTENANCE)
  - By device assignment status

- **Actions:**
  - Edit space details
  - Assign/unassign sensor
  - Assign/unassign display
  - Change state manually
  - View space history

- **Device Assignment UI:**
  ```
  ┌─────────────────────────────────┐
  │  Space A-101                    │
  │  ┌───────────────────────────┐  │
  │  │ Sensor: 0004A30B001A2B3C  │  │
  │  │ [Change] [Remove]         │  │
  │  └───────────────────────────┘  │
  │  ┌───────────────────────────┐  │
  │  │ Display: 2020203907290902 │  │
  │  │ [Change] [Remove]         │  │
  │  └───────────────────────────┘  │
  └─────────────────────────────────┘
  ```

#### 4. Devices (`pages/Devices.jsx`)

**API Calls:**
```javascript
GET /api/v1/devices?category=sensor&status=active
Response: [
  {
    id: "uuid",
    deveui: "0004A30B001A2B3C",
    category: "sensor",
    device_type: "Browan TBMS100",
    status: "active",
    enabled: true,
    last_seen_at: "2025-10-25T14:25:00Z",
    assigned_space: { id: "uuid", name: "Space A-101" }
  }
]

PUT /api/v1/devices/{deveui}
Body: { device_type, device_model, enabled, status }
Response: { status: "updated", deveui, category }

PATCH /api/v1/devices/{deveui}/description
Body: { description: "Building A - Floor 1", tags: {...} }
Response: { deveui, name, description, tags, updated_at }
```

**Features:**
- **Device List:**
  - Sensors and displays in unified view
  - Filter by category, type, status
  - Show orphan devices (unassigned)
  - Last seen timestamp with health indicator

- **Device Details Modal:**
  - ChirpStack sync status
  - Assignment status (assigned space or "Unassigned")
  - Metadata editor (description, tags)
  - Archive button

- **Orphan Device Workflow:**
  ```
  1. Orphan detected via webhook → shows in list with "Orphan" badge
  2. Admin clicks "Assign to Space"
  3. Modal shows available spaces
  4. Selection → POST /api/v1/spaces/{id}/assign-sensor?sensor_eui=XXX
  5. Device moves from "orphan" to "active" status
  ```

#### 5. Gateways (`pages/Gateways.jsx`)

**API Calls:**
```javascript
GET /api/v1/gateways
Response: [
  {
    gw_eui: "7276ff002e062e5e",
    gateway_name: "Downtown Gateway 1",
    description: "Building A - Rooftop",
    latitude: 40.7580,
    longitude: -73.9855,
    last_seen_at: "2025-10-25T14:25:00Z",
    is_online: true,
    status: "online"
  }
]

GET /api/v1/gateways/stats/summary
Response: { total: 10, online: 8, offline: 2 }

PATCH /api/v1/gateways/{gw_eui}
Body: { description: "...", tags: {...} }
Response: { gw_eui, gateway_name, description, tags, updated_at }
```

**Features:**
- **Gateway Health Dashboard:**
  - Total gateways count
  - Online/offline status (last seen < 5 min = online)
  - Map view with GPS coordinates

- **Gateway List:**
  - Online status indicator (green/red)
  - Last seen timestamp
  - Description editor (ChirpStack sync)
  - Tag management for site assignment

#### 6. Analytics (`pages/Analytics.jsx`)

**API Calls:**
```javascript
// Historical occupancy data (TODO: implement endpoint)
GET /api/v1/analytics/occupancy?from=2025-10-20&to=2025-10-25
Response: {
  timeline: [
    { timestamp: "2025-10-20T00:00:00Z", free: 120, occupied: 30, reserved: 5 }
  ]
}

// Device health metrics (Prometheus-backed)
GET /metrics (scraped by Prometheus)
```

**Features:**
- Occupancy trends over time
- Device health dashboard (battery, RSSI)
- Usage patterns by floor/zone
- Gateway coverage analysis

---

## API Integration Patterns

### 1. Authentication Context

**File:** `frontend/device-manager/src/contexts/AuthContext.jsx`

```javascript
const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [currentTenant, setCurrentTenant] = useState(null);
  const [accessToken, setAccessToken] = useState(null);

  // Login
  const login = async (email, password) => {
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    setAccessToken(data.access_token);
    setUser(data.user);
    setCurrentTenant(data.tenants[0]); // Primary tenant

    localStorage.setItem('token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
  };

  // Logout
  const logout = () => {
    setUser(null);
    setCurrentTenant(null);
    setAccessToken(null);
    localStorage.clear();
  };

  // Switch tenant (platform admin)
  const switchTenant = async (tenantId) => {
    const response = await fetch(`/api/v1/auth/switch-tenant?tenant_id=${tenantId}`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });

    const data = await response.json();

    setAccessToken(data.access_token);
    setCurrentTenant(data.tenants.find(t => t.id === tenantId));

    localStorage.setItem('token', data.access_token);
  };

  return (
    <AuthContext.Provider value={{ user, currentTenant, accessToken, login, logout, switchTenant }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

### 2. API Client (Fetch Wrapper)

**Pattern:**
```javascript
// Base API client with automatic tenant scoping
async function apiClient(endpoint, options = {}) {
  const token = localStorage.getItem('token');

  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers
    }
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (response.status === 401) {
    // Token expired - try refresh
    await refreshToken();
    // Retry original request
    return apiClient(endpoint, options);
  }

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'API request failed');
  }

  return response.json();
}

// Usage
const spaces = await apiClient('/api/v1/spaces?state=free');
```

### 3. React Query Integration (Recommended)

```javascript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Fetch spaces
function useSpaces(filters = {}) {
  const { currentTenant } = useAuth();

  return useQuery({
    queryKey: ['spaces', currentTenant.id, filters],
    queryFn: async () => {
      const params = new URLSearchParams(filters);
      return apiClient(`/api/v1/spaces?${params}`);
    },
    enabled: !!currentTenant,
    staleTime: 30000 // 30 seconds
  });
}

// Assign device to space
function useAssignDevice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ spaceId, sensorEui }) => {
      return apiClient(`/api/v1/spaces/${spaceId}/assign-sensor?sensor_eui=${sensorEui}`, {
        method: 'POST'
      });
    },
    onSuccess: () => {
      // Invalidate spaces query to refetch
      queryClient.invalidateQueries(['spaces']);
      queryClient.invalidateQueries(['devices']);
    }
  });
}

// Usage in component
function SpaceList() {
  const { data: spaces, isLoading } = useSpaces({ state: 'free' });
  const assignDevice = useAssignDevice();

  const handleAssign = (spaceId, sensorEui) => {
    assignDevice.mutate({ spaceId, sensorEui });
  };

  if (isLoading) return <Spinner />;

  return <table>{/* ... */}</table>;
}
```

---

## State Management

### Current Approach: Context + React Query

**Benefits:**
- Simple for small team
- No Redux boilerplate
- Server state managed by React Query
- Client state in Context or component state

**Structure:**
```
AuthContext (Global)
  ├─ user
  ├─ currentTenant
  ├─ accessToken
  └─ methods: login, logout, switchTenant

React Query (Server State)
  ├─ spaces: useSpaces()
  ├─ devices: useDevices()
  ├─ gateways: useGateways()
  ├─ sites: useSites()
  └─ mutations: useAssignDevice(), useUpdateSpace()

Component State (Local UI)
  ├─ modal open/closed
  ├─ form inputs
  ├─ filters/sorting
  └─ sidebar collapsed
```

### Potential Future: Zustand (if needed)

```javascript
import create from 'zustand';

const useAppStore = create((set) => ({
  // Filters persisted across pages
  globalFilters: {},
  setGlobalFilter: (key, value) => set((state) => ({
    globalFilters: { ...state.globalFilters, [key]: value }
  })),

  // UI preferences
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen }))
}));
```

---

## Component Library

### Design System: Tailwind CSS

**Utilities:**
- `bg-gray-50` - Background colors
- `text-sm` - Typography
- `rounded-lg` - Border radius
- `shadow` - Elevation
- `hover:bg-gray-100` - Interactive states

**Common Components:**

#### Button
```javascript
<button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
  Save
</button>
```

#### Card
```javascript
<div className="bg-white shadow rounded-lg p-6">
  <h3 className="text-lg font-medium text-gray-900">Title</h3>
  <p className="mt-2 text-sm text-gray-500">Content</p>
</div>
```

#### Table
```javascript
<table className="min-w-full divide-y divide-gray-200">
  <thead className="bg-gray-50">
    <tr>
      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
        Name
      </th>
    </tr>
  </thead>
  <tbody className="bg-white divide-y divide-gray-200">
    {/* rows */}
  </tbody>
</table>
```

### Icon Library: Lucide React

```javascript
import { Wifi, MapPin, Settings } from 'lucide-react';

<Wifi className="w-5 h-5 text-gray-400" />
```

---

## Authentication Flow

### 1. Login Flow

```
┌─────────┐
│  User   │
└────┬────┘
     │ 1. Enter email/password
     ▼
┌─────────────────┐
│  Login Form     │
└────┬────────────┘
     │ 2. POST /api/v1/auth/login
     ▼
┌──────────────────┐
│      API         │
│  ┌────────────┐  │
│  │ Validate   │  │
│  │ Password   │  │
│  └──────┬─────┘  │
│         │        │
│  ┌──────▼─────┐  │
│  │ Generate   │  │
│  │ JWT Tokens │  │
│  └──────┬─────┘  │
└─────────┼────────┘
          │ 3. Return tokens + user + tenants
          ▼
┌──────────────────┐
│  Auth Context    │
│  ┌────────────┐  │
│  │ Store:     │  │
│  │ • token    │  │
│  │ • user     │  │
│  │ • tenant   │  │
│  └────────────┘  │
└─────────┬────────┘
          │ 4. Redirect to dashboard
          ▼
┌──────────────────┐
│    Dashboard     │
└──────────────────┘
```

### 2. Token Refresh Flow

```
API Request → 401 Unauthorized
     │
     ▼
Check refresh_token in localStorage
     │
     ├─ Exists → POST /api/v1/auth/refresh
     │              ↓
     │          New access_token + refresh_token
     │              ↓
     │          Update localStorage
     │              ↓
     │          Retry original request
     │
     └─ Missing → Redirect to /login
```

### 3. Platform Admin Tenant Switch Flow

```
┌──────────────────┐
│ Platform Admin   │
│ Clicks dropdown  │
└────┬─────────────┘
     │ 1. GET /api/v1/me/tenants
     ▼
┌──────────────────────┐
│ Show tenant list:    │
│ • Platform (All)     │
│ • Acme Corp (owner)  │
│ • Beta Inc (admin)   │
└────┬─────────────────┘
     │ 2. User selects "Acme Corp"
     ▼
POST /api/v1/auth/switch-tenant?tenant_id=acme-uuid
     │
     ▼
┌──────────────────────┐
│ API returns:         │
│ • new JWT (tenant=   │
│   acme)              │
│ • new refresh_token  │
└────┬─────────────────┘
     │ 3. Update AuthContext
     ▼
┌──────────────────────┐
│ currentTenant =      │
│ "Acme Corp"          │
│                      │
│ All subsequent API   │
│ calls use Acme       │
│ tenant context       │
└──────────────────────┘
```

---

## Summary: How UI Leverages API

### Key Integration Points

1. **Authentication:**
   - Login → `POST /api/v1/auth/login`
   - Refresh → `POST /api/v1/auth/refresh`
   - Switch → `POST /api/v1/auth/switch-tenant`

2. **Tenant Management (Platform Admin):**
   - List all → `GET /api/v1/admin/tenants`
   - Get my tenants → `GET /api/v1/me/tenants`

3. **Spaces:**
   - List → `GET /api/v1/spaces?filters`
   - Update → `PATCH /api/v1/spaces/{id}`
   - Assign sensor → `POST /api/v1/spaces/{id}/assign-sensor`
   - Stats → `GET /api/v1/spaces/stats/summary`

4. **Devices:**
   - List → `GET /api/v1/devices?category=sensor`
   - Update → `PUT /api/v1/devices/{deveui}`
   - Metadata → `PATCH /api/v1/devices/{deveui}/description`

5. **Gateways:**
   - List → `GET /api/v1/gateways`
   - Stats → `GET /api/v1/gateways/stats/summary`
   - Update → `PATCH /api/v1/gateways/{gw_eui}`

### Design Patterns

✅ **Automatic tenant scoping** - JWT contains tenant_id, API enforces isolation
✅ **Optimistic updates** - UI updates immediately, rolls back on error
✅ **Polling for real-time** - Spaces refresh every 30s to show sensor updates
✅ **Progressive enhancement** - Feature flags enable gradual rollout
✅ **Mobile-first responsive** - Works on tablet/phone for on-site management

---

**End of UI Architecture Documentation**
