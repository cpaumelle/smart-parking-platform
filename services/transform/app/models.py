# app/models.py
# Version: 0.5.2 - 2025-07-29 08:35 UTC
# Changelog:
# - Added  field to Gateway, DeviceContext, and DeviceType for soft-deletion support

from sqlalchemy import (
    Column, String, TIMESTAMP, Text, ForeignKey, JSON, Integer, DateTime
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.base import Base
import uuid

# ─── Device Types ───────────────────────────────────────────────────────────────

class DeviceType(Base):
    __tablename__ = "device_types"
    __table_args__ = {"schema": "transform"}

    device_type_id = Column(Integer, primary_key=True, index=True)
    device_type = Column(Text, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    unpacker = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)

    devices = relationship("DeviceContext", back_populates="device_type")

    def as_dict(self):
        return {
            "device_type_id": self.device_type_id,
            "device_type": self.device_type,
            "description": self.description,
            "unpacker": self.unpacker,
            "created_at": self.created_at,
            "archived_at": self.archived_at,
        }

# ─── Device Context ─────────────────────────────────────────────────────────────

class DeviceContext(Base):
    __tablename__ = "device_context"
    __table_args__ = {"schema": "transform"}

    deveui = Column(String, primary_key=True)
    name = Column(String(255), nullable=True)
    location_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    device_type_id = Column(Integer, ForeignKey("transform.device_types.device_type_id", ondelete="SET NULL"), nullable=True)
    site_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    floor_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    room_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    zone_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    last_gateway = Column(String, nullable=True)
    lifecycle_state = Column(String, default="NEW_ORPHAN", nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    assigned_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    unassigned_at = Column(TIMESTAMP(timezone=True), nullable=True)
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)

    device_type = relationship("DeviceType", back_populates="devices")

    def as_dict(self):
        return {
            "deveui": self.deveui,
            "name": self.name,
            "location_id": str(self.location_id) if self.location_id else None,
            "device_type_id": self.device_type_id,
            "site_id": str(self.site_id) if self.site_id else None,
            "floor_id": str(self.floor_id) if self.floor_id else None,
            "room_id": str(self.room_id) if self.room_id else None,
            "zone_id": str(self.zone_id) if self.zone_id else None,
            "last_gateway": self.last_gateway,
            "lifecycle_state": self.lifecycle_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assigned_at": self.assigned_at,
            "unassigned_at": self.unassigned_at,
            "archived_at": self.archived_at,
        }

# ─── Uplinks ────────────────────────────────────────────────────────────────────

class IngestUplink(Base):
    __tablename__ = "ingest_uplinks"
    __table_args__ = {"schema": "transform"}

    uplink_uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingest_uplink_id = Column(Integer, nullable=True)
    deveui = Column(String)
    timestamp = Column(TIMESTAMP)
    fport = Column(Integer, nullable=True)
    payload = Column(Text)
    uplink_metadata = Column(JSON)
    source = Column(String)
    gateway_eui = Column(String, nullable=True)
    inserted_at = Column(TIMESTAMP, server_default=func.now())
    last_updated = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    error_message = Column(Text)

class ProcessedUplink(Base):
    __tablename__ = "processed_uplinks"
    __table_args__ = {"schema": "transform"}

    uplink_uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deveui = Column(String, nullable=False)
    timestamp = Column(DateTime)
    fport = Column(Integer)
    payload = Column(String)
    uplink_metadata = Column(JSON)
    source = Column(String)

    device_type_id = Column(Integer, ForeignKey("transform.device_types.device_type_id", ondelete="SET NULL"), nullable=True)
    site_id = Column(String)
    floor_id = Column(String)
    room_id = Column(String)
    zone_id = Column(String)
    gateway_eui = Column(String)
    payload_decoded = Column(JSONB, nullable=True)

    inserted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    device_type = relationship("DeviceType", primaryjoin="foreign(ProcessedUplink.device_type_id) == DeviceType.device_type_id", lazy="joined")

# ─── Enrichment Logs ─────────────────────────────────────────────────────────────

class EnrichmentLog(Base):
    __tablename__ = "enrichment_logs"
    __table_args__ = {"schema": "transform"}

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uplink_uuid = Column(UUID(as_uuid=True), ForeignKey("transform.ingest_uplinks.uplink_uuid", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(String, nullable=False)
    status = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

# ─── Gateways ────────────────────────────────────────────────────────────────────

class Gateway(Base):
    __tablename__ = "gateways"
    __table_args__ = {"schema": "transform"}

    gw_eui = Column(String, primary_key=True)
    gateway_name = Column(Text, nullable=True)
    site_id = Column(UUID, nullable=True)
    location_id = Column(UUID, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=True)
    status = Column(String, nullable=True)

# ─── Locations ───────────────────────────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": "transform"}

    location_id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    parent_id = Column(UUID, ForeignKey("transform.locations.location_id"), nullable=True)
    uplink_metadata = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def as_dict(self):
        return {
            "location_id": str(self.location_id),
            "name": self.name,
            "type": self.type,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "uplink_metadata": self.uplink_metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
        }

