# netmore_parser.py - Extract fields from Netmore uplink payloads
# Version: 0.2.0 - 2025-07-21 21:35 UTC
# Changelog:
# - Normalized deveui to uppercase
# - Extracted gateway_eui, RSSI, and SNR

from dateutil.parser import isoparse
from datetime import datetime

def parse_netmore(payload: dict):
    # Handle list wrapping
    if isinstance(payload, list) and len(payload) == 1:
        payload = payload[0]
    elif isinstance(payload, list) and len(payload) > 1:
        raise ValueError("Netmore payloads with multiple uplinks not supported yet")

    deveui = payload.get("devEui")
    payload_hex = payload.get("payload")
    raw_ts = payload.get("timestamp")

    try:
        received_at = isoparse(raw_ts) if raw_ts else datetime.utcnow()
    except Exception:
        received_at = datetime.utcnow()

    fport = int(payload.get("fPort") or payload.get("FPort") or 0)

    # Gateway info
    gw_raw = payload.get("gatewayIdentifier")
    gateway_eui = f"NETMORE-{gw_raw}" if gw_raw else None
    rssi = float(payload.get("rssi")) if payload.get("rssi") else None
    snr = float(payload.get("snr")) if payload.get("snr") else None

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