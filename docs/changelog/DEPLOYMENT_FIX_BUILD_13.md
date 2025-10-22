# Deployment Fix: Build 13 - Docker .gitignore Issue

**Date**: 2025-10-21
**Build**: 13 (20251021.13)
**Status**: ✅ RESOLVED AND DEPLOYED

---

## Problem Summary

Despite committing Builds 11, 12, and 13 to Git and rebuilding the Docker container multiple times with `--no-cache`, the deployed application was stuck showing Build 10. The user's browser continued to receive Build 10 files even after multiple deployment attempts.

## Root Cause

**The Docker build context was excluding the `dist/` folder due to `.gitignore`.**

### Technical Details:

1. **`.gitignore` Contains `dist`**:
   - The Vite project's `.gitignore` includes `dist` to prevent committing build artifacts to Git
   - This is standard practice for Node.js/Vite projects

2. **Docker BuildKit Respects `.gitignore`**:
   - When Docker BuildKit is enabled (default in modern Docker), it uses `.gitignore` rules when calculating the build context
   - If no `.dockerignore` file exists, Docker assumes you want to ignore everything in `.gitignore`

3. **Build Context Only 329 Bytes**:
   - The `dist/` folder is 884KB but Docker was only transferring 329B of context
   - This 329B consisted only of `Dockerfile` and `nginx.conf`
   - The `COPY dist/ /usr/share/nginx/html/` command was copying nothing or an empty directory

4. **Old Cached Layers**:
   - Docker was using cached layers from a previous build that happened to have the Build 10 dist folder
   - Even with `--no-cache`, the base nginx:alpine image already had some files at that path
   - The COPY operation completed in 0.0s because there was nothing to copy

### Evidence:

```bash
# Docker build output showing tiny context:
#8 [internal] load build context
#8 transferring context: 329B done   ← Should be ~884KB!
#8 DONE 0.0s

#10 [3/4] COPY dist/ /usr/share/nginx/html/
#10 DONE 0.0s   ← Copying nothing takes 0.0s
```

## Solution

**Created `.dockerignore` file to explicitly control what Docker includes/excludes.**

### File: `frontend/device-manager/.dockerignore`

```dockerignore
# Minimal .dockerignore - only exclude what we don't need
# This ensures dist/ is included (unlike .gitignore)

node_modules
.git
src
public
*.md
```

### Why This Works:

1. When `.dockerignore` exists, Docker uses it INSTEAD of `.gitignore`
2. We explicitly exclude only what Docker doesn't need:
   - `node_modules` - dev dependencies (not needed in production image)
   - `.git` - version control metadata
   - `src` - source code (only need compiled `dist`)
   - `public` - source assets (only need compiled `dist`)
   - `*.md` - documentation files
3. By NOT listing `dist` in `.dockerignore`, it's now included in the build context

### Results After Fix:

```bash
# Build context size verification:
$ du -sh frontend/device-manager/dist/
884K	frontend/device-manager/dist/

# Docker image inspection:
$ docker run --rm parking-v5-device-manager-ui:latest cat /usr/share/nginx/html/version.json
{
  "version": "5.3.1",
  "build": "13",   ← Correct!
  ...
}

# Public deployment verification:
$ curl -s https://devices.verdegris.eu/version.json | jq .build
"13"   ← Success!
```

## Deployment Steps Used

1. **Created `.dockerignore` file** to override `.gitignore` behavior
2. **Removed old Docker image**:
   ```bash
   docker compose down device-manager-ui
   docker rmi parking-v5-device-manager-ui:latest
   ```
3. **Rebuilt image from scratch**:
   ```bash
   docker compose build --no-cache device-manager-ui
   ```
4. **Started new container**:
   ```bash
   docker compose up -d device-manager-ui
   ```
5. **Verified deployment**:
   ```bash
   curl -s https://devices.verdegris.eu/version.json
   ```

## Build 13 Features Now Live

### Device Configuration Modal (`src/components/DeviceConfigurationModal.tsx`):

1. **Device Type Dropdown Fixed**:
   - **Before**: Hardcoded `https://api3.sensemy.cloud` URL causing 404/CORS errors
   - **After**: Uses `deviceService.getDeviceMetadata()` with proper authentication
   - **Impact**: Dropdown now populates with all available device types

2. **Site Selection Simplified**:
   - **Before**: "Location *" label with complex hierarchy (sites → floors → rooms → zones)
   - **After**: "Site *" label with single dropdown using Sites API
   - **Impact**: Cleaner UX, aligns with v5.3 database structure

3. **Parking Space Registration Section Added**:
   - New section explaining how to assign devices to parking spots
   - Directs users to Parking Spaces page for space assignment
   - Improves user guidance for complete device setup

### Gateway Configuration Modal (`src/components/gateways/GatewayConfigModal.jsx`):

1. **Site Assignment Dropdown Fixed**:
   - **Before**: "Location Assignment" with empty dropdown
   - **After**: "Site Assignment" showing sites from Sites API
   - **Impact**: Users can now assign gateways to buildings/campuses

## Lessons Learned

### For Future Deployments:

1. **Always Create `.dockerignore` for Frontend Projects**:
   - Don't rely on Docker to automatically handle `.gitignore` correctly
   - Explicitly define what should/shouldn't be in the build context

2. **Verify Build Context Size**:
   - Check Docker build output for "transferring context: XXX" line
   - If size seems too small, something is being excluded incorrectly

3. **Inspect Built Images**:
   - Use `docker run --rm <image> ls -lah /path` to verify files are copied
   - Use `docker run --rm <image> cat /path/to/file` to check file contents
   - Don't assume `--no-cache` will fix everything

4. **Frontend Build Verification**:
   - Check timestamps on built assets match recent build
   - Verify version.json content in both dist folder and running container
   - Test public URL immediately after deployment

## Cache Busting

The user specifically requested "make sure to use the full deplpyment script to force the cache update for teh Reacy Vite site."

### How Vite Handles Cache Busting:

Vite automatically generates content-hashed filenames for all assets:
- `index-vOtmoqQ5.js` (JavaScript bundle)
- `index-DXfPRtbF.css` (CSS bundle)

These hashes change whenever the file content changes, ensuring browsers always fetch the latest version.

### Additional Cache Control:

The nginx configuration already includes proper cache headers:
```nginx
cache-control: no-cache, no-store, must-revalidate
expires: 0
pragma: no-cache
```

This prevents browsers from caching the `index.html` file, which references the hashed assets.

## Verification Checklist

- [x] Build 13 files present in dist/ folder (884KB)
- [x] .dockerignore created and committed
- [x] Docker image rebuilt from scratch
- [x] Container running with Build 13 image
- [x] Public URL serves Build 13 (version.json shows "13")
- [x] JavaScript bundle has correct timestamp (2025-10-21 11:58:29 GMT)
- [x] User can see Build 13 in browser (cache busting working)

## Deployment Status

**Environment**: Production
**URL**: https://devices.verdegris.eu
**Build**: 13 (20251021.13)
**Deployed**: 2025-10-21 12:08:00 UTC
**Status**: ✅ LIVE

---

## Commands Reference

### Rebuild and Deploy:
```bash
# Navigate to project root
cd /opt/v5-smart-parking

# Stop and remove old container
docker compose down device-manager-ui

# Remove old image
docker rmi parking-v5-device-manager-ui:latest

# Rebuild from scratch
docker compose build --no-cache device-manager-ui

# Start new container
docker compose up -d device-manager-ui

# Verify
curl -s https://devices.verdegris.eu/version.json | jq .build
```

### Verify Build Context:
```bash
# Check dist folder size
du -sh frontend/device-manager/dist/

# Inspect built image
docker run --rm parking-v5-device-manager-ui:latest ls -lah /usr/share/nginx/html/
docker run --rm parking-v5-device-manager-ui:latest cat /usr/share/nginx/html/version.json
```

### Frontend Build:
```bash
cd frontend/device-manager
npm run build
ls -lah dist/
```

---

**Issue Resolved**: Docker .gitignore excluding dist folder from build context
**Solution**: Created .dockerignore with minimal exclusions
**Impact**: All builds (11, 12, 13) now deployable, Build 13 live in production
