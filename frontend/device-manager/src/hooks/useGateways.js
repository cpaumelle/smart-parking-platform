// src/hooks/useGateways.js
// Updated to focus on configuration status like devices page
import { useState, useEffect, useCallback, useMemo } from 'react';
import { listGateways } from '../services/gateways';
import { getGatewayConfigStatus, GATEWAY_CONFIG_STATUS } from '../utils/gatewayConfigStatus';

export const GATEWAY_CONFIG_FILTERS = {
  ALL: 'all',
  CONFIGURED: 'configured',
  PARTIAL: 'partial',
  ORPHANED: 'orphaned',
  ARCHIVED: 'archived',
};

export const useGateways = (initialFilters = {}) => {
  const [gateways, setGateways] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    status: GATEWAY_CONFIG_FILTERS.ALL,
    search: '',
    includeArchived: false,
    ...initialFilters
  });

  const fetchGateways = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listGateways({ includeArchived: filters.includeArchived });
      setGateways(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch gateways:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [filters.includeArchived]);

  const updateFilters = (patch) => setFilters(prev => ({ ...prev, ...patch }));

  const filtered = useMemo(() => {
    const term = (filters.search || '').toLowerCase().trim();

    return gateways.filter(gw => {
      // Configuration status filter (like devices page)
      if (filters.status !== GATEWAY_CONFIG_FILTERS.ALL) {
        const isArchived = !!gw.archived_at;
        const configStatus = getGatewayConfigStatus(gw);

        if (filters.status === GATEWAY_CONFIG_FILTERS.ARCHIVED && !isArchived) return false;
        if (filters.status === GATEWAY_CONFIG_FILTERS.CONFIGURED && configStatus !== GATEWAY_CONFIG_STATUS.CONFIGURED) return false;
        if (filters.status === GATEWAY_CONFIG_FILTERS.PARTIAL && configStatus !== GATEWAY_CONFIG_STATUS.PARTIAL) return false;
        if (filters.status === GATEWAY_CONFIG_FILTERS.ORPHANED && configStatus !== GATEWAY_CONFIG_STATUS.ORPHANED) return false;
      }

      // Text search on EUI or gateway name
      if (term) {
        const inEui = gw.gw_eui?.toLowerCase().includes(term);
        const inName = gw.gateway_name?.toLowerCase().includes(term);
        if (!inEui && !inName) return false;
      }

      return true;
    });
  }, [gateways, filters.status, filters.search]);

  const counts = useMemo(() => {
    const c = { total: gateways.length, configured: 0, partial: 0, orphaned: 0, archived: 0 };
    
    for (const gw of gateways) {
      if (gw.archived_at) { 
        c.archived++; 
        continue; 
      }
      
      // Count based on configuration status (like devices page)
      const configStatus = getGatewayConfigStatus(gw);
      switch (configStatus) {
        case GATEWAY_CONFIG_STATUS.CONFIGURED:
          c.configured++;
          break;
        case GATEWAY_CONFIG_STATUS.PARTIAL:
          c.partial++;
          break;
        case GATEWAY_CONFIG_STATUS.ORPHANED:
        default:
          c.orphaned++;
          break;
      }
    }
    
    return c;
  }, [gateways]);

  useEffect(() => { fetchGateways(); }, [fetchGateways]);

  return {
    gateways: filtered,
    loading,
    error,
    filters,
    updateFilters,
    fetchGateways,
    getGatewayCounts: () => counts
  };
};

export default useGateways;