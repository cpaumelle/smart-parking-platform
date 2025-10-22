# Deployment Scripts

Automation scripts for deploying, backing up, and rolling back the Smart Parking Platform.

## 📋 Scripts Overview

| Script | Purpose | Usage |
|--------|---------|-------|
| `deploy.sh` | Zero-downtime deployment with health checks | `./scripts/deploy.sh` |
| `backup-database.sh` | PostgreSQL database backup with compression | `./scripts/backup-database.sh` |
| `rollback.sh` | Interactive rollback tool (code + database) | `./scripts/rollback.sh` |

## 🚀 Deployment

### Basic Deployment

```bash
# Deploy latest changes
./scripts/deploy.sh
```

### Skip Database Backup

```bash
# Skip backup (faster, less safe)
./scripts/deploy.sh --skip-backup
```

### What It Does

1. **Pre-flight checks**: Validates Docker, docker-compose.yml
2. **Database backup**: Creates compressed backup in `backups/`
3. **Pull images**: Updates Docker images to latest
4. **Run migrations**: Applies database schema changes
5. **Update services**: Recreates containers with health checks
6. **Cleanup**: Removes unused Docker images and old backups
7. **Verification**: Tests all services are healthy

### Health Checks

The deployment script waits for services to pass health checks before proceeding. If a service fails health check, it automatically triggers a rollback.

**Health check retries**: 30 attempts (60 seconds total)

## 💾 Database Backup

### Manual Backup

```bash
# Create database backup
./scripts/backup-database.sh
```

### Backup Files

Backups are stored in `backups/` directory:

```
backups/
├── parking-db-20251022-102327.sql.gz       # Regular backup
├── parking-db-20251022-102327.sql.gz.meta  # Backup metadata
├── parking-db-20251022-weekly.sql.gz       # Weekly backup (Sundays)
└── parking-db-20251022-monthly.sql.gz      # Monthly backup (1st day)
```

### Retention Policy

- **Daily backups**: Last 30 days
- **Weekly backups**: Last 12 weeks (Sundays)
- **Monthly backups**: Last 12 months (1st day of month)

### Backup Metadata

Each backup includes a `.meta` file with:
- Timestamp and database info
- Git commit hash and message
- Database statistics (table sizes, row counts)

## ⏮️ Rollback

### Interactive Rollback Tool

```bash
# Launch interactive rollback menu
./scripts/rollback.sh
```

### Rollback Options

1. **Code + Services**: Rollback to previous Git commit and restart services
2. **Database Only**: Restore from a database backup
3. **Full Rollback**: Both code and database
4. **Show Commits**: View recent Git commits
5. **Show Backups**: List available database backups

### Example Session

```bash
$ ./scripts/rollback.sh

========================================
Smart Parking Platform - Rollback Tool
========================================

What would you like to rollback?

  [1] Code + Services (Git rollback)
  [2] Database only
  [3] Code + Services + Database (Full rollback)
  [4] Show recent commits
  [5] Show database backups
  [q] Quit

Select option: 4

Recent commits:
b933717 feat: Implement Docker secrets management (Phase 4.2)
d6f3b67 feat: Implement tenant-aware rate limiting (Phase 4.1)
eeaabb7 feat: Implement request tracing with context (Phase 3.2)
```

### Safety Features

- **Confirmation prompts**: Requires explicit "yes" for destructive operations
- **Backup branches**: Creates Git backup branches before rollback
- **Pre-rollback backup**: Backs up current database before restoring
- **Health checks**: Verifies services after rollback

## 📊 Logs

All scripts create detailed logs in `logs/` directory:

```
logs/
├── deploy-20251022-102327.log
├── rollback-20251022-145530.log
└── ...
```

Logs include:
- Timestamps for all operations
- Health check results
- Error messages and stack traces
- Service status before/after

## 🔧 Configuration

### Docker Compose Services

Services are defined in `docker-compose.yml`. The deployment script updates services in this order:

1. `api` - Main application backend

Additional services can be added to the `SERVICES` array in `deploy.sh`.

### Health Check Settings

```bash
# In deploy.sh
HEALTH_CHECK_RETRIES=30      # Number of retry attempts
HEALTH_CHECK_INTERVAL=2      # Seconds between retries
```

### Backup Retention

```bash
# In backup-database.sh
KEEP_DAYS=30        # Daily backups retention
KEEP_WEEKLY=12      # Weekly backups retention
KEEP_MONTHLY=12     # Monthly backups retention
```

## 🐛 Troubleshooting

### Deployment Fails

1. Check logs: `tail -f logs/deploy-*.log`
2. Verify Docker is running: `docker info`
3. Check service health: `docker compose ps`
4. View service logs: `docker compose logs api`

### Health Check Timeout

If services consistently fail health checks:

1. Increase `HEALTH_CHECK_RETRIES` in `deploy.sh`
2. Check service logs for startup errors
3. Verify resource limits in `docker-compose.yml`

### Backup Fails

1. Check disk space: `df -h`
2. Verify database is running: `docker compose ps postgres`
3. Check database permissions

### Rollback Fails

1. Check Git repository is clean: `git status`
2. Verify backups exist: `ls -lh backups/`
3. Ensure Docker has permission to rebuild images

## 📝 Best Practices

### Before Deployment

- [ ] Test on staging environment first
- [ ] Review changes: `git log --oneline -10`
- [ ] Check disk space: `df -h`
- [ ] Notify users of maintenance window

### During Deployment

- [ ] Monitor logs in real-time
- [ ] Watch service health: `watch docker compose ps`
- [ ] Check API responses: `curl http://localhost:8000/health`

### After Deployment

- [ ] Verify all services healthy
- [ ] Test critical functionality
- [ ] Monitor error rates and performance
- [ ] Keep deployment log for records

### Regular Maintenance

- [ ] Weekly: Review backup retention
- [ ] Monthly: Test rollback procedure
- [ ] Quarterly: Clean old Docker images
- [ ] Yearly: Rotate secrets and credentials

## 🔐 Security

### Secrets Management

Secrets are managed via Docker secrets (see `secrets/README.md`):
- Never commit secrets to Git
- Use Docker secrets or environment variables
- Rotate secrets regularly

### Backup Security

- Backups contain sensitive data
- Store backups securely with encryption
- Restrict access to backup files (chmod 600)
- Consider off-site backup storage

## 📞 Support

For issues or questions:

1. Check logs first: `logs/deploy-*.log`
2. Review this README
3. See main project documentation in `docs/`
4. Create an issue on GitHub

## 🔗 Related Documentation

- [Docker Secrets](../secrets/README.md) - Secret management
- [Implementation Plan](../docs/changelog/IMPLEMENTATION_PLAN_v5.8.md) - v5.8 roadmap
- [Operations Guide](../docs/operations/) - Detailed operations procedures
