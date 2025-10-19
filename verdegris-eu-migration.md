# Complete Domain Migration Plan for Verdegris

## Current Domain Inventory

### Your Existing Domains (v1)
```
✅ devices.verdegris.eu       → Parking UI (React app)
✅ chirpstack.verdegris.eu    → ChirpStack Network Server
✅ www.verdegris.eu           → Static website
❓ api.verdegris.eu           → API endpoint?
❓ parking-ingest.verdegris.eu → Webhook endpoint?
❓ parking-display.verdegris.eu → Display service?
```

### What the Refactor Includes vs Doesn't Include

#### ✅ Included in Refactor:
- **Backend API** (all 7 services → 1 service)
- **Database** (consolidated schema)
- **ChirpStack integration** (webhook processing)

#### ❌ NOT Included (Need to Preserve):
- **React UI** (devices.verdegris.eu)
- **ChirpStack UI** (chirpstack.verdegris.eu)  
- **Static Website** (www.verdegris.eu)

---

## Complete Architecture with ALL Services

```yaml
# docker-compose.yml - COMPLETE setup including UI and static site
version: '3.8'

services:
  # ============================================================
  # CORE SERVICES (New v2)
  # ============================================================
  
  # Single API replacing 7 services
  api:
    build: .
    container_name: parking-api
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://parking:parking@postgres:5432/parking
      REDIS_URL: redis://redis:6379/0
      CHIRPSTACK_HOST: chirpstack
      CHIRPSTACK_PORT: 8080
      CHIRPSTACK_API_KEY: ${CHIRPSTACK_API_KEY}
      CORS_ORIGINS: https://devices.verdegris.eu,https://www.verdegris.eu
    networks:
      - parking-network
    labels:
      - "traefik.enable=true"
      
      # Main API endpoint (for new integrations)
      - "traefik.http.routers.api.rule=Host(`api.verdegris.eu`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
      
      # Legacy endpoints (for compatibility)
      - "traefik.http.routers.ingest.rule=Host(`parking-ingest.verdegris.eu`)"
      - "traefik.http.routers.ingest.entrypoints=websecure"
      - "traefik.http.routers.ingest.tls.certresolver=letsencrypt"
      - "traefik.http.routers.ingest.service=api"
      - "traefik.http.routers.ingest.middlewares=rewrite-webhook"
      
      # Rewrite old webhook path to new
      - "traefik.http.middlewares.rewrite-webhook.replacepathregex.regex=^/api/v1/webhook"
      - "traefik.http.middlewares.rewrite-webhook.replacepathregex.replacement=/api/v1/uplink"

  # ============================================================
  # UI SERVICES (Keep existing)
  # ============================================================
  
  # React Parking UI
  parking-ui:
    image: nginx:alpine
    container_name: parking-ui
    restart: unless-stopped
    volumes:
      # Your existing React build
      - ./ui/build:/usr/share/nginx/html:ro
      - ./config/nginx/ui.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - parking-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ui.rule=Host(`devices.verdegris.eu`)"
      - "traefik.http.routers.ui.entrypoints=websecure"
      - "traefik.http.routers.ui.tls.certresolver=letsencrypt"
      - "traefik.http.services.ui.loadbalancer.server.port=80"

  # Static Website
  static-website:
    image: nginx:alpine
    container_name: static-website
    restart: unless-stopped
    volumes:
      # Your existing static site
      - ./website:/usr/share/nginx/html:ro
    networks:
      - parking-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.website.rule=Host(`www.verdegris.eu`) || Host(`verdegris.eu`)"
      - "traefik.http.routers.website.entrypoints=websecure"
      - "traefik.http.routers.website.tls.certresolver=letsencrypt"
      - "traefik.http.services.website.loadbalancer.server.port=80"
      
      # Redirect non-www to www
      - "traefik.http.routers.website-redirect.rule=Host(`verdegris.eu`)"
      - "traefik.http.routers.website-redirect.entrypoints=websecure"
      - "traefik.http.routers.website-redirect.tls.certresolver=letsencrypt"
      - "traefik.http.routers.website-redirect.middlewares=www-redirect"
      - "traefik.http.middlewares.www-redirect.redirectregex.regex=^https://verdegris.eu/(.*)"
      - "traefik.http.middlewares.www-redirect.redirectregex.replacement=https://www.verdegris.eu/$${1}"

  # ============================================================
  # EXISTING SERVICES (Keep as-is)
  # ============================================================
  
  # ChirpStack
  chirpstack:
    image: chirpstack/chirpstack:4
    container_name: chirpstack
    restart: unless-stopped
    environment:
      POSTGRESQL_DSN: postgresql://parking:parking@postgres:5432/chirpstack?sslmode=disable
    volumes:
      - ./config/chirpstack:/etc/chirpstack:ro
    networks:
      - parking-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.chirpstack.rule=Host(`chirpstack.verdegris.eu`)"
      - "traefik.http.routers.chirpstack.entrypoints=websecure"
      - "traefik.http.routers.chirpstack.tls.certresolver=letsencrypt"
      - "traefik.http.services.chirpstack.loadbalancer.server.port=8080"

  # Database (shared by all services)
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: parking
      POSTGRES_PASSWORD: ${DB_PASSWORD:-parking}
      POSTGRES_DB: parking
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d:ro
    networks:
      - parking-network

  # Redis
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - parking-network

  # Mosquitto (for ChirpStack)
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    restart: unless-stopped
    volumes:
      - ./config/mosquitto:/mosquitto/config:ro
    networks:
      - parking-network

  # ============================================================
  # TRAEFIK (Handles all domains)
  # ============================================================
  
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./config/traefik:/etc/traefik:ro
      - ./certs:/certs
    networks:
      - parking-network
    environment:
      - TRAEFIK_LOG_LEVEL=INFO

networks:
  parking-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

---

## Migration Plan for Each Domain

### 1. devices.verdegris.eu (React UI)
```javascript
// Update React app's API configuration
// src/config/api.js (or wherever you configure the API)

// OLD (pointing to multiple services)
const API_ENDPOINTS = {
  spaces: 'https://parking-api.verdegris.eu/api/v1/spaces',
  display: 'https://parking-display.verdegris.eu/api/v1/display',
  ingest: 'https://parking-ingest.verdegris.eu/api/v1/data'
}

// NEW (all pointing to single API)
const API_ENDPOINTS = {
  spaces: 'https://api.verdegris.eu/api/v1/spaces',
  display: 'https://api.verdegris.eu/api/v1/display',  
  ingest: 'https://api.verdegris.eu/api/v1/uplink'
}

// Or even simpler:
const API_BASE = 'https://api.verdegris.eu/api/v1';
```

**No other changes needed to the UI!** It just needs to point to the new consolidated API.

### 2. chirpstack.verdegris.eu
**NO CHANGES NEEDED** - ChirpStack stays exactly as it is, just update the webhook URL:
- Old webhook: `https://parking-ingest.verdegris.eu/api/v1/webhook`
- New webhook: `https://api.verdegris.eu/api/v1/uplink`

### 3. www.verdegris.eu (Static Site)
**NO CHANGES NEEDED** - Your static website remains unchanged.

---

## Complete Domain Map

| Domain | Purpose | Migration Action |
|--------|---------|-----------------|
| **devices.verdegris.eu** | React Parking UI | Update API endpoints in React config |
| **chirpstack.verdegris.eu** | ChirpStack UI | No change (just update webhook) |
| **www.verdegris.eu** | Company website | No change |
| **api.verdegris.eu** | NEW consolidated API | Create new (all services in one) |
| **parking-ingest.verdegris.eu** | Legacy webhook | Keep working (redirects to new API) |
| **parking-display.verdegris.eu** | Legacy display API | Keep working (redirects to new API) |

---

## Step-by-Step Migration

### Day 1: Deploy New Backend
```bash
# 1. Deploy the new consolidated API
docker compose up -d api postgres redis

# 2. Test it works
curl https://api.verdegris.eu/health

# 3. Keep old services running for now
```

### Day 2: Update React UI
```bash
# 1. Update API endpoints in React app
cd ui
vim src/config/api.js  # Update endpoints

# 2. Build new version
npm run build

# 3. Deploy new UI build
docker compose restart parking-ui

# 4. Test UI still works with new API
```

### Day 3: Update ChirpStack
```bash
# 1. Log into ChirpStack UI
# 2. Applications > Your App > Integrations
# 3. Update HTTP webhook URL to: https://api.verdegris.eu/api/v1/uplink
# 4. Test with a sensor uplink
```

### Week 2: Shut Down Old Services
```bash
# Once everything is confirmed working:

# 1. Stop old services
docker stop parking-ingest parking-display parking-api ...

# 2. Remove old containers
docker rm parking-ingest parking-display parking-api ...

# 3. Clean up old domain DNS entries (optional)
```

---

## React UI Update Requirements

### What Needs Updating in Your React App:

#### 1. API Configuration File
```javascript
// src/config/index.js or similar
export const config = {
  // OLD
  // apiUrl: process.env.REACT_APP_API_URL || 'https://parking-api.verdegris.eu',
  
  // NEW
  apiUrl: process.env.REACT_APP_API_URL || 'https://api.verdegris.eu',
}
```

#### 2. Environment Variables
```bash
# .env.production
# OLD
REACT_APP_API_URL=https://parking-api.verdegris.eu
REACT_APP_DISPLAY_URL=https://parking-display.verdegris.eu

# NEW
REACT_APP_API_URL=https://api.verdegris.eu
# Display endpoints now part of main API
```

#### 3. Any Hardcoded Service URLs
```javascript
// Search your React code for any hardcoded domains
grep -r "parking-" src/
grep -r "verdegris.eu" src/

// Update any found references to use the single API
```

---

## Testing Checklist

### Backend (New v2 API)
- [ ] `curl https://api.verdegris.eu/health` returns healthy
- [ ] `curl https://api.verdegris.eu/api/v1/spaces` returns spaces
- [ ] ChirpStack webhook delivers to new endpoint

### Frontend (React UI)
- [ ] devices.verdegris.eu loads
- [ ] Can view parking spaces
- [ ] Can see real-time updates
- [ ] Can make reservations

### ChirpStack
- [ ] chirpstack.verdegris.eu loads
- [ ] Can see devices
- [ ] Uplinks are processed

### Static Site
- [ ] www.verdegris.eu loads
- [ ] All pages accessible

---

## Important Notes

1. **Your React UI doesn't need rewriting** - Just update API endpoints
2. **ChirpStack doesn't change** - Just update webhook URL
3. **Static site is unaffected** - Continues as normal
4. **All domains keep working** - No downtime during migration
5. **Gradual migration** - Can run old and new in parallel

The v2 refactor is ONLY the backend consolidation. Your UI and other services remain exactly as they are, just pointing to a simpler, faster backend!
