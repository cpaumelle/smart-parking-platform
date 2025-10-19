#\!/bin/bash
# Quick version check script
# Version: 5.0.0 - 2025-10-17

echo "🔍 Smart Parking Platform V5 - Version Check"
echo "==========================================="
echo ""

# Production version
echo "🌍 Production (devices.verdegris.eu):"
PROD_VERSION=$(curl -s https://devices.verdegris.eu/version.json 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$PROD_VERSION" | jq '.'
else
    echo "❌ Could not reach production version endpoint"
fi

echo ""
echo "📋 Quick info:"
if [ -n "$PROD_VERSION" ]; then
    BUILD_NUM=$(echo "$PROD_VERSION" | jq -r '.buildNumber')
    BUILD_TIME=$(echo "$PROD_VERSION" | jq -r '.buildTimestamp')
    echo "   Build: $BUILD_NUM"
    echo "   Time:  $BUILD_TIME"
fi
