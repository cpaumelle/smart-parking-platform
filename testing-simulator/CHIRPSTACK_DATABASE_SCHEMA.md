# ChirpStack v4 Database Schema Documentation

## Overview

ChirpStack v4 uses PostgreSQL to store all LoRaWAN network server data including tenants, applications, devices, gateways, and device profiles.

**Database:** `chirpstack`  
**Default Port:** 5432  
**Schema:** `public`

---

## Entity Hierarchy

```
Tenant (Organization)
  ├── Applications (LoRaWAN Applications)
  │   └── Devices (End devices)
  │       └── Device Keys (OTAA keys)
  ├── Device Profiles (Device configurations)
  └── Gateways (LoRaWAN gateways)
```

---

## Core Tables

### 1. `tenant` - Multi-tenancy

Represents organizations/customers in multi-tenant deployments.

**Key Fields:**
- `id` (UUID, PK) - Unique tenant identifier
- `name` (VARCHAR(100)) - Tenant name
- `description` (TEXT) - Tenant description
- `can_have_gateways` (BOOLEAN) - Can register gateways
- `max_device_count` (INTEGER) - Maximum devices allowed
- `max_gateway_count` (INTEGER) - Maximum gateways allowed
- `tags` (JSONB) - Custom tags

**Relationships:**
- One tenant → Many applications
- One tenant → Many device profiles
- One tenant → Many gateways

**Example Query:**
```sql
SELECT id, name, max_device_count, max_gateway_count 
FROM tenant;
```

---

### 2. `application` - LoRaWAN Applications

Groups devices together for organizational purposes.

**Key Fields:**
- `id` (UUID, PK) - Unique application identifier
- `tenant_id` (UUID, FK) - Parent tenant
- `name` (VARCHAR(100)) - Application name
- `description` (TEXT) - Application description
- `mqtt_tls_cert` (BYTEA) - MQTT TLS certificate
- `tags` (JSONB) - Custom tags
- `created_at`, `updated_at` (TIMESTAMP)

**Relationships:**
- Many applications → One tenant
- One application → Many devices

**Example:**
```sql
SELECT id, name, tenant_id, 
       (SELECT COUNT(*) FROM device WHERE application_id = application.id) as device_count
FROM application;
```

---

### 3. `device_profile` - Device Configurations

Defines device capabilities and LoRaWAN parameters.

**Key Fields:**
- `id` (UUID, PK) - Unique profile identifier
- `tenant_id` (UUID, FK) - Parent tenant
- `name` (VARCHAR(100)) - Profile name
- `region` (VARCHAR(10)) - LoRaWAN region (e.g., EU868, US915)
- `mac_version` (VARCHAR(10)) - LoRaWAN MAC version (e.g., 1.0.3, 1.1.0)
- `reg_params_revision` (VARCHAR(20)) - Regional parameters revision
- `supports_otaa` (BOOLEAN) - Over-The-Air Activation support
- `supports_class_b` (BOOLEAN) - Class B support
- `supports_class_c` (BOOLEAN) - Class C support
- `adr_algorithm_id` (VARCHAR(100)) - ADR algorithm
- `uplink_interval` (INTEGER) - Expected uplink interval (seconds)
- `payload_codec_runtime` (VARCHAR(20)) - Codec runtime (NONE, CAYENNE_LPP, JS)
- `payload_codec_script` (TEXT) - JavaScript codec
- `tags` (JSONB) - Custom tags

**Class-Specific Parameters:**
- `class_b_params` (JSONB) - Class B configuration
- `class_c_params` (JSONB) - Class C configuration
- `relay_params` (JSONB) - Relay configuration

**Example Profiles:**
```sql
SELECT id, name, mac_version, region, supports_otaa, supports_class_c
FROM device_profile
WHERE tenant_id = '97e4f067-b35e-4e4d-9ba8-94d484474d9b';
```

---

### 4. `device` - End Devices

Represents individual LoRaWAN devices.

**Key Fields:**
- `dev_eui` (BYTEA, PK) - Device EUI (8 bytes, unique identifier)
- `application_id` (UUID, FK) - Parent application
- `device_profile_id` (UUID, FK) - Device profile
- `name` (VARCHAR(100)) - Device name
- `description` (TEXT) - Device description
- `join_eui` (BYTEA) - Join/App EUI (8 bytes)
- `enabled_class` (CHAR(1)) - Current class: 'A', 'B', or 'C'
- `skip_fcnt_check` (BOOLEAN) - Skip frame counter validation
- `is_disabled` (BOOLEAN) - Device disabled flag
- `tags` (JSONB) - Custom tags
- `variables` (JSONB) - Device variables

**State Fields:**
- `last_seen_at` (TIMESTAMP) - Last uplink timestamp
- `dev_addr` (BYTEA) - Device address (4 bytes, assigned after join)
- `device_session` (BYTEA) - Current session state
- `battery_level` (NUMERIC(5,2)) - Battery percentage
- `margin` (INTEGER) - Link margin
- `dr` (SMALLINT) - Data rate

**Location Fields:**
- `latitude`, `longitude` (DOUBLE PRECISION)
- `altitude` (REAL)

**Important Notes:**
1. **dev_eui** must be **8 bytes** (16 hex characters)
2. **join_eui** must be **8 bytes** (often all zeros or manufacturer EUI)
3. **enabled_class** determines device behavior:
   - 'A' - Class A (most devices)
   - 'C' - Class C (always listening, like Busylights)
   - 'B' - Class B (scheduled receive windows)

**Example:**
```sql
-- Get device with hex-encoded EUI
SELECT 
    encode(dev_eui, 'hex') as dev_eui,
    name,
    encode(join_eui, 'hex') as join_eui,
    enabled_class,
    skip_fcnt_check,
    is_disabled,
    last_seen_at
FROM device
WHERE application_id = '345b028b-9f0a-4c56-910c-6a05dc2dc22f'
LIMIT 5;
```

---

### 5. `device_keys` - OTAA Keys

Stores encryption keys for Over-The-Air Activation.

**Key Fields:**
- `dev_eui` (BYTEA, PK, FK) - Device EUI (references device)
- `nwk_key` (BYTEA) - Network key (16 bytes)
- `app_key` (BYTEA) - Application key (16 bytes)
- `gen_app_key` (BYTEA) - Generated app key
- `join_nonce` (INTEGER) - Join nonce counter
- `dev_nonces` (JSONB) - Used device nonces (replay protection)
- `created_at`, `updated_at` (TIMESTAMP)

**Important Notes:**
1. For **LoRaWAN 1.0.x**: `nwk_key` == `app_key` (same value)
2. For **LoRaWAN 1.1+**: `nwk_key` ≠ `app_key` (different keys)
3. Keys must be **16 bytes** (32 hex characters)
4. ⚠️ **CRITICAL**: `dev_nonces` must be `{}` (empty object), NOT `[]` (empty array)
   - Wrong: `'[]'::jsonb` → ChirpStack error: "invalid type: sequence, expected a map"
   - Correct: `'{}'::jsonb` → Works properly

**Example:**
```sql
SELECT 
    encode(dev_eui, 'hex') as dev_eui,
    encode(nwk_key, 'hex') as nwk_key,
    encode(app_key, 'hex') as app_key,
    join_nonce
FROM device_keys
WHERE dev_eui = decode('58a0cb0000108ff7', 'hex');
```

---

### 6. `gateway` - LoRaWAN Gateways

Represents LoRaWAN gateways forwarding device uplinks.

**Key Fields:**
- `gateway_id` (BYTEA, PK) - Gateway EUI (8 bytes)
- `tenant_id` (UUID, FK) - Parent tenant
- `name` (VARCHAR(100)) - Gateway name
- `description` (TEXT) - Gateway description
- `latitude`, `longitude`, `altitude` - Location
- `tags` (JSONB) - Custom tags
- `stats_interval_secs` (INTEGER) - Stats reporting interval
- `last_seen_at` (TIMESTAMP) - Last activity

---

## Supporting Tables

### `device_queue_item` - Downlink Queue

Queued downlink messages for devices.

**Key Fields:**
- `id` (UUID, PK)
- `dev_eui` (BYTEA, FK) - Target device
- `fport` (SMALLINT) - LoRaWAN FPort
- `data` (BYTEA) - Payload
- `confirmed` (BOOLEAN) - Requires acknowledgment
- `is_pending` (BOOLEAN) - Awaiting transmission

---

### `application_integration` - External Integrations

Configuration for HTTP, MQTT, and other integrations.

**Key Fields:**
- `application_id` (UUID, FK)
- `kind` (VARCHAR(20)) - Integration type (HTTP, MQTT, etc.)
- `configuration` (JSONB) - Integration config

---

## Data Types Reference

### Binary Data Storage

ChirpStack stores LoRaWAN identifiers as **bytea** (binary):

| Field | Size | Format | Example (Hex) |
|-------|------|--------|---------------|
| dev_eui | 8 bytes | 16 hex chars | `70b3d5326000a899` |
| join_eui | 8 bytes | 16 hex chars | `70b3d53260000100` |
| dev_addr | 4 bytes | 8 hex chars | `01abcdef` |
| nwk_key | 16 bytes | 32 hex chars | `af324ad563414ec85027247ec0e1cb71` |
| app_key | 16 bytes | 32 hex chars | `00112233445566778899aabbccddeeff` |

### Converting Between Hex and Binary

**Hex String → Binary:**
```sql
-- Insert device with hex DevEUI
INSERT INTO device (dev_eui, ...) 
VALUES (decode('7e57000000000001', 'hex'), ...);
```

**Binary → Hex String:**
```sql
-- Query device with hex-encoded DevEUI
SELECT encode(dev_eui, 'hex') as dev_eui FROM device;
```

---

## Indexes

ChirpStack uses several index types for performance:

- **B-tree indexes** - Primary keys, foreign keys, lookups
- **GIN indexes** - Full-text search (trgm), JSONB tags
- **Trigram indexes** - Fast text search on names

Example:
```sql
-- Fast search by device name (uses idx_device_name_trgm)
SELECT * FROM device WHERE name ILIKE '%sensor%';

-- Fast search by tags (uses idx_device_tags)
SELECT * FROM device WHERE tags @> '{"simulator": "true"}';
```

---

## Common Queries

### Get All Devices in an Application

```sql
SELECT 
    encode(d.dev_eui, 'hex') as dev_eui,
    d.name,
    d.description,
    d.enabled_class,
    d.last_seen_at,
    dp.name as profile_name
FROM device d
JOIN device_profile dp ON d.device_profile_id = dp.id
WHERE d.application_id = '345b028b-9f0a-4c56-910c-6a05dc2dc22f'
ORDER BY d.name;
```

### Get Device with Keys

```sql
SELECT 
    encode(d.dev_eui, 'hex') as dev_eui,
    d.name,
    encode(dk.app_key, 'hex') as app_key,
    encode(dk.nwk_key, 'hex') as nwk_key
FROM device d
LEFT JOIN device_keys dk ON d.dev_eui = dk.dev_eui
WHERE d.name ILIKE '%sensor%';
```

### Count Devices by Application

```sql
SELECT 
    a.name as application,
    COUNT(d.dev_eui) as device_count
FROM application a
LEFT JOIN device d ON a.id = d.application_id
WHERE a.tenant_id = '97e4f067-b35e-4e4d-9ba8-94d484474d9b'
GROUP BY a.id, a.name;
```

### Get Devices Never Seen

```sql
SELECT 
    encode(dev_eui, 'hex') as dev_eui,
    name,
    created_at
FROM device
WHERE last_seen_at IS NULL
ORDER BY created_at DESC;
```

---

## Insert Device Example (SQL)

### Step 1: Insert Device

```sql
INSERT INTO device (
    dev_eui,
    application_id,
    device_profile_id,
    name,
    description,
    join_eui,
    enabled_class,
    skip_fcnt_check,
    is_disabled,
    external_power_source,
    tags,
    variables,
    created_at,
    updated_at,
    app_layer_params
) VALUES (
    decode('7e57000000000001', 'hex'),                      -- dev_eui (8 bytes)
    '345b028b-9f0a-4c56-910c-6a05dc2dc22f',                -- application_id
    '8a67cf91-daad-4910-b2d1-f3e4ae05e35a',                -- device_profile_id
    'TESTING Sensor 1',                                      -- name
    '⚠️ TESTING ONLY - Safe to delete',                    -- description
    decode('0000000000000000', 'hex'),                      -- join_eui (8 bytes, often zeros)
    'A',                                                     -- enabled_class (A, B, or C)
    true,                                                    -- skip_fcnt_check (useful for testing)
    false,                                                   -- is_disabled
    false,                                                   -- external_power_source
    '{"simulator": "true", "testing": "true"}'::jsonb,      -- tags
    '{}'::jsonb,                                            -- variables
    NOW(),                                                   -- created_at
    NOW(),                                                   -- updated_at
    '{}'::jsonb                                             -- app_layer_params
);
```

### Step 2: Insert Device Keys

```sql
INSERT INTO device_keys (
    dev_eui,
    nwk_key,
    app_key,
    gen_app_key,
    join_nonce,
    dev_nonces,
    created_at,
    updated_at
) VALUES (
    decode('7e57000000000001', 'hex'),                      -- dev_eui
    decode('00112233445566778899aabbccddeeff', 'hex'),      -- nwk_key (16 bytes)
    decode('00112233445566778899aabbccddeeff', 'hex'),      -- app_key (16 bytes, same for LoRaWAN 1.0.x)
    decode('00000000000000000000000000000000', 'hex'),      -- gen_app_key (16 bytes, empty)
    0,                                                       -- join_nonce
    '{}'::jsonb,                                            -- dev_nonces (empty object, NOT array)
    NOW(),                                                   -- created_at
    NOW()                                                    -- updated_at
);
```

---

## Constraints and Validation

### Foreign Key Cascades

When a tenant, application, or device profile is deleted:
- **CASCADE DELETE** removes all dependent records
- Example: Deleting an application removes all its devices and device keys

### Unique Constraints

- `dev_eui` is globally unique (primary key)
- `gateway_id` is globally unique
- Application names are unique per tenant

### Required Fields

Most fields are `NOT NULL` and require values:
- Provide empty strings `''` for unused text fields
- Provide empty JSONB `'{}'` for tags/variables
- Use `false` for boolean flags if not enabled

---

## Performance Considerations

### Indexes for Fast Lookups

- **dev_eui lookups**: Uses primary key index
- **Device name search**: Uses trigram GIN index
- **Tag searches**: Uses JSONB GIN index
- **Application filtering**: Uses B-tree index on application_id

### Bulk Operations

For bulk inserts:
1. Use transactions (`BEGIN`/`COMMIT`)
2. Consider disabling triggers temporarily
3. Use `COPY` command for large datasets

---

## Security Notes

1. **API Keys**: Stored in `api_key` table with tenant association
2. **Device Keys**: Stored encrypted in `device_keys` table
3. **Access Control**: Tenant-based multi-tenancy model
4. **Replay Protection**: `dev_nonces` tracks used nonces

---

**Last Updated:** 2025-10-13  
**ChirpStack Version:** 4.14.1  
**Database:** PostgreSQL 15+

