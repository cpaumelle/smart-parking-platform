// src/services/parkingSpacesService.js
import apiClient from './apiClient.js';

export const parkingSpacesService = {
  async getSpaces(params = {}) {
    try {
      console.log('Fetching parking spaces with params:', params);
      const response = await apiClient.get('/api/v1/spaces/', { params });
      const spaces = response.data?.spaces || [];
      console.log('Retrieved ' + spaces.length + ' parking spaces');
      return { spaces, count: spaces.length };
    } catch (error) {
      console.error('Failed to fetch parking spaces:', error.userMessage);
      throw error;
    }
  },

  async getSpace(spaceId) {
    try {
      const response = await apiClient.get('/api/v1/spaces/' + spaceId);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch parking space:', error.userMessage);
      throw error;
    }
  },

  async createSpace(data) {
    try {
      console.log('Creating parking space:', data);
      const response = await apiClient.post('/api/v1/spaces/', data);
      console.log('Parking space created successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to create parking space:', error.userMessage);
      throw error;
    }
  },

  async updateSpace(spaceId, data) {
    try {
      console.log('Updating parking space:', spaceId);
      const response = await apiClient.patch('/api/v1/spaces/' + spaceId, data);
      console.log('Parking space updated successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to update parking space:', error.userMessage);
      throw error;
    }
  },

  async deleteSpace(spaceId, force = false) {
    try {
      console.log('Deleting parking space:', spaceId);
      const params = force ? { force: true } : {};
      const response = await apiClient.delete('/api/v1/spaces/' + spaceId, { params });
      console.log('Parking space deleted successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to delete parking space:', error.userMessage);
      throw error;
    }
  },

  // REMOVED - /restore endpoint doesn't exist in v5.3 API
  // Spaces are soft-deleted via DELETE and can be filtered with includeDeleted param
  // async restoreSpace(spaceId) { ... }

  // REMOVED - /sensor-list endpoint doesn't exist
  // Use getAvailableSensors() instead which calls /api/v1/devices
  // async getSensorList() { ... }

  async getAvailableSensors() {
    try {
      console.log('Fetching available sensors');
      const response = await apiClient.get('/api/v1/devices', { 
        params: { device_category: 'sensor', enabled: true } 
      });
      console.log('Retrieved available sensors', response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch available sensors:', error.userMessage);
      throw error;
    }
  },

  async getAvailableDisplays() {
    try {
      console.log('Fetching available displays');
      const response = await apiClient.get('/api/v1/devices', {
        params: { device_category: 'display', enabled: true }
      });
      console.log('Retrieved available displays', response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch available displays:', error.userMessage);
      throw error;
    }
  },

  /**
   * Assign a sensor device to a parking space
   * @param {string} space_id - Space UUID
   * @param {string} sensor_eui - Sensor device EUI (16 hex chars)
   * @returns {Promise<Object>}
   */
  async assignSensor(space_id, sensor_eui) {
    try {
      console.log(`Assigning sensor ${sensor_eui} to space ${space_id}`);
      const response = await apiClient.post(
        `/api/v1/spaces/${space_id}/assign-sensor?sensor_eui=${sensor_eui}`
      );
      console.log('Sensor assigned successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to assign sensor:', error.userMessage);
      throw error;
    }
  },

  /**
   * Assign a display device to a parking space
   * @param {string} space_id - Space UUID
   * @param {string} display_eui - Display device EUI (16 hex chars)
   * @returns {Promise<Object>}
   */
  async assignDisplay(space_id, display_eui) {
    try {
      console.log(`Assigning display ${display_eui} to space ${space_id}`);
      const response = await apiClient.post(
        `/api/v1/spaces/${space_id}/assign-display?display_eui=${display_eui}`
      );
      console.log('Display assigned successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to assign display:', error.userMessage);
      throw error;
    }
  },

  /**
   * Unassign the sensor device from a parking space
   * @param {string} space_id - Space UUID
   * @returns {Promise<Object>}
   */
  async unassignSensor(space_id) {
    try {
      console.log(`Unassigning sensor from space ${space_id}`);
      const response = await apiClient.delete(`/api/v1/spaces/${space_id}/unassign-sensor`);
      console.log('Sensor unassigned successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to unassign sensor:', error.userMessage);
      throw error;
    }
  },

  /**
   * Unassign the display device from a parking space
   * @param {string} space_id - Space UUID
   * @returns {Promise<Object>}
   */
  async unassignDisplay(space_id) {
    try {
      console.log(`Unassigning display from space ${space_id}`);
      const response = await apiClient.delete(`/api/v1/spaces/${space_id}/unassign-display`);
      console.log('Display unassigned successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to unassign display:', error.userMessage);
      throw error;
    }
  },

  /**
   * Get space statistics summary
   * @returns {Promise<Object>}
   */
  async getStats() {
    try {
      const response = await apiClient.get('/api/v1/spaces/stats/summary');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch space stats:', error.userMessage);
      throw error;
    }
  },

  /**
   * Get distinct values for hierarchy dropdowns
   * This is a helper to populate cascading dropdowns
   * @param {string} field - 'building', 'floor', or 'zone'
   * @param {Object} filters - Parent filters (e.g., {building: 'North Block'})
   * @returns {Promise<Array<string>>}
   */
  async getDistinctValues(field, filters = {}) {
    const { spaces } = await this.getSpaces(filters);
    const values = new Set();
    spaces.forEach(space => {
      if (space[field]) {
        values.add(space[field]);
      }
    });
    return Array.from(values).sort();
  }
};
