#!/bin/bash
# Rollback script for Smart Parking Platform
# Reverts to a previous deployment state

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_FILE="$PROJECT_ROOT/logs/rollback-$(date +%Y%m%d-%H%M%S).log"

# Services to rollback
SERVICES=("api")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $*" | tee -a "$LOG_FILE"
}

check_health() {
    local service=$1
    local retries=30

    log "Checking health of $service..."

    for i in $(seq 1 $retries); do
        if docker compose ps "$service" | grep -q "healthy"; then
            log "✓ $service is healthy"
            return 0
        fi

        if docker compose ps "$service" | grep -q "Up"; then
            log "  Waiting for health check... ($i/$retries)"
        else
            log_error "$service is not running!"
            return 1
        fi

        sleep 2
    done

    log_error "$service failed health check"
    return 1
}

# ============================================================================
# Git Rollback
# ============================================================================

rollback_to_commit() {
    local target_commit=$1

    log "========================================"
    log "Rolling back to commit: $target_commit"
    log "========================================"

    cd "$PROJECT_ROOT"

    # Verify commit exists
    if ! git cat-file -e "$target_commit^{commit}" 2>/dev/null; then
        log_error "Commit $target_commit does not exist!"
        return 1
    fi

    # Show commit info
    log_info "Target commit details:"
    git log -1 --pretty=format:"  Commit: %H%n  Author: %an <%ae>%n  Date: %ad%n  Message: %s%n" "$target_commit"

    # Confirm rollback
    echo ""
    read -p "Are you sure you want to rollback to this commit? (yes/NO) " -r
    echo ""
    if [[ ! $REPLY == "yes" ]]; then
        log_warning "Rollback cancelled by user"
        exit 0
    fi

    # Create backup branch
    local backup_branch="backup-before-rollback-$(date +%Y%m%d-%H%M%S)"
    log "Creating backup branch: $backup_branch"
    git branch "$backup_branch"

    # Perform rollback
    log "Rolling back code..."
    if git reset --hard "$target_commit"; then
        log "✓ Code rolled back successfully"
    else
        log_error "Failed to rollback code!"
        return 1
    fi

    return 0
}

# ============================================================================
# Database Rollback
# ============================================================================

list_database_backups() {
    log "========================================"
    log "Available Database Backups"
    log "========================================"

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR"/*.sql.gz 2>/dev/null)" ]; then
        log_warning "No database backups found in $BACKUP_DIR"
        return 1
    fi

    local backups=($(ls -t "$BACKUP_DIR"/parking-db-*.sql.gz))
    local count=1

    for backup in "${backups[@]}"; do
        local basename=$(basename "$backup")
        local size=$(du -h "$backup" | cut -f1)
        local date=$(stat -c %y "$backup" | cut -d. -f1)

        echo "  [$count] $basename"
        echo "      Size: $size"
        echo "      Date: $date"

        # Show metadata if available
        if [ -f "$backup.meta" ]; then
            local commit=$(grep "^Commit:" "$backup.meta" | head -1 | cut -d: -f2 | xargs)
            if [ -n "$commit" ]; then
                echo "      Git: ${commit:0:7}"
            fi
        fi

        echo ""
        ((count++))

        # Only show last 10 backups
        if [ $count -gt 10 ]; then
            log_info "Showing last 10 backups. Total: ${#backups[@]}"
            break
        fi
    done

    return 0
}

restore_database_backup() {
    local backup_file=$1

    log "========================================"
    log "Restoring Database Backup"
    log "========================================"

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log "Backup file: $(basename "$backup_file")"
    log "Size: $(du -h "$backup_file" | cut -f1)"

    # Confirm restore
    echo ""
    log_warning "This will OVERWRITE the current database!"
    read -p "Are you sure you want to restore this backup? (yes/NO) " -r
    echo ""
    if [[ ! $REPLY == "yes" ]]; then
        log_warning "Database restore cancelled by user"
        return 0
    fi

    # Create a backup of current database first
    log "Creating backup of current database before restore..."
    if bash "$SCRIPT_DIR/backup-database.sh"; then
        log "✓ Current database backed up"
    else
        log_error "Failed to backup current database!"
        read -p "Continue with restore anyway? (yes/NO) " -r
        echo ""
        if [[ ! $REPLY == "yes" ]]; then
            return 1
        fi
    fi

    # Decompress backup
    log "Decompressing backup..."
    local temp_sql="${backup_file%.gz}"
    if gunzip -c "$backup_file" > "$temp_sql"; then
        log "✓ Backup decompressed"
    else
        log_error "Failed to decompress backup!"
        rm -f "$temp_sql"
        return 1
    fi

    # Restore database
    log "Restoring database..."
    if docker compose exec -T parking-postgres psql -U parking parking < "$temp_sql"; then
        log "✓ Database restored successfully"
    else
        log_error "Failed to restore database!"
        rm -f "$temp_sql"
        return 1
    fi

    # Cleanup temp file
    rm -f "$temp_sql"

    log "✓ Database rollback complete"
    return 0
}

# ============================================================================
# Service Rollback
# ============================================================================

rollback_services() {
    log "========================================"
    log "Rolling back Services"
    log "========================================"

    cd "$PROJECT_ROOT"

    # Rebuild images with current code
    log "Rebuilding Docker images..."
    if docker compose build "${SERVICES[@]}"; then
        log "✓ Images rebuilt"
    else
        log_error "Failed to rebuild images!"
        return 1
    fi

    # Restart services
    log "Restarting services..."
    for service in "${SERVICES[@]}"; do
        log "  Restarting $service..."

        if docker compose up -d --force-recreate --no-deps "$service"; then
            if check_health "$service"; then
                log "✓ $service rolled back successfully"
            else
                log_error "$service failed health check after rollback!"
                return 1
            fi
        else
            log_error "Failed to restart $service!"
            return 1
        fi

        sleep 3
    done

    log "✓ All services rolled back successfully"
    return 0
}

# ============================================================================
# Interactive Menu
# ============================================================================

show_menu() {
    echo ""
    echo "========================================"
    echo "Smart Parking Platform - Rollback Tool"
    echo "========================================"
    echo ""
    echo "What would you like to rollback?"
    echo ""
    echo "  [1] Code + Services (Git rollback)"
    echo "  [2] Database only"
    echo "  [3] Code + Services + Database (Full rollback)"
    echo "  [4] Show recent commits"
    echo "  [5] Show database backups"
    echo "  [q] Quit"
    echo ""
    read -p "Select option: " -n 1 -r
    echo ""
    return 0
}

rollback_code_only() {
    # Show recent commits
    log "Recent commits:"
    git log --oneline -10

    echo ""
    read -p "Enter commit hash to rollback to: " commit_hash

    if rollback_to_commit "$commit_hash"; then
        if rollback_services; then
            log ""
            log "✓ Code rollback complete!"
        else
            log_error "Service rollback failed!"
            return 1
        fi
    else
        log_error "Code rollback failed!"
        return 1
    fi
}

rollback_database_only() {
    if ! list_database_backups; then
        return 1
    fi

    echo ""
    read -p "Enter backup number or full path: " backup_choice

    # If it's a number, get the file from the list
    if [[ "$backup_choice" =~ ^[0-9]+$ ]]; then
        local backups=($(ls -t "$BACKUP_DIR"/parking-db-*.sql.gz))
        local index=$((backup_choice - 1))

        if [ $index -lt 0 ] || [ $index -ge ${#backups[@]} ]; then
            log_error "Invalid backup number!"
            return 1
        fi

        backup_file="${backups[$index]}"
    else
        backup_file="$backup_choice"
    fi

    restore_database_backup "$backup_file"
}

rollback_full() {
    log "========================================"
    log "Full Rollback (Code + Database)"
    log "========================================"

    if rollback_code_only; then
        echo ""
        log "Code rolled back. Now rolling back database..."
        rollback_database_only
    else
        log_error "Code rollback failed, skipping database rollback"
        return 1
    fi
}

# ============================================================================
# Main Function
# ============================================================================

main() {
    mkdir -p "$(dirname "$LOG_FILE")"

    log "Rollback tool started"
    log "Log file: $LOG_FILE"

    # Check prerequisites
    cd "$PROJECT_ROOT"

    if ! docker info &> /dev/null; then
        log_error "Docker is not running!"
        exit 1
    fi

    # Interactive menu
    while true; do
        show_menu

        case $REPLY in
            1)
                rollback_code_only
                ;;
            2)
                rollback_database_only
                ;;
            3)
                rollback_full
                ;;
            4)
                log "Recent commits:"
                git log --oneline --graph -20
                ;;
            5)
                list_database_backups
                ;;
            q|Q)
                log "Exiting rollback tool"
                exit 0
                ;;
            *)
                log_warning "Invalid option"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..." -r
    done
}

# ============================================================================
# Error Handling
# ============================================================================

trap 'log_error "Rollback failed! Check log: $LOG_FILE"' ERR

# ============================================================================
# Entry Point
# ============================================================================

main
