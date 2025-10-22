# OpenAPI 3.1 Specification Validation Report
**Generated:** 2025-10-21
**Application:** Smart Parking Platform v5.3
**Validation Status:** ⚠️ PARTIAL MATCH - Several discrepancies found

## Executive Summary

This report compares the OpenAPI 3.1 specification defined in `docs/OpenAPI_3_1_spec.md` against the actual API implementation in the v5.3 codebase. The validation reveals several endpoints that exist in the implementation but are not documented in the OpenAPI spec, and vice versa.

**Key Findings:**
- ✅ Core authentication endpoints match
- ✅ Health check endpoints match
- ⚠️ Display policy endpoints have path prefix mismatch
- ❌ Several implemented endpoints missing from spec
- ❌ Some spec endpoints not implemented
- ⚠️ Webhook endpoint path differs

---

## Endpoint Comparison Matrix

### ✅ Fully Matched Endpoints

These endpoints are defined in both the OpenAPI spec and the implementation with matching paths and methods:

| Endpoint | Method | OpenAPI Spec | Implementation | Notes |
|----------|--------|--------------|----------------|-------|
| `/health` | GET | ✅ | ✅ `main_tenanted.py:279` | Health check |
| `/health/ready` | GET | ✅ | ✅ `main_tenanted.py:337` | Readiness probe |
| `/metrics` | GET | ✅ | ✅ `routers/metrics.py:12` | Prometheus metrics |
| `/api/v1/auth/login` | POST | ✅ | ✅ `api_tenants.py:42` | User login |
| `/api/v1/spaces` | GET | ✅ | ✅ `routers/spaces_tenanted.py:23` | List spaces |
| `/api/v1/spaces` | POST | ✅ | ✅ `routers/spaces_tenanted.py:204` | Create space |
| `/api/v1/spaces/{space_id}` | GET | ✅ | ✅ `routers/spaces_tenanted.py:134` | Get space |
| `/api/v1/spaces/{space_id}` | PATCH | ✅ | ✅ `routers/spaces_tenanted.py:290` | Update space |
| `/api/v1/spaces/{space_id}` | DELETE | ✅ | ✅ `routers/spaces_tenanted.py:374` | Delete space |
| `/api/v1/reservations` | GET | ✅ | ✅ `routers/reservations.py:27` | List reservations |
| `/api/v1/reservations` | POST | ✅ | ✅ `routers/reservations.py:95` | Create reservation |
| `/api/v1/reservations/{reservation_id}` | GET | ✅ | ✅ `routers/reservations.py:353` | Get reservation |
| `/api/v1/reservations/{reservation_id}` | DELETE | ✅ | ✅ `routers/reservations.py:295` | Cancel reservation |
| `/api/v1/devices` | GET | ✅ | ✅ `routers/devices.py:85` | List devices |
| `/api/v1/downlinks/queue/metrics` | GET | ✅ | ✅ `routers/downlink_monitor.py:13` | Queue metrics |
| `/api/v1/downlinks/queue/health` | GET | ✅ | ✅ `routers/downlink_monitor.py:65` | Queue health |
| `/api/v1/downlinks/queue/clear-metrics` | POST | ✅ | ✅ `routers/downlink_monitor.py:131` | Clear metrics |

---

### ⚠️ Partial Matches (Path or Method Differences)

These endpoints exist in both but have discrepancies:

#### Display Policies Path Mismatch
**OpenAPI Spec:**
```
/api/v1/tenants/{tenant_id}/display-policies
/api/v1/tenants/{tenant_id}/display-policies/{policy_id}/activate
```

**Implementation:**
```python
# routers/display_policies.py
router = APIRouter(prefix="/api/v1/display-policies", tags=["display-policies"])

GET    /api/v1/display-policies/                              (line 84)
GET    /api/v1/display-policies/{policy_id}                   (line 164)
POST   /api/v1/display-policies/                              (line 221)
PATCH  /api/v1/display-policies/{policy_id}                   (line 309)
POST   /api/v1/display-policies/admin-overrides               (line 391)
DELETE /api/v1/display-policies/admin-overrides/{override_id} (line 469)
GET    /api/v1/display-policies/spaces/{space_id}/computed-state (line 509)
```

**Issue:** The implementation does NOT include `/tenants/{tenant_id}` in the path prefix. Tenant scoping is done via JWT/API key authentication, not path parameters.

**Recommendation:** Update OpenAPI spec to remove `/tenants/{tenant_id}` prefix from display policy endpoints.

---

#### Webhook Endpoint Path Mismatch
**OpenAPI Spec:**
```
POST /webhooks/uplink
```

**Implementation:**
```python
# main.py (old non-tenanted version)
POST /api/v1/uplink  (main.py:288)
```

**Issue:** The spec uses `/webhooks/uplink` but implementation has `/api/v1/uplink`.

**Status:** This appears to be a legacy endpoint in `main.py` (non-tenanted version). The tenanted version (`main_tenanted.py`) doesn't have this endpoint explicitly defined at the app level, suggesting it may be handled differently.

**Recommendation:** Clarify which webhook endpoint path is the canonical one for v5.3 multi-tenant implementation.

---

### ❌ Endpoints in OpenAPI Spec but NOT Implemented

These endpoints are defined in the OpenAPI spec but do not exist in the current implementation:

| Endpoint | Method | Spec Location | Status |
|----------|--------|---------------|--------|
| `/api/v1/me` | GET | Line 543 | ❌ Not found |
| `/api/v1/me/limits` | GET | Line 562 | ❌ Not found |
| `/api/v1/tenants` | POST | Line 576 | ⚠️ Exists as `/api/v1/auth/register` |
| `/api/v1/auth/refresh` | POST | Line 617 | ❌ Not found |
| `/api/v1/tenants/{tenant_id}` | GET | Line 634 | ⚠️ Exists as `/api/v1/tenants/current` |
| `/api/v1/tenants/{tenant_id}` | PATCH | Line 634 | ⚠️ Exists as `/api/v1/tenants/current` |
| `/api/v1/tenants/{tenant_id}/users` | GET | Line 647 | ⚠️ Exists as `/api/v1/users` |
| `/api/v1/sites/{site_id}/spaces` | GET | Line 676 | ❌ Not found |
| `/api/v1/spaces/{space_id}/availability` | GET | Line 749 | ✅ Exists in `routers/spaces.py:160` (V4 compat) |
| `/api/v1/spaces/{space_id}/actuate` | POST | Line 769 | ❌ Not found |
| `/api/v1/spaces/{space_id}/sensor` | PATCH | Line 879 | ❌ Not found |
| `/api/v1/spaces/{space_id}/display` | PATCH | Line 892 | ❌ Not found |
| `/api/v1/tasks/{task_id}` | GET | Line 984 | ❌ Not found |

**Analysis:**
1. **User Profile Endpoints** (`/api/v1/me`): Not implemented yet
2. **Tenant Management**: Implemented but with different path structure (uses `/api/v1/tenants/current` instead of `/api/v1/tenants/{tenant_id}`)
3. **Token Refresh** (`/api/v1/auth/refresh`): Not implemented (JWT tokens are long-lived, 24h)
4. **Space Actuation**: Not implemented as a dedicated endpoint (likely handled via display state machine)
5. **Async Tasks**: Not implemented (`/api/v1/tasks/{task_id}`)

---

### ❌ Endpoints Implemented but NOT in OpenAPI Spec

These endpoints exist in the implementation but are missing from the OpenAPI specification:

| Endpoint | Method | Implementation | Purpose |
|----------|--------|----------------|---------|
| `/api/v1/auth/register` | POST | `api_tenants.py:154` | Register user + create tenant |
| `/api/v1/tenants/current` | GET | `api_tenants.py:243` | Get current tenant |
| `/api/v1/tenants/current` | PATCH | `api_tenants.py:260` | Update current tenant |
| `/api/v1/sites` | GET | `api_tenants.py:294` | List sites |
| `/api/v1/sites` | POST | `api_tenants.py:309` | Create site |
| `/api/v1/sites/{site_id}` | GET | `api_tenants.py:331` | Get site |
| `/api/v1/sites/{site_id}` | PATCH | `api_tenants.py:349` | Update site |
| `/api/v1/users` | GET | `api_tenants.py:389` | List tenant users |
| `/api/v1/api-keys` | GET | `api_tenants.py:435` | List API keys |
| `/api/v1/api-keys` | POST | `api_tenants.py:450` | Create API key |
| `/api/v1/api-keys/{key_id}` | DELETE | `api_tenants.py:490` | Revoke API key |
| `/api/v1/webhook-secret` | POST | `api_tenants.py:513` | Create webhook secret |
| `/api/v1/webhook-secret/rotate` | POST | `api_tenants.py:548` | Rotate webhook secret |
| `/api/v1/orphan-devices` | GET | `api_tenants.py:580` | List orphan devices |
| `/api/v1/orphan-devices/{device_eui}/assign` | POST | `api_tenants.py:614` | Assign orphan device |
| `/api/v1/orphan-devices/{device_eui}` | DELETE | `api_tenants.py:651` | Delete orphan device |
| `/api/v1/devices/device-types` | GET | `routers/devices.py:15` | List device types |
| `/api/v1/devices/{deveui}` | GET | `routers/devices.py:251` | Get device details |
| `/api/v1/devices/full-metadata` | GET | `routers/devices.py:379` | Get all devices with metadata (V4 compat) |
| `/api/v1/devices/{deveui}` | PUT | `routers/devices.py:475` | Update device |
| `/api/v1/devices/{deveui}/archive` | PATCH | `routers/devices.py:616` | Archive device |
| `/api/v1/spaces/stats/summary` | GET | `routers/spaces_tenanted.py:408` | Space statistics |
| `/api/v1/gateways` | GET | `routers/gateways.py:11` | List gateways |
| `/api/v1/gateways/{gw_eui}` | GET | `routers/gateways.py:70` | Get gateway |
| `/api/v1/gateways/stats/summary` | GET | `routers/gateways.py:137` | Gateway statistics |
| `/health/live` | GET | `main_tenanted.py:403` | Liveness probe (K8s) |

**Analysis:**
These are significant production features that should be documented in the OpenAPI spec:
- **API Key Management** (critical for service-to-service auth)
- **Webhook Secret Management** (critical for webhook signature validation)
- **Orphan Device Management** (critical for device auto-discovery)
- **Site Management** (critical for multi-site tenants)
- **Gateway Management** (operational monitoring)
- **Device Type Registry** (device catalog)
- **Liveness Probe** (Kubernetes health checks)

---

## Router Prefixes Summary

| Router File | Prefix | Tags | Included in main_tenanted.py |
|-------------|--------|------|------------------------------|
| `api_tenants.py` | `/api/v1` | Multi-Tenancy | ✅ Yes |
| `routers/spaces_tenanted.py` | `/api/v1/spaces` | spaces | ✅ Yes |
| `routers/downlink_monitor.py` | `/api/v1/downlinks` | downlinks | ✅ Yes |
| `routers/metrics.py` | (no prefix) | Observability | ✅ Yes |
| `routers/devices.py` | `/api/v1/devices` | devices | ❌ Commented out (TODO: Add tenant scoping) |
| `routers/reservations.py` | `/api/v1/reservations` | reservations | ❌ Commented out (TODO: Add tenant scoping) |
| `routers/gateways.py` | `/api/v1/gateways` | gateways | ❌ Not included |
| `routers/display_policies.py` | `/api/v1/display-policies` | display-policies | ❌ Not included |
| `routers/spaces.py` | `/api/v1/spaces` | spaces | ❌ V4 compatibility (superseded by spaces_tenanted) |

**Note:** Several routers are not included in `main_tenanted.py` (lines 234-237 show TODOs for adding tenant scoping).

---

## Critical Discrepancies

### 1. Display Policy Endpoints Not Mounted
**Severity:** 🔴 HIGH

The `routers/display_policies.py` router is fully implemented but is **NOT** included in `main_tenanted.py`. This means all display policy management endpoints are inaccessible in the production app.

**Location:** `main_tenanted.py:232` (metrics router is included, but display_policies is not)

**Fix Required:**
```python
# main_tenanted.py
from .routers.display_policies import router as display_policies_router
app.include_router(display_policies_router)
```

---

### 2. Devices and Reservations Routers Commented Out
**Severity:** 🟡 MEDIUM

Both `routers/devices.py` and `routers/reservations.py` are commented out in `main_tenanted.py` with TODO notes to add tenant scoping.

**Location:** `main_tenanted.py:234-237`

**Status:**
- `reservations.py` - Already has tenant scoping logic (queries include `tenant_id`)
- `devices.py` - No explicit tenant scoping (lists all devices across tenants)

**Fix Required:**
- Add tenant filtering to `routers/devices.py`
- Uncomment both routers in `main_tenanted.py`

---

### 3. Gateway Router Not Included
**Severity:** 🟢 LOW

The `routers/gateways.py` router exists but is not included in `main_tenanted.py`. Gateways are infrastructure-level resources, so tenant scoping may not be required if tenants share gateways.

**Recommendation:** Determine if gateways should be tenant-scoped or remain global. If global, add router without tenant scoping.

---

### 4. OpenAPI Spec Uses Tenant ID in Path
**Severity:** 🟡 MEDIUM

The OpenAPI spec uses `/api/v1/tenants/{tenant_id}/...` pattern for many endpoints, but the implementation uses JWT/API key authentication to determine tenant context, with paths like `/api/v1/tenants/current/...`.

**Examples:**
- **Spec:** `GET /api/v1/tenants/{tenant_id}` → **Impl:** `GET /api/v1/tenants/current`
- **Spec:** `GET /api/v1/tenants/{tenant_id}/users` → **Impl:** `GET /api/v1/users`
- **Spec:** `POST /api/v1/tenants/{tenant_id}/display-policies` → **Impl:** `POST /api/v1/display-policies`

**Recommendation:** Update OpenAPI spec to match the implementation's authentication-based tenant scoping approach. This is the correct design pattern for multi-tenant SaaS (tenant is implicit from auth, not explicit in URL).

---

## Missing Features

### 1. User Profile Endpoints
**Status:** ❌ Not Implemented

The spec defines:
- `GET /api/v1/me` - Get current user profile
- `GET /api/v1/me/limits` - Get current user rate limits

**Implementation:** Not found in codebase.

**Recommendation:** Implement these endpoints in `api_tenants.py` as they are common requirements for SaaS applications.

---

### 2. Token Refresh Endpoint
**Status:** ❌ Not Implemented

The spec defines:
- `POST /api/v1/auth/refresh` - Refresh JWT access token

**Implementation:** Not found. Current JWTs are long-lived (24 hours).

**Recommendation:** Implement refresh token flow for better security:
1. Short-lived access tokens (15 min)
2. Long-lived refresh tokens (30 days)
3. Refresh endpoint to exchange refresh token for new access token

**Note:** The database has a `refresh_tokens` table (migration 007) but the endpoint is not implemented.

---

### 3. Space Actuation Endpoint
**Status:** ❌ Not Implemented

The spec defines:
- `POST /api/v1/spaces/{space_id}/actuate` - Manually trigger display update

**Implementation:** Not found as a dedicated endpoint.

**Analysis:** Display actuation happens automatically via the state machine when:
- Sensor readings arrive (webhook)
- Reservations are created/cancelled
- Admin overrides are set

**Recommendation:** Implement a manual actuation endpoint for testing and debugging purposes. This is useful for:
- Testing display devices
- Forcing a state refresh
- Debugging state machine issues

---

### 4. Async Task Inspection
**Status:** ❌ Not Implemented

The spec defines:
- `GET /api/v1/tasks/{task_id}` - Get async task status

**Implementation:** Not found.

**Analysis:** The background task manager (`BackgroundTaskManager`) exists but doesn't expose an API for inspecting task status.

**Recommendation:** Implement task inspection API if async operations are exposed to clients. Otherwise, remove from spec.

---

## Recommendations

### Immediate Actions (High Priority)

1. **✅ Fix Display Policy Router Inclusion**
   - Add `display_policies_router` to `main_tenanted.py`
   - Test all display policy endpoints
   - File: `main_tenanted.py:232`

2. **✅ Add Tenant Scoping to Devices Router**
   - Filter devices by tenant_id in all queries
   - Add tenant context dependency
   - Uncomment router inclusion in `main_tenanted.py`
   - File: `routers/devices.py`

3. **✅ Uncomment Reservations Router**
   - Verify tenant scoping is correct
   - Uncomment router inclusion in `main_tenanted.py`
   - File: `main_tenanted.py:236`

4. **✅ Update OpenAPI Spec Tenant Path Prefix**
   - Remove `/tenants/{tenant_id}` from paths
   - Document authentication-based tenant scoping
   - Update display policy paths to `/api/v1/display-policies`
   - File: `docs/OpenAPI_3_1_spec.md`

---

### Short-Term Actions (Medium Priority)

5. **📝 Add Missing Endpoints to OpenAPI Spec**
   - Document all `api_tenants.py` endpoints:
     - API key management (`/api/v1/api-keys`)
     - Webhook secret management (`/api/v1/webhook-secret`)
     - Orphan device management (`/api/v1/orphan-devices`)
     - Site management (`/api/v1/sites`)
   - Document gateway endpoints (`/api/v1/gateways`)
   - Document liveness probe (`/health/live`)
   - File: `docs/OpenAPI_3_1_spec.md`

6. **📝 Implement User Profile Endpoints**
   - `GET /api/v1/me` - Current user info
   - `GET /api/v1/me/limits` - Rate limit status
   - File: `api_tenants.py`

7. **📝 Implement Token Refresh Flow**
   - `POST /api/v1/auth/refresh`
   - Use existing `refresh_tokens` table (migration 007)
   - File: `api_tenants.py`

8. **📝 Clarify Webhook Endpoint**
   - Decide canonical path: `/webhooks/uplink` or `/api/v1/uplink`
   - Implement in `main_tenanted.py` if not present
   - Document signature validation requirements

---

### Long-Term Actions (Low Priority)

9. **🔧 Decide Gateway Router Inclusion**
   - Determine if gateways should be tenant-scoped
   - Include router in `main_tenanted.py` if needed
   - File: `main_tenanted.py`

10. **🔧 Implement Manual Actuation Endpoint**
    - `POST /api/v1/spaces/{space_id}/actuate`
    - For testing and debugging
    - File: `routers/spaces_tenanted.py`

11. **🔧 Implement Task Inspection API**
    - `GET /api/v1/tasks/{task_id}`
    - If async operations are exposed to clients
    - File: New router `routers/tasks.py`

---

## Validation Checklist

Use this checklist to track progress on resolving discrepancies:

- [ ] Display policies router included in main_tenanted.py
- [ ] Devices router has tenant scoping
- [ ] Devices router included in main_tenanted.py
- [ ] Reservations router included in main_tenanted.py
- [ ] OpenAPI spec updated with correct display policy paths
- [ ] OpenAPI spec updated with authentication-based tenant scoping documentation
- [ ] OpenAPI spec includes all API key management endpoints
- [ ] OpenAPI spec includes all webhook secret endpoints
- [ ] OpenAPI spec includes all orphan device endpoints
- [ ] OpenAPI spec includes all site management endpoints
- [ ] OpenAPI spec includes gateway endpoints
- [ ] OpenAPI spec includes liveness probe endpoint
- [ ] User profile endpoints implemented (`/api/v1/me`)
- [ ] Token refresh endpoint implemented (`/api/v1/auth/refresh`)
- [ ] Webhook endpoint path clarified and documented
- [ ] Gateway router inclusion decision made
- [ ] Manual actuation endpoint implemented (optional)
- [ ] Task inspection API implemented (optional)

---

## Testing Recommendations

After implementing fixes, validate with:

1. **Automated OpenAPI Validation**
   ```bash
   # Generate OpenAPI spec from FastAPI app
   python -c "from src.main_tenanted import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi_generated.json

   # Compare with documented spec
   # Use openapi-diff or similar tool
   ```

2. **Manual Endpoint Testing**
   ```bash
   # Test each endpoint category
   # Authentication
   curl -X POST http://localhost:8000/api/v1/auth/login -d '{"email":"test@test.com","password":"pass"}'

   # Spaces (with JWT)
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/spaces

   # Display policies
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/display-policies

   # API keys
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/api-keys
   ```

3. **Integration Tests**
   - Add integration tests for all critical endpoints
   - Verify tenant isolation (RLS)
   - Verify authentication and authorization
   - Test error responses match spec

---

## Appendix: Full Endpoint Inventory

### Implemented Endpoints by Router

#### api_tenants.py (`/api/v1`)
```
POST   /api/v1/auth/login
POST   /api/v1/auth/register
GET    /api/v1/tenants/current
PATCH  /api/v1/tenants/current
GET    /api/v1/sites
POST   /api/v1/sites
GET    /api/v1/sites/{site_id}
PATCH  /api/v1/sites/{site_id}
GET    /api/v1/users
GET    /api/v1/api-keys
POST   /api/v1/api-keys
DELETE /api/v1/api-keys/{key_id}
POST   /api/v1/webhook-secret
POST   /api/v1/webhook-secret/rotate
GET    /api/v1/orphan-devices
POST   /api/v1/orphan-devices/{device_eui}/assign
DELETE /api/v1/orphan-devices/{device_eui}
```

#### routers/spaces_tenanted.py (`/api/v1/spaces`)
```
GET    /api/v1/spaces
GET    /api/v1/spaces/{space_id}
POST   /api/v1/spaces
PATCH  /api/v1/spaces/{space_id}
DELETE /api/v1/spaces/{space_id}
GET    /api/v1/spaces/stats/summary
```

#### routers/reservations.py (`/api/v1/reservations`)
```
GET    /api/v1/reservations
POST   /api/v1/reservations
GET    /api/v1/reservations/{reservation_id}
DELETE /api/v1/reservations/{reservation_id}
```

#### routers/devices.py (`/api/v1/devices`) - NOT INCLUDED IN APP
```
GET    /api/v1/devices/device-types
GET    /api/v1/devices
GET    /api/v1/devices/{deveui}
GET    /api/v1/devices/full-metadata
PUT    /api/v1/devices/{deveui}
PATCH  /api/v1/devices/{deveui}/archive
```

#### routers/display_policies.py (`/api/v1/display-policies`) - NOT INCLUDED IN APP
```
GET    /api/v1/display-policies
GET    /api/v1/display-policies/{policy_id}
POST   /api/v1/display-policies
PATCH  /api/v1/display-policies/{policy_id}
POST   /api/v1/display-policies/admin-overrides
DELETE /api/v1/display-policies/admin-overrides/{override_id}
GET    /api/v1/display-policies/spaces/{space_id}/computed-state
```

#### routers/downlink_monitor.py (`/api/v1/downlinks`)
```
GET    /api/v1/downlinks/queue/metrics
GET    /api/v1/downlinks/queue/health
POST   /api/v1/downlinks/queue/clear-metrics
```

#### routers/gateways.py (`/api/v1/gateways`) - NOT INCLUDED IN APP
```
GET    /api/v1/gateways
GET    /api/v1/gateways/{gw_eui}
GET    /api/v1/gateways/stats/summary
```

#### routers/metrics.py (no prefix)
```
GET    /metrics
```

#### main_tenanted.py (app-level endpoints)
```
GET    /health
GET    /health/ready
GET    /health/live
```

---

## Conclusion

The OpenAPI specification and implementation have significant overlap but several critical discrepancies that need to be resolved:

1. **Router Inclusion Issues**: Display policies, devices, and gateways routers are implemented but not mounted in the main app
2. **Path Prefix Mismatches**: OpenAPI spec uses `/tenants/{tenant_id}` prefix but implementation uses authentication-based tenant scoping
3. **Missing Documentation**: Many production-critical endpoints (API keys, webhook secrets, orphan devices, sites) are not documented in the OpenAPI spec
4. **Missing Implementation**: Some spec-defined endpoints (user profile, token refresh, manual actuation) are not implemented

**Priority:**
1. Fix router inclusion (display policies, devices, gateways)
2. Update OpenAPI spec to match actual implementation patterns
3. Document all implemented endpoints
4. Implement missing critical features (user profile, token refresh)

**Next Steps:**
1. Review and approve this validation report
2. Create GitHub issues for each discrepancy
3. Prioritize and schedule fixes
4. Update OpenAPI spec to be the source of truth
5. Set up automated OpenAPI validation in CI/CD pipeline
