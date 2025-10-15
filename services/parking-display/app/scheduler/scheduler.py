"""
APScheduler initialization and management
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import logging
import os

logger = logging.getLogger("parking-scheduler")

# Singleton scheduler instance
_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler

    if _scheduler is None:
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable required")
        
        # Job store configuration
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=database_url,
                tablename='apscheduler_jobs',
                tableschema='scheduler'
            )
        }

        # Executor configuration
        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine multiple missed executions into one
            'max_instances': 1,  # Prevent concurrent execution of same job
            'misfire_grace_time': 300  # 5 minutes
        }

        # Create scheduler
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        logger.info(f"✅ APScheduler initialized with PostgreSQL jobstore")

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
