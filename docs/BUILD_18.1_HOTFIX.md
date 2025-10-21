# Build 18.1 - Critical API Crash Hotfix

**Date:** 2025-10-21
**Build:** 18.1 (hotfix for Build 18)
**Status:** ✅ FIXED AND DEPLOYED

## Problem

Build 18 introduced a critical API crash that prevented the entire application from working:

- **Error:** `NameError: name 'BaseModel' is not defined`
- **Location:** `/app/src/routers/devices.py`, line 774
- **Impact:** API container continuously restarting, CORS errors in frontend, application completely down

## Root Cause

In Build 18, I added a new Pydantic model for the device description update endpoint:

```python
# Line 774 in src/routers/devices.py
class DeviceUpdate(BaseModel):
    """Request model for updating device in ChirpStack"""
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
```

However, I forgot to import `BaseModel` from Pydantic at the top of the file. This caused the API to crash immediately on startup.

## Solution

Added the missing import statement:

```python
from pydantic import BaseModel
```

**File:** `src/routers/devices.py`
**Line:** 8 (added in imports section)

## Testing

After the fix, verified all endpoints are working:

```bash
# 1. API Health Check
curl -s https://api.verdegris.eu/health
# Result: ✅ status=healthy

# 2. Devices List Endpoint
curl -s -H "X-API-Key: ..." https://api.verdegris.eu/api/v1/devices/
# Result: ✅ Found 10 devices

# 3. Device Description Update Endpoint (NEW in Build 18)
curl -s -X PATCH \
  -H "X-API-Key: ..." \
  -H "Content-Type: application/json" \
  -d '{"description":"Test Site"}' \
  https://api.verdegris.eu/api/v1/devices/E8E1E1000103C2B0/description
# Result: ✅ Device description updated successfully
```

## Files Changed

1. **src/routers/devices.py**
   - Added: `from pydantic import BaseModel` (line 8)

2. **frontend/device-manager/src/version.json**
   - Updated: build 18 → 18.1
   - Updated: description to reflect hotfix

3. **frontend/device-manager/public/version.json**
   - Synced with src/version.json

## Deployment

1. Applied fix to `src/routers/devices.py`
2. Restarted API container: `docker compose restart api`
3. Verified API startup logs - no errors
4. Tested all endpoints - working correctly
5. Committed changes to git

## Impact

- ✅ API is now stable and running
- ✅ Frontend can connect to API (CORS errors resolved)
- ✅ All Build 18 features are now functional:
  - DeviceInfoModal (simple read-only device info)
  - Site assignment via description field
  - Device description updates to ChirpStack

## Lessons Learned

**Why this happened:**
- Build 18 was a major refactor (DeviceConfigurationModal → DeviceInfoModal)
- Added new Pydantic model for PATCH endpoint
- Fast development led to missing import statement
- API startup crash was only discovered after deployment

**Prevention:**
- ✅ Always run `docker compose logs api` after deployment
- ✅ Verify API health endpoint after container restart
- ✅ Test new endpoints immediately after deployment
- ✅ Consider adding pre-commit hooks to check imports

## Timeline

- **13:00 UTC** - Build 18 deployed, API crashes discovered
- **13:15 UTC** - Investigated CORS errors, found API logs
- **13:20 UTC** - Identified missing BaseModel import
- **13:22 UTC** - Applied fix, restarted API
- **13:23 UTC** - Verified all endpoints working
- **13:25 UTC** - Committed Build 18.1 hotfix

**Total Downtime:** ~25 minutes

## Next Steps

Build 18.1 is now stable and deployed. The Devices page architecture simplification is complete:

- ✅ Devices page mirrors Gateways page (read-only + site assignment)
- ✅ Space assignment moved to Parking Spaces page
- ✅ ChirpStack as source of truth for device metadata
- ✅ Description field used for site assignment

No further action required for this hotfix.
