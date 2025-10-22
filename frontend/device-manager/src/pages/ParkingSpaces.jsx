// src/pages/ParkingSpaces.jsx
import { useState, useEffect } from 'react';
import { useSpaces } from '../hooks/useSpaces.js';
import { useAuth } from '../contexts/AuthContext.jsx';
import SpaceFormModal from '../components/parking-spaces/SpaceFormModal.jsx';
import { reservationService } from '../services/reservationService.js';
import siteService from '../services/siteService.js';

const ParkingSpaces = () => {
  const { spaces, loading, error, filters, setFilters, fetchSpaces, createSpace, updateSpace, deleteSpace, autoRefresh, setAutoRefresh, lastRefresh } = useSpaces();
  const { currentTenant } = useAuth();
  const isPlatformAdmin = currentTenant?.role === 'platform_admin';

  const [showModal, setShowModal] = useState(false);
  const [editingSpace, setEditingSpace] = useState(null);
  const [reservations, setReservations] = useState({});
  const [reservationLoading, setReservationLoading] = useState({});
  const [currentTime, setCurrentTime] = useState(new Date());
  const [sites, setSites] = useState([]);
  const [loadingSites, setLoadingSites] = useState(true);

  // Fetch sites for filter dropdown
  useEffect(() => {
    const fetchSites = async () => {
      try {
        setLoadingSites(true);
        const response = await siteService.getSites({ include_inactive: false });
        setSites(response.sites || []);
      } catch (err) {
        console.error('Failed to load sites:', err);
      } finally {
        setLoadingSites(false);
      }
    };
    fetchSites();
  }, []);

  // Fetch active reservations for all spaces using new service
  const fetchReservations = async () => {
    try {
      const data = await reservationService.getReservations({ status: 'confirmed' });  // v5.3 uses 'confirmed' not 'active'
      const reservationMap = {};
      data.reservations.forEach(res => {
        reservationMap[res.space_id] = res;
      });
      setReservations(reservationMap);
    } catch (err) {
      console.error('Error fetching reservations:', err);
    }
  };

  // Fetch reservations when spaces change
  useEffect(() => {
    if (spaces.length > 0) {
      fetchReservations();
    }
  }, [spaces]);

  // Update clock every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const updateFilters = (newFilters) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  };

  const getStateBadgeColor = (state) => {
    switch(state?.toLowerCase()) {
      case 'free':
      case 'available': return 'bg-green-100 text-green-800';
      case 'occupied': return 'bg-red-100 text-red-800';
      case 'reserved': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Get effective state considering both database state and active reservations
  const getEffectiveState = (space) => {
    // If there's an active reservation, override state to RESERVED
    if (reservations[space.id]) {
      return 'RESERVED';
    }
    return space.state || 'unknown';
  };

  const handleCreate = () => {
    setEditingSpace(null);
    setShowModal(true);
  };

  const handleEdit = (space) => {
    setEditingSpace(space);
    setShowModal(true);
  };

  const handleSave = async (formData) => {
    if (editingSpace) {
      await updateSpace(editingSpace.id, formData);
    } else {
      await createSpace(formData);
    }
  };

  const handleArchive = async (space) => {
    if (confirm(`Archive "${space.name}"?\n\nThis will disable the space and remove it from the active list.`)) {
      await deleteSpace(space.id);
    }
  };

  // Create a 2-hour reservation using new service
  const handleReserve = async (space) => {
    if (reservationLoading[space.id]) return;

    setReservationLoading(prev => ({ ...prev, [space.id]: true }));

    try {
      const now = new Date();
      const twoHoursLater = new Date(now.getTime() + 2 * 60 * 60 * 1000);

      const data = await reservationService.createReservation({
        space_id: space.id,
        reserved_from: now,
        reserved_until: twoHoursLater,
        external_booking_id: `UI-${Date.now()}`,
        external_system: 'device_manager_ui',
        reservation_type: 'manual',
        grace_period_minutes: 15
      });

      const startLocal = now.toLocaleString();
      const startUTC = now.toISOString().replace('T', ' ').substring(0, 19);
      const endLocal = twoHoursLater.toLocaleString();
      const endUTC = twoHoursLater.toISOString().replace('T', ' ').substring(0, 19);

      alert(`✅ Reservation created successfully!\n\nSpace: ${space.name}\nDuration: 2 hours\nReservation ID: ${data.reservation_id.substring(0, 8)}...\n\nStart (Local): ${startLocal}\nStart (UTC): ${startUTC}\n\nEnd (Local): ${endLocal}\nEnd (UTC): ${endUTC}`);

      await fetchReservations();
      await fetchSpaces();
    } catch (err) {
      console.error('Error creating reservation:', err);
      const errorMessage = err.userMessage || err.message || 'Unknown error';
      alert(`❌ Error creating reservation: ${errorMessage}`);
    } finally {
      setReservationLoading(prev => ({ ...prev, [space.id]: false }));
    }
  };

  // Cancel active reservation using new service
  const handleCancelReservation = async (space) => {
    const reservation = reservations[space.id];
    if (!reservation) return;

    if (!confirm(`Cancel reservation for "${space.name}"?\n\nReservation ID: ${reservation.reservation_id.substring(0, 8)}...\nBooked until: ${new Date(reservation.reserved_until).toLocaleString()}`)) {
      return;
    }

    setReservationLoading(prev => ({ ...prev, [space.id]: true }));

    try {
      await reservationService.cancelReservation(reservation.reservation_id, 'ui_cancellation');
      alert(`✅ Reservation cancelled successfully for ${space.name}`);
      await fetchReservations();
      await fetchSpaces();
    } catch (err) {
      console.error('Error cancelling reservation:', err);
      const errorMessage = err.userMessage || err.message || 'Unknown error';
      alert(`❌ Error cancelling reservation: ${errorMessage}`);
    } finally {
      setReservationLoading(prev => ({ ...prev, [space.id]: false }));
    }
  };

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="text-red-400">⚠️</div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading parking spaces</h3>
              <div className="mt-2 text-sm text-red-700">{error}</div>
              <button onClick={fetchSpaces} className="mt-4 bg-red-600 text-white px-3 py-2 rounded-md text-sm hover:bg-red-700">
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 xl:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Parking Spaces</h1>
          <p className="mt-1 text-sm text-gray-600">Manage parking space assignments and monitor occupancy</p>
          <div className="mt-2 text-xs text-gray-500 font-mono">
            <span className="mr-4">🕐 Local: {currentTime.toLocaleString()}</span>
            <span>🌍 UTC: {currentTime.toISOString().replace('T', ' ').substring(0, 19)}</span>
            <span className="ml-4">🔄 Auto-refresh: <span className={autoRefresh ? "text-green-600 font-semibold" : "text-gray-400"}>{autoRefresh ? "ON (5s)" : "OFF"}</span> <button onClick={() => setAutoRefresh(!autoRefresh)} className="ml-2 text-blue-600 hover:underline text-xs">[toggle]</button></span>
          </div>
        </div>
        <div className="flex space-x-2">
          <button onClick={fetchSpaces} disabled={loading} className="bg-gray-100 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-200 disabled:opacity-50">
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
          <button onClick={handleCreate} className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
            + Create Space
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-gray-900">{spaces.length}</div>
          <div className="text-sm text-gray-600">Total Spaces</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-green-600">
            {spaces.filter(s => ['FREE', 'available'].includes(s.state)).length}
          </div>
          <div className="text-sm text-gray-600">Available</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-red-600">
            {spaces.filter(s => s.state === 'occupied').length}
          </div>
          <div className="text-sm text-gray-600">Occupied</div>
        </div>
        <div className="bg-white p-4 rounded-lg border">
          <div className="text-2xl font-bold text-yellow-600">
            {spaces.filter(s => s.state === 'reserved').length}
          </div>
          <div className="text-sm text-gray-600">Reserved</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg border space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
            <select
              value={filters.site_id || ''}
              onChange={(e) => updateFilters({ site_id: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              disabled={loadingSites}
            >
              <option value="">All Sites</option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Building</label>
            <input type="text" placeholder="Filter by building..." value={filters.building || ''} onChange={(e) => updateFilters({ building: e.target.value })} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Floor</label>
            <input type="text" placeholder="Filter by floor..." value={filters.floor || ''} onChange={(e) => updateFilters({ floor: e.target.value })} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Zone</label>
            <input type="text" placeholder="Filter by zone..." value={filters.zone || ''} onChange={(e) => updateFilters({ zone: e.target.value })} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
            <input type="text" placeholder="Search spaces..." value={filters.search || ''} onChange={(e) => updateFilters({ search: e.target.value })} className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
          </div>
        </div>
      </div>

      {/* Spaces Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-sm text-gray-600">Loading parking spaces...</p>
          </div>
        ) : spaces.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-600">No parking spaces found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Space</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Location</th>
                  {isPlatformAdmin && (
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tenant</th>
                  )}
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sensor</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Display</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {spaces.map((space) => {
                  const hasReservation = !!reservations[space.id];
                  const isLoading = reservationLoading[space.id];

                  return (
                    <tr key={space.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex flex-col">
                          <div className="text-sm font-medium text-gray-900">{space.name}</div>
                          {space.code && <div className="text-xs text-gray-500">{space.code}</div>}
                          {hasReservation && (
                            <div className="text-xs text-yellow-600 mt-1">
                              <div>📅 Reserved until:</div>
                              <div className="font-mono">Local: {new Date(reservations[space.id].reserved_until).toLocaleString()}</div>
                              <div className="font-mono">UTC: {new Date(reservations[space.id].reserved_until).toISOString().replace('T', ' ').substring(0, 19)}</div>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">
                          {space.site_name && <div className="font-medium">{space.site_name}</div>}
                          {[space.building, space.floor, space.zone].filter(Boolean).length > 0 && (
                            <div className="text-xs text-gray-500 mt-0.5">
                              {[space.building, space.floor, space.zone].filter(Boolean).join(' • ')}
                            </div>
                          )}
                          {!space.site_name && [space.building, space.floor, space.zone].filter(Boolean).length === 0 && '-'}
                        </div>
                      </td>
                      {isPlatformAdmin && (
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {space.tenant_name || (
                              <span className="text-gray-400 italic">No tenant</span>
                            )}
                          </div>
                        </td>
                      )}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {(() => {
                          const effectiveState = getEffectiveState(space);
                          return (
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStateBadgeColor(effectiveState)}`}>
                              {effectiveState}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-gray-500">
                        {space.sensor_eui ? `...${space.sensor_eui.slice(-6)}` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono text-gray-500">
                        {space.display_eui ? `...${space.display_eui.slice(-6)}` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {(() => {
                          const effectiveState = getEffectiveState(space);
                          return (
                            <div className="flex items-center space-x-2">
                              {/* Colored indicator matching display state */}
                              {effectiveState?.toLowerCase() === 'free' && <span className="text-green-500 text-2xl leading-none">●</span>}
                              {effectiveState?.toLowerCase() === 'occupied' && <span className="text-red-500 text-2xl leading-none">●</span>}
                              {effectiveState?.toLowerCase() === 'reserved' && <span className="text-yellow-500 text-2xl leading-none">●</span>}
                              {(!effectiveState || !['free', 'occupied', 'reserved'].includes(effectiveState.toLowerCase())) && <span className="text-gray-400 text-2xl leading-none">●</span>}
                              {/* Enabled/disabled indicator */}
                            </div>
                          );
                        })()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm space-x-2">
                        <button onClick={() => handleEdit(space)} className="text-blue-600 hover:text-blue-900">Edit</button>
                        {hasReservation ? (
                          <button 
                            onClick={() => handleCancelReservation(space)} 
                            disabled={isLoading}
                            className="text-orange-600 hover:text-orange-900 disabled:opacity-50"
                          >
                            {isLoading ? '...' : 'Cancel Reservation'}
                          </button>
                        ) : (
                          <button 
                            onClick={() => handleReserve(space)} 
                            disabled={isLoading}
                            className="text-green-600 hover:text-green-900 disabled:opacity-50"
                          >
                            {isLoading ? '...' : 'Reserve'}
                          </button>
                        )}
                        <button onClick={() => handleArchive(space)} className="text-red-600 hover:text-red-900">Archive</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal */}
      <SpaceFormModal isOpen={showModal} onClose={() => setShowModal(false)} onSave={handleSave} space={editingSpace} />
    </div>
  );
};

export default ParkingSpaces;
