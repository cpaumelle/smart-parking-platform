# async_tasks/unpack_02_enrich_retry_pending.py
# Version: 0.6.1 – 2025-08-06 15:05 UTC
# Changelog:
# - Adds ensure_device_context_exists for missing DevEUIs
# - Logs ORPHAN insertion to enrichment_logs
# - Aligns logic with unpack_01_enrich_new.py

"""
📦 UNPACKING PIPELINE STAGE
Retries previously PENDING uplinks to enrich with device_type_id only.
Location twinning (site_id, etc.) is not used.

Sequence:
- unpack_01_enrich_new.py
- unpack_02_enrich_retry_pending.py
"""

from database.connections import get_sync_db_session
from constants.enrichment_steps import Step, Status
from logging_helpers.enrichment_logger import log_step
from logging_helpers.query_latest_logs import find_uplinks_by_latest_log
from services.gateway_handler import insert_or_update_processed_uplink
from services.device_handler import ensure_device_context_exists
from models import DeviceContext, ProcessedUplink, Gateway
from datetime import datetime

def ensure_gateway_exists(db, gateway_eui: str, uplink_uuid=None) -> bool:
    if not gateway_eui:
        return False

    print(f"🔍 Checking gateway: {gateway_eui} ...", end=" ")
    existing = db.query(Gateway).filter_by(gw_eui=gateway_eui).first()
    if existing:
        print("✅ already exists")
        return False

    gateway = Gateway(
        gw_eui=gateway_eui,
        gateway_name="Orphan Gateway",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(gateway)
    db.commit()

    print("➕ inserted")
    if uplink_uuid:
        log_step(db, uplink_uuid, Step.CONTEXT_ENRICHMENT, Status.PENDING, f"New orphan gateway: {gateway_eui}")

    return True

def run():
    db_gen = get_sync_db_session()
    db = next(db_gen)

    try:
        uplinks = find_uplinks_by_latest_log(db, Step.CONTEXT_ENRICHMENT, Status.PENDING)

        if not uplinks:
            print("✅ No pending uplinks to retry.")
            return

        print(f"🔁 Retrying {len(uplinks)} pending enrichments...")

        retried, fixed, unresolved, gateways_added = 0, 0, 0, 0

        for uplink in uplinks:
            retried += 1
            deveui = uplink.deveui
            gateway_eui = uplink.gateway_eui

            if ensure_gateway_exists(db, gateway_eui, uplink.uplink_uuid):
                gateways_added += 1

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

                log_step(db, uplink.uplink_uuid, Step.CONTEXT_ENRICHMENT, Status.SUCCESS, "Retry resolved with device type")
                print(f"✅ Fixed: {uplink.uplink_uuid} ({deveui})")
                fixed += 1
            else:
                ensure_device_context_exists(deveui, gateway_eui, db)
                log_step(db, uplink.uplink_uuid, Step.CONTEXT_ENRICHMENT, Status.PENDING, "No matching device context found — ORPHAN inserted")
                print(f"❌ Unresolved: {uplink.uplink_uuid} ({deveui}) → ORPHAN inserted")
                unresolved += 1

        db.commit()
        print(f"\n📊 Retry Summary: 🔁 {retried} retried, ✅ {fixed} fixed, ❌ {unresolved} unresolved, 🛰️ {gateways_added} gateways added")

    finally:
        db_gen.close()

if __name__ == "__main__":
    run()
