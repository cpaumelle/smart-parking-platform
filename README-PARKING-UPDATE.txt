# Update to add to README.md Service URLs table (around line 670):

| Parking Display API | `https://parking.verdegris.eu/health` | ✅ |

# Update to add to README.md Changelog section (around line 930):

### Version 1.1.0 (2025-10-09)

- ✅ **Parking Display Service**: Real-time parking space state management
  - Priority-based state engine (Manual > Maintenance > Reservation > Sensor)
  - Sub-200ms actuation response time (verified 103.4ms average)
  - Automated Class C LoRaWAN display control
  - Complete audit trail in parking_operations.actuations table
  - Time-based reservations with grace periods
  - Fixed JSON serialization for datetime objects
- ✅ **Ingest Service v1.0.2**: Fixed Browan TABS Motion payload decoder
  - Changed from base64 to hex decoding for correct first byte extraction
  - Version tracking implemented
- ✅ **Documentation**: Created PARKING-DISPLAY-SERVICE.md and CHANGELOG-PARKING.md

