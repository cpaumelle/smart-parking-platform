// src/services/reservationService.js
// Reservation API service using v5.3 multi-tenant API
import apiClient from './apiClient.js';

// Format date for PostgreSQL timestamp (ISO 8601 UTC)
const formatDateForAPI = (date) => {
  return date.toISOString();
};

export const reservationService = {
  /**
   * List reservations with optional filters
   * @param {Object} params - Filter parameters
   * @param {string} params.status - Filter by status (active, completed, cancelled)
   * @param {string} params.space_id - Filter by space UUID
   * @param {string} params.from - Start datetime (ISO 8601)
   * @param {string} params.until - End datetime (ISO 8601)
   * @returns {Promise<{reservations: Array, count: number}>}
   */
  async getReservations({ status, space_id, from, until } = {}) {
    try {
      const params = new URLSearchParams();
      if (status) params.append('status', status);
      if (space_id) params.append('space_id', space_id);
      if (from) params.append('from', from);
      if (until) params.append('until', until);

      const queryString = params.toString();
      const url = queryString ? `/api/v1/reservations/?${queryString}` : '/api/v1/reservations/';

      const response = await apiClient.get(url);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch reservations:', error.userMessage);
      throw error;
    }
  },

  /**
   * Get a single reservation by ID
   * @param {string} reservation_id - Reservation UUID
   * @returns {Promise<Object>}
   */
  async getReservation(reservation_id) {
    try {
      const response = await apiClient.get(`/api/v1/reservations/${reservation_id}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch reservation:', error.userMessage);
      throw error;
    }
  },

  /**
   * Create a new reservation
   * @param {Object} reservationData - Reservation data
   * @param {string} reservationData.space_id - Space UUID (required)
   * @param {Date|string} reservationData.reserved_from - Start datetime (required)
   * @param {Date|string} reservationData.reserved_until - End datetime (required)
   * @param {string} reservationData.external_booking_id - External system booking ID (optional)
   * @param {string} reservationData.external_system - External system name (optional)
   * @param {string} reservationData.reservation_type - Type: 'manual', 'api', 'web' (optional)
   * @param {number} reservationData.grace_period_minutes - Grace period before cancellation (optional)
   * @returns {Promise<Object>}
   */
  async createReservation({
    space_id,
    reserved_from,
    reserved_until,
    external_booking_id,
    external_system = 'device_manager_ui',
    reservation_type = 'manual',
    grace_period_minutes = 15
  }) {
    try {
      // Convert Date objects to ISO strings if needed
      const fromDate = reserved_from instanceof Date ? formatDateForAPI(reserved_from) : reserved_from;
      const untilDate = reserved_until instanceof Date ? formatDateForAPI(reserved_until) : reserved_until;

      console.log(`Creating reservation for space ${space_id} from ${fromDate} to ${untilDate}`);

      const response = await apiClient.post('/api/v1/reservations/', {
        id: space_id,  // API expects 'id' field (V4 compatibility - this is actually space_id)
        reserved_from: fromDate,
        reserved_until: untilDate,
        external_booking_id,
        external_system,
        reservation_type,
        grace_period_minutes
      });

      console.log('Reservation created successfully:', response.data.reservation_id);
      return response.data;
    } catch (error) {
      console.error('Failed to create reservation:', error.userMessage || error.message);
      throw error;
    }
  },

  /**
   * Cancel an existing reservation
   * @param {string} reservation_id - Reservation UUID
   * @param {string} reason - Cancellation reason (default: 'user_cancelled')
   * @returns {Promise<Object>}
   */
  async cancelReservation(reservation_id, reason = 'user_cancelled') {
    try {
      console.log(`Cancelling reservation ${reservation_id} with reason: ${reason}`);
      const response = await apiClient.delete(
        `/api/v1/reservations/${reservation_id}?reason=${encodeURIComponent(reason)}`
      );
      console.log('Reservation cancelled successfully');
      return response.data;
    } catch (error) {
      console.error('Failed to cancel reservation:', error.userMessage);
      throw error;
    }
  },

  /**
   * Quick reservation helper: Reserve a space for a specific duration
   * @param {string} space_id - Space UUID
   * @param {number} hours - Duration in hours (default: 2)
   * @returns {Promise<Object>}
   */
  async quickReserve(space_id, hours = 2) {
    const now = new Date();
    const until = new Date(now.getTime() + hours * 60 * 60 * 1000);

    return this.createReservation({
      space_id,
      reserved_from: now,
      reserved_until: until,
      external_booking_id: `UI-${Date.now()}`,
      external_system: 'device_manager_ui',
      reservation_type: 'manual',
      grace_period_minutes: 15
    });
  }
};

export default reservationService;
