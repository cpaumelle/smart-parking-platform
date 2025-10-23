"""Database connection with RLS support"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()

class TenantAwareSession:
    """Database session with automatic RLS context"""
    
    def __init__(self, tenant_id: str, is_platform_admin: bool = False, user_role: str = "viewer"):
        self.tenant_id = tenant_id
        self.is_platform_admin = is_platform_admin
        self.user_role = user_role
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session with RLS context set"""
        async with AsyncSessionLocal() as session:
            try:
                if settings.enable_rls:
                    # Set RLS context
                    await session.execute(
                        text("SET LOCAL app.current_tenant_id = :tenant_id"),
                        {"tenant_id": self.tenant_id}
                    )
                    await session.execute(
                        text("SET LOCAL app.is_platform_admin = :is_admin"),
                        {"is_admin": str(self.is_platform_admin).lower()}
                    )
                    await session.execute(
                        text("SET LOCAL app.user_role = :role"),
                        {"role": self.user_role}
                    )
                
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database (create tables if needed)"""
    async with engine.begin() as conn:
        # Run any initialization needed
        logger.info("Database initialized")

async def close_db():
    """Close database connections"""
    await engine.dispose()
    logger.info("Database connections closed")
