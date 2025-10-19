# Kuando Busylight IoT Omega - Downlink Reference

## Working Configuration (Tested & Verified)

### Payload Format
**5 bytes total:** `[Red, Blue, Green, OnTime, OffTime]`

⚠️ **IMPORTANT:** Byte order is R-B-G (Blue and Green are swapped from standard RGB!)

### Parameters
- **FPort:** `15` (mandatory - Kuando requirement)
- **OnTime:** `0x64` (100 decimal) - steady light
- **OffTime:** `0x00` - no flashing
- **Confirmed:** `false` (unconfirmed downlinks work fine)
- **AutoUplink byte:** Do NOT include (causes issues)

### Color Examples (Tested Working)

| Color  | Hex Payload    | Breakdown                              |
|--------|----------------|----------------------------------------|
| RED    | `FF00006400`   | R=255, B=0, G=0, OnTime=100, OffTime=0 |
| GREEN  | `0000FF6400`   | R=0, B=0, G=255, OnTime=100, OffTime=0 |
| YELLOW | `FF00FF6400`   | R=255, B=0, G=255, OnTime=100, OffTime=0 |
| BLUE   | `00FF006400`   | R=0, B=255, G=0, OnTime=100, OffTime=0 |
| ORANGE | `FFA5006400`   | R=255, B=165, G=0, OnTime=100, OffTime=0 |

### Parking Space State Mapping

```python
colors = {
    "FREE": (0, 255, 0),        # Green
    "OCCUPIED": (255, 0, 0),     # Red
    "RESERVED": (255, 255, 0),   # Yellow
    "MAINTENANCE": (255, 165, 0) # Orange
}

# Convert to Kuando format (swap B and G!)
r, g, b = colors["FREE"]
payload = bytes([r, b, g, 0x64, 0x00])  # Note: b before g!
```

### Sending via ChirpStack gRPC API (Python)

```python
from chirpstack_api.api.device_pb2 import DeviceQueueItem, EnqueueDeviceQueueItemRequest
from chirpstack_api.api.device_pb2_grpc import DeviceServiceStub
import grpc

# Configuration
CHIRPSTACK_HOST = "chirpstack"
CHIRPSTACK_PORT = 8080
API_KEY = "your-api-key"
DEVICE_EUI = "2020203705250102"

# Create payload (example: RED)
payload = bytes([0xFF, 0x00, 0x00, 0x64, 0x00])

# Connect and send
channel = grpc.insecure_channel(f"{CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}")
client = DeviceServiceStub(channel)
auth_token = [("authorization", f"Bearer {API_KEY}")]

queue_item = DeviceQueueItem(
    dev_eui=DEVICE_EUI,
    confirmed=False,
    f_port=15,
    data=payload
)

req = EnqueueDeviceQueueItemRequest(queue_item=queue_item)
response = client.Enqueue(req, metadata=auth_token)

print(f"Queued: {response.id}")
```

### Sending via ChirpStack CLI

```bash
# RED downlink
chirpstack-cli enqueue-downlink \
  --dev-eui 2020203705250102 \
  --fport 15 \
  --data FF00006400

# GREEN downlink
chirpstack-cli enqueue-downlink \
  --dev-eui 2020203705250102 \
  --fport 15 \
  --data 0000FF6400

# YELLOW downlink
chirpstack-cli enqueue-downlink \
  --dev-eui 2020203705250102 \
  --fport 15 \
  --data FF00FF6400
```

### Sending via ChirpStack UI

1. Navigate to **Applications → [Your App] → Devices → [Device EUI]**
2. Go to **"Queue"** tab
3. Click **"Enqueue downlink"**
4. Set:
   - **FPort:** `15`
   - **Payload (hex):** e.g., `FF00006400` for RED
   - **Confirmed:** unchecked
5. Click **"Enqueue"**

### Expected Behavior

- **Class C devices:** Downlink transmits within 1-5 seconds
- **Transmission:** ChirpStack logs show `gRPC Enqueue` → `schedule` → `tx_ack`
- **Visual confirmation:** Display changes color immediately upon receiving downlink

### Troubleshooting

**Display doesn't change color:**
- ✅ Verify FPort is exactly `15`
- ✅ Verify payload is exactly 5 bytes (not 6!)
- ✅ Check byte order: [R, B, G] not [R, G, B]
- ✅ Use OnTime=0x64 (not 0xFF)
- ✅ Confirm device is Class C in ChirpStack
- ✅ Check ChirpStack logs for `tx_ack` (successful transmission)

**Downlink queued but not transmitting:**
- Wait 30-60 seconds for Class C scheduler
- Trigger device uplink to create immediate transmission window
- Check ChirpStack logs for scheduler activity

### Tested Devices

- Display 1: `2020203705250102`
- Display 2: `202020410a1c0702`
- Display 3: `2020203907290902`
- Display 4: `202020390c0e0902`

All tested successfully with this configuration.

---

**Last Updated:** 2025-10-16  
**Platform:** ChirpStack v4.15.0  
**Firmware:** Kuando Busylight IoT Omega (LoRaWAN)
