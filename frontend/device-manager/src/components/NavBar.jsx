import TenantSwitcher from './TenantSwitcher';
import { useAuth } from '../contexts/AuthContext';

export default function NavBar() {
  const { isAuthenticated } = useAuth();

  return (
    <header className="bg-white border-b px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between">
        {/* Logo/Title */}
        <div className="font-semibold text-lg text-gray-800">
          SenseMy IoT Platform
        </div>

        {/* Tenant Switcher (only show when authenticated) */}
        {isAuthenticated && (
          <div className="flex items-center gap-4">
            <TenantSwitcher />
          </div>
        )}
      </div>
    </header>
  );
}
