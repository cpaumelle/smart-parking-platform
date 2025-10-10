from unpackers.monitoring import imbuildings_pc1

print("\n🔬 Test: Real-world imBuildings PC1 payload previously misparsed")
payload_hex = "02060004a30b00fb671300012a0000000082000000008b"
fport = 1
payload_bytes = bytes.fromhex(payload_hex)

print(f"🔢 HEX: {payload_hex}")
print(f"📦 FPort: {fport}")
decoded = imbuildings_pc1.unpack(payload_bytes, fport)

print("✅ Decoded:")
for k, v in decoded.items():
    print(f"  {k}: {v}")
