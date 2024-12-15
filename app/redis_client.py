"""Redis client wrapper with connection pooling and sentinel support."""

import logging
from typing import Optional, List, Tuple
from redis import Redis, ConnectionPool, Sentinel
from redis.exceptions import RedisError, ConnectionError

from app.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client wrapper with connection pooling and error handling."""

    def __init__(self):
        """Initialize Redis client with connection pool."""
        self.settings = get_settings()
        self._client: Optional[Redis] = None
        self._sentinel: Optional[Sentinel] = None
        self._use_sentinel = bool(self.settings.redis_sentinel_hosts)

    def connect(self) -> None:
        """Establish connection to Redis (standalone or Sentinel)."""
        try:
            if self._use_sentinel:
                self._connect_sentinel()
            else:
                self._connect_standalone()

            # Test connection
            self._client.ping()
            logger.info("Successfully connected to Redis")

        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _connect_standalone(self) -> None:
        """Connect to standalone Redis instance."""
        pool = ConnectionPool(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            db=self.settings.redis_db,
            password=self.settings.redis_password if self.settings.redis_password else None,
            max_connections=self.settings.redis_max_connections,
            decode_responses=True,
        )
        self._client = Redis(connection_pool=pool)
        logger.info(f"Connecting to Redis at {self.settings.redis_host}:{self.settings.redis_port}")

    def _connect_sentinel(self) -> None:
        """Connect to Redis via Sentinel for high availability."""
        sentinel_hosts = self._parse_sentinel_hosts()
        self._sentinel = Sentinel(
            sentinel_hosts,
            socket_timeout=0.5,
            decode_responses=True,
        )
        self._client = self._sentinel.master_for(
            self.settings.redis_master_name,
            socket_timeout=0.5,
            db=self.settings.redis_db,
        )
        logger.info(f"Connecting to Redis via Sentinel (master: {self.settings.redis_master_name})")

    def _parse_sentinel_hosts(self) -> List[Tuple[str, int]]:
        """Parse comma-separated sentinel hosts into list of tuples."""
        hosts = []
        for host_str in self.settings.redis_sentinel_hosts.split(","):
            host_str = host_str.strip()
            if ":" in host_str:
                host, port = host_str.split(":")
                hosts.append((host, int(port)))
            else:
                hosts.append((host_str, 26379))
        return hosts

    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            logger.info("Redis connection closed")

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        try:
            return self._client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None

    def incr(self, key: str) -> Optional[int]:
        """Increment value in Redis (atomic operation)."""
        try:
            return self._client.incr(key)
        except RedisError as e:
            logger.error(f"Redis INCR error for key '{key}': {e}")
            return None

    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            return self._client.expire(key, seconds)
        except RedisError as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            return False

    def ttl(self, key: str) -> int:
        """Get time-to-live for a key in seconds."""
        try:
            return self._client.ttl(key)
        except RedisError as e:
            logger.error(f"Redis TTL error for key '{key}': {e}")
            return -1

    def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self._client.ping()
        except RedisError as e:
            logger.error(f"Redis PING error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            return bool(self._client.delete(key))
        except RedisError as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        _redis_client.connect()
    return _redis_client


def close_redis_client() -> None:
    """Close the global Redis client instance."""
    global _redis_client
    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
