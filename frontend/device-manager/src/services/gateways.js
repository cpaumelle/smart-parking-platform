/**
 * services/gateways.js
 * Version: 2.0.0 - v5.3 Multi-Tenant API
 * Last Updated: 2025-10-21
 * Changelog:
 * - Updated for v5.3 multi-tenant Parking API
 * - Removed write operations (gateways are read-only in v5.3)
 * - Added gateway statistics endpoint
 * - Gateways are auto-discovered via ChirpStack integration
 */

import api from './apiClient.js'; // preconfigured axios instance

// List all gateways (read-only)
export const listGateways = (opts = {}) =>
  api.get('/api/v1/gateways', { params: { includeArchived: !!opts.includeArchived } })
     .then(r => r.data);

// Get single gateway (read-only)
export const getGateway = (gw_eui) =>
  api.get(`/api/v1/gateways/${gw_eui}`).then(r => r.data);

// Get gateway statistics summary
export const getGatewayStats = () =>
  api.get('/api/v1/gateways/stats/summary').then(r => r.data);

// ============================================================
// REMOVED - Gateways are read-only in v5.3 Multi-Tenant API
// Gateways are auto-discovered via ChirpStack integration
// ============================================================
// export const createGateway = (payload) => ...
// export const updateGateway = (gw_eui, payload) => ...
// export const archiveGateway = (gw_eui) => ...
