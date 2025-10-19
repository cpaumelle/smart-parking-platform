// src/utils/gatewayConfigStatus.js
// Configuration status utilities to match devices page functionality

export const GATEWAY_CONFIG_STATUS = {
  CONFIGURED: 'configured',
  PARTIAL: 'partial', 
  ORPHANED: 'orphaned'
};

export const GATEWAY_CONFIG_FILTERS = {
  ALL: 'all',
  CONFIGURED: 'configured',
  PARTIAL: 'partial',
  ORPHANED: 'orphaned',
  ARCHIVED: 'archived'
};

export const GATEWAY_CONFIG_FILTER_LABELS = {
  [GATEWAY_CONFIG_FILTERS.ALL]: 'All Gateways',
  [GATEWAY_CONFIG_FILTERS.CONFIGURED]: 'Configured',
  [GATEWAY_CONFIG_FILTERS.PARTIAL]: 'Partially Configured', 
  [GATEWAY_CONFIG_FILTERS.ORPHANED]: 'Needs Configuration',
  [GATEWAY_CONFIG_FILTERS.ARCHIVED]: 'Archived'
};

/**
 * Determine gateway configuration status based on real API data and backend logic
 * Based on actual patterns: "Orphan Gateway" = auto-created, needs configuration
 */
export const getGatewayConfigStatus = (gateway) => {
  // Archived gateways are handled separately
  if (gateway.archived_at) {
    return null;
  }

  // Check if gateway has essential configuration
  const hasCustomName = gateway.gateway_name && 
                        gateway.gateway_name !== 'Orphan Gateway' && 
                        gateway.gateway_name.trim() !== '';
  const hasLocation = gateway.location_id || gateway.site_id;

  // Fully configured: has custom name AND location assignment
  if (hasCustomName && hasLocation) {
    return GATEWAY_CONFIG_STATUS.CONFIGURED;
  }

  // Partial: has custom name but no location assignment
  if (hasCustomName && !hasLocation) {
    return GATEWAY_CONFIG_STATUS.PARTIAL;
  }

  // Orphaned: auto-created with default name or no name, needs human configuration
  return GATEWAY_CONFIG_STATUS.ORPHANED;
};

/**
 * Get configuration status badge properties
 */
export const getGatewayConfigBadge = (gateway) => {
  if (gateway.archived_at) {
    return {
      className: 'px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600',
      text: 'ARCHIVED'
    };
  }

  const configStatus = getGatewayConfigStatus(gateway);

  switch (configStatus) {
    case GATEWAY_CONFIG_STATUS.CONFIGURED:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800',
        text: 'CONFIGURED'
      };
    case GATEWAY_CONFIG_STATUS.PARTIAL:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800',
        text: 'PARTIAL'
      };
    case GATEWAY_CONFIG_STATUS.ORPHANED:
    default:
      return {
        className: 'px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800',
        text: 'NEEDS CONFIG'
      };
  }
};

/**
 * Get required action for gateway (similar to devices page)
 * Based on real configuration patterns
 */
export const getRequiredGatewayAction = (gateway) => {
  if (gateway.archived_at) {
    return 'Archived';
  }

  const hasCustomName = gateway.gateway_name && 
                        gateway.gateway_name !== 'Orphan Gateway' && 
                        gateway.gateway_name.trim() !== '';
  const hasLocation = gateway.location_id || gateway.site_id;

  if (!hasCustomName) {
    return 'Set gateway name';
  }
  
  if (!hasLocation) {
    return 'Assign location';
  }

  return 'Fully configured';
};

/**
 * Check if gateway needs configuration
 */
export const gatewayNeedsConfiguration = (gateway) => {
  if (gateway.archived_at) return false;
  
  const configStatus = getGatewayConfigStatus(gateway);
  return configStatus !== GATEWAY_CONFIG_STATUS.CONFIGURED;
};
