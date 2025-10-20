# Display State Machine - Truth Table & Documentation

**Version:** 5.3
**Date:** 2025-10-20
**Status:** ✅ Implemented

---

## Overview

The Display State Machine is a **deterministic, priority-based system** that computes the correct display state (color/blink) for parking spaces by combining:

1. **Sensor readings** (occupied/vacant/unknown) with debouncing
2. **Reservation status** (reserved_now/reserved_soon/free)
3. **Admin overrides** (blocked/out_of_service)
4. **Per-tenant policies** (colors, thresholds, behaviors)

---

## Priority Levels (Highest to Lowest)

The state machine evaluates inputs in strict priority order:

| Priority | Input Type | Display State | Notes |
|----------|------------|---------------|-------|
| **1** | `out_of_service` (admin) | `MAINTENANCE` | Purple/config color, highest priority |
| **2** | `blocked` (admin) | `MAINTENANCE` | Gray/config color |
| **3** | `reserved_now` | `RESERVED` | Orange/config color, active reservation |
| **4** | `reserved_soon` | `RESERVED` | Yellow/config color, optional blink |
| **5** | `sensor: occupied` | `OCCUPIED` | Red/config color (after debouncing) |
| **5** | `sensor: vacant` | `FREE` | Green/config color (after debouncing) |
| **6** | `sensor: unknown` | _Hold last stable_ | Last confirmed state for 60s |
| **7** | _default_ | `FREE` | Green/config color, no data available |

---

## Truth Table

### Inputs

| Symbol | Meaning | Values |
|--------|---------|--------|
| `AO` | Admin Override | `out_of_service`, `blocked`, `none` |
| `RN` | Reservation Now | `true` (active), `false` |
| `RS` | Reservation Soon | `true` (within threshold), `false` |
| `SS` | Stable Sensor State | `occupied`, `vacant`, `unknown`, `null` |
| `ST` | Sensor Timeout | `true` (>60s), `false` |

### Output

| Symbol | Meaning |
|--------|---------|
| `DS` | Display State |
| `DC` | Display Color |
| `BL` | Blink |

---

### Complete Truth Table

| AO | RN | RS | SS | ST | → DS | → DC | → BL | Reason |
|----|----|----|----|----|------|------|------|--------|
| `out_of_service` | * | * | * | * | `MAINTENANCE` | `out_of_service_color` | `false` | **P1**: Admin override out_of_service |
| `blocked` | * | * | * | * | `MAINTENANCE` | `blocked_color` | `false` | **P2**: Admin override blocked |
| `none` | `true` | * | * | * | `RESERVED` | `reserved_color` | `false` | **P3**: Active reservation |
| `none` | `false` | `true` | * | * | `RESERVED` | `reserved_soon_color` | `policy.blink` | **P4**: Upcoming reservation |
| `none` | `false` | `false` | `occupied` | `false` | `OCCUPIED` | `occupied_color` | `false` | **P5**: Sensor occupied (stable) |
| `none` | `false` | `false` | `vacant` | `false` | `FREE` | `free_color` | `false` | **P5**: Sensor vacant (stable) |
| `none` | `false` | `false` | `unknown` | `false` | _last stable_ | _last color_ | _last blink_ | **P6**: Sensor unknown, hold state |
| `none` | `false` | `false` | `null` | * | `FREE` | `free_color` | `false` | **P7**: No data, default free |
| `none` | `false` | `false` | * | `true` | _last stable_ | _last color_ | _last blink_ | **P6**: Sensor timeout, hold state |

**Legend:**
- `*` = any value
- `→` = produces output
- **P1-P7** = Priority levels

---

## Sensor Debouncing Logic

To prevent flicker from noisy sensors, the system requires **2 consecutive identical readings** within the **debounce window** (default 10s) to confirm a state change.

### Debouncing State Machine

```
┌──────────────┐
│ Initial      │
│ (no data)    │
└──────┬───────┘
       │ reading₁
       ▼
┌──────────────┐    reading₂ (same)    ┌──────────────┐
│ Pending      │────within window──────▶│ Stable       │
│ (1 reading)  │                        │ (confirmed)  │
└──────┬───────┘                        └──────────────┘
       │
       │ reading₂ (different)
       │ OR timeout
       ▼
┌──────────────┐
│ Restart      │
│ Pending      │
└──────────────┘
```

### Debounce Examples

#### Example 1: Successful Confirmation
```
t=0s:   vacant  → pending (count=1)
t=5s:   vacant  → CONFIRMED (count=2) ✅ stable_state = vacant
t=10s:  vacant  → no change (already stable)
```

#### Example 2: Noisy Signal (Rejected)
```
t=0s:   vacant   → pending (count=1)
t=5s:   occupied → restart pending (different reading)
t=10s:  vacant   → restart pending (different reading)
t=15s:  vacant   → CONFIRMED (count=2) ✅ stable_state = vacant
```

#### Example 3: Timeout (Rejected)
```
t=0s:   vacant → pending (count=1)
t=12s:  vacant → restart pending (outside 10s window)
```

---

## Policy Configuration

Policies are **per-tenant configurable** via API (`/api/v1/display-policies`).

### Policy Fields

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `reserved_soon_threshold_sec` | int | 900 | 0-3600 | Show reserved_soon this many seconds before reservation |
| `sensor_unknown_timeout_sec` | int | 60 | 0-300 | Hold last stable state for this long |
| `debounce_window_sec` | int | 10 | 5-30 | Require 2 readings within this window |
| `occupied_color` | hex | `FF0000` | 6 chars | Red |
| `free_color` | hex | `00FF00` | 6 chars | Green |
| `reserved_color` | hex | `FFA500` | 6 chars | Orange |
| `reserved_soon_color` | hex | `FFFF00` | 6 chars | Yellow |
| `blocked_color` | hex | `808080` | 6 chars | Gray |
| `out_of_service_color` | hex | `800080` | 6 chars | Purple |
| `blink_reserved_soon` | bool | `false` | - | Enable blinking for reserved_soon |
| `blink_pattern_ms` | int | 500 | 100-2000 | On/off cycle time |
| `allow_sensor_override` | bool | `true` | - | Future: can sensor override reservation? |

### Example Policy

```json
{
  "name": "Standard Traffic Light",
  "thresholds": {
    "reserved_soon_threshold_sec": 900,
    "sensor_unknown_timeout_sec": 60,
    "debounce_window_sec": 10
  },
  "colors": {
    "occupied": "FF0000",
    "free": "00FF00",
    "reserved": "FFA500",
    "reserved_soon": "FFFF00",
    "blocked": "808080",
    "out_of_service": "800080"
  },
  "behaviors": {
    "blink_reserved_soon": true,
    "blink_pattern_ms": 500
  }
}
```

---

## API Endpoints

### Policy Management

- `GET /api/v1/display-policies?tenant_id={id}` - List policies
- `GET /api/v1/display-policies/{id}` - Get policy details
- `POST /api/v1/display-policies?tenant_id={id}` - Create policy
- `PATCH /api/v1/display-policies/{id}` - Update policy

### Admin Overrides

- `POST /api/v1/display-policies/admin-overrides` - Create override
- `DELETE /api/v1/display-policies/admin-overrides/{id}` - Remove override

### Computed State

- `GET /api/v1/display-policies/spaces/{space_id}/computed-state` - View state machine output

---

## Testing Scenarios

### Scenario 1: Normal Operation
```
Given: Space is free, no reservations
When:  Sensor detects occupied (×2 within 10s)
Then:  Display = OCCUPIED (red)
```

### Scenario 2: Reservation Priority
```
Given: Space is occupied (sensor), but reservation active
When:  Reservation starts
Then:  Display = RESERVED (orange) - overrides sensor
```

### Scenario 3: Admin Override
```
Given: Space is occupied with active reservation
When:  Admin marks space as out_of_service
Then:  Display = MAINTENANCE (purple) - highest priority
```

### Scenario 4: Noisy Sensor (Debouncing)
```
Given: Space is free (stable)
When:  Sensor flips: vacant → occupied → vacant → occupied
       (all within 1 second)
Then:  Display = FREE (no change, debouncing rejects noise)
```

### Scenario 5: Reserved Soon
```
Given: Space is free, reservation starts in 10 minutes
When:  Current time = 10 minutes before reservation
Then:  Display = RESERVED (yellow, blinking if enabled)
```

### Scenario 6: Sensor Timeout
```
Given: Space is occupied (stable)
When:  Sensor stops reporting (>60s)
Then:  Display = OCCUPIED (hold last stable state)
When:  Timeout continues for 5 minutes
Then:  Still OCCUPIED (hold indefinitely until new data)
```

---

## Implementation Files

| File | Purpose |
|------|---------|
| `migrations/006_display_state_machine.sql` | Database schema, tables, functions |
| `src/display_state_machine.py` | Core state machine logic, debouncing |
| `src/routers/display_policies.py` | REST API endpoints |
| `docs/DISPLAY_STATE_MACHINE_TRUTH_TABLE.md` | This document |

---

## Database Tables

### `display_policies`
Per-tenant configuration for display behavior.

### `sensor_debounce_state`
Tracks sensor reading history for each space:
- Last reading
- Pending state (awaiting confirmation)
- Stable state (confirmed after debouncing)
- Last display state

### `space_admin_overrides`
Admin overrides (blocked/out_of_service) with time ranges.

---

## Database Function

### `compute_display_state(space_id, tenant_id)`

PostgreSQL function that implements the priority logic:

```sql
SELECT * FROM compute_display_state(
    '550e8400-e29b-41d4-a716-446655440000',  -- space_id
    'tenant-uuid'                              -- tenant_id
);

-- Returns:
-- display_state | display_color | display_blink | priority_level | reason
-- OCCUPIED      | FF0000        | false         | 5              | Sensor: occupied
```

---

## View: `v_space_display_states`

Real-time monitoring view showing computed states for all spaces:

```sql
SELECT * FROM v_space_display_states
WHERE tenant_id = 'tenant-uuid'
ORDER BY space_code;
```

Columns:
- `space_id`, `space_code`, `space_name`
- `db_state` (current database state)
- `display_state`, `display_color`, `display_blink` (computed)
- `priority_level`, `reason` (why this state?)
- `stable_sensor_state`, `has_active_reservation`, `admin_override`

---

## Hysteresis & Edge Oscillation Mitigation

### Problem
Sensors near threshold values can oscillate rapidly, causing display flicker.

### Solutions Implemented

1. **Debouncing (5-30s window)**
   - Require 2 consecutive identical readings
   - Reject single anomalous readings

2. **Timeout Hold (60s)**
   - When sensor goes unknown, hold last stable state
   - Prevents flicker during brief network issues

3. **Configurable Thresholds**
   - Tenants can tune `debounce_window_sec` based on sensor behavior
   - Longer window = more stable, but slower response

4. **Priority Locking**
   - Once higher-priority state is active (e.g., reservation), sensor cannot override
   - Prevents "jitter" between reservation and sensor states

---

## Future Enhancements

1. **Predictive Reserved Soon**
   - Show yellow earlier for frequent users
   - ML-based arrival time prediction

2. **Sensor Confidence Scoring**
   - Use RSSI/SNR to weight readings
   - Ignore low-confidence readings

3. **Policy Scheduling**
   - Different policies for day/night
   - Weekend vs weekday behaviors

4. **A/B Testing**
   - Run multiple policies simultaneously
   - Compare user satisfaction metrics

---

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| ✅ Documented truth table | COMPLETE | This document |
| ✅ Tests show stable behavior under noisy signals | PENDING | Unit tests needed |
| ✅ Policy changeable without code deploy | COMPLETE | REST API + database |
| ✅ Per-tenant policies | COMPLETE | `display_policies.tenant_id` |
| ✅ Hysteresis/edge oscillation mitigation | COMPLETE | Debouncing + timeout hold |

---

## Changelog

**2025-10-20 - v5.3 Initial Implementation**
- Created database schema (migration 006)
- Implemented state machine logic
- Added REST API endpoints
- Created truth table documentation
- Deployed to `parking_v5` database

---

**Last Updated:** 2025-10-20
**Author:** Smart Parking Platform Team
**Related Docs:** `docs/v5.3-03-occupancy-display-state-machine.md`
