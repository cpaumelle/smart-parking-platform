from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import os
import sys
import json
sys.path.append("/app")

from app.routers import actuations, spaces, reservations, admin
from app.database import init_db_pool, close_db_pool, get_db_dependency, get_db_pool
from app.tasks.monitor import start_monitoring_tasks
from app.scheduler.scheduler import start_scheduler, shutdown_scheduler
from app.utils.idempotency import init_redis, close_redis
from app.utils.tenant_context import init_tenant_context
from app.middleware import UsageTrackingMiddleware
from app.utils.errors import (
    ParkingAPIError,
    parking_api_error_handler,
    validation_error_handler,
    generic_exception_handler
)
from fastapi.exceptions import RequestValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("parking-display")

# Background tasks storage
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""

    # Startup
    logger.info("=========================================================")
    logger.info("Parking Display Service v1.5.1 starting")
    logger.info("Multi-Tenancy: ENABLED (PostgreSQL RLS)")
    logger.info("=========================================================")

    try:
        # Initialize database
        await init_db_pool()
        logger.info("✅ Database connection pool initialized")

        # Initialize tenant context (CRITICAL FOR MULTI-TENANCY)
        init_tenant_context(get_db_pool())
        logger.info("✅ Tenant context manager initialized")

        # Initialize Redis for idempotency
        await init_redis()
        logger.info("✅ Redis initialized for idempotency cache")

        # Start APScheduler for reservation management
        start_scheduler()
        logger.info("✅ APScheduler started for reservation lifecycle management")

        # Start background monitoring tasks
        monitor_task = asyncio.create_task(start_monitoring_tasks())
        background_tasks.append(monitor_task)
        logger.info("✅ Background monitoring tasks started")

        logger.info("=========================================================")
        logger.info("Parking Display Service fully operational")
        logger.info("=========================================================")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Parking Display Service")

    try:
        # Cancel background tasks
        for task in background_tasks:
            task.cancel()

        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
            logger.info("Background tasks stopped")

        # Shutdown APScheduler
        shutdown_scheduler()
        logger.info("APScheduler shutdown")

        # Close Redis connection
        await close_redis()

        # Close database pool
        await close_db_pool()
        logger.info("Database connections closed")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="Parking Display Service",
    description="Smart parking state management and Class C display actuation (Multi-Tenant)",
    version="1.5.1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (restricted origins - security hardened)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://devices.verdegris.eu",
        "https://parking.verdegris.eu"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)
# Usage tracking middleware
app.add_middleware(UsageTrackingMiddleware)

# Include routers
app.include_router(actuations.router, prefix="/v1/actuations", tags=["actuations"])
app.include_router(spaces.router, prefix="/v1/spaces", tags=["spaces"])
app.include_router(reservations.router, prefix="/v1/reservations", tags=["reservations"])
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])

# Register exception handlers
app.add_exception_handler(ParkingAPIError, parking_api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "parking-display",
        "version": "1.5.1",
        "status": "operational",
        "description": "Smart parking state management and Class C display actuation",
        "multi_tenancy": "enabled",
        "endpoints": {
            "actuations": "/v1/actuations",
            "spaces": "/v1/spaces",
            "reservations": "/v1/reservations",
            "health": "/health",
            "admin": "/v1/admin",
            "docs": "/docs"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Prometheus Metrics Endpoint
from app.utils.metrics import get_metrics

@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint"""
    return await get_metrics()


@app.get("/health")
async def health_check():
    """Comprehensive health check with multi-tenancy validation"""
    try:
        db_pool = get_db_pool()
        
        # Test database connection and get stats
        async with db_pool.acquire() as conn:
            db_result = await conn.fetchval("SELECT 1")
            database_connected = db_result == 1
            
            # Use SECURITY DEFINER function that bypasses RLS
            stats_json = await conn.fetchval("SELECT public.get_health_check_stats()")
            stats = json.loads(stats_json)
            
            # Validate multi-tenancy is working
            tenant_check = stats.get("active_tenants", 0) > 0
        
        # Test Redis connection
        redis_connected = False
        try:
            from app.utils.idempotency import get_redis_client
            redis_client = get_redis_client()
            if redis_client:
                await redis_client.ping()
                redis_connected = True
        except:
            pass

        # Add scheduler status
        scheduler_running = False
        scheduled_jobs_count = 0
        try:
            from app.scheduler.scheduler import get_scheduler
            scheduler = get_scheduler()
            scheduler_running = scheduler.running
            scheduled_jobs_count = len(scheduler.get_jobs())
        except:
            pass

        # Determine overall status
        all_healthy = all([
            database_connected,
            tenant_check,
            redis_connected,
            scheduler_running
        ])

        # Parse last_actuation timestamp if present
        last_actuation = None
        if stats.get("last_actuation"):
            from datetime import datetime as dt
            last_actuation = stats["last_actuation"]

        return {
            "status": "healthy" if all_healthy else "degraded",
            "service": "parking-display",
            "version": "1.5.1",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if database_connected else "unhealthy",
                "redis": "healthy" if redis_connected else "unhealthy",
                "scheduler": "healthy" if scheduler_running else "unhealthy",
                "multi_tenancy": "healthy" if tenant_check else "unhealthy"
            },
            "statistics": {
                "active_tenants": stats.get("active_tenants", 0),
                "active_api_keys": stats.get("active_api_keys", 0),
                "parking_spaces": stats.get("spaces_count", 0),
                "active_reservations": stats.get("active_reservations", 0),
                "scheduled_jobs": scheduled_jobs_count
            },
            "last_actuation": last_actuation,
            "multi_tenancy": "enabled"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "parking-display",
            "version": "1.5.1",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "components": {
                "database": "unknown",
                "redis": "unknown",
                "scheduler": "unknown",
                "multi_tenancy": "unknown"
            }
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
