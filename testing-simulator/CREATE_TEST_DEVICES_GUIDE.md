# Creating Test Devices in ChirpStack UI - Step by Step Guide

## Overview

We'll create **10 test devices** for the simulator:
- **5 parking sensors** (Class A) - Send uplinks when parking state changes
- **5 Kuando Busylights** (Class C) - Receive downlinks to change colors

## Before You Start

1. Open ChirpStack UI: **https://lorawan.verdegris.eu**
2. Login credentials: (you should have these)
3. Have this guide open in another window

---

## Part 1: Create 5 Parking Sensors (Class A)

### Sensor 1

**Step 1:** Navigate to Applications
- Click **Applications** in sidebar
- Click **Class A devices** application

**Step 2:** Add Device
- Click **+ Add Device** button

**Step 3:** Fill Device Information
```
Device name: TESTING Sensor 1
Device description: ⚠️ TESTING ONLY - Simulated parking sensor - Safe to delete
Device EUI: TEST0000SENSOR00
Device profile: Class A 1.0.3 Rev A EU868
```

**Important Options:**
- ✅ Check "Skip frame-counter check" (helpful for testing)
- ✅ Leave "Disable device" unchecked

**Step 4:** Click **Submit**

**Step 5:** Configure Device Keys (OTAA)
- You'll be on the device details page
- Click **Keys (OTAA)** tab
- Click **Set Device Keys**
- Enter or generate AppKey: `00112233445566778899AABBCCDDEEFF`
  - Or click the 🔄 icon to generate random key
- NwkKey will auto-fill (same as AppKey for LoRaWAN 1.0.x)
- Click **Submit**

**Step 6:** Note the AppKey
Write it down or take a screenshot - you'll need it if you want to use real devices later.

---

### Sensors 2-5

Repeat the same steps for:

**Sensor 2:**
```
Device name: TESTING Sensor 2
Device description: ⚠️ TESTING ONLY - Simulated parking sensor - Safe to delete
Device EUI: TEST0001SENSOR00
Device profile: Class A 1.0.3 Rev A EU868
AppKey: 11223344556677889900AABBCCDDEEFF (or generate)
```

**Sensor 3:**
```
Device name: TESTING Sensor 3
Device description: ⚠️ TESTING ONLY - Simulated parking sensor - Safe to delete
Device EUI: TEST0002SENSOR00
Device profile: Class A 1.0.3 Rev A EU868
AppKey: 22334455667788990011AABBCCDDEEFF (or generate)
```

**Sensor 4:**
```
Device name: TESTING Sensor 4
Device description: ⚠️ TESTING ONLY - Simulated parking sensor - Safe to delete
Device EUI: TEST0003SENSOR00
Device profile: Class A 1.0.3 Rev A EU868
AppKey: 33445566778899001122AABBCCDDEEFF (or generate)
```

**Sensor 5:**
```
Device name: TESTING Sensor 5
Device description: ⚠️ TESTING ONLY - Simulated parking sensor - Safe to delete
Device EUI: TEST0004SENSOR00
Device profile: Class A 1.0.3 Rev A EU868
AppKey: 44556677889900112233AABBCCDDEEFF (or generate)
```

---

## Part 2: Create 5 Kuando Busylights (Class C)

### Busylight 1

**Step 1:** Navigate to Class C Application
- Click **Applications** in sidebar
- Click **Class C LED controllers** application

**Step 2:** Add Device
- Click **+ Add Device** button

**Step 3:** Fill Device Information
```
Device name: TESTING Busylight 1
Device description: ⚠️ TESTING ONLY - Simulated Kuando Busylight - Safe to delete
Device EUI: TEST0000BUSYLT00
Device profile: Kuando Busylight
```

**Important Options:**
- ✅ Check "Skip frame-counter check" (helpful for testing)
- ✅ Leave "Disable device" unchecked

**Step 4:** Click **Submit**

**Step 5:** Configure Device Keys (OTAA)
- Click **Keys (OTAA)** tab
- Click **Set Device Keys**
- Enter or generate AppKey: `AABBCCDDEEFF00112233445566778899`
  - Or click the 🔄 icon to generate random key
- NwkKey will auto-fill
- Click **Submit**

---

### Busylights 2-5

Repeat the same steps for:

**Busylight 2:**
```
Device name: TESTING Busylight 2
Device description: ⚠️ TESTING ONLY - Simulated Kuando Busylight - Safe to delete
Device EUI: TEST0001BUSYLT00
Device profile: Kuando Busylight
AppKey: BBCCDDEEFF00112233445566778899AA (or generate)
```

**Busylight 3:**
```
Device name: TESTING Busylight 3
Device description: ⚠️ TESTING ONLY - Simulated Kuando Busylight - Safe to delete
Device EUI: TEST0002BUSYLT00
Device profile: Kuando Busylight
AppKey: CCDDEEFF00112233445566778899AABB (or generate)
```

**Busylight 4:**
```
Device name: TESTING Busylight 4
Device description: ⚠️ TESTING ONLY - Simulated Kuando Busylight - Safe to delete
Device EUI: TEST0003BUSYLT00
Device profile: Kuando Busylight
AppKey: DDEEFF00112233445566778899AABBCC (or generate)
```

**Busylight 5:**
```
Device name: TESTING Busylight 5
Device description: ⚠️ TESTING ONLY - Simulated Kuando Busylight - Safe to delete
Device EUI: TEST0004BUSYLT00
Device profile: Kuando Busylight
AppKey: EEFF00112233445566778899AABBCCDD (or generate)
```

---

## Part 3: Verify Devices Created

### Check Sensors
1. Go to **Applications → Class A devices**
2. You should see 5 devices starting with "TESTING Sensor"
3. All should show as "Never seen" (that's normal - they haven't sent uplinks yet)

### Check Busylights
1. Go to **Applications → Class C LED controllers**
2. You should see 5 devices starting with "TESTING Busylight"
3. All should show as "Never seen" (that's normal)

---

## Part 4: Test with Simulator

Now that devices are registered, test the simulator:

```bash
cd /opt/smart-parking/testing-simulator
sudo venv/bin/python3 test_mqtt_uplink.py
```

### What Should Happen:
1. ✅ MQTT connection succeeds
2. ✅ Uplink sent for TEST0000SENSOR00
3. ✅ Ingest service receives and processes the uplink
4. ✅ Device appears in transform service API

### Verify in Logs:
```bash
# Check ingest service
sudo docker compose logs -f ingest-service

# Should see:
# INFO:parking-detector:Received uplink from TEST0000SENSOR00
```

### Check in ChirpStack UI:
1. Go to the device page for "TESTING Sensor 1"
2. Click **LoRaWAN frames** tab
3. You should see the uplink appear!

---

## Quick Reference - Device List

### Sensors (Class A devices app)
```
TEST0000SENSOR00 - TESTING Sensor 1
TEST0001SENSOR00 - TESTING Sensor 2
TEST0002SENSOR00 - TESTING Sensor 3
TEST0003SENSOR00 - TESTING Sensor 4
TEST0004SENSOR00 - TESTING Sensor 5
```

### Busylights (Class C LED controllers app)
```
TEST0000BUSYLT00 - TESTING Busylight 1
TEST0001BUSYLT00 - TESTING Busylight 2
TEST0002BUSYLT00 - TESTING Busylight 3
TEST0003BUSYLT00 - TESTING Busylight 4
TEST0004BUSYLT00 - TESTING Busylight 5
```

---

## Cleanup When Done

To delete all test devices:

### Option 1: ChirpStack UI
1. Go to each application
2. Select devices with checkboxes
3. Click **Delete selected devices**

### Option 2: Script (TODO)
```bash
cd /opt/smart-parking/testing-simulator
sudo venv/bin/python3 cleanup_test_devices.py
```

---

## Troubleshooting

### "Device EUI already exists"
- Device was created before
- Either delete the old one or use a different DevEUI

### "Device profile not found"
- Make sure you're in the correct application
- Class A sensors → "Class A devices" application
- Busylights → "Class C LED controllers" application

### "Keys not set"
- Go back to the device
- Click **Keys (OTAA)** tab
- Set the keys

### Simulator uplink not processed
- Make sure device exists in ChirpStack
- Check device is not disabled
- Check ingest service logs for errors

---

## Time Estimate

- **5 sensors**: ~10 minutes (2 min each)
- **5 busylights**: ~10 minutes (2 min each)
- **Total**: ~20 minutes

## Tips

- ✅ Use copy/paste for DevEUI to avoid typos
- ✅ The description with ⚠️ emoji helps identify test devices
- ✅ You can generate random AppKeys - you don't need to type them
- ✅ "Skip frame-counter check" is useful for simulation/testing
- ✅ Test after creating the first device before doing all 10

---

**Ready to start?** Open https://lorawan.verdegris.eu and follow Part 1!
