# winext_an102c.py – Version: 0.3.0 – 2025-07-23 14:45 UTC
# Changelog:
# - Fully rewritten to align with official spec (uplinks on FPort 46)
# - Supports heartbeat (0x01), self-test (0x02), and alarm (0x03) frames
# - Accepts memoryview or bytes input
# - All values decoded according to Winext 2019.7.23 manual

def unpack(payload, fport: int) -> dict:
    if fport != 46:
        raise ValueError(f"Unexpected port {fport}, expected 46")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) < 2:
        raise ValueError(f"Payload too short: {len(b)} bytes")

    sensor_type = b[0]
    frame_type = b[1]

    if sensor_type != 0x01:
        raise ValueError(f"Unexpected sensor type: 0x{sensor_type:02X}, expected 0x01")

    if frame_type == 0x01:  # Heartbeat
        if len(b) != 11:
            raise ValueError(f"Unexpected heartbeat length: {len(b)} bytes, expected 11")
        return {
            "frame_type": "heartbeat",
            "smoke_concentration": b[2] / 100,
            "temperature": int.from_bytes(b[3:5], 'big', signed=True) / 100,
            "humidity": b[5],
            "battery_percent": b[6],
            **parse_alarm_flags(b[7]),
            **parse_fault_flags(b[8]),
            "pollution": b[9],
            "voltage": b[10] / 10
        }

    elif frame_type == 0x02:  # Self-test
        if len(b) != 3:
            raise ValueError(f"Unexpected self-test length: {len(b)} bytes, expected 3")
        return {
            "frame_type": "self_test",
            **parse_self_test_flags(b[2])
        }

    elif frame_type == 0x03:  # Alarm
        if len(b) != 10:
            raise ValueError(f"Unexpected alarm length: {len(b)} bytes, expected 10")
        return {
            "frame_type": "alarm",
            **parse_alarm_flags(b[2]),
            **parse_fault_flags(b[3]),
            "smoke_concentration": b[4] / 100,
            "temperature": int.from_bytes(b[5:7], 'big', signed=True) / 100,
            "humidity": b[7],
            "battery_percent": b[8],
            "pollution": b[9]
        }

    else:
        raise ValueError(f"Unknown frame type: 0x{frame_type:02X}")


# 🧩 Helper: Alarm bitflags
def parse_alarm_flags(byte):
    return {
        "alarm_smoke": bool(byte & 0x01),
        "alarm_temperature": bool(byte & 0x02),
        "alarm_low_battery": bool(byte & 0x04)
    }

# 🧩 Helper: Fault bitflags
def parse_fault_flags(byte):
    return {
        "fault_smoke_sensor": bool(byte & 0x01),
        "fault_temp_rh_sensor": bool(byte & 0x02)
    }

# 🧩 Helper: Self-test bitflags
def parse_self_test_flags(byte):
    return {
        "self_test_active": bool(byte & 0x80),
        "self_test_smoke_sensor_fail": bool(byte & 0x01),
        "self_test_temp_rh_sensor_fail": bool(byte & 0x02)
    }