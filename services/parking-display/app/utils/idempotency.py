# services/parking-display/app/utils/idempotency.py
from typing import Optional, Any
import redis.asyncio as redis
import json
import logging
from datetime import timedelta

logger = logging.getLogger("idempotency")

# Redis client (initialize on startup)
_redis_client: Optional[redis.Redis] = None


async def init_redis(redis_url: str = "redis://parking-redis:6379/0"):
    """Initialize Redis client for idempotency cache"""
    global _redis_client
    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        await _redis_client.ping()
        logger.info(f"✅ Redis idempotency cache initialized: {redis_url}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Redis: {e}")
        logger.warning("⚠️ Idempotency will be disabled (Redis unavailable)")
        _redis_client = None


async def close_redis():
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing Redis: {e}")
        finally:
            _redis_client = None


async def get_cached_response(idempotency_key: str) -> Optional[dict]:
    """
    Get cached response for idempotency key

    Returns:
        Cached response dict if exists, None otherwise
    """
    if not _redis_client:
        logger.debug("Redis not initialized, idempotency disabled")
        return None

    try:
        cached_json = await _redis_client.get(f"idempotency:{idempotency_key}")
        if cached_json:
            logger.info(f"♻️ Idempotency cache hit: {idempotency_key}")
            return json.loads(cached_json)
        return None
    except Exception as e:
        logger.error(f"❌ Redis get error: {e}")
        return None


async def cache_response(
    idempotency_key: str,
    response: Any,
    ttl: timedelta = timedelta(hours=24)
):
    """
    Cache response for idempotency key

    Args:
        idempotency_key: Unique key for request
        response: Response to cache (must be JSON-serializable)
        ttl: Time-to-live for cache entry (default: 24 hours)
    """
    if not _redis_client:
        logger.debug("Redis not initialized, skipping cache")
        return

    try:
        response_json = json.dumps(response, default=str)
        await _redis_client.setex(
            f"idempotency:{idempotency_key}",
            int(ttl.total_seconds()),
            response_json
        )
        logger.info(f"💾 Cached response for idempotency key: {idempotency_key}")
    except Exception as e:
        logger.error(f"❌ Redis set error: {e}")
