// src/components/PlatformAdminBanner.jsx
import { useAuth } from '../contexts/AuthContext';

export default function PlatformAdminBanner() {
  const { currentTenant } = useAuth();

  // Only show for platform admins
  if (!currentTenant || currentTenant.role !== 'platform_admin') {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-4 py-2 shadow-md">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Icon */}
          <div className="w-8 h-8 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
            <span className="text-xl">⚡</span>
          </div>

          {/* Message */}
          <div>
            <div className="font-bold text-sm">
              Platform Admin Mode
            </div>
            <div className="text-xs text-purple-100">
              You are viewing data across ALL tenants. Changes will affect the entire platform.
            </div>
          </div>
        </div>

        {/* Info Badge */}
        <div className="hidden sm:flex items-center gap-2 bg-white bg-opacity-10 px-3 py-1 rounded-full">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-xs font-medium">
            Cross-Tenant View Active
          </span>
        </div>
      </div>
    </div>
  );
}
