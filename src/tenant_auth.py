"""
Multi-Tenancy Authentication & Authorization
Handles tenant resolution, JWT tokens, and RBAC
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Security, HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import bcrypt

from src.models import TenantContext, UserRole, TokenData
from src.auth import API_KEY_HEADER, APIKeyInfo, verify_api_key

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = None  # Set by main.py from config
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Bearer token security
security = HTTPBearer(auto_error=False)

# Global database pool reference
_db_pool = None

def set_db_pool(pool):
    """Set the database pool for authentication"""
    global _db_pool
    _db_pool = pool

def set_jwt_secret(secret: str):
    """Set the JWT secret key"""
    global JWT_SECRET_KEY
    JWT_SECRET_KEY = secret

# ============================================================
# JWT Token Functions
# ============================================================

def create_access_token(user_id: UUID, tenant_id: UUID, role: UserRole) -> str:
    """
    Create a JWT access token for a user

    Args:
        user_id: User UUID
        tenant_id: Tenant UUID
        role: User role in this tenant

    Returns:
        JWT token string
    """
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT secret key not configured")

    expires_at = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role.value,
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.utcnow().timestamp())
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT access token

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None otherwise
    """
    if not JWT_SECRET_KEY:
        logger.error("JWT secret key not configured")
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        return TokenData(
            user_id=UUID(payload["user_id"]),
            tenant_id=UUID(payload["tenant_id"]),
            role=UserRole(payload["role"]),
            exp=datetime.fromtimestamp(payload["exp"])
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Expired JWT token")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding JWT token: {e}")
        return None

# ============================================================
# Password Hashing
# ============================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Bcrypt hash suitable for database storage
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a bcrypt hash

    Args:
        password: Plain text password
        password_hash: Bcrypt hash from database

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8') if isinstance(password_hash, str) else password_hash
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

# ============================================================
# Tenant Resolution
# ============================================================

async def resolve_tenant_from_api_key(api_key_info: APIKeyInfo) -> Optional[TenantContext]:
    """
    Resolve tenant context from API key

    Args:
        api_key_info: Verified API key info

    Returns:
        TenantContext if successful, None otherwise
    """
    if not _db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        # Get API key with tenant info and scopes
        row = await _db_pool.fetchrow("""
            SELECT ak.id, ak.tenant_id, ak.scopes, t.name, t.slug, t.is_active
            FROM api_keys ak
            INNER JOIN tenants t ON ak.tenant_id = t.id
            WHERE ak.id = $1 AND ak.is_active = true AND t.is_active = true
        """, UUID(api_key_info.id))

        if not row:
            logger.warning(f"API key {api_key_info.id} not found or inactive")
            return None

        return TenantContext(
            tenant_id=row['tenant_id'],
            tenant_name=row['name'],
            tenant_slug=row['slug'],
            api_key_id=UUID(api_key_info.id),
            api_key_scopes=row['scopes'],
            source='api_key'
        )

    except Exception as e:
        logger.error(f"Error resolving tenant from API key: {e}")
        return None

async def resolve_tenant_from_jwt(token_data: TokenData) -> Optional[TenantContext]:
    """
    Resolve tenant context from JWT token

    Args:
        token_data: Decoded JWT token data

    Returns:
        TenantContext if successful, None otherwise
    """
    if not _db_pool:
        logger.error("Database pool not initialized")
        return None

    try:
        # Verify user membership is still active
        row = await _db_pool.fetchrow("""
            SELECT
                t.id as tenant_id,
                t.name as tenant_name,
                t.slug as tenant_slug,
                um.role,
                u.is_active as user_active,
                um.is_active as membership_active,
                t.is_active as tenant_active
            FROM users u
            INNER JOIN user_memberships um ON u.id = um.user_id
            INNER JOIN tenants t ON um.tenant_id = t.id
            WHERE u.id = $1 AND um.tenant_id = $2
        """, token_data.user_id, token_data.tenant_id)

        if not row:
            logger.warning(f"User {token_data.user_id} has no membership in tenant {token_data.tenant_id}")
            return None

        if not row['user_active']:
            logger.warning(f"User {token_data.user_id} is inactive")
            return None

        if not row['membership_active']:
            logger.warning(f"User {token_data.user_id} membership in tenant {token_data.tenant_id} is inactive")
            return None

        if not row['tenant_active']:
            logger.warning(f"Tenant {token_data.tenant_id} is inactive")
            return None

        return TenantContext(
            tenant_id=row['tenant_id'],
            tenant_name=row['tenant_name'],
            tenant_slug=row['tenant_slug'],
            user_id=token_data.user_id,
            user_role=UserRole(row['role']),
            source='jwt'
        )

    except Exception as e:
        logger.error(f"Error resolving tenant from JWT: {e}")
        return None

# ============================================================
# Authentication Dependencies
# ============================================================

async def get_current_tenant(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> TenantContext:
    """
    FastAPI dependency that resolves tenant context from either JWT or API key

    Priority:
    1. JWT Bearer token (user authentication)
    2. X-API-Key header (service authentication)

    Raises:
        HTTPException: 401 if no authentication provided or invalid
        HTTPException: 403 if tenant is inactive
    """
    tenant_context = None

    # Try JWT first
    if credentials and credentials.credentials:
        token_data = decode_access_token(credentials.credentials)
        if token_data:
            tenant_context = await resolve_tenant_from_jwt(token_data)
            if tenant_context:
                logger.info(f"Authenticated user {token_data.user_id} for tenant {tenant_context.tenant_id}")

    # Fall back to API key
    if not tenant_context and api_key:
        api_key_info = await verify_api_key(api_key)
        if api_key_info:
            tenant_context = await resolve_tenant_from_api_key(api_key_info)
            if tenant_context:
                logger.info(f"Authenticated API key {api_key_info.name} for tenant {tenant_context.tenant_id}")

    # No valid authentication
    if not tenant_context:
        logger.warning(f"No valid authentication from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide either JWT Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Attach tenant context to request state
    request.state.tenant_id = tenant_context.tenant_id
    request.state.tenant_name = tenant_context.tenant_name
    request.state.auth_source = tenant_context.source

    return tenant_context

async def get_optional_tenant(
    request: Request,
    api_key: Optional[str] = Security(API_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[TenantContext]:
    """
    Optional tenant context - returns None if no authentication provided
    Used for public endpoints that have different behavior for authenticated users
    """
    try:
        return await get_current_tenant(request, api_key, credentials)
    except HTTPException:
        return None

# ============================================================
# RBAC Dependencies
# ============================================================

def require_role(minimum_role: UserRole):
    """
    Decorator factory for role-based access control

    Usage:
        @app.get("/admin/endpoint")
        async def admin_endpoint(tenant: TenantContext = Depends(require_role(UserRole.ADMIN))):
            ...

    Role hierarchy (lowest to highest):
        VIEWER < OPERATOR < ADMIN < OWNER
    """
    role_hierarchy = {
        UserRole.VIEWER: 1,
        UserRole.OPERATOR: 2,
        UserRole.ADMIN: 3,
        UserRole.OWNER: 4
    }

    async def check_role(tenant: TenantContext = Depends(get_current_tenant)) -> TenantContext:
        # API keys have implicit admin access (no user_role)
        if tenant.source == 'api_key':
            return tenant

        # Check user role
        if not tenant.user_role:
            logger.warning(f"No user role in tenant context for user {tenant.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        user_level = role_hierarchy.get(tenant.user_role, 0)
        required_level = role_hierarchy.get(minimum_role, 999)

        if user_level < required_level:
            logger.warning(
                f"User {tenant.user_id} role {tenant.user_role.value} insufficient for {minimum_role.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher"
            )

        return tenant

    return check_role

# Convenience dependencies for common roles
require_viewer = require_role(UserRole.VIEWER)
require_operator = require_role(UserRole.OPERATOR)
require_admin = require_role(UserRole.ADMIN)
require_owner = require_role(UserRole.OWNER)
