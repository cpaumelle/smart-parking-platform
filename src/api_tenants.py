"""
Tenant Management & Authentication API Endpoints
Handles tenant CRUD, user management, authentication, and RBAC
"""
import logging
import json
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from asyncpg import Pool

from src.models import (
    Tenant, TenantCreate, TenantUpdate,
    Site, SiteCreate, SiteUpdate,
    User, UserCreate, UserUpdate, UserWithMemberships,
    UserMembership, UserMembershipCreate, UserMembershipUpdate,
    LoginRequest, LoginResponse, RegistrationRequest,
    RefreshRequest, RefreshResponse,
    UserProfileResponse, UserLimitsResponse,
    APIKey, APIKeyCreate, APIKeyResponse,
    TenantContext, UserRole
)
from src.tenant_auth import (
    get_current_tenant, require_owner, require_admin,
    create_access_token, hash_password, verify_password,
    set_db_pool as set_tenant_auth_db_pool
)
from src.auth import generate_api_key, hash_api_key
from src.database import get_db
from src.api_scopes import require_scopes
from src.webhook_validation import get_or_create_webhook_secret, rotate_webhook_secret
from src.orphan_devices import get_orphan_devices, assign_orphan_device, delete_orphan_device
from src.refresh_token_service import get_refresh_token_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Multi-Tenancy"])

# ============================================================
# Authentication Endpoints
# ============================================================

@router.post("/auth/login", response_model=LoginResponse, summary="User Login")
async def login(
    request: Request,
    login_req: LoginRequest,
    db: Pool = Depends(get_db)
):
    """
    Authenticate user and return JWT token

    The token includes:
    - User ID
    - Primary tenant ID (first active membership)
    - User role in that tenant

    Users can switch tenants by requesting a new token.
    """
    try:
        # Find user by email
        user_row = await db.fetchrow("""
            SELECT id, email, name, password_hash, is_active, email_verified
            FROM users
            WHERE email = $1
        """, login_req.email.lower())

        if not user_row:
            logger.warning(f"Login attempt for non-existent email: {login_req.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Check if user is active
        if not user_row['is_active']:
            logger.warning(f"Login attempt for inactive user: {login_req.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Please contact support."
            )

        # Verify password
        if not verify_password(login_req.password, user_row['password_hash']):
            logger.warning(f"Invalid password for user: {login_req.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Get user's tenants
        tenant_rows = await db.fetch("""
            SELECT t.id, t.name, t.slug, um.role, um.is_active
            FROM user_memberships um
            INNER JOIN tenants t ON um.tenant_id = t.id
            WHERE um.user_id = $1 AND um.is_active = true AND t.is_active = true
            ORDER BY um.created_at ASC
        """, user_row['id'])

        if not tenant_rows:
            logger.warning(f"User {login_req.email} has no active tenant memberships")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active tenant membership found"
            )

        # Use first tenant as primary
        primary_tenant = tenant_rows[0]

        # Create JWT token (short-lived: 15 minutes)
        access_token = create_access_token(
            user_id=user_row['id'],
            tenant_id=primary_tenant['id'],
            role=UserRole(primary_tenant['role'])
        )

        # Create refresh token (long-lived: 30 days)
        refresh_token_service = get_refresh_token_service()

        # Extract client information for device fingerprinting
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        device_fingerprint = request.headers.get("x-device-fingerprint")  # Optional client-provided fingerprint

        refresh_token = await refresh_token_service.create_refresh_token(
            db=db,
            user_id=user_row['id'],
            device_fingerprint=device_fingerprint,
            ip_address=client_ip,
            user_agent=user_agent
        )

        # Update last login
        await db.execute("""
            UPDATE users SET last_login_at = NOW() WHERE id = $1
        """, user_row['id'])

        logger.info(f"User {login_req.email} logged in successfully (tenant: {primary_tenant['slug']})")

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=15 * 60,  # 15 minutes in seconds
            refresh_expires_in=30 * 24 * 60 * 60,  # 30 days in seconds
            user=User(
                id=user_row['id'],
                email=user_row['email'],
                name=user_row['name'],
                is_active=user_row['is_active'],
                email_verified=user_row['email_verified'],
                created_at=datetime.utcnow()
            ),
            tenants=[
                {
                    "id": str(row['id']),
                    "name": row['name'],
                    "slug": row['slug'],
                    "role": row['role']
                }
                for row in tenant_rows
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/auth/register", response_model=User, status_code=status.HTTP_201_CREATED, summary="Register New User (with new tenant)")
async def register(
    registration: RegistrationRequest,
    db: Pool = Depends(get_db)
):
    """
    Register a new user and create a new tenant

    Request body:
    {
        "user": {"email": "admin@acme.com", "name": "Admin User", "password": "securepass123"},
        "tenant": {"name": "Acme Corp", "slug": "acme"}
    }

    This creates:
    1. A new user account
    2. A new tenant (organization)
    3. A default site for the tenant
    4. User membership with OWNER role

    Use this for new organizations signing up.
    """
    user_create = registration.user
    tenant_create = registration.tenant
    try:
        # Check if user already exists
        existing = await db.fetchrow("SELECT id FROM users WHERE email = $1", user_create.email.lower())
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Check if tenant slug is available
        existing_tenant = await db.fetchrow("SELECT id FROM tenants WHERE slug = $1", tenant_create.slug.lower())
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant slug already taken"
            )

        async with db.acquire() as conn:
            async with conn.transaction():
                # Create user
                user_row = await conn.fetchrow("""
                    INSERT INTO users (email, name, password_hash, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, email, name, is_active, email_verified, created_at, updated_at
                """, user_create.email.lower(), user_create.name, hash_password(user_create.password),
                json.dumps(user_create.metadata) if user_create.metadata else None)

                # Create tenant
                tenant_row = await conn.fetchrow("""
                    INSERT INTO tenants (name, slug, metadata, settings)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                """, tenant_create.name, tenant_create.slug.lower(),
                json.dumps(tenant_create.metadata) if tenant_create.metadata else None,
                json.dumps(tenant_create.settings) if tenant_create.settings else None)

                # Create default site
                await conn.execute("""
                    INSERT INTO sites (tenant_id, name, timezone, location)
                    VALUES ($1, $2, $3, $4)
                """, tenant_row['id'], f"{tenant_create.name} - Main Site", "UTC", json.dumps({}))

                # Create user membership with OWNER role
                await conn.execute("""
                    INSERT INTO user_memberships (user_id, tenant_id, role)
                    VALUES ($1, $2, $3)
                """, user_row['id'], tenant_row['id'], UserRole.OWNER.value)

                logger.info(f"New user registered: {user_create.email} with tenant {tenant_create.slug}")

                return User(**dict(user_row))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/auth/refresh", response_model=RefreshResponse, summary="Refresh Access Token")
async def refresh_token(
    request: Request,
    refresh_req: RefreshRequest,
    db: Pool = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Security features:
    - Token rotation: Old refresh token is revoked, new one issued
    - Reuse detection: If revoked token is reused, all tokens for that device are revoked
    - Device fingerprinting: Tracks device changes for security monitoring

    Request headers (optional but recommended):
    - X-Device-Fingerprint: Unique device identifier (browser fingerprint)

    Returns:
    - New access token (15 min expiry)
    - New refresh token (30 day expiry)

    Example:
    ```
    POST /api/v1/auth/refresh
    {
        "refresh_token": "abc123..."
    }
    ```

    Response:
    ```
    {
        "access_token": "eyJ...",
        "refresh_token": "xyz789...",
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_expires_in": 2592000
    }
    ```
    """
    try:
        refresh_token_service = get_refresh_token_service()

        # Extract client information
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        device_fingerprint = request.headers.get("x-device-fingerprint")

        # Validate and rotate refresh token
        user_id, new_refresh_token = await refresh_token_service.validate_and_rotate(
            db=db,
            token=refresh_req.refresh_token,
            device_fingerprint=device_fingerprint,
            ip_address=client_ip,
            user_agent=user_agent
        )

        if not user_id or not new_refresh_token:
            logger.warning(f"Invalid or expired refresh token from IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        # Get user's primary tenant (same logic as login)
        tenant_rows = await db.fetch("""
            SELECT t.id, t.name, t.slug, um.role, um.is_active
            FROM user_memberships um
            INNER JOIN tenants t ON um.tenant_id = t.id
            WHERE um.user_id = $1 AND um.is_active = true AND t.is_active = true
            ORDER BY um.created_at ASC
        """, user_id)

        if not tenant_rows:
            logger.warning(f"User {user_id} has no active tenant memberships during token refresh")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active tenant membership found"
            )

        primary_tenant = tenant_rows[0]

        # Create new access token
        access_token = create_access_token(
            user_id=user_id,
            tenant_id=primary_tenant['id'],
            role=UserRole(primary_tenant['role'])
        )

        logger.info(f"Refreshed access token for user_id={user_id}, tenant={primary_tenant['slug']}")

        return RefreshResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=15 * 60,  # 15 minutes
            refresh_expires_in=30 * 24 * 60 * 60  # 30 days
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.get("/me", response_model=UserProfileResponse, summary="Get Current User Profile")
async def get_current_user_profile(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """
    Get current authenticated user's profile

    Returns:
    - User details
    - Current tenant context (from JWT)
    - All accessible tenants with roles

    Example:
    ```
    GET /api/v1/me
    Authorization: Bearer eyJ...
    ```

    Response:
    ```
    {
        "user": {
            "id": "uuid",
            "email": "user@example.com",
            "name": "John Doe",
            ...
        },
        "current_tenant": {
            "id": "uuid",
            "name": "Acme Corp",
            "slug": "acme",
            "role": "admin"
        },
        "all_tenants": [...]
    }
    ```
    """
    try:
        # Get user details
        user_row = await db.fetchrow("""
            SELECT id, email, name, is_active, email_verified, created_at, updated_at, last_login_at
            FROM users
            WHERE id = $1
        """, tenant.user_id)

        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        # Get all tenant memberships
        tenant_rows = await db.fetch("""
            SELECT t.id, t.name, t.slug, um.role, um.is_active
            FROM user_memberships um
            INNER JOIN tenants t ON um.tenant_id = t.id
            WHERE um.user_id = $1 AND um.is_active = true AND t.is_active = true
            ORDER BY um.created_at ASC
        """, tenant.user_id)

        # Get current tenant details
        current_tenant_info = None
        all_tenants = []

        for row in tenant_rows:
            tenant_info = {
                "id": str(row['id']),
                "name": row['name'],
                "slug": row['slug'],
                "role": row['role']
            }
            all_tenants.append(tenant_info)

            if row['id'] == tenant.tenant_id:
                current_tenant_info = tenant_info

        if not current_tenant_info:
            # Fallback if current tenant not in memberships (shouldn't happen)
            current_tenant_info = {
                "id": str(tenant.tenant_id),
                "name": tenant.tenant_name,
                "slug": tenant.tenant_slug,
                "role": tenant.user_role.value if tenant.user_role else "viewer"
            }

        return UserProfileResponse(
            user=User(**dict(user_row)),
            current_tenant=current_tenant_info,
            all_tenants=all_tenants
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile"
        )

@router.get("/me/limits", response_model=UserLimitsResponse, summary="Get Current User Rate Limits")
async def get_current_user_limits(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """
    Get current user's rate limits and resource quotas

    Returns:
    - Per-tenant rate limits (requests/minute, reservations/minute)
    - Resource quotas (max spaces, max devices, max reservations)
    - Current usage counts

    Example:
    ```
    GET /api/v1/me/limits
    Authorization: Bearer eyJ...
    ```

    Response:
    ```
    {
        "tenant_id": "uuid",
        "tenant_name": "Acme Corp",
        "rate_limits": {
            "requests_per_minute": 100,
            "reservations_per_minute": 10
        },
        "quotas": {
            "max_spaces": 500,
            "max_devices": 1000,
            "max_concurrent_reservations": 100
        },
        "usage": {
            "spaces": 42,
            "devices": 85,
            "active_reservations": 12
        }
    }
    ```
    """
    try:
        # Get tenant settings (may contain custom limits)
        tenant_row = await db.fetchrow("""
            SELECT settings
            FROM tenants
            WHERE id = $1
        """, tenant.tenant_id)

        # Default rate limits (can be overridden in tenant settings)
        rate_limits = {
            "requests_per_minute": 100,
            "reservations_per_minute": 10,
            "webhook_requests_per_minute": 1000
        }

        # Default quotas
        quotas = {
            "max_spaces": 500,
            "max_devices": 1000,
            "max_concurrent_reservations": 100,
            "max_sites": 10
        }

        # Override with tenant-specific settings if present
        if tenant_row and tenant_row['settings']:
            settings = tenant_row['settings']
            if isinstance(settings, str):
                settings = json.loads(settings)

            if 'rate_limits' in settings:
                rate_limits.update(settings['rate_limits'])
            if 'quotas' in settings:
                quotas.update(settings['quotas'])

        # Get current usage
        spaces_count = await db.fetchval("""
            SELECT COUNT(*) FROM spaces
            WHERE tenant_id = $1 AND deleted_at IS NULL
        """, tenant.tenant_id)

        # Count both sensor and display devices
        sensor_devices_count = await db.fetchval("""
            SELECT COUNT(DISTINCT sd.dev_eui)
            FROM sensor_devices sd
            INNER JOIN spaces s ON s.sensor_eui = sd.dev_eui
            WHERE s.tenant_id = $1 AND s.deleted_at IS NULL
        """, tenant.tenant_id)

        display_devices_count = await db.fetchval("""
            SELECT COUNT(DISTINCT dd.dev_eui)
            FROM display_devices dd
            INNER JOIN spaces s ON s.display_eui = dd.dev_eui
            WHERE s.tenant_id = $1 AND s.deleted_at IS NULL
        """, tenant.tenant_id)

        active_reservations_count = await db.fetchval("""
            SELECT COUNT(*) FROM reservations
            WHERE tenant_id = $1
              AND status IN ('pending', 'active')
              AND end_time > NOW()
        """, tenant.tenant_id)

        sites_count = await db.fetchval("""
            SELECT COUNT(*) FROM sites
            WHERE tenant_id = $1 AND is_active = true
        """, tenant.tenant_id)

        usage = {
            "spaces": spaces_count or 0,
            "sensor_devices": sensor_devices_count or 0,
            "display_devices": display_devices_count or 0,
            "total_devices": (sensor_devices_count or 0) + (display_devices_count or 0),
            "active_reservations": active_reservations_count or 0,
            "sites": sites_count or 0
        }

        return UserLimitsResponse(
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.tenant_name,
            rate_limits=rate_limits,
            quotas=quotas,
            usage=usage
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user limits"
        )

# ============================================================
# Tenant Management
# ============================================================

@router.get("/tenants/current", response_model=Tenant, summary="Get Current Tenant")
async def get_current_tenant_info(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """Get information about the current authenticated tenant"""
    row = await db.fetchrow("""
        SELECT id, name, slug, metadata, settings, is_active, created_at, updated_at
        FROM tenants
        WHERE id = $1
    """, tenant.tenant_id)

    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return Tenant(**dict(row))

@router.patch("/tenants/current", response_model=Tenant, summary="Update Current Tenant")
async def update_current_tenant(
    tenant_update: TenantUpdate,
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """Update current tenant (requires OWNER role)"""
    update_fields = []
    values = []
    param_count = 1

    for field, value in tenant_update.dict(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(tenant.tenant_id)
    query = f"""
        UPDATE tenants
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count}
        RETURNING id, name, slug, metadata, settings, is_active, created_at, updated_at
    """

    row = await db.fetchrow(query, *values)
    return Tenant(**dict(row))

# ============================================================
# Site Management - MOVED TO src/routers/sites.py
# ============================================================
# Sites API has been moved to dedicated router: src/routers/sites.py
# Use /api/v1/sites endpoints instead (see sites.py for implementation)

# ============================================================
# User Management (Tenant Users)
# ============================================================

@router.get("/users", response_model=List[UserWithMemberships], summary="List Tenant Users", dependencies=[Depends(require_scopes("users:read"))])
async def list_tenant_users(
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """List all users in the current tenant (requires ADMIN role, API key requires users:read scope)"""
    rows = await db.fetch("""
        SELECT u.id, u.email, u.name, u.is_active, u.email_verified, u.created_at, u.updated_at, u.last_login_at,
               um.id as membership_id, um.role, um.is_active as membership_active, um.created_at as membership_created_at
        FROM users u
        INNER JOIN user_memberships um ON u.id = um.user_id
        WHERE um.tenant_id = $1
        ORDER BY u.email
    """, tenant.tenant_id)

    users_dict = {}
    for row in rows:
        user_id = row['id']
        if user_id not in users_dict:
            users_dict[user_id] = UserWithMemberships(
                id=row['id'],
                email=row['email'],
                name=row['name'],
                is_active=row['is_active'],
                email_verified=row['email_verified'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                last_login_at=row['last_login_at'],
                memberships=[]
            )

        users_dict[user_id].memberships.append(UserMembership(
            id=row['membership_id'],
            user_id=row['id'],
            tenant_id=tenant.tenant_id,
            role=UserRole(row['role']),
            is_active=row['membership_active'],
            created_at=row['membership_created_at']
        ))

    return list(users_dict.values())

# ============================================================
# API Key Management
# ============================================================

@router.get("/api-keys", response_model=List[APIKey], summary="List API Keys")
async def list_api_keys(
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """List all API keys for the current tenant (requires OWNER role)"""
    rows = await db.fetch("""
        SELECT id, key_name as name, tenant_id, scopes, last_used_at, is_active, created_at
        FROM api_keys
        WHERE tenant_id = $1
        ORDER BY created_at DESC
    """, tenant.tenant_id)

    return [APIKey(**dict(row)) for row in rows]

@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED, summary="Create API Key")
async def create_api_key(
    api_key_create: APIKeyCreate,
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """
    Create a new API key (requires OWNER role)

    ⚠️ The plain text API key is only shown once - save it securely!
    """
    # Ensure API key is created for current tenant
    if api_key_create.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create API key for different tenant"
        )

    # Generate new API key
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)

    # Store in database with scopes
    row = await db.fetchrow("""
        INSERT INTO api_keys (key_hash, key_name, tenant_id, scopes, is_active)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, key_name as name, tenant_id, scopes, created_at
    """, key_hash, api_key_create.name, api_key_create.tenant_id, api_key_create.scopes, True)

    logger.info(f"Created API key '{api_key_create.name}' for tenant {tenant.tenant_id} with scopes: {api_key_create.scopes}")

    return APIKeyResponse(
        id=row['id'],
        name=row['name'],
        key=plain_key,  # Only shown once!
        tenant_id=row['tenant_id'],
        scopes=row['scopes'],
        created_at=row['created_at']
    )

@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke API Key")
async def revoke_api_key(
    key_id: UUID,
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """Revoke an API key (requires OWNER role)"""
    result = await db.execute("""
        UPDATE api_keys
        SET is_active = false
        WHERE id = $1 AND tenant_id = $2
    """, key_id, tenant.tenant_id)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="API key not found")

    logger.info(f"Revoked API key {key_id} for tenant {tenant.tenant_id}")
    return None

# ============================================================
# Webhook Secret Management
# ============================================================

@router.post("/webhook-secret", summary="Create Webhook Secret", status_code=status.HTTP_201_CREATED)
async def create_webhook_secret(
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """
    Create a webhook secret for HMAC signature validation (requires OWNER role)

    ⚠️ The plain text secret is only shown once - configure it in ChirpStack immediately!

    This secret is used to validate X-Webhook-Signature headers from ChirpStack webhooks,
    ensuring that uplinks come from your authorized Network Server.
    """
    try:
        secret = await get_or_create_webhook_secret(tenant.tenant_id, db)

        return {
            "secret": secret,
            "algorithm": "sha256",
            "header_name": "X-Webhook-Signature",
            "warning": "Save this secret securely - it cannot be retrieved after creation!"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating webhook secret: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook secret"
        )

@router.post("/webhook-secret/rotate", summary="Rotate Webhook Secret")
async def rotate_webhook_secret_endpoint(
    tenant: TenantContext = Depends(require_owner),
    db: Pool = Depends(get_db)
):
    """
    Rotate (replace) the webhook secret (requires OWNER role)

    ⚠️ The new secret is only shown once - update ChirpStack immediately!
    ⚠️ Old webhooks using the previous secret will fail after rotation!
    """
    try:
        new_secret = await rotate_webhook_secret(tenant.tenant_id, db)

        return {
            "secret": new_secret,
            "algorithm": "sha256",
            "header_name": "X-Webhook-Signature",
            "warning": "Update ChirpStack with this new secret immediately! Old secret is now inactive."
        }

    except Exception as e:
        logger.error(f"Error rotating webhook secret: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate webhook secret"
        )

# ============================================================
# Orphan Device Management
# ============================================================

@router.get("/orphan-devices", summary="List Orphan Devices")
async def list_orphan_devices(
    include_assigned: bool = Query(False, description="Include devices already assigned"),
    since_hours: Optional[int] = Query(None, description="Only show devices seen in last N hours"),
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """
    List orphan devices (devices sending uplinks but not assigned to spaces)

    Requires: ADMIN role or higher

    This helps with device provisioning by showing which devices are transmitting
    but not yet configured in the system.
    """
    try:
        orphans = await get_orphan_devices(db, include_assigned, since_hours)

        return {
            "orphan_devices": orphans,
            "count": len(orphans),
            "filters": {
                "include_assigned": include_assigned,
                "since_hours": since_hours
            }
        }

    except Exception as e:
        logger.error(f"Error listing orphan devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list orphan devices"
        )

@router.post("/orphan-devices/{device_eui}/assign", summary="Assign Orphan Device")
async def assign_orphan(
    device_eui: str,
    space_id: UUID,
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """
    Mark an orphan device as assigned to a space (requires ADMIN role)

    Note: This only updates the tracking record. You still need to update
    the space's sensor_eui field separately.
    """
    try:
        success = await assign_orphan_device(db, device_eui, str(space_id))

        if success:
            return {
                "message": "Orphan device marked as assigned",
                "device_eui": device_eui,
                "space_id": str(space_id)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orphan device {device_eui} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning orphan device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign orphan device"
        )

@router.delete("/orphan-devices/{device_eui}", summary="Delete Orphan Device")
async def delete_orphan(
    device_eui: str,
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """
    Delete an orphan device record (requires ADMIN role)

    Use this to clean up orphan records for devices that have been decommissioned
    or were added by mistake.
    """
    try:
        success = await delete_orphan_device(db, device_eui)

        if success:
            return {
                "message": "Orphan device deleted",
                "device_eui": device_eui
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orphan device {device_eui} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting orphan device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete orphan device"
        )
