/*
 * SenseMy IoT Platform - Locations Router
 * Version: 1.0.0
 * Created: 2025-08-08 15:50:00 UTC
 * 
 * Simple router component that directs to LocationManager
 */
import LocationManager from './LocationManager.jsx';

export default function Locations({ initialFilters }) {
  return <LocationManager />;
}
