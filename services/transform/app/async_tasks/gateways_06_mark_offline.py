"""
gateways_06_mark_offline.py
Version: 1.3.0 – 2025-08-05 12:45 UTC
Authors: SenseMy IoT Team

Purpose:
- Marks gateways as 'offline' if their last_seen_at is NULL or older than 24 hours

Changelog:
- Logs both gw_eui and last_seen_at for marked gateways
"""

from database.connections import get_sync_db_session
from models import Gateway
from datetime import datetime, timedelta

print(f"⏳ Running gateway offline status sweep at {datetime.utcnow().isoformat()}")

def run():
    db_gen = get_sync_db_session()
    db = next(db_gen)

    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)

        # Step 1: Mark stale gateways offline
        to_offline = (
            db.query(Gateway)
            .filter(Gateway.status == "online", (Gateway.last_seen_at == None) | (Gateway.last_seen_at < cutoff))
            .all()
        )

        for gw in to_offline:
            print(f"🔻 Marking offline: {gw.gw_eui} (last_seen_at={gw.last_seen_at})")
            gw.status = "offline"
            gw.updated_at = datetime.utcnow()

        # Step 2: Mark recently seen gateways back online
        to_online = (
            db.query(Gateway)
            .filter(Gateway.status == "offline", Gateway.last_seen_at != None, Gateway.last_seen_at >= cutoff)
            .all()
        )

        for gw in to_online:
            print(f"🔼 Marking online: {gw.gw_eui} (last_seen_at={gw.last_seen_at})")
            gw.status = "online"
            gw.updated_at = datetime.utcnow()

        db.commit()
        print(f"✅ Sweep complete: {len(to_offline)} offline, {len(to_online)} online")

    except Exception as e:
        print(f"❌ Error updating gateway statuses: {e}")

    finally:
        db_gen.close()

if __name__ == "__main__":
    run()
