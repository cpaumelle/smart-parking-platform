"""
JOIN Request Handler
Detects device JOIN/rejoin and triggers automatic state recovery
"""
import logging
import json
import asyncio
from datetime import datetime

logger = logging.getLogger("join-handler")

class JoinHandler:
    """Handle LoRaWAN JOIN requests and trigger state recovery"""
    
    @staticmethod
    async def handle_join_event(dev_eui: str, join_data: dict, db_connection):
        """
        Process a JOIN request event
        
        Args:
            dev_eui: Device EUI that joined
            join_data: JOIN request metadata
            db_connection: Database connection
        """
        try:
            logger.info(f"📡 JOIN detected for {dev_eui}")
            
            # Check if this is a display device
            display = await db_connection.fetchrow("""
                SELECT 
                    dr.display_id,
                    dr.dev_eui,
                    dr.display_type,
                    s.space_id,
                    s.space_name,
                    s.current_state,
                    s.display_codes,
                    dr.fport,
                    dr.confirmed_downlinks
                FROM parking_config.display_registry dr
                LEFT JOIN parking_spaces.spaces s 
                    ON s.display_device_deveui = dr.dev_eui
                WHERE dr.dev_eui = $1
                  AND dr.enabled = TRUE
            """, dev_eui)
            
            if not display:
                logger.debug(f"JOIN from non-display device or disabled: {dev_eui}")
                return
            
            space_id = display["space_id"]
            space_name = display["space_name"]
            
            if not space_id:
                logger.warning(f"Display {dev_eui} not assigned to any space")
                return
            
            logger.info(f"🔄 JOIN from display: {space_name} ({dev_eui})")
            
            # Log JOIN event
            await db_connection.execute("""
                INSERT INTO parking_operations.device_events (
                    dev_eui, device_type, event_type,
                    space_id, event_data
                )
                VALUES ($1, 'display', 'join', $2, $3)
            """, dev_eui, space_id, json.dumps(join_data))
            
            # Queue state recovery downlink
            # Import here to avoid circular dependency
            from app.services.state_engine import ParkingStateEngine
            from app.services.downlink_client import DownlinkClient
            from app.models import ParkingState
            
            # Determine current expected state
            state_result = await ParkingStateEngine.determine_display_state(
                space_id=str(space_id),
                sensor_state=ParkingState(display["current_state"]),
                db_connection=db_connection
            )
            
            expected_state = state_result["display_state"]
            display_code = ParkingStateEngine.get_display_code(
                expected_state, 
                display["display_codes"]
            )
            
            logger.info(f"💡 Restoring {space_name} to {expected_state.value} after JOIN")
            
            # Send downlink (wait a few seconds after JOIN to avoid collision)
            await asyncio.sleep(3)
            
            downlink_client = DownlinkClient()
            result = await downlink_client.send_downlink(
                dev_eui=dev_eui,
                fport=display["fport"],
                data=display_code,
                confirmed=display["confirmed_downlinks"]
            )
            
            # Log restoration actuation
            actuation_id = await ParkingStateEngine.log_actuation(
                space_id=str(space_id),
                trigger_type="join_recovery",
                trigger_source=dev_eui,
                trigger_data={"reason": "device_joined", "join_data": join_data},
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
                  AND event_type = 'join'
                ORDER BY created_at DESC
                LIMIT 1
            """, result["success"], dev_eui)
            
            if result["success"]:
                logger.info(f"✅ JOIN recovery successful for {space_name}")
            else:
                logger.error(f"❌ JOIN recovery failed for {space_name}: {result['error']}")
            
        except Exception as e:
            logger.error(f"Error handling JOIN for {dev_eui}: {e}", exc_info=True)


async def start_join_listener():
    """
    Start listening for JOIN events from ChirpStack via MQTT or database polling
    
    Note: This is a placeholder. Actual implementation depends on:
    - ChirpStack publishing JOIN events to MQTT (not currently configured)
    - OR polling ChirpStack API for recent JOINs
    - OR detecting JOINs from DevAddr/fCnt changes in uplinks (already implemented in rejoin_detector)
    """
    logger.info("📡 JOIN listener would start here (currently handled via rejoin detection)")
    pass
