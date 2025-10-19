// src/utils/navigationHelper.js
// Version: 1.0.0 - 2025-08-09 14:45:00 UTC
// Changelog:
// - Created navigation helper for URL parameter management
// - Supports filter-based navigation between pages
// - Maintains URL state for bookmarking and browser history
// - Compatible with existing tab-based navigation system

export const navigationHelper = {
  /**
   * Navigate to a page with specific filters
   * @param {string} page - Target page (devices, gateways, locations)
   * @param {object} filters - Filter parameters to apply
   * @param {function} setActiveTab - Tab setter function
   */
  navigateWithFilters: (page, filters = {}, setActiveTab) => {
    // Set the active tab
    if (setActiveTab) {
      setActiveTab(page);
    }

    // Build URL parameters
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== 'all' && value !== '') {
        params.set(key, value);
      }
    });

    // Update URL with parameters
    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({ page, filters }, '', newURL);

    // Dispatch custom event for components to listen to navigation changes
    window.dispatchEvent(new CustomEvent('navigationWithFilters', {
      detail: { page, filters }
    }));
  },

  /**
   * Get current filters from URL parameters
   * @param {object} defaultFilters - Default filter values
   * @returns {object} Current filter state
   */
  getFiltersFromURL: (defaultFilters = {}) => {
    const params = new URLSearchParams(window.location.search);
    const filters = { ...defaultFilters };
    
    params.forEach((value, key) => {
      filters[key] = value;
    });
    
    return filters;
  },

  /**
   * Update URL parameters without navigation
   * @param {object} filters - Filter parameters to update
   */
  updateURLParams: (filters) => {
    const params = new URLSearchParams(window.location.search);
    
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== 'all' && value !== '') {
        params.set(key, value);
      } else {
        params.delete(key);
      }
    });

    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.replaceState({}, '', newURL);
  },

  /**
   * Clear all URL parameters
   */
  clearURLParams: () => {
    window.history.replaceState({}, '', window.location.pathname);
  },

  /**
   * Check if specific filters are active in URL
   * @param {object} targetFilters - Filters to check for
   * @returns {boolean} True if all target filters match current URL
   */
  hasActiveFilters: (targetFilters) => {
    const currentFilters = navigationHelper.getFiltersFromURL();
    
    return Object.entries(targetFilters).every(([key, value]) => {
      return currentFilters[key] === value;
    });
  },

  /**
   * Generate a URL for a specific page and filters (for links)
   * @param {string} page - Target page
   * @param {object} filters - Filter parameters
   * @returns {string} URL with parameters
   */
  generateURL: (page, filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== 'all' && value !== '') {
        params.set(key, value);
      }
    });

    const queryString = params.toString();
    return queryString ? `#${page}?${queryString}` : `#${page}`;
  },

  /**
   * Setup listener for browser back/forward navigation
   * @param {function} callback - Function to call on navigation
   * @returns {function} Cleanup function
   */
  setupPopstateListener: (callback) => {
    const handlePopState = (event) => {
      const filters = navigationHelper.getFiltersFromURL();
      callback(filters, event.state);
    };

    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }
};

export default navigationHelper;
