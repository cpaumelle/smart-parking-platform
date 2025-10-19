# Downlink Reliability - Quick Reference Guide

**Version:** 5.2.1
**Last Updated:** 2025-10-17

---

## Features at a Glance

| Feature | What It Does | When It Runs |
|---------|-------------|--------------|
| **Verification** | Checks if downlink succeeded (RGB + counter) | Every Kuando downlink |
| **Pre-flight Check** | Blocks downlinks if no gateways online | Before every downlink |
| **Queue Monitor** | Detects stuck downlinks after 15s | Per downlink (background) |
| **Auto-Cleanup** | Flushes stuck queues automatically | Every 5 minutes |
| **Auto-Uplink** | Triggers device response for verification | Every Kuando downlink |

---

## How It Works

### 1. Send Downlink

```bash
POST /api/v1/downlink/2020203907290902
{
  "payload": "00ff0000ff",  # 5-byte color command
  "fport": 15
}
```

**What Happens:**
1. ✅ Gateway health checked (blocks if offline)
2. ✅ 6th byte (`01`) automatically added
3. ✅ Expected RGB stored in Redis
4. ✅ Downlink queued to ChirpStack
5. ✅ Background monitor started (15s timeout)

**Response:**
```json
{
  "success": true,
  "message": "Downlink queued for 2020203907290902",
  "data": {
    "id": "queue-id-uuid",
    "gateway_health": {
      "status": "healthy",
      "online_gateways": 2,
      "total_gateways": 2
    }
  }
}
```

### 2. Device Responds

**Device sends auto-uplink** (triggered by 6th byte):
- Contains: RGB color + downlink counter
- Parsed automatically by API
- Stored in Redis for 1 hour

### 3. Verification

**System compares:**
- Expected RGB vs Actual RGB → Must match
- Previous counter vs Current counter → Must increment

**Result logged:**
```
✅ [req_xxx] [OK] Kuando downlink verified successfully
   RGB match=True (255,0,0 vs 255,0,0), counter incremented=True (10 > 9)
```

or

```
⚠️  [req_xxx] [FAIL] Kuando downlink verification failed
    RGB match=False (255,0,0 vs 0,255,0), counter incremented=False (10 > 10)
```

---

## Monitoring Commands

### Check Gateway Health
```bash
curl http://localhost:8000/api/v1/gateways/health
```

### Check Device Queue
```bash
curl http://localhost:8000/api/v1/devices/2020203907290902/queue
```

### Flush Device Queue (Manual)
```bash
curl -X DELETE http://localhost:8000/api/v1/devices/2020203907290902/queue
```

### Watch Logs

**Verification Results:**
```bash
docker logs parking-api --follow | grep "Downlink VERIFIED"
```

**Stuck Downlinks:**
```bash
docker logs parking-api --follow | grep "STUCK"
```

**Background Cleanup:**
```bash
docker logs parking-api --follow | grep "Flushing"
```

**All Reliability Events:**
```bash
docker logs parking-api --follow | grep -E "(Gateway health|Queue monitoring|VERIFIED|STUCK|Flushing)"
```

---

## Log Patterns

### Success Flow
```
[req_abc123] Sending downlink to 2020203907290902
[req_abc123] Gateway health check passed: 2 gateways online
[req_abc123] Added auto-uplink byte to Kuando downlink
[req_abc123] Stored expected RGB for 2020203907290902: (255,0,0), previous_counter=9
[req_abc123] Started queue monitoring for 2020203907290902 (queue_id: xyz-789)

# 15 seconds later...
✅ Downlink transmitted for 2020203907290902 - queue_id xyz-789 cleared from queue

# Device responds...
[req_def456] Kuando uplink received, payload length: 24
[req_def456] Kuando decoded payload: {'downlinks_received': 10, 'red': 255, 'blue': 0, 'green': 0, ...}
[req_def456] Downlink verification: RGB match=True (255,0,0 vs 255,0,0), counter incremented=True (10 > 9)
[req_def456] [OK] Kuando downlink verified successfully ✅
```

### Gateway Issue
```
[req_abc123] Limited gateway redundancy: only 1 gateway online. Downlink reliability may be reduced.
```

### No Gateways Online
```
[req_abc123] No online gateways available - aborting downlink to 2020203907290902
HTTP 503: No online gateways available. Cannot send downlink.
```

### Stuck Downlink
```
⚠️  Downlink STUCK for 2020203907290902 after 15s - queue_id xyz-789 still pending.
    Gateway may be offline or device not transmitting.
```

### Background Cleanup
```
Gateway issues detected: 1 offline, 1 online. Checking for stuck downlinks...
Found 2 devices with stuck downlinks
Flushing 3 stuck downlink(s) for 2020203907290902 (oldest: 2025-10-17 12:00:00)
✅ Flushed queue for 2020203907290902
```

---

## Troubleshooting

### Problem: Verification Failed

**Possible Causes:**
1. Out-of-order uplink (normal LoRaWAN behavior)
2. Device not applying color
3. Wrong RGB sent

**Action:**
- Check if counter incremented (device received it)
- If RGB wrong but counter OK → Device issue
- If both wrong → Downlink didn't reach device

### Problem: Downlink Stuck

**Possible Causes:**
1. Gateway offline
2. Device not transmitting
3. Poor signal strength

**Action:**
- Wait for background cleanup (5 min)
- Or manually flush: `DELETE /api/v1/devices/{dev_eui}/queue`
- Check gateway status: `GET /api/v1/gateways/health`

### Problem: No Gateway Online

**Symptoms:**
- HTTP 503 when sending downlink
- Log: "No online gateways available"

**Action:**
1. Check gateway connectivity
2. Restart gateways if needed
3. Verify gateway in ChirpStack UI

---

## Configuration

### Queue Monitor Timeout
**Default:** 15 seconds
**Location:** `src/main.py` line 648
```python
timeout=15  # Adjust as needed
```

### Background Cleanup Interval
**Default:** 5 minutes
**Location:** `src/background_tasks.py` line 335
```python
await asyncio.sleep(300)  # 300 seconds = 5 minutes
```

### Stuck Downlink Threshold
**Default:** 10 minutes
**Location:** `src/background_tasks.py` line 362
```python
created_at < NOW() - INTERVAL '10 minutes'
```

### Redis TTLs
**Pending Downlink:** 5 minutes (`src/main.py` line 588)
**Last Uplink:** 1 hour (`src/main.py` line 336)

---

## Kuando Auto-Uplink Setup

### Method 1: 6th Byte (Universal) ✅
**Status:** ACTIVE (automatic)
**Works on:** ALL firmware versions (3.1, 4.3, 6.1)
**How:** System automatically adds `0x01` as 6th byte
**Effect:** One-time uplink per downlink

### Method 2: 0601 Command (Persistent) 🔧
**Status:** Manual setup required
**Works on:** Firmware >= 5.6 only
**Compatible Devices:**
- `2020203907290902` (FW 6.1) ✅
- `202020390c0e0902` (FW 6.1) ✅

**To Enable:**
1. Via Kuando UI or API
2. Payload: `0601` (hex)
3. FPort: `15`
4. Send once per device

**Effect:** Persistent auto-uplink (no 6th byte needed)

---

## Performance Metrics

### Typical Verification Flow
```
T+0s   : Downlink sent
T+0.5s : Device receives downlink
T+1s   : Device sends auto-uplink
T+1.5s : API receives uplink
T+1.5s : Verification completed ✅
T+15s  : Queue monitor confirms transmission ✅
```

### Background Cleanup
```
Every 5 minutes:
- Gateway health check: ~50ms
- Stuck downlink query: ~100ms
- Queue flush (if needed): ~200ms per device
```

### Redis Operations
```
Per Downlink:
- SETEX (pending): ~1ms
- GET (last uplink): ~1ms
- DELETE (after verify): ~1ms

Total overhead: ~3ms per downlink
```

---

## API Response Examples

### Successful Downlink
```json
{
  "success": true,
  "message": "Downlink queued for 2020203907290902",
  "data": {
    "id": "dcdf00a3-a81b-4f19-ae4b-c7b56b72e196",
    "dev_eui": "2020203907290902",
    "f_port": 15,
    "confirmed": false,
    "data": "AAD//wAB",
    "gateway_health": {
      "status": "healthy",
      "online_gateways": 2,
      "total_gateways": 2
    }
  }
}
```

### Gateway Offline
```json
{
  "error": "SERVICE_UNAVAILABLE",
  "message": "No online gateways available. Cannot send downlink.",
  "status_code": 503
}
```

---

## Best Practices

### 1. Monitor Gateway Health
- Check `/api/v1/gateways/health` regularly
- Set up alerts for gateway offline events
- Maintain 2+ gateways for redundancy

### 2. Watch Verification Logs
- Monitor for consistent failures
- Investigate RGB mismatches
- Track counter increment failures

### 3. Queue Management
- Let background cleanup handle stuck downlinks
- Manual flush only for urgent cases
- Monitor queue depth per device

### 4. Firmware Upgrades
- Upgrade devices to FW >= 5.6 for persistent auto-uplink
- Test `0601` command on one device first
- Document firmware versions in device metadata

---

## Support

**Documentation:**
- Complete Guide: `docs/DOWNLINK_RELIABILITY_IMPLEMENTATION_COMPLETE.md`
- Progress Tracking: `docs/RELIABILITY_PROGRESS_2025-10-17.md`
- Changelog: `CHANGELOG.md` (v5.2.1)

**Logs:**
- Main logs: `docker logs parking-api`
- Filtered logs: See "Monitoring Commands" above

**Health Checks:**
- API: `GET /health`
- Gateways: `GET /api/v1/gateways/health`

---

**Version:** 5.2.1
**Status:** ✅ Production Ready
**Last Updated:** 2025-10-17
