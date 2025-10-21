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
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

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
from .models import HealthStatus, ProcessingResult
from .exceptions import ParkingException

# Webhook processing imports
from .device_handlers import parse_chirpstack_webhook
from .webhook_validation import verify_webhook_signature
from .orphan_devices import handle_orphan_device
from .utils import generate_request_id
import json
import base64
from typing import Dict, Any

# Multi-tenancy imports
from .tenant_auth import set_db_pool as set_tenant_auth_db_pool, set_jwt_secret
from .auth import set_db_pool as set_auth_db_pool
from .rate_limit import RateLimiter, set_rate_limiter, RateLimitConfig

# Routers
from .api_tenants import router as tenants_router
from .routers.sites import router as sites_router
from .routers.spaces_tenanted import router as spaces_router  # Tenanted version
from .routers.downlink_monitor import router as downlink_monitor_router
from .routers.metrics import router as metrics_router
from .routers.display_policies import router as display_policies_router
from .routers.devices import router as devices_router
from .routers.reservations import router as reservations_router
from .routers.gateways import router as gateways_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Proxy Headers Middleware
# ============================================================

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle X-Forwarded-* headers from reverse proxy

    This fixes HTTPS redirect issues when behind a reverse proxy/load balancer.
    When the proxy terminates HTTPS, FastAPI receives HTTP requests but needs
    to know the original protocol was HTTPS to generate correct redirect URLs.
    """
    async def dispatch(self, request: Request, call_next):
        # Get forwarded protocol (https or http)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")

        if forwarded_proto:
            # Override the URL scheme in the request scope
            request.scope["scheme"] = forwarded_proto

        if forwarded_host:
            # Override the host
            request.scope["server"] = (forwarded_host, None)

        # Continue processing the request
        response = await call_next(request)

        return response

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
    set_auth_db_pool(db_pool.pool)  # CRITICAL: Initialize auth.py db_pool for API key verification
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
    lifespan=lifespan,
    root_path="",  # Required for proper URL generation behind proxy
    root_path_in_servers=False
)

# Proxy headers middleware (MUST be first to handle X-Forwarded-* headers)
app.add_middleware(ProxyHeadersMiddleware)

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
app.include_router(sites_router)  # Sites (buildings/locations)
app.include_router(spaces_router)  # Parking spaces
app.include_router(reservations_router)
app.include_router(devices_router)

# Display policy management (tenant-scoped)
app.include_router(display_policies_router)

# Downlink queue monitoring (requires admin auth)
app.include_router(downlink_monitor_router)

# Gateway monitoring (infrastructure-level, shared across tenants)
app.include_router(gateways_router)

# Observability endpoints
app.include_router(metrics_router)

# ============================================================
# ChirpStack Webhook Endpoint
# ============================================================

@app.post("/api/v1/uplink", response_model=ProcessingResult, tags=["ChirpStack"])
async def process_uplink(request: Request, webhook_data: Dict[str, Any]):
    """
    Process ChirpStack uplink webhook with signature validation and idempotency

    Security:
    - Validates webhook HMAC signature (per-tenant secrets)
    - Deduplicates uplinks via (tenant_id, device_eui, fcnt) unique constraint

    Handles sensor data, device discovery, and Kuando verification
    """
    start_time = datetime.utcnow()
    request_id = generate_request_id()

    try:
        # Extract device info
        device_info = webhook_data.get("deviceInfo", {})
        device_eui_raw = device_info.get("devEui", "")
        device_name = device_info.get("deviceName", "unknown")
        profile_name = device_info.get("deviceProfileName", "unknown")

        if not device_eui_raw:
            raise ValueError("Missing device EUI in uplink")

        # Normalize device_eui to UPPERCASE (database standard) - systematic fix for case sensitivity
        from .utils import normalize_deveui
        device_eui = normalize_deveui(device_eui_raw)

        logger.info(f"[{request_id}] Processing uplink from {device_eui} (profile: {profile_name})")

        db_pool = request.app.state.db_pool
        state_manager = request.app.state.state_manager
        device_registry = request.app.state.device_registry

        # Query device from database to get handler_class
        device_record = await db_pool.get_sensor_device_by_deveui(device_eui)

        # Check if device is assigned to a space (for tenant_id lookup)
        space = await db_pool.get_space_by_sensor(device_eui)
        tenant_id = space.tenant_id if space else None

        # Validate webhook signature (if tenant has a secret configured)
        # Note: We read raw body for HMAC validation
        body = await request.body()
        await verify_webhook_signature(request, tenant_id, db_pool.pool, body)

        if tenant_id:
            logger.debug(f"[{request_id}] Webhook signature validated for tenant {tenant_id}")

        # Get handler for device based on ChirpStack device profile
        handler = None
        if device_record and device_record.get('handler_class'):
            # Try database-stored handler class first
            handler = device_registry.get_handler_by_class(device_record['handler_class'])
            if handler:
                logger.debug(f"[{request_id}] Using handler from database: {device_record['handler_class']}")

        if not handler:
            # Fallback: Match handler by device profile from ChirpStack
            handler = device_registry.get_handler(profile_name)
            if handler:
                logger.debug(f"[{request_id}] Matched handler for device profile: {profile_name}")

        # Parse ChirpStack webhook data
        parsed_data = parse_chirpstack_webhook(webhook_data)

        # Decode payload using handler (if available)
        uplink = None
        if handler:
            try:
                uplink = handler.parse_uplink(webhook_data)
                logger.debug(f"[{request_id}] Parsed uplink: occupancy={uplink.occupancy_state}, battery={uplink.battery}")
            except Exception as e:
                logger.error(f"[{request_id}] Handler parsing failed: {e}")

        # ============================================================
        # Kuando Verification Logic
        # ============================================================
        is_kuando = device_eui.startswith("202020")

        if is_kuando and parsed_data.get("payload"):
            try:
                # Decode base64 payload
                payload_b64 = parsed_data["payload"]
                payload_bytes = base64.b64decode(payload_b64)

                logger.info(f"[{request_id}] Kuando uplink received, payload length: {len(payload_bytes)}")

                # Parse Kuando uplink format (based on firmware response)
                payload_object = {}
                if len(payload_bytes) >= 8:
                    # Kuando uplink includes status fields
                    payload_object = {
                        "downlinks_received": payload_bytes[0],
                        "red": payload_bytes[1],
                        "blue": payload_bytes[2],  # Note: Kuando swaps blue/green
                        "green": payload_bytes[3],
                        "options": payload_bytes[4],
                        "auto_uplink": payload_bytes[5] if len(payload_bytes) > 5 else 0,
                        "reserved": payload_bytes[6] if len(payload_bytes) > 6 else 0,
                        "raw_payload": payload_b64
                    }

                    logger.info(f"[{request_id}] Kuando decoded payload: {payload_object}")

                    # Store in Redis for verification
                    await state_manager.redis_client.setex(
                        f"device:{device_eui}:last_kuando_uplink",
                        3600,  # 1 hour TTL
                        json.dumps({
                            "timestamp": datetime.utcnow().isoformat(),
                            "downlinks_received": payload_object["downlinks_received"],
                            "rgb": [payload_object["red"], payload_object["blue"], payload_object["green"]],
                            "options": payload_object["options"],
                            "request_id": request_id
                        })
                    )

                    # Check for pending downlink verification
                    pending_key = f"device:{device_eui}:pending_downlink"
                    pending_data = await state_manager.redis_client.get(pending_key)

                    if pending_data:
                        expected = json.loads(pending_data)
                        expected_r, expected_b, expected_g = expected["rgb"]
                        expected_counter = expected["counter"]

                        actual_r = payload_object["red"]
                        actual_b = payload_object["blue"]
                        actual_g = payload_object["green"]
                        actual_counter = payload_object["downlinks_received"]

                        # Verify RGB values match and counter incremented
                        rgb_match = (actual_r == expected_r and
                                   actual_b == expected_b and
                                   actual_g == expected_g)
                        counter_incremented = actual_counter > expected_counter

                        logger.info(
                            f"[{request_id}] Downlink verification: "
                            f"RGB match={rgb_match} ({actual_r},{actual_b},{actual_g} vs {expected_r},{expected_b},{expected_g}), "
                            f"counter incremented={counter_incremented} ({actual_counter} > {expected_counter})"
                        )

                        if rgb_match and counter_incremented:
                            logger.info(f"[{request_id}] [OK] Kuando downlink verified successfully")
                            await state_manager.redis_client.delete(pending_key)
                        else:
                            logger.warning(f"[{request_id}] [FAIL] Kuando downlink verification failed")

            except Exception as e:
                logger.error(f"[{request_id}] Kuando verification error: {e}", exc_info=True)

        # ============================================================
        # Device Discovery (ORPHAN Pattern)
        # ============================================================

        # Get or create device type based on ChirpStack profile
        device_type = await db_pool.get_or_create_device_type_by_profile(
            chirpstack_profile_name=profile_name,
            sample_payload=parsed_data,
            category="sensor"
        )

        # Get or create sensor device
        sensor_device = await db_pool.get_or_create_sensor_device(
            dev_eui=device_eui,
            device_type_id=device_type["id"],
            device_name=device_name,
            device_model=device_type["type_code"]
        )

        # Check if device is assigned to a space (already queried earlier for tenant_id)
        if not space:
            # ORPHAN device - track in orphan_devices table
            logger.info(f"[{request_id}] ORPHAN device {device_eui} - tracking uplink")

            # Track orphan device
            orphan_info = await handle_orphan_device(
                db=db_pool.pool,
                device_eui=device_eui,
                payload=parsed_data.get("payload", "").encode() if parsed_data.get("payload") else None,
                rssi=parsed_data.get("rssi"),
                snr=parsed_data.get("snr")
            )

            # Store telemetry for orphan device
            if uplink:
                await db_pool.insert_telemetry(device_eui, uplink)

            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ProcessingResult(
                status="orphan_device",
                device_eui=device_eui,
                space_code=None,
                state=None,
                request_id=request_id,
                processing_time_ms=processing_time_ms
            )

        # ============================================================
        # Process Sensor Data and Update State
        # ============================================================

        if uplink and uplink.occupancy_state:
            # Update space state based on sensor reading
            result = await state_manager.update_space_state(
                space_id=str(space.id),
                new_state=uplink.occupancy_state,
                source="sensor_uplink",
                request_id=request_id
            )

            # Store sensor reading (with fcnt for idempotency)
            await db_pool.insert_sensor_reading(
                device_eui=device_eui,
                space_id=str(space.id),
                occupancy_state=uplink.occupancy_state.value,
                battery=uplink.battery,
                rssi=uplink.rssi,
                snr=uplink.snr,
                timestamp=uplink.timestamp,
                fcnt=parsed_data.get("fcnt"),
                tenant_id=str(space.tenant_id) if space.tenant_id else None
            )

            logger.info(
                f"[{request_id}] Space {space.code} updated: "
                f"{result.previous_state} -> {result.new_state}, "
                f"display_updated={result.display_updated}"
            )

            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ProcessingResult(
                status="success",
                device_eui=device_eui,
                space_code=space.code,
                state=result.new_state.value,
                request_id=request_id,
                processing_time_ms=processing_time_ms
            )
        else:
            # No occupancy data (display device or unknown)
            logger.debug(f"[{request_id}] No occupancy data in uplink from {device_eui}")

            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ProcessingResult(
                status="no_occupancy_data",
                device_eui=device_eui,
                space_code=space.code if space else None,
                state=None,
                request_id=request_id,
                processing_time_ms=processing_time_ms
            )

    except Exception as e:
        logger.error(f"[{request_id}] Webhook processing error: {e}", exc_info=True)
        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ProcessingResult(
            status="error",
            device_eui=device_eui if 'device_eui' in locals() else "unknown",
            space_code=None,
            state=None,
            request_id=request_id,
            processing_time_ms=processing_time_ms
        )

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
