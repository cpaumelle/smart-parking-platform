# Device Types Architecture

**Smart Parking Platform v5**
**Feature Version:** v5.1.0
**Date:** 2025-10-17

---

## Overview

The **device_types** table provides a centralized registry of all supported device types in the Smart Parking Platform. It separates device type metadata (handlers, capabilities, default configuration) from individual device instances, enabling:

- **Type-level configuration management**
- **Centralized handler/decoder registration**
- **Easy extensibility** (add new device types via database)
- **Referential integrity** for device types
- **Default settings inheritance** for new devices

---

## Architecture Pattern

```
┌──────────────────┐
│  device_types    │ (Type catalog)
│  - handler_class │
│  - capabilities  │
│  - default_config│
└────────┬─────────┘
         │ 1
         │
         ├──────────────────┬──────────────────┐
         │ *                │ *                │
         ▼                  ▼                  │
┌────────────────┐  ┌─────────────────┐       │
│sensor_devices  │  │display_devices  │       │
│- device_type_id│  │- device_type_id │       │
│- dev_eui       │  │- dev_eui        │       │
│- specific cfg  │  │- specific cfg   │       │
└────────────────┘  └─────────────────┘       │
                                               │
Benefits:                                      │
✅ Single source of truth for device types    │
✅ Handler classes registered at type level    │
✅ Default configs inherited by devices        │
✅ New types added without code changes        │
```

---

## Table Definition

### device_types

**Purpose:** Central registry of all supported device types with handler, capability, and configuration metadata.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `type_code` | varchar(50) | NOT NULL | - | Unique type identifier (browan_tabs, kuando_busylight) |
| `category` | varchar(20) | NOT NULL | - | Device category ('sensor' or 'display') |
| `name` | varchar(100) | NOT NULL | - | Human-readable type name |
| `manufacturer` | varchar(100) | NULL | - | Device manufacturer |
| `handler_class` | varchar(100) | NULL | - | Python handler/decoder class name |
| `default_config` | jsonb | NULL | '{}' | Default configuration for this type |
| `capabilities` | jsonb | NULL | '{}' | Device capabilities (sensors: occupancy, temp; displays: colors) |
| `enabled` | boolean | NULL | true | Type enabled/disabled |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (type_code) - Each type has unique identifier
- `CHECK valid_category` - category ∈ {sensor, display}

**Indexes:**
- `idx_device_types_category` (category, enabled) WHERE enabled = TRUE
- `idx_device_types_code` (type_code, enabled) WHERE enabled = TRUE

**Triggers:**
- `update_device_types_updated_at` - Automatically updates `updated_at` on row modification

---

## Current Device Types

### Sensor Types

**1. browan_tabs** (Browan TBMS100 TABS)
```json
{
  "type_code": "browan_tabs",
  "category": "sensor",
  "name": "Browan TBMS100 TABS",
  "manufacturer": "Browan Communications",
  "handler_class": "BrowanTabsHandler",
  "capabilities": {
    "occupancy": true,
    "temperature": true,
    "battery": true,
    "rssi": true,
    "snr": true
  }
}
```

**2. dragino_lds02** (Dragino LDS02 Door Sensor)
```json
{
  "type_code": "dragino_lds02",
  "category": "sensor",
  "name": "Dragino LDS02 Door Sensor",
  "manufacturer": "Dragino",
  "handler_class": "DraginoHandler",
  "capabilities": {
    "occupancy": true,
    "door_state": true,
    "battery": true
  }
}
```

**3. generic_occupancy** (Generic Occupancy Sensor)
```json
{
  "type_code": "generic_occupancy",
  "category": "sensor",
  "name": "Generic Occupancy Sensor",
  "handler_class": "GenericOccupancyHandler",
  "capabilities": {
    "occupancy": true
  }
}
```

### Display Types

**1. kuando_busylight** (Kuando Busylight IoT Omega)
```json
{
  "type_code": "kuando_busylight",
  "category": "display",
  "name": "Kuando Busylight IoT Omega",
  "manufacturer": "Kuando",
  "handler_class": "KuandoHandler",
  "default_config": {
    "fport": 15,
    "confirmed_downlinks": false,
    "display_codes": {
      "FREE": "0000FF6400",
      "OCCUPIED": "FF00006400",
      "RESERVED": "FF00FF6400",
      "MAINTENANCE": "FFA5006400"
    }
  }
}
```

**2. led_matrix** (LED Matrix Display)
```json
{
  "type_code": "led_matrix",
  "category": "display",
  "name": "LED Matrix Display",
  "handler_class": "LEDMatrixHandler",
  "default_config": {
    "fport": 1,
    "confirmed_downlinks": false
  }
}
```

---

## Integration with Device Tables

### sensor_devices Integration

The `sensor_devices` table now includes `device_type_id` foreign key:

```sql
ALTER TABLE sensor_devices
  ADD COLUMN device_type_id UUID REFERENCES device_types(id);
```

**Benefits:**
- Device inherits handler class from type
- Type-level capabilities provide template
- Easy to query all devices of a specific type
- Referential integrity ensures valid types

**Example Query:**
```sql
-- Get all Browan TABS sensors with their type info
SELECT
  sd.dev_eui,
  sd.device_model,
  dt.name as type_name,
  dt.handler_class,
  dt.capabilities
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE dt.type_code = 'browan_tabs';
```

### display_devices Integration

The `display_devices` table now includes `device_type_id` foreign key:

```sql
ALTER TABLE display_devices
  ADD COLUMN device_type_id UUID REFERENCES device_types(id);
```

**Benefits:**
- Type-level default display codes
- Type-level default FPort configuration
- New devices inherit type defaults
- Easy type-based queries

**Example Query:**
```sql
-- Get all Kuando displays with their type defaults
SELECT
  dd.dev_eui,
  dd.display_codes as device_codes,
  dt.name as type_name,
  dt.default_config->>'fport' as default_fport,
  dt.default_config->'display_codes' as default_colors
FROM display_devices dd
JOIN device_types dt ON dd.device_type_id = dt.id
WHERE dt.type_code = 'kuando_busylight';
```

---

## Common Operations

### Adding a New Device Type

```sql
-- Add a new sensor type
INSERT INTO device_types (
  type_code,
  category,
  name,
  manufacturer,
  handler_class,
  capabilities
) VALUES (
  'elsys_ers',
  'sensor',
  'Elsys ERS Environmental Sensor',
  'Elsys',
  'ElsysHandler',
  '{"occupancy": true, "temperature": true, "humidity": true, "co2": true}'::jsonb
);
```

### Querying Device Type Usage

```sql
-- Show device type usage statistics
SELECT
  dt.category,
  dt.type_code,
  dt.name,
  CASE
    WHEN dt.category = 'sensor' THEN
      (SELECT COUNT(*) FROM sensor_devices WHERE device_type_id = dt.id)
    WHEN dt.category = 'display' THEN
      (SELECT COUNT(*) FROM display_devices WHERE device_type_id = dt.id)
  END as devices_using_type,
  dt.enabled
FROM device_types dt
ORDER BY dt.category, devices_using_type DESC;
```

### Finding Devices by Capability

```sql
-- Find all sensors with temperature capability
SELECT
  sd.dev_eui,
  sd.device_model,
  dt.name as type_name,
  dt.capabilities
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE dt.capabilities->>'temperature' = 'true'
  AND sd.enabled = TRUE
  AND dt.enabled = TRUE;
```

### Getting Handler Class for Device

```sql
-- Get handler class for a specific device
SELECT
  sd.dev_eui,
  dt.handler_class,
  dt.capabilities
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE sd.dev_eui = '58a0cb0000115b4e';
```

---

## Benefits of Device Types Table

### 1. Centralized Type Management
- **Single source of truth** for all device types
- **Handler registration** at type level (not per-device)
- **Easy to add new types** without code deployment

### 2. Configuration Inheritance
- **Default configurations** defined at type level
- New devices **inherit type defaults** automatically
- Override defaults at device level when needed

### 3. Capability Discovery
- **Query devices by capability** (all temperature sensors, all CO2 sensors)
- **Validate device capabilities** before processing
- **API can expose** supported device types

### 4. Referential Integrity
- **Can only use registered types** (FK constraint)
- **Prevents typos** in device type codes
- **Type-safe device categorization**

### 5. Handler Management
- **Handler class names** stored centrally
- **Application loads handlers** based on device type
- **No hardcoded handler mappings** in code

### 6. Extensibility
- **Add new device types** via database (no code changes)
- **Disable obsolete types** via enabled flag
- **Version device type configs** over time

---

## Migration from device_type String to device_type_id FK

### Before (String-based)
```sql
CREATE TABLE sensor_devices (
  device_type VARCHAR(50) NOT NULL  -- String value, no validation
);
```

**Problems:**
- No validation of type values
- Typos possible (browan_tab vs browan_tabs)
- Handler mapping scattered in code
- No centralized type metadata

### After (FK-based)
```sql
CREATE TABLE device_types (
  id UUID PRIMARY KEY,
  type_code VARCHAR(50) UNIQUE,
  handler_class VARCHAR(100),
  capabilities JSONB
);

CREATE TABLE sensor_devices (
  device_type VARCHAR(50),  -- Kept for backward compatibility
  device_type_id UUID REFERENCES device_types(id)  -- New FK
);
```

**Benefits:**
- ✅ Type validation via FK constraint
- ✅ Centralized type metadata
- ✅ Handler class lookup via join
- ✅ Backward compatible (old string column kept)

---

## Future Enhancements

### 1. Handler Version Tracking
```sql
ALTER TABLE device_types
  ADD COLUMN handler_version VARCHAR(20);
```

### 2. Type-Specific Validation Rules
```sql
ALTER TABLE device_types
  ADD COLUMN validation_rules JSONB;
```

### 3. Firmware Compatibility Matrix
```sql
CREATE TABLE device_type_firmware (
  device_type_id UUID REFERENCES device_types(id),
  firmware_version VARCHAR(50),
  compatible BOOLEAN,
  notes TEXT
);
```

### 4. Type-Specific Downlink Templates
```sql
ALTER TABLE device_types
  ADD COLUMN downlink_templates JSONB;
```

---

## Sample Queries

### Get All Device Types with Usage Count
```sql
SELECT
  dt.category,
  dt.type_code,
  dt.name,
  dt.manufacturer,
  dt.handler_class,
  CASE
    WHEN dt.category = 'sensor' THEN
      (SELECT COUNT(*) FROM sensor_devices WHERE device_type_id = dt.id)
    WHEN dt.category = 'display' THEN
      (SELECT COUNT(*) FROM display_devices WHERE device_type_id = dt.id)
  END as device_count,
  dt.enabled
FROM device_types dt
ORDER BY dt.category, device_count DESC;
```

### Find Spaces with Specific Sensor Type
```sql
SELECT
  s.name as space_name,
  s.code as space_code,
  dt.name as sensor_type,
  dt.manufacturer,
  sd.dev_eui as sensor_eui
FROM spaces s
JOIN sensor_devices sd ON s.sensor_device_id = sd.id
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE dt.type_code = 'browan_tabs'
  AND s.deleted_at IS NULL;
```

### Get Device Type Capabilities for API
```sql
SELECT
  type_code,
  category,
  name,
  manufacturer,
  capabilities,
  enabled
FROM device_types
WHERE enabled = TRUE
ORDER BY category, name;
```

### Validate Device Against Type Capabilities
```sql
-- Check if a device's reported data matches type capabilities
SELECT
  sd.dev_eui,
  dt.type_code,
  dt.capabilities as expected_capabilities,
  -- Would compare against actual sensor_readings columns
  dt.capabilities->>'occupancy' as supports_occupancy,
  dt.capabilities->>'temperature' as supports_temperature
FROM sensor_devices sd
JOIN device_types dt ON sd.device_type_id = dt.id
WHERE sd.dev_eui = '58a0cb0000115b4e';
```

---

## Related Documentation

- `/docs/DATABASE_SCHEMA.md` - Complete database schema documentation
- `/docs/V2_SCHEMA_IMPROVEMENT_PROPOSAL.md` - Architecture design rationale
- `/docs/KUANDO_DOWNLINK_REFERENCE.md` - Display-specific protocols

---

**For implementation details, see:**
- `/src/device_handlers/` - Handler class implementations
- `/src/models.py` - Pydantic models for device types
- `/src/database.py` - Database queries using device types
