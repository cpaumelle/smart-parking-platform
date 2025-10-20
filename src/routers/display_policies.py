# src/routers/display_policies.py
# Display Policy Management API for V5.3 Smart Parking Platform

from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/display-policies", tags=["display-policies"])


# ============================================================
# Request/Response Models
# ============================================================

class DisplayPolicyBase(BaseModel):
    """Base display policy fields"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

    # Thresholds
    reserved_soon_threshold_sec: int = Field(900, ge=0, le=3600, description="Show reserved_soon this many seconds before reservation (0-3600)")
    sensor_unknown_timeout_sec: int = Field(60, ge=0, le=300, description="Hold last stable state for this many seconds (0-300)")
    debounce_window_sec: int = Field(10, ge=5, le=30, description="Require 2 readings within this window (5-30)")

    # Colors (hex RGB)
    occupied_color: str = Field("FF0000", regex="^[0-9A-Fa-f]{6}$")
    free_color: str = Field("00FF00", regex="^[0-9A-Fa-f]{6}$")
    reserved_color: str = Field("FFA500", regex="^[0-9A-Fa-f]{6}$")
    reserved_soon_color: str = Field("FFFF00", regex="^[0-9A-Fa-f]{6}$")
    blocked_color: str = Field("808080", regex="^[0-9A-Fa-f]{6}$")
    out_of_service_color: str = Field("800080", regex="^[0-9A-Fa-f]{6}$")

    # Behaviors
    blink_reserved_soon: bool = False
    blink_pattern_ms: int = Field(500, ge=100, le=2000)
    allow_sensor_override: bool = True


class DisplayPolicyCreate(DisplayPolicyBase):
    """Request model for creating a display policy"""
    pass


class DisplayPolicyUpdate(BaseModel):
    """Request model for updating a display policy (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None

    reserved_soon_threshold_sec: Optional[int] = Field(None, ge=0, le=3600)
    sensor_unknown_timeout_sec: Optional[int] = Field(None, ge=0, le=300)
    debounce_window_sec: Optional[int] = Field(None, ge=5, le=30)

    occupied_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")
    free_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")
    reserved_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")
    reserved_soon_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")
    blocked_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")
    out_of_service_color: Optional[str] = Field(None, regex="^[0-9A-Fa-f]{6}$")

    blink_reserved_soon: Optional[bool] = None
    blink_pattern_ms: Optional[int] = Field(None, ge=100, le=2000)
    allow_sensor_override: Optional[bool] = None


class AdminOverrideCreate(BaseModel):
    """Request model for creating an admin override"""
    space_id: uuid.UUID
    override_type: str = Field(..., regex="^(blocked|out_of_service)$")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# Display Policy Endpoints
# ============================================================

@router.get("/", response_model=List[Dict[str, Any]])
async def list_display_policies(
    request: Request,
    tenant_id: Optional[uuid.UUID] = None
):
    """
    List display policies

    If tenant_id is provided, returns policies for that tenant.
    Otherwise, returns all policies (admin only).
    """
    try:
        db_pool = request.app.state.db_pool

        # TODO: Add tenant_id extraction from JWT/API key
        # For now, require tenant_id parameter

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id parameter is required"
            )

        query = """
            SELECT
                id, tenant_id, name, description, is_active,
                reserved_soon_threshold_sec, sensor_unknown_timeout_sec, debounce_window_sec,
                occupied_color, free_color, reserved_color, reserved_soon_color,
                blocked_color, out_of_service_color,
                blink_reserved_soon, blink_pattern_ms, allow_sensor_override,
                created_at, updated_at
            FROM display_policies
            WHERE tenant_id = $1
            ORDER BY is_active DESC, created_at DESC
        """

        rows = await db_pool.fetch(query, tenant_id)

        policies = []
        for row in rows:
            policies.append({
                "id": str(row['id']),
                "tenant_id": str(row['tenant_id']),
                "name": row['name'],
                "description": row['description'],
                "is_active": row['is_active'],
                "thresholds": {
                    "reserved_soon_threshold_sec": row['reserved_soon_threshold_sec'],
                    "sensor_unknown_timeout_sec": row['sensor_unknown_timeout_sec'],
                    "debounce_window_sec": row['debounce_window_sec']
                },
                "colors": {
                    "occupied": row['occupied_color'],
                    "free": row['free_color'],
                    "reserved": row['reserved_color'],
                    "reserved_soon": row['reserved_soon_color'],
                    "blocked": row['blocked_color'],
                    "out_of_service": row['out_of_service_color']
                },
                "behaviors": {
                    "blink_reserved_soon": row['blink_reserved_soon'],
                    "blink_pattern_ms": row['blink_pattern_ms'],
                    "allow_sensor_override": row['allow_sensor_override']
                },
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
            })

        return policies

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list display policies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{policy_id}", response_model=Dict[str, Any])
async def get_display_policy(
    request: Request,
    policy_id: uuid.UUID
):
    """Get details of a specific display policy"""
    try:
        db_pool = request.app.state.db_pool

        row = await db_pool.fetchrow("""
            SELECT * FROM display_policies WHERE id = $1
        """, policy_id)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Display policy {policy_id} not found"
            )

        return {
            "id": str(row['id']),
            "tenant_id": str(row['tenant_id']),
            "name": row['name'],
            "description": row['description'],
            "is_active": row['is_active'],
            "thresholds": {
                "reserved_soon_threshold_sec": row['reserved_soon_threshold_sec'],
                "sensor_unknown_timeout_sec": row['sensor_unknown_timeout_sec'],
                "debounce_window_sec": row['debounce_window_sec']
            },
            "colors": {
                "occupied": row['occupied_color'],
                "free": row['free_color'],
                "reserved": row['reserved_color'],
                "reserved_soon": row['reserved_soon_color'],
                "blocked": row['blocked_color'],
                "out_of_service": row['out_of_service_color']
            },
            "behaviors": {
                "blink_reserved_soon": row['blink_reserved_soon'],
                "blink_pattern_ms": row['blink_pattern_ms'],
                "allow_sensor_override": row['allow_sensor_override']
            },
            "created_at": row['created_at'].isoformat(),
            "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get display policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_display_policy(
    request: Request,
    policy: DisplayPolicyCreate,
    tenant_id: uuid.UUID
):
    """
    Create a new display policy for a tenant

    Note: Only one policy can be active per tenant at a time.
    Creating a new active policy will deactivate the old one.
    """
    try:
        db_pool = request.app.state.db_pool

        # Verify tenant exists
        tenant = await db_pool.fetchrow("SELECT id FROM tenants WHERE id = $1", tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found"
            )

        # Create policy
        query = """
            INSERT INTO display_policies (
                tenant_id, name, description, is_active,
                reserved_soon_threshold_sec, sensor_unknown_timeout_sec, debounce_window_sec,
                occupied_color, free_color, reserved_color, reserved_soon_color,
                blocked_color, out_of_service_color,
                blink_reserved_soon, blink_pattern_ms, allow_sensor_override
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            RETURNING id, created_at
        """

        result = await db_pool.fetchrow(
            query,
            tenant_id,
            policy.name,
            policy.description,
            True,  # is_active (will deactivate others via constraint)
            policy.reserved_soon_threshold_sec,
            policy.sensor_unknown_timeout_sec,
            policy.debounce_window_sec,
            policy.occupied_color,
            policy.free_color,
            policy.reserved_color,
            policy.reserved_soon_color,
            policy.blocked_color,
            policy.out_of_service_color,
            policy.blink_reserved_soon,
            policy.blink_pattern_ms,
            policy.allow_sensor_override
        )

        # Invalidate policy cache + bump Redis version key for distributed cache coherence
        if hasattr(request.app.state, 'display_state_machine'):
            await request.app.state.display_state_machine.invalidate_policy_cache(str(tenant_id))

        # Bump Redis version key to invalidate all app-level caches
        if hasattr(request.app.state, 'redis_client'):
            redis_client = request.app.state.redis_client
            await redis_client.incr(f"display_policy:tenant:{tenant_id}:v")
            logger.info(f"Bumped policy version for tenant {tenant_id}")

        # Trigger recompute for all spaces
        if hasattr(request.app.state, 'display_state_machine'):
            recomputed = await request.app.state.display_state_machine.force_recompute_all_spaces(str(tenant_id))
            logger.info(f"Recomputed {recomputed} spaces after policy creation")

        return {
            "id": str(result['id']),
            "tenant_id": str(tenant_id),
            "name": policy.name,
            "created_at": result['created_at'].isoformat(),
            "message": "Display policy created successfully. All spaces will be recomputed."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create display policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{policy_id}")
async def update_display_policy(
    request: Request,
    policy_id: uuid.UUID,
    updates: DisplayPolicyUpdate
):
    """Update a display policy (partial update)"""
    try:
        db_pool = request.app.state.db_pool

        # Build update query dynamically
        update_fields = []
        params = [policy_id]
        param_idx = 2

        for field, value in updates.dict(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        update_fields.append(f"updated_at = NOW()")

        query = f"""
            UPDATE display_policies
            SET {', '.join(update_fields)}
            WHERE id = $1
            RETURNING id, tenant_id, name, updated_at
        """

        result = await db_pool.fetchrow(query, *params)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Display policy {policy_id} not found"
            )

        tenant_id = str(result['tenant_id'])

        # Invalidate cache + bump Redis version key
        if hasattr(request.app.state, 'display_state_machine'):
            await request.app.state.display_state_machine.invalidate_policy_cache(tenant_id)

        if hasattr(request.app.state, 'redis_client'):
            redis_client = request.app.state.redis_client
            await redis_client.incr(f"display_policy:tenant:{tenant_id}:v")
            logger.info(f"Bumped policy version for tenant {tenant_id}")

        # Trigger recompute
        if hasattr(request.app.state, 'display_state_machine'):
            recomputed = await request.app.state.display_state_machine.force_recompute_all_spaces(tenant_id)
            logger.info(f"Recomputed {recomputed} spaces after policy update")

        return {
            "id": str(result['id']),
            "tenant_id": tenant_id,
            "name": result['name'],
            "updated_at": result['updated_at'].isoformat(),
            "message": "Display policy updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update display policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================
# Admin Override Endpoints
# ============================================================

@router.post("/admin-overrides", status_code=status.HTTP_201_CREATED)
async def create_admin_override(
    request: Request,
    override: AdminOverrideCreate
):
    """
    Create an admin override for a parking space

    Override types:
    - blocked: Space temporarily unavailable (maintenance, etc.)
    - out_of_service: Space permanently offline

    These override all other states (reservations, sensors)
    """
    try:
        db_pool = request.app.state.db_pool

        # Verify space exists
        space = await db_pool.fetchrow("""
            SELECT id, tenant_id, code FROM spaces WHERE id = $1 AND deleted_at IS NULL
        """, override.space_id)

        if not space:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Space {override.space_id} not found"
            )

        tenant_id = space['tenant_id']

        # Create override
        result = await db_pool.fetchrow("""
            INSERT INTO space_admin_overrides (
                space_id, tenant_id, override_type,
                start_time, end_time, reason, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, created_at
        """,
            override.space_id,
            tenant_id,
            override.override_type,
            override.start_time or datetime.utcnow(),
            override.end_time,
            override.reason,
            override.notes
        )

        # Trigger display recompute for this space
        if hasattr(request.app.state, 'display_state_machine'):
            command = await request.app.state.display_state_machine.compute_display_command(
                str(override.space_id),
                str(tenant_id)
            )

            logger.info(
                f"Admin override created for space {space['code']}: "
                f"{override.override_type} -> {command.state} ({command.color})"
            )

        return {
            "id": str(result['id']),
            "space_id": str(override.space_id),
            "space_code": space['code'],
            "override_type": override.override_type,
            "created_at": result['created_at'].isoformat(),
            "message": f"Admin override '{override.override_type}' created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create admin override: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/admin-overrides/{override_id}")
async def delete_admin_override(
    request: Request,
    override_id: uuid.UUID
):
    """Remove an admin override"""
    try:
        db_pool = request.app.state.db_pool

        result = await db_pool.fetchrow("""
            UPDATE space_admin_overrides
            SET is_active = false
            WHERE id = $1
            RETURNING space_id, override_type
        """, override_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Admin override {override_id} not found"
            )

        # TODO: Trigger display recompute

        return {
            "id": str(override_id),
            "space_id": str(result['space_id']),
            "message": "Admin override removed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete admin override: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/spaces/{space_id}/computed-state", response_model=Dict[str, Any])
async def get_computed_display_state(
    request: Request,
    space_id: uuid.UUID
):
    """
    Get the computed display state for a space

    Shows the result of the state machine computation including:
    - Current state, color, blink behavior
    - Priority level and reason
    - Sensor debounce state
    - Active reservation status
    - Admin overrides
    """
    try:
        db_pool = request.app.state.db_pool

        # Get space info
        space = await db_pool.fetchrow("""
            SELECT * FROM v_space_display_states WHERE space_id = $1
        """, space_id)

        if not space:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Space {space_id} not found"
            )

        return {
            "space_id": str(space['space_id']),
            "space_code": space['space_code'],
            "space_name": space['space_name'],
            "tenant_id": str(space['tenant_id']),
            "db_state": space['db_state'],
            "computed_display": {
                "state": space['display_state'],
                "color": space['display_color'],
                "blink": space['display_blink'],
                "priority_level": space['priority_level'],
                "reason": space['reason']
            },
            "sensor": {
                "stable_state": space['stable_sensor_state'],
                "stable_since": space['stable_since'].isoformat() if space['stable_since'] else None
            },
            "has_active_reservation": bool(space['has_active_reservation']),
            "admin_override": space['admin_override'],
            "last_updated": space['last_display_updated_at'].isoformat() if space['last_display_updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get computed display state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
