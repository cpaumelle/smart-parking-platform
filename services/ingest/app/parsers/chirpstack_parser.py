# chirpstack_parser.py - Extract fields from ChirpStack v4 uplink payloads
# Version: 0.1.0 - 2025-10-02 18:00 UTC
# Changelog:
# - Initial implementation for ChirpStack v4 JSON format
# - Extracts DevEUI, timestamp, fPort, payload (base64 decoded)
# - Extracts gateway EUI, RSSI, and SNR from rxInfo[0]

import base64
from datetime import datetime
from dateutil.parser import isoparse

def parse_chirpstack(payload: dict):
    try:
        # Extract device info
        device_info = payload.get("deviceInfo", {})
        deveui = device_info.get("devEui")

        # Extract timestamp
        raw_ts = payload.get("time")
        try:
            received_at = isoparse(raw_ts) if raw_ts else datetime.utcnow()
        except Exception:
            received_at = datetime.utcnow()

        # Extract fPort
        fport = payload.get("fPort")

        # Decode Base64 payload to hex
        payload_b64 = payload.get("data")
        if payload_b64:
            try:
                payload_hex = base64.b64decode(payload_b64).hex()
            except Exception:
                payload_hex = None
        else:
            payload_hex = None

        # Extract gateway info from rxInfo[0]
        rx_info = payload.get("rxInfo", [])
        gateway_eui = None
        rssi = None
        snr = None

        if rx_info and isinstance(rx_info, list) and len(rx_info) > 0:
            first_rx = rx_info[0]
            gateway_eui = first_rx.get("gatewayId")
            rssi = first_rx.get("rssi")
            snr = first_rx.get("snr")

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

    except Exception as e:
        raise ValueError(f"Error parsing ChirpStack payload: {e}")
