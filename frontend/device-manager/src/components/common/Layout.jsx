// src/components/common/Layout.jsx
import { useState } from 'react';
import Navigation from './Navigation.jsx';
import LoadingSpinner from './LoadingSpinner.jsx';

const Layout = ({ children, loading = false, error = null }) => {
  const [currentPath, setCurrentPath] = useState('/devices');

  const handleNavigate = (path) => {
    setCurrentPath(path);
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md w-full bg-white rounded-lg shadow-md p-6">
          <div className="text-center">
            <div className="text-red-600 text-6xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Something went wrong</h2>
            <p className="text-gray-600 mb-4">{error.message || 'An unexpected error occurred'}</p>
            <button 
              onClick={() => window.location.reload()}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            >
              Reload Page
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation 
        currentPath={currentPath}
        onNavigate={handleNavigate}
      />
      
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="large" />
          </div>
        ) : (
          <>
            {children}
          </>
        )}
      </main>
      
      <footer className="bg-white border-t border-gray-200 mt-8">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div>
              SenseMy IoT Platform - Device & Location Management
            </div>
            <div>
              Built with ❤️ for IoT infrastructure management
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
