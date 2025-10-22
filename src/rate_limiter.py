"""
Tenant-aware rate limiting using Redis

Provides rate limiting middleware with per-tenant quotas:
- Read operations: 100 requests/minute, 1000 requests/hour
- Write operations: 10 requests/minute, 100 requests/hour
- Anonymous requests: 20 requests/minute

Features:
- Redis-backed storage for distributed rate limiting
- Tenant-scoped rate limits (isolated per tenant_id)
- Decorator-based limit overrides for specific endpoints
- 429 Too Many Requests responses with retry-after headers
"""
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import structlog
from datetime import datetime, timedelta
import redis.asyncio as redis

from .config import get_settings

logger = structlog.get_logger()
settings = get_settings()


# ============================================================================
# Redis-based Rate Limiter
# ============================================================================

class RateLimiter:
    """
    Redis-based rate limiter with sliding window algorithm

    Uses Redis sorted sets to track request timestamps within time windows.
    Provides tenant-scoped rate limiting with configurable limits.
    """

    def __init__(self, redis_client: redis.Redis):
        """Initialize rate limiter with Redis client"""
        self.redis = redis_client
        self.enabled = settings.rate_limit_enabled

        # Default limits (requests per window)
        self.default_limits = {
            "minute": settings.rate_limit_per_minute,  # 100/min
            "hour": settings.rate_limit_per_hour       # 1000/hour
        }

        # Window durations in seconds
        self.windows = {
            "minute": 60,
            "hour": 3600
        }

        logger.info(
            "rate_limiter_initialized",
            enabled=self.enabled,
            limits=self.default_limits
        )

    async def check_limit(
        self,
        tenant_id: str,
        operation_type: str = "read",
        custom_limits: Optional[dict] = None
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is within rate limits

        Args:
            tenant_id: Tenant identifier for scoped limits
            operation_type: "read" or "write" for different limits
            custom_limits: Override default limits (e.g. {"minute": 10})

        Returns:
            (allowed: bool, retry_after_seconds: Optional[int])
        """
        if not self.enabled:
            return True, None

        # Determine limits based on operation type
        if operation_type == "write":
            limits = {"minute": 10, "hour": 100}  # Stricter for writes
        else:
            limits = self.default_limits.copy()

        # Apply custom limits if provided
        if custom_limits:
            limits.update(custom_limits)

        now = time.time()

        # Check each time window
        for window_name, limit in limits.items():
            window_seconds = self.windows[window_name]

            # Redis key: rate_limit:{tenant_id}:{window}
            key = f"rate_limit:{tenant_id}:{window_name}"

            # Remove old entries outside the window
            window_start = now - window_seconds
            await self.redis.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            request_count = await self.redis.zcard(key)

            # Check if limit exceeded
            if request_count >= limit:
                # Calculate retry-after time (when oldest request expires)
                oldest_requests = await self.redis.zrange(key, 0, 0, withscores=True)
                if oldest_requests:
                    oldest_timestamp = oldest_requests[0][1]
                    retry_after = int(oldest_timestamp + window_seconds - now) + 1

                    logger.warning(
                        "rate_limit_exceeded",
                        tenant_id=tenant_id,
                        window=window_name,
                        limit=limit,
                        current=request_count,
                        retry_after=retry_after
                    )

                    return False, retry_after

            # Add current request to sorted set
            await self.redis.zadd(key, {str(now): now})

            # Set expiration on key (cleanup)
            await self.redis.expire(key, window_seconds + 60)

        # All windows passed
        logger.debug(
            "rate_limit_passed",
            tenant_id=tenant_id,
            operation_type=operation_type
        )

        return True, None

    async def get_limit_info(self, tenant_id: str) -> dict:
        """Get current rate limit status for tenant"""
        info = {}
        now = time.time()

        for window_name, limit in self.default_limits.items():
            window_seconds = self.windows[window_name]
            key = f"rate_limit:{tenant_id}:{window_name}"

            # Remove old entries
            window_start = now - window_seconds
            await self.redis.zremrangebyscore(key, 0, window_start)

            # Count current requests
            current = await self.redis.zcard(key)

            info[window_name] = {
                "limit": limit,
                "current": current,
                "remaining": max(0, limit - current),
                "reset_at": datetime.fromtimestamp(now + window_seconds).isoformat()
            }

        return info


# ============================================================================
# Rate Limiting Middleware
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on all requests

    Extracts tenant_id from request state (set by auth middleware)
    and enforces per-tenant rate limits using Redis.
    """

    def __init__(self, app, rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to request"""

        # Skip rate limiting for health check and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Extract tenant ID from request state (set by auth middleware)
        tenant_id = "anonymous"
        if hasattr(request.state, "tenant_id"):
            tenant_id = str(request.state.tenant_id)

        # Determine operation type (read vs write)
        operation_type = "write" if request.method in ["POST", "PUT", "PATCH", "DELETE"] else "read"

        # Check rate limit
        allowed, retry_after = await self.rate_limiter.check_limit(
            tenant_id=tenant_id,
            operation_type=operation_type
        )

        if not allowed:
            # Rate limit exceeded - return 429
            logger.warning(
                "rate_limit_rejected",
                tenant_id=tenant_id,
                method=request.method,
                path=request.url.path,
                retry_after=retry_after
            )

            headers = {
                "X-RateLimit-Limit": str(self.rate_limiter.default_limits["minute"]),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after)
            }

            return JSONResponse(
                status_code=429,
                headers=headers,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded for tenant {tenant_id}. Please try again in {retry_after} seconds.",
                    "retry_after": retry_after,
                    "tenant_id": tenant_id
                }
            )

        # Add rate limit headers to response
        response = await call_next(request)

        # Get current limit info
        limit_info = await self.rate_limiter.get_limit_info(tenant_id)
        minute_info = limit_info.get("minute", {})

        response.headers["X-RateLimit-Limit"] = str(minute_info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(minute_info.get("remaining", 0))

        return response


# ============================================================================
# Decorator for Custom Rate Limits
# ============================================================================

def rate_limit(limit_per_minute: Optional[int] = None, limit_per_hour: Optional[int] = None):
    """
    Decorator to override rate limits for specific endpoints

    Example:
        @router.post("/spaces")
        @rate_limit(limit_per_minute=5, limit_per_hour=50)
        async def create_space():
            pass

    Args:
        limit_per_minute: Custom minute limit
        limit_per_hour: Custom hour limit
    """
    def decorator(func: Callable):
        # Store custom limits as function attribute
        custom_limits = {}
        if limit_per_minute is not None:
            custom_limits["minute"] = limit_per_minute
        if limit_per_hour is not None:
            custom_limits["hour"] = limit_per_hour

        func._rate_limit_override = custom_limits
        return func

    return decorator


# ============================================================================
# Helper Functions
# ============================================================================

def get_tenant_id_from_request(request: Request) -> str:
    """Extract tenant ID from request for rate limiting"""
    if hasattr(request.state, "tenant_id"):
        return str(request.state.tenant_id)

    # Fallback to X-Tenant-ID header if available
    return request.headers.get("X-Tenant-ID", "anonymous")
