// src/hooks/useAnalytics.js
// Version: 1.0.0 - 2025-08-09 15:55 UTC
// Changelog:
// - Initial analytics hook implementation
// - Real-time data fetching with auto-refresh
// - Error handling and loading states
// - Follows existing hook patterns from useDevices/useLocations

import { useState, useEffect, useCallback } from 'react';
import { analyticsService } from '../services/analytics.js';

export const useAnalytics = (options = {}) => {
  const { autoRefresh = true, refreshInterval = 60000 } = options; // 1 minute default
  
  const [occupancyData, setOccupancyData] = useState([]);
  const [aggregationPatterns, setAggregationPatterns] = useState([]);
  const [deviceStatus, setDeviceStatus] = useState([]);
  const [serviceHealth, setServiceHealth] = useState(null);
  
  const [loading, setLoading] = useState({
    occupancy: false,
    patterns: false,
    devices: false,
    health: false
  });
  
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Fetch occupancy data
  const fetchOccupancyData = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, occupancy: true }));
      setError(null);
      
      const data = await analyticsService.getOccupancyData();
      setOccupancyData(data || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch occupancy data:', err);
      setError(err);
    } finally {
      setLoading(prev => ({ ...prev, occupancy: false }));
    }
  }, []);

  // Fetch aggregation patterns
  const fetchAggregationPatterns = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, patterns: true }));
      
      const patterns = await analyticsService.getAggregationPatterns();
      setAggregationPatterns(patterns || []);
    } catch (err) {
      console.error('Failed to fetch aggregation patterns:', err);
      setError(err);
    } finally {
      setLoading(prev => ({ ...prev, patterns: false }));
    }
  }, []);

  // Fetch device status
  const fetchDeviceStatus = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, devices: true }));
      
      const status = await analyticsService.getDeviceStatus();
      setDeviceStatus(status || []);
    } catch (err) {
      console.error('Failed to fetch device status:', err);
      setError(err);
    } finally {
      setLoading(prev => ({ ...prev, devices: false }));
    }
  }, []);

  // Check service health
  const checkHealth = useCallback(async () => {
    try {
      setLoading(prev => ({ ...prev, health: true }));
      
      const health = await analyticsService.getHealth();
      setServiceHealth(health);
    } catch (err) {
      console.error('Failed to check analytics health:', err);
      setServiceHealth({ status: 'error', error: err.message });
    } finally {
      setLoading(prev => ({ ...prev, health: false }));
    }
  }, []);

  // Refresh all data
  const refreshAll = useCallback(async () => {
    await Promise.all([
      fetchOccupancyData(),
      fetchDeviceStatus(),
      checkHealth()
    ]);
  }, [fetchOccupancyData, fetchDeviceStatus, checkHealth]);

  // Initial data load
  useEffect(() => {
    const loadInitialData = async () => {
      await Promise.all([
        fetchAggregationPatterns(),
        refreshAll()
      ]);
    };
    
    loadInitialData();
  }, [fetchAggregationPatterns, refreshAll]);

  // Auto-refresh setup
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(refreshAll, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, refreshAll]);

  // Computed statistics
  const statistics = {
    totalDevices: deviceStatus.length,
    activeDevices: deviceStatus.filter(d => d.isActive).length,
    totalOccupancy: deviceStatus.reduce((sum, d) => sum + d.currentOccupancy, 0),
    totalTrafficIn: deviceStatus.reduce((sum, d) => sum + d.recentTraffic.in, 0),
    totalTrafficOut: deviceStatus.reduce((sum, d) => sum + d.recentTraffic.out, 0)
  };

  const isLoading = Object.values(loading).some(Boolean);

  return {
    // Data
    occupancyData,
    aggregationPatterns,
    deviceStatus,
    serviceHealth,
    statistics,
    
    // State
    loading,
    isLoading,
    error,
    lastUpdated,
    
    // Actions
    refreshAll,
    fetchOccupancyData,
    fetchDeviceStatus,
    checkHealth
  };
};

export default useAnalytics;
