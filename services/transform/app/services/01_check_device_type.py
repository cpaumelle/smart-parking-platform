# 01_check_device_type.py
# Version: 0.2.0 - 2025-07-20 09:43 UTC
# Changelog:
# - Preserve NULL for device_type_id when no match is found (no fake strings)
# - Log reason explicitly in enrichment_logs.detail (e.g. 'No matching twinning record')
# - Compatible with device_type_id foreign key constraint
# - Uses internal port 5432 from .env (TRANSFORM_DB_INTERNAL_PORT)
# - No bogus updates or strings inserted
# - Matches enrich fallback logic

import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_HOST = os.getenv("TRANSFORM_DB_HOST", "transform-database")
DB_PORT = os.getenv("TRANSFORM_DB_INTERNAL_PORT", "5432")  # Always internal Docker port!
DB_NAME = os.getenv("TRANSFORM_DB_NAME", "transform_db")
DB_USER = os.getenv("TRANSFORM_DB_USER", "transform_user")
DB_PASS = os.getenv("TRANSFORM_DB_PASSWORD", "secret")

def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )

def log_enrichment(cur, uplink_uuid, step, detail, status):
    cur.execute("""
        INSERT INTO transform.enrichment_logs (log_id, uplink_uuid, step, detail, status, timestamp)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (
        str(uuid.uuid4()), uplink_uuid, step, detail, status
    ))

def enrich_device_type():
    print("🔍 Checking for uplinks missing device_type_id...")

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT uplink_uuid, deveui
                FROM transform.processed_uplinks
                WHERE device_type_id IS NULL
                ORDER BY inserted_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall()

            print(f"🧠 Found {len(rows)} uplinks to process")

            for row in rows:
                uplink_uuid = row["uplink_uuid"]
                deveui = row["deveui"]

                cur.execute("""
                    SELECT device_type_id
                    FROM transform.device_context
                    WHERE deveui = %s AND unassigned_at IS NULL
                    ORDER BY assigned_at DESC
                    LIMIT 1
                """, (deveui,))
                twin = cur.fetchone()

                if twin and twin.get("device_type_id"):
                    device_type_id = twin["device_type_id"]
                    cur.execute("""
                        UPDATE transform.processed_uplinks
                        SET device_type_id = %s, updated_at = NOW()
                        WHERE uplink_uuid = %s
                    """, (device_type_id, uplink_uuid))

                    log_enrichment(
                        cur, uplink_uuid, "check_device_type",
                        f"Assigned device_type_id {device_type_id} from context", "success"
                    )
                    print(f"[✓] {deveui} → {device_type_id}")

                else:
                    # No device_type_id found, log but do NOT insert bogus string
                    log_enrichment(
                        cur, uplink_uuid, "check_device_type",
                        "No matching twinning record", "error"
                    )
                    print(f"[!] {deveui} → NULL (no context)")

            conn.commit()

if __name__ == "__main__":
    enrich_device_type()