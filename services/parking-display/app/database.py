import os
import asyncpg
from contextlib import asynccontextmanager
import logging
import asyncio

logger = logging.getLogger("database")

# Database configuration - MUST be set via environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Set it in docker-compose.yml or .env file. "
        "Example: postgresql://user:password@host:5432/dbname"
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

@asynccontextmanager
async def get_db_with_timeout(timeout_seconds: float = 2.0):
    """
    Get database connection with timeout (for health checks).
    
    Raises RuntimeError if connection cannot be acquired within timeout.
    """
    if not _pool:
        raise RuntimeError("Database pool not initialized")
    
    connection = None
    try:
        connection = await asyncio.wait_for(
            _pool.acquire(),
            timeout=timeout_seconds
        )
        yield connection
    except asyncio.TimeoutError:
        raise RuntimeError(f"Could not acquire database connection within {timeout_seconds}s - pool may be exhausted")
    finally:
        if connection:
            await _pool.release(connection)
