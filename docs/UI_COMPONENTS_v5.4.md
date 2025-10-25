# Smart Parking Platform - UI Components Implementation Guide v5.4

**Last Updated:** 2025-10-25
**Version:** 5.4.0
**Purpose:** Implementation guide for enhanced platform admin and tenant management UI components

**Implementation Status:** ✅ COMPLETED - All components implemented and ready for integration

---

## Implementation Progress

| Component | Status | File Location |
|-----------|--------|---------------|
| AdminModeIndicator | ✅ Implemented | `frontend/device-manager/src/components/PlatformAdmin/AdminModeIndicator.jsx` |
| PlatformAdminQuickActions | ✅ Implemented | `frontend/device-manager/src/components/PlatformAdmin/PlatformAdminQuickActions.jsx` |
| DeviceAssignmentHistory | ✅ Implemented | `frontend/device-manager/src/components/PlatformAdmin/DeviceAssignmentHistory.jsx` |
| TenantLimitsWidget | ✅ Implemented | `frontend/device-manager/src/components/PlatformAdmin/TenantLimitsWidget.jsx` |
| useSimplifiedNav Hook | ✅ Implemented | `frontend/device-manager/src/hooks/useSimplifiedNav.js` |
| ApiKeysManagement | ✅ Implemented | `frontend/device-manager/src/components/PlatformAdmin/ApiKeysManagement.jsx` |
| Platform Admin Service | ✅ Implemented | `frontend/device-manager/src/services/platformAdminService.js` |
| API Keys Service | ✅ Implemented | `frontend/device-manager/src/services/apiKeysService.js` |
| Tailwind Animations | ✅ Configured | `frontend/device-manager/tailwind.config.js` |
| Component Index | ✅ Created | `frontend/device-manager/src/components/PlatformAdmin/index.js` |

---

## Table of Contents

1. [AdminModeIndicator Component](#adminmodeindicator-component)
2. [PlatformAdminQuickActions Component](#platformadminquickactions-component)
3. [DeviceAssignmentHistory Component](#deviceassignmenthistory-component)
4. [TenantLimitsWidget Component](#tenantlimitswidget-component)
5. [Role-Based Navigation Hook](#role-based-navigation-hook)
6. [ApiKeysManagement Component](#apikeysmanagement-component)
7. [Installation Instructions](#installation-instructions)
8. [Integration Guide](#integration-guide)

---

## AdminModeIndicator Component

**File:** `frontend/src/components/PlatformAdmin/AdminModeIndicator.jsx`

### Purpose
Visual indicator showing platform admins which tenant context they're currently viewing. Prevents confusion when switching between tenants.

### Implementation

```javascript
// frontend/src/components/PlatformAdmin/AdminModeIndicator.jsx

import React from 'react';
import { Shield, Eye } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { PLATFORM_TENANT_ID } from '../../config/featureFlags';

export function AdminModeIndicator() {
  const { currentTenant, user } = useAuth();

  if (!user?.is_platform_admin) {
    return null;
  }

  const isPlatformMode = currentTenant?.id === PLATFORM_TENANT_ID;

  return (
    <div className="fixed top-16 right-4 z-50 animate-fade-in">
      {isPlatformMode ? (
        <div className="bg-purple-100 text-purple-800 px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-lg border border-purple-200">
          <Shield className="w-4 h-4" />
          <span className="font-semibold">Platform Admin Mode</span>
          <span className="text-purple-600">•</span>
          <span>Viewing All Tenants</span>
        </div>
      ) : (
        <div className="bg-blue-100 text-blue-800 px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-lg border border-blue-200">
          <Eye className="w-4 h-4" />
          <span>Viewing as:</span>
          <span className="font-semibold">{currentTenant?.name}</span>
        </div>
      )}
    </div>
  );
}
```

### API Integration
- Reads `currentTenant` from AuthContext
- Updates automatically when tenant switched via `POST /api/v1/auth/switch-tenant`

### Usage
```javascript
// In main layout component
import { AdminModeIndicator } from './components/PlatformAdmin/AdminModeIndicator';

function MainLayout() {
  return (
    <div>
      <Navbar />
      <AdminModeIndicator />  {/* Add here */}
      <MainContent />
    </div>
  );
}
```

---

## PlatformAdminQuickActions Component

**File:** `frontend/src/components/PlatformAdmin/QuickActions.jsx`

### Purpose
Provides quick access to platform admin-only operations directly from any page.

### Implementation

```javascript
// frontend/src/components/PlatformAdmin/QuickActions.jsx

import React from 'react';
import { AlertCircle, Link2, FileText } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export function PlatformAdminQuickActions() {
  const { user, currentTenant } = useAuth();
  const navigate = useNavigate();
  const { data: orphanCount } = useOrphanDevicesCount();

  if (!user?.is_platform_admin) {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-purple-50 to-blue-50 border-l-4 border-purple-500 p-4 mb-6 rounded-r-lg shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple-600" />
          Platform Admin Actions
        </h3>
        {currentTenant?.id !== 'platform' && (
          <span className="text-xs text-gray-500">
            Viewing: {currentTenant?.name}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => navigate('/platform/orphan-devices')}
          className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm"
        >
          <AlertCircle className="w-4 h-4 text-orange-500" />
          Orphan Devices
          {orphanCount > 0 && (
            <span className="ml-1 px-2 py-0.5 bg-orange-100 text-orange-800 text-xs rounded-full">
              {orphanCount}
            </span>
          )}
        </button>

        <button
          onClick={() => navigate('/platform/reassign-device')}
          className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm"
        >
          <Link2 className="w-4 h-4 text-blue-500" />
          Reassign Device
        </button>

        <button
          onClick={() => navigate('/platform/audit-log')}
          className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm"
        >
          <FileText className="w-4 h-4 text-gray-500" />
          System Audit Log
        </button>
      </div>
    </div>
  );
}

// Hook to get orphan device count
function useOrphanDevicesCount() {
  const { currentTenant } = useAuth();

  return useQuery({
    queryKey: ['orphan-devices-count', currentTenant?.id],
    queryFn: async () => {
      const response = await fetch('/api/v1/orphan-devices', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      const data = await response.json();
      return data.orphan_devices?.length || 0;
    },
    enabled: currentTenant?.id === 'platform',
    refetchInterval: 60000 // Refresh every minute
  });
}
```

### API Integration
```javascript
GET /api/v1/orphan-devices
Response: { orphan_devices: [...], total: 5 }
```

### Usage
```javascript
// Add to dashboard or header
import { PlatformAdminQuickActions } from './components/PlatformAdmin/QuickActions';

function Dashboard() {
  return (
    <div>
      <PlatformAdminQuickActions />
      <DashboardContent />
    </div>
  );
}
```

---

## DeviceAssignmentHistory Component

**File:** `frontend/src/components/Devices/AssignmentHistory.jsx`

### Purpose
Shows complete assignment history for a device, leveraging the new `device_assignments` audit table.

### Implementation

```javascript
// frontend/src/components/Devices/AssignmentHistory.jsx

import React from 'react';
import { Link, Unlink, User } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

export function DeviceAssignmentHistory({ deviceEui }) {
  const { data: history, isLoading } = useDeviceHistory(deviceEui);

  if (isLoading) {
    return <div className="animate-pulse h-64 bg-gray-100 rounded"></div>;
  }

  if (!history || history.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No assignment history available</p>
      </div>
    );
  }

  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {history.map((assignment, idx) => (
          <li key={assignment.id}>
            <div className="relative pb-8">
              {/* Connector line */}
              {idx !== history.length - 1 && (
                <span
                  className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"
                  aria-hidden="true"
                />
              )}

              <div className="relative flex space-x-3">
                {/* Icon */}
                <div>
                  <span className={`h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white ${
                    assignment.unassigned_at
                      ? 'bg-red-100 text-red-600'
                      : 'bg-green-100 text-green-600'
                  }`}>
                    {assignment.unassigned_at ? (
                      <Unlink className="w-4 h-4" />
                    ) : (
                      <Link className="w-4 h-4" />
                    )}
                  </span>
                </div>

                {/* Content */}
                <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                  <div>
                    <p className="text-sm text-gray-900 font-medium">
                      {assignment.unassigned_at ? 'Unassigned from' : 'Assigned to'}{' '}
                      <span className="font-semibold">{assignment.space_code}</span>
                    </p>
                    {assignment.space_name && (
                      <p className="text-sm text-gray-500">{assignment.space_name}</p>
                    )}
                    {assignment.notes && (
                      <p className="mt-1 text-sm text-gray-600 italic">
                        "{assignment.notes}"
                      </p>
                    )}
                    {assignment.assigned_by_name && (
                      <p className="mt-1 text-xs text-gray-500 flex items-center gap-1">
                        <User className="w-3 h-3" />
                        by {assignment.assigned_by_name}
                      </p>
                    )}
                  </div>

                  <div className="whitespace-nowrap text-right text-sm text-gray-500">
                    <time dateTime={assignment.assigned_at}>
                      {formatRelativeTime(assignment.assigned_at)}
                    </time>
                    {assignment.unassigned_at && (
                      <div className="text-xs text-gray-400">
                        Duration: {calculateDuration(assignment.assigned_at, assignment.unassigned_at)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// API hook to fetch device history
function useDeviceHistory(deviceEui) {
  return useQuery({
    queryKey: ['device-history', deviceEui],
    queryFn: async () => {
      const response = await fetch(`/api/v1/devices/${deviceEui}/assignments`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch device history');
      }

      return response.json();
    },
    enabled: !!deviceEui
  });
}

// Helper functions
function formatRelativeTime(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function calculateDuration(start, end) {
  const diffMs = new Date(end) - new Date(start);
  const diffDays = Math.floor(diffMs / 86400000);
  const diffHours = Math.floor((diffMs % 86400000) / 3600000);

  if (diffDays > 0) return `${diffDays}d ${diffHours}h`;
  return `${diffHours}h`;
}
```

### API Integration
```javascript
// New endpoint needed
GET /api/v1/devices/{deveui}/assignments
Response: [
  {
    id: "uuid",
    device_eui: "0004A30B001A2B3C",
    space_id: "uuid",
    space_code: "A-101",
    space_name: "Space A-101",
    assigned_at: "2025-10-20T10:00:00Z",
    unassigned_at: "2025-10-25T14:00:00Z",
    assigned_by: "user-uuid",
    assigned_by_name: "John Admin",
    notes: "Moved to new floor"
  }
]
```

### Usage
```javascript
// In device details modal
function DeviceDetailsModal({ device }) {
  const [activeTab, setActiveTab] = useState('details');

  return (
    <Modal>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="history">Assignment History</TabsTrigger>
        </TabsList>

        <TabsContent value="details">
          <DeviceDetails device={device} />
        </TabsContent>

        <TabsContent value="history">
          <DeviceAssignmentHistory deviceEui={device.deveui} />
        </TabsContent>
      </Tabs>
    </Modal>
  );
}
```

---

## TenantLimitsWidget Component

**File:** `frontend/src/components/Tenant/LimitsWidget.jsx`

### Purpose
Visualizes tenant resource usage against configured limits, helping admins understand capacity.

### Implementation

```javascript
// frontend/src/components/Tenant/LimitsWidget.jsx

import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useQuery } from '@tanstack/react-query';

export function TenantLimitsWidget() {
  const { currentTenant } = useAuth();
  const { data: limits, isLoading } = useTenantLimits();

  if (!currentTenant || currentTenant.id === 'platform') {
    return null; // Don't show in platform mode
  }

  if (isLoading) {
    return <div className="animate-pulse h-48 bg-gray-100 rounded"></div>;
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Resource Usage</h3>
        {limits?.hasWarnings && (
          <span className="flex items-center gap-1 text-sm text-orange-600">
            <AlertTriangle className="w-4 h-4" />
            Approaching limits
          </span>
        )}
      </div>

      <div className="space-y-4">
        <LimitBar
          label="Sites"
          current={limits?.usage?.sites_count || 0}
          max={limits?.quotas?.max_sites || 10}
          icon="building"
        />

        <LimitBar
          label="Parking Spaces"
          current={limits?.usage?.spaces_count || 0}
          max={limits?.quotas?.max_spaces || 500}
          icon="car"
        />

        <LimitBar
          label="Devices (Sensors + Displays)"
          current={limits?.usage?.total_devices || 0}
          max={limits?.quotas?.max_devices || 1000}
          icon="wifi"
        />

        <LimitBar
          label="Active Users"
          current={limits?.usage?.users_count || 0}
          max={limits?.quotas?.max_users || 50}
          icon="users"
        />
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">
          Need higher limits? <a href="/contact-sales" className="text-blue-600 hover:underline">Contact sales</a>
        </p>
      </div>
    </div>
  );
}

function LimitBar({ label, current, max, icon }) {
  const percentage = Math.min((current / max) * 100, 100);
  const isNearLimit = percentage > 80;
  const isAtLimit = percentage >= 100;

  return (
    <div>
      <div className="flex justify-between text-sm mb-1.5">
        <span className="text-gray-700 font-medium">{label}</span>
        <span className={`font-semibold ${
          isAtLimit ? 'text-red-600' :
          isNearLimit ? 'text-orange-600' :
          'text-gray-900'
        }`}>
          {current.toLocaleString()} / {max.toLocaleString()}
        </span>
      </div>

      <div className="relative">
        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${
              isAtLimit ? 'bg-red-500' :
              isNearLimit ? 'bg-orange-500' :
              'bg-green-500'
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Warning indicator */}
        {isNearLimit && !isAtLimit && (
          <div className="absolute -right-1 top-1/2 -translate-y-1/2">
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </div>
        )}

        {/* At limit indicator */}
        {isAtLimit && (
          <div className="flex items-center gap-1 mt-1 text-xs text-red-600">
            <AlertTriangle className="w-3 h-3" />
            Limit reached - contact support to increase
          </div>
        )}
      </div>

      {/* Percentage display */}
      <div className="text-xs text-gray-500 mt-1">
        {percentage.toFixed(1)}% used
      </div>
    </div>
  );
}

// API hook
function useTenantLimits() {
  const { currentTenant } = useAuth();

  return useQuery({
    queryKey: ['tenant-limits', currentTenant?.id],
    queryFn: async () => {
      const response = await fetch('/api/v1/me/limits', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch limits');
      }

      const data = await response.json();

      // Calculate if approaching any limits
      const hasWarnings = Object.entries(data.usage).some(([key, value]) => {
        const limitKey = 'max_' + key.replace('_count', 's');
        const max = data.quotas[limitKey];
        return max && (value / max) > 0.8;
      });

      return { ...data, hasWarnings };
    },
    enabled: !!currentTenant && currentTenant.id !== 'platform',
    refetchInterval: 300000 // Refresh every 5 minutes
  });
}
```

### API Integration
```javascript
GET /api/v1/me/limits
Response: {
  tenant_id: "uuid",
  tenant_name: "Acme Corp",
  rate_limits: {
    requests_per_minute: 100,
    reservations_per_minute: 10
  },
  quotas: {
    max_spaces: 500,
    max_devices: 1000,
    max_sites: 10,
    max_users: 50
  },
  usage: {
    spaces_count: 42,
    sensor_devices_count: 38,
    display_devices_count: 40,
    total_devices: 78,
    sites_count: 2,
    users_count: 5
  }
}
```

### Usage
```javascript
// In dashboard sidebar or settings page
function Dashboard() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <div className="lg:col-span-3">
        <MainDashboardContent />
      </div>

      <div className="lg:col-span-1">
        <TenantLimitsWidget />
      </div>
    </div>
  );
}
```

---

## Role-Based Navigation Hook

**File:** `frontend/src/hooks/useSimplifiedNav.js`

### Purpose
Dynamically generates navigation items based on user role and current tenant context.

### Implementation

```javascript
// frontend/src/hooks/useSimplifiedNav.js

import { useMemo } from 'react';
import {
  Home, Building, Building2, Wifi, Settings,
  BarChart3, Users, Shield, Calendar, Car
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { PLATFORM_TENANT_ID } from '../config/featureFlags';

export function useSimplifiedNav() {
  const { user, currentTenant } = useAuth();

  const navItems = useMemo(() => {
    const baseItems = [
      { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/dashboard' }
    ];

    // Platform admin in platform mode - system-wide view
    if (user?.is_platform_admin && currentTenant?.id === PLATFORM_TENANT_ID) {
      return [
        ...baseItems,
        {
          id: 'tenants',
          label: 'All Tenants',
          icon: Building,
          path: '/platform/tenants',
          badge: null
        },
        {
          id: 'device-pool',
          label: 'Device Pool',
          icon: Wifi,
          path: '/platform/devices',
          badge: null
        },
        {
          id: 'audit',
          label: 'Audit Log',
          icon: Shield,
          path: '/platform/audit',
          badge: null
        },
        {
          id: 'settings',
          label: 'Platform Settings',
          icon: Settings,
          path: '/platform/settings',
          badge: null
        }
      ];
    }

    // Platform admin viewing specific tenant - show tenant admin view
    // OR Tenant Owner/Admin - full access
    if (user?.role === 'owner' || user?.role === 'admin' || user?.is_platform_admin) {
      return [
        ...baseItems,
        {
          id: 'sites',
          label: 'Sites',
          icon: Building2,
          path: '/sites',
          badge: null
        },
        {
          id: 'spaces',
          label: 'Parking Spaces',
          icon: Car,
          path: '/spaces',
          badge: null
        },
        {
          id: 'devices',
          label: 'Devices',
          icon: Wifi,
          path: '/devices',
          badge: null
        },
        {
          id: 'reservations',
          label: 'Reservations',
          icon: Calendar,
          path: '/reservations',
          badge: null
        },
        {
          id: 'analytics',
          label: 'Analytics',
          icon: BarChart3,
          path: '/analytics',
          badge: null
        },
        {
          id: 'team',
          label: 'Team',
          icon: Users,
          path: '/team',
          badge: null
        },
        {
          id: 'settings',
          label: 'Settings',
          icon: Settings,
          path: '/settings',
          badge: null
        }
      ];
    }

    // Operator - can manage spaces and reservations
    if (user?.role === 'operator') {
      return [
        ...baseItems,
        {
          id: 'spaces',
          label: 'Parking Spaces',
          icon: Car,
          path: '/spaces',
          badge: null
        },
        {
          id: 'reservations',
          label: 'Reservations',
          icon: Calendar,
          path: '/reservations',
          badge: null
        },
        {
          id: 'devices',
          label: 'Devices',
          icon: Wifi,
          path: '/devices',
          badge: null,
          disabled: false // Operators can view devices
        }
      ];
    }

    // Viewer - read-only access
    return [
      ...baseItems,
      {
        id: 'spaces',
        label: 'Parking Spaces',
        icon: Car,
        path: '/spaces',
        badge: null,
        disabled: false
      },
      {
        id: 'reservations',
        label: 'Reservations',
        icon: Calendar,
        path: '/reservations',
        badge: null,
        disabled: false
      }
    ];
  }, [user, currentTenant]);

  return navItems;
}

// Helper hook to check permissions
export function useHasPermission(action) {
  const { user, currentTenant } = useAuth();

  const permissions = useMemo(() => ({
    // Platform admin can do everything
    '*': user?.is_platform_admin,

    // Owner permissions
    'tenant.delete': user?.role === 'owner',
    'team.manage': ['owner', 'admin'].includes(user?.role),
    'apikeys.create': ['owner', 'admin'].includes(user?.role),

    // Admin permissions
    'spaces.create': ['owner', 'admin', 'operator'].includes(user?.role),
    'spaces.edit': ['owner', 'admin', 'operator'].includes(user?.role),
    'devices.assign': ['owner', 'admin'].includes(user?.role),

    // Operator permissions
    'reservations.create': ['owner', 'admin', 'operator'].includes(user?.role),
    'reservations.cancel': ['owner', 'admin', 'operator'].includes(user?.role),

    // Viewer permissions (read-only)
    'spaces.view': true,
    'reservations.view': true,
    'devices.view': true
  }), [user]);

  return permissions['*'] || permissions[action] || false;
}
```

### Usage
```javascript
// In sidebar component
import { useSimplifiedNav, useHasPermission } from '../hooks/useSimplifiedNav';

function Sidebar() {
  const navItems = useSimplifiedNav();
  const canManageTeam = useHasPermission('team.manage');

  return (
    <nav>
      {navItems.map(item => (
        <NavItem
          key={item.id}
          {...item}
          disabled={item.disabled}
        />
      ))}
    </nav>
  );
}
```

---

## ApiKeysManagement Component

**File:** `frontend/src/pages/Settings/ApiKeys.jsx`

### Purpose
Self-service API key management for tenant admins.

### Implementation

```javascript
// frontend/src/pages/Settings/ApiKeys.jsx

import React, { useState } from 'react';
import { Plus, Copy, Eye, EyeOff, Trash2, AlertCircle } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../contexts/AuthContext';

export function ApiKeysManagement() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);
  const queryClient = useQueryClient();
  const { currentTenant } = useAuth();

  const { data: apiKeys, isLoading } = useApiKeys();
  const revokeKey = useRevokeKey();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">API Keys</h2>
          <p className="mt-1 text-sm text-gray-500">
            Manage API keys for programmatic access to {currentTenant?.name}
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create API Key
        </button>
      </div>

      {/* Warning */}
      <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
        <div className="flex">
          <AlertCircle className="w-5 h-5 text-yellow-400" />
          <div className="ml-3">
            <p className="text-sm text-yellow-700">
              API keys are shown only once upon creation. Store them securely.
            </p>
          </div>
        </div>
      </div>

      {/* Keys Table */}
      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="h-16 bg-gray-200 rounded"></div>
          <div className="h-16 bg-gray-200 rounded"></div>
        </div>
      ) : apiKeys?.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500">No API keys created yet</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 text-blue-600 hover:underline"
          >
            Create your first API key
          </button>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Scopes
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Used
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Expires
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {apiKeys?.map(key => (
                <tr key={key.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {key.name}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {key.scopes.map(scope => (
                        <span
                          key={scope}
                          className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded"
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {key.last_used_at ? formatRelativeTime(key.last_used_at) : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(key.expires_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => {
                        if (confirm('Revoke this API key? This action cannot be undone.')) {
                          revokeKey.mutate(key.id);
                        }
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateApiKeyModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={(newKey) => {
            setCopiedKey(newKey);
            setShowCreateModal(false);
            queryClient.invalidateQueries(['api-keys']);
          }}
        />
      )}

      {/* Success Modal showing new key */}
      {copiedKey && (
        <NewKeyModal
          apiKey={copiedKey}
          onClose={() => setCopiedKey(null)}
        />
      )}
    </div>
  );
}

// API hooks
function useApiKeys() {
  const { currentTenant } = useAuth();

  return useQuery({
    queryKey: ['api-keys', currentTenant?.id],
    queryFn: async () => {
      const response = await fetch(`/api/v1/tenants/${currentTenant.id}/api-keys`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (!response.ok) throw new Error('Failed to fetch API keys');

      const data = await response.json();
      return data.api_keys;
    },
    enabled: !!currentTenant && currentTenant.id !== 'platform'
  });
}

function useRevokeKey() {
  const queryClient = useQueryClient();
  const { currentTenant } = useAuth();

  return useMutation({
    mutationFn: async (keyId) => {
      const response = await fetch(`/api/v1/tenants/${currentTenant.id}/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (!response.ok) throw new Error('Failed to revoke key');

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['api-keys']);
    }
  });
}

// Helper components omitted for brevity (CreateApiKeyModal, NewKeyModal)
```

### API Integration
```javascript
GET /api/v1/tenants/{tenant_id}/api-keys
POST /api/v1/tenants/{tenant_id}/api-keys
DELETE /api/v1/tenants/{tenant_id}/api-keys/{key_id}
```

---

## Installation Instructions

### 1. Add Components to Project

```bash
# Create directory structure
mkdir -p frontend/src/components/PlatformAdmin
mkdir -p frontend/src/components/Tenant
mkdir -p frontend/src/components/Devices
mkdir -p frontend/src/hooks
mkdir -p frontend/src/pages/Settings

# Copy component files from this documentation
# (Each component code block above should be saved to its respective file)
```

### 2. Install Required Dependencies

```bash
cd frontend
npm install lucide-react @tanstack/react-query
```

### 3. Add to Main Layout

```javascript
// frontend/src/layouts/MainLayout.jsx
import { AdminModeIndicator } from '../components/PlatformAdmin/AdminModeIndicator';
import { PlatformAdminQuickActions } from '../components/PlatformAdmin/QuickActions';

export function MainLayout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <AdminModeIndicator />

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <PlatformAdminQuickActions />
        {children}
      </main>
    </div>
  );
}
```

### 4. Add to Routes

```javascript
// frontend/src/App.jsx
import { ApiKeysManagement } from './pages/Settings/ApiKeys';

function App() {
  return (
    <Routes>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/settings/api-keys" element={<ApiKeysManagement />} />
      {/* ... other routes */}
    </Routes>
  );
}
```

### 5. Add New API Endpoint (Backend)

```python
# backend/src/routers/devices.py
@router.get("/devices/{deveui}/assignments", summary="Get Device Assignment History")
async def get_device_assignments(
    deveui: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """Get complete assignment history for a device"""
    assignments = await db.fetch("""
        SELECT
            da.id,
            da.device_eui,
            da.space_id,
            s.code as space_code,
            s.name as space_name,
            da.assigned_at,
            da.unassigned_at,
            da.assigned_by,
            u.name as assigned_by_name,
            da.notes
        FROM device_assignments da
        LEFT JOIN spaces s ON da.space_id = s.id
        LEFT JOIN users u ON da.assigned_by = u.id
        WHERE da.device_eui = $1
        AND s.tenant_id = $2
        ORDER BY da.assigned_at DESC
    """, deveui.upper(), tenant.tenant_id)

    return [dict(row) for row in assignments]
```

---

## Integration Guide

### Quick Start Integration

All components have been implemented and are ready for integration into the Device Manager application. Here's how to add them to your application:

#### 1. Update AuthContext to Include Platform Admin Flag

The existing AuthContext needs to be enhanced to include the `is_platform_admin` flag from the login response:

```javascript
// frontend/device-manager/src/services/authService.js

// Update the login method to store is_platform_admin
login: async (email, password) => {
  const response = await apiClient.post('/api/v1/auth/login', { email, password });
  const { access_token, user, tenants, is_platform_admin } = response.data;

  // Store enhanced user object
  localStorage.setItem('user', JSON.stringify({ ...user, is_platform_admin }));
  localStorage.setItem('token', access_token);

  return response.data;
}
```

#### 2. Add Components to Main Layout

```javascript
// frontend/device-manager/src/App.jsx or MainLayout component

import { AdminModeIndicator, PlatformAdminQuickActions } from './components/PlatformAdmin';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Add AdminModeIndicator at top level */}
      <AdminModeIndicator />

      <Navbar />

      <main className="container mx-auto px-4 py-6">
        {/* Add PlatformAdminQuickActions to dashboard */}
        <PlatformAdminQuickActions />

        {/* Your existing routes/content */}
        <Routes>
          {/* ... */}
        </Routes>
      </main>
    </div>
  );
}
```

#### 3. Add TenantLimitsWidget to Dashboard

```javascript
// frontend/device-manager/src/components/Dashboard.jsx

import { TenantLimitsWidget } from './PlatformAdmin';

function Dashboard() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        {/* Your main dashboard content */}
      </div>

      <div className="lg:col-span-1">
        {/* Add resource limits widget to sidebar */}
        <TenantLimitsWidget />
      </div>
    </div>
  );
}
```

#### 4. Add DeviceAssignmentHistory to Device Details Page

```javascript
// frontend/device-manager/src/pages/DeviceDetailsPage.jsx

import { DeviceAssignmentHistory } from '../components/PlatformAdmin';

function DeviceDetailsPage({ deveui }) {
  return (
    <div className="space-y-6">
      {/* Device info */}

      {/* Assignment history */}
      <DeviceAssignmentHistory deveui={deveui} />
    </div>
  );
}
```

#### 5. Create API Keys Page

```javascript
// frontend/device-manager/src/pages/ApiKeysPage.jsx

import { ApiKeysManagement } from '../components/PlatformAdmin';

export function ApiKeysPage() {
  return (
    <div className="max-w-6xl mx-auto">
      <ApiKeysManagement />
    </div>
  );
}

// Add to routes
// <Route path="/api-keys" element={<ApiKeysPage />} />
```

#### 6. Update Navigation with Role-Based Menu

```javascript
// frontend/device-manager/src/components/NavBar.jsx

import { useSimplifiedNav } from '../hooks/useSimplifiedNav';

function NavBar() {
  const navItems = useSimplifiedNav();

  return (
    <nav className="bg-white shadow">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex space-x-4">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className="flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium"
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                  {item.badge && (
                    <span className="badge">{item.badge}</span>
                  )}
                </NavLink>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
```

### Backend Integration Required

The following backend endpoint needs to be added to support DeviceAssignmentHistory:

```python
# backend/src/routers/devices.py

@router.get("/devices/{deveui}/assignments",
    response_model=List[DeviceAssignment],
    summary="Get Device Assignment History")
async def get_device_assignments(
    deveui: str,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """
    Get complete assignment history for a device

    Returns chronological list of all assignments/unassignments
    Platform admins can see assignments across all tenants
    """
    # For platform admins, show all assignments
    if tenant.source == 'platform_admin':
        query = """
            SELECT
                'assigned' as action,
                s.sensor_eui as device_eui,
                sp.created_at as timestamp,
                t.name as tenant_name,
                si.name as site_name,
                sp.code as space_code,
                sp.name as space_name,
                'system' as performed_by,
                NULL as notes
            FROM spaces sp
            INNER JOIN sites si ON sp.site_id = si.id
            INNER JOIN tenants t ON si.tenant_id = t.id
            WHERE sp.sensor_eui = $1
            ORDER BY sp.created_at DESC
        """
        assignments = await db.fetch(query, deveui.upper())
    else:
        # For regular users, only show assignments in their tenant
        query = """
            SELECT
                'assigned' as action,
                s.sensor_eui as device_eui,
                sp.created_at as timestamp,
                t.name as tenant_name,
                si.name as site_name,
                sp.code as space_code,
                sp.name as space_name,
                'system' as performed_by,
                NULL as notes
            FROM spaces sp
            INNER JOIN sites si ON sp.site_id = si.id
            INNER JOIN tenants t ON si.tenant_id = t.id
            WHERE sp.sensor_eui = $1 AND t.id = $2
            ORDER BY sp.created_at DESC
        """
        assignments = await db.fetch(query, deveui.upper(), tenant.tenant_id)

    return [dict(row) for row in assignments]
```

### Testing Checklist

- [ ] AdminModeIndicator appears for platform admins only
- [ ] PlatformAdminQuickActions shows orphaned device count
- [ ] DeviceAssignmentHistory displays complete timeline
- [ ] TenantLimitsWidget shows accurate resource usage
- [ ] Navigation menu changes based on user role
- [ ] API Keys can be created and revoked
- [ ] Tenant switching works correctly
- [ ] All components handle loading and error states

### File Locations Summary

```
frontend/device-manager/
├── src/
│   ├── components/
│   │   └── PlatformAdmin/
│   │       ├── AdminModeIndicator.jsx          ✅ Implemented
│   │       ├── PlatformAdminQuickActions.jsx   ✅ Implemented
│   │       ├── DeviceAssignmentHistory.jsx     ✅ Implemented
│   │       ├── TenantLimitsWidget.jsx          ✅ Implemented
│   │       ├── ApiKeysManagement.jsx           ✅ Implemented
│   │       └── index.js                        ✅ Created
│   ├── hooks/
│   │   └── useSimplifiedNav.js                 ✅ Implemented
│   ├── services/
│   │   ├── platformAdminService.js             ✅ Implemented
│   │   └── apiKeysService.js                   ✅ Implemented
│   └── tailwind.config.js                      ✅ Updated (animations)
```

---

**End of UI Components Implementation Guide**
