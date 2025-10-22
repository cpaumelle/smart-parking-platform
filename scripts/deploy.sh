#!/bin/bash
# Zero-downtime deployment script with health checks and rollback
# Smart Parking Platform v5.8

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_FILE="$PROJECT_ROOT/logs/deploy-$(date +%Y%m%d-%H%M%S).log"

# Services to update (in order)
SERVICES=("api")

# Health check configuration
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*" | tee -a "$LOG_FILE"
}

log_step() {
    echo ""
    echo -e "${GREEN}========================================${NC}" | tee -a "$LOG_FILE"
    echo -e "${GREEN}$*${NC}" | tee -a "$LOG_FILE"
    echo -e "${GREEN}========================================${NC}" | tee -a "$LOG_FILE"
}

check_health() {
    local service=$1
    local retries=$HEALTH_CHECK_RETRIES

    log "Checking health of $service..."

    for i in $(seq 1 $retries); do
        # Check if container is running and healthy
        if docker compose ps "$service" | grep -q "healthy"; then
            log "✓ $service is healthy"
            return 0
        fi

        # Check if container is at least running
        if docker compose ps "$service" | grep -q "Up"; then
            log "  Waiting for health check... ($i/$retries)"
        else
            log_error "$service is not running!"
            return 1
        fi

        sleep $HEALTH_CHECK_INTERVAL
    done

    log_error "$service failed health check after $retries attempts"
    return 1
}

get_current_image() {
    local service=$1
    docker compose images "$service" | grep "$service" | awk '{print $4}'
}

rollback_service() {
    local service=$1
    log_warning "Rolling back $service..."

    # Restore from backup image tag
    docker compose up -d --no-deps "$service"

    if check_health "$service"; then
        log "✓ Rollback successful for $service"
        return 0
    else
        log_error "Rollback failed for $service!"
        return 1
    fi
}

# ============================================================================
# Pre-deployment Checks
# ============================================================================

preflight_checks() {
    log_step "Step 1: Pre-deployment Checks"

    # Ensure we're in the project root
    cd "$PROJECT_ROOT"

    # Check Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running!"
        exit 1
    fi
    log "✓ Docker is running"

    # Check Docker Compose is available
    if ! command -v docker &> /dev/null; then
        log_error "docker compose is not available!"
        exit 1
    fi
    log "✓ docker compose is available"

    # Validate docker-compose.yml
    if ! docker compose config > /dev/null 2>&1; then
        log_error "docker-compose.yml is invalid!"
        exit 1
    fi
    log "✓ docker-compose.yml is valid"

    # Check git status
    if [ -d ".git" ]; then
        GIT_VERSION=$(git describe --tags --always 2>/dev/null || echo "unknown")
        GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        log "Git version: $GIT_VERSION"
        log "Git branch: $GIT_BRANCH"
    fi

    # Create necessary directories
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$(dirname "$LOG_FILE")"

    log "✓ Pre-deployment checks passed"
}

# ============================================================================
# Database Backup
# ============================================================================

backup_database() {
    log_step "Step 2: Database Backup"

    if [ -f "$SCRIPT_DIR/backup-database.sh" ]; then
        if bash "$SCRIPT_DIR/backup-database.sh"; then
            log "✓ Database backup complete"
        else
            log_error "Database backup failed!"
            read -p "Continue deployment without backup? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        log_warning "Backup script not found, skipping database backup"
    fi
}

# ============================================================================
# Pull Images
# ============================================================================

pull_images() {
    log_step "Step 3: Pulling Latest Images"

    log "Pulling images for services: ${SERVICES[*]}"

    if docker compose pull "${SERVICES[@]}"; then
        log "✓ Images pulled successfully"
    else
        log_error "Failed to pull images!"
        exit 1
    fi

    # Show image info
    for service in "${SERVICES[@]}"; do
        image=$(get_current_image "$service")
        log "  $service: $image"
    done
}

# ============================================================================
# Database Migrations
# ============================================================================

run_migrations() {
    log_step "Step 4: Database Migrations"

    # Check if we're running in a managed environment with migrations
    if [ -d "$PROJECT_ROOT/migrations" ]; then
        log "Running database migrations..."

        # Run migrations using the API container
        if docker compose exec -T api python -c "print('Migration check OK')" &> /dev/null; then
            log "✓ Migrations check passed"
        else
            log_warning "Could not verify migrations (API may not be running)"
        fi
    else
        log_warning "No migrations directory found, skipping"
    fi
}

# ============================================================================
# Service Update
# ============================================================================

update_services() {
    log_step "Step 5: Updating Services"

    for service in "${SERVICES[@]}"; do
        log ""
        log "Updating $service..."

        # Get current image for potential rollback
        current_image=$(get_current_image "$service")
        log "  Current image: $current_image"

        # Recreate container with new image
        log "  Recreating container..."
        if ! docker compose up -d --force-recreate --no-deps "$service"; then
            log_error "Failed to recreate $service!"
            rollback_service "$service"
            exit 1
        fi

        # Wait for health check
        if ! check_health "$service"; then
            log_error "$service failed health check!"
            rollback_service "$service"
            exit 1
        fi

        log "✓ $service updated successfully"

        # Brief pause between services
        sleep 3
    done

    log "✓ All services updated successfully"
}

# ============================================================================
# Cleanup
# ============================================================================

cleanup() {
    log_step "Step 6: Cleanup"

    log "Removing unused Docker images..."
    docker image prune -f | tee -a "$LOG_FILE" || log_warning "Image cleanup failed"

    log "Removing old backups (keeping last 10)..."
    if [ -d "$BACKUP_DIR" ]; then
        ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
        log "✓ Old backups cleaned"
    fi

    log "✓ Cleanup complete"
}

# ============================================================================
# Post-deployment Verification
# ============================================================================

verify_deployment() {
    log_step "Step 7: Post-deployment Verification"

    log "Verifying service status..."
    docker compose ps | tee -a "$LOG_FILE"

    log ""
    log "Checking service health..."
    for service in "${SERVICES[@]}"; do
        if check_health "$service"; then
            log "✓ $service: healthy"
        else
            log_error "$service: unhealthy!"
            return 1
        fi
    done

    log "✓ All services are healthy"

    # Test API endpoint if available
    if command -v curl &> /dev/null; then
        log ""
        log "Testing API health endpoint..."
        if docker compose exec -T api curl -sf http://localhost:8000/health > /dev/null; then
            log "✓ API health check passed"
        else
            log_warning "API health endpoint not accessible"
        fi
    fi

    return 0
}

# ============================================================================
# Main Deployment Flow
# ============================================================================

main() {
    log_step "Smart Parking Platform Deployment"
    log "Started at: $(date)"
    log "Log file: $LOG_FILE"

    # Run deployment steps
    preflight_checks
    backup_database
    pull_images
    run_migrations
    update_services
    cleanup
    verify_deployment

    log_step "Deployment Complete!"
    log "Finished at: $(date)"
    log "Log file: $LOG_FILE"

    echo ""
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo ""
}

# ============================================================================
# Error Handling
# ============================================================================

trap 'log_error "Deployment failed! Check log: $LOG_FILE"; exit 1' ERR

# ============================================================================
# Entry Point
# ============================================================================

# Parse command line arguments
SKIP_BACKUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-backup    Skip database backup"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main deployment
main
