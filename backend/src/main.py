"""Main FastAPI application for V6"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .core.config import settings
from .core.database import init_db, close_db
from .middleware.request_id import RequestIDMiddleware
from .middleware.tenant import TenantMiddleware

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Smart Parking Platform with Multi-Tenant Architecture and Row-Level Security",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TenantMiddleware)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "features": {
            "v6_api": settings.use_v6_api,
            "rls_enabled": settings.enable_rls,
            "audit_log": settings.enable_audit_log,
            "metrics": settings.enable_metrics
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


@app.get("/api/v6/status")
async def v6_status():
    """V6 API status endpoint"""
    return {
        "api_version": "v6",
        "features": {
            "multi_tenant": True,
            "row_level_security": settings.enable_rls,
            "platform_admin": True,
            "device_lifecycle": True,
            "reservations": True,
            "audit_log": settings.enable_audit_log
        },
        "platform_tenant_id": settings.platform_tenant_id
    }


# Import and include routers (to be implemented)
# from .routers import devices, spaces, reservations, tenants
# app.include_router(devices.router, prefix="/api/v6/devices", tags=["devices"])
# app.include_router(spaces.router, prefix="/api/v6/spaces", tags=["spaces"])
# app.include_router(reservations.router, prefix="/api/v6/reservations", tags=["reservations"])
# app.include_router(tenants.router, prefix="/api/v6/tenants", tags=["tenants"])

logger.info(f"{settings.app_name} initialized successfully")
