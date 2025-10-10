# ChirpStack Tooling

Tools for managing ChirpStack device profiles and configurations on VM 110.

## Files

- `manage_browan_devices.py` - Unified script to import, list, and delete Browan device profiles
- `.env` - API key configuration

## Usage

### Import Browan Device Profiles

Import all Browan devices for a specific region with "Browan" prefix and default ADR enabled:

```bash
cd /opt/chirpstack/00-chirpstack-tooling

# Import EU868 devices (default)
./manage_browan_devices.py import

# Import US915 devices
./manage_browan_devices.py import --region US902-928

# Import without "Browan" prefix
./manage_browan_devices.py import --no-prefix
```

### List Browan Device Profiles

```bash
./manage_browan_devices.py list
```

### Delete All Browan Device Profiles

```bash
./manage_browan_devices.py delete
```

## Features

When importing, the script automatically:
- ✓ Adds "Browan" prefix to device names (unless --no-prefix)
- ✓ Includes JavaScript payload decoders
- ✓ Enables default LoRa ADR algorithm
- ✓ Configures region-specific settings
- ✓ Skips existing profiles

## Available Browan Devices

1. Ambient Light Sensor
2. Door/Window Sensor
3. Industrial Tracker
4. Motion Sensor
5. Object Locator
6. Sound Level Sensor
7. Temperature & Humidity Sensor
8. Water Leak Sensor

## Supported Regions

- EU863-870 (EU868)
- US902-928 (US915)
- AU915-928 (AU915)
- AS923
- IN865-867 (IN865)

## Configuration

API key is stored in `.env`:

```bash
CHIRPSTACK_API_KEY=your-jwt-token-here
```

Or pass via command line:

```bash
./manage_browan_devices.py import --api-key "your-token"
```

## Repository

Browan device definitions are cloned from:
https://github.com/browanofficial/lorawan-devices

Located at: `/opt/browan-lorawan-devices/`
