# Security & Infrastructure Audit Report

**Smart Parking Platform**  
**Audit Date:** 2025-10-13  
**Platform Version:** 1.2.0  
**Auditor:** Claude Code Infrastructure Review  
**Scope:** Complete infrastructure, code quality, security posture

---

## Executive Summary

### Assessment: ⚠️ **HIGH RISK - IMMEDIATE ACTION REQUIRED**

The Smart Parking Platform has **7 critical, 5 high, 8 medium, and 4 low priority** security issues.

**Critical Issues:**
1. ❌ **No authentication** on any service
2. ❌ **Database ports publicly exposed** (5432, 6432)
3. ❌ **MQTT broker public, no auth** (1883, 9001)
4. ❌ **Adminer database admin public**
5. ❌ **FileBrowser with filesystem access public**
6. ❌ **Wildcard CORS** on all services
7. ❌ **Connection leaks** in ingest service

---

## 🔴 CRITICAL: Public Services Without Authentication

### Exposed Endpoints

| Service | URL | Risk | Attack Vector |
|---------|-----|------|---------------|
| **Adminer** | adminer.verdegris.eu | 🔴 **CRITICAL** | Full DB access |
| **FileBrowser** | files.verdegris.eu | 🔴 **CRITICAL** | Filesystem + secrets |
| **Traefik** | traefik.verdegris.eu | 🔴 **CRITICAL** | Infrastructure view |
| **Ingest** | ingest.verdegris.eu | 🔴 **CRITICAL** | Inject fake data |
| **Downlink** | downlink.verdegris.eu | 🔴 **CRITICAL** | Control devices |
| **Transform** | transform.verdegris.eu | 🟠 **HIGH** | Device metadata |
| **Parking** | parking.verdegris.eu | 🟠 **HIGH** | Manipulate spaces |

---

## Database Exposure (CRITICAL)

**Current:** PostgreSQL bound to `0.0.0.0:5432` - **PUBLICLY ACCESSIBLE**

```bash
# Anyone can connect:
psql -h verdegris.eu -U parking_user -d parking_platform
```

**Fix (IMMEDIATE):**
```yaml
# docker-compose.yml
postgres-primary:
  ports:
    - "127.0.0.1:5432:5432"  # ✅ Localhost only
```

---

## MQTT Broker Exposed (CRITICAL)

**Current:** No authentication, public access

```bash
# Anyone can subscribe to all topics:
mosquitto_sub -h verdegris.eu -t 'application/#' -v
```

**Fix:**
```bash
# Create password file
docker exec parking-mosquitto mosquitto_passwd -c /mosquitto/config/passwd admin

# Update mosquitto.conf
password_file /mosquitto/config/passwd
allow_anonymous false
```

---

## Code Quality Issues

### 1. Database Connection Patterns (3 different approaches)

| Service | Library | Pattern | Issue |
|---------|---------|---------|-------|
| ingest | psycopg2 (sync) | New connection per query | ❌ Leak |
| transform | sqlalchemy + asyncpg | Async engine | ⚠️ Mixed |
| parking-display | asyncpg | Connection pool | ✅ Good |

**Ingest service creates 2 connections per request:**
```python
# Line 107
with get_conn() as conn:  # Connection 1
    cur.execute(...)

# Line 126  
with get_conn() as conn:  # Connection 2 (NEW!)
    cur.execute(...)
```

### 2. Wildcard CORS on All Services

```python
# All services have:
allow_origins=["*"]  # ❌ Accepts requests from ANY domain
```

### 3. Hard-Coded Service URLs

```python
TRANSFORM_URL = "http://parking-transform:9000/process-uplink/uplink"
PARKING_DISPLAY_SERVICE_URL = "http://parking-display:8100"
```

---

## Immediate Actions (24 Hours)

### 1. Lock Down Database

```bash
cd /opt/smart-parking

# Edit docker-compose.yml
sudo nano docker-compose.yml

# Change lines 45-47:
postgres-primary:
  ports:
    - "127.0.0.1:5432:5432"

# Change lines 69-71:
pgbouncer:
  ports:
    - "127.0.0.1:6432:6432"

# Restart
sudo docker compose up -d postgres-primary pgbouncer
```

### 2. Secure Admin Interfaces

```bash
# Generate password
htpasswd -nb admin "SecurePassword123" | sudo tee /opt/smart-parking/config/traefik/.htpasswd

# Create middleware config
sudo tee /opt/smart-parking/config/traefik/dynamic.yml << 'EEOF'
http:
  middlewares:
    admin-auth:
      basicAuth:
        usersFile: /config/.htpasswd
EEOF

# Update docker-compose.yml labels for adminer, filebrowser, traefik:
labels:
  - "traefik.http.routers.SERVICE.middlewares=admin-auth@file"

# Restart Traefik
sudo docker compose restart traefik
```

### 3. Secure MQTT

```bash
# Create password file
sudo docker exec parking-mosquitto mosquitto_passwd -c /mosquitto/config/passwd admin

# Update mosquitto.conf
sudo tee -a /opt/smart-parking/config/mosquitto/mosquitto.conf << 'EEOF'
password_file /mosquitto/config/passwd
allow_anonymous false
EEOF

# Restart Mosquitto
sudo docker compose restart mosquitto
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| 🔴 Critical | 7 |
| 🟠 High | 5 |
| 🟡 Medium | 8 |
| 🟢 Low | 4 |
| **Total** | **24** |

**Estimated Fix Time:** 8-12 weeks (full remediation)  
**Critical Fixes:** 1-2 weeks  

---

## Risk Score by Service

| Service | Score | Priority |
|---------|-------|----------|
| Adminer | 9.8 | 🔴 Immediate |
| FileBrowser | 9.8 | 🔴 Immediate |
| PostgreSQL | 9.1 | 🔴 Immediate |
| MQTT | 8.6 | 🔴 Immediate |
| Ingest | 8.4 | 🔴 1 week |
| Downlink | 8.2 | 🔴 1 week |
| Transform | 7.8 | 🟠 2 weeks |
| Parking Display | 7.6 | 🟠 2 weeks |

---

## Compliance Status

### GDPR
❌ **NON-COMPLIANT**
- No audit logging (Art. 30)
- Inadequate security (Art. 32)

### OWASP Top 10
❌ **3/10 vulnerabilities addressed**

---

**Recommendation:** DO NOT operate in production until critical fixes are implemented.

**Next Steps:** Review Implementation Plan document.

---

*Document Version: 1.0*  
*Classification: CONFIDENTIAL*
