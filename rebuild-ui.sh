#!/bin/bash
set -e

echo "========================================="
echo "🚀 SenseMy UI Cache-Busting Rebuild"
echo "========================================="
echo ""

UI_DIR="/opt/smart-parking/iot-platform-reference/10-ui-frontend/sensemy-platform"
COMPOSE_DIR="/opt/smart-parking"

# Step 1: Update version number
echo "📝 Step 1/8: Updating version number..."
python3 << 'PYEOF'
import json
from datetime import datetime, timezone

version_file = "/opt/smart-parking/iot-platform-reference/10-ui-frontend/sensemy-platform/src/version.json"

with open(version_file, 'r') as f:
    version = json.load(f)

# Increment build
version['build'] = int(version['build']) + 1

# Update timestamps
now = datetime.now(timezone.utc)
version['buildTimestamp'] = now.strftime('%Y-%m-%d %H:%M:%S UTC')
version['buildDate'] = now.strftime('%Y%m%d')
version['buildTime'] = now.strftime('%H%M%S')
version['buildNumber'] = f"{version['buildDate']}.{version['build']}"

with open(version_file, 'w') as f:
    json.dump(version, f, indent=2)

print(f"   ✓ Version: {version['buildNumber']}")
PYEOF

# Step 2: Clean all caches
echo "🧹 Step 2/8: Cleaning all caches..."
cd "$UI_DIR"
rm -rf dist node_modules/.vite .vite 2>/dev/null || true
echo "   ✓ Cleared dist, .vite, node_modules/.vite"

# Step 2.5: Copy version.json to public directory for Vite
echo "📋 Step 2.5/8: Copying version.json to public directory..."
mkdir -p "$UI_DIR/public"
cp "$UI_DIR/src/version.json" "$UI_DIR/public/version.json"
echo "   ✓ version.json copied to public/"

# Step 3: Build with clean container
echo "🔨 Step 3/8: Building with fresh Node container..."
docker run --rm \
  -v "$(pwd)":/app \
  -w /app \
  node:20-alpine \
  sh -c "npm run build" 2>&1 | grep -E "✓|error|warning|built in" || true
echo "   ✓ Build complete"

# Step 4: Stop and remove container
echo "🛑 Step 4/8: Stopping container..."
cd "$COMPOSE_DIR"
docker compose stop device-manager-ui 2>&1 | grep -v "warning" || true
docker rm -f parking-device-manager 2>/dev/null || true
echo "   ✓ Container stopped and removed"

# Step 5: Remove old image
echo "🗑️  Step 5/8: Removing old Docker image..."
docker rmi -f smart-parking-device-manager-ui 2>&1 | grep -E "Untagged|Deleted" | head -2 || true
echo "   ✓ Old image removed"

# Step 6: Rebuild Docker image with no cache
echo "🐳 Step 6/8: Building new Docker image (no cache)..."
docker compose build --no-cache device-manager-ui 2>&1 | grep -E "DONE|Built" | tail -3
echo "   ✓ New image built"

# Step 7: Start container
echo "🚀 Step 7/8: Starting container..."
docker compose up -d device-manager-ui 2>&1 | grep -E "Started|Creating" || true
sleep 2
echo "   ✓ Container started"

# Step 8: Verify version.json
echo "🔍 Step 8/8: Verifying version.json..."
echo "   Source version:"
cat "$UI_DIR/src/version.json" | grep -E "buildNumber" | sed 's/^/      /'
echo "   Dist version:"
cat "$UI_DIR/dist/version.json" | grep -E "buildNumber" | sed 's/^/      /'

echo ""
echo "========================================="
echo "✅ Rebuild Complete!"
echo "========================================="
echo ""
echo "📊 New Build Info:"
cat "$UI_DIR/src/version.json" | grep -E "buildNumber|buildTimestamp" | sed 's/^/   /'
echo ""
echo "🌐 Access: https://ops.verdegris.eu"
echo ""
echo "💡 Tip: Hard refresh your browser (Ctrl+Shift+R / Cmd+Shift+R)"
echo "   to bypass browser cache and see the new build."
echo ""
