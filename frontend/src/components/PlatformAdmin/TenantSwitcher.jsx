// frontend/src/components/PlatformAdmin/TenantSwitcher.jsx

import React, { useState } from 'react';
import { PLATFORM_TENANT_ID } from '../../config/featureFlags';

/**
 * TenantSwitcher - Allows platform admins to switch between tenant contexts
 * 
 * Features:
 * - Only visible to platform admins
 * - Switch to "Platform" view to see all tenants
 * - Switch to specific tenant view to see only that tenant's data
 * - Reloads page after switch to ensure clean state
 */
export function TenantSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  
  // TODO: Replace with actual hooks
  // const { data: currentTenant } = useCurrentTenant();
  // const { data: tenants } = useTenants();
  // const switchTenant = useSwitchTenant();
  
  const currentTenant = {
    id: PLATFORM_TENANT_ID,
    name: 'Platform',
    isPlatformAdmin: true
  };
  
  const tenants = [
    { id: PLATFORM_TENANT_ID, name: 'Platform', subscriptionTier: 'enterprise' },
    { id: '11111111-1111-1111-1111-111111111111', name: 'Acme Corp', subscriptionTier: 'pro' },
    { id: '22222222-2222-2222-2222-222222222222', name: 'TechStart', subscriptionTier: 'basic' },
  ];
  
  const handleSwitch = async (tenantId) => {
    try {
      // await switchTenant.mutateAsync(tenantId);
      setIsOpen(false);
      
      // Invalidate all cached data
      // queryClient.invalidateQueries();
      
      // Optionally reload the page for clean state
      if (tenantId === PLATFORM_TENANT_ID) {
        window.location.href = '/platform/dashboard';
      } else {
        window.location.href = '/dashboard';
      }
    } catch (error) {
      console.error('Failed to switch tenant:', error);
      // toast.error('Failed to switch tenant');
    }
  };
  
  // Only show for platform admins
  if (!currentTenant?.isPlatformAdmin) {
    return null;
  }
  
  return (
    <div className="relative inline-block text-left">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
      >
        <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
        {currentTenant.name}
        {currentTenant.id === PLATFORM_TENANT_ID && (
          <span className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">Platform</span>
        )}
        <svg className="ml-2 h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </button>
      
      {isOpen && (
        <div className="origin-top-right absolute right-0 mt-2 w-64 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5">
          <div className="py-1" role="menu">
            <div className="px-4 py-2 text-xs text-gray-500 font-semibold">Switch Tenant</div>
            
            {/* Platform Tenant Option */}
            <button
              onClick={() => handleSwitch(PLATFORM_TENANT_ID)}
              className={'block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ' + 
                (currentTenant.id === PLATFORM_TENANT_ID ? 'bg-blue-50' : '')}
            >
              <div className="flex items-center">
                <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
                Platform (All Tenants)
                {currentTenant.id === PLATFORM_TENANT_ID && (
                  <svg className="ml-auto h-4 w-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
            </button>
            
            <div className="border-t border-gray-100"></div>
            
            {/* Customer Tenants */}
            {tenants
              .filter(t => t.id !== PLATFORM_TENANT_ID)
              .map(tenant => (
                <button
                  key={tenant.id}
                  onClick={() => handleSwitch(tenant.id)}
                  className={'block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ' +
                    (currentTenant.id === tenant.id ? 'bg-blue-50' : '')}
                >
                  <div className="flex items-center">
                    <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    <span className="flex-1">{tenant.name}</span>
                    <span className="px-2 py-0.5 text-xs border border-gray-300 rounded">
                      {tenant.subscriptionTier}
                    </span>
                    {currentTenant.id === tenant.id && (
                      <svg className="ml-2 h-4 w-4 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
