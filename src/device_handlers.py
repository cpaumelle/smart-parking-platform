"""
Device handlers for different sensor types
Copy the decoding logic from your old code here
"""
import base64
import logging
from typing import Dict, Any, Optional, Protocol, List
from abc import ABC, abstractmethod
import struct

from .models import SpaceState, SensorUplink
from .utils import hex_to_base64, base64_to_hex, get_display_color

logger = logging.getLogger(__name__)

# ============================================================
# Device Handler Protocol
# ============================================================

class DeviceHandler(Protocol):
    """Protocol for device handlers"""

    def can_handle(self, device_eui: str) -> bool:
        """Check if this handler can process the device"""
        ...

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse uplink data from device"""
        ...

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode downlink command"""
        ...

# ============================================================
# Base Handler
# ============================================================

class BaseDeviceHandler(ABC):
    """Base class for device handlers"""

    def __init__(self):
        self.device_patterns = []  # DevEUI patterns this handler supports

    def can_handle(self, device_eui: str) -> bool:
        """Check if this handler supports the device"""
        device_eui = device_eui.lower()

        for pattern in self.device_patterns:
            if device_eui.startswith(pattern):
                return True

        return False

    @abstractmethod
    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse device uplink"""
        pass

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode downlink - override in subclasses"""
        return b""

    def parse_chirpstack_uplink(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract common ChirpStack fields"""
        device_info = data.get("deviceInfo", {})
        rx_info = data.get("rxInfo", [{}])[0]

        return {
            "device_eui": device_info.get("devEui", "").lower(),
            "payload": data.get("data", ""),
            "rssi": rx_info.get("rssi"),
            "snr": rx_info.get("snr"),
            "gateway_id": rx_info.get("gatewayId"),
            "timestamp": data.get("time")
        }

# ============================================================
# Browan TABS Motion Sensor Handler
# ============================================================

class BrowanTabsHandler(BaseDeviceHandler):
    """
    Handler for Browan TABS Motion sensors
    COPY YOUR EXACT DECODING LOGIC HERE
    """

    def __init__(self):
        super().__init__()
        # Add your actual Browan device EUI prefixes
        self.device_patterns = [
            "58a0cb",  # Browan prefix
            "0011223344"  # Test devices
        ]

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse Browan TABS uplink"""

        # Extract ChirpStack fields
        parsed = self.parse_chirpstack_uplink(data)

        # Decode payload (COPY FROM YOUR OLD CODE)
        payload_b64 = parsed["payload"]

        try:
            # Decode base64
            payload_bytes = base64.b64decode(payload_b64)

            # Parse Browan format (FROM parking_detector.py lines 45-72)
            occupancy = SpaceState.FREE
            battery = None

            if len(payload_bytes) >= 1:
                status_byte = payload_bytes[0]

                # Bit 0 = occupancy
                if status_byte & 0x01:
                    occupancy = SpaceState.OCCUPIED

                # Byte 1 = battery (if present)
                if len(payload_bytes) >= 2:
                    battery = payload_bytes[1] / 100.0  # Convert to voltage

            return SensorUplink(
                device_eui=parsed["device_eui"],
                timestamp=parsed["timestamp"],
                occupancy_state=occupancy,
                battery=battery,
                rssi=parsed["rssi"],
                snr=parsed["snr"],
                gateway_id=parsed["gateway_id"],
                raw_payload=payload_b64
            )

        except Exception as e:
            logger.error(f"Failed to parse Browan payload: {e}")

            # Return minimal data
            return SensorUplink(
                device_eui=parsed["device_eui"],
                timestamp=parsed["timestamp"],
                rssi=parsed["rssi"],
                snr=parsed["snr"],
                raw_payload=payload_b64
            )

# ============================================================
# Heltec Display Handler
# ============================================================

class HeltecDisplayHandler(BaseDeviceHandler):
    """Handler for Heltec WiFi LoRa displays"""

    def __init__(self):
        super().__init__()
        self.device_patterns = [
            "70b3d57ed006",  # Heltec prefix
        ]

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Heltec displays don't send occupancy data"""
        parsed = self.parse_chirpstack_uplink(data)

        return SensorUplink(
            device_eui=parsed["device_eui"],
            timestamp=parsed["timestamp"],
            rssi=parsed["rssi"],
            snr=parsed["snr"],
            raw_payload=parsed.get("payload")
        )

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode display command"""

        if command == "set_color":
            state = params.get("state", "FREE")
            color_hex = get_display_color(state)
            return bytes.fromhex(color_hex)

        elif command == "set_rgb":
            r = params.get("r", 0)
            g = params.get("g", 0)
            b = params.get("b", 0)
            return bytes([r, g, b])

        return b""

    def get_color_for_state(self, state: SpaceState) -> bytes:
        """Get color bytes for parking state"""
        color_hex = get_display_color(state.value)
        return bytes.fromhex(color_hex)

# ============================================================
# Kuando Busylight Handler
# ============================================================

class KuandoBusylightHandler(BaseDeviceHandler):
    """
    Handler for Kuando Busylight devices
    COPY FROM YOUR BUSYLIGHT INTEGRATION
    """

    def __init__(self):
        super().__init__()
        self.device_patterns = [
            "202020",  # Kuando prefix
        ]

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Kuando devices don't send uplink data"""
        parsed = self.parse_chirpstack_uplink(data)

        return SensorUplink(
            device_eui=parsed["device_eui"],
            timestamp=parsed["timestamp"],
            rssi=parsed["rssi"],
            snr=parsed["snr"],
            raw_payload=parsed.get("payload")
        )

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """
        Encode Kuando Busylight command
        Format: [Cmd, R, G, B, Options, AutoUplink]
        """

        if command == "set_color":
            state = params.get("state", "FREE")

            # Color mapping for Kuando (FROM BUSYLIGHT_INTEGRATION_GUIDE.md)
            colors = {
                "FREE": (0, 255, 0),      # Green
                "OCCUPIED": (255, 0, 0),   # Red
                "RESERVED": (255, 255, 0), # Yellow
                "MAINTENANCE": (255, 165, 0) # Orange
            }

            r, g, b = colors.get(state, (0, 0, 255))  # Blue for unknown

            # Kuando command format with automatic uplink
            # 6th byte (0x01) triggers immediate uplink response (works on all FW versions)
            # This enables downlink verification by getting immediate feedback
            return bytes([
                0x00,  # Command byte
                r,     # Red
                g,     # Green
                b,     # Blue
                0x00,  # Options (no flash, no dim)
                0x01   # Auto-uplink (triggers immediate uplink response with device status)
            ])

        return b""

# ============================================================
# Device Handler Registry
# ============================================================

class DeviceHandlerRegistry:
    """Registry for device handlers"""

    def __init__(self):
        self.handlers: List[BaseDeviceHandler] = []
        self._device_cache: Dict[str, BaseDeviceHandler] = {}

    def register(self, handler: BaseDeviceHandler):
        """Register a device handler"""
        self.handlers.append(handler)
        logger.info(f"Registered handler: {handler.__class__.__name__}")

    def get_handler(self, device_eui: str) -> Optional[BaseDeviceHandler]:
        """Get handler for device"""

        # Check cache
        if device_eui in self._device_cache:
            return self._device_cache[device_eui]

        # Find handler
        for handler in self.handlers:
            if handler.can_handle(device_eui):
                self._device_cache[device_eui] = handler
                return handler

        logger.warning(f"No handler found for device {device_eui}")
        return None

    def get_handler_by_class(self, handler_class: str) -> Optional[BaseDeviceHandler]:
        """Get handler by class name"""
        for handler in self.handlers:
            if handler.__class__.__name__ == handler_class:
                return handler
        return None

    def auto_register(self):
        """Auto-register all built-in handlers"""
        self.register(BrowanTabsHandler())
        self.register(HeltecDisplayHandler())
        self.register(KuandoBusylightHandler())
        logger.info(f"Auto-registered {len(self.handlers)} handlers")

    def list_handlers(self) -> List[str]:
        """List registered handler names"""
        return [h.__class__.__name__ for h in self.handlers]

# ============================================================
# Generic ChirpStack Parser (Fallback)
# ============================================================

def parse_chirpstack_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic ChirpStack webhook parser
    COPY FROM services/ingest/app/parsers/chirpstack_parser.py
    """
    device_info = data.get("deviceInfo", {})
    rx_info = data.get("rxInfo", [{}])[0]
    tx_info = data.get("txInfo", {})

    return {
        "device_eui": device_info.get("devEui", "").lower(),
        "device_name": device_info.get("deviceName"),
        "application_id": device_info.get("applicationId"),
        "frequency": tx_info.get("frequency"),
        "dr": tx_info.get("dr"),
        "fport": data.get("fPort"),
        "fcnt": data.get("fCnt"),
        "payload": data.get("data", ""),
        "rssi": rx_info.get("rssi"),
        "snr": rx_info.get("snr"),
        "gateway_id": rx_info.get("gatewayId", "").lower(),
        "timestamp": data.get("time")
    }
