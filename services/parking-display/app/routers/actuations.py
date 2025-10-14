from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
import logging
import time
import asyncio
import sys
sys.path.append("/app")

from app.database import get_db_dependency, get_db
from app.models import (
    SensorUplinkRequest, ManualActuationRequest, ActuationResponse,
    ParkingState, TriggerType
)
from app.services.state_engine import ParkingStateEngine
from app.services.downlink_client import DownlinkClient

router = APIRouter()
logger = logging.getLogger("actuations")

@router.post("/sensor-uplink", response_model=ActuationResponse)
async def handle_sensor_uplink(
    request: SensorUplinkRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db_dependency)
):
    """
    Handle Class A sensor uplink from Ingest Service

    This is the main entry point for real-time parking actuation.
    Optimized for <200ms response time.
    """
    start_time = time.time()

    try:
        # Find parking space by sensor DevEUI
        space_query = """
            SELECT
                s.space_id,
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                s.auto_actuation,
                s.reservation_priority,
                s.maintenance_mode,
                dr.display_codes,
                dr.fport,
                dr.confirmed_downlinks
            FROM parking_spaces.spaces s
            JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE UPPER(s.occupancy_sensor_deveui) = UPPER($1)
              AND s.enabled = TRUE
        """

        space = await db.fetchrow(space_query, request.sensor_deveui)

        if not space:
            logger.warning(f"No parking space found for sensor {request.sensor_deveui}")
            return ActuationResponse(
                status="ignored",
                space_id="unknown",
                new_state=request.occupancy_state,
                reason="sensor_not_mapped",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        space_id = str(space["space_id"])

        # Update sensor state in database (synchronous for data consistency)
        await update_sensor_state(
            space_id, request.occupancy_state, request.timestamp, db
        )

        # Determine display state using state engine
        state_result = await ParkingStateEngine.determine_display_state(
            space_id=space_id,
            sensor_state=request.occupancy_state,
            db_connection=db
        )

        # Check if actuation needed
        if not state_result["should_actuate"]:
            logger.info(f"No actuation needed for {space['space_name']} - state unchanged")
            return ActuationResponse(
                status="no_change",
                space_id=space_id,
                space_name=space["space_name"],
                new_state=ParkingState(space["current_state"]),
                reason=state_result["reason"],
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Queue immediate actuation in background
        background_tasks.add_task(
            execute_immediate_actuation,
            space_id=space_id,
            space_name=space["space_name"],
            previous_state=space["current_state"],
            new_state=state_result["display_state"],
            display_deveui=space["display_device_deveui"],
            display_codes=space["display_codes"],
            fport=space["fport"],
            confirmed_downlinks=space["confirmed_downlinks"],
            trigger_type=TriggerType.SENSOR_UPLINK,
            trigger_source=request.sensor_deveui,
            trigger_data=request.model_dump(mode='json'),
            state_metadata=state_result
        )

        processing_time = (time.time() - start_time) * 1000

        # Log performance
        if processing_time > 100:
            logger.warning(f"Slow sensor processing: {processing_time:.1f}ms for {request.sensor_deveui}")

        return ActuationResponse(
            status="queued_immediate",
            space_id=space_id,
            space_name=space["space_name"],
            previous_state=ParkingState(space["current_state"]),
            new_state=state_result["display_state"],
            reason=state_result["reason"],
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Error handling sensor uplink from {request.sensor_deveui}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/manual", response_model=ActuationResponse)
async def manual_actuation(
    request: ManualActuationRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db_dependency)
):
    """
    Manual override - force display to specific state
    """
    try:
        # Validate space exists and get current state
        space_query = """
            SELECT
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                dr.display_codes,
                dr.fport,
                dr.confirmed_downlinks
            FROM parking_spaces.spaces s
            JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE s.space_id = $1 AND s.enabled = TRUE
        """

        space = await db.fetchrow(space_query, request.space_id)

        if not space:
            raise HTTPException(status_code=404, detail="Parking space not found or disabled")

        # Check if change needed
        if space["current_state"] == request.new_state.value:
            return ActuationResponse(
                status="no_change",
                space_id=request.space_id,
                space_name=space["space_name"],
                new_state=request.new_state,
                reason="already_in_target_state"
            )

        # Queue manual actuation
        background_tasks.add_task(
            execute_immediate_actuation,
            space_id=request.space_id,
            space_name=space["space_name"],
            previous_state=space["current_state"],
            new_state=request.new_state,
            display_deveui=space["display_device_deveui"],
            display_codes=space["display_codes"],
            fport=space["fport"],
            confirmed_downlinks=space["confirmed_downlinks"],
            trigger_type=TriggerType.MANUAL_OVERRIDE,
            trigger_source=request.user_id or "api",
            trigger_data=request.model_dump(mode='json'),
            state_metadata={"reason": "manual_override"}
        )

        return ActuationResponse(
            status="queued_immediate",
            space_id=request.space_id,
            space_name=space["space_name"],
            previous_state=ParkingState(space["current_state"]),
            new_state=request.new_state,
            reason="manual_override"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual actuation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def execute_immediate_actuation(
    space_id: str,
    space_name: str,
    previous_state: str,
    new_state: ParkingState,
    display_deveui: str,
    display_codes: dict,
    fport: int,
    confirmed_downlinks: bool,
    trigger_type: TriggerType,
    trigger_source: str,
    trigger_data: dict,
    state_metadata: dict
):
    """
    Background task to execute display actuation immediately

    Priority: Send downlink first, update database after
    """
    actuation_start = time.time()

    async with get_db() as db:
        try:
            # 1. Log actuation attempt first
            actuation_id = await ParkingStateEngine.log_actuation(
                space_id=space_id,
                trigger_type=trigger_type.value,
                trigger_source=trigger_source,
                trigger_data=trigger_data,
                previous_state=previous_state,
                new_state=new_state,
                display_deveui=display_deveui,
                display_code=ParkingStateEngine.get_display_code(new_state, display_codes),
                db_connection=db
            )

            # 2. Send downlink immediately (highest priority)
            downlink_client = DownlinkClient()
            display_code = ParkingStateEngine.get_display_code(new_state, display_codes)

            downlink_result = await downlink_client.send_downlink(
                dev_eui=display_deveui,
                fport=fport,  # Use fport from display registry (e.g., 15 for Kuando)
                data=display_code,
                confirmed=confirmed_downlinks  # Use setting from display registry
            )

            # 3. Update actuation log with downlink result
            await db.execute("""
                UPDATE parking_operations.actuations
                SET downlink_sent = $1,
                    downlink_confirmed = $2,
                    response_time_ms = $3,
                    downlink_error = $4,
                    sent_at = NOW()
                WHERE actuation_id = $5
            """,
                downlink_result["success"],
                False,  # Class C doesnt confirm
                downlink_result["response_time_ms"],
                downlink_result["error"],
                actuation_id
            )

            # 4. Update space state if downlink successful
            if downlink_result["success"]:
                await db.execute("""
                    UPDATE parking_spaces.spaces
                    SET current_state = $1,
                        display_state = $1,
                        last_display_update = NOW(),
                        state_changed_at = NOW(),
                        updated_at = NOW()
                    WHERE space_id = $2
                """, new_state.value, space_id)

                total_time = (time.time() - actuation_start) * 1000
                logger.info(f"Space {space_name}: {previous_state} -> {new_state.value} ({total_time:.1f}ms)")
            else:
                logger.error(f"Failed actuation {space_name}: {downlink_result['error']}")

        except Exception as e:
            logger.error(f"Error executing actuation for space {space_id}: {e}", exc_info=True)

async def update_sensor_state(space_id: str, sensor_state: ParkingState, timestamp, db):
    """Update sensor state tracking (non-blocking)"""
    try:
        # Convert to naive UTC datetime for asyncpg (TIMESTAMPTZ columns expect naive UTC)
        if timestamp and hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
            # Remove timezone info - asyncpg + TIMESTAMPTZ handles it
            timestamp = timestamp.replace(tzinfo=None)

        await db.execute("""
            UPDATE parking_spaces.spaces
            SET sensor_state = $1,
                last_sensor_update = $2,
                updated_at = NOW()
            WHERE space_id = $3
        """, sensor_state.value, timestamp, space_id)
    except Exception as e:
        logger.error(f"Error updating sensor state for space {space_id}: {e}")

@router.get("/status/{space_id}")
async def get_space_status(space_id: str, db = Depends(get_db_dependency)):
    """Get current status of parking space"""
    try:
        query = """
            SELECT
                s.space_id,
                s.space_name,
                s.current_state,
                s.sensor_state,
                s.last_sensor_update,
                s.last_display_update,
                s.enabled,
                s.maintenance_mode,
                r.reservation_id,
                r.reserved_until,
                r.external_booking_id
            FROM parking_spaces.spaces s
            LEFT JOIN parking_spaces.reservations r ON s.space_id = r.space_id
                AND r.status = 'active'
                AND r.reserved_from <= NOW()
                AND r.reserved_until >= NOW()
            WHERE s.space_id = $1
        """

        result = await db.fetchrow(query, space_id)

        if not result:
            raise HTTPException(status_code=404, detail="Parking space not found")

        active_reservation = None
        if result["reservation_id"]:
            active_reservation = {
                "reservation_id": str(result["reservation_id"]),
                "reserved_until": result["reserved_until"].isoformat(),
                "external_booking_id": result["external_booking_id"]
            }

        return {
            "space_id": str(result["space_id"]),
            "space_name": result["space_name"],
            "current_state": result["current_state"],
            "sensor_state": result["sensor_state"],
            "last_sensor_update": result["last_sensor_update"],
            "last_display_update": result["last_display_update"],
            "enabled": result["enabled"],
            "maintenance_mode": result["maintenance_mode"],
            "active_reservation": active_reservation
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting space status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
