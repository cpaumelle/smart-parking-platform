# Traefik Configuration for Smart Parking v2

## What Changed

### From v1 (7 services with domains):
- parking-ingest.your-domain.com → Ingest service
- parking-display.your-domain.com → Display service  
- parking-api.your-domain.com → API Gateway
- parking-admin.your-domain.com → Admin UI
- chirpstack.your-domain.com → ChirpStack
- grafana.your-domain.com → Grafana
- pgadmin.your-domain.com → PgAdmin

### To v2 (1 service with multiple routes):
- api.your-domain.com → Single API (all endpoints)
- chirpstack.your-domain.com → ChirpStack (unchanged)
- grafana.your-domain.com → Grafana (optional)

---

## Option 1: Simple Traefik Setup (Recommended)

### docker-compose.yml (add to existing)
```yaml
version: '3.8'

services:
  # Your existing api, postgres, redis services...
  
  # ADD THIS: Traefik reverse proxy
  traefik:
    image: traefik:v3.0
    container_name: parking-traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Traefik dashboard (optional)
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./config/traefik/traefik.yml:/traefik.yml:ro
      - ./config/traefik/dynamic.yml:/dynamic.yml:ro
      - ./certs:/certs
    networks:
      - parking-network
    labels:
      - "traefik.enable=true"
      # Traefik dashboard (optional)
      - "traefik.http.routers.traefik.rule=Host(`traefik.your-domain.com`)"
      - "traefik.http.routers.traefik.service=api@internal"
      - "traefik.http.routers.traefik.tls=true"
      - "traefik.http.routers.traefik.tls.certresolver=letsencrypt"

  # MODIFY your API service to add labels
  api:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      
      # Main API domain
      - "traefik.http.routers.api.rule=Host(`api.your-domain.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls=true"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
      
      # LEGACY COMPATIBILITY - Route old domains to new API
      - "traefik.http.routers.legacy-ingest.rule=Host(`parking-ingest.your-domain.com`)"
      - "traefik.http.routers.legacy-ingest.entrypoints=websecure"
      - "traefik.http.routers.legacy-ingest.tls=true"
      - "traefik.http.routers.legacy-ingest.service=api"
      - "traefik.http.routers.legacy-ingest.middlewares=ingest-rewrite"
      
      - "traefik.http.routers.legacy-display.rule=Host(`parking-display.your-domain.com`)"
      - "traefik.http.routers.legacy-display.entrypoints=websecure"
      - "traefik.http.routers.legacy-display.tls=true"
      - "traefik.http.routers.legacy-display.service=api"
      
      # Path rewriting for legacy routes
      - "traefik.http.middlewares.ingest-rewrite.replacepathregex.regex=^/api/v1/webhook"
      - "traefik.http.middlewares.ingest-rewrite.replacepathregex.replacement=/api/v1/uplink"

  # ChirpStack (unchanged)
  chirpstack:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.chirpstack.rule=Host(`chirpstack.your-domain.com`)"
      - "traefik.http.routers.chirpstack.entrypoints=websecure"
      - "traefik.http.routers.chirpstack.tls=true"
      - "traefik.http.routers.chirpstack.tls.certresolver=letsencrypt"
      - "traefik.http.services.chirpstack.loadbalancer.server.port=8080"
```

### config/traefik/traefik.yml
```yaml
# Static configuration
api:
  dashboard: true
  debug: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: your-email@your-domain.com
      storage: /certs/acme.json
      httpChallenge:
        entryPoint: web
      # Use staging for testing
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: parking-network
  file:
    filename: /dynamic.yml
    watch: true

log:
  level: INFO

accessLog: {}
```

### config/traefik/dynamic.yml
```yaml
# Dynamic configuration for non-Docker services
http:
  routers:
    # Redirect old parking-api domain to new api domain
    api-redirect:
      rule: "Host(`parking-api.your-domain.com`)"
      service: api-redirect
      tls:
        certResolver: letsencrypt
      middlewares:
        - redirect-to-api
    
  services:
    api-redirect:
      loadBalancer:
        servers:
          - url: "http://api:8000"
  
  middlewares:
    redirect-to-api:
      redirectRegex:
        regex: "^https://parking-api.your-domain.com/(.*)"
        replacement: "https://api.your-domain.com/${1}"
        permanent: true
```

---

## Option 2: Nginx Instead of Traefik (Simpler)

If you prefer Nginx (simpler but no auto-SSL):

### config/nginx/nginx.conf
```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }
    
    upstream chirpstack {
        server chirpstack:8080;
    }
    
    # Redirect all HTTP to HTTPS
    server {
        listen 80 default_server;
        return 301 https://$host$request_uri;
    }
    
    # Main API
    server {
        listen 443 ssl http2;
        server_name api.your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    
    # Legacy domain compatibility
    server {
        listen 443 ssl http2;
        server_name parking-ingest.your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        # Rewrite old webhook path to new
        location /api/v1/webhook {
            proxy_pass http://api/api/v1/uplink;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    
    # Legacy display service domain
    server {
        listen 443 ssl http2;
        server_name parking-display.your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    
    # ChirpStack
    server {
        listen 443 ssl http2;
        server_name chirpstack.your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        location / {
            proxy_pass http://chirpstack;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            
            # WebSocket support for ChirpStack
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

---

## Migration Strategy for Domains

### Phase 1: Compatibility Mode (Day 1)
Keep all old domains working but routing to new service:
- parking-ingest.your-domain.com → api:8000/api/v1/uplink
- parking-display.your-domain.com → api:8000
- parking-api.your-domain.com → api:8000

### Phase 2: Transition (Week 1-2)
Update all references to use new domain:
- ChirpStack webhook: api.your-domain.com/api/v1/uplink
- Frontend: api.your-domain.com
- Documentation: Update all URLs

### Phase 3: Cleanup (Month 1)
Once confirmed everything uses new domains:
- Remove legacy domain configurations
- Update DNS to remove old subdomains
- Simplify Traefik rules

---

## Quick Setup Instructions

### For Traefik (Recommended):
```bash
# 1. Create certificate storage
mkdir -p certs
touch certs/acme.json
chmod 600 certs/acme.json

# 2. Create Traefik config
mkdir -p config/traefik
# Copy the traefik.yml and dynamic.yml from above

# 3. Update docker-compose.yml with Traefik service

# 4. Update your domains in the config files

# 5. Start everything
docker compose up -d

# 6. Check Traefik dashboard
# http://traefik.your-domain.com
```

### For Nginx:
```bash
# 1. Create SSL directory
mkdir -p config/nginx/ssl

# 2. Copy your SSL certificates
cp /path/to/cert.pem config/nginx/ssl/
cp /path/to/key.pem config/nginx/ssl/

# 3. Create nginx.conf (from above)

# 4. Add nginx service to docker-compose.yml

# 5. Start everything
docker compose up -d
```

---

## Domain Simplification Benefits

### Before (v1): 7+ domains
- parking-ingest.your-domain.com
- parking-display.your-domain.com
- parking-api.your-domain.com
- parking-admin.your-domain.com
- chirpstack.your-domain.com
- grafana.your-domain.com
- pgadmin.your-domain.com

### After (v2): 2-3 domains
- api.your-domain.com (everything)
- chirpstack.your-domain.com (unchanged)
- grafana.your-domain.com (optional)

### SSL Certificate Management
- Before: 7 certificates to manage
- After: 2-3 certificates
- Or use wildcard: *.your-domain.com

---

## Testing Domain Migration

```bash
# Test old domain still works (compatibility)
curl https://parking-ingest.your-domain.com/health
curl https://parking-display.your-domain.com/health

# Test new domain works
curl https://api.your-domain.com/health

# Test ChirpStack webhook with old URL
curl -X POST https://parking-ingest.your-domain.com/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"deviceInfo":{"devEui":"test"}}'

# Should be routed to new endpoint
# Check logs: docker compose logs api | grep uplink
```

---

## Important Notes

1. **Keep old domains working initially** - Don't break existing integrations
2. **Update ChirpStack webhook gradually** - Test with one device first
3. **Monitor both old and new paths** - Ensure compatibility layer works
4. **SSL certificates** - Reuse existing certs or use Let's Encrypt auto-renewal
5. **DNS changes** - Can keep all old domains pointing to same server

The beauty of consolidating to 1 service is you can route ALL old domains to the same container and handle routing internally!
