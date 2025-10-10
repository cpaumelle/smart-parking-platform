# Version: 0.2.2 - 2025-07-22 16:55 UTC
# Changelog:
# - Truncate gateway_eui to last 16 chars (standardize format)

from dateutil.parser import isoparse
from datetime import datetime

def parse_actility(payload: dict):
    uplink = payload.get("DevEUI_uplink", {})
    deveui = uplink.get("DevEUI")
    payload_hex = uplink.get("payload_hex")
    raw_ts = uplink.get("Time")

    try:
        received_at = isoparse(raw_ts) if raw_ts else datetime.utcnow()
    except Exception:
        received_at = datetime.utcnow()

    fport = uplink.get("FPort")

    # Preferred 16-char Gateway EUI from BaseStationData
    raw_gateway = uplink.get("BaseStationData", {}).get("name", "")
    gateway_eui = raw_gateway[-16:] if raw_gateway else None

    rssi = uplink.get("LrrRSSI")
    snr = uplink.get("LrrSNR")

    return {
        "deveui": deveui.upper() if deveui else None,
        "payload": payload_hex,
        "received_at": received_at,
        "fport": fport,
        "uplink_metadata": payload,
        "gateway_eui": gateway_eui,
        "gateway_rssi": rssi,
        "gateway_snr": snr,
    }