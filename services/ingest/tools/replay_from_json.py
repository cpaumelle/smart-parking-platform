"""
Replay Uplinks from JSON
Version: 0.1.0
Last Updated: 2025-08-06 15:10 UTC
Authors: SenseMy IoT Team

Changelog:
- Initial version to POST CSV-derived JSON uplinks to ingest API
- Supports optional deduplication against ingest.raw_uplinks
- Respects INGEST_REPLAY_URL env var or defaults to Actility-compatible endpoint
"""

import os
import sys
import json
import argparse
import psycopg2
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

# Load env if available
load_dotenv()

# Constants
DEFAULT_REPLAY_URL = "https://dev.sensemy.cloud/uplink?source=actility-replay"
REPLAY_URL = os.getenv("INGEST_REPLAY_URL", DEFAULT_REPLAY_URL)

# DB config for deduplication
INGEST_DB_HOST = os.getenv("INGEST_DB_HOST", "ingest-database")
INGEST_DB_PORT = os.getenv("INGEST_DB_INTERNAL_PORT", "5432")
INGEST_DB_NAME = os.getenv("INGEST_DB_NAME", "ingest_db")
INGEST_DB_USER = os.getenv("INGEST_DB_USER", "ingestuser")
INGEST_DB_PASSWORD = os.getenv("INGEST_DB_PASSWORD", "secret")

def get_db_conn():
    return psycopg2.connect(
        host=INGEST_DB_HOST,
        port=INGEST_DB_PORT,
        dbname=INGEST_DB_NAME,
        user=INGEST_DB_USER,
        password=INGEST_DB_PASSWORD
    )

def is_duplicate(deveui, payload, timestamp):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM ingest.raw_uplinks
                WHERE deveui = %s
                AND payload = %s
                AND ABS(EXTRACT(EPOCH FROM (received_at - %s))) < 1.0
                LIMIT 1;
            """, (deveui, payload, timestamp))
            return cur.fetchone() is not None

def parse_args():
    parser = argparse.ArgumentParser(description="Replay uplinks from a JSON file to the ingest API.")
    parser.add_argument("json_file", help="Path to uplinks_clean.json")
    parser.add_argument("--check-db", action="store_true", help="Enable deduplication by checking ingest.raw_uplinks")
    return parser.parse_args()

def main():
    args = parse_args()
    path = args.json_file
    check_db = args.check_db

    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        sys.exit(1)

    with open(path, "r") as f:
        try:
            uplinks = json.load(f)
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            sys.exit(1)

    print(f"📦 Loaded {len(uplinks)} uplinks from {path}")
    print(f"🌍 Target URL: {REPLAY_URL}")
    print(f"🔍 Deduplication: {'enabled' if check_db else 'disabled'}\n")

    sent = 0
    skipped = 0
    failed = 0

    for entry in uplinks:
        try:
            item = entry.get("DevEUI_uplink", {})
            deveui = item.get("DevEUI")
            timestamp = datetime.fromisoformat(item.get("Time").replace("Z", "+00:00"))
            payload = item.get("payload_hex")

            if check_db and is_duplicate(deveui, payload, timestamp):
                print(f"⚠️  Skipping duplicate: {deveui} @ {timestamp.isoformat()}")
                skipped += 1
                continue

            res = requests.post(REPLAY_URL, json=entry)
            if res.status_code == 200:
                print(f"✅ Sent: {deveui} @ {timestamp.isoformat()}")
                sent += 1
            else:
                print(f"❌ Error {res.status_code} for {deveui}: {res.text}")
                failed += 1

        except Exception as e:
            print(f"❌ Exception for {entry}: {e}")
            failed += 1

    print("\n📊 Summary:")
    print(f" - ✅ Sent: {sent}")
    print(f" - ⚠️  Skipped (duplicates): {skipped}")
    print(f" - ❌ Failed: {failed}")

if __name__ == "__main__":
    main()
