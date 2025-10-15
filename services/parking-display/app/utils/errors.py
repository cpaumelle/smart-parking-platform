"""
Error Handling Module
=====================
Centralized error handling with:
- Standard error response formats
- Safe error messages (no sensitive data leakage)
- API key redaction in logs
- Specific exception types for different scenarios
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional, Dict, Any
import logging
import traceback
from datetime import datetime

logger = logging.getLogger("errors")


# ============================================================================
# Error Response Models
# ============================================================================

class ErrorResponse:
    """Standard error response format for all API errors"""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp
            }
        }


# ============================================================================
# Custom Exception Classes
# ============================================================================

class ParkingAPIError(Exception):
    """Base exception for all parking API errors"""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(ParkingAPIError):
    """Raised when a requested resource doesnt exist"""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id}
        )


class ResourceConflictError(ParkingAPIError):
    """Raised when a resource already exists or conflicts with existing data"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )


class ValidationError(ParkingAPIError):
    """Raised when input validation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class TenantIsolationViolationError(ParkingAPIError):
    """Raised when cross-tenant access is attempted"""

    def __init__(self, tenant_slug: str, resource_id: str):
        super().__init__(
            message="Resource not found",  # Deliberately vague for security
            error_code="RESOURCE_NOT_FOUND",  # Do not reveal its a permission issue
            status_code=status.HTTP_404_NOT_FOUND,
            details={}  # Do not leak tenant info
        )
        # Log the actual violation internally
        logger.warning(
            f"🚨 SECURITY: Tenant isolation violation detected - "
            f"tenant={tenant_slug} attempted access to resource={resource_id}"
        )


class DatabaseConnectionError(ParkingAPIError):
    """Raised when database connection fails"""

    def __init__(self):
        super().__init__(
            message="Service temporarily unavailable. Please try again later.",
            error_code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class RateLimitExceededError(ParkingAPIError):
    """Raised when rate limit is exceeded"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after}
        )


# ============================================================================
# Security Utilities
# ============================================================================

def redact_api_key(api_key: Optional[str]) -> str:
    """
    Redact API key for safe logging.

    Shows only the first 12 characters to help with debugging while
    preventing key leakage in logs.

    Examples:
        sp_live_kWnUJ0HMHEwM_06AK4Vi06WNYs2Cz-DdisHQNxYlxXg
        -> sp_live_kWn***REDACTED***

        invalid_key
        -> ***REDACTED***
    """
    if not api_key:
        return "***NO_KEY***"

    if api_key.startswith("sp_live_") and len(api_key) > 12:
        return f"{api_key[:12]}***REDACTED***"
    elif api_key.startswith("sp_test_") and len(api_key) > 12:
        return f"{api_key[:12]}***REDACTED***"
    else:
        return "***REDACTED***"


def sanitize_error_message(error: Exception, is_production: bool = True) -> str:
    """
    Sanitize error messages to prevent information leakage.

    In production: Return generic messages
    In development: Return actual error details for debugging
    """
    if not is_production:
        return str(error)

    # Map common database errors to safe messages
    error_str = str(error).lower()

    if "connection" in error_str or "pool" in error_str:
        return "Database connection error. Please try again later."

    if "timeout" in error_str:
        return "Request timed out. Please try again."

    if "foreign key" in error_str:
        return "Invalid reference. Related resource may not exist."

    if "unique constraint" in error_str or "duplicate key" in error_str:
        return "Resource already exists."

    if "not null constraint" in error_str:
        return "Required field missing."

    # Default generic message
    return "An error occurred while processing your request."


# ============================================================================
# Exception Handlers (FastAPI)
# ============================================================================

async def parking_api_error_handler(request: Request, exc: ParkingAPIError) -> JSONResponse:
    """Handle custom ParkingAPIError exceptions"""

    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code
    )

    # Log based on severity
    if exc.status_code >= 500:
        logger.error(
            f"API Error {exc.status_code}: {exc.error_code} - {exc.message}",
            extra={"details": exc.details}
        )
    else:
        logger.info(
            f"API Error {exc.status_code}: {exc.error_code} - {exc.message}"
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.to_dict(),
        headers=_get_error_headers(exc)
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors (422)"""

    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": errors},
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    logger.info(f"Validation error: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.to_dict()
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions (500)"""

    # Log full traceback for debugging
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        exc_info=True
    )

    # Return safe error message
    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
        details={},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.to_dict()
    )


def _get_error_headers(exc: ParkingAPIError) -> Dict[str, str]:
    """Get additional HTTP headers for specific error types"""
    headers = {}

    # Add Retry-After header for rate limits
    if isinstance(exc, RateLimitExceededError):
        retry_after = exc.details.get("retry_after", 60)
        headers["Retry-After"] = str(retry_after)

    return headers


# ============================================================================
# Logging Utilities
# ============================================================================

class SafeLogger:
    """
    Logger wrapper that automatically redacts sensitive information.

    Usage:
        safe_logger = SafeLogger(logger)
        safe_logger.info("Auth attempt", api_key=raw_api_key)
        # Logs: "Auth attempt api_key=sp_live_kWn***REDACTED***"
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _redact_kwargs(self, kwargs: dict) -> dict:
        """Redact sensitive fields in kwargs"""
        redacted = {}
        for key, value in kwargs.items():
            if key in ("api_key", "x_api_key", "authorization"):
                redacted[key] = redact_api_key(value)
            elif key in ("password", "secret", "token"):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted

    def info(self, message: str, **kwargs):
        redacted = self._redact_kwargs(kwargs)
        extra_info = " ".join(f"{k}={v}" for k, v in redacted.items())
        self.logger.info(f"{message} {extra_info}" if extra_info else message)


    def warning(self, message: str, **kwargs):
        redacted = self._redact_kwargs(kwargs)
        extra_info = " ".join(f"{k}={v}" for k, v in redacted.items())
        self.logger.warning(f"{message} {extra_info}" if extra_info else message)

    def error(self, message: str, **kwargs):
        redacted = self._redact_kwargs(kwargs)
        extra_info = " ".join(f"{k}={v}" for k, v in redacted.items())
        self.logger.error(f"{message} {extra_info}" if extra_info else message)
