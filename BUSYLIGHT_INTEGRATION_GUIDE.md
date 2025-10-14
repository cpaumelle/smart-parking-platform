# Kuando Busylight IoT LoRaWAN Integration Guide

## Smart Parking Solution with ChirpStack

**Document Version:** 2.0  
**Last Updated:** October 2025  
**Based on:** Firmware 5.8+, Hardware 1.2+, v4.0.3 Technical Documentation

---

## Device Overview

**Product:** Kuando Busylight IoT Omega LoRaWAN  
**Class:** Class C LoRaWAN Device  
**Use Case:** Visual parking availability indicator

### Key Specifications

- **LoRaWAN Class:** C (continuous receive windows for immediate downlinks)
- **Frequency Bands:** EU863-870, US902-928, AU915-928 MHz
- **MAC Version:** 1.0.3
- **Regional Parameters:** Revision B
- **FPort:** 15 (for all color commands and control)
- **LED:** Multi-color RGB with customizable brightness and flashing
- **Visibility:** 360-degree
- **Power:** USB powered (3m/9ft cord with adapter included)
- **Certifications:** CE, FCC, RCM, RoHS

### Why Class C is Perfect for Parking

Class C devices keep their receive windows open continuously (except when transmitting), enabling:

- **Immediate response** to parking occupancy changes
- **Real-time visual feedback** without waiting for uplink windows
- No latency between sensor detection and light update
- Ideal for user-facing applications where instant feedback matters

---

## Payload Format

### Downlink Payload Structure (5-6 bytes)

The Busylight accepts a **5-byte or 6-byte payload** on **FPort 15**:

```
Byte 0: Red (0-255)
Byte 1: Blue (0-255)
Byte 2: Green (0-255)
Byte 3: On-time (0-255, in 1/10 second units)
Byte 4: Off-time (0-255, in 1/10 second units)
Byte 5: [Optional] Auto-reply trigger (0x01)
```

**⚠️ IMPORTANT - Firmware 5.8+ Byte Order:**
- Byte 0 = Red
- Byte 1 = **Blue** (swapped from earlier firmware)
- Byte 2 = **Green** (swapped from earlier firmware)

### Timing Explanation

- **Byte 3 & 4:** Control blinking pattern in **1/10 second units**
  - Value of **10** = 1 second
  - Value of **255** = 25.5 seconds (maximum)
  - Value of **0** = minimum duration
- **Solid light:** Set on-time=255, off-time=0
- **Blinking (1 sec on/off):** Set on-time=10, off-time=10

### Optional 6th Byte (Firmware 5.8+)

Adding a 6th byte `0x01` triggers an automatic uplink reply after the device processes the downlink. Useful for confirmation.

```
Example: 00 FF 00 FF 00 01
         ^  ^  ^  ^  ^  ^
         R  B  G  On Of Reply
```

### Payload Examples

#### Solid Green (Parking Available)

```
Hex: 00 64 00 FF 00
RGB: (0, 100, 0)
Pattern: Solid (on=255, off=0)
```

#### Solid Red (Parking Occupied)

```
Hex: 64 00 00 FF 00
RGB: (100, 0, 0)
Pattern: Solid (on=255, off=0)
```

#### Solid Orange (Almost Full / Reserved)

```
Hex: FF A5 00 FF 00
RGB: (255, 165, 0)
Pattern: Solid (on=255, off=0)
```

#### Blinking Orange (Expiring Soon)

```
Hex: FF A5 00 7F 7F
RGB: (255, 165, 0)
Pattern: Blinking (on=127, off=127)
```

#### Solid Blue (Disabled/Maintenance)

```
Hex: 00 00 64 FF 00
RGB: (0, 0, 100)
Pattern: Solid (on=255, off=0)
```

#### White (System Active/Testing)

```
Hex: FF FF FF FF 00
RGB: (255, 255, 255)
Pattern: Solid (on=255, off=0)
```

#### Off

```
Hex: FF FF FF 00 FF
RGB: (255, 255, 255)
On-time: 0, Off-time: 255
```

---

## Parking Color Scheme Recommendations

### Simple 2-State System

| Status | Color | Payload (Hex) | Description |
| --- | --- | --- | --- |
| Available | Green | `00 64 00 FF 00` | Spot is free |
| Occupied | Red | `64 00 00 FF 00` | Spot is taken |

### Enhanced 4-State System

| Status | Color | Payload (Hex) | Description |
| --- | --- | --- | --- |
| Available | Green | `00 64 00 FF 00` | Spot is free |
| Occupied | Red | `64 00 00 FF 00` | Spot is taken |
| Reserved | Orange | `FF A5 00 FF 00` | Spot is reserved |
| Disabled | Blue | `00 00 64 FF 00` | Out of service |

### Advanced 6-State System with Alerts

| Status | Color | Payload (Hex) | Description |
| --- | --- | --- | --- |
| Available | Green | `00 64 00 FF 00` | Spot is free |
| Occupied | Red | `64 00 00 FF 00` | Spot is taken |
| Reserved | Solid Orange | `FF A5 00 FF 00` | Spot is reserved |
| Expiring Soon | Blinking Orange | `FF A5 00 7F 7F` | Reservation ending |
| Maintenance | Blue | `00 00 64 FF 00` | Under maintenance |
| Unknown | Blinking White | `FF FF FF 7F 7F` | Sensor issue |

---

## ChirpStack Integration

### 1. Device Registration

#### Create Device Profile

Navigate to: **Device Profiles** → **Add device profile**

**Settings:**

- **Name:** `Busylight-Parking-ClassC`
- **LoRaWAN MAC version:** 1.0.3
- **Regional parameters revision:** B
- **Device class:** **Class-C**
- **Supports OTAA:** Yes (recommended)
- **RX2 data rate:** 3 (or as per regional plan)
- **RX2 frequency:** As per regional plan
- **Class-C timeout:** 5 seconds (for confirmed downlinks)

#### Add Device to Application

Navigate to: **Applications** → **[Your Parking App]** → **Devices** → **Add device**

**Device Information:**

- **Device name:** `Parking-Spot-A1-Light` (use your naming convention)
- **Device description:** `Visual indicator for parking spot A1`
- **Device profile:** Select `Busylight-Parking-ClassC`

**LoRaWAN Credentials** (from leaflet in box):

- **DevEUI:** 16-digit hex from device leaflet
- **AppEUI/JoinEUI:** 16-digit hex from device leaflet
- **AppKey:** 32-digit hex from device leaflet

**Important:** The Busylight **automatically sends JOIN requests** when powered on. Simply:

1. Register the device in ChirpStack first
2. Plug in the USB power adapter
3. Device will join within seconds
4. Check the "Events" tab to confirm join-accept

---

### 2. Testing the Integration

#### Initial Test: Turn Light White

After the device joins, test Class C downlink:

1. Navigate to device → **Queue** tab
2. Enter payload: `FF FF FF FF 00` (white, solid)
3. **FPort:** 15
4. Click **Enqueue**
5. Light should change **immediately** (within 1-5 seconds)

#### Verify Device is Sending Status

Check the **Events** tab - you should see periodic uplinks containing:

```json
{
  "RSSI": -78,
  "SNR": 37,
  "lastcolor_red": 255,
  "lastcolor_green": 255,
  "lastcolor_blue": 255,
  "lastcolor_ontime": 255,
  "lastcolor_offtime": 0,
  "messages_received": 1,
  "messages_send": 1
}
```

---

### 3. Integration Methods

ChirpStack supports multiple ways to send downlinks to the Busylight:

#### A. HTTP API (Recommended for Applications)

**Endpoint:**

```
POST https://your-chirpstack-server/api/devices/{devEUI}/queue
```

**Headers:**

```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Body:**

```json
{
  "queueItem": {
    "confirmed": false,
    "fPort": 15,
    "data": "AABkAAD/AA=="
  }
}
```

Note: `data` must be **base64 encoded**

#### B. MQTT Integration

**Topic:**

```
application/{application_id}/device/{devEUI}/command/down
```

**Payload:**

```json
{
  "devEui": "YOUR_DEVICE_EUI",
  "confirmed": false,
  "fPort": 15,
  "data": "AABkAAD/AA=="
}
```

#### C. gRPC API

For high-performance applications, use ChirpStack's gRPC API directly.

---

## Implementation Examples

### Python Implementation

```python
import requests
import base64
from typing import Tuple

class BusylightController:
    """Control Kuando Busylight via ChirpStack API"""

    def __init__(self, chirpstack_url: str, api_key: str):
        self.base_url = chirpstack_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def create_payload(self, red: int, blue: int, green: int,
                       ontime: int = 255, offtime: int = 0,
                       auto_reply: bool = False) -> str:
        """
        Create base64 encoded payload for Busylight (Firmware 5.8+)

        ⚠️ IMPORTANT: Byte order is R-B-G (Blue and Green swapped vs older firmware)

        Args:
            red: 0-255
            blue: 0-255
            green: 0-255
            ontime: 0-255 (in 1/10 second units, 255 = 25.5 sec solid)
            offtime: 0-255 (in 1/10 second units, 0 = no off time)
            auto_reply: If True, adds 6th byte to trigger uplink confirmation

        Returns:
            Base64 encoded payload string
        """
        if auto_reply:
            payload = bytes([red, blue, green, ontime, offtime, 0x01])
        else:
            payload = bytes([red, blue, green, ontime, offtime])
        return base64.b64encode(payload).decode('utf-8')

    def send_downlink(self, dev_eui: str, payload_b64: str, 
                     confirmed: bool = False) -> dict:
        """
        Send downlink to device

        Args:
            dev_eui: Device EUI (16 hex characters)
            payload_b64: Base64 encoded payload
            confirmed: Whether to request ACK

        Returns:
            API response
        """
        url = f"{self.base_url}/api/devices/{dev_eui}/queue"
        data = {
            "queueItem": {
                "confirmed": confirmed,
                "fPort": 15,
                "data": payload_b64
            }
        }

        response = requests.post(url, json=data, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def set_color(self, dev_eui: str, red: int, blue: int, green: int,
                  solid: bool = True, auto_reply: bool = False) -> dict:
        """
        Set Busylight to a specific color

        Args:
            dev_eui: Device EUI
            red: 0-255
            green: 0-255  
            blue: 0-255
            solid: True for solid, False for blinking

        Returns:
            API response
        """
        if solid:
            payload = self.create_payload(red, blue, green, 255, 0, auto_reply)
        else:
            # Blinking: 1 second on, 1 second off (10 = 1 sec in 1/10 units)
            payload = self.create_payload(red, blue, green, 10, 10, auto_reply)

        return self.send_downlink(dev_eui, payload)

    # Predefined parking colors
    def set_available(self, dev_eui: str) -> dict:
        """Green - Parking available"""
        return self.set_color(dev_eui, red=0, blue=0, green=100)

    def set_occupied(self, dev_eui: str) -> dict:
        """Red - Parking occupied"""
        return self.set_color(dev_eui, red=100, blue=0, green=0)

    def set_reserved(self, dev_eui: str) -> dict:
        """Orange - Parking reserved"""
        return self.set_color(dev_eui, red=255, blue=0, green=165)

    def set_expiring_soon(self, dev_eui: str) -> dict:
        """Blinking Orange - Reservation expiring"""
        return self.set_color(dev_eui, red=255, blue=0, green=165, solid=False)

    def set_maintenance(self, dev_eui: str) -> dict:
        """Blue - Under maintenance"""
        return self.set_color(dev_eui, red=0, blue=100, green=0)

    def set_off(self, dev_eui: str) -> dict:
        """Turn off the light"""
        payload = self.create_payload(255, 255, 255, 0, 255)
        return self.send_downlink(dev_eui, payload)


# Usage example
if __name__ == "__main__":
    # Initialize controller
    controller = BusylightController(
        chirpstack_url="https://your-chirpstack-server.com",
        api_key="YOUR_API_KEY_HERE"
    )

    # Device EUI from your Busylight
    SPOT_A1_DEV_EUI = "70b3d57ed0012345"

    # Set parking spot to available (green)
    controller.set_available(SPOT_A1_DEV_EUI)

    # Set to occupied (red)
    controller.set_occupied(SPOT_A1_DEV_EUI)

    # Set to reserved (orange)
    controller.set_reserved(SPOT_A1_DEV_EUI)
```

---

### Node.js Implementation

```javascript
const axios = require('axios');

class BusylightController {
    constructor(chirpstackUrl, apiKey) {
        this.baseUrl = chirpstackUrl.replace(/\/$/, '');
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    /**
     * Create base64 encoded payload
     */
    createPayload(red, blue, green, ontime = 255, offtime = 0, autoReply = false) {
        const bytes = autoReply
            ? [red, blue, green, ontime, offtime, 0x01]
            : [red, blue, green, ontime, offtime];
        const buffer = Buffer.from(bytes);
        return buffer.toString('base64');
    }

    /**
     * Send downlink to device
     */
    async sendDownlink(devEui, payloadB64, confirmed = false) {
        const url = `${this.baseUrl}/api/devices/${devEui}/queue`;
        const data = {
            queueItem: {
                confirmed: confirmed,
                fPort: 15,
                data: payloadB64
            }
        };

        const response = await axios.post(url, data, { headers: this.headers });
        return response.data;
    }

    /**
     * Set color
     */
    async setColor(devEui, red, blue, green, solid = true, autoReply = false) {
        const payload = solid
            ? this.createPayload(red, blue, green, 255, 0, autoReply)
            : this.createPayload(red, blue, green, 10, 10, autoReply);

        return await this.sendDownlink(devEui, payload);
    }

    // Parking-specific methods
    async setAvailable(devEui) {
        return await this.setColor(devEui, 0, 0, 100);
    }

    async setOccupied(devEui) {
        return await this.setColor(devEui, 100, 0, 0);
    }

    async setReserved(devEui) {
        return await this.setColor(devEui, 255, 0, 165);
    }

    async setExpiringSoon(devEui) {
        return await this.setColor(devEui, 255, 0, 165, false);
    }

    async setMaintenance(devEui) {
        return await this.setColor(devEui, 0, 100, 0);
    }

    async setOff(devEui) {
        const payload = this.createPayload(255, 255, 255, 0, 255);
        return await this.sendDownlink(devEui, payload);
    }
}

// Usage
const controller = new BusylightController(
    'https://your-chirpstack-server.com',
    'YOUR_API_KEY'
);

const DEVICE_EUI = '70b3d57ed0012345';

// Set to available
controller.setAvailable(DEVICE_EUI)
    .then(() => console.log('Light set to green (available)'))
    .catch(err => console.error('Error:', err));
```

---

### Integration with Parking Sensors

```python
"""
Example: Integrate ultrasonic parking sensor with Busylight
"""
import time
from busylight_controller import BusylightController

class ParkingSpot:
    def __init__(self, spot_id: str, sensor_dev_eui: str, 
                 light_dev_eui: str, controller: BusylightController):
        self.spot_id = spot_id
        self.sensor_dev_eui = sensor_dev_eui
        self.light_dev_eui = light_dev_eui
        self.controller = controller
        self.current_state = None

    def update_from_sensor(self, sensor_data: dict):
        """
        Update light based on sensor reading

        sensor_data format:
        {
            "occupied": true/false,
            "distance_cm": 50,
            "confidence": 95
        }
        """
        occupied = sensor_data.get('occupied', False)

        if occupied and self.current_state != 'occupied':
            print(f"Spot {self.spot_id}: Occupied detected")
            self.controller.set_occupied(self.light_dev_eui)
            self.current_state = 'occupied'

        elif not occupied and self.current_state != 'available':
            print(f"Spot {self.spot_id}: Available detected")
            self.controller.set_available(self.light_dev_eui)
            self.current_state = 'available'


class ParkingLotController:
    """Manage multiple parking spots"""

    def __init__(self, chirpstack_url: str, api_key: str):
        self.controller = BusylightController(chirpstack_url, api_key)
        self.spots = {}

    def add_spot(self, spot_id: str, sensor_dev_eui: str, 
                 light_dev_eui: str):
        """Register a parking spot"""
        spot = ParkingSpot(spot_id, sensor_dev_eui, 
                          light_dev_eui, self.controller)
        self.spots[spot_id] = spot
        # Initialize to available
        self.controller.set_available(light_dev_eui)

    def handle_sensor_uplink(self, dev_eui: str, data: dict):
        """Handle incoming sensor data"""
        # Find which spot this sensor belongs to
        for spot in self.spots.values():
            if spot.sensor_dev_eui == dev_eui:
                spot.update_from_sensor(data)
                break

    def set_all_maintenance(self):
        """Set all lights to maintenance mode"""
        for spot in self.spots.values():
            self.controller.set_maintenance(spot.light_dev_eui)
            time.sleep(0.5)  # Avoid flooding

    def get_availability_summary(self) -> dict:
        """Get summary of parking lot status"""
        available = sum(1 for s in self.spots.values() 
                       if s.current_state == 'available')
        occupied = sum(1 for s in self.spots.values() 
                      if s.current_state == 'occupied')

        return {
            'total_spots': len(self.spots),
            'available': available,
            'occupied': occupied,
            'spots': {sid: s.current_state 
                     for sid, s in self.spots.items()}
        }


# Example usage
if __name__ == "__main__":
    lot = ParkingLotController(
        chirpstack_url="https://your-server.com",
        api_key="YOUR_KEY"
    )

    # Register spots
    lot.add_spot("A1", 
                 sensor_dev_eui="sensor_eui_1",
                 light_dev_eui="light_eui_1")

    lot.add_spot("A2",
                 sensor_dev_eui="sensor_eui_2", 
                 light_dev_eui="light_eui_2")

    # Simulate sensor updates
    lot.handle_sensor_uplink("sensor_eui_1", {
        "occupied": True,
        "distance_cm": 45,
        "confidence": 98
    })

    # Get status
    status = lot.get_availability_summary()
    print(f"Available spots: {status['available']}/{status['total_spots']}")
```

---

## MQTT Integration Example

For real-time updates using MQTT:

```python
import paho.mqtt.client as mqtt
import json
import base64

class BusylightMQTT:
    def __init__(self, broker_host: str, broker_port: int, 
                 username: str, password: str, application_id: str):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.application_id = application_id

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(broker_host, broker_port, 60)

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected with result code {rc}")
        # Subscribe to uplink messages
        topic = f"application/{self.application_id}/device/+/event/up"
        client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        """Handle incoming sensor messages"""
        payload = json.loads(msg.payload.decode())
        dev_eui = payload.get('devEui')

        # Process uplink and send appropriate downlink
        print(f"Received from {dev_eui}: {payload}")

    def send_color(self, dev_eui: str, red: int, blue: int, green: int):
        """Send color command via MQTT (Firmware 5.8+ byte order: R-B-G)"""
        payload_bytes = bytes([red, blue, green, 255, 0])
        payload_b64 = base64.b64encode(payload_bytes).decode()

        message = {
            "devEui": dev_eui,
            "confirmed": False,
            "fPort": 15,
            "data": payload_b64
        }

        topic = f"application/{self.application_id}/device/{dev_eui}/command/down"
        self.client.publish(topic, json.dumps(message))

    def start(self):
        self.client.loop_forever()
```

---

## Best Practices

### 1. Downlink Queuing Strategy

- **Class C devices** receive downlinks almost immediately
- ChirpStack queues messages FIFO (First In, First Out)
- **Avoid flooding:** Wait 5+ seconds between messages to same device
- Use **unconfirmed downlinks** for status updates (faster)
- Use **confirmed downlinks** for critical operations (slower, needs ACK)

### 2. Color Brightness

- Use **moderate values** (0-100) for better visibility
- **Full brightness (255)** can be harsh indoors
- Consider ambient lighting conditions
- Test different values on-site

### 3. Power Considerations

- Device requires **continuous USB power**
- Plan for power redundancy in critical spots
- Consider UPS for gateway and power adapters
- Monitor gateway connectivity

### 4. Network Planning

- **Range:** ~100m indoors (varies with construction)
- **Gateway placement:** One per floor recommended
- **Class C power usage:** Higher than Class A (always listening)
- Plan for 5-10 devices per gateway (conservative)

### 5. Error Handling

```python
def safe_update_light(controller, dev_eui, color_func):
    """Safely update light with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            color_func(dev_eui)
            return True
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return False
```

---

## Troubleshooting

### Light Not Responding

1. **Check device joined:** Look for join-accept in Events tab
2. **Verify Class C:** Check device profile configuration
3. **Check gateway connectivity:** Ensure gateway online
4. **Verify payload format:** Must be 5 bytes, FPort 15
5. **Check base64 encoding:** Ensure payload is properly encoded

### Delayed Updates

1. **Class A mode:** Device might not be in Class C
2. **Gateway congestion:** Too many devices
3. **Poor signal:** Check RSSI/SNR in uplinks
4. **Queue backup:** Clear old downlinks

### Inconsistent Colors

1. **Multiple controllers:** Ensure no conflicts
2. **Rapid updates:** Add delays between commands
3. **Check current state:** Read device uplinks
4. **Power cycle:** Unplug and replug device

---

## Advanced: Device Commands

The Busylight also supports **2-byte control commands** on FPort 15:

### Set Uplink Interval

```
Byte 0: 0x04 (command)
Byte 1: interval in minutes (e.g., 0x0A = 10 minutes)
```

Example: Set 10-minute interval

```
Payload: 04 0A
Base64: BAo=
```

---

## Security Considerations

1. **API Key Management**
  
  - Store API keys securely (environment variables/secrets manager)
  - Use separate keys for dev/prod
  - Rotate keys regularly
2. **Device Security**
  
  - Keep DevEUI/AppKey confidential
  - Store credentials encrypted
  - Limit API access by IP if possible
3. **Network Security**
  
  - Use HTTPS for ChirpStack API
  - Enable TLS for MQTT if available
  - Monitor for unusual downlink patterns

---

## Monitoring and Metrics

Track these metrics for your deployment:

- **Join success rate** (should be >95%)
- **Downlink delivery time** (Class C: <5s typical)
- **Light response time** (user-perceived latency)
- **Gateway duty cycle** (stay under regional limits)
- **Sensor-to-light sync accuracy**

---

## Summary

The Kuando Busylight IoT is an excellent Class C display device for parking solutions:

✅ **Immediate response** via Class C downlinks  
✅ **Simple 5-byte payload** for color control  
✅ **Auto-join on power-up** for easy deployment  
✅ **360° visibility** for clear status indication  
✅ **Proven in production** (meeting rooms, parking, desks)

**Next Steps:**

1. Order devices (ensure correct frequency band)
2. Set up ChirpStack device profiles
3. Test with single device
4. Deploy and integrate with parking sensors
5. Monitor and optimize

---

**Document Version:** 2.0  
**Last Updated:** October 2025  
**Based on:** v4.0.3 Technical Documentation (Firmware 5.8, Hardware 1.2)  
**For Support:** support@plenom.com or busylight.com/support
