// src/services/authService.js
import axios from 'axios';
import API_CONFIG from '../config/api.js';

const AUTH_TOKEN_KEY = 'parking_auth_token';
const REFRESH_TOKEN_KEY = 'parking_refresh_token';
const USER_KEY = 'parking_user';
const TENANT_KEY = 'parking_tenant';

class AuthService {
  constructor() {
    this.authClient = axios.create({
      baseURL: API_CONFIG.parkingURL,
      timeout: API_CONFIG.timeout,
      headers: API_CONFIG.headers
    });
  }

  /**
   * Login with email and password
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{user, token, refreshToken, tenants}>}
   */
  async login(email, password) {
    try {
      console.log('🔐 Attempting login for:', email);

      const response = await this.authClient.post('/api/v1/auth/login', {
        email,
        password
      });

      const { access_token, refresh_token, user, tenants } = response.data;

      // Store tokens and user info
      this.setAccessToken(access_token);
      this.setRefreshToken(refresh_token);

      // Store user with tenants included
      const userWithTenants = { ...user, tenants };
      this.setUser(userWithTenants);

      // Store first tenant as current tenant (can be changed later)
      if (tenants && tenants.length > 0) {
        this.setCurrentTenant(tenants[0]);
      }

      console.log('✅ Login successful:', user.email);
      console.log('📋 Available tenants:', tenants.length);
      console.log('📦 Tenants stored in user object');

      return {
        user: userWithTenants,  // Return the merged user object with tenants
        token: access_token,
        refreshToken: refresh_token,
        tenants
      };
    } catch (error) {
      console.error('❌ Login failed:', error.response?.data?.detail || error.message);
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  }

  /**
   * Refresh access token using refresh token
   * @returns {Promise<{accessToken, refreshToken}>}
   */
  async refreshAccessToken() {
    try {
      const refreshToken = this.getRefreshToken();

      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      console.log('🔄 Refreshing access token...');

      const response = await this.authClient.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken
      });

      const { access_token, refresh_token: new_refresh_token } = response.data;

      // Update stored tokens
      this.setAccessToken(access_token);
      this.setRefreshToken(new_refresh_token);

      console.log('✅ Token refreshed successfully');

      return {
        accessToken: access_token,
        refreshToken: new_refresh_token
      };
    } catch (error) {
      console.error('❌ Token refresh failed:', error.response?.data?.detail || error.message);
      // If refresh fails, clear all auth data
      this.logout();
      throw new Error('Session expired. Please login again.');
    }
  }

  /**
   * Logout - clear all stored auth data
   */
  logout() {
    console.log('👋 Logging out...');
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(TENANT_KEY);
  }

  /**
   * Check if user is authenticated
   * @returns {boolean}
   */
  isAuthenticated() {
    return !!this.getAccessToken();
  }

  /**
   * Get current access token
   * @returns {string|null}
   */
  getAccessToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  }

  /**
   * Set access token
   * @param {string} token
   */
  setAccessToken(token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  }

  /**
   * Get refresh token
   * @returns {string|null}
   */
  getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  /**
   * Set refresh token
   * @param {string} token
   */
  setRefreshToken(token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  }

  /**
   * Get current user
   * @returns {object|null}
   */
  getUser() {
    const userJson = localStorage.getItem(USER_KEY);
    return userJson ? JSON.parse(userJson) : null;
  }

  /**
   * Set current user
   * @param {object} user
   */
  setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  /**
   * Get current tenant
   * @returns {object|null}
   */
  getCurrentTenant() {
    const tenantJson = localStorage.getItem(TENANT_KEY);
    return tenantJson ? JSON.parse(tenantJson) : null;
  }

  /**
   * Set current tenant
   * @param {object} tenant
   */
  setCurrentTenant(tenant) {
    localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
  }

  /**
   * Get authorization header for API requests
   * @returns {object}
   */
  getAuthHeader() {
    const token = this.getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
}

// Create singleton instance
const authService = new AuthService();

export default authService;
