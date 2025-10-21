// src/components/devices/DeviceInfoModal.jsx
// Version: 1.0.0 - Build 18 - Simple device info modal (like Gateway modal)
// Device info is read-only from ChirpStack
// Site assignment via ChirpStack description field

import { useState, useEffect } from 'react';
import { Settings, AlertCircle, Save } from 'lucide-react';
import Modal from '../common/Modal.jsx';
import { formatLastSeen, formatDateTime } from '../../utils/formatters.js';
import siteService from '../../services/siteService.js';

const DeviceInfoModal = ({ device, onClose, onSaved }) => {
  // Form state for editing description (site assignment)
  const [description, setDescription] = useState(device.description || '');
  const [selectedSiteId, setSelectedSiteId] = useState('');
  const [sites, setSites] = useState([]);
  const [loadingSites, setLoadingSites] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Determine if this is a display or sensor
  const isDisplay = device.device_type?.toLowerCase().includes('display') ||
                     device.device_type?.toLowerCase().includes('heltec');

  // Load sites from API
  useEffect(() => {
    const fetchSites = async () => {
      try {
        setLoadingSites(true);
        const response = await siteService.getSites({ include_inactive: false });
        setSites(response.sites || []);
      } catch (err) {
        console.error('Failed to load sites:', err);
        setError('Failed to load sites.');
      } finally {
        setLoadingSites(false);
      }
    };
    fetchSites();
  }, []);

  // Handle site selection from dropdown
  const handleSiteSelect = (siteId) => {
    setSelectedSiteId(siteId);
    const site = sites.find(s => s.id === siteId);
    if (site) {
      setDescription(site.name);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess(false);

      // Update device description in ChirpStack via our API
      // TODO: Create PATCH /api/v1/devices/{dev_eui} endpoint
      const { deviceService } = await import('../../services/deviceService.js');
      await deviceService.updateDeviceDescription(device.deveui, { description });

      setSuccess(true);
      if (onSaved) {
        onSaved();
      }

      // Close modal after 1 second
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error('Failed to update device:', err);
      setError(err?.message || 'Failed to update device description');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Device Information: ${device.name || device.deveui}`}
      size="large"
    >
      <div className="space-y-6">
        {/* Informational Notice */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-blue-900">Site Assignment via Description Field</h4>
              <p className="text-sm text-blue-700 mt-1">
                Use the description field below to assign this device to a site or location.
                This field is stored in ChirpStack and is also visible in the ChirpStack admin interface.
              </p>
            </div>
          </div>
        </div>

        {/* Device Details (Read-Only from ChirpStack) */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3">Device Details (from ChirpStack)</h4>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Device Name (Read-Only)
              </label>
              <div className="text-sm text-gray-900 font-medium">
                {device.name || 'Unnamed Device'}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Device EUI (Hardware ID)
              </label>
              <div className="text-sm text-gray-900 font-mono bg-gray-100 px-2 py-1 rounded">
                {device.deveui}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Device Type / Profile
              </label>
              <div className="text-sm text-gray-900 font-medium">
                {device.device_type || device.device_profile_name || (
                  <span className="text-gray-400 italic font-normal">Not configured</span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                📋 Device type is managed in ChirpStack device profiles
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Category
              </label>
              <div className="text-sm text-gray-900">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  isDisplay ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                }`}>
                  {isDisplay ? '🖥️ Display Device' : '📡 Sensor Device'}
                </span>
              </div>
            </div>

            {device.last_seen_at && (
              <div>
                <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Last Seen
                </label>
                <div className="text-sm text-gray-900">
                  {formatLastSeen(device.last_seen_at) || 'Never'}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Site Selection Dropdown */}
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Site Assignment *
          </label>
          {loadingSites ? (
            <div className="text-sm text-gray-500 py-2">Loading sites...</div>
          ) : (
            <select
              value={selectedSiteId}
              onChange={(e) => handleSiteSelect(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={saving}
            >
              <option value="">-- Select a Site --</option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  🏢 {site.name} ({site.spaces_count || 0} spaces)
                </option>
              ))}
            </select>
          )}
          <p className="text-xs text-gray-500 mt-1">
            Select the site where this device is installed
          </p>
        </div>

        {/* Description Field (Auto-populated or Manual) */}
        <div>
          <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Description (Auto-populated from site selection)
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., Main Building"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
            disabled={saving}
            readOnly
          />
          <p className="text-xs text-gray-500 mt-1">
            This value is stored in ChirpStack's description field
          </p>
        </div>

        {/* Space Assignment Note */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0" />
            <div>
              <h4 className="text-sm font-medium text-yellow-900">Parking Space Assignment</h4>
              <p className="text-sm text-yellow-700 mt-1">
                To assign this {isDisplay ? 'display' : 'sensor'} to a specific parking space,
                go to the <strong>Parking Spaces</strong> page and edit the space.
              </p>
            </div>
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start">
              <Save className="w-5 h-5 text-green-600 mt-0.5 mr-2 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-medium text-green-900">Device Updated Successfully!</h4>
                <p className="text-sm text-green-700 mt-1">
                  The site assignment has been saved to ChirpStack.
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

export default DeviceInfoModal;
