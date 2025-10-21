// src/components/gateways/GatewayConfigModal.jsx
// Version: 4.0.0 - v5.3 Multi-Tenant API
// Changelog:
// - Version 4.0.0: Made modal fully informational (read-only) - gateways managed in ChirpStack
// - Version 3.0.0: DISABLED update functionality (gateways are read-only in v5.3)
// - Gateways are auto-discovered and managed via ChirpStack

import { Settings, AlertCircle } from 'lucide-react';
import Modal from '../common/Modal.jsx';
import { formatLastSeen, formatDateTime } from '../../utils/formatters.js';
import {
  getGatewayConfigStatus,
  getGatewayConfigBadge,
  getRequiredGatewayAction
} from '../../utils/gatewayConfigStatus.js';

const GatewayConfigModal = ({ gateway, onClose, onSaved }) => {
  // No form state needed - this is a read-only informational modal

  // Configuration status analysis
  const configStatus = getGatewayConfigStatus(gateway);
  const configBadge = getGatewayConfigBadge(gateway);
  const requiredAction = getRequiredGatewayAction(gateway);
  const isOrphaned = gateway.gateway_name === 'Orphan Gateway' || !gateway.gateway_name;

  // Operational status (separate from configuration)
  const getOperationalBadge = () => {
    if (gateway.archived_at) return { color: 'bg-gray-100 text-gray-600', text: 'ARCHIVED' };
    if (gateway.status === 'online') return { color: 'bg-green-100 text-green-800', text: 'ONLINE' };
    if (gateway.status === 'offline') return { color: 'bg-red-100 text-red-800', text: 'OFFLINE' };
    return { color: 'bg-gray-100 text-gray-600', text: 'UNKNOWN' };
  };

  const operationalBadge = getOperationalBadge();

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Gateway Information: ${gateway.gateway_name || gateway.gw_eui}`}
      size="large"
    >
      <div className="space-y-6">
        {/* Configuration Status Overview */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3 flex items-center">
            <Settings className="w-4 h-4 mr-2" />
            Configuration Status
          </h4>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Gateway EUI</label>
              <div className="text-sm font-mono bg-gray-100 px-3 py-2 rounded border-2 border-gray-200 text-gray-700">
                <span className="text-xs text-gray-500 uppercase tracking-wide">Hardware ID:</span>
                <br />
                {gateway.gw_eui}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Configuration Status</label>
              <div className="mt-1">
                <span className={`px-2 py-1 rounded text-xs font-medium ${configBadge.className}`}>
                  {configBadge.text}
                </span>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Required Action</label>
              <div className="text-sm text-gray-900">{requiredAction}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Operational Status</label>
              <div className="mt-1">
                <span className={`px-2 py-1 rounded text-xs font-medium ${operationalBadge.color}`}>
                  {operationalBadge.text}
                </span>
              </div>
            </div>
          </div>

          {/* Configuration Issues Alert */}
          {configStatus !== 'configured' && (
            <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded flex items-start">
              <AlertCircle className="w-4 h-4 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
              <div className="text-sm">
                <p className="text-yellow-800 font-medium">Configuration Required</p>
                <p className="text-yellow-700">
                  {isOrphaned && 'This gateway was auto-created and needs a custom name. '}
                  {!formData.location_id && 'Location assignment is required for spatial analytics and device management.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Informational Notice */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-yellow-900">Gateway Management</h4>
              <p className="text-sm text-yellow-700 mt-1">
                Gateways are managed directly in ChirpStack and are read-only in this interface.
                To modify gateway settings (name, location, description), please use the ChirpStack admin interface.
              </p>
            </div>
          </div>
        </div>

        {/* Gateway Details (Read-Only) */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3">Gateway Details</h4>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Gateway Name
              </label>
              <div className="text-sm text-gray-900 font-medium">
                {gateway.gateway_name || 'Unnamed Gateway'}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Gateway EUI (Hardware ID)
              </label>
              <div className="text-sm text-gray-900 font-mono bg-gray-100 px-2 py-1 rounded">
                {gateway.gw_eui}
              </div>
            </div>

            {gateway.description && (
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Description
                </label>
                <div className="text-sm text-gray-900">
                  {gateway.description}
                </div>
              </div>
            )}

            {(gateway.latitude || gateway.longitude) && (
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  GPS Coordinates
                </label>
                <div className="text-sm text-gray-900">
                  Lat: {gateway.latitude?.toFixed(6) || 'N/A'},
                  Lon: {gateway.longitude?.toFixed(6) || 'N/A'}
                  {gateway.altitude && `, Alt: ${gateway.altitude}m`}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Last Seen
                </label>
                <div className="text-sm text-gray-900">
                  {formatLastSeen(gateway.last_seen_at) || 'Never'}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Created
                </label>
                <div className="text-sm text-gray-900">
                  {formatDateTime(gateway.created_at)}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* How to Update */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <Settings className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">How to Update Gateway Settings</h4>
              <p className="text-sm text-blue-700 mt-1">
                To modify this gateway's configuration:
              </p>
              <ol className="text-sm text-blue-700 mt-2 ml-4 list-decimal space-y-1">
                <li>Open the ChirpStack admin interface</li>
                <li>Navigate to Gateways → Select this gateway</li>
                <li>Update name, description, location, or other settings</li>
                <li>Changes will be automatically reflected here</li>
              </ol>
            </div>
          </div>
        </div>

        {/* Close Button */}
        <div className="flex items-center justify-end pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-white bg-blue-600 border border-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default GatewayConfigModal;
