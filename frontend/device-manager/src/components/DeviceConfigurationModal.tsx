// 10-ui-frontend/sensemy-platform/src/components/DeviceConfigurationModal.tsx
// Version: 1.0.0 - 2025-08-08 06:30 UTC
// Changelog:
// - Initial implementation of device configuration modal with location hierarchy
// - Smart device type suggestions based on payload analysis
// - Temporal assignment tracking with historical timestamps
// - Integration with existing v1/devices and v1/locations APIs

import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, CheckCircle, Clock, MapPin } from 'lucide-react';

interface Device {
  deveui: string;
  name?: string;
  device_type_id?: number;
  device_type?: string;
  location_id?: string;
  location_name?: string;
  site_name?: string;
  floor_name?: string;
  room_name?: string;
  zone_name?: string;
  last_seen_at?: string;
  lifecycle_state?: string;
  status: 'orphaned' | 'partial' | 'configured';
}

interface DeviceType {
  device_type_id: number;
  device_type: string;
  description: string;
  confidence?: number; // For smart suggestions
}

interface Location {
  location_id: string;
  name: string;
  type: 'site' | 'floor' | 'room' | 'zone';
  parent_id?: string;
  full_path?: string;
}

interface LocationHierarchy {
  sites: Location[];
  floors: Location[];
  rooms: Location[];
  zones: Location[];
}

interface DeviceConfigurationProps {
  device: Device;
  isOpen: boolean;
  onClose: () => void;
  onSave: (config: DeviceConfig) => Promise<void>;
}

interface DeviceConfig {
  device_type_id: number;
  location_id: string;
  name: string;
  assigned_at: string;
}

const DeviceConfigurationModal: React.FC<DeviceConfigurationProps> = ({
  device,
  isOpen,
  onClose,
  onSave,
}) => {
  // State management
  const [config, setConfig] = useState<Partial<DeviceConfig>>({
    device_type_id: device.device_type_id,
    location_id: device.location_id || '',
    name: device.name || '',
    assigned_at: new Date().toISOString(),
  });
  
  const [deviceTypes, setDeviceTypes] = useState<DeviceType[]>([]);
  const [locations, setLocations] = useState<LocationHierarchy>({
    sites: [],
    floors: [],
    rooms: [],
    zones: [],
  });
  
  const [selectedSite, setSelectedSite] = useState<string>('');
  const [selectedFloor, setSelectedFloor] = useState<string>('');
  const [selectedRoom, setSelectedRoom] = useState<string>('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [smartSuggestions, setSmartSuggestions] = useState<DeviceType[]>([]);

  // Load data on mount
  useEffect(() => {
    if (isOpen) {
      loadDeviceTypes();
      loadLocations();
      loadSmartSuggestions();
    }
  }, [isOpen, device.deveui]);

  // Update location cascade when selections change
  useEffect(() => {
    if (selectedSite) {
      const floors = locations.floors.filter(f => f.parent_id === selectedSite);
      setLocations(prev => ({ ...prev, floors }));
    }
  }, [selectedSite]);

  useEffect(() => {
    if (selectedFloor) {
      const rooms = locations.rooms.filter(r => r.parent_id === selectedFloor);
      setLocations(prev => ({ ...prev, rooms }));
    }
  }, [selectedFloor]);

  useEffect(() => {
    if (selectedRoom) {
      const zones = locations.zones.filter(z => z.parent_id === selectedRoom);
      setLocations(prev => ({ ...prev, zones }));
      // Set room as final location if no zones
      if (zones.length === 0) {
        setConfig(prev => ({ ...prev, location_id: selectedRoom }));
      }
    }
  }, [selectedRoom]);

  const loadDeviceTypes = async () => {
    try {
      // Use deviceService which calls /api/v1/devices/full-metadata with proper auth
      const { deviceService } = await import('../services/deviceService.js');
      const allDevices = await deviceService.getDeviceMetadata();

      // Extract unique device types from metadata
      const uniqueTypes = new Map();
      allDevices.forEach(device => {
        if (device.device_type_lns) {
          uniqueTypes.set(device.device_type_lns, {
            device_type_id: uniqueTypes.size + 1,
            device_type: device.device_type_lns,
            description: `${device.device_type_lns} sensor`
          });
        }
      });

      // Add some common device types for parking sensors
      const commonTypes = [
        { device_type_id: 100, device_type: 'browan_tabs', description: 'Browan TABS - Parking Sensor' },
        { device_type_id: 101, device_type: 'heltec_display', description: 'Heltec Display - E-ink Display' },
        { device_type_id: 102, device_type: 'kuando_busylight', description: 'Kuando Busylight - Status Light' },
        { device_type_id: 103, device_type: 'milesight_am103', description: 'Milesight AM103 - Environment Sensor' },
        { device_type_id: 104, device_type: 'generic_sensor', description: 'Generic LoRaWAN Sensor' }
      ];

      setDeviceTypes([...Array.from(uniqueTypes.values()), ...commonTypes]);
    } catch (err) {
      console.error('Error loading device types:', err);
      setError('Failed to load device types');
    }
  };

  const loadLocations = async () => {
    try {
      // Use Sites API to load sites
      const { siteService } = await import('../services/siteService.js');
      const response = await siteService.getSites({ include_inactive: false });

      // Convert sites to location format for backwards compatibility
      const siteLocations = (response.sites || []).map(site => ({
        location_id: site.id,
        name: site.name,
        type: 'site' as const,
        spaces_count: site.spaces_count
      }));

      // Simple hierarchy with just sites (no floors/rooms/zones in v5.3)
      const hierarchy = {
        sites: siteLocations,
        floors: [],
        rooms: [],
        zones: []
      };

      setLocations(hierarchy);
    } catch (err) {
      console.error('Error loading sites:', err);
      setError('Failed to load sites');
    }
  };

  const loadSmartSuggestions = async () => {
    try {
      // Use deviceService which calls /api/v1/devices/full-metadata
      const { deviceService } = await import('../services/deviceService.js');
      const allDevices = await deviceService.getDeviceMetadata();
      const currentDevice = allDevices.find(d => d.deveui === device.deveui);

      if (currentDevice?.device_type_lns) {
        const suggestions = [{
          device_type_id: 1000,
          device_type: currentDevice.device_type_lns,
          description: `Detected from recent data: ${currentDevice.device_type_lns}`,
          confidence: 0.85
        }];
        setSmartSuggestions(suggestions);
      }
    } catch (err) {
      console.error('Error loading smart suggestions:', err);
      // Non-critical, don't show error
    }
  };

  const handleSave = async () => {
    if (!config.device_type_id || !config.location_id) {
      setError('Please select both device type and location');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Use deviceService which calls /api/v1/devices/{deveui}
      const { deviceService } = await import('../services/deviceService.js');

      const updateData = {
        device_type_id: config.device_type_id,
        location_id: config.location_id,
        name: config.name || device.deveui,
        // Map location_id to site/floor/room based on selection
        ...(selectedSite && { site_id: selectedSite }),
        ...(selectedFloor && { floor_id: selectedFloor }),
        ...(selectedRoom && { room_id: selectedRoom }),
        lifecycle_state: 'CONFIGURED'
      };

      await deviceService.updateDevice(device.deveui, updateData);

      // Call the parent's onSave callback with the config
      await onSave({
        device_type_id: config.device_type_id!,
        location_id: config.location_id!,
        name: config.name || device.deveui,
        assigned_at: config.assigned_at || new Date().toISOString(),
      });

      onClose();
    } catch (err) {
      console.error('Error saving device configuration:', err);
      setError(err instanceof Error ? err.message : 'Failed to save device configuration');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'configured': return 'text-green-600 bg-green-50';
      case 'partial': return 'text-yellow-600 bg-yellow-50';
      case 'orphaned': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'configured': return <CheckCircle className="w-4 h-4" />;
      case 'partial': return <Clock className="w-4 h-4" />;
      case 'orphaned': return <AlertCircle className="w-4 h-4" />;
      default: return <AlertCircle className="w-4 h-4" />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Configure Device</h2>
            <div className="flex items-center space-x-3 mt-2">
              <code className="text-sm bg-gray-100 px-2 py-1 rounded">{device.deveui}</code>
              <span className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(device.status)}`}>
                {getStatusIcon(device.status)}
                <span className="capitalize">{device.status}</span>
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 text-red-400 mr-2" />
                <span className="text-red-700">{error}</span>
              </div>
            </div>
          )}

          {/* Device Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Device Name (Optional)
            </label>
            <input
              type="text"
              value={config.name || ''}
              onChange={(e) => setConfig(prev => ({ ...prev, name: e.target.value }))}
              placeholder={`Unnamed device (${device.deveui})`}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Device Type Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Device Type *
            </label>
            
            {/* Smart Suggestions */}
            {smartSuggestions.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-gray-600 mb-2">💡 Smart suggestions based on recent data:</p>
                <div className="flex flex-wrap gap-2">
                  {smartSuggestions.map((suggestion) => (
                    <button
                      key={suggestion.device_type_id}
                      onClick={() => setConfig(prev => ({ ...prev, device_type_id: suggestion.device_type_id }))}
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        config.device_type_id === suggestion.device_type_id
                          ? 'bg-blue-100 border-blue-300 text-blue-700'
                          : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {suggestion.device_type} 
                      {suggestion.confidence && (
                        <span className="ml-1 text-gray-500">({Math.round(suggestion.confidence * 100)}%)</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <select
              value={config.device_type_id || ''}
              onChange={(e) => setConfig(prev => ({ ...prev, device_type_id: parseInt(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            >
              <option value="">Select device type...</option>
              {deviceTypes.map((type) => (
                <option key={type.device_type_id} value={type.device_type_id}>
                  {type.device_type} - {type.description}
                </option>
              ))}
            </select>
          </div>

          {/* Site Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <MapPin className="inline w-4 h-4 mr-1" />
              Site *
            </label>
            
            <div className="space-y-3">
              {/* Site Selection */}
              <select
                value={selectedSite}
                onChange={(e) => {
                  setSelectedSite(e.target.value);
                  setConfig(prev => ({ ...prev, location_id: e.target.value }));
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select site...</option>
                {locations.sites.map((site: any) => (
                  <option key={site.location_id} value={site.location_id}>
                    🏢 {site.name} {site.spaces_count ? `(${site.spaces_count} spaces)` : ''}
                  </option>
                ))}
              </select>

              <p className="text-xs text-gray-500 mt-1">
                Select the building/site where this device is installed.
              </p>
            </div>
          </div>

          {/* Parking Space Assignment (if assigned) */}
          {device.deveui && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Parking Space Registration</h4>
              <div className="text-sm text-blue-700">
                {/* This will show the assigned parking space */}
                <p className="text-gray-600 italic">
                  Check parking spaces page to assign this device to a specific parking spot.
                </p>
              </div>
            </div>
          )}


          {/* Assignment Timestamp */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Assignment Date & Time
            </label>
            <input
              type="datetime-local"
              value={config.assigned_at ? new Date(config.assigned_at).toISOString().slice(0, 16) : ''}
              onChange={(e) => setConfig(prev => ({ ...prev, assigned_at: new Date(e.target.value).toISOString() }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500 mt-1">
              This tracks when the device was assigned to this location for historical purposes.
            </p>
          </div>

          {/* Current Configuration Preview */}
          {device.status === 'configured' && (
            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Current Configuration</h4>
              <div className="text-sm text-blue-700 space-y-1">
                <p><strong>Type:</strong> {device.device_type}</p>
                <p><strong>Location:</strong> {[device.site_name, device.floor_name, device.room_name, device.zone_name].filter(Boolean).join(' > ')}</p>
                {device.last_seen_at && (
                  <p><strong>Last Seen:</strong> {new Date(device.last_seen_at).toLocaleString()}</p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading || !config.device_type_id || !config.location_id}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save Configuration
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeviceConfigurationModal;