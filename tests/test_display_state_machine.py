"""
Unit tests for Display State Machine (v5.3)

Tests cover:
- Priority rules
- Sensor debouncing
- Noisy signal rejection
- Policy application
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import asyncio

# Import the modules we're testing
import sys
sys.path.insert(0, '/opt/v5-smart-parking/src')

from display_state_machine import (
    DisplayStateMachine,
    SensorState,
    SensorReading,
    DisplayPolicy,
    DebounceState
)


class MockDBPool:
    """Mock database pool for testing"""

    def __init__(self):
        self.data = {
            'debounce_states': {},
            'policies': {},
            'reservations': [],
            'overrides': []
        }
        self.execute_calls = []
        self.fetch_calls = []

    async def fetchrow(self, query, *args):
        """Mock fetchrow"""
        self.fetch_calls.append((query, args))

        # Mock policy fetch
        if 'display_policies' in query:
            tenant_id = str(args[0])
            return self.data['policies'].get(tenant_id)

        # Mock debounce state fetch
        if 'sensor_debounce_state' in query:
            space_id = str(args[0])
            return self.data['debounce_states'].get(space_id)

        # Mock compute_display_state function
        if 'compute_display_state' in query:
            return {
                'display_state': 'FREE',
                'display_color': '00FF00',
                'display_blink': False,
                'priority_level': 7,
                'reason': 'Test: default'
            }

        return None

    async def fetch(self, query, *args):
        """Mock fetch"""
        return []

    async def execute(self, query, *args):
        """Mock execute"""
        self.execute_calls.append((query, args))


@pytest.fixture
def db_pool():
    """Fixture for mock database pool"""
    return MockDBPool()


@pytest.fixture
def state_machine(db_pool):
    """Fixture for state machine instance"""
    return DisplayStateMachine(db_pool)


@pytest.fixture
def default_policy():
    """Fixture for default display policy"""
    return DisplayPolicy(
        id='policy-1',
        tenant_id='tenant-1',
        name='Test Policy',
        reserved_soon_threshold_sec=900,
        sensor_unknown_timeout_sec=60,
        debounce_window_sec=10,
        occupied_color='FF0000',
        free_color='00FF00',
        reserved_color='FFA500',
        reserved_soon_color='FFFF00',
        blocked_color='808080',
        out_of_service_color='800080',
        blink_reserved_soon=False,
        blink_pattern_ms=500,
        allow_sensor_override=True
    )


# ============================================================
# Test: Sensor Debouncing
# ============================================================

@pytest.mark.asyncio
async def test_debounce_single_reading_not_confirmed(state_machine, db_pool):
    """Single sensor reading should NOT change stable state"""

    space_id = 'space-1'
    tenant_id = 'tenant-1'

    # Initial state: free
    db_pool.data['debounce_states'][space_id] = {
        'space_id': space_id,
        'stable_sensor_state': 'vacant',
        'stable_since': datetime.utcnow() - timedelta(minutes=5),
        'last_sensor_state': 'vacant',
        'pending_sensor_state': None,
        'pending_since': None,
        'pending_count': 0
    }

    # Send ONE occupied reading
    reading = SensorReading(
        state=SensorState.OCCUPIED,
        timestamp=datetime.utcnow()
    )

    state_changed, _ = await state_machine.process_sensor_reading(
        space_id, tenant_id, reading
    )

    # Should NOT change (needs 2 readings)
    assert state_changed == False


@pytest.mark.asyncio
async def test_debounce_two_readings_confirmed(state_machine, db_pool, default_policy):
    """Two consecutive identical readings within window should confirm state change"""

    space_id = 'space-1'
    tenant_id = 'tenant-1'

    # Setup policy
    db_pool.data['policies'][tenant_id] = {
        'id': default_policy.id,
        'tenant_id': tenant_id,
        'name': default_policy.name,
        'reserved_soon_threshold_sec': default_policy.reserved_soon_threshold_sec,
        'sensor_unknown_timeout_sec': default_policy.sensor_unknown_timeout_sec,
        'debounce_window_sec': default_policy.debounce_window_sec,
        'occupied_color': default_policy.occupied_color,
        'free_color': default_policy.free_color,
        'reserved_color': default_policy.reserved_color,
        'reserved_soon_color': default_policy.reserved_soon_color,
        'blocked_color': default_policy.blocked_color,
        'out_of_service_color': default_policy.out_of_service_color,
        'blink_reserved_soon': default_policy.blink_reserved_soon,
        'blink_pattern_ms': default_policy.blink_pattern_ms,
        'allow_sensor_override': default_policy.allow_sensor_override
    }

    # Initial state: free
    db_pool.data['debounce_states'][space_id] = {
        'space_id': space_id,
        'stable_sensor_state': 'vacant',
        'stable_since': datetime.utcnow() - timedelta(minutes=5),
        'last_sensor_state': 'vacant',
        'pending_sensor_state': None,
        'pending_since': None,
        'pending_count': 0
    }

    now = datetime.utcnow()

    # First reading: occupied
    reading1 = SensorReading(state=SensorState.OCCUPIED, timestamp=now)
    state_changed1, _ = await state_machine.process_sensor_reading(
        space_id, tenant_id, reading1
    )
    assert state_changed1 == False  # Pending

    # Second reading: occupied (5 seconds later, within 10s window)
    reading2 = SensorReading(
        state=SensorState.OCCUPIED,
        timestamp=now + timedelta(seconds=5)
    )
    state_changed2, command = await state_machine.process_sensor_reading(
        space_id, tenant_id, reading2
    )

    # Should CONFIRM state change
    assert state_changed2 == True
    assert command is not None


@pytest.mark.asyncio
async def test_debounce_timeout_resets_pending(state_machine, db_pool, default_policy):
    """Readings outside debounce window should reset pending state"""

    space_id = 'space-1'
    tenant_id = 'tenant-1'

    # Setup
    db_pool.data['policies'][tenant_id] = {**default_policy.__dict__}
    db_pool.data['debounce_states'][space_id] = {
        'space_id': space_id,
        'stable_sensor_state': 'vacant',
        'stable_since': datetime.utcnow() - timedelta(minutes=5),
        'last_sensor_state': 'vacant',
        'pending_sensor_state': 'occupied',  # Already pending
        'pending_since': datetime.utcnow() - timedelta(seconds=15),  # 15s ago (> 10s window)
        'pending_count': 1
    }

    # Send another occupied reading (but too late)
    reading = SensorReading(
        state=SensorState.OCCUPIED,
        timestamp=datetime.utcnow()
    )

    state_changed, _ = await state_machine.process_sensor_reading(
        space_id, tenant_id, reading
    )

    # Should NOT confirm (timeout reset)
    assert state_changed == False


@pytest.mark.asyncio
async def test_noisy_signal_rejected(state_machine, db_pool, default_policy):
    """Rapid oscillating readings should be rejected"""

    space_id = 'space-1'
    tenant_id = 'tenant-1'

    # Setup
    db_pool.data['policies'][tenant_id] = {**default_policy.__dict__}
    db_pool.data['debounce_states'][space_id] = {
        'space_id': space_id,
        'stable_sensor_state': 'vacant',
        'stable_since': datetime.utcnow() - timedelta(minutes=5),
        'last_sensor_state': 'vacant',
        'pending_sensor_state': None,
        'pending_since': None,
        'pending_count': 0
    }

    now = datetime.utcnow()

    # Simulate noisy sensor: vacant → occupied → vacant → occupied
    readings = [
        SensorReading(state=SensorState.OCCUPIED, timestamp=now),
        SensorReading(state=SensorState.VACANT, timestamp=now + timedelta(seconds=1)),
        SensorReading(state=SensorState.OCCUPIED, timestamp=now + timedelta(seconds=2)),
        SensorReading(state=SensorState.VACANT, timestamp=now + timedelta(seconds=3)),
    ]

    state_changes = 0
    for reading in readings:
        state_changed, _ = await state_machine.process_sensor_reading(
            space_id, tenant_id, reading
        )
        if state_changed:
            state_changes += 1

    # Should NOT confirm any changes (all rejected due to noise)
    assert state_changes == 0


# ============================================================
# Test: Policy Cache
# ============================================================

@pytest.mark.asyncio
async def test_policy_cache(state_machine, db_pool, default_policy):
    """Policy should be cached to avoid repeated DB queries"""

    tenant_id = 'tenant-1'
    db_pool.data['policies'][tenant_id] = {**default_policy.__dict__}

    # First call - should query DB
    policy1 = await state_machine._get_display_policy(tenant_id)
    assert len(db_pool.fetch_calls) == 1

    # Second call - should use cache
    policy2 = await state_machine._get_display_policy(tenant_id)
    assert len(db_pool.fetch_calls) == 1  # No new query

    assert policy1.id == policy2.id


@pytest.mark.asyncio
async def test_policy_cache_invalidation(state_machine, db_pool, default_policy):
    """Cache should be invalidated on policy update"""

    tenant_id = 'tenant-1'
    db_pool.data['policies'][tenant_id] = {**default_policy.__dict__}

    # Get policy (caches it)
    await state_machine._get_display_policy(tenant_id)

    # Invalidate cache
    await state_machine.invalidate_policy_cache(tenant_id)

    # Next call should query DB again
    initial_calls = len(db_pool.fetch_calls)
    await state_machine._get_display_policy(tenant_id)
    assert len(db_pool.fetch_calls) > initial_calls


# ============================================================
# Test: Default Policy
# ============================================================

@pytest.mark.asyncio
async def test_default_policy_when_none_configured(state_machine, db_pool):
    """Should return default policy if tenant has none configured"""

    tenant_id = 'new-tenant'
    # No policy in db_pool.data

    policy = await state_machine._get_display_policy(tenant_id)

    assert policy.name == "Default Policy"
    assert policy.debounce_window_sec == 10
    assert policy.free_color == "00FF00"


# ============================================================
# Test: Debounce State Persistence
# ============================================================

@pytest.mark.asyncio
async def test_debounce_state_saved(state_machine, db_pool):
    """Debounce state should be persisted to database"""

    state = DebounceState(
        space_id='space-1',
        last_sensor_state=SensorState.OCCUPIED,
        stable_sensor_state=SensorState.OCCUPIED,
        stable_since=datetime.utcnow()
    )

    await state_machine._save_debounce_state(state)

    # Check that execute was called with INSERT/UPDATE
    assert len(db_pool.execute_calls) == 1
    query, args = db_pool.execute_calls[0]
    assert 'sensor_debounce_state' in query
    assert 'space-1' in str(args[0])


# ============================================================
# Run Tests
# ============================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
