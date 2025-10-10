# IoT Platform Integration Plan

**Source:** sensemy-iot-platform (dev-v4.0.2)  
**Target:** Smart Parking Platform  
**Date:** 2025-10-07  

---

## IoT Platform Analysis

### Services Discovered

| Service | Directory | Port | Technology | Database |
|---------|-----------|------|------------|----------|
| Ingest | 01-ingest-server | 8100 | Python/FastAPI | ingest-database (PostgreSQL 15) |
| Transform | 02-transform | 9101 | Python/FastAPI | transform-database (PostgreSQL 15) |
| Analytics | 03-analytics | 7000 | Python/FastAPI | transform-database (shared) |
| UI Frontend | 10-ui-frontend | 8500 | React/Vite/Nginx | N/A (reads from Transform API) |
| Adminer | 88-tools/adminer-custom | 8180 | PHP | N/A (DB management) |

### Key Differences from Smart Parking Setup

**IoT Platform:**
- Separate PostgreSQL container per service
- External `sensemy_network` and `charliehub_net` networks
- Caddy reverse proxy (external)
- Services communicate via network

**Smart Parking Platform:**
- Single unified PostgreSQL 16 (already deployed)
- `parking-network` and `web` networks
- Traefik reverse proxy (already deployed)
- Multiple schemas in one database

---

## Integration Strategy

### Phase 1: Copy Services (Next Step)

#### 1.1 Ingest Service
```bash
# Copy directory
cp -r iot-platform-reference/01-ingest-server/ services/ingest/

# Modifications needed:
- Update Dockerfile (if needed)
- Change database connection to unified PostgreSQL
- Update environment variables in .env
- Add Traefik labels
- Test LoRaWAN payload ingestion
```

**Database Connection Changes:**
```python
# OLD (separate DB):
DATABASE_URL = postgresql://ingest_user:password@ingest-database:5432/ingest_db

# NEW (unified DB with schema):
DATABASE_URL = postgresql://parking_user:password@postgres-primary:5432/parking_platform
# Use schema: ingest
```

#### 1.2 Transform Service
```bash
# Copy directory
cp -r iot-platform-reference/02-transform/ services/transform/

# Modifications needed:
- Update Dockerfile (if needed)
- Change database connection to unified PostgreSQL
- Update environment variables
- Add Traefik labels
- Configure API endpoints
```

**Database Connection Changes:**
```python
# OLD (separate DB):
DATABASE_URL = postgresql://transform_user:password@transform-database:5432/transform_db

# NEW (unified DB with schema):
DATABASE_URL = postgresql://parking_user:password@postgres-primary:5432/parking_platform
# Use schemas: devices, spaces (adapt from transform schema)
```

#### 1.3 Analytics Service
```bash
# Copy directory
cp -r iot-platform-reference/03-analytics/ services/analytics/

# Modifications needed:
- Update Dockerfile
- Change database connection
- Update environment variables
- Add Traefik labels
- Adapt analytics for parking metrics
```

#### 1.4 UI Frontend
```bash
# Copy directory
cp -r iot-platform-reference/10-ui-frontend/sensemy-platform/ ui/operations/

# Modifications needed:
- Update API base URL to Smart Parking endpoints
- Rebrand UI for parking operations
- Add Traefik labels
- Configure Nginx
```

---

## Phase 2: Database Schema Migration

### Existing Schemas (Smart Parking)
```sql
- core           -- System config, users, roles
- devices        -- Sensor registration, device metadata
- spaces         -- Parking space definitions, locations
- reservations   -- Booking system, availability
- analytics      -- Historical data, aggregations
- ingest         -- Raw sensor data staging
```

### IoT Platform Schema Mapping

| IoT Table | Smart Parking Schema | Notes |
|-----------|---------------------|-------|
| ingest.uplinks | ingest.uplinks | Keep as-is, raw LoRaWAN data |
| transform.devices | devices.sensors | Parking sensor devices |
| transform.gateways | devices.gateways | LoRaWAN gateways |
| transform.locations | core.locations | Hierarchical location structure |
| transform.measurements | analytics.raw_measurements | Sensor readings |

### SQL Migration Steps
1. Review initdb scripts from IoT platform
2. Adapt table structures for parking use case
3. Create unified init script in `/database/init/02-iot-tables.sql`
4. Test schema creation

---

## Phase 3: Docker Compose Integration

### Current docker-compose.yml Structure
```yaml
services:
  traefik:          # ✅ Deployed
  postgres-primary: # ✅ Deployed
  pgbouncer:        # ✅ Deployed
  mosquitto:        # ✅ Deployed
  chirpstack:       # ✅ Deployed
  adminer:          # ✅ Deployed (port 8180)
  
  # TO BE ADDED:
  ingest-service:   # 🔄 From IoT platform
  transform-service:# 🔄 From IoT platform
  analytics-service:# 🔄 From IoT platform
  ui-operations:    # 🔄 From IoT platform
  booking-api:      # ⭐ New service (future)
```

### Service Template (Ingest Example)
```yaml
  ingest-service:
    build: ./services/ingest
    container_name: parking-ingest
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres-primary:5432/${POSTGRES_DB}
      DATABASE_SCHEMA: ingest
      CHIRPSTACK_API_URL: http://chirpstack:8080
      CHIRPSTACK_API_TOKEN: ${CHIRPSTACK_API_TOKEN}
    volumes:
      - ./services/ingest/app:/app
    networks:
      - parking-network
      - web
    depends_on:
      postgres-primary:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ingest.rule=Host(`ingest.${DOMAIN}`)"
      - "traefik.http.routers.ingest.entrypoints=websecure"
      - "traefik.http.routers.ingest.tls.certresolver=letsencrypt"
      - "traefik.http.services.ingest.loadbalancer.server.port=8000"
```

---

## Phase 4: Environment Configuration

### New .env Variables Needed
```bash
# Ingest Service
INGEST_PORT=8000
CHIRPSTACK_API_URL=http://chirpstack:8080
CHIRPSTACK_API_TOKEN=<from_chirpstack_ui>

# Transform Service
TRANSFORM_PORT=9000
TRANSFORM_SCHEDULE="*/5 * * * *"  # Cron schedule

# Analytics Service
ANALYTICS_PORT=7000
ANALYTICS_RETENTION_DAYS=90

# UI Frontend
UI_PORT=3000
TRANSFORM_API_BASE=https://transform.verdegris.eu/v1
```

---

## Phase 5: Testing Plan

### 5.1 Service Startup
- [ ] All containers start successfully
- [ ] Database connections established
- [ ] Health checks pass
- [ ] Traefik discovers all routes
- [ ] SSL certificates generated

### 5.2 Data Flow Test
- [ ] Send test LoRaWAN uplink to ChirpStack
- [ ] Verify data appears in ingest service
- [ ] Verify transform service processes data
- [ ] Verify analytics service aggregates data
- [ ] Verify UI displays data

### 5.3 API Endpoints Test
- [ ] `https://ingest.verdegris.eu/health` - 200 OK
- [ ] `https://transform.verdegris.eu/health` - 200 OK
- [ ] `https://analytics.verdegris.eu/health` - 200 OK
- [ ] `https://ops.verdegris.eu` - UI loads

---

## Key Adaptation Points

### 1. Database Connections
**Challenge:** IoT platform expects separate databases  
**Solution:** Update connection strings to use single database with schemas

### 2. Network Names
**Challenge:** IoT platform uses `sensemy_network` and `charliehub_net`  
**Solution:** Replace with `parking-network` and `web`

### 3. Reverse Proxy
**Challenge:** IoT platform designed for Caddy  
**Solution:** Replace with Traefik labels

### 4. Service Discovery
**Challenge:** IoT services have hardcoded container names  
**Solution:** Update service names to match Smart Parking convention (parking-*)

### 5. Environment Variables
**Challenge:** Different .env structure  
**Solution:** Merge variables into Smart Parking .env

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Database schema conflicts | Medium | Test in isolated schema first |
| Service dependencies break | High | Review all imports and connections |
| Port conflicts | Low | Already planned port allocation |
| SSL/Traefik issues | Medium | Test each service individually |
| Data model mismatch | Medium | Adapt tables for parking use case |

---

## Next Immediate Steps

1. ✅ Clone IoT platform repository
2. ✅ Document architecture
3. 🔄 **Copy ingest service to `/services/ingest/`**
4. 🔄 **Update ingest Dockerfile and config**
5. 🔄 **Add ingest to docker-compose.yml**
6. 🔄 **Test ingest service deployment**
7. 🔄 **Repeat for transform and analytics**

---

## Success Criteria

- [ ] All 3 services (ingest, transform, analytics) running
- [ ] Services connect to unified PostgreSQL
- [ ] HTTPS endpoints accessible via Traefik
- [ ] LoRaWAN data flows: ChirpStack → Ingest → Transform → Analytics
- [ ] UI displays parking sensor data
- [ ] No conflicts with existing infrastructure
- [ ] Documentation updated

---

**Ready to proceed with Phase 1: Copy and adapt ingest service!**
