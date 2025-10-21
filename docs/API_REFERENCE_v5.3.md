# Smart Parking Platform API Reference - v5.3

**Base URL:** `https://api.verdegris.eu`
**Version:** 5.3.0
**Last Updated:** 2025-10-21
**Status:** ✅ All routers enabled and fully functional

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Rate Limiting](#rate-limiting)
4. [Error Handling](#error-handling)
5. [Health & Monitoring](#health--monitoring)
6. [Authentication & Tenancy](#authentication--tenancy-endpoints)
7. [Sites & Spaces](#sites--spaces)
8. [Reservations](#reservations)
9. [Devices](#devices)
10. [Display Policies](#display-policies)
11. [Downlink Management](#downlink-management)
12. [Webhook Integration](#webhook-integration)
13. [Audit & Security](#audit--security)
14. [Admin Endpoints](#admin-endpoints)

---

## Overview

The Smart Parking Platform API is a RESTful API built with FastAPI that provides comprehensive parking management capabilities with multi-tenancy, real-time occupancy tracking, and reservation management.

### Key Features

- **Multi-tenant architecture** with complete data isolation
- **Dual authentication** - JWT tokens for users, API keys for services
- **Role-based access control** (RBAC) with 4-level hierarchy
- **Real-time occupancy** via LoRaWAN sensors
- **Reservation engine** with overlap prevention
- **Display control** with policy-driven state machines
- **Comprehensive observability** with Prometheus metrics

### API Conventions

- **HTTP Methods:** GET (read), POST (create), PATCH (update), DELETE (delete)
- **Response Format:** JSON
- **Date/Time Format:** ISO 8601 (UTC)
- **IDs:** UUIDs (RFC 4122)
- **Status Codes:** Standard HTTP status codes

---

## Authentication

The API supports two authentication methods:

### 1. JWT Tokens (User Authentication)

**Use Case:** User-facing applications, web/mobile apps

**Flow:**
1. Register tenant and owner user OR login with existing credentials
2. Receive JWT access token (24-hour expiry)
3. Include token in `Authorization` header for all requests

**Example:**
```bash
# Login
curl -X POST https://api.verdegris.eu/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@acme.com",
    "password": "secure-password"
  }'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@acme.com",
    "tenant_id": "tenant-uuid",
    "role": "owner"
  }
}

# Use token
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  https://api.verdegris.eu/api/v1/spaces
```

### 2. API Keys (Service Authentication)

**Use Case:** Service-to-service integration, webhooks, background jobs

**Flow:**
1. Create API key via admin endpoint (requires Owner/Admin role)
2. Store key securely (shown only once)
3. Include key in `X-API-Key` header

**Example:**
```bash
# Create API key (requires JWT auth)
curl -X POST https://api.verdegris.eu/api/v1/tenants/{tenant_id}/api-keys \
  -H "Authorization: Bearer {jwt_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Webhook Service",
    "scopes": ["webhook:ingest", "spaces:read"],
    "expires_at": "2026-01-01T00:00:00Z"
  }'

# Use API key
curl -H "X-API-Key: your-64-char-hex-api-key" \
  https://api.verdegris.eu/api/v1/spaces
```

### Role-Based Access Control (RBAC)

| Role | Permissions |
|------|-------------|
| **Owner** | Full access: manage users, delete tenant, all operations |
| **Admin** | Manage spaces, reservations, devices, API keys, display policies |
| **Operator** | Create/update spaces and reservations, view all resources |
| **Viewer** | Read-only access to spaces, reservations, sensor data |

### API Key Scopes

| Scope | Permissions |
|-------|-------------|
| `spaces:read` | View spaces and their status |
| `spaces:write` | Create/update spaces (includes read) |
| `devices:read` | View devices |
| `devices:write` | Manage devices (includes read) |
| `reservations:read` | View reservations |
| `reservations:write` | Create/cancel reservations (includes read) |
| `telemetry:read` | Access sensor readings |
| `webhook:ingest` | Submit uplinks (webhook-only) |
| `admin:*` | Full administrative access |

---

## Rate Limiting

Rate limits are enforced per tenant using a token bucket algorithm:

- **Default:** 100 requests/minute per tenant
- **Burst:** Up to 200 requests in short burst
- **Webhook endpoint:** 200 requests/minute (higher limit)

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1634567890
```

**429 Response:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit of 100 requests/minute exceeded",
  "retry_after": 42
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "error": "error_code",
  "message": "Human-readable error description",
  "details": {
    "field": "Additional context"
  },
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Successful request |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request body, missing fields |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Overlapping reservation, duplicate resource |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (rare) |
| 503 | Service Unavailable | Dependency unavailable |

### Common Error Codes

| Error Code | Description |
|------------|-------------|
| `authentication_failed` | Invalid credentials |
| `insufficient_permissions` | User/API key lacks required role/scope |
| `resource_not_found` | Requested resource does not exist |
| `validation_error` | Request validation failed |
| `reservation_conflict` | Overlapping reservation exists |
| `tenant_mismatch` | Resource belongs to different tenant |
| `rate_limit_exceeded` | Too many requests |

---

## Health & Monitoring

### GET /health

Basic health check.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "5.3.0",
  "timestamp": "2025-10-21T10:30:00Z"
}
```

### GET /health/ready

Kubernetes readiness probe - checks all dependencies.

**Response:** `200 OK` or `503 Service Unavailable`
```json
{
  "status": "ready",
  "checks": {
    "database": "ready",
    "redis": "ready",
    "chirpstack_mqtt": "ready",
    "downlink_worker": "ready"
  },
  "stats": {
    "db_pool": {
      "size": 20,
      "free_connections": 15
    },
    "redis": {
      "connected": true,
      "memory_used_mb": 45
    }
  }
}
```

**Use Case:** Kubernetes uses this to determine if pod can receive traffic.

### GET /health/live

Kubernetes liveness probe - checks if process is alive.

**Response:** `200 OK` or `503 Service Unavailable`
```json
{
  "status": "alive",
  "checks": {
    "task_manager": "alive",
    "downlink_worker": "alive",
    "webhook_spool_worker": "alive"
  }
}
```

**Use Case:** Kubernetes uses this to restart deadlocked pods.

### GET /metrics

Prometheus metrics endpoint (OpenMetrics format).

**Authentication:** None required

**Response:** `200 OK` (text/plain)
```
# HELP uplink_requests_total Total uplink webhook requests received
# TYPE uplink_requests_total counter
uplink_requests_total{status="success",tenant_id="tenant-uuid"} 1523

# HELP downlink_queue_depth Current depth of downlink queue
# TYPE downlink_queue_depth gauge
downlink_queue_depth{queue_type="pending"} 12
downlink_queue_depth{queue_type="dead_letter"} 2

# HELP actuation_latency_seconds End-to-end actuation latency
# TYPE actuation_latency_seconds histogram
actuation_latency_seconds_bucket{tenant_id="tenant-uuid",le="1.0"} 1234
actuation_latency_seconds_bucket{tenant_id="tenant-uuid",le="5.0"} 1456
actuation_latency_seconds_sum{tenant_id="tenant-uuid"} 3456.78
actuation_latency_seconds_count{tenant_id="tenant-uuid"} 1500
```

**Use Case:** Prometheus scrapes this endpoint every 15-60 seconds for monitoring.

---

## Authentication & Tenancy Endpoints

### POST /api/v1/tenants

Register a new tenant organization and owner user.

**Authentication:** None required (public endpoint)

**Request Body:**
```json
{
  "tenant": {
    "name": "Acme Corporation",
    "slug": "acme",
    "metadata": {
      "industry": "parking",
      "company_size": "50-200"
    },
    "settings": {
      "timezone": "America/New_York",
      "currency": "USD"
    }
  },
  "user": {
    "email": "admin@acme.com",
    "name": "John Admin",
    "password": "SecurePassword123!@#",
    "metadata": {
      "phone": "+1-555-0123"
    }
  }
}
```

**Response:** `201 Created`
```json
{
  "tenant": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Acme Corporation",
    "slug": "acme",
    "is_active": true,
    "created_at": "2025-10-21T10:00:00Z"
  },
  "user": {
    "id": "660f9511-f39c-52e5-b827-557766551111",
    "email": "admin@acme.com",
    "name": "John Admin",
    "role": "owner",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Validations:**
- Tenant slug must be unique, lowercase, alphanumeric + hyphens
- Email must be unique across all tenants
- Password minimum 12 characters, must include uppercase, lowercase, number, symbol

### POST /api/v1/auth/login

Login and receive JWT access token.

**Authentication:** None required

**Request Body:**
```json
{
  "email": "admin@acme.com",
  "password": "SecurePassword123!@#"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "refresh_token": "a1b2c3d4e5f6...",
  "user": {
    "id": "660f9511-f39c-52e5-b827-557766551111",
    "email": "admin@acme.com",
    "name": "John Admin",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "owner"
  }
}
```

**Error Response:** `401 Unauthorized`
```json
{
  "error": "authentication_failed",
  "message": "Invalid email or password"
}
```

### POST /api/v1/auth/refresh

Refresh access token using refresh token.

**Authentication:** None required (uses refresh token)

**Request Body:**
```json
{
  "refresh_token": "a1b2c3d4e5f6..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### GET /api/v1/tenants/{tenant_id}

Get tenant details.

**Authentication:** Required (JWT or API key)

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Acme Corporation",
  "slug": "acme",
  "is_active": true,
  "metadata": {
    "industry": "parking"
  },
  "settings": {
    "timezone": "America/New_York"
  },
  "created_at": "2025-10-21T10:00:00Z",
  "updated_at": "2025-10-21T10:00:00Z"
}
```

### GET /api/v1/tenants/{tenant_id}/users

List users in tenant.

**Authentication:** Required (Admin or Owner role)

**Query Parameters:**
- `limit` (int, default: 100) - Results per page
- `offset` (int, default: 0) - Pagination offset
- `role` (string, optional) - Filter by role

**Response:** `200 OK`
```json
{
  "users": [
    {
      "id": "660f9511-f39c-52e5-b827-557766551111",
      "email": "admin@acme.com",
      "name": "John Admin",
      "role": "owner",
      "is_active": true,
      "email_verified": true,
      "created_at": "2025-10-21T10:00:00Z",
      "last_login_at": "2025-10-21T14:30:00Z"
    },
    {
      "id": "770fa622-g40d-63f6-c938-668877662222",
      "email": "operator@acme.com",
      "name": "Jane Operator",
      "role": "operator",
      "is_active": true,
      "email_verified": true,
      "created_at": "2025-10-21T11:00:00Z"
    }
  ],
  "total": 2,
  "limit": 100,
  "offset": 0
}
```

### POST /api/v1/tenants/{tenant_id}/users

Invite new user to tenant.

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "email": "operator@acme.com",
  "name": "Jane Operator",
  "role": "operator",
  "send_invite_email": true
}
```

**Response:** `201 Created`
```json
{
  "id": "770fa622-g40d-63f6-c938-668877662222",
  "email": "operator@acme.com",
  "name": "Jane Operator",
  "role": "operator",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_active": true,
  "invite_token": "inv_a1b2c3d4e5f6...",
  "invite_expires_at": "2025-10-28T10:00:00Z"
}
```

### PATCH /api/v1/tenants/{tenant_id}/users/{user_id}

Update user role or status.

**Authentication:** Required (Owner role)

**Request Body:**
```json
{
  "role": "admin",
  "is_active": true
}
```

**Response:** `200 OK` (updated user object)

### DELETE /api/v1/tenants/{tenant_id}/users/{user_id}

Remove user from tenant.

**Authentication:** Required (Owner role)

**Response:** `200 OK`
```json
{
  "message": "User removed from tenant",
  "user_id": "770fa622-g40d-63f6-c938-668877662222"
}
```

---

## Sites & Spaces

### POST /api/v1/tenants/{tenant_id}/sites

Create a new site (physical location).

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "name": "Downtown Parking Garage",
  "address": "123 Main Street, New York, NY 10001",
  "timezone": "America/New_York",
  "gps_latitude": 40.7580,
  "gps_longitude": -73.9855,
  "metadata": {
    "floors": 5,
    "total_capacity": 250
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "880gb733-h51e-74g7-d049-779988773333",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Downtown Parking Garage",
  "address": "123 Main Street, New York, NY 10001",
  "timezone": "America/New_York",
  "gps_latitude": 40.7580,
  "gps_longitude": -73.9855,
  "metadata": {
    "floors": 5,
    "total_capacity": 250
  },
  "created_at": "2025-10-21T10:00:00Z"
}
```

### GET /api/v1/tenants/{tenant_id}/sites

List all sites for tenant.

**Authentication:** Required

**Query Parameters:**
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Response:** `200 OK`
```json
{
  "sites": [
    {
      "id": "880gb733-h51e-74g7-d049-779988773333",
      "name": "Downtown Parking Garage",
      "address": "123 Main Street, New York, NY 10001",
      "space_count": 125,
      "occupied_count": 45,
      "occupancy_rate": 0.36
    }
  ],
  "total": 1
}
```

### POST /api/v1/sites/{site_id}/spaces

Create a parking space.

**Authentication:** Required (Admin, Operator, or Owner role)

**Request Body:**
```json
{
  "code": "A-101",
  "name": "Space A-101 (First Floor)",
  "floor": "1",
  "zone": "A",
  "space_type": "standard",
  "sensor_eui": "0004a30b001a2b3c",
  "display_eui": "2020203907290902",
  "gps_latitude": 40.7580,
  "gps_longitude": -73.9855,
  "metadata": {
    "ada_compliant": false,
    "ev_charger": false,
    "width_meters": 2.5,
    "length_meters": 5.0
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "990hc844-i62f-85h8-e150-880099884444",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "site_id": "880gb733-h51e-74g7-d049-779988773333",
  "code": "A-101",
  "name": "Space A-101 (First Floor)",
  "floor": "1",
  "zone": "A",
  "space_type": "standard",
  "state": "free",
  "sensor_eui": "0004a30b001a2b3c",
  "display_eui": "2020203907290902",
  "created_at": "2025-10-21T10:00:00Z"
}
```

### GET /api/v1/spaces

List all parking spaces (tenant-scoped).

**Authentication:** Required

**Query Parameters:**
- `site_id` (UUID, optional) - Filter by site
- `floor` (string, optional) - Filter by floor
- `zone` (string, optional) - Filter by zone
- `state` (enum, optional) - Filter by state: `free`, `occupied`, `reserved`, `maintenance`
- `space_type` (string, optional) - Filter by type
- `limit` (int, default: 100, max: 1000)
- `offset` (int, default: 0)

**Example:**
```bash
GET /api/v1/spaces?state=free&floor=1&limit=20
```

**Response:** `200 OK`
```json
{
  "spaces": [
    {
      "id": "990hc844-i62f-85h8-e150-880099884444",
      "code": "A-101",
      "name": "Space A-101 (First Floor)",
      "site_name": "Downtown Parking Garage",
      "floor": "1",
      "zone": "A",
      "state": "free",
      "sensor_eui": "0004a30b001a2b3c",
      "display_eui": "2020203907290902",
      "last_sensor_reading_at": "2025-10-21T14:25:00Z",
      "current_reservation": null
    }
  ],
  "total": 1,
  "filters": {
    "state": "free",
    "floor": "1"
  }
}
```

### GET /api/v1/spaces/{space_id}

Get details of a single parking space.

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "id": "990hc844-i62f-85h8-e150-880099884444",
  "code": "A-101",
  "name": "Space A-101 (First Floor)",
  "site_id": "880gb733-h51e-74g7-d049-779988773333",
  "site_name": "Downtown Parking Garage",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "floor": "1",
  "zone": "A",
  "space_type": "standard",
  "state": "free",
  "sensor_eui": "0004a30b001a2b3c",
  "display_eui": "2020203907290902",
  "gps_latitude": 40.7580,
  "gps_longitude": -73.9855,
  "metadata": {
    "ada_compliant": false,
    "ev_charger": false
  },
  "last_sensor_reading": {
    "timestamp": "2025-10-21T14:25:00Z",
    "occupancy_state": "free",
    "battery": 3.6,
    "rssi": -85,
    "snr": 7.5
  },
  "current_reservation": null,
  "created_at": "2025-10-21T10:00:00Z",
  "updated_at": "2025-10-21T14:25:00Z"
}
```

### PATCH /api/v1/spaces/{space_id}

Update a parking space (partial update).

**Authentication:** Required (Admin, Operator, or Owner role)

**Request Body (all fields optional):**
```json
{
  "name": "Space A-101 (First Floor - VIP)",
  "state": "maintenance",
  "metadata": {
    "ada_compliant": true,
    "notes": "Reserved for executives"
  }
}
```

**Response:** `200 OK` (updated space object)

### DELETE /api/v1/spaces/{space_id}

Soft delete a parking space.

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "message": "Space deleted",
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "deleted_at": "2025-10-21T15:00:00Z"
}
```

**Error:** `409 Conflict` if active reservations exist
```json
{
  "error": "active_reservations_exist",
  "message": "Cannot delete space with active reservations",
  "active_reservations": 2
}
```

### GET /api/v1/spaces/{space_id}/availability

Check parking space availability for a time range.

**Authentication:** Required

**Query Parameters:**
- `from` (ISO 8601 datetime, required) - Start of availability check
- `to` (ISO 8601 datetime, required) - End of availability check

**Example:**
```bash
GET /api/v1/spaces/990hc844-i62f-85h8-e150-880099884444/availability?from=2025-10-22T09:00:00Z&to=2025-10-22T17:00:00Z
```

**Response:** `200 OK`
```json
{
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "space_code": "A-101",
  "space_name": "Space A-101 (First Floor)",
  "query_start": "2025-10-22T09:00:00Z",
  "query_end": "2025-10-22T17:00:00Z",
  "is_available": false,
  "reservations": [
    {
      "id": "aa0id955-j73g-96i9-f261-991100995555",
      "reserved_from": "2025-10-22T10:00:00Z",
      "reserved_until": "2025-10-22T14:00:00Z",
      "status": "confirmed",
      "user_email": "user@example.com"
    }
  ],
  "current_state": "free",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Use Case:** Check if space is available before creating reservation.

---

## Reservations

### POST /api/v1/reservations

Create a parking reservation with **idempotency** and **overlap prevention**.

**Authentication:** Required (any authenticated user)

**Request Body:**
```json
{
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "reserved_from": "2025-10-22T10:00:00Z",
  "reserved_until": "2025-10-22T14:00:00Z",
  "user_email": "user@example.com",
  "user_phone": "+1-555-0199",
  "request_id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "metadata": {
    "vehicle_plate": "ABC-1234",
    "purpose": "business_meeting"
  }
}
```

**Key Features:**
- **Idempotency:** Same `request_id` returns existing reservation (prevents double-booking on retry)
- **Overlap Prevention:** PostgreSQL EXCLUDE constraint prevents conflicts at database level
- **Automatic Expiry:** Background job expires reservation after `reserved_until`

**Response:** `201 Created`
```json
{
  "id": "aa0id955-j73g-96i9-f261-991100995555",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "space_code": "A-101",
  "reserved_from": "2025-10-22T10:00:00Z",
  "reserved_until": "2025-10-22T14:00:00Z",
  "duration_hours": 4,
  "status": "confirmed",
  "user_email": "user@example.com",
  "user_phone": "+1-555-0199",
  "request_id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "metadata": {
    "vehicle_plate": "ABC-1234"
  },
  "created_at": "2025-10-21T15:00:00Z"
}
```

**Error:** `409 Conflict` (overlapping reservation)
```json
{
  "error": "reservation_conflict",
  "message": "Overlapping reservation exists for this space and time range",
  "requested": {
    "space_id": "990hc844-i62f-85h8-e150-880099884444",
    "reserved_from": "2025-10-22T10:00:00Z",
    "reserved_until": "2025-10-22T14:00:00Z"
  },
  "conflicts": [
    {
      "id": "bb1je066-k84h-07j0-g372-002211006666",
      "reserved_from": "2025-10-22T09:00:00Z",
      "reserved_until": "2025-10-22T11:00:00Z",
      "status": "confirmed"
    }
  ]
}
```

**Validations:**
- Maximum reservation duration: 24 hours
- `reserved_until` must be after `reserved_from`
- Space must exist and be available

### GET /api/v1/reservations

List reservations (tenant-scoped).

**Authentication:** Required

**Query Parameters:**
- `space_id` (UUID, optional) - Filter by space
- `user_email` (string, optional) - Filter by user
- `status` (enum, optional) - Filter by status: `pending`, `confirmed`, `cancelled`, `expired`
- `date_from` (ISO datetime, optional) - Filter by start date
- `date_to` (ISO datetime, optional) - Filter by end date
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Example:**
```bash
GET /api/v1/reservations?status=confirmed&date_from=2025-10-22T00:00:00Z&limit=50
```

**Response:** `200 OK`
```json
{
  "reservations": [
    {
      "id": "aa0id955-j73g-96i9-f261-991100995555",
      "space_code": "A-101",
      "reserved_from": "2025-10-22T10:00:00Z",
      "reserved_until": "2025-10-22T14:00:00Z",
      "status": "confirmed",
      "user_email": "user@example.com",
      "created_at": "2025-10-21T15:00:00Z"
    }
  ],
  "total": 1,
  "filters": {
    "status": "confirmed",
    "date_from": "2025-10-22T00:00:00Z"
  }
}
```

### GET /api/v1/reservations/{reservation_id}

Get reservation details.

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "id": "aa0id955-j73g-96i9-f261-991100995555",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "space_code": "A-101",
  "space_name": "Space A-101 (First Floor)",
  "site_name": "Downtown Parking Garage",
  "reserved_from": "2025-10-22T10:00:00Z",
  "reserved_until": "2025-10-22T14:00:00Z",
  "duration_hours": 4,
  "status": "confirmed",
  "user_email": "user@example.com",
  "user_phone": "+1-555-0199",
  "request_id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "metadata": {
    "vehicle_plate": "ABC-1234",
    "purpose": "business_meeting"
  },
  "created_at": "2025-10-21T15:00:00Z",
  "updated_at": "2025-10-21T15:00:00Z"
}
```

### DELETE /api/v1/reservations/{reservation_id}

Cancel a reservation.

**Authentication:** Required (Admin, Operator, Owner, or reservation owner)

**Response:** `200 OK`
```json
{
  "message": "Reservation cancelled",
  "reservation_id": "aa0id955-j73g-96i9-f261-991100995555",
  "status": "cancelled",
  "cancelled_at": "2025-10-21T16:00:00Z"
}
```

**Error:** `409 Conflict`
```json
{
  "error": "reservation_already_cancelled",
  "message": "Reservation is already cancelled or expired"
}
```

---

## Devices

### GET /api/v1/devices

List all devices (sensors + displays) for tenant.

**Authentication:** Required

**Query Parameters:**
- `device_type` (enum, optional) - Filter by type: `sensor`, `display`
- `status` (enum, optional) - Filter by status: `active`, `inactive`, `orphan`
- `site_id` (UUID, optional) - Filter by site
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Response:** `200 OK`
```json
{
  "devices": [
    {
      "id": "cc2kf177-l95i-18k1-h483-113322117777",
      "dev_eui": "0004a30b001a2b3c",
      "device_type": "sensor",
      "device_model": "Browan TBMS100",
      "status": "active",
      "assigned_to_space": {
        "space_id": "990hc844-i62f-85h8-e150-880099884444",
        "space_code": "A-101"
      },
      "last_seen_at": "2025-10-21T14:25:00Z",
      "battery": 3.6,
      "rssi": -85
    },
    {
      "id": "dd3lg288-m06j-29l2-i594-224433228888",
      "dev_eui": "2020203907290902",
      "device_type": "display",
      "device_model": "Kuando Busylight IoT",
      "status": "active",
      "assigned_to_space": {
        "space_id": "990hc844-i62f-85h8-e150-880099884444",
        "space_code": "A-101"
      },
      "last_seen_at": "2025-10-21T14:20:00Z",
      "current_color": "green"
    }
  ],
  "total": 2
}
```

### GET /api/v1/devices/orphans

List all orphan devices (auto-discovered, not yet assigned).

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "orphan_devices": [
    {
      "id": "ee4mh399-n17k-30m3-j605-335544339999",
      "dev_eui": "0004a30b001a9999",
      "device_type": "sensor",
      "device_model": "Browan TBMS100",
      "status": "orphan",
      "first_seen_at": "2025-10-21T12:00:00Z",
      "last_seen_at": "2025-10-21T14:25:00Z",
      "uplink_count": 47,
      "battery": 3.8,
      "rssi": -78
    }
  ],
  "total": 1
}
```

**Use Case:** Admin reviews orphan devices and assigns them to spaces.

### POST /api/v1/spaces/{space_id}/sensor

Assign sensor device to space.

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "device_eui": "0004a30b001a9999"
}
```

**Response:** `200 OK`
```json
{
  "message": "Sensor assigned to space",
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "space_code": "A-101",
  "sensor_eui": "0004a30b001a9999",
  "device_status": "active"
}
```

### POST /api/v1/spaces/{space_id}/display

Assign display device to space.

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "device_eui": "2020203907299999"
}
```

**Response:** `200 OK`

### DELETE /api/v1/spaces/{space_id}/sensor

Unassign sensor from space.

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "message": "Sensor unassigned from space",
  "space_id": "990hc844-i62f-85h8-e150-880099884444",
  "sensor_eui": "0004a30b001a9999",
  "device_status": "inactive"
}
```

### DELETE /api/v1/spaces/{space_id}/display

Unassign display from space.

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`

---

## Display Policies

### GET /api/v1/tenants/{tenant_id}/display-policies

List display policies for tenant.

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "policies": [
    {
      "id": "ff5ni400-o28l-41n4-k716-446655440000",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "policy_name": "Standard 3-Color Traffic Light",
      "is_active": true,
      "display_codes": {
        "free": {
          "led_color": "green",
          "blink": false
        },
        "occupied": {
          "led_color": "red",
          "blink": false
        },
        "reserved": {
          "led_color": "blue",
          "blink": true
        }
      },
      "created_at": "2025-10-21T10:00:00Z",
      "activated_at": "2025-10-21T10:00:00Z"
    }
  ],
  "active_policy_id": "ff5ni400-o28l-41n4-k716-446655440000"
}
```

### POST /api/v1/tenants/{tenant_id}/display-policies

Create new display policy.

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "policy_name": "Custom 4-Color Policy",
  "display_codes": {
    "free": {
      "led_color": "green",
      "blink": false
    },
    "occupied": {
      "led_color": "red",
      "blink": false
    },
    "reserved": {
      "led_color": "blue",
      "blink": true
    },
    "maintenance": {
      "led_color": "orange",
      "blink": false
    }
  },
  "is_active": false
}
```

**Response:** `201 Created`

### POST /api/v1/tenants/{tenant_id}/display-policies/{policy_id}/activate

Activate display policy (deactivates all others).

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "message": "Display policy activated",
  "policy_id": "ff5ni400-o28l-41n4-k716-446655440000",
  "cache_invalidated": true,
  "affected_displays": 125
}
```

**Effects:**
- Deactivates all other policies for tenant (only one active policy allowed)
- Increments Redis cache version
- All displays will update on next state change

---

## Downlink Management

### GET /api/v1/downlinks/queue/metrics

Get downlink queue metrics.

**Authentication:** Required

**Response:** `200 OK`
```json
{
  "queue": {
    "pending_depth": 12,
    "processing_depth": 2,
    "dead_letter_depth": 1
  },
  "throughput": {
    "enqueued_total": 1523,
    "sent_total": 1485,
    "failed_total": 15,
    "dead_lettered_total": 8,
    "deduplicated_total": 235,
    "coalesced_total": 89
  },
  "success_rate": 0.990,
  "latency": {
    "p50_ms": 145,
    "p95_ms": 3200,
    "p99_ms": 4850
  },
  "rate_limits": {
    "gateway": {
      "limit_per_minute": 30,
      "current_usage": 12
    },
    "tenant": {
      "limit_per_minute": 100,
      "current_usage": 23
    }
  }
}
```

**Use Case:** Monitoring dashboard, alerting on queue depth or success rate.

### GET /api/v1/downlinks/queue/health

Get downlink queue health status.

**Authentication:** Required

**Response:** `200 OK` or `503 Service Unavailable`
```json
{
  "status": "healthy",
  "checks": {
    "worker_alive": true,
    "redis_connection": true,
    "chirpstack_connection": true
  },
  "queue_depth": 12,
  "dead_letter_depth": 1,
  "last_processed_at": "2025-10-21T14:29:45Z"
}
```

### POST /api/v1/downlinks/queue/clear-metrics

Reset queue metrics (admin operation).

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "message": "Queue metrics cleared"
}
```

---

## Webhook Integration

### POST /webhooks/uplink

ChirpStack webhook endpoint for device uplinks.

**Authentication:** Required (HMAC-SHA256 signature validation)

**Headers:**
```
X-Chirpstack-Signature: sha256=a1b2c3d4e5f6...
Content-Type: application/json
```

**Request Body (from ChirpStack):**
```json
{
  "deviceInfo": {
    "devEui": "0004a30b001a2b3c",
    "deviceName": "Sensor A-101"
  },
  "fCnt": 1234,
  "data": "AQIDBAUGBw==",
  "rxInfo": [{
    "gatewayId": "gateway-001",
    "rssi": -85,
    "snr": 7.5,
    "time": "2025-10-21T14:25:00Z"
  }]
}
```

**Response:** `200 OK`
```json
{
  "status": "processed",
  "space_code": "A-101",
  "state_change": {
    "from": "free",
    "to": "occupied"
  },
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000"
}
```

**Key Features:**
- **Signature validation:** HMAC-SHA256 with per-tenant secret
- **fcnt deduplication:** Prevents duplicate processing (unique constraint)
- **Back-pressure handling:** Spools to disk if database unavailable
- **Orphan device tracking:** Auto-discovers new devices

**Error:** `401 Unauthorized` (invalid signature)
```json
{
  "error": "invalid_signature",
  "message": "Webhook signature validation failed"
}
```

---

## Audit & Security

### GET /api/v1/tenants/{tenant_id}/audit-log

Query audit log for tenant.

**Authentication:** Required (Admin or Owner role)

**Query Parameters:**
- `action` (string, optional) - Filter by action (e.g., "space.delete")
- `user_id` (UUID, optional) - Filter by user
- `resource_type` (string, optional) - Filter by resource type
- `date_from` (ISO datetime, optional)
- `date_to` (ISO datetime, optional)
- `limit` (int, default: 100)
- `offset` (int, default: 0)

**Response:** `200 OK`
```json
{
  "audit_logs": [
    {
      "id": "gg6oj511-p39m-52o5-l827-557766551111",
      "created_at": "2025-10-21T15:00:00Z",
      "actor_type": "user",
      "actor_name": "admin@acme.com",
      "action": "space.delete",
      "resource_type": "space",
      "resource_id": "990hc844-i62f-85h8-e150-880099884444",
      "old_values": {
        "code": "A-101",
        "state": "free"
      },
      "new_values": null,
      "success": true,
      "request_id": "req-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }
  ],
  "total": 1
}
```

**Use Case:** Security audit, compliance reporting, incident investigation.

### POST /api/v1/tenants/{tenant_id}/api-keys

Create API key for tenant.

**Authentication:** Required (Admin or Owner role)

**Request Body:**
```json
{
  "name": "Webhook Service",
  "scopes": ["webhook:ingest", "spaces:read"],
  "expires_at": "2026-01-01T00:00:00Z",
  "metadata": {
    "purpose": "ChirpStack webhook integration"
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "hh7pk622-q40n-63p6-m938-668877662222",
  "name": "Webhook Service",
  "key": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
  "scopes": ["webhook:ingest", "spaces:read"],
  "created_at": "2025-10-21T15:00:00Z",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

**Important:** API key is shown **only once**. Store securely!

### GET /api/v1/tenants/{tenant_id}/api-keys

List API keys for tenant.

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "api_keys": [
    {
      "id": "hh7pk622-q40n-63p6-m938-668877662222",
      "name": "Webhook Service",
      "scopes": ["webhook:ingest", "spaces:read"],
      "created_at": "2025-10-21T15:00:00Z",
      "expires_at": "2026-01-01T00:00:00Z",
      "last_used_at": "2025-10-21T14:30:00Z",
      "revoked_at": null
    }
  ],
  "total": 1
}
```

### DELETE /api/v1/tenants/{tenant_id}/api-keys/{key_id}

Revoke API key (immediate effect).

**Authentication:** Required (Admin or Owner role)

**Response:** `200 OK`
```json
{
  "message": "API key revoked",
  "key_id": "hh7pk622-q40n-63p6-m938-668877662222",
  "revoked_at": "2025-10-21T16:00:00Z",
  "revoked_by": "660f9511-f39c-52e5-b827-557766551111"
}
```

**Effect:** Revoked key fails authentication immediately (no grace period).

---

## Admin Endpoints

### GET /api/v1/admin/system/stats

System-wide statistics (super admin only).

**Authentication:** Required (super admin API key)

**Response:** `200 OK`
```json
{
  "tenants": {
    "total": 25,
    "active": 23
  },
  "spaces": {
    "total": 3420,
    "occupied": 1234,
    "reserved": 456,
    "occupancy_rate": 0.49
  },
  "devices": {
    "sensors": 3420,
    "displays": 2100,
    "orphans": 15
  },
  "reservations": {
    "active": 456,
    "today": 892
  },
  "uptime_seconds": 1234567
}
```

---

## Appendices

### A. Webhook Signature Validation

To validate webhook signatures (for custom integrations):

```python
import hmac
import hashlib

def validate_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Validate HMAC-SHA256 webhook signature

    Args:
        payload: Raw request body (bytes)
        signature: X-Chirpstack-Signature header value
        secret: Tenant webhook secret

    Returns:
        True if valid, False otherwise
    """
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Extract hash from "sha256=..." format
    provided = signature.replace("sha256=", "")

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, provided)
```

### B. Idempotency Keys

All mutation endpoints (POST, PATCH, DELETE) support idempotency via `request_id`:

```bash
# First request
curl -X POST https://api.verdegris.eu/api/v1/reservations \
  -H "Authorization: Bearer {token}" \
  -d '{"request_id": "req-12345", ...}'
# Response: 201 Created

# Retry (same request_id)
curl -X POST https://api.verdegris.eu/api/v1/reservations \
  -H "Authorization: Bearer {token}" \
  -d '{"request_id": "req-12345", ...}'
# Response: 200 OK (returns existing reservation)
```

### C. Pagination

All list endpoints support pagination:

```bash
# First page
GET /api/v1/spaces?limit=50&offset=0

# Second page
GET /api/v1/spaces?limit=50&offset=50
```

Response includes pagination metadata:
```json
{
  "items": [...],
  "total": 250,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

### D. Filtering & Searching

Use query parameters for filtering:

```bash
# Multiple filters
GET /api/v1/spaces?state=free&floor=1&zone=A

# Date range
GET /api/v1/reservations?date_from=2025-10-22T00:00:00Z&date_to=2025-10-23T00:00:00Z

# Search by code (partial match)
GET /api/v1/spaces?code=A-1*
```

---

## Recent Updates (v5.3 - October 2025)

### All Routers Now Enabled ✅

As of 2025-10-21, all API routers have been enabled and are fully functional:

**Newly Enabled Routers:**
1. **Display Policies** (`/api/v1/display-policies`) - 7 endpoints for policy-driven display control
2. **Devices** (`/api/v1/devices`) - 6 endpoints with tenant scoping for device management
3. **Reservations** (`/api/v1/reservations`) - 4 endpoints with tenant isolation
4. **Gateways** (`/api/v1/gateways`) - 3 endpoints for infrastructure monitoring

**Enhancements:**
- Full tenant scoping on all multi-tenant resources
- RBAC enforcement with role and scope validation
- Prometheus metrics fully operational (`/metrics`)
- Pydantic 2.10 compatibility

**Total Endpoints:** 60+ endpoints across 9 routers

For detailed implementation information, see:
- [`docs/OPENAPI_VALIDATION_REPORT.md`](./OPENAPI_VALIDATION_REPORT.md) - Validation analysis
- [`docs/OPENAPI_IMPLEMENTATION_SUMMARY.md`](./OPENAPI_IMPLEMENTATION_SUMMARY.md) - Implementation details

---

**Last Updated:** 2025-10-21
**API Version:** 5.3.0
**Maintained By:** Verdegris Engineering Team

For interactive documentation, visit: https://api.verdegris.eu/docs
