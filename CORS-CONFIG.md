# CORS Configuration
**Smart Parking Platform - Security Audit Task 1.5**
**Created:** 2025-10-13 21:10 UTC

---

## Overview

All API services now use restricted CORS (Cross-Origin Resource Sharing) policies instead of wildcard `allow_origins=["*"]`. This prevents unauthorized websites from making requests to the platform APIs.

---

## Service CORS Configurations

### 1. Ingest Service (`ingest.verdegris.eu`)
**Allowed Origins:**
```
https://chirpstack.verdegris.eu
https://ingest.verdegris.eu
```

**Justification:**
- ChirpStack webhooks may call the ingest service
- Self-origin for API documentation/testing

**Environment Variable:**
```yaml
CORS_ORIGINS: https://chirpstack.${DOMAIN},https://ingest.${DOMAIN}
```

---

### 2. Transform Service (`transform.verdegris.eu`)
**Allowed Origins:**
```
https://ops.verdegris.eu
https://verdegris.eu
https://devices.verdegris.eu
```

**Justification:**
- Device manager UI (devices.verdegris.eu) queries device data
- Main website may display metrics
- Operations dashboard (if exists) needs access

**Environment Variable:**
```yaml
CORS_ORIGINS: https://ops.${DOMAIN},https://${DOMAIN},https://devices.${DOMAIN}
```

---

### 3. Downlink Service (`downlink.verdegris.eu`)
**Allowed Origins:**
```
https://ops.verdegris.eu
https://verdegris.eu
https://devices.verdegris.eu
```

**Justification:**
- Device manager UI sends downlinks to configure devices
- Operations dashboard may send commands
- Main website may trigger actions

**Environment Variable:**
```yaml
CORS_ORIGINS: https://ops.${DOMAIN},https://${DOMAIN},https://devices.${DOMAIN}
```

---

### 4. Parking Display Service (`parking.verdegris.eu`)
**Allowed Origins:**
```
https://devices.verdegris.eu
https://parking.verdegris.eu
```

**Justification:**
- Device manager UI monitors/controls parking displays
- Parking dashboard (self-origin) for UI

**Environment Variable:**
```yaml
CORS_ORIGINS: https://devices.${DOMAIN},https://parking.${DOMAIN}
```

---

## Implementation Details

### Code Pattern

All services now follow this pattern:

```python
# CORS - Restricted to allowed origins
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

### Files Modified

1. **docker-compose.yml** - Added `CORS_ORIGINS` environment variables to:
   - `ingest-service` (line 166)
   - `downlink-service` (already existed, line 216)
   - `transform-service` (already existed, line 191)
   - `parking-display-service` (line 242)

2. **Service Code Files:**
   - `/opt/smart-parking/services/ingest/app/main.py`
   - `/opt/smart-parking/services/downlink/app/main.py`
   - `/opt/smart-parking/services/parking-display/app/main.py`
   - `/opt/smart-parking/services/transform/app/main.py` (already correct)

### Backups Created

All modified service files backed up with suffix:
```
*.backup-20251013-security
```

---

## Testing CORS

### Test Allowed Origin (Should Work)

```bash
# From devices.verdegris.eu - should work for transform service
curl -X OPTIONS https://transform.verdegris.eu/api/endpoint \
  -H "Origin: https://devices.verdegris.eu" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

Expected response headers:
```
Access-Control-Allow-Origin: https://devices.verdegris.eu
Access-Control-Allow-Credentials: true
```

### Test Blocked Origin (Should Fail)

```bash
# From unauthorized origin - should NOT get CORS headers
curl -X OPTIONS https://transform.verdegris.eu/api/endpoint \
  -H "Origin: https://malicious-site.com" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

Expected: No `Access-Control-Allow-Origin` header in response

---

## Security Benefits

✅ **Before (Wildcard CORS):**
- ANY website could make requests to APIs
- Risk of CSRF attacks
- Data exfiltration possible from malicious sites

✅ **After (Restricted CORS):**
- Only whitelisted origins can make requests
- CSRF attack surface reduced
- Unauthorized sites cannot access API data

---

## Maintenance

### Adding New Allowed Origins

1. Update `docker-compose.yml` environment variable:
```yaml
CORS_ORIGINS: https://existing.${DOMAIN},https://new-service.${DOMAIN}
```

2. Recreate the service:
```bash
sudo docker compose up -d --force-recreate <service-name>
```

3. Verify:
```bash
sudo docker exec <container-name> printenv CORS_ORIGINS
```

### Troubleshooting CORS Errors

If legitimate requests are being blocked:

1. Check browser console for CORS error
2. Verify origin is in allowed list:
   ```bash
   sudo docker exec <container> printenv CORS_ORIGINS
   ```
3. Check service logs for CORS middleware messages
4. Add origin to whitelist if legitimate

---

## Related Security Measures

- **Task 1.1:** Database ports bound to localhost
- **Task 1.2:** Admin interfaces require authentication
- **Task 1.3:** MQTT broker requires authentication
- **Task 1.4:** Public ports restricted by firewall
- **Task 1.5:** CORS restricted to allowed origins ← This document

---

**Last Updated:** 2025-10-13 21:10 UTC
**Next Review:** When adding new frontends or services
