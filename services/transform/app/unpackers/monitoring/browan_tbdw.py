# browan_tbdw.py - Version: 0.2.0 - 2025-07-23 13:50 UTC
# Changelog:
# - Rewritten using canonical unpacking structure
# - Accepts bytes or memoryview safely
# - Validates port 100 and length 8
# - Correctly decodes open/closed status, battery, temp, and event counters

def unpack(payload: bytes, fport: int) -> dict:
    if fport != 100:
        raise ValueError(f"Unexpected port {fport}, expected 100")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 8:
        raise ValueError(f"Payload length is {len(b)} bytes, expected 8")

    status_byte = b[0]
    battery_byte = b[1]
    pcb_temp_byte = b[2]
    time_minutes = int.from_bytes(b[3:5], byteorder="little")
    event_count = int.from_bytes(b[5:8], byteorder="little")

    open_shut_status = bool(status_byte & 0x01)
    battery_voltage = (25 + (battery_byte & 0x0F)) / 10
    temperature_c = (pcb_temp_byte & 0x7F) - 32

    return {
        "status": 1 if open_shut_status else 0,
        "open_shut": "open" if open_shut_status else "closed",
        "battery_voltage": battery_voltage,
        "pcb_temperature": temperature_c,
        "time_since_last_event": time_minutes,
        "event_count": event_count
    }