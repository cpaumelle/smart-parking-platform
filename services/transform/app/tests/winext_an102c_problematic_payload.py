# tests/winext_an102c_problematic_payload.py
# Version: 0.1.0 – 2025-07-23 14:50 UTC
# Test case for Winext AN-102C payload that failed previously (FPort=46)

from unpackers.monitoring import winext_an102c

hex_payload = "010100080e003b0000001f"
fport = 46
payload_bytes = bytes.fromhex(hex_payload)

print("🔬 Test: Real-world Winext AN-102C payload previously misparsed")
print(f"🔢 HEX: {hex_payload}")
print(f"📦 FPort: {fport}")

try:
    decoded = winext_an102c.unpack(payload_bytes, fport)
    print("✅ Decoded:")
    for k, v in decoded.items():
        print(f"  {k}: {v}")
except Exception as e:
    print(f"❌ Failed to decode: {e}")
