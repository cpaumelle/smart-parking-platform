#!/bin/bash
# Complete SenseMy IoT Platform Deployment Script with Version Verification
# Version: 1.1.0 - 2025-08-11 18:10:00 UTC - Fixed path handling
# Author: SenseMy IoT Development Team

set -e

echo "🚀 SenseMy IoT Platform - Complete Deployment with Version Verification"
echo "====================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get current directory and project root
CURRENT_DIR=$(pwd)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Ensure we're in the right place
if [[ "$CURRENT_DIR" != *"10-ui-frontend/sensemy-platform" ]]; then
    print_error "Script must be run from 10-ui-frontend/sensemy-platform directory"
    print_status "Current directory: $CURRENT_DIR"
    print_status "Please run: cd ~/v4-iot-pipeline/10-ui-frontend/sensemy-platform && ./deploy-with-version.sh"
    exit 1
fi

# Step 1: Build with version
print_status "Building application with version tracking..."
./build-with-version.sh

if [ $? -ne 0 ]; then
    print_error "Build failed!"
    exit 1
fi

# Get build info for verification
BUILD_NUMBER=$(jq -r '.buildNumber' src/version.json)
BUILD_VERSION=$(jq -r '.version' src/version.json)
BUILD_TIMESTAMP=$(jq -r '.buildTimestamp' src/version.json)

print_success "Build completed: v${BUILD_VERSION} Build ${BUILD_NUMBER}"

# Step 2: Navigate to project root (fixed path)
cd ~/v4-iot-pipeline
PROJECT_ROOT=$(pwd)
print_status "Project root: $PROJECT_ROOT"

# Verify we're in the right place
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found in $PROJECT_ROOT"
    exit 1
fi

# Step 3: Determine correct service name
print_status "Detecting frontend service name..."

# Check for different possible service names
if grep -q "ui-frontend:" docker-compose.yml; then
    SERVICE_NAME="ui-frontend"
elif grep -q "frontend:" docker-compose.yml; then
    SERVICE_NAME="frontend"
elif grep -q "ui_frontend:" docker-compose.yml; then
    SERVICE_NAME="ui_frontend"
else
    print_error "Could not find frontend service in docker-compose.yml"
    print_status "Available services:"
    docker compose config --services 2>/dev/null || docker-compose config --services
    exit 1
fi

print_success "Found frontend service: $SERVICE_NAME"

# Step 4: Stop existing container
print_status "Stopping existing frontend container..."
docker compose stop $SERVICE_NAME 2>/dev/null || print_warning "Container not running"

# Step 5: Remove existing container and image for clean rebuild
print_status "Removing existing container and image..."
docker compose rm -f $SERVICE_NAME 2>/dev/null || true

# Get the image name and remove it
IMAGE_NAME=$(docker compose config | grep -A 10 "$SERVICE_NAME:" | grep image: | awk '{print $2}' || echo "")
if [ -z "$IMAGE_NAME" ]; then
    # If no image specified, it's built locally with this naming pattern
    IMAGE_NAME="${PWD##*/}-${SERVICE_NAME}"
fi

print_status "Removing image: $IMAGE_NAME"
docker image rm "$IMAGE_NAME" 2>/dev/null || print_warning "Image not found"

# Step 6: Build new container
print_status "Building new container (no cache)..."
docker compose build $SERVICE_NAME --no-cache

if [ $? -ne 0 ]; then
    print_error "Container build failed!"
    exit 1
fi

print_success "Container built successfully"

# Step 7: Start new container
print_status "Starting new container..."
docker compose up -d $SERVICE_NAME

if [ $? -ne 0 ]; then
    print_error "Container start failed!"
    exit 1
fi

print_success "Container started"

# Step 8: Wait for container to be ready
print_status "Waiting for container to be ready..."
for i in {1..30}; do
    if docker compose ps $SERVICE_NAME | grep -q "Up"; then
        print_success "Container is running"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Container failed to start properly"
        docker compose logs $SERVICE_NAME --tail 20
        exit 1
    fi
    sleep 2
    echo -n "."
done
echo

# Step 9: Additional wait for nginx to be ready
print_status "Waiting for nginx to serve content..."
sleep 10

# Step 10: Verify deployment
print_status "Verifying deployment..."

# Check container status
CONTAINER_STATUS=$(docker compose ps $SERVICE_NAME --format "table {{.Status}}" | tail -n +2)
print_status "Container status: $CONTAINER_STATUS"

# Test local access (check the port from docker-compose)
UI_PORT=$(grep -A 5 "$SERVICE_NAME:" docker-compose.yml | grep ports: -A 1 | grep -o '[0-9]*:80' | cut -d: -f1 || echo "8801")
print_status "Testing local access on port $UI_PORT..."
LOCAL_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null http://localhost:$UI_PORT || echo "000")
if [ "$LOCAL_RESPONSE" = "200" ]; then
    print_success "Local access: OK"
else
    print_warning "Local access failed (HTTP $LOCAL_RESPONSE)"
fi

# Test version endpoint locally
print_status "Testing local version endpoint..."
LOCAL_VERSION=$(curl -s http://localhost:$UI_PORT/version.json 2>/dev/null | jq -r '.buildNumber' 2>/dev/null || echo "failed")
if [ "$LOCAL_VERSION" = "$BUILD_NUMBER" ]; then
    print_success "Local version endpoint: OK (Build $LOCAL_VERSION)"
else
    print_warning "Local version endpoint: Expected $BUILD_NUMBER, got $LOCAL_VERSION"
fi

# Test external access
print_status "Testing external access..."
EXTERNAL_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null https://app2.sensemy.cloud || echo "000")
if [ "$EXTERNAL_RESPONSE" = "200" ]; then
    print_success "External access: OK"
else
    print_warning "External access failed (HTTP $EXTERNAL_RESPONSE)"
fi

# Test external version endpoint
print_status "Testing external version endpoint..."
EXTERNAL_VERSION=$(curl -s https://app2.sensemy.cloud/version.json 2>/dev/null | jq -r '.buildNumber' 2>/dev/null || echo "failed")
if [ "$EXTERNAL_VERSION" = "$BUILD_NUMBER" ]; then
    print_success "External version endpoint: OK (Build $EXTERNAL_VERSION)"
else
    print_warning "External version endpoint: Expected $BUILD_NUMBER, got $EXTERNAL_VERSION"
    print_status "This might take a moment to propagate through the reverse proxy"
fi

# Step 11: Show deployment summary
echo
print_success "🎉 Deployment Complete!"
echo "=============================="
echo "📦 Version: $BUILD_VERSION"
echo "🔢 Build: $BUILD_NUMBER"
echo "🕒 Built: $BUILD_TIMESTAMP"
echo "🐳 Container: $SERVICE_NAME"
echo "🌐 Local: http://localhost:$UI_PORT"
echo "🌍 External: https://app2.sensemy.cloud"
echo "📋 Version: https://app2.sensemy.cloud/version.json"
echo

# Step 12: Show container logs (last few lines)
print_status "Recent container logs:"
docker compose logs $SERVICE_NAME --tail 10

echo
print_success "Deployment verification complete! 🚀"
echo "You can now test the responsive design with build number $BUILD_NUMBER"

# Return to original directory
cd "$CURRENT_DIR"
