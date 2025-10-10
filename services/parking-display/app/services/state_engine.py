from typing import Optional, Dict, Any
import json
from datetime import datetime
import logging
import sys
sys.path.append("/app")
from app.models import ParkingState

logger = logging.getLogger("state-engine")

class ParkingStateEngine:
    """
    Core business logic for determining parking space display state

    State Priority Rules:
    1. Manual Override (highest priority)
    2. Maintenance Mode
    3. Active Reservation
    4. Sensor State (lowest priority)
    """

    @staticmethod
    async def determine_display_state(
        space_id: str,
        sensor_state: Optional[ParkingState] = None,
        manual_override: Optional[ParkingState] = None,
        db_connection = None
    ) -> Dict[str, Any]:
        """
        Determine what state the Class C display should show

        Returns:
        {
            "display_state": ParkingState,
            "reason": str,
            "priority": int,
            "metadata": dict,
            "should_actuate": bool
        }
        """

        # Get space configuration and current state
        space_data = await ParkingStateEngine._get_space_data(space_id, db_connection)
        if not space_data:
            raise ValueError(f"Parking space {space_id} not found")

        current_state = space_data["current_state"]

        # Priority 1: Manual Override
        if manual_override:
            return {
                "display_state": manual_override,
                "reason": "manual_override",
                "priority": 1,
                "metadata": {"override_value": manual_override},
                "should_actuate": current_state != manual_override.value
            }

        # Priority 2: Maintenance Mode
        if space_data["maintenance_mode"]:
            return {
                "display_state": ParkingState.MAINTENANCE,
                "reason": "maintenance_mode",
                "priority": 2,
                "metadata": {"maintenance_enabled": True},
                "should_actuate": current_state != ParkingState.MAINTENANCE.value
            }

        # Priority 3: Active Reservation (if reservation_priority enabled)
        if space_data["reservation_priority"]:
            active_reservation = await ParkingStateEngine._get_active_reservation(space_id, db_connection)
            if active_reservation:
                return {
                    "display_state": ParkingState.RESERVED,
                    "reason": "active_reservation",
                    "priority": 3,
                    "metadata": {
                        "reservation_id": str(active_reservation["reservation_id"]),
                        "reserved_until": active_reservation["reserved_until"].isoformat(),
                        "external_booking_id": active_reservation.get("external_booking_id")
                    },
                    "should_actuate": current_state != ParkingState.RESERVED.value
                }

        # Priority 4: Sensor State (if auto_actuation enabled)
        if space_data["auto_actuation"] and sensor_state:
            return {
                "display_state": sensor_state,
                "reason": "sensor_state",
                "priority": 4,
                "metadata": {"sensor_value": sensor_state.value},
                "should_actuate": current_state != sensor_state.value
            }

        # Fallback: Keep current state
        return {
            "display_state": ParkingState(current_state),
            "reason": "no_change",
            "priority": 5,
            "metadata": {"fallback": True},
            "should_actuate": False
        }

    @staticmethod
    async def _get_space_data(space_id: str, db_connection) -> Optional[Dict]:
        """Get space configuration and current state"""
        query = """
            SELECT
                s.space_id,
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                s.auto_actuation,
                s.reservation_priority,
                s.maintenance_mode,
                s.enabled,
                dr.display_codes
            FROM parking_spaces.spaces s
            LEFT JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE s.space_id = $1 AND s.enabled = TRUE
        """

        result = await db_connection.fetchrow(query, space_id)
        return dict(result) if result else None

    @staticmethod
    async def _get_active_reservation(space_id: str, db_connection) -> Optional[Dict]:
        """Get active reservation for space"""
        query = """
            SELECT
                reservation_id,
                reserved_from,
                reserved_until,
                external_booking_id,
                external_system,
                booking_metadata
            FROM parking_spaces.reservations
            WHERE space_id = $1
              AND status = 'active'
              AND reserved_from <= NOW()
              AND reserved_until >= NOW()
            ORDER BY reserved_from DESC
            LIMIT 1
        """

        result = await db_connection.fetchrow(query, space_id)
        return dict(result) if result else None

    @staticmethod
    def get_display_code(state: ParkingState, display_codes) -> str:
        """Get hex code for display state - handles both dict and JSON string"""
        # Handle case where display_codes might be a JSON string
        if isinstance(display_codes, str):
            import json
            display_codes = json.loads(display_codes)
        return display_codes.get(state.value, display_codes.get("FREE", "01"))

    @staticmethod
    async def log_actuation(
        space_id: str,
        trigger_type: str,
        trigger_source: str,
        trigger_data: Dict,
        previous_state: str,
        new_state: ParkingState,
        display_deveui: str,
        display_code: str,
        db_connection
    ) -> str:
        """Log actuation attempt and return actuation_id"""

        query = """
            INSERT INTO parking_operations.actuations (
                space_id, trigger_type, trigger_source, trigger_data,
                previous_state, new_state, display_deveui, display_code
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING actuation_id
        """

        actuation_id = await db_connection.fetchval(
            query,
            space_id, trigger_type, trigger_source, json.dumps(trigger_data),
            previous_state, new_state.value, display_deveui, display_code
        )

        return str(actuation_id)
