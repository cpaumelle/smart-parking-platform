# ChirpStack Gateway WebSocket Connection Issue

## Problem Summary

The Kerlink gateway (EUI: 7076FF006404010B) is sending router-info requests to ChirpStack but not establishing a persistent WebSocket connection. ChirpStack shows the gateway as "Never Seen" because it expects statistics messages over an established WebSocket, not just periodic HTTP POST router-info requests.

## Current Infrastructure Setup

### Network Topology
- **Gateway**: Kerlink gateway at `10.35.1.117` (LAN network)
- **ChirpStack**: VM 110 at `10.44.1.110` (internal network)
  - Gateway Bridge listening on port `3001` (WebSocket endpoint)
- **Traefik**: VM 111 at `10.44.1.11` (reverse proxy)
- **Public Domain**: `chirpstack-gw.sensemy.cloud` resolves to `147.28.103.108` (public IP)

### What We've Built

1. **Domain Manager Configuration**
   - Created domain `chirpstack-gw.sensemy.cloud`
   - Service type: `websocket` (new type we added)
   - Backend: `10.44.1.110:3001`
   - DNS: Already configured via DDNS manager

2. **Traefik Configuration**
   - **Standard entrypoint** (`websecure` on port 443): Uses HTTP/2, breaks WebSockets
   - **WebSocket entrypoint** (`websecure-ws` on port 3002): HTTP/1.1 only, supports WebSockets
   - Configuration file: `/opt/charliehub/traefik-prod/config/static-routes.yml`
   - Router for `chirpstack-gw.sensemy.cloud`:
     - Uses `websecure-ws` entrypoint (port 3002)
     - No middleware (headers stripped)
     - `passHostHeader: true` enabled
     - TLS with Let's Encrypt

3. **Gateway Configuration Script**
   - Location: `/opt/iot-platform/00-chirsptack-tooling/onboard_kerlink_gateway.sh`
   - Environment file: `.env` with `LNS_WEBSOCKET_URL=wss://chirpstack-gw.sensemy.cloud:3002`
   - Successfully extracts gateway EUI from `/tmp/board_info.json`
   - Registers gateway in ChirpStack via gRPC API

## Root Cause Analysis

### Why HTTP/2 Breaks WebSockets
WebSocket protocol requires HTTP/1.1 for the upgrade handshake. Traefik's default HTTPS endpoint (port 443) uses HTTP/2, which doesn't support WebSocket upgrades. This is why we created the separate `websecure-ws` entrypoint on port 3002.

### Current Connection Flow Issues

**Gateway → ChirpStack (Current State)**
```
Gateway (10.35.1.117)
  ↓ DNS lookup: chirpstack-gw.sensemy.cloud
  ↓ Resolves to: 147.28.103.108 (public IP)
  ↓ Tries to connect: wss://chirpstack-gw.sensemy.cloud:3002
  ✗ FAILS - Can't reach public IP from internal network
```

**What Actually Works**
```
Gateway (10.35.1.117)
  ↓ Direct connection: ws://10.44.1.110:3001
  ↓ HTTP POST router-info requests work
  ✓ ChirpStack Gateway Bridge receives router-info
  ✗ But WebSocket upgrade never succeeds
```

## Solution: UniFi Router Configuration

To make `wss://chirpstack-gw.sensemy.cloud:3002` work for both internal and external gateways:

### 1. Local DNS Override (Split DNS)

**Purpose**: Internal devices use local Traefik IP instead of routing through public IP

**UniFi Configuration**:
- Go to: **Settings → Networks → [Your LAN] → DHCP Name Server**
- Or: **Settings → Internet → DNS**
- Add Custom DNS Record:
  ```
  Hostname: chirpstack-gw.sensemy.cloud
  IP Address: 10.44.1.11
  ```

**Result**:
- Internal gateway resolves `chirpstack-gw.sensemy.cloud` → `10.44.1.11` (Traefik)
- External gateways resolve to public IP `147.28.103.108`

### 2. Port Forward Rule

**Purpose**: External gateways can reach ChirpStack WebSocket endpoint

**UniFi Configuration**:
- Go to: **Settings → Routing & Firewall → Port Forwarding**
- Add New Port Forward Rule:
  ```
  Name: ChirpStack Gateway WebSocket
  Protocol: TCP
  Port: 3002
  Forward IP: 10.44.1.11 (VM 111 - Traefik)
  Forward Port: 3002
  ```

**Verification**:
```bash
# From external network:
curl -I https://chirpstack-gw.sensemy.cloud:3002
# Should get response from Traefik
```

### 3. Hairpin NAT / NAT Loopback (Optional but Recommended)

**Purpose**: Allows internal devices to use public domain/IP even without local DNS override

**UniFi Configuration**:
- Go to: **Settings → Advanced Features**
- Look for: **Enable Hairpin NAT** or **NAT Loopback**
- Enable if available

**Note**: Not all UniFi devices support this. If unavailable, local DNS override (#1) is sufficient.

## Expected Connection Flow After Configuration

### Internal Gateways (Pre-deployment Testing)
```
Gateway (10.35.1.117)
  ↓ Configures: wss://chirpstack-gw.sensemy.cloud:3002
  ↓ DNS lookup via local DNS override
  ↓ Resolves to: 10.44.1.11 (Traefik internal IP)
  ↓ Connects to: Traefik VM 111 port 3002
  ↓ Traefik routes to: ChirpStack Gateway Bridge (10.44.1.110:3001)
  ✓ WebSocket established
  ✓ Statistics messages sent
  ✓ ChirpStack UI shows "Connected"
```

### External Gateways (Field Deployment)
```
Gateway (remote, via cellular)
  ↓ Configures: wss://chirpstack-gw.sensemy.cloud:3002
  ↓ DNS lookup via public DNS
  ↓ Resolves to: 147.28.103.108 (public IP)
  ↓ Connects to: Public IP port 3002
  ↓ Router forwards to: Traefik VM 111 port 3002
  ↓ Traefik routes to: ChirpStack Gateway Bridge (10.44.1.110:3001)
  ✓ WebSocket established
  ✓ Statistics messages sent
  ✓ ChirpStack UI shows "Connected"
```

## Verification Steps After UniFi Configuration

### 1. Test DNS Resolution (from gateway)
```bash
# SSH to gateway
ssh root@10.35.1.117

# Check DNS resolution
nslookup chirpstack-gw.sensemy.cloud
# Should return: 10.44.1.11 (internal IP)
```

### 2. Test Port Connectivity
```bash
# From gateway, test if port 3002 is reachable
ping -c 2 10.44.1.11
# Port test (if telnet available)
telnet 10.44.1.11 3002
```

### 3. Configure Gateway with Final URL
```bash
/user/basic_station/bin/klk_bs_config --enable --lns-uri 'wss://chirpstack-gw.sensemy.cloud:3002'
```

### 4. Monitor Connection
```bash
# On VM 110, watch gateway bridge logs
docker logs -f chirpstack-gateway-bridge

# Look for:
# - "router-info request received" (already working)
# - WebSocket connection established messages
# - Statistics messages from gateway
```

### 5. Check ChirpStack UI
- Navigate to: https://chirpstack.sensemy.cloud
- Go to: Gateways → klk-fevo-04010B
- Status should change from "Never Seen" to "Last seen: [timestamp]"
- Connection indicator should show green/connected

## Technical Details

### Port Requirements
| Port | Protocol | Purpose | Exposed |
|------|----------|---------|---------|
| 443 | HTTPS/HTTP2 | Standard web traffic (ChirpStack UI, API) | Yes |
| 3002 | HTTPS/HTTP1.1 | WebSocket connections (gateways) | Yes (new) |
| 3001 | HTTP/WS | Gateway Bridge internal endpoint | No (internal only) |
| 8080 | HTTP | ChirpStack gRPC API | No (internal only) |

### Service Type Comparison in Domain Manager
| Service Type | Entrypoint | HTTP Version | Middleware | Use Case |
|--------------|------------|--------------|------------|----------|
| `spa` | websecure (443) | HTTP/2 | Security headers | Web applications |
| `api` | websecure (443) | HTTP/2 | CORS headers | REST APIs |
| `websocket` | websecure-ws (3002) | HTTP/1.1 only | None | WebSocket services |
| `proxy` | websecure (443) | HTTP/2 | None | Pass-through proxies |

### Why This Approach Works
1. **Single URL for all gateways**: `wss://chirpstack-gw.sensemy.cloud:3002`
2. **No reconfiguration needed**: Pre-configure on LAN, deploy to field
3. **Proper WebSocket support**: Dedicated HTTP/1.1 entrypoint
4. **Scalable**: Can add more WebSocket services using same infrastructure

## Files Modified

### Traefik Generator Script
- **Location**: `/opt/charliehub/scripts/traefik_gen_v2.py`
- **Changes**:
  - Added WebSocket service type detection
  - Routes WebSocket services to `websecure-ws` entrypoint
  - Skips headers middleware for WebSocket services
  - Sets `passHostHeader: true` for WebSocket services

### Traefik Docker Compose
- **Location**: `/opt/charliehub/traefik-prod/docker-compose.yml`
- **Changes**: Added websecure-ws entrypoint on port 3002

### Gateway Onboarding Script
- **Location**: `/opt/iot-platform/00-chirsptack-tooling/onboard_kerlink_gateway.sh`
- **Changes**:
  - Fixed EUI extraction from `/tmp/board_info.json`
  - Updated to use correct Kerlink commands (opkg, klk_bs_config paths)
  - Fixed monit service name (`station` not `basicstation`)
  - Accepts both "y" and "yes" for confirmation

### Environment Configuration
- **Location**: `/opt/iot-platform/00-chirsptack-tooling/.env`
- **Setting**: `LNS_WEBSOCKET_URL=wss://chirpstack-gw.sensemy.cloud:3002`

## Next Steps

1. **Configure UniFi** (steps above)
2. **Add port forward** for 3002 → 10.44.1.11
3. **Add local DNS override** for chirpstack-gw.sensemy.cloud → 10.44.1.11
4. **Test gateway connection** with production URL
5. **Verify in ChirpStack UI** that gateway shows as connected
6. **Test with external gateway** once available

## Troubleshooting

If gateway still doesn't connect after UniFi configuration:

### Check DNS Resolution
```bash
# From gateway
nslookup chirpstack-gw.sensemy.cloud
# Should return 10.44.1.11 for internal gateway
```

### Check Traefik Logs
```bash
docker logs -f traefik_prod | grep chirpstack-gw
```

### Check Gateway Logs
```bash
# SSH to gateway
ssh root@10.35.1.117
# View Basic Station logs (uses syslog)
logread | grep station
```

### Check ChirpStack Gateway Bridge
```bash
docker logs -f chirpstack-gateway-bridge
# Look for WebSocket upgrade errors or connection attempts
```

### Verify Traefik Configuration
```bash
cat /opt/charliehub/traefik-prod/config/static-routes.yml | grep -A 10 chirpstack-gw
```
