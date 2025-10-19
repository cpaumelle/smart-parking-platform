/*
 * SenseMy IoT Platform - Analytics Dashboard
 * Version: 3.0.0 - Environmental Analytics Migration
 * Last Updated: 2025-08-11 23:58:00 UTC
 * Author: SenseMy IoT Development Team
 *
 * Changelog:
 * - Migrated from occupancy analytics to environmental analytics
 * - Fixed TypeError: recentTraffic undefined
 * - Updated to use useEnvironmental hook instead of useAnalytics
 * - Added environmental metrics display (temperature, humidity, CO2)
 * - Added device health monitoring with battery status
 * - Added ASHRAE compliance indicators
 * - Removed legacy occupancy code that was causing errors
 * - Responsive design maintained with environmental focus
 */

import React, { useState } from 'react';
import {
  BarChart3,
  Users,
  Activity,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Clock,
  TrendingUp,
  TrendingDown,
  Wifi,
  WifiOff,
  Thermometer,
  Droplets,
  Wind,
  Battery,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';

// Import environmental hook instead of analytics hook
import { useEnvironmental } from '../hooks/useEnvironmental.js';
import VersionInfo from "../components/common/VersionInfo.jsx";

const Analytics = () => {
  // Use environmental hook for current environmental analytics platform
  const {
    processedLatestReadings,
    deviceHealth,
    metricAvailability,
    environmentalHourly,
    sensorCapabilities,
    loading,
    isLoading,
    error,
    lastUpdated,
    hasData,
    refreshAll
  } = useEnvironmental({
    autoRefresh: true,
    refreshInterval: 60000, // 1 minute
    hours: 24
  });

  const [refreshing, setRefreshing] = useState(false);

  // Handle manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshAll();
    } finally {
      setRefreshing(false);
    }
  };

  // Compute environmental statistics
  const environmentalStats = {
    totalSensors: processedLatestReadings.length,
    activeSensors: processedLatestReadings.filter(d => 
      d.status?.environmental_status === 'ok'
    ).length,
    temperatureSensors: metricAvailability.temperature?.count || 0,
    humiditySensors: metricAvailability.humidity?.count || 0,
    co2Sensors: metricAvailability.co2?.count || 0,
    healthyDevices: deviceHealth.filter(d => d.overall_health === 'healthy').length,
    totalHealthMonitored: deviceHealth.length
  };

  // Get last updated text
  const getLastUpdatedText = () => {
    if (!lastUpdated) return 'Never';
    const now = new Date();
    const diffMinutes = Math.floor((now - lastUpdated) / (1000 * 60));
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes === 1) return '1 minute ago';
    if (diffMinutes < 60) return `${diffMinutes} minutes ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours === 1) return '1 hour ago';
    return `${diffHours} hours ago`;
  };

  // Get status color for environmental readings
  const getStatusColor = (status) => {
    switch (status) {
      case 'ok': return 'text-green-600 bg-green-50 border-green-200';
      case 'sensor_error': return 'text-red-600 bg-red-50 border-red-200';
      case 'stale_data': return 'text-orange-600 bg-orange-50 border-orange-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  // Get health status color
  const getHealthColor = (health) => {
    switch (health) {
      case 'healthy': return 'text-green-600';
      case 'warning': return 'text-orange-600';
      case 'critical': return 'text-red-600';
      case 'offline': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  // Get ASHRAE compliance indicator
  const getASHRAEIndicator = (ashrae) => {
    if (!ashrae) return null;
    
    return ashrae.compliant ? (
      <ShieldCheck className="w-4 h-4 text-green-500" title={ashrae.message} />
    ) : (
      <ShieldAlert className="w-4 h-4 text-red-500" title={ashrae.message} />
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header with Version Info */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Environmental Analytics</h1>
          <p className="descriptive-text">Real-time environmental monitoring and sensor health</p>
        </div>
        
        <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-2 sm:space-y-0 sm:space-x-4">
          <VersionInfo />
          <button
            onClick={handleRefresh}
            disabled={refreshing || isLoading}
            className={`btn-primary ${refreshing || isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="responsive-card bg-red-50 border-red-200 fade-in">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-red-800">Error Loading Analytics</h3>
              <p className="text-sm text-red-700 mt-1">
                {error.userMessage || error.message || 'An error occurred while loading environmental data'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Environmental Statistics Cards */}
      <div className="analytics-stats-grid">
        <div className="stat-card fade-in">
          <div className="flex items-center justify-between w-full lg:flex-col lg:items-start">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Sensors</p>
              <p className="stat-number text-blue-600">
                {environmentalStats.activeSensors}/{environmentalStats.totalSensors}
              </p>
            </div>
            <Activity className="w-8 h-8 text-blue-400 flex-shrink-0" />
          </div>
        </div>

        <div className="stat-card fade-in">
          <div className="flex items-center justify-between w-full lg:flex-col lg:items-start">
            <div>
              <p className="text-sm font-medium text-gray-600">Temperature Sensors</p>
              <p className="stat-number text-green-600">{environmentalStats.temperatureSensors}</p>
            </div>
            <Thermometer className="w-8 h-8 text-green-400 flex-shrink-0" />
          </div>
        </div>

        <div className="stat-card fade-in">
          <div className="flex items-center justify-between w-full lg:flex-col lg:items-start">
            <div>
              <p className="text-sm font-medium text-gray-600">Humidity Sensors</p>
              <p className="stat-number text-blue-600">{environmentalStats.humiditySensors}</p>
            </div>
            <Droplets className="w-8 h-8 text-blue-400 flex-shrink-0" />
          </div>
        </div>

        <div className="stat-card fade-in">
          <div className="flex items-center justify-between w-full lg:flex-col lg:items-start">
            <div>
              <p className="text-sm font-medium text-gray-600">CO2 Sensors</p>
              <p className="stat-number text-purple-600">{environmentalStats.co2Sensors}</p>
            </div>
            <Wind className="w-8 h-8 text-purple-400 flex-shrink-0" />
          </div>
        </div>
      </div>

      {/* Environmental Sensor Grid */}
      <div className="responsive-card fade-in">
        <div className="flex items-center justify-between border-b border-gray-200 pb-4 mb-6">
          <h2 className="section-title">Environmental Sensors</h2>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Clock className="w-4 h-4" />
            <span>Updated {getLastUpdatedText()}</span>
          </div>
        </div>

        {processedLatestReadings.length > 0 ? (
          <div className="device-grid">
            {processedLatestReadings.map((sensor) => (
              <div
                key={sensor.deveui}
                className={`device-card gpu-accelerated ${getStatusColor(sensor.status?.environmental_status)}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900 mb-1">
                      {sensor.device_name || `Device ${sensor.deveui.slice(-6)}`}
                    </h3>
                    <p className="text-xs text-gray-500 mb-1">{sensor.device_type}</p>
                    <code className="text-xs text-gray-500 bg-white px-2 py-1 rounded font-mono">
                      {sensor.deveui}
                    </code>
                  </div>
                  {sensor.status?.environmental_status === 'ok' ? (
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                  )}
                </div>

                <div className="space-y-3">
                  {/* Temperature */}
                  {sensor.temperature && (
                    <div className="flex justify-between items-center">
                      <div className="flex items-center space-x-2">
                        <Thermometer className="w-4 h-4 text-red-400" />
                        <span className="descriptive-text">Temperature:</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">
                          {sensor.temperature.value?.toFixed(1)}°C
                        </span>
                        {getASHRAEIndicator(sensor.temperature.ashrae)}
                      </div>
                    </div>
                  )}

                  {/* Humidity */}
                  {sensor.humidity && (
                    <div className="flex justify-between items-center">
                      <div className="flex items-center space-x-2">
                        <Droplets className="w-4 h-4 text-blue-400" />
                        <span className="descriptive-text">Humidity:</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">
                          {sensor.humidity.value?.toFixed(1)}%
                        </span>
                        {getASHRAEIndicator(sensor.humidity.ashrae)}
                      </div>
                    </div>
                  )}

                  {/* CO2 */}
                  {sensor.co2 && (
                    <div className="flex justify-between items-center">
                      <div className="flex items-center space-x-2">
                        <Wind className="w-4 h-4 text-purple-400" />
                        <span className="descriptive-text">CO2:</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">
                          {sensor.co2.value?.toFixed(0)} ppm
                        </span>
                        {getASHRAEIndicator(sensor.co2.ashrae)}
                      </div>
                    </div>
                  )}

                  {/* Data Freshness */}
                  <div className="flex justify-between items-center">
                    <span className="descriptive-text">Status:</span>
                    <span className={`text-sm font-medium ${
                      sensor.status?.environmental_status === 'ok' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {sensor.status?.data_freshness || 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <BarChart3 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="section-title text-gray-900 mb-2">No Environmental Data</h3>
            <p className="descriptive-text max-w-md mx-auto">
              {isLoading ? 'Loading environmental sensors...' : 'No environmental sensors found with recent data.'}
            </p>
          </div>
        )}
      </div>

      {/* Device Health Monitor */}
      {deviceHealth.length > 0 && (
        <div className="responsive-card fade-in">
          <div className="border-b border-gray-200 pb-4 mb-6">
            <h2 className="section-title">Device Health Monitor</h2>
            <p className="descriptive-text">Battery and connectivity status</p>
          </div>

          <div className="device-grid">
            {deviceHealth.slice(0, 12).map((device) => (
              <div
                key={device.deveui}
                className={`device-card gpu-accelerated border-gray-200 bg-gray-50`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900 mb-1">
                      {device.device_name || `Device ${device.deveui.slice(-6)}`}
                    </h3>
                    <p className="text-xs text-gray-500 mb-1">{device.device_type}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    {device.connectivity?.status === 'online' ? (
                      <Wifi className="w-4 h-4 text-green-500" />
                    ) : (
                      <WifiOff className="w-4 h-4 text-gray-400" />
                    )}
                    <Battery className={`w-4 h-4 ${
                      device.battery?.status === 'good' ? 'text-green-500' :
                      device.battery?.status === 'low' ? 'text-orange-500' : 'text-red-500'
                    }`} />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="descriptive-text">Battery:</span>
                    <span className={`text-sm font-medium ${
                      device.battery?.status === 'good' ? 'text-green-600' :
                      device.battery?.status === 'low' ? 'text-orange-600' : 'text-red-600'
                    }`}>
                      {device.battery?.level}% ({device.battery?.status})
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="descriptive-text">Health:</span>
                    <span className={`text-sm font-medium ${getHealthColor(device.overall_health)}`}>
                      {device.overall_health}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Environmental Readings Table */}
      {environmentalHourly.length > 0 && (
        <div className="responsive-card fade-in">
          <div className="border-b border-gray-200 pb-4 mb-6">
            <h2 className="section-title">Recent Environmental Readings</h2>
          </div>

          <div className="table-responsive">
            <table className="table-styled">
              <thead className="table-header">
                <tr>
                  <th>Device</th>
                  <th>Time</th>
                  <th className="hidden sm:table-cell">Temperature</th>
                  <th className="hidden sm:table-cell">Humidity</th>
                  <th className="hidden sm:table-cell">CO2</th>
                  <th>Readings</th>
                </tr>
              </thead>
              <tbody className="table-body">
                {environmentalHourly.slice(0, 10).map((record, index) => (
                  <tr key={`${record.deveui}-${record.hour_bucket}-${index}`} className="hover:bg-gray-50">
                    <td>
                      <div className="font-medium text-gray-900">
                        {record.device_name || record.deveui.slice(-6)}
                      </div>
                      <div className="sm:hidden text-xs text-gray-500 mt-1">
                        {record.temperature && `T: ${record.temperature.avg?.toFixed(1)}°C`}
                        {record.humidity && ` H: ${record.humidity.avg?.toFixed(0)}%`}
                        {record.co2 && ` CO2: ${record.co2.avg?.toFixed(0)}`}
                      </div>
                    </td>
                    <td className="descriptive-text">
                      <div className="hidden sm:block">
                        {new Date(record.hour_bucket).toLocaleString()}
                      </div>
                      <div className="sm:hidden">
                        {new Date(record.hour_bucket).toLocaleDateString()}
                        <br />
                        {new Date(record.hour_bucket).toLocaleTimeString()}
                      </div>
                    </td>
                    <td className="hidden sm:table-cell">
                      {record.temperature ? (
                        <span className="text-gray-900 font-medium">
                          {record.temperature.avg?.toFixed(1)}°C
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="hidden sm:table-cell">
                      {record.humidity ? (
                        <span className="text-blue-600 font-medium">
                          {record.humidity.avg?.toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="hidden sm:table-cell">
                      {record.co2 ? (
                        <span className="text-purple-600 font-medium">
                          {record.co2.avg?.toFixed(0)} ppm
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        {record.metadata?.reading_count || 0} readings
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Analytics;
