# routers/chirpstack_devices.py
# ChirpStack Device Management API
# Version: 1.0.0 - 2025-10-13
# Purpose: Direct database access to ChirpStack tables (same pattern as devices.py)

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from database.chirpstack_connection import get_chirpstack_db
from models_chirpstack import (
    ChirpStackDevice,
    ChirpStackDeviceKeys,
    ChirpStackApplication,
    ChirpStackDeviceProfile
)

router = APIRouter()

# ==================== Pydantic Schemas ====================

class DeviceKeysCreate(BaseModel):
    app_key: str = Field(..., min_length=32, max_length=32, pattern="^[0-9A-Fa-f]{32}$")
    nwk_key: str = Field(..., min_length=32, max_length=32, pattern="^[0-9A-Fa-f]{32}$")

class DeviceCreate(BaseModel):
    dev_eui: str = Field(..., min_length=16, max_length=16, pattern="^[0-9A-Fa-f]{16}$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    application_id: str
    device_profile_id: str
    join_eui: str = Field(default="0000000000000000", min_length=16, max_length=16, pattern="^[0-9A-Fa-f]{16}$")
    enabled_class: str = Field(default="A", pattern="^[ABC]$")
    skip_fcnt_check: bool = False
    is_disabled: bool = False
    external_power_source: bool = False
    tags: dict = {}
    keys: Optional[DeviceKeysCreate] = None

class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    application_id: Optional[str] = None
    device_profile_id: Optional[str] = None
    enabled_class: Optional[str] = Field(None, pattern="^[ABC]$")
    skip_fcnt_check: Optional[bool] = None
    is_disabled: Optional[bool] = None
    external_power_source: Optional[bool] = None
    tags: Optional[dict] = None

class DeviceResponse(BaseModel):
    dev_eui: str
    name: str
    description: str
    application_id: str
    device_profile_id: str
    join_eui: str
    enabled_class: str
    skip_fcnt_check: bool
    is_disabled: bool
    external_power_source: bool
    battery_level: Optional[float]
    tags: dict
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime]

class DeviceListResponse(BaseModel):
    total: int
    items: List[DeviceResponse]

class DeviceKeysResponse(BaseModel):
    dev_eui: str
    app_key: str
    nwk_key: str
    join_nonce: int

class ApplicationResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    tags: dict
    created_at: datetime
    updated_at: datetime

class DeviceProfileResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    region: str
    mac_version: str
    supports_otaa: bool
    supports_class_b: bool
    supports_class_c: bool
    tags: dict
    created_at: datetime
    updated_at: datetime

class BulkDeviceDelete(BaseModel):
    dev_euis: List[str]

class BulkOperationResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    errors: List[str]

# ==================== Helper Functions ====================

def bytes_to_hex(data) -> str:
    """Convert bytes/memoryview to hex string"""
    if data is None:
        return ""
    # Handle memoryview objects from PostgreSQL bytea
    if isinstance(data, memoryview):
        data = bytes(data)
    elif not isinstance(data, bytes):
        data = bytes(data)
    return data.hex().upper()

def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes"""
    return bytes.fromhex(hex_str)

def device_to_response(device: ChirpStackDevice) -> DeviceResponse:
    """Convert ORM model to response schema"""
    return DeviceResponse(
        dev_eui=bytes_to_hex(device.dev_eui),
        name=device.name,
        description=device.description or "",
        application_id=str(device.application_id),
        device_profile_id=str(device.device_profile_id),
        join_eui=bytes_to_hex(device.join_eui),
        enabled_class=device.enabled_class,
        skip_fcnt_check=device.skip_fcnt_check,
        is_disabled=device.is_disabled,
        external_power_source=device.external_power_source,
        battery_level=float(device.battery_level) if device.battery_level else None,
        tags=device.tags or {},
        created_at=device.created_at,
        updated_at=device.updated_at,
        last_seen_at=device.last_seen_at
    )

# ==================== Device Endpoints ====================

@router.get("/devices", response_model=DeviceListResponse, tags=["ChirpStack Devices"])
def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    application_id: Optional[str] = None,
    device_profile_id: Optional[str] = None,
    search: Optional[str] = None,
    device_class: Optional[str] = None,
    include_disabled: bool = True,
    db: Session = Depends(get_chirpstack_db)
):
    """List ChirpStack devices with filters and pagination"""
    query = db.query(ChirpStackDevice)
    
    # Apply filters
    if application_id:
        query = query.filter(ChirpStackDevice.application_id == application_id)
    if device_profile_id:
        query = query.filter(ChirpStackDevice.device_profile_id == device_profile_id)
    if search:
        query = query.filter(ChirpStackDevice.name.ilike(f"%{search}%"))
    if device_class:
        query = query.filter(ChirpStackDevice.enabled_class == device_class)
    if not include_disabled:
        query = query.filter(ChirpStackDevice.is_disabled == False)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    devices = query.offset(skip).limit(limit).all()
    
    return DeviceListResponse(
        total=total,
        items=[device_to_response(d) for d in devices]
    )

@router.get("/devices/{dev_eui}", response_model=DeviceResponse, tags=["ChirpStack Devices"])
def get_device(dev_eui: str, db: Session = Depends(get_chirpstack_db)):
    """Get a specific ChirpStack device by DevEUI"""
    device = db.query(ChirpStackDevice).filter(
        ChirpStackDevice.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {dev_eui} not found")
    
    return device_to_response(device)

@router.post("/devices", response_model=DeviceResponse, status_code=201, tags=["ChirpStack Devices"])
def create_device(device_data: DeviceCreate, db: Session = Depends(get_chirpstack_db)):
    """Create a new ChirpStack device"""
    # Check if device already exists
    existing = db.query(ChirpStackDevice).filter(
        ChirpStackDevice.dev_eui == hex_to_bytes(device_data.dev_eui)
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail=f"Device {device_data.dev_eui} already exists")
    
    # Create device
    device = ChirpStackDevice(
        dev_eui=hex_to_bytes(device_data.dev_eui),
        name=device_data.name,
        description=device_data.description,
        application_id=device_data.application_id,
        device_profile_id=device_data.device_profile_id,
        join_eui=hex_to_bytes(device_data.join_eui),
        enabled_class=device_data.enabled_class,
        skip_fcnt_check=device_data.skip_fcnt_check,
        is_disabled=device_data.is_disabled,
        external_power_source=device_data.external_power_source,
        tags=device_data.tags,
        variables={},
        app_layer_params={}
    )
    
    db.add(device)
    
    # Create keys if provided
    if device_data.keys:
        keys = ChirpStackDeviceKeys(
            dev_eui=hex_to_bytes(device_data.dev_eui),
            app_key=hex_to_bytes(device_data.keys.app_key),
            nwk_key=hex_to_bytes(device_data.keys.nwk_key),
            join_nonce=0
        )
        db.add(keys)
    
    db.commit()
    db.refresh(device)
    
    return device_to_response(device)

@router.put("/devices/{dev_eui}", response_model=DeviceResponse, tags=["ChirpStack Devices"])
def update_device(dev_eui: str, update_data: DeviceUpdate, db: Session = Depends(get_chirpstack_db)):
    """Update a ChirpStack device"""
    device = db.query(ChirpStackDevice).filter(
        ChirpStackDevice.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {dev_eui} not found")
    
    # Update fields
    if update_data.name is not None:
        device.name = update_data.name
    if update_data.description is not None:
        device.description = update_data.description
    if update_data.application_id is not None:
        device.application_id = update_data.application_id
    if update_data.device_profile_id is not None:
        device.device_profile_id = update_data.device_profile_id
    if update_data.enabled_class is not None:
        device.enabled_class = update_data.enabled_class
    if update_data.skip_fcnt_check is not None:
        device.skip_fcnt_check = update_data.skip_fcnt_check
    if update_data.is_disabled is not None:
        device.is_disabled = update_data.is_disabled
    if update_data.external_power_source is not None:
        device.external_power_source = update_data.external_power_source
    if update_data.tags is not None:
        device.tags = update_data.tags
    
    db.commit()
    db.refresh(device)
    
    return device_to_response(device)

@router.delete("/devices/{dev_eui}", status_code=204, tags=["ChirpStack Devices"])
def delete_device(dev_eui: str, db: Session = Depends(get_chirpstack_db)):
    """Delete a ChirpStack device"""
    device = db.query(ChirpStackDevice).filter(
        ChirpStackDevice.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {dev_eui} not found")
    
    db.delete(device)
    db.commit()
    
    return None

# ==================== Device Keys Endpoints ====================

@router.get("/devices/{dev_eui}/keys", response_model=DeviceKeysResponse, tags=["ChirpStack Device Keys"])
def get_device_keys(dev_eui: str, db: Session = Depends(get_chirpstack_db)):
    """Get device OTAA keys"""
    keys = db.query(ChirpStackDeviceKeys).filter(
        ChirpStackDeviceKeys.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if not keys:
        raise HTTPException(status_code=404, detail=f"Keys not found for device {dev_eui}")
    
    return DeviceKeysResponse(
        dev_eui=dev_eui,
        app_key=bytes_to_hex(keys.app_key),
        nwk_key=bytes_to_hex(keys.nwk_key),
        join_nonce=keys.join_nonce
    )

@router.put("/devices/{dev_eui}/keys", response_model=DeviceKeysResponse, tags=["ChirpStack Device Keys"])
def update_device_keys(dev_eui: str, keys_data: DeviceKeysCreate, db: Session = Depends(get_chirpstack_db)):
    """Create or update device OTAA keys"""
    # Check device exists
    device = db.query(ChirpStackDevice).filter(
        ChirpStackDevice.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {dev_eui} not found")
    
    # Check if keys exist
    keys = db.query(ChirpStackDeviceKeys).filter(
        ChirpStackDeviceKeys.dev_eui == hex_to_bytes(dev_eui)
    ).first()
    
    if keys:
        # Update existing keys
        keys.app_key = hex_to_bytes(keys_data.app_key)
        keys.nwk_key = hex_to_bytes(keys_data.nwk_key)
    else:
        # Create new keys
        keys = ChirpStackDeviceKeys(
            dev_eui=hex_to_bytes(dev_eui),
            app_key=hex_to_bytes(keys_data.app_key),
            nwk_key=hex_to_bytes(keys_data.nwk_key),
            join_nonce=0
        )
        db.add(keys)
    
    db.commit()
    db.refresh(keys)
    
    return DeviceKeysResponse(
        dev_eui=dev_eui,
        app_key=bytes_to_hex(keys.app_key),
        nwk_key=bytes_to_hex(keys.nwk_key),
        join_nonce=keys.join_nonce
    )

# ==================== Bulk Operations ====================

@router.delete("/devices/bulk", response_model=BulkOperationResponse, tags=["ChirpStack Bulk Operations"])
def bulk_delete_devices(bulk_data: BulkDeviceDelete, db: Session = Depends(get_chirpstack_db)):
    """Bulk delete devices"""
    succeeded = 0
    failed = 0
    errors = []
    
    for dev_eui in bulk_data.dev_euis:
        try:
            device = db.query(ChirpStackDevice).filter(
                ChirpStackDevice.dev_eui == hex_to_bytes(dev_eui)
            ).first()
            
            if device:
                db.delete(device)
                succeeded += 1
            else:
                failed += 1
                errors.append(f"{dev_eui}: not found")
        except Exception as e:
            failed += 1
            errors.append(f"{dev_eui}: {str(e)}")
    
    db.commit()
    
    return BulkOperationResponse(
        total=len(bulk_data.dev_euis),
        succeeded=succeeded,
        failed=failed,
        errors=errors
    )

# ==================== Reference Data ====================

@router.get("/applications", response_model=List[ApplicationResponse], tags=["ChirpStack Reference Data"])
def list_applications(
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_chirpstack_db)
):
    """List all ChirpStack applications"""
    query = db.query(ChirpStackApplication)
    
    if tenant_id:
        query = query.filter(ChirpStackApplication.tenant_id == tenant_id)
    
    applications = query.all()
    
    return [ApplicationResponse(
        id=str(app.id),
        tenant_id=str(app.tenant_id),
        name=app.name,
        description=app.description or "",
        tags=app.tags or {},
        created_at=app.created_at,
        updated_at=app.updated_at
    ) for app in applications]

@router.get("/device-profiles", response_model=List[DeviceProfileResponse], tags=["ChirpStack Reference Data"])
def list_device_profiles(
    tenant_id: Optional[str] = None,
    supports_class_c: Optional[bool] = None,
    db: Session = Depends(get_chirpstack_db)
):
    """List ChirpStack device profiles"""
    query = db.query(ChirpStackDeviceProfile)
    
    if tenant_id:
        query = query.filter(ChirpStackDeviceProfile.tenant_id == tenant_id)
    if supports_class_c is not None:
        query = query.filter(ChirpStackDeviceProfile.supports_class_c == supports_class_c)
    
    profiles = query.all()
    
    return [DeviceProfileResponse(
        id=str(profile.id),
        tenant_id=str(profile.tenant_id),
        name=profile.name,
        description=profile.description or "",
        region=profile.region,
        mac_version=profile.mac_version,
        supports_otaa=profile.supports_otaa,
        supports_class_b=profile.supports_class_b,
        supports_class_c=profile.supports_class_c,
        tags=profile.tags or {},
        created_at=profile.created_at,
        updated_at=profile.updated_at
    ) for profile in profiles]
