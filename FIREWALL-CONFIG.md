# Firewall Configuration
**Smart Parking Platform - Security Audit Task 1.4**
**Created:** 2025-10-13 21:00 UTC

---

## UFW Status

```
Status: active
Default: deny (incoming), allow (outgoing), deny (routed)
Logging: on (low)
```

---

## Allowed Ports (PUBLIC)

| Port | Protocol | Service | Purpose | Justification |
|------|----------|---------|---------|---------------|
| 22 | TCP | SSH | Server administration | Required for remote management |
| 80 | TCP | HTTP | Traefik | Redirect to HTTPS |
| 443 | TCP | HTTPS | Traefik | All web services (websites, APIs, UIs) |
| 1700 | UDP | LoRaWAN | ChirpStack gateway protocol | Required for LoRaWAN gateways to connect |
| 3001 | TCP | BasicStation | ChirpStack Gateway Bridge | Required for BasicStation gateways |

---

## Blocked Ports (Localhost Only)

| Port | Protocol | Service | Status | Security Measure |
|------|----------|---------|--------|------------------|
| 1883 | TCP | MQTT | ✅ Bound to 127.0.0.1 | Password auth + firewall blocked |
| 9001 | TCP | MQTT WebSockets | ✅ Bound to 127.0.0.1 | Password auth + firewall blocked |
| 5432 | TCP | PostgreSQL | ✅ Bound to 127.0.0.1 | Firewall blocked |
| 6432 | TCP | PgBouncer | ✅ Bound to 127.0.0.1 | Firewall blocked |

---

## Blocked Ports (Not in Firewall Rules)

| Port | Protocol | Service | Status |
|------|----------|---------|--------|
| 8080 | TCP | Python HTTP Server | ✅ Blocked by default deny |
| 8888 | TCP | Python HTTP Server | ✅ Blocked by default deny |
| 53 | TCP/UDP | systemd-resolved | ✅ Localhost only (127.0.0.53/54) |

**Note:** Ports 8080 and 8888 are running Python HTTP servers started by user `ubuntu`. These may be for development/testing and should be reviewed.

---

## Port Binding Summary

### Public (0.0.0.0 binding):
```
0.0.0.0:22    → SSH (allowed in firewall)
0.0.0.0:80    → Traefik HTTP (allowed in firewall)
0.0.0.0:443   → Traefik HTTPS (allowed in firewall)
0.0.0.0:3001  → Gateway Bridge (allowed in firewall)
0.0.0.0:8080  → Python HTTP (BLOCKED by firewall default deny)
0.0.0.0:8888  → Python HTTP (BLOCKED by firewall default deny)
```

### Localhost Only (127.0.0.1 binding):
```
127.0.0.1:1883  → MQTT (internal services only)
127.0.0.1:9001  → MQTT WebSockets (internal services only)
127.0.0.1:5432  → PostgreSQL (internal services only)
127.0.0.1:6432  → PgBouncer (internal services only)
127.0.0.1:53    → systemd-resolved DNS (system only)
```

---

## Verification Commands

### Check Firewall Status
```bash
sudo ufw status verbose
```

### Check Listening Ports
```bash
sudo netstat -tulpn | grep LISTEN
```

### Test External MQTT Access (should fail)
```bash
# From external host:
mosquitto_sub -h verdegris.eu -p 1883 -t "test"
# Expected: Connection refused or timeout
```

### Test Internal MQTT Access (should work)
```bash
# From server localhost:
mosquitto_sub -h localhost -u mqttadmin -P *** -t "test"
# Expected: Connected (no messages)
```

---

## Changes Made (Task 1.4)

### File: `/opt/smart-parking/docker-compose.yml`

**Before:**
```yaml
mosquitto:
  ports:
    - 1883:1883
    - 9001:9001
```

**After:**
```yaml
mosquitto:
  ports:
    - "127.0.0.1:1883:1883"
    - "127.0.0.1:9001:9001"
```

---

## Security Posture

✅ **Achieved:**
- MQTT ports (1883, 9001) not accessible from internet
- Database ports (5432, 6432) not accessible from internet
- Only essential ports (HTTP/HTTPS, LoRaWAN) are public
- Default deny policy blocks any undocumented ports
- Defense in depth: localhost binding + firewall + authentication

⚠️ **Review Needed:**
- Python HTTP servers on 8080/8888 (purpose unclear, may be dev artifacts)

---

**Last Updated:** 2025-10-13 21:00 UTC
**Next Review:** After any service port changes
