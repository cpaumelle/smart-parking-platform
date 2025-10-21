// src/pages/Sites.jsx
import { useState, useEffect } from 'react';
import siteService from '../services/siteService.js';

const Sites = () => {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingSite, setEditingSite] = useState(null);
  const [includeInactive, setIncludeInactive] = useState(false);

  // Fetch sites from API
  const fetchSites = async () => {
    try {
      setLoading(true);
      const data = await siteService.getSites({ include_inactive: includeInactive });
      setSites(data.sites || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching sites:', err);
      setError(err.message || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
  }, [includeInactive]);

  const handleCreate = () => {
    setEditingSite(null);
    setShowModal(true);
  };

  const handleEdit = (site) => {
    setEditingSite(site);
    setShowModal(true);
  };

  const handleSave = async (formData) => {
    try {
      if (editingSite) {
        await siteService.updateSite(editingSite.id, formData);
      } else {
        await siteService.createSite(formData);
      }
      setShowModal(false);
      fetchSites();
    } catch (err) {
      console.error('Error saving site:', err);
      alert(`Failed to save site: ${err.message}`);
    }
  };

  const handleArchive = async (site) => {
    if (confirm(`Archive "${site.name}"?\n\nThis will deactivate the site.`)) {
      try {
        await siteService.archiveSite(site.id);
        fetchSites();
      } catch (err) {
        console.error('Error archiving site:', err);
        alert(`Failed to archive site: ${err.message}`);
      }
    }
  };

  const handleRestore = async (site) => {
    try {
      await siteService.restoreSite(site.id);
      fetchSites();
    } catch (err) {
      console.error('Error restoring site:', err);
      alert(`Failed to restore site: ${err.message}`);
    }
  };

  const handleDelete = async (site) => {
    const hasSpaces = site.spaces_count > 0;
    const confirmMsg = hasSpaces
      ? `Delete "${site.name}"?\n\nWARNING: This site has ${site.spaces_count} parking spaces. They will be orphaned.`
      : `Delete "${site.name}"?`;

    if (confirm(confirmMsg)) {
      try {
        await siteService.deleteSite(site.id, hasSpaces);
        fetchSites();
      } catch (err) {
        console.error('Error deleting site:', err);
        alert(`Failed to delete site: ${err.message}`);
      }
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sites</h1>
          <p className="text-gray-500 mt-1">Manage physical locations and buildings</p>
        </div>
        <button
          onClick={handleCreate}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          + Add Site
        </button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex items-center gap-4">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-gray-700">Show inactive sites</span>
        </label>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Sites Table */}
      {!loading && !error && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timezone
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Spaces
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sites.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No sites found. Click "Add Site" to create one.
                  </td>
                </tr>
              ) : (
                sites.map((site) => (
                  <tr key={site.id} className={!site.is_active ? 'bg-gray-50 opacity-60' : ''}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{site.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {site.timezone || 'UTC'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {site.spaces_count || 0} spaces
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        site.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {site.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(site.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => handleEdit(site)}
                        className="text-blue-600 hover:text-blue-900 mr-3"
                      >
                        Edit
                      </button>
                      {site.is_active ? (
                        <button
                          onClick={() => handleArchive(site)}
                          className="text-yellow-600 hover:text-yellow-900 mr-3"
                        >
                          Archive
                        </button>
                      ) : (
                        <button
                          onClick={() => handleRestore(site)}
                          className="text-green-600 hover:text-green-900 mr-3"
                        >
                          Restore
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(site)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Site Form Modal */}
      {showModal && (
        <SiteFormModal
          site={editingSite}
          onSave={handleSave}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
};

// Site Form Modal Component
const SiteFormModal = ({ site, onSave, onClose }) => {
  const [formData, setFormData] = useState({
    name: site?.name || '',
    timezone: site?.timezone || 'UTC',
    location: site?.location || null,
    metadata: site?.metadata || {},
    is_active: site?.is_active ?? true,
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-bold mb-4">
          {site ? 'Edit Site' : 'Create New Site'}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Site Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              required
              placeholder="e.g., Building A, Downtown Garage"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Timezone
            </label>
            <select
              value={formData.timezone}
              onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York</option>
              <option value="America/Chicago">America/Chicago</option>
              <option value="America/Los_Angeles">America/Los_Angeles</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Paris">Europe/Paris</option>
            </select>
          </div>

          <div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded"
              />
              <span className="text-sm font-medium text-gray-700">Active</span>
            </label>
          </div>

          <div className="flex gap-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              {site ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Sites;
