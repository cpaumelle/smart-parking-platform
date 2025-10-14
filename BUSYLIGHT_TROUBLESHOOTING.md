# Kuando Busylight LoRaWAN Troubleshooting Guide

## Common Issues, Fixes, and Community Solutions

**Version:** 2.0  
**Last Updated:** October 2025  
**Based on:** Real-world deployments, community forums, and official documentation

---

## Table of Contents

1. [JOIN Problems](#join-problems)
2. [Connection Stability Issues](#connection-stability-issues)
3. [Class C Downlink Delays](#class-c-downlink-delays)
4. [EU868-Specific Issues](#eu868-specific-issues)
5. [Configuration Best Practices](#configuration-best-practices)
6. [Firmware and Device Behavior](#firmware-and-device-behavior)
7. [Advanced Diagnostics](#advanced-diagnostics)
8. [Community-Sourced Workarounds](#community-sourced-workarounds)

---

## JOIN Problems

### Issue 1: Device Stuck on Yellow Light (Join Loop)

**Symptoms:**

- Device starts with white blink
- Turns soft yellow and stays yellow
- Never turns green (joined state)
- Join requests visible in gateway but no join-accept

**LED Behavior Reference** (from official documentation):

- **White blink** → Device starting up
- **Soft yellow** → Attempting to join (sending JoinRequests)
- **Soft green** → Successfully joined network
- **Stays yellow** → Unable to join

**Root Causes & Solutions:**

#### 1.1 Credential Mismatch

**Problem:** DevEUI, AppEUI, or AppKey don't match between device and server

**Solution:**

```bash
# Double-check all credentials match EXACTLY
Device Leaflet:
- DevEUI: [16 hex digits] 
- AppEUI/JoinEUI: [16 hex digits]
- AppKey: [32 hex digits]

ChirpStack Server:
- Must match character-for-character
- Case-insensitive for hex, but verify anyway
- No spaces, no dashes
- Default AppEUI: 70B3D57ED1000000
```

**Verification Steps:**

1. View leaflet in device box
2. Compare with ChirpStack device configuration
3. Re-enter credentials if uncertain
4. Power cycle device (unplug 30 seconds, replug)

#### 1.2 Device Registered AFTER Powering On

**Problem:** Device tried to join before being registered in ChirpStack

**Solution:**

```
CORRECT ORDER:
1. Register device in ChirpStack first
2. Power cycle gateway (ensure it's listening)
3. Then plug in Busylight USB power
4. Watch Events tab for join

INCORRECT ORDER (causes issues):
1. Plug in device first
2. Register later
→ Device may give up after failed attempts
```

**Fix:** Unplug device, wait 30 seconds, replug

#### 1.3 Wrong Device Class Configuration

**Problem:** Device profile not set to Class C

**Solution:**

```
ChirpStack Device Profile Must Have:
☑ Device supports Class-C: ENABLED
☑ LoRaWAN MAC version: 1.0.2 or 1.0.3
☑ Regional parameters revision: B
☑ Supports OTAA: YES
```

#### 1.4 Wrong Frequency Plan

**Problem:** Gateway and device on different frequency bands

**Solution:**

```
EU868 Busylight:
- Device Profile Region: EU868
- Gateway configured for: EU868
- RX2 Frequency: 869.525 MHz
- RX2 Data Rate: 0 (SF12/125kHz)

US915 Busylight:
- Device Profile Region: US915
- Gateway configured for: US915  
- RX2 Data Rate: 2

Verify device box matches gateway region!
```

#### 1.5 DevNonce Replay Issue

**Problem:** Device reusing DevNonce after power cycle

**From Community:**

> "The join-server stores the Dev-Nonce. According to LoRaWAN spec, an end node cannot use the same Dev-Nonce it has used previously. The join-server will simply reject that."

**Solution:**

```bash
# In ChirpStack, flush DevNonce history
# Device Dashboard → Actions → Flush DevNonce queue

# Or via API:
POST /api/devices/{devEUI}/flush-dev-nonces

# Then power cycle device
```

**Prevention:** Busylight should have persistent DevNonce counter, but if repeatedly failing:

- Check if firmware is properly storing state
- Contact Plenom support for firmware update

---

### Issue 2: EU868 Duty Cycle Collision During Mass Join

**Symptoms:**

- Multiple devices being deployed simultaneously
- Some devices join quickly, others stuck in yellow
- Join-accepts being delayed or dropped

**Official Warning** (from Plenom documentation):

> "PLEASE NOTE for EU: If many devices are started within short time, there is a risk for duty cycle on join accept. It might take longer time for all to join, but device will keep requesting until join is accepted."

**Root Cause:**
EU868 has strict **1% duty cycle** limits. When deploying multiple Busylights:

- Gateway must space join-accept messages
- 10+ devices joining simultaneously can saturate duty cycle
- Gateway may drop join-accepts to stay within limits

**Solutions:**

#### 2.1 Staggered Deployment

```
Deploy devices in batches:
- Batch 1: 5 devices → wait 2 minutes
- Batch 2: 5 devices → wait 2 minutes
- Batch 3: 5 devices → continue...

This prevents duty cycle saturation
```

#### 2.2 Increase RX2 Data Rate (Advanced)

**From Plenom Official Recommendations:**

```toml
# Recommended NS Settings for EU868:
RX2 Data-Rate: 4 or 5 (instead of default 0)
# Higher DR = faster transmission = less airtime
# Helps with duty cycle management
```

**ChirpStack Configuration:**

```toml
# In device profile:
rx2_dr = 4  # Instead of 0
rx2_frequency = 869525000  # 869.525 MHz

# RX2 at 869.525 MHz has 10% duty cycle
# Much better than 1% on other channels
```

#### 2.3 Be Patient

- Device will **keep trying** until joined
- Official doc confirms: "device will keep requesting until join is accepted"
- Can take **5-15 minutes** if many devices joining
- Yellow light is normal during this period

---

### Issue 3: US915/AU915 Join Delays

**Symptoms:**

- US915 or AU915 device
- Join takes 5-30 minutes
- Eventually succeeds but very slow

**Official Warning** (from Plenom documentation):

> "PLEASE NOTE for US and AU: As the LoRaWAN band for US and AUS include 64 upstream channels it might take some time before the devices hits a frequency an 8-channel gateway is listening on."

**Root Cause:**

- US915/AU915 have **64 uplink channels**
- Most gateways only listen on **8 channels**
- Device randomly selects channels
- May take many attempts to hit a gateway-monitored channel

**Solutions:**

#### 3.1 Use 16-Channel Gateway

- Doubles the probability of hitting correct channel
- Reduces join time by ~50%

#### 3.2 Configure Channel Mask (Advanced)

**From Plenom Recommendations:**

```toml
# Recommended Settings:
US915:
- RX2 Data-Rate: 2
- Default channel mask: 8-channel
- Channels: SubBand 2 (recommended)

AU915:
- RX2 Data-Rate: 4
- Default channel mask: 8-channel
```

**ChirpStack Sub-Band Configuration:**

```bash
# For US915, common sub-bands:
# Sub-band 2: Channels 8-15 (most popular on TTN)
# Configure in gateway and device profile
```

#### 3.3 Expect Longer Join Times

- **Normal**: 2-10 minutes for US915/AU915
- **With 8-ch gateway**: Up to 30 minutes possible
- Device will eventually succeed
- This is a limitation of the frequency plan, not the device

---

## Connection Stability Issues

### Issue 4: Device Disconnects After Hours/Days

**Symptoms:**

- Device joins successfully (green light)
- Works fine for hours or days
- Suddenly stops responding to downlinks
- No uplinks received
- Must be power-cycled to reconnect

**Root Causes & Solutions:**

#### 4.1 ADR Convergence Issues

**Problem:** Adaptive Data Rate causes device to use incompatible parameters

**From Official Recommendations:**

```toml
# Plenom recommends DISABLING ADR on server side:
ADR: Disabled on server side

# Why? Busylight is:
- Stationary (not moving)
- USB powered (no battery concerns)
- Indoor installation (stable RF environment)
- ADR adds complexity without benefit
```

**ChirpStack Fix:**

```toml
# In device profile:
supports_adr = false

# Or in chirpstack.toml:
[network]
mac_commands_disabled = false
# But disable ADR via device profile
```

**Alternative:** If ADR must be enabled:

```python
# Set ADR parameters conservatively
# In device profile:
adr_algorithm_id = "default"
min_dr = 0
max_dr = 5  # Don't let it go too high
```

#### 4.2 Lost Downlink Sync (RX Window Drift)

**Community Finding:**

> "The device's RX1 and RX2 reception parameters become out of sync with the network server" - MachineQ

**Symptoms:**

- Device sending uplinks (visible in gateway)
- Server sending downlinks (visible in queue)
- Device not receiving downlinks
- Class C window not open

**Solution: Link Check Request**

```python
# Force device to verify connectivity
# Send LinkCheckReq MAC command

# Downlink payload (FPort 0):
# Command: 0x02 (LinkCheckReq)
payload = bytes([0x02])

# Device will respond with signal quality
# This re-syncs RX windows
```

**Prevention:**

```toml
# In ChirpStack configuration:
# Reduce class_c_lock_duration
class_c_lock_duration = "2s"  # Instead of 5s

# Send periodic "keep-alive" downlinks
# Every 15-30 minutes, send any downlink
# Prevents drift
```

#### 4.3 Gateway Switching / Coverage Issues

**Problem:** Device switches between gateways with incompatible channel maps

**Community Finding:**

> "The device transitioned quickly between two gateways with channel maps that don't overlap" - MachineQ

**This happens when:**

- Multiple gateways in range
- Gateways configured for different sub-bands
- Device locks onto one gateway's channels
- Server switches to different gateway
- Channel mismatch → connection lost

**Solution:**

```bash
# Standardize gateway configurations:
1. All gateways in area use same frequency plan
2. Same sub-band configuration
3. Same channel mask

# ChirpStack: Monitor which gateway is being used
# Device → LoRaWAN Frames → Check "Gateway ID"
# If constantly switching → investigate coverage
```

#### 4.4 Confirmed Downlink Timeout

**Problem:** Using confirmed downlinks in Class C without proper timeout

**From Community:**

> "Class-C devices have a CLASS_C_RESP_TIMEOUT of 8 seconds for confirmed downlinks"

**Issue:**

- Confirmed downlink sent
- Device must ACK within 8 seconds
- If no ACK, server marks device as disconnected
- Queue backs up, future downlinks fail

**Solution:**

```python
# For Busylight status updates:
# Use UNCONFIRMED downlinks!

# ChirpStack API:
{
  "queueItem": {
    "confirmed": false,  # IMPORTANT!
    "fPort": 15,
    "data": "AABkAAD/AA=="  # Green light
  }
}

# Only use confirmed for critical operations
# And increase timeout in device profile
```

**Device Profile Settings:**

```toml
class_c_timeout = 3  # Reduce from 5s to 3s
# Faster failure detection
# Faster retries
```

---

### Issue 5: Periodic 30-Minute Disconnections

**Symptoms:**

- Device works for exactly 30 minutes
- Then stops responding
- Must send uplink to "wake up"
- Pattern repeats every 30 minutes

**Root Cause:** Keep-alive interval misconfiguration

**From Official Documentation:**

> "After join the device will initial send uplink with acknowledge request. When uplink is confirmed keep alive signals (unconfirmed) will be send every 30 min."

**The Issue:**

- Device sends keep-alive every 30 minutes
- If these uplinks fail/aren't confirmed
- Device thinks it's disconnected
- Closes Class C window
- Waits for next keep-alive cycle

**Solutions:**

#### 5.1 Monitor Keep-Alive Uplinks

```bash
# In ChirpStack Events tab, you should see:
# Every 30 minutes:
- Uplink frame (unconfirmed)
- Contains device status

# If these are missing:
- Check gateway connectivity
- Check device signal quality (RSSI/SNR)
- Verify no RF interference at 30-min intervals
```

#### 5.2 Send Periodic Downlinks

```python
# Workaround: Keep connection "alive" artificially
# Every 15 minutes, send a downlink

import schedule
import time

def send_keepalive():
    # Send current color as "refresh"
    controller.set_color(dev_eui, 0, 100, 0)  # Green

schedule.every(15).minutes.do(send_keepalive)

while True:
    schedule.run_pending()
    time.sleep(60)
```

#### 5.3 Adjust Keep-Alive Interval (Advanced)

```python
# Send device command to change interval
# FPort 15, 2-byte command:

# Command structure:
# Byte 0: 0x04 (set interval command)
# Byte 1: interval in minutes (0x0A = 10 minutes)

# Set to 10-minute intervals:
payload = bytes([0x04, 0x0A])
payload_b64 = base64.b64encode(payload).decode()

# Send via ChirpStack
# This increases keep-alive frequency
# Better connection monitoring
```

---

## Class C Downlink Delays

### Issue 6: Downlinks Taking 5-10 Seconds

**Symptoms:**

- Downlink queued in ChirpStack
- Takes 5-10 seconds for light to change
- Expected: <2 seconds for Class C

**Root Causes & Solutions:**

#### 6.1 Class-C Lock Duration (Most Common)

**Problem:** ChirpStack default lock prevents rapid downlinks

**From ChirpStack Documentation:**

> "The class_c_lock_duration defines the lock duration between scheduling two Class-C downlink payloads for the same device"

**Default:** 5 seconds (too long for visual indicators)

**Solution:**

```toml
# Edit /etc/chirpstack/chirpstack.toml

[network.scheduler]
interval = "1s"
class_c_lock_duration = "1s"  # Reduce from 5s
class_a_lock_duration = "2s"

# Restart ChirpStack:
sudo systemctl restart chirpstack
```

**Impact:**

- Before: 5-10 second delays
- After: 1-3 second response time
- Much better user experience

#### 6.2 Using Confirmed Downlinks

**Problem:** Waiting for ACK adds delay

**Solution:**

```python
# For status updates (colors):
# ALWAYS use unconfirmed

# ChirpStack UI:
☐ Confirmed  # Leave UNCHECKED

# API:
"confirmed": false

# Reserve confirmed for critical operations only
```

#### 6.3 Gateway Scheduling Delay

**Community Finding:**

> "Some gateways buffer downlinks. It takes almost 4 seconds till the action is executed, using default RX2 - SF 12"

**Causes:**

- Gateway JIT (Just-In-Time) queue
- High spreading factor (SF12) = slow transmission
- Gateway firmware delays

**Solutions:**

**A. Increase RX2 Data Rate:**

```toml
# In device profile:
# EU868:
rx2_dr = 4  # Or 5 (faster than default 0/SF12)

# US915:
rx2_dr = 2  # Faster than default

# Faster DR = faster transmission = less delay
```

**B. Gateway Firmware Update:**

- Check manufacturer for latest firmware
- Some gateways have known scheduling bugs
- Semtech packet forwarder generally better than custom

**C. Gateway Configuration:**

```json
// In gateway config (if accessible):
{
  "downlink_schedule_delay": 0,  // Minimize delay
  "jit_queue_enabled": true,
  "jit_queue_size": 16
}
```

#### 6.4 Network Server Processing Delay

**Problem:** ChirpStack taking time to process queue

**Solution:**

```toml
# In chirpstack.toml:
[network]
get_downlink_data_delay = "50ms"  # Reduce from 100ms

# Balance:
# - Lower = faster response
# - Too low = application may not queue in time
# - 50-100ms is sweet spot
```

---

## EU868-Specific Issues

### Issue 7: Intermittent Downlink Failures in EU868

**Symptoms:**

- Some downlinks work immediately
- Others take minutes or fail
- Pattern seems random
- More common with multiple devices

**Root Cause:** EU868 **1% duty cycle** limits

**Explanation:**

```
EU868 Duty Cycle Rules:
- Most channels: 1% duty cycle
- 869.525 MHz (RX2): 10% duty cycle

Example:
- Gateway transmits 1-second downlink
- Must wait 99 seconds before next transmission
- On same frequency

With multiple devices:
- Downlinks queue up
- Duty cycle limits cause delays
- Some downlinks delayed minutes
```

**Solutions:**

#### 7.1 Use RX2 Window Exclusively

```toml
# Configure device to use RX2 only
# RX2 at 869.525 MHz has 10% duty cycle

# In device profile:
rx_delay_1 = 1
rx2_dr = 4 or 5
rx2_frequency = 869525000

# This gives 10x more downlink capacity
```

#### 7.2 Spread Updates Over Time

```python
# Don't send all downlinks at once
import time

devices = ["dev1", "dev2", "dev3", ...]

for device in devices:
    controller.set_available(device)
    time.sleep(2)  # 2-second spacing
    # Prevents duty cycle saturation
```

#### 7.3 Batch Color Changes

```python
# Group devices by current color
# Only send updates when state changes

class ParkingLot:
    def __init__(self):
        self.device_states = {}

    def update_only_if_changed(self, dev_eui, new_color):
        if self.device_states.get(dev_eui) != new_color:
            controller.set_color(dev_eui, *new_color)
            self.device_states[dev_eui] = new_color
            return True
        return False  # No downlink sent
```

#### 7.4 Monitor Duty Cycle

```bash
# In ChirpStack:
# Gateway → Statistics
# Look for "Duty Cycle" metrics

# If approaching limits:
- Reduce downlink frequency
- Increase spacing between messages
- Consider additional gateway
```

---

### Issue 8: Join-Accept Failures in Dense EU868 Deployments

**Symptoms:**

- 20+ devices in same area
- Many devices stuck in join loop
- Gateway shows high traffic
- Some devices eventually join, others don't

**Root Cause:** Join-accept duty cycle saturation + channel congestion

**From Community Experience:**

> "If many devices are started within short time, there is a risk for duty cycle on join accept"

**Solutions:**

#### 8.1 Deploy Gateway Per Floor/Area

```
Recommended:
- 1 gateway per 10-15 Busylights
- Or 1 gateway per floor
- Spreads duty cycle across gateways
```

#### 8.2 Pre-Provision Devices

```bash
# Option: Use ABP instead of OTAA
# For large deployments

# ABP Benefits:
- No join procedure
- Immediate operation
- No duty cycle impact from joins

# ABP Drawbacks:
- Less secure
- Manual key management
- No automatic key renewal

# For Busylight (stationary, indoor):
# ABP is acceptable for large deployments
```

**ABP Configuration:**

```python
# In ChirpStack, when adding device:
Activation mode: ABP
- Device Address: [provided by Plenom]
- Network Session Key: [provided]
- Application Session Key: [provided]

# Device operates immediately
# No join delay
```

#### 8.3 Staggered Power-On Procedure

```bash
# For deployment teams:
1. Power on 5 devices
2. Wait for all to show green (joined)
3. Power on next 5 devices
4. Repeat

# Prevents duty cycle collision
# Ensures all devices join successfully
```

---

## Configuration Best Practices

### Recommended ChirpStack Settings

**From Plenom Official Documentation** + Community Best Practices:

#### EU868 Configuration

```toml
# Device Profile:
lorawan_version = "1.0.3"
regional_parameters_revision = "B"
supports_class_c = true
supports_otaa = true

# RX Windows:
rx_delay_1 = 1
rx2_dr = 4  # Or 5 (recommended)
rx2_frequency = 869525000  # 869.525 MHz

# ADR:
supports_adr = false  # Disable for Busylight

# Class C:
class_c_timeout = 3  # Seconds

# EU Channel Frequencies (MHz):
channels = [
  867.1,
  867.3,
  867.5,
  867.7,
  867.9,
  868.1,  # If available
  868.3,  # If available
  868.5   # If available
]
```

#### US915 Configuration

```toml
# Device Profile:
lorawan_version = "1.0.3"
regional_parameters_revision = "B"
supports_class_c = true
supports_otaa = true

# RX Windows:
rx_delay_1 = 1
rx2_dr = 2  # Recommended for US915
rx2_frequency = 923300000  # Sub-band dependent

# ADR:
supports_adr = false

# Sub-Band:
# Use Sub-Band 2 (channels 8-15)
# Most common on public networks
```

#### Server Configuration

```toml
# /etc/chirpstack/chirpstack.toml

[network.scheduler]
interval = "1s"
class_a_lock_duration = "2s"
class_c_lock_duration = "1s"  # Fast response

[network]
get_downlink_data_delay = "50ms"
mac_commands_disabled = false
```

---

### Device Profile Checklist

Before deploying Busylights, verify:

```
☑ LoRaWAN MAC version: 1.0.2 or 1.0.3
☑ Regional parameters revision: B
☑ Device class: Class-C ENABLED
☑ Supports OTAA: YES
☑ ADR: DISABLED (recommended)
☑ RX2 data rate: 4-5 (EU868) or 2 (US915)
☑ RX2 frequency: Correct for region
☑ Class-C timeout: 2-3 seconds
☑ Confirmed downlink timeout: 3-5 seconds
☑ Frequency plan: Matches device box label
```

---

## Firmware and Device Behavior

### Known Device Behaviors

#### Power-On Sequence

```
0-5 seconds:   White blink (startup)
5-10 seconds:  Soft yellow (attempting join)
10-60 seconds: Stays yellow (joining in progress)
Success:       Turns soft green (joined)
Failure:       Stays yellow indefinitely
```

#### Keep-Alive Pattern

```
After successful join:
- Initial uplink: Confirmed (waits for ACK)
- If ACK received:
  - Switches to unconfirmed uplinks
  - Sends every 30 minutes (default)
  - Contains device status
```

#### Status Uplink Contents

```json
{
  "RSSI": -78,
  "SNR": 37,
  "adr_state": 1,
  "hw_rev": 12,
  "sw_rev": 53,
  "lastcolor_red": 0,
  "lastcolor_green": 100,
  "lastcolor_blue": 0,
  "lastcolor_ontime": 255,
  "lastcolor_offtime": 0,
  "messages_received": 148,
  "messages_send": 24
}
```

**What this tells you:**

- `RSSI/SNR`: Signal quality
- `lastcolor_*`: Current displayed color
- `messages_received`: Downlinks received successfully
- `messages_send`: Uplinks transmitted

**Monitoring:**

- If `messages_received` not increasing → downlinks failing
- If `RSSI < -120 dBm` → signal too weak
- If `SNR < 0` → poor signal quality

---

### Firmware Versions

**Current Version:** Check device status uplink for `sw_rev`

**Firmware 5.8+ (v4.0.3) - Latest:**
- **sw_rev 58+:** Latest stable firmware with new features
- **Hardware 1.2+:** Required for firmware 5.8
- **Key changes from earlier versions:**
  - **Byte order changed:** R-G-B → R-B-G (Blue and Green swapped)
  - **New 6th byte:** Optional auto-reply trigger (0x01)
  - **New command 0x06:** Enable/disable auto uplink
  - **Timing units clarified:** Byte 3-4 are in 1/10 second units
  - **Updated watchdog default:** 0xF0=240 (~5 days)
  - **Power consumption data:** Official measurements provided

**Known Issues by Version:**

- **Early versions (<50):** ADR handling issues
- **Version 53-57:** Stable, but uses old R-G-B byte order
- **Version 58+:** Latest with R-B-G byte order (firmware 5.8)

**How to Check:**

```bash
# In ChirpStack Events:
# Look at uplink data for "sw_rev" field
# Compare with latest from Plenom
```

**Firmware Updates:**

- Not user-flashable
- Must contact Plenom support
- FUOTA (Firmware Update Over The Air) not currently supported
- If persistent issues, request RMA with firmware update

---

## Advanced Diagnostics

### Signal Quality Analysis

**RSSI (Received Signal Strength Indicator):**

```
Excellent: > -80 dBm
Good:      -80 to -100 dBm
Fair:      -100 to -115 dBm
Poor:      -115 to -120 dBm
Unusable:  < -120 dBm
```

**SNR (Signal-to-Noise Ratio):**

```
Excellent: > 10 dB
Good:      5 to 10 dB
Fair:      0 to 5 dB
Poor:      -5 to 0 dB
Critical:  < -5 dB
```

**Action Based on Values:**

```python
if rssi < -115 or snr < 0:
    # Poor signal
    # Actions:
    # - Move device closer to gateway
    # - Check gateway antenna
    # - Verify no RF interference
    # - Consider additional gateway
```

### Connection Monitoring Script

```python
#!/usr/bin/env python3
"""
Monitor Busylight connection health
Alert on anomalies
"""

import requests
import time
from datetime import datetime, timedelta

class BusylightMonitor:
    def __init__(self, chirpstack_url, api_key, dev_eui):
        self.base_url = chirpstack_url
        self.headers = {'Authorization': f'Bearer {api_key}'}
        self.dev_eui = dev_eui
        self.last_uplink = None
        self.last_downlink_success = None

    def check_health(self):
        """Check device health metrics"""
        # Get recent frames
        url = f"{self.base_url}/api/devices/{self.dev_eui}/frames"
        params = {'limit': 10}

        response = requests.get(url, headers=self.headers, params=params)
        frames = response.json().get('result', [])

        # Analyze uplinks
        uplinks = [f for f in frames if f.get('uplinkFrame')]
        if uplinks:
            latest_uplink = uplinks[0]
            rssi = latest_uplink.get('rxInfo', [{}])[0].get('rssi')
            snr = latest_uplink.get('rxInfo', [{}])[0].get('snr')

            print(f"[{datetime.now()}] Device: {self.dev_eui}")
            print(f"  RSSI: {rssi} dBm")
            print(f"  SNR: {snr} dB")

            # Alert on poor signal
            if rssi and rssi < -115:
                print("  ⚠️  WARNING: Poor RSSI")
            if snr and snr < 0:
                print("  ⚠️  WARNING: Poor SNR")

            self.last_uplink = datetime.now()

        # Check if uplink is overdue (>35 minutes)
        if self.last_uplink:
            age = datetime.now() - self.last_uplink
            if age > timedelta(minutes=35):
                print(f"  🚨 ALERT: No uplink for {age.seconds//60} minutes")
                print(f"     Expected keep-alive every 30 minutes")
                return False

        return True

# Usage
monitor = BusylightMonitor(
    chirpstack_url="https://your-server.com",
    api_key="YOUR_API_KEY",
    dev_eui="70b3d57ed1000000"
)

while True:
    monitor.check_health()
    time.sleep(300)  # Check every 5 minutes
```

### Packet Capture Analysis

**For deep debugging, capture gateway traffic:**

```bash
# On gateway (if accessible):
# Capture LoRaWAN packets
sudo tcpdump -i any port 1700 -w lorawan_capture.pcap

# Analyze with Wireshark
# Filter: lorawan
# Look for:
# - Join Request/Accept sequences
# - Downlink scheduling
# - Timing issues
```

---

## Community-Sourced Workarounds

### Workaround 1: "Power Cycle Automation"

**Problem:** Device occasionally needs power cycle to reconnect

**Community Solution:**

```python
# Implement automatic "virtual power cycle"
# Send special downlink sequence that resets device state

def emergency_reset_sequence(dev_eui):
    """
    Send sequence that often fixes stuck devices
    without physical power cycle
    """
    # 1. Turn off
    controller.set_off(dev_eui)
    time.sleep(2)

    # 2. Flash white (mimic startup)
    controller.set_color(dev_eui, 255, 255, 255, solid=False)
    time.sleep(2)

    # 3. Return to current state
    controller.set_available(dev_eui)  # Or whatever state

    # Sometimes this "wakes up" a stuck device
```

### Workaround 2: "Heartbeat Downlink"

**Problem:** Connection drifts after long periods without downlinks

**Community Solution:**

```python
# Send periodic "heartbeat" downlinks
# Even if color doesn't need to change

import schedule

def heartbeat():
    """Send current color as refresh"""
    for device in all_devices:
        current_color = device_states[device]
        controller.set_color(device, *current_color)
        time.sleep(1)

# Run every 10 minutes
schedule.every(10).minutes.do(heartbeat)
```

### Workaround 3: "Join Monitor & Auto-Recover"

**Problem:** Devices sometimes fail to join on first try

**Community Solution:**

```python
def monitor_join_status():
    """
    Monitor for devices stuck in join loop
    Auto-retry with different parameters
    """
    # Check device status
    events = get_device_events(dev_eui)

    # Look for repeated join requests without accept
    join_requests = [e for e in events if 'JoinRequest' in e]
    join_accepts = [e for e in events if 'JoinAccept' in e]

    if len(join_requests) > 10 and len(join_accepts) == 0:
        print(f"Device {dev_eui} stuck in join loop")

        # Try fixes:
        # 1. Flush DevNonce
        flush_dev_nonce(dev_eui)

        # 2. Check device profile
        verify_device_profile(dev_eui)

        # 3. Alert administrator
        send_alert(f"Device {dev_eui} needs attention")
```

### Workaround 4: "Adaptive Retry Logic"

**Problem:** Downlinks sometimes fail, need retry

**Community Solution:**

```python
def send_with_retry(dev_eui, color_func, max_attempts=3):
    """
    Send downlink with exponential backoff retry
    """
    for attempt in range(max_attempts):
        try:
            # Send downlink
            result = color_func(dev_eui)

            # Wait and verify
            time.sleep(5)

            # Check if received
            status = get_device_status(dev_eui)
            if status['lastcolor'] == expected_color:
                return True

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")

        # Exponential backoff
        wait_time = (2 ** attempt) * 2
        time.sleep(wait_time)

    # All attempts failed
    print(f"Failed to update {dev_eui} after {max_attempts} attempts")
    return False
```

---

## Quick Reference: Troubleshooting Flowchart

```
Device Won't Join (Yellow Light)
    ↓
Check 1: Credentials match?
    No → Re-enter DevEUI/AppEUI/AppKey
    Yes → Continue
    ↓
Check 2: Device profile = Class C?
    No → Change to Class C
    Yes → Continue
    ↓
Check 3: Frequency plan matches box label?
    No → Fix frequency plan
    Yes → Continue
    ↓
Check 4: Gateway sees join requests?
    No → Check gateway, move device closer
    Yes → Continue
    ↓
Check 5: Join-accepts being sent?
    No → Check credentials again, flush DevNonce
    Yes but device not receiving → Signal issue, check RSSI/SNR
    ↓
Check 6: EU868 with multiple devices?
    Yes → Duty cycle issue, deploy in batches
    No → Continue
    ↓
Check 7: US915/AU915?
    Yes → Wait longer (2-10 min normal)
    No → Contact Plenom support


Device Joined but Downlinks Slow/Fail
    ↓
Check 1: Using confirmed downlinks?
    Yes → Switch to unconfirmed
    No → Continue
    ↓
Check 2: class_c_lock_duration setting?
    >2s → Reduce to 1s
    ≤2s → Continue
    ↓
Check 3: RX2 data rate?
    DR0 (SF12) → Increase to DR4/DR5 (EU) or DR2 (US)
    Already higher → Continue
    ↓
Check 4: Multiple rapid downlinks?
    Yes → Add 1-2s spacing
    No → Continue
    ↓
Check 5: EU868 duty cycle saturation?
    Yes → Spread updates, use RX2 exclusively
    No → Check gateway firmware


Device Disconnects After Hours
    ↓
Check 1: ADR enabled?
    Yes → Disable ADR
    No → Continue
    ↓
Check 2: Keep-alive uplinks arriving every 30 min?
    No → Signal quality issue, check RSSI/SNR
    Yes → Continue
    ↓
Check 3: Multiple gateways in range?
    Yes → Standardize gateway configs
    No → Continue
    ↓
Check 4: Downlinks still working but no response?
    Yes → RX window drift, send LinkCheckReq
    No → Continue
    ↓
    Implement periodic heartbeat downlinks
```

---

## Getting Additional Help

### Official Plenom Support

**Contact:**

- Email: support@plenom.com
- Website: https://busylight.com/support/
- Technical Documentation: Request latest LoRaWAN commands document

**What to Include:**

```
1. Device Information:
   - DevEUI
   - Firmware version (from uplink data)
   - Frequency band (EU868/US915/AU915)

2. Problem Description:
   - LED behavior (yellow/green/other)
   - Duration of issue
   - Deployment scenario

3. Diagnostic Data:
   - ChirpStack event logs
   - Gateway LoRaWAN frames
   - RSSI/SNR values
   - Join request/accept sequence

4. Configuration:
   - Device profile settings
   - Gateway model and firmware
   - Number of devices in deployment
```

### ChirpStack Community

**Forum:** https://forum.chirpstack.io/

- Active community
- Search for "Class C" and "downlink" issues
- Many similar use cases

### LoRaWAN Resources

- **Semtech Developer Portal:** https://lora-developers.semtech.com/
- **LoRa Alliance Spec:** Latest LoRaWAN specification
- **The Things Network Forum:** https://www.thethingsnetwork.org/forum/

---

## Appendix: Common Error Messages

### "MIC mismatch"

**Meaning:** Message Integrity Code failed  
**Cause:** Wrong AppKey  
**Fix:** Verify AppKey in device and server match exactly

### "DevNonce has already been used"

**Meaning:** Device reused a DevNonce value  
**Cause:** DevNonce not persistent across power cycles  
**Fix:** Flush DevNonce queue in ChirpStack, contact Plenom if persistent

### "Uplink channel not found"

**Meaning:** Device transmitting on unsupported channel  
**Cause:** Frequency plan mismatch  
**Fix:** Verify device and gateway frequency plans match

### "Duty cycle limit reached"

**Meaning:** Gateway hit regulatory transmission limits  
**Cause:** Too many downlinks in short time (EU868)  
**Fix:** Space out downlinks, use RX2 window, add gateways

### "Class C timeout"

**Meaning:** No ACK received for confirmed downlink  
**Cause:** Device not receiving or not responding  
**Fix:** Check signal quality, increase timeout, use unconfirmed

### "Device not activated"

**Meaning:** Device not in joined state  
**Cause:** Join failed or device reset  
**Fix:** Check join sequence, verify credentials

---

## Document History

**v2.0 (October 2025)**

- Deep research into community issues
- Added EU868 duty cycle solutions
- Class C performance tuning
- Connection stability fixes
- Real-world deployment scenarios
- **Added firmware 5.8 notes** (v4.0.3 documentation)

**v1.0 (Initial)**

- Basic troubleshooting
- Official documentation compilation

---


---

## Firmware Compatibility Note

**⚠️ CRITICAL: Check Your Firmware Version!**

If you have **firmware 5.8+ (sw_rev 58+)**, the byte order for colors is **R-B-G**.
If you have **older firmware (sw_rev <58)**, the byte order may be **R-G-B**.

To check your firmware:
1. View device uplink in ChirpStack Events
2. Look for `sw_rev` field
3. Compare with integration guide

**See BUSYLIGHT_INTEGRATION_GUIDE.md for correct byte order and updated code examples.**

---
## Contributing

Found a new issue or solution? Please contribute:

- Open GitHub issue with details
- Email documentation updates
- Share on ChirpStack forum

**This is a living document based on real deployments and community experience.**

---

**Remember:** The Busylight is a robust device when properly configured. Most issues stem from network configuration, not the device itself. When in doubt:

1. ✅ Verify credentials
2. ✅ Check frequency plan
3. ✅ Confirm Class C enabled
4. ✅ Disable ADR
5. ✅ Use unconfirmed downlinks
6. ✅ Monitor signal quality

Good luck with your deployment! 🟢🔴🟠
