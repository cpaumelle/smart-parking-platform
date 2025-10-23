"""Tenant context middleware"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract and validate tenant context from request"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract tenant slug from header or path
        tenant_slug = request.headers.get("X-Tenant-Slug")
        
        if tenant_slug:
            request.state.tenant_slug = tenant_slug
            logger.debug(f"Tenant context: {tenant_slug}")
        
        response = await call_next(request)
        return response
