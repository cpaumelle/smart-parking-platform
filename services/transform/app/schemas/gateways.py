# schemas/gateways.py
# Version: 0.2.1 - 2025-08-05 13:35 UTC
# Changelog:
# - GatewayUpdate schema now includes `archived_at: Optional[datetime]`
# - Allows unarchiving via PUT /gateways/{gw_eui}

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class GatewayIn(BaseModel):
    gw_eui: str
    gateway_name: Optional[str] = None
    site_id: Optional[UUID] = None
    location_id: Optional[UUID] = None

class GatewayUpdate(BaseModel):
    gateway_name: Optional[str] = None
    site_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    archived_at: Optional[datetime] = None  # ✅ Allow unarchiving

class GatewayOut(GatewayIn):
    gw_eui: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    status: Optional[str] = "offline"

    class Config:
        from_attributes = True
