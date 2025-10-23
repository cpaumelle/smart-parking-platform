// frontend/src/services/api/v6/DeviceServiceV6.js

import { apiClient } from '../apiClient';

class DeviceServiceV6 {
  constructor() {
    this.baseUrl = '/api/v6/devices';
    this.cache = new Map();
  }

  async listDevices(options = {}) {
    const params = new URLSearchParams();
    if (options.status) params.append('status', options.status);
    if (options.includeStats) params.append('include_stats', 'true');

    const paramString = params.toString();
    const cacheKey = 'devices-' + paramString;

    // Check cache
    if (this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (Date.now() - cached.timestamp < 30000) { // 30 seconds
        return cached.data;
      }
    }

    const url = paramString ? this.baseUrl + '?' + paramString : this.baseUrl;
    const response = await apiClient.get(url);

    // Cache response
    this.cache.set(cacheKey, {
      data: response.data,
      timestamp: Date.now()
    });

    return response.data;
  }

  async assignDevice(deviceId, spaceId, reason) {
    const response = await apiClient.post(
      this.baseUrl + '/' + deviceId + '/assign',
      { space_id: spaceId, reason }
    );

    // Invalidate cache after mutation
    this.invalidateCache();

    return response.data;
  }

  async unassignDevice(deviceId, reason) {
    const response = await apiClient.post(
      this.baseUrl + '/' + deviceId + '/unassign',
      { reason }
    );

    // Invalidate cache after mutation
    this.invalidateCache();

    return response.data;
  }

  async getPoolStats() {
    const response = await apiClient.get(this.baseUrl + '/pool/stats');
    return response.data;
  }

  invalidateCache(pattern) {
    if (pattern) {
      // Invalidate matching keys
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key);
        }
      }
    } else {
      // Clear all cache
      this.cache.clear();
    }
  }
}

export default new DeviceServiceV6();
