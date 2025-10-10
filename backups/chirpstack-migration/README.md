# CT 110 - ChirpStack Migration Guide to chirpstack.verdegris.eu

**Version:** 1.0.0
**Last Updated:** 2025-10-07 14:45:00 UTC  
**Source:** CT110 (10.44.1.110) - chirpstack.sensemy.cloud  
**Target:** chirpstack.verdegris.eu  
**ChirpStack Version:** 4.14.1  
**Database:** PostgreSQL on CT112 (10.44.1.12)

---

## Executive Summary

This document provides a complete migration plan for the ChirpStack LoRaWAN Network Server currently running on CT110 (10.44.1.110) with database on CT112 (10.44.1.12) to a new deployment at **chirpstack.verdegris.eu**.

### Current Deployment Status
- **5 registered devices** (LoRaWAN end-devices)
- **1 registered gateway** (LoRa gateway)
- **2 applications** configured
- **ChirpStack 4.14.1** running in Docker
- **PostgreSQL 15** database (chirpstack_db on CT112)
- **Region:** EU868 (867-868 MHz)
- **MQTT Integration** enabled
- **Public Access:** https://chirpstack.sensemy.cloud

---

## Current Architecture

### Service Stack (CT110)

```
┌─────────────────────────────────────────────────┐
│         LoRa Gateways (UDP 1700)               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  ChirpStack Gateway Bridge (Port 1700/udp)    │
│  chirpstack/chirpstack-gateway-bridge:4       │
│  + Basic Station support (Port 3001/tcp)      │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│         Mosquitto MQTT Broker                  │
│         eclipse-mosquitto:2                    │
│         Ports: 1883 (MQTT), 9001 (WS)         │
└──────────┬─────────────────────┬───────────────┘
           │                     │
           ▼                     ▼
┌──────────────────┐   ┌─────────────────────────┐
│  ChirpStack      │   │   Redis Cache           │
│  Server 4.14.1   │   │   redis:7-alpine        │
│  Port 8080       │   │   Port 6379 (internal)  │
└────────┬─────────┘   └─────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  PostgreSQL Database (CT112 - 10.44.1.12:5432) │
│  Database: chirpstack_db                        │
│  User: chirpstack                               │
│  23 tables, 5 devices, 1 gateway, 2 apps       │
└─────────────────────────────────────────────────┘
```

### Docker Containers

| Container | Image | Status | Ports | Purpose |
|-----------|-------|--------|-------|---------|
| chirpstack | chirpstack/chirpstack:4 | Up (unhealthy*) | 8080 | LoRaWAN Network Server |
| chirpstack-gateway-bridge | chirpstack/chirpstack-gateway-bridge:4 | Up 5 days | 1700/udp, 3001 | Gateway protocol converter |
| chirpstack-mosquitto | eclipse-mosquitto:2 | Up 5 days (healthy) | 1883, 9001 | MQTT broker |
| chirpstack-redis | redis:7-alpine | Up 5 days (healthy) | 6379 | Cache/sessions |
| chirpstack-postgres-client-1 | postgres:15-alpine | Up 5 days | - | DB utilities |

*Note: ChirpStack container shows unhealthy status - needs investigation before migration

### Database Schema

**Database:** chirpstack_db on 10.44.1.12  
**Tables:** 23 tables including:
- `device` (5 records)
- `gateway` (1 record)  
- `application` (2 records)
- `device_profile` (device configurations)
- `device_keys` (LoRaWAN encryption keys)
- `tenant` (multi-tenancy support)
- `user` (user accounts)
- `api_key` (API authentication)

---

## Configuration Files

### 1. Docker Compose (/opt/chirpstack/docker-compose.yml)

```yaml
services:
  postgres-client:
    image: postgres:15-alpine
    environment:
      PGHOST: 10.44.1.12
      PGPORT: 5432
      PGDATABASE: chirpstack_db
      PGUSER: chirpstack
      PGPASSWORD: secret

  redis:
    image: redis:7-alpine
    container_name: chirpstack-redis
    volumes:
      - redis-data:/data

  mosquitto:
    image: eclipse-mosquitto:2
    container_name: chirpstack-mosquitto
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - mosquitto-data:/mosquitto/data
      - mosquitto-log:/mosquitto/log
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf

  chirpstack-gateway-bridge:
    image: chirpstack/chirpstack-gateway-bridge:4
    ports:
      - "1700:1700/udp"
      - "3001:3001"
    volumes:
      - ./chirpstack-gateway-bridge.toml:/etc/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml

  chirpstack:
    image: chirpstack/chirpstack:4
    ports:
      - "8080:8080"
    volumes:
      - ./chirpstack.toml:/etc/chirpstack/chirpstack.toml
```

### 2. ChirpStack Configuration (/opt/chirpstack/chirpstack.toml)

```toml
[postgresql]
dsn = "postgres://chirpstack:secret@10.44.1.12:5432/chirpstack_db?sslmode=disable"

[redis]
servers = ["redis://redis:6379"]

[network]
net_id = "000000"
enabled_regions = ["eu868"]

[api]
bind = "0.0.0.0:8080"

[integration.mqtt]
server = "tcp://mosquitto:1883"
json = true
qos = 0
clean_session = false
client_id = "chirpstack_integration"
event_topic_template = "application/{{.ApplicationID}}/device/{{.DevEUI}}/event/{{.EventType}}"
command_topic_template = "application/{{.ApplicationID}}/device/{{.DevEUI}}/command/{{.CommandType}}"

[[regions]]
  name = "eu868"
  common_name = "EU868"
  
  [regions.gateway.backend.mqtt]
    event_topic = "gateway/+/event/+"
    state_topic = "gateway/+/state/+"
    command_topic = "gateway/{{ gateway_id }}/command/{{ command }}"
    server = "tcp://mosquitto:1883"
  
  # 8 EU868 channels (867.1 - 868.5 MHz)
  [[regions.network.channels]]
    frequency = 868100000
    min_dr = 0
    max_dr = 5
```

### 3. Environment Variables (/opt/chirpstack/.env)

```bash
POSTGRES_HOST=10.44.1.12
POSTGRES_PORT=5432
POSTGRES_DB=chirpstack_db
POSTGRES_USER=chirpstack
POSTGRES_PASSWORD=secret

REDIS_URL=redis://redis:6379
MQTT_BROKER=tcp://mosquitto:1883

CHIRPSTACK_NETWORK_NET_ID=000000
CHIRPSTACK_NETWORK_ENABLED_REGIONS=US915  # Note: Config file uses EU868

CHIRPSTACK_DEFAULT_ADMIN_USER=admin
CHIRPSTACK_DEFAULT_ADMIN_PASSWORD=admin  # ⚠️ CHANGE THIS!
```

### 4. MQTT Broker (/opt/chirpstack/mosquitto.conf)

```conf
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

---

## Migration Plan

### Phase 1: Pre-Migration Preparation

#### 1.1 Export Database
```bash
# From CT110 or any machine with PostgreSQL client
PGPASSWORD=secret pg_dump -h 10.44.1.12 -U chirpstack chirpstack_db > chirpstack_db_backup_$(date +%Y%m%d).sql

# Or using Docker container on CT110
pct exec 110 -- docker exec chirpstack-postgres-client-1 pg_dump > /tmp/chirpstack_backup.sql
```

#### 1.2 Export Configuration Files
```bash
# From px1-turbo host
mkdir -p /root/chirpstack-migration
pct exec 110 -- tar -czf /tmp/chirpstack-config.tar.gz -C /opt chirpstack
pct pull 110 /tmp/chirpstack-config.tar.gz /root/chirpstack-migration/
```

#### 1.3 Document Current State
```bash
# Export device list
pct exec 110 -- docker exec chirpstack-postgres-client-1 psql -c "\copy (SELECT * FROM device) TO '/tmp/devices.csv' CSV HEADER"

# Export gateway list
pct exec 110 -- docker exec chirpstack-postgres-client-1 psql -c "\copy (SELECT * FROM gateway) TO '/tmp/gateways.csv' CSV HEADER"

# Export applications
pct exec 110 -- docker exec chirpstack-postgres-client-1 psql -c "\copy (SELECT * FROM application) TO '/tmp/applications.csv' CSV HEADER"
```

#### 1.4 Test Database Backup
```bash
# Verify backup file integrity
PGPASSWORD=secret psql -h 10.44.1.12 -U chirpstack -d postgres -c "CREATE DATABASE chirpstack_test;"
PGPASSWORD=secret psql -h 10.44.1.12 -U chirpstack -d chirpstack_test < chirpstack_db_backup_YYYYMMDD.sql
```

### Phase 2: New Server Setup (chirpstack.verdegris.eu)

#### 2.1 Server Requirements
- **OS:** Ubuntu 22.04 LTS or Debian 12
- **RAM:** Minimum 2GB, Recommended 4GB
- **Disk:** 20GB+ with SSD preferred
- **Network:** 
  - Port 8080 (HTTPS via reverse proxy)
  - Port 1700/udp (LoRa gateways)
  - Port 3001 (Basic Station - optional)
  - Port 1883 (MQTT - optional external access)

#### 2.2 Install Docker & Docker Compose
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose v2
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

#### 2.3 Setup PostgreSQL Database

**Option A: Local PostgreSQL (Recommended)**
```bash
# Create docker-compose.yml with PostgreSQL service
services:
  postgres:
    image: postgres:15-alpine
    container_name: chirpstack-postgres
    environment:
      POSTGRES_DB: chirpstack_db
      POSTGRES_USER: chirpstack
      POSTGRES_PASSWORD: <STRONG_PASSWORD>
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
```

**Option B: External PostgreSQL**
- Create database: `chirpstack_db`
- Create user: `chirpstack` with password
- Grant permissions: `GRANT ALL ON DATABASE chirpstack_db TO chirpstack;`

#### 2.4 Transfer Configuration Files
```bash
# Copy configuration files to new server
scp chirpstack-config.tar.gz user@chirpstack.verdegris.eu:/opt/
ssh user@chirpstack.verdegris.eu
cd /opt && tar -xzf chirpstack-config.tar.gz
```

#### 2.5 Update Configuration for New Environment
```bash
# Edit /opt/chirpstack/chirpstack.toml
[postgresql]
dsn = "postgres://chirpstack:<NEW_PASSWORD>@postgres:5432/chirpstack_db?sslmode=disable"
# Or for external DB:
# dsn = "postgres://chirpstack:<PASSWORD>@<DB_HOST>:5432/chirpstack_db?sslmode=disable"

# Edit /opt/chirpstack/.env
POSTGRES_PASSWORD=<NEW_PASSWORD>
CHIRPSTACK_DEFAULT_ADMIN_PASSWORD=<NEW_STRONG_PASSWORD>
```

### Phase 3: Data Migration

#### 3.1 Restore Database
```bash
# Transfer database backup to new server
scp chirpstack_db_backup_YYYYMMDD.sql user@chirpstack.verdegris.eu:/tmp/

# Import to PostgreSQL
# Option A: Local PostgreSQL container
docker exec -i chirpstack-postgres psql -U chirpstack chirpstack_db < /tmp/chirpstack_db_backup_YYYYMMDD.sql

# Option B: External PostgreSQL
PGPASSWORD=<PASSWORD> psql -h <DB_HOST> -U chirpstack chirpstack_db < /tmp/chirpstack_db_backup_YYYYMMDD.sql
```

#### 3.2 Verify Data Migration
```bash
# Check record counts match
docker exec chirpstack-postgres psql -U chirpstack chirpstack_db -c "
  SELECT 'devices' as table, COUNT(*) FROM device
  UNION ALL SELECT 'gateways', COUNT(*) FROM gateway
  UNION ALL SELECT 'applications', COUNT(*) FROM application;"

# Expected output:
#    table     | count 
# -------------+-------
#  devices     |     5
#  gateways    |     1
#  applications|     2
```

#### 3.3 Update API Keys & Secrets (if applicable)
```bash
# Review and regenerate API keys for security
docker exec chirpstack-postgres psql -U chirpstack chirpstack_db -c "SELECT id, name FROM api_key;"

# Consider regenerating for production
# (Done via ChirpStack UI after startup)
```

### Phase 4: Service Deployment

#### 4.1 Start Services
```bash
cd /opt/chirpstack
docker compose up -d

# Wait for services to start
sleep 30

# Check service health
docker compose ps
docker compose logs chirpstack | tail -50
```

#### 4.2 Verify ChirpStack Startup
```bash
# Check ChirpStack API
curl -f http://localhost:8080

# Expected: HTML page with "ChirpStack" title

# Check database connection
docker compose logs chirpstack | grep -i "postgresql"
# Should show: "successfully connected to PostgreSQL"
```

#### 4.3 Login & Verify Web UI
```
URL: http://<SERVER_IP>:8080
Username: admin
Password: <NEW_ADMIN_PASSWORD from .env>

Verify:
- Dashboard loads
- 5 devices visible
- 1 gateway visible
- 2 applications visible
```

### Phase 5: Reverse Proxy & SSL

#### 5.1 Configure Domain (chirpstack.verdegris.eu)
```bash
# Add DNS A record
chirpstack.verdegris.eu → <NEW_SERVER_IP>

# Wait for DNS propagation
dig chirpstack.verdegris.eu
```

#### 5.2 Setup Nginx Reverse Proxy with Let's Encrypt
```bash
# Install Nginx and Certbot
sudo apt install nginx certbot python3-certbot-nginx

# Create Nginx configuration
sudo cat > /etc/nginx/sites-available/chirpstack << 'EOF'
server {
    listen 80;
    server_name chirpstack.verdegris.eu;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/chirpstack /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Obtain SSL certificate
sudo certbot --nginx -d chirpstack.verdegris.eu
```

#### 5.3 Alternative: Traefik Integration
If using Traefik (like CharliHub setup):
```yaml
# Add to docker-compose.yml
  chirpstack:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.chirpstack.rule=Host(`chirpstack.verdegris.eu`)"
      - "traefik.http.routers.chirpstack.entrypoints=websecure"
      - "traefik.http.routers.chirpstack.tls.certresolver=letsencrypt"
      - "traefik.http.services.chirpstack.loadbalancer.server.port=8080"
```

### Phase 6: Gateway Migration

#### 6.1 Update Gateway Configuration
For each LoRa gateway, update server address:
- **Old:** `10.44.1.110` or `chirpstack.sensemy.cloud`
- **New:** `chirpstack.verdegris.eu`

#### 6.2 Gateway Forwarder Settings
**Semtech Packet Forwarder:**
```json
{
  "gateway_conf": {
    "server_address": "chirpstack.verdegris.eu",
    "serv_port_up": 1700,
    "serv_port_down": 1700
  }
}
```

**LoRa Basics Station:**
```json
{
  "uri": "wss://chirpstack.verdegris.eu:3001",
  "tc_cred": {
    "token": "YOUR_GATEWAY_TOKEN"
  }
}
```

#### 6.3 Verify Gateway Connectivity
```bash
# Watch gateway events in ChirpStack UI
# Navigate to: Gateways → <Gateway Name> → Live LoRaWAN frames

# Or monitor MQTT
docker exec chirpstack-mosquitto mosquitto_sub -t "gateway/+/event/+" -v
```

### Phase 7: Post-Migration Validation

#### 7.1 Functional Tests
- [ ] Gateway connects and sends stats
- [ ] Devices send uplinks successfully
- [ ] Downlinks can be scheduled and transmitted
- [ ] Application integrations work (MQTT, HTTP, etc.)
- [ ] Web UI fully functional
- [ ] API endpoints accessible

#### 7.2 Performance Validation
```bash
# Check database performance
docker exec chirpstack-postgres psql -U chirpstack chirpstack_db -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
  FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"

# Monitor container resources
docker stats --no-stream
```

#### 7.3 Security Hardening
- [ ] Change default admin password
- [ ] Regenerate API keys
- [ ] Review user accounts and permissions
- [ ] Enable PostgreSQL SSL if using external DB
- [ ] Configure firewall rules (UFW/iptables)
- [ ] Set up automated backups
- [ ] Enable monitoring/alerting

### Phase 8: Cutover & Decommission

#### 8.1 DNS Cutover
```bash
# Update DNS for existing domain (if reusing)
chirpstack.sensemy.cloud → <NEW_SERVER_IP>

# Or add new DNS record
chirpstack.verdegris.eu → <NEW_SERVER_IP>
```

#### 8.2 Grace Period
- Run both systems in parallel for 24-48 hours
- Monitor new system for issues
- Keep old system as fallback

#### 8.3 Decommission Old System
```bash
# On CT110
pct exec 110 -- docker compose -f /opt/chirpstack/docker-compose.yml down

# Archive configuration
pct exec 110 -- tar -czf /opt/chirpstack_archive_$(date +%Y%m%d).tar.gz /opt/chirpstack/

# Optional: Keep database backup on CT112 for recovery
```

---

## Rollback Plan

If migration fails, rollback to CT110:

### Quick Rollback
```bash
# On CT110
pct exec 110 -- docker compose -f /opt/chirpstack/docker-compose.yml up -d

# Update DNS back to old IP
chirpstack.sensemy.cloud → 10.44.1.110 (via proxy)

# Verify services
pct exec 110 -- docker compose ps
```

### Data Rollback
If data was modified on new system:
```bash
# Restore from backup taken in Phase 1
PGPASSWORD=secret psql -h 10.44.1.12 -U chirpstack -d chirpstack_db < chirpstack_db_backup_YYYYMMDD.sql
```

---

## Backup Strategy for New System

### Automated Database Backups
```bash
# Create backup script
cat > /opt/chirpstack/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/chirpstack/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker exec chirpstack-postgres pg_dump -U chirpstack chirpstack_db | gzip > $BACKUP_DIR/chirpstack_$DATE.sql.gz

# Keep last 30 days
find $BACKUP_DIR -name "chirpstack_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/chirpstack/backup.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/chirpstack/backup.sh" | crontab -
```

### Configuration Backup
```bash
# Weekly configuration backup
cat > /opt/chirpstack/backup-config.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/chirpstack/config-backups"
DATE=$(date +%Y%m%d)
mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/chirpstack-config_$DATE.tar.gz \
  /opt/chirpstack/*.toml \
  /opt/chirpstack/*.conf \
  /opt/chirpstack/.env \
  /opt/chirpstack/docker-compose.yml

find $BACKUP_DIR -name "chirpstack-config_*.tar.gz" -mtime +90 -delete
EOF

chmod +x /opt/chirpstack/backup-config.sh
echo "0 3 * * 0 /opt/chirpstack/backup-config.sh" | crontab -
```

---

## Troubleshooting

### ChirpStack Won't Start
```bash
# Check logs
docker compose logs chirpstack

# Common issues:
# 1. Database connection failed → verify PostgreSQL is running and credentials
# 2. Redis connection failed → verify Redis is running
# 3. Port 8080 already in use → check with: netstat -tlnp | grep 8080
```

### Gateway Not Connecting
```bash
# Check gateway bridge logs
docker compose logs chirpstack-gateway-bridge

# Verify UDP port 1700 is open
sudo netstat -ulnp | grep 1700

# Check firewall
sudo ufw status
```

### Database Migration Issues
```bash
# Check schema version
docker exec chirpstack-postgres psql -U chirpstack chirpstack_db -c "SELECT version FROM __diesel_schema_migrations ORDER BY version DESC LIMIT 1;"

# If version mismatch, run migrations
docker exec chirpstack /usr/bin/chirpstack migrate
```

---

## Monitoring & Health Checks

### Service Health
```bash
# Container health status
docker compose ps

# Resource usage
docker stats --no-stream

# Database connections
docker exec chirpstack-postgres psql -U chirpstack chirpstack_db -c "SELECT COUNT(*) FROM pg_stat_activity;"
```

### ChirpStack Metrics
- **Web UI:** Dashboard → System status
- **API:** `GET http://localhost:8080/api/internal/system-info`
- **Logs:** `docker compose logs -f chirpstack`

---

## Security Recommendations

### Pre-Migration Security Audit
- [ ] Review all user accounts and permissions
- [ ] Document all API keys in use
- [ ] Identify any custom integrations
- [ ] Review gateway authentication methods

### Post-Migration Security
- [ ] Force password reset for all users
- [ ] Enable 2FA for admin accounts (if supported)
- [ ] Regenerate all API keys
- [ ] Configure rate limiting on reverse proxy
- [ ] Set up fail2ban for brute force protection
- [ ] Enable database connection encryption (SSL)
- [ ] Regular security updates (Docker images, OS patches)

---

## Migration Checklist

### Pre-Migration
- [ ] Export database backup
- [ ] Export configuration files
- [ ] Document current state (devices, gateways, apps)
- [ ] Test database backup restoration
- [ ] Prepare new server infrastructure
- [ ] Configure DNS for new domain

### Migration
- [ ] Install Docker & Docker Compose on new server
- [ ] Setup PostgreSQL (local or external)
- [ ] Transfer configuration files
- [ ] Update configuration for new environment
- [ ] Restore database
- [ ] Verify data integrity
- [ ] Start ChirpStack services
- [ ] Configure reverse proxy & SSL

### Post-Migration
- [ ] Login to web UI and verify data
- [ ] Update gateway configurations
- [ ] Test gateway connectivity
- [ ] Verify device uplinks/downlinks
- [ ] Test application integrations
- [ ] Configure monitoring & alerting
- [ ] Setup automated backups
- [ ] Security hardening
- [ ] Update documentation
- [ ] Monitor system for 24-48 hours

### Decommission
- [ ] Confirm new system stable
- [ ] Archive old configuration
- [ ] Shutdown old ChirpStack instance
- [ ] Keep database backup for recovery
- [ ] Update DNS records

---

## Files to Export from CT110

### Configuration Files
```bash
/opt/chirpstack/docker-compose.yml
/opt/chirpstack/chirpstack.toml
/opt/chirpstack/chirpstack-gateway-bridge.toml
/opt/chirpstack/mosquitto.conf
/opt/chirpstack/.env
/opt/chirpstack/README.md
/opt/chirpstack/KERLINK_GATEWAY_SETUP.md
```

### Database
```bash
# Full database dump
chirpstack_db from 10.44.1.12:5432

# CSV exports (optional, for reference)
/tmp/devices.csv
/tmp/gateways.csv
/tmp/applications.csv
```

### Docker Volumes (optional)
```bash
# Redis data
chirpstack_redis-data

# Mosquitto persistence
chirpstack_mosquitto-data
chirpstack_mosquitto-log
```

---

## Support Resources

### ChirpStack Documentation
- Official Docs: https://www.chirpstack.io/docs/
- Migration Guide: https://www.chirpstack.io/docs/chirpstack/installation/migrations/
- API Reference: https://www.chirpstack.io/docs/chirpstack/api/

### Community
- Forum: https://forum.chirpstack.io/
- GitHub: https://github.com/chirpstack/chirpstack

---

**Migration Package Created:** 2025-10-07 14:45:00 UTC  
**ChirpStack Version:** 4.14.1  
**Database:** PostgreSQL 15  
**Status:** Ready for Migration

