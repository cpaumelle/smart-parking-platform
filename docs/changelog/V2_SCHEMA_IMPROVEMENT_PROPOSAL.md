# V2 Database Schema Improvement Proposal

**Based on V4 Architecture Analysis**  
**Date:** 2025-10-16  
**Status:** Proposal

---

## Executive Summary

The current V2 schema conflates **device metadata** with **space metadata** in the `spaces` table. V4's architecture demonstrates a superior approach with separate device registries. This proposal outlines a path to adopt V4's proven patterns while maintaining backward compatibility.

---

## Current V2 vs V4 Architecture

### Current V2 (Simple but Limited)

```
spaces table:
├── Space metadata: name, code, building, floor, zone, GPS
├── Device references: sensor_eui, display_eui (inline)
└── Current state: state field

Pros:
✅ Simple 1:1 mapping (one sensor → one space)
✅ Fast lookups (no joins needed)
✅ Works for fixed installations

Cons:
❌ No device inventory independent of spaces
❌ No device metadata (model, manufacturer, capabilities)
❌ Device swaps lose history
❌ Can't track device lifecycle (install/test/decommission)
❌ Display config hardcoded (not per-device)
```

### V4 (Flexible and Scalable)

```
Separate Registries:
├── parking_config.sensor_registry
│   ├── sensor_id (PK)
│   ├── dev_eui (unique)
│   ├── sensor_type, device_model, manufacturer
│   ├── payload_decoder
│   └── device_metadata (jsonb)
│
├── parking_config.display_registry
│   ├── display_id (PK)
│   ├── dev_eui (unique)
│   ├── display_type, device_model, manufacturer
│   ├── display_codes (jsonb) - per-device color mappings!
│   ├── fport, confirmed_downlinks
│   └── enabled, last_seen
│
└── parking_spaces.spaces
    ├── Space metadata: space_name, space_code, location
    ├── Device FKs: occupancy_sensor_id, display_device_id
    ├── Denormalized DevEUIs: occupancy_sensor_deveui, display_device_deveui (fast lookups!)
    └── Current state: current_state, sensor_state, display_state

Additional:
├── transform.device_context - Full device lifecycle tracking
├── transform.locations - Hierarchical location structure
└── parking_operations.actuations - Complete audit trail
```

---

## Key V4 Patterns to Adopt

### 1. Separate Device Registries

**V4 Pattern:**
```sql
-- Sensor registry with full metadata
parking_config.sensor_registry:
  - sensor_id (PK)
  - dev_eui (unique)
  - sensor_type, device_model, manufacturer
  - payload_decoder
  - enabled, created_at

-- Display registry with configuration
parking_config.display_registry:
  - display_id (PK)
  - dev_eui (unique)
  - display_type, device_model
  - display_codes (jsonb) - per-device!
  - fport, confirmed_downlinks
  - enabled, last_seen
```

**Benefits:**
- ✅ Device inventory independent of space assignments
- ✅ Store device-specific configuration (FPort 15 for Kuando!)
- ✅ Track device lifecycle (install → active → decommissioned)
- ✅ Device metadata (model, manufacturer, firmware)
- ✅ Per-device display color mappings (not hardcoded)

---

### 2. Foreign Key + Denormalized DevEUI Pattern

**V4 Pattern:**
```sql
parking_spaces.spaces:
  - occupancy_sensor_id (FK → sensor_registry.sensor_id)
  - occupancy_sensor_deveui (denormalized for fast lookup)
  - display_device_id (FK → display_registry.display_id)
  - display_device_deveui (denormalized for fast lookup)
```

**Why Both FK and DevEUI?**
- **FK (sensor_id, display_id):** Referential integrity, device metadata joins
- **Denormalized DevEUI:** Fast uplink lookup without joins (`WHERE sensor_deveui = 'xxx'`)

**Maintained via Trigger:**
```sql
CREATE TRIGGER sync_sensor_deveui
BEFORE INSERT OR UPDATE ON parking_spaces.spaces
FOR EACH ROW
EXECUTE FUNCTION sync_device_deveuis();
```

---

### 3. Actuation Audit Trail

**V4 Pattern:**
```sql
parking_operations.actuations:
  - actuation_id, space_id
  - trigger_type (sensor_uplink, api_reservation, manual_override)
  - previous_state → new_state
  - display_deveui, display_code (payload sent)
  - fport, confirmed
  - downlink_sent, downlink_confirmed
  - response_time_ms, downlink_error
  - retry_count
  - created_at, sent_at, confirmed_at
```

**Benefits:**
- ✅ Complete operational history
- ✅ Downlink success/failure tracking
- ✅ Performance metrics (response_time_ms)
- ✅ Debugging (trigger_type, downlink_error)
- ✅ Compliance (full audit trail)

---

### 4. Per-Device Display Configuration

**V4 Pattern:**
```sql
display_registry.display_codes (jsonb):
{
  "FREE": "0000FF6400",
  "OCCUPIED": "FF00006400",
  "RESERVED": "FF00FF6400",
  "MAINTENANCE": "FFA5006400"
}

display_registry.fport: 15  -- Kuando-specific!
```

**Current V2 Problem:**
```python
# Hardcoded in state_manager.py:
colors = {
    SpaceState.FREE: (0, 255, 0),
    SpaceState.OCCUPIED: (255, 0, 0),
    # ...
}
payload = bytes([r, b, g, 0x64, 0x00])  # Hardcoded format!
```

**V4 Solution:**
- Store color codes **per display** in database
- Different displays can have different colors
- No code changes needed to adjust colors
- Supports different display types (Kuando, LED matrix, e-paper)

---

## Proposed V2 Improvements

### Phase 1: Add Device Registries (Non-Breaking)

**New Tables:**

```sql
-- Sensor registry
CREATE TABLE sensor_devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dev_eui VARCHAR(16) NOT NULL UNIQUE,
  device_type VARCHAR(50) NOT NULL,  -- browan_tabs, dragino, etc.
  device_model VARCHAR(100),
  manufacturer VARCHAR(100),
  payload_decoder VARCHAR(100),  -- Handler class name
  capabilities JSONB DEFAULT '{}',  -- {occupancy, temperature, battery}
  enabled BOOLEAN DEFAULT TRUE,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Display registry
CREATE TABLE display_devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dev_eui VARCHAR(16) NOT NULL UNIQUE,
  device_type VARCHAR(50) NOT NULL,  -- kuando_busylight, led_matrix
  device_model VARCHAR(100),
  manufacturer VARCHAR(100),
  display_codes JSONB NOT NULL,  -- State → hex payload mappings
  fport INTEGER DEFAULT 1,  -- LoRaWAN FPort
  confirmed_downlinks BOOLEAN DEFAULT FALSE,
  enabled BOOLEAN DEFAULT TRUE,
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_sensor_devices_deveui ON sensor_devices(dev_eui, enabled) WHERE enabled = TRUE;
CREATE INDEX idx_display_devices_deveui ON display_devices(dev_eui, enabled) WHERE enabled = TRUE;
```

---

### Phase 2: Update Spaces Table (Breaking Change)

**Add foreign keys while keeping DevEUI columns:**

```sql
ALTER TABLE spaces
  ADD COLUMN sensor_device_id UUID REFERENCES sensor_devices(id),
  ADD COLUMN display_device_id UUID REFERENCES display_devices(id);

-- Keep sensor_eui and display_eui for backward compatibility and fast lookups
-- Rename for clarity:
ALTER TABLE spaces
  RENAME COLUMN sensor_eui TO sensor_deveui;
ALTER TABLE spaces
  RENAME COLUMN display_eui TO display_deveui;

-- Sync trigger to maintain denormalized DevEUIs
CREATE OR REPLACE FUNCTION sync_device_deveuis()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.sensor_device_id IS NOT NULL THEN
    NEW.sensor_deveui := (SELECT dev_eui FROM sensor_devices WHERE id = NEW.sensor_device_id);
  END IF;
  
  IF NEW.display_device_id IS NOT NULL THEN
    NEW.display_deveui := (SELECT dev_eui FROM display_devices WHERE id = NEW.display_device_id);
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER spaces_sync_deveuis
BEFORE INSERT OR UPDATE ON spaces
FOR EACH ROW
EXECUTE FUNCTION sync_device_deveuis();
```

---

### Phase 3: Add Actuation Audit Trail

```sql
CREATE TABLE actuations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  space_id UUID NOT NULL REFERENCES spaces(id),
  trigger_type VARCHAR(30) NOT NULL,  -- sensor_uplink, api_reservation, manual_override
  trigger_source VARCHAR(100),  -- uplink_id, reservation_id, api_key_id
  previous_state VARCHAR(20),
  new_state VARCHAR(20) NOT NULL,
  display_deveui VARCHAR(16) NOT NULL,
  display_code VARCHAR(20) NOT NULL,  -- Hex payload sent
  fport INTEGER,
  confirmed BOOLEAN DEFAULT FALSE,
  downlink_sent BOOLEAN DEFAULT FALSE,
  downlink_error TEXT,
  response_time_ms INTEGER,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sent_at TIMESTAMPTZ,
  confirmed_at TIMESTAMPTZ,
  
  CONSTRAINT valid_trigger_type CHECK (trigger_type IN (
    'sensor_uplink', 'api_reservation', 'manual_override', 'system_cleanup', 'reservation_expired'
  ))
);

CREATE INDEX idx_actuations_space_time ON actuations(space_id, created_at DESC);
CREATE INDEX idx_actuations_trigger ON actuations(trigger_type, created_at DESC);
CREATE INDEX idx_actuations_errors ON actuations(downlink_sent, downlink_error)
  WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL;
```

---

## Migration Path

### Step 1: Create New Tables (No Downtime)

```sql
-- Create sensor_devices and display_devices tables
-- Populate from existing spaces table
INSERT INTO sensor_devices (dev_eui, device_type, device_model)
SELECT DISTINCT sensor_eui, 'occupancy', 'Unknown'
FROM spaces
WHERE sensor_eui IS NOT NULL;

INSERT INTO display_devices (dev_eui, device_type, device_model, display_codes, fport)
SELECT DISTINCT 
  display_eui, 
  'kuando_busylight',
  'Kuando Busylight IoT Omega',
  '{
    "FREE": "0000FF6400",
    "OCCUPIED": "FF00006400",
    "RESERVED": "FF00FF6400",
    "MAINTENANCE": "FFA5006400"
  }'::jsonb,
  15
FROM spaces
WHERE display_eui IS NOT NULL;
```

### Step 2: Add Foreign Keys (Minimal Downtime)

```sql
-- Add FK columns (nullable during migration)
ALTER TABLE spaces
  ADD COLUMN sensor_device_id UUID,
  ADD COLUMN display_device_id UUID;

-- Populate FKs
UPDATE spaces SET sensor_device_id = (
  SELECT id FROM sensor_devices WHERE dev_eui = spaces.sensor_eui
);

UPDATE spaces SET display_device_id = (
  SELECT id FROM display_devices WHERE dev_eui = spaces.display_eui
);

-- Add FK constraints
ALTER TABLE spaces
  ADD CONSTRAINT fk_sensor_device FOREIGN KEY (sensor_device_id) REFERENCES sensor_devices(id),
  ADD CONSTRAINT fk_display_device FOREIGN KEY (display_device_id) REFERENCES display_devices(id);
```

### Step 3: Update Application Code

**Old Code (V2 Current):**
```python
# Hardcoded colors
colors = {SpaceState.FREE: (0, 255, 0)}
payload = bytes([r, b, g, 0x64, 0x00])

# Queue downlink
await chirpstack_client.queue_downlink(
    device_eui=display_eui,
    payload=payload,
    fport=15  # Hardcoded!
)
```

**New Code (V2 Improved):**
```python
# Get display config from database
display = await db_pool.fetchrow("""
    SELECT dev_eui, display_codes, fport
    FROM display_devices
    WHERE id = $1
""", space.display_device_id)

# Get color code for state
payload_hex = display['display_codes'][new_state]
payload = bytes.fromhex(payload_hex)

# Queue downlink with per-device config
await chirpstack_client.queue_downlink(
    device_eui=display['dev_eui'],
    payload=payload,
    fport=display['fport']  # From DB!
)

# Log actuation
await db_pool.execute("""
    INSERT INTO actuations (
        space_id, trigger_type, previous_state, new_state,
        display_deveui, display_code, fport, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
""", space_id, 'sensor_uplink', prev_state, new_state, 
    display['dev_eui'], payload_hex, display['fport'])
```

---

## Benefits of Proposed Changes

### Device Management
✅ Separate device inventory from space assignments  
✅ Track device metadata (model, manufacturer, capabilities)  
✅ Device lifecycle management (install → test → active → decommissioned)  
✅ Easy device swaps (update FK, history preserved)  

### Configuration Flexibility
✅ Per-device display color mappings (not hardcoded)  
✅ Per-device FPort configuration  
✅ Support multiple display types  
✅ No code changes needed to adjust colors  

### Operations & Debugging
✅ Complete actuation audit trail  
✅ Downlink success/failure tracking  
✅ Performance metrics  
✅ Trigger source tracking  

### Scalability
✅ Fast lookups maintained (denormalized DevEUIs)  
✅ Referential integrity (foreign keys)  
✅ Support for complex topologies (shared displays, mobile sensors)  
✅ Ready for device rotation/maintenance workflows  

---

## Backward Compatibility

### During Migration
- ✅ Keep `sensor_eui` and `display_eui` columns (renamed to `sensor_deveui`, `display_deveui`)
- ✅ Existing queries still work
- ✅ Add FKs as nullable initially
- ✅ Populate gradually

### After Migration
- ✅ DevEUI columns maintained via trigger (always in sync)
- ✅ Fast lookups still work (`WHERE sensor_deveui = 'xxx'`)
- ✅ New queries can join to device registries for metadata

---

## Recommended Approach

### Option A: Gradual Migration (Recommended)
1. ✅ Create device registry tables (Phase 1)
2. ✅ Populate from existing spaces
3. ✅ Add FK columns to spaces (nullable)
4. ✅ Update application code to use registries
5. ✅ Add actuation logging
6. ✅ Deploy and test
7. ✅ Make FKs NOT NULL (once stable)

### Option B: Keep Current Schema
- Document limitations
- Accept 1:1 mapping constraint
- Hardcode display configs
- Simple but inflexible

---

## Next Steps

**Decision Required:**
1. **Adopt V4 patterns** (separate device registries, actuation logs)
2. **Keep current schema** (document limitations, move forward)
3. **Hybrid approach** (add some V4 features, defer others)

**If proceeding with improvements:**
- [ ] Review and approve this proposal
- [ ] Create migration SQL scripts
- [ ] Update Pydantic models
- [ ] Update application code
- [ ] Test on staging environment
- [ ] Document new architecture

---

**References:**
- `V4_DATABASE_SCHEMA.md` - V4 schema documentation
- `DATABASE_SCHEMA.md` - Current V2 schema documentation
- `KUANDO_DOWNLINK_REFERENCE.md` - Display payload specifications

