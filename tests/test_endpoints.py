"""Unit tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.main import app
from app.rate_limiter import RateLimiter, RateLimitResult
from datetime import datetime, timezone


@pytest.fixture
def mock_rate_limiter():
    """Create a mock RateLimiter."""
    return Mock(spec=RateLimiter)


@pytest.fixture
def client(mock_rate_limiter):
    """Create a test client with mocked dependencies."""
    with patch("app.redis_client.get_redis_client") as mock_redis_getter:
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_getter.return_value = mock_redis

        # Override rate limiter in middleware
        with patch("app.middleware.RateLimiter", return_value=mock_rate_limiter):
            client = TestClient(app)
            yield client


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "redis" in data
    assert "version" in data
    assert "timestamp" in data


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Distributed Rate Limiting Service"
    assert "version" in data
    assert data["status"] == "running"


def test_protected_resource_success(client, mock_rate_limiter):
    """Test successful request to protected resource."""
    # Setup - Allow the request
    mock_rate_limiter.check_rate_limit.return_value = RateLimitResult(
        allowed=True,
        limit=100,
        remaining=99,
        reset_at=datetime.now(timezone.utc),
        current_count=1,
        window="2025-10-24-14:30",
    )

    # Execute
    response = client.post(
        "/api/resource",
        json={"action": "process", "data": {"test": "value"}},
        headers={"X-API-Key": "testuser"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Request successful"
    assert "request_id" in data
    assert "timestamp" in data

    # Check rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_protected_resource_rate_limited(client, mock_rate_limiter):
    """Test rate limited request to protected resource."""
    # Setup - Deny the request
    mock_rate_limiter.check_rate_limit.return_value = RateLimitResult(
        allowed=False,
        limit=100,
        remaining=0,
        reset_at=datetime.now(timezone.utc),
        current_count=101,
        window="2025-10-24-14:30",
        retry_after=45,
    )

    # Execute
    response = client.post(
        "/api/resource",
        json={"action": "process"},
        headers={"X-API-Key": "testuser"},
    )

    # Assert
    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "Rate limit exceeded"
    assert data["limit"] == 100
    assert data["retry_after"] == 45

    # Check rate limit headers
    assert response.headers["X-RateLimit-Limit"] == "100"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["Retry-After"] == "45"


def test_rate_limit_status_endpoint(client, mock_rate_limiter):
    """Test rate limit status endpoint."""
    # Setup
    mock_rate_limiter.get_rate_limit_status.return_value = RateLimitResult(
        allowed=True,
        limit=100,
        remaining=42,
        reset_at=datetime.now(timezone.utc),
        current_count=58,
        window="2025-10-24-14:30",
    )

    # Execute
    response = client.get(
        "/rate-limit/status",
        headers={"X-API-Key": "testuser"},
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["identifier"] == "testuser"
    assert data["identifier_type"] == "user"
    assert data["limit"] == 100
    assert data["remaining"] == 42
    assert data["current_count"] == 58


def test_ip_based_rate_limiting(client, mock_rate_limiter):
    """Test IP-based rate limiting when no API key is provided."""
    # Setup
    mock_rate_limiter.check_rate_limit.return_value = RateLimitResult(
        allowed=True,
        limit=20,
        remaining=19,
        reset_at=datetime.now(timezone.utc),
        current_count=1,
        window="2025-10-24-14:30",
    )

    # Execute - No X-API-Key header
    response = client.post(
        "/api/resource",
        json={"action": "process"},
    )

    # Assert
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "20"  # IP limit


def test_health_endpoint_bypasses_rate_limiting(client, mock_rate_limiter):
    """Test that health endpoint bypasses rate limiting."""
    # Execute
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    # Rate limiter should not be called for health endpoint
    mock_rate_limiter.check_rate_limit.assert_not_called()
