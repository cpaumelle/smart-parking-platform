// src/services/locationService.js
import apiClient from './apiClient.js';

export const locationService = {
  // GET /v1/locations
  async getLocations(params = {}) {
    try {
      console.log('🔍 Fetching locations with params:', params);
      const response = await apiClient.get('/v1/locations', { params });
      console.log(`✅ Retrieved ${response.data?.length || 0} locations`);
      return response.data;
    } catch (error) {
      console.error('❌ Failed to fetch locations:', error.userMessage);
      throw error;
    }
  },

  // POST /v1/locations
  async createLocation(data) {
    try {
      console.log('📝 Creating location:', data);
      const response = await apiClient.post('/v1/locations', data);
      console.log('✅ Location created successfully');
      return response.data;
    } catch (error) {
      console.error('❌ Failed to create location:', error.userMessage);
      throw error;
    }
  },

  // PUT /v1/locations/{id}
  async updateLocation(locationId, data) {
    try {
      console.log(`📝 Updating location ${locationId}:`, data);
      const response = await apiClient.put(`/v1/locations/${locationId}`, data);
      console.log('✅ Location updated successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to update location ${locationId}:`, error.userMessage);
      throw error;
    }
  },

  // PUT /v1/locations/{id}/archive
  async archiveLocation(locationId, confirm = true) {
    try {
      console.log(`🗑️ Archiving location: ${locationId}`);
      const response = await apiClient.put(`/v1/locations/${locationId}/archive?confirm=${confirm}`);
      console.log('✅ Location archived successfully');
      return response.data;
    } catch (error) {
      console.error(`❌ Failed to archive location ${locationId}:`, error.userMessage);
      throw error;
    }
  }
};
