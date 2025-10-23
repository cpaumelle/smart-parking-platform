"""Pydantic schemas for API validation"""

from .tenant import TenantCreate, TenantUpdate, TenantResponse
from .device import (
    SensorDeviceCreate, SensorDeviceUpdate, SensorDeviceResponse,
    DisplayDeviceCreate, DisplayDeviceUpdate, DisplayDeviceResponse,
    GatewayCreate, GatewayUpdate, GatewayResponse,
    DeviceAssignmentCreate, DeviceAssignmentResponse
)
from .space import SpaceCreate, SpaceUpdate, SpaceResponse, SiteCreate, SiteUpdate, SiteResponse
from .reservation import ReservationCreate, ReservationUpdate, ReservationResponse
from .reading import SensorReadingCreate, SensorReadingResponse

__all__ = [
    "TenantCreate", "TenantUpdate", "TenantResponse",
    "SensorDeviceCreate", "SensorDeviceUpdate", "SensorDeviceResponse",
    "DisplayDeviceCreate", "DisplayDeviceUpdate", "DisplayDeviceResponse",
    "GatewayCreate", "GatewayUpdate", "GatewayResponse",
    "DeviceAssignmentCreate", "DeviceAssignmentResponse",
    "SpaceCreate", "SpaceUpdate", "SpaceResponse",
    "SiteCreate", "SiteUpdate", "SiteResponse",
    "ReservationCreate", "ReservationUpdate", "ReservationResponse",
    "SensorReadingCreate", "SensorReadingResponse",
]
