# src/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import v6 routers
from src.routers.v6 import devices, dashboard, gateways
from src.core.database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart Parking Platform v6",
    description="Multi-tenant parking management system with Row-Level Security",
    version="6.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "https://app.example.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register v6 endpoints
app.include_router(devices.router, tags=["v6"])
app.include_router(dashboard.router, tags=["v6"])
app.include_router(gateways.router, tags=["v6"])

# Startup and shutdown events
@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    logger.info("Starting Smart Parking Platform v6...")
    await db.connect()
    logger.info("Database connected")

@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown"""
    logger.info("Shutting down Smart Parking Platform v6...")
    await db.disconnect()
    logger.info("Database disconnected")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "6.0.0",
        "api": "v6",
        "features": {
            "multi_tenant": True,
            "row_level_security": True,
            "device_pool_management": True,
            "chirpstack_sync": True
        }
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Smart Parking Platform v6",
        "version": "6.0.0",
        "description": "Multi-tenant parking management system",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
