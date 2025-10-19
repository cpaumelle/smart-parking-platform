// src/hooks/useDevicesWithURL.js
// Version: 2.0.0 - 2025-08-09 14:30:00 UTC
// Changelog:
// - Added URL parameter integration for filters
// - Enhanced navigation support for dashboard links
// - Maintains backward compatibility with existing useDevices
// - Added updateURL helper for filter state persistence

import { useState, useEffect, useCallback, useMemo } from 'react';
import { deviceService } from '../services/index.js';
import { getDeviceStatus } from '../utils/deviceStatus.js';
import { DEVICE_FILTERS } from '../utils/constants.js';

export const useDevicesWithURL = (initialFilters = {}) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Get filters from URL parameters or use defaults
  const getFiltersFromURL = useCallback(() => {
    const params = new URLSearchParams(window.location.search);
    return {
      status: params.get('status') || DEVICE_FILTERS.ALL,
      search: params.get('search') || '',
      device_type: params.get('device_type') || '',
      location_id: params.get('location_id') || '',
      ...initialFilters
    };
  }, [initialFilters]);

  const [filters, setFilters] = useState(getFiltersFromURL);

  // Update URL when filters change
  const updateURL = useCallback((newFilters) => {
    const params = new URLSearchParams();
    
    Object.entries(newFilters).forEach(([key, value]) => {
      if (value && value !== 'all' && value !== '') {
        params.set(key, value);
      }
    });

    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({}, '', newURL);
  }, []);

  const fetchDevices = useCallback(async (params = {}) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await deviceService.getDevices(params);
      setDevices(response || []);
    } catch (err) {
      console.error('Failed to fetch devices:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const filteredDevices = useMemo(() => {
    return devices.filter(device => {
      if (filters.status !== DEVICE_FILTERS.ALL) {
        const deviceStatus = getDeviceStatus(device);
        
        if (filters.status === DEVICE_FILTERS.ORPHANED && deviceStatus !== 'orphaned') {
          return false;
        }
        if (filters.status === DEVICE_FILTERS.PARTIAL && !['partial_type', 'partial_location'].includes(deviceStatus)) {
          return false;
        }
        if (filters.status === DEVICE_FILTERS.CONFIGURED && deviceStatus !== 'configured') {
          return false;
        }
        if (filters.status === DEVICE_FILTERS.ARCHIVED && deviceStatus !== 'archived') {
          return false;
        }
      }

      if (filters.search) {
        const searchTerm = filters.search.toLowerCase();
        const matchesDevEUI = device.deveui?.toLowerCase().includes(searchTerm);
        const matchesName = device.name?.toLowerCase().includes(searchTerm);
        if (!matchesDevEUI && !matchesName) {
          return false;
        }
      }

      return true;
    });
  }, [devices, filters]);

  const updateFilters = useCallback((newFilters) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    updateURL(updatedFilters);
  }, [filters, updateURL]);

  const getDeviceCounts = useMemo(() => {
    const counts = {
      total: devices.length,
      orphaned: 0,
      partial: 0,
      configured: 0,
      archived: 0
    };

    devices.forEach(device => {
      const status = getDeviceStatus(device);
      switch (status) {
        case 'orphaned':
          counts.orphaned++;
          break;
        case 'partial_type':
        case 'partial_location':
          counts.partial++;
          break;
        case 'configured':
          counts.configured++;
          break;
        case 'archived':
          counts.archived++;
          break;
      }
    });

    return counts;
  }, [devices]);

  // Listen for URL changes (browser back/forward)
  useEffect(() => {
    const handlePopState = () => {
      setFilters(getFiltersFromURL());
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [getFiltersFromURL]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  return {
    devices: filteredDevices,
    loading,
    error,
    filters,
    updateFilters,
    fetchDevices,
    getDeviceCounts
  };
};
