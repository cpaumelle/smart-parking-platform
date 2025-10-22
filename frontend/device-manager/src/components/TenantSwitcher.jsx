// src/components/TenantSwitcher.jsx
import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import authService from '../services/authService';

export default function TenantSwitcher() {
  const { user, currentTenant, switchTenant } = useAuth();
  const [availableTenants, setAvailableTenants] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    // Get available tenants from user data (populated during login)
    console.log('🏢 TenantSwitcher - user:', user);
    console.log('🏢 TenantSwitcher - user.tenants:', user?.tenants);
    if (user && user.tenants) {
      console.log('🏢 TenantSwitcher - Setting available tenants:', user.tenants.length);
      setAvailableTenants(user.tenants);
    } else {
      console.warn('⚠️ TenantSwitcher - No tenants found in user object');
    }
  }, [user]);

  const handleTenantSwitch = async (tenant) => {
    if (switching) return;  // Prevent double-clicks

    try {
      setSwitching(true);
      setIsOpen(false);

      console.log('🔄 Switching to tenant:', tenant.name, tenant.slug);

      // Call backend to get new token for this tenant
      const result = await authService.switchTenant(tenant.slug);

      // Update auth context
      switchTenant(result.tenants.find(t => t.slug === tenant.slug));

      // Reload page to refresh all data with new tenant context
      window.location.reload();
    } catch (error) {
      console.error('❌ Tenant switch failed:', error);
      alert('Failed to switch tenant: ' + error.message);
      setSwitching(false);
    }
  };

  // Determine role badge styling
  const getRoleBadge = (role) => {
    const badges = {
      platform_admin: {
        text: 'PLATFORM ADMIN',
        className: 'bg-purple-600 text-white font-bold'
      },
      owner: {
        text: 'OWNER',
        className: 'bg-blue-600 text-white'
      },
      admin: {
        text: 'ADMIN',
        className: 'bg-green-600 text-white'
      },
      operator: {
        text: 'OPERATOR',
        className: 'bg-yellow-600 text-white'
      },
      viewer: {
        text: 'VIEWER',
        className: 'bg-gray-600 text-white'
      }
    };
    return badges[role] || { text: role?.toUpperCase(), className: 'bg-gray-500 text-white' };
  };

  if (!currentTenant) {
    return null;
  }

  const roleBadge = getRoleBadge(currentTenant.role);
  const isPlatformAdmin = currentTenant.role === 'platform_admin';

  return (
    <div className="relative">
      {/* Tenant Switcher Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
          isPlatformAdmin
            ? 'border-purple-300 bg-purple-50 hover:bg-purple-100'
            : 'border-gray-300 bg-white hover:bg-gray-50'
        }`}
      >
        {/* Tenant Icon */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold ${
          isPlatformAdmin ? 'bg-purple-600' : 'bg-blue-600'
        }`}>
          {isPlatformAdmin ? '⚡' : currentTenant.name?.charAt(0) || 'T'}
        </div>

        {/* Tenant Info */}
        <div className="text-left">
          <div className="text-sm font-semibold text-gray-800">
            {currentTenant.name}
          </div>
          <div className={`text-xs px-2 py-0.5 rounded inline-block ${roleBadge.className}`}>
            {roleBadge.text}
          </div>
        </div>

        {/* Dropdown Arrow */}
        {availableTenants.length > 1 && (
          <svg
            className={`w-4 h-4 text-gray-600 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && availableTenants.length > 1 && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Menu */}
          <div className="absolute right-0 mt-2 w-72 bg-white border border-gray-200 rounded-lg shadow-xl z-20">
            <div className="p-2">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                Switch Tenant
              </div>
              {availableTenants.map((tenant) => {
                const isActive = tenant.id === currentTenant.id;
                const tenantRoleBadge = getRoleBadge(tenant.role);
                const isTenantPlatformAdmin = tenant.role === 'platform_admin';

                return (
                  <button
                    key={tenant.id}
                    onClick={() => !isActive && handleTenantSwitch(tenant)}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-left transition-colors ${
                      isActive
                        ? 'bg-blue-50 cursor-default'
                        : 'hover:bg-gray-50 cursor-pointer'
                    }`}
                  >
                    {/* Tenant Icon */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 ${
                      isTenantPlatformAdmin ? 'bg-purple-600' : 'bg-blue-600'
                    }`}>
                      {isTenantPlatformAdmin ? '⚡' : tenant.name?.charAt(0) || 'T'}
                    </div>

                    {/* Tenant Details */}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-800 truncate">
                        {tenant.name}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${tenantRoleBadge.className}`}>
                          {tenantRoleBadge.text}
                        </span>
                        {tenant.slug && (
                          <span className="text-xs text-gray-500 truncate">
                            {tenant.slug}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Active Indicator */}
                    {isActive && (
                      <svg className="w-5 h-5 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Footer Info */}
            <div className="border-t border-gray-100 px-3 py-2 text-xs text-gray-500">
              Logged in as: {user?.email}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
