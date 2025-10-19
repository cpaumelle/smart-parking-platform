// src/config/api.js
const API_CONFIG = {
  baseURL: import.meta.env.VITE_TRANSFORM_API_URL || 
           window.APP_CONFIG?.TRANSFORM_API_BASE || 
           'https://api3.sensemy.cloud',
  
  // ChirpStack Manager API endpoint
  chirpstackURL: import.meta.env.VITE_CHIRPSTACK_API_URL ||
                 window.APP_CONFIG?.CHIRPSTACK_API_BASE ||
                 'https://chirpstack-api.verdegris.eu',
  
  // Parking Spaces API endpoint
  parkingURL: import.meta.env.VITE_PARKING_API_URL ||
              window.APP_CONFIG?.PARKING_API_BASE ||
              'https://parking.verdegris.eu',
  
  timeout: 10000,
  withCredentials: true,
  
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
};

console.log('🔧 API Configuration loaded:', {
  baseURL: API_CONFIG.baseURL,
  chirpstackURL: API_CONFIG.chirpstackURL,
  parkingURL: API_CONFIG.parkingURL,
  environment: import.meta.env.VITE_NODE_ENV,
  mode: import.meta.env.MODE
});

export default API_CONFIG;
