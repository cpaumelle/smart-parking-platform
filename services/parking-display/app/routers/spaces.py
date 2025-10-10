from fastapi import APIRouter, Depends, HTTPException
import logging
import sys
sys.path.append("/app")

from app.database import get_db_dependency
from app.models import CreateSpaceRequest

router = APIRouter()
logger = logging.getLogger("spaces")

@router.get("/")
async def list_spaces(db = Depends(get_db_dependency)):
    """List all parking spaces"""
    try:
        query = """
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
            ORDER BY s.space_name
        """

        results = await db.fetch(query)

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

        return {"spaces": spaces, "count": len(spaces)}

    except Exception as e:
        logger.error(f"Error listing spaces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-list")
async def get_sensor_list(db = Depends(get_db_dependency)):
    """Get list of parking sensor DevEUIs for Ingest Service cache"""
    try:
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

        return {
            "sensor_deveuis": sensor_deveuis,
            "sensor_to_space": sensor_to_space,
            "count": len(sensor_deveuis)
        }

    except Exception as e:
        logger.error(f"Error getting sensor list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_space(request: CreateSpaceRequest, db = Depends(get_db_dependency)):
    """Create new parking space"""
    try:
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

        # Insert space
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

        logger.info(f"Created parking space: {request.space_name} ({space_id})")

        return {
            "status": "created",
            "space_id": str(space_id),
            "space_name": request.space_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating space: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
