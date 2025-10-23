"""Sensor Reading Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class SensorReadingBase(BaseModel):
    """Base sensor reading schema"""
    occupancy: bool
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class SensorReadingCreate(SensorReadingBase):
    """Schema for creating a sensor reading"""
    device_id: UUID
    space_id: Optional[UUID] = None
    rssi: Optional[int] = None
    snr: Optional[float] = None
    gateway_id: Optional[str] = None


class SensorReadingResponse(SensorReadingBase):
    """Schema for sensor reading response"""
    id: UUID
    tenant_id: UUID
    device_id: UUID
    space_id: Optional[UUID] = None
    rssi: Optional[int] = None
    snr: Optional[float] = None
    gateway_id: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True
