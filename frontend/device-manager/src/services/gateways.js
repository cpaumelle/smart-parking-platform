/**
 * services/gateways.js
 * Version: 3.0.0 - v5.3 Multi-Tenant API with ChirpStack Update
 * Last Updated: 2025-10-21
 * Changelog:
 * - v3.0.0: Added updateGateway for description field (site assignment via ChirpStack)
 * - v2.0.0: Updated for v5.3 multi-tenant Parking API
 * - Removed create/archive operations (gateways are auto-discovered)
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

// Update gateway description and/or tags in ChirpStack
// Description field is ideal for site assignment
export const updateGateway = (gw_eui, payload) =>
  api.patch(`/api/v1/gateways/${gw_eui}`, payload).then(r => r.data);

// ============================================================
// REMOVED - Gateways cannot be created or archived via API
// Gateways are auto-discovered via ChirpStack integration
// ============================================================
// export const createGateway = (payload) => ...
// export const archiveGateway = (gw_eui) => ...
