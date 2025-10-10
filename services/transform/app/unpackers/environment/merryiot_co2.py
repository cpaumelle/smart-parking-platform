# merryiot_cd10.py - Version: 0.2.0 - 2025-07-22 13:20 UTC
# Changelog:
# - Supports CO₂ sensor uplinks on port 127
# - Parses 7-byte payload: status, battery, temp, RH, CO₂
# - Handles bytes or memoryview input safely

def unpack(payload: bytes, fport: int) -> dict:
    if fport != 127:
        raise ValueError(f"Unexpected fport: {fport}, expected 127")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) != 7:
        raise ValueError(f"Unexpected payload length: {len(b)} bytes, expected 7")

    # Byte 0: Status bits
    status = b[0]
    trigger_event = bool(status & 0x01)
    button_pressed = bool(status & 0x02)
    co2_high = bool(status & 0x10)
    co2_calibration = bool(status & 0x20)

    # Byte 1: Battery
    battery_raw = b[1] & 0x0F
    battery_voltage = (21 + battery_raw) / 10.0

    # Bytes 2-3: Temperature (signed, little-endian)
    temp_raw = int.from_bytes(b[2:4], "little", signed=True)
    temperature_c = temp_raw / 10.0

    # Byte 4: Humidity (7 bits)
    humidity = b[4] & 0x7F

    # Bytes 5-6: CO₂ ppm (unsigned, little-endian)
    co2_ppm = int.from_bytes(b[5:7], "little")

    return {
        "trigger_event": trigger_event,
        "button_pressed": button_pressed,
        "co2_high_alarm": co2_high,
        "co2_calibration_flag": co2_calibration,
        "battery_voltage": battery_voltage,
        "temperature": temperature_c,
        "humidity": humidity,
        "co2_ppm": co2_ppm
    }