"""
Spaces Router - Full CRUD API for parking spaces
Ported from V4 and adapted to V5 schema
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional, List, Dict, Any
import logging
from uuid import UUID
from datetime import datetime

from ..models import (
    SpaceCreate, SpaceUpdate, Space, SpaceState,
    ReservationStatus
)

router = APIRouter(prefix="/api/v1/spaces", tags=["spaces"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any])
async def list_spaces(
    request: Request,
    building: Optional[str] = Query(None, description="Filter by building"),
    floor: Optional[str] = Query(None, description="Filter by floor"),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    state: Optional[SpaceState] = Query(None, description="Filter by current state"),
    include_deleted: bool = Query(False, description="Include soft-deleted spaces")
):
    """
    List all parking spaces with optional filters

    Returns spaces with basic info (no device details)
    """
    try:
        db_pool = request.app.state.db_pool
        # Build dynamic query with filters
        conditions = []
        params = []
        param_count = 1

        if building is not None:
            conditions.append(f"s.building = ${param_count}")
            params.append(building)
            param_count += 1

        if floor is not None:
            conditions.append(f"s.floor = ${param_count}")
            params.append(floor)
            param_count += 1

        if zone is not None:
            conditions.append(f"s.zone = ${param_count}")
            params.append(zone)
            param_count += 1

        if state is not None:
            conditions.append(f"s.state = ${param_count}")
            params.append(state.value)
            param_count += 1

        # Add soft delete filter
        if not include_deleted:
            conditions.append("s.deleted_at IS NULL")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                s.id,
                s.name,
                s.code,
                s.building,
                s.floor,
                s.zone,
                s.state,
                s.sensor_eui,
                s.display_eui,
                s.gps_latitude,
                s.gps_longitude,
                s.metadata,
                s.created_at,
                s.updated_at,
                s.deleted_at
            FROM spaces s
            {where_clause}
            ORDER BY s.name
        """

        results = await db_pool.fetch(query, *params)

        spaces = []
        for row in results:
            spaces.append({
                "id": str(row["id"]),
                "name": row["name"],
                "code": row["code"],
                "building": row["building"],
                "floor": row["floor"],
                "zone": row["zone"],
                "state": row["state"],
                "sensor_eui": row["sensor_eui"],
                "display_eui": row["display_eui"],
                "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
                "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
                "metadata": row["metadata"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "deleted_at": row["deleted_at"].isoformat() if row["deleted_at"] else None
            })

        logger.info(f"List spaces: count={len(spaces)} filters={len(conditions)}")
        return {"spaces": spaces, "count": len(spaces)}

    except Exception as e:
        logger.error(f"Error listing spaces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensor-list", response_model=Dict[str, Any])
async def get_sensor_list(request: Request):
    """
    Get list of active sensor DevEUIs mapped to space IDs

    Used by ingest service for caching sensor → space mappings
    """
    try:
        db_pool = request.app.state.db_pool
        query = """
            SELECT
                s.sensor_eui,
                s.id as space_id
            FROM spaces s
            WHERE s.deleted_at IS NULL
              AND s.sensor_eui IS NOT NULL
        """

        results = await db_pool.fetch(query)

        sensor_deveuis = []
        sensor_to_space = {}

        for row in results:
            dev_eui = row["sensor_eui"]
            space_id = str(row["space_id"])
            sensor_deveuis.append(dev_eui)
            sensor_to_space[dev_eui] = space_id

        logger.info(f"Sensor list: count={len(sensor_deveuis)}")
        return {
            "sensor_deveuis": sensor_deveuis,
            "sensor_to_space": sensor_to_space,
            "count": len(sensor_deveuis)
        }

    except Exception as e:
        logger.error(f"Error getting sensor list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{space_id}/availability", response_model=Dict[str, Any])
async def get_space_availability(
    request: Request,
    space_id: UUID,
    from_time: datetime = Query(..., alias="from", description="Start of availability check period (ISO 8601)"),
    to_time: datetime = Query(..., alias="to", description="End of availability check period (ISO 8601)")
):
    """
    Check parking space availability for a given time range

    Returns:
    - is_available: True if no confirmed/pending reservations overlap with the requested period
    - reservations: List of all reservations overlapping with the period
    - current_state: Current space state from sensor/manual updates

    The DB EXCLUDE constraint prevents overlapping confirmed/pending reservations,
    so this endpoint queries the DB truth without cache correctness bugs.
    """
    try:
        db_pool = request.app.state.db_pool

        # Validate time range
        if to_time <= from_time:
            raise HTTPException(
                status_code=400,
                detail="'to' time must be after 'from' time"
            )

        # Check space exists
        space_query = """
            SELECT id, code, name, state, tenant_id
            FROM spaces
            WHERE id = $1 AND deleted_at IS NULL
        """
        space = await db_pool.fetchrow(space_query, str(space_id))

        if not space:
            raise HTTPException(
                status_code=404,
                detail=f"Space {space_id} not found"
            )

        # Find all reservations overlapping with the requested period
        # Uses PostgreSQL range overlap operator &&
        reservations_query = """
            SELECT
                id,
                space_id,
                tenant_id,
                start_time,
                end_time,
                status,
                user_email,
                user_phone,
                metadata,
                created_at,
                updated_at
            FROM reservations
            WHERE space_id = $1
              AND status IN ('pending', 'confirmed')
              AND tstzrange(start_time, end_time, '[)') && tstzrange($2, $3, '[)')
            ORDER BY start_time ASC
        """

        reservation_rows = await db_pool.fetch(
            reservations_query,
            str(space_id),
            from_time,
            to_time
        )

        # Convert to response format
        reservations = []
        for row in reservation_rows:
            reservations.append({
                "id": str(row["id"]),
                "space_id": str(row["space_id"]),
                "tenant_id": str(row["tenant_id"]),
                "start_time": row["start_time"].isoformat(),
                "end_time": row["end_time"].isoformat(),
                "status": row["status"],
                "user_email": row["user_email"],
                "user_phone": row["user_phone"],
                "metadata": row["metadata"] or {},
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            })

        # Space is available if no overlapping reservations
        is_available = len(reservations) == 0

        logger.info(
            f"Availability check for space {space['code']}: "
            f"{from_time.isoformat()} to {to_time.isoformat()} - "
            f"{'AVAILABLE' if is_available else 'OCCUPIED'} "
            f"({len(reservations)} overlapping reservations)"
        )

        return {
            "space_id": str(space["id"]),
            "space_code": space["code"],
            "space_name": space["name"],
            "query_start": from_time.isoformat(),
            "query_end": to_time.isoformat(),
            "is_available": is_available,
            "reservations": reservations,
            "current_state": space["state"],
            "tenant_id": str(space["tenant_id"]) if space["tenant_id"] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking availability for space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{space_id}", response_model=Dict[str, Any])
async def get_space(
    request: Request,
    space_id: UUID
):
    """
    Get detailed information about a parking space

    Returns space with device details and active reservation
    """
    try:
        db_pool = request.app.state.db_pool
        # Main space query with device details
        query = """
            SELECT
                s.id,
                s.name,
                s.code,
                s.building,
                s.floor,
                s.zone,
                s.gps_latitude,
                s.gps_longitude,
                s.sensor_eui,
                s.display_eui,
                s.state,
                s.metadata,
                s.created_at,
                s.updated_at,
                s.deleted_at,
                -- Sensor details
                sd.device_type as sensor_type,
                sd.device_model as sensor_model,
                sd.manufacturer as sensor_manufacturer,
                sd.last_seen_at as sensor_last_seen,
                -- Display details
                dd.device_type as display_type,
                dd.device_model as display_model,
                dd.manufacturer as display_manufacturer,
                dd.last_seen_at as display_last_seen
            FROM spaces s
            LEFT JOIN sensor_devices sd ON s.sensor_device_id = sd.id
            LEFT JOIN display_devices dd ON s.display_device_id = dd.id
            WHERE s.id = $1
        """

        space = await db_pool.fetchrow(query, str(space_id))

        if not space:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

        # Check for active reservation
        reservation_query = """
            SELECT
                id,
                start_time,
                end_time,
                user_email,
                user_phone,
                status,
                metadata
            FROM reservations
            WHERE space_id = $1
              AND status IN ('pending', 'confirmed')
              AND end_time > NOW()
            ORDER BY start_time DESC
            LIMIT 1
        """

        active_reservation = await db_pool.fetchrow(reservation_query, str(space_id))

        # Get most recent state change
        state_change_query = """
            SELECT
                previous_state,
                new_state,
                source,
                timestamp
            FROM state_changes
            WHERE space_id = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """

        last_state_change = await db_pool.fetchrow(state_change_query, str(space_id))

        # Build sensor details
        sensor_details = None
        if space["sensor_type"]:
            sensor_details = {
                "sensor_type": space["sensor_type"],
                "model": space["sensor_model"],
                "manufacturer": space["sensor_manufacturer"],
                "last_seen": space["sensor_last_seen"].isoformat() if space["sensor_last_seen"] else None
            }

        # Build display details
        display_details = None
        if space["display_type"]:
            display_details = {
                "display_type": space["display_type"],
                "model": space["display_model"],
                "manufacturer": space["display_manufacturer"],
                "last_seen": space["display_last_seen"].isoformat() if space["display_last_seen"] else None
            }

        # Build reservation details
        reservation_details = None
        if active_reservation:
            reservation_details = {
                "id": str(active_reservation["id"]),
                "start_time": active_reservation["start_time"].isoformat(),
                "end_time": active_reservation["end_time"].isoformat(),
                "user_email": active_reservation["user_email"],
                "user_phone": active_reservation["user_phone"],
                "status": active_reservation["status"],
                "metadata": active_reservation["metadata"]
            }

        # Build state change details
        state_change_details = None
        if last_state_change:
            state_change_details = {
                "previous_state": last_state_change["previous_state"],
                "new_state": last_state_change["new_state"],
                "source": last_state_change["source"],
                "timestamp": last_state_change["timestamp"].isoformat()
            }

        return {
            "id": str(space["id"]),
            "name": space["name"],
            "code": space["code"],
            "building": space["building"],
            "floor": space["floor"],
            "zone": space["zone"],
            "gps_latitude": float(space["gps_latitude"]) if space["gps_latitude"] else None,
            "gps_longitude": float(space["gps_longitude"]) if space["gps_longitude"] else None,
            "sensor_eui": space["sensor_eui"],
            "display_eui": space["display_eui"],
            "sensor_details": sensor_details,
            "display_details": display_details,
            "state": space["state"],
            "last_state_change": state_change_details,
            "metadata": space["metadata"],
            "active_reservation": reservation_details,
            "created_at": space["created_at"].isoformat() if space["created_at"] else None,
            "updated_at": space["updated_at"].isoformat() if space["updated_at"] else None,
            "deleted_at": space["deleted_at"].isoformat() if space["deleted_at"] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict[str, Any])
async def create_space(
    request: Request,
    space_data: SpaceCreate
):
    """
    Create new parking space

    Validates that sensor and display devices exist if provided
    """
    try:
        db_pool = request.app.state.db_pool
        # Lookup sensor_device_id and display_device_id from dev_euis
        sensor_device_id = None
        display_device_id = None

        if space_data.sensor_eui:
            sensor_device_id = await db_pool.fetchval(
                "SELECT id FROM sensor_devices WHERE dev_eui = $1",
                space_data.sensor_eui
            )
            if not sensor_device_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sensor device {space_data.sensor_eui} not found in registry"
                )

        if space_data.display_eui:
            display_device_id = await db_pool.fetchval(
                "SELECT id FROM display_devices WHERE dev_eui = $1",
                space_data.display_eui
            )
            if not display_device_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Display device {space_data.display_eui} not found in registry"
                )

        # Insert space
        query = """
            INSERT INTO spaces (
                name, code, building, floor, zone,
                gps_latitude, gps_longitude,
                sensor_eui, display_eui,
                sensor_device_id, display_device_id,
                state, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING id, name, code
        """

        result = await db_pool.fetchrow(
            query,
            space_data.name,
            space_data.code,
            space_data.building,
            space_data.floor,
            space_data.zone,
            space_data.gps_latitude,
            space_data.gps_longitude,
            space_data.sensor_eui,
            space_data.display_eui,
            sensor_device_id,
            display_device_id,
            space_data.state.value,
            space_data.metadata
        )

        logger.info(f"Created parking space: {space_data.name} ({result['id']})")

        return {
            "status": "created",
            "id": str(result["id"]),
            "name": result["name"],
            "code": result["code"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{space_id}", response_model=Dict[str, Any])
@router.patch("/{space_id}", response_model=Dict[str, Any])
async def update_space(
    request: Request,
    space_id: UUID,
    space_data: SpaceUpdate
):
    """
    Update parking space attributes

    Supports partial updates (PATCH) - only provided fields are updated
    """
    try:
        db_pool = request.app.state.db_pool
        # Check space exists
        existing = await db_pool.fetchval(
            "SELECT id FROM spaces WHERE id = $1 AND deleted_at IS NULL",
            str(space_id)
        )

        if not existing:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

        # Build update query dynamically based on provided fields
        updates = []
        params = []
        param_count = 1

        # Always update updated_at
        updates.append(f"updated_at = NOW()")

        if space_data.name is not None:
            updates.append(f"name = ${param_count}")
            params.append(space_data.name)
            param_count += 1

        if space_data.code is not None:
            updates.append(f"code = ${param_count}")
            params.append(space_data.code)
            param_count += 1

        if space_data.building is not None:
            updates.append(f"building = ${param_count}")
            params.append(space_data.building)
            param_count += 1

        if space_data.floor is not None:
            updates.append(f"floor = ${param_count}")
            params.append(space_data.floor)
            param_count += 1

        if space_data.zone is not None:
            updates.append(f"zone = ${param_count}")
            params.append(space_data.zone)
            param_count += 1

        if space_data.state is not None:
            updates.append(f"state = ${param_count}")
            params.append(space_data.state.value)
            param_count += 1

        if space_data.metadata is not None:
            updates.append(f"metadata = ${param_count}")
            params.append(space_data.metadata)
            param_count += 1

        # Handle sensor device change
        if space_data.sensor_eui is not None:
            sensor_device_id = await db_pool.fetchval(
                "SELECT id FROM sensor_devices WHERE dev_eui = $1",
                space_data.sensor_eui
            )
            if not sensor_device_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Sensor device {space_data.sensor_eui} not found in registry"
                )

            updates.append(f"sensor_device_id = ${param_count}")
            params.append(sensor_device_id)
            param_count += 1

            updates.append(f"sensor_eui = ${param_count}")
            params.append(space_data.sensor_eui)
            param_count += 1

        # Handle display device change
        if space_data.display_eui is not None:
            display_device_id = await db_pool.fetchval(
                "SELECT id FROM display_devices WHERE dev_eui = $1",
                space_data.display_eui
            )
            if not display_device_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Display device {space_data.display_eui} not found in registry"
                )

            updates.append(f"display_device_id = ${param_count}")
            params.append(display_device_id)
            param_count += 1

            updates.append(f"display_eui = ${param_count}")
            params.append(space_data.display_eui)
            param_count += 1

        if not updates or updates == ["updated_at = NOW()"]:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Add space_id as last parameter
        params.append(str(space_id))
        space_id_param = f"${param_count}"

        update_query = f"""
            UPDATE spaces
            SET {", ".join(updates)}
            WHERE id = {space_id_param}
            RETURNING id, name, code
        """

        result = await db_pool.fetchrow(update_query, *params)

        logger.info(f"Updated parking space: {result['name']} ({space_id})")

        return {
            "status": "updated",
            "id": str(result["id"]),
            "name": result["name"],
            "code": result["code"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{space_id}", response_model=Dict[str, Any])
async def delete_space(
    request: Request,
    space_id: UUID,
    force: bool = Query(False, description="Force delete even with active reservations")
):
    """
    Soft delete parking space (set deleted_at timestamp)

    Preserves all historical data. Use force=true to delete with active reservations.
    """
    try:
        db_pool = request.app.state.db_pool
        # Check space exists and not already deleted
        existing = await db_pool.fetchrow(
            "SELECT id, name, deleted_at FROM spaces WHERE id = $1",
            str(space_id)
        )

        if not existing:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

        if existing["deleted_at"]:
            raise HTTPException(status_code=400, detail=f"Space {space_id} is already deleted")

        # Check for active reservations
        active_reservations = await db_pool.fetchval(
            "SELECT COUNT(*) FROM reservations WHERE space_id = $1 AND status = 'active' AND end_time > NOW()",
            str(space_id)
        )

        if active_reservations > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail=f"Space has {active_reservations} active reservation(s). Use force=true to delete anyway."
            )

        # If force, cancel active reservations
        reservations_cancelled = 0
        if force and active_reservations > 0:
            await db_pool.execute("""
                UPDATE reservations
                SET status = 'cancelled',
                    updated_at = NOW()
                WHERE space_id = $1 AND status = 'active' AND end_time > NOW()
            """, str(space_id))
            reservations_cancelled = active_reservations
            logger.info(f"Cancelled {active_reservations} reservation(s) for deleting space {space_id}")

        # Soft delete - set deleted_at
        result = await db_pool.fetchrow("""
            UPDATE spaces
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            RETURNING deleted_at
        """, str(space_id))

        logger.info(f"Deleted (soft) parking space: {existing['name']} ({space_id})")

        return {
            "status": "deleted",
            "id": str(space_id),
            "name": existing["name"],
            "deleted_at": result["deleted_at"].isoformat(),
            "reservations_cancelled": reservations_cancelled
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{space_id}/restore", response_model=Dict[str, Any])
async def restore_space(
    request: Request,
    space_id: UUID
):
    """
    Restore a soft-deleted parking space

    Clears the deleted_at timestamp, making the space active again
    """
    try:
        db_pool = request.app.state.db_pool
        # Check space exists and is deleted
        existing = await db_pool.fetchrow(
            "SELECT id, name, deleted_at FROM spaces WHERE id = $1",
            str(space_id)
        )

        if not existing:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

        if not existing["deleted_at"]:
            raise HTTPException(status_code=400, detail=f"Space {space_id} is not deleted")

        # Restore the space
        await db_pool.execute("""
            UPDATE spaces
            SET deleted_at = NULL,
                updated_at = NOW()
            WHERE id = $1
        """, str(space_id))

        logger.info(f"Restored parking space: {existing['name']} ({space_id})")

        return {
            "status": "restored",
            "id": str(space_id),
            "name": existing["name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{space_id}/availability", response_model=Dict[str, Any])
async def get_space_availability(
    request: Request,
    space_id: UUID,
    from_time: datetime = Query(..., alias="from", description="Start of availability check period (ISO 8601)"),
    to_time: datetime = Query(..., alias="to", description="End of availability check period (ISO 8601)")
):
    """
    Check parking space availability for a given time range

    Returns:
    - is_available: True if no confirmed/pending reservations overlap with the requested period
    - reservations: List of all reservations overlapping with the period
    - current_state: Current space state from sensor/manual updates

    The DB EXCLUDE constraint prevents overlapping confirmed/pending reservations,
    so this endpoint queries the DB truth without cache correctness bugs.
    """
    try:
        db_pool = request.app.state.db_pool

        # Validate time range
        if to_time <= from_time:
            raise HTTPException(
                status_code=400,
                detail="'to' time must be after 'from' time"
            )

        # Check space exists
        space_query = """
            SELECT id, code, name, state, tenant_id
            FROM spaces
            WHERE id = $1 AND deleted_at IS NULL
        """
        space = await db_pool.fetchrow(space_query, str(space_id))

        if not space:
            raise HTTPException(
                status_code=404,
                detail=f"Space {space_id} not found"
            )

        # Find all reservations overlapping with the requested period
        # Uses PostgreSQL range overlap operator &&
        reservations_query = """
            SELECT
                id,
                space_id,
                tenant_id,
                start_time,
                end_time,
                status,
                user_email,
                user_phone,
                metadata,
                created_at,
                updated_at
            FROM reservations
            WHERE space_id = $1
              AND status IN ('pending', 'confirmed')
              AND tstzrange(start_time, end_time, '[)') && tstzrange($2, $3, '[)')
            ORDER BY start_time ASC
        """

        reservation_rows = await db_pool.fetch(
            reservations_query,
            str(space_id),
            from_time,
            to_time
        )

        # Convert to response format
        reservations = []
        for row in reservation_rows:
            reservations.append({
                "id": str(row["id"]),
                "space_id": str(row["space_id"]),
                "tenant_id": str(row["tenant_id"]),
                "start_time": row["start_time"].isoformat(),
                "end_time": row["end_time"].isoformat(),
                "status": row["status"],
                "user_email": row["user_email"],
                "user_phone": row["user_phone"],
                "metadata": row["metadata"] or {},
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            })

        # Space is available if no overlapping reservations
        is_available = len(reservations) == 0

        logger.info(
            f"Availability check for space {space['code']}: "
            f"{from_time.isoformat()} to {to_time.isoformat()} - "
            f"{'AVAILABLE' if is_available else 'OCCUPIED'} "
            f"({len(reservations)} overlapping reservations)"
        )

        return {
            "space_id": str(space["id"]),
            "space_code": space["code"],
            "space_name": space["name"],
            "query_start": from_time.isoformat(),
            "query_end": to_time.isoformat(),
            "is_available": is_available,
            "reservations": reservations,
            "current_state": space["state"],
            "tenant_id": str(space["tenant_id"]) if space["tenant_id"] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking availability for space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
