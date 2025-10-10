# tests/test_am103_problematic_payload.py
# Version: 0.1.0 - 2025-07-22 17:35 UTC
# Tests unpacker on real-world payload that previously unpacked incorrectly

from unpackers.environment import milesight_am103

def main():
    # Real-world payload that previously gave unrealistic temperature (691.3°C)
    hex_payload = "01756403671b0104685c077d3105"
    fport = 85

    print("\n🔬 Test: Real-world Milesight AM103 payload previously misparsed")
    print(f"🔢 HEX: {hex_payload}")
    print(f"📦 FPort: {fport}")

    payload = bytes.fromhex(hex_payload)

    try:
        decoded = milesight_am103.unpack(payload, fport)
        print("✅ Decoded:")
        for k, v in decoded.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"❌ Error during unpacking: {e}")

if __name__ == "__main__":
    main()
