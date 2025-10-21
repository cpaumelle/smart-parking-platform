# Database Schema Documentation

**Smart Parking Platform v5**
**Database:** `parking_v5`
**PostgreSQL Version:** 16.10

---

## Overview

The Smart Parking Platform uses PostgreSQL with the following extensions:
- `uuid-ossp` - UUID generation functions
- `pgcrypto` - Cryptographic functions for API key hashing and password hashing
- `btree_gist` - Support for EXCLUDE constraints (reservation overlap prevention)

### Architecture

The schema follows a **multi-tenant device registry pattern** with strict tenant isolation:

**Multi-Tenancy Layer (v5.3.0):**
- **Tenant management:** `tenants`, `sites` (organizational hierarchy)
- **User management:** `users`, `user_memberships` (RBAC with 4-level role hierarchy)
- **Security:** `api_keys` (tenant-scoped API keys with scope enforcement), `webhook_secrets` (per-tenant webhook signing)
- **Device tracking:** `orphan_devices` (auto-discovered devices awaiting assignment)

**Device & Space Management:**
- **Device registries:** `sensor_devices`, `display_devices` (device metadata, capabilities, tenant-scoped)
- **Space management:** `spaces` (location metadata, current state, tenant and site scoped)
- **Operational logs:** `sensor_readings`, `state_changes`, `actuations` (time-series and audit data)
- **Business logic:** `reservations` (tenant-scoped booking with overlap prevention and idempotency)

### Tables

**Multi-Tenancy Tables (v5.3.0):**
1. **tenants** - Tenant organizations with isolation metadata
2. **sites** - Physical locations per tenant
3. **users** - User accounts with bcrypt password hashing
4. **user_memberships** - User-tenant-role mappings (RBAC)
5. **webhook_secrets** - Per-tenant HMAC-SHA256 webhook signing keys
6. **orphan_devices** - Auto-discovered devices with fcnt tracking

**Core Tables:**
7. **device_types** - Centralized device type registry with handler and configuration metadata
8. **sensor_devices** - Sensor device registry with metadata and capabilities (tenant-scoped)
9. **display_devices** - Display device registry with per-device configuration (tenant-scoped)
10. **spaces** - Parking space definitions and current state (tenant and site scoped)
11. **actuations** - Display update audit trail with success/failure tracking
12. **sensor_readings** - Historical sensor data from IoT devices (fcnt deduplication)
13. **state_changes** - Audit log of all state transitions
14. **reservations** - Parking space reservations with tenant isolation and idempotency
15. **api_keys** - API authentication credentials with tenant scoping and scope enforcement

**Display & Downlink Tables (v5.3.0):**
16. **display_policies** - Policy-driven display control rules (one active per tenant)
17. **display_state_cache** - Redis cache version tracking for policy invalidation
18. **sensor_debounce_state** - Duplicate sensor event prevention

**Security & Audit Tables (v5.3.0):**
19. **audit_log** - Append-only audit trail (immutable via database trigger)
20. **refresh_tokens** - JWT refresh tokens with 30-day expiry and device fingerprinting

### Views

1. **v_spaces** - Materialized view with pre-joined tenant/site data (v5.3.0)
2. **unassigned_sensors** - Sensors with status='orphan' not linked to any space
3. **unassigned_displays** - Displays with status='orphan' not linked to any space
4. **all_unassigned_devices** - Union of unassigned sensors and displays
5. **orphan_devices** - All orphan devices with device type metadata
6. **orphan_device_types** - Device types with status='orphan' and device counts
7. **inconsistent_devices** - Devices with status mismatches (active but unassigned, orphan but assigned)

> **Note:** For detailed device types architecture, see `/docs/DEVICE_TYPES_ARCHITECTURE.md`
> **Note:** For ORPHAN device auto-discovery pattern, see `/docs/ORPHAN_DEVICE_ARCHITECTURE.md`
> **Note:** For downlink reliability and reconciliation system, see `/docs/DOWNLINK_RELIABILITY_IMPLEMENTATION_COMPLETE.md`
> **Note:** For Class-C downlink queue implementation, see `/docs/CLASS_C_DOWNLINK_QUEUE.md`
> **Note:** For webhook hardening, see `/docs/WEBHOOK_INGEST_IMPLEMENTATION.md`
> **Note:** For observability and operations, see `/docs/OPERATIONAL_RUNBOOKS.md`
> **Note:** For security and audit logging, see `/docs/SECURITY_TENANCY.md`
> **Note:** For testing strategy, see `/docs/TESTING_STRATEGY_IMPLEMENTATION.md`

### Background Processes & Data Integrity

The system employs **periodic background tasks** to ensure data integrity and display synchronization:

#### Display Reconciliation (Every 2 minutes)
**Purpose:** Guarantee 100% sync between database state and physical display devices

**Process:**
1. Query all active `spaces` with `display_eui` not null
2. Join with `display_devices` to get device configuration
3. For each space:
   - Fetch current state from `spaces.state`
   - Check Redis cache for last known display RGB (`device:{dev_eui}:last_kuando_uplink`)
   - Compare expected vs actual RGB values
   - **If mismatch:** Queue corrective downlink via ChirpStack
   - **If no recent data:** Poll device (send refresh downlink)
   - **If in sync:** Log confirmation

**SQL Query Pattern:**
```sql
SELECT s.id, s.code, s.state, s.display_eui,
       dd.display_codes, dd.fport, dd.confirmed_downlinks
FROM spaces s
INNER JOIN display_devices dd ON s.display_eui = dd.dev_eui
WHERE s.deleted_at IS NULL
  AND s.display_eui IS NOT NULL
  AND dd.enabled = TRUE
```

**Corrective Actions:**
- **Mismatch Detection:** Log to `actuations` table with `trigger_type='system_cleanup'`
- **Polling:** Update Redis with fresh display status on response
- **Failure:** Log error and retry on next cycle

#### Other Background Tasks
- **Queue Cleanup** (Every 5 min): Flush stuck downlinks when gateways offline
- **Monitoring** (Every 5 min): System health metrics and space state distribution
- **Cleanup** (Every 1 hour): Purge old `sensor_readings` (>30 days), `state_changes` (>90 days)

---

## Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      MULTI-TENANCY LAYER (v5.3.0)                        │
└──────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │     tenants      │
                    │  (id: UUID PK)   │
                    │  - name, slug    │
                    └────────┬─────────┘
                             │ 1
                  ┌──────────┴──────────┬──────────────┬──────────────┐
                  │ *                   │ *            │ *            │ *
                  ▼                     ▼              ▼              ▼
          ┌──────────────┐      ┌──────────┐  ┌────────────┐ ┌──────────────┐
          │    sites     │      │  users   │  │  api_keys  │ │webhook_secrets│
          │ (tenant_id FK│      │          │  │(tenant_id) │ │(tenant_id FK) │
          └──────┬───────┘      └────┬─────┘  └────────────┘ └──────────────┘
                 │ 1                 │ 1
                 │                   │
                 │                   │ *
                 │                   ▼
                 │            ┌────────────────┐
                 │            │user_memberships│
                 │            │(user_id FK,    │
                 │            │tenant_id FK,   │
                 │            │role: enum)     │
                 │            └────────────────┘
                 │
┌────────────────┴────────────────────────────────────────────────────────┐
│                      DEVICE & SPACE LAYER                                │
└──────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  device_types    │
                    │  (id: UUID PK)   │
                    │  - handler_class │
                    └────────┬─────────┘
                             │
                  ┌──────────┴──────────┐
                  │ 1                   │ 1
                  ▼ *                   ▼ *
┌──────────────────────┐       ┌──────────────────────┐       ┌────────────────┐
│  sensor_devices      │       │  display_devices     │       │orphan_devices  │
│  (id: UUID PK)       │       │  (id: UUID PK)       │       │(dev_eui,fcnt)  │
│  - device_type_id FK │       │  - device_type_id FK │       │(tenant_id FK)  │
└────────┬─────────────┘       └────────┬─────────────┘       └────────────────┘
         │                              │
         │ 1                            │ 1
         │                              │
         ▼ *                            ▼ *
    ┌────────────────────────────────────────┐
    │              spaces                    │
    │  (id: UUID PK)                         │
    │  - tenant_id (FK) ← TENANT SCOPED      │
    │  - site_id (FK)                        │
    │  - sensor_device_id (FK)               │
    │  - display_device_id (FK)              │
    │  - sensor_eui (denormalized)           │
    │  - display_eui (denormalized)          │
    └───┬────────┬────────┬──────────────────┘
        │ 1      │ 1      │ 1
        │        │        │
        │ *      │ *      │ *
        ▼        ▼        ▼
  ┌──────────┐ ┌────────────┐ ┌──────────────────────┐
  │sensor_   │ │state_      │ │   reservations       │
  │readings  │ │changes     │ │ (tenant_id FK)       │
  └──────────┘ └────────────┘ │ (request_id)         │
        │ 1                   │ EXCLUDE constraint   │
        │                     └──────────────────────┘
        │ *
        ▼
  ┌──────────┐
  │actuations│  (display update audit trail)
  └──────────┘

NOTES:
- tenants: Root of multi-tenancy hierarchy, strict isolation enforced via FK
- sites: Physical locations per tenant, spaces must belong to a site
- users: Global user accounts, linked to tenants via user_memberships
- user_memberships: Maps users to tenants with roles (owner/admin/operator/viewer)
- api_keys: Tenant-scoped with scopes (read/write/manage/admin)
- webhook_secrets: Per-tenant HMAC-SHA256 signing keys
- orphan_devices: Auto-discovered devices with fcnt deduplication
- spaces: Tenant and site scoped via FK + tenant_id sync trigger
- reservations: Tenant-scoped with EXCLUDE constraint preventing overlaps + idempotent via request_id
- device_types: Central registry for device type metadata
- sensor_devices & display_devices: Can share same dev_eui (dual-role devices)
- spaces: Links to both device registries (FK) + denormalized DevEUIs (performance)
- actuations: Audit trail linked to spaces and display_devices
```

---

## Table Definitions

### Multi-Tenancy Tables (v5.3.0)

### 1. tenants

**Purpose:** Root table for multi-tenant organization hierarchy with strict isolation.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `name` | varchar(255) | NOT NULL | - | Organization name |
| `slug` | varchar(100) | NOT NULL | - | URL-safe unique identifier |
| `is_active` | boolean | NOT NULL | true | Tenant enabled/disabled |
| `metadata` | jsonb | NULL | - | Additional tenant metadata |
| `settings` | jsonb | NULL | - | Tenant-specific settings (timezone, features, etc.) |
| `created_at` | timestamptz | NOT NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (slug) - Unique identifier for URL routing

**Indexes:**
- `idx_tenants_slug` (slug) WHERE is_active = true
- `idx_tenants_active` (is_active, created_at)

**Triggers:**
- `update_tenants_updated_at` - Automatically updates `updated_at` on row modification

**Example Data:**
```json
{
  "name": "Acme Corporation",
  "slug": "acme",
  "is_active": true,
  "metadata": {"industry": "parking", "billing_plan": "enterprise"},
  "settings": {"timezone": "America/New_York", "max_spaces": 500}
}
```

---

### 2. sites

**Purpose:** Physical locations within a tenant (buildings, parking lots, campuses).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NOT NULL | - | Foreign key to tenants |
| `name` | varchar(255) | NOT NULL | - | Site name |
| `timezone` | varchar(50) | NOT NULL | 'UTC' | IANA timezone (e.g., 'America/New_York') |
| `location` | jsonb | NULL | - | Address, GPS coordinates, metadata |
| `created_at` | timestamptz | NOT NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
- `UNIQUE` (tenant_id, name) - Site names unique within tenant

**Indexes:**
- `idx_sites_tenant` (tenant_id, created_at)

**Triggers:**
- `update_sites_updated_at` - Automatically updates `updated_at` on row modification

**Example Data:**
```json
{
  "tenant_id": "tenant-uuid",
  "name": "Building A - Main Parking",
  "timezone": "America/Los_Angeles",
  "location": {
    "address": "123 Main St, San Francisco, CA 94102",
    "latitude": 37.7749,
    "longitude": -122.4194
  }
}
```

---

### 3. users

**Purpose:** User accounts with bcrypt password hashing (12 rounds).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `email` | varchar(255) | NOT NULL | - | User email (unique, case-insensitive) |
| `name` | varchar(255) | NOT NULL | - | Full name |
| `password_hash` | text | NOT NULL | - | bcrypt hash with 12 rounds |
| `is_active` | boolean | NOT NULL | true | User account enabled/disabled |
| `email_verified` | boolean | NOT NULL | false | Email verification status |
| `metadata` | jsonb | NULL | - | Additional user metadata (phone, avatar, etc.) |
| `created_at` | timestamptz | NOT NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (email) - Case-insensitive unique constraint

**Indexes:**
- `idx_users_email` (LOWER(email)) WHERE is_active = true
- `idx_users_active` (is_active, created_at)

**Triggers:**
- `update_users_updated_at` - Automatically updates `updated_at` on row modification

**Security:**
- Passwords hashed using bcrypt with 12 rounds (via Python `bcrypt.hashpw()`)
- Email stored lowercase for case-insensitive matching
- No password storage in plaintext

---

### 4. user_memberships

**Purpose:** Maps users to tenants with role-based access control (RBAC).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `user_id` | uuid | NOT NULL | - | Foreign key to users |
| `tenant_id` | uuid | NOT NULL | - | Foreign key to tenants |
| `role` | varchar(50) | NOT NULL | 'viewer' | Role (owner, admin, operator, viewer) |
| `created_at` | timestamptz | NOT NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NOT NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (user_id) REFERENCES users(id) ON DELETE CASCADE
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
- `UNIQUE` (user_id, tenant_id) - One role per user per tenant
- `CHECK` (role IN ('owner', 'admin', 'operator', 'viewer'))

**Indexes:**
- `idx_user_memberships_user` (user_id, tenant_id)
- `idx_user_memberships_tenant` (tenant_id, role)

**Triggers:**
- `update_user_memberships_updated_at` - Automatically updates `updated_at` on row modification

**Role Hierarchy:**
- **owner**: Full access including tenant deletion and user management
- **admin**: Manage resources (spaces, reservations, devices, API keys)
- **operator**: Create/update spaces and reservations, view all data
- **viewer**: Read-only access to spaces, reservations, sensor data

---

### 5. webhook_secrets

**Purpose:** Per-tenant HMAC-SHA256 webhook signature validation.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NOT NULL | - | Foreign key to tenants |
| `secret_key` | text | NOT NULL | - | HMAC-SHA256 secret key (base64 encoded) |
| `is_active` | boolean | NOT NULL | true | Secret enabled/disabled |
| `last_used_at` | timestamptz | NULL | - | Last successful signature validation |
| `created_at` | timestamptz | NOT NULL | now() | Creation timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
- `UNIQUE` (tenant_id, is_active) WHERE is_active = true - One active secret per tenant

**Indexes:**
- `idx_webhook_secrets_tenant` (tenant_id) WHERE is_active = true

**Purpose:**
- External webhook integrations (e.g., reservation confirmations, sensor alerts)
- Validates incoming webhooks using HMAC-SHA256 signature
- Prevents webhook spoofing and replay attacks

---

### 6. orphan_devices

**Purpose:** Auto-discovered devices with fcnt deduplication (prevents duplicate sensor readings).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NULL | - | Foreign key to tenants (null if unassigned) |
| `dev_eui` | varchar(16) | NOT NULL | - | LoRaWAN device EUI |
| `last_fcnt` | integer | NULL | - | Last frame counter (for deduplication) |
| `last_uplink_at` | timestamptz | NULL | - | Last uplink timestamp |
| `uplink_count` | integer | NOT NULL | 0 | Total uplink count |
| `created_at` | timestamptz | NOT NULL | now() | First seen timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL
- `UNIQUE` (dev_eui) - One entry per device

**Indexes:**
- `idx_orphan_devices_deveui` (dev_eui)
- `idx_orphan_devices_tenant` (tenant_id, last_uplink_at)

**Purpose:**
- Tracks devices sending uplinks but not yet registered in sensor_devices/display_devices
- Prevents duplicate sensor readings via frame counter (fcnt) tracking
- Helps identify devices needing assignment to tenants

**fcnt Deduplication Logic:**
```python
# Reject duplicate uplinks with same or lower fcnt
if uplink.fcnt <= orphan_device.last_fcnt:
    return {"status": "duplicate", "reason": "fcnt already processed"}
```

---

### Core Tables

### 7. device_types

**Purpose:** Centralized registry of device types with handler mapping, ChirpStack profile linking, and ORPHAN auto-discovery support.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `type_code` | varchar | NOT NULL | - | Unique type identifier (browan_tabs, kuando_busylight, etc.) |
| `category` | varchar | NOT NULL | - | Device category (sensor, display) |
| `name` | varchar | NOT NULL | - | Human-readable name |
| `manufacturer` | varchar | NULL | - | Device manufacturer |
| `handler_class` | varchar | NULL | - | Python handler class name for payload decoding |
| `default_config` | jsonb | NULL | '{}' | Default device configuration |
| `capabilities` | jsonb | NULL | '{}' | Device capabilities (occupancy, temperature, battery) |
| `enabled` | boolean | NULL | true | Device type enabled/disabled |
| `status` | varchar | NULL | 'confirmed' | Type status (orphan, confirmed) |
| `chirpstack_profile_name` | varchar | NULL | - | ChirpStack device profile name (for auto-discovery) |
| `chirpstack_profile_id` | uuid | NULL | - | ChirpStack device profile UUID |
| `sample_payload` | jsonb | NULL | - | Sample decoded payload |
| `sample_raw_payload` | jsonb | NULL | - | Sample raw payload for testing |
| `confirmed_at` | timestamptz | NULL | - | When type was confirmed from orphan |
| `confirmed_by` | varchar | NULL | - | Who confirmed the type |
| `notes` | text | NULL | - | Additional notes |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (type_code) - One registry entry per type
- `CHECK` (category IN ('sensor', 'display'))
- `CHECK` (status IN ('orphan', 'confirmed'))

**Indexes:**
- `idx_device_types_type_code` (type_code, enabled) WHERE enabled = TRUE
- `idx_device_types_status` (status, created_at)
- `idx_device_types_chirpstack_profile` (chirpstack_profile_name) WHERE chirpstack_profile_name IS NOT NULL

**Triggers:**
- `update_device_types_updated_at` - Automatically updates `updated_at` on row modification

**Purpose:**
This table enables:
1. **Centralized handler mapping** - Python code looks up handler_class by device type
2. **ORPHAN auto-discovery** - System creates orphan device_types when unknown devices send uplinks
3. **ChirpStack profile linking** - Maps ChirpStack device profiles to internal type codes
4. **Device lifecycle** - Track confirmed vs orphan types awaiting classification

**Example Data:**
```json
{
  "type_code": "browan_tbms100_motion",
  "category": "sensor",
  "name": "Browan TBMS100 TABS",
  "manufacturer": "Browan Communications",
  "handler_class": "BrowanTabsHandler",
  "chirpstack_profile_name": "Browan_TBMS100_1_0_3",
  "chirpstack_profile_id": "7a3f2c4e-5b6d-4e8a-9c1f-3d2e4b5a6c7d",
  "status": "confirmed",
  "capabilities": {"occupancy": true, "temperature": true, "battery": true}
}
```

---

### 2. sensor_devices

**Purpose:** Device registry for occupancy sensors with metadata, capabilities, and configuration.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `dev_eui` | varchar(16) | NOT NULL | - | LoRaWAN device EUI (unique) |
| `device_type` | varchar(50) | NOT NULL | - | Device type (browan_tabs, dragino, etc.) |
| `device_type_id` | uuid | NULL | - | FK to device_types (centralized type registry) |
| `device_model` | varchar(100) | NULL | - | Manufacturer's model name |
| `manufacturer` | varchar(100) | NULL | - | Device manufacturer |
| `payload_decoder` | varchar(100) | NULL | - | Handler class name for payload parsing |
| `capabilities` | jsonb | NULL | '{}' | Device capabilities (occupancy, temperature, battery) |
| `status` | varchar(30) | NULL | 'orphan' | Device lifecycle status (orphan, active, inactive, decommissioned) |
| `enabled` | boolean | NULL | true | Device enabled/disabled |
| `last_seen_at` | timestamptz | NULL | - | Last uplink timestamp |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (dev_eui) - One registry entry per device
- `FOREIGN KEY` (device_type_id) REFERENCES device_types(id)
- `CHECK` (status IN ('orphan', 'active', 'inactive', 'decommissioned'))

**Indexes:**
- `idx_sensor_devices_deveui` (dev_eui, enabled) WHERE enabled = TRUE
- `idx_sensor_devices_status` (status, created_at)

**Triggers:**
- `update_sensor_devices_updated_at` - Automatically updates `updated_at` on row modification

**Example Data:**
```json
{
  "dev_eui": "58a0cb0000115b4e",
  "device_type": "browan_tabs",
  "device_model": "Browan TBMS100 TABS",
  "manufacturer": "Browan Communications",
  "payload_decoder": "BrowanTabsHandler",
  "capabilities": {"occupancy": true, "temperature": true, "battery": true}
}
```

---

### 3. display_devices

**Purpose:** Device registry for display devices with per-device configuration (color codes, FPort, etc.).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `dev_eui` | varchar(16) | NOT NULL | - | LoRaWAN device EUI (unique) |
| `device_type` | varchar(50) | NOT NULL | - | Display type (kuando_busylight, led_matrix) |
| `device_type_id` | uuid | NULL | - | FK to device_types (centralized type registry) |
| `device_model` | varchar(100) | NULL | - | Manufacturer's model name |
| `manufacturer` | varchar(100) | NULL | - | Device manufacturer |
| `display_codes` | jsonb | NOT NULL | - | State → hex payload mappings |
| `fport` | integer | NULL | 1 | LoRaWAN FPort for downlinks |
| `confirmed_downlinks` | boolean | NULL | false | Request confirmed downlinks |
| `status` | varchar(30) | NULL | 'orphan' | Device lifecycle status (orphan, active, inactive, decommissioned) |
| `enabled` | boolean | NULL | true | Device enabled/disabled |
| `last_seen_at` | timestamptz | NULL | - | Last seen timestamp |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `UNIQUE` (dev_eui) - One registry entry per device
- `FOREIGN KEY` (device_type_id) REFERENCES device_types(id)
- `CHECK` (status IN ('orphan', 'active', 'inactive', 'decommissioned'))

**Indexes:**
- `idx_display_devices_deveui` (dev_eui, enabled) WHERE enabled = TRUE
- `idx_display_devices_status` (status, created_at)

**Triggers:**
- `update_display_devices_updated_at` - Automatically updates `updated_at` on row modification

**Example Data:**
```json
{
  "dev_eui": "2020203705250102",
  "device_type": "kuando_busylight",
  "device_model": "Kuando Busylight IoT Omega",
  "manufacturer": "Kuando",
  "display_codes": {
    "FREE": "0000FF6400",
    "OCCUPIED": "FF00006400",
    "RESERVED": "FF00FF6400",
    "MAINTENANCE": "FFA5006400"
  },
  "fport": 15,
  "confirmed_downlinks": false
}
```

---

### 10. spaces

**Purpose:** Core table storing parking space definitions, device associations, and current state (tenant and site scoped).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NOT NULL | - | FK to tenants (v5.3.0) |
| `site_id` | uuid | NOT NULL | - | FK to sites (v5.3.0) |
| `name` | varchar(100) | NOT NULL | - | Human-readable name |
| `code` | varchar(20) | NOT NULL | - | Space identifier (unique within tenant) |
| `building` | varchar(100) | NULL | - | Building location |
| `floor` | varchar(20) | NULL | - | Floor level |
| `zone` | varchar(50) | NULL | - | Parking zone |
| `gps_latitude` | numeric(10,8) | NULL | - | GPS latitude (-90 to 90) |
| `gps_longitude` | numeric(11,8) | NULL | - | GPS longitude (-180 to 180) |
| `sensor_device_id` | uuid | NULL | - | FK to sensor_devices |
| `display_device_id` | uuid | NULL | - | FK to display_devices |
| `sensor_eui` | varchar(16) | NULL | - | Denormalized sensor EUI (fast lookups) |
| `display_eui` | varchar(16) | NULL | - | Denormalized display EUI (fast lookups) |
| `state` | varchar(20) | NOT NULL | 'FREE' | Current state (enum) |
| `metadata` | jsonb | NULL | - | Additional JSON metadata |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |
| `deleted_at` | timestamptz | NULL | - | Soft delete timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) (v5.3.0)
- `FOREIGN KEY` (site_id) REFERENCES sites(id) (v5.3.0)
- `UNIQUE` (tenant_id, code) - Space codes unique within tenant (v5.3.0)
- `UNIQUE` (sensor_eui) - One sensor per space
- `FOREIGN KEY` (sensor_device_id) REFERENCES sensor_devices(id)
- `FOREIGN KEY` (display_device_id) REFERENCES display_devices(id)
- `CHECK valid_state` - State ∈ {FREE, OCCUPIED, RESERVED, MAINTENANCE}
- `CHECK valid_gps` - GPS coordinates within valid ranges

**Indexes:**
- `idx_spaces_tenant` (tenant_id, deleted_at) WHERE deleted_at IS NULL (v5.3.0)
- `idx_spaces_site` (site_id, deleted_at) WHERE deleted_at IS NULL (v5.3.0)
- `idx_spaces_sensor` (sensor_eui) WHERE deleted_at IS NULL
- `idx_spaces_state` (state) WHERE deleted_at IS NULL
- `idx_spaces_building` (building) WHERE deleted_at IS NULL
- `idx_spaces_location` (building, floor, zone) WHERE deleted_at IS NULL
- `idx_spaces_sensor_device` (sensor_device_id)
- `idx_spaces_display_device` (display_device_id)
- `idx_spaces_tenant_code` (tenant_id, code) UNIQUE (v5.3.0)

**Triggers:**
- `update_spaces_updated_at` - Automatically updates `updated_at` on row modification
- `spaces_sync_deveuis` - Automatically syncs denormalized sensor_eui and display_eui from device registries
- `spaces_sync_tenant_id` - Automatically syncs tenant_id from site (v5.3.0)

**Design Pattern:**
This table uses a **hybrid approach** with both foreign keys and denormalized DevEUIs:
- **Foreign keys** (`sensor_device_id`, `display_device_id`): Enable joins to device registries for metadata
- **Denormalized DevEUIs** (`sensor_eui`, `display_eui`): Enable fast uplink lookups without joins
- **Trigger-maintained sync**: `spaces_sync_deveuis` keeps DevEUI columns in sync automatically

---

### 5. actuations

**Purpose:** Complete audit trail of display update attempts with success/failure tracking and performance metrics.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `space_id` | uuid | NOT NULL | - | Foreign key to spaces |
| `trigger_type` | varchar(30) | NOT NULL | - | What triggered the update (enum) |
| `trigger_source` | varchar(100) | NULL | - | Request ID, uplink ID, etc. |
| `previous_state` | varchar(20) | NULL | - | State before transition |
| `new_state` | varchar(20) | NOT NULL | - | State after transition |
| `display_deveui` | varchar(16) | NOT NULL | - | Target display EUI |
| `display_device_id` | uuid | NULL | - | FK to display_devices |
| `display_code` | varchar(20) | NOT NULL | - | Hex payload sent |
| `fport` | integer | NOT NULL | - | LoRaWAN FPort used |
| `confirmed` | boolean | NULL | false | Requested confirmed downlink |
| `downlink_sent` | boolean | NULL | false | Successfully queued |
| `downlink_queue_id` | varchar(100) | NULL | - | ChirpStack queue ID |
| `downlink_error` | text | NULL | - | Error message if failed |
| `response_time_ms` | integer | NULL | - | Time to queue downlink (ms) |
| `retry_count` | integer | NULL | 0 | Number of retry attempts |
| `created_at` | timestamptz | NULL | now() | Actuation initiated timestamp |
| `sent_at` | timestamptz | NULL | - | Downlink queued timestamp |
| `confirmed_at` | timestamptz | NULL | - | Downlink confirmed timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (space_id) REFERENCES spaces(id)
- `FOREIGN KEY` (display_device_id) REFERENCES display_devices(id)
- `CHECK valid_trigger_type` - trigger_type ∈ {sensor_uplink, api_reservation, manual_override, system_cleanup, reservation_expired}

**Indexes:**
- `idx_actuations_space_time` (space_id, created_at DESC)
- `idx_actuations_trigger` (trigger_type, created_at DESC)
- `idx_actuations_errors` (downlink_sent, downlink_error) WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL
- `idx_actuations_display` (display_deveui, created_at DESC)

**Use Cases:**
- Operational debugging (why didn't display update?)
- Performance monitoring (response time trends)
- Success rate tracking (downlink reliability)
- Compliance auditing (complete operational history)

---

### 6. sensor_readings

**Purpose:** Time-series data from occupancy sensors and environmental metrics.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | bigint | NOT NULL | nextval() | Primary key (auto-increment) |
| `device_eui` | varchar(16) | NOT NULL | - | Sensor LoRaWAN EUI |
| `space_id` | uuid | NULL | - | Foreign key to spaces |
| `occupancy_state` | varchar(20) | NULL | - | Detected occupancy state |
| `battery` | numeric(3,2) | NULL | - | Battery level (0.00-1.00) |
| `temperature` | numeric(4,1) | NULL | - | Temperature in Celsius |
| `rssi` | integer | NULL | - | Received Signal Strength Indicator |
| `snr` | numeric(4,1) | NULL | - | Signal-to-Noise Ratio |
| `timestamp` | timestamptz | NULL | now() | Reading timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (space_id) REFERENCES spaces(id)

**Indexes:**
- `idx_sensor_readings_device_time` (device_eui, timestamp DESC)
- `idx_sensor_readings_space_time` (space_id, timestamp DESC) WHERE space_id IS NOT NULL
- `idx_sensor_readings_timestamp_brin` BRIN (timestamp) - Efficient for time-series queries

**Sequence:** `sensor_readings_id_seq` (START 1, INCREMENT 1)

---

### 7. state_changes

**Purpose:** Audit log of all parking space state transitions with full context.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | bigint | NOT NULL | nextval() | Primary key (auto-increment) |
| `space_id` | uuid | NOT NULL | - | Foreign key to spaces |
| `previous_state` | varchar(20) | NULL | - | State before transition |
| `new_state` | varchar(20) | NOT NULL | - | State after transition |
| `source` | varchar(50) | NOT NULL | - | Trigger source (sensor/manual/reservation) |
| `request_id` | varchar(50) | NULL | - | Request trace ID for debugging |
| `metadata` | jsonb | NULL | - | Additional context (JSON) |
| `timestamp` | timestamptz | NULL | now() | Transition timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (space_id) REFERENCES spaces(id)

**Indexes:**
- `idx_state_changes_space` (space_id, timestamp DESC)
- `idx_state_changes_timestamp_brin` BRIN (timestamp) - Efficient for time-series queries

**Sequence:** `state_changes_id_seq` (START 1, INCREMENT 1)

---

### 14. reservations

**Purpose:** Parking space reservation management with tenant isolation, overlap prevention, and idempotency guarantees (v5.3.0).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NOT NULL | - | FK to tenants (v5.3.0) |
| `space_id` | uuid | NOT NULL | - | Foreign key to spaces |
| `start_time` | timestamptz | NOT NULL | - | Reservation start time |
| `end_time` | timestamptz | NOT NULL | - | Reservation end time |
| `user_email` | varchar(255) | NULL | - | User email address |
| `user_phone` | varchar(20) | NULL | - | User phone number |
| `status` | varchar(20) | NOT NULL | 'pending' | Reservation status (enum) (v5.3.0) |
| `request_id` | uuid | NULL | - | Idempotency key (v5.3.0) |
| `metadata` | jsonb | NULL | - | Additional booking details |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `updated_at` | timestamptz | NULL | now() | Last update timestamp |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) (v5.3.0)
- `FOREIGN KEY` (space_id) REFERENCES spaces(id)
- `CHECK valid_times` - end_time > start_time
- `CHECK valid_duration` - (end_time - start_time) ≤ 24 hours
- `CHECK valid_status` - Status ∈ {pending, confirmed, expired, cancelled} (v5.3.0)
- `EXCLUDE CONSTRAINT` - Prevents overlapping reservations using btree_gist (v5.3.0):
  ```sql
  EXCLUDE USING gist (
    space_id WITH =,
    tstzrange(start_time, end_time) WITH &&
  ) WHERE (status IN ('pending', 'confirmed'))
  ```

**Indexes:**
- `idx_reservations_tenant` (tenant_id, status) (v5.3.0)
- `idx_reservations_space` (space_id)
- `idx_reservations_status` (status) WHERE status IN ('pending', 'confirmed') (v5.3.0)
- `idx_reservations_time` (start_time, end_time) WHERE status IN ('pending', 'confirmed') (v5.3.0)
- `idx_reservations_request_id` (request_id) WHERE request_id IS NOT NULL (v5.3.0)

**Triggers:**
- `update_reservations_updated_at` - Automatically updates `updated_at` on row modification
- `reservations_sync_tenant_id` - Automatically syncs tenant_id from space (v5.3.0)

**Key Features (v5.3.0):**

**1. Database-Level Overlap Prevention:**
The EXCLUDE constraint guarantees no two active reservations (`pending` or `confirmed`) can overlap for the same space, even under high concurrency. This prevents double-booking at the database level.

**2. Idempotency:**
The `request_id` field enables idempotent reservation creation. If a client retries the same request with the same `request_id`, the API returns the existing reservation instead of creating a duplicate.

**3. Updated Status Values:**
- `pending` - Awaiting payment or approval
- `confirmed` - Active reservation
- `expired` - Past end_time (auto-expired by background job)
- `cancelled` - Cancelled by user or admin

**4. Automatic Expiry:**
A background job runs every 60 seconds to mark reservations as `expired` after their `end_time` passes.

**Example Query - Check Overlap:**
```sql
SELECT * FROM reservations
WHERE space_id = 'space-uuid'
  AND status IN ('pending', 'confirmed')
  AND tstzrange(start_time, end_time) && tstzrange('2025-10-21 10:00', '2025-10-21 12:00');
```

---

### 15. api_keys

**Purpose:** API authentication with tenant scoping and scope-based access control (v5.3.0).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | uuid | NOT NULL | gen_random_uuid() | Primary key |
| `tenant_id` | uuid | NOT NULL | - | FK to tenants (v5.3.0) |
| `key_hash` | varchar(255) | NOT NULL | - | SHA-256 hash of API key |
| `key_name` | varchar(100) | NULL | - | Friendly name for key |
| `scopes` | text[] | NULL | '{read}' | Scope array (read, write, manage, admin) (v5.3.0) |
| `last_used_at` | timestamptz | NULL | - | Last successful authentication |
| `is_active` | boolean | NULL | true | Key enabled/disabled |
| `created_at` | timestamptz | NULL | now() | Creation timestamp |
| `is_admin` | boolean | NULL | false | Admin privileges flag (legacy) |

**Constraints:**
- `PRIMARY KEY` (id)
- `FOREIGN KEY` (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE (v5.3.0)
- `UNIQUE` (key_hash) - Prevent duplicate keys

**Indexes:**
- `idx_api_keys_tenant` (tenant_id, is_active) WHERE is_active = true (v5.3.0)
- `idx_api_keys_active` (is_active) WHERE is_active = true
- `idx_api_keys_admin` (is_admin) WHERE is_active = true AND is_admin = true

**Scope Enforcement (v5.3.0):**

API key scopes implement least-privilege access control:

| Scope | Allowed Operations |
|-------|-------------------|
| `read` | GET requests only (view spaces, reservations, sensor data) |
| `write` | GET + POST/PATCH (create/update spaces and reservations) |
| `manage` | GET + POST/PATCH/DELETE (full resource management) |
| `admin` | All operations + user management, API key creation, tenant settings |

**Example:**
```json
{
  "tenant_id": "tenant-uuid",
  "key_name": "Production API Key",
  "scopes": ["read", "write"],
  "is_active": true
}
```

**Scope Validation Logic:**
```python
# API endpoint requires 'write' scope
if 'write' not in api_key.scopes and 'manage' not in api_key.scopes and 'admin' not in api_key.scopes:
    raise HTTPException(status_code=403, detail="Insufficient permissions")
```

---

## Database Views

The schema includes 7 views designed for multi-tenant queries, device management, ORPHAN device discovery, and operational monitoring.

### 1. v_spaces (Materialized View)

**Purpose:** Pre-joined spaces with tenant and site data for high-performance queries (v5.3.0).

**Type:** Materialized View (requires periodic REFRESH)

**Query Pattern:**
```sql
SELECT * FROM v_spaces
WHERE tenant_slug = 'acme'
  AND state = 'FREE'
ORDER BY code;
```

**Columns:**
- `space_id` (uuid) - Space primary key
- `tenant_id` (uuid) - Tenant FK
- `tenant_name` (varchar) - Tenant name
- `tenant_slug` (varchar) - Tenant URL slug
- `site_id` (uuid) - Site FK
- `site_name` (varchar) - Site name
- `site_timezone` (varchar) - Site timezone
- `code` (varchar) - Space code
- `name` (varchar) - Space name
- `building` (varchar) - Building location
- `floor` (varchar) - Floor level
- `zone` (varchar) - Parking zone
- `state` (varchar) - Current state (FREE, OCCUPIED, RESERVED, MAINTENANCE)
- `sensor_eui` (varchar) - Sensor device EUI
- `display_eui` (varchar) - Display device EUI
- `created_at` (timestamptz) - Creation timestamp
- `updated_at` (timestamptz) - Last update timestamp

**SQL Definition:**
```sql
CREATE MATERIALIZED VIEW v_spaces AS
SELECT
  s.id AS space_id,
  s.tenant_id,
  t.name AS tenant_name,
  t.slug AS tenant_slug,
  s.site_id,
  si.name AS site_name,
  si.timezone AS site_timezone,
  s.code,
  s.name,
  s.building,
  s.floor,
  s.zone,
  s.state,
  s.sensor_eui,
  s.display_eui,
  s.created_at,
  s.updated_at
FROM spaces s
INNER JOIN tenants t ON s.tenant_id = t.id
INNER JOIN sites si ON s.site_id = si.id
WHERE s.deleted_at IS NULL;

CREATE UNIQUE INDEX idx_v_spaces_space_id ON v_spaces(space_id);
CREATE INDEX idx_v_spaces_tenant_slug ON v_spaces(tenant_slug, state);
CREATE INDEX idx_v_spaces_site ON v_spaces(site_id, state);
```

**Refresh Strategy:**
```sql
-- Refresh on demand (when spaces/tenants/sites change)
REFRESH MATERIALIZED VIEW CONCURRENTLY v_spaces;
```

**Use Cases:**
- Fast tenant-scoped space listing without joins
- Dashboard queries showing spaces by tenant
- Public API endpoints returning space availability
- Analytics queries aggregating by tenant/site

**Performance Benefit:**
- **Before (3 JOINs):** ~15ms for 1000 spaces
- **After (Materialized View):** ~2ms for 1000 spaces
- **Improvement:** 7.5x faster

---

### 2. unassigned_sensors

**Purpose:** Lists all sensor devices with `status='orphan'` that are NOT linked to any active space.

**Query Pattern:**
```sql
SELECT * FROM unassigned_sensors
ORDER BY last_seen_at DESC;
```

**Columns:**
- `id` (uuid) - Sensor device ID
- `dev_eui` (varchar) - Device EUI
- `device_model` (varchar) - Device model name
- `status` (varchar) - Device status (always 'orphan' for this view)
- `type_code` (varchar) - Device type code from device_types
- `device_type_name` (varchar) - Human-readable type name
- `category` (varchar) - Device category ('sensor')
- `type_status` (varchar) - Device type status (orphan/confirmed)
- `last_seen_at` (timestamptz) - Last uplink timestamp
- `created_at` (timestamptz) - Device creation timestamp
- `reading_count` (bigint) - Total number of sensor_readings for this device

**Use Cases:**
- Find new sensors that need space assignment
- Identify sensors removed from spaces
- Monitor sensor registration queue

**Important Note:**
A device can appear in `unassigned_sensors` even if it's actively used as a display. See "Dual-Role Devices" section for explanation.

---

### 2. unassigned_displays

**Purpose:** Lists all display devices with `status='orphan'` that are NOT linked to any active space.

**Query Pattern:**
```sql
SELECT * FROM unassigned_displays
ORDER BY last_seen_at DESC;
```

**Columns:**
- `id` (uuid) - Display device ID
- `dev_eui` (varchar) - Device EUI
- `device_model` (varchar) - Device model name
- `status` (varchar) - Device status (always 'orphan' for this view)
- `type_code` (varchar) - Device type code from device_types
- `device_type_name` (varchar) - Human-readable type name
- `category` (varchar) - Device category ('display')
- `type_status` (varchar) - Device type status (orphan/confirmed)
- `last_seen_at` (timestamptz) - Last seen timestamp
- `created_at` (timestamptz) - Device creation timestamp

**Use Cases:**
- Find new displays that need space assignment
- Identify displays removed from spaces
- Monitor display registration queue

---

### 3. all_unassigned_devices

**Purpose:** Union of `unassigned_sensors` and `unassigned_displays` - all orphan devices not assigned to spaces.

**Query Pattern:**
```sql
SELECT * FROM all_unassigned_devices
ORDER BY last_seen_at DESC;
```

**Columns:**
- `device_category` (text) - 'sensor' or 'display'
- `id` (uuid) - Device ID
- `dev_eui` (varchar) - Device EUI
- `device_model` (varchar) - Device model name
- `type_code` (varchar) - Device type code
- `device_type_name` (varchar) - Human-readable type name
- `type_status` (varchar) - Device type status
- `last_seen_at` (timestamptz) - Last seen timestamp
- `created_at` (timestamptz) - Device creation timestamp

**Use Cases:**
- Unified view of all unassigned devices
- Frontend device assignment UI
- Monitoring new device registrations

**SQL Definition:**
```sql
CREATE VIEW all_unassigned_devices AS
SELECT 'sensor'::text AS device_category, *
FROM unassigned_sensors
UNION ALL
SELECT 'display'::text AS device_category, *
FROM unassigned_displays
ORDER BY last_seen_at DESC NULLS LAST;
```

---

### 4. orphan_devices

**Purpose:** All devices (sensor + display) with `status='orphan'`, enriched with device type metadata.

**Query Pattern:**
```sql
SELECT * FROM orphan_devices
WHERE chirpstack_profile_name IS NOT NULL
ORDER BY created_at DESC;
```

**Columns:**
- `device_category` (text) - 'sensor' or 'display'
- `id` (uuid) - Device ID
- `dev_eui` (varchar) - Device EUI
- `device_model` (varchar) - Device model name
- `status` (varchar) - Device status (always 'orphan')
- `type_code` (varchar) - Device type code
- `type_name` (varchar) - Device type name
- `chirpstack_profile_name` (varchar) - ChirpStack device profile
- `last_seen_at` (timestamptz) - Last seen timestamp
- `created_at` (timestamptz) - Device creation timestamp

**Difference from unassigned_sensors/displays:**
- `orphan_devices` shows ALL orphan devices (even if assigned to spaces - rare edge case)
- `unassigned_sensors/displays` shows only orphan devices NOT linked to spaces
- Includes ChirpStack profile name for troubleshooting

**Use Cases:**
- ORPHAN device auto-discovery monitoring
- Troubleshoot ChirpStack profile mapping
- Identify devices needing type confirmation

---

### 5. orphan_device_types

**Purpose:** Device types with `status='orphan'` awaiting confirmation, with device counts and sample EUIs.

**Query Pattern:**
```sql
SELECT * FROM orphan_device_types
ORDER BY device_count DESC;
```

**Columns:**
- `id` (uuid) - Device type ID
- `type_code` (varchar) - Type code
- `name` (varchar) - Type name
- `category` (varchar) - 'sensor' or 'display'
- `chirpstack_profile_name` (varchar) - ChirpStack profile name
- `sample_payload` (jsonb) - Sample decoded payload
- `created_at` (timestamptz) - Type creation timestamp
- `device_count` (bigint) - Number of devices using this type
- `sample_dev_euis` (json) - Array of up to 5 sample device EUIs

**Use Cases:**
- Identify orphan types needing confirmation
- See how many devices are blocked by unconfirmed types
- Quick access to sample EUIs for testing

**Example Output:**
```json
{
  "type_code": "orphan_unknown_profile_abc123",
  "name": "ORPHAN: Unknown Device Type",
  "category": "sensor",
  "chirpstack_profile_name": "Custom_Sensor_Profile",
  "device_count": 12,
  "sample_dev_euis": ["58a0cb0000112233", "58a0cb0000445566", "58a0cb0000778899"]
}
```

---

### 6. inconsistent_devices

**Purpose:** Detects device status inconsistencies (devices marked 'active' but not assigned, or 'orphan' but assigned).

**Query Pattern:**
```sql
SELECT * FROM inconsistent_devices;
```

**Columns:**
- `device_category` (text) - 'sensor' or 'display'
- `id` (uuid) - Device ID
- `dev_eui` (varchar) - Device EUI
- `status` (varchar) - Current device status
- `inconsistency` (text) - Type of inconsistency
  - `ACTIVE_BUT_UNASSIGNED` - Device marked active but not in any space
  - `ORPHAN_BUT_ASSIGNED` - Device marked orphan but linked to space
- `issue` (text) - Human-readable issue description

**Use Cases:**
- Data quality monitoring
- Identify status update bugs
- Periodic cleanup scripts

**Example Inconsistency:**
```
device_category: sensor
dev_eui: 58a0cb0000115b4e
status: active
inconsistency: ACTIVE_BUT_UNASSIGNED
issue: Device marked active but not assigned to any space
```

**Resolution:**
- For `ACTIVE_BUT_UNASSIGNED`: Either assign to space or change status to 'orphan'
- For `ORPHAN_BUT_ASSIGNED`: Change status to 'active' (device is actually in use)

---

## Architectural Patterns

### Dual-Role Devices (Kuando Busylight)

**Important:** Some devices can exist in BOTH `sensor_devices` AND `display_devices` tables simultaneously.

**Example: Kuando Busylight IoT Omega**
- **As Display** (primary role): Receives downlink commands to change RGB color (FPort 15)
- **As Sensor** (secondary role): Sends uplink status messages with current RGB state (FPort 6)

**How It Works:**

1. **Display Registration** (manual or via ORPHAN discovery):
   - Added to `display_devices` with display_codes configuration
   - Linked to space via `spaces.display_device_id` and `spaces.display_eui`

2. **Sensor Auto-Registration** (automatic on first uplink):
   - System receives RGB status uplink from same DevEUI
   - Creates entry in `sensor_devices` with status='orphan'
   - Device appears in `unassigned_sensors` view

3. **Space Assignment**:
   - Space links to display via `display_eui` (for sending color commands)
   - Space may or may not link to sensor via `sensor_eui` (for reading status)
   - Typically spaces use `display_eui` only for Kuando devices

**Why This Appears Confusing:**

When querying `all_unassigned_devices`, you may see devices like:
```
dev_eui: 2020203907290902
device_category: sensor
status: orphan
device_model: Brighter Kuando 290902
```

Even though this device is actively used as a display in the "WINDOW" space!

**Explanation:**
- Device IS assigned as a **display** (via `spaces.display_eui`)
- Device is NOT assigned as a **sensor** (no `spaces.sensor_eui` link)
- Therefore it correctly appears as an "unassigned sensor"

**When to Link Both:**
- **Display only** (typical): Space uses downlinks to control color, ignores uplinks
- **Display + Sensor** (advanced): Space uses downlinks for control AND uplinks for verification/reconciliation
- Current system: Reconciliation uses Redis cache of Kuando uplinks without requiring sensor_eui link

**Database Query Examples:**

Find Kuando devices acting as both sensor and display:
```sql
SELECT
    sd.dev_eui,
    sd.device_model as sensor_model,
    dd.device_model as display_model,
    s.code as assigned_space,
    s.display_eui IS NOT NULL as linked_as_display,
    s.sensor_eui IS NOT NULL as linked_as_sensor
FROM sensor_devices sd
INNER JOIN display_devices dd ON sd.dev_eui = dd.dev_eui
LEFT JOIN spaces s ON (s.display_eui = dd.dev_eui OR s.sensor_eui = sd.dev_eui)
    AND s.deleted_at IS NULL
WHERE sd.dev_eui LIKE '202020%'  -- Kuando prefix
ORDER BY s.code;
```

---

## Custom Functions & Triggers

### update_updated_at()

**Type:** Trigger Function
**Language:** PL/pgSQL

```sql
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$
```

**Usage:** Automatically updates the `updated_at` timestamp on row updates.

**Applied to:**
- `sensor_devices.updated_at`
- `display_devices.updated_at`
- `spaces.updated_at`
- `reservations.updated_at`

---

### sync_device_deveuis()

**Type:** Trigger Function
**Language:** PL/pgSQL

```sql
CREATE OR REPLACE FUNCTION sync_device_deveuis()
RETURNS TRIGGER AS $$
BEGIN
  -- Sync sensor DevEUI when sensor_device_id is set/changed
  IF NEW.sensor_device_id IS NOT NULL THEN
    NEW.sensor_eui := (SELECT dev_eui FROM sensor_devices WHERE id = NEW.sensor_device_id);
  ELSIF NEW.sensor_device_id IS NULL THEN
    NEW.sensor_eui := NULL;
  END IF;

  -- Sync display DevEUI when display_device_id is set/changed
  IF NEW.display_device_id IS NOT NULL THEN
    NEW.display_eui := (SELECT dev_eui FROM display_devices WHERE id = NEW.display_device_id);
  ELSIF NEW.display_device_id IS NULL THEN
    NEW.display_eui := NULL;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Usage:** Automatically syncs denormalized `sensor_eui` and `display_eui` columns in `spaces` table when device FKs are updated.

**Applied to:**
- `spaces` (BEFORE INSERT OR UPDATE)

**Why This Pattern:**
- **Foreign keys** enable joins to device registries for rich metadata
- **Denormalized DevEUIs** enable fast uplink lookups without joins (`WHERE sensor_eui = 'xxx'`)
- **Trigger maintains consistency** automatically - no manual sync needed

---

## Enums & Valid Values

### Space State
```
FREE         - Available for parking
OCCUPIED     - Currently in use
RESERVED     - Reserved for future use
MAINTENANCE  - Under maintenance, unavailable
```

### Reservation Status
```
active      - Currently active reservation
completed   - Reservation fulfilled
cancelled   - Cancelled by user
no_show     - User did not arrive
```

### State Change Sources
```
sensor      - Triggered by IoT sensor uplink
manual      - Manual override via API/UI
reservation - Triggered by reservation system
system      - System-initiated change
```

### Actuation Trigger Types
```
sensor_uplink      - Display update triggered by sensor uplink
api_reservation    - Display update triggered by reservation API
manual_override    - Manual display update via API/UI
system_cleanup     - System maintenance operation
reservation_expired - Reservation time expired
```

---

## Relationships

### Foreign Keys

```sql
-- sensor_devices → device_types
ALTER TABLE sensor_devices
  ADD CONSTRAINT fk_device_type
  FOREIGN KEY (device_type_id) REFERENCES device_types(id);

-- display_devices → device_types
ALTER TABLE display_devices
  ADD CONSTRAINT fk_device_type
  FOREIGN KEY (device_type_id) REFERENCES device_types(id);

-- spaces → sensor_devices
ALTER TABLE spaces
  ADD CONSTRAINT fk_sensor_device
  FOREIGN KEY (sensor_device_id) REFERENCES sensor_devices(id);

-- spaces → display_devices
ALTER TABLE spaces
  ADD CONSTRAINT fk_display_device
  FOREIGN KEY (display_device_id) REFERENCES display_devices(id);

-- sensor_readings → spaces
ALTER TABLE sensor_readings
  ADD CONSTRAINT fk_space
  FOREIGN KEY (space_id) REFERENCES spaces(id);

-- state_changes → spaces
ALTER TABLE state_changes
  ADD CONSTRAINT fk_space
  FOREIGN KEY (space_id) REFERENCES spaces(id);

-- reservations → spaces
ALTER TABLE reservations
  ADD CONSTRAINT fk_space
  FOREIGN KEY (space_id) REFERENCES spaces(id);

-- actuations → spaces
ALTER TABLE actuations
  ADD CONSTRAINT fk_space
  FOREIGN KEY (space_id) REFERENCES spaces(id);

-- actuations → display_devices
ALTER TABLE actuations
  ADD CONSTRAINT fk_display_device
  FOREIGN KEY (display_device_id) REFERENCES display_devices(id);
```

### Relationship Cardinality

- **device_types ↔ sensor_devices:** 1:N (one device type can have many sensors)
- **device_types ↔ display_devices:** 1:N (one device type can have many displays)
- **sensor_devices ↔ spaces:** 1:N (one sensor can be assigned to multiple spaces over time)
- **display_devices ↔ spaces:** 1:N (one display can be assigned to multiple spaces over time)
- **spaces ↔ sensor_readings:** 1:N (one space has many readings)
- **spaces ↔ state_changes:** 1:N (one space has many state changes)
- **spaces ↔ reservations:** 1:N (one space has many reservations)
- **spaces ↔ actuations:** 1:N (one space has many display updates)
- **display_devices ↔ actuations:** 1:N (one display has many actuation attempts)

**Special Case - Dual-Role Devices:**
- **sensor_devices ↔ display_devices:** N:N via shared dev_eui (Kuando devices exist in both tables)
- Same physical device can be registered as both sensor and display
- Spaces link separately via sensor_device_id/display_device_id (or via denormalized EUIs)

---

## Indexing Strategy

### BRIN Indexes
Used for time-series data on large tables:
- `sensor_readings.timestamp`
- `state_changes.timestamp`

**Benefit:** Efficient range queries on timestamp columns with minimal storage overhead.

### Partial Indexes
Used to index only relevant rows:
- `idx_spaces_sensor WHERE deleted_at IS NULL`
- `idx_sensor_devices_deveui WHERE enabled = TRUE`
- `idx_display_devices_deveui WHERE enabled = TRUE`
- `idx_reservations_status WHERE status = 'active'`
- `idx_actuations_errors WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL`

**Benefit:** Smaller index size, faster lookups on filtered data.

### Composite Indexes
Used for common query patterns:
- `(building, floor, zone)` - Location-based queries
- `(space_id, timestamp DESC)` - Space history queries
- `(device_eui, timestamp DESC)` - Device history queries
- `(start_time, end_time)` - Reservation overlap checks
- `(display_deveui, created_at DESC)` - Display actuation history

---

## Data Retention

### Time-Series Data
- **sensor_readings:** Retained indefinitely (consider partitioning for >1M rows)
- **state_changes:** Retained indefinitely for audit trail
- **actuations:** Retained indefinitely for operational audit trail

### Device Registries
- **sensor_devices:** Use `enabled = FALSE` for decommissioned devices (soft disable)
- **display_devices:** Use `enabled = FALSE` for decommissioned devices (soft disable)

### Soft Deletes
- **spaces:** Uses `deleted_at` for soft deletion (can be restored)

---

## Performance Considerations

### Query Optimization
1. **Time-series queries:** Use BRIN indexes on timestamp columns
2. **Active data filtering:** Use partial indexes (WHERE deleted_at IS NULL, WHERE enabled = TRUE)
3. **Space lookups:** Use composite indexes for common patterns
4. **Device lookups:** Fast uplink processing uses denormalized DevEUI columns (no joins needed)

### Partitioning Recommendations
When `sensor_readings` exceeds 10M rows:
```sql
-- Partition by timestamp (monthly)
CREATE TABLE sensor_readings_y2025m01
  PARTITION OF sensor_readings
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

When `actuations` exceeds 5M rows:
```sql
-- Partition by timestamp (monthly)
CREATE TABLE actuations_y2025m01
  PARTITION OF actuations
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

---

## Migration History

Migrations are managed manually. See `README.md` for migration procedures.

**Schema Evolution:**
- **v2.0.0** (2025-10-16): Initial V2 schema with basic tables
- **v2.1.0** (2025-10-17): Added device registries (sensor_devices, display_devices) and actuation audit trail
- **v5.0.0** (2025-10-17): Database renamed from parking_v2 to parking_v5
- **v5.1.0** (2025-10-17): Added device_types table with centralized type registry
- **v5.2.0** (2025-10-17): Added ORPHAN device discovery pattern (status, ChirpStack profile mapping)
- **v5.3.0** (2025-10-17): Added 6 database views (unassigned_sensors, unassigned_displays, all_unassigned_devices, orphan_devices, orphan_device_types, inconsistent_devices)
- **v5.4.0** (2025-10-17): Documentation update - Added complete device_types definition, dual-role device architecture pattern, comprehensive view documentation
- **v5.5.0** (2025-10-20): **Multi-Tenancy with RBAC**
  - **New tables:** tenants, sites, users, user_memberships, webhook_secrets, orphan_devices (with fcnt tracking)
  - **Updated tables:**
    - `api_keys`: Added tenant_id (FK), scopes (text[])
    - `spaces`: Added tenant_id (FK), site_id (FK), unique constraint (tenant_id, code)
    - `reservations`: Added tenant_id (FK), request_id (idempotency), status values changed to (pending, confirmed, expired, cancelled), EXCLUDE constraint for overlap prevention
  - **New triggers:**
    - `spaces_sync_tenant_id` - Syncs tenant_id from site
    - `reservations_sync_tenant_id` - Syncs tenant_id from space
    - `tenant_id_validation` - Validates tenant_id consistency across FK relationships
  - **New materialized view:** `v_spaces` - Pre-joined spaces with tenant/site data for performance
  - **Database extensions:** Added btree_gist for EXCLUDE constraint support
  - **Migrations:** 002_multi_tenancy_rbac.sql, 003_multi_tenancy_hardening.sql, 004_reservations_and_webhook_hardening.sql, 005_reservation_statuses.sql

**Current Schema Version:** v5.5.0
**Last Updated:** 2025-10-20

---

## Sample Queries

### Get current space occupancy
```sql
SELECT
    building,
    COUNT(*) FILTER (WHERE state = 'FREE') as free_spaces,
    COUNT(*) FILTER (WHERE state = 'OCCUPIED') as occupied_spaces,
    COUNT(*) as total_spaces
FROM spaces
WHERE deleted_at IS NULL
GROUP BY building;
```

### Get space with full device metadata
```sql
SELECT
  s.name,
  s.code,
  s.state,
  -- Sensor info
  sd.device_type as sensor_type,
  sd.device_model as sensor_model,
  sd.capabilities as sensor_capabilities,
  -- Display info
  dd.device_type as display_type,
  dd.device_model as display_model,
  dd.fport as display_fport,
  dd.display_codes->>'FREE' as free_color,
  dd.display_codes->>'OCCUPIED' as occupied_color
FROM spaces s
LEFT JOIN sensor_devices sd ON s.sensor_device_id = sd.id
LEFT JOIN display_devices dd ON s.display_device_id = dd.id
WHERE s.code = 'A1-003';
```

### Find all spaces with Browan TABS sensors
```sql
SELECT
  s.name,
  s.code,
  sd.dev_eui,
  sd.device_model,
  sd.last_seen_at
FROM spaces s
JOIN sensor_devices sd ON s.sensor_device_id = sd.id
WHERE sd.device_type = 'browan_tabs'
  AND s.deleted_at IS NULL
  AND sd.enabled = TRUE;
```

### Get actuation history for a space
```sql
SELECT
  a.created_at,
  a.trigger_type,
  a.previous_state || ' → ' || a.new_state as transition,
  a.display_code as payload_sent,
  a.fport,
  a.downlink_sent,
  a.downlink_error,
  a.response_time_ms,
  a.downlink_queue_id
FROM actuations a
JOIN spaces s ON a.space_id = s.id
WHERE s.code = 'A1-003'
ORDER BY a.created_at DESC
LIMIT 50;
```

### Get display update success rate by device
```sql
SELECT
  dd.dev_eui,
  dd.device_model,
  COUNT(*) as total_attempts,
  COUNT(*) FILTER (WHERE downlink_sent = TRUE) as successful,
  COUNT(*) FILTER (WHERE downlink_sent = FALSE) as failed,
  ROUND(100.0 * COUNT(*) FILTER (WHERE downlink_sent = TRUE) / COUNT(*), 2) as success_rate,
  AVG(response_time_ms) FILTER (WHERE downlink_sent = TRUE) as avg_response_ms
FROM actuations a
JOIN display_devices dd ON a.display_device_id = dd.id
WHERE a.created_at > NOW() - INTERVAL '7 days'
GROUP BY dd.dev_eui, dd.device_model
ORDER BY total_attempts DESC;
```

### Find spaces with recent sensor activity
```sql
SELECT
    s.name,
    s.code,
    sr.timestamp as last_reading,
    sr.occupancy_state,
    sd.device_type,
    sd.device_model
FROM spaces s
LEFT JOIN sensor_devices sd ON s.sensor_device_id = sd.id
LEFT JOIN LATERAL (
    SELECT * FROM sensor_readings
    WHERE device_eui = s.sensor_eui
    ORDER BY timestamp DESC
    LIMIT 1
) sr ON true
WHERE s.deleted_at IS NULL
ORDER BY sr.timestamp DESC NULLS LAST;
```

### Get state change history for a space
```sql
SELECT
    sc.timestamp,
    sc.previous_state || ' → ' || sc.new_state as transition,
    sc.source,
    sc.request_id
FROM state_changes sc
JOIN spaces s ON sc.space_id = s.id
WHERE s.code = 'A1-003'
ORDER BY sc.timestamp DESC
LIMIT 50;
```

### Check for reservation conflicts
```sql
SELECT *
FROM reservations
WHERE space_id = '...'
  AND status = 'active'
  AND (
    (start_time <= '2025-10-17 10:00' AND end_time > '2025-10-17 10:00') OR
    (start_time < '2025-10-17 12:00' AND end_time >= '2025-10-17 12:00') OR
    (start_time >= '2025-10-17 10:00' AND end_time <= '2025-10-17 12:00')
  );
```

### Update display color codes for a device
```sql
-- Change color scheme for a specific display
UPDATE display_devices
SET display_codes = '{
  "FREE": "00FFFF6400",
  "OCCUPIED": "FF00006400",
  "RESERVED": "FFFF006400",
  "MAINTENANCE": "FFA5006400"
}'::jsonb
WHERE dev_eui = '2020203705250102';
```

### Swap sensor between spaces
```sql
-- Move sensor from one space to another
-- The sensor_eui column will auto-update via trigger!
UPDATE spaces
SET sensor_device_id = (
  SELECT id FROM sensor_devices WHERE dev_eui = '58a0cb0000115b4e'
)
WHERE code = 'A1-004';
```

### Find dual-role devices (Kuando)
```sql
-- Find devices that exist in both sensor_devices and display_devices
SELECT
    sd.dev_eui,
    sd.device_model as sensor_model,
    sd.status as sensor_status,
    dd.device_model as display_model,
    dd.status as display_status,
    s.code as space_code,
    s.display_eui IS NOT NULL as used_as_display,
    s.sensor_eui IS NOT NULL as used_as_sensor
FROM sensor_devices sd
INNER JOIN display_devices dd ON sd.dev_eui = dd.dev_eui
LEFT JOIN spaces s ON (s.display_eui = dd.dev_eui OR s.sensor_eui = sd.dev_eui)
    AND s.deleted_at IS NULL
WHERE sd.dev_eui LIKE '202020%'  -- Kuando prefix
ORDER BY s.code NULLS LAST;
```

### Query all unassigned devices
```sql
-- Use the all_unassigned_devices view for a unified list
SELECT
    device_category,
    dev_eui,
    device_model,
    type_code,
    device_type_name,
    last_seen_at
FROM all_unassigned_devices
WHERE last_seen_at > NOW() - INTERVAL '7 days'  -- Active in last week
ORDER BY last_seen_at DESC;
```

### Find orphan device types needing confirmation
```sql
-- Device types auto-created during ORPHAN discovery
SELECT
    type_code,
    name,
    category,
    chirpstack_profile_name,
    device_count,
    sample_dev_euis
FROM orphan_device_types
WHERE device_count > 0
ORDER BY device_count DESC;
```

---

## Backup & Recovery

### Recommended Backup Strategy
```bash
# Full database backup
pg_dump -U parking_user -d parking_v5 -F c -f parking_v5_$(date +%Y%m%d).dump

# Schema-only backup
pg_dump -U parking_user -d parking_v5 -s > schema.sql

# Data-only backup
pg_dump -U parking_user -d parking_v5 -a > data.sql

# Backup specific tables
pg_dump -U parking_user -d parking_v5 -t sensor_devices -t display_devices > device_registries.sql
```

### Point-in-Time Recovery
Requires WAL archiving enabled in PostgreSQL configuration.

---

## Architecture Benefits

### Device Registry Pattern

**Benefits over inline device metadata:**
1. ✅ Device inventory independent of space assignments
2. ✅ Device lifecycle tracking (install → test → active → decommissioned)
3. ✅ Easy device swaps (update FK, history preserved)
4. ✅ Per-device configuration (FPort, display codes) - no code changes needed
5. ✅ Support for device rotation and maintenance workflows

**Hybrid FK + Denormalized DevEUI approach:**
1. ✅ Fast uplink processing (no joins needed for device lookup)
2. ✅ Rich metadata queries (join to device registries when needed)
3. ✅ Referential integrity via foreign keys
4. ✅ Automatic consistency via trigger

### Actuation Audit Trail

**Benefits:**
1. ✅ Complete operational history (every display update attempt)
2. ✅ Success/failure tracking (identify problematic displays)
3. ✅ Performance monitoring (response time trends)
4. ✅ Debugging support (trace trigger source, payload sent, errors)
5. ✅ Compliance (full audit trail for regulatory requirements)

---

**For implementation details, see:**
- `/src/models.py` - Pydantic models
- `/src/database.py` - Database connection pool
- `/src/state_manager.py` - State management and actuation logging
- `/docs/DEVICE_TYPES_ARCHITECTURE.md` - Device types registry architecture
- `/docs/V2_SCHEMA_IMPROVEMENT_PROPOSAL.md` - Architecture design document
- `/docs/KUANDO_DOWNLINK_REFERENCE.md` - Display payload specifications
