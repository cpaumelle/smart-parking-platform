import os
import asyncpg
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("database")

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://parking_user:parking_password@parking-postgres:5432/parking_platform"
)

# Connection pool
_pool = None

async def init_db_pool():
    """Initialize database connection pool"""
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=30
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise

async def close_db_pool():
    """Close database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")

@asynccontextmanager
async def get_db():
    """Get database connection from pool"""
    if not _pool:
        raise RuntimeError("Database pool not initialized")

    async with _pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation error: {e}")
            raise

async def get_db_dependency():
    """FastAPI dependency for database connection"""
    async with get_db() as db:
        yield db
