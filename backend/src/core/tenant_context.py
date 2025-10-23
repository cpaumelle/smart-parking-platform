"""Tenant context management for V6"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum, IntEnum
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from .database import get_db, TenantAwareSession
from .config import settings

class TenantType(str, Enum):
    PLATFORM = "platform"
    CUSTOMER = "customer"
    TRIAL = "trial"

class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3
    OWNER = 4
    PLATFORM_ADMIN = 999

class TenantContext(BaseModel):
    """Enhanced tenant context for V6"""
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    tenant_type: TenantType
    user_id: UUID
    username: str
    email: str
    role: Role
    is_platform_admin: bool = False
    is_cross_tenant_access: bool = False
    subscription_tier: str = "basic"
    features: Dict[str, bool] = Field(default_factory=dict)
    limits: Dict[str, int] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    @property
    def is_viewing_platform_tenant(self) -> bool:
        """Check if currently viewing the platform tenant"""
        return str(self.tenant_id) == settings.platform_tenant_id
    
    @property
    def can_manage_all_tenants(self) -> bool:
        """Check if user can manage all tenants"""
        return self.is_platform_admin and self.is_viewing_platform_tenant
    
    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """Check if user can access a specific tenant"""
        if self.is_platform_admin:
            return True
        return str(self.tenant_id) == str(target_tenant_id)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        permission_map = {
            "read": [Role.VIEWER, Role.OPERATOR, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "write": [Role.OPERATOR, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "manage": [Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN],
            "admin": [Role.OWNER, Role.PLATFORM_ADMIN],
            "platform": [Role.PLATFORM_ADMIN]
        }
        
        allowed_roles = permission_map.get(permission, [])
        return self.role in allowed_roles
    
    def get_db_session(self) -> TenantAwareSession:
        """Get a database session with this tenant context"""
        return TenantAwareSession(
            tenant_id=str(self.tenant_id),
            is_platform_admin=self.is_platform_admin,
            user_role=self.role.name
        )

async def get_tenant_context(
    current_user: dict = Depends(lambda: {"id": UUID("00000000-0000-0000-0000-000000000000")}),
    tenant_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> TenantContext:
    """Get tenant context for the current request
    
    Note: This is a simplified version. Full implementation requires:
    - User authentication (get_current_user dependency)
    - UserMembership and Tenant models
    """
    
    # Simplified implementation for now - will be completed with auth system
    # This allows other components to be developed in parallel
    
    context = TenantContext(
        tenant_id=UUID(settings.platform_tenant_id),
        tenant_name=settings.platform_tenant_name,
        tenant_slug=settings.platform_tenant_slug,
        tenant_type=TenantType.PLATFORM,
        user_id=current_user.get("id", UUID("00000000-0000-0000-0000-000000000000")),
        username=current_user.get("username", "system"),
        email=current_user.get("email", "system@platform.local"),
        role=Role.PLATFORM_ADMIN,
        is_platform_admin=True,
        subscription_tier="enterprise",
        features={},
        limits={}
    )
    
    # Apply RLS context to the session
    if settings.enable_rls:
        await db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(context.tenant_id)}
        )
        await db.execute(
            text("SET LOCAL app.is_platform_admin = :is_admin"),
            {"is_admin": context.is_platform_admin}
        )
    
    return context

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant: TenantContext = kwargs.get("tenant")
            if not tenant or not tenant.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
