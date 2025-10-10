# ChirpStack Migration Quick Start

**Source:** CT110 (10.44.1.110) - chirpstack.sensemy.cloud  
**Target:** chirpstack.verdegris.eu  
**Date:** 2025-10-07

## Package Contents

- `chirpstack_db_backup.sql` - PostgreSQL database dump (1,410 lines, 5 devices, 1 gateway, 2 apps)
- `chirpstack-config.tar.gz` - All configuration files
- `chirpstack/` - Extracted configuration directory
- `README.md` - Complete migration guide (805 lines)

## Quick Migration Steps

### 1. On New Server (chirpstack.verdegris.eu)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh

# Transfer this entire directory
scp -r chirpstack-migration/ user@chirpstack.verdegris.eu:/opt/

# Navigate to directory
cd /opt/chirpstack-migration/chirpstack
```

### 2. Update Configuration

```bash
# Edit .env file
nano .env

# Change these values:
POSTGRES_PASSWORD=<NEW_STRONG_PASSWORD>
CHIRPSTACK_DEFAULT_ADMIN_PASSWORD=<NEW_ADMIN_PASSWORD>
```

```bash
# Edit chirpstack.toml
nano chirpstack.toml

# Update database connection (if using local PostgreSQL):
[postgresql]
dsn = "postgres://chirpstack:<NEW_PASSWORD>@postgres:5432/chirpstack_db?sslmode=disable"
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Watch logs
docker compose logs -f
```

### 4. Restore Database

```bash
# Wait for PostgreSQL to be ready
docker compose exec postgres pg_isready

# Restore database
cat ../chirpstack_db_backup.sql | docker compose exec -T postgres psql -U chirpstack chirpstack_db

# Verify
docker compose exec postgres psql -U chirpstack chirpstack_db -c "
  SELECT 'devices' as table, COUNT(*) FROM device
  UNION ALL SELECT 'gateways', COUNT(*) FROM gateway
  UNION ALL SELECT 'applications', COUNT(*) FROM application;"
```

### 5. Verify ChirpStack

```bash
# Access web UI
http://<SERVER_IP>:8080

# Login
Username: admin
Password: <NEW_ADMIN_PASSWORD from .env>

# Verify:
- 5 devices visible
- 1 gateway visible
- 2 applications visible
```

### 6. Configure Reverse Proxy

See README.md "Phase 5: Reverse Proxy & SSL" for:
- Nginx + Let's Encrypt setup
- OR Traefik configuration

### 7. Update Gateways

Update your LoRa gateway server address:
- Old: `10.44.1.110` or `chirpstack.sensemy.cloud`
- New: `chirpstack.verdegris.eu`

Port 1700/udp (Semtech) or 3001/tcp (Basic Station)

## Key Configuration Files

- `docker-compose.yml` - Service orchestration
- `chirpstack.toml` - ChirpStack server config (EU868 region, PostgreSQL, MQTT)
- `chirpstack-gateway-bridge.toml` - Gateway Bridge config (ports 1700, 3001)
- `mosquitto.conf` - MQTT broker config
- `.env` - Environment variables (passwords, credentials)

## Important Notes

- **Database:** Current backup has 5 devices, 1 gateway, 2 applications
- **Region:** EU868 (867-868 MHz, 8 channels configured)
- **MQTT:** Enabled for application integration
- **Basic Station:** Supported on port 3001 (WebSocket + TLS)
- **Health:** ChirpStack container currently showing unhealthy status - verify after migration

## Troubleshooting

**ChirpStack won't start:**
```bash
docker compose logs chirpstack
# Check PostgreSQL connection, Redis connection, port conflicts
```

**Gateway not connecting:**
```bash
docker compose logs chirpstack-gateway-bridge
sudo netstat -ulnp | grep 1700
```

**Database issues:**
```bash
docker compose exec postgres psql -U chirpstack chirpstack_db
```

## Full Documentation

See `README.md` for complete step-by-step migration guide including:
- Detailed architecture
- Security hardening
- Backup strategy
- Monitoring setup
- Rollback procedures
