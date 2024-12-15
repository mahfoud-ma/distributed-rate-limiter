"""Main FastAPI application for distributed rate limiting service."""

import logging
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header
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
from app.redis_client import get_redis_client, close_redis_client
from app import __version__

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    # Startup
    logger.info("Starting Distributed Rate Limiting Service")
    try:
        # Initialize Redis connection
        redis_client = get_redis_client()
        logger.info("Redis connection established")

        # Store clients in app state
        app.state.redis_client = redis_client
        app.state.rate_limiter = RateLimiter(redis_client)

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Distributed Rate Limiting Service")
    close_redis_client()


# Create FastAPI application
app = FastAPI(
    title="Distributed Rate Limiting Service",
    description="High-performance API rate limiter built with FastAPI and Redis",
    version=__version__,
    lifespan=lifespan,
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint to verify service and Redis connectivity.

    Returns:
        HealthResponse with service status
    """
    redis_client = request.app.state.redis_client

    # Check Redis connectivity
    redis_status = "connected" if redis_client.ping() else "disconnected"

    return HealthResponse(
        status="healthy" if redis_status == "connected" else "degraded",
        redis=redis_status,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/api/resource", response_model=ResourceResponse, tags=["API"])
async def protected_resource(
    resource_request: ResourceRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> ResourceResponse:
    """Protected resource endpoint that enforces rate limiting.

    This is the main demo endpoint that shows rate limiting in action.
    Include an X-API-Key header for user-based limiting, or omit it
    for IP-based limiting.

    Args:
        resource_request: Request body with action and optional data
        x_api_key: Optional API key for user identification

    Returns:
        ResourceResponse with request details
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
    """Check current rate limit status without consuming a request.

    This endpoint allows clients to check their remaining rate limit
    quota without incrementing their counter.

    Args:
        request: HTTP request
        x_api_key: Optional API key for user identification

    Returns:
        RateLimitStatus with current quota information
    """
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
    """Root endpoint with basic service information."""
    return {
        "service": "Distributed Rate Limiting Service",
        "version": __version__,
        "status": "running",
        "documentation": "/docs",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully."""
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
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )
