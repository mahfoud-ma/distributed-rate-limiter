# Configuration management for the rate limiting service

from typing import Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Redis Configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")

    # Redis Sentinel for high availability deployments
    redis_sentinel_hosts: str = Field(default="", alias="REDIS_SENTINEL_HOSTS")
    redis_master_name: str = Field(default="mymaster", alias="REDIS_MASTER_NAME")

    # Application Configuration
    log_level: str = Field(default="WARNING", alias="LOG_LEVEL")
    rate_limit_window: int = Field(default=60, alias="RATE_LIMIT_WINDOW")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    environment: str = Field(default="production", alias="ENVIRONMENT")

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


# Predefined rate limit tiers
# These define different access levels for users
RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "free": {
        "requests_per_minute": 20,
        "requests_per_hour": 1000,
    },
    "premium": {
        "requests_per_minute": 100,
        "requests_per_hour": 10000,
    },
    "admin": {
        "requests_per_minute": -1,  # No limits
        "requests_per_hour": -1,
    },
}

# Default tier applied when user tier isn't specified
DEFAULT_TIER = "free"

# Active rate limit strategies for different identifier types
# User identification uses the X-API-Key header when present,
# otherwise falls back to IP-based limiting for anonymous requests
RATE_LIMIT_STRATEGIES = {
    "user": {
        "limit": RATE_LIMITS["free"]["requests_per_minute"],
        "window": 60,  # seconds
    },
    "ip": {
        "limit": RATE_LIMITS["free"]["requests_per_minute"],
        "window": 60,  # seconds
    },
}


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
