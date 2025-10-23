"""Space and site models"""

from sqlalchemy import Column, String, Boolean, Integer, Float, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class Site(Base):
    """Site model - physical location containing spaces"""
    __tablename__ = "sites"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Site information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Location
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Status
    status = Column(String(50), default="active")
    
    # Metadata
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="sites")
    spaces = relationship("Space", back_populates="site")
    
    def __repr__(self):
        return f"<Site {self.name} tenant={self.tenant_id}>"


class Space(Base):
    """Parking space model with tenant ownership"""
    __tablename__ = "spaces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True, index=True)
    
    # Space information
    name = Column(String(255), nullable=False)
    space_number = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    
    # Space type
    space_type = Column(String(50), default="standard")  # standard, handicap, ev, compact, etc.
    
    # Location within site
    floor = Column(String(50), nullable=True)
    zone = Column(String(50), nullable=True)
    
    # Status
    status = Column(String(50), default="available")  # available, occupied, reserved, out_of_service
    occupancy = Column(Boolean, default=False)
    
    # Device assignment
    has_sensor = Column(Boolean, default=False)
    has_display = Column(Boolean, default=False)
    
    # Reservation support
    reservable = Column(Boolean, default=True)
    
    # Pricing
    hourly_rate = Column(Float, nullable=True)
    daily_rate = Column(Float, nullable=True)
    
    # Metadata
    metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_occupancy_change = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="spaces")
    site = relationship("Site", back_populates="spaces")
    sensor_device = relationship("SensorDevice", back_populates="assigned_space", uselist=False, foreign_keys="SensorDevice.assigned_space_id")
    display_device = relationship("DisplayDevice", back_populates="assigned_space", uselist=False, foreign_keys="DisplayDevice.assigned_space_id")
    device_assignments = relationship("DeviceAssignment", back_populates="space")
    reservations = relationship("Reservation", back_populates="space")
    
    def __repr__(self):
        return f"<Space {self.name} tenant={self.tenant_id}>"
