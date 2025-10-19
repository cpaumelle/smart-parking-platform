// src/components/environmental/EnvironmentalTrends.jsx
// Version: 2.0.0 - Multi-Device Chart Support
// Last Updated: 2025-08-12 00:35:00 UTC
// Enhanced for multiple sensor lines with device selection

import React, { useState, useMemo } from 'react';
import {
 LineChart,
 Line,
 AreaChart,
 Area,
 XAxis,
 YAxis,
 CartesianGrid,
 Tooltip,
 Legend,
 ResponsiveContainer,
 ReferenceLine
} from 'recharts';
import {
 TrendingUp,
 TrendingDown,
 BarChart3,
 Activity,
 Thermometer,
 Droplets,
 Wind,
 Eye,
 EyeOff,
 MapPin,
 Cpu
} from 'lucide-react';

const EnvironmentalTrends = ({
 chartData = [],
 selectedMetric = 'temperature',
 selectedDevices = [],
 hours = 24,
 loading = false,
 error = null,
 sensorCapabilities = null,
 onChartTypeChange = null,
 className = ''
}) => {
 const [chartType, setChartType] = useState('line'); // 'line' or 'area'
 const [showMinMax, setShowMinMax] = useState(false);
 const [hiddenDevices, setHiddenDevices] = useState(new Set());
 const [groupBy, setGroupBy] = useState('none'); // 'none', 'location', 'device_type'

 // Enhanced color palette for multiple devices
 const deviceColors = [
   '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
   '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1',
   '#14b8a6', '#f43f5e', '#8d4ad8', '#0ea5e9', '#22c55e',
   '#a855f7', '#059669', '#dc2626', '#7c3aed', '#0891b2'
 ];

 // Metric configuration
 const metricConfig = {
   temperature: {
     icon: Thermometer,
     label: 'Temperature',
     unit: '°C',
     color: '#f97316',
     ashrae: { min: 20, max: 25 }
   },
   humidity: {
     icon: Droplets,
     label: 'Humidity',
     unit: '%',
     color: '#3b82f6',
     ashrae: { min: 40, max: 60 }
   },
   co2: {
     icon: Wind,
     label: 'CO2',
     unit: 'ppm',
     color: '#10b981',
     ashrae: { max: 1000 }
   }
 };

 // Get ASHRAE standards for current metric
 const getASHRAEStandards = () => {
   if (!sensorCapabilities?.capabilities?.[selectedMetric]?.ashrae_standard) {
     return metricConfig[selectedMetric]?.ashrae || {};
   }
   return sensorCapabilities.capabilities[selectedMetric].ashrae_standard;
 };

 // Get unique devices in chart data
 const devicesInChart = useMemo(() => {
   const devices = [...new Set(chartData.map(item => item.deveui))];
   return devices.map((deveui, index) => {
     const sample = chartData.find(item => item.deveui === deveui);
     return {
       deveui,
       device_name: sample?.device_name || deveui.slice(-6),
       device_type: sample?.device_type || 'Unknown',
       color: deviceColors[index % deviceColors.length],
       isVisible: !hiddenDevices.has(deveui)
     };
   });
 }, [chartData, hiddenDevices]);

 // Process chart data for Recharts with multiple devices
 const processedChartData = useMemo(() => {
   if (!chartData.length) return [];

   // Group data by time bucket
   const timeGroups = {};
   
   chartData.forEach(item => {
     const timeKey = item.timestamp;
     if (!timeGroups[timeKey]) {
       timeGroups[timeKey] = {
         timestamp: timeKey,
         timeDisplay: new Date(timeKey).toLocaleTimeString('en-US', {
           hour: '2-digit',
           minute: '2-digit',
           hour12: false
         }),
         dateDisplay: new Date(timeKey).toLocaleDateString('en-US', {
           month: 'short',
           day: 'numeric'
         })
       };
     }
     
     // Add device-specific data
     const deviceKey = `${item.deveui}_${selectedMetric}`;
     timeGroups[timeKey][deviceKey] = item[`${selectedMetric}_avg`];
     timeGroups[timeKey][`${deviceKey}_min`] = item[`${selectedMetric}_min`];
     timeGroups[timeKey][`${deviceKey}_max`] = item[`${selectedMetric}_max`];
     timeGroups[timeKey][`${item.deveui}_name`] = item.device_name || item.deveui.slice(-6);
   });

   return Object.values(timeGroups).sort((a, b) => a.timestamp - b.timestamp);
 }, [chartData, selectedMetric]);

 // Toggle device visibility
 const toggleDeviceVisibility = (deveui) => {
   const newHidden = new Set(hiddenDevices);
   if (newHidden.has(deveui)) {
     newHidden.delete(deveui);
   } else {
     newHidden.add(deveui);
   }
   setHiddenDevices(newHidden);
 };

 // Show/hide all devices
 const toggleAllDevices = (show) => {
   if (show) {
     setHiddenDevices(new Set());
   } else {
     setHiddenDevices(new Set(devicesInChart.map(d => d.deveui)));
   }
 };

 // Group devices by location or type
 const deviceGroups = useMemo(() => {
   if (groupBy === 'none') return { 'All Devices': devicesInChart };
   
   const groups = {};
   devicesInChart.forEach(device => {
     const groupKey = groupBy === 'location' 
       ? device.device_name.split(' ')[0] || 'Unknown Location'
       : device.device_type;
     
     if (!groups[groupKey]) groups[groupKey] = [];
     groups[groupKey].push(device);
   });
   
   return groups;
 }, [devicesInChart, groupBy]);

 // Custom tooltip component
 const CustomTooltip = ({ active, payload, label }) => {
   if (!active || !payload || !payload.length) return null;

   const config = metricConfig[selectedMetric];
   const ashrae = getASHRAEStandards();

   return (
     <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg max-w-xs">
       <p className="text-sm text-gray-600 mb-2">
         {label} • {payload[0]?.payload?.dateDisplay}
       </p>

       <div className="space-y-1 max-h-48 overflow-y-auto">
         {payload.map((entry, index) => {
           const deveui = entry.dataKey.split('_')[0];
           const deviceName = entry.payload[`${deveui}_name`] || deveui.slice(-6);
           
           return (
             <div key={index} className="flex items-center justify-between text-xs">
               <div className="flex items-center">
                 <div 
                   className="w-2 h-2 rounded-full mr-2" 
                   style={{ backgroundColor: entry.color }}
                 />
                 <span className="truncate max-w-20">{deviceName}</span>
               </div>
               <span className="font-medium ml-2">
                 {entry.value?.toFixed(1)} {config?.unit}
               </span>
             </div>
           );
         })}
       </div>

       {/* ASHRAE Compliance */}
       {ashrae && (
         <div className="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-600">
           <div>ASHRAE: {selectedMetric === 'co2' ? `≤ ${ashrae.max}` : `${ashrae.min}-${ashrae.max}`} {config?.unit}</div>
         </div>
       )}
     </div>
   );
 };

 // Handle chart type change
 const handleChartTypeChange = (newType) => {
   setChartType(newType);
   if (onChartTypeChange) {
     onChartTypeChange(newType);
   }
 };

 const config = metricConfig[selectedMetric];
 const ashrae = getASHRAEStandards();
 const visibleDevices = devicesInChart.filter(d => d.isVisible);

 if (loading) {
   return (
     <div className={`environmental-trends ${className}`}>
       <div className="flex items-center justify-center p-8">
         <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
         <span className="ml-3 text-gray-600">Loading trend data...</span>
       </div>
     </div>
   );
 }

 if (error) {
   return (
     <div className={`environmental-trends ${className}`}>
       <div className="bg-red-50 border border-red-200 rounded-md p-4">
         <div className="flex items-center">
           <TrendingDown className="h-5 w-5 text-red-600 mr-2" />
           <span className="text-red-800 font-medium">Failed to load trend data</span>
         </div>
         <p className="text-red-700 text-sm mt-1">{error.message}</p>
       </div>
     </div>
   );
 }

 return (
   <div className={`environmental-trends ${className}`}>
     {/* Enhanced Header with Controls */}
     <div className="flex flex-col space-y-4 mb-6">
       <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
         <div className="flex items-center">
           {config && React.createElement(config.icon, {
             className: 'w-5 h-5 mr-2',
             style: { color: config.color }
           })}
           <h3 className="text-lg font-semibold text-gray-900">
             {config?.label} Trends ({hours}h) - {visibleDevices.length}/{devicesInChart.length} sensors
           </h3>
         </div>

         {/* Chart Controls */}
         <div className="flex items-center space-x-2">
           {/* Group By Selector */}
           <select
             value={groupBy}
             onChange={(e) => setGroupBy(e.target.value)}
             className="text-sm border border-gray-300 rounded px-2 py-1"
           >
             <option value="none">All Devices</option>
             <option value="device_type">Group by Type</option>
             <option value="location">Group by Location</option>
           </select>

           {/* Visibility Controls */}
           <button
             onClick={() => toggleAllDevices(visibleDevices.length === 0)}
             className="text-sm px-2 py-1 border border-gray-300 rounded hover:bg-gray-50"
           >
             {visibleDevices.length === 0 ? 'Show All' : 'Hide All'}
           </button>

           {/* Min/Max Toggle */}
           <label className="flex items-center text-sm">
             <input
               type="checkbox"
               checked={showMinMax}
               onChange={(e) => setShowMinMax(e.target.checked)}
               className="mr-1"
             />
             Min/Max
           </label>

           {/* Chart Type Selector */}
           <div className="flex bg-gray-100 rounded-md p-1">
             <button
               onClick={() => handleChartTypeChange('line')}
               className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                 chartType === 'line'
                   ? 'bg-white text-blue-600 shadow-sm'
                   : 'text-gray-600 hover:text-gray-900'
               }`}
             >
               <Activity className="w-4 h-4" />
             </button>
             <button
               onClick={() => handleChartTypeChange('area')}
               className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                 chartType === 'area'
                   ? 'bg-white text-blue-600 shadow-sm'
                   : 'text-gray-600 hover:text-gray-900'
               }`}
             >
               <BarChart3 className="w-4 h-4" />
             </button>
           </div>
         </div>
       </div>

       {/* Device Selection Grid */}
       <div className="bg-gray-50 rounded-lg p-4">
         {Object.entries(deviceGroups).map(([groupName, devices]) => (
           <div key={groupName} className="mb-4 last:mb-0">
             {groupBy !== 'none' && (
               <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                 {groupBy === 'location' ? <MapPin className="w-4 h-4 mr-1" /> : <Cpu className="w-4 h-4 mr-1" />}
                 {groupName}
               </h4>
             )}
             <div className="flex flex-wrap gap-2">
               {devices.map(device => (
                 <button
                   key={device.deveui}
                   onClick={() => toggleDeviceVisibility(device.deveui)}
                   className={`inline-flex items-center px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                     device.isVisible
                       ? 'bg-white border-2 shadow-sm'
                       : 'bg-gray-200 border-2 border-gray-300 opacity-50'
                   }`}
                   style={{
                     borderColor: device.isVisible ? device.color : 'transparent',
                     color: device.isVisible ? device.color : '#6b7280'
                   }}
                 >
                   {device.isVisible ? <Eye className="w-3 h-3 mr-1" /> : <EyeOff className="w-3 h-3 mr-1" />}
                   <div
                     className="w-2 h-2 rounded-full mr-2"
                     style={{ backgroundColor: device.isVisible ? device.color : '#9ca3af' }}
                   />
                   <span className="truncate max-w-24">{device.device_name}</span>
                 </button>
               ))}
             </div>
           </div>
         ))}
       </div>
     </div>

     {/* Chart */}
     {processedChartData.length > 0 && visibleDevices.length > 0 ? (
       <div className="bg-white border border-gray-200 rounded-lg p-4">
         <ResponsiveContainer width="100%" height={400}>
           {chartType === 'area' ? (
             <AreaChart data={processedChartData}>
               <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
               <XAxis
                 dataKey="timeDisplay"
                 stroke="#6b7280"
                 fontSize={12}
                 interval="preserveStartEnd"
               />
               <YAxis
                 stroke="#6b7280"
                 fontSize={12}
                 label={{
                   value: config?.unit || '',
                   angle: -90,
                   position: 'insideLeft',
                   style: { textAnchor: 'middle' }
                 }}
               />
               <Tooltip content={<CustomTooltip />} />
               <Legend />

               {/* ASHRAE Reference Lines */}
               {ashrae.min && (
                 <ReferenceLine
                   y={ashrae.min}
                   stroke="#10b981"
                   strokeDasharray="5 5"
                   label={{ value: `Min: ${ashrae.min}`, position: "insideTopRight" }}
                 />
               )}
               {ashrae.max && (
                 <ReferenceLine
                   y={ashrae.max}
                   stroke="#ef4444"
                   strokeDasharray="5 5"
                   label={{ value: `Max: ${ashrae.max}`, position: "insideTopRight" }}
                 />
               )}

               {/* Device Areas */}
               {visibleDevices.map((device, index) => (
                 <Area
                   key={device.deveui}
                   type="monotone"
                   dataKey={`${device.deveui}_${selectedMetric}`}
                   stroke={device.color}
                   fill={device.color}
                   fillOpacity={0.3}
                   strokeWidth={2}
                   name={device.device_name}
                 />
               ))}
             </AreaChart>
           ) : (
             <LineChart data={processedChartData}>
               <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
               <XAxis
                 dataKey="timeDisplay"
                 stroke="#6b7280"
                 fontSize={12}
                 interval="preserveStartEnd"
               />
               <YAxis
                 stroke="#6b7280"
                 fontSize={12}
                 label={{
                   value: config?.unit || '',
                   angle: -90,
                   position: 'insideLeft',
                   style: { textAnchor: 'middle' }
                 }}
               />
               <Tooltip content={<CustomTooltip />} />
               <Legend />

               {/* ASHRAE Reference Lines */}
               {ashrae.min && (
                 <ReferenceLine
                   y={ashrae.min}
                   stroke="#10b981"
                   strokeDasharray="5 5"
                   label={{ value: `Min: ${ashrae.min}`, position: "insideTopRight" }}
                 />
               )}
               {ashrae.max && (
                 <ReferenceLine
                   y={ashrae.max}
                   stroke="#ef4444"
                   strokeDasharray="5 5"
                   label={{ value: `Max: ${ashrae.max}`, position: "insideTopRight" }}
                 />
               )}

               {/* Device Lines */}
               {visibleDevices.map((device, index) => (
                 <Line
                   key={device.deveui}
                   type="monotone"
                   dataKey={`${device.deveui}_${selectedMetric}`}
                   stroke={device.color}
                   strokeWidth={2}
                   dot={{ fill: device.color, strokeWidth: 2, r: 3 }}
                   activeDot={{ r: 5, stroke: device.color, strokeWidth: 2 }}
                   name={device.device_name}
                   connectNulls={false}
                 />
               ))}
             </LineChart>
           )}
         </ResponsiveContainer>
       </div>
     ) : (
       <div className="text-center py-8 bg-gray-50 rounded-lg">
         <TrendingUp className="mx-auto h-12 w-12 text-gray-400 mb-4" />
         <h3 className="text-lg font-medium text-gray-900 mb-2">No Trend Data Available</h3>
         <p className="text-gray-600">
           {devicesInChart.length === 0 
             ? `No historical data found for ${config?.label?.toLowerCase()} in the last ${hours} hours.`
             : `All sensors are hidden. Click "Show All" to display data.`
           }
         </p>
       </div>
     )}
   </div>
 );
};

export default EnvironmentalTrends;
