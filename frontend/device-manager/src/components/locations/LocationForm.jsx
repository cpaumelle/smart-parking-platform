/*
 * SenseMy IoT Platform - Location Form Component
 * Version: 1.0.0
 * Created: 2025-08-08 16:15:00 UTC
 * Author: SenseMy IoT Team
 * 
 * Form component for creating and editing locations.
 * Supports hierarchical location creation with proper validation
 * and parent selection logic.
 */

import { useState, useEffect, useMemo } from "react";
import { locationService } from "../../services/locationService.js";

// Location type hierarchy rules
const LOCATION_TYPES = [
  { value: 'site', label: 'Site', parentTypes: [] },
  { value: 'floor', label: 'Floor', parentTypes: ['site'] },
  { value: 'room', label: 'Room', parentTypes: ['floor'] },
  { value: 'zone', label: 'Zone', parentTypes: ['room'] }
];

// Helper function to get all nodes from a tree
function flattenTree(tree) {
  const flattened = [];
  
  const traverse = (nodes, level = 0) => {
    nodes.forEach(node => {
      flattened.push({ ...node, level });
      if (node.children && node.children.length > 0) {
        traverse(node.children, level + 1);
      }
    });
  };
  
  traverse(tree);
  return flattened;
}

export default function LocationForm({ 
  location, 
  availableParents, 
  onSaved, 
  onCancel, 
  isSubmitting, 
  setIsSubmitting, 
  setError 
}) {
  const [formData, setFormData] = useState({
    name: '',
    type: 'site',
    parent_id: null,
    uplink_metadata: {}
  });
  
  const [validationErrors, setValidationErrors] = useState({});
  const isEditing = !!(location && location.location_id);

  // Initialize form data when location prop changes
  useEffect(() => {
    if (location) {
      setFormData({
        name: location.name || '',
        type: location.type || 'site',
        parent_id: location.parent_id || null,
        uplink_metadata: location.uplink_metadata || {}
      });
    } else {
      setFormData({
        name: '',
        type: 'site',
        parent_id: null,
        uplink_metadata: {}
      });
    }
    setValidationErrors({});
  }, [location]);

  // Get available parent locations based on selected type
  const availableParentOptions = useMemo(() => {
    const selectedType = LOCATION_TYPES.find(t => t.value === formData.type);
    if (!selectedType || selectedType.parentTypes.length === 0) {
      return [];
    }

    const flatLocations = flattenTree(availableParents || []);
    return flatLocations
      .filter(loc => selectedType.parentTypes.includes(loc.type))
      .filter(loc => !isEditing || loc.location_id !== location.location_id); // Don't allow self as parent
  }, [formData.type, availableParents, isEditing, location]);

  // Reset parent when type changes to invalid combination
  useEffect(() => {
    if (formData.parent_id && availableParentOptions.length > 0) {
      const isValidParent = availableParentOptions.some(p => p.location_id === formData.parent_id);
      if (!isValidParent) {
        setFormData(prev => ({ ...prev, parent_id: null }));
      }
    }
  }, [formData.parent_id, availableParentOptions]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));

    // Clear validation error when user starts typing
    if (validationErrors[field]) {
      setValidationErrors(prev => ({
        ...prev,
        [field]: null
      }));
    }
  };

  const validateForm = () => {
    const errors = {};

    if (!formData.name.trim()) {
      errors.name = 'Location name is required';
    } else if (formData.name.trim().length < 2) {
      errors.name = 'Location name must be at least 2 characters';
    }

    if (!formData.type) {
      errors.type = 'Location type is required';
    }

    // Validate parent requirement
    const selectedType = LOCATION_TYPES.find(t => t.value === formData.type);
    if (selectedType && selectedType.parentTypes.length > 0 && !formData.parent_id) {
      errors.parent_id = `${selectedType.label} must have a parent ${selectedType.parentTypes.join(' or ')}`;
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const submitData = {
        name: formData.name.trim(),
        type: formData.type,
        parent_id: formData.parent_id || null,
        uplink_metadata: formData.uplink_metadata
      };

      if (isEditing) {
        await locationService.updateLocation(location.location_id, submitData);
      } else {
        await locationService.createLocation(submitData);
      }

      onSaved();
    } catch (error) {
      console.error('Failed to save location:', error);
      setError(error.userMessage || error.message || 'Failed to save location');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatParentOption = (parent) => {
    const indent = '  '.repeat(parent.level);
    return `${indent}${parent.name} (${parent.type})`;
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Location Name */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
          Location Name *
        </label>
        <input
          type="text"
          id="name"
          value={formData.name}
          onChange={(e) => handleInputChange('name', e.target.value)}
          className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            validationErrors.name ? 'border-red-300 focus:ring-red-500' : 'border-gray-300'
          }`}
          placeholder="Enter location name"
          disabled={isSubmitting}
        />
        {validationErrors.name && (
          <p className="mt-1 text-sm text-red-600">{validationErrors.name}</p>
        )}
      </div>

      {/* Location Type */}
      <div>
        <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
          Location Type *
        </label>
        <select
          id="type"
          value={formData.type}
          onChange={(e) => handleInputChange('type', e.target.value)}
          className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            validationErrors.type ? 'border-red-300 focus:ring-red-500' : 'border-gray-300'
          }`}
          disabled={isSubmitting}
        >
          {LOCATION_TYPES.map(type => (
            <option key={type.value} value={type.value}>
              {type.label}
              {type.parentTypes.length > 0 && ` (requires ${type.parentTypes.join(' or ')} parent)`}
            </option>
          ))}
        </select>
        {validationErrors.type && (
          <p className="mt-1 text-sm text-red-600">{validationErrors.type}</p>
        )}
      </div>

      {/* Parent Location */}
      {availableParentOptions.length > 0 && (
        <div>
          <label htmlFor="parent_id" className="block text-sm font-medium text-gray-700 mb-1">
            Parent Location
            {LOCATION_TYPES.find(t => t.value === formData.type)?.parentTypes.length > 0 && ' *'}
          </label>
          <select
            id="parent_id"
            value={formData.parent_id || ''}
            onChange={(e) => handleInputChange('parent_id', e.target.value || null)}
            className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              validationErrors.parent_id ? 'border-red-300 focus:ring-red-500' : 'border-gray-300'
            }`}
            disabled={isSubmitting}
          >
            <option value="">-- Select Parent --</option>
            {availableParentOptions.map(parent => (
              <option key={parent.location_id} value={parent.location_id}>
                {formatParentOption(parent)}
              </option>
            ))}
          </select>
          {validationErrors.parent_id && (
            <p className="mt-1 text-sm text-red-600">{validationErrors.parent_id}</p>
          )}
        </div>
      )}

      {/* Metadata (Optional) */}
      <div>
        <label htmlFor="metadata" className="block text-sm font-medium text-gray-700 mb-1">
          Additional Metadata (Optional)
        </label>
        <textarea
          id="metadata"
          value={JSON.stringify(formData.uplink_metadata, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              handleInputChange('uplink_metadata', parsed);
            } catch {
              // Invalid JSON, keep the raw text for editing
              handleInputChange('uplink_metadata', e.target.value);
            }
          }}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          placeholder='{"capacity": 50, "access_level": "public"}'
          disabled={isSubmitting}
        />
        <p className="mt-1 text-xs text-gray-500">
            Optional: Store custom properties as JSON, e.g. capacity limits or access controls
        </p>
      </div>

      {/* Form Actions */}
      <div className="flex items-center justify-end space-x-3 pt-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting || Object.keys(validationErrors).length > 0}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {isSubmitting ? (
            <div className="flex items-center space-x-2">
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>{isEditing ? 'Updating...' : 'Creating...'}</span>
            </div>
          ) : (
            isEditing ? 'Update Location' : 'Create Location'
          )}
        </button>
      </div>
    </form>
  );
}
