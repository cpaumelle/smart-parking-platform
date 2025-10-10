# browan_tbwl100.py - Version: 0.2.0 - 2025-07-23 14:15 UTC
# Changelog:
# - Uses canonical pattern (like TBHH100)
# - Accepts bytes or memoryview safely
# - Handles FPort 106 (status) and 204 (config)
# - Validates payload lengths and returns unpacked values

def unpack(payload, fport: int) -> dict:
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if fport == 106:
        return unpack_status(b)
    elif fport == 204:
        return unpack_config_response(b)
    else:
        raise ValueError(f"Unexpected fport: {fport}, expected 106 or 204")


def unpack_status(b: bytes) -> dict:
    if len(b) != 5:
        raise ValueError(f"Unexpected payload length for status: {len(b)} bytes, expected 5")

    status = b[0]
    battery = b[1]
    pcb_temp = b[2]
    humidity_raw = b[3]
    env_temp = b[4]

    leak_detected = bool(status & 0x01)
    leak_interrupt = bool(status & 0x10)
    temperature_changed = bool(status & 0x20)
    humidity_changed = bool(status & 0x40)

    battery_voltage = (25 + (battery & 0x0F)) / 10
    pcb_temperature = (pcb_temp & 0x7F) - 32
    environment_temperature = (env_temp & 0x7F) - 32

    humidity = humidity_raw & 0x7F
    humidity_error = humidity_raw == 0x7F

    return {
        "leak_detected": leak_detected,
        "leak_interrupt": leak_interrupt,
        "temperature_changed": temperature_changed,
        "humidity_changed": humidity_changed,
        "battery_voltage": battery_voltage,
        "pcb_temperature": pcb_temperature,
        "humidity": humidity,
        "humidity_error": humidity_error,
        "environment_temperature": environment_temperature
    }


def unpack_config_response(b: bytes) -> dict:
    if len(b) != 10:
        raise ValueError(f"Unexpected payload length for config response: {len(b)} bytes, expected 10")

    keep_alive_interval = int.from_bytes(b[1:3], byteorder="little")
    temp_delta = b[3]
    humidity_delta = b[5]
    detection_interval = int.from_bytes(b[7:9], byteorder="little")

    return {
        "keep_alive_interval": keep_alive_interval,
        "temperature_delta": temp_delta,
        "humidity_delta": humidity_delta,
        "detection_interval": detection_interval
    }