"""main.py - Ingest Server Entry (Actility + Netmore + TTI + ChirpStack Support + MQTT)
Version: 0.9.0 - 2025-10-06 21:05 UTC
Changelog:
- Added MQTT publishing capability for ChirpStack integration
- Publishes to application/{app_id}/device/{dev_eui}/event/up topic
"""

# [unchanged import block]
from fastapi import FastAPI, HTTPException, Request
import os, json, logging
from datetime import datetime, timedelta
import psycopg2
from fastapi.middleware.cors import CORSMiddleware
from dateutil.parser import isoparse

from forwarders.transform_forwarder import forward_to_transform
from forwarders.mqtt_publisher import init_mqtt, publish_to_mqtt
from parsers.actility_parser import parse_actility
from parsers.netmore_parser import parse_netmore
from parsers.tti_parser import parse_tti
from parsers.chirpstack_parser import parse_chirpstack
from parking_detector import parking_detector, refresh_parking_cache_task, forward_to_parking_display

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
# CORS - Restricted to allowed origins
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

DB_HOST = os.getenv("INGEST_DB_HOST", "localhost")
DB_PORT = os.getenv("INGEST_DB_INTERNAL_PORT", "5432")
DB_NAME = os.getenv("INGEST_DB_NAME", "ingest_db")
DB_USER = os.getenv("INGEST_DB_USER", "ingestuser")
DB_PASS = os.getenv("INGEST_DB_PASSWORD", "secret")

# ChirpStack application ID (for MQTT topic)
CHIRPSTACK_APP_ID = os.getenv("CHIRPSTACK_APP_ID", "345b028b-9f0a-4c56-910c-6a05dc2dc22f")

# Initialize MQTT on module load
init_mqtt()

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
# Startup event to initialize parking sensor cache
@app.on_event("startup")
async def startup_event():
    import asyncio
    asyncio.create_task(refresh_parking_cache_task())
    logger.info("🅿️  Parking sensor cache refresh task started")


@app.post("/uplink")
async def receive_uplink(req: Request):
    try:
        source = req.query_params.get("source", "").lower()
        body = await req.body()
        created_at = datetime.utcnow()
        logger.info(f"🛰️  Incoming request on /uplink from source={source or 'auto'}: {body}")

        payload = json.loads(body.decode("utf-8")) if body else {}

        # Auto-detect LNS type
        if not source:
            if isinstance(payload, dict):
                if "DevEUI_uplink" in payload:
                    source = "actility"
                elif "end_device_ids" in payload:
                    source = "tti"
                elif "deviceInfo" in payload and "rxInfo" in payload:
                    source = "chirpstack"
            elif isinstance(payload, list):
                if payload and isinstance(payload[0], dict) and "devEui" in payload[0]:
                    source = "netmore"

        # Normalize uplink using correct parser
        if source.startswith("actility"):
            uplink_data = parse_actility(payload)
        elif source == "netmore":
            if isinstance(payload, list) and len(payload) > 0:
                uplink_data = parse_netmore(payload[0])
            else:
                raise ValueError("Expected array of Netmore payloads")
        elif source == "tti":
            uplink_data = parse_tti(payload)
        elif source == "chirpstack":
            uplink_data = parse_chirpstack(payload)
        else:
            logger.error(f"🚫 Unknown or unsupported source: {source}")
            raise ValueError(f"Unknown or unsupported source: {source}")

        deveui = uplink_data["deveui"]
        if not deveui:
            raise ValueError("Missing DevEUI in parsed payload")

        received_at = uplink_data["received_at"]
        payload_hex = uplink_data["payload"]

        # Deduplication check
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM ingest.raw_uplinks
                        WHERE deveui = %s
                          AND payload = %s
                          AND received_at = %s
                          AND received_at > NOW() - INTERVAL '30 seconds'
                    """, (deveui, payload_hex, received_at))
                    duplicate_count = cur.fetchone()[0]

                    if duplicate_count > 0:
                        logger.info(f"⚠️  Duplicate uplink skipped for {deveui} @ {received_at}")
                        return {"status": "duplicate-skipped", "deveui": deveui}
        except Exception as e:
            logger.warning(f"⚠️ Deduplication check failed, proceeding anyway: {e}")

        # Insert into ingest.raw_uplinks
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ingest.raw_uplinks (deveui, received_at, fport, payload, uplink_metadata, source, gateway_eui)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING uplink_id
                    """, (
                        deveui,
                        received_at,
                        uplink_data.get("fport"),
                        payload_hex,
                        json.dumps(uplink_data["uplink_metadata"]),
                        source,
                        uplink_data.get("gateway_eui")
                    ))
                    ingest_id = cur.fetchone()[0]
                    conn.commit()
        except Exception as e:
            logger.error(f"❌ DB insert failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database insert error: {e}")

        # Publish to MQTT (for ChirpStack sources)
        if source == "chirpstack":
            try:
                mqtt_payload = {
                    "applicationID": CHIRPSTACK_APP_ID,
                    "devEUI": deveui,
                    "fPort": uplink_data.get("fport"),
                    "data": payload_hex,
                    "receivedAt": received_at.isoformat(),
                    "metadata": uplink_data["uplink_metadata"],
                    "gatewayEUI": uplink_data.get("gateway_eui"),
                    "ingestId": ingest_id
                }
                publish_to_mqtt(CHIRPSTACK_APP_ID, deveui, "up", mqtt_payload)
            except Exception as e:
                logger.warning(f"⚠️ MQTT publish failed (non-fatal): {e}")

        # Check if this is a parking sensor and forward to parking-display service
        is_parking = parking_detector.is_parking_sensor(deveui)
        if is_parking:
            space_id = parking_detector.get_space_id(deveui)
            if space_id:
                logger.info(f"🅿️  Parking sensor detected: {deveui} -> space {space_id}")
                # Forward to parking display (fire-and-forget, non-blocking)
                try:
                    parking_uplink = {
                        "devEUI": deveui,
                        "fPort": uplink_data.get("fport"),
                        "data": payload_hex,
                        "timestamp": received_at.isoformat(),
                        "object": uplink_data.get("uplink_metadata", {}).get("decoded", {}),
                        "rxInfo": uplink_data.get("uplink_metadata", {}).get("rxInfo", [])
                    }
                    await forward_to_parking_display(parking_uplink, space_id)
                except Exception as e:
                    logger.warning(f"⚠️ Parking forward failed (non-fatal): {e}")
            else:
                logger.warning(f"⚠️ Parking sensor {deveui} not mapped to space")


        # Forward to Transform
        forward_payload = {
            "deveui": deveui,
            "received_at": received_at.isoformat(),
            "fport": uplink_data.get("fport"),
            "payload": payload_hex,
            "uplink_metadata": uplink_data["uplink_metadata"],
            "source": source,
            "ingest_id": ingest_id,
            "gateway_eui": uplink_data.get("gateway_eui"),
        }

        logger.info(f"📤 Forwarding to Transform: {json.dumps(forward_payload, indent=2)}")
        await forward_to_transform(forward_payload)

        logger.info(f"✔️ Stored and forwarded uplink for {deveui}")
        return {"status": "stored-and-forwarded", "deveui": deveui}

    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
