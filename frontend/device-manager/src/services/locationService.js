// src/services/locationService.js
// Updated to use multi-tenant Parking API v5.3 (spaces instead of separate locations)
// Note: In v5.3, there is no separate "locations" hierarchy - just parking spaces with site grouping
import apiClient from './apiClient.js';

export const locationService = {
  // GET /api/v1/spaces/ - In v5.3, spaces ARE the locations
  // Spaces have site_id, site_name, code, name, etc.
  async getLocations(params = {}) {
    try {
      console.log('🔍 Fetching parking spaces (displayed as locations) with params:', params);
      const response = await apiClient.get('/api/v1/spaces/', { params });
      const spaces = response.data?.spaces || response.data || [];
      console.log(`✅ Retrieved ${spaces.length} parking spaces`);
      // Return spaces as "locations" for UI compatibility
      return spaces;
    } catch (error) {
      console.error('❌ Failed to fetch parking spaces:', error.userMessage);
      throw error;
    }
  },

  // POST /api/v1/spaces/ - Create a parking space (displayed as location)
  async createLocation(data) {
    try {
      console.log('📝 Creating parking space:', data);
      const response = await apiClient.post('/api/v1/spaces/', data);
      console.log('✅ Parking space created successfully');
      return response.data;
    } catch (error) {
      console.error('❌ Failed to create parking space:', error.userMessage);
      throw error;
    }
  },

  // PATCH /api/v1/spaces/{id} - Update a parking space
  async updateLocation(locationId, data) {
    try {
      console.log(`📝 Updating parking space ${locationId}:`, data);
      const response = await apiClient.patch(`/api/v1/spaces/${locationId}`, data);
      console.log('✅ Parking space updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update parking space ${locationId}:`, error.userMessage);
      throw error;
    }
  },

  // DELETE /api/v1/spaces/{id} - Soft delete a parking space
  async archiveLocation(locationId, confirm = true) {
    try {
      console.log(`🗑️ Archiving parking space: ${locationId}`);
      const response = await apiClient.delete(`/api/v1/spaces/${locationId}`, { params: { force: false } });
      console.log('✅ Parking space archived successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to archive parking space ${locationId}:`, error.userMessage);
      throw error;
    }
  }
};
