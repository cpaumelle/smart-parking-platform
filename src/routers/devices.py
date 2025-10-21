"""
Devices Router - CRUD API for sensor and display devices
Manages both sensor_devices and display_devices tables
Multi-tenancy enabled with tenant scoping
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from typing import Optional, List, Dict, Any
import logging
from uuid import UUID
from datetime import datetime

from ..models import TenantContext
from ..tenant_auth import get_current_tenant, require_viewer, require_admin
from ..api_scopes import require_scopes

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
logger = logging.getLogger(__name__)


@router.get("/device-types", response_model=List[Dict[str, Any]])
async def list_device_types(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category: 'sensor' or 'display'")
):
    """
    List all device types

    Returns device type definitions from device_types table
    """
    try:
        db_pool = request.app.state.db_pool

        conditions = ["enabled = true"]
        params = []

        if category:
            conditions.append(f"category = ${len(params) + 1}")
            params.append(category)

        where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT
                id,
                type_code,
                category,
                name,
                manufacturer,
                handler_class,
                default_config,
                capabilities,
                enabled,
                status,
                chirpstack_profile_name,
                created_at,
                updated_at
            FROM device_types
            {where_clause}
            ORDER BY category, name
        """

        results = await db_pool.fetch(query, *params)

        device_types = []
        for row in results:
            device_types.append({
                "id": str(row["id"]),
                "type_code": row["type_code"],
                "category": row["category"],
                "name": row["name"],
                "manufacturer": row["manufacturer"],
                "handler_class": row["handler_class"],
                "default_config": row["default_config"],
                "capabilities": row["capabilities"],
                "enabled": row["enabled"],
                "status": row["status"],
                "chirpstack_profile_name": row["chirpstack_profile_name"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            })

        logger.info(f"List device types: count={len(device_types)} category={category}")
        return device_types

    except Exception as e:
        logger.error(f"Error listing device types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[Dict[str, Any]], dependencies=[Depends(require_scopes("devices:read"))])
async def list_devices(
    request: Request,
    device_type: Optional[str] = Query(None, description="Filter by device_type (sensor/display)"),
    device_category: Optional[str] = Query(None, description="Filter by category: 'sensor' or 'display'"),
    status: Optional[str] = Query(None, description="Filter by status (orphan/active/inactive/decommissioned)"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled flag"),
    include_archived: bool = Query(False, description="Include disabled devices"),
    include_orphans: bool = Query(True, description="Include orphan (unassigned) devices"),
    tenant: TenantContext = Depends(require_viewer)
):
    """
    List devices visible to the current tenant

    Returns devices that are either:
    - Assigned to spaces owned by the current tenant
    - Orphan devices (not assigned to any space) if include_orphans=true

    Each device has a 'category' field indicating 'sensor' or 'display'

    Requires: VIEWER role or higher, API key requires devices:read scope
    """
    try:
        db_pool = request.app.state.db_pool
        devices = []

        # Determine which device categories to fetch
        categories_to_fetch = []
        if device_category == 'sensor':
            categories_to_fetch = ['sensor']
        elif device_category == 'display':
            categories_to_fetch = ['display']
        else:
            categories_to_fetch = ['sensor', 'display']

        # Fetch sensor devices (tenant-scoped)
        if 'sensor' in categories_to_fetch:
            sensor_conditions = []
            sensor_params = [tenant.tenant_id]
            param_count = 2

            # Tenant scoping: include devices assigned to tenant's spaces or orphans
            if include_orphans:
                sensor_conditions.append("""(
                    sd.status = 'orphan' OR
                    EXISTS (
                        SELECT 1 FROM spaces s
                        WHERE s.sensor_eui = sd.dev_eui
                        AND s.tenant_id = $1
                        AND s.deleted_at IS NULL
                    )
                )""")
            else:
                sensor_conditions.append("""EXISTS (
                    SELECT 1 FROM spaces s
                    WHERE s.sensor_eui = sd.dev_eui
                    AND s.tenant_id = $1
                    AND s.deleted_at IS NULL
                )""")

            if device_type is not None:
                sensor_conditions.append(f"sd.device_type = ${param_count}")
                sensor_params.append(device_type)
                param_count += 1

            if status is not None:
                sensor_conditions.append(f"sd.status = ${param_count}")
                sensor_params.append(status)
                param_count += 1

            if enabled is not None:
                sensor_conditions.append(f"sd.enabled = ${param_count}")
                sensor_params.append(enabled)
                param_count += 1
            elif not include_archived:
                sensor_conditions.append("sd.enabled = true")

            where_clause = "WHERE " + " AND ".join(sensor_conditions)

            sensor_query = f"""
                SELECT
                    sd.id,
                    sd.dev_eui as deveui,
                    sd.device_type,
                    sd.device_model,
                    sd.manufacturer,
                    sd.payload_decoder,
                    sd.capabilities,
                    sd.enabled,
                    sd.last_seen_at,
                    sd.created_at,
                    sd.updated_at,
                    sd.status,
                    'sensor' as category
                FROM sensor_devices sd
                {where_clause}
                ORDER BY sd.created_at DESC
            """

            sensor_results = await db_pool.fetch(sensor_query, *sensor_params)
            logger.info(f"[Tenant:{tenant.tenant_id}] Found {len(sensor_results)} sensor devices")

            for row in sensor_results:
                devices.append({
                    "id": str(row["id"]),
                    "deveui": row["deveui"],
                    "category": "sensor",
                    "device_type": row["device_type"],
                    "device_model": row["device_model"],
                    "manufacturer": row["manufacturer"],
                    "payload_decoder": row["payload_decoder"],
                    "capabilities": row["capabilities"],
                    "enabled": row["enabled"],
                    "status": row["status"],
                    "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                })

        # Fetch display devices (tenant-scoped)
        if 'display' in categories_to_fetch:
            display_conditions = []
            display_params = [tenant.tenant_id]
            param_count = 2

            # Tenant scoping: include devices assigned to tenant's spaces or orphans
            if include_orphans:
                display_conditions.append("""(
                    dd.status = 'orphan' OR
                    EXISTS (
                        SELECT 1 FROM spaces s
                        WHERE s.display_eui = dd.dev_eui
                        AND s.tenant_id = $1
                        AND s.deleted_at IS NULL
                    )
                )""")
            else:
                display_conditions.append("""EXISTS (
                    SELECT 1 FROM spaces s
                    WHERE s.display_eui = dd.dev_eui
                    AND s.tenant_id = $1
                    AND s.deleted_at IS NULL
                )""")

            if device_type is not None:
                display_conditions.append(f"dd.device_type = ${param_count}")
                display_params.append(device_type)
                param_count += 1

            if status is not None:
                display_conditions.append(f"dd.status = ${param_count}")
                display_params.append(status)
                param_count += 1

            if enabled is not None:
                display_conditions.append(f"dd.enabled = ${param_count}")
                display_params.append(enabled)
                param_count += 1
            elif not include_archived:
                display_conditions.append("dd.enabled = true")

            where_clause = "WHERE " + " AND ".join(display_conditions)

            display_query = f"""
                SELECT
                    dd.id,
                    dd.dev_eui as deveui,
                    dd.device_type,
                    dd.device_model,
                    dd.manufacturer,
                    dd.display_codes,
                    dd.fport,
                    dd.confirmed_downlinks,
                    dd.enabled,
                    dd.last_seen_at,
                    dd.created_at,
                    dd.updated_at,
                    dd.status,
                    'display' as category
                FROM display_devices dd
                {where_clause}
                ORDER BY dd.created_at DESC
            """

            display_results = await db_pool.fetch(display_query, *display_params)
            logger.info(f"[Tenant:{tenant.tenant_id}] Found {len(display_results)} display devices")

            for row in display_results:
                devices.append({
                    "id": str(row["id"]),
                    "deveui": row["deveui"],
                    "category": "display",
                    "device_type": row["device_type"],
                    "device_model": row["device_model"],
                    "manufacturer": row["manufacturer"],
                    "display_codes": row["display_codes"],
                    "fport": row["fport"],
                    "confirmed_downlinks": row["confirmed_downlinks"],
                    "enabled": row["enabled"],
                    "status": row["status"],
                    "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
                })

        logger.info(f"List devices: count={len(devices)} category_filter={device_category}")
        return devices

    except Exception as e:
        logger.error(f"Error listing devices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deveui}", response_model=Dict[str, Any])
async def get_device(
    request: Request,
    deveui: str
):
    """
    Get detailed information about a specific device

    Searches both sensor_devices and display_devices tables
    """
    try:
        db_pool = request.app.state.db_pool

        # Try sensor_devices first
        sensor_query = """
            SELECT
                id,
                dev_eui as deveui,
                device_type,
                device_model,
                manufacturer,
                payload_decoder,
                capabilities,
                enabled,
                last_seen_at,
                created_at,
                updated_at,
                status,
                'sensor' as category
            FROM sensor_devices
            WHERE dev_eui = $1
        """

        device = await db_pool.fetchrow(sensor_query, deveui)

        if device:
            # Check if assigned to a space
            space_query = """
                SELECT id, name, code
                FROM spaces
                WHERE sensor_eui = $1 AND deleted_at IS NULL
            """
            space = await db_pool.fetchrow(space_query, deveui)

            return {
                "id": str(device["id"]),
                "deveui": device["deveui"],
                "category": "sensor",
                "device_type": device["device_type"],
                "device_model": device["device_model"],
                "manufacturer": device["manufacturer"],
                "payload_decoder": device["payload_decoder"],
                "capabilities": device["capabilities"],
                "enabled": device["enabled"],
                "status": device["status"],
                "last_seen_at": device["last_seen_at"].isoformat() if device["last_seen_at"] else None,
                "created_at": device["created_at"].isoformat() if device["created_at"] else None,
                "updated_at": device["updated_at"].isoformat() if device["updated_at"] else None,
                "assigned_space": {
                    "id": str(space["id"]),
                    "name": space["name"],
                    "code": space["code"]
                } if space else None
            }

        # Try display_devices
        display_query = """
            SELECT
                id,
                dev_eui as deveui,
                device_type,
                device_model,
                manufacturer,
                display_codes,
                fport,
                confirmed_downlinks,
                enabled,
                last_seen_at,
                created_at,
                updated_at,
                status,
                'display' as category
            FROM display_devices
            WHERE dev_eui = $1
        """

        device = await db_pool.fetchrow(display_query, deveui)

        if device:
            # Check if assigned to a space
            space_query = """
                SELECT id, name, code
                FROM spaces
                WHERE display_eui = $1 AND deleted_at IS NULL
            """
            space = await db_pool.fetchrow(space_query, deveui)

            return {
                "id": str(device["id"]),
                "deveui": device["deveui"],
                "category": "display",
                "device_type": device["device_type"],
                "device_model": device["device_model"],
                "manufacturer": device["manufacturer"],
                "display_codes": device["display_codes"],
                "fport": device["fport"],
                "confirmed_downlinks": device["confirmed_downlinks"],
                "enabled": device["enabled"],
                "status": device["status"],
                "last_seen_at": device["last_seen_at"].isoformat() if device["last_seen_at"] else None,
                "created_at": device["created_at"].isoformat() if device["created_at"] else None,
                "updated_at": device["updated_at"].isoformat() if device["updated_at"] else None,
                "assigned_space": {
                    "id": str(space["id"]),
                    "name": space["name"],
                    "code": space["code"]
                } if space else None
            }

        raise HTTPException(status_code=404, detail=f"Device {deveui} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device {deveui}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-metadata", response_model=List[Dict[str, Any]])
async def get_device_metadata(request: Request):
    """
    Get full metadata for all devices including assignment status

    Compatible with V4 API format
    """
    try:
        db_pool = request.app.state.db_pool

        # Get all sensors with space assignments
        sensor_query = """
            SELECT
                sd.dev_eui as deveui,
                sd.device_type,
                sd.device_model,
                sd.manufacturer,
                sd.enabled,
                sd.status,
                sd.last_seen_at,
                s.id as space_id,
                s.name as space_name,
                s.code as space_code,
                'sensor' as category
            FROM sensor_devices sd
            LEFT JOIN spaces s ON s.sensor_eui = sd.dev_eui AND s.deleted_at IS NULL
            WHERE sd.enabled = true
            ORDER BY sd.created_at DESC
        """

        sensors = await db_pool.fetch(sensor_query)

        # Get all displays with space assignments
        display_query = """
            SELECT
                dd.dev_eui as deveui,
                dd.device_type,
                dd.device_model,
                dd.manufacturer,
                dd.enabled,
                dd.status,
                dd.last_seen_at,
                s.id as space_id,
                s.name as space_name,
                s.code as space_code,
                'display' as category
            FROM display_devices dd
            LEFT JOIN spaces s ON s.display_eui = dd.dev_eui AND s.deleted_at IS NULL
            WHERE dd.enabled = true
            ORDER BY dd.created_at DESC
        """

        displays = await db_pool.fetch(display_query)

        devices = []

        for row in sensors:
            devices.append({
                "deveui": row["deveui"],
                "category": "sensor",
                "device_type": row["device_type"],
                "device_model": row["device_model"],
                "manufacturer": row["manufacturer"],
                "enabled": row["enabled"],
                "status": row["status"],
                "lifecycle_state": row["status"],  # V4 compatibility
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "location_id": str(row["space_id"]) if row["space_id"] else None,
                "location_name": row["space_name"],
                "assigned": row["space_id"] is not None
            })

        for row in displays:
            devices.append({
                "deveui": row["deveui"],
                "category": "display",
                "device_type": row["device_type"],
                "device_model": row["device_model"],
                "manufacturer": row["manufacturer"],
                "enabled": row["enabled"],
                "status": row["status"],
                "lifecycle_state": row["status"],  # V4 compatibility
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "location_id": str(row["space_id"]) if row["space_id"] else None,
                "location_name": row["space_name"],
                "assigned": row["space_id"] is not None
            })

        logger.info(f"Device metadata: count={len(devices)}")
        return devices

    except Exception as e:
        logger.error(f"Error getting device metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{deveui}", response_model=Dict[str, Any])
async def update_device(
    request: Request,
    deveui: str,
    update_data: Dict[str, Any]
):
    """
    Update device attributes

    Automatically determines if device is sensor or display
    """
    try:
        db_pool = request.app.state.db_pool

        # Check if it's a sensor
        sensor_exists = await db_pool.fetchval(
            "SELECT id FROM sensor_devices WHERE dev_eui = $1",
            deveui
        )

        if sensor_exists:
            # Update sensor device
            updates = []
            params = []
            param_count = 1

            updates.append("updated_at = NOW()")

            if "device_type" in update_data:
                updates.append(f"device_type = ${param_count}")
                params.append(update_data["device_type"])
                param_count += 1

            if "device_model" in update_data:
                updates.append(f"device_model = ${param_count}")
                params.append(update_data["device_model"])
                param_count += 1

            if "manufacturer" in update_data:
                updates.append(f"manufacturer = ${param_count}")
                params.append(update_data["manufacturer"])
                param_count += 1

            if "enabled" in update_data:
                updates.append(f"enabled = ${param_count}")
                params.append(update_data["enabled"])
                param_count += 1

            if "status" in update_data:
                updates.append(f"status = ${param_count}")
                params.append(update_data["status"])
                param_count += 1

            if not updates or updates == ["updated_at = NOW()"]:
                raise HTTPException(status_code=400, detail="No fields to update")

            params.append(deveui)
            update_query = f"""
                UPDATE sensor_devices
                SET {", ".join(updates)}
                WHERE dev_eui = ${param_count}
                RETURNING dev_eui
            """

            result = await db_pool.fetchrow(update_query, *params)
            logger.info(f"Updated sensor device: {deveui}")

            return {
                "status": "updated",
                "deveui": result["dev_eui"],
                "category": "sensor"
            }

        # Check if it's a display
        display_exists = await db_pool.fetchval(
            "SELECT id FROM display_devices WHERE dev_eui = $1",
            deveui
        )

        if display_exists:
            # Update display device
            updates = []
            params = []
            param_count = 1

            updates.append("updated_at = NOW()")

            if "device_type" in update_data:
                updates.append(f"device_type = ${param_count}")
                params.append(update_data["device_type"])
                param_count += 1

            if "device_model" in update_data:
                updates.append(f"device_model = ${param_count}")
                params.append(update_data["device_model"])
                param_count += 1

            if "manufacturer" in update_data:
                updates.append(f"manufacturer = ${param_count}")
                params.append(update_data["manufacturer"])
                param_count += 1

            if "enabled" in update_data:
                updates.append(f"enabled = ${param_count}")
                params.append(update_data["enabled"])
                param_count += 1

            if "status" in update_data:
                updates.append(f"status = ${param_count}")
                params.append(update_data["status"])
                param_count += 1

            if not updates or updates == ["updated_at = NOW()"]:
                raise HTTPException(status_code=400, detail="No fields to update")

            params.append(deveui)
            update_query = f"""
                UPDATE display_devices
                SET {", ".join(updates)}
                WHERE dev_eui = ${param_count}
                RETURNING dev_eui
            """

            result = await db_pool.fetchrow(update_query, *params)
            logger.info(f"Updated display device: {deveui}")

            return {
                "status": "updated",
                "deveui": result["dev_eui"],
                "category": "display"
            }

        raise HTTPException(status_code=404, detail=f"Device {deveui} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device {deveui}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{deveui}/archive", response_model=Dict[str, Any])
async def archive_device(
    request: Request,
    deveui: str,
    confirm: bool = Query(True, description="Confirmation flag")
):
    """
    Archive (disable) a device

    V4-compatible endpoint that sets enabled=false
    """
    try:
        db_pool = request.app.state.db_pool

        # Try sensor first
        sensor_result = await db_pool.fetchrow("""
            UPDATE sensor_devices
            SET enabled = false, updated_at = NOW()
            WHERE dev_eui = $1
            RETURNING dev_eui
        """, deveui)

        if sensor_result:
            logger.info(f"Archived sensor device: {deveui}")
            return {
                "status": "archived",
                "deveui": sensor_result["dev_eui"],
                "category": "sensor"
            }

        # Try display
        display_result = await db_pool.fetchrow("""
            UPDATE display_devices
            SET enabled = false, updated_at = NOW()
            WHERE dev_eui = $1
            RETURNING dev_eui
        """, deveui)

        if display_result:
            logger.info(f"Archived display device: {deveui}")
            return {
                "status": "archived",
                "deveui": display_result["dev_eui"],
                "category": "display"
            }

        raise HTTPException(status_code=404, detail=f"Device {deveui} not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving device {deveui}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
