"""
Rate Limiting Middleware

Implements token bucket rate limiting using Redis for:
- Per-API-key rate limiting
- Per-IP rate limiting for unauthenticated requests
- Configurable limits with burst support
"""
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    burst_size: int = 10  # Allow bursts up to this many requests


class RateLimiter:
    """Token bucket rate limiter using Redis"""

    def __init__(self, redis_url: str):
        self.redis_client: Optional[redis.Redis] = None
        self.redis_url = redis_url

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Rate limiter initialized with Redis")

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit using token bucket algorithm

        Args:
            key: Unique identifier (API key or IP address)
            config: Rate limit configuration

        Returns:
            Tuple of (allowed: bool, headers: dict)
        """
        if not self.redis_client:
            logger.warning("Rate limiter not initialized, allowing request")
            return True, {}

        now = time.time()

        # Redis key for this limiter
        redis_key = f"rate_limit:{key}"

        # Token bucket parameters
        tokens_per_second = config.requests_per_minute / 60.0
        max_tokens = config.burst_size

        try:
            # Get current bucket state
            pipe = self.redis_client.pipeline()
            pipe.hget(redis_key, "tokens")
            pipe.hget(redis_key, "last_update")
            results = await pipe.execute()

            current_tokens = float(results[0]) if results[0] else max_tokens
            last_update = float(results[1]) if results[1] else now

            # Add tokens based on time elapsed
            time_passed = now - last_update
            new_tokens = min(
                max_tokens,
                current_tokens + (time_passed * tokens_per_second)
            )

            # Check if we have at least 1 token
            logger.debug(f"Rate limit check for {key}: current_tokens={current_tokens}, new_tokens={new_tokens}, time_passed={time_passed}")

            if new_tokens >= 1.0:
                # Consume 1 token
                new_tokens -= 1.0

                # Update bucket state
                pipe = self.redis_client.pipeline()
                pipe.hset(redis_key, "tokens", str(new_tokens))
                pipe.hset(redis_key, "last_update", str(now))
                pipe.expire(redis_key, 120)  # Expire after 2 minutes of inactivity
                await pipe.execute()

                # Calculate reset time
                reset_in = int((max_tokens - new_tokens) / tokens_per_second)

                headers = {
                    "X-RateLimit-Limit": str(config.requests_per_minute),
                    "X-RateLimit-Remaining": str(int(new_tokens)),
                    "X-RateLimit-Reset": str(int(now) + reset_in)
                }

                logger.debug(f"Rate limit passed for {key}: {int(new_tokens)} tokens remaining")
                return True, headers
            else:
                # Rate limited
                reset_in = int((1.0 - new_tokens) / tokens_per_second)

                headers = {
                    "X-RateLimit-Limit": str(config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now) + reset_in),
                    "Retry-After": str(reset_in)
                }

                logger.info(f"Rate limit exceeded for {key}: new_tokens={new_tokens}, need 1.0")
                return False, headers

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, allow the request (fail open)
            return True, {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting"""

    def __init__(
        self,
        app: ASGIApp,
        default_config: RateLimitConfig,
        api_key_config: RateLimitConfig
    ):
        super().__init__(app)
        self.default_config = default_config
        self.api_key_config = api_key_config

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting"""

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Get rate limiter instance (may be None during startup)
        rate_limiter = get_rate_limiter()
        if not rate_limiter or not rate_limiter.redis_client:
            # Rate limiter not ready, allow request
            return await call_next(request)

        # Determine rate limit key and config
        api_key = request.headers.get("X-API-Key")

        if api_key:
            # Rate limit by API key
            limit_key = f"api_key:{api_key[:16]}"  # Use first 16 chars as key
            config = self.api_key_config
        else:
            # Rate limit by IP for unauthenticated requests
            client_ip = request.client.host if request.client else "unknown"
            limit_key = f"ip:{client_ip}"
            config = self.default_config

        # Check rate limit
        allowed, headers = await rate_limiter.check_rate_limit(limit_key, config)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {limit_key}")
            return Response(
                content='{"detail":"Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={**headers, "Content-Type": "application/json"},
                media_type="application/json"
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in headers.items():
            response.headers[header] = value

        return response


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> Optional[RateLimiter]:
    """Get the global rate limiter instance"""
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter):
    """Set the global rate limiter instance"""
    global _rate_limiter
    _rate_limiter = limiter
