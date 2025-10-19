// src/utils/gatewayConstants.js
// Based on real API data and database schema

export const GATEWAY_STATUS = {
  ONLINE: 'online',
  OFFLINE: 'offline',
  NULL: null
};

export const GATEWAY_FILTERS = {
  ALL: 'all',
  ONLINE: 'online',
  OFFLINE: 'offline',
  UNSET: 'unset',
  ARCHIVED: 'archived'
};

export const GATEWAY_FILTER_LABELS = {
  [GATEWAY_FILTERS.ALL]: 'All Gateways',
  [GATEWAY_FILTERS.ONLINE]: 'Online',
  [GATEWAY_FILTERS.OFFLINE]: 'Offline', 
  [GATEWAY_FILTERS.UNSET]: 'Status Not Set',
  [GATEWAY_FILTERS.ARCHIVED]: 'Archived'
};

export const GATEWAY_STATUS_OPTIONS = [
  { value: GATEWAY_STATUS.OFFLINE, label: 'Offline' },
  { value: GATEWAY_STATUS.ONLINE, label: 'Online' },
  { value: GATEWAY_STATUS.NULL, label: 'Not Set' }
];

// Real database fields based on API response
export const GATEWAY_FIELDS = {
  GW_EUI: 'gw_eui',
  GATEWAY_NAME: 'gateway_name',
  SITE_ID: 'site_id',
  LOCATION_ID: 'location_id',
  STATUS: 'status',
  LAST_SEEN_AT: 'last_seen_at',
  CREATED_AT: 'created_at',
  UPDATED_AT: 'updated_at',
  ARCHIVED_AT: 'archived_at'
};

// Status badge configuration
export const getGatewayStatusBadge = (status, isArchived = false) => {
  if (isArchived) {
    return {
      className: 'px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600',
      text: 'ARCHIVED'
    };
  }

  switch (status) {
    case GATEWAY_STATUS.ONLINE:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800',
        text: 'ONLINE'
      };
    case GATEWAY_STATUS.OFFLINE:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800',
        text: 'OFFLINE'
      };
    case GATEWAY_STATUS.NULL:
    default:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800',
        text: 'NOT SET'
      };
  }
};

// Gateway validation utilities
export const validateGatewayEui = (eui) => {
  if (!eui || !eui.trim()) {
    return { valid: false, message: 'Gateway EUI is required' };
  }

  // Based on real data, EUIs can be:
  // - 16 hex chars: "7076FF00640503CA"
  // - Various formats: "NETMORE-30833", "CP-Dinard-7076FF006404010B"
  // So we'll be more flexible than strict hex validation
  
  const trimmed = eui.trim();
  
  if (trimmed.length < 3) {
    return { valid: false, message: 'Gateway EUI is too short' };
  }
  
  if (trimmed.length > 50) {
    return { valid: false, message: 'Gateway EUI is too long' };
  }

  return { valid: true };
};

export const validateGatewayName = (name) => {
  if (!name || !name.trim()) {
    return { valid: false, message: 'Gateway name is required' };
  }

  if (name.trim().length > 255) {
    return { valid: false, message: 'Gateway name must be 255 characters or less' };
  }

  return { valid: true };
};
