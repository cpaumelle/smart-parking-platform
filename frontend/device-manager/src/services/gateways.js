/**
 * services/gateways.js
 * Version: 1.0.1
 * Last Updated: 2025-08-08 11:18 UTC+2
 * Changelog:
 * - Switch to axios client (services/apiClient.js) instead of raw config object
 */

import api from './apiClient.js'; // preconfigured axios instance

export const listGateways = (opts = {}) =>
  api.get('/api/v1/gateways', { params: { includeArchived: !!opts.includeArchived } })
     .then(r => r.data);

export const getGateway = (gw_eui) =>
  api.get(`/api/v1/gateways/${gw_eui}`).then(r => r.data);

export const createGateway = (payload) =>
  api.post('/api/v1/gateways/', payload).then(r => r.data);

export const updateGateway = (gw_eui, payload) =>
  api.put(`/api/v1/gateways/${gw_eui}`, payload).then(r => r.data);

export const archiveGateway = (gw_eui) =>
  api.patch(`/api/v1/gateways/${gw_eui}/archive`, {}, { params: { confirm: true } })
     .then(r => r.data);
