# verify_and_replay.py
# Version: 0.1.1 - 2025-08-02 15:55 UTC
# Purpose: Replay missing uplinks from ingest DB to transform service
# Notes:
# - Reuses forward_to_transform() from app.forwarders
# - Reuses get_conn() from app.main
# - Compares ingest.raw_uplinks vs transform.ingest_uplinks by uplink_id

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg2
import json
from datetime import datetime
from forwarders.transform_forwarder import forward_to_transform
from main import get_conn

# Transform DB config
TRANSFORM_DB_HOST = os.getenv("TRANSFORM_DB_HOST", "transform-database")
TRANSFORM_DB_PORT = os.getenv("TRANSFORM_DB_INTERNAL_PORT", "5546")
TRANSFORM_DB_NAME = os.getenv("TRANSFORM_DB_NAME", "transform_db")
TRANSFORM_DB_USER = os.getenv("TRANSFORM_DB_USER", "transform_user")
TRANSFORM_DB_PASSWORD = os.getenv("TRANSFORM_DB_PASSWORD", "secret")

def get_transform_conn():
    return psycopg2.connect(
        host=TRANSFORM_DB_HOST,
        port=TRANSFORM_DB_PORT,
        dbname=TRANSFORM_DB_NAME,
        user=TRANSFORM_DB_USER,
        password=TRANSFORM_DB_PASSWORD
    )

def get_transform_uplink_ids():
    with get_transform_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ingest_uplink_id FROM transform.ingest_uplinks")
            return set(row[0] for row in cur.fetchall())

def get_recent_ingest_uplinks(limit=10000):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT uplink_id, deveui, received_at, fport, payload, uplink_metadata, source, gateway_eui
                FROM ingest.raw_uplinks
                ORDER BY uplink_id DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

def replay_uplinks():
    transform_ids = get_transform_uplink_ids()
    rows = get_recent_ingest_uplinks()

    print(f"🔍 Found {len(rows)} recent uplinks in ingest.raw_uplinks")
    print(f"🧱 Found {len(transform_ids)} uplinks in transform.ingest_uplinks")

    missing = [r for r in rows if r[0] not in transform_ids]
    print(f"🚨 {len(missing)} uplinks missing in transform → replaying...")

    for row in missing:
        uplink_id, deveui, received_at, fport, payload, uplink_metadata, source, gateway_eui = row
        forward_payload = {
            "deveui": deveui,
            "received_at": received_at.isoformat(),
            "fport": fport,
            "payload": payload,
            "uplink_metadata": uplink_metadata,
            "source": source,
            "ingest_id": uplink_id,
            "gateway_eui": gateway_eui
        }

        try:
            print(f"➡️  Reposting uplink_id {uplink_id} for {deveui}...")
            import asyncio
            asyncio.run(forward_to_transform(forward_payload))
            print(f"✅ Success for {uplink_id}")
        except Exception as e:
            print(f"❌ Failed for {uplink_id}: {e}")

if __name__ == "__main__":
    replay_uplinks()
