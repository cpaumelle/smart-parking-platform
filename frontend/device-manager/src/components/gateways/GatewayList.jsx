// src/components/gateways/GatewayList.jsx
// Redesigned as card-based layout like devices page, focusing on configuration
import { useState } from 'react';
import { formatLastSeen, formatDateTime } from '../../utils/formatters.js';
import { archiveGateway, updateGateway } from '../../services/gateways.js';
import { 
  getGatewayConfigBadge, 
  getRequiredGatewayAction,
  gatewayNeedsConfiguration 
} from '../../utils/gatewayConfigStatus.js';

const GatewayCard = ({ gateway, onConfigure, onArchive, onUnarchive, isLoading }) => {
  const configBadge = getGatewayConfigBadge(gateway);
  const requiredAction = getRequiredGatewayAction(gateway);
  const isArchived = !!gateway.archived_at;
  const needsConfig = gatewayNeedsConfiguration(gateway);

  // Operational status indicator (separate from configuration status)
  const getOperationalStatus = () => {
    if (isArchived) return null;
    
    switch (gateway.status) {
      case 'online':
        return { icon: '🟢', text: 'Online', color: 'text-green-600' };
      case 'offline':
        return { icon: '🔴', text: 'Offline', color: 'text-red-600' };
      default:
        return { icon: '⚫', text: 'Status Unknown', color: 'text-gray-600' };
    }
  };

  const operationalStatus = getOperationalStatus();

  return (
    <div className={`bg-white border rounded-lg p-4 ${isArchived ? 'bg-gray-50' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex-shrink-0 h-10 w-10">
            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-medium text-gray-900 truncate">
                {gateway.gateway_name || 'Unnamed Gateway'}
              </h3>
              <span className={configBadge.className}>
                {configBadge.text}
              </span>
            </div>
            <p className="text-sm text-gray-500 font-mono">{gateway.gw_eui}</p>
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-2">
        {/* Operational Status */}
        {operationalStatus && (
          <div className="flex items-center text-sm">
            <span className="mr-1">{operationalStatus.icon}</span>
            <span className={operationalStatus.color}>{operationalStatus.text}</span>
            {gateway.last_seen_at && (
              <span className="text-gray-500 ml-2">
                Last seen: {formatLastSeen(gateway.last_seen_at)}
              </span>
            )}
          </div>
        )}

        {/* Location Information */}
        {gateway.location_id && (
          <div className="flex items-center text-sm text-gray-600">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Location assigned
          </div>
        )}

        {/* Configuration Status */}
        <div className="flex items-center text-sm text-gray-600">
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {requiredAction}
        </div>

        {/* Archive Status */}
        {isArchived && (
          <div className="flex items-center text-sm text-yellow-600">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8l4 4 4-4" />
            </svg>
            Archived: {formatDateTime(gateway.archived_at)}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="mt-4 flex justify-between">
        {!isArchived && (
          <button
            onClick={() => onConfigure(gateway)}
            disabled={isLoading}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              needsConfig 
                ? 'bg-blue-600 text-white hover:bg-blue-700' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            } disabled:opacity-50`}
          >
            <svg className="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Configure
          </button>
        )}

        <div className="flex space-x-2">
          {!isArchived && (
            <button
              onClick={() => onArchive(gateway.gw_eui)}
              disabled={isLoading}
              className="px-3 py-2 text-red-600 hover:text-red-800 text-sm disabled:opacity-50"
            >
              Archive
            </button>
          )}
          
          {isArchived && (
            <button
              onClick={() => onUnarchive(gateway)}
              disabled={isLoading}
              className="px-3 py-2 text-green-600 hover:text-green-800 text-sm disabled:opacity-50"
            >
              Unarchive
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const GatewayList = ({ items, onChanged, onConfigure, loading }) => {
  const [actionsLoading, setActionsLoading] = useState({});

  const setActionLoading = (gw_eui, loading) => {
    setActionsLoading(prev => ({
      ...prev,
      [gw_eui]: loading
    }));
  };

  const handleArchive = async (gw_eui) => {
    if (!confirm(`Archive gateway ${gw_eui}? This will hide it from the main list.`)) return;
    
    try {
      setActionLoading(gw_eui, true);
      await archiveGateway(gw_eui);
      onChanged?.();
    } catch (error) {
      console.error('Failed to archive gateway:', error);
      alert(`Failed to archive gateway: ${error?.message || 'Unknown error'}`);
    } finally {
      setActionLoading(gw_eui, false);
    }
  };

  const handleUnarchive = async (gateway) => {
    if (!confirm(`Unarchive gateway ${gateway.gw_eui}? This will restore it to the active list.`)) return;
    
    try {
      setActionLoading(gateway.gw_eui, true);
      await updateGateway(gateway.gw_eui, { archived_at: null });
      onChanged?.();
    } catch (error) {
      console.error('Failed to unarchive gateway:', error);
      alert(`Failed to unarchive gateway: ${error?.message || 'Unknown error'}`);
    } finally {
      setActionLoading(gateway.gw_eui, false);
    }
  };

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading gateways...</p>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12">
        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-gray-900">No gateways found</h3>
        <p className="mt-1 text-sm text-gray-500">
          Get started by adding a new gateway or adjusting your filters.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {items.map(gateway => (
          <GatewayCard
            key={gateway.gw_eui}
            gateway={gateway}
            onConfigure={onConfigure}
            onArchive={handleArchive}
            onUnarchive={handleUnarchive}
            isLoading={actionsLoading[gateway.gw_eui]}
          />
        ))}
      </div>
    </div>
  );
};

export default GatewayList;