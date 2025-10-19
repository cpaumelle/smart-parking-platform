# V4 Smart Parking Platform - Database Schema Documentation

**Document Version:** 1.0.0
**Date:** 2025-10-16
**Database:** PostgreSQL 16
**Subject:** Complete v4 database schema reference for smart parking platform

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Databases](#databases)
3. [Schema Structure](#schema-structure)
4. [Ingest Schema](#ingest-schema)
5. [Transform Schema](#transform-schema)
6. [Parking Config Schema](#parking-config-schema)
7. [Parking Spaces Schema](#parking-spaces-schema)
8. [Parking Operations Schema](#parking-operations-schema)
9. [Relationships & ERD](#relationships--erd)
10. [Indexes](#indexes)
11. [Sample Queries](#sample-queries)
12. [Kuando Integration](#kuando-integration)

---

## Architecture Overview

### Multi-Database Architecture

The v4 platform uses a **dual-database architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Server                         │
│                                                              │
│  ┌──────────────────────┐  ┌─────────────────────────────┐ │
│  │  chirpstack          │  │  parking_platform           │ │
│  │  (LoRaWAN NS)        │  │  (Application Layer)        │ │
│  │                      │  │                             │ │
│  │  - Devices           │  │  Schemas:                   │ │
│  │  - Applications      │  │  ├─ ingest                  │ │
│  │  - Device profiles   │  │  ├─ transform               │ │
│  │  - Device queue      │  │  ├─ parking_config          │ │
│  │  - Gateways          │  │  ├─ parking_spaces          │ │
│  │                      │  │  └─ parking_operations      │ │
│  └──────────────────────┘  └─────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
LoRaWAN Device
    ↓ uplink
Gateway
    ↓ UDP/MQTT
ChirpStack (chirpstack DB)
    ↓ HTTP Webhook
Ingest Service → ingest.raw_uplinks
    ↓
Transform Service → transform.processed_uplinks
    ↓
Parking Display Service → parking_spaces.spaces
    ↓ downlink via ChirpStack gRPC
Display Device
```

---

## Databases

### 1. `chirpstack`

**Purpose:** ChirpStack Network Server data
**Owner:** ChirpStack v4
**Access:** Read-only from application services (via gRPC API)

**Key Tables (managed by ChirpStack):**
- `device` - LoRaWAN devices
- `device_queue_item` - Downlink queue
- `application` - ChirpStack applications
- `device_profile` - Device configurations
- `gateway` - LoRaWAN gateways

**Extensions:**
- `pg_trgm` - Trigram indexing for text search

### 2. `parking_platform`

**Purpose:** Application layer data and business logic
**Owner:** Smart Parking Platform
**User:** `parking_user` (unified user with full access)

**Schemas:**
- `ingest` - Raw uplink storage
- `transform` - Data processing and enrichment
- `parking_config` - Device registries
- `parking_spaces` - Parking space management
- `parking_operations` - Operational logs

**Extensions:**
- `uuid-ossp` - UUID generation
- `pgcrypto` - Cryptographic functions

---

## Schema Structure

### Schema Responsibilities

| Schema | Purpose | Services |
|--------|---------|----------|
| `ingest` | Raw uplink ingestion from ChirpStack webhook | Ingest Service |
| `transform` | Payload decoding, enrichment, device context | Transform Service |
| `parking_config` | Device registry (sensors & displays) | Parking Display Service |
| `parking_spaces` | Parking space definitions and reservations | Parking Display Service |
| `parking_operations` | Actuation logs and operational telemetry | Parking Display Service |

---

## Ingest Schema

### Purpose
Store raw LoRaWAN uplinks from ChirpStack webhook for processing pipeline.

### Tables

#### `ingest.raw_uplinks`

**Purpose:** Raw uplink storage from ChirpStack HTTP integration

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `uplink_id` | SERIAL | PRIMARY KEY | Auto-incrementing uplink ID |
| `deveui` | TEXT | NOT NULL | Device EUI (hex string) |
| `received_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Webhook receipt timestamp |
| `fport` | INTEGER | | LoRaWAN FPort |
| `payload` | TEXT | | Base64 or hex payload |
| `uplink_metadata` | JSONB | | Full ChirpStack uplink JSON |
| `source` | TEXT | NOT NULL, DEFAULT 'chirpstack' | Uplink source identifier |
| `processed` | BOOLEAN | DEFAULT FALSE | Processing flag |
| `gateway_eui` | VARCHAR(64) | | Gateway that received uplink |

**Indexes:**
```sql
CREATE INDEX idx_raw_uplinks_deveui ON ingest.raw_uplinks (deveui);
CREATE INDEX idx_raw_uplinks_received_at ON ingest.raw_uplinks (received_at);
CREATE INDEX idx_raw_uplinks_processed ON ingest.raw_uplinks (processed);
```

**Sample Data:**
```json
{
  "uplink_id": 12345,
  "deveui": "70b3d57ed0067001",
  "received_at": "2025-10-16T12:34:56Z",
  "fport": 1,
  "payload": "0100",
  "uplink_metadata": {
    "deviceInfo": {"devEui": "70b3d57ed0067001"},
    "rxInfo": [{"rssi": -85, "snr": 8.5}]
  },
  "source": "chirpstack",
  "processed": false,
  "gateway_eui": "7076ff0064030456"
}
```

---

## Transform Schema

### Purpose
Decode payloads, enrich with device context, and prepare data for analytics.

### Tables

#### `transform.device_types`

**Purpose:** Device type definitions and payload decoder mappings

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `device_type_id` | SERIAL | PRIMARY KEY | Auto-incrementing type ID |
| `device_type` | VARCHAR(255) | NOT NULL | Device type name |
| `description` | TEXT | | Human-readable description |
| `unpacker` | VARCHAR(255) | | Python unpacker function name |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `archived_at` | TIMESTAMPTZ | | Soft delete timestamp |

**Examples:**
```sql
INSERT INTO transform.device_types (device_type, unpacker) VALUES
  ('tabs_occupancy', 'tabs_occupancy_v2'),
  ('kuando_busylight', 'kuando_busylight'),
  ('netvox_door', 'netvox_r718n3');
```

---

#### `transform.locations`

**Purpose:** Hierarchical location structure (site → floor → room → zone)

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `location_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique location ID |
| `name` | TEXT | NOT NULL | Location name |
| `type` | TEXT | CHECK IN ('site', 'floor', 'room', 'zone') | Location type |
| `parent_id` | UUID | REFERENCES locations(location_id) | Parent location (hierarchy) |
| `uplink_metadata` | JSONB | | Additional metadata |
| `created_at` | TIMESTAMPTZ | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | | Last update timestamp |
| `archived_at` | TIMESTAMPTZ | | Soft delete timestamp |

**Hierarchy Example:**
```
Site: "Woki Building"
  └─ Floor: "1st Floor"
      └─ Zone: "Zone A"
          └─ Room: "Conference Room A1"
```

---

#### `transform.device_context`

**Purpose:** Device metadata, location assignments, lifecycle tracking

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `deveui` | VARCHAR(16) | PRIMARY KEY | Device EUI (hex, lowercase) |
| `name` | VARCHAR(255) | | Human-readable device name |
| `device_type_id` | INTEGER | FK → device_types | Device type reference |
| `location_id` | UUID | FK → locations | Current location |
| `site_id` | UUID | FK → locations | Site reference (denormalized) |
| `floor_id` | UUID | FK → locations | Floor reference (denormalized) |
| `room_id` | UUID | FK → locations | Room reference (denormalized) |
| `zone_id` | UUID | FK → locations | Zone reference (denormalized) |
| `lifecycle_state` | VARCHAR(50) | | Device state (active, testing, decommissioned) |
| `last_gateway` | VARCHAR(255) | | Last gateway EUI |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Registration timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |
| `assigned_at` | TIMESTAMP | | Location assignment timestamp |
| `unassigned_at` | TIMESTAMP | | Location removal timestamp |
| `archived_at` | TIMESTAMPTZ | | Soft delete timestamp |

**Named Foreign Keys:**
- `fk_device_context_site` → `locations(location_id)`
- `fk_device_context_floor` → `locations(location_id)`
- `fk_device_context_room` → `locations(location_id)`
- `fk_device_context_zone` → `locations(location_id)`

---

#### `transform.gateways`

**Purpose:** LoRaWAN gateway registry and status tracking

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `gw_eui` | TEXT | PRIMARY KEY | Gateway EUI (hex) |
| `gateway_name` | VARCHAR(255) | | Gateway name |
| `site_id` | UUID | FK → locations | Site location |
| `location_id` | UUID | FK → locations | Specific location |
| `status` | VARCHAR(10) | DEFAULT 'offline' | Gateway status |
| `last_seen_at` | TIMESTAMP | | Last activity timestamp |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Registration timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |
| `archived_at` | TIMESTAMPTZ | | Soft delete timestamp |

---

#### `transform.ingest_uplinks`

**Purpose:** Copy of raw uplinks for transform processing

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `uplink_uuid` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique uplink ID |
| `ingest_uplink_id` | SERIAL | | Original ingest ID |
| `deveui` | VARCHAR(16) | | Device EUI |
| `timestamp` | TIMESTAMP | | Uplink timestamp |
| `fport` | INTEGER | | LoRaWAN FPort |
| `payload` | TEXT | | Raw payload |
| `uplink_metadata` | JSONB | | Full metadata |
| `gateway_eui` | VARCHAR(64) | | Gateway EUI |
| `source` | VARCHAR(100) | | Source identifier |
| `inserted_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Insert timestamp |
| `last_updated` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Update timestamp |
| `error_message` | TEXT | | Processing error |

**Indexes:**
```sql
CREATE INDEX idx_ingest_uplinks_deveui ON transform.ingest_uplinks (deveui);
CREATE INDEX idx_ingest_uplinks_timestamp ON transform.ingest_uplinks (timestamp);
```

---

#### `transform.processed_uplinks`

**Purpose:** Decoded and enriched sensor data with full context

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `uplink_uuid` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique uplink ID |
| `deveui` | VARCHAR(16) | FK → device_context | Device EUI |
| `timestamp` | TIMESTAMP | | Uplink timestamp |
| `fport` | INTEGER | | LoRaWAN FPort |
| `payload` | BYTEA | | Raw payload bytes |
| `payload_decoded` | JSONB | | Decoded payload |
| `uplink_metadata` | JSONB | | Full metadata |
| `device_type_id` | INTEGER | FK → device_types | Device type |
| `location_id` | UUID | FK → locations | Device location |
| `site_id` | UUID | FK → locations | Site (denormalized) |
| `floor_id` | UUID | FK → locations | Floor (denormalized) |
| `room_id` | UUID | FK → locations | Room (denormalized) |
| `zone_id` | UUID | FK → locations | Zone (denormalized) |
| `gateway_eui` | VARCHAR(32) | | Gateway EUI |
| `source` | VARCHAR(100) | | Source identifier |
| `inserted_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Insert timestamp |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Update timestamp |

**Named Foreign Keys:**
- `fk_processed_site` → `locations(location_id)`
- `fk_processed_floor` → `locations(location_id)`
- `fk_processed_room` → `locations(location_id)`
- `fk_processed_zone` → `locations(location_id)`

**Example Decoded Payload:**
```json
{
  "payload_decoded": {
    "occupancy": "OCCUPIED",
    "battery_level": 3.2,
    "temperature": 21.5,
    "device_online": true
  }
}
```

---

#### `transform.enrichment_logs`

**Purpose:** Processing logs for debugging and monitoring

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `log_id` | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() | Unique log ID |
| `uplink_uuid` | UUID | | Related uplink UUID |
| `step` | VARCHAR(100) | CHECK IN (...) | Processing step |
| `detail` | TEXT | | Log detail message |
| `status` | VARCHAR(50) | CHECK IN (...) | Step status |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Log timestamp |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Valid Steps:**
- `ingestion_received`
- `enrichment`
- `context_enrichment`
- `unpacking_init`
- `unpacking`
- `analytics_forwarding`
- `CONTEXT_ENRICHED`
- `FAILED`
- `UNPACKED`
- `FAILED_UNPACK`

**Valid Statuses:**
- `new`, `pending`, `success`, `error`, `fail`
- `ready_for_unpacking`
- `SUCCESS`, `FAILED`, `PENDING`, `SKIPPED`

**Index:**
```sql
CREATE INDEX idx_enrichment_logs_uplink_uuid ON transform.enrichment_logs (uplink_uuid);
```

---

## Parking Config Schema

### Purpose
Device registries for sensors and displays used in parking system.

### Tables

#### `parking_config.sensor_registry`

**Purpose:** Occupancy sensor device registry

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `sensor_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique sensor ID |
| `dev_eui` | VARCHAR(16) | NOT NULL, UNIQUE | Device EUI |
| `sensor_type` | VARCHAR(50) | NOT NULL | Sensor type (occupancy, environment, door) |
| `device_model` | VARCHAR(100) | | Device model name |
| `manufacturer` | VARCHAR(100) | | Manufacturer name |
| `is_parking_related` | BOOLEAN | DEFAULT FALSE | Parking system flag |
| `payload_decoder` | VARCHAR(100) | | Decoder function name |
| `device_metadata` | JSONB | DEFAULT '{}' | Additional metadata |
| `commissioning_notes` | TEXT | | Installation notes |
| `enabled` | BOOLEAN | DEFAULT TRUE | Operational status |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Index:**
```sql
CREATE INDEX idx_sensor_registry_parking
  ON parking_config.sensor_registry(dev_eui, is_parking_related)
  WHERE is_parking_related = TRUE;
```

**Example:**
```sql
INSERT INTO parking_config.sensor_registry
  (dev_eui, sensor_type, device_model, manufacturer, is_parking_related, payload_decoder)
VALUES
  ('70b3d57ed0067001', 'occupancy', 'TABS AMB8420', 'Miromico', TRUE, 'tabs_occupancy_v2');
```

---

#### `parking_config.display_registry`

**Purpose:** Display device registry with color code mappings

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `display_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique display ID |
| `dev_eui` | VARCHAR(16) | NOT NULL, UNIQUE | Device EUI |
| `display_type` | VARCHAR(50) | NOT NULL | Display type (kuando_busylight, led_matrix, e_paper) |
| `device_model` | VARCHAR(100) | | Device model name |
| `manufacturer` | VARCHAR(100) | | Manufacturer name |
| `display_codes` | JSONB | DEFAULT '{...}' | State → hex payload mappings |
| `fport` | INTEGER | DEFAULT 1 | LoRaWAN FPort for downlinks |
| `confirmed_downlinks` | BOOLEAN | DEFAULT FALSE | Request LoRaWAN ACK |
| `max_payload_size` | INTEGER | DEFAULT 51 | Max payload bytes |
| `enabled` | BOOLEAN | DEFAULT TRUE | Operational status |
| `last_seen` | TIMESTAMP | | Last uplink timestamp |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |

**Default Display Codes:**
```json
{
  "FREE": "01",
  "OCCUPIED": "02",
  "RESERVED": "03",
  "OUT_OF_ORDER": "04",
  "MAINTENANCE": "05"
}
```

**Kuando Busylight Display Codes:**
```json
{
  "FREE": "0000FFFF00",
  "OCCUPIED": "FF0000FF00",
  "RESERVED": "FF0032FF00",
  "MAINTENANCE": "00FF00FF00",
  "OUT_OF_ORDER": "00FF00FF00"
}
```

**Index:**
```sql
CREATE INDEX idx_display_registry_deveui
  ON parking_config.display_registry(dev_eui, enabled)
  WHERE enabled = TRUE;
```

---

## Parking Spaces Schema

### Purpose
Parking space definitions, sensor-display pairing, and reservations.

### Tables

#### `parking_spaces.spaces`

**Purpose:** Core parking space entity with sensor-display pairing

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `space_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique space ID |
| `space_name` | VARCHAR(100) | NOT NULL, UNIQUE | Human-readable name |
| `space_code` | VARCHAR(20) | | Short code (e.g., "A1-001") |
| `location_description` | TEXT | | Location description |
| `building` | VARCHAR(100) | | Building name |
| `floor` | VARCHAR(50) | | Floor identifier |
| `zone` | VARCHAR(50) | | Zone identifier |
| `gps_latitude` | DECIMAL(10,8) | | GPS latitude |
| `gps_longitude` | DECIMAL(11,8) | | GPS longitude |
| `occupancy_sensor_id` | UUID | FK → sensor_registry | Sensor reference |
| `display_device_id` | UUID | FK → display_registry | Display reference |
| `occupancy_sensor_deveui` | VARCHAR(16) | | Sensor DevEUI (denormalized) |
| `display_device_deveui` | VARCHAR(16) | | Display DevEUI (denormalized) |
| `current_state` | VARCHAR(20) | DEFAULT 'FREE' | Current parking state |
| `sensor_state` | VARCHAR(20) | DEFAULT 'FREE' | Last sensor reading |
| `display_state` | VARCHAR(20) | DEFAULT 'FREE' | Last display state |
| `last_sensor_update` | TIMESTAMP | | Last sensor uplink |
| `last_display_update` | TIMESTAMP | | Last downlink sent |
| `state_changed_at` | TIMESTAMP | DEFAULT NOW() | State change timestamp |
| `auto_actuation` | BOOLEAN | DEFAULT TRUE | Enable auto actuation |
| `reservation_priority` | BOOLEAN | DEFAULT TRUE | Reservations override sensors |
| `enabled` | BOOLEAN | DEFAULT TRUE | Operational status |
| `maintenance_mode` | BOOLEAN | DEFAULT FALSE | Maintenance flag |
| `space_metadata` | JSONB | DEFAULT '{}' | Additional metadata |
| `notes` | TEXT | | Administrative notes |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last update timestamp |
| `archived` | BOOLEAN | DEFAULT FALSE | Archival flag |
| `archived_at` | TIMESTAMP | | Archival timestamp |
| `archived_by` | VARCHAR(255) | | Who archived |
| `archived_reason` | TEXT | | Archival reason |

**Constraints:**
```sql
CONSTRAINT valid_states CHECK (current_state IN (
  'FREE', 'OCCUPIED', 'RESERVED', 'OUT_OF_ORDER', 'MAINTENANCE'
));

CONSTRAINT sensor_display_required CHECK (
  archived = TRUE OR (
    (occupancy_sensor_deveui IS NOT NULL OR maintenance_mode = TRUE) AND
    display_device_deveui IS NOT NULL
  )
);
```

**Indexes:**
```sql
CREATE INDEX idx_spaces_sensor_lookup
  ON parking_spaces.spaces(occupancy_sensor_deveui, enabled)
  WHERE enabled = TRUE;

CREATE INDEX idx_spaces_display_lookup
  ON parking_spaces.spaces(display_device_deveui, enabled)
  WHERE enabled = TRUE;

CREATE INDEX idx_spaces_location
  ON parking_spaces.spaces(building, floor, zone);

CREATE INDEX idx_spaces_state
  ON parking_spaces.spaces(current_state, enabled);

CREATE INDEX idx_spaces_active
  ON parking_spaces.spaces(space_id, enabled, archived)
  WHERE enabled = TRUE AND archived = FALSE;

CREATE INDEX idx_spaces_archived
  ON parking_spaces.spaces(archived_at)
  WHERE archived = TRUE;
```

---

#### `parking_spaces.reservations`

**Purpose:** Time-based parking reservations

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `reservation_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique reservation ID |
| `space_id` | UUID | NOT NULL, FK → spaces ON DELETE CASCADE | Space reference |
| `reserved_from` | TIMESTAMP | NOT NULL | Reservation start time |
| `reserved_until` | TIMESTAMP | NOT NULL | Reservation end time |
| `external_booking_id` | VARCHAR(255) | | External system ID |
| `external_system` | VARCHAR(100) | DEFAULT 'api' | Source system |
| `external_user_id` | VARCHAR(255) | | User identifier |
| `booking_metadata` | JSONB | DEFAULT '{}' | Customer info, vehicle details |
| `reservation_type` | VARCHAR(50) | DEFAULT 'standard' | Type (standard, vip, maintenance, event) |
| `status` | VARCHAR(20) | DEFAULT 'active' | Reservation status |
| `grace_period_minutes` | INTEGER | DEFAULT 15 | No-show grace period |
| `no_show_detected_at` | TIMESTAMP | | No-show detection timestamp |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `activated_at` | TIMESTAMP | | Activation timestamp |
| `completed_at` | TIMESTAMP | | Completion timestamp |
| `cancelled_at` | TIMESTAMP | | Cancellation timestamp |
| `cancellation_reason` | TEXT | | Cancellation reason |

**Constraints:**
```sql
CONSTRAINT valid_time_range CHECK (reserved_until > reserved_from);

CONSTRAINT valid_status CHECK (status IN (
  'active', 'cancelled', 'completed', 'expired', 'no_show'
));
```

**Indexes:**
```sql
CREATE INDEX idx_reservations_active
  ON parking_spaces.reservations(space_id, status, reserved_from, reserved_until)
  WHERE status = 'active';

CREATE INDEX idx_reservations_timerange
  ON parking_spaces.reservations(reserved_from, reserved_until);

CREATE INDEX idx_reservations_external
  ON parking_spaces.reservations(external_system, external_booking_id);
```

---

## Parking Operations Schema

### Purpose
Operational logs and audit trails for display actuations.

### Tables

#### `parking_operations.actuations`

**Purpose:** Complete audit trail of display downlinks

**Columns:**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `actuation_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique actuation ID |
| `space_id` | UUID | NOT NULL, FK → spaces | Space reference |
| `trigger_type` | VARCHAR(30) | NOT NULL | Trigger type |
| `trigger_source` | VARCHAR(100) | | Trigger source identifier |
| `trigger_data` | JSONB | | Raw trigger data |
| `previous_state` | VARCHAR(20) | | State before change |
| `new_state` | VARCHAR(20) | NOT NULL | New state |
| `state_reason` | VARCHAR(100) | | Reason for state |
| `display_deveui` | VARCHAR(16) | NOT NULL | Display DevEUI |
| `display_code` | VARCHAR(10) | NOT NULL | Hex payload sent |
| `fport` | INTEGER | DEFAULT 1 | LoRaWAN FPort |
| `confirmed` | BOOLEAN | DEFAULT FALSE | Confirmed downlink flag |
| `downlink_sent` | BOOLEAN | DEFAULT FALSE | Sent successfully flag |
| `downlink_confirmed` | BOOLEAN | DEFAULT FALSE | ACK received flag |
| `response_time_ms` | INTEGER | | Downlink response time |
| `downlink_error` | TEXT | | Error message |
| `retry_count` | INTEGER | DEFAULT 0 | Retry attempts |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| `sent_at` | TIMESTAMP | | Sent timestamp |
| `confirmed_at` | TIMESTAMP | | ACK timestamp |

**Constraints:**
```sql
CONSTRAINT valid_trigger_type CHECK (trigger_type IN (
  'sensor_uplink',
  'api_reservation',
  'manual_override',
  'system_cleanup',
  'reservation_expired'
));
```

**Indexes:**
```sql
CREATE INDEX idx_actuations_space_time
  ON parking_operations.actuations(space_id, created_at DESC);

CREATE INDEX idx_actuations_trigger
  ON parking_operations.actuations(trigger_type, created_at DESC);

CREATE INDEX idx_actuations_errors
  ON parking_operations.actuations(downlink_sent, downlink_error)
  WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL;
```

**Example:**
```json
{
  "actuation_id": "a1b2c3d4-...",
  "space_id": "space-uuid",
  "trigger_type": "api_reservation",
  "trigger_source": "reservation-uuid",
  "previous_state": "FREE",
  "new_state": "RESERVED",
  "state_reason": "API reservation created",
  "display_deveui": "2020203705250102",
  "display_code": "FF0032FF00",
  "fport": 15,
  "confirmed": false,
  "downlink_sent": true,
  "response_time_ms": 145
}
```

---

## Relationships & ERD

### Core Entity Relationships

```
┌──────────────────────────────────────────────────────────────────────┐
│                     PARKING SYSTEM CORE                              │
└──────────────────────────────────────────────────────────────────────┘

parking_config.sensor_registry
    └─── (1:1) ─→ parking_spaces.spaces.occupancy_sensor_id

parking_config.display_registry
    └─── (1:1) ─→ parking_spaces.spaces.display_device_id

parking_spaces.spaces
    ├─── (1:N) ─→ parking_spaces.reservations.space_id
    └─── (1:N) ─→ parking_operations.actuations.space_id
```

### Transform Relationships

```
transform.locations (hierarchical)
    ├─── (1:N) ─→ transform.device_context.location_id
    ├─── (1:N) ─→ transform.device_context.site_id
    ├─── (1:N) ─→ transform.device_context.floor_id
    ├─── (1:N) ─→ transform.device_context.room_id
    ├─── (1:N) ─→ transform.device_context.zone_id
    ├─── (1:N) ─→ transform.gateways.site_id
    ├─── (1:N) ─→ transform.gateways.location_id
    ├─── (1:N) ─→ transform.processed_uplinks.location_id
    ├─── (1:N) ─→ transform.processed_uplinks.site_id
    ├─── (1:N) ─→ transform.processed_uplinks.floor_id
    ├─── (1:N) ─→ transform.processed_uplinks.room_id
    └─── (1:N) ─→ transform.processed_uplinks.zone_id

transform.device_types
    ├─── (1:N) ─→ transform.device_context.device_type_id
    └─── (1:N) ─→ transform.processed_uplinks.device_type_id

transform.device_context
    └─── (1:N) ─→ transform.processed_uplinks.deveui
```

### Full ERD Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE SYSTEM ERD                               │
└─────────────────────────────────────────────────────────────────────────┘

                      ┌─────────────────┐
                      │  ingest.        │
                      │  raw_uplinks    │
                      └────────┬────────┘
                               │
                               ↓ (processing)
                      ┌─────────────────┐
                      │  transform.     │
                      │  ingest_uplinks │
                      └────────┬────────┘
                               │
                               ↓ (decode + enrich)
     ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
     │ transform.   │→ │  transform.      │ ←│ transform.   │
     │ device_types │  │  processed_      │  │ locations    │
     └──────────────┘  │  uplinks         │  └──────────────┘
                       └────────┬─────────┘
                                │
                    ┌───────────┴──────────┐
                    ↓                      ↓
          ┌──────────────────┐   ┌─────────────────┐
          │ transform.       │   │ parking_config. │
          │ device_context   │   │ sensor_registry │
          └──────────────────┘   └────────┬────────┘
                                           │
                                           ↓ (1:1)
                ┌──────────────────────────────────────────┐
                │        parking_spaces.spaces             │
                │  - occupancy_sensor_id (FK)              │
                │  - display_device_id (FK)                │
                │  - current_state                         │
                └──────────────┬───────────┬───────────────┘
                               │           │
                    ┌──────────┘           └──────────┐
                    ↓ (1:N)                           ↓ (1:N)
       ┌────────────────────┐          ┌──────────────────────┐
       │ parking_spaces.    │          │ parking_operations.  │
       │ reservations       │          │ actuations           │
       └────────────────────┘          └──────────────────────┘
                                                    ↓ (downlink)
                                       ┌──────────────────────┐
                                       │ parking_config.      │
                                       │ display_registry     │
                                       └──────────────────────┘
                                                    ↓ (gRPC)
                                       ┌──────────────────────┐
                                       │ ChirpStack           │
                                       │ (device_queue_item)  │
                                       └──────────────────────┘
```

---

## Indexes

### Performance Indexes by Schema

#### Ingest Schema
```sql
-- Raw uplink lookups
idx_raw_uplinks_deveui (deveui)
idx_raw_uplinks_received_at (received_at)
idx_raw_uplinks_processed (processed)
```

#### Transform Schema
```sql
-- Uplink processing
idx_ingest_uplinks_deveui (deveui)
idx_ingest_uplinks_timestamp (timestamp)
idx_transform_ingest_deveui (deveui)
idx_transform_ingest_timestamp (timestamp)

-- Enrichment logs
idx_enrichment_logs_uplink_uuid (uplink_uuid)
```

#### Parking Config Schema
```sql
-- Sensor registry (partial index)
idx_sensor_registry_parking (dev_eui, is_parking_related)
  WHERE is_parking_related = TRUE

-- Display registry (partial index)
idx_display_registry_deveui (dev_eui, enabled)
  WHERE enabled = TRUE
```

#### Parking Spaces Schema
```sql
-- Space lookups (partial indexes)
idx_spaces_sensor_lookup (occupancy_sensor_deveui, enabled)
  WHERE enabled = TRUE

idx_spaces_display_lookup (display_device_deveui, enabled)
  WHERE enabled = TRUE

-- Location queries
idx_spaces_location (building, floor, zone)

-- State queries
idx_spaces_state (current_state, enabled)

-- Active spaces (partial index)
idx_spaces_active (space_id, enabled, archived)
  WHERE enabled = TRUE AND archived = FALSE

-- Archived spaces (partial index)
idx_spaces_archived (archived_at)
  WHERE archived = TRUE

-- Reservation queries (partial index)
idx_reservations_active (space_id, status, reserved_from, reserved_until)
  WHERE status = 'active'

idx_reservations_timerange (reserved_from, reserved_until)
idx_reservations_external (external_system, external_booking_id)
```

#### Parking Operations Schema
```sql
-- Actuation logs
idx_actuations_space_time (space_id, created_at DESC)
idx_actuations_trigger (trigger_type, created_at DESC)

-- Error tracking (partial index)
idx_actuations_errors (downlink_sent, downlink_error)
  WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL
```

---

## Sample Queries

### Common Queries

#### 1. Get Active Parking Spaces
```sql
SELECT
  s.space_id,
  s.space_name,
  s.space_code,
  s.current_state,
  s.building,
  s.floor,
  s.zone,
  sr.dev_eui AS sensor_deveui,
  dr.dev_eui AS display_deveui
FROM parking_spaces.spaces s
LEFT JOIN parking_config.sensor_registry sr ON s.occupancy_sensor_id = sr.sensor_id
LEFT JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
WHERE s.enabled = TRUE
  AND s.archived = FALSE
ORDER BY s.building, s.floor, s.space_code;
```

#### 2. Find Space by Sensor Uplink
```sql
SELECT
  s.space_id,
  s.space_name,
  s.current_state,
  s.display_device_deveui,
  dr.display_codes,
  dr.fport
FROM parking_spaces.spaces s
JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
WHERE s.occupancy_sensor_deveui = '70b3d57ed0067001'
  AND s.enabled = TRUE
  AND s.archived = FALSE;
```

#### 3. Get Active Reservations
```sql
SELECT
  r.reservation_id,
  s.space_name,
  s.space_code,
  r.reserved_from,
  r.reserved_until,
  r.status,
  r.external_user_id,
  r.booking_metadata
FROM parking_spaces.reservations r
JOIN parking_spaces.spaces s ON r.space_id = s.space_id
WHERE r.status = 'active'
  AND r.reserved_until > NOW()
ORDER BY r.reserved_from;
```

#### 4. Get Actuation History for Space
```sql
SELECT
  a.actuation_id,
  a.created_at,
  a.trigger_type,
  a.previous_state,
  a.new_state,
  a.display_code,
  a.downlink_sent,
  a.response_time_ms,
  a.downlink_error
FROM parking_operations.actuations a
WHERE a.space_id = 'space-uuid-here'
ORDER BY a.created_at DESC
LIMIT 100;
```

#### 5. Get Failed Downlinks
```sql
SELECT
  a.actuation_id,
  s.space_name,
  a.display_deveui,
  a.created_at,
  a.new_state,
  a.display_code,
  a.downlink_error,
  a.retry_count
FROM parking_operations.actuations a
JOIN parking_spaces.spaces s ON a.space_id = s.space_id
WHERE a.downlink_sent = FALSE
   OR a.downlink_error IS NOT NULL
ORDER BY a.created_at DESC
LIMIT 50;
```

#### 6. Get Processed Uplinks with Context
```sql
SELECT
  pu.uplink_uuid,
  pu.deveui,
  pu.timestamp,
  pu.payload_decoded,
  dc.name AS device_name,
  dt.device_type,
  l.name AS location_name,
  s.name AS site_name
FROM transform.processed_uplinks pu
LEFT JOIN transform.device_context dc ON pu.deveui = dc.deveui
LEFT JOIN transform.device_types dt ON pu.device_type_id = dt.device_type_id
LEFT JOIN transform.locations l ON pu.location_id = l.location_id
LEFT JOIN transform.locations s ON pu.site_id = s.location_id
WHERE pu.timestamp > NOW() - INTERVAL '24 hours'
ORDER BY pu.timestamp DESC
LIMIT 100;
```

#### 7. Building Occupancy Summary
```sql
SELECT
  s.building,
  s.floor,
  COUNT(*) AS total_spaces,
  SUM(CASE WHEN s.current_state = 'FREE' THEN 1 ELSE 0 END) AS free_spaces,
  SUM(CASE WHEN s.current_state = 'OCCUPIED' THEN 1 ELSE 0 END) AS occupied_spaces,
  SUM(CASE WHEN s.current_state = 'RESERVED' THEN 1 ELSE 0 END) AS reserved_spaces,
  ROUND(100.0 * SUM(CASE WHEN s.current_state = 'OCCUPIED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS occupancy_pct
FROM parking_spaces.spaces s
WHERE s.enabled = TRUE
  AND s.archived = FALSE
  AND s.maintenance_mode = FALSE
GROUP BY s.building, s.floor
ORDER BY s.building, s.floor;
```

---

## Kuando Integration

### Kuando-Specific Tables and Queries

#### Display Registry Entry for Kuando
```sql
INSERT INTO parking_config.display_registry (
  dev_eui,
  display_type,
  device_model,
  manufacturer,
  display_codes,
  fport,
  confirmed_downlinks,
  enabled
)
VALUES (
  '2020203705250102',
  'kuando_busylight',
  'Kuando Busylight IoT Omega LoRaWAN',
  'Kuando',
  '{
    "FREE": "0000FFFF00",
    "OCCUPIED": "FF0000FF00",
    "RESERVED": "FF0032FF00",
    "MAINTENANCE": "00FF00FF00",
    "OUT_OF_ORDER": "00FF00FF00"
  }'::jsonb,
  15,
  FALSE,
  TRUE
);
```

#### Create Parking Space with Kuando Display
```sql
INSERT INTO parking_spaces.spaces (
  space_name,
  space_code,
  building,
  floor,
  zone,
  occupancy_sensor_id,
  display_device_id,
  occupancy_sensor_deveui,
  display_device_deveui,
  current_state,
  auto_actuation,
  enabled
)
VALUES (
  'Woki Space A1-001',
  'A1-001',
  'Woki',
  '1st Floor',
  'Zone A',
  (SELECT sensor_id FROM parking_config.sensor_registry WHERE dev_eui = '70b3d57ed0067001'),
  (SELECT display_id FROM parking_config.display_registry WHERE dev_eui = '2020203705250102'),
  '70b3d57ed0067001',
  '2020203705250102',
  'FREE',
  TRUE,
  TRUE
);
```

#### Get Kuando Display Color Code for State
```sql
SELECT
  s.space_id,
  s.space_name,
  s.current_state,
  dr.dev_eui AS display_deveui,
  dr.display_codes ->> s.current_state AS color_code,
  dr.fport
FROM parking_spaces.spaces s
JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
WHERE s.space_id = 'space-uuid-here';
```

**Result:**
```
space_id: a1b2c3d4-...
space_name: Woki Space A1-001
current_state: RESERVED
display_deveui: 2020203705250102
color_code: FF0032FF00
fport: 15
```

#### List All Kuando Devices
```sql
SELECT
  dr.dev_eui,
  dr.device_model,
  dr.display_codes,
  dr.enabled,
  dr.last_seen,
  COUNT(s.space_id) AS spaces_assigned
FROM parking_config.display_registry dr
LEFT JOIN parking_spaces.spaces s ON dr.display_id = s.display_device_id
WHERE dr.display_type = 'kuando_busylight'
  AND dr.dev_eui LIKE '202020%'
GROUP BY dr.display_id, dr.dev_eui, dr.device_model, dr.display_codes, dr.enabled, dr.last_seen
ORDER BY dr.dev_eui;
```

---

## References

**Source Files:**
- `/opt/smart-parking-v4-OLD/database/init/01-create-databases.sql`
- `/opt/smart-parking-v4-OLD/database/init/02-iot-platform-tables.sql`
- `/opt/smart-parking-v4-OLD/database/init/04-parking-display-schema.sql`
- `/opt/smart-parking-v4-OLD/database/init/05-parking-spaces-archival.sql`

**Related Documentation:**
- `V4_KUANDO_DOWNLINK_MECHANISM.md` - Downlink integration details
- `KUANDO_DOWNLINK_REFERENCE.md` - Kuando payload specifications

**PostgreSQL Version:** 16
**ChirpStack Version:** 4.x
**Platform:** Smart Parking v4

---

**Document Maintainer:** Claude Code
**Last Updated:** 2025-10-16
**Version:** 1.0.0
