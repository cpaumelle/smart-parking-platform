# Frontend Build & Deployment Guide

## Cache-Busting Build System

The V5 frontend uses an auto-incrementing build number system to handle Vite's aggressive caching.

### How It Works

1. **Build Number**: Automatically increments on each build
2. **Asset Hashing**: Vite generates new hashes for JS/CSS files (e.g., `index-wm5WwVWG.js`)
3. **Version Endpoint**: `/version.json` exposed for clients to check current build
4. **Index.html**: Always served fresh (no caching) to load new hashed assets

### Build Scripts

#### `build-with-version.sh`
Main build script that:
- Increments build number in `src/version.json`
- Creates timestamp and build ID
- Runs Vite build with new version
- Copies `version.json` to `dist/` for serving

**Usage:**
```bash
cd /opt/v5-smart-parking/frontend/device-manager
./build-with-version.sh
```

**Output:**
- Updates `src/version.json` with new build number
- Creates production build in `dist/`
- Includes `version.json` in build output

#### `check-version.sh`
Quick script to verify deployed version:

**Usage:**
```bash
cd /opt/v5-smart-parking/frontend/device-manager
./check-version.sh
```

**Output:**
```
🌍 Production (devices.verdegris.eu):
{
  "version": "4.0.0",
  "build": 41,
  "buildTimestamp": "2025-10-17 16:13:01 UTC",
  "buildNumber": "20251017.41"
}
```

### Full Deployment Process

```bash
# 1. Build with version bump (on host)
cd /opt/v5-smart-parking/frontend/device-manager
docker run --rm -v $(pwd):/app -w /app node:20-alpine sh -c \
  "apk add --no-cache bash jq git && ./build-with-version.sh"

# 2. Deploy to nginx container
docker cp dist/. parking-device-manager:/usr/share/nginx/html/

# 3. Restart nginx (forces fresh index.html)
docker restart parking-device-manager

# 4. Verify deployment
./check-version.sh
```

### Why This Works for Cache Busting

1. **New Asset Names**: Each build creates files with new hashes
   - Old: `index-upDihmjK.js`
   - New: `index-wm5WwVWG.js`

2. **Fresh HTML**: Restarting nginx clears any HTML caching, forcing browsers to fetch new `index.html` which references the new asset hashes

3. **Version Tracking**: Clients can poll `/version.json` to detect new builds and prompt refresh

4. **Progressive Enhancement**: Old cached assets won't be used because HTML references new files

### Build Number Format

- **Version**: Semantic version (e.g., `4.0.0`)
- **Build**: Sequential number (increments each build)
- **Build Number**: `YYYYMMDD.BUILD` (e.g., `20251017.41`)
- **Timestamp**: UTC timestamp of build

### Troubleshooting

**Problem**: Browser still showing old version after deployment

**Solutions**:
1. Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
2. Check `/version.json` endpoint to verify deployment
3. Clear browser cache completely
4. Check nginx is serving new files: `docker exec parking-device-manager ls -la /usr/share/nginx/html/assets/`

**Problem**: Build number not incrementing

**Cause**: `src/version.json` not writable or jq not installed

**Solution**: 
```bash
# Ensure proper permissions
sudo chmod 664 /opt/v5-smart-parking/frontend/device-manager/src/version.json

# Verify jq is installed in build container
docker run --rm node:20-alpine sh -c "apk add jq && jq --version"
```

### Integration with Frontend Code

The `useVersion` hook (if implemented) can fetch `/version.json` and:
- Display build info in footer/about page
- Detect when a new build is available
- Prompt users to refresh when version changes

Example:
```javascript
useEffect(() => {
  const checkVersion = async () => {
    const response = await fetch('/version.json');
    const serverVersion = await response.json();
    
    if (serverVersion.build > currentBuild) {
      // Prompt user to refresh
      showUpdateNotification();
    }
  };
  
  // Check every 5 minutes
  const interval = setInterval(checkVersion, 5 * 60 * 1000);
  return () => clearInterval(interval);
}, []);
```

### Version File Schema

```json
{
  "version": "4.0.0",           // Semantic version
  "build": 41,                   // Auto-incrementing build number
  "buildTimestamp": "...",       // Human-readable timestamp
  "buildDate": "20251017",       // YYYYMMDD
  "buildTime": "161301",         // HHMMSS
  "buildNumber": "20251017.41",  // Unique build ID
  "gitCommit": "91af18b",        // Git commit hash (if available)
  "environment": "production"    // Build environment
}
```
