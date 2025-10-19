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

        # Create JWT token
        access_token = create_access_token(
            user_id=user_row['id'],
            tenant_id=primary_tenant['id'],
            role=UserRole(primary_tenant['role'])
        )

        # Update last login
        await db.execute("""
            UPDATE users SET last_login_at = NOW() WHERE id = $1
        """, user_row['id'])

        logger.info(f"User {login_req.email} logged in successfully")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=60 * 24 * 60,  # 24 hours in seconds
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
# Site Management
# ============================================================

@router.get("/sites", response_model=List[Site], summary="List Sites", dependencies=[Depends(require_scopes("sites:read"))])
async def list_sites(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """List all sites in the current tenant (API key requires sites:read scope)"""
    rows = await db.fetch("""
        SELECT id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
        FROM sites
        WHERE tenant_id = $1 AND is_active = true
        ORDER BY created_at ASC
    """, tenant.tenant_id)

    return [Site(**dict(row)) for row in rows]

@router.post("/sites", response_model=Site, status_code=status.HTTP_201_CREATED, summary="Create Site", dependencies=[Depends(require_scopes("sites:write"))])
async def create_site(
    site_create: SiteCreate,
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """Create a new site (requires ADMIN role, API key requires sites:write scope)"""
    # Ensure site is created in current tenant
    if site_create.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create site in different tenant"
        )

    row = await db.fetchrow("""
        INSERT INTO sites (tenant_id, name, timezone, location, metadata)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
    """, site_create.tenant_id, site_create.name, site_create.timezone, site_create.location, site_create.metadata)

    return Site(**dict(row))

@router.get("/sites/{site_id}", response_model=Site, summary="Get Site", dependencies=[Depends(require_scopes("sites:read"))])
async def get_site(
    site_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Pool = Depends(get_db)
):
    """Get a specific site (API key requires sites:read scope)"""
    row = await db.fetchrow("""
        SELECT id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
        FROM sites
        WHERE id = $1 AND tenant_id = $2
    """, site_id, tenant.tenant_id)

    if not row:
        raise HTTPException(status_code=404, detail="Site not found")

    return Site(**dict(row))

@router.patch("/sites/{site_id}", response_model=Site, summary="Update Site", dependencies=[Depends(require_scopes("sites:write"))])
async def update_site(
    site_id: UUID,
    site_update: SiteUpdate,
    tenant: TenantContext = Depends(require_admin),
    db: Pool = Depends(get_db)
):
    """Update a site (requires ADMIN role, API key requires sites:write scope)"""
    # Verify site belongs to tenant
    existing = await db.fetchrow("SELECT id FROM sites WHERE id = $1 AND tenant_id = $2", site_id, tenant.tenant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Site not found")

    update_fields = []
    values = []
    param_count = 1

    for field, value in site_update.dict(exclude_unset=True).items():
        update_fields.append(f"{field} = ${param_count}")
        values.append(value)
        param_count += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.extend([site_id, tenant.tenant_id])
    query = f"""
        UPDATE sites
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = ${param_count} AND tenant_id = ${param_count + 1}
        RETURNING id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
    """

    row = await db.fetchrow(query, *values)
    return Site(**dict(row))

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
