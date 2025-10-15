"""
Reservation Expiry Task
Automatically expires reservations that have passed their reserved_until time
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List
import sys
sys.path.append("/app")

from app.database import get_db
from app.tasks.reconciliation import trigger_space_reconciliation
from app.monitoring.stats import get_stats_registry

logger = logging.getLogger("reservation-expiry")

class ReservationExpiryTask:
    """Background task to expire old reservations"""

    def __init__(self, check_interval_minutes: int = 5):
        self.check_interval_minutes = check_interval_minutes
        self.stats_registry = get_stats_registry()
        self.stats = {
            "total_checks": 0,
            "reservations_expired": 0,
            "reconciliations_triggered": 0,
            "errors": 0
        }

    async def run_forever(self):
        """Main expiry loop"""
        logger.info(f"🕐 Reservation expiry task started (interval: {self.check_interval_minutes} min)")

        while True:
            try:
                await self.expire_old_reservations()
                await asyncio.sleep(self.check_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in reservation expiry loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 min before retrying

    async def expire_old_reservations(self):
        """Find and expire active reservations that have passed their end time"""
        start_time = datetime.now(timezone.utc)

        async with get_db() as db:
            try:
                # Find all active reservations where reserved_until < NOW()
                expired_reservations = await db.fetch("""
                    SELECT
                        reservation_id,
                        space_id,
                        reserved_from,
                        reserved_until,
                        external_booking_id
                    FROM parking_spaces.reservations
                    WHERE status = 'active'
                      AND reserved_until < NOW()
                    ORDER BY reserved_until ASC
                """)

                self.stats["total_checks"] += 1

                if not expired_reservations:
                    logger.debug("✅ No expired reservations found")
                    return

                logger.info(f"⏰ Found {len(expired_reservations)} expired reservations to process")

                expired_space_ids = set()

                for reservation in expired_reservations:
                    try:
                        reservation_id = str(reservation["reservation_id"])
                        space_id = str(reservation["space_id"])
                        reserved_until = reservation["reserved_until"]
                        external_booking_id = reservation["external_booking_id"]

                        # Update reservation status to 'expired'
                        await db.execute("""
                            UPDATE parking_spaces.reservations
                            SET status = 'expired',
                                completed_at = NOW()
                            WHERE reservation_id = $1
                        """, reservation_id)

                        self.stats["reservations_expired"] += 1
                        expired_space_ids.add(space_id)

                        logger.info(
                            f"✅ Expired reservation {reservation_id[:8]}... "
                            f"(booking: {external_booking_id}, ended: {reserved_until})"
                        )

                    except Exception as e:
                        logger.error(f"Error expiring reservation {reservation_id}: {e}")
                        self.stats["errors"] += 1

                # Trigger reconciliation for all affected spaces
                for space_id in expired_space_ids:
                    try:
                        await trigger_space_reconciliation(space_id)
                        self.stats["reconciliations_triggered"] += 1
                        logger.info(f"🔄 Triggered reconciliation for space {space_id}")
                    except Exception as e:
                        logger.error(f"Error triggering reconciliation for space {space_id}: {e}")
                        self.stats["errors"] += 1

                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"✅ Expiry cycle complete: {len(expired_reservations)} expired, "
                    f"{len(expired_space_ids)} spaces reconciled in {elapsed:.1f}s "
                    f"(total: {self.stats['reservations_expired']} expired, "
                    f"{self.stats['errors']} errors)"
                )
                
                # Update stats registry (Phase 2.2)
                await self.stats_registry.update_stats(
                    task_name="reservation_expiry",
                    success=True,
                    custom_metrics={
                        "reservations_expired": len(expired_reservations),
                        "spaces_reconciled": len(expired_space_ids),
                        "elapsed_seconds": elapsed
                    }
                )

            except Exception as e:
                logger.error(f"Error in expire_old_reservations: {e}", exc_info=True)
                self.stats["errors"] += 1
                
                # Update stats registry with error (Phase 2.2)
                await self.stats_registry.update_stats(
                    task_name="reservation_expiry",
                    success=False,
                    error_message=str(e)
                )


async def start_reservation_expiry_task(check_interval_minutes: int = 5):
    """Start the reservation expiry background task"""
    expiry_task = ReservationExpiryTask(check_interval_minutes=check_interval_minutes)
    await expiry_task.run_forever()
