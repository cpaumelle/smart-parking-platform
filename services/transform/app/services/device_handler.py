"""
SenseMy IoT: Device Handler
Version: 0.1.0
Last Updated: 2025-08-06 16:50 UTC+2

Handles automatic insertion of missing DevEUIs as ORPHAN entries in transform.device_context.
"""

from models import DeviceContext
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

def ensure_device_context_exists(deveui: str, gateway_eui: str, db):
    if not deveui:
        print("⚠️ Skipping device context check: DevEUI is null")
        return

    existing = db.query(DeviceContext).filter_by(deveui=deveui).first()
    if existing:
        print(f"ℹ️ DeviceContext already exists: {deveui}")
        return

    print(f"🆕 New orphan DevEUI detected: {deveui} → inserting into device_context")
    new_device = DeviceContext(
        deveui=deveui,
        lifecycle_state="ORPHAN",
        last_gateway=gateway_eui,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_device)
    try:
        db.commit()
        print(f"✅ ORPHAN DeviceContext inserted: {deveui}")
    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ Failed to insert ORPHAN DevEUI {deveui}: {e}")
