from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging
import sys
sys.path.append("/app")

from app.dependencies import get_authenticated_tenant
from app.utils.tenant_context import get_tenant_db
from app.models import CreateSpaceRequest, UpdateSpaceRequest, SpaceDetailResponse

router = APIRouter()
logger = logging.getLogger("spaces")

@router.get("/")
async def list_spaces(
    building: Optional[str] = Query(None, description="Filter by building"),
    floor: Optional[str] = Query(None, description="Filter by floor"),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    state: Optional[str] = Query(None, description="Filter by current state"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    include_archived: bool = Query(False, description="Include archived spaces"),
    auth = Depends(get_authenticated_tenant)
):
    """List all parking spaces with optional filters (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
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
                conditions.append(f"s.current_state = ${param_count}")
                params.append(state)
                param_count += 1

            if enabled is not None:
                conditions.append(f"s.enabled = ${param_count}")
                params.append(enabled)
                param_count += 1


            # Add archived filter
            if not include_archived:
                conditions.append("s.archived = FALSE")

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            query = f"""
                SELECT
                    s.space_id,
                    s.space_name,
                    s.space_code,
                    s.building,
                    s.floor,
                    s.zone,
                    s.current_state,
                    s.occupancy_sensor_deveui,
                    s.display_device_deveui,
                    s.enabled,
                    s.maintenance_mode
                FROM parking_spaces.spaces s
                {where_clause}
                ORDER BY s.space_name
            """

            results = await db.fetch(query, *params)

            spaces = []
            for row in results:
                spaces.append({
                    "space_id": str(row["space_id"]),
                    "space_name": row["space_name"],
                    "space_code": row["space_code"],
                    "building": row["building"],
                    "floor": row["floor"],
                    "zone": row["zone"],
                    "current_state": row["current_state"],
                    "occupancy_sensor_deveui": row["occupancy_sensor_deveui"],
                    "display_device_deveui": row["display_device_deveui"],
                    "enabled": row["enabled"],
                    "maintenance_mode": row["maintenance_mode"]
                })

            logger.info(f"List spaces: tenant={auth.tenant_slug} count={len(spaces)}")
            return {"spaces": spaces, "count": len(spaces)}

    except Exception as e:
        logger.error(f"Error listing spaces (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-list")
async def get_sensor_list(auth = Depends(get_authenticated_tenant)):
    """Get list of parking sensor DevEUIs for Ingest Service cache (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            query = """
                SELECT
                    s.occupancy_sensor_deveui,
                    s.space_id
                FROM parking_spaces.spaces s
                WHERE s.enabled = TRUE
                  AND s.occupancy_sensor_deveui IS NOT NULL
            """

            results = await db.fetch(query)

            sensor_deveuis = []
            sensor_to_space = {}

            for row in results:
                dev_eui = row["occupancy_sensor_deveui"]
                space_id = str(row["space_id"])
                sensor_deveuis.append(dev_eui)
                sensor_to_space[dev_eui] = space_id

            logger.info(f"Sensor list: tenant={auth.tenant_slug} count={len(sensor_deveuis)}")
            return {
                "sensor_deveuis": sensor_deveuis,
                "sensor_to_space": sensor_to_space,
                "count": len(sensor_deveuis)
            }

    except Exception as e:
        logger.error(f"Error getting sensor list (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{space_id}")
async def get_space(
    space_id: str,
    auth = Depends(get_authenticated_tenant)
):
    """Get detailed information about a parking space (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Main space query with device details
            query = """
                SELECT
                    s.space_id,
                    s.space_name,
                    s.space_code,
                    s.location_description,
                    s.building,
                    s.floor,
                    s.zone,
                    s.gps_latitude,
                    s.gps_longitude,
                    s.occupancy_sensor_deveui,
                    s.display_device_deveui,
                    s.current_state,
                    s.sensor_state,
                    s.display_state,
                    s.last_sensor_update,
                    s.last_display_update,
                    s.state_changed_at,
                    s.auto_actuation,
                    s.reservation_priority,
                    s.enabled,
                    s.maintenance_mode,
                    s.space_metadata,
                    s.notes,
                    s.created_at,
                    s.updated_at,
                    -- Sensor details
                    sr.sensor_type,
                    sr.device_model as sensor_model,
                    sr.manufacturer as sensor_manufacturer,
                    -- Display details
                    dr.display_type,
                    dr.device_model as display_model,
                    dr.manufacturer as display_manufacturer
                FROM parking_spaces.spaces s
                LEFT JOIN parking_config.sensor_registry sr ON s.occupancy_sensor_id = sr.sensor_id
                LEFT JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
                WHERE s.space_id = $1
            """

            space = await db.fetchrow(query, space_id)

            # RLS will automatically filter - if space not found, could be:
            # 1. Space doesn't exist, OR
            # 2. Space belongs to different tenant (RLS blocked)
            # Both return 404 (correct - don't leak tenant information)
            if not space:
                raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

            # Check for active reservation
            reservation_query = """
                SELECT
                    reservation_id,
                    reserved_from,
                    reserved_until,
                    external_booking_id,
                    external_system,
                    status
                FROM parking_spaces.reservations
                WHERE space_id = $1 AND status = 'active'
                ORDER BY reserved_from DESC
                LIMIT 1
            """

            active_reservation = await db.fetchrow(reservation_query, space_id)

            # Build sensor details
            sensor_details = None
            if space["sensor_type"]:
                sensor_details = {
                    "sensor_type": space["sensor_type"],
                    "model": space["sensor_model"],
                    "manufacturer": space["sensor_manufacturer"]
                }

            # Build display details
            display_details = None
            if space["display_type"]:
                display_details = {
                    "display_type": space["display_type"],
                    "model": space["display_model"],
                    "manufacturer": space["display_manufacturer"]
                }

            # Build reservation details
            reservation_details = None
            if active_reservation:
                reservation_details = {
                    "reservation_id": str(active_reservation["reservation_id"]),
                    "reserved_from": active_reservation["reserved_from"].isoformat(),
                    "reserved_until": active_reservation["reserved_until"].isoformat(),
                    "external_booking_id": active_reservation["external_booking_id"],
                    "external_system": active_reservation["external_system"],
                    "status": active_reservation["status"]
                }

            return {
                "space_id": str(space["space_id"]),
                "space_name": space["space_name"],
                "space_code": space["space_code"],
                "location_description": space["location_description"],
                "building": space["building"],
                "floor": space["floor"],
                "zone": space["zone"],
                "gps_latitude": float(space["gps_latitude"]) if space["gps_latitude"] else None,
                "gps_longitude": float(space["gps_longitude"]) if space["gps_longitude"] else None,
                "occupancy_sensor_deveui": space["occupancy_sensor_deveui"],
                "display_device_deveui": space["display_device_deveui"],
                "sensor_details": sensor_details,
                "display_details": display_details,
                "current_state": space["current_state"],
                "sensor_state": space["sensor_state"],
                "display_state": space["display_state"],
                "last_sensor_update": space["last_sensor_update"].isoformat() if space["last_sensor_update"] else None,
                "last_display_update": space["last_display_update"].isoformat() if space["last_display_update"] else None,
                "state_changed_at": space["state_changed_at"].isoformat() if space["state_changed_at"] else None,
                "auto_actuation": space["auto_actuation"],
                "reservation_priority": space["reservation_priority"],
                "enabled": space["enabled"],
                "maintenance_mode": space["maintenance_mode"],
                "space_metadata": space["space_metadata"],
                "notes": space["notes"],
                "active_reservation": reservation_details,
                "created_at": space["created_at"].isoformat(),
                "updated_at": space["updated_at"].isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting space {space_id} (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_space(
    request: CreateSpaceRequest,
    auth = Depends(get_authenticated_tenant)
):
    """Create new parking space (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Lookup sensor_id and display_id from dev_euis
            sensor_lookup = await db.fetchval(
                "SELECT sensor_id FROM parking_config.sensor_registry WHERE dev_eui = $1",
                request.occupancy_sensor_deveui
            )

            display_lookup = await db.fetchval(
                "SELECT display_id FROM parking_config.display_registry WHERE dev_eui = $1",
                request.display_device_deveui
            )

            if not sensor_lookup:
                raise HTTPException(status_code=400, detail=f"Sensor {request.occupancy_sensor_deveui} not found in registry")

            if not display_lookup:
                raise HTTPException(status_code=400, detail=f"Display {request.display_device_deveui} not found in registry")

            # Insert space (tenant_id automatically set via DEFAULT in table)
            query = """
                INSERT INTO parking_spaces.spaces (
                    space_name, space_code, location_description, building, floor, zone,
                    occupancy_sensor_id, display_device_id,
                    occupancy_sensor_deveui, display_device_deveui,
                    auto_actuation, reservation_priority, space_metadata, enabled
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, TRUE)
                RETURNING space_id
            """

            space_id = await db.fetchval(
                query,
                request.space_name,
                request.space_code,
                request.location_description,
                request.building,
                request.floor,
                request.zone,
                sensor_lookup,
                display_lookup,
                request.occupancy_sensor_deveui,
                request.display_device_deveui,
                request.auto_actuation,
                request.reservation_priority,
                request.space_metadata
            )

            logger.info(f"Created parking space: {request.space_name} ({space_id}) tenant={auth.tenant_slug}")

            return {
                "status": "created",
                "space_id": str(space_id),
                "space_name": request.space_name
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating space (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{space_id}")
@router.patch("/{space_id}")
async def update_space(
    space_id: str,
    request: UpdateSpaceRequest,
    auth = Depends(get_authenticated_tenant)
):
    """Update parking space attributes (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Check space exists (RLS will auto-filter by tenant)
            existing = await db.fetchval(
                "SELECT space_id FROM parking_spaces.spaces WHERE space_id = $1",
                space_id
            )

            if not existing:
                # Could be: space doesn't exist OR belongs to different tenant
                raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

            # Build update query dynamically based on provided fields
            updates = []
            params = []
            param_count = 1

            # Add updated_at
            updates.append(f"updated_at = NOW()")

            if request.space_name is not None:
                updates.append(f"space_name = ${param_count}")
                params.append(request.space_name)
                param_count += 1

            if request.space_code is not None:
                updates.append(f"space_code = ${param_count}")
                params.append(request.space_code)
                param_count += 1

            if request.location_description is not None:
                updates.append(f"location_description = ${param_count}")
                params.append(request.location_description)
                param_count += 1

            if request.building is not None:
                updates.append(f"building = ${param_count}")
                params.append(request.building)
                param_count += 1

            if request.floor is not None:
                updates.append(f"floor = ${param_count}")
                params.append(request.floor)
                param_count += 1

            if request.zone is not None:
                updates.append(f"zone = ${param_count}")
                params.append(request.zone)
                param_count += 1

            if request.auto_actuation is not None:
                updates.append(f"auto_actuation = ${param_count}")
                params.append(request.auto_actuation)
                param_count += 1

            if request.reservation_priority is not None:
                updates.append(f"reservation_priority = ${param_count}")
                params.append(request.reservation_priority)
                param_count += 1

            if request.maintenance_mode is not None:
                updates.append(f"maintenance_mode = ${param_count}")
                params.append(request.maintenance_mode)
                param_count += 1

            if request.enabled is not None:
                updates.append(f"enabled = ${param_count}")
                params.append(request.enabled)
                param_count += 1

            if request.space_metadata is not None:
                updates.append(f"space_metadata = ${param_count}")
                params.append(request.space_metadata)
                param_count += 1

            if request.notes is not None:
                updates.append(f"notes = ${param_count}")
                params.append(request.notes)
                param_count += 1

            # Handle sensor device change
            if request.occupancy_sensor_deveui is not None:
                sensor_lookup = await db.fetchval(
                    "SELECT sensor_id FROM parking_config.sensor_registry WHERE dev_eui = $1",
                    request.occupancy_sensor_deveui
                )
                if not sensor_lookup:
                    raise HTTPException(status_code=400, detail=f"Sensor {request.occupancy_sensor_deveui} not found in registry")

                updates.append(f"occupancy_sensor_id = ${param_count}")
                params.append(sensor_lookup)
                param_count += 1

                updates.append(f"occupancy_sensor_deveui = ${param_count}")
                params.append(request.occupancy_sensor_deveui)
                param_count += 1

            # Handle display device change
            if request.display_device_deveui is not None:
                display_lookup = await db.fetchval(
                    "SELECT display_id FROM parking_config.display_registry WHERE dev_eui = $1",
                    request.display_device_deveui
                )
                if not display_lookup:
                    raise HTTPException(status_code=400, detail=f"Display {request.display_device_deveui} not found in registry")

                updates.append(f"display_device_id = ${param_count}")
                params.append(display_lookup)
                param_count += 1

                updates.append(f"display_device_deveui = ${param_count}")
                params.append(request.display_device_deveui)
                param_count += 1

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            # Add space_id as last parameter
            params.append(space_id)
            space_id_param = f"${param_count}"

            update_query = f"""
                UPDATE parking_spaces.spaces
                SET {", ".join(updates)}
                WHERE space_id = {space_id_param}
                RETURNING space_id, space_name
            """

            result = await db.fetchrow(update_query, *params)

            logger.info(f"Updated parking space: {result['space_name']} ({space_id}) tenant={auth.tenant_slug}")

            return {
                "status": "updated",
                "space_id": str(result["space_id"]),
                "space_name": result["space_name"]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating space {space_id} (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{space_id}/archive")
async def archive_space(
    space_id: str,
    archived_by: str = Query(..., description="User archiving the space"),
    archived_reason: str = Query(..., description="Reason for archiving"),
    force: bool = Query(False, description="Force archive with active reservations"),
    auth = Depends(get_authenticated_tenant)
):
    """Archive parking space (permanent deactivation, preserves historical data, tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Check space exists and not already archived (RLS filters by tenant)
            existing = await db.fetchrow(
                "SELECT space_id, space_name, enabled, archived FROM parking_spaces.spaces WHERE space_id = $1",
                space_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

            if existing["archived"]:
                raise HTTPException(status_code=400, detail=f"Space {space_id} is already archived")

            # Check for active reservations (RLS scoped)
            active_reservations = await db.fetchval(
                "SELECT COUNT(*) FROM parking_spaces.reservations WHERE space_id = $1 AND status = 'active'",
                space_id
            )

            if active_reservations > 0 and not force:
                raise HTTPException(
                    status_code=400,
                    detail=f"Space has {active_reservations} active reservation(s). Use force=true to archive anyway."
                )

            # Cancel active reservations if force
            if force and active_reservations > 0:
                await db.execute("""
                    UPDATE parking_spaces.reservations
                    SET status = 'cancelled',
                        cancelled_at = NOW(),
                        cancellation_reason = 'space_archived'
                    WHERE space_id = $1 AND status = 'active'
                """, space_id)
                logger.info(f"Cancelled {active_reservations} reservation(s) for archiving space {space_id} tenant={auth.tenant_slug}")

            # Archive the space
            result = await db.fetchrow("""
                UPDATE parking_spaces.spaces
                SET enabled = FALSE,
                    archived = TRUE,
                    archived_at = NOW(),
                    archived_by = $2,
                    archived_reason = $3,
                    updated_at = NOW()
                WHERE space_id = $1
                RETURNING archived_at
            """, space_id, archived_by, archived_reason)

            logger.info(f"Archived parking space: {existing['space_name']} ({space_id}) by {archived_by} tenant={auth.tenant_slug}")

            return {
                "status": "archived",
                "space_id": str(space_id),
                "space_name": existing["space_name"],
                "archived_at": result["archived_at"].isoformat(),
                "archived_by": archived_by,
                "archived_reason": archived_reason,
                "reservations_cancelled": active_reservations if force else 0
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving space {space_id} (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{space_id}/restore")
async def restore_space(
    space_id: str,
    restored_by: str = Query(..., description="User restoring the space"),
    auth = Depends(get_authenticated_tenant)
):
    """Restore an archived parking space (tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Check space exists and is archived (RLS filters by tenant)
            existing = await db.fetchrow(
                "SELECT space_id, space_name, archived FROM parking_spaces.spaces WHERE space_id = $1",
                space_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

            if not existing["archived"]:
                raise HTTPException(status_code=400, detail=f"Space {space_id} is not archived")

            # Restore the space
            await db.execute("""
                UPDATE parking_spaces.spaces
                SET enabled = TRUE,
                    archived = FALSE,
                    archived_at = NULL,
                    archived_by = NULL,
                    archived_reason = NULL,
                    updated_at = NOW()
                WHERE space_id = $1
            """, space_id)

            logger.info(f"Restored parking space: {existing['space_name']} ({space_id}) by {restored_by} tenant={auth.tenant_slug}")

            return {
                "status": "restored",
                "space_id": str(space_id),
                "space_name": existing["space_name"],
                "restored_by": restored_by
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring space {space_id} (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def delete_space(
    space_id: str,
    force: bool = Query(False, description="Force delete even with active reservations"),
    auth = Depends(get_authenticated_tenant)
):
    """Soft delete parking space (set enabled=FALSE, tenant-scoped)"""
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Check space exists (RLS filters by tenant)
            existing = await db.fetchrow(
                "SELECT space_id, space_name, enabled FROM parking_spaces.spaces WHERE space_id = $1",
                space_id
            )

            if not existing:
                raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

            if not existing["enabled"]:
                raise HTTPException(status_code=400, detail=f"Space {space_id} is already disabled")

            # Check for active reservations (RLS scoped)
            active_reservations = await db.fetchval(
                "SELECT COUNT(*) FROM parking_spaces.reservations WHERE space_id = $1 AND status = 'active'",
                space_id
            )

            if active_reservations > 0 and not force:
                raise HTTPException(
                    status_code=400,
                    detail=f"Space has {active_reservations} active reservation(s). Use force=true to delete anyway."
                )

            # If force, cancel active reservations
            if force and active_reservations > 0:
                await db.execute("""
                    UPDATE parking_spaces.reservations
                    SET status = 'cancelled',
                        cancelled_at = NOW(),
                        cancellation_reason = 'space_deleted'
                    WHERE space_id = $1 AND status = 'active'
                """, space_id)
                logger.info(f"Cancelled {active_reservations} reservation(s) for space {space_id} tenant={auth.tenant_slug}")

            # Soft delete - set enabled=FALSE
            await db.execute("""
                UPDATE parking_spaces.spaces
                SET enabled = FALSE,
                    updated_at = NOW()
                WHERE space_id = $1
            """, space_id)

            logger.info(f"Deleted (disabled) parking space: {existing['space_name']} ({space_id}) tenant={auth.tenant_slug}")

            return {
                "status": "deleted",
                "space_id": str(space_id),
                "space_name": existing["space_name"],
                "reservations_cancelled": active_reservations if force else 0
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting space {space_id} (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
