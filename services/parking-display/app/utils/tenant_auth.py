"""
Tenant Authentication Module
=============================
Validates API keys and returns tenant context for Row-Level Security.

Security Features:
- API key bcrypt validation
- Tenant status checking
- API key expiration handling
- Last-used tracking
- Rate limiting support (TODO)
"""

from fastapi import Security, HTTPException, status, Header
from typing import Optional
from uuid import UUID
import logging
from datetime import datetime, timezone
import asyncpg

logger = logging.getLogger("tenant_auth")
from app.utils.errors import redact_api_key
from app.utils.metrics import record_auth_attempt
from app.utils.audit import AuditLogger


class TenantAuthResult:
    """
    Result of tenant authentication.
    
    Contains tenant context needed for database RLS and business logic.
    """
    
    def __init__(
        self,
        tenant_id: UUID,
        tenant_slug: str,
        tenant_name: str,
        api_key_id: UUID,
        scopes: list,
        subscription_tier: str,
        is_active: bool
    ):
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.tenant_name = tenant_name
        self.api_key_id = api_key_id
        self.scopes = scopes
        self.subscription_tier = subscription_tier
        self.is_active = is_active
    
    def __repr__(self):
        return f"<TenantAuth tenant={self.tenant_slug} tier={self.subscription_tier}>"


async def verify_tenant_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db_pool = None  # Will be injected by the service
) -> TenantAuthResult:
    """
    Verify API key and return tenant context.
    
    SECURITY CRITICAL:
    1. Looks up API key in database using bcrypt comparison
    2. Validates key is active and not expired
    3. Validates tenant is active
    4. Returns tenant_id for RLS context
    5. Logs access for audit trail
    
    Args:
        x_api_key: API key from X-API-Key header
        db_pool: Database connection pool
    
    Returns:
        TenantAuthResult with tenant context
    
    Raises:
        HTTPException 401: Invalid API key format
        HTTPException 403: Invalid, revoked, expired, or inactive tenant
    """
    
    # Validate API key format
    if not x_api_key or len(x_api_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Include 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    # Redact API key for safe logging
    key_redacted = redact_api_key(x_api_key)
    
    if not db_pool:
        logger.error("❌ Database pool not provided to verify_tenant_api_key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service misconfigured"
        )
    
    try:
        # Query database for API key (using bcrypt comparison)
        query = """
            SELECT 
                ak.api_key_id,
                ak.tenant_id,
                t.tenant_slug,
                t.tenant_name,
                t.subscription_tier,
                ak.scopes,
                ak.is_active as key_active,
                ak.expires_at,
                t.is_active as tenant_active
            FROM core.api_keys ak
            JOIN core.tenants t ON ak.tenant_id = t.tenant_id
            WHERE ak.key_hash = crypt($1, ak.key_hash)
            LIMIT 1
        """
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, x_api_key)
        
        if not row:
            AuditLogger.log_auth_failure(db_pool, "invalid_api_key", ip_address=None, api_key_prefix=key_redacted)
            logger.warning(f"❌ Invalid API key attempt: {key_redacted}...")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key"
            )
        
        # Check if key is active
        if not row['key_active']:
            logger.warning(f"❌ Revoked API key used: {key_redacted}... tenant={row['tenant_slug']}")
            AuditLogger.log_auth_failure(db_pool, "revoked_api_key", api_key_prefix=key_redacted)
            record_auth_attempt(row['tenant_slug'], False, "revoked")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key has been revoked"
            )
        
        # Check if tenant is active
        if not row['tenant_active']:
            logger.warning(f"❌ Inactive tenant access attempt: {row['tenant_slug']}")
            record_auth_attempt(row['tenant_slug'], False, "inactive_tenant")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant account is inactive"
            )
        
        # Check if key is expired
        if row['expires_at'] and row['expires_at'] < datetime.now(timezone.utc):
            logger.warning(f"❌ Expired API key used: {key_redacted}... tenant={row['tenant_slug']}")
            AuditLogger.log_auth_failure(db_pool, "expired_api_key", api_key_prefix=key_redacted)
            record_auth_attempt(row['tenant_slug'], False, "expired")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key has expired"
            )
        
        # Update last_used_at (fire and forget - don't block request)
        import asyncio
        asyncio.create_task(_update_key_last_used(db_pool, row['api_key_id']))
        
        # Record successful authentication
        record_auth_attempt(row['tenant_slug'], True)
        AuditLogger.log_auth_success(db_pool, row['tenant_id'], row['tenant_slug'], row['api_key_id'])
        logger.info(f"✅ Authenticated: tenant={row['tenant_slug']} tier={row['subscription_tier']} key={key_redacted}...")
        
        return TenantAuthResult(
            tenant_id=row['tenant_id'],
            tenant_slug=row['tenant_slug'],
            tenant_name=row['tenant_name'],
            api_key_id=row['api_key_id'],
            scopes=row['scopes'],
            subscription_tier=row['subscription_tier'],
            is_active=row['tenant_active']
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (auth failures)
        raise
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def _update_key_last_used(db_pool, api_key_id: UUID):
    """
    Update last_used_at timestamp (background task).
    
    This is a fire-and-forget task that doesn't block the request.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE core.api_keys 
                SET last_used_at = NOW() 
                WHERE api_key_id = $1
            """, api_key_id)
    except Exception as e:
        logger.warning(f"Failed to update last_used_at: {e}")


# Optional: For endpoints that don't require authentication (health checks, etc.)
async def optional_tenant_auth(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db_pool = None
) -> Optional[TenantAuthResult]:
    """
    Optional tenant authentication for public endpoints.
    
    Returns None if no API key provided, otherwise validates the key.
    """
    if not x_api_key:
        return None
    
    return await verify_tenant_api_key(x_api_key, db_pool)
