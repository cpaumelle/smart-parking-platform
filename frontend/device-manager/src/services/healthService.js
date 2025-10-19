// src/services/healthService.js
import apiClient from './apiClient.js';

export const healthService = {
  // GET /health
  async check() {
    try {
      console.log('🏥 Performing health check');
      const response = await apiClient.get('/health');
      console.log('✅ Health check passed:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ Health check failed:', error.userMessage);
      throw error;
    }
  }
};
