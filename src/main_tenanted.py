"""
Smart Parking Platform v5.3 - Main Application with Multi-Tenancy
FastAPI application with ChirpStack integration, state management, and RBAC
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Local imports
from .config import settings
from .database import DatabasePool
from .state_manager import StateManager
from .chirpstack_client import ChirpStackClient
from .gateway_monitor import GatewayMonitor
from .device_handlers import DeviceHandlerRegistry
from .background_tasks import BackgroundTaskManager
from .downlink_queue import DownlinkQueue, DownlinkRateLimiter, DownlinkWorker
from .webhook_spool import WebhookSpool, set_spool
from .models import HealthStatus
from .exceptions import ParkingException

# Multi-tenancy imports
from .tenant_auth import set_db_pool as set_tenant_auth_db_pool, set_jwt_secret
from .rate_limit import RateLimiter, set_rate_limiter, RateLimitConfig

# Routers
from .api_tenants import router as tenants_router
from .routers.spaces_tenanted import router as spaces_router  # Tenanted version
from .routers.downlink_monitor import router as downlink_monitor_router
from .routers.metrics import router as metrics_router
# from .routers.devices import router as devices_router  # TODO: Add tenant scoping
# from .routers.reservations import router as reservations_router  # TODO: Add tenant scoping
# from .routers.gateways import router as gateways_router  # Can remain public or add tenant scoping

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Application Lifecycle Management
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle (startup/shutdown)
    Initializes all required services and cleans up on shutdown
    """
    logger.info(f">> Starting {settings.app_name} v{settings.app_version}")

    # Validate JWT secret
    jwt_secret = os.getenv("JWT_SECRET_KEY", settings.secret_key)
    if not jwt_secret or len(jwt_secret) < 32:
        logger.error("JWT_SECRET_KEY is missing or too short (minimum 32 characters)")
        raise ValueError("JWT_SECRET_KEY must be at least 32 characters")

    # Initialize database pool
    db_pool = DatabasePool()
    await db_pool.initialize()
    app.state.db_pool = db_pool
    logger.info("[OK] Database pool initialized")

    # Initialize multi-tenancy auth
    set_tenant_auth_db_pool(db_pool.pool)
    set_jwt_secret(jwt_secret)
    logger.info("[OK] Multi-tenancy authentication initialized")

    # Initialize rate limiter (for API requests)
    rate_limiter = RateLimiter(settings.redis_url)
    await rate_limiter.initialize()
    set_rate_limiter(rate_limiter)
    app.state.rate_limiter = rate_limiter
    logger.info("[OK] Rate limiter initialized")

    # Initialize webhook spool for back-pressure handling
    webhook_spool = WebhookSpool()
    await webhook_spool.start_worker()
    set_spool(webhook_spool)
    app.state.webhook_spool = webhook_spool
    logger.info("[OK] Webhook spool initialized")

    # Initialize downlink queue and worker (for Class-C displays)
    downlink_queue = DownlinkQueue(rate_limiter.redis_client)
    downlink_rate_limiter = DownlinkRateLimiter(rate_limiter.redis_client)
    app.state.downlink_queue = downlink_queue
    app.state.downlink_rate_limiter = downlink_rate_limiter
    logger.info("[OK] Downlink queue initialized")

    # Initialize Redis and state manager (with downlink queue)
    state_manager = StateManager(
        db_pool=db_pool,
        redis_url=settings.redis_url,
        downlink_queue=downlink_queue  # Enable durable downlink queue
    )
    await state_manager.initialize()
    app.state.state_manager = state_manager
    logger.info("[OK] State manager initialized with durable downlink queue")

    # Initialize ChirpStack client
    chirpstack_client = ChirpStackClient(
        host=settings.chirpstack_host,
        port=settings.chirpstack_port,
        api_key=settings.chirpstack_api_key
    )
    await chirpstack_client.connect()
    app.state.chirpstack_client = chirpstack_client

    # Link ChirpStack client to state manager for downlinks
    state_manager.chirpstack_client = chirpstack_client
    logger.info("[OK] ChirpStack client initialized")

    # Initialize gateway monitor
    chirpstack_dsn = chirpstack_client.chirpstack_dsn
    gateway_monitor = GatewayMonitor(chirpstack_dsn)
    await gateway_monitor.connect()
    app.state.gateway_monitor = gateway_monitor
    logger.info("[OK] Gateway monitor initialized")

    # Initialize device handler registry
    device_registry = DeviceHandlerRegistry()
    device_registry.auto_register()
    app.state.device_registry = device_registry
    logger.info(f"[OK] Device registry initialized with handlers: {device_registry.list_handlers()}")

    # Initialize downlink worker (processes queue in background)
    downlink_worker = DownlinkWorker(
        queue=downlink_queue,
        rate_limiter=downlink_rate_limiter,
        chirpstack_client=chirpstack_client,
        worker_id="worker-1"
    )
    await downlink_worker.start()
    app.state.downlink_worker = downlink_worker
    logger.info("[OK] Downlink worker started")

    # Initialize background tasks
    task_manager = BackgroundTaskManager(
        db_pool=db_pool,
        state_manager=state_manager,
        chirpstack_client=chirpstack_client,
        gateway_monitor=gateway_monitor
    )
    await task_manager.start()
    app.state.task_manager = task_manager
    logger.info("[OK] Background task manager started")

    logger.info(f">> {settings.app_name} v{settings.app_version} is ready with multi-tenancy and durable downlink queue!")

    yield

    # Shutdown: cleanup resources
    logger.info(">> Shutting down application...")

    if hasattr(app.state, 'task_manager'):
        await app.state.task_manager.stop()
        logger.info("[OK] Background tasks stopped")

    if hasattr(app.state, 'downlink_worker'):
        await app.state.downlink_worker.stop()
        logger.info("[OK] Downlink worker stopped")

    if hasattr(app.state, 'webhook_spool'):
        await app.state.webhook_spool.stop_worker()
        logger.info("[OK] Webhook spool worker stopped")

    if hasattr(app.state, 'gateway_monitor'):
        await app.state.gateway_monitor.disconnect()
        logger.info("[OK] Gateway monitor closed")

    if hasattr(app.state, 'chirpstack_client'):
        await app.state.chirpstack_client.disconnect()
        logger.info("[OK] ChirpStack client closed")

    if hasattr(app.state, 'state_manager'):
        await app.state.state_manager.close()
        logger.info("[OK] State manager closed")

    if hasattr(app.state, 'rate_limiter'):
        await app.state.rate_limiter.close()
        logger.info("[OK] Rate limiter closed")

    if hasattr(app.state, 'db_pool'):
        await app.state.db_pool.close()
        logger.info("[OK] Database pool closed")

    logger.info(">> Shutdown complete")

# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title=f"{settings.app_name} (Multi-Tenant)",
    version=settings.app_version,
    description="Smart Parking Platform with ChirpStack integration and multi-tenancy",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# API Routers
# ============================================================

# Multi-tenancy & authentication endpoints
app.include_router(tenants_router)

# Tenant-scoped resource endpoints
app.include_router(spaces_router)

# Downlink queue monitoring (requires admin auth)
app.include_router(downlink_monitor_router)

# Observability endpoints
app.include_router(metrics_router)

# TODO: Add tenant scoping to these routers
# app.include_router(devices_router)
# app.include_router(reservations_router)
# app.include_router(gateways_router)

# ============================================================
# Exception Handlers
# ============================================================

@app.exception_handler(ParkingException)
async def parking_exception_handler(request: Request, exc: ParkingException):
    """Handle custom parking exceptions"""
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
    )

# ============================================================
# Health Checks
# ============================================================

@app.get("/health", response_model=HealthStatus, tags=["System"])
async def health_check(request: Request):
    """
    Comprehensive health check endpoint
    Returns system status and component health
    """
    checks = {}
    stats = {}
    overall_status = "healthy"

    # Database check
    try:
        db_pool = request.app.state.db_pool
        stats["database"] = db_pool.get_stats()
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"
        overall_status = "degraded"

    # Redis check
    try:
        state_manager = request.app.state.state_manager
        await state_manager.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"
        overall_status = "degraded"

    # ChirpStack check
    try:
        chirpstack_client = request.app.state.chirpstack_client
        cs_health = await chirpstack_client.health_check()
        checks["chirpstack"] = cs_health["status"]
        stats["chirpstack"] = cs_health
    except Exception as e:
        checks["chirpstack"] = f"unhealthy: {e}"
        overall_status = "degraded"

    # Rate limiter check
    try:
        rate_limiter = request.app.state.rate_limiter
        if rate_limiter and rate_limiter.redis_client:
            checks["rate_limiter"] = "healthy"
        else:
            checks["rate_limiter"] = "not initialized"
            overall_status = "degraded"
    except Exception as e:
        checks["rate_limiter"] = f"unhealthy: {e}"
        overall_status = "degraded"

    return HealthStatus(
        status=overall_status,
        version=settings.app_version,
        timestamp=datetime.utcnow(),
        checks=checks,
        stats=stats
    )

@app.get("/health/ready", tags=["System"])
async def readiness_check(request: Request):
    """
    Kubernetes readiness probe - checks if app can serve traffic

    Returns 200 if all critical dependencies are available:
    - Database connectivity
    - Redis connectivity
    - ChirpStack MQTT connection

    Returns 503 if any dependency is unavailable
    """
    checks = {}
    all_ready = True

    # Check database
    try:
        db_pool = request.app.state.db_pool
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ready"
    except Exception as e:
        checks["database"] = f"not ready: {str(e)[:100]}"
        all_ready = False

    # Check Redis
    try:
        state_manager = request.app.state.state_manager
        await state_manager.ping()
        checks["redis"] = "ready"
    except Exception as e:
        checks["redis"] = f"not ready: {str(e)[:100]}"
        all_ready = False

    # Check ChirpStack connection
    try:
        chirpstack_client = request.app.state.chirpstack_client
        if chirpstack_client and chirpstack_client.mqtt_client and chirpstack_client.mqtt_client.is_connected():
            checks["chirpstack_mqtt"] = "ready"
        else:
            checks["chirpstack_mqtt"] = "not connected"
            all_ready = False
    except Exception as e:
        checks["chirpstack_mqtt"] = f"not ready: {str(e)[:100]}"
        all_ready = False

    # Check downlink worker
    try:
        downlink_worker = request.app.state.downlink_worker
        if downlink_worker and downlink_worker.running:
            checks["downlink_worker"] = "ready"
        else:
            checks["downlink_worker"] = "not running"
            # Don't fail readiness for worker - degraded mode OK
    except Exception as e:
        checks["downlink_worker"] = f"error: {str(e)[:100]}"

    if all_ready:
        return {"status": "ready", "checks": checks}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": checks}
        )


@app.get("/health/live", tags=["System"])
async def liveness_check(request: Request):
    """
    Kubernetes liveness probe - checks if app is alive

    Returns 200 if:
    - Process is running
    - Background workers are alive (not deadlocked)

    Returns 503 if process is deadlocked or unhealthy
    """
    checks = {}
    is_alive = True

    # Check task manager is running
    try:
        task_manager = request.app.state.task_manager
        if task_manager and task_manager.running:
            checks["task_manager"] = "alive"
        else:
            checks["task_manager"] = "stopped"
            is_alive = False
    except Exception as e:
        checks["task_manager"] = f"error: {str(e)[:100]}"
        is_alive = False

    # Check downlink worker heartbeat
    try:
        downlink_worker = request.app.state.downlink_worker
        if downlink_worker:
            checks["downlink_worker"] = "alive" if downlink_worker.running else "stopped"
        else:
            checks["downlink_worker"] = "not initialized"
    except Exception as e:
        checks["downlink_worker"] = f"error: {str(e)[:100]}"

    # Check webhook spool worker
    try:
        webhook_spool = request.app.state.webhook_spool
        if webhook_spool:
            checks["webhook_spool"] = "alive" if webhook_spool.running else "stopped"
        else:
            checks["webhook_spool"] = "not initialized"
    except Exception as e:
        checks["webhook_spool"] = f"error: {str(e)[:100]}"

    if is_alive:
        return {"status": "live", "checks": checks}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "dead", "checks": checks}
        )

# ============================================================
# Request ID Middleware (for logging)
# ============================================================

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request for tracing"""
    from .utils import generate_request_id
    request_id = generate_request_id()
    request.state.request_id = request_id

    # Add to logging context
    import logging
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record

    logging.setLogRecordFactory(record_factory)

    response = await call_next(request)

    # Reset factory
    logging.setLogRecordFactory(old_factory)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    return response

# ============================================================
# Row-Level Security (RLS) Middleware
# ============================================================

@app.middleware("http")
async def set_tenant_context_for_rls(request: Request, call_next):
    """
    Set tenant context for Row-Level Security on every request

    This middleware extracts the tenant_id from:
    1. JWT token (for user authentication)
    2. API key (for service-to-service auth)

    And stores it in request.state.tenant_id for use by database operations.

    Note: The actual RLS setting (app.current_tenant) is done by the
    DatabasePool.acquire() method when tenant_id is passed to it.
    """
    # Extract tenant_id from authentication
    tenant_id = None

    try:
        # Try JWT authentication first (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            from .tenant_auth import decode_access_token
            token_data = decode_access_token(token)
            if token_data:
                tenant_id = token_data.tenant_id

        # Try API key authentication if JWT not present
        if not tenant_id:
            api_key = request.headers.get("X-API-Key")
            if api_key:
                from .auth import verify_api_key
                api_key_info = await verify_api_key(api_key)
                if api_key_info:
                    from .tenant_auth import resolve_tenant_from_api_key
                    tenant_context = await resolve_tenant_from_api_key(api_key_info)
                    if tenant_context:
                        tenant_id = tenant_context.tenant_id

        # Store tenant_id in request state for database operations
        request.state.tenant_id = tenant_id

        # Log tenant context (for debugging)
        if tenant_id:
            logger.debug(f"RLS tenant context set: {tenant_id}")

    except Exception as e:
        logger.warning(f"Error setting tenant context for RLS: {e}")
        request.state.tenant_id = None

    response = await call_next(request)
    return response
