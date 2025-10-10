# async_tasks/unpack_03_ready_for_unpacking.py
# Version: 0.5.1 – 2025-07-23 10:45 UTC
# Changelog:
# - Renamed from run_03_ready_for_unpacking.py
# - Canonical unpacking header added

"""
📦 UNPACKING PIPELINE STAGE
Marks uplinks as READY_FOR_UNPACKING if their last log was enrichment SUCCESS.

Sequence:
- unpack_03_ready_for_unpacking.py
Triggers:
- unpack_04_unpack_ready.py
- unpack_05_unpack_retry_failed.py
"""

from database.connections import get_sync_db_session
from constants.enrichment_steps import Step, Status
from logging_helpers.enrichment_logger import log_step
from logging_helpers.query_latest_logs import find_uplinks_by_latest_log

def run():
    db_gen = get_sync_db_session()
    db = next(db_gen)

    try:
        uplinks = find_uplinks_by_latest_log(db, Step.CONTEXT_ENRICHMENT, Status.SUCCESS)

        if not uplinks:
            print("✅ No enriched uplinks to mark for unpacking.")
            return

        print(f"📦 Marking {len(uplinks)} uplinks as ready for unpacking...")

        marked = 0

        for uplink in uplinks:
            log_step(
                db,
                uplink.uplink_uuid,
                Step.UNPACKING_INIT,
                Status.READY,
                "Enrichment complete, ready to unpack"
            )
            print(f"📘 Ready: {uplink.uplink_uuid} ({uplink.deveui})")
            marked += 1

        db.commit()
        print(f"\n📊 Summary: 📦 {marked} marked as ready for unpacking")

    finally:
        db_gen.close()

if __name__ == "__main__":
    run()
