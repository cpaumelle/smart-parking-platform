# V4 Kuando Downlink Mechanism - Technical Documentation

**Document Version:** 1.0.0
**Date:** 2025-10-16
**Subject:** How the v4 Smart Parking Platform sent downlinks to Kuando Busylight devices via ChirpStack

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Database Structure](#database-structure)
4. [Kuando Payload Encoding](#kuando-payload-encoding)
5. [Complete Message Flow](#complete-message-flow)
6. [API Specifications](#api-specifications)
7. [Example Transactions](#example-transactions)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────┐
│  Parking Display    │  (parking-display service)
│     Service         │  - Manages parking state
│                     │  - Triggers actuations
│  Port: 8100         │
└──────────┬──────────┘
           │ HTTP POST /downlink/send
           │ {"dev_eui": "...", "fport": 15, "data": "FF0032FF00"}
           v
┌─────────────────────┐
│  Downlink Service   │  (downlink-service)
│   (gRPC Wrapper)    │  - REST → gRPC converter
│                     │  - Payload validation
│  Port: 8000         │  - Hex/Base64 decoding
└──────────┬──────────┘
           │ gRPC: DeviceServiceStub.Enqueue()
           │ EnqueueDeviceQueueItemRequest
           v
┌─────────────────────┐
│    ChirpStack       │  (chirpstack)
│  Network Server     │  - LoRaWAN network server
│                     │  - Manages device queues
│  Port: 8080         │  - Class C scheduling
└──────────┬──────────┘
           │ LoRaWAN (Class C)
           │ Immediate downlink transmission
           v
┌─────────────────────┐
│  Kuando Busylight   │  Device EUI: 202020xxxxxxxxxx
│   IoT Omega         │  Class: C (always listening)
│   (LoRaWAN Device)  │  FPort: 15
└─────────────────────┘
```

---

## Component Details

### 1. Downlink Service (`downlink-service`)

**Purpose:** FastAPI REST wrapper around ChirpStack gRPC API

**Location:** `/opt/smart-parking-v4-OLD/services/downlink/`

**Key Features:**
- Converts REST API calls to ChirpStack gRPC calls
- Validates and decodes hex/base64 payloads
- Manages ChirpStack authentication
- Provides device queue management

**Docker Configuration:**
```yaml
downlink-service:
  build: ./services/downlink
  container_name: parking-downlink
  environment:
    CHIRPSTACK_API_URL: parking-chirpstack:8080
    CHIRPSTACK_API_TOKEN: ${CHIRPSTACK_API_TOKEN}
  networks:
    - parking-network
```

**Core Implementation** (`services/downlink/app/main.py`):

```python
# Import ChirpStack gRPC API
from chirpstack_api import api
import grpc

# Create gRPC channel
def get_grpc_channel():
    channel = grpc.insecure_channel(CHIRPSTACK_API_URL)
    return channel

# Send downlink endpoint
@app.post("/downlink/send")
async def send_downlink(request: DownlinkRequest):
    # 1. Parse incoming payload (hex or base64)
    data_bytes = bytes.fromhex(request.data)

    # 2. Create ChirpStack queue item
    queue_item = api.DeviceQueueItem(
        dev_eui=request.dev_eui,      # "2020203705250102"
        confirmed=request.confirmed,   # False
        f_port=request.fport,          # 15
        data=data_bytes,               # b'\xFF\x00\x32\xFF\x00'
    )

    # 3. Enqueue via gRPC
    req = api.EnqueueDeviceQueueItemRequest(queue_item=queue_item)
    response = client.Enqueue(req, metadata=auth_token)

    # 4. Return confirmation
    return {
        "status": "queued",
        "dev_eui": request.dev_eui,
        "f_cnt": response.f_cnt,
        "fport": request.fport
    }
```

**ChirpStack gRPC Integration:**
- Uses `chirpstack_api` Python package
- Calls `DeviceServiceStub.Enqueue()` method
- Authenticates with Bearer token in gRPC metadata
- Returns frame counter (f_cnt) for tracking

---

### 2. Parking Display Service (`parking-display`)

**Purpose:** Orchestrates parking space state management and display actuations

**Location:** `/opt/smart-parking-v4-OLD/services/parking-display/`

**Key Features:**
- State machine for parking spaces (FREE/OCCUPIED/RESERVED)
- Reservation management with APScheduler
- Automatic actuation on sensor updates
- Reconciliation and health monitoring

**Downlink Client** (`app/services/downlink_client.py`):

```python
class DownlinkClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or "http://parking-downlink:8000"
        self.timeout = 5.0
        self.max_retries = 2

    async def send_downlink(
        self,
        dev_eui: str,
        fport: int,
        data: str,  # Hex payload
        confirmed: bool = False
    ):
        # POST to downlink service
        response = await client.post(
            f"{self.base_url}/downlink/send",
            json={
                "dev_eui": dev_eui,
                "fport": fport,
                "data": data,
                "confirmed": confirmed
            }
        )

        # Return result with retry logic
        return {
            "success": response.status_code == 200,
            "response_time_ms": ...,
            "error": None
        }
```

**Actuation Flow** (`app/routers/actuations.py`):

```python
# 1. Get display configuration from database
display_codes = {
    "FREE": "0000FFFF00",      # Green
    "OCCUPIED": "FF0000FF00",  # Red
    "RESERVED": "FF0032FF00",  # Orange
}

# 2. Select payload based on state
display_code = display_codes[new_state]  # "FF0032FF00" for RESERVED

# 3. Send downlink
downlink_result = await downlink_client.send_downlink(
    dev_eui=display_deveui,  # "2020203705250102"
    fport=fport,              # 15
    data=display_code,        # "FF0032FF00"
    confirmed=False
)

# 4. Log actuation in database
await db.execute("""
    UPDATE parking_operations.actuations
    SET downlink_sent = $1,
        sent_at = NOW()
    WHERE actuation_id = $2
""", downlink_result["success"], actuation_id)
```

---

## Database Structure

### Display Registry (`parking_config.display_registry`)

Stores device configurations and state-to-payload mappings.

```sql
CREATE TABLE parking_config.display_registry (
    display_id UUID PRIMARY KEY,
    dev_eui VARCHAR(16) NOT NULL UNIQUE,  -- "2020203705250102"
    display_type VARCHAR(50),              -- "kuando_busylight"
    device_model VARCHAR(100),             -- "Kuando IoT Omega"
    manufacturer VARCHAR(100),             -- "Kuando"

    -- Display codes configuration (state → hex payload)
    display_codes JSONB DEFAULT '{
        "FREE": "0000FFFF00",
        "OCCUPIED": "FF0000FF00",
        "RESERVED": "FF0032FF00",
        "OUT_OF_ORDER": "00FF00FF00",
        "MAINTENANCE": "00FF00FF00"
    }',

    -- LoRaWAN configuration
    fport INTEGER DEFAULT 15,              -- FPort for Kuando
    confirmed_downlinks BOOLEAN DEFAULT FALSE,
    max_payload_size INTEGER DEFAULT 51,

    enabled BOOLEAN DEFAULT TRUE,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Kuando Device Example:**
```json
{
  "display_id": "a1b2c3d4-...",
  "dev_eui": "2020203705250102",
  "display_type": "kuando_busylight",
  "device_model": "Kuando Busylight IoT Omega LoRaWAN",
  "manufacturer": "Kuando",
  "display_codes": {
    "FREE": "0000FFFF00",
    "OCCUPIED": "FF0000FF00",
    "RESERVED": "FF0032FF00",
    "MAINTENANCE": "00FF00FF00"
  },
  "fport": 15,
  "confirmed_downlinks": false,
  "enabled": true
}
```

### Parking Spaces (`parking_spaces.spaces`)

Links sensors and displays to physical parking spaces.

```sql
CREATE TABLE parking_spaces.spaces (
    space_id UUID PRIMARY KEY,
    space_name VARCHAR(100) NOT NULL UNIQUE,  -- "Woki Space A1-002"
    space_code VARCHAR(20),                   -- "A1-002"

    -- Device pairing
    occupancy_sensor_id UUID,
    display_device_id UUID REFERENCES parking_config.display_registry(display_id),

    -- DevEUI denormalized for fast lookup
    occupancy_sensor_deveui VARCHAR(16),      -- "70b3d57ed0067001"
    display_device_deveui VARCHAR(16),        -- "202020410a1c0702"

    -- State tracking
    current_state VARCHAR(20) DEFAULT 'FREE',
    sensor_state VARCHAR(20) DEFAULT 'FREE',
    display_state VARCHAR(20) DEFAULT 'FREE',

    -- Timing
    last_sensor_update TIMESTAMP,
    last_display_update TIMESTAMP,
    state_changed_at TIMESTAMP,

    -- Configuration
    auto_actuation BOOLEAN DEFAULT TRUE,
    reservation_priority BOOLEAN DEFAULT TRUE,

    enabled BOOLEAN DEFAULT TRUE
);
```

### Actuations Log (`parking_operations.actuations`)

Tracks every downlink sent to displays.

```sql
CREATE TABLE parking_operations.actuations (
    actuation_id UUID PRIMARY KEY,
    space_id UUID REFERENCES parking_spaces.spaces(space_id),

    -- State transition
    previous_state VARCHAR(20),
    new_state VARCHAR(20),
    trigger_source VARCHAR(50),  -- 'sensor', 'reservation', 'manual', 'reconciliation'

    -- Downlink details
    display_deveui VARCHAR(16),
    fport INTEGER,
    payload_hex VARCHAR(200),
    downlink_sent BOOLEAN,
    downlink_confirmed BOOLEAN,
    downlink_error TEXT,

    -- Timing
    requested_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    response_time_ms NUMERIC(10,2)
);
```

---

## Kuando Payload Encoding

### Payload Format

Kuando Busylight devices use a **5-byte payload** on **FPort 15**:

```
Byte 0: Red intensity (0-255)
Byte 1: Blue intensity (0-255)
Byte 2: Green intensity (0-255)
Byte 3: On duration (255 = solid, 0-254 = pulsing)
Byte 4: Off duration (0 = no flash, 1-255 = flash interval)
```

**Important:** Color order is **R-B-G**, NOT R-G-B!

### Standard Parking Colors

| State | Color | RGB | Hex Payload | Description |
|-------|-------|-----|-------------|-------------|
| **FREE** | Green | (0, 0, 255) | `0000FFFF00` | Available parking |
| **OCCUPIED** | Red | (255, 0, 0) | `FF0000FF00` | Occupied parking |
| **RESERVED** | Orange | (255, 0, 50) | `FF0032FF00` | Reserved parking |
| **MAINTENANCE** | Blue | (0, 255, 0) | `00FF00FF00` | Under maintenance |
| **OUT_OF_ORDER** | Blue | (0, 255, 0) | `00FF00FF00` | Disabled |

**Additional Colors:**
- **Purple (VIP):** `64B400FF00` - RGB(100, 180, 0)
- **Cyan (EV Charging):** `00FFFFFF00` - RGB(0, 255, 255)
- **Yellow (Warning):** `FF00FFFF00` - RGB(255, 0, 255)
- **Pink (Handicap):** `FF6400FF00` - RGB(255, 100, 0)
- **White (System):** `FFFFFFFF00` - RGB(255, 255, 255)
- **Off:** `000000FF00` - RGB(0, 0, 0)

### Encoding Example

**To display ORANGE (Reserved state):**

```python
# RGB values for orange
red = 255
blue = 0
green = 50
on_time = 255    # Solid (no pulsing)
off_time = 0     # No flashing

# Create 5-byte payload
payload_bytes = bytes([red, blue, green, on_time, off_time])
# Result: b'\xFF\x00\x32\xFF\x00'

# Convert to hex string for API
payload_hex = payload_bytes.hex().upper()
# Result: "FF0032FF00"
```

### Device Configuration

**Kuando Busylight IoT Omega:**
- **Class:** C (always listening, receives downlinks immediately)
- **FPort:** 15 (mandatory for color commands)
- **Confirmed downlinks:** FALSE (not required for Class C)
- **Max payload:** 5 bytes for color commands
- **Response:** Uplink heartbeat on FPort 15 (empty payload)

---

## Complete Message Flow

### Scenario: Parking Space Reserved via API

```
┌──────────────┐
│  REST API    │  POST /spaces/{space_id}/reserve
│   Request    │  {"user_email": "user@example.com", ...}
└──────┬───────┘
       │
       v
┌─────────────────────────────────────────────────────────────────┐
│  Parking Display Service (parking-display:8100)                 │
│                                                                  │
│  1. Create reservation in database                              │
│     INSERT INTO parking_spaces.reservations ...                 │
│                                                                  │
│  2. Query display configuration                                 │
│     SELECT display_codes, fport FROM parking_config.display_registry │
│     WHERE dev_eui = '2020203705250102'                          │
│                                                                  │
│     Returns: {                                                  │
│       "display_codes": {                                        │
│         "RESERVED": "FF0032FF00"                                │
│       },                                                        │
│       "fport": 15                                               │
│     }                                                           │
│                                                                  │
│  3. Create actuation record                                     │
│     INSERT INTO parking_operations.actuations                   │
│     (space_id, new_state, trigger_source, display_deveui)       │
│     VALUES ($1, 'RESERVED', 'reservation', '2020203705250102')  │
│                                                                  │
│  4. Call downlink client                                        │
└──────┬───────────────────────────────────────────────────────────┘
       │ HTTP POST
       │ URL: http://parking-downlink:8000/downlink/send
       │ Body: {
       │   "dev_eui": "2020203705250102",
       │   "fport": 15,
       │   "data": "FF0032FF00",
       │   "confirmed": false
       │ }
       v
┌─────────────────────────────────────────────────────────────────┐
│  Downlink Service (parking-downlink:8000)                       │
│                                                                  │
│  1. Validate payload format                                     │
│     - Check dev_eui is 16-char hex                              │
│     - Check fport is 1-223                                      │
│     - Check data is valid hex or base64                         │
│                                                                  │
│  2. Decode hex payload                                          │
│     data_bytes = bytes.fromhex("FF0032FF00")                    │
│     # Result: b'\xFF\x00\x32\xFF\x00' (5 bytes)                │
│                                                                  │
│  3. Create ChirpStack gRPC request                              │
│     queue_item = api.DeviceQueueItem(                           │
│         dev_eui="2020203705250102",                             │
│         confirmed=False,                                        │
│         f_port=15,                                              │
│         data=b'\xFF\x00\x32\xFF\x00'                            │
│     )                                                           │
│                                                                  │
│  4. Call ChirpStack gRPC API                                    │
└──────┬───────────────────────────────────────────────────────────┘
       │ gRPC Call
       │ Service: api.DeviceServiceStub
       │ Method: Enqueue()
       │ Metadata: Authorization: Bearer <token>
       │ Request: EnqueueDeviceQueueItemRequest{queue_item}
       v
┌─────────────────────────────────────────────────────────────────┐
│  ChirpStack Network Server (parking-chirpstack:8080)            │
│                                                                  │
│  1. Authenticate gRPC request                                   │
│     - Verify Bearer token                                       │
│     - Check device exists                                       │
│                                                                  │
│  2. Validate device configuration                               │
│     - Lookup device in chirpstack.device table                  │
│     - Verify device is Class C                                  │
│     - Check device is not disabled                              │
│                                                                  │
│  3. Queue downlink in database                                  │
│     INSERT INTO chirpstack.device_queue                         │
│     (dev_eui, f_port, data, f_cnt, is_pending, ...)            │
│     VALUES ('2020203705250102', 15, '\xFF\x00\x32\xFF\x00', ...) │
│                                                                  │
│  4. Schedule Class C transmission                               │
│     - Class C devices listen continuously                       │
│     - Downlink sent in next available RX window                 │
│     - Typically transmitted within 1-2 seconds                  │
│                                                                  │
│  5. Return response                                             │
│     response.f_cnt = 42  # Frame counter                        │
└──────┬───────────────────────────────────────────────────────────┘
       │
       │ gRPC Response: EnqueueDeviceQueueItemResponse
       │ {f_cnt: 42}
       │
       v
┌─────────────────────────────────────────────────────────────────┐
│  Downlink Service (parking-downlink:8000)                       │
│                                                                  │
│  Return JSON response:                                          │
│  {                                                              │
│    "status": "queued",                                          │
│    "dev_eui": "2020203705250102",                               │
│    "f_cnt": 42,                                                 │
│    "fport": 15,                                                 │
│    "confirmed": false                                           │
│  }                                                              │
└──────┬───────────────────────────────────────────────────────────┘
       │
       │ HTTP 200 OK
       v
┌─────────────────────────────────────────────────────────────────┐
│  Parking Display Service                                        │
│                                                                  │
│  Update actuation record:                                       │
│  UPDATE parking_operations.actuations                           │
│  SET downlink_sent = TRUE,                                      │
│      sent_at = NOW(),                                           │
│      response_time_ms = 145.2                                   │
│  WHERE actuation_id = ...                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  LoRaWAN Transmission (1-2 seconds later)                       │
│                                                                  │
│  ChirpStack → Gateway → Kuando Device                           │
│  - LoRaWAN MAC payload with application data                    │
│  - FPort: 15                                                    │
│  - Data: FF0032FF00                                             │
│                                                                  │
│  Device decodes and displays ORANGE color:                      │
│  - Red: 255 (FF)                                                │
│  - Blue: 0 (00)                                                 │
│  - Green: 50 (32)                                               │
│  - Solid (no pulsing/flashing)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Specifications

### Downlink Service REST API

**Base URL:** `http://parking-downlink:8000`

#### POST /downlink/send

Send a downlink to a LoRaWAN device.

**Request:**
```json
{
  "dev_eui": "2020203705250102",
  "fport": 15,
  "data": "FF0032FF00",
  "confirmed": false
}
```

**Response (200 OK):**
```json
{
  "status": "queued",
  "dev_eui": "2020203705250102",
  "f_cnt": 42,
  "fport": 15,
  "confirmed": false
}
```

**Error Responses:**
- `400 Bad Request`: Invalid payload format or parameters
- `500 Internal Server Error`: ChirpStack gRPC error

**Payload Format:**
- `data` field accepts:
  - **Hex string:** `"FF0032FF00"` (even-length, 0-9a-fA-F)
  - **Base64:** `"AQIDBA=="` (standard base64 encoding)

---

#### GET /downlink/queue/{dev_eui}

Get pending downlinks for a device.

**Response:**
```json
{
  "dev_eui": "2020203705250102",
  "total_count": 2,
  "items": [
    {
      "f_cnt": 42,
      "fport": 15,
      "confirmed": false,
      "data": "ff0032ff00",
      "is_pending": true
    }
  ]
}
```

---

#### DELETE /downlink/queue/{dev_eui}

Clear all pending downlinks for a device.

**Response:**
```json
{
  "status": "flushed",
  "dev_eui": "2020203705250102"
}
```

---

### ChirpStack gRPC API

The downlink service uses ChirpStack's official gRPC API.

**Protocol:** gRPC (HTTP/2)
**Host:** `parking-chirpstack:8080`
**Authentication:** Bearer token in metadata

**Key Methods Used:**

#### DeviceServiceStub.Enqueue()

**Request:** `EnqueueDeviceQueueItemRequest`
```protobuf
message EnqueueDeviceQueueItemRequest {
  DeviceQueueItem queue_item = 1;
}

message DeviceQueueItem {
  string dev_eui = 1;        // "2020203705250102"
  bool confirmed = 2;         // false
  uint32 f_port = 3;         // 15
  bytes data = 4;            // \xFF\x00\x32\xFF\x00
}
```

**Response:** `EnqueueDeviceQueueItemResponse`
```protobuf
message EnqueueDeviceQueueItemResponse {
  uint32 f_cnt = 1;  // Frame counter (e.g., 42)
}
```

---

## Example Transactions

### Example 1: Send Green (Available) Color

**REST API Call:**
```bash
curl -X POST http://parking-downlink:8000/downlink/send \
  -H "Content-Type: application/json" \
  -d '{
    "dev_eui": "2020203705250102",
    "fport": 15,
    "data": "0000FFFF00",
    "confirmed": false
  }'
```

**Response:**
```json
{
  "status": "queued",
  "dev_eui": "2020203705250102",
  "f_cnt": 43,
  "fport": 15,
  "confirmed": false
}
```

**Result:** Device displays **GREEN** light (RGB: 0, 0, 255)

---

### Example 2: Send Red (Occupied) Color

**Python Code:**
```python
import requests

DOWNLINK_URL = "http://parking-downlink:8000/downlink/send"

# Send red color
response = requests.post(DOWNLINK_URL, json={
    "dev_eui": "2020203705250102",
    "fport": 15,
    "data": "FF0000FF00",  # Red: R=255, B=0, G=0, solid
    "confirmed": False
})

print(response.json())
# {"status": "queued", "dev_eui": "2020203705250102", "f_cnt": 44, ...}
```

---

### Example 3: Parking Display Service Integration

**Full actuation flow:**
```python
# 1. Query display configuration
display = await db.fetchrow("""
    SELECT dev_eui, display_codes, fport, confirmed_downlinks
    FROM parking_config.display_registry
    WHERE dev_eui = $1 AND enabled = TRUE
""", "2020203705250102")

# 2. Get color code for new state
display_codes = display['display_codes']  # {"RESERVED": "FF0032FF00", ...}
color_code = display_codes.get("RESERVED")  # "FF0032FF00"

# 3. Send downlink
downlink_client = DownlinkClient(base_url="http://parking-downlink:8000")
result = await downlink_client.send_downlink(
    dev_eui=display['dev_eui'],
    fport=display['fport'],
    data=color_code,
    confirmed=display['confirmed_downlinks']
)

# 4. Log result
await db.execute("""
    INSERT INTO parking_operations.actuations
    (space_id, new_state, display_deveui, fport, payload_hex, downlink_sent)
    VALUES ($1, $2, $3, $4, $5, $6)
""", space_id, "RESERVED", display['dev_eui'], 15, "FF0032FF00", result['success'])
```

---

## Key Differences from V5

### What V5 Should Implement

1. **Direct ChirpStack Integration**
   - V5 uses `chirpstack_client.py` to call ChirpStack database directly
   - Should use gRPC API like v4 for proper queueing
   - Current V5 implementation may bypass ChirpStack's downlink queue

2. **Display Registry**
   - V4 stored display codes in `parking_config.display_registry` table
   - V5 hardcodes colors in Kuando UI
   - Should migrate display registry to v5 database

3. **Actuation Logging**
   - V4 logged all downlinks in `parking_operations.actuations`
   - V5 has no downlink audit trail
   - Critical for debugging and monitoring

4. **Retry Logic**
   - V4 had exponential backoff retry in `downlink_client.py`
   - V5 should implement similar retry mechanism

5. **Health Monitoring**
   - V4 tracked `response_time_ms` and `downlink_error`
   - V5 needs observability for downlink failures

---

## References

**Source Code Locations (v4):**
- Downlink Service: `/opt/smart-parking-v4-OLD/services/downlink/`
- Parking Display: `/opt/smart-parking-v4-OLD/services/parking-display/`
- Database Schema: `/opt/smart-parking-v4-OLD/database/init/04-parking-display-schema.sql`
- Kuando Colors: `/opt/smart-parking-v4-OLD/KUANDO_COLOR_RESULTS.md`

**ChirpStack Documentation:**
- gRPC API: https://www.chirpstack.io/docs/chirpstack/api/grpc.html
- Device Queue: https://www.chirpstack.io/docs/chirpstack/use/device-queue.html

**Kuando Documentation:**
- Technical Docs: `services/v4_2__Technical-Documentation-kuando-Busylight-IoT-Omega-v4.2.2-HW1.2_1.5.pdf`

---

**Document Maintainer:** Claude Code
**Last Updated:** 2025-10-16
**Version:** 1.0.0
