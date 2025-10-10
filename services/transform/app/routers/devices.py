# app/routers/devices.py
# Version: 0.5.1 - 2025-08-20 07:17 UTC
# Changelog:
# - Added `last_uplink` field to GET /devices based on latest processed uplink
# - Uses subquery on transform.processed_uplinks.timestamp

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import text
from typing import List, Dict, Optional, Any
from database.connections import get_sync_db_session
from models import DeviceContext, DeviceType, IngestUplink, ProcessedUplink, Location as LocationORM
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid
import json

router = APIRouter()

# -----------------------------
# Pydantic Schemas
# -----------------------------
class DeviceIn(BaseModel):
    deveui: str = Field(..., min_length=16, max_length=16, pattern="^[0-9A-Fa-f]{16}$")
    device_type_id: Optional[int] = None
    location_id: Optional[str] = None
    site_id: Optional[str] = None
    floor_id: Optional[str] = None
    room_id: Optional[str] = None
    zone_id: Optional[str] = None
    lifecycle_state: Optional[str] = Field(default="NEW_ORPHAN")

    @validator('deveui', pre=True)
    def to_uppercase(cls, v):
        return v.upper()

class DeviceUpdate(BaseModel):
    device_type_id: Optional[int] = None
    name: Optional[str] = None
    location_id: Optional[str] = None
    site_id: Optional[str] = None
    floor_id: Optional[str] = None
    room_id: Optional[str] = None
    zone_id: Optional[str] = None
    lifecycle_state: Optional[str] = None

class DeviceOut(BaseModel):
    deveui: str
    name: Optional[str]
    device_type_id: Optional[int]
    device_type: Optional[str] = None
    location_id: Optional[str]
    location_name: Optional[str] = None
    site_id: Optional[str]
    floor_id: Optional[str]
    room_id: Optional[str]
    zone_id: Optional[str]
    last_gateway: Optional[str]
    lifecycle_state: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    assigned_at: Optional[datetime]
    unassigned_at: Optional[datetime]
    last_uplink: Optional[datetime] = None

class DeviceTypeOut(BaseModel):
    device_type_id: int
    device_type: str
    description: Optional[str]
    unpacker: Optional[str]
    created_at: Optional[datetime]
    
class DeviceConfig(BaseModel):
    device_type_id: int
    location_id: str
    name: Optional[str] = None
    assigned_at: datetime

class LocationResponse(BaseModel):
    location_id: str
    name: str
    type: str
    parent_id: Optional[str] = None

class LocationHierarchy(BaseModel):
    sites: List[LocationResponse]
    floors: List[LocationResponse]
    rooms: List[LocationResponse]
    zones: List[LocationResponse]

class SmartSuggestion(BaseModel):
    device_type_id: int
    device_type: str
    description: str
    confidence: float
    recent_usage: int

# -----------------------------
# UTILITY: Device with Relationships + Last Seen
# -----------------------------
def enrich_device_data(db: Session, device: DeviceContext) -> Dict:
    """Enrich device data with related information"""
    data = device.as_dict()

    # Add device type name
    if device.device_type_id:
        dt = db.query(DeviceType).filter_by(device_type_id=device.device_type_id).first()
        if dt:
            data["device_type"] = dt.device_type

    # Add location name
    if device.location_id:
        loc = db.query(LocationORM).filter_by(location_id=device.location_id, archived_at=None).first()
        if loc:
            data["location_name"] = loc.name

    # Add last seen timestamp from processed uplinks
    last_uplink = (
        db.query(func.max(ProcessedUplink.timestamp))
        .filter(ProcessedUplink.deveui == device.deveui)
        .scalar()
    )
    data["last_uplink"] = last_uplink

    return data

# -----------------------------
# GET /devices
# -----------------------------
@router.get("", response_model=List[DeviceOut])
def get_devices(
    db: Session = Depends(get_sync_db_session),
    device_type: Optional[str] = None,
    location_id: Optional[str] = None,
    site_id: Optional[str] = None,
    floor_id: Optional[str] = None,
    room_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    assigned_only: Optional[bool] = None
):
    """Get all devices with optional filtering"""
    query = db.query(DeviceContext).filter(DeviceContext.archived_at == None)

    if device_type:
        query = query.join(DeviceType).filter(DeviceType.device_type == device_type)
    if location_id:
        query = query.filter(DeviceContext.location_id == location_id)
    if site_id:
        query = query.filter(DeviceContext.site_id == site_id)
    if floor_id:
        query = query.filter(DeviceContext.floor_id == floor_id)
    if room_id:
        query = query.filter(DeviceContext.room_id == room_id)
    if zone_id:
        query = query.filter(DeviceContext.zone_id == zone_id)
    if lifecycle_state:
        query = query.filter(DeviceContext.lifecycle_state == lifecycle_state)
    if assigned_only is True:
        query = query.filter(DeviceContext.location_id.isnot(None))
    elif assigned_only is False:
        query = query.filter(DeviceContext.location_id.is_(None))

    devices = query.all()
    return [DeviceOut(**enrich_device_data(db, device)) for device in devices]


# -----------------------------
# GET /devices/full-metadata
# -----------------------------
def extract_metadata(source: str, meta: dict) -> dict:
    result = {}

    try:
        if source == "actility" and "DevEUI_uplink" in meta:
            uplink = meta["DevEUI_uplink"]
            result.update({
                "deveui": uplink.get("DevEUI"),
                "last_uplink": uplink.get("Time"),
                "fport": uplink.get("FPort"),
                "rssi": uplink.get("LrrRSSI"),
                "snr": uplink.get("LrrSNR"),
                "gateway_eui": uplink.get("Lrrid"),
                "gateway_name": uplink.get("BaseStationData", {}).get("name"),
                "device_label": uplink.get("CustomerData", {}).get("name"),
                "device_group": uplink.get("CustomerData", {}).get("doms", [{}])[0].get("n"),
                "device_model": uplink.get("DriverCfg", {}).get("mod", {}).get("pId"),
                "device_type_lns": uplink.get("CustomerData", {}).get("alr", {}).get("pro")
            })

        elif source == "netmore":
            result.update({
                "deveui": meta.get("devEui"),
                "last_uplink": meta.get("timestamp"),
                "fport": int(meta.get("fPort") or 0),
                "rssi": int(meta.get("rssi") or 0),
                "snr": float(meta.get("snr") or 0),
                "gateway_eui": meta.get("gatewayIdentifier"),
                "device_type_lns": meta.get("sensorType")
            })

        elif source == "tti":
            ids = meta.get("end_device_ids", {})
            uplink = meta.get("uplink_message") or meta.get("uplink_normalized") or {}
            rx = (uplink.get("rx_metadata") or [{}])[0]
            version = uplink.get("version_ids", {})

            result.update({
                "deveui": ids.get("dev_eui"),
                "last_uplink": uplink.get("received_at") or meta.get("received_at"),
                "fport": uplink.get("f_port"),
                "rssi": rx.get("rssi"),
                "snr": rx.get("snr"),
                "gateway_eui": rx.get("gateway_ids", {}).get("eui"),
                "gateway_id": rx.get("gateway_ids", {}).get("gateway_id"),
                "device_model": version.get("model_id"),
                "device_vendor": version.get("brand_id")
            })

    except Exception as e:
        result["parse_error"] = str(e)

    return result


@router.get("/full-metadata")
def get_full_device_metadata(db: Session = Depends(get_sync_db_session)) -> List[Dict[str, Any]]:
    """Get latest uplink metadata for each known device from ingest_uplinks"""
    subquery = (
        db.query(
            IngestUplink.deveui,
            func.max(IngestUplink.timestamp).label("max_ts")
        )
        .group_by(IngestUplink.deveui)
        .subquery()
    )

    results = (
        db.query(IngestUplink)
        .join(subquery, (IngestUplink.deveui == subquery.c.deveui) & (IngestUplink.timestamp == subquery.c.max_ts))
        .all()
    )

    enriched = []
    for row in results:
        base = {
            "deveui": row.deveui,
            "source": row.source,
            "timestamp": row.timestamp
        }
        try:
            meta = row.uplink_metadata or {}
            enriched_meta = extract_metadata(row.source, meta)
            base.update(enriched_meta)
        except Exception as e:
            base["parse_error"] = str(e)

        enriched.append(base)

    return enriched

# -----------------------------
# PUT /devices/{deveui} - Update Device Assignment
# -----------------------------
@router.put("/{deveui}", response_model=DeviceOut)
def update_device(deveui: str, update: DeviceUpdate, db: Session = Depends(get_sync_db_session)):
    """Update existing device assignment (type, location, name)"""
    device = db.query(DeviceContext).filter_by(deveui=deveui.upper(), archived_at=None).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update only provided fields
    for key, value in update.dict(exclude_unset=True).items():
        if hasattr(device, key):
            setattr(device, key, value)
    
    # Update timestamps
    device.updated_at = datetime.utcnow()
    if update.location_id:
        device.assigned_at = datetime.utcnow()

    db.commit()
    db.refresh(device)
    return DeviceOut(**enrich_device_data(db, device))

@router.get("/device-types", response_model=List[DeviceTypeOut])
def get_device_types(db: Session = Depends(get_sync_db_session)):
    """Get all available device types for the dropdown."""
    query = db.query(DeviceType).filter(DeviceType.archived_at == None).order_by(DeviceType.device_type)
    device_types = query.all()
    return [DeviceTypeOut(**d.__dict__) for d in device_types]

@router.get("/locations/hierarchy", response_model=LocationHierarchy)
def get_location_hierarchy(db: Session = Depends(get_sync_db_session)):
    """Get location hierarchy for cascading selectors."""
    locations = db.query(LocationORM).filter(LocationORM.archived_at == None).order_by(LocationORM.type, LocationORM.name).all()
    
    # Group by type
    hierarchy = {
        'sites': [],
        'floors': [],
        'rooms': [],
        'zones': []
    }
    
    for loc in locations:
        location_response = LocationResponse(**loc.__dict__)
        if location_response.type == 'site':
            hierarchy['sites'].append(location_response)
        elif location_response.type == 'floor':
            hierarchy['floors'].append(location_response)
        elif location_response.type == 'room':
            hierarchy['rooms'].append(location_response)
        elif location_response.type == 'zone':
            hierarchy['zones'].append(location_response)
    
    return LocationHierarchy(**hierarchy)

@router.get("/{deveui}/suggestions", response_model=List[SmartSuggestion])
def get_device_suggestions(deveui: str, db: Session = Depends(get_sync_db_session)):
    """Get smart device type suggestions based on payload analysis."""
    # This query analyzes recent payloads to suggest device types
    query = """
    WITH recent_payloads AS (
        SELECT 
            pu.payload_decoded,
            pu.device_type_id,
            dt.device_type,
            dt.description,
            COUNT(*) as usage_count
        FROM transform.processed_uplinks pu
        JOIN transform.device_types dt ON dt.device_type_id = pu.device_type_id
        WHERE pu.deveui = :deveui
        GROUP BY pu.payload_decoded, pu.device_type_id, dt.device_type, dt.description
    ), 
    confidence_scores AS (
        SELECT 
            device_type_id,
            device_type,
            description,
            usage_count,
            CAST(usage_count AS FLOAT) / SUM(usage_count) OVER () AS confidence
        FROM recent_payloads
    )
    SELECT
        device_type_id,
        device_type,
        description,
        confidence,
        usage_count AS recent_usage
    FROM confidence_scores
    ORDER BY confidence DESC
    LIMIT 5
    """
    
    # Execute the raw SQL query
    result = db.execute(text(query), {'deveui': deveui.upper()})
    suggestions = result.fetchall()
    
    # Convert results to Pydantic models
    return [SmartSuggestion(**dict(s._mapping)) for s in suggestions]
