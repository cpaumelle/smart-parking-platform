"""
Tenant Context Manager
=======================
Manages tenant context for database connections using PostgreSQL session variables.

This is the CRITICAL security component for Row-Level Security (RLS).

How it works:
1. Acquires database connection from pool
2. Starts a transaction
3. Sets PostgreSQL session variable: SET LOCAL app.current_tenant_id = '<tenant_id>'
4. All subsequent queries on this connection are automatically filtered by RLS policies
5. Transaction and context are automatically cleared when connection returns to pool

Security Guarantee:
Even if application code has bugs or SQL injection vulnerabilities,
PostgreSQL RLS enforces tenant isolation at the database level.
"""

from contextlib import asynccontextmanager
from uuid import UUID
import logging
import asyncpg

logger = logging.getLogger("tenant_context")


class TenantContext:
    """
    Manages tenant context for database connections.
    
    SECURITY: This sets PostgreSQL session variable that RLS policies use.
    """
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    @asynccontextmanager
    async def with_tenant(self, tenant_id: UUID):
        """
        Acquire connection, start transaction, and set tenant context.
        
        Usage:
            async with tenant_context.with_tenant(tenant_id) as conn:
                # All queries on this connection are scoped to tenant_id
                result = await conn.fetch("SELECT * FROM parking_spaces.spaces")
                # RLS ensures only tenant_id's rows are returned
        
        Args:
            tenant_id: UUID of the tenant
        
        Yields:
            asyncpg.Connection with tenant context set in transaction
        """
        async with self.pool.acquire() as conn:
            # Start transaction (required for SET LOCAL)
            async with conn.transaction():
                try:
                    # Set tenant context (CRITICAL FOR SECURITY)
                    # Note: SET LOCAL doesn't support parameterized queries,
                    # but tenant_id is a UUID so this is safe
                    await conn.execute(
                        f"SET LOCAL app.current_tenant_id = '{str(tenant_id)}'"
                    )
                    
                    logger.debug(f"✅ Tenant context set: {tenant_id}")
                    
                    yield conn
                    
                except Exception as e:
                    logger.error(f"❌ Error in tenant context: {e}")
                    raise
                # Transaction automatically commits on context exit
                # SET LOCAL is automatically cleared when transaction ends


# Global tenant context instance (will be initialized with pool)
_tenant_context: TenantContext = None


def init_tenant_context(pool: asyncpg.Pool):
    """
    Initialize global tenant context with database pool.
    
    Call this during application startup after database pool is initialized.
    """
    global _tenant_context
    _tenant_context = TenantContext(pool)
    logger.info("✅ Tenant context manager initialized")


def get_tenant_context() -> TenantContext:
    """
    Get the global tenant context instance.
    
    Raises:
        RuntimeError: If tenant context not initialized
    """
    if not _tenant_context:
        raise RuntimeError("Tenant context not initialized. Call init_tenant_context() first.")
    return _tenant_context


@asynccontextmanager
async def get_tenant_db(tenant_id: UUID):
    """
    FastAPI-style dependency for tenant-scoped database connection.
    
    Usage in FastAPI endpoints:
        from utils.tenant_auth import TenantAuthResult, verify_tenant_api_key
        from utils.tenant_context import get_tenant_db
        
        @app.get("/v1/spaces")
        async def list_spaces(auth: TenantAuthResult = Depends(verify_tenant_api_key)):
            async with get_tenant_db(auth.tenant_id) as db:
                spaces = await db.fetch("SELECT * FROM parking_spaces.spaces")
                # RLS automatically filters to auth.tenant_id
                return {"spaces": spaces}
    
    Args:
        tenant_id: UUID of the authenticated tenant
    
    Yields:
        asyncpg.Connection with tenant context set in transaction
    """
    context = get_tenant_context()
    async with context.with_tenant(tenant_id) as conn:
        yield conn
