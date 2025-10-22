# Smart Parking Platform Documentation

Welcome to the Smart Parking Platform v5.8 documentation. This guide provides comprehensive documentation for architecture, APIs, operations, and security.

## 📚 Documentation Structure

### [Architecture](/docs/architecture/)
Core system design, data models, and technical architecture:
- [Database Schema](architecture/database-schema.md) - Complete v5 database structure
- [Multi-Tenancy](architecture/multi-tenancy.md) - Multi-tenant RBAC architecture
- [State Machine](architecture/state-machine.md) - Occupancy display state machine
- [Reservation Engine](architecture/reservation-engine.md) - Reservation system design
- [Downlink Pipeline](architecture/downlink-pipeline.md) - Class C downlink architecture
- [Device Types](architecture/device-types.md) - Device architecture patterns
- [Kuando Downlink Reference](architecture/kuando-downlink-reference.md) - Kuando device integration

### [API Documentation](/docs/api/)
REST API reference and integration guides:
- [API Reference](api/reference.md) - Complete API endpoint documentation
- [OpenAPI Specification](api/openapi.md) - OpenAPI 3.1 spec
- [Webhook Integration](api/webhook-integration.md) - External webhook system
- [Sites API](api/sites-api.md) - Sites management endpoints

### [Operations](/docs/operations/)
Deployment, monitoring, and operational procedures:
- [Deployment Guide](operations/deployment.md) - Production deployment procedures
- [Monitoring](operations/monitoring.md) - Observability and metrics
- [Runbooks](operations/runbooks.md) - Operational runbooks for common issues
- [Testing Strategy](operations/testing-strategy.md) - Testing approach and guidelines
- [Ops UI](operations/ops-ui.md) - Operations dashboard guide

### [Security](/docs/security/)
Authentication, authorization, and security policies:
- [Multi-Tenancy Security](security/tenancy.md) - Row-level security and tenant isolation
- [RBAC](security/rbac.md) - Role-based access control

### [Changelog](/docs/changelog/)
Version history, implementation plans, and historical documentation:
- [Implementation Plan v5.8](changelog/IMPLEMENTATION_PLAN_v5.8.md) - Current implementation roadmap
- [Recommendations 2025-10-22](changelog/20251022_recommendations.md) - Latest recommendations
- Build notes and historical implementation guides

## 🚀 Quick Start

1. **For Developers**: Start with [Architecture](architecture/) to understand system design
2. **For API Users**: See [API Reference](api/reference.md) for endpoint documentation
3. **For Operations**: Review [Deployment Guide](operations/deployment.md) and [Runbooks](operations/runbooks.md)
4. **For Security**: Check [Multi-Tenancy Security](security/tenancy.md) and [RBAC](security/rbac.md)

## 📋 Current Version

**Version**: v5.8.0
**Last Updated**: 2025-10-22
**Status**: Production Ready

## 🔗 Related Resources

- Main [README.md](../README.md) - Project overview and setup instructions
- [Docker Compose Configuration](../docker-compose.yml) - Service orchestration
- [API Source Code](../src/) - Python FastAPI implementation
