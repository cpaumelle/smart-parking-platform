# app/routers/spaces.py
# Version: 1.1.0 - 2025-10-13
# Parking spaces router for transform service with full CRUD

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from database.connections import get_sync_db_session
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

router = APIRouter()

# Pydantic schemas
class ParkingSpaceOut(BaseModel):
    space_id: str
    space_name: Optional[str]
    space_code: Optional[str]
    building: Optional[str]
    floor: Optional[str]
    zone: Optional[str]
    current_state: Optional[str]
    occupancy_sensor_deveui: Optional[str]
    display_device_deveui: Optional[str]
    enabled: Optional[bool]
    maintenance_mode: Optional[bool]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class ParkingSpacesResponse(BaseModel):
    spaces: List[ParkingSpaceOut]
    total: int

class CreateSpaceRequest(BaseModel):
    space_name: str = Field(..., min_length=1, max_length=100)
    space_code: Optional[str] = Field(None, max_length=20)
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    occupancy_sensor_deveui: str = Field(..., min_length=16, max_length=16)
    display_device_deveui: str = Field(..., min_length=16, max_length=16)

class UpdateSpaceRequest(BaseModel):
    space_name: Optional[str] = Field(None, min_length=1, max_length=100)
    space_code: Optional[str] = Field(None, max_length=20)
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    occupancy_sensor_deveui: Optional[str] = Field(None, min_length=16, max_length=16)
    display_device_deveui: Optional[str] = Field(None, min_length=16, max_length=16)
    maintenance_mode: Optional[bool] = None
    enabled: Optional[bool] = None

class AvailableSensor(BaseModel):
    dev_eui: str
    sensor_type: Optional[str]
    device_model: Optional[str]
    manufacturer: Optional[str]
    is_available: bool
    assigned_to: Optional[str] = None

class AvailableDisplay(BaseModel):
    dev_eui: str
    display_type: Optional[str]
    device_model: Optional[str]
    manufacturer: Optional[str]
    is_available: bool
    assigned_to: Optional[str] = None

# GET /v1/spaces - List parking spaces with filters
@router.get("/spaces", response_model=ParkingSpacesResponse)
def get_parking_spaces(
    building: Optional[str] = Query(None),
    floor: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_sync_db_session)
):
    try:
        query = """
            SELECT 
                space_id, space_name, space_code, building, floor, zone,
                current_state, occupancy_sensor_deveui, display_device_deveui,
                enabled, maintenance_mode, created_at, updated_at
            FROM parking_spaces.spaces
            WHERE archived_at IS NULL
        """
        
        params = {}
        if building:
            query += " AND building = :building"
            params["building"] = building
        if floor:
            query += " AND floor = :floor"
            params["floor"] = floor
        if zone:
            query += " AND zone = :zone"
            params["zone"] = zone
        if state:
            query += " AND current_state = :state"
            params["state"] = state
        if enabled is not None:
            query += " AND enabled = :enabled"
            params["enabled"] = enabled
        
        query += " ORDER BY building, floor, zone, space_name"
        
        result = db.execute(text(query), params)
        rows = result.fetchall()
        
        spaces = [ParkingSpaceOut(
            space_id=str(row[0]), space_name=row[1], space_code=row[2],
            building=row[3], floor=row[4], zone=row[5], current_state=row[6],
            occupancy_sensor_deveui=row[7], display_device_deveui=row[8],
            enabled=row[9], maintenance_mode=row[10],
            created_at=row[11], updated_at=row[12]
        ) for row in rows]
        
        return ParkingSpacesResponse(spaces=spaces, total=len(spaces))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /v1/spaces/{space_id}
@router.get("/spaces/{space_id}", response_model=ParkingSpaceOut)
def get_parking_space(space_id: str, db: Session = Depends(get_sync_db_session)):
    try:
        query = text("""
            SELECT space_id, space_name, space_code, building, floor, zone,
                   current_state, occupancy_sensor_deveui, display_device_deveui,
                   enabled, maintenance_mode, created_at, updated_at
            FROM parking_spaces.spaces
            WHERE space_id = :space_id AND archived_at IS NULL
        """)
        
        result = db.execute(query, {"space_id": space_id})
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Parking space not found")
        
        return ParkingSpaceOut(
            space_id=str(row[0]), space_name=row[1], space_code=row[2],
            building=row[3], floor=row[4], zone=row[5], current_state=row[6],
            occupancy_sensor_deveui=row[7], display_device_deveui=row[8],
            enabled=row[9], maintenance_mode=row[10],
            created_at=row[11], updated_at=row[12]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST /v1/spaces - Create new space
@router.post("/spaces", response_model=ParkingSpaceOut)
def create_parking_space(space: CreateSpaceRequest, db: Session = Depends(get_sync_db_session)):
    try:
        space_id = str(uuid.uuid4())
        query = text("""
            INSERT INTO parking_spaces.spaces (
                space_id, space_name, space_code, building, floor, zone,
                occupancy_sensor_deveui, display_device_deveui,
                enabled, current_state, created_at, updated_at
            ) VALUES (
                :space_id, :space_name, :space_code, :building, :floor, :zone,
                :occupancy_sensor_deveui, :display_device_deveui,
                TRUE, 'FREE', NOW(), NOW()
            )
            RETURNING space_id, space_name, space_code, building, floor, zone,
                      current_state, occupancy_sensor_deveui, display_device_deveui,
                      enabled, maintenance_mode, created_at, updated_at
        """)
        
        result = db.execute(query, {
            "space_id": space_id,
            "space_name": space.space_name,
            "space_code": space.space_code,
            "building": space.building,
            "floor": space.floor,
            "zone": space.zone,
            "occupancy_sensor_deveui": space.occupancy_sensor_deveui,
            "display_device_deveui": space.display_device_deveui
        })
        db.commit()
        
        row = result.fetchone()
        return ParkingSpaceOut(
            space_id=str(row[0]), space_name=row[1], space_code=row[2],
            building=row[3], floor=row[4], zone=row[5], current_state=row[6],
            occupancy_sensor_deveui=row[7], display_device_deveui=row[8],
            enabled=row[9], maintenance_mode=row[10],
            created_at=row[11], updated_at=row[12]
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# PATCH /v1/spaces/{space_id} - Update space
@router.patch("/spaces/{space_id}", response_model=ParkingSpaceOut)
def update_parking_space(
    space_id: str,
    space: UpdateSpaceRequest,
    db: Session = Depends(get_sync_db_session)
):
    try:
        updates = []
        params = {"space_id": space_id}
        
        if space.space_name is not None:
            updates.append("space_name = :space_name")
            params["space_name"] = space.space_name
        if space.space_code is not None:
            updates.append("space_code = :space_code")
            params["space_code"] = space.space_code
        if space.building is not None:
            updates.append("building = :building")
            params["building"] = space.building
        if space.floor is not None:
            updates.append("floor = :floor")
            params["floor"] = space.floor
        if space.zone is not None:
            updates.append("zone = :zone")
            params["zone"] = space.zone
        if space.occupancy_sensor_deveui is not None:
            updates.append("occupancy_sensor_deveui = :occupancy_sensor_deveui")
            params["occupancy_sensor_deveui"] = space.occupancy_sensor_deveui
        if space.display_device_deveui is not None:
            updates.append("display_device_deveui = :display_device_deveui")
            params["display_device_deveui"] = space.display_device_deveui
        if space.maintenance_mode is not None:
            updates.append("maintenance_mode = :maintenance_mode")
            params["maintenance_mode"] = space.maintenance_mode
        if space.enabled is not None:
            updates.append("enabled = :enabled")
            params["enabled"] = space.enabled
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = NOW()")
        
        query = text(f"""
            UPDATE parking_spaces.spaces
            SET {', '.join(updates)}
            WHERE space_id = :space_id AND archived_at IS NULL
            RETURNING space_id, space_name, space_code, building, floor, zone,
                      current_state, occupancy_sensor_deveui, display_device_deveui,
                      enabled, maintenance_mode, created_at, updated_at
        """)
        
        result = db.execute(query, params)
        db.commit()
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Parking space not found")
        
        return ParkingSpaceOut(
            space_id=str(row[0]), space_name=row[1], space_code=row[2],
            building=row[3], floor=row[4], zone=row[5], current_state=row[6],
            occupancy_sensor_deveui=row[7], display_device_deveui=row[8],
            enabled=row[9], maintenance_mode=row[10],
            created_at=row[11], updated_at=row[12]
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# POST /v1/spaces/{space_id}/archive - Archive space
@router.post("/spaces/{space_id}/archive")
def archive_parking_space(space_id: str, db: Session = Depends(get_sync_db_session)):
    try:
        query = text("""
            UPDATE parking_spaces.spaces
            SET archived_at = NOW(), enabled = FALSE
            WHERE space_id = :space_id AND archived_at IS NULL
            RETURNING space_id
        """)

        result = db.execute(query, {"space_id": space_id})
        db.commit()

        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Parking space not found")

        return {"status": "archived", "space_id": str(row[0])}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# GET /v1/devices/sensors/available - Get available parking sensors
@router.get("/devices/sensors/available", response_model=List[AvailableSensor])
def get_available_sensors(db: Session = Depends(get_sync_db_session)):
    """
    Get list of parking sensors with availability status.
    Sensors are Class A devices (occupancy sensors).
    Only shows sensors marked as parking-related.
    """
    try:
        query = text("""
            SELECT
                sr.dev_eui,
                sr.sensor_type,
                sr.device_model,
                sr.manufacturer,
                CASE
                    WHEN s.occupancy_sensor_deveui IS NULL THEN true
                    ELSE false
                END as is_available,
                s.space_name as assigned_to
            FROM parking_config.sensor_registry sr
            LEFT JOIN parking_spaces.spaces s
                ON sr.dev_eui = s.occupancy_sensor_deveui
                AND s.archived_at IS NULL
            WHERE sr.enabled = true
                AND sr.is_parking_related = true
            ORDER BY is_available DESC, sr.dev_eui
        """)

        result = db.execute(query)
        rows = result.fetchall()

        sensors = [AvailableSensor(
            dev_eui=row[0],
            sensor_type=row[1],
            device_model=row[2],
            manufacturer=row[3],
            is_available=row[4],
            assigned_to=row[5]
        ) for row in rows]

        return sensors
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /v1/devices/displays/available - Get available parking displays
@router.get("/devices/displays/available", response_model=List[AvailableDisplay])
def get_available_displays(db: Session = Depends(get_sync_db_session)):
    """
    Get list of parking displays with availability status.
    Displays are Class C devices (LED displays, busylights).
    """
    try:
        query = text("""
            SELECT
                dr.dev_eui,
                dr.display_type,
                dr.device_model,
                dr.manufacturer,
                CASE
                    WHEN s.display_device_deveui IS NULL THEN true
                    ELSE false
                END as is_available,
                s.space_name as assigned_to
            FROM parking_config.display_registry dr
            LEFT JOIN parking_spaces.spaces s
                ON dr.dev_eui = s.display_device_deveui
                AND s.archived_at IS NULL
            WHERE dr.enabled = true
            ORDER BY is_available DESC, dr.dev_eui
        """)

        result = db.execute(query)
        rows = result.fetchall()

        displays = [AvailableDisplay(
            dev_eui=row[0],
            display_type=row[1],
            device_model=row[2],
            manufacturer=row[3],
            is_available=row[4],
            assigned_to=row[5]
        ) for row in rows]

        return displays
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Pydantic models for device registration
class RegisterSensorRequest(BaseModel):
    dev_eui: str = Field(..., min_length=16, max_length=16)
    sensor_type: str
    device_model: Optional[str] = None
    manufacturer: Optional[str] = None
    is_parking_related: bool = True

class RegisterDisplayRequest(BaseModel):
    dev_eui: str = Field(..., min_length=16, max_length=16)
    display_type: str
    device_model: Optional[str] = None
    manufacturer: Optional[str] = None

class DeviceRegistrationStatus(BaseModel):
    dev_eui: str
    is_parking_sensor: bool
    is_display: bool
    sensor_info: Optional[Dict[str, Any]] = None
    display_info: Optional[Dict[str, Any]] = None

# POST /v1/devices/{deveui}/register-as-sensor
@router.post("/devices/{deveui}/register-as-sensor")
def register_as_parking_sensor(
    deveui: str,
    data: RegisterSensorRequest,
    db: Session = Depends(get_sync_db_session)
):
    """
    Register a device as a parking sensor (Class A occupancy sensor).
    Creates or updates entry in sensor_registry with is_parking_related=true.
    """
    try:
        # Check if already exists
        check_query = text("""
            SELECT sensor_id FROM parking_config.sensor_registry
            WHERE dev_eui = :dev_eui
        """)
        existing = db.execute(check_query, {"dev_eui": deveui}).fetchone()

        if existing:
            # Update existing
            update_query = text("""
                UPDATE parking_config.sensor_registry
                SET sensor_type = :sensor_type,
                    device_model = :device_model,
                    manufacturer = :manufacturer,
                    is_parking_related = :is_parking_related,
                    enabled = true,
                    updated_at = NOW()
                WHERE dev_eui = :dev_eui
            """)
            db.execute(update_query, {
                "dev_eui": deveui,
                "sensor_type": data.sensor_type,
                "device_model": data.device_model,
                "manufacturer": data.manufacturer,
                "is_parking_related": data.is_parking_related
            })
        else:
            # Insert new
            insert_query = text("""
                INSERT INTO parking_config.sensor_registry (
                    dev_eui, sensor_type, device_model, manufacturer,
                    is_parking_related, enabled, created_at, updated_at
                ) VALUES (
                    :dev_eui, :sensor_type, :device_model, :manufacturer,
                    :is_parking_related, true, NOW(), NOW()
                )
            """)
            db.execute(insert_query, {
                "dev_eui": deveui,
                "sensor_type": data.sensor_type,
                "device_model": data.device_model,
                "manufacturer": data.manufacturer,
                "is_parking_related": data.is_parking_related
            })

        db.commit()
        return {"status": "success", "message": f"Device {deveui} registered as parking sensor"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# POST /v1/devices/{deveui}/register-as-display
@router.post("/devices/{deveui}/register-as-display")
def register_as_display(
    deveui: str,
    data: RegisterDisplayRequest,
    db: Session = Depends(get_sync_db_session)
):
    """
    Register a device as a parking display (Class C LED/indicator device).
    Creates or updates entry in display_registry.
    """
    try:
        # Check if already exists
        check_query = text("""
            SELECT display_id FROM parking_config.display_registry
            WHERE dev_eui = :dev_eui
        """)
        existing = db.execute(check_query, {"dev_eui": deveui}).fetchone()

        if existing:
            # Update existing
            update_query = text("""
                UPDATE parking_config.display_registry
                SET display_type = :display_type,
                    device_model = :device_model,
                    manufacturer = :manufacturer,
                    enabled = true,
                    updated_at = NOW()
                WHERE dev_eui = :dev_eui
            """)
            db.execute(update_query, {
                "dev_eui": deveui,
                "display_type": data.display_type,
                "device_model": data.device_model,
                "manufacturer": data.manufacturer
            })
        else:
            # Insert new
            insert_query = text("""
                INSERT INTO parking_config.display_registry (
                    dev_eui, display_type, device_model, manufacturer,
                    enabled, created_at, updated_at
                ) VALUES (
                    :dev_eui, :display_type, :device_model, :manufacturer,
                    true, NOW(), NOW()
                )
            """)
            db.execute(insert_query, {
                "dev_eui": deveui,
                "display_type": data.display_type,
                "device_model": data.device_model,
                "manufacturer": data.manufacturer
            })

        db.commit()
        return {"status": "success", "message": f"Device {deveui} registered as display"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# DELETE /v1/devices/{deveui}/unregister-sensor
@router.delete("/devices/{deveui}/unregister-sensor")
def unregister_parking_sensor(deveui: str, db: Session = Depends(get_sync_db_session)):
    """Remove device from parking sensor registry."""
    try:
        query = text("""
            UPDATE parking_config.sensor_registry
            SET is_parking_related = false, updated_at = NOW()
            WHERE dev_eui = :dev_eui
            RETURNING sensor_id
        """)
        result = db.execute(query, {"dev_eui": deveui})
        db.commit()

        if result.fetchone():
            return {"status": "success", "message": f"Device {deveui} unregistered from parking sensors"}
        else:
            return {"status": "not_found", "message": f"Device {deveui} not found in sensor registry"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# DELETE /v1/devices/{deveui}/unregister-display
@router.delete("/devices/{deveui}/unregister-display")
def unregister_display(deveui: str, db: Session = Depends(get_sync_db_session)):
    """Remove device from parking display registry."""
    try:
        query = text("""
            DELETE FROM parking_config.display_registry
            WHERE dev_eui = :dev_eui
            RETURNING display_id
        """)
        result = db.execute(query, {"dev_eui": deveui})
        db.commit()

        if result.fetchone():
            return {"status": "success", "message": f"Device {deveui} unregistered from displays"}
        else:
            return {"status": "not_found", "message": f"Device {deveui} not found in display registry"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# GET /v1/devices/{deveui}/parking-registration
@router.get("/devices/{deveui}/parking-registration", response_model=DeviceRegistrationStatus)
def get_device_parking_registration(deveui: str, db: Session = Depends(get_sync_db_session)):
    """Get parking registration status for a device."""
    try:
        # Check sensor registry
        sensor_query = text("""
            SELECT sensor_type, device_model, manufacturer, is_parking_related, enabled
            FROM parking_config.sensor_registry
            WHERE dev_eui = :dev_eui
        """)
        sensor_result = db.execute(sensor_query, {"dev_eui": deveui}).fetchone()

        # Check display registry
        display_query = text("""
            SELECT display_type, device_model, manufacturer, enabled
            FROM parking_config.display_registry
            WHERE dev_eui = :dev_eui
        """)
        display_result = db.execute(display_query, {"dev_eui": deveui}).fetchone()

        sensor_info = None
        if sensor_result:
            sensor_info = {
                "sensor_type": sensor_result[0],
                "device_model": sensor_result[1],
                "manufacturer": sensor_result[2],
                "is_parking_related": sensor_result[3],
                "enabled": sensor_result[4]
            }

        display_info = None
        if display_result:
            display_info = {
                "display_type": display_result[0],
                "device_model": display_result[1],
                "manufacturer": display_result[2],
                "enabled": display_result[3]
            }

        return DeviceRegistrationStatus(
            dev_eui=deveui,
            is_parking_sensor=sensor_result is not None and sensor_result[3],  # is_parking_related
            is_display=display_result is not None,
            sensor_info=sensor_info,
            display_info=display_info
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
