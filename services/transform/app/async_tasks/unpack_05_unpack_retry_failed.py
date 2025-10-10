# async_tasks/unpack_05_unpack_retry_failed.py
# Version: 0.5.8 – 2025-07-23 10:45 UTC
# Changelog:
# - Renamed from run_05_unpack_retry_failed.py
# - Canonical unpacking pipeline header added

"""
📦 UNPACKING PIPELINE STAGE
Retries failed unpacking attempts from previous stages.

Sequence:
- unpack_05_unpack_retry_failed.py
"""

from database.connections import get_sync_db_session
from constants.enrichment_steps import Step, Status
from logging_helpers.enrichment_logger import log_step
from unpackers.registry import get_unpacker
from async_tasks.unpack_utils import get_failed_unpacks, safe_unpack_and_catch
from sqlalchemy.orm import Session
from datetime import datetime

def run():
    db_gen = get_sync_db_session()
    db: Session = next(db_gen)

    try:
        results = get_failed_unpacks(db)
        if not results:
            print("✅ No failed unpacked uplinks to retry.")
            return

        print(f"🔁 Retrying unpack for {len(results)} uplinks...")
        retried, failed = 0, 0

        for uplink, device_type in results:
            try:
                print(f"\n🧪 Uplink UUID: {uplink.uplink_uuid}")
                print(f"🧪 DevEUI={uplink.deveui}, FPort={uplink.fport}")
                print(f"🧪 Raw payload (type={type(uplink.payload)}): {uplink.payload}")

                payload_bytes = uplink.payload
                if isinstance(payload_bytes, memoryview):
                    print("🔁 Converting memoryview to bytes")
                    payload_bytes = payload_bytes.tobytes()

                print(f"🧪 Payload HEX: {payload_bytes.hex()}")
                uplink.payload = payload_bytes  # ensure bytes stored for decoding

                unpacker_func = get_unpacker(device_type.unpacker)
                if not unpacker_func:
                    raise ValueError(f"Unpacker '{device_type.unpacker}' not found in registry")

                decoded = safe_unpack_and_catch(uplink.deveui, uplink, unpacker_func)
                if not isinstance(decoded, dict):
                    decoded = {"status": "not_decoded"}

                uplink.payload_decoded = decoded
                uplink.updated_at = datetime.utcnow()
                db.merge(uplink)

                log_step(
                    db,
                    uplink.uplink_uuid,
                    Step.UNPACKING,
                    Status.SUCCESS,
                    f"Retry unpacked by '{device_type.unpacker}'"
                )

                print(f"✅ Retried: {uplink.uplink_uuid} ({uplink.deveui}) → {decoded}")
                retried += 1

            except Exception as e:
                log_step(
                    db,
                    uplink.uplink_uuid,
                    Step.UNPACKING,
                    Status.FAIL,
                    f"{str(e)} | DevEUI={uplink.deveui}, Port={uplink.fport}, Len={len(uplink.payload or b'')}"
                )
                print(f"❌ Retry failed: {uplink.uplink_uuid} (DevEUI={uplink.deveui}, Port={uplink.fport}, Len={len(uplink.payload or b'')}) → {type(e).__name__}: {str(e)}")
                failed += 1

        db.commit()
        print(f"\n📊 Summary: 🔁 {retried} retried, ❌ {failed} still failing")

    finally:
        db_gen.close()

if __name__ == "__main__":
    run()