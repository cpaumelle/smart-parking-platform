"""Device Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


# Sensor Device Schemas
class SensorDeviceBase(BaseModel):
    """Base sensor device schema"""
    dev_eui: str = Field(..., min_length=16, max_length=16)
    join_eui: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    hardware_version: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class SensorDeviceCreate(SensorDeviceBase):
    """Schema for creating a sensor device"""
    app_key: Optional[str] = None


class SensorDeviceUpdate(BaseModel):
    """Schema for updating a sensor device"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    lifecycle_state: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class SensorDeviceResponse(SensorDeviceBase):
    """Schema for sensor device response"""
    id: UUID
    tenant_id: UUID
    status: str
    lifecycle_state: str
    assigned_space_id: Optional[UUID] = None
    assigned_at: Optional[datetime] = None
    chirpstack_device_id: Optional[UUID] = None
    battery_level: Optional[int] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Display Device Schemas
class DisplayDeviceBase(BaseModel):
    """Base display device schema"""
    dev_eui: str = Field(..., min_length=16, max_length=16)
    join_eui: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    display_type: str = Field(default="e-ink")
    hardware_version: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class DisplayDeviceCreate(DisplayDeviceBase):
    """Schema for creating a display device"""
    app_key: Optional[str] = None


class DisplayDeviceUpdate(BaseModel):
    """Schema for updating a display device"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    display_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class DisplayDeviceResponse(DisplayDeviceBase):
    """Schema for display device response"""
    id: UUID
    tenant_id: UUID
    status: str
    lifecycle_state: str
    assigned_space_id: Optional[UUID] = None
    assigned_at: Optional[datetime] = None
    current_state: Optional[str] = None
    battery_level: Optional[int] = None
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Gateway Schemas
class GatewayBase(BaseModel):
    """Base gateway schema"""
    gateway_id: str = Field(..., min_length=16, max_length=16)
    name: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class GatewayCreate(GatewayBase):
    """Schema for creating a gateway"""
    pass


class GatewayUpdate(BaseModel):
    """Schema for updating a gateway"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class GatewayResponse(GatewayBase):
    """Schema for gateway response"""
    id: UUID
    tenant_id: UUID
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Device Assignment Schemas
class DeviceAssignmentCreate(BaseModel):
    """Schema for creating a device assignment"""
    sensor_device_id: UUID
    space_id: UUID
    reason: Optional[str] = None


class DeviceAssignmentResponse(BaseModel):
    """Schema for device assignment response"""
    id: UUID
    sensor_device_id: UUID
    space_id: UUID
    assigned_by: UUID
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    unassigned_by: Optional[UUID] = None
    reason: Optional[str] = None
    
    class Config:
        from_attributes = True
