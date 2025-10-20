# Operational Runbooks - Smart Parking Platform v5.3

**Purpose:** Quick reference guide for common operational incidents and procedures.

**Last Updated:** 2025-10-20

---

## Table of Contents

1. [Health Check Procedures](#health-check-procedures)
2. [ChirpStack Down](#chirpstack-down)
3. [Redis Full / Out of Memory](#redis-full)
4. [PostgreSQL Failover](#postgresql-failover)
5. [Downlink Queue Issues](#downlink-queue-issues)
6. [High Orphan Device Count](#high-orphan-device-count)
7. [Rate Limiting Alerts](#rate-limiting-alerts)
8. [Backup & Restore](#backup--restore)

---

## Health Check Procedures

### Quick Health Check

```bash
# Overall health
curl https://api.verdegris.eu/health | jq

# Readiness (can serve traffic?)
curl https://api.verdegris.eu/health/ready | jq

# Liveness (process alive?)
curl https://api.verdegris.eu/health/live | jq
```

### Component-Specific Checks

```bash
# Database connectivity
docker compose exec postgres psql -U parking_user -d parking -c "SELECT 1"

# Redis connectivity
docker compose exec redis redis-cli PING

# ChirpStack connectivity (check MQTT)
docker compose logs chirpstack --tail 50

# Downlink queue depth
curl https://api.verdegris.eu/api/v1/downlinks/queue/metrics | jq '.queue'
```

### Metrics Endpoint

```bash
# Prometheus metrics
curl https://api.verdegris.eu/metrics

# Filter specific metrics
curl https://api.verdegris.eu/metrics | grep uplink_requests_total
```

---

## ChirpStack Down

**Symptoms:**
- `/health/ready` returns 503
- No uplinks being processed
- ChirpStack MQTT connection shows "not connected"

### Diagnosis

```bash
# Check ChirpStack logs
docker compose logs chirpstack --tail 100

# Check MQTT broker
docker compose logs mosquitto --tail 50

# Test MQTT connectivity
mosquitto_sub -h localhost -p 1883 -t '#' -u admin -P password
```

### Resolution

#### 1. Restart ChirpStack

```bash
docker compose restart chirpstack
docker compose logs chirpstack --follow
```

#### 2. Check Configuration

```bash
# Verify ChirpStack can reach database
docker compose exec chirpstack cat /etc/chirpstack/chirpstack.toml | grep postgresql

# Verify MQTT configuration
docker compose exec chirpstack cat /etc/chirpstack/chirpstack.toml | grep mqtt
```

#### 3. Verify Recovery

```bash
# Wait 30 seconds, then check health
sleep 30
curl https://api.verdegris.eu/health/ready | jq '.checks.chirpstack_mqtt'

# Should show "ready"
```

### Impact

- **Uplinks:** Queued in MQTT broker (retained for up to 24h)
- **Downlinks:** Queued in Redis (processed when ChirpStack recovers)
- **No data loss** if recovered within 24 hours

---

## Redis Full / Out of Memory

**Symptoms:**
- OOM errors in logs
- `/health/ready` shows Redis "not ready"
- State manager operations failing

### Diagnosis

```bash
# Check Redis memory usage
docker compose exec redis redis-cli INFO memory | grep used_memory_human

# Check maxmemory config
docker compose exec redis redis-cli CONFIG GET maxmemory

# Check eviction policy
docker compose exec redis redis-cli CONFIG GET maxmemory-policy
```

### Resolution

#### 1. Immediate: Flush Non-Critical Keys

```bash
# Clear old session data (if using Redis for sessions)
docker compose exec redis redis-cli --scan --pattern 'session:*' | xargs redis-cli DEL

# Clear old orphan device tracking (older than 30 days)
# Manual cleanup - review before executing
```

#### 2. Increase Memory Limit

```yaml
# docker-compose.yml
services:
  redis:
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

```bash
docker compose up -d redis
```

#### 3. Enable Persistence (if not already)

```yaml
services:
  redis:
    command: redis-server --save 60 1000 --maxmemory 2gb
    volumes:
      - redis_data:/data
```

### Prevention

- Set `maxmemory-policy allkeys-lru` for automatic eviction
- Monitor Redis memory usage in Prometheus
- Set alerts at 80% memory usage

---

## PostgreSQL Failover

**Symptoms:**
- Database connection errors
- `/health/ready` shows database "not ready"
- Webhooks being spooled to `/var/spool/parking-uplinks/`

### Diagnosis

```bash
# Check database connectivity
docker compose exec api python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://parking_user:password@postgres:5432/parking').fetchval('SELECT 1'))"

# Check PostgreSQL logs
docker compose logs postgres --tail 100
```

### Resolution

#### 1. Restart PostgreSQL

```bash
docker compose restart postgres

# Wait for startup
docker compose logs postgres --follow

# Look for "database system is ready to accept connections"
```

#### 2. Check Connection Pool

```bash
# View pool stats in health endpoint
curl https://api.verdegris.eu/health | jq '.stats.database'
```

#### 3. Drain Webhook Spool

```bash
# Check spool depth
ls -1 /var/spool/parking-uplinks/pending/ | wc -l

# Webhooks will automatically drain once DB is back
# Monitor progress:
watch -n 5 'ls -1 /var/spool/parking-uplinks/pending/ | wc -l'
```

### Recovery Verification

```bash
# Verify database health
curl https://api.verdegris.eu/health/ready | jq '.checks.database'

# Verify no webhooks in spool
ls /var/spool/parking-uplinks/pending/

# Check for any dead-lettered webhooks
ls /var/spool/parking-uplinks/dead-letter/
```

---

## Downlink Queue Issues

### High Queue Depth

**Symptoms:**
- `downlink_queue_depth` > 100
- Slow display updates
- Increasing latency

#### Diagnosis

```bash
# Check queue metrics
curl https://api.verdegris.eu/api/v1/downlinks/queue/metrics | jq

# Check worker status
curl https://api.verdegris.eu/health/live | jq '.checks.downlink_worker'
```

#### Resolution

```bash
# Restart downlink worker (via API restart)
docker compose restart api

# Or increase rate limits (if bottleneck is ChirpStack)
# Edit src/downlink_queue.py:
# DEFAULT_GATEWAY_LIMIT_PER_MIN = 60  # Increase from 30
```

### Dead-Letter Queue Growing

**Symptoms:**
- `downlink_dead_letter_total` increasing
- Displays not updating

#### Diagnosis

```bash
# Check dead-letter depth
curl https://api.verdegris.eu/api/v1/downlinks/queue/metrics | jq '.queue.dead_letter_depth'

# Inspect Redis dead-letter queue
docker compose exec redis redis-cli LRANGE dl:dead 0 -1
```

#### Resolution

```bash
# Identify common failure pattern
docker compose exec redis redis-cli LRANGE dl:dead 0 10 | jq '.last_error'

# Fix root cause (e.g., invalid device EUI, gateway offline)

# Retry dead-lettered commands (manual)
# Move from dead-letter back to pending:
docker compose exec redis redis-cli RPOPLPUSH dl:dead dl:pending
```

---

## High Orphan Device Count

**Symptoms:**
- `orphan_devices_gauge` > 50
- Frequent "ORPHAN device" log messages

### Diagnosis

```bash
# Query orphan devices
curl https://api.verdegris.eu/api/v1/devices/orphans | jq

# Check last_seen timestamps
docker compose exec postgres psql -U parking_user -d parking -c "
SELECT dev_eui, first_seen, last_seen, uplink_count
FROM orphan_devices
WHERE assigned_to_space_id IS NULL
ORDER BY uplink_count DESC
LIMIT 10;"
```

### Resolution

#### 1. Assign Devices to Spaces

```bash
# Via API
curl -X POST https://api.verdegris.eu/api/v1/spaces/{space_id}/sensor \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"device_eui": "0004a30b001a2b3c"}'
```

#### 2. Delete Inactive Orphans

```sql
-- Devices not seen in 30 days
DELETE FROM orphan_devices
WHERE last_seen < NOW() - INTERVAL '30 days'
AND assigned_to_space_id IS NULL;
```

---

## Rate Limiting Alerts

**Symptoms:**
- `rate_limit_rejections_total` increasing
- 429 responses in logs
- Clients reporting "Too Many Requests"

### Diagnosis

```bash
# Check rate limit rejections by tenant
curl https://api.verdegris.eu/metrics | grep rate_limit_rejections_total

# Check Redis rate limit keys
docker compose exec redis redis-cli KEYS 'rate_limit:*'
```

### Resolution

#### 1. Identify Offending Client

```bash
# Check logs for tenant_id with high rejection rate
docker compose logs api | grep "429" | grep tenant_id
```

#### 2. Temporarily Increase Limits

```python
# src/rate_limit.py
DEFAULT_REQUESTS_PER_MINUTE = 120  # Increase from 60
```

#### 3. Contact Tenant

- Inform tenant of rate limit
- Suggest batching requests
- Implement exponential backoff in client

---

## Backup & Restore

### Nightly Backup Procedure

```bash
#!/bin/bash
# backup-parking-db.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/parking"

# Create backup directory
mkdir -p $BACKUP_DIR

# PostgreSQL dump
docker compose exec -T postgres pg_dump -U parking_user parking > \
  $BACKUP_DIR/parking_${DATE}.sql

# Compress
gzip $BACKUP_DIR/parking_${DATE}.sql

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/parking_${DATE}.sql.gz \
  s3://verdegris-backups/parking/

# Retention: Keep last 7 days locally, 30 days in S3
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

### Restore Procedure

```bash
# Stop API to prevent writes
docker compose stop api

# Restore from backup
gunzip parking_20251020_120000.sql.gz
docker compose exec -T postgres psql -U parking_user -d parking < \
  parking_20251020_120000.sql

# Restart API
docker compose start api

# Verify restoration
curl https://api.verdegris.eu/health | jq
```

### Quarterly Restore Drill

- **Schedule:** Last Sunday of each quarter
- **Procedure:**
  1. Restore to staging environment
  2. Run integration tests
  3. Verify data integrity
  4. Document any issues

---

## SLO Monitoring

### Key SLOs

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Actuation Latency (p95) | < 5s | > 10s |
| Downlink Success Rate | > 99% | < 95% |
| API Availability | > 99.9% | < 99% |
| Uplink Processing Rate | > 200 msg/s | < 100 msg/s |

### Prometheus Alerts

```yaml
# alerts.yml
groups:
  - name: parking_slos
    rules:
      - alert: HighActuationLatency
        expr: histogram_quantile(0.95, actuation_latency_seconds) > 10
        for: 5m
        annotations:
          summary: "Actuation latency p95 > 10s"

      - alert: DownlinkFailureRate
        expr: rate(downlink_failed_total[5m]) / rate(downlink_enqueued_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "Downlink failure rate > 5%"
```

---

## Emergency Contacts

- **On-Call Engineer:** Check PagerDuty rotation
- **Database Admin:** dba@verdegris.eu
- **ChirpStack Support:** support@chirpstack.io

---

**Last Reviewed:** 2025-10-20
**Next Review:** 2026-01-20
