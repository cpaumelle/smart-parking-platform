"""
Rejoin Detection and Recovery Service
Detects when LoRaWAN devices rejoin the network and restores correct state
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

logger = logging.getLogger("rejoin-detector")

class RejoinDetector:
    """Detect device rejoins and trigger state recovery"""
    
    @staticmethod
    async def check_for_rejoin(
        dev_eui: str,
        dev_addr: str,
        fcnt: int,
        device_type: str,
        db_connection
    ) -> Optional[Dict[str, Any]]:
        """
        Check if device has rejoined the network
        
        Returns:
            Dict with rejoin info if detected, None otherwise
        """
        # Get last known state for this device
        if device_type == "display":
            last_state = await db_connection.fetchrow("""
                SELECT last_dev_addr, last_fcnt, last_uplink_at
                FROM parking_config.display_registry
                WHERE dev_eui = $1
            """, dev_eui)
        else:
            # For sensors, check transform service data
            return None  # Not implemented for sensors yet
        
        if not last_state:
            # First time seeing this device - not a rejoin
            logger.info(f"First uplink from {dev_eui}")
            await RejoinDetector._update_device_state(dev_eui, dev_addr, fcnt, device_type, db_connection)
            return None
        
        last_dev_addr = last_state["last_dev_addr"]
        last_fcnt = last_state["last_fcnt"]
        
        # Detect rejoin conditions
        rejoin_detected = False
        rejoin_reason = None
        
        # Condition 1: DevAddr changed
        if last_dev_addr and last_dev_addr != dev_addr:
            rejoin_detected = True
            rejoin_reason = "dev_addr_changed"
            logger.warning(f"DevAddr change detected for {dev_eui}: {last_dev_addr} -> {dev_addr}")
        
        # Condition 2: Frame counter reset (from high number to 0-5)
        elif last_fcnt and last_fcnt > 10 and fcnt < 5:
            rejoin_detected = True
            rejoin_reason = "fcnt_reset"
            logger.warning(f"fCnt reset detected for {dev_eui}: {last_fcnt} -> {fcnt}")
        
        if rejoin_detected:
            rejoin_info = {
                "dev_eui": dev_eui,
                "previous_dev_addr": last_dev_addr,
                "new_dev_addr": dev_addr,
                "previous_fcnt": last_fcnt,
                "new_fcnt": fcnt,
                "reason": rejoin_reason,
                "detected_at": datetime.utcnow()
            }
            
            # Log rejoin event
            await RejoinDetector._log_rejoin_event(rejoin_info, device_type, db_connection)
            
            # Update device state
            await RejoinDetector._update_device_state(dev_eui, dev_addr, fcnt, device_type, db_connection)
            
            return rejoin_info
        
        # Normal uplink - just update state
        await RejoinDetector._update_device_state(dev_eui, dev_addr, fcnt, device_type, db_connection)
        return None
    
    @staticmethod
    async def _log_rejoin_event(rejoin_info: Dict, device_type: str, db_connection):
        """Log rejoin event to database"""
        try:
            # Get space_id if this is a display
            space_id = None
            if device_type == "display":
                space_id = await db_connection.fetchval("""
                    SELECT space_id FROM parking_spaces.spaces
                    WHERE display_device_deveui = $1
                """, rejoin_info["dev_eui"])
            
            event_id = await db_connection.fetchval("""
                INSERT INTO parking_operations.device_events (
                    dev_eui, device_type, event_type,
                    previous_dev_addr, new_dev_addr,
                    previous_fcnt, new_fcnt,
                    space_id, event_data
                )
                VALUES ($1, $2, 'rejoin', $3, $4, $5, $6, $7, $8)
                RETURNING event_id
            """,
                rejoin_info["dev_eui"],
                device_type,
                rejoin_info.get("previous_dev_addr"),
                rejoin_info["new_dev_addr"],
                rejoin_info.get("previous_fcnt"),
                rejoin_info["new_fcnt"],
                space_id,
                {
                    "reason": rejoin_info["reason"],
                    "detected_at": rejoin_info["detected_at"].isoformat()
                }
            )
            
            logger.info(f"Logged rejoin event {event_id} for {rejoin_info['dev_eui']}")
            
        except Exception as e:
            logger.error(f"Error logging rejoin event: {e}", exc_info=True)
    
    @staticmethod
    async def _update_device_state(dev_eui: str, dev_addr: str, fcnt: int, device_type: str, db_connection):
        """Update device's last known state"""
        try:
            if device_type == "display":
                await db_connection.execute("""
                    UPDATE parking_config.display_registry
                    SET last_dev_addr = $1,
                        last_fcnt = $2,
                        last_uplink_at = NOW()
                    WHERE dev_eui = $3
                """, dev_addr, fcnt, dev_eui)
        except Exception as e:
            logger.error(f"Error updating device state: {e}")
    
    @staticmethod
    async def recover_display_state(dev_eui: str, db_connection) -> Dict[str, Any]:
        """
        Recover display state after rejoin
        Queries current expected state and sends actuation
        
        Returns:
            Recovery result dict
        """
        try:
            # Get space and current expected state
            space_info = await db_connection.fetchrow("""
                SELECT 
                    s.space_id,
                    s.space_name,
                    s.current_state,
                    s.display_device_deveui,
                    s.display_codes,
                    s.fport,
                    s.confirmed_downlinks,
                    s.maintenance_mode,
                    s.auto_actuation
                FROM parking_spaces.spaces s
                WHERE s.display_device_deveui = $1
                  AND s.enabled = TRUE
            """, dev_eui)
            
            if not space_info:
                logger.warning(f"No enabled space found for display {dev_eui}")
                return {"success": False, "reason": "no_space_found"}
            
            if not space_info["auto_actuation"]:
                logger.info(f"Auto-actuation disabled for space {space_info['space_name']}")
                return {"success": False, "reason": "auto_actuation_disabled"}
            
            # Import here to avoid circular dependency
            from app.services.state_engine import ParkingStateEngine
            from app.services.downlink_client import DownlinkClient
            from app.models import ParkingState
            
            # Determine current expected display state
            state_result = await ParkingStateEngine.determine_display_state(
                space_id=str(space_info["space_id"]),
                sensor_state=ParkingState(space_info["current_state"]),
                db_connection=db_connection
            )
            
            expected_state = state_result["display_state"]
            display_code = ParkingStateEngine.get_display_code(expected_state, space_info["display_codes"])
            
            logger.info(f"Recovering {space_info['space_name']} to state: {expected_state.value}")
            
            # Send downlink
            downlink_client = DownlinkClient()
            result = await downlink_client.send_downlink(
                dev_eui=dev_eui,
                fport=space_info["fport"],
                data=display_code,
                confirmed=space_info["confirmed_downlinks"]
            )
            
            # Log recovery actuation
            actuation_id = await ParkingStateEngine.log_actuation(
                space_id=str(space_info["space_id"]),
                trigger_type="rejoin_recovery",
                trigger_source=dev_eui,
                trigger_data={"reason": "device_rejoined"},
                previous_state="UNKNOWN",
                new_state=expected_state,
                display_deveui=dev_eui,
                display_code=display_code,
                db_connection=db_connection
            )
            
            # Update actuation result
            await db_connection.execute("""
                UPDATE parking_operations.actuations
                SET downlink_sent = $1,
                    response_time_ms = $2,
                    downlink_error = $3,
                    sent_at = NOW()
                WHERE actuation_id = $4
            """,
                result["success"],
                result["response_time_ms"],
                result["error"],
                actuation_id
            )
            
            # Update device event with recovery status
            await db_connection.execute("""
                UPDATE parking_operations.device_events
                SET recovery_action = 'state_restored',
                    recovery_successful = $1
                WHERE dev_eui = $2
                  AND event_type = 'rejoin'
                ORDER BY created_at DESC
                LIMIT 1
            """, result["success"], dev_eui)
            
            logger.info(f"Rejoin recovery {'successful' if result['success'] else 'failed'} for {space_info['space_name']}")
            
            return {
                "success": result["success"],
                "space_name": space_info["space_name"],
                "restored_state": expected_state.value,
                "response_time_ms": result["response_time_ms"]
            }
            
        except Exception as e:
            logger.error(f"Error recovering display state for {dev_eui}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
