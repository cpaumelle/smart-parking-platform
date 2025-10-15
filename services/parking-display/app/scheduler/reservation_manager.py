"""
Reservation Manager - Handles lifecycle job scheduling
"""
from app.scheduler.scheduler import get_scheduler
from app.scheduler.jobs import (
    activate_reservation_wrapper,
    check_no_show_wrapper,
    complete_reservation_wrapper,
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
    def schedule_reservation_lifecycle(
        reservation_id: str,
        reserved_from: datetime,
        reserved_until: datetime,
        grace_period_minutes: int
    ):
        """
        Schedule all lifecycle jobs for a new reservation

        Args:
            reservation_id: UUID of the reservation
            reserved_from: Start time of reservation
            reserved_until: End time of reservation
            grace_period_minutes: Grace period for no-show detection
        """
        scheduler = get_scheduler()

        try:
            # Job 1: Activate reservation at start time
            scheduler.add_job(
                func=activate_reservation_wrapper,
                args=[reservation_id],
                trigger='date',
                run_date=reserved_from,
                id=f"activate_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=60  # Allow 1 minute grace for activation
            )
            logger.info(f"📅 Scheduled activation for {reservation_id} at {reserved_from}")

            # Job 2: Check no-show after grace period
            grace_end = reserved_from + timedelta(minutes=grace_period_minutes)
            scheduler.add_job(
                func=check_no_show_wrapper,
                args=[reservation_id],
                trigger='date',
                run_date=grace_end,
                id=f"noshow_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=300  # Allow 5 minutes grace for no-show check
            )
            logger.info(f"📅 Scheduled no-show check for {reservation_id} at {grace_end}")

            # Job 3: Complete reservation at end time
            scheduler.add_job(
                func=complete_reservation_wrapper,
                args=[reservation_id],
                trigger='date',
                run_date=reserved_until,
                id=f"complete_{reservation_id}",
                replace_existing=True,
                misfire_grace_time=300  # Allow 5 minutes grace for completion
            )
            logger.info(f"📅 Scheduled completion for {reservation_id} at {reserved_until}")

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
            except Exception:
                # Job may not exist (already executed or never scheduled)
                logger.debug(f"Job {job_id} not found (may have already executed)")

        logger.info(f"✅ Cancelled {cancelled_count}/3 jobs for reservation {reservation_id}")
        return cancelled_count

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
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                })

        return jobs_status
