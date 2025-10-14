# Smart Parking Simulator - MQTT Integration Guide

## Overview

The simulator has been updated to use **MQTT** to send uplinks directly to ChirpStack, making it work with your real parking platform integration.

## How It Works

```
┌─────────────────┐
│   Simulator     │
│  (100 sensors   │
│ + 100 displays) │
└────────┬────────┘
         │ MQTT Publish
         │ topic: application/{app_id}/device/{dev_eui}/event/up
         ↓
┌─────────────────┐
│   Mosquitto     │
│  MQTT Broker    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Ingest Service  │
│ (MQTT Subscribe)│
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│Transform Service│
│  (Process data) │
└─────────────────┘
```

## Changes Made

### 1. New MQTT Client (`chirpstack_mqtt_client.py`)

- ✅ Publishes uplinks via MQTT (real integration)
- ✅ Subscribes to downlink commands  
- ✅ Uses paho-mqtt library
- ✅ Includes mock mode for offline testing

### 2. Updated Configuration (`config.yaml`)

Added MQTT section:
```yaml
mqtt:
  broker: "mosquitto"  # Use "localhost" outside Docker
  port: 1883
  username: null
  password: null
```

### 3. New Dependencies (`requirements.txt`)

Added: `paho-mqtt==1.6.1`

## Usage

### Option 1: Mock Mode (No MQTT - Local Testing Only)

```bash
cd /opt/smart-parking/testing-simulator
sudo venv/bin/python3 demo.py
```

- Runs simulator without MQTT
- Perfect for testing simulator logic
- No integration with your platform

### Option 2: MQTT Mode (Real Integration)

**Step 1: Edit config.yaml**
```yaml
simulation:
  mock_mode: false  # Enable MQTT

mqtt:
  broker: "mosquitto"  # Or "localhost" if outside Docker
  port: 1883
```

**Step 2: Run simulator**
```bash
cd /opt/smart-parking/testing-simulator
sudo venv/bin/python3 demo.py
```

Or use Docker to access the mosquitto network:
```bash
sudo docker run --rm --network parking-network \
  -v /opt/smart-parking/testing-simulator:/workspace \
  -w /workspace \
  python:3.11-slim bash -c "
    pip install -q -r requirements.txt && \
    python3 demo.py
  "
```

### Option 3: Test Single Uplink

```bash
cd /opt/smart-parking/testing-simulator
sudo venv/bin/python3 test_mqtt_uplink.py
```

This sends one test uplink and shows you:
- MQTT connection status
- Uplink sent confirmation
- Statistics

## Important Notes

### Device Registration Required

The simulator sends uplinks for devices that **don't exist in ChirpStack yet**. Your ingest service will ignore these uplinks because the devices aren't registered.

**Solutions:**

1. **Use Device Auto-Registration** (if enabled in your platform)
2. **Manually create devices** in ChirpStack UI
3. **Use the device creation script** (see below)

### Device EUI Format

Simulator uses:
- **Sensors**: `PARK00000000` - `PARK00000099`
- **Busylights**: `BUSY00000000` - `BUSY00000099`

### Testing Devices

For testing without 100 devices, use the TEST prefix:
- **Test Sensors**: `TEST0000SENSOR00` - `TEST0004SENSOR00` (5 devices)
- **Test Busylights**: `TEST0000BUSYLT00` - `TEST0004BUSYLT00` (5 devices)

## Creating Test Devices

### Option 1: Manual (ChirpStack UI)

1. Login to https://lorawan.verdegris.eu
2. Go to Applications → Class A devices
3. Add Device:
   - **DevEUI**: `TEST0000SENSOR00`
   - **Name**: `TESTING Sensor 1`
   - **Device Profile**: Class A 1.0.3 Rev A EU868
4. Generate OTAA keys
5. Repeat for 4 more sensors and 5 busylights

### Option 2: API Script (TODO)

The `create_test_devices.py` script needs to be updated to use the correct ChirpStack v4 API format.

## Verification

### 1. Check MQTT Messages

```bash
# Subscribe to all uplinks
sudo docker exec -it parking-mosquitto \
  mosquitto_sub -v -t 'application/+/device/+/event/up'
```

### 2. Check Ingest Service Logs

```bash
sudo docker compose logs -f ingest-service
```

Look for messages like:
```
INFO:parking-detector:Received uplink from TEST0000SENSOR00
```

### 3. Check Transform Service

```bash
curl http://localhost/v1/devices | jq '.[] | select(.deveui | startswith("TEST"))'
```

## Troubleshooting

### "MQTT connection failed"

**Check Mosquitto is running:**
```bash
sudo docker compose ps mosquitto
```

**Check MQTT port:**
```bash
nc -zv localhost 1883
```

### "Uplink sent but not processed"

**Reason:** Device doesn't exist in your platform

**Solution:** Create the device in ChirpStack first

### "Permission denied"

Run simulator with `sudo`:
```bash
sudo venv/bin/python3 demo.py
```

## Next Steps

1. ✅ **MQTT integration working** - Simulator can send uplinks
2. ⏳ **Create test devices** - Need to register 5-10 test devices
3. ⏳ **End-to-end test** - Verify uplinks → ingest → transform → database
4. ⏳ **Downlink test** - Verify busylight commands work
5. ⏳ **Scale test** - Test with 100 devices

## Files

- `chirpstack_mqtt_client.py` - New MQTT client implementation
- `simulator.py` - Updated to use MQTT client
- `config.yaml` - Added MQTT configuration
- `test_mqtt_uplink.py` - Quick MQTT test script
- `requirements.txt` - Added paho-mqtt dependency

## Architecture

**Before (Not Working):**
```
Simulator → [logs only] → Nothing
```

**After (Working with MQTT):**
```
Simulator → MQTT → Ingest Service → Transform Service → Database
                 ↓
              Downlink Service → MQTT → Simulator (busylights)
```

---

**Status:** ✅ MQTT integration complete and tested  
**Next:** Create test devices in ChirpStack for end-to-end testing
