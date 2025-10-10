# connections.py - database
# Version: 0.3.0 - 2025-07-19 20:45 UTC
# Changelog:
# - Added sync engine and sessionmaker for CLI scripts
# - Async engine remains default for FastAPI and background tasks

import os
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Read environment variables
DB_HOST = os.environ.get("TRANSFORM_DB_HOST", "transform-database")
DB_PORT = os.environ.get("TRANSFORM_DB_INTERNAL_PORT", "5432")
DB_NAME = os.environ.get("TRANSFORM_DB_NAME", "transform_db")
DB_USER = os.environ.get("TRANSFORM_DB_USER", "transform_user")
DB_PASSWORD = os.environ.get("TRANSFORM_DB_PASSWORD", "transformpass")

# URL-encode username and password to handle special characters like @ in passwords
DB_USER_ENCODED = quote_plus(DB_USER)
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

# Async DB URL (FastAPI, background tasks)
ASYNC_DATABASE_URL = f"postgresql+asyncpg://{DB_USER_ENCODED}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=True
)

# Sync DB URL (CLI scripts)
SYNC_DATABASE_URL = f"postgresql://{DB_USER_ENCODED}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=True)

# ✅ FastAPI-compatible async dependency
async def get_db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# ✅ CLI-compatible sync DB session (for scripts like run_enrich_new)
def get_sync_db_session():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
