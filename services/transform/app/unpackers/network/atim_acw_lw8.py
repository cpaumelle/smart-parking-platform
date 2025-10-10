# atim_acw_lw8.py - v0.1.1 - 2023-07-10
# Payload decoder for ATIM ACW/LW8-TST LoRaWAN Tester

def unpack(payload_hex: str, fport: int) -> dict:
    if fport != 2:
        raise ValueError(f"Unexpected port {fport}, expected 2")

    b = bytes.fromhex(payload_hex)

    if len(b) != 1:
        raise ValueError(f"Unexpected payload length: {len(b)} bytes, expected 1")

    status = b[0]
    
    if status == 0x00:
        description = "Waiting for network"
    elif status == 0x01:
        description = "No signal"
    elif status == 0x02:
        description = "Low signal"
    elif status == 0x03:
        description = "Good signal" 
    elif status == 0x04:
        description = "Excellent signal"
    else:
        description = f"Unknown status: {status}"
        
    return {
        "status": status,
        "description": description
    }