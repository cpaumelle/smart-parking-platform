# browan_tbhh100.py - Version: 0.2.0 - 2025-07-23 08:05 UTC
# Changelog:
# - Accepts bytes or memoryview safely
# - Confirmed unpacking -21°C for freezer TBHH100
# - Supports ports 102, 103, 107

def unpack(payload: bytes, fport: int) -> dict:
    if fport not in [102, 103, 107]:
        raise ValueError(f"Unexpected port {fport}, expected 102, 103, or 107")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) < 4:
        raise ValueError(f"Payload too short: {len(b)} bytes, expected at least 4")

    battery = b[1]
    temp_raw = b[2]
    humidity_raw = b[3]

    battery_voltage = (25 + (battery & 0x0F)) / 10
    temperature_c = (temp_raw & 0x7F) - 32
    humidity_pct = humidity_raw & 0x7F
    humidity_error = humidity_pct == 127

    return {
        "battery_voltage": battery_voltage,
        "temperature": temperature_c,
        "humidity": humidity_pct,
        "humidity_error": humidity_error
    }
