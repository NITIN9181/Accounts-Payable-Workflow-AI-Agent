"""Redis client for AP Workflow Agent."""

try:
    import redis
except ImportError:
    redis = None

from typing import Optional

from ap_workflow.core.config import settings


class RedisClient:
    """Redis client wrapper with connection pooling."""

    def __init__(self, url: str = None, max_connections: int = None):
        """Initialize Redis client with connection pool."""
        self.url = url or settings.redis_url
        self.max_connections = max_connections or settings.redis_pool_size
        self._pool = None
        self._client = None
        self._redis_available = redis is not None

    @property
    def pool(self) -> Optional['redis.ConnectionPool']:
        """Get or create connection pool."""
        if not self._redis_available:
            return None
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                self.url,
                max_connections=self.max_connections,
                decode_responses=False
            )
        return self._pool

    @property
    def client(self) -> Optional['redis.Redis']:
        """Get Redis client instance."""
        if not self._redis_available:
            return None
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client

    def close(self):
        """Close Redis connection pool."""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            self._client = None

    def get(self, key: str) -> Optional[bytes]:
        """Get value from Redis."""
        if not self._redis_available or not self.client:
            return None
        try:
            return self.client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: bytes, ex: int = None) -> bool:
        """Set value in Redis with optional expiration."""
        if not self._redis_available or not self.client:
            return False
        try:
            if ex:
                return self.client.set(key, value, ex=ex)
            return self.client.set(key, value)
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self._redis_available or not self.client:
            return False
        try:
            return bool(self.client.delete(key))
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self._redis_available or not self.client:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False

    def incr(self, key: str) -> int:
        """Increment key value."""
        if not self._redis_available or not self.client:
            return 0
        try:
            return self.client.incr(key)
        except Exception:
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        if not self._redis_available or not self.client:
            return False
        try:
            return bool(self.client.expire(key, seconds))
        except Exception:
            return False


# Global Redis client instance
redis_client = RedisClient()


def get_redis_client() -> RedisClient:
    """Get Redis client instance."""
    return redis_client
