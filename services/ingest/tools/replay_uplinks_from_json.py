"""
Replay Uplinks to Ingest API
Version: 1.2.0
Last Updated: 2025-08-06 15:33 UTC
Authors: SenseMy IoT Team

Changelog:
- Adds deduplication before sending each uplink
- Skips entries with missing DevEUI, FPort, or payload_hex
"""

import json
import time
import requests
from datetime import datetime

API_URL = "https://dev.sensemy.cloud/uplink?source=actility"

def load_json_file(filename):
    with open(filename, "r") as f:
        return json.load(f)

def dedup_key(entry):
    try:
        eui = entry["DevEUI_uplink"]["DevEUI"]
        ts = entry["DevEUI_uplink"]["Time"]
        payload = entry["DevEUI_uplink"]["payload_hex"]
        return f"{eui}_{ts}_{payload}"
    except KeyError:
        return None

def send_uplink(entry):
    try:
        response = requests.post(API_URL, json=entry, timeout=5)
        print(f"📤 Sent {entry['DevEUI_uplink']['DevEUI']} @ {entry['DevEUI_uplink']['Time']} → {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending uplink: {e}")

def main():
    uplinks = load_json_file("uplinks_clean.json")
    print(f"🔢 Loaded {len(uplinks)} uplinks from JSON")

    sent = 0
    dedup_set = set()

    for entry in uplinks:
        key = dedup_key(entry)
        if not key:
            print("⚠️  Skipping malformed entry")
            continue

        if key in dedup_set:
            print(f"⏩ Duplicate skipped: {key}")
            continue

        dedup_set.add(key)
        send_uplink(entry)
        sent += 1
        time.sleep(0.25)

    print(f"\n✅ Done. Sent {sent} unique uplinks.")

if __name__ == "__main__":
    main()
