"""Downlink queue model"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from ..core.database import Base


class DownlinkQueue(Base):
    """Downlink message queue for LoRaWAN devices"""
    __tablename__ = "downlink_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Device target
    device_eui = Column(String(16), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)  # sensor, display
    
    # Message
    payload = Column(Text, nullable=False)
    port = Column(Integer, default=1)
    confirmed = Column(Boolean, default=False)
    
    # Priority
    priority = Column(Integer, default=5)  # 1-10, lower is higher priority
    
    # Status
    status = Column(String(50), default="pending")  # pending, sent, acked, failed
    
    # Retry logic
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    next_attempt_at = Column(TIMESTAMP, nullable=True)
    
    # Result
    sent_at = Column(TIMESTAMP, nullable=True)
    acked_at = Column(TIMESTAMP, nullable=True)
    failed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DownlinkQueue device={self.device_eui} status={self.status}>"
