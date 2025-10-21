// src/components/devices/DeviceList.jsx
import { useState } from 'react';
import { useDevices } from '../../hooks/useDevices.js';
import StatusBadge from '../common/StatusBadge.jsx';
import LoadingSpinner from '../common/LoadingSpinner.jsx';
import DeviceConfigModal from './DeviceConfigModal.jsx';
import { DEVICE_FILTERS, FILTER_LABELS } from '../../utils/constants.js';
import { formatLastSeen } from '../../utils/formatters.js';
import { deviceNeedsAction } from '../../utils/deviceStatus.js';

const DeviceList = ({ initialFilters }) => {
  const {
    devices,
    loading,
    error,
    filters,
    updateFilters,
    getDeviceCounts,
    fetchDevices
  } = useDevices(initialFilters);

  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);

  const counts = getDeviceCounts();

  const handleDeviceSelect = (device) => {
    setSelectedDevice(device);
    setShowConfigModal(true);
  };

  const handleConfigClose = () => {
    setSelectedDevice(null);
    setShowConfigModal(false);
    fetchDevices();
  };


  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <div className="text-red-400">⚠️</div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">
              Error loading devices
            </h3>
            <div className="mt-2 text-sm text-red-700">
              {error.userMessage || error.message}
            </div>
            <div className="mt-4">
              <button
                onClick={() => fetchDevices()}
                className="bg-red-600 text-white px-3 py-2 rounded-md text-sm hover:bg-red-700"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Device Management</h1>
          <p className="mt-1 text-sm text-gray-600">
            Manage device assignments and monitor status
          </p>
        </div>
        <button
          onClick={() => fetchDevices()}
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Refreshing...' : '🔄 Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:gap-4 md:grid-cols-4">
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-gray-900">{counts.total}</div>
          <div className="text-sm text-gray-600">Total Devices</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-red-600">{counts.orphaned}</div>
          <div className="text-sm text-gray-600">Orphaned</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-yellow-600">{counts.partial}</div>
          <div className="text-sm text-gray-600">Partial Config</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-green-600">{counts.configured}</div>
          <div className="text-sm text-gray-600">Configured</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-gray-600">{counts.archived}</div>
          <div className="text-sm text-gray-600">Archived</div>
        </div>
      </div>

      <div className="bg-white p-4 rounded-lg border space-y-4">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => updateFilters({ status: e.target.value })}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              {Object.entries(FILTER_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1 min-w-64">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Devices
            </label>
            <input
              type="text"
              placeholder="Search by DevEUI or name..."
              value={filters.search}
              onChange={(e) => updateFilters({ search: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="text-sm text-gray-600">
          Showing {devices.length} of {counts.total} devices
        </div>
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        {loading ? (
          <div className="p-8">
            <LoadingSpinner size="large" text="Loading devices..." />
          </div>
        ) : devices.length === 0 ? (
          <div className="p-8 text-center">
            <div className="text-gray-400 text-6xl mb-4">📱</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No devices found</h3>
            <p className="text-gray-600">
              {filters.status !== DEVICE_FILTERS.ALL || filters.search
                ? 'Try adjusting your filters'
                : 'Devices will appear here once they start sending uplinks'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Device
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Site
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Seen
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {devices.map((device) => (
                  <tr key={device.deveui} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {device.name || 'Unnamed Device'}
                        </div>
                        <div className="text-sm text-gray-500 font-mono">
                          {device.deveui}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">
                        {device.device_type || (
                          <span className="text-gray-400 italic">Not assigned</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">
                        {device.location_name || (
                          <span className="text-gray-400 italic">Not assigned</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge device={device} size="small" />
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatLastSeen(device.last_uplink)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex space-x-2">
                        {deviceNeedsAction(device) ? (
                          <button
                            onClick={() => handleDeviceSelect(device)}
                            className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                          >
                            Configure
                          </button>
                        ) : (
                          <button
                            onClick={() => handleDeviceSelect(device)}
                            className="bg-gray-100 text-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-200"
                          >
                            Edit
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showConfigModal && selectedDevice && (
        <DeviceConfigModal
          device={selectedDevice}
          onClose={handleConfigClose}
          onSave={handleConfigClose}
        />
      )}
    </div>
  );
};

export default DeviceList;
