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
