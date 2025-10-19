// src/services/chirpstackService.js
// ChirpStack Device Manager API Service
// Version: 3.0.0 - 2025-10-13
// Consolidated: Now uses apiClient and Transform service (/v1/chirpstack/*)

import apiClient from './apiClient.js';

export const chirpstackService = {
  // ==================== Device Operations ====================

  // List devices with filters and pagination
  async getDevices(params = {}) {
    try {
      console.log('🔍 Fetching ChirpStack devices with params:', params);
      const response = await apiClient.get('/v1/chirpstack/devices', { params });
      console.log(`✅ Retrieved ${response.data?.total || 0} devices`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch ChirpStack devices:', error.userMessage);
      throw error;
    }
  },

  // Get single device by DevEUI
  async getDevice(devEui) {
    try {
      console.log(`🔍 Fetching ChirpStack device: ${devEui}`);
      const response = await apiClient.get(`/v1/chirpstack/devices/${devEui}`);
      console.log('✅ Retrieved device:', response.data?.name || devEui);
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to fetch device ${devEui}:`, error.userMessage);
      throw error;
    }
  },

  // Create new device
  async createDevice(deviceData) {
    try {
      console.log('📝 Creating ChirpStack device:', deviceData);
      const response = await apiClient.post('/v1/chirpstack/devices', deviceData);
      console.log('✅ Device created successfully:', response.data?.dev_eui);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to create device:', error.userMessage);
      throw error;
    }
  },

  // Update device
  async updateDevice(devEui, updateData) {
    try {
      console.log(`📝 Updating ChirpStack device ${devEui}:`, updateData);
      const response = await apiClient.put(`/v1/chirpstack/devices/${devEui}`, updateData);
      console.log('✅ Device updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update device ${devEui}:`, error.userMessage);
      throw error;
    }
  },

  // Delete device
  async deleteDevice(devEui) {
    try {
      console.log(`🗑️ Deleting ChirpStack device: ${devEui}`);
      await apiClient.delete(`/v1/chirpstack/devices/${devEui}`);
      console.log('✅ Device deleted successfully');
      return { success: true };
    } catch (error) {
      console.error(`❌ Failed to delete device ${devEui}:`, error.userMessage);
      throw error;
    }
  },

  // ==================== Device Keys Operations ====================

  // Get device OTAA keys
  async getDeviceKeys(devEui) {
    try {
      console.log(`🔑 Fetching keys for device: ${devEui}`);
      const response = await apiClient.get(`/v1/chirpstack/devices/${devEui}/keys`);
      console.log('✅ Retrieved device keys');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to fetch keys for ${devEui}:`, error.userMessage);
      throw error;
    }
  },

  // Update device OTAA keys
  async updateDeviceKeys(devEui, keysData) {
    try {
      console.log(`🔑 Updating keys for device: ${devEui}`);
      const response = await apiClient.put(`/v1/chirpstack/devices/${devEui}/keys`, keysData);
      console.log('✅ Device keys updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update keys for ${devEui}:`, error.userMessage);
      throw error;
    }
  },

  // ==================== Bulk Operations ====================

  // Bulk delete devices
  async bulkDeleteDevices(devEuis) {
    try {
      console.log(`🗑️ Bulk deleting ${devEuis.length} devices`);
      const response = await apiClient.delete('/v1/chirpstack/devices/bulk', {
        data: { dev_euis: devEuis }
      });
      console.log('✅ Bulk delete completed:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Bulk delete failed:', error.userMessage);
      throw error;
    }
  },

  // ==================== Reference Data ====================

  // Get applications list
  async getApplications(tenantId = null) {
    try {
      console.log('🔍 Fetching applications');
      const params = tenantId ? { tenant_id: tenantId } : {};
      const response = await apiClient.get('/v1/chirpstack/applications', { params });
      console.log(`✅ Retrieved ${response.data?.length || 0} applications`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch applications:', error.userMessage);
      throw error;
    }
  },

  // Get device profiles list
  async getDeviceProfiles(params = {}) {
    try {
      console.log('🔍 Fetching device profiles');
      const response = await apiClient.get('/v1/chirpstack/device-profiles', { params });
      console.log(`✅ Retrieved ${response.data?.length || 0} device profiles`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch device profiles:', error.userMessage);
      throw error;
    }
  }
};

export default chirpstackService;
