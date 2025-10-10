# browan_tbhv110.py - Version: 0.2.0 - 2025-07-23 12:45 UTC
# Changelog:
# - Canonicalized for memoryview/bytes safety
# - Preserved full IAQ decoding logic
# - Improved validation, field names, and inline comments

def unpack(payload, fport: int) -> dict:
    if fport == 103:
        return unpack_status(payload)
    elif fport == 204:
        return unpack_config_response(payload)
    else:
        raise ValueError(f"Unexpected fport: {fport}")

def unpack_status(payload) -> dict:
    # Accept bytes or memoryview
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 11:
        raise ValueError(f"Unexpected payload length for status: {len(b)} bytes, expected 11")

    status = b[0]
    battery = b[1]
    pcb_temp = b[2]
    humidity = b[3]
    co2_eq = int.from_bytes(b[4:6], 'big')   # CO₂ equivalent in ppm
    voc = int.from_bytes(b[6:8], 'big')      # VOC level in ppb
    iaq = int.from_bytes(b[8:10], 'big')     # IAQ index
    env_temp = b[10]

    # Flags from status byte
    trigger_event = bool(status & 0x01)
    temp_changed = bool(status & 0x10)
    humidity_changed = bool(status & 0x20)
    iaq_changed = bool(status & 0x40)

    battery_voltage = (25 + (battery & 0x0F)) / 10
    pcb_temp_c = (pcb_temp & 0x7F) - 32
    env_temp_c = (env_temp & 0x7F) - 32
    humidity_pct = humidity & 0x7F

    return {
        "trigger_event": trigger_event,
        "temp_changed": temp_changed,
        "humidity_changed": humidity_changed,
        "iaq_changed": iaq_changed,
        "battery_voltage": battery_voltage,
        "pcb_temperature": pcb_temp_c,
        "humidity": humidity_pct,
        "co2_equivalent": co2_eq,
        "voc": voc,
        "iaq_index": iaq,
        "environment_temperature": env_temp_c
    }

def unpack_config_response(payload) -> dict:
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 8:
        raise ValueError(f"Unexpected payload length for config response: {len(b)} bytes, expected 8")

    keep_alive_interval = b[1] * 5  # in seconds
    temp_delta = b[3]
    humidity_delta = b[5]
    iaq_delta = b[7]

    return {
        "keep_alive_interval": keep_alive_interval,
        "temperature_delta": temp_delta,
        "humidity_delta": humidity_delta,
        "iaq_index_delta": iaq_delta
    }