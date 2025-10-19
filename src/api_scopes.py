"""
API Key Scope Enforcement
Implements least-privilege access control for API keys
"""
import logging
from typing import Set
from fastapi import HTTPException, status, Depends

from src.models import TenantContext
from src.tenant_auth import get_current_tenant

logger = logging.getLogger(__name__)

# Define scope hierarchy and mappings
SCOPE_HIERARCHY = {
    # Read scopes
    "spaces:read": ["spaces:read"],
    "devices:read": ["devices:read"],
    "reservations:read": ["reservations:read"],
    "telemetry:read": ["telemetry:read"],
    "users:read": ["users:read"],
    "sites:read": ["sites:read"],
    "tenants:read": ["tenants:read"],

    # Write scopes (include read)
    "spaces:write": ["spaces:read", "spaces:write"],
    "devices:write": ["devices:read", "devices:write"],
    "reservations:write": ["reservations:read", "reservations:write"],
    "sites:write": ["sites:read", "sites:write"],
    "tenants:write": ["tenants:read", "tenants:write"],

    # Special scopes
    "webhook:ingest": ["webhook:ingest"],
    "admin:*": ["*"],  # Full access
}


def expand_scopes(scopes: Set[str]) -> Set[str]:
    """
    Expand scopes based on hierarchy

    Example:
        expand_scopes({"spaces:write"}) -> {"spaces:read", "spaces:write"}
    """
    expanded = set()
    for scope in scopes:
        if scope in SCOPE_HIERARCHY:
            expanded.update(SCOPE_HIERARCHY[scope])
        else:
            expanded.add(scope)
    return expanded


def check_scopes(required: Set[str], tenant: TenantContext):
    """
    Check if the current tenant context has required scopes

    Args:
        required: Set of required scopes (e.g., {"spaces:write"})
        tenant: Current tenant context from authentication

    Raises:
        HTTPException: 403 if scopes are insufficient

    Note:
        - JWT users (authenticated via Bearer token) have implicit full access
        - API keys (authenticated via X-API-Key) are checked against scopes column
    """
    # JWT users have full access (already role-gated by require_* dependencies)
    if tenant.source == "jwt":
        logger.debug(f"JWT user {tenant.user_id} has implicit full access")
        return

    # API keys must have explicit scopes
    if tenant.source == "api_key":
        # Check if API key has scopes defined
        if not tenant.api_key_scopes:
            logger.error(f"API key {tenant.api_key_id} has no scopes defined")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key has no scopes defined"
            )

        # Expand scopes based on hierarchy
        expanded_required = expand_scopes(required)
        expanded_available = expand_scopes(set(tenant.api_key_scopes))

        # Wildcard grants everything
        if "*" in expanded_available or "admin:*" in expanded_available:
            logger.debug(f"API key {tenant.api_key_id} has wildcard access")
            return

        # Check if all required scopes are available
        if not expanded_required.issubset(expanded_available):
            missing = expanded_required - expanded_available
            logger.warning(
                f"API key {tenant.api_key_id} lacks required scopes. "
                f"Required: {required}, Available: {tenant.api_key_scopes}, Missing: {missing}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scopes: {', '.join(sorted(missing))}"
            )

        logger.debug(f"API key {tenant.api_key_id} has sufficient scopes for {required}")
        return

    # Unknown auth source
    logger.error(f"Unknown auth source: {tenant.source}")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid authentication source"
    )


def require_scopes(*required_scopes: str):
    """
    FastAPI dependency factory for scope checking

    Usage:
        @app.post("/api/v1/spaces", dependencies=[Depends(require_scopes("spaces:write"))])
        async def create_space(...):
            ...

    Args:
        *required_scopes: Variable number of required scope strings

    Returns:
        FastAPI dependency function
    """
    required = set(required_scopes)

    async def check_scopes_dependency(tenant: TenantContext = Depends(get_current_tenant)):
        check_scopes(required, tenant)
        return tenant

    return check_scopes_dependency


# ============================================================
# Scope Enforcement for API Keys (Full Implementation)
# ============================================================

async def enforce_api_key_scopes(required_scopes: Set[str], api_key_id: str, db) -> bool:
    """
    Check if API key has required scopes

    Args:
        required_scopes: Set of required scopes
        api_key_id: API key UUID
        db: Database connection pool

    Returns:
        True if API key has all required scopes

    Raises:
        HTTPException: 403 if scopes are insufficient
    """
    try:
        # Fetch API key scopes from database
        row = await db.fetchrow("""
            SELECT scopes
            FROM api_keys
            WHERE id = $1 AND is_active = true
        """, api_key_id)

        if not row:
            logger.error(f"API key {api_key_id} not found or inactive")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key not found or inactive"
            )

        api_key_scopes = set(row['scopes'])

        # Expand both sets based on hierarchy
        expanded_required = expand_scopes(required_scopes)
        expanded_available = expand_scopes(api_key_scopes)

        # Check if all required scopes are available
        if "*" in expanded_available:
            # Wildcard grants everything
            return True

        if not expanded_required.issubset(expanded_available):
            missing = expanded_required - expanded_available
            logger.warning(f"API key {api_key_id} missing scopes: {missing}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scopes: {', '.join(missing)}"
            )

        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking API key scopes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify API key scopes"
        )


# ============================================================
# Convenience Scope Definitions
# ============================================================

# Common scope sets for different operations
SCOPES_SPACES_READ = {"spaces:read"}
SCOPES_SPACES_WRITE = {"spaces:write"}
SCOPES_DEVICES_READ = {"devices:read"}
SCOPES_DEVICES_WRITE = {"devices:write"}
SCOPES_RESERVATIONS_READ = {"reservations:read"}
SCOPES_RESERVATIONS_WRITE = {"reservations:write"}
SCOPES_WEBHOOK_INGEST = {"webhook:ingest"}
SCOPES_TELEMETRY_READ = {"telemetry:read"}

# Example usage in routers:
"""
from src.api_scopes import require_scopes, SCOPES_SPACES_WRITE

@router.post("/spaces", dependencies=[Depends(require_scopes("spaces:write"))])
async def create_space(...):
    ...
"""
