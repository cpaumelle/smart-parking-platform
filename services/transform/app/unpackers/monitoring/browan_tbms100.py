# browan_tbms100.py - Version: 0.2.0 - 2025-07-23 14:00 UTC
# Changelog:
# - Rewritten to follow canonical unpacker structure
# - Accepts bytes or memoryview safely
# - Handles FPort 102 (Status) and 204 (Config Response)
# - Validates payload lengths and performs correct decoding

def unpack(payload, fport: int) -> dict:
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if fport == 102:
        return unpack_status(b)
    elif fport == 204:
        return unpack_config_response(b)
    else:
        raise ValueError(f"Unexpected fport: {fport}, expected 102 or 204")


def unpack_status(b: bytes) -> dict:
    if len(b) != 8:
        raise ValueError(f"Unexpected payload length for status: {len(b)} bytes, expected 8")

    status = b[0]
    battery = b[1]
    temp_raw = b[2]
    time_since = int.from_bytes(b[3:5], byteorder="little")
    count = int.from_bytes(b[5:8], byteorder="little")

    occupied = bool(status & 0x01)
    battery_voltage = (25 + (battery & 0x0F)) / 10
    temperature_c = (temp_raw & 0x7F) - 32

    return {
        "occupied": occupied,
        "battery_voltage": battery_voltage,
        "pcb_temperature": temperature_c,
        "time_since_last_event": time_since,
        "event_count": count
    }


def unpack_config_response(b: bytes) -> dict:
    if len(b) != 16:
        raise ValueError(f"Unexpected payload length for config response: {len(b)} bytes, expected 16")

    reporting_interval = int.from_bytes(b[1:3], byteorder="little")
    occupied_interval = int.from_bytes(b[3:5], byteorder="little")
    free_time = b[6]
    trigger_count = int.from_bytes(b[8:10], byteorder="little")
    pir_config = int.from_bytes(b[11:15], byteorder="little")

    return {
        "reporting_interval": reporting_interval,
        "occupied_interval": occupied_interval,
        "free_detection_time": free_time,
        "trigger_count": trigger_count,
        "pir_config": pir_config
    }