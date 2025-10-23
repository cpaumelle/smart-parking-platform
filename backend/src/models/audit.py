"""Audit log model"""

from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID, INET
from datetime import datetime
import uuid

from ..core.database import Base


class AuditLog(Base):
    """Immutable audit log for all system actions"""
    __tablename__ = "audit_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    
    # Actor information
    actor_type = Column(String(50), nullable=False)  # user, api_key, system, webhook
    actor_id = Column(String(255), nullable=True, index=True)
    actor_details = Column(JSON, default={})
    
    # Action information
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)
    
    # Change tracking
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Request context
    request_id = Column(String(255), nullable=True, index=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timestamp (immutable)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog {self.action} {self.resource_type} by {self.actor_type}>"
