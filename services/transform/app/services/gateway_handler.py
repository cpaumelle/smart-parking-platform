# app/services/gateway_handler.py
# Version: 0.6.1 – 2025-08-05 10:50 UTC
# Changelog:
# - Normalized gateway_eui in all functions (last 16 hex chars, uppercase)
# - Prevents mismatches between ingest and DB

from sqlalchemy.orm import Session
from models import ProcessedUplink, Gateway
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

def normalize_gateway_eui(eui: str) -> str:
    """
    Normalize gateway EUI by stripping and taking last 16 characters (uppercase).
    Example: 'CP-Dinard-7076FF006404010B' → '7076FF006404010B'
    """
    if not eui:
        return None
    return eui.strip()[-16:].upper()

def ensure_gateway_exists(gateway_eui: str, db: Session):
    """
    Check if gateway_eui exists in the gateways table. If not, insert it as an orphan.
    """
    gateway_eui = normalize_gateway_eui(gateway_eui)
    if not gateway_eui:
        print("⚠️ Skipping gateway check: gateway_eui is null")
        return

    existing = db.query(Gateway).filter_by(gw_eui=gateway_eui).first()
    if existing:
        print(f"ℹ️ Gateway already exists: {gateway_eui}")
        return

    print(f"🛰️ New orphan gateway detected: {gateway_eui} → inserting...")
    new_gateway = Gateway(
        gw_eui=gateway_eui,
        gateway_name=None,
        site_id=None,
        location_id=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        status='online'
    )
    db.add(new_gateway)
    try:
        db.commit()
        print(f"✅ Orphan gateway inserted: {gateway_eui}")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ Failed to insert orphan gateway {gateway_eui}: {e}")

def mark_gateway_online(gateway_eui: str, db: Session):
    """
    Set gateway as online and update last_seen_at timestamp.
    """
    gateway_eui = normalize_gateway_eui(gateway_eui)
    if not gateway_eui:
        return

    try:
        updated = db.query(Gateway).filter_by(gw_eui=gateway_eui).update({
            "status": "online",
            "last_seen_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        if updated:
            db.commit()
            print(f"🔄 Gateway marked online: {gateway_eui}")
        else:
            print(f"⚠️ No matching gateway found for: {gateway_eui}")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ Failed to update gateway status: {e}")

def insert_or_update_processed_uplink(uplink, db: Session):
    """
    Final enrichment step: insert enriched uplink into transform.processed_uplinks
    and ensure gateway is recorded in transform.gateways.

    Accepts either a dict or a ProcessedUplink object.
    """
    def extract(field):
        if isinstance(uplink, dict):
            return uplink.get(field)
        return getattr(uplink, field, None)

    gateway_eui = extract("gateway_eui")
    ensure_gateway_exists(gateway_eui, db)
    mark_gateway_online(gateway_eui, db)

    if isinstance(uplink, ProcessedUplink):
        try:
            db.merge(uplink)
            db.commit()
            print(f"✅ Enriched uplink stored: {uplink.uplink_uuid} for DevEUI={uplink.deveui}")
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Error storing enriched uplink: {e}")
            raise
        return

    processed = ProcessedUplink(
        uplink_uuid=extract("uplink_uuid"),
        deveui=extract("deveui"),
        timestamp=extract("timestamp"),
        fport=extract("fport"),
        payload=extract("payload"),
        uplink_metadata=extract("uplink_metadata"),
        device_type_id=extract("device_type_id"),
        site_id=extract("site_id"),
        floor_id=extract("floor_id"),
        room_id=extract("room_id"),
        zone_id=extract("zone_id"),
        source=extract("source"),
        ingest_uplink_id=extract("ingest_uplink_id"),
        gateway_eui=normalize_gateway_eui(gateway_eui),
        inserted_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        db.merge(processed)
        db.commit()
        print(f"✅ Enriched uplink stored: {processed.uplink_uuid} for DevEUI={processed.deveui}")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ Error storing enriched uplink: {e}")
        raise
