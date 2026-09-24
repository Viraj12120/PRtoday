"""Redis caching module for PR Today."""

import logging

from pr_today.config import settings

logger = logging.getLogger("pr_today.cache")

_redis_client = None


async def init_cache() -> None:
    """Initialize the Redis connection pool if configured."""
    global _redis_client
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            # Verify connectivity
            await _redis_client.ping()
            logger.info("Redis connected: %s", settings.REDIS_URL)
        except Exception as e:
            logger.warning("Redis unavailable: %s", e)
            _redis_client = None


async def get_redis():
    """Return the shared Redis client, or None if unavailable."""
    return _redis_client


async def close_cache() -> None:
    """Close the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed.")
