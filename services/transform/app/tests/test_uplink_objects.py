# test_uplink_objects.py
# Version: 0.1.0 - 2025-07-21 19:05 UTC
# Purpose: Test uplink object type and field availability

from database.connections import get_sync_db_session
from constants.enrichment_steps import Step, Status
from logging_helpers.query_latest_logs import find_uplinks_by_latest_log

def run():
    db_gen = get_sync_db_session()
    db = next(db_gen)

    try:
        uplinks = find_uplinks_by_latest_log(db, Step.UNPACKING_INIT, Status.READY)
        print(f"🔍 Retrieved {len(uplinks)} uplinks")

        for i, uplink in enumerate(uplinks[:3]):
            print(f"\n--- Uplink {i+1} ---")
            print(f"Type: {type(uplink)}")
            print(f"Fields: {dir(uplink)}")
            print(f"uplink.__dict__: {uplink.__dict__}")
    finally:
        db_gen.close()

if __name__ == "__main__":
    run()
