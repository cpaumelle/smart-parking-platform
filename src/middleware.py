"""
Request tracing and context propagation middleware

Provides request ID tracking, timing, and context variables
that are accessible throughout the request lifecycle.
"""
import uuid
import time
from contextvars import ContextVar
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


# ============================================================================
# Context Variables (thread-safe request-scoped variables)
# ============================================================================

# Request ID - unique identifier for each request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Tenant ID - current tenant making the request
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")

# User ID - authenticated user (if applicable)
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


# ============================================================================
# Context Helper Functions
# ============================================================================

def get_request_id() -> str:
    """Get current request ID from context"""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context"""
    request_id_var.set(request_id)


def get_tenant_id() -> Optional[str]:
    """Get current tenant ID from context"""
    tenant_id = tenant_id_var.get()
    return tenant_id if tenant_id else None


def set_tenant_id(tenant_id: str) -> None:
    """Set tenant ID in context"""
    tenant_id_var.set(tenant_id)


def get_user_id() -> Optional[str]:
    """Get current user ID from context"""
    user_id = user_id_var.get()
    return user_id if user_id else None


def set_user_id(user_id: str) -> None:
    """Set user ID in context"""
    user_id_var.set(user_id)


# ============================================================================
# Request Tracing Middleware
# ============================================================================

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request tracing with context propagation

    Features:
    - Generates or extracts request ID
    - Tracks request timing
    - Adds response headers (X-Request-ID, X-Response-Time)
    - Binds context to structlog for automatic inclusion in logs
    - Stores request ID in context variable for access anywhere
    """

    async def dispatch(self, request: Request, call_next):
        """Process request with tracing"""

        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(request_id)

        # Extract tenant ID if available (will be set by auth middleware)
        # For now, just check if it's in the request state
        if hasattr(request.state, "tenant_id"):
            set_tenant_id(str(request.state.tenant_id))

        # Bind to structlog context (automatically included in all logs)
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path
        )

        start_time = time.time()

        # Log request start
        logger.info("request_started",
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "unknown"),
            query_params=dict(request.query_params) if request.query_params else None
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception with context
            duration_ms = (time.time() - start_time) * 1000
            logger.error("request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2)
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Add tracing headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Add tenant ID header if available
        tenant_id = get_tenant_id()
        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id

        # Log request completion
        logger.info("request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            tenant_id=tenant_id
        )

        # Clear context
        structlog.contextvars.unbind_contextvars("request_id", "method", "path")

        return response


# ============================================================================
# Tenant Context Middleware
# ============================================================================

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and store tenant context

    This should run after authentication middleware has identified the tenant.
    It propagates the tenant ID to context variables for easy access.
    """

    async def dispatch(self, request: Request, call_next):
        """Extract tenant context and propagate"""

        # Check if tenant_id was set by authentication
        if hasattr(request.state, "tenant_id"):
            tenant_id = str(request.state.tenant_id)
            set_tenant_id(tenant_id)

            # Also bind to structlog
            structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

        # Check if user_id was set by authentication
        if hasattr(request.state, "user_id"):
            user_id = str(request.state.user_id)
            set_user_id(user_id)

            # Also bind to structlog
            structlog.contextvars.bind_contextvars(user_id=user_id)

        response = await call_next(request)

        # Clear tenant context
        if hasattr(request.state, "tenant_id"):
            structlog.contextvars.unbind_contextvars("tenant_id")
        if hasattr(request.state, "user_id"):
            structlog.contextvars.unbind_contextvars("user_id")

        return response


# ============================================================================
# Response Headers Middleware
# ============================================================================

def add_security_headers(response: Response) -> Response:
    """Add security headers to response"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""

    async def dispatch(self, request: Request, call_next):
        """Add security headers"""
        response = await call_next(request)
        return add_security_headers(response)
