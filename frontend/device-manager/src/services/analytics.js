// src/services/analytics.js
// Version: 2.0.0 - 2025-08-11 23:45:00 UTC
// Enhanced for Environmental Analytics Dashboard
// Added: Metric-specific endpoints, sensor capabilities, ASHRAE standards

import apiClient from './apiClient.js';

const ANALYTICS_BASE_URL = 'https://analytics.sensemy.cloud';

// Create analytics-specific API client
const analyticsClient = {
  get: async (endpoint) => {
    const response = await fetch(`${ANALYTICS_BASE_URL}${endpoint}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Analytics API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }
};

export const analyticsService = {
  // ═══════════════════════════════════════════════════════════════════
  // EXISTING ENDPOINTS (PRESERVED)
  // ═══════════════════════════════════════════════════════════════════

  // Get service health status
  getHealth: async () => {
    try {
      return await analyticsClient.get('/health');
    } catch (error) {
      console.error('Failed to get analytics health:', error);
      throw new Error(error.userMessage || error.message || 'Failed to check analytics service health');
    }
  },

  // Get aggregation patterns (configuration)
  getAggregationPatterns: async () => {
    try {
      return await analyticsClient.get('/v1/aggregations');
    } catch (error) {
      console.error('Failed to get aggregation patterns:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load aggregation patterns');
    }
  },

  // Get occupancy analytics data (legacy - for backward compatibility)
  getOccupancyData: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/aggregations/analytics/occupancy${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get occupancy data:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load occupancy data');
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // NEW ENVIRONMENTAL ANALYTICS ENDPOINTS
  // ═══════════════════════════════════════════════════════════════════

  // Get environmental sensor capabilities for metric-first navigation
  getSensorCapabilities: async () => {
    try {
      return await analyticsClient.get('/v1/environment/sensors/capabilities');
    } catch (error) {
      console.error('Failed to get sensor capabilities:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load sensor capabilities');
    }
  },

  // Get latest environmental readings
  getEnvironmentalLatest: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/latest${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get environmental latest:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load latest environmental data');
    }
  },

  // Get hourly environmental aggregations
  getEnvironmentalHourly: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/hourly${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get environmental hourly:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load hourly environmental data');
    }
  },

  // Get device health status
  getDeviceHealth: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/health${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get device health:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load device health data');
    }
  },

  // Get environmental device types with capabilities
  getEnvironmentalDeviceTypes: async () => {
    try {
      return await analyticsClient.get('/v1/environment/devices/types');
    } catch (error) {
      console.error('Failed to get environmental device types:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load environmental device types');
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // METRIC-SPECIFIC ENDPOINTS FOR METRIC-FIRST NAVIGATION
  // ═══════════════════════════════════════════════════════════════════

  // Get temperature-specific data
  getTemperatureData: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/metrics/temperature${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get temperature data:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load temperature data');
    }
  },

  // Get humidity-specific data
  getHumidityData: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/metrics/humidity${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get humidity data:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load humidity data');
    }
  },

  // Get CO2-specific data
  getCO2Data: async (params = {}) => {
    try {
      const queryString = new URLSearchParams(params).toString();
      const endpoint = `/v1/environment/metrics/co2${queryString ? '?' + queryString : ''}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to get CO2 data:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load CO2 data');
    }
  },

  // Compare environmental metrics across devices/locations
  compareEnvironmentalMetrics: async (metric, devices, hours = 24) => {
    try {
      const params = new URLSearchParams({
        metric,
        devices: Array.isArray(devices) ? devices.join(',') : devices,
        hours: hours.toString()
      });
      const endpoint = `/v1/environment/metrics/compare?${params.toString()}`;
      return await analyticsClient.get(endpoint);
    } catch (error) {
      console.error('Failed to compare environmental metrics:', error);
      throw new Error(error.userMessage || error.message || 'Failed to compare environmental metrics');
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // HELPER FUNCTIONS FOR ENVIRONMENTAL ANALYTICS
  // ═══════════════════════════════════════════════════════════════════

  // Get metric-specific data based on metric type
  getMetricData: async (metric, params = {}) => {
    const metricEndpoints = {
      temperature: analyticsService.getTemperatureData,
      humidity: analyticsService.getHumidityData,
      co2: analyticsService.getCO2Data
    };

    const endpoint = metricEndpoints[metric];
    if (!endpoint) {
      throw new Error(`Invalid metric: ${metric}. Use: temperature, humidity, co2`);
    }

    return await endpoint(params);
  },

  // Get compatible devices for a specific metric
  getCompatibleDevices: async (metric) => {
    try {
      const capabilities = await analyticsService.getSensorCapabilities();
      const metricCapability = capabilities.capabilities[metric];
      
      if (!metricCapability) {
        throw new Error(`Metric ${metric} not found in capabilities`);
      }

      // Get devices that support this metric
      const deviceTypes = capabilities.device_type_breakdown.filter(
        dt => dt[`supports_${metric}`]
      );

      return {
        sensor_count: metricCapability.sensor_count,
        coverage_percent: metricCapability.coverage_percent,
        compatible_device_types: deviceTypes,
        ashrae_standard: metricCapability.ashrae_standard
      };
    } catch (error) {
      console.error(`Failed to get compatible devices for ${metric}:`, error);
      throw new Error(error.userMessage || error.message || `Failed to get compatible devices for ${metric}`);
    }
  },

  // Check if value is within ASHRAE standards
  checkASHRAECompliance: (metric, value) => {
    const standards = {
      temperature: { min: 20, max: 25, unit: "°C" },
      humidity: { min: 40, max: 60, unit: "%" },
      co2: { max: 1000, unit: "ppm" }
    };

    const standard = standards[metric];
    if (!standard || value === null || value === undefined) {
      return { compliant: null, status: 'unknown', message: 'No data' };
    }

    let compliant, status, message;

    if (metric === 'co2') {
      compliant = value <= standard.max;
      status = compliant ? 'good' : 'poor';
      message = compliant ? `Good (${value} ≤ ${standard.max} ${standard.unit})` : 
                           `Poor (${value} > ${standard.max} ${standard.unit})`;
    } else {
      compliant = value >= standard.min && value <= standard.max;
      status = compliant ? 'good' : 'poor';
      message = compliant ? `Good (${standard.min}-${standard.max} ${standard.unit})` : 
                           `Outside range (${value} ${standard.unit})`;
    }

    return { compliant, status, message, standard };
  },

  // Legacy compatibility - real-time device status
  getDeviceStatus: async () => {
    try {
      const environmentalData = await analyticsService.getEnvironmentalLatest();
      const healthData = await analyticsService.getDeviceHealth();

      // Process data to determine active/inactive devices
      const deviceStatus = {};
      const now = new Date();
      const recentThreshold = new Date(now.getTime() - (2 * 60 * 60 * 1000)); // 2 hours ago

      // Process environmental data
      environmentalData.forEach(record => {
        const recordTime = new Date(record.timestamp);
        const isRecent = recordTime >= recentThreshold;
        
        deviceStatus[record.deveui] = {
          deveui: record.deveui,
          device_name: record.device_name,
          device_type: record.device_type,
          lastSeen: record.timestamp,
          isActive: isRecent,
          environmental_status: record.status?.environmental_status || 'unknown',
          temperature: record.temperature?.value,
          humidity: record.humidity?.value,
          co2: record.co2?.value
        };
      });

      // Merge health data
      healthData.forEach(record => {
        if (deviceStatus[record.deveui]) {
          deviceStatus[record.deveui].battery_status = record.battery?.status;
          deviceStatus[record.deveui].overall_health = record.overall_health;
          deviceStatus[record.deveui].connectivity_status = record.connectivity?.status;
        }
      });

      return Object.values(deviceStatus);
    } catch (error) {
      console.error('Failed to get device status:', error);
      throw new Error(error.userMessage || error.message || 'Failed to load device status');
    }
  }
};

export default analyticsService;
