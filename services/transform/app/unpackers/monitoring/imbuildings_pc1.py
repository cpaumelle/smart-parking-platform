# imbuildings_pc1.py
# Version: 0.3.0 - 2025-07-22 13:58 UTC
# Changelog:
# - Fully rewritten unpacker for Type 0x02 / Variant 0x06 based on official IMBUILDINGS spec
# - Strict 23-byte payload check
# - Fields: DevEUI, battery voltage, counters, status flags, payload counter

def unpack(payload, fport):
    if not isinstance(payload, (bytes, memoryview)):
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    b = bytes(payload)
    if len(b) != 23:
        raise ValueError(f"Expected 23-byte payload for Type 2 Variant 6, got {len(b)} bytes")

    if b[0] != 0x02 or b[1] != 0x06:
        raise ValueError(f"Unsupported payload type/variant: {b[0]:02x}/{b[1]:02x}")

    # Start unpacking
    deveui = b[2:10].hex()
    status = b[10]
    battery_voltage_mv = int.from_bytes(b[11:13], 'big')  # mV
    battery_voltage_v = round(battery_voltage_mv / 1000, 3)

    counter_a = int.from_bytes(b[13:15], 'big')
    counter_b = int.from_bytes(b[15:17], 'big')
    status_flags = b[17]
    total_counter_a = int.from_bytes(b[18:20], 'big')
    total_counter_b = int.from_bytes(b[20:22], 'big')
    payload_counter = b[22]

    return {
        "dev_eui": deveui,
        "status_byte": status,
        "battery_voltage": battery_voltage_v,
        "counter_a": counter_a,
        "counter_b": counter_b,
        "total_counter_a": total_counter_a,
        "total_counter_b": total_counter_b,
        "payload_counter": payload_counter,
        "status_flags_raw": f"{status_flags:08b}",
    }