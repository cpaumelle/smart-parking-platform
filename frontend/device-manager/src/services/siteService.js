/**
 * Site Service - v5.3 Multi-Tenant API
 * Manages sites (buildings/campuses/locations) that contain parking spaces
 *
 * Sites are the top-level organizational unit:
 * Tenant → Sites → Spaces
 *
 * Version: 1.0.0
 */

import apiClient from './apiClient.js';

export const siteService = {
  /**
   * Get all sites for the current tenant
   * @param {Object} params - Query parameters
   * @param {boolean} params.include_inactive - Include inactive sites
   * @returns {Promise<{sites: Array, total: number}>}
   */
  async getSites(params = {}) {
    const response = await apiClient.get('/api/v1/sites', { params });
    return response.data;
  },

  /**
   * Get a single site by ID
   * @param {string} siteId - Site UUID
   * @returns {Promise<Object>} Site object
   */
  async getSite(siteId) {
    const response = await apiClient.get(`/api/v1/sites/${siteId}`);
    return response.data;
  },

  /**
   * Create a new site (requires admin role)
   * @param {Object} siteData - Site creation data
   * @param {string} siteData.name - Site name (required)
   * @param {string} siteData.timezone - IANA timezone (default: 'UTC')
   * @param {Object} siteData.location - GPS coordinates and address (optional)
   * @param {Object} siteData.metadata - Additional metadata (optional)
   * @param {boolean} siteData.is_active - Whether site is active (default: true)
   * @returns {Promise<Object>} Created site object
   */
  async createSite(siteData) {
    const response = await apiClient.post('/api/v1/sites', siteData);
    return response.data;
  },

  /**
   * Update an existing site (requires admin role)
   * @param {string} siteId - Site UUID
   * @param {Object} updates - Fields to update
   * @returns {Promise<Object>} Updated site object
   */
  async updateSite(siteId, updates) {
    const response = await apiClient.patch(`/api/v1/sites/${siteId}`, updates);
    return response.data;
  },

  /**
   * Delete (deactivate) a site (requires admin role)
   * @param {string} siteId - Site UUID
   * @param {boolean} force - Force delete even if site has parking spaces
   * @returns {Promise<void>}
   */
  async deleteSite(siteId, force = false) {
    await apiClient.delete(`/api/v1/sites/${siteId}`, {
      params: { force }
    });
  },

  /**
   * Archive a site (soft delete by setting is_active=false)
   * @param {string} siteId - Site UUID
   * @returns {Promise<Object>} Updated site object
   */
  async archiveSite(siteId) {
    return await this.updateSite(siteId, { is_active: false });
  },

  /**
   * Restore an archived site
   * @param {string} siteId - Site UUID
   * @returns {Promise<Object>} Updated site object
   */
  async restoreSite(siteId) {
    return await this.updateSite(siteId, { is_active: true });
  },
};

export default siteService;
