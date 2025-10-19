// src/components/environmental/MetricSelector.jsx
// Version: 1.0.0 - 2025-08-11 23:55:00 UTC
// Metric-first navigation component for environmental analytics
// Displays available metrics with sensor counts and coverage

import React from 'react';
import { Thermometer, Droplets, Wind } from 'lucide-react';

const MetricSelector = ({ 
  selectedMetric, 
  onMetricChange, 
  metricAvailability = {},
  sensorCapabilities = null,
  disabled = false,
  className = '',
  showCounts = true,
  showIcons = true
}) => {
  // Metric configuration with icons and display names
  const metricConfig = {
    temperature: {
      icon: Thermometer,
      label: 'Temperature',
      emoji: '🌡️',
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      borderColor: 'border-orange-200'
    },
    humidity: {
      icon: Droplets,
      label: 'Humidity',
      emoji: '💧',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200'
    },
    co2: {
      icon: Wind,
      label: 'CO2',
      emoji: '🫁',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200'
    }
  };

  // Get metric display text with sensor count
  const getMetricDisplayText = (metric) => {
    const config = metricConfig[metric];
    if (!config) return metric;

    const availability = metricAvailability[metric];
    const count = availability?.count || 0;
    
    if (showCounts && count > 0) {
      return `${config.emoji} ${config.label} (${count})`;
    }
    
    return `${config.emoji} ${config.label}`;
  };

  // Get metric availability status
  const getMetricStatus = (metric) => {
    const availability = metricAvailability[metric];
    if (!availability) return 'unknown';

    const count = availability.count || 0;
    const percentage = availability.percentage || 0;

    if (count === 0) return 'unavailable';
    if (percentage === 100) return 'full';
    if (percentage >= 50) return 'partial';
    return 'limited';
  };

  // Handle metric selection
  const handleMetricChange = (event) => {
    if (disabled) return;
    
    const newMetric = event.target.value;
    if (onMetricChange) {
      onMetricChange(newMetric);
    }
  };

  // Get status indicator color
  const getStatusColor = (status) => {
    switch (status) {
      case 'full': return 'text-green-600';
      case 'partial': return 'text-yellow-600';
      case 'limited': return 'text-orange-600';
      case 'unavailable': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  // Get status badge
  const getStatusBadge = (metric) => {
    const status = getMetricStatus(metric);
    const availability = metricAvailability[metric];
    const percentage = availability?.percentage || 0;

    if (status === 'unavailable') {
      return (
        <span className="text-xs text-red-600 ml-1">
          (No sensors)
        </span>
      );
    }

    if (status === 'full') {
      return (
        <span className="text-xs text-green-600 ml-1">
          (100%)
        </span>
      );
    }

    return (
      <span className={`text-xs ml-1 ${getStatusColor(status)}`}>
        ({percentage.toFixed(1)}%)
      </span>
    );
  };

  return (
    <div className={`metric-selector ${className}`}>
      {/* Label */}
      <label htmlFor="metric-select" className="block text-sm font-medium text-gray-700 mb-1">
        📊 Analyze
      </label>

      {/* Metric Selector */}
      <div className="relative">
        <select
          id="metric-select"
          value={selectedMetric}
          onChange={handleMetricChange}
          disabled={disabled}
          className={`
            block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
            ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white cursor-pointer'}
            text-sm font-medium
          `}
        >
          {Object.keys(metricConfig).map(metric => (
            <option key={metric} value={metric}>
              {getMetricDisplayText(metric)}
            </option>
          ))}
        </select>

        {/* Loading indicator */}
        {disabled && (
          <div className="absolute right-8 top-1/2 transform -translate-y-1/2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          </div>
        )}
      </div>

      {/* Metric Details */}
      {sensorCapabilities && (
        <div className="mt-2 text-xs text-gray-600">
          {Object.keys(metricConfig).map(metric => {
            const config = metricConfig[metric];
            const isSelected = metric === selectedMetric;
            const availability = metricAvailability[metric];
            const count = availability?.count || 0;
            
            return (
              <div
                key={metric}
                className={`
                  inline-flex items-center px-2 py-1 rounded-md mr-2 mb-1
                  ${isSelected ? `${config.bgColor} ${config.borderColor} border` : 'bg-gray-50'}
                  ${isSelected ? config.color : 'text-gray-600'}
                `}
              >
                {showIcons && React.createElement(config.icon, { 
                  className: `w-3 h-3 mr-1 ${isSelected ? config.color : 'text-gray-400'}` 
                })}
                <span className="font-medium">{config.label}</span>
                {showCounts && getStatusBadge(metric)}
              </div>
            );
          })}
        </div>
      )}

      {/* ASHRAE Standard Info for Selected Metric */}
      {sensorCapabilities && selectedMetric && (
        <div className="mt-2 p-2 bg-gray-50 rounded-md text-xs">
          <div className="font-medium text-gray-700 mb-1">
            ASHRAE Standard for {metricConfig[selectedMetric]?.label}:
          </div>
          <div className="text-gray-600">
            {getASHRAEStandardText(selectedMetric, sensorCapabilities)}
          </div>
        </div>
      )}
    </div>
  );
};

// Helper function to get ASHRAE standard text
const getASHRAEStandardText = (metric, capabilities) => {
  const metricCapability = capabilities.capabilities?.[metric];
  if (!metricCapability?.ashrae_standard) return 'No standard defined';

  const standard = metricCapability.ashrae_standard;
  
  if (metric === 'co2') {
    return `≤ ${standard.max} ${standard.unit} (Good air quality)`;
  } else {
    return `${standard.min}-${standard.max} ${standard.unit} (Comfort range)`;
  }
};

export default MetricSelector;
