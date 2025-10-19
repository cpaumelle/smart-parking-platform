// src/components/chirpstack/ChirpStackDeviceModal.jsx
import React, { useState, useEffect } from 'react';
import { chirpstackService } from '../../services/chirpstackService.js';
import { X, Save, Key } from 'lucide-react';

const ChirpStackDeviceModal = ({ device, applications, deviceProfiles, onClose }) => {
  const isEdit = !!device;
  
  const [formData, setFormData] = useState({
    dev_eui: device?.dev_eui || '',
    name: device?.name || '',
    description: device?.description || '',
    application_id: device?.application_id || '',
    device_profile_id: device?.device_profile_id || '',
    join_eui: device?.join_eui || '0000000000000000',
    enabled_class: device?.enabled_class || 'A',
    skip_fcnt_check: device?.skip_fcnt_check || true,
    is_disabled: device?.is_disabled || false,
    external_power_source: device?.external_power_source || false
  });

  const [showKeys, setShowKeys] = useState(false);
  const [keysData, setKeysData] = useState({
    app_key: '',
    nwk_key: ''
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isEdit) {
      loadDeviceKeys();
    }
  }, [device]);

  const loadDeviceKeys = async () => {
    if (!device?.dev_eui) return;
    try {
      const keys = await chirpstackService.getDeviceKeys(device.dev_eui);
      setKeysData({
        app_key: keys.app_key || '',
        nwk_key: keys.nwk_key || ''
      });
    } catch (err) {
      console.log('No keys found for device');
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleKeyChange = (field, value) => {
    setKeysData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      if (isEdit) {
        // Update existing device
        await chirpstackService.updateDevice(device.dev_eui, formData);
        
        // Update keys if provided
        if (keysData.app_key && keysData.nwk_key) {
          await chirpstackService.updateDeviceKeys(device.dev_eui, keysData);
        }
      } else {
        // Create new device
        const devicePayload = {
          ...formData,
          keys: (keysData.app_key && keysData.nwk_key) ? keysData : undefined
        };
        await chirpstackService.createDevice(devicePayload);
      }
      
      onClose(true); // Close with refresh
    } catch (err) {
      console.error('Failed to save device:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to save device');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-bold text-gray-900">
            {isEdit ? 'Edit Device' : 'Create New Device'}
          </h2>
          <button
            onClick={() => onClose(false)}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* DevEUI */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              DevEUI <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.dev_eui}
              onChange={(e) => handleChange('dev_eui', e.target.value.toUpperCase())}
              disabled={isEdit}
              placeholder="0000000000000000"
              maxLength={16}
              required
              className="w-full px-3 py-2 border rounded-md font-mono disabled:bg-gray-100"
            />
            <p className="mt-1 text-xs text-gray-500">16-character hexadecimal DevEUI</p>
          </div>

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Device Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          {/* Application */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Application <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.application_id}
              onChange={(e) => handleChange('application_id', e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">Select Application</option>
              {applications.map(app => (
                <option key={app.id} value={app.id}>{app.name}</option>
              ))}
            </select>
          </div>

          {/* Device Profile */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Device Profile <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.device_profile_id}
              onChange={(e) => handleChange('device_profile_id', e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">Select Profile</option>
              {deviceProfiles.map(profile => (
                <option key={profile.id} value={profile.id}>{profile.name}</option>
              ))}
            </select>
          </div>

          {/* JoinEUI */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              JoinEUI
            </label>
            <input
              type="text"
              value={formData.join_eui}
              onChange={(e) => handleChange('join_eui', e.target.value.toUpperCase())}
              placeholder="0000000000000000"
              maxLength={16}
              className="w-full px-3 py-2 border rounded-md font-mono"
            />
          </div>

          {/* Device Class */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Device Class
            </label>
            <select
              value={formData.enabled_class}
              onChange={(e) => handleChange('enabled_class', e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="A">Class A</option>
              <option value="B">Class B</option>
              <option value="C">Class C</option>
            </select>
          </div>

          {/* Checkboxes */}
          <div className="space-y-3">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.skip_fcnt_check}
                onChange={(e) => handleChange('skip_fcnt_check', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Skip Frame Counter Check</span>
            </label>

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.external_power_source}
                onChange={(e) => handleChange('external_power_source', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">External Power Source</span>
            </label>

            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.is_disabled}
                onChange={(e) => handleChange('is_disabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Disable Device</span>
            </label>
          </div>

          {/* OTAA Keys Section */}
          <div className="border-t pt-6">
            <button
              type="button"
              onClick={() => setShowKeys(!showKeys)}
              className="flex items-center space-x-2 text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              <Key className="w-4 h-4" />
              <span>{showKeys ? 'Hide' : 'Show'} OTAA Keys</span>
            </button>

            {showKeys && (
              <div className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    AppKey
                  </label>
                  <input
                    type="text"
                    value={keysData.app_key}
                    onChange={(e) => handleKeyChange('app_key', e.target.value.toUpperCase())}
                    placeholder="00000000000000000000000000000000"
                    maxLength={32}
                    className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    NwkKey
                  </label>
                  <input
                    type="text"
                    value={keysData.nwk_key}
                    onChange={(e) => handleKeyChange('nwk_key', e.target.value.toUpperCase())}
                    placeholder="00000000000000000000000000000000"
                    maxLength={32}
                    className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-6 border-t">
            <button
              type="button"
              onClick={() => onClose(false)}
              className="px-4 py-2 border rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
            >
              <Save className="w-4 h-4 mr-2" />
              {saving ? 'Saving...' : isEdit ? 'Update Device' : 'Create Device'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChirpStackDeviceModal;
