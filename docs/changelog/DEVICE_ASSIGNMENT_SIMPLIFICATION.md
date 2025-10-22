# Device Assignment Simplification - Build 18

## Problem Statement

The previous DeviceConfigurationModal was overly complex:
- Tried to manage device types in parking database (duplication with ChirpStack)
- Complex location hierarchy (sites/floors/rooms/zones) - v5.3 only has sites
- Confusing device_type_id assignments
- Data synchronization issues between parking_v5 and ChirpStack
- Tried to assign devices to spaces from Devices page (wrong place)

## New Architecture - SIMPLIFIED

**Devices Page = Like Gateways Page**

Devices page shows read-only ChirpStack information and allows site assignment only.
Space assignment happens in the Parking Spaces page.

### Data Sources

**ChirpStack Database (Source of Truth for LoRaWAN):**
- `device` table: dev_eui, name, device_profile_id
- `device_profile` table: id, name (e.g., "browan_tbms100_motion")
- `gateway` table: gateway_id, name, description, last_seen_at

**Parking_v5 Database (Source of Truth for Parking Business Logic):**
- `sites` table: id, name, timezone
- `spaces` table: id, code, name, site_id, **sensor_eui**, **display_eui**
- `reservations` table: space assignments and booking logic

### Device Assignment Flow

```
1. Device discovered in ChirpStack
   ↓
2. Device appears in Devices page (orphan status)
   ↓
3. User opens Device Assignment Modal
   ↓
4. User selects:
   - Site (building/campus)
   - Space (specific parking spot within site)
   ↓
5. Save updates spaces table:
   - If sensor: UPDATE spaces SET sensor_eui = '{dev_eui}' WHERE id = '{space_id}'
   - If display: UPDATE spaces SET display_eui = '{dev_eui}' WHERE id = '{space_id}'
```

## New Device Assignment Modal

### What It Shows (Read-Only):
- ✅ Device EUI (from ChirpStack)
- ✅ Device Name (from ChirpStack)
- ✅ Device Type/Profile (from ChirpStack device_profile.name) - **READ ONLY**
- ✅ Category (Sensor vs Display)

### What User Configures:
- ✅ Site Selection (dropdown from Sites API)
- ✅ Space Selection (dropdown from spaces within selected site)

### What Happens on Save:
```javascript
// For sensor devices:
PATCH /api/v1/spaces/{space_id}
{
  "sensor_eui": "E8E1E1000103C2B0"
}

// For display devices:
PATCH /api/v1/spaces/{space_id}
{
  "display_eui": "202020390C0E0902"
}
```

## Benefits

1. **Single Source of Truth:**
   - Device types managed in ChirpStack only
   - No data duplication
   - No sync issues

2. **Simpler UX:**
   - Select site → Select space → Done
   - No complex hierarchy
   - Clear device-to-space relationship

3. **Clearer Data Model:**
   ```
   Device (ChirpStack)
     └─ assigned to → Space (parking_v5)
                       └─ belongs to → Site (parking_v5)
   ```

4. **Less Code:**
   - Removed complex device type management
   - Removed floors/rooms/zones (not in v5.3)
   - Simpler state management

## Implementation

### Files Created:
- `frontend/device-manager/src/components/DeviceAssignmentModal.jsx` (NEW)
  - 280 lines (was 500+ in old modal)
  - Clear, focused responsibility
  - Uses existing parkingSpacesService

### Files to Update:
- `src/components/DeviceList.jsx` - Use new DeviceAssignmentModal
- `src/routers/devices.py` - Enhance to JOIN with ChirpStack device_profile
- `src/routers/devices.py` - Enhance to JOIN with spaces for site/space info

## API Changes Needed

### GET /api/v1/devices - Enhanced Response

Current response per device:
```json
{
  "id": "uuid",
  "deveui": "E8E1E1000103C2B0",
  "device_type": "browan_tbms100_motion",
  "status": "active"
}
```

Enhanced response needed:
```json
{
  "id": "uuid",
  "deveui": "E8E1E1000103C2B0",
  "name": "Printer Tabs C3F8",  // from ChirpStack device.name
  "device_type": "browan_tbms100_motion",  // still in parking_v5 for backward compat
  "device_profile_name": "browan_tbms100_motion",  // from ChirpStack device_profile.name
  "category": "sensor",
  "status": "active",
  "assigned_space_id": "uuid",  // from spaces.id WHERE sensor_eui = this device
  "assigned_space_code": "WINDOW",  // from spaces.code
  "assigned_space_name": "window",  // from spaces.name
  "assigned_site_id": "uuid",  // from sites.id via spaces.site_id
  "assigned_site_name": "Default Site"  // from sites.name
}
```

### Implementation:
```sql
-- For sensor devices:
SELECT
  sd.id,
  sd.dev_eui as deveui,
  sd.device_type,
  d.name as device_name,  -- JOIN with ChirpStack
  dp.name as device_profile_name,  -- JOIN with ChirpStack
  sd.category,
  sd.status,
  s.id as assigned_space_id,
  s.code as assigned_space_code,
  s.name as assigned_space_name,
  si.id as assigned_site_id,
  si.name as assigned_site_name
FROM sensor_devices sd
LEFT JOIN chirpstack.device d ON UPPER(sd.dev_eui) = UPPER(encode(d.dev_eui, 'hex'))
LEFT JOIN chirpstack.device_profile dp ON d.device_profile_id = dp.id
LEFT JOIN spaces s ON s.sensor_eui = sd.dev_eui AND s.tenant_id = $1
LEFT JOIN sites si ON s.site_id = si.id
WHERE ... tenant scoping ...
```

## Migration Path

1. ✅ Create new DeviceAssignmentModal.jsx
2. ⏳ Enhance GET /api/v1/devices with ChirpStack + spaces JOINs
3. ⏳ Update DeviceList to use new modal
4. ⏳ Update DeviceList table columns to show site/space
5. ⏳ Deploy Build 18
6. 🗑️ Eventually remove old DeviceConfigurationModal.tsx

## User Experience

### Before (Complex):
1. Open device modal
2. Select device type from dropdown (confusing - already in ChirpStack)
3. Navigate complex location hierarchy
4. Save updates multiple tables

### After (Simple):
1. Open device modal
2. See device type (read-only, from ChirpStack)
3. Select site from dropdown
4. Select space from dropdown
5. Save assigns device to that space

## Testing Checklist

- [ ] Backend returns device_profile_name from ChirpStack
- [ ] Backend returns assigned_site_name and assigned_space_name
- [ ] DeviceList shows site and space columns
- [ ] Device Assignment Modal opens
- [ ] Site dropdown populates
- [ ] Space dropdown filters by selected site
- [ ] Save assigns sensor_eui or display_eui to space
- [ ] Device status changes from orphan to active
- [ ] DeviceList refreshes and shows assignment

## Next Steps

Awaiting user approval on this approach before proceeding with:
1. Backend API enhancements (JOIN with ChirpStack)
2. DeviceList updates
3. Build 18 deployment
