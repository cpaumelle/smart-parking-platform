# services/parking-display/app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
import sys
sys.path.append("/app")

from app.scheduler.scheduler import get_scheduler
from app.scheduler.reservation_manager import ReservationManager
from app.database import get_db_dependency

router = APIRouter()
logger = logging.getLogger("admin")


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get APScheduler status and statistics
    
    Returns:
        - scheduler_running: Boolean indicating if scheduler is active
        - total_jobs: Total number of scheduled jobs
        - jobs_by_type: Breakdown by job type (activate/noshow/complete)
        - next_5_jobs: Next 5 upcoming jobs with timing
    """
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        # Sort jobs by next_run_time
        sorted_jobs = sorted(
            [j for j in jobs if j.next_run_time], 
            key=lambda j: j.next_run_time
        )
        
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
        logger.error(f"Error getting scheduler status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/jobs/{reservation_id}")
async def get_reservation_jobs(reservation_id: str):
    """
    Get all scheduled jobs for a specific reservation
    
    Args:
        reservation_id: UUID of the reservation
        
    Returns:
        List of jobs with their status and timing
    """
    try:
        jobs = ReservationManager.get_reservation_jobs(reservation_id)
        
        return {
            "reservation_id": reservation_id,
            "jobs_found": len(jobs),
            "jobs": jobs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting reservation jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reservations/health")
async def reservation_system_health(db = Depends(get_db_dependency)):
    """
    Comprehensive health check for reservation system
    
    Returns:
        - Scheduler status
        - Reservation statistics (last 7 days)
        - Job counts by status
    """
    try:
        # Get reservation statistics
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
        
        # Get scheduler status
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
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking reservation health: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/scheduler/jobs")
async def list_all_jobs():
    """
    List all currently scheduled jobs
    
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
        
        return {
            "total_jobs": len(job_list),
            "jobs": job_list,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/reconcile")
async def trigger_reconciliation(db = Depends(get_db_dependency)):
    """
    Manual reconciliation trigger - sync DB reservations with scheduler jobs
    
    This endpoint:
    1. Checks all active/pending reservations in DB
    2. Verifies they have scheduled jobs
    3. Creates missing jobs if needed
    
    Returns:
        Summary of reconciliation actions
    """
    try:
        # Get all active and pending reservations
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
        
        return {
            "status": "reconciliation_complete",
            "total_reservations_checked": len(reservations),
            "reservations_with_all_jobs": len(existing_jobs),
            "reservations_with_missing_jobs": len(missing_jobs),
            "missing_jobs_details": missing_jobs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during reconciliation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
