"""Tenant Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class TenantBase(BaseModel):
    """Base tenant schema"""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="customer")
    subscription_tier: str = Field(default="basic")
    features: Dict[str, bool] = Field(default_factory=dict)
    limits: Dict[str, int] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TenantCreate(TenantBase):
    """Schema for creating a tenant"""
    pass


class TenantUpdate(BaseModel):
    """Schema for updating a tenant"""
    name: Optional[str] = None
    type: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    features: Optional[Dict[str, bool]] = None
    limits: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class TenantResponse(TenantBase):
    """Schema for tenant response"""
    id: UUID
    subscription_status: str
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
