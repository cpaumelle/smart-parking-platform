# Architecture Documentation

This directory contains the core architectural documentation for the Smart Parking Platform v5.

## Overview

The Smart Parking Platform is a multi-tenant IoT system that manages parking spaces using LoRaWAN sensors and display devices. The architecture is built on PostgreSQL with row-level security, Redis caching, and FastAPI.

## Core Architecture Documents

### Data & Schema
- **[Database Schema](database-schema.md)** - Complete PostgreSQL v5 schema with RLS, triggers, and constraints
- **[Multi-Tenancy](multi-tenancy.md)** - Multi-tenant architecture with RBAC and row-level security
- **[Orphan Devices](orphan-devices.md)** - Unassigned device management architecture

### State Management
- **[State Machine](state-machine.md)** - Occupancy display state machine logic
- **[State Machine Truth Table](state-machine-truth-table.md)** - Complete state transition matrix
- **[Reservation Engine](reservation-engine.md)** - Reservation booking and conflict resolution

### IoT & Downlink
- **[Downlink Pipeline](downlink-pipeline.md)** - ChirpStack Class C downlink architecture
- **[Kuando Downlink Reference](kuando-downlink-reference.md)** - Kuando Busylight protocol
- **[Kuando Downlink v4](kuando-downlink-v4.md)** - Legacy v4 downlink mechanism
- **[Device Types](device-types.md)** - Sensor and display device architecture

### Performance & Reliability
- **[Reliability Reference](reliability-reference.md)** - System reliability patterns and SLAs

## Key Architectural Decisions

### 1. Multi-Tenancy Strategy
- **Row-Level Security (RLS)**: PostgreSQL RLS policies enforce tenant isolation at the database level
- **Tenant Context**: Every request carries tenant_id from API key authentication
- **Shared Schema**: All tenants share the same schema with RLS-enforced filtering

### 2. State Machine Design
The occupancy state machine has 4 states:
- `FREE` - Space is available
- `OCCUPIED` - Space is occupied by a vehicle
- `RESERVED` - Space is reserved but not yet occupied
- `RESERVED_OCCUPIED` - Reserved space is now occupied

State transitions are governed by:
- Sensor readings (occupancy detection)
- Reservation timing (start_time, end_time)
- Manual overrides (admin actions)

### 3. Downlink Reliability
ChirpStack Class C downlinks use:
- **Immediate queuing**: Downlinks queued immediately on state change
- **Retry logic**: 3 attempts with exponential backoff
- **Confirmation tracking**: Downlink acknowledgment monitoring
- **Fallback mechanisms**: Manual reconciliation for failed downlinks

### 4. Device Assignment
- **Flexible Assignment**: Sensors and displays can be assigned independently
- **Site-Level Defaults**: Sites can have default gateways
- **Dynamic Reassignment**: Devices can be moved between spaces
- **Orphan Management**: Unassigned devices tracked in separate tables

## Data Flow

```
LoRaWAN Sensor → ChirpStack → Webhook → API → State Machine → Database
                                          ↓
                                    Downlink Queue
                                          ↓
                                Display Device (Kuando Busylight)
```

## Technology Stack

- **API**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 with RLS
- **Cache**: Redis 7
- **IoT Network**: ChirpStack v4 (LoRaWAN)
- **Message Broker**: Mosquitto (MQTT)
- **Reverse Proxy**: Traefik v3

## Performance Characteristics

- **API Response Time**: < 200ms (P95)
- **Database Query Time**: < 50ms (P95)
- **Downlink Latency**: < 5 seconds (Class C)
- **Cache Hit Rate**: > 70%

## Next Steps

- See [Database Schema](database-schema.md) for complete data model
- Review [State Machine](state-machine.md) for occupancy logic
- Check [Downlink Pipeline](downlink-pipeline.md) for IoT integration
- Read [Multi-Tenancy](multi-tenancy.md) for security architecture
