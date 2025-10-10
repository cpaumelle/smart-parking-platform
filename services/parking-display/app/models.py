from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ParkingState(str, Enum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MAINTENANCE = "MAINTENANCE"

class TriggerType(str, Enum):
    SENSOR_UPLINK = "sensor_uplink"
    API_RESERVATION = "api_reservation"
    MANUAL_OVERRIDE = "manual_override"
    SYSTEM_CLEANUP = "system_cleanup"
    RESERVATION_EXPIRED = "reservation_expired"

# Request models
class SensorUplinkRequest(BaseModel):
    """Request from Ingest Service when parking sensor sends uplink"""
    sensor_deveui: str = Field(..., min_length=16, max_length=16, description="Sensor DevEUI")
    space_id: Optional[str] = Field(None, description="Space ID if known by ingest")
    occupancy_state: ParkingState = Field(..., description="Sensor occupancy reading")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: Optional[str] = Field(None, description="Raw hex payload")
    payload_data: Dict[str, Any] = Field(default_factory=dict, description="Decoded payload data")
    rssi: Optional[float] = Field(None, description="Signal strength")
    snr: Optional[float] = Field(None, description="Signal to noise ratio")

    @field_validator("sensor_deveui")
    def validate_deveui(cls, v):
        if not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("DevEUI must be hexadecimal")
        return v.lower()

class ReservationRequest(BaseModel):
    """Create new parking reservation"""
    space_id: str = Field(..., description="Parking space UUID")
    reserved_from: datetime = Field(..., description="Reservation start time")
    reserved_until: datetime = Field(..., description="Reservation end time")
    external_booking_id: Optional[str] = Field(None, description="External system booking ID")
    external_system: str = Field("api", description="External system name")
    external_user_id: Optional[str] = Field(None, description="External user identifier")
    booking_metadata: Dict[str, Any] = Field(default_factory=dict)
    reservation_type: str = Field("standard", description="Reservation type")
    grace_period_minutes: int = Field(15, ge=0, le=60, description="No-show grace period")

    @field_validator("reserved_until")
    def validate_time_range(cls, v, info):
        if "reserved_from" in info.data and v <= info.data["reserved_from"]:
            raise ValueError("reserved_until must be after reserved_from")
        return v

class ManualActuationRequest(BaseModel):
    """Manual override for parking space state"""
    space_id: str = Field(..., description="Parking space UUID")
    new_state: ParkingState = Field(..., description="Desired display state")
    reason: str = Field("manual_override", description="Reason for override")
    override_duration_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Override duration (max 24h)")
    user_id: Optional[str] = Field(None, description="User performing override")

class CreateSpaceRequest(BaseModel):
    """Create new parking space"""
    space_name: str = Field(..., min_length=1, max_length=100)
    space_code: Optional[str] = Field(None, max_length=20)
    location_description: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    occupancy_sensor_deveui: str = Field(..., min_length=16, max_length=16)
    display_device_deveui: str = Field(..., min_length=16, max_length=16)
    auto_actuation: bool = Field(True)
    reservation_priority: bool = Field(True)
    space_metadata: Dict[str, Any] = Field(default_factory=dict)

# Response models
class ActuationResponse(BaseModel):
    """Response from actuation request"""
    status: str = Field(..., description="Processing status")
    space_id: str
    space_name: Optional[str] = None
    previous_state: Optional[ParkingState] = None
    new_state: ParkingState
    reason: str = Field(..., description="Reason for state change")
    processing_time_ms: Optional[float] = None
    actuation_id: Optional[str] = None

class SpaceStatusResponse(BaseModel):
    """Current parking space status"""
    space_id: str
    space_name: str
    current_state: ParkingState
    sensor_state: Optional[ParkingState] = None
    last_sensor_update: Optional[datetime] = None
    last_display_update: Optional[datetime] = None
    active_reservation: Optional[Dict[str, Any]] = None
    enabled: bool

class HealthResponse(BaseModel):
    """Service health status"""
    status: str
    service: str
    version: str
    timestamp: datetime
    database_connected: bool
    parking_spaces_count: int
    active_reservations_count: int
    last_actuation: Optional[datetime] = None
