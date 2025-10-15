# APScheduler Implementation Plan for Parking Reservation Management

**Date**: 2025-10-15  
**Status**: Planning Phase  
**Target**: Replace `parking_03_reservation_cleanup.py` with APScheduler-based system  
**Estimated Effort**: 3-4 days

---

## Executive Summary

This document outlines the migration from the current polling-based reservation cleanup task to an event-driven APScheduler implementation with robustness enhancements (idempotency, saga pattern, circuit breaker).

### Current vs Proposed Architecture

| Aspect | Current (Background Task) | Proposed (APScheduler) |
| --- | --- | --- |
| **Execution Model** | Poll every 30s, check all reservations | Event-driven, scheduled per reservation |
| **Resource Usage** | Constant DB queries | Minimal queries, triggered only when needed |
| **Precision** | ±30s window | Sub-second precision |
| **Durability** | In-memory tasks, lost on restart | Persistent in PostgreSQL |
| **Cancellation** | Next poll cycle detects cancellation | Immediate task cancellation |
| **Observability** | Custom logging only | APScheduler UI + custom logging |
| **Scaling** | Single instance only | Multi-instance with DB job store |

### Key Benefits

✅ **Precision**: Exact timing for activation, no-show detection, completion  
✅ **Efficiency**: No polling overhead, event-driven execution  
✅ **Durability**: Jobs survive service restarts  
✅ **Scalability**: Ready for multi-instance deployment  
✅ **Robustness**: Built-in retry, error handling, idempotency

---

## Phase 1: Infrastructure Setup

### 1.1 Install APScheduler

**File**: `services/parking-display/requirements.txt`

```txt
# Existing dependencies
fastapi==0.115.0
uvicorn==0.32.1
sqlalchemy==2.0.36
asyncpg==0.30.0
pydantic==2.10.3

# NEW: APScheduler
apscheduler==3.10.4
```

**Install**:

```bash
cd /opt/smart-parking/services/parking-display
source venv/bin/activate
pip install apscheduler==3.10.4
pip freeze > requirements.txt
```

### 1.2 Database Schema for Job Store

**File**: `database/migrations/007_apscheduler_jobstore.sql`

```sql
-- APScheduler uses its own tables for job persistence
-- These are created automatically, but we need to ensure proper schema

-- Create schema for APScheduler jobs (optional, can use public or parking_operations)
CREATE SCHEMA IF NOT EXISTS scheduler;
GRANT USAGE ON SCHEMA scheduler TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA scheduler TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA scheduler GRANT ALL ON TABLES TO parking_user;

-- APScheduler will create these tables automatically:
-- - scheduler.apscheduler_jobs (job definitions, triggers, next_run_time)

-- Index for performance (APScheduler creates these, but good to document)
-- CREATE INDEX IF NOT EXISTS ix_apscheduler_jobs_next_run_time ON scheduler.apscheduler_jobs(next_run_time);
```

**Apply migration**:

```bash
psql -h localhost -U parking_user -d parking_platform -f database/migrations/007_apscheduler_jobstore.sql
```

### 1.3 Scheduler Configuration

**File**: `services/parking-display/app/config.py`

```python
# services/parking-display/app/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Existing settings
    DATABASE_URL: str
    CHIRPSTACK_GRPC_URL: str = "parking-chirpstack:8080"
    CHIRPSTACK_API_TOKEN: str

    # NEW: APScheduler settings
    APSCHEDULER_JOBSTORE_URL: Optional[str] = None  # Defaults to DATABASE_URL
    APSCHEDULER_TIMEZONE: str = "UTC"
    APSCHEDULER_THREAD_POOL_MAX_WORKERS: int = 10
    APSCHEDULER_MISFIRE_GRACE_TIME: int = 300  # 5 minutes

    # NEW: Robustness settings
    ENABLE_IDEMPOTENCY: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
```

**Add to `.env`**:

```bash
# APScheduler Configuration
APSCHEDULER_TIMEZONE=UTC
APSCHEDULER_THREAD_POOL_MAX_WORKERS=10
APSCHEDULER_MISFIRE_GRACE_TIME=300

# Robustness Features
ENABLE_IDEMPOTENCY=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60
```

---

## Phase 2: Scheduler Core Implementation

### 2.1 Scheduler Initialization

**File**: `services/parking-display/app/scheduler/scheduler.py`

```python
# services/parking-display/app/scheduler/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from app.config import settings
import logging

logger = logging.getLogger("parking-scheduler")

# Singleton scheduler instance
_scheduler: AsyncIOScheduler | None = None

def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler

    if _scheduler is None:
        # Job store configuration
        jobstore_url = settings.APSCHEDULER_JOBSTORE_URL or settings.DATABASE_URL

        jobstores = {
            'default': SQLAlchemyJobStore(
                url=jobstore_url,
                tablename='apscheduler_jobs',
                tableschema='scheduler'  # Use dedicated schema
            )
        }

        # Executor configuration
        executors = {
            'default': ThreadPoolExecutor(
                max_workers=settings.APSCHEDULER_THREAD_POOL_MAX_WORKERS
            )
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine multiple missed executions into one
            'max_instances': 1,  # Prevent concurrent execution of same job
            'misfire_grace_time': settings.APSCHEDULER_MISFIRE_GRACE_TIME
        }

        # Create scheduler
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=settings.APSCHEDULER_TIMEZONE
        )

        logger.info(f"✅ APScheduler initialized with jobstore: {jobstore_url}")

    return _scheduler

def start_scheduler():
    """Start the scheduler (call on app startup)"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ APScheduler started")

def shutdown_scheduler():
    """Shutdown the scheduler gracefully (call on app shutdown)"""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("✅ APScheduler shutdown complete")
```

### 2.2 Integrate with FastAPI Lifecycle

**File**: `services/parking-display/app/main.py`

```python
# services/parking-display/app/main.py
from fastapi import FastAPI
from app.scheduler.scheduler import start_scheduler, shutdown_scheduler
import logging

logger = logging.getLogger("parking-display")

app = FastAPI(title="Parking Display Service")

# Existing routers
from app.routers import actuations, spaces, reservations
app.include_router(actuations.router, prefix="/v1/actuations", tags=["actuations"])
app.include_router(spaces.router, prefix="/v1/spaces", tags=["spaces"])
app.include_router(reservations.router, prefix="/v1/reservations", tags=["reservations"])

@app.on_event("startup")
async def startup_event():
    """Initialize scheduler on startup"""
    logger.info("🚀 Starting Parking Display Service")
    start_scheduler()
    logger.info("✅ Startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler gracefully"""
    logger.info("🛑 Shutting down Parking Display Service")
    shutdown_scheduler()
    logger.info("✅ Shutdown complete")

@app.get("/health")
async def health_check():
    from app.scheduler.scheduler import get_scheduler
    scheduler = get_scheduler()

    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "pending_jobs": len(scheduler.get_jobs())
    }
```

---

## Phase 3: Reservation Lifecycle Jobs

### 3.1 Job Functions

**File**: `services/parking-display/app/scheduler/jobs.py`

```python
# services/parking-display/app/scheduler/jobs.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from app.database import async_session_maker
from app.services.downlink_service import send_downlink_to_display
import logging
import asyncio

logger = logging.getLogger("parking-jobs")

async def activate_reservation_job(reservation_id: str):
    """
    Job: Activate a reservation when its start time arrives
    Trigger: reservation.reserved_from
    """
    async with async_session_maker() as db:
        try:
            logger.info(f"⏰ Activating reservation {reservation_id}")

            # Update reservation status
            result = await db.execute(text("""
                UPDATE parking_operations.reservations
                SET status = 'active',
                    activated_at = NOW()
                WHERE reservation_id = :reservation_id
                  AND status = 'pending'
                RETURNING space_id, external_booking_id
            """), {"reservation_id": reservation_id})

            row = result.fetchone()
            if not row:
                logger.warning(f"Reservation {reservation_id} not found or already activated")
                return

            space_id, external_booking_id = row.space_id, row.external_booking_id

            # Update parking space state to RESERVED
            await db.execute(text("""
                UPDATE parking_config.spaces
                SET current_state = 'RESERVED',
                    state_changed_at = NOW()
                WHERE space_id = :space_id
            """), {"space_id": space_id})

            # Send downlink to display (RESERVED = yellow)
            await send_downlink_to_display(db, space_id, "RESERVED")

            # Log actuation event
            await db.execute(text("""
                INSERT INTO parking_operations.actuations (
                    space_id, previous_state, new_state, reason, trigger_type
                ) VALUES (
                    :space_id, 'FREE', 'RESERVED', 'reservation_activated', 'scheduled_job'
                )
            """), {"space_id": space_id})

            await db.commit()

            logger.info(f"✅ Reservation {reservation_id} activated for space {space_id}")

        except Exception as e:
            logger.error(f"❌ Failed to activate reservation {reservation_id}: {e}", exc_info=True)
            await db.rollback()
            raise

async def check_no_show_job(reservation_id: str):
    """
    Job: Check if vehicle arrived within grace period
    Trigger: reservation.reserved_from + grace_period_minutes
    """
    async with async_session_maker() as db:
        try:
            logger.info(f"⏰ Checking no-show for reservation {reservation_id}")

            # Get reservation and space details
            result = await db.execute(text("""
                SELECT 
                    r.space_id,
                    r.reserved_from,
                    r.grace_period_minutes,
                    s.last_sensor_update,
                    s.sensor_state
                FROM parking_operations.reservations r
                JOIN parking_config.spaces s ON r.space_id = s.space_id
                WHERE r.reservation_id = :reservation_id
                  AND r.status = 'active'
            """), {"reservation_id": reservation_id})

            row = result.fetchone()
            if not row:
                logger.warning(f"Reservation {reservation_id} not found or not active")
                return

            # Check if vehicle arrived (sensor shows OCCUPIED after reservation start)
            vehicle_arrived = (
                row.sensor_state == 'OCCUPIED' and
                row.last_sensor_update >= row.reserved_from
            )

            if vehicle_arrived:
                logger.info(f"✅ Vehicle arrived for reservation {reservation_id}")
                return  # Vehicle arrived, no action needed

            # No vehicle detected - mark as no-show
            logger.warning(f"⚠️ No-show detected for reservation {reservation_id}")

            await db.execute(text("""
                UPDATE parking_operations.reservations
                SET status = 'no_show',
                    no_show_detected_at = NOW()
                WHERE reservation_id = :reservation_id
            """), {"reservation_id": reservation_id})

            # Release parking space back to FREE
            await db.execute(text("""
                UPDATE parking_config.spaces
                SET current_state = 'FREE',
                    state_changed_at = NOW()
                WHERE space_id = :space_id
            """), {"space_id": row.space_id})

            # Send downlink to display (FREE = green)
            await send_downlink_to_display(db, row.space_id, "FREE")

            # Log actuation event
            await db.execute(text("""
                INSERT INTO parking_operations.actuations (
                    space_id, previous_state, new_state, reason, trigger_type
                ) VALUES (
                    :space_id, 'RESERVED', 'FREE', 'no_show_detected', 'scheduled_job'
                )
            """), {"space_id": row.space_id})

            await db.commit()

            logger.info(f"✅ Reservation {reservation_id} marked as no-show, space released")

        except Exception as e:
            logger.error(f"❌ Failed to check no-show for {reservation_id}: {e}", exc_info=True)
            await db.rollback()
            raise

async def complete_reservation_job(reservation_id: str):
    """
    Job: Complete a reservation when its end time arrives
    Trigger: reservation.reserved_until
    """
    async with async_session_maker() as db:
        try:
            logger.info(f"⏰ Completing reservation {reservation_id}")

            # Update reservation status
            result = await db.execute(text("""
                UPDATE parking_operations.reservations
                SET status = 'completed',
                    completed_at = NOW()
                WHERE reservation_id = :reservation_id
                  AND status = 'active'
                RETURNING space_id
            """), {"reservation_id": reservation_id})

            row = result.fetchone()
            if not row:
                logger.warning(f"Reservation {reservation_id} not found or already completed")
                return

            space_id = row.space_id

            # Get current sensor state to determine new display state
            sensor_result = await db.execute(text("""
                SELECT sensor_state FROM parking_config.spaces
                WHERE space_id = :space_id
            """), {"space_id": space_id})

            sensor_state = sensor_result.fetchone().sensor_state

            # Update parking space state based on sensor
            new_state = sensor_state if sensor_state in ('OCCUPIED', 'FREE') else 'FREE'

            await db.execute(text("""
                UPDATE parking_config.spaces
                SET current_state = :new_state,
                    state_changed_at = NOW()
                WHERE space_id = :space_id
            """), {"space_id": space_id, "new_state": new_state})

            # Send downlink to display
            await send_downlink_to_display(db, space_id, new_state)

            # Log actuation event
            await db.execute(text("""
                INSERT INTO parking_operations.actuations (
                    space_id, previous_state, new_state, reason, trigger_type
                ) VALUES (
                    :space_id, 'RESERVED', :new_state, 'reservation_completed', 'scheduled_job'
                )
            """), {"space_id": space_id, "new_state": new_state})

            await db.commit()

            logger.info(f"✅ Reservation {reservation_id} completed, space state: {new_state}")

        except Exception as e:
            logger.error(f"❌ Failed to complete reservation {reservation_id}: {e}", exc_info=True)
            await db.rollback()
            raise

def run_async_job(coro):
    """
    Wrapper to run async functions in APScheduler's thread pool
    APScheduler executes jobs in threads, but our jobs are async
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

### 3.2 Reservation Manager

**File**: `services/parking-display/app/scheduler/reservation_manager.py`

```python
# services/parking-display/app/scheduler/reservation_manager.py
from app.scheduler.scheduler import get_scheduler
from app.scheduler.jobs import (
    activate_reservation_job,
    check_no_show_job,
    complete_reservation_job,
    run_async_job
)
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("reservation-manager")

class ReservationManager:
    """Manages lifecycle jobs for parking reservations"""

    @staticmethod
    def schedule_reservation_lifecycle(reservation):
        """
        Schedule all lifecycle jobs for a new reservation

        Args:
            reservation: Reservation object with:
                - reservation_id (UUID)
                - reserved_from (datetime)
                - reserved_until (datetime)
                - grace_period_minutes (int)
        """
        scheduler = get_scheduler()
        reservation_id = str(reservation.reservation_id)

        try:
            # Job 1: Activate reservation at start time
            scheduler.add_job(
                func=run_async_job,
                args=[activate_reservation_job(reservation_id)],
                trigger='date',
                run_date=reservation.reserved_from,
                id=f"activate_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=60  # Allow 1 minute grace for activation
            )
            logger.info(f"📅 Scheduled activation for {reservation_id} at {reservation.reserved_from}")

            # Job 2: Check no-show after grace period
            grace_end = reservation.reserved_from + timedelta(
                minutes=reservation.grace_period_minutes
            )
            scheduler.add_job(
                func=run_async_job,
                args=[check_no_show_job(reservation_id)],
                trigger='date',
                run_date=grace_end,
                id=f"noshow_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=300  # Allow 5 minutes grace for no-show check
            )
            logger.info(f"📅 Scheduled no-show check for {reservation_id} at {grace_end}")

            # Job 3: Complete reservation at end time
            scheduler.add_job(
                func=run_async_job,
                args=[complete_reservation_job(reservation_id)],
                trigger='date',
                run_date=reservation.reserved_until,
                id=f"complete_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=300  # Allow 5 minutes grace for completion
            )
            logger.info(f"📅 Scheduled completion for {reservation_id} at {reservation.reserved_until}")

            logger.info(f"✅ All lifecycle jobs scheduled for reservation {reservation_id}")

        except Exception as e:
            logger.error(f"❌ Failed to schedule jobs for reservation {reservation_id}: {e}")
            raise

    @staticmethod
    def cancel_reservation_jobs(reservation_id: str):
        """
        Cancel all scheduled jobs for a reservation
        Call this when a reservation is manually cancelled
        """
        scheduler = get_scheduler()

        job_ids = [
            f"activate_{reservation_id}",
            f"noshow_{reservation_id}",
            f"complete_{reservation_id}"
        ]

        cancelled_count = 0
        for job_id in job_ids:
            try:
                scheduler.remove_job(job_id)
                cancelled_count += 1
                logger.info(f"🗑️ Cancelled job {job_id}")
            except Exception as e:
                # Job may not exist (already executed or never scheduled)
                logger.debug(f"Job {job_id} not found (may have already executed)")

        logger.info(f"✅ Cancelled {cancelled_count}/3 jobs for reservation {reservation_id}")

    @staticmethod
    def get_reservation_jobs(reservation_id: str):
        """Get status of all jobs for a reservation"""
        scheduler = get_scheduler()

        job_ids = [
            f"activate_{reservation_id}",
            f"noshow_{reservation_id}",
            f"complete_{reservation_id}"
        ]

        jobs_status = []
        for job_id in job_ids:
            job = scheduler.get_job(job_id)
            if job:
                jobs_status.append({
                    "job_id": job_id,
                    "next_run_time": job.next_run_time,
                    "trigger": str(job.trigger)
                })

        return jobs_status
```

---

## Phase 4: API Integration

### 4.1 Update Reservation Create Endpoint

**File**: `services/parking-display/app/routers/reservations.py`

```python
# services/parking-display/app/routers/reservations.py (UPDATED)
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.scheduler.reservation_manager import ReservationManager
from app.models import ReservationCreate, ReservationResponse
from typing import Optional
import logging

router = APIRouter()
logger = logging.getLogger("reservations-api")

# NEW: Idempotency store (simple in-memory, upgrade to Redis later)
_idempotency_cache = {}

@router.post("/", response_model=ReservationResponse)
async def create_reservation(
    reservation: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Create a new parking reservation

    Idempotency: Use Idempotency-Key header to prevent duplicate reservations
    """

    # NEW: Check idempotency key
    if idempotency_key:
        cached_response = _idempotency_cache.get(idempotency_key)
        if cached_response:
            logger.info(f"♻️ Returning cached response for idempotency key: {idempotency_key}")
            return cached_response

    try:
        # Validate space exists and is enabled
        space_check = await db.execute(text("""
            SELECT space_id, current_state
            FROM parking_config.spaces
            WHERE space_id = :space_id AND enabled = TRUE AND archived = FALSE
        """), {"space_id": str(reservation.space_id)})

        if not space_check.fetchone():
            raise HTTPException(status_code=404, detail="Parking space not found or disabled")

        # Validate time range
        if reservation.reserved_until <= reservation.reserved_from:
            raise HTTPException(
                status_code=400,
                detail="reserved_until must be after reserved_from"
            )

        # Check for overlapping reservations
        overlap_check = await db.execute(text("""
            SELECT reservation_id
            FROM parking_operations.reservations
            WHERE space_id = :space_id
              AND status NOT IN ('cancelled', 'no_show', 'expired', 'completed')
              AND (
                  (reserved_from <= :start AND reserved_until > :start)
                  OR (reserved_from < :end AND reserved_until >= :end)
                  OR (reserved_from >= :start AND reserved_until <= :end)
              )
        """), {
            "space_id": str(reservation.space_id),
            "start": reservation.reserved_from,
            "end": reservation.reserved_until
        })

        if overlap_check.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Reservation conflicts with existing reservation"
            )

        # Create reservation record
        result = await db.execute(text("""
            INSERT INTO parking_operations.reservations (
                space_id, reserved_from, reserved_until, external_booking_id,
                external_system, external_user_id, booking_metadata,
                reservation_type, grace_period_minutes
            ) VALUES (
                :space_id, :from, :until, :booking_id, :system, :user_id,
                :metadata::jsonb, :type, :grace
            )
            RETURNING reservation_id, status, created_at
        """), {
            "space_id": str(reservation.space_id),
            "from": reservation.reserved_from,
            "until": reservation.reserved_until,
            "booking_id": reservation.external_booking_id,
            "system": reservation.external_system,
            "user_id": reservation.external_user_id,
            "metadata": reservation.booking_metadata.json() if reservation.booking_metadata else "{}",
            "type": reservation.reservation_type,
            "grace": reservation.grace_period_minutes
        })

        row = result.fetchone()
        await db.commit()

        # NEW: Schedule lifecycle jobs via APScheduler
        from datetime import datetime
        reservation_obj = type('Reservation', (), {
            'reservation_id': row.reservation_id,
            'reserved_from': reservation.reserved_from,
            'reserved_until': reservation.reserved_until,
            'grace_period_minutes': reservation.grace_period_minutes
        })()

        ReservationManager.schedule_reservation_lifecycle(reservation_obj)

        response = ReservationResponse(
            status="created",
            reservation_id=row.reservation_id,
            space_id=reservation.space_id,
            reserved_from=reservation.reserved_from,
            reserved_until=reservation.reserved_until
        )

        # Cache response for idempotency
        if idempotency_key:
            _idempotency_cache[idempotency_key] = response

        logger.info(f"✅ Reservation {row.reservation_id} created with scheduled jobs")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create reservation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
```

### 4.2 Update Reservation Cancel Endpoint

**File**: `services/parking-display/app/routers/reservations.py` (continued)

```python
@router.delete("/{reservation_id}")
async def cancel_reservation(
    reservation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cancel an active reservation and remove scheduled jobs"""

    try:
        # Update reservation status
        result = await db.execute(text("""
            UPDATE parking_operations.reservations
            SET status = 'cancelled',
                cancelled_at = NOW()
            WHERE reservation_id = :reservation_id
              AND status IN ('pending', 'active')
            RETURNING space_id
        """), {"reservation_id": reservation_id})

        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found or already completed"
            )

        space_id = row.space_id

        # Release parking space back to sensor state
        await db.execute(text("""
            UPDATE parking_config.spaces
            SET current_state = sensor_state,
                state_changed_at = NOW()
            WHERE space_id = :space_id
        """), {"space_id": space_id})

        await db.commit()

        # NEW: Cancel all scheduled jobs
        ReservationManager.cancel_reservation_jobs(reservation_id)

        logger.info(f"✅ Reservation {reservation_id} cancelled, jobs removed")

        return {
            "status": "cancelled",
            "reservation_id": reservation_id,
            "jobs_cancelled": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to cancel reservation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Phase 5: Robustness Enhancements

### 5.1 Idempotency with Redis

**File**: `services/parking-display/app/utils/idempotency.py`

```python
# services/parking-display/app/utils/idempotency.py
from typing import Optional, Any
import redis.asyncio as redis
import json
import logging
from datetime import timedelta

logger = logging.getLogger("idempotency")

# Redis client (initialize on startup)
_redis_client: Optional[redis.Redis] = None

async def init_redis(redis_url: str = "redis://parking-redis:6379/0"):
    """Initialize Redis client for idempotency cache"""
    global _redis_client
    _redis_client = redis.from_url(redis_url, decode_responses=True)
    logger.info(f"✅ Redis idempotency cache initialized: {redis_url}")

async def close_redis():
    """Close Redis connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        logger.info("✅ Redis connection closed")

async def get_cached_response(idempotency_key: str) -> Optional[dict]:
    """
    Get cached response for idempotency key

    Returns:
        Cached response dict if exists, None otherwise
    """
    if not _redis_client:
        logger.warning("Redis not initialized, idempotency disabled")
        return None

    try:
        cached_json = await _redis_client.get(f"idempotency:{idempotency_key}")
        if cached_json:
            logger.info(f"♻️ Idempotency cache hit: {idempotency_key}")
            return json.loads(cached_json)
        return None
    except Exception as e:
        logger.error(f"❌ Redis get error: {e}")
        return None

async def cache_response(
    idempotency_key: str,
    response: Any,
    ttl: timedelta = timedelta(hours=24)
):
    """
    Cache response for idempotency key

    Args:
        idempotency_key: Unique key for request
        response: Response to cache (must be JSON-serializable)
        ttl: Time-to-live for cache entry
    """
    if not _redis_client:
        logger.warning("Redis not initialized, skipping cache")
        return

    try:
        response_json = json.dumps(response, default=str)
        await _redis_client.setex(
            f"idempotency:{idempotency_key}",
            int(ttl.total_seconds()),
            response_json
        )
        logger.info(f"💾 Cached response for idempotency key: {idempotency_key}")
    except Exception as e:
        logger.error(f"❌ Redis set error: {e}")
```

**Update main.py**:

```python
# services/parking-display/app/main.py (UPDATED)
from app.utils.idempotency import init_redis, close_redis

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Parking Display Service")
    start_scheduler()
    await init_redis()  # NEW
    logger.info("✅ Startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down Parking Display Service")
    shutdown_scheduler()
    await close_redis()  # NEW
    logger.info("✅ Shutdown complete")
```

**Update reservations.py to use Redis**:

```python
# In create_reservation endpoint
from app.utils.idempotency import get_cached_response, cache_response

if idempotency_key:
    cached = await get_cached_response(idempotency_key)
    if cached:
        return cached

# ... create reservation logic ...

if idempotency_key:
    await cache_response(idempotency_key, response.dict())
```

### 5.2 Circuit Breaker for External APIs

**File**: `services/parking-display/app/utils/circuit_breaker.py`

```python
# services/parking-display/app/utils/circuit_breaker.py
from functools import wraps
from datetime import datetime, timedelta
from typing import Callable
import logging

logger = logging.getLogger("circuit-breaker")

class CircuitBreaker:
    """
    Circuit breaker pattern implementation

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout)
        self.name = name

        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable):
        """Decorator to wrap function with circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if circuit is open
            if self.state == "OPEN":
                if datetime.utcnow() - self.last_failure_time > self.recovery_timeout:
                    # Try to recover
                    self.state = "HALF_OPEN"
                    logger.info(f"🔄 Circuit breaker '{self.name}' entering HALF_OPEN state")
                else:
                    # Still open, fail fast
                    logger.warning(f"⚠️ Circuit breaker '{self.name}' is OPEN, request rejected")
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN")

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Success - reset failure count
                if self.state == "HALF_OPEN":
                    logger.info(f"✅ Circuit breaker '{self.name}' recovered, entering CLOSED state")
                    self.state = "CLOSED"
                    self.failure_count = 0

                return result

            except Exception as e:
                # Failure - increment counter
                self.failure_count += 1
                self.last_failure_time = datetime.utcnow()

                logger.error(f"❌ Circuit breaker '{self.name}' failure {self.failure_count}/{self.failure_threshold}: {e}")

                # Check if threshold exceeded
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    logger.error(f"🔴 Circuit breaker '{self.name}' is now OPEN")

                raise

        return wrapper

# Global circuit breaker instances
_circuit_breakers = {}

def get_circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
    """Get or create a circuit breaker instance"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name=name
        )
    return _circuit_breakers[name]
```

**Usage Example**:

```python
# services/parking-display/app/services/external_booking_api.py
from app.utils.circuit_breaker import get_circuit_breaker
import httpx

booking_api_breaker = get_circuit_breaker("booking_api", failure_threshold=5, recovery_timeout=60)

@booking_api_breaker.call
async def send_booking_confirmation(booking_id: str, confirmation_data: dict):
    """Send confirmation to external booking system with circuit breaker"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://booking-api.example.com/confirm/{booking_id}",
            json=confirmation_data,
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()
```

### 5.3 Saga Pattern for Multi-Step Operations

**File**: `services/parking-display/app/utils/saga.py`

```python
# services/parking-display/app/utils/saga.py
from typing import Callable, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger("saga")

@dataclass
class SagaStep:
    """
    Represents a single step in a saga

    Attributes:
        action: Function to execute (forward action)
        compensate: Function to execute on rollback
        name: Human-readable step name
    """
    action: Callable
    compensate: Callable
    name: str

class Saga:
    """
    Saga pattern implementation for distributed transactions

    Example:
        saga = Saga("create_reservation")
        saga.add_step(lock_space, unlock_space, "lock_space")
        saga.add_step(create_record, delete_record, "create_record")
        saga.add_step(send_downlink, cancel_downlink, "send_downlink")

        result = await saga.execute(space_id="123")
    """

    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []
        self.executed_steps: List[Tuple[SagaStep, any]] = []

    def add_step(self, action: Callable, compensate: Callable, name: str):
        """Add a step to the saga"""
        self.steps.append(SagaStep(action=action, compensate=compensate, name=name))

    async def execute(self, *args, **kwargs):
        """
        Execute all saga steps

        If any step fails, automatically compensates all previous steps in reverse order
        """
        logger.info(f"🚀 Starting saga: {self.name} with {len(self.steps)} steps")

        try:
            # Execute steps forward
            for step in self.steps:
                logger.info(f"⏩ Executing step: {step.name}")
                result = await step.action(*args, **kwargs)
                self.executed_steps.append((step, result))
                logger.info(f"✅ Step completed: {step.name}")

            logger.info(f"✅ Saga completed successfully: {self.name}")
            return self.executed_steps[-1][1] if self.executed_steps else None

        except Exception as e:
            logger.error(f"❌ Saga failed at step: {self.executed_steps[-1][0].name if self.executed_steps else 'initial'}")
            logger.error(f"Error: {e}", exc_info=True)

            # Compensate in reverse order
            await self._compensate()

            raise Exception(f"Saga '{self.name}' failed and compensated: {e}")

    async def _compensate(self):
        """Execute compensation actions in reverse order"""
        if not self.executed_steps:
            logger.info("No steps to compensate")
            return

        logger.warning(f"⏪ Starting compensation for saga: {self.name}")

        # Compensate in reverse order
        for step, result in reversed(self.executed_steps):
            try:
                logger.info(f"↩️ Compensating step: {step.name}")
                await step.compensate(result)
                logger.info(f"✅ Compensation completed: {step.name}")
            except Exception as e:
                logger.error(f"❌ Compensation failed for step {step.name}: {e}")
                # Continue compensating other steps even if one fails

        logger.info(f"✅ Compensation completed for saga: {self.name}")
```

**Usage Example**:

```python
# services/parking-display/app/services/reservation_saga.py
from app.utils.saga import Saga

async def create_reservation_with_saga(reservation_data):
    """Create reservation using saga pattern for rollback safety"""

    saga = Saga("create_reservation")

    # Step 1: Lock parking space
    async def lock_space():
        # Lock space in database
        await db.execute("UPDATE spaces SET locked = TRUE WHERE space_id = :id")
        return reservation_data.space_id

    async def unlock_space(space_id):
        await db.execute("UPDATE spaces SET locked = FALSE WHERE space_id = :id")

    saga.add_step(lock_space, unlock_space, "lock_space")

    # Step 2: Create reservation record
    async def create_record():
        result = await db.execute("INSERT INTO reservations (...) RETURNING reservation_id")
        return result.fetchone().reservation_id

    async def delete_record(reservation_id):
        await db.execute("DELETE FROM reservations WHERE reservation_id = :id")

    saga.add_step(create_record, delete_record, "create_record")

    # Step 3: Schedule APScheduler jobs
    async def schedule_jobs():
        ReservationManager.schedule_reservation_lifecycle(reservation_data)
        return reservation_data.reservation_id

    async def cancel_jobs(reservation_id):
        ReservationManager.cancel_reservation_jobs(reservation_id)

    saga.add_step(schedule_jobs, cancel_jobs, "schedule_jobs")

    # Step 4: Send downlink to display
    async def send_downlink():
        await send_downlink_to_display(db, reservation_data.space_id, "RESERVED")
        return reservation_data.space_id

    async def cancel_downlink(space_id):
        await send_downlink_to_display(db, space_id, "FREE")

    saga.add_step(send_downlink, cancel_downlink, "send_downlink")

    # Execute saga
    return await saga.execute()
```

---

## Phase 6: Migration & Testing

### 6.1 Migration Checklist

**Pre-Migration**:

- [ ] Review current `parking_03_reservation_cleanup.py` logic
- [ ] Backup database: `pg_dump parking_platform > backup_pre_apscheduler.sql`
- [ ] Test APScheduler in development environment
- [ ] Document all active reservations: `SELECT COUNT(*) FROM reservations WHERE status = 'active'`

**Migration Steps**:

1. [ ] Apply database migration `007_apscheduler_jobstore.sql`
2. [ ] Deploy new code with APScheduler (keep old task disabled)
3. [ ] Verify scheduler starts: Check `/health` endpoint
4. [ ] Test with one new reservation
5. [ ] Monitor APScheduler logs for 1 hour
6. [ ] If stable, disable old `parking_03` background task
7. [ ] Delete `parking_03_reservation_cleanup.py`

**Post-Migration**:

- [ ] Monitor APScheduler job store: `SELECT COUNT(*) FROM scheduler.apscheduler_jobs`
- [ ] Verify no missed activations/completions
- [ ] Test manual cancellation (jobs removed from scheduler)
- [ ] Load test: Create 50 overlapping reservations

### 6.2 Testing Scenarios

**Test 1: Basic Reservation Lifecycle**

```python
# Create reservation starting in 1 minute
import requests
from datetime import datetime, timedelta

response = requests.post("https://parking.verdegris.eu/v1/reservations/", json={
    "space_id": "550e8400-e29b-41d4-a716-446655440000",
    "reserved_from": (datetime.utcnow() + timedelta(minutes=1)).isoformat() + "Z",
    "reserved_until": (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z",
    "external_booking_id": "TEST-001",
    "grace_period_minutes": 2
})

reservation_id = response.json()["reservation_id"]

# Wait and observe logs:
# - Activation job runs after 1 minute
# - No-show check runs after 3 minutes (1 min + 2 min grace)
# - Completion job runs after 5 minutes
```

**Test 2: No-Show Detection**

```python
# Create reservation but don't send occupancy uplink
# Should mark as no_show after grace period

response = requests.post("https://parking.verdegris.eu/v1/reservations/", json={
    "space_id": "550e8400-e29b-41d4-a716-446655440000",
    "reserved_from": datetime.utcnow().isoformat() + "Z",
    "reserved_until": (datetime.utcnow() + timedelta(minutes=10)).isoformat() + "Z",
    "grace_period_minutes": 1
})

# Wait 2 minutes
# Check: SELECT status FROM reservations WHERE reservation_id = '...'
# Expected: status = 'no_show'
```

**Test 3: Manual Cancellation**

```python
# Create reservation
response = requests.post("https://parking.verdegris.eu/v1/reservations/", json={
    "space_id": "550e8400-e29b-41d4-a716-446655440000",
    "reserved_from": (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z",
    "reserved_until": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
})

reservation_id = response.json()["reservation_id"]

# Immediately cancel
requests.delete(f"https://parking.verdegris.eu/v1/reservations/{reservation_id}")

# Check scheduler: No jobs should exist
# psql: SELECT COUNT(*) FROM scheduler.apscheduler_jobs WHERE id LIKE '%reservation_id%'
# Expected: 0
```

**Test 4: Service Restart Durability**

```bash
# Create reservation
curl -X POST https://parking.verdegris.eu/v1/reservations/ -d '{...}'

# Check jobs exist
psql -c "SELECT id, next_run_time FROM scheduler.apscheduler_jobs"

# Restart service
docker compose restart parking-display

# Verify jobs still exist and will execute
psql -c "SELECT id, next_run_time FROM scheduler.apscheduler_jobs"
```

**Test 5: Idempotency**

```bash
# Send same request twice with same idempotency key
curl -X POST https://parking.verdegris.eu/v1/reservations/ \
  -H "Idempotency-Key: test-12345" \
  -d '{...}'

curl -X POST https://parking.verdegris.eu/v1/reservations/ \
  -H "Idempotency-Key: test-12345" \
  -d '{...}'

# Second request should return cached response, not create duplicate
```

---

## Phase 7: Monitoring & Observability

### 7.1 APScheduler Monitoring Endpoint

**File**: `services/parking-display/app/routers/admin.py` (new)

```python
# services/parking-display/app/routers/admin.py
from fastapi import APIRouter, Depends
from app.scheduler.scheduler import get_scheduler
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter()

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get APScheduler status and statistics"""
    scheduler = get_scheduler()

    jobs = scheduler.get_jobs()

    return {
        "scheduler_running": scheduler.running,
        "total_jobs": len(jobs),
        "jobs_by_type": {
            "activate": len([j for j in jobs if j.id.startswith("activate_")]),
            "noshow": len([j for j in jobs if j.id.startswith("noshow_")]),
            "complete": len([j for j in jobs if j.id.startswith("complete_")])
        },
        "next_5_jobs": [
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in sorted(jobs, key=lambda j: j.next_run_time or datetime.max)[:5]
        ]
    }

@router.get("/scheduler/jobs/{reservation_id}")
async def get_reservation_jobs(reservation_id: str):
    """Get all scheduled jobs for a specific reservation"""
    from app.scheduler.reservation_manager import ReservationManager

    jobs = ReservationManager.get_reservation_jobs(reservation_id)

    return {
        "reservation_id": reservation_id,
        "jobs": jobs
    }

@router.get("/reservations/health")
async def reservation_system_health(db: AsyncSession = Depends(get_db)):
    """Health check for reservation system"""

    # Get reservation statistics
    result = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'active') as active,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
            COUNT(*) FILTER (WHERE status = 'no_show') as no_show,
            COUNT(*) FILTER (WHERE status = 'expired') as expired
        FROM parking_operations.reservations
        WHERE created_at > NOW() - INTERVAL '7 days'
    """))

    stats = result.fetchone()

    scheduler = get_scheduler()

    return {
        "status": "healthy" if scheduler.running else "unhealthy",
        "scheduler_running": scheduler.running,
        "total_scheduled_jobs": len(scheduler.get_jobs()),
        "reservations_last_7_days": {
            "pending": stats.pending,
            "active": stats.active,
            "completed": stats.completed,
            "cancelled": stats.cancelled,
            "no_show": stats.no_show,
            "expired": stats.expired
        }
    }
```

**Register in main.py**:

```python
from app.routers import admin
app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
```

### 7.2 Prometheus Metrics (Optional)

**File**: `services/parking-display/requirements.txt` (add)

```txt
prometheus-fastapi-instrumentator==7.0.0
```

**File**: `services/parking-display/app/main.py` (add)

```python
from prometheus_fastapi_instrumentator import Instrumentator

# Add after app creation
Instrumentator().instrument(app).expose(app)

# Metrics available at: https://parking.verdegris.eu/metrics
```

---

## Phase 8: Deployment

### 8.1 Deployment Steps

**Step 1: Update Dependencies**

```bash
cd /opt/smart-parking/services/parking-display
pip install -r requirements.txt
```

**Step 2: Apply Database Migration**

```bash
psql -h localhost -U parking_user -d parking_platform -f /opt/smart-parking/database/migrations/007_apscheduler_jobstore.sql
```

**Step 3: Update Environment Variables**

```bash
# Add to .env
cat >> /opt/smart-parking/.env << EOF

# APScheduler Configuration
APSCHEDULER_TIMEZONE=UTC
APSCHEDULER_THREAD_POOL_MAX_WORKERS=10
APSCHEDULER_MISFIRE_GRACE_TIME=300

# Robustness Features
ENABLE_IDEMPOTENCY=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60
EOF
```

**Step 4: Rebuild and Deploy**

```bash
cd /opt/smart-parking
docker compose build parking-display
docker compose up -d parking-display
```

**Step 5: Verify Deployment**

```bash
# Check logs
docker compose logs -f parking-display

# Check health
curl https://parking.verdegris.eu/health

# Check scheduler status
curl https://parking.verdegris.eu/v1/admin/scheduler/status
```

### 8.2 Rollback Plan

If issues occur:

```bash
# Rollback to previous version
cd /opt/smart-parking
git checkout <previous-commit-hash> services/parking-display/

# Rebuild and redeploy
docker compose build parking-display
docker compose up -d parking-display

# Re-enable old background task (if needed)
# Uncomment parking_03 in docker-compose.yml
```

---

## Phase 9: Documentation Updates

### 9.1 Update README.md

Add section to `/opt/smart-parking/README.md`:

```markdown
## Reservation Management

The parking reservation system uses **APScheduler** for robust, event-driven reservation lifecycle management.

### Features
- ✅ **Precise Timing**: Sub-second precision for activation/completion
- ✅ **Durability**: Jobs survive service restarts (PostgreSQL job store)
- ✅ **Idempotency**: Prevent duplicate reservations with Idempotency-Key header
- ✅ **Circuit Breaker**: Automatic failure handling for external APIs
- ✅ **Saga Pattern**: Rollback safety for multi-step operations

### Architecture
- **APScheduler**: Event-driven job scheduling
- **Job Store**: PostgreSQL (schema: `scheduler`)
- **Redis**: Idempotency cache (24-hour TTL)

### Monitoring
- **Scheduler Status**: `GET /v1/admin/scheduler/status`
- **Reservation Health**: `GET /v1/reservations/health`
- **Job Details**: `GET /v1/admin/scheduler/jobs/{reservation_id}`
```

### 9.2 Create APSCHEDULER.md

**File**: `/opt/smart-parking/APSCHEDULER.md`

````markdown
# APScheduler Implementation Guide

This document describes the APScheduler-based reservation management system.

## Architecture

[Include diagrams and detailed technical documentation]

## Job Lifecycle

1. **Reservation Created** → Schedule 3 jobs
2. **Activation Job** → Runs at `reserved_from`
3. **No-Show Job** → Runs at `reserved_from + grace_period`
4. **Completion Job** → Runs at `reserved_until`

## Troubleshooting

### Jobs Not Executing

Check:
1. Scheduler running: `GET /v1/admin/scheduler/status`
2. Job exists in database: `SELECT * FROM scheduler.apscheduler_jobs WHERE id = 'activate_...'`
3. Next run time in future: Job may have already executed

### High Job Count

Normal: ~3 jobs per active reservation. If >1000 jobs, investigate:
- Old reservations not cleaned up
- Cancelled reservations with orphaned jobs

## Maintenance

### Cleanup Old Jobs
```sql
DELETE FROM scheduler.apscheduler_jobs
WHERE next_run_time < NOW() - INTERVAL '7 days';
````

```
---

## Timeline & Effort Estimate

| Phase | Tasks | Duration | Dependencies |
|-------|-------|----------|--------------|
| **Phase 1** | Infrastructure setup | 0.5 days | None |
| **Phase 2** | Scheduler core | 0.5 days | Phase 1 |
| **Phase 3** | Job implementation | 1 day | Phase 2 |
| **Phase 4** | API integration | 0.5 days | Phase 3 |
| **Phase 5** | Robustness enhancements | 1 day | Phase 4 |
| **Phase 6** | Migration & testing | 0.5 days | Phase 5 |
| **Phase 7** | Monitoring | 0.5 days | Phase 6 |
| **Phase 8** | Deployment | 0.5 days | Phase 7 |
| **Phase 9** | Documentation | 0.5 days | Phase 8 |
| **Total** | | **3-4 days** | |

---

## Success Criteria

- [ ] APScheduler running and persistent across restarts
- [ ] All reservation lifecycle events execute within ±10 seconds of scheduled time
- [ ] Zero duplicate reservations (idempotency working)
- [ ] Manual cancellation removes all scheduled jobs
- [ ] No-show detection works correctly (grace period logic)
- [ ] Circuit breaker prevents cascading failures
- [ ] Saga pattern provides rollback safety
- [ ] Monitoring endpoints provide visibility
- [ ] Load test: 100 concurrent reservations processed without errors

---

## Risk Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| APScheduler performance issues | High | Low | Load test before production, monitor job execution time |
| Job store database contention | Medium | Low | Use dedicated schema, index on next_run_time |
| Service restart during job execution | Medium | Medium | Jobs are idempotent, will retry on next run |
| Clock skew between servers | High | Low | Use UTC everywhere, NTP sync |
| Redis unavailability | Low | Low | Idempotency degrades gracefully (falls back to DB check) |

---

## Next Steps

1. **Review this plan** with team
2. **Set up development environment** (Phase 1)
3. **Implement core scheduler** (Phase 2)
4. **Test in staging** with synthetic load
5. **Deploy to production** with gradual rollout
6. **Monitor for 1 week** before removing old background task

---

**Author**: Smart Parking Team  
**Last Updated**: 2025-10-15  
**Status**: Planning Complete - Ready for Implementation
```
