"""Redis cache service using redis"""

from typing import Optional, Any
import json
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """Cache service using Redis"""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.disabled = settings.disable_redis

    async def initialize(self):
        """Initialize Redis connection"""
        if self.disabled:
            logger.info("Redis disabled, cache service not initialized")
            return

        pool = None
        try:
            connection_string = (
                f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
            )
            if settings.redis_password:
                connection_string = f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"

            # Create connection pool
            pool = ConnectionPool.from_url(
                connection_string,
                encoding="utf-8",
                decode_responses=True,
            )
            self.redis = Redis(connection_pool=pool)

            # Test connection
            await self.redis.ping()
            logger.info("Redis cache service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.disabled = True
            self.redis = None
            if pool:
                await pool.aclose()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if self.disabled or not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get cache key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        if self.disabled or not self.redis:
            return

        try:
            serialized = json.dumps(value)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")

    async def delete(self, key: str):
        """Delete key from cache"""
        if self.disabled or not self.redis:
            return

        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if self.disabled or not self.redis:
            return False

        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check cache key {key}: {e}")
            return False

    async def ping(self) -> bool:
        """Ping Redis server"""
        if self.disabled or not self.redis:
            return False

        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.aclose()
            # Close connection pool if available
            if hasattr(self.redis, "connection_pool") and self.redis.connection_pool:
                await self.redis.connection_pool.aclose()
            logger.info("Redis cache service closed")


# Global cache instance
cache_service = CacheService()
