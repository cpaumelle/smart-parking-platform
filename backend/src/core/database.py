# src/core/database.py

import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os

class TenantAwareDatabase:
    """Database connection manager with automatic RLS context setting"""

    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or os.getenv(
            'DATABASE_URL',
            'postgresql://parking_user:password@localhost/parking_v6'
        )
        self.pool = None

    async def connect(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=10,
            max_size=20
        )

    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def transaction(self, tenant_context) -> AsyncGenerator:
        """Execute queries within tenant context"""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Set RLS context
                await connection.execute(
                    "SET LOCAL app.current_tenant_id = $1",
                    str(tenant_context.tenant_id)
                )
                await connection.execute(
                    "SET LOCAL app.is_platform_admin = $1",
                    tenant_context.is_platform_admin
                )
                await connection.execute(
                    "SET LOCAL app.user_role = $1",
                    str(tenant_context.role)
                )
                yield connection

    async def execute(self, query: str, *args):
        """Execute a query"""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch single value"""
        async with self.pool.acquire() as connection:
            return await connection.fetchval(query, *args)

# Global database instance
db = TenantAwareDatabase()

async def get_db():
    """FastAPI dependency for database access"""
    return db
