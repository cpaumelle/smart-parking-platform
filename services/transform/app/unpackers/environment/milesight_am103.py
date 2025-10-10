# milesight_am103.py - Version: 0.2.1 - 2025-07-22 16:55 UTC
# Changelog:
# - Fixed temperature and CO₂ decoding: uses 'little' byte order (not 'big')
# - Accepts bytes or memoryview
# - Parses TLV-encoded telemetry and FF-prefixed metadata frames
# - Returns temperature, humidity, battery %, and CO₂ ppm

def unpack(payload, fport: int) -> dict:
    if fport != 85:
        raise ValueError(f"Unexpected fport: {fport}, expected 85")

    if isinstance(payload, memoryview):
        b = payload.tobytes()
    elif isinstance(payload, bytes):
        b = payload
    else:
        raise TypeError(f"Expected bytes or memoryview, got {type(payload)}")

    if not b:
        return {"status": "not_decoded", "error": "empty payload"}

    # Fallback for basic metadata frames
    if b[0] == 0xFF:
        return unpack_basic_info(b)

    result = {}
    index = 0
    while index + 1 < len(b):
        channel = b[index]
        data_type = b[index + 1]

        try:
            size = data_size(channel, data_type)
            data = b[index + 2: index + 2 + size]

            if (channel, data_type) == (0x01, 0x75):  # Battery (1 byte)
                result['battery_raw'] = data[0]
                result['battery_pct'] = round((data[0] / 254) * 100)

            elif (channel, data_type) == (0x03, 0x67):  # Temperature (2 bytes, little endian)
                temp = int.from_bytes(data, 'little', signed=True)
                result['temperature'] = temp / 10.0

            elif (channel, data_type) == (0x04, 0x68):  # Humidity (1 byte)
                result['humidity'] = data[0] / 2.0

            elif (channel, data_type) == (0x07, 0x7D):  # CO₂ (2 bytes, little endian)
                result['co2_ppm'] = int.from_bytes(data, 'little')

            else:
                result[f"unknown_{channel:02X}_{data_type:02X}"] = data.hex()

            index += 2 + size

        except Exception as e:
            result[f"error_at_index_{index}"] = str(e)
            break

    return result


def data_size(channel, data_type):
    if (channel, data_type) == (0x01, 0x75): return 1  # Battery
    if (channel, data_type) == (0x03, 0x67): return 2  # Temperature
    if (channel, data_type) == (0x04, 0x68): return 1  # Humidity
    if (channel, data_type) == (0x07, 0x7D): return 2  # CO₂
    raise ValueError(f"Unknown channel/type ({channel:#x}, {data_type:#x})")


def unpack_basic_info(b):
    result = {}
    index = 1  # Skip 0xFF prefix
    while index + 4 <= len(b):
        try:
            channel = b[index]
            data_type = b[index + 1]
            size = b[index + 2]
            data = b[index + 3:index + 3 + size]

            if (channel, data_type) == (0xFF, 0x01):
                result["protocol_version"] = data[0]
            elif (channel, data_type) == (0xFF, 0x09):
                result["hardware_version"] = f"{data[0]}.{data[1]}"
            elif (channel, data_type) == (0xFF, 0x0A):
                result["software_version"] = f"{data[0]}.{data[1]}"
            elif (channel, data_type) == (0xFF, 0x0F):
                dt = data[0]
                result["device_type"] = ["Class A", "Class B", "Class C"][dt] if dt <= 2 else f"Unknown ({dt})"
            elif (channel, data_type) == (0xFF, 0x16):
                result["device_sn"] = data.hex()
            elif (channel, data_type) == (0xFF, 0x18):
                val = data[0]
                result["temp_sensor"] = bool(val & 0x01)
                result["hum_sensor"] = bool(val & 0x02)
                result["co2_sensor"] = bool(val & 0x10)
            else:
                result[f"unknown_basic_{channel:02X}_{data_type:02X}"] = data.hex()

            index += 3 + size

        except Exception as e:
            result[f"error_basic_at_index_{index}"] = str(e)
            break

    return result