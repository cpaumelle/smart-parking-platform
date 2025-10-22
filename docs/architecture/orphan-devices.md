# ORPHAN Device Architecture

**Smart Parking Platform v5**
**Feature Version:** v5.2.0
**Date:** 2025-10-17

---

## Overview

The **ORPHAN pattern** enables **event-driven auto-discovery** of LoRaWAN devices from ChirpStack without manual pre-registration. When a device sends its first uplink, the system automatically creates device and device type records marked as "ORPHAN" until an administrator reviews and confirms the configuration.

This pattern solves several key problems:
- ✅ **No manual device registration** - devices self-register on first uplink
- ✅ **Type-safe auto-discovery** - new device profiles auto-create device types
- ✅ **Admin workflow** - explicit confirmation before devices go into production
- ✅ **Zero data loss** - all uplinks stored, even from unconfirmed devices
- ✅ **Historical preservation** - device reassignments preserve temporal correctness

---

## Architecture Components

### 1. Device Type Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ ChirpStack Device Profile: "BrowanTABS_v1"                  │
└───────────────┬─────────────────────────────────────────────┘
                │ First uplink arrives
                ▼
┌─────────────────────────────────────────────────────────────┐
│ device_types (status: 'orphan')                             │
│ - type_code: 'orphan_browantabs_v1'                         │
│ - chirpstack_profile_name: 'BrowanTABS_v1'                  │
│ - sample_payload: {occupancy: true, temp: 22.5, ...}        │
│ - handler_class: NULL (awaiting admin)                      │
│ - capabilities: {} (awaiting admin)                         │
└───────────────┬─────────────────────────────────────────────┘
                │ Admin reviews and confirms
                ▼
┌─────────────────────────────────────────────────────────────┐
│ device_types (status: 'confirmed')                          │
│ - handler_class: 'BrowanTabsHandler' ✓                      │
│ - capabilities: {occupancy: true, temperature: true} ✓      │
│ - confirmed_by: 'admin@verdegris.eu'                        │
│ - confirmed_at: 2025-10-17T14:30:00Z                        │
└─────────────────────────────────────────────────────────────┘
```

### 2. Device Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ ChirpStack Device: DevEUI 58a0cb0000115b4e                   │
└───────────────┬─────────────────────────────────────────────┘
                │ First uplink arrives
                ▼
┌─────────────────────────────────────────────────────────────┐
│ sensor_devices (status: 'orphan')                           │
│ - dev_eui: '58a0cb0000115b4e'                                │
│ - device_type_id: → ORPHAN device_type                      │
│ - NOT assigned to any space                                 │
└───────────────┬─────────────────────────────────────────────┘
                │ Admin assigns to space
                ▼
┌─────────────────────────────────────────────────────────────┐
│ sensor_devices (status: 'active')                           │
│ + spaces.sensor_device_id → this device                     │
│ + sensor_readings being processed                           │
│ + actuations triggering displays                            │
└───────────────┬─────────────────────────────────────────────┘
                │ Device unassigned or removed
                ▼
┌─────────────────────────────────────────────────────────────┐
│ sensor_devices (status: 'inactive' or 'decommissioned')     │
│ - Historical data preserved                                 │
│ - Can be reassigned to different space                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### device_types Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key |
| `type_code` | varchar(50) | Unique type identifier |
| `category` | varchar(20) | 'sensor' or 'display' |
| `name` | varchar(100) | Human-readable name |
| `manufacturer` | varchar(100) | Device manufacturer |
| `handler_class` | varchar(100) | Python handler class (NULL for ORPHAN) |
| `default_config` | jsonb | Default configuration |
| `capabilities` | jsonb | Device capabilities |
| `enabled` | boolean | Type enabled/disabled |
| **`status`** | **varchar(30)** | **'orphan', 'confirmed', 'disabled'** |
| **`chirpstack_profile_name`** | **varchar(100)** | **ChirpStack device_profile name** |
| **`chirpstack_profile_id`** | **uuid** | **ChirpStack device_profile.id** |
| **`sample_payload`** | **jsonb** | **Sample normalized uplink** |
| **`sample_raw_payload`** | **jsonb** | **Sample raw uplink** |
| **`confirmed_at`** | **timestamptz** | **When admin confirmed** |
| **`confirmed_by`** | **varchar(100)** | **Who confirmed** |
| **`notes`** | **text** | **Admin notes** |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Update timestamp |

**New Constraints:**
```sql
CHECK (status IN ('orphan', 'confirmed', 'disabled'))
UNIQUE (chirpstack_profile_name) WHERE chirpstack_profile_name IS NOT NULL
```

### sensor_devices & display_devices Tables

**New Column Added:**
```sql
status VARCHAR(30) DEFAULT 'orphan'
CHECK (status IN ('orphan', 'active', 'inactive', 'decommissioned'))
```

**Device Status Meanings:**
- **`orphan`**: Auto-discovered, not assigned to any space
- **`active`**: Assigned to space, actively used
- **`inactive`**: Unassigned from space, can be reassigned
- **`decommissioned`**: Permanently retired, historical data preserved

---

## Auto-Discovery Flow

### Step-by-Step Process

**1. Uplink Arrives at /api/v1/uplink**
```json
{
  "deviceInfo": {
    "devEui": "58a0cb0000115b4e",
    "deviceName": "BrowanSensor01",
    "deviceProfileName": "BrowanTABS_v1"
  },
  "object": {
    "occupancy": true,
    "temperature": 22.5,
    "battery": 95,
    "rssi": -87,
    "snr": 9.5
  }
}
```

**2. Check Device Type Exists**
```python
# Query device_types by ChirpStack profile name
device_type = await db.fetchrow("""
    SELECT id, type_code, status, handler_class, capabilities
    FROM device_types
    WHERE chirpstack_profile_name = $1
""", "BrowanTABS_v1")
```

**3a. If Device Type NOT Found → Create ORPHAN Type**
```python
# Auto-generate type_code from profile name
type_code = f"orphan_{profile_name.lower().replace(' ', '_')}"

# Auto-detect capabilities from payload keys
capabilities = auto_detect_capabilities(payload_object)
# → {"occupancy": true, "temperature": true, "battery": true}

# Create ORPHAN device type
device_type_id = await db.fetchval("""
    INSERT INTO device_types (
        type_code,
        category,
        name,
        status,
        chirpstack_profile_name,
        sample_payload,
        capabilities
    ) VALUES ($1, $2, $3, 'orphan', $4, $5, $6)
    RETURNING id
""", type_code, 'sensor', f"ORPHAN: {profile_name}",
    profile_name, payload_object, capabilities)
```

**3b. If Device Type Found → Use Existing**
```python
device_type_id = device_type['id']
```

**4. Check Device Exists**
```python
device = await db.fetchrow("""
    SELECT id, status, device_type_id
    FROM sensor_devices
    WHERE dev_eui = $1
""", dev_eui)
```

**5a. If Device NOT Found → Create ORPHAN Device**
```python
device_id = await db.fetchval("""
    INSERT INTO sensor_devices (
        dev_eui,
        device_type_id,
        device_model,
        status,
        last_seen
    ) VALUES ($1, $2, $3, 'orphan', NOW())
    RETURNING id
""", dev_eui, device_type_id, device_name)
```

**5b. If Device Found → Update Last Seen**
```python
await db.execute("""
    UPDATE sensor_devices
    SET last_seen = NOW()
    WHERE id = $1
""", device_id)
```

**6. Store Sensor Reading (Always, Even for ORPHAN)**
```python
# Always store data, even if device is ORPHAN
await db.execute("""
    INSERT INTO sensor_readings (
        device_id,
        occupancy,
        temperature,
        battery_level,
        rssi,
        snr,
        raw_payload
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
""", device_id, occupancy, temperature, battery, rssi, snr, raw_payload)
```

**7. Process or Skip Actuation**
```python
if device['status'] == 'active':
    # Device assigned to space → trigger display update
    await process_actuation(device_id, occupancy)
else:
    # Device is ORPHAN → log only, no actuation
    logger.info(f"ORPHAN device {dev_eui} - data stored, no actuation")
```

---

## Admin Workflows

### Workflow 1: Confirm ORPHAN Device Type

**Query ORPHAN types:**
```sql
SELECT
    dt.id,
    dt.type_code,
    dt.name,
    dt.chirpstack_profile_name,
    dt.sample_payload,
    dt.created_at,
    COUNT(sd.id) as sensor_count
FROM device_types dt
LEFT JOIN sensor_devices sd ON sd.device_type_id = dt.id
WHERE dt.status = 'orphan'
GROUP BY dt.id
ORDER BY dt.created_at DESC;
```

**Example result:**
```
type_code                | name                      | sample_payload                                | sensor_count
-------------------------|---------------------------|-----------------------------------------------|-------------
orphan_browantabs_v1     | ORPHAN: BrowanTABS_v1     | {"occupancy": true, "temperature": 22.5, ...} | 3
orphan_dragino_lds02_v2  | ORPHAN: DraginoLDS02_v2   | {"door_open": false, "battery": 87, ...}      | 1
```

**Admin reviews payload and confirms:**
```sql
UPDATE device_types
SET
    status = 'confirmed',
    handler_class = 'BrowanTabsHandler',
    capabilities = '{"occupancy": true, "temperature": true, "battery": true, "rssi": true, "snr": true}'::jsonb,
    confirmed_by = 'admin@verdegris.eu',
    confirmed_at = NOW(),
    notes = 'Browan TBMS100 TABS sensor - confirmed for parking occupancy detection'
WHERE id = 'device-type-uuid';
```

### Workflow 2: Assign ORPHAN Device to Space

**Query ORPHAN devices:**
```sql
SELECT
    sd.id,
    sd.dev_eui,
    sd.device_model,
    dt.name as type_name,
    dt.status as type_status,
    sd.last_seen,
    (SELECT COUNT(*) FROM sensor_readings WHERE device_id = sd.id) as reading_count
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE sd.status = 'orphan'
ORDER BY sd.last_seen DESC;
```

**Example result:**
```
dev_eui              | device_model      | type_name                  | type_status | last_seen           | reading_count
---------------------|-------------------|----------------------------|-------------|---------------------|---------------
58a0cb0000115b4e     | BrowanSensor01    | ORPHAN: BrowanTABS_v1      | orphan      | 2025-10-17 14:30:00 | 42
58a0cb00001196f3     | BrowanSensor02    | Browan TBMS100 TABS        | confirmed   | 2025-10-17 14:25:00 | 15
```

**Admin assigns device to space:**
```sql
-- Update space to use this sensor
UPDATE spaces
SET sensor_device_id = 'sensor-device-uuid'
WHERE id = 'space-uuid';

-- Mark sensor as active
UPDATE sensor_devices
SET status = 'active'
WHERE id = 'sensor-device-uuid';
```

### Workflow 3: Reassign Device (Move Between Spaces)

**Move sensor from Space A to Space B:**
```sql
-- Unassign from Space A
UPDATE spaces
SET sensor_device_id = NULL
WHERE id = 'space-a-uuid';

-- Assign to Space B
UPDATE spaces
SET sensor_device_id = 'sensor-device-uuid'
WHERE id = 'space-b-uuid';

-- Device remains 'active'
-- Historical sensor_readings unchanged (temporally correct)
```

**Important:** Historical data is NOT modified. sensor_readings table preserves all data with original timestamps, maintaining temporal correctness.

### Workflow 4: Decommission Device

**Permanently retire device:**
```sql
-- Unassign from space
UPDATE spaces
SET sensor_device_id = NULL
WHERE sensor_device_id = 'sensor-device-uuid';

-- Mark as decommissioned (soft delete)
UPDATE sensor_devices
SET status = 'decommissioned'
WHERE id = 'sensor-device-uuid';

-- All historical data preserved
-- Device can no longer be assigned to spaces
```

---

## Admin API Endpoints

All admin endpoints require authentication via `X-API-Key` header with admin privileges.

### Device Management

**GET /api/v1/admin/devices/unassigned**
List all unassigned devices (ORPHAN status, not assigned to any space)

**Response:**
```json
{
  "sensors": [
    {
      "id": "6030aae6-3780-45a7-a724-0c418ad01363",
      "dev_eui": "58a0cb000011590d",
      "device_model": "58a0cb000011590d",
      "status": "orphan",
      "type_code": "browan_tbms100_motion",
      "device_type_name": "Browan TBMS100 TABS",
      "type_status": "confirmed",
      "last_seen_at": "2025-10-17T07:55:39.802100+00:00",
      "created_at": "2025-10-17T07:50:24.460742+00:00"
    }
  ],
  "displays": [
    {
      "id": "eb853e4b-56b6-4020-8f93-7f0a5376c601",
      "dev_eui": "2020203907290902",
      "device_model": "Brighter Kuando 290902",
      "status": "orphan",
      "type_code": "kuando_busylight",
      "device_type_name": "Kuando Busylight IoT Omega",
      "type_status": "confirmed",
      "last_seen_at": "2025-10-17T07:55:01.708533+00:00",
      "created_at": "2025-10-17T07:55:01.708533+00:00"
    }
  ],
  "total": 2
}
```

**POST /api/v1/admin/devices/sensor/{device_id}/assign**
Assign a sensor device to a space

**Query Parameters:**
- `space_id` (required): UUID of the space to assign the sensor to

**Response:**
```json
{
  "status": "assigned",
  "sensor_id": "6030aae6-3780-45a7-a724-0c418ad01363",
  "sensor_eui": "58a0cb000011590d",
  "space_id": "0cd57dcc-7851-43ce-9b93-5cd5a223998c",
  "space_code": "ACME-P001"
}
```

**Validation:**
- Sensor must exist
- Space must exist
- Space must not already have a sensor assigned
- Updates sensor status from 'orphan' to 'active'
- Sets space.sensor_device_id to the sensor ID

**POST /api/v1/admin/devices/display/{device_id}/assign**
Assign a display device to a space

**Query Parameters:**
- `space_id` (required): UUID of the space to assign the display to

**Response:**
```json
{
  "status": "assigned",
  "display_id": "eb853e4b-56b6-4020-8f93-7f0a5376c601",
  "display_eui": "2020203907290902",
  "space_id": "0cd57dcc-7851-43ce-9b93-5cd5a223998c",
  "space_code": "ACME-P001"
}
```

**Validation:**
- Display must exist
- Space must exist
- Space must not already have a display assigned
- Updates display status from 'orphan' to 'active'
- Sets space.display_device_id to the display ID

**POST /api/v1/admin/devices/sensor/{device_id}/unassign**
Unassign a sensor device from its space

**Response:**
```json
{
  "status": "unassigned",
  "sensor_id": "c17debd9-7686-4278-91fe-5b2d33071c8c",
  "sensor_eui": "acmesensor0001",
  "previous_space": "ACME-P001"
}
```

**Actions:**
- Updates sensor status from 'active' to 'inactive'
- Sets space.sensor_device_id to NULL
- Preserves all historical sensor_readings data

**POST /api/v1/admin/devices/display/{device_id}/unassign**
Unassign a display device from its space

**Response:**
```json
{
  "status": "unassigned",
  "display_id": "664e74e0-13c0-4520-a074-fdc17b3ac045",
  "display_eui": "acmedisplay001",
  "previous_space": "ACME-P001"
}
```

**Actions:**
- Updates display status from 'active' to 'inactive'
- Sets space.display_device_id to NULL
- Device can be reassigned to a different space

### Example API Usage

**List Unassigned Devices:**
```bash
curl -H "X-API-Key: YOUR_ADMIN_KEY" \
  https://api.verdegris.eu/api/v1/admin/devices/unassigned
```

**Assign Sensor to Space:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  "https://api.verdegris.eu/api/v1/admin/devices/sensor/{sensor_id}/assign?space_id={space_id}"
```

**Unassign Sensor from Space:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  https://api.verdegris.eu/api/v1/admin/devices/sensor/{sensor_id}/unassign
```

**Assign Display to Space:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  "https://api.verdegris.eu/api/v1/admin/devices/display/{display_id}/assign?space_id={space_id}"
```

**Unassign Display from Space:**
```bash
curl -X POST \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  https://api.verdegris.eu/api/v1/admin/devices/display/{display_id}/unassign
```

---

## Key Design Decisions

### 1. ORPHAN Uplinks Store Data, No Actuation
**Decision:** Store all sensor_readings, but skip actuation logic for ORPHAN devices.

**Rationale:**
- ✅ Zero data loss - all uplinks preserved for analysis
- ✅ Admin can review historical data before confirming
- ✅ Prevents unwanted display updates from unconfirmed devices
- ✅ Clear separation: data collection vs. operational use

### 2. No Auto-Assignment Based on Naming Convention
**Decision:** Do NOT auto-assign devices to spaces based on device name patterns.

**Rationale:**
- ❌ Naming conventions are fragile (typos, changes)
- ❌ Implicit assignments are error-prone
- ✅ Explicit admin confirmation is safer
- ✅ Prevents accidental production use

### 3. Device Reassignment Preserves History
**Decision:** Allow moving sensors between spaces; preserve all historical sensor_readings.

**Rationale:**
- ✅ Temporally correct - readings remain with original timestamps
- ✅ Audit trail - can see which device was in which space when
- ✅ Flexible operations - swap faulty sensors without data loss

### 4. Soft Delete (Decommission) Not Hard Delete
**Decision:** Mark devices as 'decommissioned', never DELETE rows.

**Rationale:**
- ✅ Preserve historical data
- ✅ Maintain referential integrity
- ✅ Enable audit trails
- ✅ Support compliance requirements

### 5. Device Types Also Use ORPHAN Pattern
**Decision:** Auto-create ORPHAN device_types when unknown ChirpStack profiles appear.

**Rationale:**
- ✅ Zero manual configuration for new device models
- ✅ Admin reviews sample payload to understand data structure
- ✅ Type-safe - handler_class only filled after confirmation
- ✅ Prevents crashes from unknown device types

---

## Sample Queries

### Find All ORPHAN Items

```sql
-- All ORPHAN device types
SELECT
    dt.id,
    dt.type_code,
    dt.name,
    dt.chirpstack_profile_name,
    dt.sample_payload,
    dt.created_at,
    COALESCE(
        (SELECT COUNT(*) FROM sensor_devices WHERE device_type_id = dt.id),
        (SELECT COUNT(*) FROM display_devices WHERE device_type_id = dt.id)
    ) as device_count
FROM device_types dt
WHERE dt.status = 'orphan'
ORDER BY dt.created_at DESC;

-- All ORPHAN devices (both sensors and displays)
SELECT * FROM orphan_devices;  -- Uses view created in migration
```

### Device Status Distribution

```sql
SELECT
    'sensors' as category,
    status,
    COUNT(*) as count
FROM sensor_devices
GROUP BY status

UNION ALL

SELECT
    'displays' as category,
    status,
    COUNT(*) as count
FROM display_devices
GROUP BY status

ORDER BY category, status;
```

**Example output:**
```
category  | status          | count
----------|-----------------|-------
displays  | active          | 3
displays  | orphan          | 1
sensors   | active          | 3
sensors   | orphan          | 1
```

### Devices With Confirmed Types But Still ORPHAN

```sql
-- These devices have confirmed types but haven't been assigned yet
SELECT
    sd.dev_eui,
    sd.device_model,
    dt.name as type_name,
    dt.status as type_status,
    sd.status as device_status,
    sd.last_seen,
    (SELECT COUNT(*) FROM sensor_readings WHERE device_id = sd.id) as readings
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE sd.status = 'orphan' AND dt.status = 'confirmed'
ORDER BY sd.last_seen DESC;
```

### Space Assignment History

```sql
-- Track when devices were assigned/unassigned from spaces
-- (Requires audit table or state_changes tracking)
SELECT
    s.name as space_name,
    sd.dev_eui,
    sc.state as occupancy_state,
    sc.timestamp
FROM state_changes sc
JOIN spaces s ON sc.space_id = s.id
LEFT JOIN sensor_devices sd ON s.sensor_device_id = sd.id
WHERE s.id = 'space-uuid'
ORDER BY sc.timestamp DESC
LIMIT 20;
```

---

## Migration Path

### Step 1: Run Migration SQL
```bash
docker compose exec -T postgres psql -U parking_user -d parking_v5 < orphan_device_types_migration.sql
```

### Step 2: Map Existing Types to ChirpStack Profiles
Update `chirpstack_profile_name` for all existing confirmed device_types.

### Step 3: Update Uplink Handler
Modify `/src/routes/uplink.py` to implement auto-discovery logic.

### Step 4: Create Admin API Endpoints
Add endpoints for:
- List ORPHAN types/devices
- Confirm device types
- Assign devices to spaces

### Step 5: Test Auto-Discovery
1. Register new device in ChirpStack with new profile
2. Trigger uplink
3. Verify ORPHAN device_type created
4. Verify ORPHAN sensor_device created
5. Verify sensor_reading stored
6. Verify no actuation occurred

---

## Benefits Summary

| Benefit | Description |
|---------|-------------|
| **Zero-Touch Provisioning** | Devices auto-register on first uplink |
| **Type Safety** | Unknown device types create ORPHAN entries for review |
| **Data Preservation** | All uplinks stored, even from unconfirmed devices |
| **Admin Control** | Explicit confirmation before operational use |
| **Operational Flexibility** | Move devices between spaces without data loss |
| **Historical Accuracy** | Temporal correctness preserved in reassignments |
| **Soft Delete** | Decommission preserves history for compliance |
| **Audit Trail** | Full lifecycle tracking from discovery to retirement |

---

## Related Documentation

- `/docs/DATABASE_SCHEMA.md` - Complete schema reference
- `/docs/DEVICE_TYPES_ARCHITECTURE.md` - Device types design
- `/docs/V2_SCHEMA_IMPROVEMENT_PROPOSAL.md` - Architecture rationale

---

**For implementation:**
- `/src/routes/uplink.py` - Uplink handler (auto-discovery logic)
- `/src/routes/admin.py` - Admin endpoints (ORPHAN management)
- `/src/database.py` - Database queries
