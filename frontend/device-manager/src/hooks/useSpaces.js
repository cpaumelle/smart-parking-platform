// src/hooks/useSpaces.js
import { useState, useEffect, useCallback } from 'react';
import { parkingSpacesService } from '../services/index.js';

export const useSpaces = (initialFilters = {}) => {
  const [spaces, setSpaces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(initialFilters);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchSpaces = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = {};
      if (filters.building) params.building = filters.building;
      if (filters.floor) params.floor = filters.floor;
      if (filters.zone) params.zone = filters.zone;
      if (filters.state) params.state = filters.state;
      if (filters.include_deleted) params.include_deleted = true;
      
      const data = await parkingSpacesService.getSpaces(params);
      
      let filteredSpaces = data.spaces || [];
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        filteredSpaces = filteredSpaces.filter(space =>
          space.name?.toLowerCase().includes(searchLower) ||
          space.code?.toLowerCase().includes(searchLower) ||
          space.sensor_eui?.toLowerCase().includes(searchLower) ||
          space.display_eui?.toLowerCase().includes(searchLower)
        );
      }
      
      setSpaces(filteredSpaces);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Error fetching parking spaces:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const createSpace = useCallback(async (spaceData) => {
    try {
      setLoading(true);
      await parkingSpacesService.createSpace(spaceData);
      await fetchSpaces();
      return { success: true };
    } catch (err) {
      console.error('Error creating space:', err);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, [fetchSpaces]);

  const updateSpace = useCallback(async (spaceId, spaceData) => {
    try {
      setLoading(true);
      await parkingSpacesService.updateSpace(spaceId, spaceData);
      await fetchSpaces();
      return { success: true };
    } catch (err) {
      console.error('Error updating space:', err);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, [fetchSpaces]);

  const deleteSpace = useCallback(async (spaceId, force = false) => {
    try {
      setLoading(true);
      await parkingSpacesService.deleteSpace(spaceId, force);
      await fetchSpaces();
      return { success: true };
    } catch (err) {
      console.error('Error deleting space:', err);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, [fetchSpaces]);

  const restoreSpace = useCallback(async (spaceId) => {
    try {
      setLoading(true);
      await parkingSpacesService.restoreSpace(spaceId);
      await fetchSpaces();
      return { success: true };
    } catch (err) {
      console.error('Error restoring space:', err);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  }, [fetchSpaces]);

  // Initial fetch on mount or filter change
  useEffect(() => {
    fetchSpaces();
  }, [fetchSpaces]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchSpaces();
    }, 5000); // 5 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, fetchSpaces]);

  return {
    spaces,
    loading,
    error,
    filters,
    setFilters,
    fetchSpaces,
    createSpace,
    updateSpace,
    deleteSpace,
    restoreSpace,
    autoRefresh,
    setAutoRefresh,
    lastRefresh
  };
};
