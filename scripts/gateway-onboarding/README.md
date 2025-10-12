# Gateway Onboarding Scripts - Smart Parking Platform

Automated scripts and documentation for onboarding Kerlink LoRaWAN gateways to the Smart Parking Platform ChirpStack network server.

## Quick Start

```bash
cd /opt/smart-parking/scripts/gateway-onboarding
cp .env.example .env
nano .env  # Add your ChirpStack API key
./onboard_kerlink_gateway.sh
```

## Documentation

- **SETUP.md** - Quick setup guide with step-by-step instructions

- **WEBSOCKET-SETUP.md** - WebSocket connection configuration details

## Scripts

### onboard_kerlink_gateway.sh

**Main automated onboarding script**

Features:
- ✅ Optional factory reset for clean gateway state
- ✅ Automatic gateway discovery (EUI, hostname, system info)
- ✅ Basic Station 3.4.1 installation
- ✅ ChirpStack registration via gRPC API (Python inline)
- ✅ Configuration validation and health checks
- ✅ Comprehensive error handling

Usage:
```bash
# Standard onboarding
./onboard_kerlink_gateway.sh

# With factory reset
./onboard_kerlink_gateway.sh --factory-reset
```

### manage_browan_devices.py

**Device management utility** for Browan sensor operations

## Platform Configuration

- **Domain:** verdegris.eu
- **ChirpStack Web:** https://chirpstack.verdegris.eu
- **ChirpStack gRPC:** parking-chirpstack:8080 (internal Docker)
- **Gateway WebSocket:** wss://chirpstack-gw.verdegris.eu:3002
- **Region:** EU868 (863-870 MHz)

## Requirements
- **KerOS Version:** 6.3+ compatible (uses Basic Station 3.4.1 with klk_bs_config)

- SSH access to gateway (default: admin user)
- ChirpStack API key with Admin permissions
- Gateway on same network or routable to VPS
- `sshpass` installed on host: `apt install sshpass`

## Environment Variables

Required in `.env`:
- `CHIRPSTACK_API_KEY` - Admin API key from ChirpStack UI

Optional (have sensible defaults):
- `CHIRPSTACK_GRPC_SERVER` - gRPC endpoint
- `CHIRPSTACK_WEB_URL` - Web UI URL
- `LNS_WEBSOCKET_URL` - Gateway WebSocket URL
- `DEFAULT_GATEWAY_NAME_PREFIX` - Gateway naming prefix
- `GATEWAY_STATS_INTERVAL` - Stats reporting interval (seconds)

## What the Script Does

1. **Gateway Discovery**
   - SSH into gateway
   - Extract Gateway EUI (via `klk_get_gweui` or other methods)
   - Read hostname, kernel version, architecture

2. **Basic Station Installation**
   - Downloads Basic Station 3.4.1 and Lorad packages from Kerlink
   - Installs via `opkg`
   - Configures monit monitoring

3. **ChirpStack Configuration**
   - Sets LNS WebSocket URL in `/user/basic_station/etc/tc.uri`
   - Starts Basic Station with `klk_bs_config --enable`
   - Starts monit monitoring

4. **Gateway Registration**
   - Registers gateway in ChirpStack via gRPC (Python inline script)
   - Associates with first available tenant
   - Sets statistics interval

5. **Verification**
   - Checks configuration files
   - Monitors process status
   - Reviews connection logs
   - Reports health status

## Troubleshooting

### Gateway Not Connecting

```bash
# On gateway, check logs
ssh admin@GATEWAY_IP
## Region Configuration

Configured for **EU868** (863-870 MHz) - standard European ISM band.

- Default channels: 868.1, 868.3, 868.5 MHz
- Additional channels configurable within 863-870 MHz range
- Automatic configuration via ChirpStack Gateway Profile

# Check process
ps | grep station
```

### Script Errors

- **SSH timeout:** Verify gateway IP and SSH access
- **API key error:** Regenerate API key with Admin permissions
- **Gateway already exists:** Normal - gateway was previously registered
- **Package download fails:** Check gateway internet connectivity

## Region Support

Currently configured for **US915 Sub-band 0** (Channels 0-7).

For EU868 or other regions, update:
- Gateway radio configuration
- ChirpStack Gateway Profile
- Frequency plan in script

## Security Notes

- Store `.env` file securely: `chmod 600 .env`
- Never commit API keys to version control
- Use gateway default user (admin) - don't expose root
- Factory reset removes all custom credentials

## Support

For issues or questions:
- Check SETUP.md for common problems
- Review KERLINK_GATEWAY_SETUP.md for manual configuration
- Contact platform administrator

---

**Last Updated:** 2025-10-10
**Platform:** Smart Parking Platform (verdegris.eu)
**ChirpStack Version:** 4.14.1
