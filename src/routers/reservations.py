# src/routers/reservations.py
# Reservations API Router for V5 Smart Parking Platform
# Handles parking space reservations with V4 compatibility
# Multi-tenancy enabled with tenant scoping

from fastapi import APIRouter, Request, Query, HTTPException, status, Depends
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import json
import logging

from ..models import TenantContext
from ..tenant_auth import require_viewer, require_admin
from ..api_scopes import require_scopes

router = APIRouter(prefix="/api/v1/reservations", tags=["reservations"])
logger = logging.getLogger(__name__)

class ReservationCreate(BaseModel):
    """Request model for creating a reservation (V4 API compatible)"""
    id: uuid.UUID  # This is space_id in V4 API format
    reserved_from: datetime
    reserved_until: datetime
    request_id: Optional[uuid.UUID] = None  # For idempotency (auto-generated if not provided)
    external_booking_id: Optional[str] = None
    external_system: Optional[str] = None
    reservation_type: Optional[str] = None
    grace_period_minutes: Optional[int] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None

@router.get("/", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("reservations:read"))])
async def list_reservations(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active, completed, cancelled, no_show"),
    tenant: TenantContext = Depends(require_viewer)
):
    """
    List all reservations for the current tenant

    Returns reservations in V4-compatible format with:
    - id: space_id (for UI compatibility)
    - reservation_id: actual reservation UUID
    - reserved_from/reserved_until: V4 field names

    Requires: VIEWER role or higher, API key requires reservations:read scope
    """
    try:
        db_pool = request.app.state.db_pool

        # Always filter by tenant_id
        conditions = ["r.tenant_id = $1"]
        params = [tenant.tenant_id]

        if status_filter:
            conditions.append(f"r.status = ${len(params) + 1}")
            params.append(status_filter)

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT
                r.id as reservation_id,
                r.space_id as id,
                r.start_time as reserved_from,
                r.end_time as reserved_until,
                r.status,
                r.user_email,
                r.user_phone,
                r.metadata,
                r.created_at,
                r.updated_at
            FROM reservations r
            {where_clause}
            ORDER BY r.start_time DESC
        """

        results = await db_pool.fetch(query, *params)
        logger.info(f"[Tenant:{tenant.tenant_id}] List reservations: count={len(results)}")

        reservations = []
        for row in results:
            res_dict = {
                "reservation_id": str(row["reservation_id"]),
                "id": str(row["id"]),  # space_id
                "reserved_from": row["reserved_from"].isoformat(),
                "reserved_until": row["reserved_until"].isoformat(),
                "status": row["status"],
                "user_email": row["user_email"],
                "user_phone": row["user_phone"],
                "metadata": row["metadata"] if row["metadata"] else {},
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
            reservations.append(res_dict)

        return {"reservations": reservations, "count": len(reservations)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reservations: {str(e)}"
        )

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_reservation(
    request: Request,
    reservation: ReservationCreate
):
    """
    Create a new reservation for a parking space

    Accepts V4-compatible request format and returns V4-compatible response

    Idempotency: Provide a request_id to ensure duplicate requests create only one reservation.
    If a reservation with the same request_id already exists, it will be returned instead of creating a new one.
    """
    try:
        db_pool = request.app.state.db_pool

        # Generate request_id if not provided (for idempotency)
        request_id = reservation.request_id or uuid.uuid4()

        # Check if request_id already exists (idempotency check)
        existing = await db_pool.fetchrow("""
            SELECT
                id as reservation_id,
                space_id as id,
                start_time as reserved_from,
                end_time as reserved_until,
                status,
                user_email,
                user_phone,
                metadata,
                created_at
            FROM reservations
            WHERE request_id = $1
        """, request_id)

        if existing:
            # Idempotent return - reservation already exists
            return {
                "reservation_id": str(existing["reservation_id"]),
                "id": str(existing["id"]),  # space_id
                "reserved_from": existing["reserved_from"].isoformat(),
                "reserved_until": existing["reserved_until"].isoformat(),
                "status": existing["status"],
                "user_email": existing["user_email"],
                "user_phone": existing["user_phone"],
                "metadata": existing["metadata"] if existing["metadata"] else {},
                "created_at": existing["created_at"].isoformat(),
                "idempotent": True  # Indicates this was a duplicate request
            }

        # Verify space exists
        space_check = await db_pool.fetchrow(
            "SELECT id, name, tenant_id FROM spaces WHERE id = $1 AND deleted_at IS NULL",
            reservation.id
        )

        if not space_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Space with ID {reservation.id} not found"
            )

        # Build metadata from extra fields
        metadata = {}
        if reservation.external_booking_id:
            metadata["external_booking_id"] = reservation.external_booking_id
        if reservation.external_system:
            metadata["external_system"] = reservation.external_system
        if reservation.reservation_type:
            metadata["reservation_type"] = reservation.reservation_type
        if reservation.grace_period_minutes is not None:
            metadata["grace_period_minutes"] = reservation.grace_period_minutes

        # Create reservation with request_id and tenant_id
        query = """
            INSERT INTO reservations (
                space_id, start_time, end_time, user_email, user_phone, status, metadata, request_id, tenant_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING
                id as reservation_id,
                space_id as id,
                start_time as reserved_from,
                end_time as reserved_until,
                status,
                user_email,
                user_phone,
                metadata,
                created_at
        """

        try:
            result = await db_pool.fetchrow(
                query,
                reservation.id,  # space_id
                reservation.reserved_from,
                reservation.reserved_until,
                reservation.user_email,
                reservation.user_phone,
                "confirmed",  # v5.3: use "confirmed" instead of "active"
                json.dumps(metadata) if metadata else None,
                request_id,
                space_check['tenant_id']  # tenant_id from space
            )

            return {
                "reservation_id": str(result["reservation_id"]),
                "id": str(result["id"]),  # space_id
                "reserved_from": result["reserved_from"].isoformat(),
                "reserved_until": result["reserved_until"].isoformat(),
                "status": result["status"],
                "user_email": result["user_email"],
                "user_phone": result["user_phone"],
                "metadata": result["metadata"] if result["metadata"] else {},
                "created_at": result["created_at"].isoformat()
            }

        except Exception as db_error:
            error_msg = str(db_error).lower()

            # Handle unique constraint violation (race condition on request_id)
            if "unique" in error_msg and "request_id" in error_msg:
                # Race condition - another request with same request_id succeeded
                # Fetch and return the existing reservation
                existing = await db_pool.fetchrow("""
                    SELECT
                        id as reservation_id,
                        space_id as id,
                        start_time as reserved_from,
                        end_time as reserved_until,
                        status,
                        user_email,
                        user_phone,
                        metadata,
                        created_at
                    FROM reservations
                    WHERE request_id = $1
                """, request_id)

                if existing:
                    return {
                        "reservation_id": str(existing["reservation_id"]),
                        "id": str(existing["id"]),  # space_id
                        "reserved_from": existing["reserved_from"].isoformat(),
                        "reserved_until": existing["reserved_until"].isoformat(),
                        "status": existing["status"],
                        "user_email": existing["user_email"],
                        "user_phone": existing["user_phone"],
                        "metadata": existing["metadata"] if existing["metadata"] else {},
                        "created_at": existing["created_at"].isoformat(),
                        "idempotent": True
                    }

            # Handle overlap constraint violation (EXCLUDE constraint)
            if "exclusion" in error_msg or "no_reservation_overlap" in error_msg:
                # Fetch the conflicting reservation(s) for better error message
                conflicting = await db_pool.fetch("""
                    SELECT id, start_time, end_time, status, user_email
                    FROM reservations
                    WHERE space_id = $1
                      AND status IN ('pending', 'confirmed')
                      AND tstzrange(start_time, end_time, '[)') && tstzrange($2, $3, '[)')
                    ORDER BY start_time
                    LIMIT 3
                """, reservation.id, reservation.reserved_from, reservation.reserved_until)

                conflict_details = []
                for res in conflicting:
                    conflict_details.append({
                        "reservation_id": str(res['id']),
                        "start_time": res['start_time'].isoformat(),
                        "end_time": res['end_time'].isoformat(),
                        "status": res['status'],
                        "user_email": res['user_email']
                    })

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "reservation_conflict",
                        "message": f"Reservation conflicts with {len(conflicting)} existing reservation(s) for space {reservation.id}",
                        "requested": {
                            "space_id": str(reservation.id),
                            "start_time": reservation.reserved_from.isoformat(),
                            "end_time": reservation.reserved_until.isoformat()
                        },
                        "conflicts": conflict_details
                    }
                )

            # Re-raise other database errors
            raise

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reservation: {str(e)}"
        )

@router.delete("/{reservation_id}")
async def cancel_reservation(
    request: Request,
    reservation_id: uuid.UUID,
    reason: Optional[str] = Query(None, description="Cancellation reason")
):
    """
    Cancel a reservation by setting its status to 'cancelled'

    Optionally accepts a cancellation reason which is stored in metadata
    """
    try:
        db_pool = request.app.state.db_pool

        # Update metadata with cancellation reason if provided
        if reason:
            query = """
                UPDATE reservations
                SET status = 'cancelled',
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{cancellation_reason}',
                        to_jsonb($2::text)
                    )
                WHERE id = $1
                RETURNING id, space_id, status
            """
            result = await db_pool.fetchrow(query, reservation_id, reason)
        else:
            query = """
                UPDATE reservations
                SET status = 'cancelled'
                WHERE id = $1
                RETURNING id, space_id, status
            """
            result = await db_pool.fetchrow(query, reservation_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation {reservation_id} not found"
            )

        return {
            "message": "Reservation cancelled successfully",
            "reservation_id": str(result["id"]),
            "space_id": str(result["space_id"]),
            "status": result["status"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel reservation: {str(e)}"
        )

@router.get("/{reservation_id}", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("reservations:read"))])
async def get_reservation(
    request: Request,
    reservation_id: uuid.UUID,
    tenant: TenantContext = Depends(require_viewer)
):
    """
    Get details of a specific reservation

    Requires: VIEWER role or higher, API key requires reservations:read scope
    """
    try:
        db_pool = request.app.state.db_pool

        query = """
            SELECT
                r.id as reservation_id,
                r.space_id as id,
                r.start_time as reserved_from,
                r.end_time as reserved_until,
                r.status,
                r.user_email,
                r.user_phone,
                r.metadata,
                r.created_at,
                r.updated_at,
                s.name as space_name,
                s.code as space_code
            FROM reservations r
            JOIN spaces s ON s.id = r.space_id
            WHERE r.id = $1 AND r.tenant_id = $2
        """

        result = await db_pool.fetchrow(query, reservation_id, tenant.tenant_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation {reservation_id} not found"
            )

        return {
            "reservation_id": str(result["reservation_id"]),
            "id": str(result["id"]),  # space_id
            "reserved_from": result["reserved_from"].isoformat(),
            "reserved_until": result["reserved_until"].isoformat(),
            "status": result["status"],
            "user_email": result["user_email"],
            "user_phone": result["user_phone"],
            "metadata": result["metadata"] if result["metadata"] else {},
            "created_at": result["created_at"].isoformat(),
            "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
            "space_name": result["space_name"],
            "space_code": result["space_code"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reservation: {str(e)}"
        )
