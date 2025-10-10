# merryiot_ms10.py – Version: 0.2.1 – 2025-07-23 14:25 UTC
# Changelog:
# - Corrected temperature parsing using little-endian signed int16
# - Canonical unpacker pattern: accepts bytes or memoryview
# - Field-by-field decoding of MS10 motion sensor status frame

def unpack(payload, fport: int) -> dict:
    if fport == 122:
        return unpack_status(payload)
    elif fport == 204:
        return unpack_config_response(payload)
    else:
        raise ValueError(f"Unexpected fport: {fport}")

def unpack_status(payload):
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 10:
        raise ValueError(f"Unexpected payload length for status: {len(b)} bytes, expected 10")

    status = b[0]
    battery = b[1]
    temp_raw = int.from_bytes(b[2:4], 'little', signed=True)
    humidity = b[4]
    time = int.from_bytes(b[5:7], 'little')
    count = int.from_bytes(b[7:10], 'little')  # 3-byte event count

    occupied = bool(status & 0x01)
    button_pressed = bool(status & 0x02)
    tamper_detected = bool(status & 0x04)

    battery_voltage = (21 + (battery & 0x0F)) / 10
    temp_c = temp_raw / 10.0
    humidity_pct = humidity & 0x7F

    return {
        "occupied": occupied,
        "button_pressed": button_pressed,
        "tamper_detected": tamper_detected,
        "battery_voltage": battery_voltage,
        "temperature": temp_c,
        "humidity": humidity_pct,
        "time_since_last_event": time,
        "event_count": count
    }

def unpack_config_response(payload):
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 18:
        raise ValueError(f"Unexpected payload length for config response: {len(b)} bytes, expected 18")

    keepalive_interval = int.from_bytes(b[1:3], 'little')
    occupied_interval = int.from_bytes(b[4:6], 'little')
    free_time = b[7]
    trigger_count = int.from_bytes(b[9:11], 'little')
    pir_config = int.from_bytes(b[12:16], 'little')
    tamper_enabled = bool(b[17] & 0x01)

    return {
        "keepalive_interval": keepalive_interval,
        "occupied_interval": occupied_interval,
        "free_detection_time": free_time,
        "trigger_count": trigger_count,
        "pir_config": pir_config,
        "tamper_enabled": tamper_enabled
    }