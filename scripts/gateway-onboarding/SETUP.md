# Quick Setup Guide - Smart Parking Platform

## First Time Setup

1. **Navigate to the gateway onboarding directory:**
   ```bash
   cd /opt/smart-parking/scripts/gateway-onboarding
   ```

2. **Create your .env file:**
   ```bash
   cp .env.example .env
   ```

3. **Get your ChirpStack API key:**
   - Visit: https://chirpstack.verdegris.eu
   - Login with your credentials (default: admin/admin)
   - Go to: User → API Keys → Add API Key
   - Create key with "Admin" permissions
   - Copy the generated key

4. **Edit .env and add your API key:**
   ```bash
   nano .env
   ```

   Change this line:
   ```
   CHIRPSTACK_API_KEY=
   ```

   To:
   ```
   CHIRPSTACK_API_KEY=your-actual-api-key-here
   ```

   Save and exit (Ctrl+X, Y, Enter)

5. **Secure the .env file:**
   ```bash
   chmod 600 .env
   ```

## Running the Script

```bash
./onboard_kerlink_gateway.sh
```

You'll be prompted for:
- Gateway IP address
- Gateway admin password
- Gateway name (optional - defaults to Parking-Gateway-XXXXXXXX)
- Gateway description (optional)

The script handles everything else automatically!

## Optional: Factory Reset

To wipe a gateway to factory defaults before onboarding:

```bash
./onboard_kerlink_gateway.sh --factory-reset
```

**Warning:** This will erase ALL gateway configuration and reboot the gateway!

## Configuration Variables Reference

### .env.example contents:

```bash
# ChirpStack Configuration for Smart Parking Platform (verdegris.eu)
CHIRPSTACK_API_KEY=                                         # REQUIRED: Get from ChirpStack UI
CHIRPSTACK_GRPC_SERVER=parking-chirpstack:8080             # Internal Docker service name
CHIRPSTACK_WEB_URL=https://chirpstack.verdegris.eu        # Web UI URL
LNS_WEBSOCKET_URL=wss://chirpstack-gw.verdegris.eu:3002   # Gateway Basic Station WebSocket URL

# Default Gateway Settings
DEFAULT_GATEWAY_NAME_PREFIX=Parking-Gateway                # Prefix for auto-generated names
GATEWAY_STATS_INTERVAL=30                                  # Stats reporting interval (seconds)

# Gateway SSH Configuration (optional - will prompt if not set)
# GATEWAY_IP=                                               # Pre-set gateway IP to skip prompt
# GATEWAY_PASSWORD=                                         # Pre-set password (not recommended)
GATEWAY_DEFAULT_USER=admin                                 # SSH username (default: admin)
```

## What the Script Does

1. **Gathers Gateway Information**
   - Connects via SSH to the gateway
   - Detects Gateway EUI automatically
   - Reads hostname and system information

2. **Installs Basic Station**
   - Downloads Kerlink Basic Station package (3.4.1)
   - Installs Lorad and Basic Station packages
   - Configures monit monitoring

3. **Configures ChirpStack Connection**
   - Sets LNS WebSocket URL
   - Creates configuration files
   - Starts Basic Station service

4. **Registers in ChirpStack**
   - Automatically registers gateway via gRPC API
   - Associates with default tenant
   - Sets statistics reporting interval

5. **Verifies Installation**
   - Checks service status
   - Monitors connection logs
   - Reports any issues

## Troubleshooting

### Script can't connect to gateway

- Verify gateway IP is correct
- Check SSH is enabled on gateway
- Ensure correct password
- Install `sshpass` if missing: `apt install sshpass`

### Gateway doesn't appear in ChirpStack

- Wait 1-2 minutes for initial connection
- Check gateway logs: `ssh admin@GATEWAY_IP 'tail -f /var/log/messages | grep station'`
- Verify WebSocket URL in `/user/basic_station/etc/tc.uri`
- Restart service: `ssh admin@GATEWAY_IP 'monit restart station'`

### API Key errors

- Regenerate API key in ChirpStack UI
- Ensure API key has "Admin" permissions
- Check for extra spaces when copying key

## Next Steps

Once configured, you can run the script anytime to onboard new gateways. The API key is stored securely in `.env` and won't need to be entered again.

For detailed gateway configuration and troubleshooting, see:
- `KERLINK_GATEWAY_SETUP.md` - Comprehensive manual configuration guide
- `WEBSOCKET-SETUP.md` - WebSocket connection details

---

**Platform:** Smart Parking Platform
**Domain:** verdegris.eu
**Last Updated:** 2025-10-10
