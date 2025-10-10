from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import os
import sys
sys.path.append("/app")

from app.routers import actuations, spaces, reservations
from app.database import init_db_pool, close_db_pool, get_db_dependency
from app.tasks.monitor import start_monitoring_tasks

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
    logger.info("Parking Display Service v1.0.0 starting")

    try:
        # Initialize database
        await init_db_pool()
        logger.info("Database connection pool initialized")

        # Start background monitoring tasks
        monitor_task = asyncio.create_task(start_monitoring_tasks())
        background_tasks.append(monitor_task)
        logger.info("Background monitoring tasks started")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
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

        # Close database pool
        await close_db_pool()
        logger.info("Database connections closed")

    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="Parking Display Service",
    description="Smart parking state management and Class C display actuation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(actuations.router, prefix="/v1/actuations", tags=["actuations"])
app.include_router(spaces.router, prefix="/v1/spaces", tags=["spaces"])
app.include_router(reservations.router, prefix="/v1/reservations", tags=["reservations"])

@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "parking-display",
        "version": "1.0.0",
        "status": "operational",
        "description": "Smart parking state management and Class C display actuation",
        "endpoints": {
            "actuations": "/v1/actuations",
            "spaces": "/v1/spaces",
            "reservations": "/v1/reservations",
            "health": "/health",
            "docs": "/docs"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check(db = Depends(get_db_dependency)):
    """Comprehensive health check"""
    try:
        # Test database connection
        db_result = await db.fetchval("SELECT 1")
        database_connected = db_result == 1

        # Get basic stats
        stats_query = """
            SELECT
                (SELECT COUNT(*) FROM parking_spaces.spaces WHERE enabled = TRUE) as spaces_count,
                (SELECT COUNT(*) FROM parking_spaces.reservations WHERE status = 'active') as active_reservations,
                (SELECT MAX(created_at) FROM parking_operations.actuations) as last_actuation
        """
        stats = await db.fetchrow(stats_query)

        return {
            "status": "healthy" if database_connected else "unhealthy",
            "service": "parking-display",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "database_connected": database_connected,
            "parking_spaces_count": stats["spaces_count"] or 0,
            "active_reservations_count": stats["active_reservations"] or 0,
            "last_actuation": stats["last_actuation"].isoformat() if stats["last_actuation"] else None
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "parking-display",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "database_connected": False
        }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
