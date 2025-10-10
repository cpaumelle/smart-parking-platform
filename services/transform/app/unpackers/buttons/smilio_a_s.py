# smilio_a_s.py - Version: 0.3.0 - 2025-07-23 12:15 UTC
# Changelog:
# - Canonicalized with memoryview/bytes handling
# - Preserved full frame decoding for keep-alive, normal, pulse, hall-effect, and code frames
# - Added comments for maintainability

def unpack(payload, fport: int) -> dict:
    if fport != 2:
        raise ValueError(f"Unexpected port {fport}, expected 2")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if len(b) < 2:
        raise ValueError(f"Payload too short: {len(b)} bytes")

    frame_type = b[0]

    # Frame type 0x01: Keep Alive (6 bytes)
    if frame_type == 0x01:
        if len(b) != 6:
            raise ValueError(f"Unexpected payload length for keep-alive: {len(b)} bytes, expected 6")
        battery_idle_mV = int.from_bytes(b[1:3], 'big')
        battery_tx_mV = int.from_bytes(b[3:5], 'big')
        terminator = b[5]
        if terminator != 0x64:
            raise ValueError(f"Unexpected terminator byte: 0x{terminator:02X}, expected 0x64")
        return {
            "frame_type": "keep_alive",
            "battery_idle_mV": battery_idle_mV,
            "battery_tx_mV": battery_tx_mV,
            "terminator": terminator
        }

    # Frame type 0x02: Normal (button press counters)
    elif frame_type == 0x02:
        if len(b) != 11:
            raise ValueError(f"Unexpected payload length for normal: {len(b)} bytes, expected 11")
        return {
            "frame_type": "normal",
            "counter_1": int.from_bytes(b[1:3], 'big'),
            "counter_2": int.from_bytes(b[3:5], 'big'),
            "counter_3": int.from_bytes(b[5:7], 'big'),
            "counter_4": int.from_bytes(b[7:9], 'big'),
            "counter_5": int.from_bytes(b[9:11], 'big')
        }

    # Frame type 0x03: Hall Effect (magnet detection)
    elif frame_type == 0x03:
        if len(b) != 12:
            raise ValueError(f"Unexpected payload length for hall effect: {len(b)} bytes, expected 12")
        return {
            "frame_type": "hall_effect",
            "counter_1": int.from_bytes(b[1:3], 'big'),
            "counter_2": int.from_bytes(b[3:5], 'big'),
            "counter_3": int.from_bytes(b[5:7], 'big'),
            "counter_4": int.from_bytes(b[7:9], 'big'),
            "counter_5": int.from_bytes(b[9:11], 'big')
        }

    # Frame type 0x40: Pulse mode (binary on/off states)
    elif frame_type == 0x40:
        if len(b) != 12:
            raise ValueError(f"Unexpected payload length for pulse: {len(b)} bytes, expected 12")
        return {
            "frame_type": "pulse",
            "button_1": bool(int.from_bytes(b[1:3], 'big')),
            "button_2": bool(int.from_bytes(b[3:5], 'big')),
            "button_3": bool(int.from_bytes(b[5:7], 'big')),
            "button_4": bool(int.from_bytes(b[7:9], 'big')),
            "button_5": bool(int.from_bytes(b[9:11], 'big'))
        }

    # Frame type 0x10–0x1F: Code mode (ack + 2 x 4-byte codes)
    elif frame_type & 0xF0 == 0x10:
        if len(b) != 15:
            raise ValueError(f"Unexpected payload length for code mode: {len(b)} bytes, expected 15")
        ack_1 = (frame_type & 0x0C) >> 2
        ack_2 = frame_type & 0x03
        return {
            "frame_type": "code",
            "ack_1": ack_1,
            "ack_2": ack_2,
            "time_last": int.from_bytes(b[1:3], 'big'),
            "time_tx": int.from_bytes(b[3:5], 'big'),
            "code_2": int.from_bytes(b[5:9], 'big'),
            "code_1": int.from_bytes(b[9:13], 'big')
        }

    else:
        raise ValueError(f"Unexpected frame type: 0x{frame_type:02X}")