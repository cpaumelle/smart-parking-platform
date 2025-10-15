# services/parking-display/app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
import sys
sys.path.append("/app")

from app.scheduler.scheduler import get_scheduler
from app.scheduler.reservation_manager import ReservationManager
from app.dependencies import get_authenticated_tenant
from app.utils.tenant_context import get_tenant_db

router = APIRouter()
logger = logging.getLogger("admin")


@router.get("/scheduler/status")
async def get_scheduler_status(auth = Depends(get_authenticated_tenant)):
    """
    Get APScheduler status and statistics (tenant-scoped)
    
    Returns:
        - scheduler_running: Boolean indicating if scheduler is active
        - total_jobs: Total number of scheduled jobs for this tenant
        - jobs_by_type: Breakdown by job type (activate/noshow/complete)
        - next_5_jobs: Next 5 upcoming jobs with timing
    """
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        # NOTE: Scheduler jobs are global (not tenant-filtered)
        # In multi-tenant setup, job_id should include tenant context
        # For Phase 3, returning all jobs (will enhance in Phase 4)
        
        # Sort jobs by next_run_time
        sorted_jobs = sorted(
            [j for j in jobs if j.next_run_time], 
            key=lambda j: j.next_run_time
        )
        
        logger.info(f"Scheduler status requested by tenant={auth.tenant_slug}")
        
        return {
            "status": "healthy" if scheduler.running else "unhealthy",
            "scheduler_running": scheduler.running,
            "total_jobs": len(jobs),
            "jobs_by_type": {
                "activate": len([j for j in jobs if j.id.startswith("activate_")]),
                "noshow": len([j for j in jobs if j.id.startswith("noshow_")]),
                "complete": len([j for j in jobs if j.id.startswith("complete_")])
            },
            "next_5_jobs": [
                {
                    "job_id": job.id,
                    "job_type": job.id.split("_")[0],
                    "reservation_id": "_".join(job.id.split("_")[1:]),
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in sorted_jobs[:5]
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler status (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/jobs/{reservation_id}")
async def get_reservation_jobs(
    reservation_id: str,
    auth = Depends(get_authenticated_tenant)
):
    """
    Get all scheduled jobs for a specific reservation (tenant-scoped)
    
    Args:
        reservation_id: UUID of the reservation
        
    Returns:
        List of jobs with their status and timing
    """
    try:
        # Verify reservation belongs to tenant
        async with get_tenant_db(auth.tenant_id) as db:
            reservation_check = await db.fetchval(
                "SELECT reservation_id FROM parking_spaces.reservations WHERE reservation_id = $1",
                reservation_id
            )
            
            if not reservation_check:
                # Either doesn't exist OR belongs to different tenant
                raise HTTPException(status_code=404, detail="Reservation not found")
        
        jobs = ReservationManager.get_reservation_jobs(reservation_id)
        
        return {
            "reservation_id": reservation_id,
            "jobs_found": len(jobs),
            "jobs": jobs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reservation jobs (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reservations/health")
async def reservation_system_health(auth = Depends(get_authenticated_tenant)):
    """
    Comprehensive health check for reservation system (tenant-scoped)
    
    Returns:
        - Scheduler status
        - Reservation statistics for this tenant (last 7 days)
        - Job counts by status
    """
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Get reservation statistics for this tenant only
            stats_query = """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'active') as active,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                    COUNT(*) FILTER (WHERE status = 'no_show') as no_show,
                    COUNT(*) FILTER (WHERE status = 'expired') as expired,
                    COUNT(*) as total
                FROM parking_spaces.reservations
                WHERE created_at > NOW() - INTERVAL '7 days'
            """
            stats = await db.fetchrow(stats_query)
        
        # Get scheduler status (global)
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        return {
            "status": "healthy" if scheduler.running else "degraded",
            "scheduler": {
                "running": scheduler.running,
                "total_scheduled_jobs": len(jobs),
                "jobs_by_type": {
                    "activate": len([j for j in jobs if j.id.startswith("activate_")]),
                    "noshow": len([j for j in jobs if j.id.startswith("noshow_")]),
                    "complete": len([j for j in jobs if j.id.startswith("complete_")])
                }
            },
            "reservations_last_7_days": {
                "total": stats["total"],
                "pending": stats["pending"],
                "active": stats["active"],
                "completed": stats["completed"],
                "cancelled": stats["cancelled"],
                "no_show": stats["no_show"],
                "expired": stats["expired"]
            },
            "tenant": auth.tenant_slug,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking reservation health (tenant={auth.tenant_slug}): {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/scheduler/jobs")
async def list_all_jobs(auth = Depends(get_authenticated_tenant)):
    """
    List all currently scheduled jobs (global view for monitoring)
    
    NOTE: For Phase 3, this shows all jobs (not filtered by tenant).
    Phase 4 will enhance to show only tenant-specific jobs.
    
    Returns:
        Complete list of all jobs in the scheduler
    """
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        job_list = []
        for job in jobs:
            job_list.append({
                "job_id": job.id,
                "job_type": job.id.split("_")[0],
                "reservation_id": "_".join(job.id.split("_")[1:]),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "func": job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
            })
        
        # Sort by next_run_time
        job_list.sort(key=lambda x: x["next_run_time"] or "9999-99-99")
        
        logger.info(f"All jobs listed by tenant={auth.tenant_slug}")
        
        return {
            "total_jobs": len(job_list),
            "jobs": job_list,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing jobs (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/reconcile")
async def trigger_reconciliation(auth = Depends(get_authenticated_tenant)):
    """
    Manual reconciliation trigger - sync DB reservations with scheduler jobs (tenant-scoped)
    
    This endpoint:
    1. Checks all active/pending reservations for this tenant in DB
    2. Verifies they have scheduled jobs
    3. Creates missing jobs if needed
    
    Returns:
        Summary of reconciliation actions
    """
    try:
        async with get_tenant_db(auth.tenant_id) as db:
            # Get all active and pending reservations for this tenant
            query = """
                SELECT 
                    reservation_id,
                    reserved_from,
                    reserved_until,
                    grace_period_minutes,
                    status
                FROM parking_spaces.reservations
                WHERE status IN ('pending', 'active')
                ORDER BY reserved_from
            """
            reservations = await db.fetch(query)
        
        scheduler = get_scheduler()
        existing_job_ids = [job.id for job in scheduler.get_jobs()]
        
        missing_jobs = []
        existing_jobs = []
        
        for res in reservations:
            res_id = str(res["reservation_id"])
            
            # Check if jobs exist
            activate_job_id = f"activate_{res_id}"
            noshow_job_id = f"noshow_{res_id}"
            complete_job_id = f"complete_{res_id}"
            
            has_activate = activate_job_id in existing_job_ids
            has_noshow = noshow_job_id in existing_job_ids
            has_complete = complete_job_id in existing_job_ids
            
            if not (has_activate and has_noshow and has_complete):
                missing_jobs.append({
                    "reservation_id": res_id,
                    "status": res["status"],
                    "missing": {
                        "activate": not has_activate,
                        "noshow": not has_noshow,
                        "complete": not has_complete
                    }
                })
                
                # Re-schedule missing jobs
                ReservationManager.schedule_reservation_lifecycle(
                    reservation_id=res_id,
                    reserved_from=res["reserved_from"],
                    reserved_until=res["reserved_until"],
                    grace_period_minutes=res["grace_period_minutes"] or 15
                )
            else:
                existing_jobs.append(res_id)
        
        logger.info(f"Reconciliation complete for tenant={auth.tenant_slug}: {len(missing_jobs)} jobs recreated")
        
        return {
            "status": "reconciliation_complete",
            "tenant": auth.tenant_slug,
            "total_reservations_checked": len(reservations),
            "reservations_with_all_jobs": len(existing_jobs),
            "reservations_with_missing_jobs": len(missing_jobs),
            "missing_jobs_details": missing_jobs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during reconciliation (tenant={auth.tenant_slug}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# API Key Management Endpoints
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from app.utils.api_keys import generate_and_hash_api_key
from app.database import get_db_pool
import bcrypt
from app.utils.audit import AuditLogger


class CreateAPIKeyRequest(BaseModel):
    tenant_id: UUID
    key_name: str = Field(..., min_length=1, max_length=100, description="Descriptive name for the API key")
    scopes: List[str] = Field(default=["read", "write"], description="API key permissions")
    expires_days: Optional[int] = Field(default=None, description="Days until expiration (null = never)")


class APIKeyResponse(BaseModel):
    api_key_id: UUID
    tenant_id: UUID
    tenant_slug: str
    key_name: str
    key_prefix: str  # First 12 chars for identification
    scopes: List[str]
    is_active: bool
    created_at: str
    expires_at: Optional[str]
    last_used_at: Optional[str]


class CreateAPIKeyResponse(BaseModel):
    api_key_id: UUID
    tenant_slug: str
    key_name: str
    api_key: str  # Full key - ONLY returned on creation!
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[str]
    created_at: str
    warning: str = "Save this API key now - it will not be shown again!"


@router.post("/api-keys", response_model=CreateAPIKeyResponse, status_code=201)
async def create_api_key(
    request: CreateAPIKeyRequest,
    auth = Depends(get_authenticated_tenant)
):
    """
    Create a new API key for a tenant.
    
    **SECURITY**: Only system admins or the tenant themselves can create keys.
    For Phase 3.2, allowing authenticated tenants to create their own keys.
    
    Args:
        request: API key creation parameters
        
    Returns:
        Full API key (ONLY time it's shown!) and metadata
        
    **WARNING**: The full API key is only returned once. Store it securely!
    """
    try:
        db_pool = get_db_pool()
        
        # Generate new API key
        api_key, key_hash = generate_and_hash_api_key(prefix="sp_live_")
        
        # Insert into database
        async with db_pool.acquire() as conn:
            # Verify tenant exists
            tenant = await conn.fetchrow(
                "SELECT tenant_id, tenant_slug FROM core.tenants WHERE tenant_id = $1",
                str(request.tenant_id)
            )
            
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            
            # Check authorization - tenant can only create keys for themselves
            if str(auth.tenant_id) != str(request.tenant_id):
                raise HTTPException(
                    status_code=403, 
                    detail="Cannot create API keys for other tenants"
                )
            
            # Calculate expiration
            expires_at = None
            if request.expires_days:
                expires_at = f"NOW() + INTERVAL '{request.expires_days} days'"
            
            query = f"""
                INSERT INTO core.api_keys (
                    tenant_id, key_name, key_hash, key_prefix, scopes, is_active, expires_at
                )
                VALUES ($1, $2, $3, $4, $5, TRUE, {expires_at or 'NULL'})
                RETURNING api_key_id, created_at, expires_at
            """
            
            result = await conn.fetchrow(
                query,
                str(request.tenant_id),
                request.key_name,
                key_hash,
                api_key[:12],
                request.scopes
            )
        
        logger.info(
            f"✅ API key created: tenant={tenant['tenant_slug']} "
            f"key_name={request.key_name} by={auth.tenant_slug}"
        )
        AuditLogger.log_api_key_created(db_pool, auth.tenant_id, tenant['tenant_slug'], result['api_key_id'], request.key_name, auth.tenant_slug)
        
        return CreateAPIKeyResponse(
            api_key_id=result['api_key_id'],
            tenant_slug=tenant['tenant_slug'],
            key_name=request.key_name,
            api_key=api_key,  # Full key - ONLY shown here!
            key_prefix=api_key[:12],
            scopes=request.scopes,
            expires_at=result['expires_at'].isoformat() if result['expires_at'] else None,
            created_at=result['created_at'].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    tenant_id: Optional[UUID] = None,
    include_revoked: bool = False,
    auth = Depends(get_authenticated_tenant)
):
    """
    List API keys for a tenant.
    
    **SECURITY**: Tenants can only see their own keys.
    
    Args:
        tenant_id: Filter by tenant (defaults to authenticated tenant)
        include_revoked: Include revoked keys in results
        
    Returns:
        List of API keys (without full key value)
    """
    try:
        db_pool = get_db_pool()
        
        # Default to authenticated tenant
        target_tenant_id = tenant_id or auth.tenant_id
        
        # Check authorization
        if str(auth.tenant_id) != str(target_tenant_id):
            raise HTTPException(
                status_code=403,
                detail="Cannot view API keys for other tenants"
            )
        
        async with db_pool.acquire() as conn:
            # Build query
            query = """
                SELECT 
                    ak.api_key_id,
                    ak.tenant_id,
                    t.tenant_slug,
                    ak.key_name,
                    ak.key_hash,
                    ak.scopes,
                    ak.is_active,
                    ak.created_at,
                    ak.expires_at,
                    ak.last_used_at
                FROM core.api_keys ak
                JOIN core.tenants t ON ak.tenant_id = t.tenant_id
                WHERE ak.tenant_id = $1
            """
            
            if not include_revoked:
                query += " AND ak.is_active = TRUE"
            
            query += " ORDER BY ak.created_at DESC"
            
            results = await conn.fetch(query, str(target_tenant_id))
        
        # Format results
        api_keys = []
        for row in results:
            # Extract key prefix from hash (first 12 chars of original key)
            # We can't recover it from hash, so we'll show a placeholder
            key_prefix = "sp_live_***"
            
            api_keys.append(APIKeyResponse(
                api_key_id=row['api_key_id'],
                tenant_id=row['tenant_id'],
                tenant_slug=row['tenant_slug'],
                key_name=row['key_name'],
                key_prefix=key_prefix,
                scopes=row['scopes'],
                is_active=row['is_active'],
                created_at=row['created_at'].isoformat(),
                expires_at=row['expires_at'].isoformat() if row['expires_at'] else None,
                last_used_at=row['last_used_at'].isoformat() if row['last_used_at'] else None
            ))
        
        logger.info(f"Listed {len(api_keys)} API keys for tenant={auth.tenant_slug}")
        
        return api_keys
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/api-keys/{key_id}", status_code=200)
async def revoke_api_key(
    key_id: UUID,
    auth = Depends(get_authenticated_tenant)
):
    """
    Revoke (deactivate) an API key.
    
    **SECURITY**: Tenants can only revoke their own keys.
    
    Args:
        key_id: UUID of the API key to revoke
        
    Returns:
        Confirmation message
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            # Check key exists and belongs to tenant
            key_check = await conn.fetchrow(
                """
                SELECT ak.api_key_id, ak.tenant_id, t.tenant_slug, ak.key_name, ak.is_active
                FROM core.api_keys ak
                JOIN core.tenants t ON ak.tenant_id = t.tenant_id
                WHERE ak.api_key_id = $1
                """,
                str(key_id)
            )
            
            if not key_check:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Check authorization
            if str(auth.tenant_id) != str(key_check['tenant_id']):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot revoke API keys for other tenants"
                )
            
            if not key_check['is_active']:
                raise HTTPException(status_code=400, detail="API key already revoked")
            
            # Revoke the key
            await conn.execute(
                "UPDATE core.api_keys SET is_active = FALSE WHERE api_key_id = $1",
                str(key_id)
            )
        
        logger.warning(
            f"🔑 API key revoked: key_id={key_id} key_name={key_check['key_name']} "
            f"tenant={key_check['tenant_slug']} by={auth.tenant_slug}"
        )
        AuditLogger.log_api_key_revoked(db_pool, auth.tenant_id, key_check['tenant_slug'], key_id, key_check['key_name'], auth.tenant_slug)
        
        return {
            "status": "revoked",
            "api_key_id": str(key_id),
            "key_name": key_check['key_name'],
            "tenant_slug": key_check['tenant_slug'],
            "message": "API key successfully revoked",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.get("/api-keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key_details(
    key_id: UUID,
    auth = Depends(get_authenticated_tenant)
):
    """
    Get details for a specific API key.
    
    **SECURITY**: Tenants can only view their own keys.
    
    Args:
        key_id: UUID of the API key
        
    Returns:
        API key metadata (without full key value)
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT 
                    ak.api_key_id,
                    ak.tenant_id,
                    t.tenant_slug,
                    ak.key_name,
                    ak.scopes,
                    ak.is_active,
                    ak.created_at,
                    ak.expires_at,
                    ak.last_used_at
                FROM core.api_keys ak
                JOIN core.tenants t ON ak.tenant_id = t.tenant_id
                WHERE ak.api_key_id = $1
                """,
                str(key_id)
            )
            
            if not result:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Check authorization
            if str(auth.tenant_id) != str(result['tenant_id']):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot view API keys for other tenants"
                )
        
        return APIKeyResponse(
            api_key_id=result['api_key_id'],
            tenant_id=result['tenant_id'],
            tenant_slug=result['tenant_slug'],
            key_name=result['key_name'],
            key_prefix="sp_live_***",
            scopes=result['scopes'],
            is_active=result['is_active'],
            created_at=result['created_at'].isoformat(),
            expires_at=result['expires_at'].isoformat() if result['expires_at'] else None,
            last_used_at=result['last_used_at'].isoformat() if result['last_used_at'] else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API key details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get API key details")


@router.post("/api-keys/{key_id}/rotate", response_model=CreateAPIKeyResponse, status_code=201)
async def rotate_api_key(
    key_id: UUID,
    auth = Depends(get_authenticated_tenant)
):
    """
    Rotate an API key - creates new key and revokes old one.
    
    **SECURITY**: Tenants can only rotate their own keys.
    
    This operation:
    1. Generates a new API key
    2. Creates new database entry
    3. Revokes the old key
    4. Returns the new key (ONLY time it's shown!)
    
    Args:
        key_id: UUID of the API key to rotate
        
    Returns:
        New API key (ONLY shown once!)
        
    **WARNING**: The new key is only returned once. Store it securely!
    The old key will be immediately revoked.
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            # Get existing key details
            old_key = await conn.fetchrow(
                """
                SELECT ak.api_key_id, ak.tenant_id, t.tenant_slug, ak.key_name, 
                       ak.scopes, ak.expires_at, ak.is_active
                FROM core.api_keys ak
                JOIN core.tenants t ON ak.tenant_id = t.tenant_id
                WHERE ak.api_key_id = $1
                """,
                str(key_id)
            )
            
            if not old_key:
                raise HTTPException(status_code=404, detail="API key not found")
            
            # Check authorization
            if str(auth.tenant_id) != str(old_key['tenant_id']):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot rotate API keys for other tenants"
                )
            
            if not old_key['is_active']:
                raise HTTPException(status_code=400, detail="Cannot rotate revoked API key")
            
            # Generate new API key
            new_api_key, new_key_hash = generate_and_hash_api_key(prefix="sp_live_")
            
            # Begin transaction
            async with conn.transaction():
                # Create new key (same name with " (rotated)" suffix)
                new_key_name = f"{old_key['key_name']} (rotated)"
                
                new_result = await conn.fetchrow(
                    """
                    INSERT INTO core.api_keys (
                        tenant_id, key_name, key_hash, key_prefix, scopes, is_active, expires_at
                    )
                    VALUES ($1, $2, $3, $4, $5, TRUE, $6)
                    RETURNING api_key_id, created_at, expires_at
                    """,
                    str(old_key['tenant_id']),
                    new_key_name,
                    new_key_hash,
                    new_api_key[:12],
                    old_key['scopes'],
                    old_key['expires_at']
                )
                
                # Revoke old key
                await conn.execute(
                    "UPDATE core.api_keys SET is_active = FALSE WHERE api_key_id = $1",
                    str(key_id)
                )
        
        logger.warning(
            f"🔄 API key rotated: old_key_id={key_id} new_key_id={new_result['api_key_id']} "
            f"tenant={old_key['tenant_slug']} by={auth.tenant_slug}"
        )
        AuditLogger.log_api_key_rotated(db_pool, auth.tenant_id, old_key['tenant_slug'], key_id, new_result['api_key_id'], new_key_name, auth.tenant_slug)
        
        return CreateAPIKeyResponse(
            api_key_id=new_result['api_key_id'],
            tenant_slug=old_key['tenant_slug'],
            key_name=new_key_name,
            api_key=new_api_key,  # Full key - ONLY shown here!
            key_prefix=new_api_key[:12],
            scopes=old_key['scopes'],
            expires_at=new_result['expires_at'].isoformat() if new_result['expires_at'] else None,
            created_at=new_result['created_at'].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rotating API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to rotate API key")

# ============================================================================
# API Usage Tracking Endpoints (Phase 3.2)
# ============================================================================

@router.get("/usage/summary")
async def get_usage_summary(
    hours: int = 24,
    auth = Depends(get_authenticated_tenant)
):
    """
    Get API usage summary for authenticated tenant.
    
    Args:
        hours: Number of hours to look back (default 24)
        
    Returns:
        Usage statistics including:
        - Total requests
        - Success/failure counts  
        - Average response time
        - Requests per endpoint
        - Requests per hour
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM core.get_tenant_usage_summary($1::UUID, $2)
                """,
                str(auth.tenant_id),
                hours
            )
        
        if not result:
            return {
                "tenant": auth.tenant_slug,
                "period_hours": hours,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_response_time_ms": 0,
                "requests_per_endpoint": {},
                "requests_per_hour": {}
            }
        
        return {
            "tenant": auth.tenant_slug,
            "period_hours": hours,
            "total_requests": result["total_requests"],
            "successful_requests": result["successful_requests"],
            "failed_requests": result["failed_requests"],
            "avg_response_time_ms": float(result["avg_response_time_ms"]) if result["avg_response_time_ms"] else 0,
            "requests_per_endpoint": result["requests_per_endpoint"] or {},
            "requests_per_hour": result["requests_per_hour"] or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting usage summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get usage summary")


@router.get("/usage/rate-limit-status")
async def get_rate_limit_status(
    auth = Depends(get_authenticated_tenant)
):
    """
    Check current rate limit status for tenant.
    
    Returns:
        Current request count and limit status
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM core.check_rate_limit($1::UUID, 60, 1000)
                """,
                str(auth.tenant_id)
            )
        
        return {
            "tenant": auth.tenant_slug,
            "window_minutes": 60,
            "max_requests": 1000,
            "current_requests": result["request_count"],
            "limit_exceeded": result["limit_exceeded"],
            "window_start": result["window_start"].isoformat(),
            "window_end": result["window_end"].isoformat(),
            "requests_remaining": max(0, 1000 - result["request_count"]),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check rate limit")

# ============================================================================
# Audit Log Endpoints (Phase 3.2)
# ============================================================================

@router.get("/audit/events")
async def get_audit_events(
    hours: int = 24,
    severity: Optional[str] = None,
    auth = Depends(get_authenticated_tenant)
):
    """
    Get recent security audit events for authenticated tenant.
    
    Args:
        hours: Number of hours to look back (default 24)
        severity: Filter by severity (info, warning, error, critical)
        
    Returns:
        List of audit events with details
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT * FROM core.get_recent_security_events($1::UUID, $2, $3::core.audit_severity)
                """,
                str(auth.tenant_id),
                hours,
                severity
            )
        
        events = []
        for row in results:
            events.append({
                "audit_id": row["audit_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "event_description": row["event_description"],
                "event_details": row["event_details"],
                "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "created_at": row["created_at"].isoformat()
            })
        
        return {
            "tenant": auth.tenant_slug,
            "period_hours": hours,
            "severity_filter": severity,
            "total_events": len(events),
            "events": events,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting audit events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get audit events")


@router.get("/audit/statistics")
async def get_audit_statistics(
    hours: int = 24,
    auth = Depends(get_authenticated_tenant)
):
    """
    Get audit statistics for authenticated tenant.
    
    Args:
        hours: Number of hours to look back (default 24)
        
    Returns:
        Summary statistics of audit events
    """
    try:
        db_pool = get_db_pool()
        
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM core.get_audit_statistics($1::UUID, $2)
                """,
                str(auth.tenant_id),
                hours
            )
        
        if not result:
            return {
                "tenant": auth.tenant_slug,
                "period_hours": hours,
                "total_events": 0,
                "auth_failures": 0,
                "security_alerts": 0,
                "api_key_changes": 0,
                "events_by_type": {},
                "events_by_severity": {}
            }
        
        return {
            "tenant": auth.tenant_slug,
            "period_hours": hours,
            "total_events": result["total_events"],
            "auth_failures": result["auth_failures"],
            "security_alerts": result["security_alerts"],
            "api_key_changes": result["api_key_changes"],
            "events_by_type": result["events_by_type"] or {},
            "events_by_severity": result["events_by_severity"] or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting audit statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get audit statistics")
