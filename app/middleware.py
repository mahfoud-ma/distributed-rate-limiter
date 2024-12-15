"""Rate limiting middleware for FastAPI."""

import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.rate_limiter import RateLimiter
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting on all requests."""

    # Paths that should bypass rate limiting
    BYPASS_PATHS = ["/health", "/rate-limit/status", "/docs", "/redoc", "/openapi.json", "/"]

    def __init__(self, app, rate_limiter: RateLimiter = None):
        """Initialize rate limit middleware.

        Args:
            app: FastAPI application instance
            rate_limiter: Optional RateLimiter instance (creates one if not provided)
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter(get_redis_client())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response
        """
        # Skip rate limiting for bypass paths
        if request.url.path in self.BYPASS_PATHS:
            return await call_next(request)

        # Extract identifier from request
        identifier, identifier_type = self._extract_identifier(request)

        # Check rate limit
        result = self.rate_limiter.check_rate_limit(identifier, identifier_type)

        # Add rate limit headers to response
        if not result.allowed:
            # Rate limit exceeded - return 429
            logger.warning(
                f"Rate limit exceeded for {identifier_type}={identifier}, "
                f"count={result.current_count}, limit={result.limit}"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": result.limit,
                    "retry_after": result.retry_after,
                    "window": result.window,
                },
                headers=self._build_rate_limit_headers(result),
            )

        # Allowed - proceed with request
        response = await call_next(request)

        # Add rate limit headers to successful response
        for key, value in self._build_rate_limit_headers(result).items():
            response.headers[key] = value

        return response

    def _extract_identifier(self, request: Request) -> tuple[str, str]:
        """Extract rate limit identifier from request.

        Priority:
        1. X-API-Key header (user-based limiting)
        2. Client IP address (IP-based limiting)

        Args:
            request: HTTP request

        Returns:
            Tuple of (identifier, identifier_type)
        """
        # Check for API key header
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if api_key:
            return (api_key, "user")

        # Fallback to IP address
        # Try to get real IP from proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return (client_ip, "ip")

    def _build_rate_limit_headers(self, result) -> dict:
        """Build REST-compliant rate limit headers.

        Headers follow RFC 6585 and common API conventions:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Requests remaining in window
        - X-RateLimit-Reset: Unix timestamp when limit resets
        - Retry-After: Seconds to wait (only on 429)

        Args:
            result: RateLimitResult from rate limiter

        Returns:
            Dictionary of headers
        """
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_at.timestamp())),
        }

        # Add Retry-After header if rate limited
        if not result.allowed:
            headers["Retry-After"] = str(result.retry_after)

        return headers
