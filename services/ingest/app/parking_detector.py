"""parking_detector.py - Parking Sensor Detection and Forwarding
Version: 1.0.4 - 2025-10-14 16:30 UTC
Changelog:
- v1.0.4: Fixed fport=0 MAC command handling (ignore instead of treating as FREE)
- v1.0.3: Use uppercase DevEUIs to match ChirpStack format
- v1.0.2: Removed debug logging, verified working end-to-end pipeline
- v1.0.1: Fixed payload decoder to use bytes.fromhex() instead of base64.b64decode()
- v1.0.0: Initial implementation with cache, background refresh, Browan decoder
"""

import asyncio
import os
import httpx
from typing import Set, Dict, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("parking-detector")

class ParkingSensorDetector:
    """
    Fast in-memory cache for parking sensor detection
    Optimized for O(1) lookup performance in uplink processing
    """

    def __init__(self, parking_service_url: str = os.getenv("PARKING_DISPLAY_SERVICE_URL", "http://parking-display:8100")):
        self.parking_service_url = parking_service_url
        self.parking_sensors: Set[str] = set()
        self.sensor_to_space: Dict[str, str] = {}  # dev_eui -> space_id
        self.last_refresh: Optional[datetime] = None
        self.refresh_interval = timedelta(minutes=5)

    async def refresh_cache(self):
        """Refresh parking sensor cache from Parking Display Service"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.parking_service_url}/v1/spaces/sensor-list"
                )

                if response.status_code == 200:
                    data = response.json()

                    # Atomic update of cache - keep uppercase as received from ChirpStack
                    new_sensors = {dev_eui.upper() for dev_eui in data.get("sensor_deveuis", [])}
                    new_mapping = {dev_eui.upper(): space_id for dev_eui, space_id in data.get("sensor_to_space", {}).items()}

                    self.parking_sensors = new_sensors
                    self.sensor_to_space = new_mapping
                    self.last_refresh = datetime.utcnow()

                    logger.info(f"Parking sensor cache refreshed: {len(new_sensors)} sensors")
                    return True
                else:
                    logger.warning(f"Failed to refresh parking cache: HTTP {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error refreshing parking sensor cache: {e}")
            return False

    def is_parking_sensor(self, dev_eui: str) -> bool:
        """Fast O(1) lookup for parking sensor detection"""
        return dev_eui.upper() in self.parking_sensors

    def get_space_id(self, dev_eui: str) -> Optional[str]:
        """Get space ID for parking sensor"""
        return self.sensor_to_space.get(dev_eui.upper())

    def needs_refresh(self) -> bool:
        """Check if cache needs refresh"""
        if self.last_refresh is None:
            return True
        return datetime.utcnow() - self.last_refresh > self.refresh_interval

    async def ensure_fresh_cache(self):
        """Ensure cache is fresh, refresh if needed"""
        if self.needs_refresh():
            await self.refresh_cache()

# Global instance
parking_detector = ParkingSensorDetector()

async def refresh_parking_cache_task():
    """Background task to refresh parking sensor cache"""
    logger.info("Starting parking sensor cache refresh task (parking_detector.py v1.0.4)")

    # Initial refresh
    await parking_detector.refresh_cache()

    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes
            await parking_detector.refresh_cache()
        except Exception as e:
            logger.error(f"Error in parking cache refresh task: {e}")
            await asyncio.sleep(60)  # Retry in 1 minute on error

async def forward_to_parking_display(uplink_data: dict, space_id: str):
    """Forward parking sensor data to Parking Display Service"""
    try:
        dev_eui = uplink_data.get("devEUI", "").upper()

        # Extract occupancy state from payload
        occupancy_state = extract_occupancy_from_payload(uplink_data)

        # Skip if payload should be ignored (MAC commands, empty payloads, etc.)
        if occupancy_state is None:
            logger.info(f"⏭️  Skipping parking actuation for {dev_eui} (no valid occupancy state)")
            return

        # Prepare payload for Parking Display Service
        parking_payload = {
            "sensor_deveui": dev_eui,
            "space_id": space_id,
            "occupancy_state": occupancy_state,
            "timestamp": uplink_data.get("timestamp", datetime.utcnow().isoformat()),
            "raw_payload": uplink_data.get("data", ""),
            "payload_data": {"occupancy": occupancy_state},
            "rssi": None,
            "snr": None
        }

        # Extract RSSI/SNR from rxInfo if available
        rx_info = uplink_data.get("rxInfo", [])
        if rx_info and len(rx_info) > 0:
            parking_payload["rssi"] = rx_info[0].get("rssi")
            parking_payload["snr"] = rx_info[0].get("snr")

        # Send to Parking Display Service
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                f"{os.getenv('PARKING_DISPLAY_SERVICE_URL', 'http://parking-display:8100')}/v1/actuations/sensor-uplink",
                json=parking_payload
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"🅿️ Parking actuation: {dev_eui} -> {occupancy_state} (status: {result.get('status')})")
            else:
                logger.warning(f"Parking forward failed: HTTP {response.status_code} for {dev_eui}")

    except Exception as e:
        logger.error(f"Error forwarding to parking display: {e}")

def extract_occupancy_from_payload(uplink_data: dict) -> Optional[str]:
    """
    Extract occupancy state from Browan TABS Motion payload
    Payload format: First byte 00=FREE, 01=OCCUPIED
    Returns: FREE, OCCUPIED, or None (if uplink should be ignored)
    """
    try:
        dev_eui = uplink_data.get("devEUI", "").upper()
        fport = uplink_data.get("fPort", 0)
        payload_hex = uplink_data.get("data", "")

        # Ignore MAC commands (fport=0) - these have no application payload
        if fport == 0:
            logger.info(f"⏭️  Ignoring MAC command (fport=0) for {dev_eui}")
            return None

        # Ignore empty payloads - don't assume state
        if not payload_hex:
            logger.warning(f"⏭️  No payload data for {dev_eui} on fport {fport}, skipping")
            return None

        # Convert hex string to bytes
        try:
            payload_bytes = bytes.fromhex(payload_hex)
        except ValueError as e:
            logger.warning(f"Invalid hex payload for {dev_eui}: {payload_hex} ({e})")
            return None

        if len(payload_bytes) < 1:
            logger.warning(f"Payload too short for {dev_eui}")
            return None

        # First byte: 0x00 = FREE, 0x01 = OCCUPIED
        first_byte = payload_bytes[0]
        occupancy = "OCCUPIED" if first_byte == 0x01 else "FREE"

        logger.info(f"📊 Decoded {dev_eui}: byte={first_byte:02x} -> {occupancy}")
        return occupancy

    except Exception as e:
        logger.error(f"Failed to extract occupancy from {uplink_data.get('devEUI')}: {e}")
        return None
