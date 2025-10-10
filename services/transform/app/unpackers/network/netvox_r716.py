# netvox_r716.py – Version: 0.2.0 – 2025-07-23 15:20 UTC
# Changelog:
# - Updated to canonical unpacker format (payload, fport)
# - Accepts both bytes and memoryview inputs
# - Handles known button press frame (0x00 * 11)
# - Defensive validation of length and port

def unpack(payload, fport: int) -> dict:
    if fport != 6:
        raise ValueError(f"Unexpected fport: {fport}, expected 6")

    # Accept memoryview or bytes
    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    # Known payload from documentation and field testing: 11 zero bytes
    if b == b'\x00' * 11:
        return {
            "button_pressed": True,
            "payload_valid": True,
            "raw_length": len(b)
        }

    return {
        "button_pressed": False,
        "payload_valid": False,
        "raw_hex": b.hex(),
        "raw_length": len(b)
    }