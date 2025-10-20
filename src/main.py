"""
Smart Parking Platform v5 - Main Application
FastAPI application with ChirpStack integration, state management, and Kuando verification
"""
import asyncio
import logging
import json
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Local imports
from .config import settings
from .database import DatabasePool
from .state_manager import StateManager
from .chirpstack_client import ChirpStackClient
from .gateway_monitor import GatewayMonitor
from .device_handlers import DeviceHandlerRegistry, parse_chirpstack_webhook
from .background_tasks import BackgroundTaskManager
from .models import (
    SpaceState, SpaceCreate, SpaceUpdate, Space, SpaceFilters,
    ReservationCreate, Reservation, ReservationFilters,
    DownlinkRequest, HealthStatus, ProcessingResult, ApiResponse,
    SensorUplink
)
from .exceptions import (
    ParkingException, SpaceNotFoundError, ReservationNotFoundError,
    StateTransitionError, ChirpStackError, DatabaseError, DuplicateResourceError
)
from .utils import generate_request_id, normalize_deveui, utcnow
from .routers import spaces_router, devices_router, reservations_router, gateways_router
from .webhook_validation import verify_webhook_signature
from .orphan_devices import handle_orphan_device
from .webhook_spool import spool_webhook_on_error

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

    # Initialize database pool
    db_pool = DatabasePool()
    await db_pool.initialize()
    app.state.db_pool = db_pool
    logger.info("[OK] Database pool initialized")

    # Initialize Redis and state manager
    state_manager = StateManager(
        db_pool=db_pool,
        redis_url=settings.redis_url
    )
    await state_manager.initialize()
    app.state.state_manager = state_manager
    logger.info("[OK] State manager initialized")

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

    logger.info(f">> {settings.app_name} is ready!")

    yield

    # Shutdown: cleanup resources
    logger.info(">> Shutting down application...")

    if hasattr(app.state, 'task_manager'):
        await app.state.task_manager.stop()
        logger.info("[OK] Background tasks stopped")

    if hasattr(app.state, 'gateway_monitor'):
        await app.state.gateway_monitor.disconnect()
        logger.info("[OK] Gateway monitor closed")

    if hasattr(app.state, 'chirpstack_client'):
        await app.state.chirpstack_client.disconnect()
        logger.info("[OK] ChirpStack client closed")

    if hasattr(app.state, 'state_manager'):
        await app.state.state_manager.close()
        logger.info("[OK] State manager closed")

    if hasattr(app.state, 'db_pool'):
        await app.state.db_pool.close()
        logger.info("[OK] Database pool closed")

    logger.info(">> Shutdown complete")

# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Smart Parking Platform with ChirpStack integration",
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

# Include spaces router (comprehensive CRUD from V4)
app.include_router(spaces_router)

# Include devices router (sensor and display device management)
app.include_router(devices_router)

# Include reservations router (parking space reservations)
app.include_router(reservations_router)

# Include gateways router (ChirpStack gateway information)
app.include_router(gateways_router)

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
# Health Check
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

    # Gateway monitor check
    try:
        gateway_monitor = request.app.state.gateway_monitor
        gw_health = await gateway_monitor.get_health_summary()
        checks["gateways"] = gw_health["health_status"]
        stats["gateways"] = gw_health
    except Exception as e:
        checks["gateways"] = f"unhealthy: {e}"
        overall_status = "degraded"

    # Background tasks check
    try:
        task_manager = request.app.state.task_manager
        checks["background_tasks"] = "running" if task_manager.running else "stopped"
        stats["scheduled_tasks"] = len(task_manager.scheduled_tasks)
    except Exception as e:
        checks["background_tasks"] = f"error: {e}"
        overall_status = "degraded"

    return HealthStatus(
        status=overall_status,
        version=settings.app_version,
        timestamp=utcnow(),
        checks=checks,
        stats=stats
    )

# ============================================================
# ChirpStack Webhook Endpoints
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
        device_eui = device_info.get("devEui", "").lower()
        device_name = device_info.get("deviceName", "unknown")
        profile_name = device_info.get("deviceProfileName", "unknown")

        if not device_eui:
            raise ValueError("Missing device EUI in uplink")

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

        # Get handler for device (try database first, fallback to EUI matching)
        handler = None
        if device_record and device_record.get('handler_class'):
            handler = device_registry.get_handler_by_class(device_record['handler_class'])
            if handler:
                logger.debug(f"[{request_id}] Using handler from database: {device_record['handler_class']}")

        if not handler:
            handler = device_registry.get_handler(device_eui)

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

    except DatabaseError as e:
        # Database error - try to spool webhook for later retry
        logger.error(f"[{request_id}] Database error during uplink processing: {e}")

        spooled = await spool_webhook_on_error(
            webhook_data=webhook_data,
            device_eui=device_eui,
            request_id=request_id,
            error=e
        )

        if spooled:
            # Return 202 Accepted - webhook is spooled and will be processed later
            return ProcessingResult(
                status="spooled",
                device_eui=device_eui,
                space_code=None,
                state=None,
                request_id=request_id,
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )
        else:
            # Spooling failed - return error
            raise HTTPException(
                status_code=503,
                detail="Database unavailable and spool failed - webhook lost"
            )

    except Exception as e:
        logger.error(f"[{request_id}] Uplink processing failed: {e}", exc_info=True)

        # Try to spool for non-critical errors (but don't fail if spooling fails)
        try:
            await spool_webhook_on_error(
                webhook_data=webhook_data,
                device_eui=device_eui if 'device_eui' in locals() else "unknown",
                request_id=request_id,
                error=e
            )
        except:
            pass  # Best effort

        raise HTTPException(
            status_code=500,
            detail=f"Uplink processing failed: {str(e)}"
        )

async def verify_downlink_transmission(
    device_eui: str,
    queue_id: str,
    chirpstack_client,
    timeout: int = 15
):
    """
    Background task: Monitor downlink queue to detect stuck downlinks
    Waits for specified timeout, then checks if downlink is still pending
    """
    try:
        await asyncio.sleep(timeout)

        # Check device queue
        queue = await chirpstack_client.get_device_queue(device_eui)

        # Check if our queue_id is still pending
        pending = [item for item in queue if item.get('id') == queue_id and item.get('is_pending', False)]

        if pending:
            logger.error(
                f"⚠️  Downlink STUCK for {device_eui} after {timeout}s - "
                f"queue_id {queue_id} still pending. Gateway may be offline or device not transmitting."
            )
            return {"status": "stuck", "queue_id": queue_id}
        else:
            logger.info(
                f"✅ Downlink transmitted for {device_eui} - queue_id {queue_id} cleared from queue"
            )
            return {"status": "transmitted", "queue_id": queue_id}

    except Exception as e:
        logger.error(f"Queue monitoring error for {device_eui}: {e}", exc_info=True)
        return {"status": "error", "queue_id": queue_id, "error": str(e)}

@app.post("/api/v1/downlink/{dev_eui}", response_model=ApiResponse, tags=["ChirpStack"])
async def send_downlink(
    request: Request,
    dev_eui: str,
    downlink: DownlinkRequest
):
    """
    Send downlink to device via ChirpStack
    Supports both raw payload and high-level commands
    Includes automatic queue monitoring to detect stuck downlinks
    """
    request_id = generate_request_id()

    try:
        device_eui = normalize_deveui(dev_eui)
        logger.info(f"[{request_id}] Sending downlink to {device_eui}")

        chirpstack_client = request.app.state.chirpstack_client
        device_registry = request.app.state.device_registry
        state_manager = request.app.state.state_manager
        gateway_monitor = request.app.state.gateway_monitor

        # ============================================================
        # Pre-flight Gateway Health Check
        # ============================================================
        gw_health = await gateway_monitor.get_health_summary()

        if gw_health['online_count'] == 0:
            logger.error(f"[{request_id}] No online gateways available - aborting downlink to {device_eui}")
            raise HTTPException(
                status_code=503,
                detail="No online gateways available. Cannot send downlink."
            )

        if gw_health['online_count'] < 2:
            logger.warning(
                f"[{request_id}] Limited gateway redundancy: only {gw_health['online_count']} gateway online. "
                f"Downlink reliability may be reduced."
            )
        else:
            logger.info(
                f"[{request_id}] Gateway health check passed: {gw_health['online_count']} gateways online"
            )

        # Get handler for device
        handler = device_registry.get_handler(device_eui)

        # Encode payload
        payload_bytes = None

        if downlink.command and handler:
            # High-level command
            payload_bytes = handler.encode_downlink(
                downlink.command,
                downlink.parameters or {}
            )
            logger.info(f"[{request_id}] Encoded command '{downlink.command}': {payload_bytes.hex()}")
        elif downlink.payload:
            # Raw payload (hex or base64)
            if isinstance(downlink.payload, str):
                # Try hex first
                try:
                    payload_bytes = bytes.fromhex(downlink.payload)
                except ValueError:
                    # Try base64
                    payload_bytes = base64.b64decode(downlink.payload)
        else:
            raise ValueError("Either 'command' or 'payload' must be provided")

        # ============================================================
        # Kuando Downlink Verification Setup
        # ============================================================
        is_kuando = device_eui.startswith("202020")

        if is_kuando and payload_bytes and len(payload_bytes) >= 5:
            # Add 6th byte for auto-uplink if not present
            if len(payload_bytes) == 5:
                payload_bytes = payload_bytes + bytes([0x01])
                logger.info(f"[{request_id}] Added auto-uplink byte to Kuando downlink")

            # Store expected RGB for verification
            r, g, b = payload_bytes[1], payload_bytes[2], payload_bytes[3]

            # Get current downlink counter
            last_uplink = await state_manager.redis_client.get(
                f"device:{device_eui}:last_kuando_uplink"
            )

            counter = 0
            if last_uplink:
                last_data = json.loads(last_uplink)
                counter = last_data.get("downlinks_received", 0)

            # Store expected values
            await state_manager.redis_client.setex(
                f"device:{device_eui}:pending_downlink",
                300,  # 5 minute TTL
                json.dumps({
                    "rgb": [r, g, b],
                    "counter": counter,
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id
                })
            )

            logger.info(f"Stored expected RGB for {device_eui}: ({r},{b},{g}), previous_counter={counter}")

        # Log downlink details for debugging
        logger.info(
            f"Downlink verification check: handler={handler}, is_kuando={is_kuando}, "
            f"payload_type={type(payload_bytes)}, payload_len={len(payload_bytes) if payload_bytes else 0}"
        )

        # Queue downlink via ChirpStack
        result = await chirpstack_client.queue_downlink(
            device_eui=device_eui,
            payload=payload_bytes,
            fport=downlink.fport,
            confirmed=downlink.confirmed
        )

        # Start background queue monitoring task
        queue_id = result.get('id')
        if queue_id:
            asyncio.create_task(
                verify_downlink_transmission(
                    device_eui=device_eui,
                    queue_id=queue_id,
                    chirpstack_client=chirpstack_client,
                    timeout=15
                )
            )
            logger.info(f"[{request_id}] Started queue monitoring for {device_eui} (queue_id: {queue_id})")

        # Include gateway health in response
        result['gateway_health'] = {
            'status': gw_health['health_status'],
            'online_gateways': gw_health['online_count'],
            'total_gateways': gw_health['total_count']
        }

        return ApiResponse(
            success=True,
            message=f"Downlink queued for {device_eui}",
            data=result
        )

    except Exception as e:
        logger.error(f"[{request_id}] Downlink failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Downlink failed: {str(e)}"
        )

# ============================================================
# Space Management Endpoints
# ============================================================

@app.get("/api/v1/spaces", response_model=List[Space], tags=["Spaces"])
async def list_spaces(
    request: Request,
    building: Optional[str] = None,
    floor: Optional[str] = None,
    zone: Optional[str] = None,
    state: Optional[SpaceState] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List parking spaces with optional filters"""
    db_pool = request.app.state.db_pool

    spaces = await db_pool.get_spaces(
        building=building,
        floor=floor,
        zone=zone,
        state=state,
        limit=limit,
        offset=offset
    )

    return spaces

@app.get("/api/v1/spaces/{space_id}", response_model=Space, tags=["Spaces"])
async def get_space(request: Request, space_id: str):
    """Get single parking space by ID"""
    db_pool = request.app.state.db_pool

    space = await db_pool.get_space(space_id)
    if not space:
        raise SpaceNotFoundError(space_id)

    return space

@app.post("/api/v1/spaces", response_model=Space, status_code=201, tags=["Spaces"])
async def create_space(request: Request, space_data: SpaceCreate):
    """Create new parking space"""
    db_pool = request.app.state.db_pool

    try:
        space = await db_pool.create_space(space_data)
        logger.info(f"Created space: {space.code} (ID: {space.id})")
        return space
    except DuplicateResourceError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.patch("/api/v1/spaces/{space_id}", response_model=Space, tags=["Spaces"])
async def update_space(
    request: Request,
    space_id: str,
    space_update: SpaceUpdate
):
    """Update parking space"""
    db_pool = request.app.state.db_pool

    try:
        space = await db_pool.update_space(space_id, space_update)
        logger.info(f"Updated space: {space.code} (ID: {space.id})")
        return space
    except SpaceNotFoundError:
        raise HTTPException(status_code=404, detail="Space not found")

@app.delete("/api/v1/spaces/{space_id}", status_code=204, tags=["Spaces"])
async def delete_space(request: Request, space_id: str):
    """Delete parking space (soft delete)"""
    db_pool = request.app.state.db_pool

    try:
        await db_pool.soft_delete_space(space_id)
        logger.info(f"Deleted space: {space_id}")
        return
    except SpaceNotFoundError:
        raise HTTPException(status_code=404, detail="Space not found")

# ============================================================
# Reservation Management Endpoints
# ============================================================

@app.get("/api/v1/reservations", response_model=List[Reservation], tags=["Reservations"])
async def list_reservations(
    request: Request,
    space_id: Optional[str] = None,
    user_email: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List reservations with optional filters"""
    db_pool = request.app.state.db_pool

    reservations = await db_pool.get_reservations(
        space_id=space_id,
        user_email=user_email,
        limit=limit,
        offset=offset
    )

    return reservations

@app.get("/api/v1/reservations/{reservation_id}", response_model=Reservation, tags=["Reservations"])
async def get_reservation(request: Request, reservation_id: str):
    """Get single reservation by ID"""
    db_pool = request.app.state.db_pool

    reservation = await db_pool.get_reservation(reservation_id)
    if not reservation:
        raise ReservationNotFoundError(reservation_id)

    return reservation

@app.post("/api/v1/reservations", response_model=Reservation, status_code=201, tags=["Reservations"])
async def create_reservation(request: Request, reservation_data: ReservationCreate):
    """Create new reservation"""
    db_pool = request.app.state.db_pool
    task_manager = request.app.state.task_manager
    state_manager = request.app.state.state_manager

    try:
        # Check space availability
        available = await state_manager.check_availability(
            space_id=str(reservation_data.space_id),
            start_time=reservation_data.start_time,
            end_time=reservation_data.end_time
        )

        if not available:
            raise HTTPException(
                status_code=409,
                detail="Space is not available for the requested time period"
            )

        # Create reservation
        reservation = await db_pool.create_reservation(reservation_data)

        # Schedule background tasks for reservation lifecycle
        await task_manager.schedule_reservation(reservation)

        logger.info(
            f"Created reservation {reservation.id} for space {reservation_data.space_id} "
            f"from {reservation_data.start_time} to {reservation_data.end_time}"
        )

        return reservation

    except DuplicateResourceError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.delete("/api/v1/reservations/{reservation_id}", status_code=204, tags=["Reservations"])
async def cancel_reservation(request: Request, reservation_id: str):
    """Cancel reservation"""
    db_pool = request.app.state.db_pool
    task_manager = request.app.state.task_manager

    try:
        # Cancel reservation in database
        await db_pool.cancel_reservation(reservation_id)

        # Cancel scheduled tasks
        await task_manager.cancel_reservation_tasks(reservation_id)

        logger.info(f"Cancelled reservation: {reservation_id}")
        return

    except ReservationNotFoundError:
        raise HTTPException(status_code=404, detail="Reservation not found")

# ============================================================
# Device Management Endpoints
# ============================================================

@app.get("/api/v1/devices", response_model=List[Dict[str, Any]], tags=["Devices"])
async def list_devices(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List devices from ChirpStack"""
    chirpstack_client = request.app.state.chirpstack_client

    devices = await chirpstack_client.get_devices(limit=limit, offset=offset)
    return devices

@app.get("/api/v1/devices/displays", response_model=List[Dict[str, Any]], tags=["Devices"])
async def list_display_devices(
    request: Request,
    dev_eui_prefix: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List display devices from database
    Optionally filter by dev_eui prefix (e.g., '202020' for Kuando devices)
    """
    db_pool = request.app.state.db_pool

    try:
        # Build query with optional prefix filter
        query = """
            SELECT
                dd.id,
                dd.dev_eui,
                dd.device_model,
                dd.status,
                dd.last_seen_at,
                dd.created_at,
                dt.type_code,
                dt.name as device_type_name,
                dt.category,
                s.id as space_id,
                s.code as space_code,
                s.name as space_name
            FROM display_devices dd
            LEFT JOIN device_types dt ON dd.device_type_id = dt.id
            LEFT JOIN spaces s ON s.display_device_id = dd.id AND s.deleted_at IS NULL
            WHERE dd.enabled = true
        """

        params = []
        if dev_eui_prefix:
            query += " AND dd.dev_eui LIKE $1"
            params.append(f"{dev_eui_prefix}%")

        query += " ORDER BY dd.last_seen_at DESC NULLS LAST, dd.created_at DESC"
        query += f" LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
        params.extend([limit, offset])

        async with db_pool.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        devices = []
        for row in rows:
            devices.append({
                "id": str(row["id"]),
                "dev_eui": row["dev_eui"],
                "device_model": row["device_model"],
                "status": row["status"],
                "type_code": row["type_code"],
                "device_type_name": row["device_type_name"],
                "category": row["category"],
                "space_id": str(row["space_id"]) if row["space_id"] else None,
                "space_code": row["space_code"],
                "space_name": row["space_name"],
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None
            })

        logger.info(f"Found {len(devices)} display devices (prefix={dev_eui_prefix})")
        return devices

    except Exception as e:
        logger.error(f"Error fetching display devices: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch display devices: {str(e)}"
        )

@app.get("/api/v1/devices/{dev_eui}", response_model=Dict[str, Any], tags=["Devices"])
async def get_device(request: Request, dev_eui: str):
    """Get device information from ChirpStack"""
    chirpstack_client = request.app.state.chirpstack_client

    device_eui = normalize_deveui(dev_eui)
    device = await chirpstack_client.get_device(device_eui)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return device

@app.get("/api/v1/devices/{dev_eui}/queue", response_model=List[Dict[str, Any]], tags=["Devices"])
async def get_device_queue(request: Request, dev_eui: str):
    """Get device downlink queue"""
    chirpstack_client = request.app.state.chirpstack_client

    device_eui = normalize_deveui(dev_eui)
    queue = await chirpstack_client.get_device_queue(device_eui)

    return queue

@app.delete("/api/v1/devices/{dev_eui}/queue", status_code=204, tags=["Devices"])
async def flush_device_queue(request: Request, dev_eui: str):
    """Flush device downlink queue"""
    chirpstack_client = request.app.state.chirpstack_client

    device_eui = normalize_deveui(dev_eui)
    await chirpstack_client.flush_device_queue(device_eui)

    return

# ============================================================
# Gateway Management Endpoints
# ============================================================

@app.get("/api/v1/gateways", response_model=List[Dict[str, Any]], tags=["Gateways"])
async def list_gateways(request: Request):
    """List all gateways with status"""
    gateway_monitor = request.app.state.gateway_monitor

    gateways = await gateway_monitor.get_all_gateways(refresh=True)
    return gateways

@app.get("/api/v1/gateways/online", response_model=List[Dict[str, Any]], tags=["Gateways"])
async def list_online_gateways(request: Request):
    """List online gateways"""
    gateway_monitor = request.app.state.gateway_monitor

    gateways = await gateway_monitor.get_online_gateways()
    return gateways

@app.get("/api/v1/gateways/health", response_model=Dict[str, Any], tags=["Gateways"])
async def gateway_health(request: Request):
    """Get gateway health summary"""
    gateway_monitor = request.app.state.gateway_monitor

    health = await gateway_monitor.get_health_summary()
    return health

# ============================================================
# Root Endpoint
# ============================================================

@app.get("/", tags=["System"])
async def root():
    """API root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

# ============================================================
# Main Entry Point (for debugging)
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
