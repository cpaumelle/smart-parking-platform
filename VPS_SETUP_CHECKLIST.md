# Smart Parking VPS Setup Checklist

**VPS:** vps-819ab7a9 (Ubuntu 24.04 LTS)
**Status:** Bridge networking configured ✅
**Date:** 2025-10-07

---

## ✅ Completed Steps

- [x] Ubuntu 24.04 LTS provisioned
- [x] System updated (`apt update && apt upgrade`)
- [x] Bridge kernel module loaded (`br_netfilter`)
- [x] Kernel parameters configured (`sysctl.conf`)
- [x] Working directory created (`/opt/smart-parking`)

---

## 🔄 Next: Docker Installation

```bash
# 1. Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Add your user to docker group (avoid sudo)
sudo usermod -aG docker $USER

# 3. Install Docker Compose v2
sudo apt install -y docker-compose-plugin

# 4. Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# 5. Verify installation
docker --version
docker compose version

# 6. Test Docker (should run without sudo after relogin)
docker run hello-world
```

**⚠️ Important:** After step 2, log out and back in for group membership to take effect:
```bash
exit  # logout
ssh ubuntu@vps-819ab7a9  # login again
```

---

## 🔄 Next: Essential Tools

```bash
# PostgreSQL client (for database management)
sudo apt install -y postgresql-client-16

# Python tools (for testing/debugging)
sudo apt install -y python3-pip python3-venv

# Monitoring tools
sudo apt install -y htop iotop nethogs ncdu

# Network tools
sudo apt install -y net-tools dnsutils tcpdump

# Git (if not installed)
sudo apt install -y git

# Verify versions
psql --version      # Should be 16.x
python3 --version   # Should be 3.12.x
git --version
```

---

## 🔄 Next: Firewall Configuration

```bash
# Configure UFW (Ubuntu Firewall)
sudo ufw allow ssh          # SSH (22)
sudo ufw allow 80/tcp       # HTTP (Traefik)
sudo ufw allow 443/tcp      # HTTPS (Traefik)
sudo ufw allow 1700/udp     # LoRaWAN Gateway (ChirpStack)

# Optional: Restrict SSH to specific IP (recommended for production)
# sudo ufw delete allow ssh
# sudo ufw allow from YOUR_IP_ADDRESS to any port 22

# Enable firewall
sudo ufw --force enable

# Verify rules
sudo ufw status verbose
```

Expected output:
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                     ALLOW       Anywhere
1700/udp                   ALLOW       Anywhere
```

---

## 🔄 Next: System Optimization

```bash
# Create optimized sysctl configuration for production
sudo tee /etc/sysctl.d/99-smart-parking.conf <<EOF
# IP forwarding (Docker - already set)
net.ipv4.ip_forward = 1

# Bridge networking (Docker - already set)
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1

# Connection tracking (for LoRaWAN + WebSockets)
net.netfilter.nf_conntrack_max = 262144
net.netfilter.nf_conntrack_tcp_timeout_established = 86400

# File descriptors (for PostgreSQL + containers)
fs.file-max = 2097152
fs.inotify.max_user_watches = 524288

# Virtual memory (PostgreSQL optimization)
vm.max_map_count = 262144
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Network performance
net.core.somaxconn = 1024
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 8192
EOF

# Apply new settings
sudo sysctl --system

# Verify
sysctl fs.file-max
sysctl vm.max_map_count
```

---

## 🔄 Next: Project Structure Setup

```bash
cd /opt/smart-parking

# Create directory structure (following IoT platform pattern)
mkdir -p {database,services,ui,config,scripts,logs,backups}

# Services structure (matching refactoring plan)
mkdir -p services/{ingest,transform,analytics,booking-api}
mkdir -p ui/{admin,operations}
mkdir -p config/{traefik,chirpstack,postgres}

# Verify structure
tree -L 2 /opt/smart-parking

# Expected:
# /opt/smart-parking/
# ├── database/
# ├── services/
# │   ├── ingest/
# │   ├── transform/
# │   ├── analytics/
# │   └── booking-api/
# ├── ui/
# │   ├── admin/
# │   └── operations/
# ├── config/
# │   ├── traefik/
# │   ├── chirpstack/
# │   └── postgres/
# ├── scripts/
# ├── logs/
# └── backups/
```

---

## 🔄 Next: Clone Existing IoT Platform (for refactoring)

```bash
cd /opt/smart-parking

# Option 1: If you have Git access to IoT platform
git clone <your-iot-platform-repo> iot-platform-reference

# Option 2: If using pct from Proxmox host, copy files
# (Run on Proxmox host, not VPS):
# pct exec 113 -- tar czf /tmp/iot-platform.tar.gz /opt/iot-platform
# pct pull 113 /tmp/iot-platform.tar.gz /tmp/iot-platform.tar.gz
# scp /tmp/iot-platform.tar.gz ubuntu@vps-819ab7a9:/opt/smart-parking/
# ssh ubuntu@vps-819ab7a9
# cd /opt/smart-parking
# tar xzf iot-platform.tar.gz -C iot-platform-reference --strip-components=2

# Option 3: Manual file-by-file copy (use refactoring analysis)
# Copy specific files as documented in SMART_PARKING_REFACTORING_ANALYSIS.md
```

---

## 🔄 Next: Docker Network Setup

```bash
# Create external networks (matching IoT platform pattern)
docker network create parking-network \
  --driver bridge \
  --subnet 172.20.0.0/16 \
  --gateway 172.20.0.1

docker network create web \
  --driver bridge

# Verify networks
docker network ls

# Expected output:
# NETWORK ID     NAME              DRIVER    SCOPE
# xxxxxxxxxxxx   parking-network   bridge    local
# xxxxxxxxxxxx   web               bridge    local
```

---

## 🔄 Next: Environment Configuration

```bash
cd /opt/smart-parking

# Create .env file (adapt from IoT platform)
cat > .env <<'EOF'
# ==========================================
# SMART PARKING PLATFORM - ENVIRONMENT
# ==========================================

# Domain Configuration
DOMAIN=parking.yourdomain.com
TLS_EMAIL=admin@yourdomain.com

# Network
NETWORK_NAME=parking-network

# Service Ports
INGEST_PORT=8000
TRANSFORM_PORT=9000
ANALYTICS_PORT=7000
BOOKING_API_PORT=4000
ADMIN_UI_PORT=8080
OPS_DASHBOARD_PORT=3000

# Database Configuration (PostgreSQL container)
POSTGRES_HOST=postgres-primary
POSTGRES_PORT=5432
POSTGRES_DB=parking_platform
POSTGRES_USER=parking_user
POSTGRES_PASSWORD=CHANGE_ME_SECURE_PASSWORD

# ChirpStack Configuration
CHIRPSTACK_HOST=chirpstack
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_TOKEN=GENERATE_FROM_CHIRPSTACK_UI
CHIRPSTACK_APP_ID=GENERATE_FROM_CHIRPSTACK_UI

# MQTT Configuration (for ChirpStack)
MQTT_BROKER=mosquitto
MQTT_PORT=1883

# CORS Origins
CORS_ORIGINS=https://admin.parking.yourdomain.com,https://ops.parking.yourdomain.com

# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Timezone
TZ=UTC

# Project Name
COMPOSE_PROJECT_NAME=smart-parking
EOF

# Secure the .env file
chmod 600 .env

echo "⚠️  IMPORTANT: Edit .env and replace placeholder values!"
```

---

## 🔄 Next: Initial Docker Compose File

```bash
cd /opt/smart-parking

# Create initial docker-compose.yml (start with infrastructure)
cat > docker-compose.yml <<'EOF'
# ==========================================
# SMART PARKING PLATFORM - DOCKER COMPOSE
# Phase 1: Infrastructure Only
# ==========================================

version: '3.8'

services:
  # PostgreSQL Database
  postgres-primary:
    image: postgres:16-alpine
    container_name: parking-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    networks:
      - parking-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # PgBouncer (Connection Pooler)
  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    container_name: parking-pgbouncer
    restart: unless-stopped
    environment:
      DATABASES_HOST: postgres-primary
      DATABASES_PORT: 5432
      DATABASES_USER: ${POSTGRES_USER}
      DATABASES_PASSWORD: ${POSTGRES_PASSWORD}
      DATABASES_DBNAME: ${POSTGRES_DB}
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 25
    ports:
      - "6432:6432"
    networks:
      - parking-network
    depends_on:
      postgres-primary:
        condition: service_healthy

  # MQTT Broker (for ChirpStack)
  mosquitto:
    image: eclipse-mosquitto:2.0-openssl
    container_name: parking-mosquitto
    restart: unless-stopped
    volumes:
      - ./config/mosquitto:/mosquitto/config
      - mosquitto_data:/mosquitto/data
      - mosquitto_logs:/mosquitto/log
    ports:
      - "1883:1883"
      - "9001:9001"
    networks:
      - parking-network

  # ChirpStack LoRaWAN Network Server
  chirpstack:
    image: chirpstack/chirpstack:4.10
    container_name: parking-chirpstack
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres-primary:5432/chirpstack
    volumes:
      - ./config/chirpstack:/etc/chirpstack
      - chirpstack_data:/opt/chirpstack
    ports:
      - "8080:8080"    # Web UI
      - "1700:1700/udp" # Gateway
    networks:
      - parking-network
      - web
    depends_on:
      postgres-primary:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.chirpstack.rule=Host(\`chirpstack.${DOMAIN}\`)"
      - "traefik.http.routers.chirpstack.tls.certresolver=letsencrypt"
      - "traefik.http.services.chirpstack.loadbalancer.server.port=8080"

  # Adminer (Database UI)
  adminer:
    image: adminer:latest
    container_name: parking-adminer
    restart: unless-stopped
    ports:
      - "8180:8080"
    networks:
      - parking-network
      - web
    environment:
      ADMINER_DEFAULT_SERVER: postgres-primary
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.adminer.rule=Host(\`adminer.${DOMAIN}\`)"
      - "traefik.http.routers.adminer.tls.certresolver=letsencrypt"

volumes:
  postgres_data:
  chirpstack_data:
  mosquitto_data:
  mosquitto_logs:

networks:
  parking-network:
    external: true
  web:
    external: true
EOF

echo "✅ Initial docker-compose.yml created (infrastructure only)"
```

---

## 🔄 Next: Create Required Configuration Files

```bash
cd /opt/smart-parking

# 1. Mosquitto configuration
mkdir -p config/mosquitto
cat > config/mosquitto/mosquitto.conf <<'EOF'
# Mosquitto configuration for ChirpStack
listener 1883
allow_anonymous true
max_connections -1

# WebSocket listener (optional)
listener 9001
protocol websockets
EOF

# 2. ChirpStack configuration placeholder
mkdir -p config/chirpstack
cat > config/chirpstack/chirpstack.toml <<'EOF'
# ChirpStack configuration
# This will be generated on first run, then customize as needed

[postgresql]
dsn = "postgresql://parking_user:CHANGE_ME@postgres-primary:5432/chirpstack"

[api]
bind = "0.0.0.0:8080"

[gateway]
backend = "mqtt"

[integration.mqtt]
server = "tcp://mosquitto:1883"
EOF

# 3. Database initialization script
mkdir -p database/init
cat > database/init/01-create-databases.sql <<'EOF'
-- Create databases for smart parking platform

-- ChirpStack database
CREATE DATABASE chirpstack;

-- Smart Parking database (already created by POSTGRES_DB env var)
-- CREATE DATABASE parking_platform;

-- Create schemas in parking_platform
\c parking_platform;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS devices;
CREATE SCHEMA IF NOT EXISTS spaces;
CREATE SCHEMA IF NOT EXISTS reservations;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ingest;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE chirpstack TO parking_user;
GRANT ALL PRIVILEGES ON DATABASE parking_platform TO parking_user;
GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE parking_platform TO parking_user;
EOF

echo "✅ Configuration files created"
```

---

## 🔄 Next: Test Infrastructure Deployment

```bash
cd /opt/smart-parking

# Start infrastructure services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f postgres-primary
# Press Ctrl+C to exit logs

# Test PostgreSQL connection
docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "\dt"

# Expected: Empty tables (schemas created, no tables yet)

# Test ChirpStack UI
# Open browser: http://vps-ip:8080
# Default login: admin / admin

# Test Adminer UI
# Open browser: http://vps-ip:8180
# Server: postgres-primary
# User: parking_user
# Password: (from .env)
# Database: parking_platform
```

---

## 📋 Verification Checklist

### System Level
- [ ] Docker installed and running: `docker --version`
- [ ] Docker Compose v2 installed: `docker compose version`
- [ ] Bridge networking configured: `lsmod | grep br_netfilter`
- [ ] Firewall configured: `sudo ufw status`
- [ ] PostgreSQL client installed: `psql --version`

### Docker Level
- [ ] Networks created: `docker network ls | grep parking`
- [ ] Containers running: `docker compose ps`
- [ ] PostgreSQL healthy: `docker compose exec postgres-primary pg_isready`
- [ ] ChirpStack accessible: `curl -I http://localhost:8080`
- [ ] MQTT running: `docker compose logs mosquitto | grep listening`

### Database Level
- [ ] Database created: `docker compose exec postgres-primary psql -U parking_user -l`
- [ ] Schemas created: `docker compose exec postgres-primary psql -U parking_user -d parking_platform -c "\dn"`
- [ ] PgBouncer working: `docker compose logs pgbouncer | grep listening`

### Configuration
- [ ] `.env` file created and secured (chmod 600)
- [ ] Mosquitto config present: `cat config/mosquitto/mosquitto.conf`
- [ ] ChirpStack config present: `cat config/chirpstack/chirpstack.toml`
- [ ] Init SQL script present: `cat database/init/01-create-databases.sql`

---

## 🎯 Ready for Development

Once all verification items are checked, you're ready to:

1. **Start refactoring services** from IoT platform (VM 113)
2. **Copy and adapt** ingest service → parking-ingest
3. **Copy and adapt** transform service → parking-transform
4. **Build new** reservation system
5. **Deploy** with `docker compose up -d`

---

## 📝 Useful Commands Reference

```bash
# Docker Compose
docker compose up -d              # Start all services
docker compose down               # Stop all services
docker compose ps                 # List running services
docker compose logs -f <service>  # View logs
docker compose restart <service>  # Restart service
docker compose exec <service> sh  # Shell into container

# PostgreSQL
docker compose exec postgres-primary psql -U parking_user -d parking_platform
\dt                   # List tables
\dn                   # List schemas
\q                    # Quit

# System
docker system df      # Disk usage
docker system prune   # Clean unused resources
htop                  # System monitor
sudo ufw status       # Firewall status
journalctl -u docker -f  # Docker daemon logs
```

---

## 🚨 Troubleshooting

### If containers won't start:
```bash
docker compose logs <service-name>
docker compose down && docker compose up -d
```

### If PostgreSQL connection fails:
```bash
docker compose exec postgres-primary pg_isready -U parking_user
docker compose exec postgres-primary psql -U parking_user -d parking_platform
```

### If ChirpStack won't start:
```bash
docker compose logs chirpstack
# Check database connection in logs
```

### If port conflicts:
```bash
sudo netstat -tulpn | grep <port>
# Kill conflicting process or change port in docker-compose.yml
```

---

**Next Document:** Start with copying ingest service from VM 113 following the refactoring analysis.
root@px1-turbo:~#
