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
        space_data, active_reservation = await ParkingStateEngine._get_space_data(space_id, db_connection)
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
            # Reservation data already fetched in _get_space_data (optimized single query)
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
    async def _get_space_data(space_id: str, db_connection) -> tuple[Optional[Dict], Optional[Dict]]:
        """
        Get space configuration and active reservation in single query (OPTIMIZED).
        
        Returns:
            tuple: (space_data, active_reservation)
            - space_data: Dict with space config, or None if not found
            - active_reservation: Dict with reservation data, or None if no active reservation
        """
        query = """
            SELECT
                -- Space fields
                s.space_id,
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                s.auto_actuation,
                s.reservation_priority,
                s.maintenance_mode,
                s.enabled,
                
                -- Display registry fields
                dr.display_codes,
                dr.fport,
                dr.confirmed_downlinks,
                
                -- Active reservation fields (NULL if no reservation)
                r.reservation_id,
                r.reserved_from,
                r.reserved_until,
                r.external_booking_id,
                r.external_system,
                r.booking_metadata
                
            FROM parking_spaces.spaces s
            
            -- Join display registry
            LEFT JOIN parking_config.display_registry dr 
                ON s.display_device_id = dr.display_id
            
            -- Join active reservation (if exists)
            LEFT JOIN parking_spaces.reservations r
                ON s.space_id = r.space_id
                AND r.status = 'active'
                AND r.reserved_from <= NOW()
                AND r.reserved_until >= NOW()
            
            WHERE s.space_id = $1 
              AND s.enabled = TRUE
            
            ORDER BY r.reserved_from DESC
            LIMIT 1
        """

        result = await db_connection.fetchrow(query, space_id)
        
        if not result:
            return None, None
        
        # Extract space data
        space_data = {
            "space_id": result["space_id"],
            "space_name": result["space_name"],
            "current_state": result["current_state"],
            "display_device_deveui": result["display_device_deveui"],
            "auto_actuation": result["auto_actuation"],
            "reservation_priority": result["reservation_priority"],
            "maintenance_mode": result["maintenance_mode"],
            "enabled": result["enabled"],
            "display_codes": result["display_codes"],
            "fport": result["fport"],
            "confirmed_downlinks": result["confirmed_downlinks"]
        }
        
        # Extract reservation data (if present)
        active_reservation = None
        if result["reservation_id"]:
            active_reservation = {
                "reservation_id": result["reservation_id"],
                "reserved_from": result["reserved_from"],
                "reserved_until": result["reserved_until"],
                "external_booking_id": result["external_booking_id"],
                "external_system": result["external_system"],
                "booking_metadata": result["booking_metadata"]
            }
        
        return space_data, active_reservation

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

    @staticmethod
    async def update_space_state(
        space_id: str,
        new_state: ParkingState,
        db_connection,
        update_reason: str = "actuation"
    ) -> bool:
        """
        Update parking space display state in database.
        
        Single source of truth for state updates.
        
        Args:
            space_id: UUID of parking space
            new_state: New parking state (FREE, OCCUPIED, RESERVED, etc)
            db_connection: Active database connection
            update_reason: Reason for update (for logging/auditing)
        
        Returns:
            True if update succeeded, False otherwise
        """
        try:
            result = await db_connection.execute("""
                UPDATE parking_spaces.spaces
                SET current_state = $1,
                    display_state = $1,
                    last_display_update = NOW(),
                    state_changed_at = NOW(),
                    updated_at = NOW()
                WHERE space_id = $2
            """, new_state.value, space_id)
            
            # Verify update affected a row
            rows_updated = int(result.split()[-1]) if result else 0
            
            if rows_updated == 0:
                logger.warning(f"State update for space {space_id} affected 0 rows")
                return False
            
            logger.debug(f"Updated space {space_id} state to {new_state.value} ({update_reason})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update space {space_id} state: {e}")
            return False
