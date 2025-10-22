# Operations Documentation

Deployment, monitoring, and operational procedures for the Smart Parking Platform.

## Overview

This directory contains operational documentation for deploying, monitoring, and maintaining the Smart Parking Platform in production.

## Documentation

### Deployment
- **[Deployment Guide](deployment.md)** - Production deployment procedures with RLS
- **[Deploy Multi-Tenancy](deploy-multi-tenancy.md)** - Multi-tenant deployment specifics

### Monitoring & Observability
- **[Monitoring](monitoring.md)** - Observability, metrics, and alerting
- **[Ops UI](ops-ui.md)** - Operations dashboard guide

### Procedures
- **[Runbooks](runbooks.md)** - Operational runbooks for common issues
- **[Testing Strategy](testing-strategy.md)** - Testing approach and guidelines
- **[Testing Implementation](testing-implementation.md)** - Implementation details

## Quick Start

### Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space

### Initial Deployment

```bash
# Clone repository
git clone <repository-url>
cd v5-smart-parking

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start all services
docker compose up -d

# Check health status
docker compose ps

# View logs
docker compose logs -f api
```

### Service Health Checks

All services include health checks:

```bash
# Check all service health
docker compose ps

# Individual service status
docker inspect parking-api --format='{{.State.Health.Status}}'

# View health check logs
docker inspect parking-api --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

## Service Architecture

```
┌─────────────┐
│   Traefik   │ :80, :443 (Reverse Proxy)
└─────┬───────┘
      │
      ├─── parking-website (:80)
      ├─── parking-api (:8000)
      ├─── parking-contact-api (:8001)
      ├─── parking-device-manager (:3000)
      └─── parking-kuando-ui (:80)

┌──────────────────────────────────┐
│       Core Services              │
├──────────────────────────────────┤
│  parking-postgres    :5432       │
│  parking-redis       :6379       │
│  parking-chirpstack  :8080       │
│  parking-mosquitto   :1883, 9001 │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│       Support Services           │
├──────────────────────────────────┤
│  parking-adminer     :8080       │
│  parking-filebrowser :80         │
└──────────────────────────────────┘
```

## Resource Limits

All services have resource limits configured:

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| api | 1.0 | 512M |
| postgres | 2.0 | 2G |
| redis | 0.5 | 256M |
| chirpstack | 0.5 | 256M |
| mosquitto | 0.5 | 128M |
| traefik | 0.5 | 256M |

Monitor resource usage:

```bash
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

## Backup & Recovery

### Database Backup

```bash
# Manual backup
docker compose exec postgres pg_dump \
  -U parking -d parking \
  --format=custom --file=/tmp/backup.dump

# Copy from container
docker cp parking-postgres:/tmp/backup.dump ./backups/

# Automated daily backups (cron)
0 2 * * * /opt/v5-smart-parking/scripts/backup-database.sh
```

### Database Restore

```bash
# Copy backup to container
docker cp ./backups/backup.dump parking-postgres:/tmp/

# Restore
docker compose exec postgres pg_restore \
  -U parking -d parking \
  --clean --if-exists /tmp/backup.dump
```

## Monitoring

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api

# With timestamps
docker compose logs -f --timestamps api

# Last 100 lines
docker compose logs --tail=100 api
```

### Metrics

Access Grafana dashboards (if configured):
- System Metrics: http://localhost:3000/d/system
- API Metrics: http://localhost:3000/d/api
- Database Metrics: http://localhost:3000/d/postgres

### Alerting

Configure alerts in Grafana or Prometheus for:
- Service down (health check failures)
- High error rate (> 1%)
- High response time (P95 > 500ms)
- High resource usage (> 80%)
- Disk space low (< 20%)

## Common Operations

### Restart Service

```bash
docker compose restart api
```

### Update Service

```bash
# Rebuild and restart
docker compose up -d --build api

# Pull latest image (for external images)
docker compose pull postgres
docker compose up -d postgres
```

### Scale Service

```bash
# Scale API to 3 replicas
docker compose up -d --scale api=3
```

### View Database

Access Adminer:
- URL: http://localhost:8081
- System: PostgreSQL
- Server: postgres
- Username: parking
- Password: (from .env)

### Execute SQL

```bash
docker compose exec postgres psql -U parking -d parking

# Or from file
docker compose exec -T postgres psql -U parking -d parking < script.sql
```

## Troubleshooting

### Service Won't Start

1. Check logs: `docker compose logs service-name`
2. Verify configuration: `docker compose config`
3. Check dependencies: `docker compose ps`
4. Restart dependencies: `docker compose restart postgres redis`

### High Memory Usage

```bash
# Check stats
docker stats

# Restart service
docker compose restart api

# Check for memory leaks
docker compose logs api | grep -i "memory\|oom"
```

### Database Connection Issues

```bash
# Test connection
docker compose exec postgres pg_isready -U parking

# Check connections
docker compose exec postgres psql -U parking -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections
docker compose exec postgres psql -U parking -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';"
```

## Security

### Update Secrets

```bash
# Generate new secret
openssl rand -base64 32 > secrets/jwt_secret_key.txt

# Restart service
docker compose restart api
```

### SSL/TLS Configuration

See Traefik documentation for Let's Encrypt configuration:
- Edit `docker-compose.yml` Traefik service
- Add `--certificatesresolvers.letsencrypt.acme.email=your-email`
- Enable HTTPS redirects

## Next Steps

- Review [Deployment Guide](deployment.md) for production best practices
- Set up [Monitoring](monitoring.md) dashboards
- Familiarize with [Runbooks](runbooks.md) for incident response
- Implement [Testing Strategy](testing-strategy.md)
