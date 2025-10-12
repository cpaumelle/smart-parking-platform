# Complete Guide: Connecting Kerlink kerOS 6 Gateway to ChirpStack via Basic Station

## Table of Contents

- [Prerequisites](#prerequisites)
- [Overview](#overview)
- [Step 1: Get Your Gateway's EUI](#step-1-get-your-gateways-eui)
- [Step 2: Initial Gateway Connection](#step-2-initial-gateway-connection)
- [Step 3: Install Basic Station](#step-3-install-basic-station)
- [Step 4: Configure Basic Station for ChirpStack](#step-4-configure-basic-station-for-chirpstack)
- [Step 5: Register Gateway in ChirpStack](#step-5-register-gateway-in-chirpstack)
- [Step 6: Verification and Troubleshooting](#step-6-verification-and-troubleshooting)
- [Common Gotchas and Solutions](#common-gotchas-and-solutions)
- [Appendix A: Regional Frequency Plans](#appendix-a-regional-frequency-plans)
- [Appendix B: API Gateway Registration](#appendix-b-api-gateway-registration)

---

## Prerequisites

**Hardware:**

- Kerlink Wirnet™ i-series gateway (iFemtoCell, iStation, iFemtoCell Evolution, or iZeptoCell)
- Gateway running kerOS 6.x (verify with `cat /etc/version`)
- Active network connection (Ethernet or Cellular)

**Software:**

- ChirpStack v4 instance accessible from the gateway
- ChirpStack instance at: `chirpstack.verdregris.eu`
- SSH client (PuTTY for Windows, Terminal for Linux/Mac)

**Network:**

- Gateway must be able to reach `chirpstack.verdregris.eu` on port 3001 (WebSocket)
- Outbound HTTPS (443) for potential certificate validation
- No restrictive firewalls blocking WebSocket connections

---

## Overview

**Connection Architecture:**

```
Gateway Hardware (LoRa Concentrator)
          ↓
    lorad (LoRa daemon)
          ↓
   Basic Station Forwarder
          ↓
WebSocket (ws:// or wss://) on port 3001
          ↓
ChirpStack Gateway Bridge
          ↓
    MQTT Broker
          ↓
  ChirpStack Network Server
```

**Key Differences from kerOS 5:**

- No more `monit` - use `systemctl` for service management
- Uses `apt` instead of `opkg` for package management
- Configuration via `klk_bs_config` tool (not `klk_apps_config`)
- Environment variables available system-wide (like `$EUI64`)

---

## Step 1: Get Your Gateway's EUI

The Gateway EUI (Extended Unique Identifier) is a 64-bit (16 hex character) unique identifier you'll need to register the gateway in ChirpStack.

### Method 1: From Environment Variable (Easiest)

```bash
echo $EUI64
```

Expected output: `7276FF0039030336` (example)

### Method 2: From Board Info File

```bash
cat /run/boardinfo.env | grep EUI64
```

Or:

```bash
grep EUI64 /proc/cmdline
```

### Method 3: From Hostname

The gateway hostname contains part of the EUI. The hostname format is:

```
klk-<codename>-<last 6 digits of serial>
```

For example: `klk-wifc-030336` where `030336` are the last 6 hex digits.

To get the full EUI64:

```bash
hostname
# Result: klk-wifc-030336

# The full EUI64 for iFemtoCell would be: 7276FF0039030336
# Format: 7276FF00 + <8-digit serial>
```

**Gateway Model Prefixes:**

- **iFemtoCell**: `7276FF00` prefix
- **iStation**: `7076FF00` prefix
- **iFemtoCell Evolution**: May vary, check actual EUI64

### Method 4: From Physical Label

Look on the gateway case - the EUI64 is printed on a label.

**⚠️ GOTCHA #1:** Write down your complete EUI64 now. You'll need it multiple times. Format should be exactly 16 hex characters (0-9, A-F).

**Example EUI64:** `7276FF0039030336`

---

## Step 2: Initial Gateway Connection

### Default Credentials

**Username:** `root`  
**Password:** `pdmk-XXXXXX` where XXXXXX are the last 6 hex digits of your Board ID/EUI

**Example:** If your EUI64 is `7276FF0039030336`, password is `pdmk-030336`

### Connection Methods

#### Option A: Ethernet Connection

1. Connect gateway to your network via Ethernet
  
2. Find gateway IP from your router's DHCP leases, or use mDNS:
  
  ```bash
  ssh root@klk-wifc-XXXXXX.local
  # Replace XXXXXX with your 6-digit serial
  ```
  

#### Option B: Direct USB Connection

1. Connect USB cable from gateway to your computer
2. Gateway creates a virtual Ethernet device
3. Connect to: `ssh root@192.168.120.1`

#### Option C: WiFi AP (iFemtoCell only)

1. At boot, iFemtoCell creates WiFi AP for 1 hour
2. SSID: `klk-wifc-XXXXXX`
3. Password: Ethernet MAC address (uppercase, no spaces) - found on label
4. Connect to: `ssh root@192.168.120.1`

### First Login Steps

```bash
# SSH into gateway
ssh root@klk-wifc-030336.local
# Enter password: pdmk-030336

# IMMEDIATELY change your password for security
passwd

# Check kerOS version - must be 6.x
cat /etc/version
# Example output: 6.3.1

# Verify you have internet connectivity
ping -c 3 8.8.8.8

# Verify you can reach ChirpStack
ping -c 3 chirpstack.verdregris.eu
```

**⚠️ GOTCHA #2:** If you don't change the password within the first hour, the web interface will be permanently disabled until you reboot.

**⚠️ GOTCHA #3:** Some corporate networks block ICMP, so ping might fail even if connectivity works. Try DNS resolution instead:

```bash
nslookup chirpstack.verdregris.eu
```

---

## Step 3: Install Basic Station

### Check if Already Installed

```bash
systemctl status basicstation
```

If you see "Unit basicstation.service could not be found", it's not installed.

### Update Package Lists

```bash
apt update
```

**⚠️ GOTCHA #4:** If `apt update` fails with SSL errors, your gateway clock might be wrong. Sync time:

```bash
# Check current time
date

# If wrong, manually set (example)
date -s "2025-10-11 14:30:00"

# Or sync with NTP (preferred)
systemctl restart systemd-timesyncd
timedatectl status
```

### Install Basic Station Package

```bash
apt install basicstation
```

**Expected output:**

```
Reading package lists... Done
Building dependency tree... Done
The following NEW packages will be installed:
  basicstation
0 upgraded, 1 newly installed, 0 to remove
```

### Verify Installation

```bash
which basicstation
# Should show: /usr/bin/basicstation

basicstation --version
# Should show version information
```

**⚠️ GOTCHA #5:** Basic Station does NOT auto-start after installation. It's intentionally disabled until configured.

---

## Step 4: Configure Basic Station for ChirpStack

### Understanding the klk_bs_config Tool

The `klk_bs_config` tool is the official Kerlink utility for configuring Basic Station. It handles:

- Writing the LNS URI to `/etc/station/tc.uri`
- Configuring lorad (the LoRa daemon)
- Setting up credentials (if needed)
- Enabling the basicstation service

### Configure for ChirpStack (No TLS - Simple WebSocket)

Since ChirpStack is often deployed without TLS on internal networks, we'll use simple WebSocket (`ws://`):

```bash
sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001"
```

**⚠️ CRITICAL GOTCHA #6:** The URI **MUST** start with `ws://` (not `wss://`) if your ChirpStack doesn't use TLS. If you use `wss://` without proper certificates, the connection will fail silently.

**Expected output:**

```
Configuring Basic Station...
Writing LNS URI to /etc/station/tc.uri
Configuring lorad for EU868 (default)
Enabling basicstation service
Created symlink /etc/systemd/system/multi-user.target.wants/basicstation.service...
Configuration complete
```

### Optional: Specify Region Explicitly

If you're not in EU868, specify your region:

```bash
# For US915
sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001" --loradconf US915.json

# For AS923
sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001" --loradconf AS923-1.json
```

**Available regions:** See [Appendix A](#appendix-a-regional-frequency-plans)

### Optional: Prevent LNS from Reconfiguring Frequencies

```bash
sudo klk_bs_config --enable \
  --lns-uri "ws://chirpstack.verdregris.eu:3001" \
  --loradconf EU868.json \
  --ignore-reconf
```

The `--ignore-reconf` flag prevents ChirpStack from changing the gateway's frequency plan remotely.

### Verify Configuration Files

```bash
# Check LNS URI
cat /etc/station/tc.uri
# Should show: ws://chirpstack.verdregris.eu:3001

# Check lorad configuration
cat /etc/lorad/lorad.json | grep -A 5 '"chan_multiSF_0"'
# Should show your frequency plan
```

### Start Basic Station Service

The service should auto-start after `klk_bs_config --enable`, but verify:

```bash
sudo systemctl status basicstation
```

If not running:

```bash
sudo systemctl start basicstation
```

**⚠️ GOTCHA #7:** Basic Station won't connect until the gateway is registered in ChirpStack. The service will keep trying to connect and logging errors until you complete Step 5.

---

## Step 5: Register Gateway in ChirpStack

You need to register your gateway in ChirpStack **before** it can successfully connect.

### Method A: Using the Web UI (Recommended)

1. Open browser and navigate to: `https://chirpstack.verdregris.eu`
  
2. Log in with your ChirpStack credentials
  
3. Navigate to: **Tenants** → [Your Tenant] → **Gateways** → **Add Gateway**
  
4. Fill in the form:
  
  **Gateway ID:** Your EUI64 **without any separators or spaces**
  
  ```
  Example: 7276ff0039030336
  ```
  
  **⚠️ GOTCHA #8:** ChirpStack expects lowercase hex characters for the Gateway ID. Your gateway outputs uppercase (`7276FF0039030336`) but enter it as lowercase (`7276ff0039030336`).
  
  **Gateway name:** Choose a friendly name
  
  ```
  Example: kerlink-wifc-030336
  ```
  
  **Gateway description:** (Optional)
  
  ```
  Example: Kerlink iFemtoCell - Office Building
  ```
  
  **Network-server:** Select your network server from dropdown
  
5. Click **Submit**
  
6. (Optional) Go to the **Configuration** tab and adjust settings:
  
  - **Altitude:** Gateway altitude in meters
  - **Location:** Pin on map or enter lat/long
  - **Gateway Profile:** Select if you have custom profiles

### Method B: Using the ChirpStack API

See [Appendix B](#appendix-b-api-gateway-registration) for API examples.

### Verify Gateway Appears in UI

After registration:

1. Go to **Gateways** list
2. You should see your gateway with:
  - ⚪ Gray dot = Never connected
  - 🟢 Green dot = Online (you should see this within 30 seconds)
  - 🔴 Red dot = Previously connected, now offline

**⚠️ GOTCHA #9:** If the gateway shows red/offline after 60 seconds, proceed to troubleshooting in Step 6.

---

## Step 6: Verification and Troubleshooting

### Check Basic Station Logs

```bash
# Follow logs in real-time
sudo journalctl -fu basicstation

# View last 50 lines
sudo journalctl -u basicstation -n 50

# View logs with timestamps
sudo journalctl -u basicstation --since "5 minutes ago"
```

### Successful Connection Logs

You should see:

```
[TCE:INFO] Connected to LNS ws://chirpstack.verdregris.eu:3001
[RAL:INFO] Selected radio modem 0 (0-0)
[RAL:INFO] Starting radio
[TCE:INFO] Received router_config message
[S2E:INFO] Session established
```

### Common Error Messages and Solutions

#### Error: "Connection refused"

```
[TCE:ERRO] Connection to ws://chirpstack.verdregris.eu:3001 refused
```

**Cause:** ChirpStack Gateway Bridge is not listening on port 3001

**Solution:**

- Verify ChirpStack Gateway Bridge is running
- Check Gateway Bridge configuration has Basic Station backend enabled
- Verify firewall allows port 3001
- Test from gateway: `telnet chirpstack.verdregris.eu 3001`

#### Error: "Unknown gateway"

```
[TCE:ERRO] Received error from LNS: unknown gateway
```

**Cause:** Gateway not registered in ChirpStack, or Gateway ID mismatch

**Solution:**

- Double-check Gateway ID in ChirpStack matches exactly: `echo $EUI64 | tr '[:upper:]' '[:lower:]'`
- Ensure you registered in correct tenant
- Check Basic Station is sending correct Gateway ID: `grep gateway_ID /var/log/basicstation.log`

#### Error: "TLS handshake failed"

```
[TCE:ERRO] SSL/TLS handshake failed
```

**Cause:** Using `wss://` but certificates not configured

**Solution:**

- If no TLS needed, change to `ws://`:
  
  ```bash
  sudo klk_bs_config --disable
  sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001"
  ```
  
- If TLS needed, configure certificates (see Secure Connection section)
  

#### Error: "Invalid WebSocket upgrade"

```
[TCE:WARN] WebSocket upgrade failed: 404 Not Found
```

**Cause:** Wrong port or path

**Solution:**

- Verify ChirpStack Gateway Bridge is on port 3001
- Check Gateway Bridge logs for bind address
- Verify no reverse proxy altering paths

### Check lorad Status

Basic Station depends on lorad to access the LoRa hardware:

```bash
# Check lorad service
sudo systemctl status lorad

# View lorad logs
sudo journalctl -u lorad -n 50
```

**Expected:** lorad should be **active (running)**

### Check Network Connectivity to ChirpStack

```bash
# DNS resolution
nslookup chirpstack.verdregris.eu

# Ping (may be blocked)
ping -c 3 chirpstack.verdregris.eu

# TCP connection test
telnet chirpstack.verdregris.eu 3001
# Press Ctrl+C to exit if it connects

# Alternative TCP test
nc -zv chirpstack.verdregris.eu 3001
```

### View Gateway Status in ChirpStack UI

Once connected:

1. Go to **Gateways** → [Your Gateway]
2. Check **LoRaWAN frames** tab for activity
3. Should see heartbeats every 30 seconds
4. Check **Events** tab for connection events

### Test Uplink Reception

If you have a LoRaWAN device:

1. Send an uplink from your device
  
2. Watch Basic Station logs:
  
  ```bash
  sudo journalctl -fu basicstation | grep -i uplink
  ```
  
3. Check ChirpStack **LoRaWAN frames** page for the uplink
  

### Restart Services if Needed

```bash
# Restart Basic Station
sudo systemctl restart basicstation

# Restart lorad (only if having hardware issues)
sudo systemctl restart lorad

# Restart both
sudo systemctl restart lorad basicstation
```

**⚠️ GOTCHA #10:** Always restart lorad **before** basicstation if restarting both. Basic Station depends on lorad being ready.

---

## Common Gotchas and Solutions

### Gotcha #1: Case Sensitivity in Gateway ID

- **Issue:** Gateway EUI is `7276FF0039030336` but ChirpStack expects `7276ff0039030336`
- **Solution:** Always use lowercase when entering in ChirpStack UI/API

### Gotcha #2: Protocol Mismatch (ws vs wss)

- **Issue:** Configuration has `wss://` but ChirpStack doesn't use TLS
  
- **Solution:** Verify ChirpStack Gateway Bridge config and match protocol
  
  ```bash
  # Check if your ChirpStack uses TLS
  curl -v ws://chirpstack.verdregris.eu:3001
  # vs
  curl -v wss://chirpstack.verdregris.eu:3001
  ```
  

### Gotcha #3: Gateway Not in Correct Tenant

- **Issue:** Gateway registered in wrong tenant
- **Solution:** Delete gateway from wrong tenant, re-add to correct one

### Gotcha #4: Wrong Frequency Plan

- **Issue:** Gateway configured for EU868 but ChirpStack expects US915
  
- **Solution:** Reconfigure with correct region:
  
  ```bash
  sudo klk_bs_config --disable
  sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001" --loradconf US915.json
  ```
  

### Gotcha #5: Firewall Blocking Port 3001

- **Issue:** Corporate firewall blocks WebSocket
- **Solution:**
  - Request port 3001 to be opened
  - Or use alternative port if ChirpStack admin can configure

### Gotcha #6: Stale Configuration

- **Issue:** Previous configuration interfering
  
- **Solution:** Clean config and restart:
  
  ```bash
  sudo klk_bs_config --disable
  sudo systemctl stop basicstation
  sudo rm -f /etc/station/tc.uri /etc/station/*.key /etc/station/*.crt /etc/station/*.trust
  sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001"
  ```
  

### Gotcha #7: Time Synchronization Issues

- **Issue:** Gateway clock wrong, SSL/TLS fails
  
- **Solution:**
  
  ```bash
  sudo systemctl restart systemd-timesyncd
  timedatectl set-ntp true
  sleep 5
  timedatectl status
  ```
  

### Gotcha #8: Multiple Forwarders Running

- **Issue:** Both Basic Station and lorafwd running simultaneously
  
- **Solution:** Disable lorafwd:
  
  ```bash
  sudo systemctl stop lorafwd
  sudo systemctl disable lorafwd
  ```
  

### Gotcha #9: LoRa Hardware Not Initialized

- **Issue:** lorad failed to start or access concentrator
  
- **Solution:**
  
  ```bash
  sudo systemctl restart lorad
  sudo journalctl -u lorad | grep -i error
  ```
  

### Gotcha #10: ChirpStack Gateway Bridge Not Configured for Basic Station

- **Issue:** Gateway Bridge only listening for Semtech UDP
  
- **Solution:** Verify with ChirpStack admin that Gateway Bridge has:
  
  ```toml
  [backend]
  type = "basic_station"
  
  [backend.basic_station]
  bind = ":3001"
  ```
  

---

## Appendix A: Regional Frequency Plans

Available frequency plans in `/usr/share/lorad/frequency_plans/sx130x/`:

### Europe

```bash
--loradconf EU868.json          # EU863-870 standard
```

### North America

```bash
--loradconf US915.json           # US902-928, all 64 channels
--loradconf US915_0.json         # Sub-band 0 (channels 0-7)
--loradconf US915_1.json         # Sub-band 1 (channels 8-15)
# ... up to US915_7.json
```

### Asia-Pacific

```bash
--loradconf AS923-1.json         # AS923 with 923.2-923.4 MHz
--loradconf AS923-1-JP.json      # AS923 Japan with LBT
--loradconf AS923-2.json         # AS923-2 variant
--loradconf AS923-3.json         # AS923-3 variant
```

### China

```bash
--loradconf CN470.json           # CN470-510
```

### Australia

```bash
--loradconf AU915.json           # AU915-928
--loradconf AU915_0.json         # Sub-band 0
# ... similar to US915 sub-bands
```

### India

```bash
--loradconf IN865.json           # IN865-867
```

### Korea

```bash
--loradconf KR920.json           # KR920-923
```

### Russia

```bash
--loradconf RU864.json           # RU864-870
```

**To list all available:**

```bash
ls /usr/share/lorad/frequency_plans/sx130x/
```

**To view frequency plan details:**

```bash
cat /usr/share/lorad/frequency_plans/sx130x/EU868.json | grep -A 3 chan_multiSF
```

---

## Appendix B: API Gateway Registration

### Using curl with ChirpStack API

#### Get API Token

1. Log into ChirpStack UI
2. Navigate to **API Keys** → **Create**
3. Copy the generated token

#### Register Gateway via API

```bash
# Set variables
CHIRPSTACK_URL="https://chirpstack.verdregris.eu"
API_TOKEN="your-api-token-here"
GATEWAY_ID="7276ff0039030336"  # Lowercase!
TENANT_ID="your-tenant-id"      # Get from ChirpStack UI
GATEWAY_NAME="kerlink-wifc-030336"

# Create gateway
curl -X POST \
  "${CHIRPSTACK_URL}/api/gateways" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway": {
      "gatewayId": "'${GATEWAY_ID}'",
      "name": "'${GATEWAY_NAME}'",
      "description": "Kerlink iFemtoCell Gateway",
      "location": {
        "latitude": 52.3676,
        "longitude": 4.9041,
        "altitude": 10
      },
      "tenantId": "'${TENANT_ID}'",
      "tags": {
        "model": "iFemtoCell",
        "keros_version": "6.3.1"
      },
      "metadata": {},
      "statsInterval": 30
    }
  }'
```

#### Get Gateway Details

```bash
curl -X GET \
  "${CHIRPSTACK_URL}/api/gateways/${GATEWAY_ID}" \
  -H "Authorization: Bearer ${API_TOKEN}"
```

#### Update Gateway Location

```bash
curl -X PUT \
  "${CHIRPSTACK_URL}/api/gateways/${GATEWAY_ID}" \
  -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway": {
      "gatewayId": "'${GATEWAY_ID}'",
      "name": "'${GATEWAY_NAME}'",
      "location": {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "altitude": 35
      },
      "tenantId": "'${TENANT_ID}'"
    }
  }'
```

### Using Python Script

```python
#!/usr/bin/env python3
import requests
import json
import os

# Configuration
CHIRPSTACK_URL = "https://chirpstack.verdregris.eu"
API_TOKEN = os.environ.get("CHIRPSTACK_API_TOKEN")
GATEWAY_ID = "7276ff0039030336"  # Must be lowercase
TENANT_ID = "your-tenant-id"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

gateway_data = {
    "gateway": {
        "gatewayId": GATEWAY_ID,
        "name": f"kerlink-{GATEWAY_ID[-6:]}",
        "description": "Kerlink iFemtoCell Gateway via API",
        "location": {
            "latitude": 52.3676,
            "longitude": 4.9041,
            "altitude": 10
        },
        "tenantId": TENANT_ID,
        "tags": {
            "model": "iFemtoCell",
            "keros_version": "6.3.1",
            "deployment": "production"
        },
        "statsInterval": 30
    }
}

response = requests.post(
    f"{CHIRPSTACK_URL}/api/gateways",
    headers=headers,
    json=gateway_data
)

if response.status_code == 200:
    print(f"✓ Gateway {GATEWAY_ID} registered successfully")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"✗ Error: {response.status_code}")
    print(response.text)
```

Run with:

```bash
export CHIRPSTACK_API_TOKEN="your-token"
python3 register_gateway.py
```

---

## Advanced: Secure WebSocket Connection (wss://)

If your ChirpStack instance requires TLS:

### 1. Prepare Certificates

You'll need:

- `tc.trust` - CA certificate (to verify server)
- `tc.crt` - Client certificate (optional, for mutual TLS)
- `tc.key` - Client private key (optional, for mutual TLS)

### 2. Copy Certificates to Gateway

```bash
# From your computer
scp ca-cert.pem root@gateway-ip:/user/basic_station/etc/tc.trust
scp client-cert.pem root@gateway-ip:/user/basic_station/etc/tc.crt
scp client-key.pem root@gateway-ip:/user/basic_station/etc/tc.key

# On gateway, verify permissions
chmod 644 /user/basic_station/etc/tc.trust
chmod 644 /user/basic_station/etc/tc.crt
chmod 600 /user/basic_station/etc/tc.key
```

### 3. Configure with TLS

```bash
# With server TLS only (trust file)
sudo klk_bs_config --enable --lns-uri "wss://chirpstack.verdregris.eu:3001"

# The tool will automatically find certificates in:
# /user/basic_station/etc/
```

### 4. Verify TLS Connection

```bash
# Test with openssl
openssl s_client -connect chirpstack.verdregris.eu:3001 -servername chirpstack.verdregris.eu

# Should show certificate chain and successful handshake
```

---

## Quick Reference Commands

```bash
# Get Gateway EUI
echo $EUI64

# Install Basic Station
apt update && apt install basicstation

# Configure (No TLS)
sudo klk_bs_config --enable --lns-uri "ws://chirpstack.verdregris.eu:3001"

# Check Service Status
sudo systemctl status basicstation
sudo systemctl status lorad

# View Logs
sudo journalctl -fu basicstation
sudo journalctl -fu lorad

# Restart Services
sudo systemctl restart lorad basicstation

# Test Network
ping chirpstack.verdregris.eu
nc -zv chirpstack.verdregris.eu 3001

# Disable Basic Station
sudo klk_bs_config --disable
sudo systemctl stop basicstation

# Clean Configuration
sudo rm -f /etc/station/tc.uri /etc/station/*.key /etc/station/*.crt
```

---

## Support Resources

- **Kerlink kerOS 6 Documentation:** https://keros.docs.kerlink.com/
- **ChirpStack Documentation:** https://www.chirpstack.io/docs/
- **ChirpStack Community Forum:** https://forum.chirpstack.io/
- **Kerlink Wiki (kerOS 5 and earlier):** https://wikikerlink.fr/

---

## Version History

- **v1.0** (2025-10-11): Initial comprehensive guide for kerOS 6 to ChirpStack via Basic Station

---

**Author Notes:**

- This guide is specifically for kerOS 6.x with ChirpStack v4
- For older kerOS versions (4.x, 5.x), consult Kerlink Wiki
- Always verify your specific gateway model and kerOS version
- ChirpStack configuration may vary by deployment - consult your admin

**License:** This guide is provided as-is for educational and operational purposes.
