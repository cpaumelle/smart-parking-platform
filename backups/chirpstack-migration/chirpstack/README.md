# ChirpStack LoRaWAN Network Server - VM 110

**Version:** 1.0.0
**Last Updated:** 2025-10-01
**Status:** Production Ready
**VM ID:** 110 (chirpstack-sensemy)
**IP Address:** 10.44.1.110
**Public Domain:** https://chirpstack.sensemy.cloud
**ChirpStack Version:** 4.14.1

---

## Overview

This VM hosts a complete ChirpStack LoRaWAN Network Server stack, providing enterprise-grade LoRaWAN network management capabilities. ChirpStack is an open-source LoRaWAN Network Server that enables device management, gateway connectivity, and application integration for IoT deployments.

### Architecture Components

```
Internet (LoRa Gateways)
    ↓ UDP 1700 (Semtech Packet Forwarder)
Gateway Bridge → MQTT Broker → ChirpStack Server
                     ↓              ↓
              Applications    PostgreSQL (VM 112)
                             Redis (Local)
```

### Service Stack

| Service | Version | Port | Purpose |
|---------|---------|------|---------|
| ChirpStack | 4.14.1 | 8080 | LoRaWAN Network Server & Web UI |
| Gateway Bridge | 4.x | 1700/udp | Packet Forwarder to MQTT converter |
| Mosquitto MQTT | 2.x | 1883, 9001 | Internal message broker |
| Redis | 7-alpine | 6379 | Cache & session storage |
| PostgreSQL | 15-alpine | 5432 (VM 112) | Primary database |

---

## Installation and Configuration

### Directory Structure

```
/opt/chirpstack/
├── docker-compose.yml    # Container orchestration
├── chirpstack.toml       # ChirpStack configuration
├── mosquitto.conf        # MQTT broker configuration
└── .env                  # Environment variables
```

### Docker Compose Configuration

The deployment uses Docker Compose with the following services:

#### 1. PostgreSQL (External - VM 112)
- **Host:** 10.44.1.12:5432
- **Database:** chirpstack_db
- **User:** chirpstack
- **Password:** secret (stored in .env)

#### 2. Redis (Container)
- **Image:** redis:7-alpine
- **Purpose:** Session storage, device frame cache
- **Persistence:** Volume-backed
- **Health Check:** Redis PING command

#### 3. Mosquitto MQTT Broker (Container)
- **Image:** eclipse-mosquitto:2
- **Ports:** 1883 (MQTT), 9001 (WebSocket)
- **Configuration:** Allow anonymous (internal use only)
- **Persistence:** Message persistence enabled
- **Use Case:** Internal pub/sub for gateway-to-server communication

#### 4. ChirpStack Gateway Bridge (Container)
- **Image:** chirpstack/chirpstack-gateway-bridge:4
- **Port:** 1700/udp (Semtech packet forwarder protocol)
- **Function:** Converts UDP packets from gateways to MQTT messages
- **MQTT Topics:**
  - Event: `gateway/{{ .GatewayID }}/event/{{ .EventType }}`
  - State: `gateway/{{ .GatewayID }}/state/{{ .StateType }}`
  - Command: `gateway/{{ .GatewayID }}/command/#`

#### 5. ChirpStack Server (Container)
- **Image:** chirpstack/chirpstack:4
- **Port:** 8080 (HTTP API & Web UI)
- **Region:** US915 (US 902-928 MHz)
- **Net ID:** 000000 (private network)
- **Configuration:** TOML-based config file

---

## Network Configuration

### Internal Network (Docker Bridge)
- **Network Name:** chirpstack-net
- **Type:** Bridge network
- **Purpose:** Inter-container communication

### External Access

#### 1. Gateway Communication
- **Protocol:** Semtech UDP Packet Forwarder
- **Port:** 1700/udp
- **Access:** Direct access to VM 110
- **Firewall:** Must allow UDP 1700 from gateway IPs

#### 2. Web Interface & API
- **URL:** https://chirpstack.sensemy.cloud
- **Backend:** 10.44.1.110:8080
- **Proxy:** Traefik on VM 111
- **SSL:** Let's Encrypt (automatic)
- **Default Credentials:** admin / admin (CHANGE IMMEDIATELY)

#### 3. MQTT (Internal Only)
- **Port:** 1883 (MQTT), 9001 (WebSocket)
- **Access:** Container network only
- **Authentication:** Anonymous (secure as internal-only)

---

## ChirpStack Configuration Details

### Region Settings
```toml
[network]
net_id = "000000"
enabled_regions = ["us915_0"]
```

**US915 Sub-band 0:** Channels 0-7 (902.3 - 903.7 MHz)

### Database Connection
```toml
[postgresql]
dsn = "postgres://chirpstack:secret@10.44.1.12:5432/chirpstack_db?sslmode=disable"
```

### Redis Configuration
```toml
[redis]
servers = ["redis://redis:6379"]
```

### API Configuration
```toml
[api]
bind = "0.0.0.0:8080"
```

### MQTT Integration
```toml
[integration.mqtt]
server = "tcp://mosquitto:1883"
event_topic_template = "application/{{ .ApplicationID }}/device/{{ .DevEUI }}/event/{{ .EventType }}"
command_topic_template = "application/{{ .ApplicationID }}/device/{{ .DevEUI }}/command/{{ .CommandType }}"
```

---

## Management and Operations

### Starting the Stack

```bash
cd /opt/chirpstack
docker compose up -d
```

### Stopping the Stack

```bash
cd /opt/chirpstack
docker compose down
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f chirpstack
docker compose logs -f chirpstack-gateway-bridge
docker compose logs -f mosquitto
```

### Checking Service Health

```bash
# Container status
docker compose ps

# Health checks
docker inspect chirpstack | jq '.[0].State.Health'
docker inspect chirpstack-redis | jq '.[0].State.Health'
```

### Updating ChirpStack

```bash
cd /opt/chirpstack
docker compose pull
docker compose up -d
```

---

## Database Management

### Database Location
- **Host:** VM 112 (10.44.1.12)
- **Port:** 5432
- **Database:** chirpstack_db
- **Schema:** Managed by ChirpStack migrations

### Connecting to Database

```bash
# From VM 110
docker compose exec postgres-client psql -h 10.44.1.12 -U chirpstack -d chirpstack_db

# Or from VM 112
psql -U chirpstack -d chirpstack_db
```

### Database Backup

```bash
# From VM 112
pg_dump -U chirpstack chirpstack_db > /backup/chirpstack_$(date +%Y%m%d_%H%M%S).sql

# Or from VM 110 via Docker
docker compose exec postgres-client pg_dump -h 10.44.1.12 -U chirpstack chirpstack_db > /backup/chirpstack_$(date +%Y%m%d_%H%M%S).sql
```

### Database Restore

```bash
psql -U chirpstack -d chirpstack_db < /backup/chirpstack_20251001.sql
```

---

## Accessing ChirpStack

### Web Interface
1. Navigate to: https://chirpstack.sensemy.cloud
2. Login with default credentials:
   - **Username:** admin
   - **Password:** admin
3. **IMPORTANT:** Change password immediately after first login

### API Access

```bash
# Get API token (after login via web interface)
# API documentation: https://chirpstack.sensemy.cloud/api

# Example: List gateways
curl -H "Grpc-Metadata-Authorization: Bearer YOUR_TOKEN" \
  https://chirpstack.sensemy.cloud/api/gateways

# Example: List applications
curl -H "Grpc-Metadata-Authorization: Bearer YOUR_TOKEN" \
  https://chirpstack.sensemy.cloud/api/applications
```

---

## LoRaWAN Configuration

### Network Settings
- **Network Type:** Private LoRaWAN network
- **Net ID:** 000000 (Type 0 - Experimental)
- **Region:** US915 (902-928 MHz, US frequency plan)
- **Sub-band:** 0 (Channels 0-7: 902.3-903.7 MHz)

### Device Classes Supported
- **Class A:** Battery-powered sensors (bi-directional, downlink after uplink)
- **Class B:** Scheduled downlinks with beacons
- **Class C:** Continuous listening (mains-powered devices)

### Activation Methods
- **OTAA (Over-The-Air Activation):** Recommended for production
- **ABP (Activation By Personalization):** Supported for testing

---

## Troubleshooting

### Gateway Not Connecting

**Check gateway can reach VM:**
```bash
# From gateway, verify UDP 1700 is open
nc -u 10.44.1.110 1700
```

**Check gateway bridge logs:**
```bash
docker logs chirpstack-gateway-bridge -f
```

**Verify MQTT messages:**
```bash
docker exec -it chirpstack-mosquitto mosquitto_sub -v -t 'gateway/#'
```

### Devices Not Joining

**Check device is in correct region:**
- Ensure device firmware is set to US915
- Verify sub-band matches (sub-band 0)

**Check application and device profile:**
- Device profile region must match network region
- Application must be created and device assigned

**View ChirpStack logs:**
```bash
docker logs chirpstack -f | grep -i join
```

### Database Connection Issues

**Test database connectivity:**
```bash
docker compose exec postgres-client psql -h 10.44.1.12 -U chirpstack -d chirpstack_db -c "SELECT version();"
```

**Check PostgreSQL on VM 112:**
```bash
# On VM 112
systemctl status postgresql
netstat -tlnp | grep 5432
```

### MQTT Issues

**Check Mosquitto status:**
```bash
docker logs chirpstack-mosquitto -f
```

**Test MQTT connectivity:**
```bash
docker exec -it chirpstack-mosquitto mosquitto_pub -t 'test' -m 'hello'
docker exec -it chirpstack-mosquitto mosquitto_sub -t 'test'
```

### Web UI Not Accessible

**Check Traefik routing (on VM 111):**
```bash
curl -I -k https://localhost --header "Host: chirpstack.sensemy.cloud"
```

**Verify ChirpStack is running:**
```bash
curl -I http://10.44.1.110:8080
```

**Check DNS resolution:**
```bash
nslookup chirpstack.sensemy.cloud
```

---

## Security Considerations

### Default Credentials
- **CRITICAL:** Change default admin password immediately
- Create individual user accounts for team members
- Use API tokens for programmatic access

### Network Security
- MQTT broker is internal-only (not exposed externally)
- Database connection is unencrypted (internal network only)
- Consider enabling PostgreSQL SSL in production
- Gateway Bridge UDP port 1700 is publicly accessible (required)

### Firewall Rules Required
```bash
# Allow gateway traffic (UDP 1700)
iptables -A INPUT -p udp --dport 1700 -j ACCEPT

# Allow HTTPS (handled by VM 111 Traefik)
# Allow MQTT (internal only - no external access needed)
```

### SSL/TLS
- Web interface uses Let's Encrypt SSL (automatic via Traefik)
- Certificate renewal is automatic
- API access is HTTPS-only

---

## Backup and Disaster Recovery

### Critical Data
1. **PostgreSQL Database** (VM 112: chirpstack_db)
2. **Configuration files:** /opt/chirpstack/
3. **Redis data** (cached data, can be regenerated)

### Backup Schedule
```bash
# Daily database backup (recommended cron job)
0 2 * * * docker exec postgres pg_dump -U chirpstack chirpstack_db | gzip > /backup/chirpstack_$(date +\%Y\%m\%d).sql.gz

# Weekly config backup
0 3 * * 0 tar -czf /backup/chirpstack_config_$(date +\%Y\%m\%d).tar.gz /opt/chirpstack/
```

### Recovery Procedure
1. Restore database from backup
2. Deploy docker-compose stack with same configuration
3. Gateways and devices will reconnect automatically

---

## Performance and Scaling

### Current Capacity
- **Gateways:** Supports 100+ gateways
- **Devices:** Supports 10,000+ devices per installation
- **Message Rate:** 1000+ messages/second

### Monitoring Metrics
- Container health status (docker ps)
- ChirpStack logs (join rates, message processing)
- PostgreSQL query performance
- Redis memory usage

### Scaling Considerations
- Redis can be clustered for high availability
- PostgreSQL can be replicated for read scaling
- Multiple ChirpStack instances can share same database (with load balancer)

---

## Integration Options

### HTTP Integration
Configure in ChirpStack web interface:
- Application → Integrations → HTTP
- Send device data to external APIs
- Supports uplink, join, ack, error events

### MQTT Integration
Already configured for internal use:
- Subscribe to application topics
- Receive real-time device events
- Publish downlink commands

### AWS IoT Core / Azure IoT Hub
Supported via MQTT bridge or HTTP integration

---

## Useful Commands Reference

```bash
# Restart all services
docker compose restart

# Update to latest versions
docker compose pull && docker compose up -d

# View real-time logs
docker compose logs -f --tail=100

# Check disk usage
docker system df

# Cleanup old images
docker image prune -a

# Export database
docker compose exec postgres-client pg_dump -h 10.44.1.12 -U chirpstack chirpstack_db > backup.sql

# Check ChirpStack version
docker exec chirpstack /usr/bin/chirpstack --version

# Reset admin password (via database)
docker compose exec postgres-client psql -h 10.44.1.12 -U chirpstack -d chirpstack_db \
  -c "UPDATE \"user\" SET password_hash='...' WHERE email='admin';"
```

---

## References and Documentation

- **ChirpStack Official Docs:** https://www.chirpstack.io/docs/
- **ChirpStack v4 Guide:** https://www.chirpstack.io/docs/chirpstack/
- **Gateway Bridge Docs:** https://www.chirpstack.io/docs/chirpstack-gateway-bridge/
- **LoRaWAN Specification:** https://lora-alliance.org/resource_hub/lorawan-specification-v1-1/
- **US915 Band Plan:** https://www.thethingsnetwork.org/docs/lorawan/frequencies-by-country/

---

## Support and Maintenance

### Log Locations
- ChirpStack: `docker logs chirpstack`
- Gateway Bridge: `docker logs chirpstack-gateway-bridge`
- Mosquitto: `docker logs chirpstack-mosquitto`
- Database: VM 112 PostgreSQL logs

### Health Checks
All services have built-in Docker health checks that can be monitored:
```bash
docker compose ps
```

### Upgrade Path
1. Review ChirpStack release notes
2. Backup database and configuration
3. Pull new images: `docker compose pull`
4. Stop services: `docker compose down`
5. Start with new images: `docker compose up -d`
6. Verify migrations completed successfully
7. Test gateway connectivity

---

**Last Updated:** 2025-10-01
**Maintained By:** Infrastructure Team
**Contact:** See main infrastructure documentation
