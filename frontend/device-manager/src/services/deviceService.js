// src/services/deviceService.js
import apiClient from './apiClient.js';

export const deviceService = {
  // GET /api/v1/devices
  async getDevices(params = {}) {
    try {
      console.log('🔍 Fetching devices with params:', params);
      const response = await apiClient.get('/api/v1/devices', { params });
      console.log(`✅ Retrieved ${response.data?.length || 0} devices`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch devices:', error.userMessage);
      throw error;
    }
  },

  // GET /api/v1/devices/{deveui}
  async getDevice(deveui) {
    try {
      console.log(`🔍 Fetching device: ${deveui}`);
      const response = await apiClient.get(`/api/v1/devices/${deveui}`);
      console.log('✅ Retrieved device:', response.data?.name || response.data?.deveui);
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to fetch device ${deveui}:`, error.userMessage);
      throw error;
    }
  },

  // PUT /api/v1/devices/{deveui}
  async updateDevice(deveui, data) {
    try {
      console.log(`📝 Updating device ${deveui}:`, data);
      const response = await apiClient.put(`/api/v1/devices/${deveui}`, data);
      console.log('✅ Device updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update device ${deveui}:`, error.userMessage);
      throw error;
    }
  },

  // REMOVED - POST /api/v1/devices not supported in v5.3 API
  // Devices are auto-created when assigned to spaces via:
  // - POST /api/v1/spaces/{space_id}/assign-sensor?sensor_eui=...
  // - POST /api/v1/spaces/{space_id}/assign-display?display_eui=...
  // async createDevice(data) { ... }

  // PATCH /api/v1/devices/{deveui}/archive
  async archiveDevice(deveui, confirm = true) {
    try {
      console.log(`🗑️ Archiving device: ${deveui}`);
      const response = await apiClient.patch(`/api/v1/devices/${deveui}/archive?confirm=${confirm}`);
      console.log('✅ Device archived successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to archive device ${deveui}:`, error.userMessage);
      throw error;
    }
  },

  // GET /api/v1/devices/full-metadata
  async getDeviceMetadata() {
    try {
      console.log('🔍 Fetching device metadata');
      const response = await apiClient.get('/api/v1/devices/full-metadata');
      console.log(`✅ Retrieved metadata for ${response.data?.length || 0} devices`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch device metadata:', error.userMessage);
      throw error;
    }
  }
};
