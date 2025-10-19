# Smart Parking Platform v5

A production-ready smart parking management system using LoRaWAN sensors, ChirpStack network server, and a consolidated REST API.

**Version:** 5.2.1
**Status:** ✅ Production Deployment
**Deployed:** 2025-10-17

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Gateway Onboarding](#gateway-onboarding)
- [Services](#services)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

---

## Overview

### What is Smart Parking v5?

Smart Parking v5 is a complete rewrite of the parking management platform, consolidating 7 microservices into a single, maintainable FastAPI application. It provides:

- **Real-time occupancy tracking** via LoRaWAN sensors
- **Reservation management** with conflict detection
- **Display control** for LED/E-ink indicators
- **ChirpStack integration** for LoRaWAN device management
- **ORPHAN device auto-discovery** - zero-touch device provisioning (v5.2.0)
- **Admin device management API** - assign/unassign devices to spaces (v5.2.0)
- **RESTful API** with auto-generated documentation
- **Production-ready** with health checks, metrics, and observability

### Key Improvements Over v4

| Feature | v4 | v5 |
|---------|----|----|
| **Services** | 7 separate microservices | 1 consolidated API |
| **Lines of Code** | ~15,000 | ~3,000 |
| **Database Schema** | Complex, distributed | Simple, normalized |
| **API Endpoints** | Spread across services | Single unified API |
| **Deployment** | Complex orchestration | Single docker-compose |
| **Maintenance** | High complexity | Low complexity |

### Technology Stack

- **Backend:** Python 3.11, FastAPI, Uvicorn
- **Database:** PostgreSQL 16 with connection pooling
- **Cache:** Redis 7 with LRU eviction
- **Message Queue:** Mosquitto MQTT
- **Network Server:** ChirpStack v4
- **Reverse Proxy:** Traefik v3.1 with automatic HTTPS
- **Frontend:** React + Vite (Device Manager UI)

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   Traefik      │  (Reverse Proxy + SSL)
                    │   Port 80/443  │
                    └────────┬───────┘
                             │
        ┏━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━┓
        ▼                    ▼                    ▼
┌───────────────┐   ┌──────────────┐    ┌──────────────┐
│  API v5       │   │ ChirpStack   │    │  Device      │
│  Port 8000    │   │ Port 8080    │    │  Manager UI  │
└───────┬───────┘   └──────┬───────┘    └──────────────┘
        │                  │
        │                  │
        ▼                  ▼
┌───────────────┐   ┌──────────────┐
│  PostgreSQL   │   │  Mosquitto   │
│  Port 5432    │   │  Port 1883   │
└───────┬───────┘   └──────────────┘
        │
        ▼
┌───────────────┐
│     Redis     │
│  Port 6379    │
└───────────────┘
```

### LoRaWAN Data Flow

```
Sensor → Gateway → Gateway Bridge (UDP:1700) → Mosquitto (MQTT) →
ChirpStack (Processing) → API Webhook (HTTPS) → API v5 →
State Manager → Database + Redis → Display Downlink
```

### Domain Architecture

**Production Domains:**
- `api.verdegris.eu` - Main consolidated API
- `chirpstack.verdegris.eu` - ChirpStack UI
- `devices.verdegris.eu` - Device Manager UI
- `traefik.verdegris.eu` - Traefik Dashboard (admin auth)
- `adminer.verdegris.eu` - Database Admin (admin auth)
- `www.verdegris.eu` - Company website
- `contact.verdegris.eu` - Contact form API

**Legacy Compatibility:**
- `parking-ingest.verdegris.eu` → redirects to `api.verdegris.eu`
- `parking-display.verdegris.eu` → redirects to `api.verdegris.eu`
- `parking-api.verdegris.eu` → redirects to `api.verdegris.eu`

### Database Schema

```sql
-- Core tables
spaces              -- Parking space definitions
reservations        -- Reservation records
sensor_readings     -- Time-series sensor data
state_changes       -- State change audit log
api_keys           -- API authentication

-- Relationships
reservations.space_id → spaces.id
sensor_readings.space_id → spaces.id (optional)
state_changes.space_id → spaces.id
```

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose
- Linux server (Ubuntu 22.04+ recommended)
- Domain name with DNS configured
- SSL certificate email for Let's Encrypt

### 1. Clone and Configure

```bash
# Clone repository
cd /opt
git clone <repository-url> v5-smart-parking
cd v5-smart-parking

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

### 2. Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://parking_user:YOUR_PASSWORD@postgres:5432/parking_v2
DB_PASSWORD=YOUR_PASSWORD

# Redis
REDIS_URL=redis://redis:6379/0

# ChirpStack
CHIRPSTACK_HOST=chirpstack
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=your-chirpstack-api-key

# Domain
DOMAIN=verdegris.eu
TLS_EMAIL=admin@verdegris.eu

# Security
SECRET_KEY=generate-a-secure-32-character-key

# Application
LOG_LEVEL=INFO
DEBUG=false
CORS_ORIGINS=https://devices.verdegris.eu,https://www.verdegris.eu
```

### 3. Create Docker Volumes

```bash
# Create external volumes (preserves data across restarts)
docker volume create smart-parking_postgres_data
docker volume create smart-parking_redis_data
docker volume create smart-parking_chirpstack_data
docker volume create smart-parking_mosquitto_data
docker volume create smart-parking_mosquitto_logs
```

### 4. Start Services

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f api
```

### 5. Initialize Database

```bash
# The database schema is automatically created on first startup
# via migrations/001_initial_schema.sql

# Verify database is ready
docker compose exec postgres psql -U parking_user -d parking_v2 -c "\dt"
```

### 6. Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# Check API documentation
curl http://localhost:8000/docs

# Expected output:
{
  "status": "healthy",
  "version": "2.0.0",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "chirpstack": "healthy"
  }
}
```

### 7. Access Services

- **API:** https://api.verdegris.eu
- **API Docs:** https://api.verdegris.eu/docs
- **ChirpStack:** https://chirpstack.verdegris.eu
- **Traefik Dashboard:** https://traefik.verdegris.eu
- **Device Manager:** https://devices.verdegris.eu

---

## Gateway Onboarding

### LoRaWAN Gateway Setup

This guide covers onboarding a new LoRaWAN gateway to the ChirpStack network server.

### Step 1: Physical Installation

1. **Mount gateway** in location with good network connectivity
2. **Connect power** via PoE or DC adapter
3. **Connect network** via Ethernet or cellular
4. **Note Gateway EUI** from label (16 hex characters)

### Step 2: Gateway Configuration

#### For Semtech Packet Forwarder Gateways

Edit `global_conf.json`:

```json
{
  "gateway_conf": {
    "gateway_ID": "YOUR_GATEWAY_EUI",
    "server_address": "verdegris.eu",
    "serv_port_up": 1700,
    "serv_port_down": 1700,
    "keepalive_interval": 10,
    "stat_interval": 30,
    "push_timeout_ms": 100,
    "forward_crc_valid": true,
    "forward_crc_error": false,
    "forward_crc_disabled": false
  }
}
```

#### For LoRa Basics Station Gateways

Edit `station.conf`:

```json
{
  "radio_conf": {
    "lorawan_public": true,
    "clksrc": 0
  },
  "station_conf": {
    "log_level": "INFO",
    "log_size": 10000000,
    "log_rotate": 3,
    "CUPS_URI": "https://verdegris.eu:3001",
    "CUPS_TRUST": "",
    "TC_URI": "wss://verdegris.eu:3001",
    "TC_TRUST": ""
  }
}
```

### Step 3: Register in ChirpStack

1. **Access ChirpStack UI:** https://chirpstack.verdegris.eu
2. **Login** with admin credentials
3. **Navigate to:** Gateways → Add Gateway

**Fill in gateway details:**

```yaml
Gateway name: Gateway Building A - Roof
Gateway ID: YOUR_GATEWAY_EUI (16 hex chars)
Description: Outdoor gateway covering parking zones A-D
Network server: Default
Service profile: Default
Gateway profile: EU868

Location:
  Latitude: 51.5074
  Longitude: -0.1278
  Altitude: 15 (meters)

Metadata:
  installation_date: 2025-10-16
  building: Building A
  floor: Roof
```

4. **Save gateway**

### Step 4: Verify Connectivity

```bash
# Check gateway logs
docker compose logs -f gateway-bridge

# Check ChirpStack logs for gateway connection
docker compose logs -f chirpstack | grep -i gateway

# Check gateway status in ChirpStack UI
# Gateways → [Your Gateway] → Last seen should be recent
```

### Step 5: Test with Device

1. **Add a test device** (see Device Onboarding below)
2. **Send uplink** from device
3. **Verify reception** in ChirpStack UI: Devices → [Device] → LoRaWAN Frames
4. **Check RSSI/SNR** values to verify good signal strength

### Troubleshooting Gateway Issues

```bash
# Gateway not appearing in ChirpStack
# 1. Check gateway logs for connection errors
docker compose logs gateway-bridge --tail 50

# 2. Verify UDP port 1700 is open
sudo netstat -ulnp | grep 1700

# 3. Test gateway connectivity
ping <gateway-ip>

# 4. Check Mosquitto logs
docker compose logs mosquitto | grep gateway

# 5. Verify gateway EUI matches exactly (case-insensitive)
```

---

## Services

### Core Services

#### API Service (`api`)

**Purpose:** Main application API handling all business logic
**Port:** 8000 (internal)
**Health Check:** `/health`
**Technology:** Python 3.11, FastAPI, Uvicorn

**Key Features:**
- RESTful API with OpenAPI documentation
- ChirpStack webhook processing
- State management with Redis caching
- PostgreSQL connection pooling
- Background task processing
- Request ID tracking
- Comprehensive error handling

**Environment Variables:**
```bash
DATABASE_URL=postgresql://parking_user:password@postgres:5432/parking_v2
REDIS_URL=redis://redis:6379/0
CHIRPSTACK_HOST=chirpstack
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=your-api-key
LOG_LEVEL=INFO
DEBUG=false
```

**Logs:**
```bash
docker compose logs -f api
```

---

#### PostgreSQL (`postgres`)

**Purpose:** Primary data store
**Port:** 5432
**Image:** `postgres:16-alpine`
**Health Check:** `pg_isready`

**Databases:**
- `parking_v2` - v5 application data (current)
- `parking_platform` - v4 legacy data
- `chirpstack` - ChirpStack network server data

**Connection:**
```bash
docker compose exec postgres psql -U parking_user -d parking_v2
```

**Key Configurations:**
- Connection pooling: 20 connections
- Checksums enabled for data integrity
- Automatic backups to `/backups` volume
- WAL archiving for point-in-time recovery

---

#### Redis (`redis`)

**Purpose:** Caching and session storage
**Port:** 6379
**Image:** `redis:7-alpine`
**Persistence:** AOF (append-only file)

**Configuration:**
- Max memory: 256MB
- Eviction policy: allkeys-lru
- AOF fsync: everysec

**Usage:**
```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check cache stats
INFO stats

# Monitor commands
MONITOR
```

---

#### ChirpStack (`chirpstack`)

**Purpose:** LoRaWAN network server
**Port:** 8080 (UI + API)
**Image:** `chirpstack/chirpstack:4`
**Region:** EU868

**Key Features:**
- Device management
- Application server
- Gateway monitoring
- Webhook integration

**Access:**
```bash
# Web UI
https://chirpstack.verdegris.eu

# API
https://chirpstack.verdegris.eu/api
```

**Configuration Location:**
```bash
/opt/v5-smart-parking/config/chirpstack/chirpstack.toml
```

---

#### Mosquitto (`mosquitto`)

**Purpose:** MQTT broker for ChirpStack
**Ports:** 1883 (MQTT), 9001 (WebSocket)
**Image:** `eclipse-mosquitto:2`

**Purpose:** Message broker between gateway bridge and ChirpStack

**Test Connection:**
```bash
# Subscribe to all topics
docker compose exec mosquitto mosquitto_sub -t '#' -v

# Publish test message
docker compose exec mosquitto mosquitto_pub -t 'test' -m 'hello'
```

---

#### Traefik (`traefik`)

**Purpose:** Reverse proxy and SSL termination
**Ports:** 80 (HTTP), 443 (HTTPS), 8090 (Dashboard)
**Image:** `traefik:v3.1`

**Key Features:**
- Automatic HTTPS via Let's Encrypt
- Dynamic routing from Docker labels
- HTTP → HTTPS redirect
- Admin authentication for dashboard
- Legacy domain compatibility

**Dashboard:**
```bash
# Access dashboard (requires auth)
https://traefik.verdegris.eu

# Credentials stored in:
cat /opt/v5-smart-parking/config/traefik/ADMIN-CREDENTIALS.txt
```

---

#### Gateway Bridge (`gateway-bridge`)

**Purpose:** Convert UDP to MQTT for ChirpStack
**Ports:** 1700/udp (Semtech), 3001 (Basics Station)
**Image:** `chirpstack/chirpstack-gateway-bridge:4`

**Function:** Receives packets from LoRaWAN gateways and forwards to ChirpStack via MQTT

---

### Frontend Services

#### Device Manager UI (`device-manager-ui`)

**Purpose:** Web UI for device management
**Technology:** React + Vite
**URL:** https://devices.verdegris.eu

**Features:**
- Device list and search
- Real-time status updates
- Device onboarding wizard
- Analytics dashboard

**Configuration:**
```bash
# Frontend environment
/opt/v5-smart-parking/frontend/device-manager/.env.production
```

---

#### Website (`website`)

**Purpose:** Company website
**URL:** https://www.verdegris.eu
**Technology:** Static HTML/CSS/JS served by Nginx

---

#### Contact API (`contact-api`)

**Purpose:** Contact form submission
**URL:** https://contact.verdegris.eu
**Technology:** Python FastAPI

---

### Admin Tools

#### Adminer (`adminer`)

**Purpose:** Database administration UI
**URL:** https://adminer.verdegris.eu
**Authentication:** Basic auth via Traefik

**Quick Connect:**
- System: PostgreSQL
- Server: postgres
- Username: parking_user
- Password: (from .env)
- Database: parking_v2

---

## API Documentation

### Base URLs

**Production:** `https://api.verdegris.eu`
**Local Development:** `http://localhost:8000`

### Authentication

API key authentication via header:

```bash
curl -H "X-API-Key: your-api-key" https://api.verdegris.eu/api/v1/spaces
```

### Endpoints

#### Health & Monitoring

##### `GET /health`

Health check with component status.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-10-16T10:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "chirpstack": "healthy"
  },
  "stats": {
    "db_pool": {"size": 20, "free_connections": 15},
    "active_reservations": 5,
    "connected_devices": 42
  }
}
```

---

#### Parking Spaces

##### `GET /api/v1/spaces`

List all parking spaces with optional filtering.

**Query Parameters:**
- `building` (string) - Filter by building
- `floor` (string) - Filter by floor
- `zone` (string) - Filter by zone
- `state` (enum) - Filter by state: FREE, OCCUPIED, RESERVED, MAINTENANCE
- `limit` (int) - Results per page (default: 100, max: 1000)
- `offset` (int) - Pagination offset

**Example:**
```bash
curl "https://api.verdegris.eu/api/v1/spaces?building=A&state=FREE&limit=10"
```

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Parking A-001",
    "code": "A001",
    "building": "Building A",
    "floor": "Ground",
    "zone": "North",
    "sensor_eui": "0004a30b001a2b3c",
    "display_eui": "0004a30b001a2b3d",
    "state": "FREE",
    "gps_latitude": 51.5074,
    "gps_longitude": -0.1278,
    "metadata": {"capacity": "standard"},
    "created_at": "2025-10-16T08:00:00Z",
    "updated_at": "2025-10-16T10:30:00Z"
  }
]
```

---

##### `POST /api/v1/spaces`

Create a new parking space.

**Request Body:**
```json
{
  "name": "Parking A-001",
  "code": "A001",
  "building": "Building A",
  "floor": "Ground",
  "zone": "North",
  "sensor_eui": "0004a30b001a2b3c",
  "display_eui": "0004a30b001a2b3d",
  "gps_latitude": 51.5074,
  "gps_longitude": -0.1278,
  "state": "FREE",
  "metadata": {"capacity": "standard"}
}
```

**Response:** `201 Created` with space object

---

##### `GET /api/v1/spaces/{space_id}`

Get details of a single parking space.

**Response:** Space object or `404 Not Found`

---

##### `PATCH /api/v1/spaces/{space_id}`

Update a parking space (partial update).

**Request Body (all fields optional):**
```json
{
  "state": "MAINTENANCE",
  "sensor_eui": "0004a30b001a9999"
}
```

**Response:** Updated space object

---

##### `DELETE /api/v1/spaces/{space_id}`

Soft delete a parking space.

**Response:** `200 OK` or `409 Conflict` if active reservations exist

---

#### Reservations

##### `POST /api/v1/reservations`

Create a parking reservation.

**Request Body:**
```json
{
  "space_id": "550e8400-e29b-41d4-a716-446655440000",
  "start_time": "2025-10-16T14:00:00Z",
  "end_time": "2025-10-16T16:00:00Z",
  "user_email": "user@example.com",
  "user_phone": "+1234567890",
  "metadata": {"vehicle": "ABC123"}
}
```

**Validations:**
- Maximum reservation duration: 24 hours
- Space must be available for time range
- End time must be after start time

**Response:** `201 Created` with reservation object

---

##### `GET /api/v1/reservations`

List reservations with filtering.

**Query Parameters:**
- `space_id` (UUID)
- `user_email` (string)
- `status` (enum): active, completed, cancelled, no_show
- `date_from` (ISO datetime)
- `date_to` (ISO datetime)
- `limit` (int)
- `offset` (int)

**Example:**
```bash
curl "https://api.verdegris.eu/api/v1/reservations?status=active&limit=10"
```

---

##### `DELETE /api/v1/reservations/{reservation_id}`

Cancel a reservation.

**Response:** `200 OK` or `409 Conflict` if already cancelled/completed

---

#### LoRaWAN Integration

##### `POST /api/v1/uplink`

Process uplink from ChirpStack webhook.

**Purpose:** Receives sensor data from ChirpStack and updates space state

**Request Body (from ChirpStack):**
```json
{
  "deviceInfo": {
    "devEui": "0004a30b001a2b3c",
    "deviceName": "Sensor A-001"
  },
  "data": "AQIDBAUGBw==",
  "rxInfo": [{
    "gatewayId": "0004a30b001a0000",
    "rssi": -85,
    "snr": 7.5
  }]
}
```

**Response:**
```json
{
  "status": "processed",
  "space": "A001",
  "state": "OCCUPIED",
  "request_id": "req-12345"
}
```

---

##### `POST /api/v1/downlink/{device_eui}`

Send downlink to a device.

**Request Body:**
```json
{
  "command": "set_color",
  "parameters": {"color": "green"},
  "fport": 1,
  "confirmed": false
}
```

**Response:**
```json
{
  "status": "queued",
  "device_eui": "0004a30b001a2b3d",
  "id": "downlink-67890"
}
```

---

#### Admin Endpoints (ORPHAN Device Management)

**Authentication Required:** All admin endpoints require an API key with admin privileges.

##### `GET /api/v1/admin/devices/unassigned`

List all unassigned devices (ORPHAN status).

**Headers:**
```
X-API-Key: your-admin-api-key
```

**Response:**
```json
{
  "sensors": [
    {
      "id": "uuid",
      "dev_eui": "58a0cb000011590d",
      "device_model": "Browan Sensor 590D",
      "status": "orphan",
      "type_code": "browan_tbms100_motion",
      "device_type_name": "Browan TBMS100 TABS",
      "type_status": "confirmed",
      "last_seen_at": "2025-10-17T07:55:39Z",
      "created_at": "2025-10-17T07:50:24Z"
    }
  ],
  "displays": [
    {
      "id": "uuid",
      "dev_eui": "2020203907290902",
      "device_model": "Kuando Busylight",
      "status": "orphan",
      "type_code": "kuando_busylight",
      "device_type_name": "Kuando Busylight IoT Omega",
      "type_status": "confirmed",
      "last_seen_at": "2025-10-17T07:55:01Z",
      "created_at": "2025-10-17T07:55:01Z"
    }
  ],
  "total": 2
}
```

---

##### `POST /api/v1/admin/devices/sensor/{device_id}/assign`

Assign a sensor device to a parking space.

**Query Parameters:**
- `space_id` (required): UUID of the space

**Response:**
```json
{
  "status": "assigned",
  "sensor_id": "uuid",
  "sensor_eui": "58a0cb000011590d",
  "space_id": "space-uuid",
  "space_code": "A001"
}
```

**Actions:**
- Updates sensor status from 'orphan' to 'active'
- Sets space.sensor_device_id
- Enables actuation processing for this device

---

##### `POST /api/v1/admin/devices/display/{device_id}/assign`

Assign a display device to a parking space.

**Query Parameters:**
- `space_id` (required): UUID of the space

**Response:**
```json
{
  "status": "assigned",
  "display_id": "uuid",
  "display_eui": "2020203907290902",
  "space_id": "space-uuid",
  "space_code": "A001"
}
```

---

##### `POST /api/v1/admin/devices/sensor/{device_id}/unassign`

Unassign a sensor from its space.

**Response:**
```json
{
  "status": "unassigned",
  "sensor_id": "uuid",
  "sensor_eui": "58a0cb000011590d",
  "previous_space": "A001"
}
```

**Actions:**
- Updates sensor status from 'active' to 'inactive'
- Removes sensor from space (sets sensor_device_id to NULL)
- Preserves all historical sensor_readings

---

##### `POST /api/v1/admin/devices/display/{device_id}/unassign`

Unassign a display from its space.

**Response:**
```json
{
  "status": "unassigned",
  "display_id": "uuid",
  "display_eui": "2020203907290902",
  "previous_space": "A001"
}
```

**Actions:**
- Updates display status from 'active' to 'inactive'
- Removes display from space (sets display_device_id to NULL)
- Device can be reassigned to different space

---

**Device Lifecycle:**
```
New Device → ORPHAN (auto-discovered) → Admin Assigns → ACTIVE
                                                        ↓
                                                  Unassigned → INACTIVE
                                                        ↓
                                                  Reassigned → ACTIVE
                                                        ↓
                                                  Decommissioned
```

**For detailed documentation, see:** `/docs/ORPHAN_DEVICE_ARCHITECTURE.md`

---

### Interactive API Documentation

**Swagger UI:** https://api.verdegris.eu/docs
**ReDoc:** https://api.verdegris.eu/redoc

---

## Development

### Local Development Setup

#### 1. Clone Repository

```bash
git clone <repository-url>
cd v5-smart-parking
```

#### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 4. Set Up Local Environment

```bash
cp .env.example .env.local

# Edit .env.local with local settings
nano .env.local
```

**Local .env.local:**
```bash
DATABASE_URL=postgresql://parking:parking@localhost:5432/parking_dev
REDIS_URL=redis://localhost:6379/0
CHIRPSTACK_HOST=localhost
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=test-key
DEBUG=true
LOG_LEVEL=DEBUG
```

#### 5. Start Dependencies

```bash
# Start only PostgreSQL and Redis
docker compose up -d postgres redis

# Create development database
docker compose exec postgres createdb -U parking parking_dev
```

#### 6. Run Migrations

```bash
docker compose exec postgres psql -U parking -d parking_dev -f /docker-entrypoint-initdb.d/001_schema.sql
```

#### 7. Run Development Server

```bash
# With auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or use the development script
python -m src.main
```

#### 8. Access Development Environment

- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

### Code Structure

```
src/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management (Pydantic Settings)
├── models.py              # Pydantic data models
├── database.py            # Database connection pool
├── exceptions.py          # Custom exceptions
├── utils.py              # Utility functions
├── device_handlers.py     # Device-specific parsers
├── state_manager.py       # State transition logic
├── chirpstack_client.py   # ChirpStack gRPC/REST client
└── background_tasks.py    # Background job processing

migrations/
└── 001_initial_schema.sql # Database schema

tests/                     # Tests (to be added)
├── test_api.py
├── test_state_manager.py
└── test_device_handlers.py

config/                    # Service configurations
├── traefik/              # Traefik config
├── chirpstack/           # ChirpStack config
└── mosquitto/            # Mosquitto config

frontend/                  # Frontend applications
└── device-manager/       # Device management UI
```

---

### Testing

#### Manual Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test spaces endpoint
curl http://localhost:8000/api/v1/spaces

# Test uplink processing
curl -X POST http://localhost:8000/api/v1/uplink \
  -H "Content-Type: application/json" \
  -d '{
    "deviceInfo": {"devEui": "0004a30b001a2b3c"},
    "data": "AQIDBAUGBw=="
  }'
```

#### Unit Tests (To Be Implemented)

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_api.py -v
```

---

### Database Migrations

```bash
# Create new migration
# 1. Edit new SQL file in migrations/
# 2. Apply migration
docker compose exec postgres psql -U parking_user -d parking_v2 -f /migrations/002_new_migration.sql
```

---

### Code Quality

```bash
# Format code
black src/

# Lint code
pylint src/

# Type checking
mypy src/

# Sort imports
isort src/
```

---

## Deployment

### Production Deployment Checklist

#### Pre-Deployment

- [ ] Review all environment variables in `.env`
- [ ] Set strong passwords for all services
- [ ] Generate secure SECRET_KEY (32+ characters)
- [ ] Configure CORS_ORIGINS for production domains
- [ ] Set LOG_LEVEL=INFO and DEBUG=false
- [ ] Configure TLS_EMAIL for Let's Encrypt
- [ ] Backup existing data if migrating from v4

#### Initial Deployment

```bash
# 1. Clone repository
cd /opt
git clone <repository-url> v5-smart-parking
cd v5-smart-parking

# 2. Configure environment
cp .env.example .env
nano .env  # Edit with production values

# 3. Create volumes
docker volume create smart-parking_postgres_data
docker volume create smart-parking_redis_data
docker volume create smart-parking_chirpstack_data
docker volume create smart-parking_mosquitto_data
docker volume create smart-parking_mosquitto_logs

# 4. Start services
docker compose up -d

# 5. Check health
docker compose ps
curl http://localhost:8000/health

# 6. View logs
docker compose logs -f
```

#### Post-Deployment

- [ ] Verify all services are healthy
- [ ] Test API endpoints
- [ ] Configure ChirpStack webhook
- [ ] Test sensor uplinks
- [ ] Set up monitoring alerts
- [ ] Configure backup scripts
- [ ] Document admin credentials

---

### Zero-Downtime Updates

```bash
# 1. Pull latest code
cd /opt/v5-smart-parking
git pull

# 2. Rebuild API service
docker compose build api

# 3. Rolling restart (minimal downtime)
docker compose up -d --no-deps api

# 4. Verify deployment
curl http://localhost:8000/health

# 5. Check logs
docker compose logs -f api
```

---

### Rollback Procedure

```bash
# 1. Stop current services
docker compose down

# 2. Checkout previous version
git checkout <previous-commit-hash>

# 3. Rebuild and start
docker compose up -d --build

# 4. Verify
docker compose ps
curl http://localhost:8000/health
```

---

## Monitoring

### Health Checks

```bash
# API health
curl https://api.verdegris.eu/health

# Service health
docker compose ps
```

### Logs

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f api
docker compose logs -f chirpstack

# Follow logs with grep
docker compose logs -f api | grep ERROR

# View last N lines
docker compose logs --tail 100 api
```

### Metrics

```bash
# Database connections
docker compose exec postgres psql -U parking_user -d parking_v2 -c "SELECT count(*) FROM pg_stat_activity;"

# Redis memory usage
docker compose exec redis redis-cli INFO memory

# API request rate
docker compose logs api | grep "GET\|POST" | wc -l
```

### Alerts (To Be Configured)

**Recommended monitoring:**
- API /health endpoint every 60s
- Database connection pool exhaustion
- Redis memory usage > 80%
- Disk space < 10% free
- ChirpStack webhook failures

---

## Troubleshooting

### API Not Starting

```bash
# Check logs
docker compose logs api --tail 100

# Common issues:
# 1. Database connection failed
docker compose exec postgres pg_isready -U parking_user

# 2. Redis connection failed
docker compose exec redis redis-cli ping

# 3. Port already in use
sudo netstat -tulpn | grep 8000

# 4. Environment variables missing
docker compose exec api env | grep DATABASE_URL
```

---

### ChirpStack Webhook Not Working

```bash
# 1. Check ChirpStack logs
docker compose logs chirpstack | grep -i webhook

# 2. Check API uplink logs
docker compose logs api | grep uplink

# 3. Test webhook manually
curl -X POST https://api.verdegris.eu/api/v1/uplink \
  -H "Content-Type: application/json" \
  -d '{"deviceInfo":{"devEui":"test"}}'

# 4. Verify webhook URL in ChirpStack UI
# Should be: https://api.verdegris.eu/api/v1/uplink
```

---

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres --tail 50

# Test connection
docker compose exec postgres psql -U parking_user -d parking_v2 -c "SELECT 1"

# Check connection pool
docker compose logs api | grep "pool"
```

---

### Gateway Not Connecting

```bash
# Check gateway bridge logs
docker compose logs gateway-bridge --tail 50

# Check Mosquitto logs
docker compose logs mosquitto | grep gateway

# Verify UDP port 1700 is open
sudo netstat -ulnp | grep 1700

# Check ChirpStack gateway status
# ChirpStack UI → Gateways → [Gateway] → Last seen
```

---

### SSL Certificate Issues

```bash
# Check certificate file
ls -la /opt/v5-smart-parking/certs/acme.json

# Should be: -rw------- (600)
sudo chmod 600 /opt/v5-smart-parking/certs/acme.json

# Check Traefik logs for ACME errors
docker compose logs traefik | grep -i acme

# Force certificate renewal
docker compose restart traefik
```

---

### Performance Issues

```bash
# Check system resources
htop
df -h

# Check database performance
docker compose exec postgres psql -U parking_user -d parking_v2 -c "
SELECT pid, usename, application_name, state, query, wait_event_type
FROM pg_stat_activity
WHERE state != 'idle';
"

# Check slow queries
docker compose logs api | grep "slow query"

# Check Redis performance
docker compose exec redis redis-cli --latency
```

---

## Security

### Authentication & Authorization

#### API Key Authentication

API keys are stored hashed in the `api_keys` table.

**Generate API Key:**
```bash
docker compose exec postgres psql -U parking_user -d parking_v2 -c "
INSERT INTO api_keys (key_hash, key_name)
VALUES (crypt('your-secret-key', gen_salt('bf')), 'Production API Key');
"
```

**Use API Key:**
```bash
curl -H "X-API-Key: your-secret-key" https://api.verdegris.eu/api/v1/spaces
```

---

### Network Security

**Firewall Rules:**
```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (for Let's Encrypt)
sudo ufw allow 80/tcp

# Allow LoRaWAN gateway
sudo ufw allow 1700/udp

# Allow MQTT (if external access needed)
# sudo ufw allow 1883/tcp

# Enable firewall
sudo ufw enable
```

**Traefik HTTPS:**
- Automatic HTTPS via Let's Encrypt
- TLS 1.2+ enforced
- HSTS headers enabled

---

### Access Control

**Admin Services Protected:**
- `traefik.verdegris.eu` - Basic auth via `.htpasswd`
- `adminer.verdegris.eu` - Basic auth via `.htpasswd`

**Credentials Location:**
```bash
/opt/v5-smart-parking/config/traefik/ADMIN-CREDENTIALS.txt
/opt/v5-smart-parking/config/traefik/.htpasswd
```

---

### Data Security

**Database:**
- Passwords in environment variables (never committed)
- PostgreSQL checksums enabled for data integrity
- Regular automated backups

**Redis:**
- Password protection (to be implemented)
- Memory encryption (to be implemented)

**Secrets Management:**
- All secrets in `.env` file
- `.env` never committed to Git
- File permissions: 600 (owner read/write only)

```bash
chmod 600 /opt/v5-smart-parking/.env
```

---

### Security Best Practices

**Recommended Actions:**

1. **Change default passwords** in `.env`
2. **Generate strong SECRET_KEY** (32+ chars)
3. **Enable Redis password** authentication
4. **Set up fail2ban** for SSH protection
5. **Configure automated backups** (daily)
6. **Enable PostgreSQL SSL** connections
7. **Implement rate limiting** on API
8. **Set up intrusion detection** (e.g., OSSEC)
9. **Regular security updates** for Docker images
10. **Audit logs** review weekly

---

### Backup & Recovery

**Database Backup:**
```bash
# Manual backup
docker compose exec postgres pg_dump -U parking_user parking_v2 | gzip > backup_$(date +%Y%m%d).sql.gz

# Automated daily backups (add to crontab)
0 2 * * * cd /opt/v5-smart-parking && docker compose exec -T postgres pg_dumpall -U parking_user | gzip > /backups/daily_$(date +\%Y\%m\%d).sql.gz
```

**Full System Backup:**
```bash
# Backup entire deployment
sudo tar -czf /backups/v5-smart-parking_$(date +%Y%m%d).tar.gz \
  /opt/v5-smart-parking \
  --exclude=/opt/v5-smart-parking/node_modules
```

**Restore Database:**
```bash
gunzip < backup.sql.gz | docker compose exec -T postgres psql -U parking_user parking_v2
```

---

## Support & Contributing

### Getting Help

- **Documentation:** See `docs/` directory
- **Deployment Status:** See `DEPLOYMENT_STATUS.md`
- **Quick Reference:** See `QUICK_REFERENCE.md`

### Reporting Issues

When reporting issues, include:
1. Service logs (`docker compose logs [service]`)
2. Error messages
3. Steps to reproduce
4. Expected vs actual behavior

### Version History

- **v5.2.0** (2025-10-17) - ORPHAN device auto-discovery + Admin API endpoints
  - Auto-discovery of LoRaWAN devices from ChirpStack
  - Device lifecycle management (orphan → active → inactive → decommissioned)
  - Admin API endpoints for device assignment
  - Database views for unassigned device management
- **v2.0.0** (2025-10-16) - Initial v5 production release
- **v1.x** - Legacy v4 platform (deprecated)

---

**Last Updated:** 2025-10-17
**Maintained By:** Verdegris Engineering Team
