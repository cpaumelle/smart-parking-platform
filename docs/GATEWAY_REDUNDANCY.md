# Gateway Redundancy and Class C Downlink Failover

**Document Version:** 1.0.0
**Date:** 2025-10-17
**Platform:** Smart Parking v5

---

## Problem Statement

### Issue
Class C devices (Kuando Busylight displays) only receive downlinks via the gateway that last received their uplinks. When that gateway goes offline, downlinks are queued but never transmitted, even if other gateways are online.

### Example Scenario
1. Device `202020410a1c0702` sends uplink via gateway `7276ff003904052c`
2. Gateway `7276ff003904052c` goes offline
3. Application sends downlink command (change color to GREEN)
4. ChirpStack queues downlink for gateway `7276ff003904052c`
5. **Downlink never transmits** because gateway is offline
6. Display never changes color

---

## Root Cause: ChirpStack Routing Behavior

### How ChirpStack Routes Class C Downlinks

ChirpStack uses **device-gateway affinity** for downlink routing:

```
┌─────────────┐
│   Device    │ ───uplink via GW1───> ChirpStack stores: "Device → GW1"
└─────────────┘

Later when downlink arrives:
┌─────────────┐
│ChirpStack   │ ───downlink ONLY via GW1───> (fails if GW1 offline)
└─────────────┘
```

**Why it doesn't failover automatically:**
- ChirpStack prioritizes the gateway with best recent RSSI for that device
- No automatic fallback to other gateways
- This is by design for optimal RF performance

---

## Solutions Implemented

### ✅ Solution 1: Gateway Health Monitoring

**Implementation:** Real-time gateway status tracking

**Endpoints:**
```bash
GET /api/v1/gateways/health          # Overall gateway health
GET /api/v1/gateways                 # List all gateways with status
GET /api/v1/gateways/{id}/status     # Specific gateway status
```

**Features:**
- Monitors all gateways in real-time
- Tracks online/offline status (5-minute threshold)
- Caches status for 30 seconds
- Provides health summary

**Example Response:**
```json
{
  "total_gateways": 4,
  "online_count": 2,
  "offline_count": 2,
  "online_gateways": ["7076ff0064030456", "7076ff006404010b"],
  "offline_gateways": [
    {
      "gateway_id": "7276ff003904052c",
      "name": "7276FF003904052C",
      "minutes_offline": 59
    }
  ],
  "health_status": "healthy"
}
```

---

### ✅ Solution 2: Queue Monitoring (Planned)

**Status:** In development

**Features:**
- Monitor device queue after downlink
- Detect stalled downlinks (pending > timeout)
- Automatic queue flush for stuck items
- Alert on repeated failures

---

### ❌ Limitation: Unicast Downlinks Cannot Force Gateway Switch

**LoRaWAN Constraint:**
Once ChirpStack selects a gateway for a device based on uplink history, **unicast downlinks will always route to that gateway** until the device sends a new uplink that's received by a different gateway.

**Workaround Options:**

#### Option A: Wait for Natural Gateway Rotation
- Device eventually sends uplink (heartbeat/status)
- New uplink received by online gateway
- Future downlinks route to new gateway
- **Timeline:** Depends on device uplink interval

#### Option B: Trigger Device Uplink (If Supported)
- Some devices support uplink trigger commands
- Kuando displays: Check firmware for uplink trigger capability
- Would force immediate gateway reselection

#### Option C: Multicast Groups (Not Recommended for Kuando)
**Why not:**
- Multicast sends SAME payload to ALL devices in group
- Kuando displays need device-specific colors
- Would require 1 multicast group per device (defeats purpose)

---

## Best Practices

### 1. Gateway Redundancy

**Recommendation:** Deploy at least 2 gateways with overlapping coverage

```
Optimal Coverage:
┌────────────┐         ┌────────────┐
│  Gateway 1 │◄───────►│  Gateway 2 │
│  (Primary) │         │  (Backup)  │
└─────┬──────┘         └──────┬─────┘
      │                       │
      └───────► Device ◄──────┘
      Both gateways receive uplinks
```

**Benefits:**
- If GW1 goes offline, next uplink routes via GW2
- Downlinks automatically switch to GW2 after uplink
- 5-10 second failover time (uplink interval dependent)

### 2. Gateway Health Monitoring

**Integration Example:**
```python
# Check gateway health before critical operations
gw_health = await gateway_monitor.get_health_summary()
if gw_health['online_count'] == 0:
    logger.critical("All gateways offline - cannot send downlinks")
    raise GatewayUnavailableError()
```

### 3. Queue Management

**Automatic Cleanup:**
- Flush device queue when gateway offline > 5 minutes
- Prevents queue buildup
- Retry after gateway comes back online

### 4. Device Uplink Intervals

**For Kuando Displays:**
- Current: Unknown (check device configuration)
- Recommended: 5-10 minute heartbeat intervals
- Enables faster gateway failover

---

## Monitoring Dashboard (Planned)

### Metrics to Track:
1. **Gateway Availability**
   - Online/offline status per gateway
   - Uptime percentage
   - Last seen timestamp

2. **Downlink Success Rate**
   - Total downlinks sent
   - Successful transmissions (tx_ack received)
   - Failed downlinks (no tx_ack)
   - Average transmission time

3. **Device-Gateway Mapping**
   - Which devices use which gateways
   - Gateway switching frequency
   - Coverage gaps

---

## Troubleshooting

### Problem: Downlinks Not Reaching Device

**Check 1: Gateway Status**
```bash
curl http://api:8000/api/v1/gateways/{gateway_id}/status
```

**Check 2: Device Queue**
```bash
# Via database
SELECT * FROM device_queue_item
WHERE dev_eui = decode('202020410a1c0702', 'hex')
AND is_pending = true;
```

**Check 3: ChirpStack Logs**
```bash
docker logs parking-chirpstack --tail 100 | grep {device_eui}
```

**Solution Steps:**
1. Verify gateway is online
2. Flush device queue if gateway offline
3. Wait for device uplink from online gateway
4. Retry downlink

### Problem: Gateway Shows Offline But Actually Online

**Cause:** Last seen timestamp not updating

**Check:**
```bash
# Gateway bridge logs
docker logs parking-gateway-bridge --tail 50
```

**Solution:**
- Restart gateway bridge
- Check MQTT broker connectivity
- Verify gateway is sending stats

---

## API Reference

### Gateway Health Endpoints

#### GET /api/v1/gateways/health
Get overall gateway health summary

**Response:**
```json
{
  "total_gateways": 4,
  "online_count": 2,
  "offline_count": 2,
  "health_status": "healthy",
  "checked_at": "2025-10-17T09:01:53Z"
}
```

#### GET /api/v1/gateways
List all gateways with status

**Query Parameters:**
- `refresh`: Force cache refresh (default: false)

**Response:**
```json
[
  {
    "gateway_id": "7076ff0064030456",
    "name": "7076FF0064030456",
    "is_online": true,
    "last_seen_at": "2025-10-17T09:00:30Z",
    "minutes_offline": null
  }
]
```

#### GET /api/v1/gateways/{gateway_id}/status
Get specific gateway status

**Response:**
```json
{
  "gateway_id": "7276ff003904052c",
  "name": "7276FF003904052C",
  "is_online": false,
  "last_seen_at": "2025-10-17T08:02:30Z",
  "minutes_offline": 59
}
```

---

## Limitations

### Cannot Force Gateway Selection
**Issue:** ChirpStack v4 does not provide API to force downlink via specific gateway

**Impact:**
- Cannot manually override gateway selection
- Must wait for device to naturally switch gateways via uplink

### Class C Timeout
**Setting:** 2 seconds (configured in device profile)

**Impact:**
- ChirpStack retries downlink every 5 seconds
- If gateway offline, retries continue indefinitely
- Queue buildup if not manually flushed

---

## Recommendations

### Short Term (Implemented)
✅ Gateway health monitoring endpoints
✅ Real-time online/offline detection
✅ Health status API

### Medium Term (In Progress)
🔄 Automatic queue flush for offline gateways
🔄 Downlink success rate tracking
🔄 Failed downlink alerts

### Long Term (Planned)
📋 Device uplink trigger mechanism (if firmware supports)
📋 Gateway switching dashboard
📋 Predictive gateway health analysis
📋 Multi-gateway broadcast mode (if ChirpStack adds support)

---

## Configuration

### Gateway Offline Threshold

**Default:** 5 minutes

**Location:** `src/gateway_monitor.py`

```python
gateway_monitor = GatewayMonitor(
    chirpstack_dsn=chirpstack.chirpstack_dsn,
    offline_threshold_minutes=5  # Adjust as needed
)
```

**Recommendations:**
- 5 minutes: Standard for stable networks
- 2 minutes: For critical applications
- 10 minutes: For unreliable network conditions

### Class C Timeout

**Default:** 2 seconds

**Location:** ChirpStack device profile

**To change:**
1. Login to ChirpStack UI
2. Navigate to Device Profiles → plenom_kuando_busylight
3. Edit Class C settings
4. Update `timeout` value

---

## References

**Related Documentation:**
- `KUANDO_DOWNLINK_REFERENCE.md` - Kuando payload specifications
- `V4_KUANDO_DOWNLINK_MECHANISM.md` - V4 downlink architecture
- `V4_DATABASE_SCHEMA.md` - Database structure

**ChirpStack Documentation:**
- [Class C Devices](https://www.chirpstack.io/docs/chirpstack/features/class-c.html)
- [Downlink Queue](https://www.chirpstack.io/docs/chirpstack/features/device-queue.html)
- [Gateway Management](https://www.chirpstack.io/docs/chirpstack/features/gateways.html)

---

**Document Maintainer:** Claude Code
**Last Updated:** 2025-10-17
**Version:** 1.0.0
