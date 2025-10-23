"""Display policy model"""

from sqlalchemy import Column, String, Boolean, Integer, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class DisplayPolicy(Base):
    """Display policy for e-ink displays"""
    __tablename__ = "display_policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Policy information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Update policy
    update_on_occupancy_change = Column(Boolean, default=True)
    update_on_reservation_change = Column(Boolean, default=True)
    update_interval_minutes = Column(Integer, default=30)
    
    # Display content
    show_space_number = Column(Boolean, default=True)
    show_qr_code = Column(Boolean, default=True)
    show_reservation_info = Column(Boolean, default=True)
    
    # Display behavior
    invert_on_occupied = Column(Boolean, default=True)
    brightness_level = Column(Integer, default=100)
    
    # Custom content
    custom_content = Column(JSON, default={})
    
    # Status
    active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DisplayPolicy {self.name} tenant={self.tenant_id}>"
