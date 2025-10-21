// src/contexts/AuthContext.jsx
import React, { createContext, useState, useContext, useEffect } from 'react';
import authService from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [currentTenant, setCurrentTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load user from localStorage on mount
  useEffect(() => {
    const storedUser = authService.getUser();
    const storedTenant = authService.getCurrentTenant();

    if (storedUser) {
      setUser(storedUser);
      setCurrentTenant(storedTenant);
    }

    setLoading(false);
  }, []);

  const login = async (email, password) => {
    try {
      setError(null);
      setLoading(true);

      const result = await authService.login(email, password);

      setUser(result.user);
      setCurrentTenant(result.tenants[0] || null);

      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    setCurrentTenant(null);
    setError(null);
  };

  const refreshToken = async () => {
    try {
      await authService.refreshAccessToken();
      return true;
    } catch (err) {
      setError(err.message);
      logout();
      return false;
    }
  };

  const switchTenant = (tenant) => {
    authService.setCurrentTenant(tenant);
    setCurrentTenant(tenant);
  };

  const value = {
    user,
    currentTenant,
    loading,
    error,
    isAuthenticated: !!user,
    login,
    logout,
    refreshToken,
    switchTenant
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
