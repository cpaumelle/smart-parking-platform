"""
Prometheus Metrics Module
==========================
Exposes application metrics in Prometheus format for monitoring and alerting.

Metrics Exposed:
- API request counts (by tenant, endpoint, status code)
- API request duration  
- Authentication attempts (success/failure)
- RLS context errors
- Background task duration
- Database connection pool usage
- Tenant-specific metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from functools import wraps
import time
from typing import Optional
import logging

logger = logging.getLogger("metrics")

# ============================================================================
# Prometheus Metrics Definitions
# ============================================================================

# API Request Metrics
api_requests_total = Counter(
    "parking_api_requests_total",
    "Total number of API requests",
    ["tenant", "endpoint", "method", "status_code"]
)

api_request_duration_seconds = Histogram(
    "parking_api_request_duration_seconds",
    "API request duration in seconds",
    ["tenant", "endpoint", "method"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Authentication Metrics
auth_attempts_total = Counter(
    "parking_auth_attempts_total",
    "Total authentication attempts",
    ["tenant", "result"]  # result: success, invalid_key, expired, inactive
)

auth_failures_total = Counter(
    "parking_auth_failures_total",
    "Total authentication failures",
    ["reason"]  # missing, invalid, revoked, expired, inactive_tenant
)

# RLS & Multi-Tenancy Metrics
rls_context_errors_total = Counter(
    "parking_rls_context_errors_total",
    "RLS context setting errors",
    ["tenant"]
)

tenant_isolation_violations_total = Counter(
    "parking_tenant_isolation_violations_total",
    "Cross-tenant access attempts",
    ["tenant", "resource_type"]
)

# Background Task Metrics
background_task_duration_seconds = Histogram(
    "parking_background_task_duration_seconds",
    "Background task execution duration",
    ["task_name", "tenant"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0)
)

background_task_errors_total = Counter(
    "parking_background_task_errors_total",
    "Background task errors",
    ["task_name", "tenant"]
)

# Database Metrics
db_connections_active = Gauge(
    "parking_db_connections_active",
    "Active database connections",
    ["pool"]  # system, tenant
)

db_query_duration_seconds = Histogram(
    "parking_db_query_duration_seconds",
    "Database query duration",
    ["query_type", "tenant"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0)
)

# Parking Operations Metrics
spaces_total = Gauge(
    "parking_spaces_total",
    "Total number of parking spaces",
    ["tenant", "state"]  # FREE, OCCUPIED, RESERVED
)

reservations_active = Gauge(
    "parking_reservations_active",
    "Active reservations",
    ["tenant"]
)

actuations_total = Counter(
    "parking_actuations_total",
    "Total display actuations sent",
    ["tenant", "display_state", "result"]  # result: success, failed
)

# System Info
app_info = Info(
    "parking_app",
    "Application information"
)

# Set app info
app_info.info({
    "version": "1.5.1",
    "multi_tenancy": "enabled",
    "rls": "postgresql"
})


# ============================================================================
# Metric Helper Functions
# ============================================================================

def record_api_request(
    tenant: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration: float
):
    """Record an API request with all relevant metrics"""
    api_requests_total.labels(
        tenant=tenant,
        endpoint=endpoint,
        method=method,
        status_code=status_code
    ).inc()
    
    api_request_duration_seconds.labels(
        tenant=tenant,
        endpoint=endpoint,
        method=method
    ).observe(duration)


def record_auth_attempt(tenant: Optional[str], success: bool, reason: Optional[str] = None):
    """Record an authentication attempt"""
    if success:
        auth_attempts_total.labels(
            tenant=tenant or "unknown",
            result="success"
        ).inc()
    else:
        auth_attempts_total.labels(
            tenant=tenant or "unknown",
            result="failure"
        ).inc()
        
        if reason:
            auth_failures_total.labels(reason=reason).inc()


def record_rls_context_error(tenant: str):
    """Record an RLS context setting error"""
    rls_context_errors_total.labels(tenant=tenant).inc()
    logger.error(f"RLS context error for tenant {tenant}")


def record_tenant_isolation_violation(tenant: str, resource_type: str, resource_id: str):
    """Record a cross-tenant access attempt"""
    tenant_isolation_violations_total.labels(
        tenant=tenant,
        resource_type=resource_type
    ).inc()
    
    logger.warning(
        f"🚨 SECURITY: Tenant isolation violation - "
        f"tenant={tenant} resource_type={resource_type} resource_id={resource_id}"
    )


def record_background_task(task_name: str, tenant: str, duration: float, success: bool):
    """Record background task execution"""
    background_task_duration_seconds.labels(
        task_name=task_name,
        tenant=tenant
    ).observe(duration)
    
    if not success:
        background_task_errors_total.labels(
            task_name=task_name,
            tenant=tenant
        ).inc()


def update_space_metrics(tenant: str, free_count: int, occupied_count: int, reserved_count: int):
    """Update parking space state metrics"""
    spaces_total.labels(tenant=tenant, state="FREE").set(free_count)
    spaces_total.labels(tenant=tenant, state="OCCUPIED").set(occupied_count)
    spaces_total.labels(tenant=tenant, state="RESERVED").set(reserved_count)


def update_reservation_metrics(tenant: str, active_count: int):
    """Update active reservations metric"""
    reservations_active.labels(tenant=tenant).set(active_count)


def record_actuation(tenant: str, display_state: str, success: bool):
    """Record a display actuation"""
    result = "success" if success else "failed"
    actuations_total.labels(
        tenant=tenant,
        display_state=display_state,
        result=result
    ).inc()


def update_db_connection_metrics(pool_name: str, active_connections: int):
    """Update database connection pool metrics"""
    db_connections_active.labels(pool=pool_name).set(active_connections)


# ============================================================================
# Metrics Endpoint
# ============================================================================

async def get_metrics():
    """Return Prometheus metrics in text format"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# ============================================================================
# Decorators for Automatic Metrics Collection
# ============================================================================

def track_request_metrics(endpoint: str):
    """Decorator to automatically track API request metrics"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            tenant = "unknown"
            status_code = 200
            
            try:
                # Try to extract tenant from kwargs (auth dependency)
                auth = kwargs.get("auth")
                if auth and hasattr(auth, "tenant_slug"):
                    tenant = auth.tenant_slug
                
                # Execute the endpoint
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Extract status code from HTTPException if available
                if hasattr(e, "status_code"):
                    status_code = e.status_code
                else:
                    status_code = 500
                raise
                
            finally:
                # Record metrics
                duration = time.time() - start_time
                method = kwargs.get("request", {}).method if "request" in kwargs else "GET"
                
                record_api_request(
                    tenant=tenant,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    duration=duration
                )
        
        return wrapper
    return decorator
