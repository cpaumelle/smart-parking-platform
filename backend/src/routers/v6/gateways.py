# src/routers/v6/gateways.py

from fastapi import APIRouter, Depends, Query
from typing import Optional
from uuid import UUID

router = APIRouter(prefix="/api/v6/gateways", tags=["gateways-v6"])

@router.get("/")
async def list_gateways(
    include_offline: bool = Query(True, description="Include offline gateways"),
    site_id: Optional[UUID] = Query(None, description="Filter by site ID"),
    # tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    # db = Depends(get_db)
):
    """
    List gateways with proper tenant scoping

    Key difference from v5: Gateways are now tenant-scoped
    """
    # query = select(Gateway)
    #
    # # Tenant scoping
    # if tenant.is_viewing_platform_tenant and tenant.is_platform_admin:
    #     # Platform admin viewing platform: see ALL gateways
    #     pass
    # else:
    #     # Regular view: only tenant's gateways
    #     query = query.where(Gateway.tenant_id == tenant.tenant_id)
    #
    # # Status filter
    # if not include_offline:
    #     query = query.where(Gateway.status == 'online')
    #
    # # Site filter
    # if site_id:
    #     query = query.where(Gateway.site_id == site_id)
    #
    # result = await db.execute(query)
    # gateways = result.scalars().all()

    return {
        "gateways": [],
        "count": 0,
        "tenant_scope": "platform",
        "message": "V6 API endpoint - implement with actual database connection"
    }

@router.get("/{gateway_id}")
async def get_gateway(
    gateway_id: UUID,
    # tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    # db = Depends(get_db)
):
    """Get gateway details"""
    return {
        "id": str(gateway_id),
        "message": "V6 API endpoint - implement with actual database connection"
    }

@router.get("/{gateway_id}/stats")
async def get_gateway_stats(
    gateway_id: UUID,
    # tenant: TenantContextV6 = Depends(get_tenant_context_v6),
    # db = Depends(get_db)
):
    """Get gateway statistics and device connections"""
    return {
        "gateway_id": str(gateway_id),
        "connected_devices": 0,
        "uptime_percentage": 0,
        "message": "V6 API endpoint - implement with actual database connection"
    }
