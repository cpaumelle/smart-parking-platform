"""Reservation Pydantic schemas"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class ReservationBase(BaseModel):
    """Base reservation schema"""
    space_id: UUID
    start_time: datetime
    end_time: datetime
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    notes: Optional[str] = None
    
    @field_validator('end_time')
    @classmethod
    def validate_end_time(cls, v, info):
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class ReservationCreate(ReservationBase):
    """Schema for creating a reservation"""
    pass


class ReservationUpdate(BaseModel):
    """Schema for updating a reservation"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ReservationResponse(ReservationBase):
    """Schema for reservation response"""
    id: UUID
    tenant_id: UUID
    user_id: UUID
    status: str
    checked_in: bool
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    rate: Optional[float] = None
    total_cost: Optional[float] = None
    payment_status: str
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ReservationCancel(BaseModel):
    """Schema for cancelling a reservation"""
    cancellation_reason: Optional[str] = None
