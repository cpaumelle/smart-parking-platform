# async_tasks/unpack_utils.py
# Version: 0.3.1 – 2025-07-23 11:55 UTC
# Changelog:
# - Updated header to match canonical unpacking format
# - References constants/enrichment_steps.py for status filtering
# - Clarified intended use by unpack_04 and unpack_05

"""
📦 UNPACKING PIPELINE UTILITY MODULE
Provides shared functions for unpacking uplinks:

- get_uplinks_ready_for_unpacking(): returns uplinks marked as READY (enrichment success)
- get_failed_unpacks(): returns uplinks that failed unpacking previously
- safe_unpack_and_catch(): safely applies unpacker function with logging and error capture

Used by:
- async_tasks/unpack_04_unpack_ready.py
- async_tasks/unpack_05_unpack_retry_failed.py

Filtering logic relies on `constants/enrichment_steps.py` to match:
- Step.UNPACKING_INIT + Status.READY
- Step.UNPACKING + Status.FAIL
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from models import ProcessedUplink, EnrichmentLog, DeviceType
from constants.enrichment_steps import Step, Status

def get_uplinks_ready_for_unpacking(db: Session, limit=100):
    """
    Return list of (uplink, device_type) tuples where:
    - latest log is (step=UNPACKING_INIT, status=READY)
    - uplink.device_type_id is not null
    - device_type.unpacker is not null
    """
    latest_logs = db.query(
        EnrichmentLog.uplink_uuid,
        func.max(EnrichmentLog.created_at).label("max_time")
    ).group_by(EnrichmentLog.uplink_uuid).subquery()

    latest_matching_logs = db.query(EnrichmentLog.uplink_uuid).\
        join(latest_logs, (EnrichmentLog.uplink_uuid == latest_logs.c.uplink_uuid) &
                          (EnrichmentLog.created_at == latest_logs.c.max_time)).\
        filter(
            EnrichmentLog.step == Step.UNPACKING_INIT,
            EnrichmentLog.status == Status.READY
        ).subquery()

    results = db.query(ProcessedUplink, DeviceType).\
        join(latest_matching_logs, ProcessedUplink.uplink_uuid == latest_matching_logs.c.uplink_uuid).\
        join(DeviceType, ProcessedUplink.device_type_id == DeviceType.device_type_id).\
        filter(DeviceType.unpacker.isnot(None)).\
        order_by(ProcessedUplink.inserted_at.asc()).\
        limit(limit).all()

    return results


def get_failed_unpacks(db: Session, limit=100):
    """
    Return list of (uplink, device_type) where:
    - latest log is (step=UNPACKING, status=FAIL)
    - device_type is refreshed from device_context if stale
    """
    from models import DeviceContext  # inline import to avoid circulars

    latest_logs = db.query(
        EnrichmentLog.uplink_uuid,
        func.max(EnrichmentLog.created_at).label("max_time")
    ).group_by(EnrichmentLog.uplink_uuid).subquery()

    latest_matching_logs = db.query(EnrichmentLog.uplink_uuid).\
        join(latest_logs, (EnrichmentLog.uplink_uuid == latest_logs.c.uplink_uuid) &
                          (EnrichmentLog.created_at == latest_logs.c.max_time)).\
        filter(
            EnrichmentLog.step == Step.UNPACKING,
            EnrichmentLog.status == Status.FAIL
        ).subquery()

    uplinks = db.query(ProcessedUplink).\
        join(latest_matching_logs, ProcessedUplink.uplink_uuid == latest_matching_logs.c.uplink_uuid).\
        order_by(ProcessedUplink.updated_at.asc()).\
        limit(limit).all()

    results = []
    for uplink in uplinks:
        context = db.query(DeviceContext).filter_by(deveui=uplink.deveui).first()
        if context and context.device_type_id != uplink.device_type_id:
            print(f"♻️ Syncing device_type_id for DevEUI={uplink.deveui}: {uplink.device_type_id} → {context.device_type_id}")
            uplink.device_type_id = context.device_type_id
            db.merge(uplink)

        device_type = db.query(DeviceType).filter_by(device_type_id=uplink.device_type_id).first()
        if device_type and device_type.unpacker:
            results.append((uplink, device_type))

    return results


def safe_unpack_and_catch(dev_eui: str, uplink, unpacker_func):
    try:
        if not uplink.payload:
            raise ValueError("Missing payload")
        if uplink.fport is None:
            raise ValueError("Missing fport")

        payload = uplink.payload

        # 🧪 Step 1: Convert memoryview to bytes
        if isinstance(payload, memoryview):
            print(f"🧪 Raw payload (type=<class 'memoryview'>): {payload}")
            payload = payload.tobytes()

        # 🧪 Step 2: Handle payload as bytes or str
        if isinstance(payload, bytes):
            print(f"🧪 Raw payload (type={type(payload)}): {repr(payload)}")
            try:
                payload_str = payload.decode("ascii")
                is_hex_ascii = (
                    len(payload_str) % 2 == 0 and
                    all(c in "0123456789abcdefABCDEF" for c in payload_str)
                )
                if is_hex_ascii:
                    print("🔍 Payload looks like hex ASCII, decoding with fromhex()")
                    decoded_bytes = bytes.fromhex(payload_str)
                    if len(decoded_bytes) >= len(payload) // 2:
                        payload_bytes = decoded_bytes
                    else:
                        print("⚠️ Decoding result too short, using raw payload")
                        payload_bytes = payload
                else:
                    payload_bytes = payload
            except UnicodeDecodeError:
                payload_bytes = payload

        elif isinstance(payload, str):
            print(f"🧪 Raw payload (type=str): {payload}")
            payload_bytes = bytes.fromhex(payload)
        else:
            raise TypeError(f"Unsupported payload type: {type(payload)}")

        print(f"🔁 Converting to binary for unpacking")
        print(f"🧪 Payload HEX: {payload_bytes.hex()}")
        print(f"🔧 Using unpacker function: {unpacker_func.__module__}.{unpacker_func.__name__}")

        return unpacker_func(payload_bytes, uplink.fport)

    except Exception as e:
        raise RuntimeError(f"Exception during unpacking: {type(e).__name__}: {str(e)}")