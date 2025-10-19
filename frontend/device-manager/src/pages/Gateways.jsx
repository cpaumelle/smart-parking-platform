// src/pages/Gateways.jsx
// Redesigned to focus on configuration management like devices page
import { useState } from "react";
import { useGateways, GATEWAY_CONFIG_FILTERS } from "../hooks/useGateways.js";
import GatewayList from "../components/gateways/GatewayList.jsx";
import GatewayForm from "../components/gateways/GatewayForm.jsx";
import GatewayConfigModal from "../components/gateways/GatewayConfigModal.jsx";
import LoadingSpinner from "../components/common/LoadingSpinner.jsx";
import { GATEWAY_CONFIG_FILTER_LABELS } from "../utils/gatewayConfigStatus.js";

export default function Gateways({ initialFilters }) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedGateway, setSelectedGateway] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  
  const { 
    gateways, 
    loading, 
    error, 
    filters, 
    updateFilters, 
    fetchGateways,
    getGatewayCounts 
  } = useGateways(initialFilters);

  const counts = getGatewayCounts();

  const handleConfigureGateway = (gateway) => {
    setSelectedGateway(gateway);
    setShowConfigModal(true);
  };

  const handleGatewayUpdated = () => {
    fetchGateways();
    setShowConfigModal(false);
    setSelectedGateway(null);
  };

  const handleAddGateway = () => {
    setShowAddForm(!showAddForm);
  };

  const handleGatewayAdded = () => {
    fetchGateways();
    setShowAddForm(false);
  };

  if (loading && gateways.length === 0) {
    return <LoadingSpinner />;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gateway Management</h1>
          <p className="text-sm text-gray-600 mt-1">
            Configure and monitor your LoRaWAN gateways
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchGateways}
            disabled={loading}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button
            onClick={handleAddGateway}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
          >
            Add Gateway
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="text-sm text-red-600">
            {error?.userMessage || error?.message || "An error occurred while loading gateways"}
          </div>
        </div>
      )}

      {/* Configuration-Focused Statistics Cards (like devices page) */}
      <div className="grid grid-cols-2 gap-2 sm:gap-4 md:grid-cols-4">
        <div className="bg-white p-4 rounded-lg border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Gateways</p>
              <p className="text-2xl font-bold text-gray-900">{counts.total}</p>
            </div>
            <div className="p-2 bg-blue-100 rounded-lg">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Configured</p>
              <p className="text-2xl font-bold text-green-600">{counts.configured}</p>
            </div>
            <div className="p-2 bg-green-100 rounded-lg">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Partial</p>
              <p className="text-2xl font-bold text-yellow-600">{counts.partial}</p>
            </div>
            <div className="p-2 bg-yellow-100 rounded-lg">
              <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Needs Config</p>
              <p className="text-2xl font-bold text-red-600">{counts.orphaned}</p>
            </div>
            <div className="p-2 bg-red-100 rounded-lg">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration-Focused Filters */}
      <div className="bg-white p-4 rounded-lg border">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">Filter by Status:</label>
            <select
              value={filters.status}
              onChange={(e) => updateFilters({ status: e.target.value })}
              className="px-3 py-1 border border-gray-300 rounded-md text-sm"
            >
              {Object.entries(GATEWAY_CONFIG_FILTER_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label} ({
                    value === GATEWAY_CONFIG_FILTERS.ALL ? counts.total :
                    value === GATEWAY_CONFIG_FILTERS.CONFIGURED ? counts.configured :
                    value === GATEWAY_CONFIG_FILTERS.PARTIAL ? counts.partial :
                    value === GATEWAY_CONFIG_FILTERS.ORPHANED ? counts.orphaned :
                    value === GATEWAY_CONFIG_FILTERS.ARCHIVED ? counts.archived : 0
                  })
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">Search:</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => updateFilters({ search: e.target.value })}
              placeholder="Search by EUI or name..."
              className="px-3 py-1 border border-gray-300 rounded-md text-sm w-64"
            />
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="includeArchived"
              checked={filters.includeArchived}
              onChange={(e) => updateFilters({ includeArchived: e.target.checked })}
              className="rounded border-gray-300"
            />
            <label htmlFor="includeArchived" className="text-sm font-medium text-gray-700">
              Include Archived
            </label>
          </div>
        </div>
      </div>

      {/* Add Gateway Form */}
      {showAddForm && (
        <div className="bg-white p-6 rounded-lg border">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Add New Gateway</h2>
            <button
              onClick={() => setShowAddForm(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <GatewayForm onSaved={handleGatewayAdded} onCancel={() => setShowAddForm(false)} />
        </div>
      )}

      {/* Gateway List - Configuration-focused */}
      <div className="bg-white rounded-lg border">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">
            Gateways ({gateways.length})
          </h2>
        </div>
        <GatewayList 
          items={gateways} 
          onChanged={fetchGateways}
          onConfigure={handleConfigureGateway}
          loading={loading}
        />
      </div>

      {/* Configuration Modal */}
      {showConfigModal && selectedGateway && (
        <GatewayConfigModal
          gateway={selectedGateway}
          onClose={() => setShowConfigModal(false)}
          onSaved={handleGatewayUpdated}
        />
      )}
    </div>
  );
}