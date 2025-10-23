"""Reservation model"""

from sqlalchemy import Column, String, Boolean, Integer, Float, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class Reservation(Base):
    """Parking space reservation model"""
    __tablename__ = "reservations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id = Column(UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False, index=True)
    
    # User information
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_email = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    
    # Reservation time
    start_time = Column(TIMESTAMP, nullable=False, index=True)
    end_time = Column(TIMESTAMP, nullable=False, index=True)
    
    # Status
    status = Column(String(50), default="active")  # active, completed, cancelled, expired, no_show
    
    # Check-in/out
    checked_in = Column(Boolean, default=False)
    checked_in_at = Column(TIMESTAMP, nullable=True)
    checked_out_at = Column(TIMESTAMP, nullable=True)
    
    # Pricing
    rate = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    payment_status = Column(String(50), default="pending")  # pending, paid, refunded
    
    # Cancellation
    cancelled_at = Column(TIMESTAMP, nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSON, default={})
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    space = relationship("Space", back_populates="reservations")
    
    def __repr__(self):
        return f"<Reservation space={self.space_id} user={self.user_id} status={self.status}>"
    
    @property
    def is_active(self) -> bool:
        """Check if reservation is currently active"""
        now = datetime.utcnow()
        return (
            self.status == "active" and
            self.start_time <= now <= self.end_time
        )
    
    @property
    def is_upcoming(self) -> bool:
        """Check if reservation is upcoming"""
        now = datetime.utcnow()
        return self.status == "active" and self.start_time > now
    
    @property
    def is_expired(self) -> bool:
        """Check if reservation has expired"""
        now = datetime.utcnow()
        return self.end_time < now and self.status == "active"
