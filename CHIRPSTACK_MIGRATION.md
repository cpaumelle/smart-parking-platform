# ChirpStack Migration Guide

**From**: CT110 (Proxmox) - Old ChirpStack Instance
**To**: VPS-819ab7a9 (verdegris.eu) - New ChirpStack 4.10.2
**Date**: 2025-10-07
**Status**: Target database ready ✅

---

## Target Server Status

**New ChirpStack**: 4.10.2 (running at https://chirpstack.verdegris.eu)
**Database**: PostgreSQL 16-alpine (parking-postgres container)
**Schema Version**: 20241112135745 (latest migrations applied)
**Database Name**: `chirpstack`
**User**: `parking_user`
**Tables**: 19 tables initialized and empty

---

## Migration Steps Summary

1. **Export** ChirpStack database from old server (CT110)
2. **Transfer** export file to new server
3. **Stop** ChirpStack service on new server
4. **Import** database dump
5. **Verify** import success
6. **Restart** ChirpStack service
7. **Update** webhook to new ingest service
8. **Test** gateway connectivity and data flow

---

## Step 1: Export from Old Server (CT110)

**On your old server**, export the ChirpStack database:

```bash
# Check old ChirpStack version
docker exec chirpstack chirpstack --version

# Export database
docker exec -t ct110-postgres pg_dump -U chirpstack -d chirpstack \
  --clean --if-exists --no-owner --no-acl \
  > chirpstack_export_$(date +%Y%m%d_%H%M%S).sql

# Compress for transfer
gzip chirpstack_export_*.sql
```

---

## Step 2: Transfer to New Server

**Transfer the export file** (choose one method):

```bash
# Option A: Direct SCP
scp chirpstack_export_*.sql.gz root@151.80.58.99:/opt/smart-parking/backups/

# Option B: Via intermediate machine
scp chirpstack_export_*.sql.gz user@local:/tmp/
scp /tmp/chirpstack_export_*.sql.gz root@151.80.58.99:/opt/smart-parking/backups/
```

---

## Step 3: Import on New Server

**On new server** (verdegris.eu):

```bash
cd /opt/smart-parking

# Stop ChirpStack
sudo docker compose stop chirpstack

# Decompress export
gunzip backups/chirpstack_export_*.sql.gz

# Import database
cat backups/chirpstack_export_*.sql | \
  sudo docker compose exec -T postgres-primary psql -U parking_user -d chirpstack

# Restart ChirpStack
sudo docker compose start chirpstack

# Watch startup logs
sudo docker compose logs -f chirpstack
```

---

## Step 4: Verify Migration

```bash
# Check data imported
sudo docker compose exec postgres-primary psql -U parking_user -d chirpstack -c "
SELECT
  (SELECT COUNT(*) FROM tenant) as tenants,
  (SELECT COUNT(*) FROM application) as applications,
  (SELECT COUNT(*) FROM device) as devices,
  (SELECT COUNT(*) FROM gateway) as gateways,
  (SELECT COUNT(*) FROM device_profile) as profiles,
  (SELECT COUNT(*) FROM \"user\") as users;
"
```

---

## Step 5: Update ChirpStack Integration

**Update HTTP webhook** to point to new ingest service:

**ChirpStack UI** → Your Application → **Integrations** → **HTTP**

```
Uplink URL: https://ingest.verdegris.eu/uplink?source=chirpstack
```

---

## Step 6: Test Data Flow

```bash
# Monitor ingest service
sudo docker compose logs -f ingest-service

# Check uplinks are being received and stored
sudo docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "
SELECT COUNT(*) as uplink_count, MAX(received_at) as latest_uplink
FROM ingest.raw_uplinks;
"
```

---

## Troubleshooting

### Gateways not connecting?
Check gateway configuration points to: `chirpstack.verdegris.eu:1700`

### Users can't login?
Reset password via CLI:
```bash
sudo docker compose exec chirpstack chirpstack --config /etc/chirpstack \
  user update --email admin@example.com --password newpassword
```

### Uplinks not reaching ingest?
Test webhook manually:
```bash
curl -X POST "https://ingest.verdegris.eu/uplink?source=chirpstack" \
  -H "Content-Type: application/json" \
  -d '{"deviceInfo":{"devEui":"test"}}'
```

---

## Migration Checklist

- [ ] Export ChirpStack database from old server
- [ ] Transfer export to new server
- [ ] Import database on new server
- [ ] Verify data imported correctly
- [ ] Test ChirpStack UI login
- [ ] Update HTTP integration webhook
- [ ] Verify gateways reconnect
- [ ] Test uplink data flow
- [ ] Monitor for 24-48 hours
- [ ] Shutdown old ChirpStack

---

**Server**: vps-819ab7a9 (151.80.58.99)
**Domain**: verdegris.eu
**ChirpStack**: 4.10.2 at https://chirpstack.verdegris.eu
**Ingest**: https://ingest.verdegris.eu/uplink?source=chirpstack
