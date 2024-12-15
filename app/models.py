# Pydantic models for request/response validation

import json
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class ResourceRequest(BaseModel):
    """Request model for the protected resource endpoint."""

    action: str = Field(default="process", description="Action to perform")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Optional request data")

    @model_validator(mode='before')
    @classmethod
    def handle_various_inputs(cls, values):
        """Handle different request body formats gracefully.

        Supports:
        - Empty request body
        - Empty JSON object {}
        - Partial JSON with only some fields
        - Complete JSON with all fields
        - String inputs (attempts to parse)

        This flexibility prevents 422 validation errors from breaking
        rate limit testing and improves API usability.
        """
        if values is None:
            return {'action': 'process', 'data': None}

        # Try to parse string inputs
        if isinstance(values, str):
            try:
                values = json.loads(values)
            except json.JSONDecodeError:
                return {'action': 'process', 'data': None}

        # Handle empty dict
        if values == {}:
            return {'action': 'process', 'data': None}

        # Ensure dict has required fields with defaults
        if isinstance(values, dict):
            if 'action' not in values:
                values['action'] = 'process'
            if 'data' not in values:
                values['data'] = None

        return values

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "action": "process",
                "data": {"key": "value"}
            }
        }


class ResourceResponse(BaseModel):
    """Response model for successful requests."""

    message: str = Field(description="Response message")
    request_id: str = Field(description="Unique request identifier")
    timestamp: datetime = Field(description="Request timestamp")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Optional response data")


class RateLimitError(BaseModel):
    """Response model for rate limit exceeded errors."""

    error: str = Field(description="Error message")
    limit: int = Field(description="Rate limit threshold")
    retry_after: int = Field(description="Seconds until rate limit resets")
    window: str = Field(description="Current time window")


class RateLimitStatus(BaseModel):
    """Response model for rate limit status endpoint."""

    identifier: str = Field(description="User ID or IP address")
    identifier_type: str = Field(description="Type of identifier (user or ip)")
    limit: int = Field(description="Maximum requests allowed")
    remaining: int = Field(description="Requests remaining in current window")
    reset_at: datetime = Field(description="When the rate limit window resets")
    window: str = Field(description="Current time window identifier")
    current_count: int = Field(description="Current request count")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(description="Overall service status")
    redis: str = Field(description="Redis connection status")
    version: str = Field(description="API version")
    timestamp: datetime = Field(description="Current server time")
