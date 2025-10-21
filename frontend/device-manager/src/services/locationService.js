// src/services/locationService.js
// Updated to use multi-tenant Parking API v5.3 (sites instead of locations)
import apiClient from './apiClient.js';

export const locationService = {
  // GET /api/v1/sites (was /v1/locations)
  async getLocations(params = {}) {
    try {
      console.log('🔍 Fetching sites with params:', params);
      const response = await apiClient.get('/api/v1/sites', { params });
      console.log(`✅ Retrieved ${response.data?.length || 0} sites`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch sites:', error.userMessage);
      throw error;
    }
  },

  // POST /api/v1/sites (was /v1/locations)
  async createLocation(data) {
    try {
      console.log('📝 Creating site:', data);
      const response = await apiClient.post('/api/v1/sites', data);
      console.log('✅ Site created successfully');
      return response.data;
    } catch (error) {
      console.error('❌ Failed to create site:', error.userMessage);
      throw error;
    }
  },

  // PATCH /api/v1/sites/{id} (was PUT /v1/locations/{id})
  async updateLocation(locationId, data) {
    try {
      console.log(`📝 Updating site ${locationId}:`, data);
      const response = await apiClient.patch(`/api/v1/sites/${locationId}`, data);
      console.log('✅ Site updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update site ${locationId}:`, error.userMessage);
      throw error;
    }
  },

  // PATCH /api/v1/sites/{id} with is_active=false (was PUT /v1/locations/{id}/archive)
  async archiveLocation(locationId, confirm = true) {
    try {
      console.log(`🗑️ Archiving site: ${locationId}`);
      const response = await apiClient.patch(`/api/v1/sites/${locationId}`, { is_active: false });
      console.log('✅ Site archived successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to archive site ${locationId}:`, error.userMessage);
      throw error;
    }
  }
};
