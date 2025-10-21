// src/utils/constants.js
export const APP_CONFIG = {
  name: 'SenseMy IoT Platform',
  version: '1.0.0',
  description: 'Device and Location Management System'
};

export const NAVIGATION_ITEMS = [
  {
    id: 'dashboard',
    label: '📊 Dashboard',
    path: '/',
    description: 'Platform overview and metrics'
  },
  {
    id: 'devices', 
    label: '📱 Devices',
    path: '/devices',
    description: 'Device management and assignment'
  },
  {
    id: 'locations',
    label: '📍 Locations', 
    path: '/locations',
    description: 'Location hierarchy management'
  },
  {
    id: 'gateways',
    label: '📡 Gateways',
    path: '/gateways', 
    description: 'Gateway status and management'
  }
];

export const DEVICE_FILTERS = {
  ALL: 'all',
  UNASSIGNED: 'unassigned',     // No site assigned (Build 18+)
  ASSIGNED: 'assigned',          // Site assigned (Build 18+)
  ARCHIVED: 'archived',
  RECENTLY_ACTIVE: 'recently_active'
};

export const FILTER_LABELS = {
  [DEVICE_FILTERS.ALL]: 'All Devices',
  [DEVICE_FILTERS.UNASSIGNED]: 'Unassigned',
  [DEVICE_FILTERS.ASSIGNED]: 'Assigned to Site',
  [DEVICE_FILTERS.ARCHIVED]: 'Archived',
  [DEVICE_FILTERS.RECENTLY_ACTIVE]: 'Recently Active'
};
// Location Management Constants
export const LOCATION_TYPES = {
  SITE: 'site',
  FLOOR: 'floor',
  ROOM: 'room',
  ZONE: 'zone'
};

export const LOCATION_FILTERS = {
  ALL: 'all',
  SITES: 'sites',
  FLOORS: 'floors',
  ROOMS: 'rooms',
  ZONES: 'zones',
  ARCHIVED: 'archived'
};

export const LOCATION_FILTER_LABELS = {
  [LOCATION_FILTERS.ALL]: 'All Locations',
  [LOCATION_FILTERS.SITES]: 'Sites Only',
  [LOCATION_FILTERS.FLOORS]: 'Floors Only',
  [LOCATION_FILTERS.ROOMS]: 'Rooms Only',
  [LOCATION_FILTERS.ZONES]: 'Zones Only',
  [LOCATION_FILTERS.ARCHIVED]: 'Archived'
};
