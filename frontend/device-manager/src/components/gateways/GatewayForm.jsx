// src/components/gateways/GatewayForm.jsx
// Updated to use real API data structure and validation
import { useState } from 'react';
import { createGateway } from '../../services/gateways.js';
import { 
  GATEWAY_STATUS_OPTIONS, 
  validateGatewayEui, 
  validateGatewayName,
  GATEWAY_STATUS
} from '../../utils/gatewayConstants.js';

const GatewayForm = ({ onSaved, onCancel }) => {
  const [formData, setFormData] = useState({
    gw_eui: '',
    gateway_name: '',
    status: GATEWAY_STATUS.OFFLINE, // Default to offline as per database
    // Note: location_id and site_id would be added when location picker is implemented
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    // Clear error when user starts typing
    if (error) setError('');
  };

  const validateForm = () => {
    // Validate EUI
    const euiValidation = validateGatewayEui(formData.gw_eui);
    if (!euiValidation.valid) {
      setError(euiValidation.message);
      return false;
    }

    // Validate gateway name
    const nameValidation = validateGatewayName(formData.gateway_name);
    if (!nameValidation.valid) {
      setError(nameValidation.message);
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    try {
      setLoading(true);
      setError('');
      
      // Prepare payload with real API fields
      const payload = {
        gw_eui: formData.gw_eui.trim(),
        gateway_name: formData.gateway_name.trim(),
        status: formData.status
      };
      
      // Remove null/empty values - let backend handle defaults
      Object.keys(payload).forEach(key => {
        if (payload[key] === '' || payload[key] === null) {
          delete payload[key];
        }
      });

      await createGateway(payload);
      
      // Reset form
      setFormData({
        gw_eui: '',
        gateway_name: '',
        status: GATEWAY_STATUS.OFFLINE
      });
      
      onSaved?.();
    } catch (err) {
      console.error('Failed to create gateway:', err);
      setError(err?.userMessage || err?.message || 'Failed to create gateway');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      gw_eui: '',
      gateway_name: '',
      status: GATEWAY_STATUS.OFFLINE
    });
    setError('');
    onCancel?.();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:gap-4 md:grid-cols-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Gateway EUI <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.gw_eui}
            onChange={(e) => handleInputChange('gw_eui', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="e.g., 7076FF00640503CA or NETMORE-30833"
            required
          />
          <p className="text-xs text-gray-500 mt-1">
            Gateway identifier - can be hex format or custom string
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Gateway Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.gateway_name}
            onChange={(e) => handleInputChange('gateway_name', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Enter gateway name"
            maxLength={255}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Initial Status
          </label>
          <select
            value={formData.status}
            onChange={(e) => handleInputChange('status', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {GATEWAY_STATUS_OPTIONS.map(option => (
              <option key={option.value || 'null'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            Status can be changed later through configuration
          </p>
        </div>

        <div className="flex items-end">
          <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg w-full">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h4 className="text-sm font-medium text-blue-800">Location Assignment</h4>
                <p className="text-sm text-blue-700 mt-1">
                  Location assignment will be available after creation through the configuration modal.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3">
          <div className="text-sm text-red-600">{error}</div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-end space-x-3 pt-4">
        {onCancel && (
          <button
            type="button"
            onClick={handleCancel}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
            disabled={loading}
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Creating...' : 'Create Gateway'}
        </button>
      </div>
    </form>
  );
};

export default GatewayForm;