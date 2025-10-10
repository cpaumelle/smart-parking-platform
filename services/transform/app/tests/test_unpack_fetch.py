# async_tasks/test_unpack_fetch.py
# Version: 0.1.0 - 2025-07-21
# Purpose: Debug get_uplinks_ready_for_unpacking()

from database.connections import get_sync_db_session
from async_tasks.unpack_utils import get_uplinks_ready_for_unpacking

if __name__ == "__main__":
    db_gen = get_sync_db_session()
    db = next(db_gen)

    results = get_uplinks_ready_for_unpacking(db)

    print(f"🔍 Found {len(results)} uplinks ready for unpacking\n")

    for uplink, device_type in results[:5]:
        print(f"DevEUI: {uplink.deveui}")
        print(f"FPort: {uplink.fport}")
        print(f"Payload: {uplink.payload}")
        print(f"DeviceType: {device_type.name} → {device_type.unpacker}")
        print("—" * 40)

    db_gen.close()
