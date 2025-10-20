"""
Background task manager for periodic jobs
Handles reservation scheduling, cleanup, and monitoring
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Set
from datetime import datetime, timedelta
from dataclasses import dataclass

from .models import Reservation, SpaceState

logger = logging.getLogger(__name__)

@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    task_id: str
    reservation_id: str
    space_id: str
    action: str  # 'start' or 'end'
    scheduled_time: datetime
    task_handle: Optional[asyncio.Task] = None

class BackgroundTaskManager:
    """
    Manages background tasks for the parking system
    Handles reservation scheduling, cleanup, and monitoring
    """

    def __init__(self, db_pool, state_manager, chirpstack_client=None, gateway_monitor=None):
        self.db_pool = db_pool
        self.state_manager = state_manager
        self.chirpstack_client = chirpstack_client
        self.gateway_monitor = gateway_monitor
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._queue_cleanup_task: Optional[asyncio.Task] = None
        self._reconciliation_task: Optional[asyncio.Task] = None
        self._reservation_expiry_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background task manager"""
        if self.running:
            return

        self.running = True
        logger.info("Starting background task manager...")

        # Start periodic tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Start queue cleanup if ChirpStack client available
        if self.chirpstack_client and self.gateway_monitor:
            self._queue_cleanup_task = asyncio.create_task(self._queue_cleanup_loop())
            logger.info("Started downlink queue cleanup task")

        # Start display reconciliation task
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        logger.info("Started display reconciliation task")

        # Start reservation expiry task
        self._reservation_expiry_task = asyncio.create_task(self._reservation_expiry_loop())
        logger.info("Started reservation expiry task")

        # Load and schedule active reservations
        await self._load_active_reservations()

        logger.info("Background task manager started")

    async def stop(self):
        """Stop background task manager"""
        if not self.running:
            return

        logger.info("Stopping background task manager...")
        self.running = False

        # Cancel all scheduled tasks
        for task_id, scheduled_task in self.scheduled_tasks.items():
            if scheduled_task.task_handle:
                scheduled_task.task_handle.cancel()

        self.scheduled_tasks.clear()

        # Cancel periodic tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._queue_cleanup_task:
            self._queue_cleanup_task.cancel()
        if self._reconciliation_task:
            self._reconciliation_task.cancel()
        if self._reservation_expiry_task:
            self._reservation_expiry_task.cancel()

        logger.info("Background task manager stopped")

    async def schedule_reservation(self, reservation: Reservation):
        """
        Schedule tasks for a reservation
        Creates tasks to update space state at start and end times
        """
        try:
            now = datetime.utcnow()

            # Schedule start task (set to RESERVED)
            if reservation.start_time > now:
                start_task_id = f"res_{reservation.id}_start"
                delay = (reservation.start_time - now).total_seconds()

                task = asyncio.create_task(
                    self._reservation_start_task(
                        reservation.id,
                        reservation.space_id,
                        delay
                    )
                )

                self.scheduled_tasks[start_task_id] = ScheduledTask(
                    task_id=start_task_id,
                    reservation_id=str(reservation.id),
                    space_id=str(reservation.space_id),
                    action='start',
                    scheduled_time=reservation.start_time,
                    task_handle=task
                )

                logger.info(f"Scheduled reservation start: {start_task_id} in {delay:.0f}s")

            # Schedule end task (set to FREE)
            if reservation.end_time > now:
                end_task_id = f"res_{reservation.id}_end"
                delay = (reservation.end_time - now).total_seconds()

                task = asyncio.create_task(
                    self._reservation_end_task(
                        reservation.id,
                        reservation.space_id,
                        delay
                    )
                )

                self.scheduled_tasks[end_task_id] = ScheduledTask(
                    task_id=end_task_id,
                    reservation_id=str(reservation.id),
                    space_id=str(reservation.space_id),
                    action='end',
                    scheduled_time=reservation.end_time,
                    task_handle=task
                )

                logger.info(f"Scheduled reservation end: {end_task_id} in {delay:.0f}s")

        except Exception as e:
            logger.error(f"Failed to schedule reservation {reservation.id}: {e}", exc_info=True)

    async def cancel_reservation_tasks(self, reservation_id: str):
        """Cancel scheduled tasks for a reservation"""
        cancelled = []

        for task_id, scheduled_task in list(self.scheduled_tasks.items()):
            if scheduled_task.reservation_id == str(reservation_id):
                if scheduled_task.task_handle:
                    scheduled_task.task_handle.cancel()
                del self.scheduled_tasks[task_id]
                cancelled.append(task_id)

        if cancelled:
            logger.info(f"Cancelled tasks for reservation {reservation_id}: {cancelled}")

    async def _reservation_start_task(self, reservation_id, space_id, delay: float):
        """Task to start a reservation"""
        try:
            await asyncio.sleep(delay)

            logger.info(f"Starting reservation {reservation_id} for space {space_id}")

            # Update space to RESERVED
            await self.state_manager.update_space_state(
                space_id=str(space_id),
                new_state=SpaceState.RESERVED,
                source="reservation_start",
                request_id=f"bg_task_{reservation_id}"
            )

            # Remove from scheduled tasks
            task_id = f"res_{reservation_id}_start"
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]

        except asyncio.CancelledError:
            logger.debug(f"Reservation start task cancelled: {reservation_id}")
        except Exception as e:
            logger.error(f"Reservation start task failed: {e}", exc_info=True)

    async def _reservation_end_task(self, reservation_id, space_id, delay: float):
        """Task to end a reservation"""
        try:
            await asyncio.sleep(delay)

            logger.info(f"Ending reservation {reservation_id} for space {space_id}")

            # Update space to FREE
            await self.state_manager.update_space_state(
                space_id=str(space_id),
                new_state=SpaceState.FREE,
                source="reservation_end",
                request_id=f"bg_task_{reservation_id}"
            )

            # Mark reservation as expired (v5.3)
            await self.db_pool.execute("""
                UPDATE reservations
                SET status = 'expired', updated_at = NOW()
                WHERE id = $1 AND status IN ('pending', 'confirmed')
            """, reservation_id)

            # Remove from scheduled tasks
            task_id = f"res_{reservation_id}_end"
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]

        except asyncio.CancelledError:
            logger.debug(f"Reservation end task cancelled: {reservation_id}")
        except Exception as e:
            logger.error(f"Reservation end task failed: {e}", exc_info=True)

    async def _cleanup_loop(self):
        """Periodic cleanup of expired data"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour

                logger.debug("Running cleanup tasks...")

                # Clean old sensor readings (keep 30 days)
                cutoff = datetime.utcnow() - timedelta(days=30)
                deleted = await self.db_pool.execute("""
                    DELETE FROM sensor_readings
                    WHERE timestamp < $1
                """, cutoff)

                if deleted:
                    logger.info(f"Cleaned {deleted} old sensor readings")

                # NOTE: Reservation expiry now handled by dedicated _reservation_expiry_loop
                # This cleanup task only handles old data deletion

                # Clean old state changes (keep 90 days)
                cutoff = datetime.utcnow() - timedelta(days=90)
                await self.db_pool.execute("""
                    DELETE FROM state_changes
                    WHERE timestamp < $1
                """, cutoff)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}", exc_info=True)

    async def _monitoring_loop(self):
        """Periodic monitoring and health checks"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Count active reservations
                active_count = await self.state_manager.get_active_reservation_count()

                # Count scheduled tasks
                scheduled_count = len(self.scheduled_tasks)

                # Get space state distribution
                state_counts = await self.db_pool.fetch("""
                    SELECT state, COUNT(*) as count
                    FROM spaces
                    WHERE deleted_at IS NULL
                    GROUP BY state
                """)

                state_dist = {row['state']: row['count'] for row in state_counts}

                logger.info(
                    f"System status: "
                    f"Active reservations: {active_count}, "
                    f"Scheduled tasks: {scheduled_count}, "
                    f"Space states: {state_dist}"
                )

                # Detect stuck states (spaces occupied for more than 24 hours)
                stuck_spaces = await self.db_pool.fetch("""
                    SELECT id, code, state, updated_at
                    FROM spaces
                    WHERE state = 'OCCUPIED'
                    AND updated_at < NOW() - INTERVAL '24 hours'
                    AND deleted_at IS NULL
                """)

                if stuck_spaces:
                    logger.warning(
                        f"Found {len(stuck_spaces)} spaces in OCCUPIED state for >24h: "
                        f"{[s['code'] for s in stuck_spaces]}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}", exc_info=True)

    async def _load_active_reservations(self):
        """Load and schedule existing active/confirmed reservations on startup"""
        try:
            # Get all pending/confirmed reservations with future times
            reservations = await self.db_pool.fetch("""
                SELECT *
                FROM reservations
                WHERE status IN ('pending', 'confirmed')
                AND end_time > NOW()
                ORDER BY start_time
            """)

            for row in reservations:
                from .models import Reservation
                reservation = Reservation(**dict(row))
                await self.schedule_reservation(reservation)

            logger.info(f"Loaded and scheduled {len(reservations)} active reservations")

        except Exception as e:
            logger.error(f"Failed to load active reservations: {e}", exc_info=True)

    async def _queue_cleanup_loop(self):
        """
        Periodic cleanup of stuck downlinks
        Runs every 5 minutes to flush device queues when gateways are offline
        """
        while self.running:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                logger.debug("Running downlink queue cleanup check...")

                # Check gateway health
                gw_health = await self.gateway_monitor.get_health_summary()

                if gw_health['offline_count'] == 0:
                    # All gateways healthy, skip cleanup
                    logger.debug("All gateways online, skipping queue cleanup")
                    continue

                logger.warning(
                    f"Gateway issues detected: {gw_health['offline_count']} offline, "
                    f"{gw_health['online_count']} online. Checking for stuck downlinks..."
                )

                # Get all devices from ChirpStack with pending downlinks
                try:
                    # Query ChirpStack database for devices with old pending downlinks
                    async with self.chirpstack_client.pool.acquire() as conn:
                        stuck_devices = await conn.fetch("""
                            SELECT DISTINCT encode(dev_eui, 'hex') as dev_eui,
                                   COUNT(*) as pending_count,
                                   MIN(created_at) as oldest_downlink
                            FROM device_queue
                            WHERE is_pending = true
                              AND created_at < NOW() - INTERVAL '10 minutes'
                            GROUP BY dev_eui
                        """)

                    if not stuck_devices:
                        logger.debug("No stuck downlinks found")
                        continue

                    logger.warning(f"Found {len(stuck_devices)} devices with stuck downlinks")

                    # Flush stuck queues
                    for record in stuck_devices:
                        dev_eui = record['dev_eui']
                        pending_count = record['pending_count']
                        oldest = record['oldest_downlink']

                        logger.warning(
                            f"Flushing {pending_count} stuck downlink(s) for {dev_eui} "
                            f"(oldest: {oldest})"
                        )

                        try:
                            await self.chirpstack_client.flush_device_queue(dev_eui)
                            logger.info(f"✅ Flushed queue for {dev_eui}")
                        except Exception as e:
                            logger.error(f"Failed to flush queue for {dev_eui}: {e}")

                except Exception as e:
                    logger.error(f"Error querying stuck downlinks: {e}", exc_info=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue cleanup loop error: {e}", exc_info=True)

    async def _reconciliation_loop(self):
        """
        Periodic display reconciliation task
        Ensures displays are 100% in sync with database state
        Runs every 2 minutes for Class C (mains-powered) devices
        """
        while self.running:
            try:
                await asyncio.sleep(120)  # Run every 2 minutes

                logger.info("🔄 Starting display reconciliation check...")

                # Query all active spaces with displays
                spaces = await self.db_pool.fetch("""
                    SELECT
                        s.id, s.code, s.name, s.state,
                        s.display_eui,
                        dd.id as display_device_id,
                        dd.device_type,
                        dd.display_codes,
                        dd.fport,
                        dd.confirmed_downlinks,
                        dd.enabled
                    FROM spaces s
                    INNER JOIN display_devices dd ON s.display_eui = dd.dev_eui
                    WHERE s.deleted_at IS NULL
                      AND s.display_eui IS NOT NULL
                      AND dd.enabled = TRUE
                    ORDER BY s.updated_at DESC
                """)

                if not spaces:
                    logger.debug("No spaces with displays to reconcile")
                    continue

                logger.info(f"Reconciling {len(spaces)} spaces with displays")

                corrected_count = 0
                polled_count = 0
                error_count = 0

                for space in spaces:
                    try:
                        space_id = str(space['id'])
                        space_code = space['code']
                        display_eui = space['display_eui']
                        current_state = space['state']
                        device_type = space['device_type']

                        # Get last known display state from Redis
                        last_known_key = f"device:{display_eui}:last_kuando_uplink"
                        last_known = await self.state_manager.redis_client.get(last_known_key)

                        is_kuando = display_eui.startswith("202020")

                        if last_known:
                            # We have recent uplink data - verify it matches
                            last_data = json.loads(last_known)
                            last_rgb = last_data.get('rgb', [])

                            # Get expected RGB for current state
                            display_codes = space['display_codes']
                            if isinstance(display_codes, str):
                                display_codes = json.loads(display_codes)

                            expected_hex = display_codes.get(current_state)
                            if expected_hex:
                                # Parse expected RGB from hex
                                expected_bytes = bytes.fromhex(expected_hex)
                                expected_rgb = [expected_bytes[0], expected_bytes[1], expected_bytes[2]]

                                # Compare
                                if last_rgb != expected_rgb:
                                    logger.warning(
                                        f"⚠️ Display mismatch for {space_code}: "
                                        f"Expected {expected_rgb} ({current_state}), got {last_rgb}. "
                                        f"Sending correction downlink..."
                                    )

                                    # Send corrective downlink
                                    await self.state_manager.update_display(
                                        space_id=space_id,
                                        display_eui=display_eui,
                                        previous_state=SpaceState(current_state),
                                        new_state=SpaceState(current_state),  # Force refresh
                                        trigger_type="system_cleanup",
                                        trigger_source="reconciliation"
                                    )

                                    corrected_count += 1
                                else:
                                    logger.debug(f"✅ {space_code}: Display in sync")

                        else:
                            # No recent uplink data - send poll/refresh for Kuando
                            if is_kuando:
                                logger.info(f"📡 Polling {space_code} (no recent uplink data)")

                                # Send refresh downlink to current state (triggers auto-uplink)
                                await self.state_manager.update_display(
                                    space_id=space_id,
                                    display_eui=display_eui,
                                    previous_state=SpaceState(current_state),
                                    new_state=SpaceState(current_state),
                                    trigger_type="system_cleanup",
                                    trigger_source="reconciliation_poll"
                                )

                                polled_count += 1

                    except Exception as e:
                        error_count += 1
                        logger.error(f"Reconciliation error for space {space.get('code', 'unknown')}: {e}")

                # Summary logging
                logger.info(
                    f"✅ Reconciliation complete: "
                    f"{len(spaces)} checked, {corrected_count} corrected, "
                    f"{polled_count} polled, {error_count} errors"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconciliation loop error: {e}", exc_info=True)

    async def _reservation_expiry_loop(self):
        """
        Periodic task to expire reservations past their end_time
        Runs every 60 seconds to ensure timely expiry
        """
        while self.running:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Call the PostgreSQL function to expire old reservations
                result = await self.db_pool.fetchrow("SELECT * FROM expire_old_reservations()")

                if result and result['expired_count'] > 0:
                    expired_count = result['expired_count']
                    expired_ids = result['reservation_ids']

                    logger.info(
                        f"⏰ Expired {expired_count} reservation(s): "
                        f"{', '.join(str(rid) for rid in expired_ids[:5])}"
                        f"{' ...' if expired_count > 5 else ''}"
                    )

                    # Optionally: Update space states for expired reservations
                    # This ensures spaces are marked FREE after reservation expires
                    for reservation_id in expired_ids:
                        try:
                            # Get the space_id for this reservation
                            res_info = await self.db_pool.fetchrow("""
                                SELECT space_id, end_time
                                FROM reservations
                                WHERE id = $1
                            """, reservation_id)

                            if res_info:
                                # Update space to FREE (if not already occupied by sensor)
                                space_id = str(res_info['space_id'])

                                await self.state_manager.update_space_state(
                                    space_id=space_id,
                                    new_state=SpaceState.FREE,
                                    source="reservation_expired",
                                    request_id=f"expiry_{reservation_id}"
                                )

                                logger.debug(f"Updated space {space_id} to FREE after reservation expired")

                        except Exception as e:
                            logger.error(f"Failed to update space state for expired reservation {reservation_id}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reservation expiry loop error: {e}", exc_info=True)
