"""
Shared dependencies for parking-display service
Provides singleton instances and dependency injection patterns
"""
from fastapi import Depends, Header
from fastapi import Request
from typing import Optional
from app.services.downlink_client import DownlinkClient
from app.utils.tenant_auth import verify_tenant_api_key, TenantAuthResult
from app.database import get_db_pool

# Singleton instances
_downlink_client: DownlinkClient = None

def get_downlink_client() -> DownlinkClient:
    """
    Get shared DownlinkClient instance (singleton pattern).
    
    Returns:
        Shared DownlinkClient instance
    """
    global _downlink_client
    if _downlink_client is None:
        _downlink_client = DownlinkClient()
    return _downlink_client


async def get_authenticated_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> TenantAuthResult:
    """
    FastAPI dependency for tenant authentication via API key.
    
    This is the primary authentication mechanism for all tenant-facing endpoints.
    Validates the X-API-Key header and returns tenant context.
    
    Usage:
        @router.get("/endpoint")
        async def my_endpoint(auth = Depends(get_authenticated_tenant)):
            # auth.tenant_id contains authenticated tenant UUID
            # auth.tenant_slug contains tenant identifier (e.g., "verdegris")
            # auth.subscription_tier contains tier (e.g., "enterprise")
            async with get_tenant_db(auth.tenant_id) as db:
                # Database queries automatically scoped to tenant via RLS
                results = await db.fetch("SELECT * FROM parking_spaces.spaces")
                return {"data": results}
    
    Returns:
        TenantAuthResult: Authenticated tenant context with:
            - tenant_id: UUID
            - tenant_slug: str (e.g., "verdegris")
            - tenant_name: str (e.g., "Verdegris")
            - api_key_id: UUID
            - scopes: list[str]
            - subscription_tier: str
            - is_active: bool
    
    Raises:
        HTTPException 401: Missing or invalid API key format
        HTTPException 403: Invalid, expired, revoked, or inactive tenant
    
    Security:
        - API key validated using bcrypt comparison
        - Tenant status checked (must be active)
        - Key expiration checked
        - Access logged for audit trail
    """
    auth = await verify_tenant_api_key(x_api_key, get_db_pool())
    request.state.auth = auth  # Store for middleware
    return auth
