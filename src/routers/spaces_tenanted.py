"""
Spaces Router - Tenant-scoped CRUD API for parking spaces
Multi-tenancy enabled with RBAC
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from typing import Optional, List, Dict, Any
import logging
import hashlib
import json
from uuid import UUID
from datetime import datetime

from ..models import (
    SpaceCreate, SpaceUpdate, Space, SpaceState,
    TenantContext
)
from ..tenant_auth import get_current_tenant, require_viewer, require_admin
from ..rate_limit import get_rate_limiter
from ..api_scopes import require_scopes
from ..cache import get_cache, invalidate_space_cache

router = APIRouter(prefix="/api/v1/spaces", tags=["spaces"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:read"))])
async def list_spaces(
    request: Request,
    building: Optional[str] = Query(None, description="Filter by building"),
    floor: Optional[str] = Query(None, description="Filter by floor"),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    state: Optional[SpaceState] = Query(None, description="Filter by current state"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    include_deleted: bool = Query(False, description="Include soft-deleted spaces"),
    tenant: TenantContext = Depends(require_viewer)
):
    """
    List all parking spaces in the current tenant with optional filters

    Requires: VIEWER role or higher, API key requires spaces:read scope
    """
    try:
        # Generate cache key from filters
        cache_key_data = {
            "tenant_id": str(tenant.tenant_id),
            "building": building,
            "floor": floor,
            "zone": zone,
            "state": state.value if state else None,
            "site_id": str(site_id) if site_id else None,
            "include_deleted": include_deleted
        }
        cache_key = f"spaces:list:{hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode()).hexdigest()}"

        # Try cache first
        try:
            cache = get_cache()
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(f"[Tenant:{tenant.tenant_id}] Cache HIT for spaces list")
                return cached
        except Exception as cache_error:
            logger.warning(f"Cache get error (continuing without cache): {cache_error}")

        db_pool = request.app.state.db_pool

        # Build dynamic query with filters - ALWAYS include tenant_id
        conditions = ["s.tenant_id = $1"]
        params = [tenant.tenant_id]
        param_count = 2

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

        if site_id is not None:
            conditions.append(f"s.site_id = ${param_count}")
            params.append(site_id)
            param_count += 1

        # Add soft delete filter
        if not include_deleted:
            conditions.append("s.deleted_at IS NULL")

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT
                s.id,
                s.name,
                s.code,
                s.building,
                s.floor,
                s.zone,
                s.state,
                s.site_id,
                s.tenant_id,
                s.sensor_eui,
                s.display_eui,
                s.gps_latitude,
                s.gps_longitude,
                s.metadata,
                s.created_at,
                s.updated_at,
                s.deleted_at,
                sites.name AS site_name
            FROM spaces s
            LEFT JOIN sites ON s.site_id = sites.id
            {where_clause}
            ORDER BY s.code, s.name
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
                "site_id": str(row["site_id"]) if row["site_id"] else None,
                "site_name": row["site_name"],
                "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
                "sensor_eui": row["sensor_eui"],
                "display_eui": row["display_eui"],
                "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
                "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
                "metadata": row["metadata"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "deleted_at": row["deleted_at"].isoformat() if row["deleted_at"] else None
            })

        result = {"spaces": spaces, "count": len(spaces)}

        # Cache the result (60 second TTL for frequently changing data)
        try:
            await cache.set(cache_key, result, ttl=60)
            logger.debug(f"[Tenant:{tenant.tenant_id}] Cached spaces list result")
        except Exception as cache_error:
            logger.warning(f"Cache set error (continuing): {cache_error}")

        logger.info(f"[Tenant:{tenant.tenant_id}] List spaces: count={len(spaces)} filters={len(conditions)-1}")
        return result

    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error listing spaces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{space_id}", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:read"))])
async def get_space(
    request: Request,
    space_id: UUID,
    tenant: TenantContext = Depends(require_viewer)
):
    """
    Get a specific parking space by ID

    Requires: VIEWER role or higher, API key requires spaces:read scope
    """
    try:
        db_pool = request.app.state.db_pool

        # CRITICAL: Always scope by tenant_id to prevent cross-tenant access
        query = """
            SELECT
                s.id,
                s.name,
                s.code,
                s.building,
                s.floor,
                s.zone,
                s.state,
                s.site_id,
                s.tenant_id,
                s.sensor_eui,
                s.display_eui,
                s.gps_latitude,
                s.gps_longitude,
                s.metadata,
                s.created_at,
                s.updated_at,
                sites.name AS site_name
            FROM spaces s
            LEFT JOIN sites ON s.site_id = sites.id
            WHERE s.id = $1 AND s.tenant_id = $2 AND s.deleted_at IS NULL
        """

        row = await db_pool.fetchrow(query, space_id, tenant.tenant_id)

        if not row:
            raise HTTPException(status_code=404, detail="Space not found")

        space = {
            "id": str(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "building": row["building"],
            "floor": row["floor"],
            "zone": row["zone"],
            "state": row["state"],
            "site_id": str(row["site_id"]) if row["site_id"] else None,
            "site_name": row["site_name"],
            "tenant_id": str(row["tenant_id"]),
            "sensor_eui": row["sensor_eui"],
            "display_eui": row["display_eui"],
            "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
            "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
            "metadata": row["metadata"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
        }

        return space

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error getting space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict[str, Any], status_code=201, dependencies=[Depends(require_scopes("spaces:write"))])
async def create_space(
    request: Request,
    space: SpaceCreate,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Create a new parking space

    Requires: ADMIN role or higher, API key requires spaces:write scope
    """
    try:
        db_pool = request.app.state.db_pool

        # Verify site belongs to tenant
        site_check = await db_pool.fetchrow("""
            SELECT id, tenant_id FROM sites
            WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """, space.site_id, tenant.tenant_id)

        if not site_check:
            raise HTTPException(
                status_code=400,
                detail="Site not found or does not belong to your tenant"
            )

        # Check for duplicate space code within tenant+site
        existing = await db_pool.fetchrow("""
            SELECT id FROM spaces
            WHERE tenant_id = $1 AND site_id = $2 AND code = $3 AND deleted_at IS NULL
        """, tenant.tenant_id, space.site_id, space.code)

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Space with code '{space.code}' already exists in this site"
            )

        # Create space (tenant_id will be auto-synced by trigger)
        query = """
            INSERT INTO spaces (
                name, code, building, floor, zone,
                site_id, sensor_eui, display_eui,
                state, gps_latitude, gps_longitude, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id, name, code, building, floor, zone, state, site_id, tenant_id,
                      sensor_eui, display_eui, gps_latitude, gps_longitude,
                      metadata, created_at, updated_at
        """

        row = await db_pool.fetchrow(
            query,
            space.name, space.code, space.building, space.floor, space.zone,
            space.site_id, space.sensor_eui, space.display_eui,
            space.state.value, space.gps_latitude, space.gps_longitude, space.metadata
        )

        result = {
            "id": str(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "building": row["building"],
            "floor": row["floor"],
            "zone": row["zone"],
            "state": row["state"],
            "site_id": str(row["site_id"]),
            "tenant_id": str(row["tenant_id"]),
            "sensor_eui": row["sensor_eui"],
            "display_eui": row["display_eui"],
            "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
            "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
            "metadata": row["metadata"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()
        }

        # Invalidate space caches for this tenant
        try:
            await invalidate_space_cache(str(tenant.tenant_id))
            logger.debug(f"[Tenant:{tenant.tenant_id}] Invalidated space cache after creation")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation error (continuing): {cache_error}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Created space {row['code']} in site {space.site_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error creating space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{space_id}", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:write"))])
async def update_space(
    request: Request,
    space_id: UUID,
    space_update: SpaceUpdate,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Update a parking space

    Requires: ADMIN role or higher, API key requires spaces:write scope
    """
    try:
        db_pool = request.app.state.db_pool

        # Verify space exists and belongs to tenant
        existing = await db_pool.fetchrow("""
            SELECT id FROM spaces
            WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
        """, space_id, tenant.tenant_id)

        if not existing:
            raise HTTPException(status_code=404, detail="Space not found")

        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 1

        for field, value in space_update.dict(exclude_unset=True).items():
            if value is not None:
                if field == "state":
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value.value)
                else:
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value)
                param_count += 1

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.extend([space_id, tenant.tenant_id])

        query = f"""
            UPDATE spaces
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_count} AND tenant_id = ${param_count + 1}
            RETURNING id, name, code, building, floor, zone, state, site_id, tenant_id,
                      sensor_eui, display_eui, gps_latitude, gps_longitude,
                      metadata, created_at, updated_at
        """

        row = await db_pool.fetchrow(query, *params)

        result = {
            "id": str(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "building": row["building"],
            "floor": row["floor"],
            "zone": row["zone"],
            "state": row["state"],
            "site_id": str(row["site_id"]) if row["site_id"] else None,
            "tenant_id": str(row["tenant_id"]),
            "sensor_eui": row["sensor_eui"],
            "display_eui": row["display_eui"],
            "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
            "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
            "metadata": row["metadata"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()
        }

        # Invalidate space caches for this tenant and specific space
        try:
            await invalidate_space_cache(str(tenant.tenant_id), str(space_id))
            logger.debug(f"[Tenant:{tenant.tenant_id}] Invalidated space cache after update")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation error (continuing): {cache_error}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Updated space {space_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error updating space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{space_id}", status_code=204, dependencies=[Depends(require_scopes("spaces:write"))])
async def delete_space(
    request: Request,
    space_id: UUID,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Soft delete a parking space

    Requires: ADMIN role or higher, API key requires spaces:write scope
    """
    try:
        db_pool = request.app.state.db_pool

        # Soft delete (set deleted_at) - always scope by tenant
        result = await db_pool.execute("""
            UPDATE spaces
            SET deleted_at = NOW()
            WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
        """, space_id, tenant.tenant_id)

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Space not found")

        # Invalidate space caches for this tenant and specific space
        try:
            await invalidate_space_cache(str(tenant.tenant_id), str(space_id))
            logger.debug(f"[Tenant:{tenant.tenant_id}] Invalidated space cache after deletion")
        except Exception as cache_error:
            logger.warning(f"Cache invalidation error (continuing): {cache_error}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Deleted space {space_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error deleting space {space_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:read"))])
async def get_space_stats(
    request: Request,
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    tenant: TenantContext = Depends(require_viewer)
):
    """
    Get space statistics for the current tenant

    Returns counts by state (FREE, OCCUPIED, RESERVED, MAINTENANCE)

    Requires: VIEWER role or higher, API key requires spaces:read scope
    """
    try:
        db_pool = request.app.state.db_pool

        # Build query with optional site filter
        site_condition = "AND site_id = $2" if site_id else ""
        params = [tenant.tenant_id, site_id] if site_id else [tenant.tenant_id]

        query = f"""
            SELECT
                state,
                COUNT(*) as count
            FROM spaces
            WHERE tenant_id = $1 {site_condition} AND deleted_at IS NULL
            GROUP BY state
        """

        results = await db_pool.fetch(query, *params)

        # Build stats dict
        stats = {
            "FREE": 0,
            "OCCUPIED": 0,
            "RESERVED": 0,
            "MAINTENANCE": 0,
            "total": 0
        }

        for row in results:
            stats[row["state"]] = row["count"]
            stats["total"] += row["count"]

        logger.info(f"[Tenant:{tenant.tenant_id}] Space stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error getting space stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# Device Assignment Convenience Endpoints
# ============================================================

@router.post("/{space_id}/assign-sensor", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:write"))])
async def assign_sensor_to_space(
    request: Request,
    space_id: UUID,
    sensor_eui: str = Query(..., description="Sensor device EUI (16 hex chars)"),
    tenant: TenantContext = Depends(require_admin)
):
    """
    Assign a sensor device to a parking space (convenience endpoint)

    This is a shortcut for PATCH /spaces/{space_id} with sensor_eui in body.

    Requires: ADMIN role or higher, API key requires spaces:write scope

    Example:
    ```
    POST /api/v1/spaces/{space_id}/assign-sensor?sensor_eui=0004A30B001A2B3C
    ```

    Returns updated space with sensor_eui assigned.
    """
    try:
        db_pool = request.app.state.db_pool

        # Validate sensor_eui format (16 uppercase hex chars)
        sensor_eui_upper = sensor_eui.upper()
        if len(sensor_eui_upper) != 16 or not all(c in '0123456789ABCDEF' for c in sensor_eui_upper):
            raise HTTPException(status_code=400, detail="sensor_eui must be 16 hexadecimal characters")

        # Check if sensor exists in sensor_devices table
        sensor_exists = await db_pool.fetchval("""
            SELECT EXISTS(SELECT 1 FROM sensor_devices WHERE dev_eui = $1)
        """, sensor_eui_upper)

        if not sensor_exists:
            # Auto-create sensor device if it doesn't exist
            await db_pool.execute("""
                INSERT INTO sensor_devices (dev_eui, device_name, status)
                VALUES ($1, $2, 'active')
                ON CONFLICT (dev_eui) DO NOTHING
            """, sensor_eui_upper, f"Sensor {sensor_eui_upper[:8]}")

            logger.info(f"[Tenant:{tenant.tenant_id}] Auto-created sensor device: {sensor_eui_upper}")

        # Update space with sensor assignment
        result = await db_pool.fetchrow("""
            UPDATE spaces
            SET sensor_eui = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3 AND deleted_at IS NULL
            RETURNING id, code, name, building, floor, zone, state,
                      sensor_eui, display_eui, site_id, tenant_id,
                      created_at, updated_at
        """, sensor_eui_upper, space_id, tenant.tenant_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found in tenant {tenant.tenant_slug}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Assigned sensor {sensor_eui_upper} to space {space_id}")

        return dict(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error assigning sensor to space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{space_id}/assign-display", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:write"))])
async def assign_display_to_space(
    request: Request,
    space_id: UUID,
    display_eui: str = Query(..., description="Display device EUI (16 hex chars)"),
    tenant: TenantContext = Depends(require_admin)
):
    """
    Assign a display device to a parking space (convenience endpoint)

    This is a shortcut for PATCH /spaces/{space_id} with display_eui in body.

    Requires: ADMIN role or higher, API key requires spaces:write scope

    Example:
    ```
    POST /api/v1/spaces/{space_id}/assign-display?display_eui=0004A30B001A2B3D
    ```

    Returns updated space with display_eui assigned.
    """
    try:
        db_pool = request.app.state.db_pool

        # Validate display_eui format (16 uppercase hex chars)
        display_eui_upper = display_eui.upper()
        if len(display_eui_upper) != 16 or not all(c in '0123456789ABCDEF' for c in display_eui_upper):
            raise HTTPException(status_code=400, detail="display_eui must be 16 hexadecimal characters")

        # Check if display exists in display_devices table
        display_exists = await db_pool.fetchval("""
            SELECT EXISTS(SELECT 1 FROM display_devices WHERE dev_eui = $1)
        """, display_eui_upper)

        if not display_exists:
            # Auto-create display device if it doesn't exist
            await db_pool.execute("""
                INSERT INTO display_devices (dev_eui, device_name, status)
                VALUES ($1, $2, 'active')
                ON CONFLICT (dev_eui) DO NOTHING
            """, display_eui_upper, f"Display {display_eui_upper[:8]}")

            logger.info(f"[Tenant:{tenant.tenant_id}] Auto-created display device: {display_eui_upper}")

        # Update space with display assignment
        result = await db_pool.fetchrow("""
            UPDATE spaces
            SET display_eui = $1, updated_at = NOW()
            WHERE id = $2 AND tenant_id = $3 AND deleted_at IS NULL
            RETURNING id, code, name, building, floor, zone, state,
                      sensor_eui, display_eui, site_id, tenant_id,
                      created_at, updated_at
        """, display_eui_upper, space_id, tenant.tenant_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found in tenant {tenant.tenant_slug}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Assigned display {display_eui_upper} to space {space_id}")

        return dict(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error assigning display to space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{space_id}/unassign-sensor", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:write"))])
async def unassign_sensor_from_space(
    request: Request,
    space_id: UUID,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Unassign sensor device from a parking space (convenience endpoint)

    Sets sensor_eui to NULL for the space.

    Requires: ADMIN role or higher, API key requires spaces:write scope

    Example:
    ```
    DELETE /api/v1/spaces/{space_id}/unassign-sensor
    ```

    Returns updated space with sensor_eui set to null.
    """
    try:
        db_pool = request.app.state.db_pool

        # Update space to remove sensor assignment
        result = await db_pool.fetchrow("""
            UPDATE spaces
            SET sensor_eui = NULL, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
            RETURNING id, code, name, building, floor, zone, state,
                      sensor_eui, display_eui, site_id, tenant_id,
                      created_at, updated_at
        """, space_id, tenant.tenant_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found in tenant {tenant.tenant_slug}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Unassigned sensor from space {space_id}")

        return dict(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error unassigning sensor from space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{space_id}/unassign-display", response_model=Dict[str, Any], dependencies=[Depends(require_scopes("spaces:write"))])
async def unassign_display_from_space(
    request: Request,
    space_id: UUID,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Unassign display device from a parking space (convenience endpoint)

    Sets display_eui to NULL for the space.

    Requires: ADMIN role or higher, API key requires spaces:write scope

    Example:
    ```
    DELETE /api/v1/spaces/{space_id}/unassign-display
    ```

    Returns updated space with display_eui set to null.
    """
    try:
        db_pool = request.app.state.db_pool

        # Update space to remove display assignment
        result = await db_pool.fetchrow("""
            UPDATE spaces
            SET display_eui = NULL, updated_at = NOW()
            WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL
            RETURNING id, code, name, building, floor, zone, state,
                      sensor_eui, display_eui, site_id, tenant_id,
                      created_at, updated_at
        """, space_id, tenant.tenant_id)

        if not result:
            raise HTTPException(status_code=404, detail=f"Space {space_id} not found in tenant {tenant.tenant_slug}")

        logger.info(f"[Tenant:{tenant.tenant_id}] Unassigned display from space {space_id}")

        return dict(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Tenant:{tenant.tenant_id}] Error unassigning display from space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
