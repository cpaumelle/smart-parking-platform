// src/components/environmental/EnvironmentalDashboard.jsx
// Version: 1.0.0 - 2025-08-11 23:58:00 UTC
// Real-time environmental readings dashboard with ASHRAE compliance
// Displays current readings with status indicators and health information

import React from 'react';
import { 
  Thermometer, 
  Droplets, 
  Wind, 
  AlertTriangle, 
  CheckCircle, 
  Clock,
  Battery,
  Wifi,
  WifiOff,
  BarChart3
} from 'lucide-react';

const EnvironmentalDashboard = ({ 
  environmentalData = [],
  deviceHealth = [],
  selectedMetric = 'temperature',
  loading = false,
  error = null,
  lastUpdated = null,
  onRefresh = null,
  className = ''
}) => {
  // Get ASHRAE compliance status color
  const getComplianceColor = (ashrae) => {
    if (!ashrae || ashrae.status === 'unknown') return 'text-gray-500';
    return ashrae.status === 'good' ? 'text-green-600' : 'text-red-600';
  };

  // Get ASHRAE compliance icon
  const getComplianceIcon = (ashrae) => {
    if (!ashrae || ashrae.status === 'unknown') return Clock;
    return ashrae.status === 'good' ? CheckCircle : AlertTriangle;
  };

  // Get metric icon
  const getMetricIcon = (metric) => {
    const icons = {
      temperature: Thermometer,
      humidity: Droplets,
      co2: Wind
    };
    return icons[metric] || Thermometer;
  };

  // Get battery status color
  const getBatteryColor = (status) => {
    switch (status) {
      case 'good': return 'text-green-600';
      case 'low': return 'text-yellow-600';
      case 'critical': return 'text-red-600';
      default: return 'text-gray-500';
    }
  };

  // Get connectivity status
  const getConnectivityInfo = (device) => {
    const minutesSince = device.status?.minutes_since_reading || 0;
    
    if (minutesSince < 60) {
      return { status: 'online', color: 'text-green-600', icon: Wifi, text: 'Online' };
    } else if (minutesSince < 360) {
      return { status: 'delayed', color: 'text-yellow-600', icon: Wifi, text: 'Delayed' };
    } else {
      return { status: 'offline', color: 'text-red-600', icon: WifiOff, text: 'Offline' };
    }
  };

  // Get device health info by deveui
  const getDeviceHealthInfo = (deveui) => {
    return deviceHealth.find(health => health.deveui === deveui);
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Get last updated text
  const getLastUpdatedText = () => {
    if (!lastUpdated) return 'Never';
    const now = new Date();
    const diff = Math.floor((now - lastUpdated) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  if (loading) {
    return (
      <div className={`environmental-dashboard ${className}`}>
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading environmental data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`environmental-dashboard ${className}`}>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-red-600 mr-2" />
            <span className="text-red-800 font-medium">Failed to load environmental data</span>
          </div>
          <p className="text-red-700 text-sm mt-1">{error.message}</p>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="mt-2 px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`environmental-dashboard ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">
          Real-time Environmental Readings
        </h3>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-500">
            Last updated: {getLastUpdatedText()}
          </span>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Refresh
            </button>
          )}
        </div>
      </div>

      {/* Environmental Data Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {environmentalData.map(device => {
          const healthInfo = getDeviceHealthInfo(device.deveui);
          const connectivity = getConnectivityInfo(device);
          const MetricIcon = getMetricIcon(selectedMetric);

          return (
            <div
              key={device.deveui}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              {/* Device Header */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h4 className="font-medium text-gray-900 truncate">
                    {device.device_name || device.deveui}
                  </h4>
                  <p className="text-sm text-gray-500">{device.device_type}</p>
                </div>
                <div className="flex items-center space-x-1">
                  {/* Connectivity Status */}
                  <div className={`${connectivity.color}`} title={connectivity.text}>
                    {React.createElement(connectivity.icon, { className: 'w-4 h-4' })}
                  </div>
                  {/* Battery Status */}
                  {healthInfo?.battery && (
                    <div 
                      className={getBatteryColor(healthInfo.battery.status)}
                      title={`Battery: ${healthInfo.battery.level}${healthInfo.battery.unit} (${healthInfo.battery.status})`}
                    >
                      <Battery className="w-4 h-4" />
                    </div>
                  )}
                </div>
              </div>

              {/* Environmental Metrics */}
              <div className="space-y-3">
                {/* Temperature */}
                {device.temperature?.value !== null && device.temperature?.value !== undefined && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <Thermometer className="w-4 h-4 text-orange-600 mr-2" />
                      <span className="text-sm text-gray-600">Temperature</span>
                    </div>
                    <div className="flex items-center">
                      <span className="font-medium text-gray-900">
                        {device.temperature.value}°C
                      </span>
                      {device.temperature.ashrae && (
                        <div className={`ml-2 ${getComplianceColor(device.temperature.ashrae)}`}>
                          {React.createElement(getComplianceIcon(device.temperature.ashrae), { 
                            className: 'w-4 h-4' 
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Humidity */}
                {device.humidity?.value !== null && device.humidity?.value !== undefined && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <Droplets className="w-4 h-4 text-blue-600 mr-2" />
                      <span className="text-sm text-gray-600">Humidity</span>
                    </div>
                    <div className="flex items-center">
                      <span className="font-medium text-gray-900">
                        {device.humidity.value}%
                      </span>
                      {device.humidity.ashrae && (
                        <div className={`ml-2 ${getComplianceColor(device.humidity.ashrae)}`}>
                          {React.createElement(getComplianceIcon(device.humidity.ashrae), { 
                            className: 'w-4 h-4' 
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* CO2 */}
                {device.co2?.value !== null && device.co2?.value !== undefined && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <Wind className="w-4 h-4 text-green-600 mr-2" />
                      <span className="text-sm text-gray-600">CO2</span>
                    </div>
                    <div className="flex items-center">
                      <span className="font-medium text-gray-900">
                        {device.co2.value} ppm
                      </span>
                      {device.co2.ashrae && (
                        <div className={`ml-2 ${getComplianceColor(device.co2.ashrae)}`}>
                          {React.createElement(getComplianceIcon(device.co2.ashrae), { 
                            className: 'w-4 h-4' 
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Status Footer */}
              <div className="mt-3 pt-3 border-t border-gray-100">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>
                    {formatTimestamp(device.timestamp)}
                  </span>
                  <span className={`
                    px-2 py-1 rounded-full text-xs font-medium
                    ${device.status?.environmental_status === 'ok' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                    }
                  `}>
                    {device.status?.environmental_status || 'Unknown'}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty State */}
      {environmentalData.length === 0 && (
        <div className="text-center py-8">
          <BarChart3 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Environmental Data</h3>
          <p className="text-gray-600">No devices found for the selected metric.</p>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Refresh Data
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default EnvironmentalDashboard;
