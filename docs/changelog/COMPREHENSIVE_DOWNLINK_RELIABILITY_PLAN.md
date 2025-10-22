# Comprehensive Downlink Reliability Implementation Plan

**Date:** 2025-10-17
**Goal:** 100% reliable downlinks at scale (hundreds of devices, multiple gateways)
**Status:** Ready for Implementation

---

## Executive Summary

This plan leverages **Kuando's automatic uplink feature** (command `0601`) to achieve unprecedented downlink reliability. By enabling persistent auto-uplink on all devices, we get implicit acknowledgment for every downlink, enabling intelligent retry, verification, and gateway failover.

**Key Innovation:** Command `0601` makes every downlink trigger an automatic uplink containing:
- Downlink counter (verification of receipt)
- Current RGB values (state confirmation)
- RSSI/SNR from device perspective (gateway quality)
- Triggers ChirpStack gateway routing update

---

## Current State

### ✅ Phase 0: Foundation (COMPLETE)
**Status:** Implemented and tested

1. **Gateway Health Monitoring**
   - Tracks online/offline status (5-minute threshold)
   - Real-time health summary API
   - 30-second cache for performance
   - Endpoints:
     - `GET /api/v1/gateways/health`
     - `GET /api/v1/gateways`
     - `GET /api/v1/gateways/{id}/status`

2. **Downlink Queue Method**
   - `ChirpStackClient.queue_downlink()` - gRPC enqueue
   - Returns queue ID
   - Works for devices with online gateways

**Gap:** Monitoring only, no action on failures

---

## The Auto-Uplink Game Changer

### Kuando Command `0601` - Persistent Auto-Uplink

**What it does:**
```python
# Send once to device after join
await chirpstack.queue_downlink(dev_eui, bytes.fromhex('0601'), fport=15)

# Result: Device now sends automatic uplink after EVERY downlink
# Setting persists across power cycles
```

### Uplink Payload Structure (24 or 25 bytes)

| Bytes | Type | Content | Use Case |
|-------|------|---------|----------|
| 0-3 | int32 | RSSI (dBm) | Gateway quality from device perspective |
| 4-7 | int32 | SNR (dB) | Gateway quality from device perspective |
| 8-11 | uint32 | **Downlinks received** | ✅ Verify receipt (counter increments) |
| 12-15 | uint32 | Uplinks sent | Statistics |
| 16 | byte | **Last color RED** | ✅ Verify correct color received |
| 17 | byte | **Last color BLUE** | ✅ Verify correct color received |
| 18 | byte | **Last color GREEN** | ✅ Verify correct color received |
| 19 | byte | Time On (1/10 sec) | Verify flash pattern |
| 20 | byte | Time Off (1/10 sec) | Verify flash pattern |
| 21 | byte | SW revision | Device info |
| 22 | byte | HW revision | Device info |
| 23 | byte | ADR state | Network info |
| 24 | byte | High brightness (optional) | Display mode |

**Critical insight:** Bytes 8-11 (downlink counter) + bytes 16-18 (RGB values) provide **perfect verification** that:
1. Device received the downlink (counter incremented)
2. Device applied the correct color (RGB matches what we sent)

---

## Implementation Phases

### Phase 1: Auto-Uplink Infrastructure (HIGH PRIORITY) 🔴

#### 1.1 Device Initialization System
**File:** `/opt/v5-smart-parking/src/device_initializer.py` (NEW)

```python
"""
Kuando Device Initialization
Automatically configures devices on first join
"""
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DeviceInitializer:
    """Initialize Kuando devices with persistent settings"""

    def __init__(self, chirpstack_client, redis_client):
        self.chirpstack = chirpstack_client
        self.redis = redis_client

    async def initialize_device(self, dev_eui: str) -> Dict[str, Any]:
        """
        Initialize Kuando device with persistent auto-uplink

        Called when:
        - Device first joins network
        - Device re-joins after being offline
        - Manual re-initialization requested
        """
        logger.info(f"Initializing Kuando device {dev_eui}")

        # Check if already initialized recently (avoid duplicate init)
        init_key = f"device:{dev_eui}:initialized"
        last_init = await self.redis.get(init_key)

        if last_init:
            last_init_time = datetime.fromisoformat(last_init.decode())
            if datetime.utcnow() - last_init_time < timedelta(hours=1):
                logger.debug(f"Device {dev_eui} initialized recently, skipping")
                return {"status": "already_initialized", "initialized_at": last_init}

        try:
            # Step 1: Enable persistent auto-uplink (command 0601)
            result = await self.chirpstack.queue_downlink(
                device_eui=dev_eui,
                payload=bytes.fromhex('0601'),
                fport=15,
                confirmed=False
            )

            logger.info(f"Sent auto-uplink enable command (0601) to {dev_eui}, queue_id={result['id']}")

            # Step 2: Set custom uplink interval to 15 minutes (optional)
            # Command: 040F (0x04 = set interval, 0x0F = 15 minutes)
            await asyncio.sleep(2)  # Wait 2 seconds between commands

            interval_result = await self.chirpstack.queue_downlink(
                device_eui=dev_eui,
                payload=bytes.fromhex('040F'),  # 15-minute heartbeat
                fport=15,
                confirmed=False
            )

            logger.info(f"Set uplink interval to 15 minutes for {dev_eui}, queue_id={interval_result['id']}")

            # Step 3: Mark device as initialized
            init_time = datetime.utcnow().isoformat()
            await self.redis.set(init_key, init_time, ex=86400)  # 24h expiry

            # Step 4: Store initialization metadata
            await self.redis.hset(
                f"device:{dev_eui}:config",
                mapping={
                    "auto_uplink_enabled": "true",
                    "uplink_interval_minutes": "15",
                    "initialized_at": init_time,
                    "init_version": "1.0"
                }
            )

            return {
                "status": "initialized",
                "dev_eui": dev_eui,
                "auto_uplink_enabled": True,
                "uplink_interval": 15,
                "initialized_at": init_time,
                "commands_sent": [
                    {"command": "0601", "queue_id": result['id']},
                    {"command": "040F", "queue_id": interval_result['id']}
                ]
            }

        except Exception as e:
            logger.error(f"Failed to initialize device {dev_eui}: {e}")
            return {
                "status": "failed",
                "dev_eui": dev_eui,
                "error": str(e)
            }

    async def initialize_all_devices(self) -> Dict[str, Any]:
        """Initialize all Kuando devices in the system"""
        logger.info("Starting bulk device initialization")

        # Get all Kuando devices from database
        async with self.chirpstack.pool.acquire() as conn:
            devices = await conn.fetch("""
                SELECT encode(dev_eui, 'hex') as dev_eui, name
                FROM device
                WHERE device_profile_id IN (
                    SELECT id FROM device_profile WHERE name ILIKE '%kuando%'
                )
                AND is_disabled = false
            """)

        results = []
        for device in devices:
            dev_eui = device['dev_eui']
            result = await self.initialize_device(dev_eui)
            results.append(result)

            # Stagger initialization to avoid flooding ChirpStack
            await asyncio.sleep(5)

        success_count = sum(1 for r in results if r['status'] == 'initialized')

        return {
            "total_devices": len(devices),
            "initialized": success_count,
            "skipped": sum(1 for r in results if r['status'] == 'already_initialized'),
            "failed": sum(1 for r in results if r['status'] == 'failed'),
            "results": results
        }
```

#### 1.2 Uplink Parser
**File:** `/opt/v5-smart-parking/src/uplink_parser.py` (NEW)

```python
"""
Kuando Uplink Payload Parser
Decodes auto-uplink responses from Kuando devices
"""
import struct
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class KuandoUplinkParser:
    """Parse Kuando Busylight uplink payloads"""

    @staticmethod
    def parse(payload_hex: str) -> Dict[str, Any]:
        """
        Parse Kuando uplink payload

        Args:
            payload_hex: Hex-encoded payload (24 or 25 bytes)

        Returns:
            Dictionary with parsed fields
        """
        try:
            payload = bytes.fromhex(payload_hex)
            length = len(payload)

            if length not in [24, 25]:
                logger.warning(f"Unexpected payload length: {length} bytes")
                return {"error": "invalid_length", "length": length}

            # Parse using struct (little-endian for integers)
            rssi = struct.unpack('<i', payload[0:4])[0]  # Signed int32
            snr = struct.unpack('<i', payload[4:8])[0]   # Signed int32
            downlinks_received = struct.unpack('<I', payload[8:12])[0]  # Unsigned int32
            uplinks_sent = struct.unpack('<I', payload[12:16])[0]       # Unsigned int32

            # Parse color bytes
            last_color_red = payload[16]
            last_color_blue = payload[17]
            last_color_green = payload[18]

            # Parse timing
            time_on = payload[19]   # 1/10 seconds
            time_off = payload[20]  # 1/10 seconds

            # Parse device info
            sw_revision = payload[21]
            hw_revision = payload[22]
            adr_state = payload[23]

            # Optional high brightness mode (byte 24)
            high_brightness = payload[24] if length == 25 else None

            return {
                "rssi_dbm": rssi,
                "snr_db": snr,
                "downlinks_received": downlinks_received,
                "uplinks_sent": uplinks_sent,
                "last_color": {
                    "red": last_color_red,
                    "blue": last_color_blue,
                    "green": last_color_green,
                    "hex": f"{last_color_red:02x}{last_color_blue:02x}{last_color_green:02x}"
                },
                "timing": {
                    "on_deciseconds": time_on,
                    "off_deciseconds": time_off,
                    "on_seconds": time_on / 10.0,
                    "off_seconds": time_off / 10.0
                },
                "device_info": {
                    "sw_revision": sw_revision,
                    "hw_revision": hw_revision,
                    "adr_enabled": bool(adr_state),
                    "high_brightness": high_brightness
                },
                "parsed_successfully": True
            }

        except Exception as e:
            logger.error(f"Failed to parse uplink payload: {e}")
            return {
                "error": "parse_failed",
                "exception": str(e),
                "parsed_successfully": False
            }

    @staticmethod
    def verify_downlink_receipt(
        expected_color: Dict[str, int],
        uplink_data: Dict[str, Any],
        previous_downlink_counter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Verify that device received and applied downlink correctly

        Args:
            expected_color: {"red": 255, "blue": 0, "green": 0}
            uplink_data: Parsed uplink data
            previous_downlink_counter: Last known counter value

        Returns:
            Verification result
        """
        if not uplink_data.get('parsed_successfully'):
            return {
                "verified": False,
                "reason": "uplink_parse_failed"
            }

        # Check 1: Color matches
        actual_color = uplink_data['last_color']
        color_matches = (
            actual_color['red'] == expected_color['red'] and
            actual_color['blue'] == expected_color['blue'] and
            actual_color['green'] == expected_color['green']
        )

        # Check 2: Counter incremented (if we have previous value)
        counter_incremented = None
        if previous_downlink_counter is not None:
            current_counter = uplink_data['downlinks_received']
            counter_incremented = current_counter > previous_downlink_counter

        verified = color_matches and (counter_incremented is not False)

        return {
            "verified": verified,
            "color_matches": color_matches,
            "counter_incremented": counter_incremented,
            "expected_color": expected_color,
            "actual_color": {
                "red": actual_color['red'],
                "blue": actual_color['blue'],
                "green": actual_color['green']
            },
            "downlinks_received": uplink_data['downlinks_received'],
            "previous_counter": previous_downlink_counter
        }
```

#### 1.3 Integration: Uplink Event Handler
**File:** Modify `/opt/v5-smart-parking/src/main.py`

Add webhook endpoint to receive uplink events from ChirpStack:

```python
@app.post("/api/v1/webhooks/chirpstack/uplink", tags=["webhooks"])
async def handle_chirpstack_uplink(event: Dict[str, Any]):
    """
    Handle uplink events from ChirpStack webhook

    ChirpStack sends uplink events to this endpoint.
    We parse Kuando auto-uplink responses and verify downlinks.
    """
    try:
        # Extract device EUI and payload
        dev_eui = event.get('deviceInfo', {}).get('devEui')
        f_port = event.get('fPort')
        data_hex = event.get('data')  # Base64 encoded

        if not dev_eui or not data_hex:
            logger.warning("Uplink event missing devEui or data")
            return {"status": "ignored", "reason": "missing_fields"}

        # Decode base64 to hex
        import base64
        payload_bytes = base64.b64decode(data_hex)
        payload_hex = payload_bytes.hex()

        logger.info(f"Uplink from {dev_eui}: fPort={f_port}, payload={payload_hex}")

        # Parse if it's a Kuando uplink (24 or 25 bytes on fPort 15)
        if f_port == 15 and len(payload_bytes) in [24, 25]:
            from .uplink_parser import KuandoUplinkParser

            parsed = KuandoUplinkParser.parse(payload_hex)

            if parsed.get('parsed_successfully'):
                # Store parsed uplink data in Redis
                await redis_client.hset(
                    f"device:{dev_eui}:last_uplink",
                    mapping={
                        "timestamp": datetime.utcnow().isoformat(),
                        "rssi": parsed['rssi_dbm'],
                        "snr": parsed['snr_db'],
                        "downlinks_received": parsed['downlinks_received'],
                        "uplinks_sent": parsed['uplinks_sent'],
                        "last_color_red": parsed['last_color']['red'],
                        "last_color_blue": parsed['last_color']['blue'],
                        "last_color_green": parsed['last_color']['green']
                    }
                )

                logger.info(
                    f"Device {dev_eui} uplink: "
                    f"RSSI={parsed['rssi_dbm']}dBm, "
                    f"SNR={parsed['snr_db']}dB, "
                    f"Downlinks={parsed['downlinks_received']}, "
                    f"Color=#{parsed['last_color']['hex']}"
                )

                # Check if we're waiting for verification of a pending downlink
                pending_key = f"downlink:{dev_eui}:pending"
                pending = await redis_client.hgetall(pending_key)

                if pending:
                    # Verify the downlink
                    expected_color = {
                        "red": int(pending[b'expected_red']),
                        "blue": int(pending[b'expected_blue']),
                        "green": int(pending[b'expected_green'])
                    }
                    previous_counter = int(pending[b'previous_counter']) if b'previous_counter' in pending else None

                    verification = KuandoUplinkParser.verify_downlink_receipt(
                        expected_color=expected_color,
                        uplink_data=parsed,
                        previous_downlink_counter=previous_counter
                    )

                    if verification['verified']:
                        logger.info(f"✅ Downlink verified for {dev_eui}")
                        await redis_client.delete(pending_key)
                    else:
                        logger.warning(
                            f"⚠️ Downlink verification failed for {dev_eui}: "
                            f"color_matches={verification['color_matches']}, "
                            f"counter_incremented={verification['counter_incremented']}"
                        )

        return {"status": "processed", "dev_eui": dev_eui}

    except Exception as e:
        logger.error(f"Failed to process uplink event: {e}")
        return {"status": "error", "error": str(e)}
```

---

### Phase 2: Intelligent Downlink System (HIGH PRIORITY) 🔴

#### 2.1 Enhanced Downlink with Verification
**File:** `/opt/v5-smart-parking/src/intelligent_downlink.py` (NEW)

```python
"""
Intelligent Downlink Manager
Sends downlinks with automatic verification and retry
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class IntelligentDownlinkManager:
    """
    Manages downlink transmission with:
    - Pre-flight gateway health checks
    - Automatic verification via uplinks
    - Intelligent retry with exponential backoff
    - Queue cleanup for stuck downlinks
    """

    def __init__(
        self,
        chirpstack_client,
        gateway_monitor,
        redis_client,
        max_retries: int = 3,
        verification_timeout: int = 30
    ):
        self.chirpstack = chirpstack_client
        self.gateway_monitor = gateway_monitor
        self.redis = redis_client
        self.max_retries = max_retries
        self.verification_timeout = verification_timeout

    async def send_color_command(
        self,
        dev_eui: str,
        red: int,
        blue: int,
        green: int,
        on_time: int = 255,
        off_time: int = 0,
        wait_for_verification: bool = True
    ) -> Dict[str, Any]:
        """
        Send color command to Kuando device with automatic verification

        Args:
            dev_eui: Device EUI
            red: Red intensity (0-255)
            blue: Blue intensity (0-255)
            green: Green intensity (0-255)
            on_time: On duration in 1/100 seconds (default: steady)
            off_time: Off duration in 1/100 seconds (default: 0 = steady)
            wait_for_verification: Wait for uplink confirmation

        Returns:
            Result with verification status
        """
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            logger.info(
                f"Sending color command to {dev_eui} "
                f"(attempt {attempt}/{self.max_retries}): "
                f"RGB({red},{blue},{green})"
            )

            try:
                # Step 1: Pre-flight gateway health check
                gw_health = await self.gateway_monitor.get_health_summary()

                if gw_health['online_count'] == 0:
                    logger.error("No gateways online - cannot send downlink")
                    if attempt < self.max_retries:
                        await asyncio.sleep(10 * attempt)  # Wait before retry
                        continue
                    return {
                        "status": "failed",
                        "reason": "no_online_gateways",
                        "attempts": attempt
                    }

                if gw_health['online_count'] < 2:
                    logger.warning(f"Only {gw_health['online_count']} gateway online - limited redundancy")

                # Step 2: Get current downlink counter
                last_uplink = await self.redis.hgetall(f"device:{dev_eui}:last_uplink")
                previous_counter = None
                if last_uplink and b'downlinks_received' in last_uplink:
                    previous_counter = int(last_uplink[b'downlinks_received'])

                # Step 3: Compose payload (5 bytes: R,B,G,OnTime,OffTime)
                payload = bytes([red, blue, green, on_time, off_time])

                # Step 4: Send downlink
                result = await self.chirpstack.queue_downlink(
                    device_eui=dev_eui,
                    payload=payload,
                    fport=15,
                    confirmed=False
                )

                queue_id = result['id']
                logger.info(f"Downlink queued: queue_id={queue_id}")

                # Step 5: Store pending downlink for verification
                if wait_for_verification:
                    await self.redis.hset(
                        f"downlink:{dev_eui}:pending",
                        mapping={
                            "queue_id": queue_id,
                            "expected_red": red,
                            "expected_blue": blue,
                            "expected_green": green,
                            "previous_counter": previous_counter or 0,
                            "sent_at": datetime.utcnow().isoformat(),
                            "attempt": attempt
                        }
                    )
                    await self.redis.expire(f"downlink:{dev_eui}:pending", self.verification_timeout)

                    # Step 6: Wait for verification via uplink
                    logger.info(f"Waiting up to {self.verification_timeout}s for uplink verification...")

                    verified = await self._wait_for_verification(dev_eui, self.verification_timeout)

                    if verified:
                        logger.info(f"✅ Downlink verified for {dev_eui}")
                        return {
                            "status": "success",
                            "verified": True,
                            "dev_eui": dev_eui,
                            "queue_id": queue_id,
                            "attempts": attempt,
                            "color": {"red": red, "blue": blue, "green": green}
                        }
                    else:
                        logger.warning(f"⚠️ Downlink not verified within {self.verification_timeout}s")

                        # Check device queue for stuck downlinks
                        await self._cleanup_stuck_queue(dev_eui)

                        if attempt < self.max_retries:
                            backoff = 10 * (2 ** (attempt - 1))  # 10s, 20s, 40s
                            logger.info(f"Retrying in {backoff}s...")
                            await asyncio.sleep(backoff)
                            continue

                        return {
                            "status": "unverified",
                            "verified": False,
                            "dev_eui": dev_eui,
                            "queue_id": queue_id,
                            "attempts": attempt,
                            "reason": "verification_timeout"
                        }
                else:
                    # Fire and forget mode
                    return {
                        "status": "sent",
                        "verified": None,
                        "dev_eui": dev_eui,
                        "queue_id": queue_id,
                        "attempts": attempt
                    }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Downlink attempt {attempt} failed: {e}")

                if attempt < self.max_retries:
                    backoff = 5 * attempt
                    await asyncio.sleep(backoff)
                    continue

                return {
                    "status": "error",
                    "error": last_error,
                    "attempts": attempt
                }

        # Max retries exceeded
        return {
            "status": "failed",
            "reason": "max_retries_exceeded",
            "attempts": attempt,
            "last_error": last_error
        }

    async def _wait_for_verification(self, dev_eui: str, timeout: int) -> bool:
        """
        Wait for uplink verification
        Checks Redis for pending downlink clearance
        """
        pending_key = f"downlink:{dev_eui}:pending"

        for _ in range(timeout):
            await asyncio.sleep(1)

            # Check if pending key still exists
            exists = await self.redis.exists(pending_key)
            if not exists:
                # Key was deleted by uplink handler = verification success
                return True

        return False

    async def _cleanup_stuck_queue(self, dev_eui: str):
        """Flush device queue if downlink stuck"""
        try:
            queue = await self.chirpstack.get_device_queue(dev_eui)

            if queue:
                logger.warning(f"Flushing {len(queue)} stuck items from {dev_eui} queue")
                await self.chirpstack.flush_device_queue(dev_eui)
        except Exception as e:
            logger.error(f"Failed to cleanup queue for {dev_eui}: {e}")
```

#### 2.2 API Integration
**File:** Modify `/opt/v5-smart-parking/src/main.py`

Update the downlink endpoint to use intelligent downlink manager:

```python
@app.post("/api/v1/downlink/{dev_eui}", tags=["downlink"])
async def send_downlink_command(
    dev_eui: str,
    command: Dict[str, Any]
):
    """
    Send downlink command to Kuando device with automatic verification

    Body:
    {
        "red": 255,
        "blue": 0,
        "green": 0,
        "on_time": 255,
        "off_time": 0,
        "wait_for_verification": true
    }
    """
    try:
        from .intelligent_downlink import IntelligentDownlinkManager

        downlink_mgr = IntelligentDownlinkManager(
            chirpstack_client=chirpstack,
            gateway_monitor=gateway_monitor,
            redis_client=redis_client,
            max_retries=3,
            verification_timeout=30
        )

        result = await downlink_mgr.send_color_command(
            dev_eui=dev_eui,
            red=command.get('red', 0),
            blue=command.get('blue', 0),
            green=command.get('green', 0),
            on_time=command.get('on_time', 255),
            off_time=command.get('off_time', 0),
            wait_for_verification=command.get('wait_for_verification', True)
        )

        return result

    except Exception as e:
        logger.error(f"Downlink command failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Phase 3: Background Services (MEDIUM PRIORITY) 🟡

#### 3.1 Automatic Stuck Queue Cleanup
**File:** `/opt/v5-smart-parking/src/background_tasks.py` (NEW)

```python
"""
Background maintenance tasks
"""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Manages background maintenance tasks"""

    def __init__(self, chirpstack_client, gateway_monitor):
        self.chirpstack = chirpstack_client
        self.gateway_monitor = gateway_monitor
        self._running = False

    async def start(self):
        """Start all background tasks"""
        self._running = True
        logger.info("Starting background tasks")

        # Start cleanup task (runs every 5 minutes)
        asyncio.create_task(self._cleanup_stuck_downlinks_loop())

    async def stop(self):
        """Stop all background tasks"""
        self._running = False
        logger.info("Stopping background tasks")

    async def _cleanup_stuck_downlinks_loop(self):
        """Periodically cleanup stuck downlinks"""
        while self._running:
            try:
                await self._cleanup_stuck_downlinks()
            except Exception as e:
                logger.error(f"Stuck downlink cleanup failed: {e}")

            await asyncio.sleep(300)  # 5 minutes

    async def _cleanup_stuck_downlinks(self):
        """
        Find and flush stuck downlinks
        Targets devices with:
        - Pending downlinks > 10 minutes old
        - Gateway offline
        """
        gw_health = await self.gateway_monitor.get_health_summary()

        if gw_health['offline_count'] == 0:
            logger.debug("All gateways online, skipping stuck downlink cleanup")
            return

        logger.info(f"Checking for stuck downlinks ({gw_health['offline_count']} gateways offline)")

        async with self.chirpstack.pool.acquire() as conn:
            # Find devices with old pending downlinks
            stuck = await conn.fetch("""
                SELECT
                    encode(dev_eui, 'hex') as dev_eui,
                    COUNT(*) as pending_count,
                    MIN(created_at) as oldest_created
                FROM device_queue_item
                WHERE is_pending = true
                  AND created_at < NOW() - INTERVAL '10 minutes'
                GROUP BY dev_eui
            """)

            for record in stuck:
                dev_eui = record['dev_eui']
                pending_count = record['pending_count']
                oldest = record['oldest_created']

                age_minutes = int((datetime.utcnow() - oldest.replace(tzinfo=None)).total_seconds() / 60)

                logger.warning(
                    f"Flushing {pending_count} stuck downlinks for {dev_eui} "
                    f"(oldest: {age_minutes} minutes)"
                )

                await self.chirpstack.flush_device_queue(dev_eui)
```

---

### Phase 4: Monitoring & Metrics (LOW PRIORITY) 🟢

#### 4.1 Success Rate Tracking
**File:** `/opt/v5-smart-parking/src/metrics.py` (NEW)

```python
"""
Downlink success metrics and reporting
"""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DownlinkMetrics:
    """Track downlink success rates and performance"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def record_downlink_result(
        self,
        dev_eui: str,
        status: str,
        attempts: int = 1,
        verified: bool = False
    ):
        """
        Record downlink outcome

        Args:
            dev_eui: Device EUI
            status: "success", "failed", "unverified"
            attempts: Number of retry attempts
            verified: Whether uplink verification succeeded
        """
        timestamp = datetime.utcnow()

        # Store in sorted set (time-series)
        await self.redis.zadd(
            f"metrics:downlink:{dev_eui}",
            {
                f"{timestamp.isoformat()}:{status}:{verified}:{attempts}": timestamp.timestamp()
            }
        )

        # Keep only last 7 days
        cutoff = (timestamp - timedelta(days=7)).timestamp()
        await self.redis.zremrangebyscore(f"metrics:downlink:{dev_eui}", 0, cutoff)

    async def get_success_rate(
        self,
        dev_eui: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Calculate downlink success rate for device"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        metrics = await self.redis.zrangebyscore(
            f"metrics:downlink:{dev_eui}",
            cutoff.timestamp(),
            "+inf"
        )

        if not metrics:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "unverified": 0,
                "success_rate": 0.0,
                "avg_attempts": 0.0
            }

        total = len(metrics)
        success = sum(1 for m in metrics if b':success:' in m)
        failed = sum(1 for m in metrics if b':failed:' in m)
        unverified = sum(1 for m in metrics if b':unverified:' in m)

        # Calculate average attempts
        attempts = []
        for m in metrics:
            parts = m.decode().split(':')
            if len(parts) >= 4:
                attempts.append(int(parts[3]))

        avg_attempts = sum(attempts) / len(attempts) if attempts else 0

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "unverified": unverified,
            "success_rate": (success / total * 100) if total > 0 else 0.0,
            "avg_attempts": round(avg_attempts, 2),
            "period_hours": hours
        }
```

---

## ChirpStack Configuration

### Webhook Setup

Configure ChirpStack to send uplink events to our API:

**ChirpStack UI → Applications → smart-parking → Integrations → HTTP**

```json
{
  "uplink": {
    "endpoint": "http://api:8000/api/v1/webhooks/chirpstack/uplink",
    "headers": {
      "Authorization": "Bearer <API_KEY>"
    }
  }
}
```

---

## Implementation Priority

### Must Have (Week 1) 🔴
1. ✅ Gateway health monitoring (DONE)
2. ❌ Device initializer (send `0601` on join)
3. ❌ Uplink parser
4. ❌ Uplink webhook handler
5. ❌ Intelligent downlink manager
6. ❌ Update UI to use new downlink endpoint

### Should Have (Week 2) 🟡
7. ❌ Background stuck queue cleanup
8. ❌ ChirpStack webhook configuration
9. ❌ Bulk device initialization
10. ❌ Success rate metrics

### Nice to Have (Future) 🟢
11. ❌ Dashboard for downlink metrics
12. ❌ Alert system for failures
13. ❌ Gateway quality tracking
14. ❌ Predictive failure detection

---

## Expected Results

### Scenario: Gateway Goes Offline During Downlink

**Current Behavior (Without Auto-Uplink):**
```
1. Gateway offline
2. Downlink sent → stuck in queue forever
3. Device never receives command
4. No feedback, manual intervention required
```

**New Behavior (With Auto-Uplink + Intelligence):**
```
1. Gateway offline (detected by monitor)
2. Downlink sent to ChirpStack
3. No uplink received within 30s → unverified
4. Auto-flush stuck queue
5. Retry #1 after 10s (hoping device switched gateway via heartbeat)
6. If still stuck: Retry #2 after 20s
7. If still stuck: Retry #3 after 40s
8. If all fail: Log failure, alert, record metrics
```

### Scenario: All Gateways Online, Normal Operation

**New Behavior:**
```
1. Pre-flight check: 2/4 gateways online ✅
2. Send downlink (queue_id=abc123)
3. Device receives → changes color → sends auto-uplink
4. Uplink received within 3-5s
5. Parser verifies: counter incremented ✅, color matches ✅
6. Success logged, no retry needed
7. Metrics: 100% success rate
```

---

## Testing Plan

### Phase 1: Basic Functionality
1. Initialize single device with `0601`
2. Send color command
3. Verify uplink received
4. Verify color matches

### Phase 2: Gateway Failure
1. Take gateway offline
2. Send downlink
3. Verify retry logic triggers
4. Verify queue cleanup works
5. Bring gateway back online
6. Verify eventual success

### Phase 3: Scale Testing
1. Initialize 50 devices
2. Send 100 downlinks
3. Measure success rate
4. Analyze retry patterns
5. Test concurrent downlinks

---

## Estimated Implementation Time

| Phase | Task | Hours |
|-------|------|-------|
| 1 | Device initializer | 4 |
| 1 | Uplink parser | 3 |
| 1 | Webhook handler | 3 |
| 1 | Intelligent downlink manager | 6 |
| 1 | API integration | 2 |
| 2 | Background cleanup | 4 |
| 2 | ChirpStack webhook setup | 1 |
| 2 | Bulk initialization | 2 |
| 3 | Metrics system | 4 |
| 3 | Testing & debugging | 8 |
| **Total** | | **37 hours** |

---

## Success Criteria

1. **100% visibility** - Know status of every downlink
2. **95%+ success rate** - At scale with multiple gateways
3. **Automatic recovery** - No manual intervention for transient failures
4. **Fast feedback** - Verification within 30 seconds
5. **Scalable** - Works with hundreds of devices

---

## Next Steps

Ready to proceed with implementation?

**Recommended order:**
1. Implement device initializer
2. Implement uplink parser
3. Add webhook endpoint
4. Build intelligent downlink manager
5. Test with single device
6. Roll out to all devices
7. Monitor and optimize

---

**Document Version:** 1.0
**Author:** Claude Code
**Date:** 2025-10-17
**Status:** Ready for Implementation
