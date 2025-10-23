"""Security models - webhook secrets, API keys, refresh tokens"""

from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID, INET
from datetime import datetime
import uuid

from ..core.database import Base


class WebhookSecret(Base):
    """Webhook secret for signature verification"""
    __tablename__ = "webhook_secrets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Secret
    secret = Column(String(255), nullable=False)
    
    # Status
    active = Column(Boolean, default=True)
    
    # Rotation
    rotated_at = Column(TIMESTAMP, nullable=True)
    expires_at = Column(TIMESTAMP, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<WebhookSecret tenant={self.tenant_id} active={self.active}>"


class APIKey(Base):
    """API key for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Key information
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions
    scopes = Column(JSON, default=[])
    
    # Status
    active = Column(Boolean, default=True)
    
    # Usage tracking
    last_used_at = Column(TIMESTAMP, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Expiration
    expires_at = Column(TIMESTAMP, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    
    def __repr__(self):
        return f"<APIKey {self.name} tenant={self.tenant_id}>"


class RefreshToken(Base):
    """Refresh token for JWT authentication"""
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User and tenant
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Token
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    
    # Device information
    device_id = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)
    
    # Status
    revoked = Column(Boolean, default=False)
    revoked_at = Column(TIMESTAMP, nullable=True)
    
    # Expiration
    expires_at = Column(TIMESTAMP, nullable=False)
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    last_used_at = Column(TIMESTAMP, nullable=True)
    
    def __repr__(self):
        return f"<RefreshToken user={self.user_id} revoked={self.revoked}>"
