// src/components/devices/DeviceConfigModal.jsx
import { useState, useEffect } from 'react';
import Modal from '../common/Modal.jsx';
import StatusBadge from '../common/StatusBadge.jsx';
import { getRequiredAction } from '../../utils/deviceStatus.js';
import { deviceService } from '../../services/deviceService.js';
import { locationService } from '../../services/locationService.js';
import apiClient from '../../services/apiClient.js';

const DeviceConfigModal = ({ device, onClose, onSave }) => {
  const requiredAction = getRequiredAction(device);

  // Form state
  const [deviceName, setDeviceName] = useState(device.name || '');
  const [selectedDeviceTypeId, setSelectedDeviceTypeId] = useState(device.device_type_id || '');
  const [selectedLocationId, setSelectedLocationId] = useState(device.location_id || '');

  // Parking registration state
  const [isParkingSensor, setIsParkingSensor] = useState(false);
  const [isDisplay, setIsDisplay] = useState(false);
  const [sensorType, setSensorType] = useState('occupancy');
  const [displayType, setDisplayType] = useState('led_matrix');

  // Data state
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [locations, setLocations] = useState([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Load device types, locations, and parking registration status on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load device types
        const typesResponse = await apiClient.get('/api/v1/devices/device-types');
        setDeviceTypes(typesResponse.data || []);

        // Load locations
        const locationsResponse = await locationService.getLocations();
        setLocations(locationsResponse || []);

        // Load parking registration status
        try {
          const parkingRegResponse = await apiClient.get(`/v1/devices/${device.deveui}/parking-registration`);
          setIsParkingSensor(parkingRegResponse.data.is_parking_sensor || false);
          setIsDisplay(parkingRegResponse.data.is_display || false);
          if (parkingRegResponse.data.sensor_info) {
            setSensorType(parkingRegResponse.data.sensor_info.sensor_type || 'occupancy');
          }
          if (parkingRegResponse.data.display_info) {
            setDisplayType(parkingRegResponse.data.display_info.display_type || 'led_matrix');
          }
        } catch (err) {
          // Device not registered for parking, that's OK
          console.log('Device not registered for parking use');
        }

        setLoading(false);
      } catch (err) {
        console.error('Failed to load form data:', err);
        setError('Failed to load device types and locations. Please try again.');
        setLoading(false);
      }
    };

    loadData();
  }, [device.deveui]);

  // Handle save
  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      // Save basic device configuration
      const updateData = {
        name: deviceName || null,
        device_type_id: selectedDeviceTypeId ? parseInt(selectedDeviceTypeId) : null,
        location_id: selectedLocationId || null
      };
      console.log("📋 Form values:", { deviceName, selectedDeviceTypeId, selectedLocationId, isParkingSensor, isDisplay });

      await deviceService.updateDevice(device.deveui, updateData);

      // Handle parking sensor registration
      if (isParkingSensor) {
        await apiClient.post(`/v1/devices/${device.deveui}/register-as-sensor`, {
          dev_eui: device.deveui,
          sensor_type: sensorType,
          device_model: device.name || device.metadata_hints?.device_model || null,
          manufacturer: device.metadata_hints?.device_vendor || null,
          is_parking_related: true
        });
      } else {
        // Unregister if checkbox is unchecked
        try {
          await apiClient.delete(`/v1/devices/${device.deveui}/unregister-sensor`);
        } catch (e) {
          // Ignore if not registered
        }
      }

      // Handle display registration
      if (isDisplay) {
        await apiClient.post(`/v1/devices/${device.deveui}/register-as-display`, {
          dev_eui: device.deveui,
          display_type: displayType,
          device_model: device.name || device.metadata_hints?.device_model || null,
          manufacturer: device.metadata_hints?.device_vendor || null
        });
      } else {
        // Unregister if checkbox is unchecked
        try {
          await apiClient.delete(`/v1/devices/${device.deveui}/unregister-display`);
        } catch (e) {
          // Ignore if not registered
        }
      }

      setSuccess(true);
      setTimeout(() => {
        if (onSave) {
          onSave();
        }
        onClose();
      }, 1000);

    } catch (err) {
      console.error('Failed to save device configuration:', err);
      setError(err.userMessage || err.message || 'Failed to save device configuration');
      setSaving(false);
    }
  };

  const isSaveDisabled = !selectedDeviceTypeId || saving;

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Configure Device: ${device.deveui}`}
      size="large"
    >
      <div className="space-y-6">
        <div className="bg-gray-50 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-3">Device Information</h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700">DevEUI</label>
              <div className="text-sm text-gray-900 font-mono">{device.deveui}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Name</label>
              <div className="text-sm text-gray-900">{device.name || 'Unnamed Device'}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Current Status</label>
              <div className="mt-1">
                <StatusBadge device={device} size="small" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Required Action</label>
              <div className="text-sm text-gray-900">{requiredAction}</div>
            </div>
          </div>
        </div>

        {device.metadata_hints && (
          <div className="bg-blue-50 p-4 rounded-lg">
            <h4 className="font-medium text-gray-900 mb-3">💡 Metadata Hints</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              {device.metadata_hints.device_model && (
                <div>
                  <span className="font-medium">Device Model:</span> {device.metadata_hints.device_model}
                </div>
              )}
              {device.metadata_hints.device_vendor && (
                <div>
                  <span className="font-medium">Vendor:</span> {device.metadata_hints.device_vendor}
                </div>
              )}
              {device.metadata_hints.sensor_type && (
                <div>
                  <span className="font-medium">Sensor Type:</span> {device.metadata_hints.sensor_type}
                </div>
              )}
              {device.metadata_hints.source && (
                <div>
                  <span className="font-medium">Source:</span> {device.metadata_hints.source}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Configuration Form */}
        <div className="bg-white border border-gray-200 p-4 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-4">Device Configuration</h4>
          
          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
              <p className="mt-2 text-sm text-gray-600">Loading configuration options...</p>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Device Name */}
              <div>
                <label htmlFor="device-name" className="block text-sm font-medium text-gray-700 mb-1">
                  Device Name (optional)
                </label>
                <input
                  id="device-name"
                  type="text"
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                  placeholder="Enter a friendly name for this device"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={saving}
                />
              </div>

              {/* Device Type Selection */}
              <div>
                <label htmlFor="device-type" className="block text-sm font-medium text-gray-700 mb-1">
                  Device Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="device-type"
                  value={selectedDeviceTypeId}
                  onChange={(e) => setSelectedDeviceTypeId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={saving}
                >
                  <option value="">-- Select Device Type --</option>
                  {deviceTypes.map((type) => (
                    <option key={type.device_type_id} value={type.device_type_id}>
                      {type.device_type} {type.description ? `- ${type.description}` : ''}
                    </option>
                  ))}
                </select>
                {deviceTypes.length === 0 && (
                  <p className="mt-1 text-sm text-gray-500">No device types available</p>
                )}
                {device.metadata_hints?.device_model && (
                  <p className="mt-1 text-sm text-blue-600">
                    💡 Hint: Based on metadata, this might be a {device.metadata_hints.device_model}
                  </p>
                )}
              </div>

              {/* Location Assignment */}
              <div>
                <label htmlFor="location" className="block text-sm font-medium text-gray-700 mb-1">
                  Location (optional)
                </label>
                <select
                  id="location"
                  value={selectedLocationId}
                  onChange={(e) => setSelectedLocationId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={saving}
                >
                  <option value="">-- No Location Assigned --</option>
                  {locations.map((location) => (
                    <option key={location.location_id} value={location.location_id}>
                      {location.hierarchy_path || location.name || `Location ${location.location_id}`}
                    </option>
                  ))}
                </select>
                {locations.length === 0 && (
                  <p className="mt-1 text-sm text-gray-500">No locations configured yet</p>
                )}
              </div>

              {/* Parking Registration Section */}
              <div className="pt-4 border-t">
                <h5 className="font-medium text-gray-900 mb-3">🅿️ Parking System Registration</h5>
                <div className="space-y-3">
                  {/* Parking Sensor Checkbox */}
                  <div className="flex items-start">
                    <input
                      type="checkbox"
                      id="parking-sensor"
                      checked={isParkingSensor}
                      onChange={(e) => setIsParkingSensor(e.target.checked)}
                      className="mt-1 mr-3 h-4 w-4 text-blue-600"
                      disabled={saving}
                    />
                    <div className="flex-1">
                      <label htmlFor="parking-sensor" className="text-sm font-medium text-gray-700">
                        Parking Sensor (Class A)
                      </label>
                      <p className="text-xs text-gray-500 mt-1">
                        Register as occupancy sensor for parking space detection
                      </p>
                      {isParkingSensor && (
                        <select
                          value={sensorType}
                          onChange={(e) => setSensorType(e.target.value)}
                          className="mt-2 w-full px-2 py-1 text-sm border border-gray-300 rounded"
                          disabled={saving}
                        >
                          <option value="occupancy">Occupancy</option>
                          <option value="motion">Motion</option>
                          <option value="ultrasonic">Ultrasonic</option>
                          <option value="magnetic">Magnetic</option>
                        </select>
                      )}
                    </div>
                  </div>

                  {/* Display Checkbox */}
                  <div className="flex items-start">
                    <input
                      type="checkbox"
                      id="parking-display"
                      checked={isDisplay}
                      onChange={(e) => setIsDisplay(e.target.checked)}
                      className="mt-1 mr-3 h-4 w-4 text-blue-600"
                      disabled={saving}
                    />
                    <div className="flex-1">
                      <label htmlFor="parking-display" className="text-sm font-medium text-gray-700">
                        Parking Display (Class C)
                      </label>
                      <p className="text-xs text-gray-500 mt-1">
                        Register as LED/indicator display for parking space status
                      </p>
                      {isDisplay && (
                        <select
                          value={displayType}
                          onChange={(e) => setDisplayType(e.target.value)}
                          className="mt-2 w-full px-2 py-1 text-sm border border-gray-300 rounded"
                          disabled={saving}
                        >
                          <option value="led_matrix">LED Matrix</option>
                          <option value="kuando_busylight">Kuando Busylight</option>
                          <option value="indicator_light">Indicator Light</option>
                          <option value="e-paper">E-Paper Display</option>
                        </select>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Success Message */}
              {success && (
                <div className="bg-green-50 border border-green-200 p-3 rounded-lg">
                  <p className="text-sm text-green-800">✅ Device configuration saved successfully!</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end space-x-3 pt-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            disabled={saving}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaveDisabled}
            className={`px-4 py-2 rounded-md ${
              isSaveDisabled
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default DeviceConfigModal;
