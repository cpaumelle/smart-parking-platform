"""Tenant and user membership models"""

from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class Tenant(Base):
    """Tenant model for multi-tenancy"""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False, default="customer")  # platform, customer, trial
    
    # Subscription
    subscription_tier = Column(String(50), default="basic")
    subscription_status = Column(String(50), default="active")
    subscription_start = Column(TIMESTAMP, default=datetime.utcnow)
    subscription_end = Column(TIMESTAMP, nullable=True)
    
    # Features and limits
    features = Column(JSON, default={})
    limits = Column(JSON, default={})
    
    # Metadata
    metadata = Column(JSON, default={})
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    sensor_devices = relationship("SensorDevice", back_populates="tenant")
    display_devices = relationship("DisplayDevice", back_populates="tenant")
    gateways = relationship("Gateway", back_populates="tenant")
    spaces = relationship("Space", back_populates="tenant")
    sites = relationship("Site", back_populates="tenant")
    memberships = relationship("UserMembership", back_populates="tenant")
    
    def __repr__(self):
        return f"<Tenant {self.name} ({self.slug})>"


class UserMembership(Base):
    """User membership in a tenant with role"""
    __tablename__ = "user_memberships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Role
    role = Column(String(50), nullable=False, default="viewer")  # viewer, operator, admin, owner, platform_admin
    
    # Status
    status = Column(String(50), default="active")  # active, suspended, invited
    
    # Timestamps
    joined_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="memberships")
    
    def __repr__(self):
        return f"<UserMembership user={self.user_id} tenant={self.tenant_id} role={self.role}>"
