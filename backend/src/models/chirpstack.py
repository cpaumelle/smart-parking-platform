"""ChirpStack synchronization model"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from ..core.database import Base


class ChirpStackSync(Base):
    """ChirpStack synchronization status"""
    __tablename__ = "chirpstack_sync"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Resource being synced
    resource_type = Column(String(50), nullable=False, index=True)  # device, gateway, application
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # ChirpStack identifiers
    chirpstack_id = Column(String(255), nullable=True, index=True)
    
    # Sync status
    sync_status = Column(String(50), default="pending")  # pending, in_progress, success, failed
    last_sync_at = Column(TIMESTAMP, nullable=True)
    next_sync_at = Column(TIMESTAMP, nullable=True)
    
    # Sync details
    sync_attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    sync_data = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ChirpStackSync {self.resource_type} {self.resource_id} status={self.sync_status}>"
