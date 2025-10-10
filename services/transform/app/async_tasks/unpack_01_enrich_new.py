# 2b-transform-server/app/async_tasks/unpack_01_enrich_new.py
# Version: 0.7.0 – 2025-08-06 16:55 UTC+2
# Changelog:
# - Automatically inserts missing DevEUIs as ORPHAN into device_context
# - Logs ORPHAN insertion in context_enrichment step

"""
📦 UNPACKING PIPELINE STAGE
This script selects NEW uplinks and enriches them with device_type_id only.
Location fields (site, room, zone) are ignored.

Sequence:
- unpack_01_enrich_new.py
- unpack_02_enrich_retry_pending.py
- unpack_03_ready_for_unpacking.py
- unpack_04_unpack_ready.py
- unpack_05_unpack_retry_failed.py
"""

from database.connections import get_sync_db_session
from constants.enrichment_steps import Step, Status
from logging_helpers.enrichment_logger import log_step
from logging_helpers.query_latest_logs import find_uplinks_by_latest_log
from services.gateway_handler import insert_or_update_processed_uplink
from services.device_handler import ensure_device_context_exists
from models import DeviceContext, ProcessedUplink
from datetime import datetime

def run():
    db_gen = get_sync_db_session()
    db = next(db_gen)

    try:
        uplinks = find_uplinks_by_latest_log(db, Step.INGESTION_RECEIVED, Status.NEW)

        if not uplinks:
            print("✅ No new uplinks to enrich.")
            return

        print(f"🚀 Starting enrichment for {len(uplinks)} new uplinks...")

        started, enriched, unresolved = 0, 0, 0

        for uplink in uplinks:
            started += 1
            deveui = uplink.deveui
            gateway_eui = uplink.gateway_eui

            device = db.query(DeviceContext).filter_by(deveui=deveui).first()

            if device and device.device_type_id:
                enriched_uplink = ProcessedUplink(
                    uplink_uuid=uplink.uplink_uuid,
                    deveui=uplink.deveui,
                    timestamp=uplink.timestamp,
                    payload=uplink.payload,
                    fport=uplink.fport,
                    source=uplink.source,
                    uplink_metadata=uplink.uplink_metadata,
                    device_type_id=device.device_type_id,
                    gateway_eui=device.last_gateway or gateway_eui,
                    inserted_at=uplink.inserted_at,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.merge(enriched_uplink)

                insert_or_update_processed_uplink(db=db, uplink=enriched_uplink)

                log_step(db, uplink.uplink_uuid, Step.CONTEXT_ENRICHMENT, Status.SUCCESS, "Initial enrichment complete")
                print(f"✅ Enriched: {uplink.uplink_uuid} ({deveui})")
                enriched += 1
            else:
                # Automatically insert missing device context as ORPHAN
                ensure_device_context_exists(deveui, gateway_eui, db)

                log_step(db, uplink.uplink_uuid, Step.CONTEXT_ENRICHMENT, Status.PENDING, "No matching device context found — ORPHAN inserted")
                print(f"❌ Unresolved: {uplink.uplink_uuid} ({deveui}) → ORPHAN inserted")
                unresolved += 1

        db.commit()
        print(f"\n📊 Enrichment Summary: 🧩 {started} processed, ✅ {enriched} enriched, ❌ {unresolved} unresolved")

    finally:
        db_gen.close()

if __name__ == "__main__":
    run()
