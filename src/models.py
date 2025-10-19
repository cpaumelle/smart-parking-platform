"""
Pydantic models for request/response validation
All models in one place for simplicity
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID
import re

# ============================================================
# Enums
# ============================================================

class SpaceState(str, Enum):
    """Parking space states"""
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"

class ReservationStatus(str, Enum):
    """Reservation statuses"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class DeviceType(str, Enum):
    """Device types"""
    SENSOR = "sensor"
    DISPLAY = "display"
    GATEWAY = "gateway"

# ============================================================
# Base Models
# ============================================================

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DevEUIMixin(BaseModel):
    """Mixin for DevEUI validation"""

    @field_validator("sensor_eui", "display_eui", mode="after", check_fields=False)
    @classmethod
    def validate_deveui(cls, v):
        """Validate DevEUI format (16 hex characters)"""
        if v is not None:
            if not re.match(r"^[0-9a-fA-F]{16}$", v):
                raise ValueError(f"Invalid DevEUI format: {v}")
            return v.lower()
        return v

# ============================================================
# Space Models
# ============================================================

class SpaceBase(BaseModel):
    """Base space model with common fields"""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    building: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    zone: Optional[str] = Field(None, max_length=50)
    gps_latitude: Optional[float] = Field(None, ge=-90, le=90)
    gps_longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_gps_coordinates(self):
        """Both GPS coordinates must be provided or both null"""
        if (self.gps_latitude is None) != (self.gps_longitude is None):
            raise ValueError("Both latitude and longitude must be provided or both null")
        return self

class SpaceCreate(SpaceBase, DevEUIMixin):
    """Model for creating a space"""
    sensor_eui: Optional[str] = Field(None, description="16-character hex DevEUI")
    display_eui: Optional[str] = Field(None, description="16-character hex DevEUI")
    state: SpaceState = Field(default=SpaceState.FREE)
    metadata: Optional[Dict[str, Any]] = None

class SpaceUpdate(DevEUIMixin):
    """Model for updating a space (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    building: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    zone: Optional[str] = Field(None, max_length=50)
    sensor_eui: Optional[str] = None
    display_eui: Optional[str] = None
    state: Optional[SpaceState] = None
    metadata: Optional[Dict[str, Any]] = None

class Space(SpaceBase, DevEUIMixin, TimestampMixin):
    """Complete space model with all fields"""
    id: UUID
    sensor_eui: Optional[str] = None
    display_eui: Optional[str] = None
    state: SpaceState
    metadata: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        use_enum_values = True

# ============================================================
# Reservation Models
# ============================================================

class ReservationBase(BaseModel):
    """Base reservation model"""
    space_id: UUID
    start_time: datetime
    end_time: datetime
    user_email: Optional[str] = Field(None, max_length=255)
    user_phone: Optional[str] = Field(None, max_length=20)
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_times(self):
        """Validate reservation times"""
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError("End time must be after start time")

            # Max 24 hour reservation
            duration = self.end_time - self.start_time
            if duration.total_seconds() > 86400:
                raise ValueError("Maximum reservation duration is 24 hours")

        return self

class ReservationCreate(ReservationBase):
    """Model for creating a reservation"""
    pass

class Reservation(ReservationBase, TimestampMixin):
    """Complete reservation model"""
    id: UUID
    status: ReservationStatus

    class Config:
        orm_mode = True
        use_enum_values = True

# ============================================================
# Sensor/Device Models
# ============================================================

class SensorUplink(BaseModel):
    """Parsed sensor uplink data"""
    device_eui: str
    timestamp: datetime

    # Occupancy
    occupancy_state: Optional[SpaceState] = None

    # Telemetry
    battery: Optional[float] = Field(None, ge=0, le=100)
    temperature: Optional[float] = Field(None, ge=-50, le=100)

    # Network
    rssi: Optional[int] = Field(None, ge=-200, le=0)
    snr: Optional[float] = Field(None, ge=-20, le=20)
    gateway_id: Optional[str] = None

    # Raw data
    raw_payload: Optional[str] = None

class DownlinkRequest(BaseModel):
    """Downlink request model"""
    payload: Optional[str] = Field(None, description="Hex or Base64 payload")
    fport: int = Field(default=1, ge=1, le=223)
    confirmed: bool = Field(default=False)

    # High-level command (optional)
    command: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

# ============================================================
# Response Models
# ============================================================

class HealthStatus(BaseModel):
    """Health check response"""
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    version: str
    timestamp: datetime
    checks: Dict[str, str]
    stats: Optional[Dict[str, Any]] = None

class ProcessingResult(BaseModel):
    """Uplink processing result"""
    status: str
    device_eui: Optional[str] = None
    space_code: Optional[str] = None
    state: Optional[str] = None
    request_id: Optional[str] = None
    processing_time_ms: Optional[float] = None

class ApiResponse(BaseModel):
    """Generic API response"""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None

# ============================================================
# Query Parameters
# ============================================================

class PaginationParams(BaseModel):
    """Common pagination parameters"""
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

class SpaceFilters(PaginationParams):
    """Space query filters"""
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[SpaceState] = None
    include_deleted: bool = False

class ReservationFilters(PaginationParams):
    """Reservation query filters"""
    space_id: Optional[UUID] = None
    user_email: Optional[str] = None
    status: Optional[ReservationStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
