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
    """Reservation statuses (v5.3 spec)"""
    PENDING = "pending"      # Awaiting payment/approval
    CONFIRMED = "confirmed"  # Active reservation
    CANCELLED = "cancelled"  # Cancelled by user/admin
    EXPIRED = "expired"      # Past end_time

    # Legacy values for backward compatibility
    ACTIVE = "active"        # Deprecated: use CONFIRMED
    COMPLETED = "completed"  # Deprecated: use EXPIRED
    NO_SHOW = "no_show"      # Deprecated: use EXPIRED

class DeviceType(str, Enum):
    """Device types"""
    SENSOR = "sensor"
    DISPLAY = "display"
    GATEWAY = "gateway"

class UserRole(str, Enum):
    """User roles for RBAC"""
    OWNER = "owner"       # Full access including billing and API keys
    ADMIN = "admin"       # Manage sites, spaces, devices, users (not billing)
    OPERATOR = "operator" # Manage reservations, view telemetry, trigger displays
    VIEWER = "viewer"     # Read-only access

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
    site_id: UUID = Field(..., description="Site ID this space belongs to")
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
    site_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None  # Denormalized for fast lookups
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
    request_id: Optional[UUID] = Field(None, description="Idempotency key - if provided, duplicate requests return existing reservation")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID (auto-populated from auth context)")

class Reservation(ReservationBase, TimestampMixin):
    """Complete reservation model"""
    id: UUID
    request_id: UUID
    tenant_id: UUID
    status: ReservationStatus

    class Config:
        orm_mode = True
        use_enum_values = True

class AvailabilitySlot(BaseModel):
    """Availability time slot"""
    start_time: datetime
    end_time: datetime
    available: bool
    reservation_id: Optional[UUID] = None

class SpaceAvailability(BaseModel):
    """Space availability response"""
    space_id: UUID
    space_code: str
    space_name: str
    query_start: datetime
    query_end: datetime
    is_available: bool  # True if completely free during period
    reservations: List[Reservation] = []
    current_state: SpaceState

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

# ============================================================
# Multi-Tenancy & RBAC Models
# ============================================================

class TenantBase(BaseModel):
    """Base tenant model"""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)

class TenantCreate(TenantBase):
    """Model for creating a tenant"""
    pass

class TenantUpdate(BaseModel):
    """Model for updating a tenant"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    metadata: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class Tenant(TenantBase, TimestampMixin):
    """Complete tenant model"""
    id: UUID
    is_active: bool = True

    class Config:
        orm_mode = True

class SiteBase(BaseModel):
    """Base site model"""
    name: str = Field(..., min_length=1, max_length=255)
    timezone: str = Field(default="UTC", max_length=50)
    location: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Address, city, coordinates, etc")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SiteCreate(SiteBase):
    """Model for creating a site"""
    tenant_id: UUID

class SiteUpdate(BaseModel):
    """Model for updating a site"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)
    location: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class Site(SiteBase, TimestampMixin):
    """Complete site model"""
    id: UUID
    tenant_id: UUID
    is_active: bool = True

    class Config:
        orm_mode = True

class UserBase(BaseModel):
    """Base user model"""
    email: str = Field(..., max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        """Basic email validation"""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError("Invalid email format")
        return v.lower()

class UserCreate(UserBase):
    """Model for creating a user"""
    password: str = Field(..., min_length=8, max_length=100)

class UserUpdate(BaseModel):
    """Model for updating a user"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class UserPasswordUpdate(BaseModel):
    """Model for updating user password"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

class User(UserBase, TimestampMixin):
    """Complete user model (without password)"""
    id: UUID
    is_active: bool = True
    email_verified: bool = False
    last_login_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class UserMembershipBase(BaseModel):
    """Base user membership model"""
    role: UserRole
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class UserMembershipCreate(UserMembershipBase):
    """Model for creating a user membership"""
    user_id: UUID
    tenant_id: UUID

class UserMembershipUpdate(BaseModel):
    """Model for updating a user membership"""
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class UserMembership(UserMembershipBase, TimestampMixin):
    """Complete user membership model"""
    id: UUID
    user_id: UUID
    tenant_id: UUID
    is_active: bool = True

    class Config:
        orm_mode = True
        use_enum_values = True

class UserWithMemberships(User):
    """User model with their tenant memberships"""
    memberships: List[UserMembership] = []

class TenantContext(BaseModel):
    """Current tenant context for authenticated requests"""
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    user_id: Optional[UUID] = None
    user_role: Optional[UserRole] = None
    api_key_id: Optional[UUID] = None
    api_key_scopes: Optional[List[str]] = None  # API key scopes for enforcement

    # Resolved from JWT or API key
    source: str  # 'jwt' or 'api_key'

# ============================================================
# Authentication Models
# ============================================================

class LoginRequest(BaseModel):
    """User login request"""
    email: str
    password: str

class LoginResponse(BaseModel):
    """User login response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User
    tenants: List[Dict[str, Any]]  # Available tenants for this user

class TokenData(BaseModel):
    """JWT token payload"""
    user_id: UUID
    tenant_id: UUID
    role: UserRole
    exp: datetime

class UserInvite(BaseModel):
    """User invitation model"""
    email: str
    tenant_id: UUID
    role: UserRole
    message: Optional[str] = None

class UserInviteAccept(BaseModel):
    """Accept user invitation"""
    token: str
    password: str = Field(..., min_length=8, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)

class RegistrationRequest(BaseModel):
    """Combined user and tenant registration request"""
    user: UserCreate
    tenant: TenantCreate

# ============================================================
# API Key Models (Extended for Multi-Tenancy)
# ============================================================

class APIKeyCreate(BaseModel):
    """Model for creating an API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the API key")
    tenant_id: UUID
    scopes: List[str] = Field(
        default_factory=lambda: ["spaces:read", "devices:read"],
        description="API key scopes (e.g., spaces:read, spaces:write, webhook:ingest)"
    )
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class APIKeyResponse(BaseModel):
    """Response when creating an API key (includes plain key once)"""
    id: UUID
    name: str
    key: str  # Plain text key - only shown once!
    tenant_id: UUID
    scopes: List[str]
    created_at: datetime

class APIKey(BaseModel):
    """API key model (without the actual key)"""
    id: UUID
    name: str
    tenant_id: UUID
    scopes: List[str] = []
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime

    class Config:
        orm_mode = True
