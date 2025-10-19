# Changelog

All notable changes to Smart Parking Platform v5 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.2.1] - 2025-10-17

### Added - Downlink Reliability System ✅

#### End-to-End Verification
- **Kuando downlink verification**: RGB color + counter matching on every downlink
- **Redis-based tracking**: Expected values stored with 5-minute TTL
- **Automatic uplink parsing**: 24-byte Kuando payload decoding
- **Success/failure logging**: Detailed verification results in logs

#### Pre-flight Gateway Health Checks
- **Gateway status check**: Query gateway health before sending downlinks
- **HTTP 503 protection**: Block downlinks when no gateways online
- **Redundancy warnings**: Log warnings when only 1 gateway available
- **Response enrichment**: Gateway status included in downlink API responses

#### Queue Monitoring & Detection
- **15-second timeout**: Background task monitors each downlink
- **Stuck detection**: Identifies downlinks still pending after timeout
- **Automatic logging**: "✅ Transmitted" or "⚠️ STUCK" status per downlink
- **Zero overhead**: Asyncio background tasks, minimal performance impact

#### Background Queue Cleanup
- **5-minute interval**: Periodic cleanup of stuck downlinks
- **Gateway-aware**: Only runs when gateway issues detected
- **Automatic flushing**: Clears device queues with downlinks >10 minutes old
- **Comprehensive logging**: All cleanup actions logged for observability

#### Kuando Auto-Uplink Support
- **Universal method (6th byte)**: Works on ALL firmware versions (3.1, 4.3, 6.1)
- **Persistent method (0601 command)**: For firmware >=5.6 (2/4 devices compatible)
- **Automatic injection**: 6th byte automatically added to all Kuando downlinks
- **Firmware compatibility tracking**: Device firmware versions monitored

### Fixed
- **File recovery**: Restored corrupted main.py (868 lines) without data loss
- **Redis client references**: Fixed `redis_client` → `state_manager.redis_client` throughout
- **Background task dependencies**: Added ChirpStack and gateway monitor to BackgroundTaskManager

### Changed
- **Downlink API response**: Now includes `gateway_health` with status and counts
- **Background tasks**: Enhanced with queue monitoring and cleanup capabilities
- **Logging improvements**: Detailed verification, queue status, and cleanup logs

### Documentation
- **Complete implementation guide**: `docs/DOWNLINK_RELIABILITY_IMPLEMENTATION_COMPLETE.md`
- **Progress tracking updated**: `docs/RELIABILITY_PROGRESS_2025-10-17.md` (Phase 1: 100% complete)
- **Architecture diagrams**: Before/after data flow visualization
- **Testing results**: Verification success rate and performance metrics

### Performance
- **Verification success rate**: High (tested in production)
- **Queue monitoring overhead**: Minimal (asyncio background tasks)
- **Background cleanup interval**: 5 minutes (configurable)
- **Redis TTLs**: 5 min (pending downlinks), 1 hour (uplink data)

### Testing
- ✅ End-to-end verification flow with RGB + counter matching
- ✅ Pre-flight gateway checks (0, 1, 2+ gateways)
- ✅ Queue monitoring with 15-second timeout
- ✅ Background cleanup task initialization
- ✅ Kuando auto-uplink (6th byte method) confirmed working

---

## [5.2.0] - 2025-10-17

### Added

#### ORPHAN Device Auto-Discovery
- **Event-driven device registration**: Devices automatically register on first uplink from ChirpStack
- **Zero manual configuration**: No need to pre-register devices before deployment
- **Device type auto-creation**: Unknown ChirpStack device profiles automatically create ORPHAN device types
- **Sample payload storage**: First uplink payload stored for admin review before confirmation

#### Device Lifecycle Management
- **Device status tracking**: `orphan` → `active` → `inactive` → `decommissioned`
- **Status column added** to `sensor_devices` and `display_devices` tables
- **Device assignment workflow**: Admin explicitly assigns ORPHAN devices to spaces
- **Historical data preservation**: All sensor readings preserved during reassignments
- **Temporal correctness**: Device reassignments maintain accurate historical data

#### Admin API Endpoints
- `GET /api/v1/admin/devices/unassigned` - List all unassigned devices
- `POST /api/v1/admin/devices/sensor/{device_id}/assign` - Assign sensor to space
- `POST /api/v1/admin/devices/display/{device_id}/assign` - Assign display to space
- `POST /api/v1/admin/devices/sensor/{device_id}/unassign` - Unassign sensor from space
- `POST /api/v1/admin/devices/display/{device_id}/unassign` - Unassign display from space
- **Admin authentication**: All endpoints require API key with admin privileges

#### Database Enhancements
- **device_types table additions**:
  - `status` column: 'orphan', 'confirmed', 'disabled'
  - `chirpstack_profile_name` column: Maps to ChirpStack device_profile.name
  - `chirpstack_profile_id` column: ChirpStack device_profile.id reference
  - `sample_payload` column: Sample normalized uplink JSON
  - `sample_raw_payload` column: Original raw uplink for debugging
  - `confirmed_at` column: When admin confirmed ORPHAN type
  - `confirmed_by` column: Admin email/username who confirmed
  - `notes` column: Admin notes about type handling

- **Database views**:
  - `unassigned_sensors` - Query sensors with status='orphan'
  - `unassigned_displays` - Query displays with status='orphan'
  - `inconsistent_devices` - Find devices where status doesn't match assignment

- **Database constraints**:
  - `CHECK (status IN ('orphan', 'confirmed', 'disabled'))` on device_types
  - `UNIQUE (chirpstack_profile_name)` for 1:1 mapping to ChirpStack profiles
  - `CHECK (status IN ('orphan', 'active', 'inactive', 'decommissioned'))` on device tables

#### Documentation
- `/docs/ORPHAN_DEVICE_ARCHITECTURE.md` - Complete ORPHAN pattern documentation
- README.md updated with admin API endpoint documentation
- Device lifecycle diagrams and workflows
- Example API usage for admin operations

### Changed

#### Uplink Processing
- **Automatic device discovery**: First uplink creates ORPHAN device if not found
- **Automatic device type discovery**: Unknown ChirpStack profiles create ORPHAN device types
- **Capability auto-detection**: Device capabilities inferred from payload keys
- **Conditional actuation**: ORPHAN devices store data but don't trigger actuations
- **Last seen tracking**: `last_seen_at` updated on every uplink

#### ChirpStack Integration
- **Direct profile name mapping**: Query ChirpStack database for device profile names
- **Profile ID storage**: Store ChirpStack device_profile.id for reference
- **Device-to-type mapping**: Use `chirpstack_profile_name` for device type lookups

### Fixed
- **Device type naming consistency**: Resolved confusion between type codes and class names
- **Duplicate device handling**: Fixed devices appearing in both sensor and display tables
- **Kuando device categorization**: Moved miscategorized displays from sensor_devices table
- **Device type merging**: Consolidated duplicate Heltec device types

### Database Migrations
- `ALTER TABLE device_types ADD COLUMN status VARCHAR(30) DEFAULT 'confirmed'`
- `ALTER TABLE device_types ADD COLUMN chirpstack_profile_name VARCHAR(100)`
- `ALTER TABLE device_types ADD COLUMN chirpstack_profile_id UUID`
- `ALTER TABLE device_types ADD COLUMN sample_payload JSONB`
- `ALTER TABLE device_types ADD COLUMN sample_raw_payload JSONB`
- `ALTER TABLE device_types ADD COLUMN confirmed_at TIMESTAMPTZ`
- `ALTER TABLE device_types ADD COLUMN confirmed_by VARCHAR(100)`
- `ALTER TABLE device_types ADD COLUMN notes TEXT`
- `ALTER TABLE sensor_devices ADD COLUMN status VARCHAR(30) DEFAULT 'orphan'`
- `ALTER TABLE display_devices ADD COLUMN status VARCHAR(30) DEFAULT 'orphan'`
- Created views: `unassigned_sensors`, `unassigned_displays`, `inconsistent_devices`

### Testing
- ✅ List unassigned devices endpoint
- ✅ Assign sensor to space (orphan → active)
- ✅ Unassign sensor from space (active → inactive)
- ✅ Reassign sensor to different space
- ✅ Assign display to space (orphan → active)
- ✅ Unassign display from space (active → inactive)
- ✅ Error handling for duplicate assignments
- ✅ Admin API key authentication
- ✅ Device status consistency after operations

---

## [2.0.0] - 2025-10-16

### Added
- Initial v5 production release
- Consolidated 7 microservices into single FastAPI application
- PostgreSQL 16 with connection pooling
- Redis 7 for caching
- ChirpStack v4 integration
- Traefik v3.1 reverse proxy with automatic HTTPS
- Real-time occupancy tracking
- Reservation management with conflict detection
- Display control for LED/E-ink indicators
- RESTful API with OpenAPI documentation
- Health checks and monitoring
- Production deployment on verdegris.eu

### Changed
- Replaced 7 separate microservices with unified API
- Simplified database schema from distributed to normalized
- Reduced codebase from ~15,000 to ~3,000 lines
- Single docker-compose deployment

---

## [1.x] - Legacy (Deprecated)

v4 platform with microservices architecture. No longer maintained.

---

[5.2.0]: https://github.com/verdegris/smart-parking-v5/compare/v2.0.0...v5.2.0
[2.0.0]: https://github.com/verdegris/smart-parking-v5/releases/tag/v2.0.0
