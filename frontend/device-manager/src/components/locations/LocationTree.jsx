/*
 * SenseMy IoT Platform - Location Tree Component
 * Version: 2.0.0
 * Created: 2025-08-11 17:00:00 UTC
 * Author: SenseMy IoT Development Team
 *
 * Changelog:
 * - Complete responsive rewrite using new design system
 * - Mobile-first approach with touch-friendly interactions
 * - Simplified indentation system
 * - Enhanced accessibility and keyboard navigation
 * - Performance optimizations with proper memoization
 */

import { useState, memo } from "react";

// Helper functions for location hierarchy
const getChildType = (parentType) => {
  switch (parentType) {
    case "site": return "floor";
    case "floor": return "room";
    case "room": return "zone";
    default: return "site";
  }
};

const canHaveChildren = (locationType) => {
  return ["site", "floor", "room"].includes(locationType);
};

// Location type configuration with responsive icons
const LOCATION_CONFIG = {
  site: {
    icon: (
      <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
    color: "text-indigo-600",
    bgColor: "bg-indigo-50",
    borderColor: "border-indigo-200"
  },
  floor: {
    icon: (
      <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2 2z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 21v-4a2 2 0 012-2h2a2 2 0 012 2v4" />
      </svg>
    ),
    color: "text-green-600",
    bgColor: "bg-green-50",
    borderColor: "border-green-200"
  },
  room: {
    icon: (
      <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10v11M20 10v11" />
      </svg>
    ),
    color: "text-yellow-600",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200"
  },
  zone: {
    icon: (
      <svg className="w-4 h-4 lg:w-5 lg:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
      </svg>
    ),
    color: "text-purple-600",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200"
  }
};

const LocationNode = memo(({ location, level = 0, onEdit, onArchive, onAddChild, isSubmitting }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const config = LOCATION_CONFIG[location.type] || LOCATION_CONFIG.site;
  const hasChildren = location.children && location.children.length > 0;

  // Calculate indentation using CSS classes
  const getIndentClass = (level) => {
    if (level === 0) return '';
    if (level === 1) return 'location-indent-1';
    if (level === 2) return 'location-indent-2';
    return 'location-indent-3';
  };

  const handleToggleExpand = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  };

  const handleEdit = (e) => {
    e.stopPropagation();
    onEdit(location);
  };

  const handleArchive = (e) => {
    e.stopPropagation();
    onArchive(location.location_id, location.name);
  };

  const handleAddChild = (e) => {
    e.stopPropagation();
    const childType = getChildType(location.type);
    onAddChild({
      name: "",
      type: childType,
      parent_id: location.location_id,
      uplink_metadata: {}
    });
  };

  return (
    <div className={`${getIndentClass(level)} mb-3 fade-in`}>
      {/* Location Node */}
      <div className={`location-node ${config.bgColor} ${config.borderColor} gpu-accelerated`}>
        <div className="location-node-content">
          <div className="location-node-info">
            {/* Expand/Collapse Button */}
            <button
              onClick={handleToggleExpand}
              className={`btn-icon flex-shrink-0 ${hasChildren ? 'text-gray-500 hover:text-gray-700' : 'invisible'}`}
              disabled={!hasChildren}
              aria-label={hasChildren ? (isExpanded ? 'Collapse' : 'Expand') : 'No children'}
            >
              {hasChildren ? (
                isExpanded ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )
              ) : (
                <div className="w-4 h-4" />
              )}
            </button>

            {/* Location Icon */}
            <div className={`p-2 rounded-md ${config.color} ${config.bgColor} flex-shrink-0`}>
              {config.icon}
            </div>

            {/* Location Info */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm lg:text-base font-medium text-gray-900 truncate">
                  {location.name}
                </h3>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${config.color} ${config.bgColor} flex-shrink-0`}>
                  {location.type}
                </span>
                {hasChildren && (
                  <span className="px-2 py-1 text-xs text-gray-500 bg-gray-100 rounded-full flex-shrink-0">
                    {location.children.length} {location.children.length === 1 ? 'child' : 'children'}
                  </span>
                )}
              </div>
              {location.path_string && (
                <p className="text-xs lg:text-sm text-gray-500 mt-1 truncate">{location.path_string}</p>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="location-node-actions">
            {/* Add Child Button */}
            {canHaveChildren(location.type) && (
              <button
                onClick={handleAddChild}
                disabled={isSubmitting}
                className="btn-icon text-gray-400 hover:text-green-600 hover:bg-green-50 touch-optimized"
                title={`Add ${getChildType(location.type)} to this ${location.type}`}
                aria-label={`Add ${getChildType(location.type)}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </button>
            )}

            <button
              onClick={handleEdit}
              disabled={isSubmitting}
              className="btn-icon text-gray-400 hover:text-blue-600 hover:bg-blue-50 touch-optimized"
              title="Edit location"
              aria-label="Edit location"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>

            <button
              onClick={handleArchive}
              disabled={isSubmitting}
              className="btn-icon text-gray-400 hover:text-red-600 hover:bg-red-50 touch-optimized"
              title="Archive location"
              aria-label="Archive location"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="mt-3 space-y-3 fade-in">
          {location.children.map((child) => (
            <LocationNode
              key={child.location_id}
              location={child}
              level={level + 1}
              onEdit={onEdit}
              onArchive={onArchive}
              onAddChild={onAddChild}
              isSubmitting={isSubmitting}
            />
          ))}
        </div>
      )}
    </div>
  );
});

LocationNode.displayName = 'LocationNode';

export default function LocationTree({ locations, onEdit, onArchive, isSubmitting }) {
  const handleAddChild = (childData) => {
    // Pass the pre-populated child data to the edit handler
    onEdit(childData);
  };

  if (!locations || locations.length === 0) {
    return (
      <div className="text-center py-12 fade-in">
        <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <h3 className="section-title text-gray-900 mb-2">No Locations</h3>
        <p className="descriptive-text">No locations to display</p>
      </div>
    );
  }

  return (
    <div className="content-spacing">
      {locations.map((location) => (
        <LocationNode
          key={location.location_id}
          location={location}
          level={0}
          onEdit={onEdit}
          onArchive={onArchive}
          onAddChild={handleAddChild}
          isSubmitting={isSubmitting}
        />
      ))}
    </div>
  );
}
