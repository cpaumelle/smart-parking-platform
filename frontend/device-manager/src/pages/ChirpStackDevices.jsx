// src/pages/ChirpStackDevices.jsx
import React, { useState, useEffect } from 'react';
import { chirpstackService } from '../services/chirpstackService.js';
import { Wifi, Plus, Search, Filter, RefreshCw, Upload, Download, Trash2 } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ChirpStackDeviceModal from '../components/chirpstack/ChirpStackDeviceModal.jsx';
import ChirpStackBulkActions from '../components/chirpstack/ChirpStackBulkActions.jsx';

const ChirpStackDevices = () => {
  const [devices, setDevices] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [showBulkActions, setShowBulkActions] = useState(false);
  const [selectedDevices, setSelectedDevices] = useState(new Set());

  // Filters state
  const [filters, setFilters] = useState({
    skip: 0,
    limit: 50,
    application_id: '',
    device_profile_id: '',
    search: '',
    device_class: '',
    include_disabled: true
  });

  // Reference data
  const [applications, setApplications] = useState([]);
  const [deviceProfiles, setDeviceProfiles] = useState([]);

  useEffect(() => {
    loadDevices();
    loadReferenceData();
  }, [filters]);

  const loadDevices = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await chirpstackService.getDevices(filters);
      setDevices(data);
    } catch (err) {
      console.error('Failed to load ChirpStack devices:', err);
      setError(err.message || 'Failed to load devices');
    } finally {
      setLoading(false);
    }
  };

  const loadReferenceData = async () => {
    try {
      const [apps, profiles] = await Promise.all([
        chirpstackService.getApplications(),
        chirpstackService.getDeviceProfiles()
      ]);
      setApplications(apps || []);
      setDeviceProfiles(profiles || []);
    } catch (err) {
      console.error('Failed to load reference data:', err);
    }
  };

  const handleCreateDevice = () => {
    setSelectedDevice(null);
    setShowModal(true);
  };

  const handleEditDevice = (device) => {
    setSelectedDevice(device);
    setShowModal(true);
  };

  const handleDeleteDevice = async (devEui) => {
    if (!confirm(`Are you sure you want to delete device \${devEui}?`)) {
      return;
    }

    try {
      await chirpstackService.deleteDevice(devEui);
      loadDevices();
    } catch (err) {
      console.error('Failed to delete device:', err);
      alert(`Failed to delete device: \${err.message}`);
    }
  };

  const handleModalClose = (refresh = false) => {
    setShowModal(false);
    setSelectedDevice(null);
    if (refresh) {
      loadDevices();
    }
  };

  const handleSelectDevice = (devEui) => {
    const newSelected = new Set(selectedDevices);
    if (newSelected.has(devEui)) {
      newSelected.delete(devEui);
    } else {
      newSelected.add(devEui);
    }
    setSelectedDevices(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedDevices.size === devices.items.length) {
      setSelectedDevices(new Set());
    } else {
      setSelectedDevices(new Set(devices.items.map(d => d.dev_eui)));
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      skip: 0 // Reset pagination when filters change
    }));
  };

  const handlePagination = (direction) => {
    setFilters(prev => ({
      ...prev,
      skip: direction === 'next' 
        ? prev.skip + prev.limit 
        : Math.max(0, prev.skip - prev.limit)
    }));
  };

  if (error && !devices.items.length) {
    return (
      <div className="p-4 lg:p-6 xl:p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start">
            <div className="text-red-400 text-2xl">⚠️</div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-red-800">
                Error Loading ChirpStack Devices
              </h3>
              <p className="mt-2 text-sm text-red-700">{error}</p>
              <button
                onClick={loadDevices}
                className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const currentPage = Math.floor(filters.skip / filters.limit) + 1;
  const totalPages = Math.ceil(devices.total / filters.limit);

  return (
    <div className="p-4 lg:p-6 xl:p-8">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl lg:text-3xl font-bold text-gray-900 flex items-center">
              <Wifi className="w-8 h-8 mr-3 text-blue-600" />
              ChirpStack Device Manager
            </h1>
            <p className="mt-2 text-sm lg:text-base text-gray-600">
              Manage LoRaWAN devices in ChirpStack
            </p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => setShowBulkActions(!showBulkActions)}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 flex items-center"
            >
              <Upload className="w-4 h-4 mr-2" />
              Bulk Actions
            </button>
            <button
              onClick={handleCreateDevice}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Device
            </button>
            <button
              onClick={loadDevices}
              disabled={loading}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 \${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Bulk Actions Panel */}
      {showBulkActions && (
        <ChirpStackBulkActions
          onClose={() => setShowBulkActions(false)}
          onSuccess={loadDevices}
          applications={applications}
          deviceProfiles={deviceProfiles}
        />
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="text-3xl font-bold text-gray-900">{devices.total}</div>
          <div className="text-sm text-gray-600 mt-1">Total Devices</div>
        </div>
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="text-3xl font-bold text-green-600">
            {devices.items.filter(d => !d.is_disabled).length}
          </div>
          <div className="text-sm text-gray-600 mt-1">Active</div>
        </div>
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="text-3xl font-bold text-red-600">
            {devices.items.filter(d => d.is_disabled).length}
          </div>
          <div className="text-sm text-gray-600 mt-1">Disabled</div>
        </div>
        <div className="bg-white p-6 rounded-lg border shadow-sm">
          <div className="text-3xl font-bold text-blue-600">
            {selectedDevices.size}
          </div>
          <div className="text-sm text-gray-600 mt-1">Selected</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg border shadow-sm mb-6">
        <div className="flex items-center mb-4">
          <Filter className="w-5 h-5 text-gray-500 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                placeholder="Name or DevEUI..."
                className="pl-10 w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Application
            </label>
            <select
              value={filters.application_id}
              onChange={(e) => handleFilterChange('application_id', e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">All Applications</option>
              {applications.map(app => (
                <option key={app.id} value={app.id}>{app.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Device Profile
            </label>
            <select
              value={filters.device_profile_id}
              onChange={(e) => handleFilterChange('device_profile_id', e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">All Profiles</option>
              {deviceProfiles.map(profile => (
                <option key={profile.id} value={profile.id}>{profile.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Device Class
            </label>
            <select
              value={filters.device_class}
              onChange={(e) => handleFilterChange('device_class', e.target.value)}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">All Classes</option>
              <option value="A">Class A</option>
              <option value="B">Class B</option>
              <option value="C">Class C</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={filters.include_disabled}
                onChange={(e) => handleFilterChange('include_disabled', e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Include Disabled</span>
            </label>
          </div>
        </div>
      </div>

      {/* Device Table */}
      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        {loading && !devices.items.length ? (
          <div className="p-12 flex justify-center">
            <LoadingSpinner />
          </div>
        ) : devices.items.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            <Wifi className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            <p>No devices found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={selectedDevices.size === devices.items.length}
                        onChange={handleSelectAll}
                        className="rounded"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      DevEUI
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Application
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Class
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Seen
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {devices.items.map((device) => (
                    <tr key={device.dev_eui} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={selectedDevices.has(device.dev_eui)}
                          onChange={() => handleSelectDevice(device.dev_eui)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <code className="text-sm font-mono text-gray-900">
                          {device.dev_eui}
                        </code>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {device.name || '-'}
                        </div>
                        {device.description && (
                          <div className="text-xs text-gray-500">{device.description}</div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {device.application_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded">
                          Class {device.enabled_class}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded \${
                          device.is_disabled 
                            ? 'bg-red-100 text-red-800' 
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {device.is_disabled ? 'Disabled' : 'Active'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {device.last_seen_at 
                          ? new Date(device.last_seen_at).toLocaleString()
                          : 'Never'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => handleEditDevice(device)}
                          className="text-blue-600 hover:text-blue-900 mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeleteDevice(device.dev_eui)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t">
              <div className="text-sm text-gray-700">
                Showing {filters.skip + 1} to {Math.min(filters.skip + filters.limit, devices.total)} of {devices.total} devices
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => handlePagination('prev')}
                  disabled={filters.skip === 0}
                  className="px-4 py-2 border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Previous
                </button>
                <div className="px-4 py-2 text-sm text-gray-700">
                  Page {currentPage} of {totalPages}
                </div>
                <button
                  onClick={() => handlePagination('next')}
                  disabled={filters.skip + filters.limit >= devices.total}
                  className="px-4 py-2 border rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Device Modal */}
      {showModal && (
        <ChirpStackDeviceModal
          device={selectedDevice}
          applications={applications}
          deviceProfiles={deviceProfiles}
          onClose={handleModalClose}
        />
      )}

      {/* Bulk Delete */}
      {selectedDevices.size > 0 && (
        <div className="fixed bottom-6 right-6 bg-white border shadow-lg rounded-lg p-4 flex items-center space-x-4">
          <span className="text-sm text-gray-700">
            {selectedDevices.size} device(s) selected
          </span>
          <button
            onClick={async () => {
              if (confirm(`Delete \${selectedDevices.size} selected devices?`)) {
                try {
                  await chirpstackService.bulkDeleteDevices(Array.from(selectedDevices));
                  setSelectedDevices(new Set());
                  loadDevices();
                } catch (err) {
                  alert(`Failed to delete devices: \${err.message}`);
                }
              }
            }}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center"
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Selected
          </button>
        </div>
      )}
    </div>
  );
};

export default ChirpStackDevices;
