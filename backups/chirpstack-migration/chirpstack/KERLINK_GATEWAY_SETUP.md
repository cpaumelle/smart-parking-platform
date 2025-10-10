# Kerlink LoRaWAN Gateway Configuration Guide

**Target Network:** ChirpStack on VM 110 (chirpstack.sensemy.cloud)
**Version:** 1.0.0
**Last Updated:** 2025-10-01
**Compatible Gateways:** Kerlink Wirnet Station, iBTS, iFemtoCell, iStation

---

## Overview

This guide provides step-by-step instructions for configuring Kerlink LoRaWAN gateways to connect to the ChirpStack LoRaWAN Network Server hosted at `chirpstack.sensemy.cloud`.

### Network Information

| Parameter | Value |
|-----------|-------|
| **Server Address** | 10.44.1.110 (or chirpstack.sensemy.cloud) |
| **Protocol** | Semtech UDP Packet Forwarder |
| **Port** | 1700 (UDP) |
| **Region** | US915 |
| **Sub-band** | 0 (Channels 0-7: 902.3-903.7 MHz) |

---

## Prerequisites

- Kerlink gateway with firmware v3.x or higher
- Network connectivity between gateway and ChirpStack server
- SSH access to gateway (for manual configuration)
- Gateway admin credentials

---

## Configuration Methods

There are three methods to configure a Kerlink gateway:

1. **Web Interface** (Easiest - Recommended for beginners)
2. **SSH Command Line** (Advanced users)
3. **WMC (Wireless Management Console)** (For fleet management)

---

## Method 1: Web Interface Configuration

### Step 1: Access Gateway Web Interface

1. Connect to gateway's network (Ethernet or Wi-Fi)
2. Open browser and navigate to gateway IP address (default: 192.168.1.1)
3. Login with admin credentials
   - Default username: `admin`
   - Default password: Check gateway label or documentation

### Step 2: Configure Network Server

1. Navigate to: **LoRa > Network Server**
2. Select: **Packet Forwarder Mode**
3. Configure server settings:

```
Network Server Type: Semtech UDP
Server Address: 10.44.1.110
Server Port (Up): 1700
Server Port (Down): 1700
```

4. Click **Save** or **Apply**

### Step 3: Configure Radio Settings

1. Navigate to: **LoRa > Radio Configuration**
2. Configure region and frequency:

```
Region: US915
Frequency Plan: US915
Sub-band: Sub-band 0 (Channels 0-7)
```

3. Advanced settings (if available):
```
Transmit Power: 27 dBm (adjust based on antenna gain)
RSSI Offset: 0 dB
Radio Clock Source: Internal
```

4. Click **Save** or **Apply**

### Step 4: Set Gateway EUI

1. Navigate to: **System > Gateway ID** or **LoRa > Gateway**
2. Note the Gateway EUI (this will be used in ChirpStack)
3. Format: 16 hex characters (example: `0016C001F0000001`)
4. If not set, use gateway's MAC address with padding:
   - MAC: `0016C001F000`
   - Gateway EUI: `0016C001F0000001` (add FFFE in middle for EUI-64)

### Step 5: Verify Configuration

1. Navigate to: **System > Status** or **LoRa > Statistics**
2. Check connection status:
   - **Network Server:** Connected
   - **Packets Received:** Should increment when devices transmit
   - **Packets Forwarded:** Should match received packets

### Step 6: Restart Gateway (if needed)

1. Navigate to: **System > Reboot**
2. Click **Reboot** to apply changes

---

## Method 2: SSH Configuration (Advanced)

### Step 1: SSH into Gateway

```bash
ssh admin@GATEWAY_IP_ADDRESS
# Enter password when prompted
```

### Step 2: Locate Packet Forwarder Configuration

```bash
# Firmware v3.x and v4.x
cd /mnt/fsuser-1/lora/
ls -la

# Look for configuration file:
# - global_conf.json (older firmware)
# - local_conf.json (newer firmware)
```

### Step 3: Backup Current Configuration

```bash
cp global_conf.json global_conf.json.backup
# or
cp local_conf.json local_conf.json.backup
```

### Step 4: Edit Configuration File

```bash
# Use vi or nano editor
vi global_conf.json
```

### Step 5: Configure Server Settings

Modify or add the following section:

```json
{
  "gateway_conf": {
    "gateway_ID": "0016C001F0000001",
    "server_address": "10.44.1.110",
    "serv_port_up": 1700,
    "serv_port_down": 1700,
    "keepalive_interval": 10,
    "stat_interval": 30,
    "push_timeout_ms": 100,
    "forward_crc_valid": true,
    "forward_crc_error": false,
    "forward_crc_disabled": false,
    "gps_tty_path": "/dev/ttyACM0",
    "fake_gps": false,
    "ref_latitude": 0.0,
    "ref_longitude": 0.0,
    "ref_altitude": 0,
    "autoquit_threshold": 20
  }
}
```

### Step 6: Configure Radio Settings (if needed)

Add or modify the `SX1301_conf` section for US915:

```json
{
  "SX1301_conf": {
    "lorawan_public": true,
    "clksrc": 1,
    "antenna_gain": 0,
    "radio_0": {
      "enable": true,
      "type": "SX1257",
      "freq": 902700000,
      "rssi_offset": -166.0,
      "tx_enable": true,
      "tx_freq_min": 902000000,
      "tx_freq_max": 928000000
    },
    "radio_1": {
      "enable": true,
      "type": "SX1257",
      "freq": 903500000,
      "rssi_offset": -166.0,
      "tx_enable": false
    },
    "chan_multiSF_0": { "enable": true, "radio": 0, "if": -400000 },
    "chan_multiSF_1": { "enable": true, "radio": 0, "if": -200000 },
    "chan_multiSF_2": { "enable": true, "radio": 0, "if": 0 },
    "chan_multiSF_3": { "enable": true, "radio": 0, "if": 200000 },
    "chan_multiSF_4": { "enable": true, "radio": 1, "if": -400000 },
    "chan_multiSF_5": { "enable": true, "radio": 1, "if": -200000 },
    "chan_multiSF_6": { "enable": true, "radio": 1, "if": 0 },
    "chan_multiSF_7": { "enable": true, "radio": 1, "if": 200000 },
    "chan_Lora_std": {
      "enable": true,
      "radio": 0,
      "if": 300000,
      "bandwidth": 500000,
      "spread_factor": 8
    },
    "chan_FSK": {
      "enable": false,
      "radio": 0,
      "if": 300000,
      "bandwidth": 125000,
      "datarate": 50000
    },
    "tx_lut_0": { "pa_gain": 0, "mix_gain": 8, "rf_power": -6, "dig_gain": 0 },
    "tx_lut_1": { "pa_gain": 0, "mix_gain": 10, "rf_power": -3, "dig_gain": 0 },
    "tx_lut_2": { "pa_gain": 0, "mix_gain": 12, "rf_power": 0, "dig_gain": 0 },
    "tx_lut_3": { "pa_gain": 1, "mix_gain": 8, "rf_power": 3, "dig_gain": 0 },
    "tx_lut_4": { "pa_gain": 1, "mix_gain": 10, "rf_power": 6, "dig_gain": 0 },
    "tx_lut_5": { "pa_gain": 1, "mix_gain": 12, "rf_power": 10, "dig_gain": 0 },
    "tx_lut_6": { "pa_gain": 1, "mix_gain": 13, "rf_power": 11, "dig_gain": 0 },
    "tx_lut_7": { "pa_gain": 2, "mix_gain": 9, "rf_power": 12, "dig_gain": 0 },
    "tx_lut_8": { "pa_gain": 1, "mix_gain": 15, "rf_power": 13, "dig_gain": 0 },
    "tx_lut_9": { "pa_gain": 2, "mix_gain": 10, "rf_power": 14, "dig_gain": 0 },
    "tx_lut_10": { "pa_gain": 2, "mix_gain": 11, "rf_power": 16, "dig_gain": 0 },
    "tx_lut_11": { "pa_gain": 3, "mix_gain": 9, "rf_power": 20, "dig_gain": 0 },
    "tx_lut_12": { "pa_gain": 3, "mix_gain": 10, "rf_power": 23, "dig_gain": 0 },
    "tx_lut_13": { "pa_gain": 3, "mix_gain": 11, "rf_power": 25, "dig_gain": 0 },
    "tx_lut_14": { "pa_gain": 3, "mix_gain": 12, "rf_power": 26, "dig_gain": 0 },
    "tx_lut_15": { "pa_gain": 3, "mix_gain": 14, "rf_power": 27, "dig_gain": 0 }
  }
}
```

### Step 7: Restart Packet Forwarder

```bash
# Stop packet forwarder
/etc/init.d/lorad stop

# Start packet forwarder
/etc/init.d/lorad start

# Or restart
/etc/init.d/lorad restart

# Check status
/etc/init.d/lorad status
```

### Step 8: Monitor Logs

```bash
# View packet forwarder logs
tail -f /var/log/lora.log

# Look for connection messages:
# - "INFO: [up] PUSH_ACK received"
# - "INFO: [down] PULL_ACK received"
```

---

## Method 3: WMC (Wireless Management Console)

For managing multiple Kerlink gateways:

1. Access WMC portal: https://wmc.kerlink.com
2. Login with Kerlink credentials
3. Select gateway or create group
4. Navigate to: **Configuration > Network Server**
5. Apply settings as described in Method 1
6. Push configuration to gateway(s)

---

## Adding Gateway to ChirpStack

### Step 1: Login to ChirpStack

1. Navigate to: https://chirpstack.sensemy.cloud
2. Login with credentials

### Step 2: Create Gateway Profile (First Time Only)

1. Click: **Gateway Profiles** (left menu)
2. Click: **+ Create**
3. Fill in details:
```
Name: US915 Sub-band 0
Region: US915
Channels: 0-7 (902.3 - 903.7 MHz)
Network Server: Default
```
4. Click: **Create Gateway Profile**

### Step 3: Add Gateway

1. Click: **Gateways** (left menu)
2. Click: **+ Create**
3. Fill in gateway information:

```
Gateway Name: kerlink-gateway-001 (descriptive name)
Gateway Description: Kerlink Wirnet Station - Location XYZ
Gateway ID (EUI): 0016C001F0000001 (from gateway)
Gateway Profile: US915 Sub-band 0
Network Server: Default
Gateway Discovery: Enabled (optional)
Gateway Altitude: 10 (meters above sea level)
Gateway Location: Set on map or enter coordinates
```

4. Click: **Create Gateway**

### Step 4: Verify Connection

1. After ~1 minute, refresh the gateway page
2. Check: **Last seen at:** should show recent timestamp
3. Click: **LoRaWAN frames** tab to see live traffic
4. Status indicator should show: **Online** (green)

---

## Troubleshooting

### Gateway Not Connecting

**Problem:** Gateway shows as offline in ChirpStack

**Solutions:**

1. **Check network connectivity:**
```bash
# From gateway, ping ChirpStack server
ping 10.44.1.110

# Check if UDP 1700 is reachable
nc -u 10.44.1.110 1700
```

2. **Verify packet forwarder is running:**
```bash
ps aux | grep lora
# Should show packet forwarder process
```

3. **Check configuration file:**
```bash
cat /mnt/fsuser-1/lora/global_conf.json
# Verify server_address and ports
```

4. **Review logs:**
```bash
tail -f /var/log/lora.log
# Look for errors or connection issues
```

5. **Check firewall rules:**
```bash
# On gateway (if firewall enabled)
iptables -L -n | grep 1700

# On ChirpStack server (VM 110)
# Should allow inbound UDP 1700
```

6. **Verify Gateway EUI:**
   - EUI in ChirpStack must match gateway configuration
   - Check for typos or incorrect format

### Gateway Connects But No Packets Forwarded

**Problem:** Gateway is online but doesn't forward device packets

**Solutions:**

1. **Check radio configuration:**
   - Verify frequency plan matches region (US915)
   - Ensure sub-band is correct (sub-band 0)
   - Check antenna connection

2. **Verify device settings:**
   - Device must be configured for US915
   - Device must use sub-band 0 channels
   - Device must be registered in ChirpStack

3. **Check packet forwarder settings:**
```json
"forward_crc_valid": true,
"forward_crc_error": false,
```

4. **Monitor gateway statistics:**
```bash
# In ChirpStack web interface
Gateways > [Your Gateway] > Dashboard
# Check RX/TX packet counts
```

### High Packet Loss

**Problem:** Many packets are lost or not acknowledged

**Solutions:**

1. **Check RF environment:**
   - Look for interference sources
   - Verify antenna type and placement
   - Check antenna cable quality

2. **Adjust transmit power:**
   - Lower power if too close to devices
   - Increase power for long-range coverage (max 27 dBm EIRP)

3. **Review spreading factors:**
   - Higher SF = longer range but lower data rate
   - Ensure devices use appropriate SF for distance

4. **Check gateway placement:**
   - Elevate gateway for better line-of-sight
   - Avoid metal structures nearby
   - Ensure weatherproof enclosure doesn't block signal

### GPS Not Working

**Problem:** Gateway location shows incorrect or no GPS coordinates

**Solutions:**

1. **Check GPS antenna:**
   - Ensure GPS antenna is connected
   - Place antenna with clear view of sky
   - Wait 5-10 minutes for GPS lock

2. **Enable GPS in configuration:**
```json
"gps_tty_path": "/dev/ttyACM0",
"fake_gps": false,
```

3. **Set manual coordinates (if GPS unavailable):**
```json
"fake_gps": true,
"ref_latitude": 40.7128,
"ref_longitude": -74.0060,
"ref_altitude": 10,
```

---

## Network Connectivity Requirements

### Firewall Rules (Gateway Side)

Allow outbound traffic:
```
Protocol: UDP
Destination: 10.44.1.110
Port: 1700
Direction: Outbound
```

### Bandwidth Requirements

- **Upstream:** ~10-50 Kbps (packet forwarding)
- **Downstream:** ~5-20 Kbps (downlinks, stats)
- **Latency:** <500ms preferred

### NAT Compatibility

- Semtech UDP protocol works through NAT
- No port forwarding required on gateway side
- Ensure NAT device doesn't timeout UDP sessions too quickly

---

## Advanced Configuration

### Using Custom DNS

If using domain name instead of IP:

```json
"server_address": "chirpstack.sensemy.cloud",
```

**Note:** Ensure gateway can resolve DNS (configure DNS servers if needed)

### Multiple Network Servers (Failover)

Some Kerlink gateways support multiple servers:

```json
"servers": [
  {
    "server_address": "10.44.1.110",
    "serv_port_up": 1700,
    "serv_port_down": 1700
  },
  {
    "server_address": "backup.server.com",
    "serv_port_up": 1700,
    "serv_port_down": 1700
  }
]
```

### Custom Statistics Interval

```json
"stat_interval": 30,
"keepalive_interval": 10,
```

- `stat_interval`: How often gateway sends statistics (seconds)
- `keepalive_interval`: How often to send keepalive packet (seconds)

### Enabling Gateway Discovery

Some gateways support auto-discovery:
1. In ChirpStack: Gateway → Settings → Enable Discovery
2. Gateway will appear automatically when it connects

---

## Security Best Practices

1. **Change default passwords:**
   - Gateway admin interface
   - SSH access

2. **Disable unused services:**
   - Disable SSH if not needed
   - Disable web interface from WAN

3. **Use VPN for management:**
   - Access gateway through VPN
   - Don't expose management interfaces to internet

4. **Regular firmware updates:**
   - Check Kerlink support portal for updates
   - Apply security patches

5. **Monitor gateway access logs:**
```bash
tail -f /var/log/auth.log
```

---

## Useful Commands Reference

```bash
# Check packet forwarder status
/etc/init.d/lorad status

# Restart packet forwarder
/etc/init.d/lorad restart

# View live logs
tail -f /var/log/lora.log

# Check configuration
cat /mnt/fsuser-1/lora/global_conf.json

# Test network connectivity
ping 10.44.1.110

# Check running processes
ps aux | grep lora

# View system information
cat /var/log/sys_startup.log

# Check GPS status
cat /var/log/gps.log

# Reboot gateway
reboot
```

---

## Frequency Plan Details (US915 Sub-band 0)

### Uplink Channels (8 channels)

| Channel | Frequency (MHz) | Bandwidth | Spreading Factors |
|---------|----------------|-----------|-------------------|
| 0 | 902.3 | 125 kHz | SF7-SF10 |
| 1 | 902.5 | 125 kHz | SF7-SF10 |
| 2 | 902.7 | 125 kHz | SF7-SF10 |
| 3 | 902.9 | 125 kHz | SF7-SF10 |
| 4 | 903.1 | 125 kHz | SF7-SF10 |
| 5 | 903.3 | 125 kHz | SF7-SF10 |
| 6 | 903.5 | 125 kHz | SF7-SF10 |
| 7 | 903.7 | 125 kHz | SF7-SF10 |

### Downlink Channels (8 channels)

| Channel | Frequency (MHz) | Bandwidth |
|---------|----------------|-----------|
| 0 | 923.3 | 500 kHz |
| 1 | 923.9 | 500 kHz |
| 2 | 924.5 | 500 kHz |
| 3 | 925.1 | 500 kHz |
| 4 | 925.7 | 500 kHz |
| 5 | 926.3 | 500 kHz |
| 6 | 926.9 | 500 kHz |
| 7 | 927.5 | 500 kHz |

---

## References

- **Kerlink Gateway Documentation:** https://www.kerlink.com/support/
- **ChirpStack Docs:** https://www.chirpstack.io/docs/
- **Semtech Packet Forwarder:** https://github.com/Lora-net/packet_forwarder
- **LoRaWAN Regional Parameters:** https://lora-alliance.org/resource_hub/
- **US915 Frequency Plan:** https://www.thethingsnetwork.org/docs/lorawan/frequencies-by-country/

---

**Last Updated:** 2025-10-01
**Version:** 1.0.0
**Maintained By:** Infrastructure Team
