// src/hooks/useDevices.js
import { useState, useEffect, useCallback } from 'react';
import { deviceService } from '../services/index.js';
import { getDeviceStatus } from '../utils/deviceStatus.js';
import { DEVICE_FILTERS } from '../utils/constants.js';

export const useDevices = (initialFilters = {}) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    status: DEVICE_FILTERS.ALL,
    search: '',
    device_type: '',
    location_id: '',
    ...initialFilters
  });

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

  const filteredDevices = devices.filter(device => {
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

  const updateFilters = (newFilters) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  };

  const getDeviceCounts = () => {
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
  };

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
