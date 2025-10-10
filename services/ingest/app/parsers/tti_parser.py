# tti_parser.py - Extract fields from The Things Industries uplink payloads
# Version: 0.2.1 - 2025-08-05 11:25 UTC
# Changelog:
# - Deduplicates dual uplinks from `uplink_message` and `uplink_normalized`
# - Prefers `uplink_message` when available; falls back to `uplink_normalized`

import base64
from datetime import datetime
from dateutil.parser import isoparse

def parse_tti(payload: dict):
    try:
        uplink = payload.get("uplink_message") or payload.get("uplink_normalized") or {}
        end_device_ids = payload.get("end_device_ids", {})
        deveui = end_device_ids.get("dev_eui")
        raw_ts = uplink.get("received_at") or payload.get("received_at")
        fport = uplink.get("f_port")
        payload_b64 = uplink.get("frm_payload")

        # Decode Base64 payload
        if payload_b64:
            try:
                payload_hex = base64.b64decode(payload_b64).hex()
            except Exception:
                payload_hex = None
        else:
            payload_hex = None

        try:
            received_at = isoparse(raw_ts) if raw_ts else datetime.utcnow()
        except Exception:
            received_at = datetime.utcnow()

        # Extract gateway EUI from rx_metadata[0]
        rx_metadata = uplink.get("rx_metadata", [])
        gateway_eui = None
        if rx_metadata and isinstance(rx_metadata, list):
            gateway_eui = rx_metadata[0].get("gateway_ids", {}).get("eui")

        return {
            "deveui": deveui,
            "payload": payload_hex,
            "received_at": received_at,
            "fport": fport,
            "uplink_metadata": payload,
            "gateway_eui": gateway_eui,
        }

    except Exception as e:
        raise ValueError(f"Error parsing TTI payload: {e}")
