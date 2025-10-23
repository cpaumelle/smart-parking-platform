# src/core/tenant_context_v6.py

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from enum import IntEnum

class TenantType(str):
    PLATFORM = "platform"
    CUSTOMER = "customer"
    TRIAL = "trial"

class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3
    OWNER = 4
    PLATFORM_ADMIN = 999

class TenantContextV6(BaseModel):
    """Enhanced tenant context for v6"""

    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    tenant_type: str
    user_id: UUID
    username: str
    role: int
    is_platform_admin: bool
    subscription_tier: str = "basic"
    features: dict = {}
    limits: dict = {}

    class Config:
        arbitrary_types_allowed = True

    @property
    def is_viewing_platform_tenant(self) -> bool:
        """Check if currently viewing the platform tenant"""
        return str(self.tenant_id) == "00000000-0000-0000-0000-000000000000"

    @property
    def can_manage_all_tenants(self) -> bool:
        """Check if user can manage all tenants"""
        return self.is_platform_admin and self.is_viewing_platform_tenant

    def can_access_tenant(self, target_tenant_id: UUID) -> bool:
        """Check if user can access a specific tenant"""
        if self.is_platform_admin:
            return True
        return str(self.tenant_id) == str(target_tenant_id)

    async def apply_to_db(self, db: AsyncSession):
        """Apply tenant context to database session for RLS"""
        await db.execute(
            "SET LOCAL app.current_tenant_id = :tenant_id",
            {"tenant_id": str(self.tenant_id)}
        )
        await db.execute(
            "SET LOCAL app.is_platform_admin = :is_admin",
            {"is_admin": self.is_platform_admin}
        )

async def get_tenant_context_v6(
    # In a real implementation, you would have:
    # current_user = Depends(get_current_user),
    # db: AsyncSession = Depends(get_db)
) -> TenantContextV6:
    """
    Dependency to get enhanced tenant context
    This is a placeholder - integrate with your auth system
    """

    # TODO: Implement actual user authentication and tenant lookup
    # For now, returning a mock context
    return TenantContextV6(
        tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
        tenant_name="Platform",
        tenant_slug="platform",
        tenant_type="platform",
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        username="admin",
        role=Role.PLATFORM_ADMIN,
        is_platform_admin=True,
        subscription_tier="enterprise",
        features={"parking": True, "analytics": True, "api_access": True},
        limits={"max_devices": 10000, "max_gateways": 100, "max_spaces": 5000}
    )
