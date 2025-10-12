# kuando_busylight.py - Version: 1.0.0 - 2025-10-12
# Kuando Busylight display device unpacker
# Handles fPort 15 (status/heartbeat messages)
# Based on documentation in BUSYLIGHT_uplink_decoder.md

def unpack(payload, fport: int) -> dict:
    """
    Unpack Kuando Busylight uplink payload

    Args:
        payload: Raw payload bytes (typically empty for fPort 15)
        fport: LoRaWAN fPort (15 for status messages)

    Returns:
        dict: Decoded payload data
    """
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if fport == 15:
        return unpack_status(b)
    else:
        raise ValueError(f"Unexpected fport: {fport}, expected 15")


def unpack_status(b: bytes) -> dict:
    """
    Unpack fPort 15 status/heartbeat message

    Kuando Busylight Class C devices send periodic status uplinks on fPort 15.
    These uplinks are typically empty (0 bytes) and serve as heartbeats.
    
    However, ChirpStack may decode the uplink metadata into JSON with device status:
    - RSSI/SNR: Signal quality
    - lastcolor_*: Current displayed color (RGB + timing)
    - messages_received: Downlinks received successfully  
    - messages_send: Uplinks transmitted
    - hw_rev/sw_rev: Hardware and software versions
    - adr_state: ADR state

    Args:
        b: Payload bytes (typically empty for fPort 15)

    Returns:
        dict: Status information
    """
    # fPort 15 uplinks are typically empty (0 bytes) - just heartbeats
    # The actual device status is in the uplink metadata decoded by ChirpStack
    if len(b) == 0:
        return {
            "message_type": "heartbeat",
            "device_online": True,
            "description": "Kuando Busylight status uplink (device online)",
            "note": "Device status (color, signal quality) available in uplink_metadata"
        }

    # If there's payload data, it might be a future firmware version
    # or a specific status response
    else:
        return {
            "message_type": "unknown_payload",
            "device_online": True,
            "payload_length": len(b),
            "payload_hex": b.hex().upper(),
            "description": "Kuando Busylight uplink with unexpected payload data"
        }
