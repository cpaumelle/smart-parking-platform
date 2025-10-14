from fastapi import APIRouter, Depends, HTTPException
import logging
import json
import sys
sys.path.append("/app")

from app.database import get_db_dependency
from app.models import ReservationRequest
from app.tasks.reconciliation import trigger_space_reconciliation

router = APIRouter()
logger = logging.getLogger("reservations")

@router.post("/")
async def create_reservation(request: ReservationRequest, db = Depends(get_db_dependency)):
    """Create new parking reservation"""
    try:
        # Verify space exists
        space_check = await db.fetchval(
            "SELECT space_id FROM parking_spaces.spaces WHERE space_id = $1 AND enabled = TRUE",
            request.space_id
        )

        if not space_check:
            raise HTTPException(status_code=404, detail="Parking space not found")

        # Insert reservation
        query = """
            INSERT INTO parking_spaces.reservations (
                space_id, reserved_from, reserved_until,
                external_booking_id, external_system, external_user_id,
                booking_metadata, reservation_type, grace_period_minutes,
                status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active')
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
            request.grace_period_minutes
        )

        logger.info(f"Created reservation {reservation_id} for space {request.space_id}")

        # Trigger immediate reconciliation to update display instantly
        await trigger_space_reconciliation(request.space_id)

        return {
            "status": "created",
            "reservation_id": str(reservation_id),
            "space_id": request.space_id,
            "reserved_from": request.reserved_from.isoformat(),
            "reserved_until": request.reserved_until.isoformat()
        }

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
