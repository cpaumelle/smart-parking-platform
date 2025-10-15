"""
API Usage Tracking Middleware
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
from typing import Callable
import asyncio

logger = logging.getLogger("usage_tracker")


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track API usage per tenant"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        response = await call_next(request)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        tenant_id = None
        api_key_id = None
        
        if hasattr(request.state, "auth"):
            auth = request.state.auth
            if auth and hasattr(auth, "tenant_id"):
                tenant_id = str(auth.tenant_id)
                api_key_id = str(auth.api_key_id) if hasattr(auth, "api_key_id") else None
        
        if tenant_id and not endpoint.startswith("/health") and not endpoint.startswith("/metrics"):
            asyncio.create_task(
                self._record_usage(
                    tenant_id, api_key_id, endpoint, method, status_code,
                    response_time_ms, ip_address, user_agent
                )
            )
        
        return response
    
    async def _record_usage(self, tenant_id, api_key_id, endpoint, method, status_code,
                           response_time_ms, ip_address, user_agent):
        try:
            # Get pool dynamically (after it's initialized)
            from app.database import get_db_pool
            db_pool = get_db_pool()
            
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """SELECT core.record_api_usage($1::UUID, $2::UUID, $3, $4, $5, $6, $7::INET, $8)""",
                    tenant_id, api_key_id, endpoint, method, status_code,
                    response_time_ms, ip_address, user_agent
                )
            logger.debug(f"Usage tracked: {tenant_id} {endpoint} {method} {status_code} {response_time_ms}ms")
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
