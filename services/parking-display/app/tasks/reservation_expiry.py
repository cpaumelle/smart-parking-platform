"""
Reservation Expiry Task
Automatically expires reservations that have passed their reserved_until time
Multi-Tenant: Loops through all active tenants
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List
import sys
sys.path.append("/app")

from app.database import get_db
from app.utils.tenant_context import get_tenant_db
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
        logger.info(f"🕐 Reservation expiry task started (interval: {self.check_interval_minutes} min) - Multi-Tenant Mode")

        while True:
            try:
                await self.expire_all_tenants_reservations()
                await asyncio.sleep(self.check_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in reservation expiry loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 min before retrying

    async def expire_all_tenants_reservations(self):
        """Find and expire active reservations across all tenants"""
        start_time = datetime.now(timezone.utc)

        # Get list of active tenants (using system connection)
        async with get_db() as db:
            tenants = await db.fetch("""
                SELECT tenant_id, tenant_slug
                FROM core.tenants
                WHERE is_active = TRUE
                ORDER BY tenant_slug
            """)

        logger.info(f"🔍 Checking expired reservations for {len(tenants)} active tenant(s)")

        total_expired = 0
        total_reconciliations = 0

        # Process each tenant's reservations
        for tenant in tenants:
            try:
                tenant_id = tenant['tenant_id']
                tenant_slug = tenant['tenant_slug']

                async with get_tenant_db(tenant_id) as db:
                    # Find all active reservations where reserved_until < NOW() (RLS auto-filters)
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

                    if len(expired_reservations) > 0:
                        logger.info(f"⏰ Tenant {tenant_slug}: found {len(expired_reservations)} expired reservation(s)")

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
                                total_expired += 1
                                expired_space_ids.add(space_id)

                                logger.info(
                                    f"✅ Tenant {tenant_slug}: expired reservation {reservation_id[:8]}... "
                                    f"(booking: {external_booking_id}, ended: {reserved_until})"
                                )

                            except Exception as e:
                                logger.error(f"Error expiring reservation {reservation_id}: {e}")
                                self.stats["errors"] += 1

                        # Trigger reconciliation for all affected spaces
                        for space_id in expired_space_ids:
                            try:
                                await trigger_space_reconciliation(space_id, tenant_id=str(tenant_id))
                                self.stats["reconciliations_triggered"] += 1
                                total_reconciliations += 1
                                logger.debug(f"🔄 Triggered reconciliation for space {space_id}")
                            except Exception as e:
                                logger.error(f"Error triggering reconciliation for space {space_id}: {e}")
                                self.stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error processing tenant {tenant.get('tenant_slug', 'unknown')}: {e}", exc_info=True)
                self.stats["errors"] += 1
                continue  # Continue with other tenants

        self.stats["total_checks"] += 1

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"✅ Multi-tenant expiry complete: {total_expired} reservations expired across {len(tenants)} tenants "
            f"in {elapsed:.1f}s (reconciliations: {total_reconciliations}, errors: {self.stats['errors']})"
        )

        # Update stats registry
        await self.stats_registry.update_stats(
            task_name="reservation_expiry",
            success=True,
            custom_metrics={
                "tenants_checked": len(tenants),
                "reservations_expired": total_expired,
                "spaces_reconciled": total_reconciliations,
                "elapsed_seconds": elapsed
            }
        )


async def start_reservation_expiry_task(check_interval_minutes: int = 5):
    """Start the reservation expiry background task"""
    expiry_task = ReservationExpiryTask(check_interval_minutes=check_interval_minutes)
    await expiry_task.run_forever()
