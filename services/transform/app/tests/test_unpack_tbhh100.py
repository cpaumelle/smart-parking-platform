# test_unpack_tbhh100.py
from unpackers.environment import browan_tbhh100

# Simulate DB-provided memoryview (what causes failure)
payload = memoryview(bytes.fromhex("08fa0b4affffffff"))
fport = 103

try:
    print(browan_tbhh100.unpack(payload, fport))
except Exception as e:
    print(f"❌ Error: {e} ({type(payload)})")
