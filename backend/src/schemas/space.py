"""Space and Site Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


# Site Schemas
class SiteBase(BaseModel):
    """Base site schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class SiteCreate(SiteBase):
    """Schema for creating a site"""
    pass


class SiteUpdate(BaseModel):
    """Schema for updating a site"""
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class SiteResponse(SiteBase):
    """Schema for site response"""
    id: UUID
    tenant_id: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Space Schemas
class SpaceBase(BaseModel):
    """Base space schema"""
    name: str = Field(..., min_length=1, max_length=255)
    space_number: Optional[str] = None
    description: Optional[str] = None
    space_type: str = Field(default="standard")
    floor: Optional[str] = None
    zone: Optional[str] = None
    reservable: bool = Field(default=True)
    hourly_rate: Optional[float] = None
    daily_rate: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class SpaceCreate(SpaceBase):
    """Schema for creating a space"""
    site_id: Optional[UUID] = None


class SpaceUpdate(BaseModel):
    """Schema for updating a space"""
    name: Optional[str] = None
    space_number: Optional[str] = None
    description: Optional[str] = None
    space_type: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    status: Optional[str] = None
    reservable: Optional[bool] = None
    hourly_rate: Optional[float] = None
    daily_rate: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class SpaceResponse(SpaceBase):
    """Schema for space response"""
    id: UUID
    tenant_id: UUID
    site_id: Optional[UUID] = None
    status: str
    occupancy: bool
    has_sensor: bool
    has_display: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_occupancy_change: Optional[datetime] = None
    
    class Config:
        from_attributes = True
