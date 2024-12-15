"""Core rate limiting logic using Fixed Window Counter algorithm."""

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from app.redis_client import RedisClient
from app.config import RATE_LIMIT_STRATEGIES

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check.

    Contains all information needed to construct a proper HTTP response,
    including whether the request was allowed and appropriate headers.
    """
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    current_count: int
    window: str
    retry_after: int = 0


class RateLimiter:
    """Rate limiter using Fixed Window Counter algorithm with Redis.

    This implementation uses atomic Redis operations to prevent race
    conditions when multiple requests arrive simultaneously. Each
    identifier (user or IP) gets its own counter that resets at
    fixed time intervals.
    """

    def __init__(self, redis_client: RedisClient):
        """Initialize rate limiter with Redis client.

        Args:
            redis_client: Redis client instance for storing rate limit data
        """
        self.redis = redis_client

    def check_rate_limit(
        self,
        identifier: str,
        identifier_type: str = "user",
    ) -> RateLimitResult:
        """Check if a request should be allowed based on rate limits.

        This method is called by the middleware for every incoming request.
        It checks the current count and either allows the request (incrementing
        the counter) or denies it with a 429 response.

        Args:
            identifier: User ID or IP address
            identifier_type: Type of identifier ("user" or "ip")

        Returns:
            RateLimitResult with allow/deny decision and metadata
        """
        config = RATE_LIMIT_STRATEGIES.get(identifier_type, RATE_LIMIT_STRATEGIES["ip"])
        limit = config["limit"]
        window_seconds = config["window"]

        window = self._get_current_window(window_seconds)
        redis_key = self._build_redis_key(identifier_type, identifier, window)
        current_count = self._get_current_count(redis_key)

        # Deny if limit already reached
        if current_count >= limit:
            ttl = self.redis.ttl(redis_key)
            retry_after = ttl if ttl > 0 else window_seconds

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=self._calculate_reset_time(window, window_seconds),
                current_count=current_count,
                window=window,
                retry_after=retry_after,
            )

        # Allow request and increment counter atomically
        # INCR is atomic so no race condition with concurrent requests
        new_count = self.redis.incr(redis_key)

        # Set TTL on first request to ensure automatic cleanup
        if new_count == 1:
            self.redis.expire(redis_key, window_seconds)

        remaining = max(0, limit - new_count)

        logger.debug(
            f"Rate limit check: {identifier_type}={identifier}, "
            f"window={window}, count={new_count}/{limit}"
        )

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_at=self._calculate_reset_time(window, window_seconds),
            current_count=new_count,
            window=window,
        )

    def get_rate_limit_status(
        self,
        identifier: str,
        identifier_type: str = "user",
    ) -> RateLimitResult:
        """Get current rate limit status without incrementing counter.

        Used by the status endpoint to let clients check their quota
        without consuming a request.

        Args:
            identifier: User ID or IP address
            identifier_type: Type of identifier ("user" or "ip")

        Returns:
            RateLimitResult with current status
        """
        config = RATE_LIMIT_STRATEGIES.get(identifier_type, RATE_LIMIT_STRATEGIES["ip"])
        limit = config["limit"]
        window_seconds = config["window"]

        window = self._get_current_window(window_seconds)
        redis_key = self._build_redis_key(identifier_type, identifier, window)

        current_count = self._get_current_count(redis_key)
        remaining = max(0, limit - current_count)

        return RateLimitResult(
            allowed=current_count < limit,
            limit=limit,
            remaining=remaining,
            reset_at=self._calculate_reset_time(window, window_seconds),
            current_count=current_count,
            window=window,
        )

    def _build_redis_key(self, identifier_type: str, identifier: str, window: str) -> str:
        """Build Redis key for rate limiting.

        Pattern: rate:{type}:{identifier}:{window}

        Args:
            identifier_type: Type of identifier ("user" or "ip")
            identifier: User ID or IP address
            window: Time window identifier

        Returns:
            Redis key string
        """
        return f"rate:{identifier_type}:{identifier}:{window}"

    def _get_current_window(self, window_seconds: int) -> str:
        """Get current time window identifier.

        Generates a string representing the current time window.
        For 60-second windows, this returns something like "2025-10-25-14:30",
        which means all requests in that minute share the same key.

        Args:
            window_seconds: Window size in seconds

        Returns:
            Window identifier string
        """
        now = datetime.now(timezone.utc)

        if window_seconds == 60:
            # Minute-level window (most common)
            return now.strftime("%Y-%m-%d-%H:%M")
        elif window_seconds == 3600:
            # Hour-level window
            return now.strftime("%Y-%m-%d-%H")
        else:
            # Generic window based on epoch timestamp
            epoch = int(now.timestamp())
            window_start = (epoch // window_seconds) * window_seconds
            return str(window_start)

    def _calculate_reset_time(self, window: str, window_seconds: int) -> datetime:
        """Calculate when the current window will reset.

        Args:
            window: Current window identifier
            window_seconds: Window size in seconds

        Returns:
            Reset time as datetime
        """
        now = datetime.now(timezone.utc)

        if window_seconds == 60:
            # Reset at the end of the current minute
            reset = now.replace(second=0, microsecond=0)
            from datetime import timedelta
            reset = reset + timedelta(minutes=1)
        elif window_seconds == 3600:
            # Reset at the end of the current hour
            reset = now.replace(minute=0, second=0, microsecond=0)
            from datetime import timedelta
            reset = reset + timedelta(hours=1)
        else:
            # Generic window
            epoch = int(now.timestamp())
            window_start = (epoch // window_seconds) * window_seconds
            from datetime import timedelta
            reset = datetime.fromtimestamp(window_start, tz=timezone.utc) + timedelta(seconds=window_seconds)

        return reset

    def _get_current_count(self, redis_key: str) -> int:
        """Get current request count from Redis.

        Args:
            redis_key: Redis key to check

        Returns:
            Current count (0 if key doesn't exist)
        """
        count_str = self.redis.get(redis_key)
        if count_str is None:
            return 0
        try:
            return int(count_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid count value in Redis for key '{redis_key}': {count_str}")
            return 0

    def reset_rate_limit(self, identifier: str, identifier_type: str = "user") -> bool:
        """Reset rate limit for a specific identifier.

        Useful for testing or admin operations. Deletes the current
        window's counter, allowing the identifier to make more requests.

        Args:
            identifier: User ID or IP address
            identifier_type: Type of identifier ("user" or "ip")

        Returns:
            True if successfully reset
        """
        config = RATE_LIMIT_STRATEGIES.get(identifier_type, RATE_LIMIT_STRATEGIES["ip"])
        window = self._get_current_window(config["window"])
        redis_key = self._build_redis_key(identifier_type, identifier, window)

        return self.redis.delete(redis_key)
