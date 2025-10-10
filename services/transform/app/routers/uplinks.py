# app/routers/uplinks.py
# Version: 0.4.1 - 2025-08-05 13:15 UTC
# Changelog:
# - Updates gateways.last_seen_at when gateway_eui is present

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from dateutil.parser import isoparse
import uuid
import json
import sys
import traceback

from database.connections import get_db_session
from models import IngestUplink

router = APIRouter()

@router.post("/uplink")
async def receive_uplink(req: Request, db: AsyncSession = Depends(get_db_session)):
    try:
        payload = await req.json()
        print("📥 Received payload:", json.dumps(payload), file=sys.stderr)

        deveui = payload.get("deveui")
        if not deveui:
            raise HTTPException(status_code=400, detail="Missing deveui")

        ingest_uplink_id = payload.get("ingest_uplink_id")
        if ingest_uplink_id is None:
            raise HTTPException(status_code=400, detail="Missing ingest_uplink_id from ingest")

        uplink_uuid = str(uuid.uuid4())  # Transform UUID (our local PK)
        raw_ts = payload.get("received_at") or datetime.utcnow().isoformat()
        parsed_ts = isoparse(raw_ts).replace(tzinfo=None)

        payload_hex = payload.get("payload")
        uplink_metadata = payload.get("uplink_metadata", {})
        source = payload.get("source", "unknown")
        fport = payload.get("fport")
        gateway_eui = payload.get("gateway_eui")

        # ✅ Insert uplink
        new_uplink = IngestUplink(
            uplink_uuid=uplink_uuid,
            deveui=deveui,
            timestamp=parsed_ts,
            payload=payload_hex,
            uplink_metadata=uplink_metadata,
            source=source,
            fport=fport,
            ingest_uplink_id=ingest_uplink_id,
            gateway_eui=gateway_eui
        )
        db.add(new_uplink)
        await db.commit()

        # ✅ Update gateway last_seen_at if gateway_eui present
        if gateway_eui:
            print(f"🔄 Updating last_seen_at for gateway {gateway_eui}", file=sys.stderr)
            await db.execute(text("""
                UPDATE transform.gateways
                SET last_seen_at = :ts,
                    updated_at = :ts
                WHERE gw_eui = :eui
            """), {
                "ts": parsed_ts,
                "eui": gateway_eui
            })
            await db.commit()

        # ✅ Insert enrichment log
        await db.execute(text("""
            INSERT INTO transform.enrichment_logs (uplink_uuid, step, detail, status, created_at)
            VALUES (:uplink_uuid, :step, :detail, :status, :created_at)
        """), {
            "uplink_uuid": uplink_uuid,
            "step": "ingestion_received",
            "detail": f"Uplink stored with ingest_uplink_id {ingest_uplink_id}",
            "status": "new",
            "created_at": datetime.utcnow()
        })
        await db.commit()

        return {"status": "stored", "uplink_uuid": uplink_uuid}

    except Exception as e:
        print("❌ Uplink insert failed:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Uplink insert failed: {e}")
