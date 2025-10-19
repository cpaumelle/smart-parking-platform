"""
State management with distributed locking
Handles state transitions and prevents race conditions
"""
import redis.asyncio as redis
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import json
from contextlib import asynccontextmanager

from .models import SpaceState
from .exceptions import StateTransitionError

logger = logging.getLogger(__name__)

@dataclass
class StateUpdateResult:
    """Result of state update operation"""
    success: bool
    previous_state: SpaceState
    new_state: SpaceState
    display_updated: bool = False
    error: Optional[str] = None

class StateManager:
    """
    Manages parking space states with distributed locking
    Prevents race conditions in concurrent updates
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        SpaceState.FREE: [SpaceState.OCCUPIED, SpaceState.RESERVED, SpaceState.MAINTENANCE],
        SpaceState.OCCUPIED: [SpaceState.FREE, SpaceState.MAINTENANCE],
        SpaceState.RESERVED: [SpaceState.OCCUPIED, SpaceState.FREE, SpaceState.MAINTENANCE],
        SpaceState.MAINTENANCE: [SpaceState.FREE]
    }

    def __init__(self, db_pool, redis_url: str, chirpstack_client=None):
        self.db_pool = db_pool
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.chirpstack_client = chirpstack_client
        self.lock_timeout = 5  # seconds
        self.cache_ttl = 300  # 5 minutes

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(self.redis_url)
        await self.redis_client.ping()
        logger.info("State manager initialized with Redis")

    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.close()

    async def ping(self):
        """Health check"""
        return await self.redis_client.ping()

    @asynccontextmanager
    async def acquire_lock(self, resource: str, timeout: int = None):
        """
        Acquire distributed lock for a resource
        """
        lock_key = f"lock:{resource}"
        lock_value = f"{datetime.utcnow().timestamp()}"
        timeout = timeout or self.lock_timeout

        # Try to acquire lock
        acquired = await self.redis_client.set(
            lock_key,
            lock_value,
            nx=True,  # Only set if not exists
            ex=timeout
        )

        if not acquired:
            # Wait and retry once
            await asyncio.sleep(0.1)
            acquired = await self.redis_client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=timeout
            )

        if not acquired:
            raise StateTransitionError(
                f"Could not acquire lock for {resource}",
                None, None
            )

        try:
            yield
        finally:
            # Release lock only if we own it
            current = await self.redis_client.get(lock_key)
            if current and current.decode() == lock_value:
                await self.redis_client.delete(lock_key)

    async def update_space_state(
        self,
        space_id: str,
        new_state: SpaceState,
        source: str,
        request_id: str
    ) -> StateUpdateResult:
        """
        Update space state with validation and locking
        """

        async with self.acquire_lock(f"space:{space_id}"):
            try:
                # Get current state from database
                space = await self.db_pool.get_space(space_id)
                if not space:
                    return StateUpdateResult(
                        success=False,
                        previous_state=None,
                        new_state=new_state,
                        error="Space not found"
                    )

                current_state = SpaceState(space.state)

                # Check if state actually changed
                if current_state == new_state:
                    logger.debug(f"[{request_id}] State unchanged for space {space_id}: {current_state}")
                    return StateUpdateResult(
                        success=True,
                        previous_state=current_state,
                        new_state=new_state
                    )

                # Validate transition
                if not self.is_valid_transition(current_state, new_state, source):
                    error = f"Invalid transition from {current_state} to {new_state} via {source}"
                    logger.warning(f"[{request_id}] {error}")
                    raise StateTransitionError(error, current_state.value, new_state.value)

                # Update database
                await self.db_pool.execute("""
                    UPDATE spaces 
                    SET state = $1, updated_at = NOW()
                    WHERE id = $2
                """, new_state.value, space_id)

                # Record state change
                await self.db_pool.execute("""
                    INSERT INTO state_changes (
                        space_id, previous_state, new_state,
                        source, request_id, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                """, space_id, current_state.value, new_state.value, source, request_id)

                # Clear cache
                await self.invalidate_cache(space_id)

                # Update display if configured
                display_updated = False
                if space.display_eui:
                    display_updated = await self.update_display(
                        space_id=space_id,
                        display_eui=space.display_eui,
                        previous_state=current_state,
                        new_state=new_state,
                        trigger_type=source,
                        trigger_source=request_id
                    )

                logger.info(
                    f"[{request_id}] State updated for space {space_id}: "
                    f"{current_state} -> {new_state} (source: {source})"
                )

                return StateUpdateResult(
                    success=True,
                    previous_state=current_state,
                    new_state=new_state,
                    display_updated=display_updated
                )

            except StateTransitionError:
                raise
            except Exception as e:
                logger.error(f"[{request_id}] State update failed: {e}", exc_info=True)
                return StateUpdateResult(
                    success=False,
                    previous_state=current_state if 'current_state' in locals() else None,
                    new_state=new_state,
                    error=str(e)
                )

    def is_valid_transition(
        self,
        current_state: SpaceState,
        new_state: SpaceState,
        source: str
    ) -> bool:
        """Check if state transition is valid"""

        # Manual overrides can transition to any state
        if source == "manual":
            return True

        # Check valid transitions
        valid_states = self.VALID_TRANSITIONS.get(current_state, [])
        return new_state in valid_states

    async def update_display(
        self,
        space_id: str,
        display_eui: str,
        previous_state: SpaceState,
        new_state: SpaceState,
        trigger_type: str,
        trigger_source: str
    ) -> bool:
        """Update display device via ChirpStack downlink with actuation audit logging"""
        if not self.chirpstack_client:
            logger.warning(f"Cannot update display {display_eui}: ChirpStack client not available")
            return False

        start_time = datetime.utcnow()
        downlink_sent = False
        downlink_error = None
        queue_id = None
        display_device_id = None
        payload_hex = None
        fport = None

        try:
            # Fetch display device configuration from database
            display = await self.db_pool.fetchrow("""
                SELECT id, dev_eui, device_type, device_model, display_codes, fport, confirmed_downlinks
                FROM display_devices
                WHERE dev_eui = $1 AND enabled = TRUE
            """, display_eui)

            if not display:
                downlink_error = "Display device not found in registry or disabled"
                logger.error(f"{downlink_error}: {display_eui}")
                return False

            display_device_id = display['id']

            # Get display codes (state -> hex payload mapping)
            display_codes = display['display_codes']
            if isinstance(display_codes, str):
                display_codes = json.loads(display_codes)

            # Get payload for current state
            payload_hex = display_codes.get(new_state.value)
            if not payload_hex:
                downlink_error = f"No payload configured for state {new_state.value}"
                logger.error(f"{downlink_error} on display {display_eui}")
                return False

            # Convert hex string to bytes
            payload = bytes.fromhex(payload_hex)

            # Get FPort from device config
            fport = display['fport']
            confirmed = display['confirmed_downlinks']

            # Queue downlink via ChirpStack
            result = await self.chirpstack_client.queue_downlink(
                device_eui=display_eui,
                payload=payload,
                fport=fport,
                confirmed=confirmed
            )

            queue_id = result.get('id')
            downlink_sent = True
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)

            logger.info(
                f"Queued downlink for display {display_eui} ({display['device_type']}): "
                f"state={new_state.value}, payload={payload_hex}, fport={fport}, queue_id={queue_id}"
            )

            # Log actuation to database
            await self.db_pool.execute("""
                INSERT INTO actuations (
                    space_id, trigger_type, trigger_source,
                    previous_state, new_state,
                    display_deveui, display_device_id, display_code,
                    fport, confirmed,
                    downlink_sent, downlink_queue_id,
                    response_time_ms,
                    created_at, sent_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            """,
                space_id, trigger_type, trigger_source,
                previous_state.value, new_state.value,
                display_eui, display_device_id, payload_hex,
                fport, confirmed,
                downlink_sent, queue_id,
                response_time_ms,
                start_time, end_time
            )

            return True

        except Exception as e:
            downlink_error = str(e)
            logger.error(f"Failed to queue downlink for display {display_eui}: {e}", exc_info=True)

            # Log failed actuation
            try:
                await self.db_pool.execute("""
                    INSERT INTO actuations (
                        space_id, trigger_type, trigger_source,
                        previous_state, new_state,
                        display_deveui, display_device_id, display_code,
                        fport, confirmed,
                        downlink_sent, downlink_error,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                    space_id, trigger_type, trigger_source,
                    previous_state.value if previous_state else None, new_state.value,
                    display_eui, display_device_id, payload_hex,
                    fport, False,
                    downlink_sent, downlink_error,
                    start_time
                )
            except Exception as log_error:
                logger.error(f"Failed to log actuation error: {log_error}")

            return False

    async def check_availability(
        self,
        space_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """Check if space is available for reservation"""

        # Check for overlapping reservations
        overlapping = await self.db_pool.fetchval("""
            SELECT COUNT(*) FROM reservations
            WHERE space_id = $1
            AND status = 'active'
            AND (
                (start_time <= $2 AND end_time > $2) OR
                (start_time < $3 AND end_time >= $3) OR
                (start_time >= $2 AND end_time <= $3)
            )
        """, space_id, start_time, end_time)

        return overlapping == 0

    async def get_active_reservation_count(self) -> int:
        """Get count of active reservations"""
        return await self.db_pool.fetchval("""
            SELECT COUNT(*) FROM reservations
            WHERE status = 'active'
            AND end_time > NOW()
        """) or 0

    async def invalidate_cache(self, space_id: str):
        """Invalidate cached space data"""
        cache_keys = [
            f"space:{space_id}",
            f"space:{space_id}:state",
            f"spaces:all"
        ]

        for key in cache_keys:
            await self.redis_client.delete(key)
