# forwarders/transform_forwarder.py
# Version: 0.1.1 - 2025-07-19 18:45 UTC
# - Remaps "ingest_id" → "ingest_uplink_id" before sending to transform

import os
import httpx
import logging

logger = logging.getLogger(__name__)

TRANSFORM_URL = os.getenv(
    "TRANSFORM_URL",
    "http://transform-service:9001/process-uplink/uplink"
)

async def forward_to_transform(payload: dict):
    try:
        # 🔁 Map ingest_id → ingest_uplink_id for transform
        if "ingest_id" in payload:
            payload["ingest_uplink_id"] = payload.pop("ingest_id")

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                TRANSFORM_URL,
                headers={"Content-Type": "application/json"},
                json=payload
            )
            logger.info(f"✅ Transform response: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"❌ Error forwarding to Transform: {e}", exc_info=True)
        raise
