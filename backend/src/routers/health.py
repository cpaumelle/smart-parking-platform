"""Health and status endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.database import get_db
from ..core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


@router.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database health check"""
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }


@router.get("/health/full")
async def full_health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check"""
    
    health_status = {
        "status": "healthy",
        "version": settings.app_version,
        "components": {}
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {e}"
        health_status["status"] = "degraded"
    
    # Check RLS
    try:
        result = await db.execute(text("SELECT current_tenant_id()"))
        health_status["components"]["rls"] = "healthy"
    except Exception as e:
        health_status["components"]["rls"] = f"unhealthy: {e}"
        health_status["status"] = "degraded"
    
    return health_status
