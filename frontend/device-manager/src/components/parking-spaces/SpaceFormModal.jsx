// src/components/parking-spaces/SpaceFormModal.jsx
import { useState, useEffect } from 'react';
import { parkingSpacesService } from '../../services/parkingSpacesService.js';

const SpaceFormModal = ({ isOpen, onClose, onSave, space = null }) => {
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    building: '',
    floor: '',
    zone: '',
    sensor_eui: '',
    display_eui: '',
    enabled: true
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [sensors, setSensors] = useState([]);
  const [displays, setDisplays] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadDevices();
    }

    if (space) {
      setFormData({
        name: space.name || '',
        code: space.code || '',
        building: space.building || '',
        floor: space.floor || '',
        zone: space.zone || '',
        sensor_eui: space.sensor_eui || '',
        display_eui: space.display_eui || '',
        enabled: space.enabled !== false
      });
    } else {
      setFormData({
        name: '',
        code: '',
        building: '',
        floor: '',
        zone: '',
        sensor_eui: '',
        display_eui: '',
        enabled: true
      });
    }
  }, [space, isOpen]);

  const loadDevices = async () => {
    setLoadingDevices(true);
    try {
      const [sensorsData, displaysData] = await Promise.all([
        parkingSpacesService.getAvailableSensors(),
        parkingSpacesService.getAvailableDisplays()
      ]);
      setSensors(sensorsData);
      setDisplays(displaysData);
    } catch (err) {
      console.error('Failed to load devices:', err);
      setError('Failed to load available devices');
    } finally {
      setLoadingDevices(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      await onSave(formData);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save space');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold">
            {space ? 'Edit Parking Space' : 'Create New Parking Space'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Space Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., Parking Space A1-001"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Space Code
              </label>
              <input
                type="text"
                value={formData.code}
                onChange={(e) => setFormData({...formData, code: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., A1-001"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Building
              </label>
              <input
                type="text"
                value={formData.building}
                onChange={(e) => setFormData({...formData, building: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., Building A"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Floor
              </label>
              <input
                type="text"
                value={formData.floor}
                onChange={(e) => setFormData({...formData, floor: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., Level 1"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Zone
              </label>
              <input
                type="text"
                value={formData.zone}
                onChange={(e) => setFormData({...formData, zone: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., Zone 1"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Occupancy Sensor (Class A) <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={formData.sensor_eui}
                onChange={(e) => setFormData({...formData, sensor_eui: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm"
                disabled={loadingDevices}
              >
                <option value="">-- Select Sensor --</option>
                {sensors.filter(s => s.is_available || s.dev_eui === space?.sensor_eui).map(sensor => (
                  <option key={sensor.dev_eui} value={sensor.dev_eui}>
                    {sensor.dev_eui} - {sensor.device_model || sensor.sensor_type}
                    {!sensor.is_available && ` (assigned to ${sensor.assigned_to})`}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {loadingDevices ? 'Loading sensors...' : `${sensors.filter(s => s.is_available).length} available`}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Display Device (Class C) <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={formData.display_eui}
                onChange={(e) => setFormData({...formData, display_eui: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm"
                disabled={loadingDevices}
              >
                <option value="">-- Select Display --</option>
                {displays.filter(d => d.is_available || d.dev_eui === space?.display_eui).map(display => (
                  <option key={display.dev_eui} value={display.dev_eui}>
                    {display.dev_eui} - {display.device_model || display.display_type}
                    {!display.is_available && ` (assigned to ${display.assigned_to})`}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {loadingDevices ? 'Loading displays...' : `${displays.filter(d => d.is_available).length} available`}
              </p>
            </div>
          </div>

          {space && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({...formData, enabled: e.target.checked})}
                  className="mr-2"
                />
                <label htmlFor="enabled" className="text-sm font-medium text-gray-700">
                  Space Enabled
                </label>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="maintenance"
                  className="mr-2"
                />
                <label htmlFor="maintenance" className="text-sm font-medium text-gray-700">
                  Maintenance Mode
                </label>
              </div>
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-6 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={saving}
            >
              {saving ? 'Saving...' : space ? 'Update Space' : 'Create Space'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SpaceFormModal;
