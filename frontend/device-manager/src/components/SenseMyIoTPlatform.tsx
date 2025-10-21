// 10-ui-frontend/sensemy-platform/src/components/SenseMyIoTPlatform.tsx
// Version: 2.2.0 - 2025-10-13
// Changelog:
// - Added ChirpStack Device Manager navigation item
// - Integrated ChirpStack device management page

import React, { useState, useEffect, useCallback } from 'react';
import VersionInfo from "../components/common/VersionInfo.jsx";
import { useAuth } from "../contexts/AuthContext.jsx";
import {
  Wifi,
  MapPin,
  Settings,
  BarChart3,
  Users,
  Menu,
  X,
  Home,
  ChevronLeft,
  ChevronRight,
  Radio,
  Car,
  Building2,
  LogOut,
  User as UserIcon
} from 'lucide-react';

// Import real page implementations
import Dashboard from "../components/Dashboard.jsx";
import Devices from "../pages/Devices.jsx";
import Gateways from "../pages/Gateways.jsx";
import Sites from "../pages/Sites.jsx";
import ParkingSpaces from "../pages/ParkingSpaces.jsx";
import Analytics from "../pages/Analytics.jsx";
// ChirpStack Manager removed - use ChirpStack admin UI directly
// import ChirpStackDevices from "../pages/ChirpStackDevices.jsx";

// Custom hook for sidebar state management
const useSidebar = () => {
  const [isOpen, setIsOpen] = useState(() => {
    // Desktop default: open, Mobile default: closed
    const stored = localStorage.getItem('sidebar-open');
    if (stored !== null) return JSON.parse(stored);
    return window.innerWidth >= 1024; // lg breakpoint
  });

  const toggle = useCallback(() => {
    setIsOpen(prev => {
      const newState = !prev;
      localStorage.setItem('sidebar-open', JSON.stringify(newState));
      return newState;
    });
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    localStorage.setItem('sidebar-open', 'false');
  }, []);

  const open = useCallback(() => {
    setIsOpen(true);
    localStorage.setItem('sidebar-open', 'true');
  }, []);

  return { isOpen, toggle, close, open };
};

const SenseMyIoTPlatform: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [pageFilters, setPageFilters] = useState<Record<string, any>>({});
  const [showUserMenu, setShowUserMenu] = useState(false);
  const sidebar = useSidebar();
  const { user, currentTenant, logout } = useAuth();

  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home, disabled: false },
    { id: 'sites', label: 'Sites', icon: Building2, disabled: false },
    { id: 'parking', label: 'Parking Spaces', icon: Car, disabled: false },
    { id: 'devices', label: 'Devices', icon: Wifi, disabled: false },
    { id: 'gateways', label: 'Gateways', icon: Settings, disabled: false },
    { id: 'analytics', label: 'Analytics', icon: BarChart3, disabled: false },
    // ChirpStack Manager removed - use ChirpStack admin UI directly for device registration
    // { id: 'chirpstack', label: 'ChirpStack Manager', icon: Radio, disabled: false },
    { id: 'users', label: 'Users', icon: Users, disabled: true },
  ];

  // Handle navigation with filters from dashboard
  const handleNavigate = (page: string, filters?: Record<string, any>) => {
    setActiveTab(page);
    setPageFilters(filters || {});
    // Auto-close sidebar on mobile
    if (window.innerWidth < 1024) {
      sidebar.close();
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard onNavigate={handleNavigate} />;
      case 'sites':
        return <Sites />;
      case 'parking':
        return <ParkingSpaces />;
      case 'devices':
        return <Devices initialFilters={pageFilters} />;
      case 'gateways':
        return <Gateways initialFilters={pageFilters} />;
      case 'analytics':
        return <Analytics />;
      // ChirpStack Manager removed
      // case 'chirpstack':
      //   return <ChirpStackDevices />;
      case 'users':
        return <UsersPlaceholder />;
      default:
        return <Dashboard onNavigate={handleNavigate} />;
    }
  };

  // Close sidebar on mobile when clicking nav items
  const handleNavClick = (itemId: string) => {
    if (!navigationItems.find(item => item.id === itemId)?.disabled) {
      setActiveTab(itemId);
      setPageFilters({}); // Clear filters when navigating directly
      // Auto-close on mobile/tablet
      if (window.innerWidth < 1024) {
        sidebar.close();
      }
    }
  };

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebar.isOpen) {
        sidebar.close();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [sidebar.isOpen, sidebar.close]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Backdrop overlay for mobile */}
      {sidebar.isOpen && (
        <div
          className="fixed inset-0 bg-gray-600 bg-opacity-50 z-40 lg:z-30"
          onClick={sidebar.close}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Pure overlay on all screen sizes */}
      <div 
        className={`
          fixed inset-y-0 left-0 z-50 w-64 xl:w-80 bg-white shadow-xl
          transform transition-transform duration-250 ease-in-out
          ${sidebar.isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between h-16 lg:h-20 px-4 lg:px-6 xl:px-8 border-b border-gray-200">
          <div className="flex items-center">
            <Wifi className="w-6 h-6 lg:w-8 lg:h-8 xl:w-10 xl:h-10 text-blue-600" />
            <span className="ml-2 lg:ml-3 text-lg lg:text-xl xl:text-2xl font-semibold text-gray-900">
              SenseMy IoT
            </span>
          </div>
          
          {/* Close button - appears on all screen sizes */}
          <button
            onClick={sidebar.close}
            className="text-gray-400 hover:text-gray-600 p-2 -mr-2 rounded-lg transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-4 lg:mt-6 px-3 lg:px-4 xl:px-6 pb-20 overflow-y-auto">
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                disabled={item.disabled}
                className={`
                  w-full flex items-center px-3 lg:px-4 py-3 lg:py-4 mt-1 lg:mt-2 
                  text-sm lg:text-base font-medium rounded-lg transition-colors
                  min-h-[44px] lg:min-h-[48px] touch-manipulation
                  ${isActive
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : item.disabled
                    ? 'text-gray-400 cursor-not-allowed'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="w-5 h-5 lg:w-6 lg:h-6 mr-3 lg:mr-4 flex-shrink-0" />
                <span className="flex-1 text-left">{item.label}</span>
                {item.disabled && (
                  <span className="ml-2 text-xs lg:text-sm bg-gray-200 text-gray-500 px-2 py-1 rounded-full">
                    Soon
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Version info */}
        <div className="absolute bottom-0 left-0 right-0 p-4 lg:p-6 bg-gray-50 border-t border-gray-200">
          <div className="text-xs lg:text-sm text-gray-500">
            <div className="font-medium">SenseMy IoT Platform</div>
            <VersionInfo showFull={false} className="mt-1" />
            <div className="text-xs text-gray-400 mt-1">
              {new Date().toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Area - Always full width */}
      <div className="min-h-screen">
        {/* Top Navigation Bar */}
        <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
          <div className="flex items-center justify-between h-14 lg:h-16 xl:h-20 px-4 lg:px-6 xl:px-8">
            {/* Sidebar toggle button */}
            <button
              onClick={sidebar.toggle}
              className="text-gray-400 hover:text-gray-600 p-2 -ml-2 rounded-lg transition-colors touch-manipulation"
              aria-label={sidebar.isOpen ? 'Close sidebar' : 'Open sidebar'}
            >
              {sidebar.isOpen ? (
                <ChevronLeft className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>

            {/* Page title */}
            <div className="flex-1 ml-4">
              <h1 className="text-lg lg:text-xl xl:text-2xl font-semibold text-gray-900 capitalize">
                {activeTab === 'chirpstack' ? 'ChirpStack Manager' : activeTab}
              </h1>
            </div>

            {/* Status indicators and user menu */}
            <div className="flex items-center space-x-2 lg:space-x-4 xl:space-x-6">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 lg:w-3 lg:h-3 bg-green-400 rounded-full"></div>
                <span className="text-xs lg:text-sm xl:text-base text-gray-600">Online</span>
              </div>

              <div className="hidden sm:flex items-center space-x-2 text-xs lg:text-sm xl:text-base text-gray-600">
                <span>Tenant:</span>
                <code className="bg-gray-100 px-2 py-1 lg:px-3 lg:py-2 rounded text-xs lg:text-sm font-mono">
                  {currentTenant?.name || 'N/A'}
                </code>
              </div>

              {/* User menu */}
              <div className="relative">
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center space-x-2 text-gray-700 hover:text-gray-900 p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  aria-label="User menu"
                >
                  <UserIcon className="w-5 h-5" />
                  <span className="hidden lg:inline text-sm">{user?.email}</span>
                </button>

                {/* Dropdown menu */}
                {showUserMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setShowUserMenu(false)}
                    />
                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                      <div className="px-4 py-3 border-b border-gray-200">
                        <p className="text-sm font-medium text-gray-900">{user?.email}</p>
                        <p className="text-xs text-gray-500 mt-1">{currentTenant?.name}</p>
                      </div>
                      <button
                        onClick={() => {
                          logout();
                          setShowUserMenu(false);
                        }}
                        className="w-full flex items-center space-x-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Logout</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content - Full width utilization */}
        <main className="w-full">
          <div className="w-full max-w-none">
            {renderContent()}
          </div>
        </main>
      </div>
    </div>
  );
};

// Users placeholder component
const UsersPlaceholder: React.FC = () => (
  <div className="p-4 lg:p-8 xl:p-12">
    <div className="max-w-md mx-auto text-center py-12 lg:py-16 xl:py-24">
      <Users className="mx-auto h-12 w-12 lg:h-16 lg:w-16 xl:h-20 xl:w-20 text-gray-400 mb-4 lg:mb-6" />
      <h3 className="text-lg lg:text-xl xl:text-2xl font-semibold text-gray-900 mb-2 lg:mb-4">
        User Management
      </h3>
      <p className="text-sm lg:text-base xl:text-lg text-gray-600">
        User management system coming soon. This will include user roles, permissions, and account management.
      </p>
    </div>
  </div>
);

export default SenseMyIoTPlatform;
