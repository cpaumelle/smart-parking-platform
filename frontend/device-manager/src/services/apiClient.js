// src/services/apiClient.js
import axios from 'axios';
import API_CONFIG from '../config/api.js';

// Create axios instance
const apiClient = axios.create(API_CONFIG);

// Request interceptor - log all requests
apiClient.interceptors.request.use(
  (config) => {
    const timestamp = new Date().toISOString();
    console.log(`📤 [${timestamp}] ${config.method.toUpperCase()} ${config.baseURL}${config.url}`);
    
    if (config.data) {
      console.log('📦 Request body:', config.data);
    }
    if (config.params) {
      console.log('🔍 Request params:', config.params);
    }
    
    return config;
  },
  (error) => {
    console.error('📤❌ Request setup failed:', error);
    return Promise.reject(error);
  }
);

// Response interceptor - log all responses
apiClient.interceptors.response.use(
  (response) => {
    const timestamp = new Date().toISOString();
    const duration = response.config.metadata?.startTime 
      ? Date.now() - response.config.metadata.startTime 
      : 'unknown';
    
    console.log(`📥 [${timestamp}] ${response.status} ${response.config.url} (${duration}ms)`);
    console.log('📦 Response data:', response.data);
    
    return response;
  },
  (error) => {
    const timestamp = new Date().toISOString();
    const status = error.response?.status || 'NO_RESPONSE';
    const url = error.config?.url || 'unknown';
    
    console.error(`📥❌ [${timestamp}] ${status} ${url}`);
    console.error('Error details:', {
      message: error.message,
      code: error.code,
      response: error.response?.data
    });
    
    // Add user-friendly error messages
    if (!error.response) {
      error.userMessage = 'Cannot connect to API - check if transform service is running';
    } else if (error.response.status === 404) {
      error.userMessage = 'API endpoint not found';
    } else if (error.response.status === 500) {
      error.userMessage = 'Server error - check backend logs';
    } else if (error.response.status === 403) {
      error.userMessage = 'Access denied - check CORS configuration';
    } else if (error.response.status === 422) {
      // Handle validation errors (422 Unprocessable Entity)
      const detail = error.response?.data?.detail;
      if (Array.isArray(detail)) {
        // Pydantic validation errors - array of {type, loc, msg, input}
        error.userMessage = detail.map(err => {
          const field = err.loc ? err.loc.join(' > ') : 'unknown';
          return `${field}: ${err.msg}`;
        }).join('; ');
      } else if (typeof detail === 'object') {
        error.userMessage = JSON.stringify(detail);
      } else {
        error.userMessage = detail || 'Validation error';
      }
    } else {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'string') {
        error.userMessage = detail;
      } else if (typeof detail === 'object') {
        error.userMessage = JSON.stringify(detail);
      } else {
        error.userMessage = error.message;
      }
    }
    
    return Promise.reject(error);
  }
);

// Add request timing
apiClient.interceptors.request.use((config) => {
  config.metadata = { startTime: Date.now() };
  return config;
});

export default apiClient;
