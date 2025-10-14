# Parking System Changelog

## 2025-10-09

### Ingest Service - v1.0.2
**Fixed:** Payload decoder for Browan TABS Motion sensor
- Changed from `base64.b64decode()` to `bytes.fromhex()` for hex payload decoding
- First byte extraction now correct: `0x00` = FREE, `0x01` = OCCUPIED
- File: `/opt/smart-parking/services/ingest/app/parking_detector.py`

### Parking-Display Service - v1.0.1
**Fixed:** JSON serialization error in actuation trigger_data
- Changed `request.dict()` to `request.model_dump(mode='json')` in actuations.py lines 101, 173
- Properly serializes datetime objects when logging to `parking_operations.actuations`
- File: `/opt/smart-parking/services/parking-display/app/routers/actuations.py`

### Production Verification - 2025-10-09 12:05 UTC
**Confirmed:** Complete end-to-end pipeline working
- Sensor uplink: Browan TABS Motion (58a0cb00001019bc) → 0x01 (OCCUPIED)
- Ingest decode: ✅ Correct first byte extraction
- Parking-display: ✅ State change FREE → OCCUPIED
- Downlink sent: ✅ Code 02 to Heltec (70b3d57ed0067001) in 93.2ms
- Total actuation time: 103.4ms (target: <200ms)
- Display confirmed: ✅ Heltec display updated successfully

### Documentation
- Created: `/opt/smart-parking/PARKING-DISPLAY-SERVICE.md`
  - Complete database schema (3 schemas, 5 tables)
  - State engine priority rules
  - API endpoint specifications
  - Deployment and troubleshooting guides

## 2025-10-14

### Parking-Display Service - v1.0.2 (Critical Bug Fixes)

**Fixed:** Reconciliation logic not detecting state changes
- **Issue 1:** `trigger_space_reconciliation()` query missing display_registry fields
  - Added JOIN with display_registry to include display_codes, fport, confirmed_downlinks, last_uplink_at
  - Fixed KeyError crashes when creating reservations
- **Issue 2:** `reconcile_space()` never checked if expected_state ≠ current_state
  - Added primary check: state_mismatch detection (current vs expected)
  - Priority order: 1) State mismatch, 2) Stale update, 3) Missing uplinks
  - Reservations now trigger display updates immediately
- **Issue 3:** `current_state` never updated after successful downlink
  - Now updates current_state, display_state, state_changed_at on success
  - Database state now reflects actual display state
- File: `/opt/smart-parking/services/parking-display/app/tasks/reconciliation.py`

**Enhanced:** Reservation API with immediate reconciliation triggers
- Added `await trigger_space_reconciliation(space_id)` after create/cancel
- Display updates in <100ms instead of waiting for periodic reconciliation
- File: `/opt/smart-parking/services/parking-display/app/routers/reservations.py`

**Fixed:** Timezone handling in reservation model
- Added `@field_validator` to strip timezone info from incoming datetime objects
- Prevents "can't subtract offset-naive and offset-aware datetimes" errors
- File: `/opt/smart-parking/services/parking-display/app/models.py`

**Configuration:**
- Added `RECONCILIATION_INTERVAL_MINUTES: 1` environment variable
- Reduced from 10 minutes to 1 minute for faster backup reconciliation
- File: `/opt/smart-parking/docker-compose.yml`

### Device Manager UI - Build 38

**Added:** 5-second auto-refresh polling
- Automatically fetches latest parking space data every 5 seconds
- Added toggle control with visual indicator: "🔄 Auto-refresh: ON (5s)"
- Users can disable auto-refresh if needed
- File: `iot-platform-reference/10-ui-frontend/sensemy-platform/src/hooks/useSpaces.js`

**Enhanced:** UI responsiveness
- Added auto-refresh status indicator in header
- Real-time clock display (local + UTC)
- Colored status dots: Green (FREE), Red (OCCUPIED), Yellow (RESERVED)
- File: `iot-platform-reference/10-ui-frontend/sensemy-platform/src/pages/ParkingSpaces.jsx`

**Fixed:** Browser caching preventing updates
- Added no-cache headers for index.html and version.json
- Future deployments won't require hard refresh
- File: `iot-platform-reference/10-ui-frontend/sensemy-platform/nginx.conf`

### Production Verification - 2025-10-14 15:25 UTC

**Test 1: Existing Reservation (Woki Space A1-002)**
- State: FREE with active reservation (bug reproduced)
- After fix: Reconciliation detected state_mismatch (FREE → RESERVED)
- Downlink: FF0032FF00 (Magenta/Pink) sent in 48ms
- Result: ✅ Display updated, database correct

**Test 2: Cancel Reservation (Woki desk 1)**
- Cancelled reservation via DELETE /v1/reservations/{id}
- Immediate reconciliation triggered
- State change: RESERVED → FREE
- Downlink: 0000FFFF00 (Green) sent in 70ms
- Total time: 84ms (API call → database update)
- Result: ✅ PASSED

**Test 3: Create Reservation (Dinard Space A1-001)**
- Created reservation starting immediately via POST /v1/reservations/
- Immediate reconciliation triggered
- State change: FREE → RESERVED
- Downlink: 03 (RESERVED code) sent in 75ms
- Total time: 84ms
- Result: ✅ PASSED

### Performance Metrics
- Immediate reconciliation: <100ms (reservation → display update)
- UI auto-refresh: 5 seconds
- Periodic reconciliation: 1 minute (backup)
- End-to-end reservation flow: <100ms (API → display device)

### Data Flow (Complete)
1. User creates/cancels reservation → API call
2. Database updated (reservation status)
3. Immediate reconciliation triggered
4. State engine determines expected_state (considers reservations, sensors, maintenance)
5. Reconciliation detects mismatch → sends downlink
6. Display device receives command (<50ms)
7. Database updated with new current_state
8. UI auto-refreshes within 5 seconds
