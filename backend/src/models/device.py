"""Device models - sensors, displays, gateways, and assignments"""

from sqlalchemy import Column, String, Boolean, Integer, Float, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class SensorDevice(Base):
    """Sensor device model with tenant ownership"""
    __tablename__ = "sensor_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # LoRaWAN identifiers
    dev_eui = Column(String(16), unique=True, nullable=False, index=True)
    join_eui = Column(String(16), nullable=True)
    app_key = Column(String(32), nullable=True)
    
    # Status and lifecycle
    status = Column(String(50), default="unassigned")  # unassigned, assigned, offline, error
    lifecycle_state = Column(String(50), default="provisioned")  # provisioned, commissioned, operational, decommissioned
    
    # Assignment
    assigned_space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True, index=True)
    assigned_at = Column(TIMESTAMP, nullable=True)
    
    # ChirpStack integration
    chirpstack_device_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    chirpstack_device_profile_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Device info
    hardware_version = Column(String(50), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    battery_level = Column(Integer, nullable=True)
    last_seen = Column(TIMESTAMP, nullable=True)
    
    # Metadata
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="sensor_devices")
    assigned_space = relationship("Space", back_populates="sensor_device", foreign_keys=[assigned_space_id])
    assignments = relationship("DeviceAssignment", back_populates="sensor_device")
    
    def __repr__(self):
        return f"<SensorDevice {self.dev_eui} tenant={self.tenant_id}>"


class DisplayDevice(Base):
    """Display device model with tenant ownership"""
    __tablename__ = "display_devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Device identifiers
    dev_eui = Column(String(16), unique=True, nullable=False, index=True)
    join_eui = Column(String(16), nullable=True)
    app_key = Column(String(32), nullable=True)
    
    # Status and lifecycle
    status = Column(String(50), default="unassigned")
    lifecycle_state = Column(String(50), default="provisioned")
    
    # Assignment
    assigned_space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=True, index=True)
    assigned_at = Column(TIMESTAMP, nullable=True)
    
    # ChirpStack integration
    chirpstack_device_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    chirpstack_device_profile_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Display info
    display_type = Column(String(50), default="e-ink")  # e-ink, led, lcd
    hardware_version = Column(String(50), nullable=True)
    firmware_version = Column(String(50), nullable=True)
    battery_level = Column(Integer, nullable=True)
    last_seen = Column(TIMESTAMP, nullable=True)
    
    # Display state
    current_state = Column(String(50), nullable=True)  # vacant, occupied, reserved, error
    last_update_sent = Column(TIMESTAMP, nullable=True)
    last_update_acked = Column(TIMESTAMP, nullable=True)
    
    # Metadata
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="display_devices")
    assigned_space = relationship("Space", back_populates="display_device", foreign_keys=[assigned_space_id])
    
    def __repr__(self):
        return f"<DisplayDevice {self.dev_eui} tenant={self.tenant_id}>"


class Gateway(Base):
    """Gateway model with tenant ownership"""
    __tablename__ = "gateways"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Gateway identifiers
    gateway_id = Column(String(16), unique=True, nullable=False, index=True)
    
    # Status
    status = Column(String(50), default="online")  # online, offline, error
    
    # ChirpStack integration
    chirpstack_gateway_id = Column(String(16), nullable=True, index=True)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    
    # Gateway info
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    last_seen = Column(TIMESTAMP, nullable=True)
    
    # Metadata
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="gateways")
    
    def __repr__(self):
        return f"<Gateway {self.gateway_id} tenant={self.tenant_id}>"


class DeviceAssignment(Base):
    """Device assignment history"""
    __tablename__ = "device_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Assignment details
    sensor_device_id = Column(UUID(as_uuid=True), ForeignKey("sensor_devices.id"), nullable=False, index=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False, index=True)
    
    # Status
    assigned_by = Column(UUID(as_uuid=True), nullable=False)
    assigned_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    unassigned_at = Column(TIMESTAMP, nullable=True)
    unassigned_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Assignment reason
    reason = Column(Text, nullable=True)
    
    # Relationships
    sensor_device = relationship("SensorDevice", back_populates="assignments")
    space = relationship("Space", back_populates="device_assignments")
    
    def __repr__(self):
        return f"<DeviceAssignment device={self.sensor_device_id} space={self.space_id}>"
