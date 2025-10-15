"""
Reservation lifecycle job functions
"""
import asyncio
from datetime import datetime, timezone
import logging
import sys
sys.path.append("/app")

from app.database import get_db
from app.dependencies import get_downlink_client
from app.services.state_engine import ParkingStateEngine
from app.models import ParkingState

logger = logging.getLogger("parking-jobs")


async def activate_reservation_job(reservation_id: str):
    """
    Job: Activate a reservation when its start time arrives
    Trigger: reservation.reserved_from
    """
    async with get_db() as db:
        try:
            logger.info(f"⏰ Activating reservation {reservation_id}")

            # Update reservation status and get space info in single query
            result = await db.fetch("""
                UPDATE parking_spaces.reservations r
                SET status = 'active',
                    activated_at = NOW()
                WHERE r.reservation_id = $1
                  AND r.status = 'pending'
                RETURNING r.space_id, r.external_booking_id
            """, reservation_id)

            if not result:
                logger.warning(f"Reservation {reservation_id} not found or already activated")
                return

            space_id = str(result[0]["space_id"])
            external_booking_id = result[0]["external_booking_id"]

            # Get display device info
            display_info = await db.fetchrow("""
                SELECT 
                    s.space_name,
                    s.current_state,
                    s.display_device_deveui,
                    dr.display_codes,
                    dr.fport,
                    dr.confirmed_downlinks
                FROM parking_spaces.spaces s
                JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
                WHERE s.space_id = $1
            """, space_id)

            if not display_info:
                logger.error(f"Display info not found for space {space_id}")
                return

            previous_state = display_info["current_state"]

            # Update parking space state to RESERVED
            await db.execute("""
                UPDATE parking_spaces.spaces
                SET current_state = 'RESERVED',
                    last_display_update = NOW()
                WHERE space_id = $1
            """, space_id)

            # Get downlink client and send display update
            downlink_client = get_downlink_client()
            display_code = ParkingStateEngine.get_display_code(
                ParkingState.RESERVED,
                display_info["display_codes"]
            )

            downlink_result = await downlink_client.send_downlink(
                dev_eui=display_info["display_device_deveui"],
                fport=display_info["fport"],
                data=display_code,
                confirmed=display_info["confirmed_downlinks"]
            )

            # Log actuation event with downlink result
            await db.execute("""
                INSERT INTO parking_operations.actuations (
                    space_id, trigger_type, trigger_source, 
                    previous_state, new_state, display_code,
                    downlink_sent, response_time_ms, downlink_error
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, space_id, "reservation_activated", "apscheduler", 
                previous_state, "RESERVED", display_code,
                downlink_result["success"],
                downlink_result.get("response_time_ms"),
                downlink_result.get("error"))

            if downlink_result["success"]:
                logger.info(f"✅ Reservation {reservation_id} activated for space {display_info['space_name']} - downlink sent ({downlink_result.get('response_time_ms', 0):.0f}ms)")
            else:
                logger.error(f"❌ Reservation {reservation_id} activated but downlink failed: {downlink_result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Failed to activate reservation {reservation_id}: {e}", exc_info=True)
            raise

async def check_no_show_job(reservation_id: str):
    """
    Job: Check if vehicle arrived within grace period
    Trigger: reservation.reserved_from + grace_period_minutes
    """
    async with get_db() as db:
        try:
            logger.info(f"⏰ Checking no-show for reservation {reservation_id}")

            # Get reservation and space details
            result = await db.fetch("""
                SELECT 
                    r.space_id,
                    r.reserved_from,
                    r.grace_period_minutes,
                    s.space_name,
                    s.current_state,
                    s.last_sensor_update,
                    s.sensor_state,
                    s.display_device_deveui,
                    dr.display_codes,
                    dr.fport,
                    dr.confirmed_downlinks
                FROM parking_spaces.reservations r
                JOIN parking_spaces.spaces s ON r.space_id = s.space_id
                JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
                WHERE r.reservation_id = $1
                  AND r.status = 'active'
            """, reservation_id)

            if not result:
                logger.warning(f"Reservation {reservation_id} not found or not active")
                return

            row = result[0]
            space_id = str(row["space_id"])
            
            # Check if vehicle arrived (sensor shows OCCUPIED after reservation start)
            vehicle_arrived = (
                row["sensor_state"] == "OCCUPIED" and
                row["last_sensor_update"] and
                row["last_sensor_update"] >= row["reserved_from"]
            )

            if vehicle_arrived:
                logger.info(f"✅ Vehicle arrived for reservation {reservation_id}")
                return

            # No vehicle detected - mark as no-show
            logger.warning(f"⚠️ No-show detected for reservation {reservation_id}")

            await db.execute("""
                UPDATE parking_spaces.reservations
                SET status = 'no_show',
                    completed_at = NOW()
                WHERE reservation_id = $1
            """, reservation_id)

            # Release parking space back to FREE
            await db.execute("""
                UPDATE parking_spaces.spaces
                SET current_state = 'FREE',
                    last_display_update = NOW()
                WHERE space_id = $1
            """, space_id)

            # Send downlink to update display to FREE
            downlink_client = get_downlink_client()
            display_code = ParkingStateEngine.get_display_code(
                ParkingState.FREE,
                row["display_codes"]
            )

            downlink_result = await downlink_client.send_downlink(
                dev_eui=row["display_device_deveui"],
                fport=row["fport"],
                data=display_code,
                confirmed=row["confirmed_downlinks"]
            )

            # Log actuation event
            await db.execute("""
                INSERT INTO parking_operations.actuations (
                    space_id, trigger_type, trigger_source,
                    previous_state, new_state, display_code,
                    downlink_sent, response_time_ms, downlink_error
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, space_id, "no_show_detected", "apscheduler",
                row["current_state"], "FREE", display_code,
                downlink_result["success"],
                downlink_result.get("response_time_ms"),
                downlink_result.get("error"))

            if downlink_result["success"]:
                logger.info(f"✅ Reservation {reservation_id} marked as no-show, space {row['space_name']} released to FREE - downlink sent")
            else:
                logger.error(f"⚠️ No-show marked but downlink failed: {downlink_result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Failed to check no-show for {reservation_id}: {e}", exc_info=True)
            raise

async def complete_reservation_job(reservation_id: str):
    """
    Job: Complete a reservation when its end time arrives
    Trigger: reservation.reserved_until
    """
    async with get_db() as db:
        try:
            logger.info(f"⏰ Completing reservation {reservation_id}")

            # Update reservation status and get space info
            result = await db.fetch("""
                UPDATE parking_spaces.reservations r
                SET status = 'completed',
                    completed_at = NOW()
                WHERE r.reservation_id = $1
                  AND r.status = 'active'
                RETURNING r.space_id
            """, reservation_id)

            if not result:
                logger.warning(f"Reservation {reservation_id} not found or already completed")
                return

            space_id = str(result[0]["space_id"])

            # Get current sensor state and display info to determine new display state
            space_info = await db.fetchrow("""
                SELECT 
                    s.space_name,
                    s.current_state,
                    s.sensor_state,
                    s.display_device_deveui,
                    dr.display_codes,
                    dr.fport,
                    dr.confirmed_downlinks
                FROM parking_spaces.spaces s
                JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
                WHERE s.space_id = $1
            """, space_id)

            if not space_info:
                logger.error(f"Space info not found for {space_id}")
                return

            previous_state = space_info["current_state"]
            
            # Determine new state from sensor (what's really happening now)
            sensor_state = space_info["sensor_state"]
            if sensor_state in ("OCCUPIED", "FREE"):
                new_state = sensor_state
            else:
                # Fallback to FREE if sensor state is unknown
                new_state = "FREE"
                logger.warning(f"Unknown sensor state '{sensor_state}' for space {space_id}, defaulting to FREE")

            # Update space to sensor-based state
            await db.execute("""
                UPDATE parking_spaces.spaces
                SET current_state = $1,
                    last_display_update = NOW()
                WHERE space_id = $2
            """, new_state, space_id)

            # Send downlink with sensor-based state
            downlink_client = get_downlink_client()
            new_parking_state = ParkingState.OCCUPIED if new_state == "OCCUPIED" else ParkingState.FREE
            display_code = ParkingStateEngine.get_display_code(
                new_parking_state,
                space_info["display_codes"]
            )

            downlink_result = await downlink_client.send_downlink(
                dev_eui=space_info["display_device_deveui"],
                fport=space_info["fport"],
                data=display_code,
                confirmed=space_info["confirmed_downlinks"]
            )

            # Log actuation event
            await db.execute("""
                INSERT INTO parking_operations.actuations (
                    space_id, trigger_type, trigger_source,
                    previous_state, new_state, display_code,
                    downlink_sent, response_time_ms, downlink_error
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, space_id, "reservation_completed", "apscheduler",
                previous_state, new_state, display_code,
                downlink_result["success"],
                downlink_result.get("response_time_ms"),
                downlink_result.get("error"))

            if downlink_result["success"]:
                logger.info(f"✅ Reservation {reservation_id} completed for space {space_info['space_name']}: {previous_state} -> {new_state} (sensor-based) - downlink sent")
            else:
                logger.error(f"⚠️ Reservation completed but downlink failed: {downlink_result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Failed to complete reservation {reservation_id}: {e}", exc_info=True)
            raise

def run_async_job(coro):
    """
    Wrapper to run async functions in APScheduler's thread pool
    APScheduler executes jobs in threads, but our jobs are async
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Job wrapper functions that can be pickled by APScheduler
def activate_reservation_wrapper(reservation_id: str):
    """Wrapper for activate_reservation_job that can be pickled"""
    return run_async_job(activate_reservation_job(reservation_id))

def check_no_show_wrapper(reservation_id: str):
    """Wrapper for check_no_show_job that can be pickled"""
    return run_async_job(check_no_show_job(reservation_id))

def complete_reservation_wrapper(reservation_id: str):
    """Wrapper for complete_reservation_job that can be pickled"""
    return run_async_job(complete_reservation_job(reservation_id))
