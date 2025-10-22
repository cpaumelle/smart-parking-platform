# API Documentation

Complete REST API documentation for the Smart Parking Platform v5.

## Overview

The Smart Parking Platform provides a RESTful API built with FastAPI. All endpoints require authentication via API keys and enforce multi-tenant isolation.

## API Documentation

### Core References
- **[API Reference](reference.md)** - Complete endpoint documentation with examples
- **[OpenAPI Specification](openapi.md)** - OpenAPI 3.1 machine-readable spec
- **[OpenAPI Implementation](openapi-implementation.md)** - Implementation details
- **[OpenAPI Validation](openapi-validation.md)** - Validation and compliance report

### Integration Guides
- **[Webhook Integration](webhook-integration.md)** - External webhook system design
- **[Webhook Implementation](webhook-implementation.md)** - Implementation details
- **[Sites API](sites-api.md)** - Sites management implementation

## Quick Start

### Authentication

All API requests require an API key in the header:

```bash
curl -H "X-API-Key: your-api-key-here" \
  https://api.example.com/v1/spaces
```

The API key identifies the tenant and enforces row-level security.

### Base URL

```
Production: https://api.verdegris.com/v1
Staging: https://staging-api.verdegris.com/v1
Local: http://localhost:8000/v1
```

### Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

Errors:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": { ... }
  },
  "metadata": {
    "request_id": "uuid",
    "timestamp": "ISO8601"
  }
}
```

## Core Endpoints

### Spaces
- `GET /v1/spaces` - List all spaces for tenant
- `POST /v1/spaces` - Create a new space
- `GET /v1/spaces/{space_id}` - Get space details
- `PUT /v1/spaces/{space_id}` - Update space
- `DELETE /v1/spaces/{space_id}` - Soft-delete space

### Reservations
- `GET /v1/reservations` - List reservations (with date filtering)
- `POST /v1/reservations` - Create a reservation
- `GET /v1/reservations/{reservation_id}` - Get reservation details
- `PUT /v1/reservations/{reservation_id}` - Update reservation
- `DELETE /v1/reservations/{reservation_id}` - Cancel reservation

### Devices
- `GET /v1/devices` - List all devices
- `GET /v1/devices/orphans` - List unassigned devices
- `POST /v1/devices/{device_eui}/assign` - Assign device to space
- `POST /v1/devices/{device_eui}/unassign` - Unassign device

### State Changes
- `GET /v1/spaces/{space_id}/state` - Get current state
- `GET /v1/spaces/{space_id}/history` - Get state change history
- `POST /v1/spaces/{space_id}/override` - Manual state override

### Webhooks (External Integration)
- `POST /v1/webhooks/chirpstack` - ChirpStack uplink webhook
- `POST /v1/webhooks/external` - External system webhook

## Rate Limits

Default rate limits per tenant:
- **Read operations**: 100 requests/minute, 1000 requests/hour
- **Write operations**: 10 requests/minute, 100 requests/hour

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

## Pagination

List endpoints support pagination:

```
GET /v1/spaces?page=1&page_size=50
```

Response includes pagination metadata:

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 250,
    "total_pages": 5
  }
}
```

## Filtering & Sorting

Most list endpoints support filtering:

```
GET /v1/spaces?site_id=xxx&status=FREE
GET /v1/reservations?start_date=2025-10-22&end_date=2025-10-29
GET /v1/spaces?sort=code&order=asc
```

## Webhooks

The platform supports two webhook types:

### 1. ChirpStack Webhooks (Internal)
Receives LoRaWAN uplinks from ChirpStack:
```
POST /v1/webhooks/chirpstack
```

### 2. External Webhooks (Outbound)
Sends events to external systems:
- Reservation created/updated/cancelled
- Space state changed
- Device assignment changed

Configure webhooks in tenant settings.

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request payload |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (e.g., double booking) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

## OpenAPI Spec

Interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Next Steps

- Review [API Reference](reference.md) for detailed endpoint documentation
- Download [OpenAPI Specification](openapi.md) for code generation
- Implement [Webhook Integration](webhook-integration.md) for real-time updates
