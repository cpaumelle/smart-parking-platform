"""
Sites Router - v5.3 Multi-Tenant Parking API
Manages physical locations/buildings/campuses (sites) that contain parking spaces.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..models import TenantContext
from ..tenant_auth import get_current_tenant, require_viewer, require_admin
from ..api_scopes import require_scopes

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/sites",
    tags=["sites"]
)

# ============================================================================
# Pydantic Models
# ============================================================================

class SiteBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Site name (e.g., 'Building A', 'Downtown Garage')")
    timezone: str = Field(default="UTC", max_length=50, description="IANA timezone (e.g., 'America/Los_Angeles')")
    location: Optional[dict] = Field(default=None, description="GPS coordinates and address as JSON")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata as JSON")
    is_active: bool = Field(default=True, description="Whether the site is active")

class SiteCreate(SiteBase):
    """Request model for creating a new site"""
    pass

class SiteUpdate(BaseModel):
    """Request model for updating a site (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)
    location: Optional[dict] = None
    metadata: Optional[dict] = None
    is_active: Optional[bool] = None

class SiteResponse(SiteBase):
    """Response model for a site"""
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    spaces_count: Optional[int] = Field(default=0, description="Number of parking spaces in this site")

    class Config:
        from_attributes = True

class SitesListResponse(BaseModel):
    """Response model for list of sites"""
    sites: List[SiteResponse]
    total: int

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=SitesListResponse, dependencies=[Depends(require_scopes("sites:read"))])
async def list_sites(
    request: Request,
    include_inactive: bool = Query(False, description="Include inactive sites"),
    tenant: TenantContext = Depends(require_viewer)
):
    """
    List all sites for the current tenant.

    Returns sites with spaces count.
    """
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        # Set tenant context for RLS
        await conn.execute(f"SET app.current_tenant = '{tenant.tenant_id}'")

        # Build query
        active_filter = "" if include_inactive else "AND s.is_active = true"

        query = f"""
            SELECT
                s.id,
                s.tenant_id,
                s.name,
                s.timezone,
                s.location,
                s.metadata,
                s.is_active,
                s.created_at,
                s.updated_at,
                COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL) AS spaces_count
            FROM sites s
            LEFT JOIN spaces sp ON s.id = sp.site_id
            WHERE s.tenant_id = $1 {active_filter}
            GROUP BY s.id
            ORDER BY s.name ASC
        """

        rows = await conn.fetch(query, tenant.tenant_id)

        sites = [
            {
                "id": str(row["id"]),
                "tenant_id": str(row["tenant_id"]),
                "name": row["name"],
                "timezone": row["timezone"],
                "location": row["location"] if isinstance(row["location"], dict) else None,
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "spaces_count": row["spaces_count"] or 0
            }
            for row in rows
        ]

        logger.info(f"[Tenant:{tenant.tenant_id}] Listed {len(sites)} sites")
        return {"sites": sites, "total": len(sites)}


@router.post("/", response_model=SiteResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_scopes("sites:write")), Depends(require_admin)])
async def create_site(
    request: Request,
    site: SiteCreate,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Create a new site (requires admin role).

    Sites are physical locations/buildings that contain parking spaces.
    """
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        # Set tenant context for RLS
        await conn.execute(f"SET app.current_tenant = '{tenant.tenant_id}'")

        # Check for duplicate name within tenant
        existing = await conn.fetchrow(
            "SELECT id FROM sites WHERE tenant_id = $1 AND name = $2",
            tenant.tenant_id, site.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Site with name '{site.name}' already exists for this tenant"
            )

        # Insert site
        query = """
            INSERT INTO sites (tenant_id, name, timezone, location, metadata, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
        """

        row = await conn.fetchrow(
            query,
            tenant.tenant_id,
            site.name,
            site.timezone,
            site.location,
            site.metadata,
            site.is_active
        )

        result = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
            "timezone": row["timezone"],
            "location": row["location"] if isinstance(row["location"], dict) else None,
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
            "is_active": row["is_active"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "spaces_count": 0
        }

        logger.info(f"[Tenant:{tenant.tenant_id}] Created site: {site.name} (id={result['id']})")
        return result


@router.get("/{site_id}", response_model=SiteResponse, dependencies=[Depends(require_scopes("sites:read"))])
async def get_site(
    request: Request,
    site_id: UUID,
    tenant: TenantContext = Depends(require_viewer)
):
    """
    Get a single site by ID.
    """
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        # Set tenant context for RLS
        await conn.execute(f"SET app.current_tenant = '{tenant.tenant_id}'")

        query = """
            SELECT
                s.id,
                s.tenant_id,
                s.name,
                s.timezone,
                s.location,
                s.metadata,
                s.is_active,
                s.created_at,
                s.updated_at,
                COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL) AS spaces_count
            FROM sites s
            LEFT JOIN spaces sp ON s.id = sp.site_id
            WHERE s.id = $1 AND s.tenant_id = $2
            GROUP BY s.id
        """

        row = await conn.fetchrow(query, site_id, tenant.tenant_id)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site {site_id} not found"
            )

        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
            "timezone": row["timezone"],
            "location": row["location"] if isinstance(row["location"], dict) else None,
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
            "is_active": row["is_active"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "spaces_count": row["spaces_count"] or 0
        }


@router.patch("/{site_id}", response_model=SiteResponse, dependencies=[Depends(require_scopes("sites:write")), Depends(require_admin)])
async def update_site(
    request: Request,
    site_id: UUID,
    updates: SiteUpdate,
    tenant: TenantContext = Depends(require_admin)
):
    """
    Update a site (requires admin role).

    Only provided fields will be updated.
    """
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        # Set tenant context for RLS
        await conn.execute(f"SET app.current_tenant = '{tenant.tenant_id}'")

        # Check site exists and belongs to tenant
        existing = await conn.fetchrow(
            "SELECT id FROM sites WHERE id = $1 AND tenant_id = $2",
            site_id, tenant.tenant_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site {site_id} not found"
            )

        # Build dynamic update query
        update_fields = []
        params = [site_id, tenant.tenant_id]
        param_count = 3

        if updates.name is not None:
            # Check for duplicate name
            dup = await conn.fetchrow(
                "SELECT id FROM sites WHERE tenant_id = $1 AND name = $2 AND id != $3",
                tenant.tenant_id, updates.name, site_id
            )
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Site with name '{updates.name}' already exists"
                )
            update_fields.append(f"name = ${param_count}")
            params.append(updates.name)
            param_count += 1

        if updates.timezone is not None:
            update_fields.append(f"timezone = ${param_count}")
            params.append(updates.timezone)
            param_count += 1

        if updates.location is not None:
            update_fields.append(f"location = ${param_count}")
            params.append(updates.location)
            param_count += 1

        if updates.metadata is not None:
            update_fields.append(f"metadata = ${param_count}")
            params.append(updates.metadata)
            param_count += 1

        if updates.is_active is not None:
            update_fields.append(f"is_active = ${param_count}")
            params.append(updates.is_active)
            param_count += 1

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        query = f"""
            UPDATE sites
            SET {', '.join(update_fields)}
            WHERE id = $1 AND tenant_id = $2
            RETURNING id, tenant_id, name, timezone, location, metadata, is_active, created_at, updated_at
        """

        row = await conn.fetchrow(query, *params)

        # Get spaces count
        spaces_count = await conn.fetchval(
            "SELECT COUNT(*) FROM spaces WHERE site_id = $1 AND deleted_at IS NULL",
            site_id
        )

        result = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
            "timezone": row["timezone"],
            "location": row["location"] if isinstance(row["location"], dict) else None,
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
            "is_active": row["is_active"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "spaces_count": spaces_count or 0
        }

        logger.info(f"[Tenant:{tenant.tenant_id}] Updated site {site_id}")
        return result


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_scopes("sites:write")), Depends(require_admin)])
async def delete_site(
    request: Request,
    site_id: UUID,
    force: bool = Query(False, description="Force delete even if site has parking spaces"),
    tenant: TenantContext = Depends(require_admin)
):
    """
    Delete a site (soft delete by setting is_active=false).

    By default, fails if site has parking spaces. Use force=true to allow deletion.
    """
    db_pool = request.app.state.db_pool
    async with db_pool.acquire() as conn:
        # Set tenant context for RLS
        await conn.execute(f"SET app.current_tenant = '{tenant.tenant_id}'")

        # Check site exists
        existing = await conn.fetchrow(
            "SELECT id FROM sites WHERE id = $1 AND tenant_id = $2",
            site_id, tenant.tenant_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site {site_id} not found"
            )

        # Check for spaces
        if not force:
            spaces_count = await conn.fetchval(
                "SELECT COUNT(*) FROM spaces WHERE site_id = $1 AND deleted_at IS NULL",
                site_id
            )
            if spaces_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot delete site with {spaces_count} parking spaces. Use force=true to override."
                )

        # Soft delete (set is_active=false)
        await conn.execute(
            "UPDATE sites SET is_active = false WHERE id = $1",
            site_id
        )

        logger.info(f"[Tenant:{tenant.tenant_id}] Deleted site {site_id} (force={force})")
        return None
