#!/bin/bash
# Database backup script for PostgreSQL
# Smart Parking Platform v5.8

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/parking-db-$TIMESTAMP.sql"
BACKUP_FILE_GZ="$BACKUP_FILE.gz"

# Database configuration (from docker-compose.yml)
DB_SERVICE="postgres"  # Service name in docker-compose.yml
DB_CONTAINER="parking-postgres"  # Actual container name
DB_USER="parking"
DB_NAME="parking"

# Retention policy
KEEP_DAYS=30
KEEP_WEEKLY=12
KEEP_MONTHLY=12

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

# ============================================================================
# Backup Functions
# ============================================================================

check_prerequisites() {
    log "Checking prerequisites..."

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running!"
        exit 1
    fi

    # Check if database container is running (use service name)
    if ! docker compose ps "$DB_SERVICE" 2>&1 | grep -q "Up\|healthy"; then
        log_error "Database container is not running!"
        exit 1
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    log "✓ Prerequisites OK"
}

create_backup() {
    log "Creating database backup..."
    log "Database: $DB_NAME"
    log "Container: $DB_CONTAINER"
    log "Output: $BACKUP_FILE_GZ"

    # Create SQL dump using pg_dump (use service name for docker compose exec)
    if docker compose exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"; then
        log "✓ SQL dump created"
    else
        log_error "Failed to create SQL dump!"
        rm -f "$BACKUP_FILE"
        exit 1
    fi

    # Compress backup
    log "Compressing backup..."
    if gzip "$BACKUP_FILE"; then
        log "✓ Backup compressed"
    else
        log_error "Failed to compress backup!"
        exit 1
    fi

    # Verify backup file exists and has content
    if [ -f "$BACKUP_FILE_GZ" ] && [ -s "$BACKUP_FILE_GZ" ]; then
        local size=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
        log "✓ Backup created successfully: $size"
    else
        log_error "Backup file is empty or missing!"
        exit 1
    fi
}

create_metadata() {
    local metadata_file="$BACKUP_FILE_GZ.meta"

    log "Creating backup metadata..."

    cat > "$metadata_file" <<EOF
Backup Metadata
===============
Timestamp: $(date -Iseconds)
Database: $DB_NAME
Container: $DB_CONTAINER
Backup File: $(basename "$BACKUP_FILE_GZ")
Size: $(du -h "$BACKUP_FILE_GZ" | cut -f1)

Git Information:
$(cd "$PROJECT_ROOT" && git log -1 --pretty=format:"Commit: %H%nAuthor: %an%nDate: %ad%nMessage: %s" 2>/dev/null || echo "Not a git repository")

Database Statistics:
$(docker compose exec -T "$DB_SERVICE" psql -U "$DB_USER" "$DB_NAME" -c "SELECT schemaname, tablename, n_tup_ins as inserts, n_tup_upd as updates, n_tup_del as deletes FROM pg_stat_user_tables ORDER BY n_tup_ins DESC LIMIT 10;" 2>/dev/null || echo "Could not retrieve statistics")
EOF

    log "✓ Metadata created"
}

cleanup_old_backups() {
    log "Cleaning up old backups..."

    cd "$BACKUP_DIR"

    # Keep all backups from last KEEP_DAYS days
    log "  Keeping daily backups from last $KEEP_DAYS days..."
    find . -name "parking-db-*.sql.gz" -type f -mtime +$KEEP_DAYS ! -name "*-weekly-*" ! -name "*-monthly-*" -delete 2>/dev/null || true

    # Keep KEEP_WEEKLY weekly backups (Sundays)
    log "  Keeping last $KEEP_WEEKLY weekly backups..."
    ls -t parking-db-*-weekly-*.sql.gz 2>/dev/null | tail -n +$((KEEP_WEEKLY + 1)) | xargs -r rm -f

    # Keep KEEP_MONTHLY monthly backups (first day of month)
    log "  Keeping last $KEEP_MONTHLY monthly backups..."
    ls -t parking-db-*-monthly-*.sql.gz 2>/dev/null | tail -n +$((KEEP_MONTHLY + 1)) | xargs -r rm -f

    local remaining=$(find . -name "parking-db-*.sql.gz" -type f | wc -l)
    log "✓ Cleanup complete ($remaining backups remaining)"
}

tag_special_backups() {
    local dow=$(date +%u)  # Day of week (1=Monday, 7=Sunday)
    local dom=$(date +%d)  # Day of month

    # Tag weekly backup (Sunday)
    if [ "$dow" -eq 7 ]; then
        local weekly_file="${BACKUP_FILE_GZ/.sql.gz/-weekly.sql.gz}"
        cp "$BACKUP_FILE_GZ" "$weekly_file"
        log "✓ Weekly backup tagged"
    fi

    # Tag monthly backup (first day of month)
    if [ "$dom" -eq 01 ]; then
        local monthly_file="${BACKUP_FILE_GZ/.sql.gz/-monthly.sql.gz}"
        cp "$BACKUP_FILE_GZ" "$monthly_file"
        log "✓ Monthly backup tagged"
    fi
}

# ============================================================================
# Main Backup Flow
# ============================================================================

main() {
    log "========================================"
    log "Database Backup"
    log "========================================"

    check_prerequisites
    create_backup
    create_metadata
    tag_special_backups
    cleanup_old_backups

    log ""
    log "✓ Backup completed successfully!"
    log "Backup file: $BACKUP_FILE_GZ"
    log ""
}

# ============================================================================
# Error Handling
# ============================================================================

trap 'log_error "Backup failed!"; exit 1' ERR

# ============================================================================
# Entry Point
# ============================================================================

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Creates a PostgreSQL database backup with compression and metadata."
            echo ""
            echo "Options:"
            echo "  --help    Show this help message"
            echo ""
            echo "Retention Policy:"
            echo "  Daily:    Last $KEEP_DAYS days"
            echo "  Weekly:   Last $KEEP_WEEKLY weeks (Sundays)"
            echo "  Monthly:  Last $KEEP_MONTHLY months (1st day)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

main
