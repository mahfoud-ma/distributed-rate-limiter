"""Simplified main app for local development without lifespan issues."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Header, Body
from fastapi.responses import JSONResponse
from typing import Optional

from app.config import get_settings
from app.models import (
    ResourceRequest,
    ResourceResponse,
    RateLimitStatus,
    HealthResponse,
)
from app.middleware import RateLimitMiddleware
from app.rate_limiter import RateLimiter
from app.redis_client import RedisClient
from app import __version__

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Distributed Rate Limiting Service",
    description="High-performance API rate limiter built with FastAPI and Redis",
    version=__version__,
)

# Initialize Redis client and rate limiter
logger.info("Initializing Redis client...")
redis_client = RedisClient()
redis_client.connect()
rate_limiter = RateLimiter(redis_client)

# Store in app state
app.state.redis_client = redis_client
app.state.rate_limiter = rate_limiter

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

logger.info("Application initialized successfully")


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint to verify service and Redis connectivity."""
    redis_client = request.app.state.redis_client
    redis_status = "connected" if redis_client.ping() else "disconnected"

    return HealthResponse(
        status="healthy" if redis_status == "connected" else "degraded",
        redis=redis_status,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/api/resource", response_model=ResourceResponse, tags=["API"])
async def protected_resource(
    resource_request: ResourceRequest = Body(default=ResourceRequest()),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> ResourceResponse:
    """Protected resource endpoint that enforces rate limiting.

    The request body is optional - if not provided, defaults will be used.
    This makes testing easier while still supporting full request payloads.
    """
    request_id = f"req_{uuid.uuid4().hex[:12]}"

    logger.info(f"Processing request {request_id} with action: {resource_request.action}")

    return ResourceResponse(
        message="Request successful",
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        data={
            "processed": True,
            "action": resource_request.action,
            "user_data": resource_request.data,
        },
    )


@app.get("/rate-limit/status", response_model=RateLimitStatus, tags=["Rate Limiting"])
async def get_rate_limit_status(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> RateLimitStatus:
    """Check current rate limit status without consuming a request."""
    rate_limiter = request.app.state.rate_limiter

    # Extract identifier (same logic as middleware)
    if x_api_key:
        identifier = x_api_key
        identifier_type = "user"
    else:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            identifier = forwarded_for.split(",")[0].strip()
        else:
            identifier = request.client.host if request.client else "unknown"
        identifier_type = "ip"

    # Get rate limit status without incrementing
    result = rate_limiter.get_rate_limit_status(identifier, identifier_type)

    return RateLimitStatus(
        identifier=identifier,
        identifier_type=identifier_type,
        limit=result.limit,
        remaining=result.remaining,
        reset_at=result.reset_at,
        window=result.window,
        current_count=result.current_count,
    )


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with comprehensive service information."""
    return {
        "service": "Distributed Rate Limiting Service",
        "description": "High-performance API rate limiter built with FastAPI and Redis",
        "version": __version__,
        "status": "running",
        "algorithm": "Fixed Window Counter",
        "rate_limits": {
            "requests_per_minute": 20,
            "window_seconds": 60,
        },
        "endpoints": {
            "health": "/health",
            "protected_resource": "/api/resource",
            "rate_limit_status": "/rate-limit/status",
            "documentation": "/docs",
            "redoc": "/redoc",
        },
        "features": [
            "User-based rate limiting (via X-API-Key header)",
            "IP-based rate limiting (fallback)",
            "RFC 6585 compliant rate limit headers",
            "Real-time status checking",
            "Redis-backed distributed limiting",
        ],
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main_simple:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )
