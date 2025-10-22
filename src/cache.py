"""
Redis caching layer with automatic invalidation

Provides a caching abstraction for frequently accessed data with:
- Automatic key generation from function arguments
- TTL-based expiration
- Pattern-based cache invalidation
- Cache hit/miss metrics
"""
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from datetime import timedelta
import structlog

logger = structlog.get_logger()


class CacheManager:
    """Manages caching operations with Redis"""

    def __init__(self, redis_url: str):
        """
        Initialize the cache manager

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self._hit_count = 0
        self._miss_count = 0

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            cached = await self.redis.get(key)
            if cached:
                self._hit_count += 1
                logger.debug("cache_hit", key=key, hit_rate=self.hit_rate)
                return json.loads(cached)
            else:
                self._miss_count += 1
                logger.debug("cache_miss", key=key, hit_rate=self.hit_rate)
                return None
        except Exception as e:
            logger.error("cache_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        """
        Set cached value with TTL

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (default: 300s = 5 minutes)
        """
        try:
            await self.redis.setex(key, ttl, json.dumps(value, default=str))
            logger.debug("cache_set", key=key, ttl=ttl)
        except Exception as e:
            logger.error("cache_set_error", key=key, error=str(e))

    async def delete(self, key: str):
        """
        Delete cached value

        Args:
            key: Cache key to delete
        """
        try:
            deleted = await self.redis.delete(key)
            logger.debug("cache_delete", key=key, deleted=deleted)
        except Exception as e:
            logger.error("cache_delete_error", key=key, error=str(e))

    async def delete_pattern(self, pattern: str):
        """
        Delete all keys matching pattern

        Args:
            pattern: Redis pattern (e.g., "spaces:*", "tenant:abc:*")
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info("cache_pattern_delete", pattern=pattern, keys_deleted=deleted)
        except Exception as e:
            logger.error("cache_pattern_delete_error", pattern=pattern, error=str(e))

    async def clear_all(self):
        """Clear all cache entries (use with caution!)"""
        try:
            await self.redis.flushdb()
            logger.warning("cache_cleared_all")
        except Exception as e:
            logger.error("cache_clear_all_error", error=str(e))

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self._hit_count + self._miss_count
        if total == 0:
            return 0.0
        return round(self._hit_count / total * 100, 2)

    def cached(self, ttl: int = 300, key_prefix: str = ""):
        """
        Decorator for caching function results

        Args:
            ttl: Time to live in seconds (default: 300s = 5 minutes)
            key_prefix: Prefix for cache key (e.g., "spaces", "reservations")

        Usage:
            @cache.cached(ttl=60, key_prefix="spaces")
            async def get_space_list(tenant_id: str):
                # Expensive database query
                return spaces
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                key_data = f"{func.__name__}:{json.dumps(args, default=str)}:{json.dumps(kwargs, default=str)}"
                cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"

                # Try cache first
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result (handle None results)
                if result is not None:
                    await self.set(cache_key, result, ttl)

                return result
            return wrapper
        return decorator


# Global cache instance (initialized in main.py)
cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get the global cache instance"""
    if cache is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return cache


def init_cache(redis_url: str) -> CacheManager:
    """
    Initialize the global cache instance

    Args:
        redis_url: Redis connection URL

    Returns:
        Initialized CacheManager instance
    """
    global cache
    cache = CacheManager(redis_url)
    logger.info("cache_initialized", redis_url=redis_url.split('@')[-1])  # Don't log credentials
    return cache


# Cache invalidation helpers
async def invalidate_space_cache(tenant_id: str, space_id: Optional[str] = None):
    """
    Invalidate space-related caches

    Args:
        tenant_id: Tenant ID
        space_id: Optional specific space ID (if None, invalidates all tenant spaces)
    """
    cache = get_cache()
    if space_id:
        await cache.delete_pattern(f"spaces:*{tenant_id}*{space_id}*")
        await cache.delete_pattern(f"space_detail:*{space_id}*")
    else:
        await cache.delete_pattern(f"spaces:*{tenant_id}*")


async def invalidate_reservation_cache(tenant_id: str, reservation_id: Optional[str] = None):
    """
    Invalidate reservation-related caches

    Args:
        tenant_id: Tenant ID
        reservation_id: Optional specific reservation ID
    """
    cache = get_cache()
    if reservation_id:
        await cache.delete_pattern(f"reservations:*{reservation_id}*")
    await cache.delete_pattern(f"reservations:*{tenant_id}*")


async def invalidate_device_cache(device_eui: str):
    """
    Invalidate device-related caches

    Args:
        device_eui: Device EUI
    """
    cache = get_cache()
    await cache.delete_pattern(f"devices:*{device_eui}*")
    await cache.delete_pattern(f"orphan_devices:*")


async def invalidate_site_cache(tenant_id: str, site_id: Optional[str] = None):
    """
    Invalidate site-related caches

    Args:
        tenant_id: Tenant ID
        site_id: Optional specific site ID
    """
    cache = get_cache()
    if site_id:
        await cache.delete_pattern(f"sites:*{site_id}*")
    await cache.delete_pattern(f"sites:*{tenant_id}*")
