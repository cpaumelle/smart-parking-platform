from fastapi import APIRouter, Depends, HTTPException
from fastapi import Header
from typing import Optional
import logging
import json
from datetime import datetime, timezone
import sys
sys.path.append("/app")

from app.database import get_db_dependency
from app.models import ReservationRequest
from app.tasks.reconciliation import trigger_space_reconciliation
from app.scheduler.reservation_manager import ReservationManager
from app.utils.idempotency import get_cached_response, cache_response

router = APIRouter()
logger = logging.getLogger("reservations")

@router.post("/")
async def create_reservation(
    request: ReservationRequest, 
    db = Depends(get_db_dependency),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Create new parking reservation with idempotency support"""
    
    # Check idempotency key for duplicate requests
    if idempotency_key:
        cached = await get_cached_response(idempotency_key)
        if cached:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return cached
    
    try:
        # Verify space exists
        space_check = await db.fetchval(
            "SELECT space_id FROM parking_spaces.spaces WHERE space_id = $1 AND enabled = TRUE",
            request.space_id
        )

        if not space_check:
            raise HTTPException(status_code=404, detail="Parking space not found")

        # Determine initial status: 'pending' for future, 'active' for immediate
        now = datetime.now(timezone.utc)
        
        # Handle timezone-aware datetime comparison
        reserved_from_utc = request.reserved_from
        if reserved_from_utc.tzinfo is None:
            # If naive, assume UTC
            reserved_from_utc = reserved_from_utc.replace(tzinfo=timezone.utc)
        
        # Check if reservation starts now or in the past
        is_immediate = reserved_from_utc <= now
        initial_status = 'active' if is_immediate else 'pending'
        
        logger.info(f"Creating {'immediate' if is_immediate else 'future'} reservation (starts: {reserved_from_utc.isoformat()}, status: {initial_status})")

        # Insert reservation with smart status
        query = """
            INSERT INTO parking_spaces.reservations (
                space_id, reserved_from, reserved_until,
                external_booking_id, external_system, external_user_id,
                booking_metadata, reservation_type, grace_period_minutes,
                status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING reservation_id
        """

        reservation_id = await db.fetchval(
            query,
            request.space_id,
            request.reserved_from,
            request.reserved_until,
            request.external_booking_id,
            request.external_system,
            request.external_user_id,
            json.dumps(request.booking_metadata) if request.booking_metadata else None,
            request.reservation_type,
            request.grace_period_minutes,
            initial_status  # Use calculated status
        )

        logger.info(f"Created reservation {reservation_id} for space {request.space_id} (status: {initial_status})")
        
        # Schedule lifecycle jobs via APScheduler
        ReservationManager.schedule_reservation_lifecycle(
            reservation_id=str(reservation_id),
            reserved_from=request.reserved_from,
            reserved_until=request.reserved_until,
            grace_period_minutes=request.grace_period_minutes or 15
        )

        # Only trigger immediate reconciliation for immediate reservations
        # Future reservations will be activated by APScheduler at scheduled time
        if is_immediate:
            logger.info(f"Triggering immediate reconciliation for reservation {reservation_id}")
            await trigger_space_reconciliation(request.space_id)
        else:
            logger.info(f"Skipping reconciliation for future reservation {reservation_id} (starts at {reserved_from_utc.isoformat()})")

        response = {
            "status": "created",
            "reservation_id": str(reservation_id),
            "reservation_status": initial_status,
            "space_id": request.space_id,
            "reserved_from": request.reserved_from.isoformat(),
            "reserved_until": request.reserved_until.isoformat()
        }
        
        # Cache response for idempotency (24 hour TTL)
        if idempotency_key:
            await cache_response(idempotency_key, response)
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating reservation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_reservations(
    space_id: str = None,
    status: str = "active",
    db = Depends(get_db_dependency)
):
    """List reservations"""
    try:
        if space_id:
            query = """
                SELECT
                    r.reservation_id,
                    r.space_id,
                    r.reserved_from,
                    r.reserved_until,
                    r.external_booking_id,
                    r.external_system,
                    r.status,
                    s.space_name
                FROM parking_spaces.reservations r
                JOIN parking_spaces.spaces s ON r.space_id = s.space_id
                WHERE r.space_id = $1 AND r.status = $2
                ORDER BY r.reserved_from DESC
            """
            results = await db.fetch(query, space_id, status)
        else:
            query = """
                SELECT
                    r.reservation_id,
                    r.space_id,
                    r.reserved_from,
                    r.reserved_until,
                    r.external_booking_id,
                    r.external_system,
                    r.status,
                    s.space_name
                FROM parking_spaces.reservations r
                JOIN parking_spaces.spaces s ON r.space_id = s.space_id
                WHERE r.status = $1
                ORDER BY r.reserved_from DESC
            """
            results = await db.fetch(query, status)

        reservations = []
        for row in results:
            reservations.append({
                "reservation_id": str(row["reservation_id"]),
                "space_id": str(row["space_id"]),
                "space_name": row["space_name"],
                "reserved_from": row["reserved_from"].isoformat(),
                "reserved_until": row["reserved_until"].isoformat(),
                "external_booking_id": row["external_booking_id"],
                "external_system": row["external_system"],
                "status": row["status"]
            })

        return {"reservations": reservations, "count": len(reservations)}

    except Exception as e:
        logger.error(f"Error listing reservations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{reservation_id}")
async def cancel_reservation(reservation_id: str, db = Depends(get_db_dependency)):
    """Cancel a reservation"""
    try:
        # Get space_id before cancelling (needed for reconciliation trigger)
        space_id = await db.fetchval(
            "SELECT space_id FROM parking_spaces.reservations WHERE reservation_id = $1 AND status = 'active'",
            reservation_id
        )

        if not space_id:
            raise HTTPException(status_code=404, detail="Reservation not found or already cancelled")

        # Update reservation status
        result = await db.execute("""
            UPDATE parking_spaces.reservations
            SET status = 'cancelled',
                cancelled_at = NOW(),
                cancellation_reason = 'api_cancellation'
            WHERE reservation_id = $1 AND status = 'active'
        """, reservation_id)

        logger.info(f"Cancelled reservation {reservation_id}")
        # Cancel all scheduled jobs
        ReservationManager.cancel_reservation_jobs(str(reservation_id))


        # Trigger immediate reconciliation to update display instantly
        await trigger_space_reconciliation(str(space_id))

        return {
            "status": "cancelled",
            "reservation_id": reservation_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling reservation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
