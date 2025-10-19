# Smart Parking v5 - Quick Reference

## 🚀 Service URLs

| Service | URL | Notes |
|---------|-----|-------|
| **API v5** | https://api.verdegris.eu | Main consolidated API |
| **API Health** | https://api.verdegris.eu/health | Health check endpoint |
| **API Docs** | https://api.verdegris.eu/docs | Auto-generated API docs |
| **ChirpStack** | https://chirpstack.verdegris.eu | LoRaWAN Network Server UI |
| **Traefik Dashboard** | https://traefik.verdegris.eu | Reverse proxy dashboard (needs auth) |

## 🔗 Legacy URLs (Still Work)

| Old URL | Redirects To | Status |
|---------|--------------|--------|
| parking-ingest.verdegris.eu | api.verdegris.eu | ✅ Active |
| parking-display.verdegris.eu | api.verdegris.eu | ✅ Active |
| parking-api.verdegris.eu | api.verdegris.eu | ✅ Active |

## 🔄 API Endpoints

### Main Endpoints
```bash
# Health check
GET /health

# Parking spaces
GET /api/v1/spaces
POST /api/v1/spaces
GET /api/v1/spaces/{id}
PUT /api/v1/spaces/{id}
DELETE /api/v1/spaces/{id}

# Reservations
GET /api/v1/reservations
POST /api/v1/reservations
GET /api/v1/reservations/{id}
DELETE /api/v1/reservations/{id}

# Sensor uplinks (webhook)
POST /api/v1/uplink

# Display commands
POST /api/v1/downlink
```

### Examples
```bash
# Get all parking spaces
curl https://api.verdegris.eu/api/v1/spaces

# Create a reservation
curl -X POST https://api.verdegris.eu/api/v1/reservations \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": "uuid-here",
    "start_time": "2025-10-16T10:00:00Z",
    "end_time": "2025-10-16T12:00:00Z",
    "user_email": "user@example.com"
  }'

# Send sensor uplink (ChirpStack webhook)
curl -X POST https://api.verdegris.eu/api/v1/uplink \
  -H "Content-Type: application/json" \
  -d @chirpstack_payload.json
```

## 🐳 Docker Commands

```bash
# Navigate to project directory
cd /opt/v5-smart-parking

# View all services status
docker compose ps

# View logs (all services)
docker compose logs -f

# View specific service logs
docker compose logs -f api
docker compose logs -f chirpstack
docker compose logs -f traefik

# Restart a service
docker compose restart api

# Restart all services
docker compose restart

# Stop all services
docker compose down

# Start all services
docker compose up -d

# Rebuild and restart API
docker compose up -d --build api

# Check health
curl http://localhost:8000/health
```

## 🗄️ Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U parking_user -d parking_v2

# List databases
\l

# Connect to specific database
\c parking_v2

# List tables
\dt

# Query parking spaces
SELECT * FROM spaces;

# Query reservations
SELECT * FROM reservations WHERE status = 'active';

# Exit psql
\q
```

### Available Databases
- `chirpstack` - ChirpStack Network Server (shared with v4)
- `parking_platform` - Old v4 data
- `parking_v2` - New v5 application data

## 📊 ChirpStack Webhook Configuration

### Current Webhook URL (Legacy - works with redirect)
```
https://parking-ingest.verdegris.eu/api/v1/webhook
```

### New Webhook URL (Recommended)
```
https://api.verdegris.eu/api/v1/uplink
```

### How to Update
1. Open https://chirpstack.verdegris.eu
2. Login with your credentials
3. Navigate to: Applications → [Your App] → Integrations
4. Select HTTP Integration
5. Update "Uplink endpoint URL" to: `https://api.verdegris.eu/api/v1/uplink`
6. Save changes
7. Test with a sensor transmission

## 🔐 Traefik Dashboard Access

```bash
# Get admin credentials
cat /opt/v5-smart-parking/config/traefik/ADMIN-CREDENTIALS.txt

# Access dashboard
https://traefik.verdegris.eu
# Enter username and password when prompted
```

## 📝 Environment Variables

```bash
# View current environment
cat /opt/v5-smart-parking/.env

# Key variables:
DATABASE_URL=postgresql://parking_user:password@postgres:5432/parking_v2
REDIS_URL=redis://redis:6379/0
CHIRPSTACK_HOST=chirpstack
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=your-api-key
DOMAIN=verdegris.eu
TLS_EMAIL=admin@verdegris.eu
```

## 🔧 Troubleshooting

### API Not Responding
```bash
# Check status
docker compose ps api

# View logs
docker compose logs api --tail 100

# Restart
docker compose restart api

# Rebuild if code changed
docker compose up -d --build api
```

### ChirpStack Webhook Failing
```bash
# Check ChirpStack can reach API
docker compose exec chirpstack ping api

# Check API logs for uplink requests
docker compose logs api | grep uplink

# Test webhook manually
curl -X POST https://api.verdegris.eu/api/v1/uplink \
  -H "Content-Type: application/json" \
  -d '{"deviceInfo":{"devEui":"test"}}'
```

### Domain Not Resolving
```bash
# Check Traefik is running
docker compose ps traefik

# Check Traefik logs
docker compose logs traefik --tail 50

# Verify domain routing
docker compose exec traefik cat /config/dynamic.yml

# Test local access first
curl http://localhost:8000/health

# Test through Traefik (if DNS not updated)
curl -H "Host: api.verdegris.eu" http://localhost/health
```

### SSL Certificate Issues
```bash
# Check certificate file
ls -la /opt/v5-smart-parking/certs/acme.json

# Should be: -rw------- root root (permissions 600)
sudo chmod 600 /opt/v5-smart-parking/certs/acme.json

# Restart Traefik to reload certificates
docker compose restart traefik
```

## 📦 Backup and Recovery

```bash
# Backup databases
docker compose exec postgres pg_dumpall -U parking_user > backup_$(date +%Y%m%d).sql

# Backup specific database
docker compose exec postgres pg_dump -U parking_user parking_v2 > parking_v2_$(date +%Y%m%d).sql

# Restore database
docker compose exec -T postgres psql -U parking_user parking_v2 < backup.sql

# Backup Traefik certificates
sudo cp /opt/v5-smart-parking/certs/acme.json /backups/acme_$(date +%Y%m%d).json

# Backup entire project
sudo tar -czf /backups/v5-smart-parking_$(date +%Y%m%d).tar.gz /opt/v5-smart-parking
```

## 🚨 Emergency Procedures

### Rollback to v4
```bash
# Stop v5 services
cd /opt/v5-smart-parking
docker compose down

# Start v4 services
cd /opt/smart-parking-v4-OLD
docker compose up -d
```

### API Complete Restart
```bash
cd /opt/v5-smart-parking
docker compose restart postgres redis api
```

### Reset Everything (Nuclear Option)
```bash
cd /opt/v5-smart-parking
docker compose down
docker compose up -d
```

## 📞 Support

**Configuration Location:** `/opt/v5-smart-parking/`  
**Logs Location:** Use `docker compose logs [service]`  
**Documentation:** See `DEPLOYMENT_STATUS.md`

---

**Last Updated:** 2025-10-17
**Version:** v5.2.1
