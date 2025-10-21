// src/components/parking-spaces/SpaceFormModal.jsx
import { useState, useEffect } from 'react';
import { parkingSpacesService } from '../../services/parkingSpacesService.js';
import siteService from '../../services/siteService.js';

const SpaceFormModal = ({ isOpen, onClose, onSave, space = null }) => {
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    site_id: '',
    building: '',
    floor: '',
    zone: '',
    sensor_eui: '',
    display_eui: '',
    enabled: true
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Hierarchy data
  const [sites, setSites] = useState([]);
  const [buildings, setBuildings] = useState([]);
  const [floors, setFloors] = useState([]);
  const [zones, setZones] = useState([]);
  const [loadingHierarchy, setLoadingHierarchy] = useState(false);

  // Device data
  const [sensors, setSensors] = useState([]);
  const [displays, setDisplays] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(false);

  // Load hierarchy and devices when modal opens
  useEffect(() => {
    if (isOpen) {
      loadHierarchyData();
      loadDevices();
    }
  }, [isOpen]);

  // Populate form data when space prop changes
  useEffect(() => {
    if (space) {
      setFormData({
        name: space.name || '',
        code: space.code || '',
        site_id: space.site_id || '',
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
        site_id: '',
        building: '',
        floor: '',
        zone: '',
        sensor_eui: '',
        display_eui: '',
        enabled: true
      });
    }
  }, [space]);

  // Load sites and populate hierarchy dropdowns
  const loadHierarchyData = async () => {
    setLoadingHierarchy(true);
    try {
      // Load sites
      const sitesData = await siteService.getSites({ include_inactive: false });
      setSites(sitesData.sites || []);

      // Load distinct values for cascading dropdowns
      const [buildingsData, floorsData, zonesData] = await Promise.all([
        parkingSpacesService.getDistinctValues('building'),
        parkingSpacesService.getDistinctValues('floor'),
        parkingSpacesService.getDistinctValues('zone')
      ]);

      setBuildings(buildingsData);
      setFloors(floorsData);
      setZones(zonesData);
    } catch (err) {
      console.error('Failed to load hierarchy data:', err);
    } finally {
      setLoadingHierarchy(false);
    }
  };

  // Update cascading dropdowns when parent changes
  useEffect(() => {
    if (!isOpen || !formData.site_id) return;

    const updateCascadingData = async () => {
      try {
        // When site changes, refresh buildings for that site
        const buildingsData = await parkingSpacesService.getDistinctValues('building', {
          site_id: formData.site_id
        });
        setBuildings(buildingsData);
      } catch (err) {
        console.error('Failed to update buildings:', err);
      }
    };

    updateCascadingData();
  }, [formData.site_id, isOpen]);

  useEffect(() => {
    if (!isOpen || !formData.building) return;

    const updateCascadingData = async () => {
      try {
        // When building changes, refresh floors for that building
        const floorsData = await parkingSpacesService.getDistinctValues('floor', {
          site_id: formData.site_id,
          building: formData.building
        });
        setFloors(floorsData);
      } catch (err) {
        console.error('Failed to update floors:', err);
      }
    };

    updateCascadingData();
  }, [formData.building, formData.site_id, isOpen]);

  useEffect(() => {
    if (!isOpen || !formData.floor) return;

    const updateCascadingData = async () => {
      try {
        // When floor changes, refresh zones for that floor
        const zonesData = await parkingSpacesService.getDistinctValues('zone', {
          site_id: formData.site_id,
          building: formData.building,
          floor: formData.floor
        });
        setZones(zonesData);
      } catch (err) {
        console.error('Failed to update zones:', err);
      }
    };

    updateCascadingData();
  }, [formData.floor, formData.building, formData.site_id, isOpen]);

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

          {/* Hierarchy Section */}
          <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-4">
            <h3 className="text-sm font-medium text-blue-900 mb-1">📍 Location Hierarchy</h3>
            <p className="text-xs text-blue-700">
              Navigate existing hierarchy or create new levels. Required fields marked with *
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Site - Dropdown */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Site <span className="text-red-500">*</span>
              </label>
              <select
                required
                value={formData.site_id}
                onChange={(e) => setFormData({...formData, site_id: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                disabled={loadingHierarchy}
              >
                <option value="">-- Select a Site --</option>
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
              {loadingHierarchy && <p className="text-xs text-gray-500 mt-1">Loading sites...</p>}
            </div>

            {/* Building - Combo (dropdown + type) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Building/Block
              </label>
              <input
                list="buildings-list"
                type="text"
                value={formData.building}
                onChange={(e) => setFormData({...formData, building: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="Select existing or type new..."
                disabled={!formData.site_id}
              />
              <datalist id="buildings-list">
                {buildings.map((building) => (
                  <option key={building} value={building} />
                ))}
              </datalist>
              <p className="text-xs text-gray-500 mt-1">
                {buildings.length > 0 ? `${buildings.length} existing` : 'No existing buildings'}
              </p>
            </div>

            {/* Floor - Combo (dropdown + type) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Floor/Level
              </label>
              <input
                list="floors-list"
                type="text"
                value={formData.floor}
                onChange={(e) => setFormData({...formData, floor: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="Select existing or type new..."
                disabled={!formData.site_id}
              />
              <datalist id="floors-list">
                {floors.map((floor) => (
                  <option key={floor} value={floor} />
                ))}
              </datalist>
              <p className="text-xs text-gray-500 mt-1">
                {floors.length > 0 ? `${floors.length} existing` : 'No existing floors'}
              </p>
            </div>

            {/* Zone - Combo (dropdown + type) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Zone/Area
              </label>
              <input
                list="zones-list"
                type="text"
                value={formData.zone}
                onChange={(e) => setFormData({...formData, zone: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="Select existing or type new..."
                disabled={!formData.site_id}
              />
              <datalist id="zones-list">
                {zones.map((zone) => (
                  <option key={zone} value={zone} />
                ))}
              </datalist>
              <p className="text-xs text-gray-500 mt-1">
                {zones.length > 0 ? `${zones.length} existing` : 'No existing zones'}
              </p>
            </div>

            {/* Space Code */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Space Code <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.code}
                onChange={(e) => setFormData({...formData, code: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono"
                placeholder="e.g., WOK-N-G-V01"
              />
              <p className="text-xs text-gray-500 mt-1">
                Unique identifier for this space
              </p>
            </div>

            {/* Space Name */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Space Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2"
                placeholder="e.g., Visitor Space 01"
              />
            </div>
          </div>

          {/* Device Assignment Section - Optional */}
          <div className="bg-gray-50 border border-gray-200 rounded p-3 mt-4">
            <h3 className="text-sm font-medium text-gray-900 mb-1">🔧 Device Assignment (Optional)</h3>
            <p className="text-xs text-gray-600">
              You can assign sensors and displays now or later from the Parking Spaces table.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Occupancy Sensor (Class A)
              </label>
              <select
                value={formData.sensor_eui}
                onChange={(e) => setFormData({...formData, sensor_eui: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm"
                disabled={loadingDevices}
              >
                <option value="">-- No Sensor Assigned --</option>
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
                Display Device (Class C)
              </label>
              <select
                value={formData.display_eui}
                onChange={(e) => setFormData({...formData, display_eui: e.target.value})}
                className="w-full border border-gray-300 rounded px-3 py-2 font-mono text-sm"
                disabled={loadingDevices}
              >
                <option value="">-- No Display Assigned --</option>
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
