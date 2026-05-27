"""
Structured error response models for API consistency.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for API responses."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_TIMEFRAME = "INVALID_TIMEFRAME"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    """Detail of a single error."""
    code: ErrorCode
    message: str
    field: Optional[str] = None  # Field name if validation error
    context: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard API error response."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: int = Field(description="HTTP status code")
    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: Optional[str] = None  # For request tracing

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-05-09T12:00:00Z",
                "status": 400,
                "error": "Validation Error",
                "message": "Invalid symbol format",
                "details": [
                    {
                        "code": "INVALID_SYMBOL",
                        "message": "Symbol must be uppercase alphanumeric",
                        "field": "symbol",
                    }
                ],
                "request_id": "req_123abc",
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response wrapper (optional, for consistency)."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: int = 200
    data: Dict[str, Any]
    request_id: Optional[str] = None


def create_error_response(
    status: int,
    error: str,
    message: str,
    details: Optional[list[ErrorDetail]] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """
    Helper function to create structured error response.

    Args:
        status: HTTP status code
        error: Error type
        message: Human-readable message
        details: List of error details
        request_id: Request ID for tracing

    Returns:
        ErrorResponse object
    """
    return ErrorResponse(
        status=status,
        error=error,
        message=message,
        details=details or [],
        request_id=request_id,
    )


def validation_error_response(
    message: str,
    field: Optional[str] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a validation error response."""
    return create_error_response(
        status=400,
        error="Validation Error",
        message=message,
        details=[ErrorDetail(code=ErrorCode.VALIDATION_ERROR, message=message, field=field)],
        request_id=request_id,
    )


def not_found_response(
    message: str,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a not found error response."""
    return create_error_response(
        status=404,
        error="Not Found",
        message=message,
        details=[ErrorDetail(code=ErrorCode.NOT_FOUND, message=message)],
        request_id=request_id,
    )


def rate_limit_response(
    message: str = "Rate limit exceeded",
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a rate limit error response."""
    return create_error_response(
        status=429,
        error="Rate Limited",
        message=message,
        details=[ErrorDetail(code=ErrorCode.RATE_LIMITED, message=message)],
        request_id=request_id,
    )


def service_unavailable_response(
    message: str = "Service temporarily unavailable",
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a service unavailable error response."""
    return create_error_response(
        status=503,
        error="Service Unavailable",
        message=message,
        details=[ErrorDetail(code=ErrorCode.SERVICE_UNAVAILABLE, message=message)],
        request_id=request_id,
    )


def circuit_breaker_response(
    service_name: str = "external service",
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Create a circuit breaker open error response."""
    message = f"{service_name} is currently unavailable (circuit breaker open)"
    return create_error_response(
        status=503,
        error="Service Unavailable",
        message=message,
        details=[ErrorDetail(
            code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            message=message,
            context={"service": service_name},
        )],
        request_id=request_id,
    )
