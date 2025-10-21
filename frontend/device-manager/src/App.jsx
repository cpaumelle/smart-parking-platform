// 10-ui-frontend/sensemy-platform/src/App.jsx
// Version: 2.0.0 - 2025-10-21
// Changelog:
// - Added authentication with AuthProvider
// - Integrated login page
// - Protected routes with authentication check

import React from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import SenseMyIoTPlatform from './components/SenseMyIoTPlatform';
import Login from './pages/Login';
import './index.css';

// Protected wrapper component
function AppContent() {
  const { isAuthenticated, loading, user } = useAuth();

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login />;
  }

  // Show main platform if authenticated
  return (
    <div className="App">
      <SenseMyIoTPlatform />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
