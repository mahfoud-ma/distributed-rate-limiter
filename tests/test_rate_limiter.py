"""Unit tests for core rate limiter functionality."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone

from app.rate_limiter import RateLimiter, RateLimitResult
from app.redis_client import RedisClient


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = Mock(spec=RedisClient)
    return redis


@pytest.fixture
def rate_limiter(mock_redis):
    """Create a RateLimiter instance with mock Redis."""
    return RateLimiter(mock_redis)


def test_rate_limit_first_request(rate_limiter, mock_redis):
    """Test that first request is allowed."""
    # Setup
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True

    # Execute
    result = rate_limiter.check_rate_limit("testuser", "user")

    # Assert
    assert result.allowed is True
    assert result.current_count == 1
    assert result.remaining > 0
    mock_redis.incr.assert_called_once()
    mock_redis.expire.assert_called_once()


def test_rate_limit_within_limit(rate_limiter, mock_redis):
    """Test that requests within limit are allowed."""
    # Setup
    mock_redis.get.return_value = "50"
    mock_redis.incr.return_value = 51

    # Execute
    result = rate_limiter.check_rate_limit("testuser", "user")

    # Assert
    assert result.allowed is True
    assert result.current_count == 51
    assert result.remaining > 0
    mock_redis.incr.assert_called_once()


def test_rate_limit_at_limit(rate_limiter, mock_redis):
    """Test that request at exact limit is denied."""
    # Setup - User strategy has 100 req/min limit
    mock_redis.get.return_value = "100"
    mock_redis.ttl.return_value = 30

    # Execute
    result = rate_limiter.check_rate_limit("testuser", "user")

    # Assert
    assert result.allowed is False
    assert result.current_count == 100
    assert result.remaining == 0
    assert result.retry_after == 30
    mock_redis.incr.assert_not_called()


def test_rate_limit_exceeded(rate_limiter, mock_redis):
    """Test that requests exceeding limit are denied."""
    # Setup
    mock_redis.get.return_value = "105"
    mock_redis.ttl.return_value = 45

    # Execute
    result = rate_limiter.check_rate_limit("testuser", "user")

    # Assert
    assert result.allowed is False
    assert result.current_count == 105
    assert result.remaining == 0
    assert result.retry_after == 45


def test_rate_limit_ip_strategy(rate_limiter, mock_redis):
    """Test that IP-based limiting uses correct limits."""
    # Setup - IP strategy has 20 req/min limit
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True

    # Execute
    result = rate_limiter.check_rate_limit("192.168.1.1", "ip")

    # Assert
    assert result.allowed is True
    assert result.limit == 20  # IP limit is 20/min


def test_rate_limit_different_identifiers(rate_limiter, mock_redis):
    """Test that different identifiers have separate rate limits."""
    # Setup
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True

    # Execute
    result1 = rate_limiter.check_rate_limit("user1", "user")
    result2 = rate_limiter.check_rate_limit("user2", "user")

    # Assert
    assert result1.allowed is True
    assert result2.allowed is True
    assert mock_redis.incr.call_count == 2


def test_build_redis_key(rate_limiter):
    """Test Redis key generation."""
    window = "2025-10-24-14:30"
    key = rate_limiter._build_redis_key("user", "testuser", window)

    assert key == "rate:user:testuser:2025-10-24-14:30"


def test_get_current_window_minute(rate_limiter):
    """Test time window generation for minute-level windows."""
    window = rate_limiter._get_current_window(60)

    # Should be in format: YYYY-MM-DD-HH:MM
    assert len(window) == 16
    assert window.count("-") == 3
    assert window.count(":") == 1


def test_get_rate_limit_status(rate_limiter, mock_redis):
    """Test getting rate limit status without incrementing."""
    # Setup
    mock_redis.get.return_value = "75"

    # Execute
    result = rate_limiter.get_rate_limit_status("testuser", "user")

    # Assert
    assert result.current_count == 75
    assert result.remaining == 25  # 100 - 75
    assert result.limit == 100
    mock_redis.incr.assert_not_called()  # Should NOT increment


def test_reset_rate_limit(rate_limiter, mock_redis):
    """Test resetting rate limit for an identifier."""
    # Setup
    mock_redis.delete.return_value = True

    # Execute
    result = rate_limiter.reset_rate_limit("testuser", "user")

    # Assert
    assert result is True
    mock_redis.delete.assert_called_once()
