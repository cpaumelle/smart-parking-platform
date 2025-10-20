"""
Display State Machine for V5.3
Implements policy-driven occupancy display logic with:
- Priority-based state computation
- Sensor debouncing (2 consecutive readings)
- Admin overrides
- Per-tenant configurable policies
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .models import SpaceState

logger = logging.getLogger(__name__)


class SensorState(str, Enum):
    """Sensor reading states"""
    OCCUPIED = "occupied"
    VACANT = "vacant"
    UNKNOWN = "unknown"


class AdminOverrideType(str, Enum):
    """Admin override types"""
    BLOCKED = "blocked"
    OUT_OF_SERVICE = "out_of_service"


@dataclass
class DisplayPolicy:
    """Display policy configuration"""
    id: str
    tenant_id: str
    name: str

    # Thresholds
    reserved_soon_threshold_sec: int = 900  # 15 minutes
    sensor_unknown_timeout_sec: int = 60
    debounce_window_sec: int = 10

    # Colors
    occupied_color: str = "FF0000"
    free_color: str = "00FF00"
    reserved_color: str = "FFA500"
    reserved_soon_color: str = "FFFF00"
    blocked_color: str = "808080"
    out_of_service_color: str = "800080"

    # Behaviors
    blink_reserved_soon: bool = False
    blink_pattern_ms: int = 500
    allow_sensor_override: bool = True


@dataclass
class SensorReading:
    """Raw sensor reading"""
    state: SensorState
    timestamp: datetime
    rssi: Optional[int] = None
    snr: Optional[float] = None


@dataclass
class DebounceState:
    """Sensor debouncing state tracker"""
    space_id: str

    # Last reading
    last_sensor_state: Optional[SensorState] = None
    last_sensor_timestamp: Optional[datetime] = None

    # Pending state (awaiting confirmation)
    pending_sensor_state: Optional[SensorState] = None
    pending_since: Optional[datetime] = None
    pending_count: int = 0

    # Stable state (confirmed)
    stable_sensor_state: Optional[SensorState] = None
    stable_since: Optional[datetime] = None

    # Last display state
    last_display_state: Optional[str] = None
    last_display_color: Optional[str] = None
    last_display_blink: bool = False


@dataclass
class DisplayCommand:
    """Computed display command"""
    state: str
    color: str
    blink: bool
    priority_level: int
    reason: str
    expires_at: Optional[datetime] = None


class DisplayStateMachine:
    """
    Deterministic state machine for computing display states

    Priority order:
    1. out_of_service (admin override)
    2. blocked (admin override)
    3. reserved_now (active reservation)
    4. reserved_soon (upcoming reservation)
    5. sensor state (occupied/vacant) - with debouncing
    6. last stable state (sensor timeout)
    7. default (free)
    """

    def __init__(self, db_pool, redis_client=None):
        self.db_pool = db_pool
        self.redis_client = redis_client
        self._policy_cache: Dict[str, Tuple[DisplayPolicy, int]] = {}  # (policy, version)
        self._policy_cache_ttl = 300  # 5 minutes
        self._policy_cache_time: Dict[str, datetime] = {}

    async def process_sensor_reading(
        self,
        space_id: str,
        tenant_id: str,
        reading: SensorReading
    ) -> Tuple[bool, Optional[DisplayCommand]]:
        """
        Process sensor reading with debouncing logic

        Returns:
            (state_changed, display_command) tuple
            - state_changed: True if stable sensor state changed
            - display_command: New display command if state changed, else None
        """

        # Get or create debounce state
        debounce_state = await self._get_debounce_state(space_id)

        # Get display policy
        policy = await self._get_display_policy(tenant_id)

        # Update debounce state
        now = datetime.utcnow()
        state_changed = False

        if debounce_state.last_sensor_state != reading.state:
            # New state detected
            if debounce_state.pending_sensor_state == reading.state:
                # Same pending state - check if within debounce window
                time_diff = (now - debounce_state.pending_since).total_seconds()

                if time_diff <= policy.debounce_window_sec:
                    # Second reading within window - confirm state change!
                    debounce_state.pending_count += 1

                    if debounce_state.pending_count >= 2:
                        # CONFIRMED: Stable state changed
                        logger.info(
                            f"[DEBOUNCE] Space {space_id}: {debounce_state.stable_sensor_state} -> "
                            f"{reading.state} (confirmed after {debounce_state.pending_count} readings)"
                        )

                        debounce_state.stable_sensor_state = reading.state
                        debounce_state.stable_since = now
                        debounce_state.pending_sensor_state = None
                        debounce_state.pending_since = None
                        debounce_state.pending_count = 0
                        state_changed = True
                else:
                    # Outside window - restart pending
                    logger.debug(
                        f"[DEBOUNCE] Space {space_id}: Pending timeout "
                        f"({time_diff:.1f}s > {policy.debounce_window_sec}s), restarting"
                    )
                    debounce_state.pending_sensor_state = reading.state
                    debounce_state.pending_since = now
                    debounce_state.pending_count = 1
            else:
                # Different pending state - start new pending
                logger.debug(
                    f"[DEBOUNCE] Space {space_id}: New pending state {reading.state} "
                    f"(was {debounce_state.pending_sensor_state})"
                )
                debounce_state.pending_sensor_state = reading.state
                debounce_state.pending_since = now
                debounce_state.pending_count = 1
        else:
            # Same as last - reset pending
            debounce_state.pending_sensor_state = None
            debounce_state.pending_count = 0

        # Update last reading
        debounce_state.last_sensor_state = reading.state
        debounce_state.last_sensor_timestamp = reading.timestamp

        # Persist debounce state
        await self._save_debounce_state(debounce_state)

        # Compute display command if state changed
        display_command = None
        if state_changed:
            display_command = await self.compute_display_command(space_id, tenant_id)

            # Update last display state in debounce record
            if display_command:
                debounce_state.last_display_state = display_command.state
                debounce_state.last_display_color = display_command.color
                debounce_state.last_display_blink = display_command.blink
                await self._save_debounce_state(debounce_state)

        return (state_changed, display_command)

    async def compute_display_command(
        self,
        space_id: str,
        tenant_id: str
    ) -> DisplayCommand:
        """
        Compute display command using priority rules
        Calls PostgreSQL function compute_display_state()
        """

        result = await self.db_pool.fetchrow("""
            SELECT * FROM compute_display_state($1, $2)
        """, space_id, tenant_id)

        if not result:
            # Fallback to default
            policy = await self._get_display_policy(tenant_id)
            return DisplayCommand(
                state="FREE",
                color=policy.free_color,
                blink=False,
                priority_level=7,
                reason="Fallback: no data"
            )

        return DisplayCommand(
            state=result['display_state'],
            color=result['display_color'],
            blink=result['display_blink'],
            priority_level=result['priority_level'],
            reason=result['reason']
        )

    async def force_recompute_all_spaces(self, tenant_id: str) -> int:
        """
        Force recompute display state for all spaces in tenant
        Useful after policy changes

        Returns: Number of spaces recomputed
        """

        spaces = await self.db_pool.fetch("""
            SELECT id, code FROM spaces
            WHERE tenant_id = $1 AND deleted_at IS NULL
            ORDER BY code
        """, tenant_id)

        recomputed = 0
        for space in spaces:
            try:
                command = await self.compute_display_command(
                    str(space['id']),
                    tenant_id
                )

                logger.info(
                    f"[RECOMPUTE] Space {space['code']}: "
                    f"{command.state} ({command.color}) - {command.reason}"
                )

                recomputed += 1

                # TODO: Send display update if changed

            except Exception as e:
                logger.error(f"Failed to recompute space {space['code']}: {e}")

        logger.info(f"Recomputed {recomputed}/{len(spaces)} spaces for tenant {tenant_id}")
        return recomputed

    async def _get_display_policy(self, tenant_id: str) -> DisplayPolicy:
        """Get display policy for tenant (cached with Redis version key)"""

        # Get current version from Redis
        current_version = 0
        if self.redis_client:
            try:
                version_key = f"display_policy:tenant:{tenant_id}:v"
                version_bytes = await self.redis_client.get(version_key)
                current_version = int(version_bytes.decode()) if version_bytes else 0
            except Exception as e:
                logger.warning(f"Failed to get policy version from Redis: {e}")

        # Check cache with version matching
        cache_time = self._policy_cache_time.get(tenant_id)
        if cache_time and (datetime.utcnow() - cache_time).total_seconds() < self._policy_cache_ttl:
            cached_entry = self._policy_cache.get(tenant_id)
            if cached_entry:
                cached_policy, cached_version = cached_entry
                # Only use cache if version matches
                if cached_version == current_version:
                    return cached_policy
                else:
                    logger.debug(f"Policy cache stale for tenant {tenant_id}: v{cached_version} != v{current_version}")

        # Fetch from database
        row = await self.db_pool.fetchrow("""
            SELECT * FROM display_policies
            WHERE tenant_id = $1 AND is_active = true
            LIMIT 1
        """, tenant_id)

        if row:
            policy = DisplayPolicy(
                id=str(row['id']),
                tenant_id=str(row['tenant_id']),
                name=row['name'],
                reserved_soon_threshold_sec=row['reserved_soon_threshold_sec'],
                sensor_unknown_timeout_sec=row['sensor_unknown_timeout_sec'],
                debounce_window_sec=row['debounce_window_sec'],
                occupied_color=row['occupied_color'],
                free_color=row['free_color'],
                reserved_color=row['reserved_color'],
                reserved_soon_color=row['reserved_soon_color'],
                blocked_color=row['blocked_color'],
                out_of_service_color=row['out_of_service_color'],
                blink_reserved_soon=row['blink_reserved_soon'],
                blink_pattern_ms=row['blink_pattern_ms'],
                allow_sensor_override=row['allow_sensor_override']
            )
        else:
            # Default policy
            policy = DisplayPolicy(
                id="default",
                tenant_id=tenant_id,
                name="Default Policy"
            )

        # Cache it with version
        self._policy_cache[tenant_id] = (policy, current_version)
        self._policy_cache_time[tenant_id] = datetime.utcnow()

        logger.debug(f"Cached policy for tenant {tenant_id} at version {current_version}")
        return policy

    async def _get_debounce_state(self, space_id: str) -> DebounceState:
        """Get or create debounce state for space"""

        row = await self.db_pool.fetchrow("""
            SELECT * FROM sensor_debounce_state WHERE space_id = $1
        """, space_id)

        if row:
            return DebounceState(
                space_id=str(row['space_id']),
                last_sensor_state=SensorState(row['last_sensor_state']) if row['last_sensor_state'] else None,
                last_sensor_timestamp=row['last_sensor_timestamp'],
                pending_sensor_state=SensorState(row['pending_sensor_state']) if row['pending_sensor_state'] else None,
                pending_since=row['pending_since'],
                pending_count=row['pending_count'] or 0,
                stable_sensor_state=SensorState(row['stable_sensor_state']) if row['stable_sensor_state'] else None,
                stable_since=row['stable_since'],
                last_display_state=row['last_display_state'],
                last_display_color=row['last_display_color'],
                last_display_blink=row['last_display_blink']
            )
        else:
            # Create new
            return DebounceState(space_id=space_id)

    async def _save_debounce_state(self, state: DebounceState):
        """Save debounce state to database"""

        await self.db_pool.execute("""
            INSERT INTO sensor_debounce_state (
                space_id,
                last_sensor_state, last_sensor_timestamp,
                pending_sensor_state, pending_since, pending_count,
                stable_sensor_state, stable_since,
                last_display_state, last_display_color, last_display_blink,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            ON CONFLICT (space_id) DO UPDATE SET
                last_sensor_state = EXCLUDED.last_sensor_state,
                last_sensor_timestamp = EXCLUDED.last_sensor_timestamp,
                pending_sensor_state = EXCLUDED.pending_sensor_state,
                pending_since = EXCLUDED.pending_since,
                pending_count = EXCLUDED.pending_count,
                stable_sensor_state = EXCLUDED.stable_sensor_state,
                stable_since = EXCLUDED.stable_since,
                last_display_state = EXCLUDED.last_display_state,
                last_display_color = EXCLUDED.last_display_color,
                last_display_blink = EXCLUDED.last_display_blink,
                updated_at = NOW()
        """,
            state.space_id,
            state.last_sensor_state.value if state.last_sensor_state else None,
            state.last_sensor_timestamp,
            state.pending_sensor_state.value if state.pending_sensor_state else None,
            state.pending_since,
            state.pending_count,
            state.stable_sensor_state.value if state.stable_sensor_state else None,
            state.stable_since,
            state.last_display_state,
            state.last_display_color,
            state.last_display_blink
        )

    async def invalidate_policy_cache(self, tenant_id: str):
        """Invalidate policy cache for tenant"""
        if tenant_id in self._policy_cache:
            del self._policy_cache[tenant_id]
        if tenant_id in self._policy_cache_time:
            del self._policy_cache_time[tenant_id]

        logger.info(f"Invalidated policy cache for tenant {tenant_id}")
