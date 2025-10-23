// frontend/src/components/PlatformAdmin/DevicePoolManager.jsx

import React, { useState } from 'react';

/**
 * DevicePoolManager - Shows device distribution across all tenants
 * Platform admin only component
 */
export function DevicePoolManager() {
  const [selectedTenant, setSelectedTenant] = useState(null);
  
  // TODO: Replace with actual hook
  // const { data: stats, isLoading } = useDevicePoolStats();
  
  const isLoading = false;
  const stats = {
    totalDevices: 150,
    totalAssigned: 120,
    totalUnassigned: 30,
    byTenant: {
      'Acme Corp': { assigned: 45, unassigned: 5 },
      'TechStart': { assigned: 35, unassigned: 15 },
      'BuildCo': { assigned: 40, unassigned: 10 },
    }
  };
  
  if (isLoading) {
    return (
      <div className="animate-pulse">
        <div className="h-96 bg-gray-200 rounded"></div>
      </div>
    );
  }
  
  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Global Device Pool</h3>
        <p className="mt-1 text-sm text-gray-500">
          Manage device distribution across all tenants
        </p>
      </div>
      
      <div className="p-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Total Devices"
            value={stats?.totalDevices || 0}
            icon="cpu"
          />
          <StatCard
            title="Assigned"
            value={stats?.totalAssigned || 0}
            percentage={(stats?.totalAssigned / stats?.totalDevices) * 100}
            icon="link"
          />
          <StatCard
            title="Unassigned"
            value={stats?.totalUnassigned || 0}
            percentage={(stats?.totalUnassigned / stats?.totalDevices) * 100}
            icon="unlink"
          />
          <StatCard
            title="Active Tenants"
            value={Object.keys(stats?.byTenant || {}).length}
            icon="users"
          />
        </div>
        
        {/* Tenant Distribution Table */}
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tenant
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Assigned
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Unassigned
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Usage
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {Object.entries(stats?.byTenant || {}).map(([tenantName, data]) => {
                const total = data.assigned + data.unassigned;
                const usage = total > 0 ? (data.assigned / total) * 100 : 0;
                
                return (
                  <tr key={tenantName}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{tenantName}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{data.assigned}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{data.unassigned}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{total}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="w-20 bg-gray-200 rounded-full h-2 mr-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: usage + '%' }}
                          ></div>
                        </div>
                        <span className="text-sm text-gray-600">
                          {usage.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => setSelectedTenant(tenantName)}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, percentage, icon }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
          {percentage !== undefined && (
            <p className="text-sm text-gray-500">{percentage.toFixed(1)}%</p>
          )}
        </div>
        <div className="text-gray-400">
          {/* Icon placeholder */}
          <div className="w-8 h-8 bg-gray-300 rounded"></div>
        </div>
      </div>
    </div>
  );
}
