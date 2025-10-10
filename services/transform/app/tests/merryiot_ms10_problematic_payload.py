# merryiot_ms10_problematic_payload.py - Test for known payload issue
# Version: 0.1.0 - 2025-07-23 14:30 UTC

from unpackers.monitoring import merryiot_ms10

payload_hex = "0008fe00340000000000"
fport = 122
payload_bytes = bytes.fromhex(payload_hex)

print("\n🔬 Test: Real-world MerryIoT MS10 payload previously misparsed")
print(f"🔢 HEX: {payload_hex}")
print(f"📦 FPort: {fport}")

decoded = merryiot_ms10.unpack(payload_bytes, fport)

print("✅ Decoded:")
for k, v in decoded.items():
    print(f"  {k}: {v}")
