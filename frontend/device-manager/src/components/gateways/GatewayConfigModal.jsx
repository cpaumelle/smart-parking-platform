// src/components/gateways/GatewayConfigModal.jsx
// Version: 6.0.0 - Build 16 - Editable site assignment via ChirpStack description field
// Changelog:
// - Version 6.0.0: Added editable description field with Save/Cancel buttons - updates ChirpStack directly
// - Version 5.0.0: Added description field editing - updates ChirpStack database
// - Version 4.0.0: Made modal fully informational (read-only) - gateways managed in ChirpStack
// - Version 3.0.0: DISABLED update functionality (gateways are read-only in v5.3)
// - Gateways are auto-discovered and managed via ChirpStack

import { useState } from 'react';
import { Settings, AlertCircle, Save } from 'lucide-react';
import Modal from '../common/Modal.jsx';
import { formatLastSeen, formatDateTime } from '../../utils/formatters.js';
import {
  getGatewayConfigStatus,
  getGatewayConfigBadge,
  getRequiredGatewayAction
} from '../../utils/gatewayConfigStatus.js';
import { updateGateway } from '../../services/gateways.js';

const GatewayConfigModal = ({ gateway, onClose, onSaved }) => {
  // Form state for editing description
  const [description, setDescription] = useState(gateway.description || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess(false);

      await updateGateway(gateway.gw_eui, { description });

      setSuccess(true);
      if (onSaved) {
        onSaved();
      }

      // Close modal after 1 second
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error('Failed to update gateway:', err);
      setError(err?.message || 'Failed to update gateway description');
    } finally {
      setSaving(false);
    }
  };

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
      title={`Configure Gateway: ${gateway.gateway_name || gateway.gw_eui}`}
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
                  {!description && 'Site assignment via description field is recommended for better organization.'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Informational Notice */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">Site Assignment via Description Field</h4>
              <p className="text-sm text-blue-700 mt-1">
                Use the description field below to assign this gateway to a site or location.
                This field is stored in ChirpStack and is also visible in the ChirpStack admin interface.
              </p>
            </div>
          </div>
        </div>

        {/* Gateway Details */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3">Gateway Details</h4>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Gateway Name (Read-Only)
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

            {/* Editable Description Field */}
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Site / Location Description *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g., Main Building - Floor 2, Downtown Parking Garage, etc."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows="2"
                disabled={saving}
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter the site name or location where this gateway is installed
              </p>
            </div>

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

        {/* Success Message */}
        {success && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start">
              <Save className="w-5 h-5 text-green-600 mt-0.5 mr-2 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-medium text-green-900">Gateway Updated Successfully!</h4>
                <p className="text-sm text-green-700 mt-1">
                  The site/location assignment has been saved to ChirpStack.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 mr-2 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-medium text-red-900">Update Failed</h4>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {saving ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Site Assignment
              </>
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default GatewayConfigModal;
