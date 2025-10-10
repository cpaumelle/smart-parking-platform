#!/usr/bin/env python3
"""
Manage Browan Device Profiles in ChirpStack
- Import device profiles with codecs from Browan repository
- Rename profiles with "Browan" prefix
- Enable default ADR algorithm
"""

import os
import sys
import yaml
import grpc
from pathlib import Path
from chirpstack_api import api
from chirpstack_api import common

# Configuration
BROWAN_REPO = "/opt/browan-lorawan-devices/vendor/browan"
CHIRPSTACK_SERVER = "localhost:8080"
DEFAULT_REGION = "EU863-870"

# Region mapping
REGION_MAP = {
    "EU863-870": "EU868",
    "US902-928": "US915",
    "AU915-928": "AU915",
    "AS923": "AS923",
    "IN865-867": "IN865"
}

# MAC version mapping
MAC_VERSION_MAP = {
    "1.0": common.MacVersion.LORAWAN_1_0_0,
    "1.0.1": common.MacVersion.LORAWAN_1_0_1,
    "1.0.2": common.MacVersion.LORAWAN_1_0_2,
    "1.0.3": common.MacVersion.LORAWAN_1_0_3,
    "1.0.4": common.MacVersion.LORAWAN_1_0_4,
    "1.1": common.MacVersion.LORAWAN_1_1_0,
}

# RegParams mapping
REG_PARAMS_MAP = {
    "TS001-1.0": common.RegParamsRevision.A,
    "TS001-1.0.1": common.RegParamsRevision.A,
    "RP001-1.0.2": common.RegParamsRevision.B,
    "RP001-1.0.2-RevB": common.RegParamsRevision.B,
    "RP001-1.0.3-RevA": common.RegParamsRevision.A,
    "RP002-1.0.0": common.RegParamsRevision.A,
    "RP002-1.0.1": common.RegParamsRevision.B,
    "RP001-1.1-RevA": common.RegParamsRevision.A,
    "RP001-1.1-RevB": common.RegParamsRevision.B,
}

def load_env():
    """Load API key from .env if available"""
    env_file = "/opt/iot-platform/00-chirsptack-tooling/.env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith('CHIRPSTACK_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return None

def get_device_files():
    """Get all Browan device definition files"""
    devices = []
    for f in Path(BROWAN_REPO).glob("*.yaml"):
        # Skip profile, codec, and index files
        if not any(x in f.name for x in ['-profile', '-codec', 'index']):
            devices.append(f)
    return devices

def load_codec(codec_file):
    """Load JavaScript codec from file"""
    if os.path.exists(codec_file):
        with open(codec_file, 'r') as f:
            return f.read()
    return None

def create_device_profile(channel, auth_token, tenant_id, device_info, region, add_prefix=True):
    """Create a device profile in ChirpStack"""

    # Load device YAML
    with open(device_info['yaml_file'], 'r') as f:
        device_data = yaml.safe_load(f)

    # Get profile for region
    firmware = device_data['firmwareVersions'][0]
    if region not in firmware['profiles']:
        return {'skipped': True, 'name': device_data['name']}

    profile_data = firmware['profiles'][region]
    profile_id = profile_data['id']

    # Load profile YAML
    profile_file = Path(BROWAN_REPO) / f"{profile_id}.yaml"
    with open(profile_file, 'r') as f:
        profile_yaml = yaml.safe_load(f)

    # Load codec JavaScript
    codec_name = profile_data.get('codec')
    codec_js = ""
    if codec_name:
        codec_file = Path(BROWAN_REPO) / f"{codec_name}.js"
        codec_js = load_codec(codec_file) or ""

    # Create device profile
    client = api.DeviceProfileServiceStub(channel)
    req = api.CreateDeviceProfileRequest()

    # Add Browan prefix if requested
    profile_name = device_data['name']
    if add_prefix and not profile_name.startswith('Browan'):
        profile_name = f"Browan {profile_name}"

    req.device_profile.tenant_id = tenant_id
    req.device_profile.name = profile_name
    req.device_profile.description = device_data.get('description', '')
    req.device_profile.region = REGION_MAP.get(region, "EU868")
    req.device_profile.mac_version = MAC_VERSION_MAP.get(profile_yaml['macVersion'], common.MacVersion.LORAWAN_1_0_3)
    req.device_profile.reg_params_revision = REG_PARAMS_MAP.get(profile_yaml['regionalParametersVersion'], common.RegParamsRevision.A)
    req.device_profile.supports_otaa = profile_yaml.get('supportsJoin', True)
    req.device_profile.supports_class_b = profile_yaml.get('supportsClassB', False)
    req.device_profile.supports_class_c = profile_yaml.get('supportsClassC', False)
    req.device_profile.adr_algorithm_id = "default"  # Enable default ADR

    # Add codec if available
    if codec_js:
        req.device_profile.payload_codec_runtime = api.CodecRuntime.JS
        req.device_profile.payload_codec_script = codec_js

    try:
        resp = client.Create(req, metadata=auth_token)
        return {
            'success': True,
            'id': resp.id,
            'name': profile_name,
            'region': region
        }
    except grpc.RpcError as e:
        if "object already exists" in str(e):
            return {'error': 'exists', 'name': profile_name}
        else:
            return {'error': str(e), 'name': profile_name}

def list_profiles(channel, auth_token, tenant_id):
    """List all Browan device profiles"""
    profile_client = api.DeviceProfileServiceStub(channel)
    req = api.ListDeviceProfilesRequest()
    req.tenant_id = tenant_id
    req.limit = 100
    resp = profile_client.List(req, metadata=auth_token)

    browan_profiles = [p for p in resp.result if 'browan' in p.name.lower()]
    return browan_profiles

def delete_profiles(channel, auth_token, tenant_id):
    """Delete all Browan device profiles"""
    profile_client = api.DeviceProfileServiceStub(channel)
    profiles = list_profiles(channel, auth_token, tenant_id)

    deleted = 0
    for profile in profiles:
        req = api.DeleteDeviceProfileRequest()
        req.id = profile.id
        try:
            profile_client.Delete(req, metadata=auth_token)
            print(f"  ✓ Deleted: {profile.name}")
            deleted += 1
        except Exception as e:
            print(f"  ✗ Error deleting {profile.name}: {e}")

    return deleted

def import_profiles(channel, auth_token, tenant_id, region, add_prefix=True):
    """Import all Browan device profiles"""
    device_files = get_device_files()
    print(f"Found {len(device_files)} Browan devices")
    print()

    created = 0
    skipped = 0
    errors = 0

    for device_file in sorted(device_files):
        device_name = device_file.stem.replace('-', ' ').title()
        print(f"Processing: {device_name}")

        result = create_device_profile(
            channel,
            auth_token,
            tenant_id,
            {'yaml_file': device_file},
            region,
            add_prefix
        )

        if result.get('skipped'):
            print(f"  ⚠ Region {region} not supported, skipping")
            skipped += 1
        elif 'error' in result:
            if result['error'] == 'exists':
                print(f"  ✓ Already exists")
                skipped += 1
            else:
                print(f"  ✗ Error: {result['error']}")
                errors += 1
        elif result.get('success'):
            print(f"  ✓ Created: {result['name']} (ID: {result['id']})")
            created += 1

    return created, skipped, errors

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Manage Browan device profiles in ChirpStack')
    parser.add_argument('action', choices=['import', 'list', 'delete'], help='Action to perform')
    parser.add_argument('--api-key', help='ChirpStack API key (or set in .env)')
    parser.add_argument('--region', default=DEFAULT_REGION, help=f'LoRaWAN region (default: {DEFAULT_REGION})')
    parser.add_argument('--no-prefix', action='store_true', help='Do not add "Browan" prefix to device names')

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or load_env()
    if not api_key:
        print("Error: No API key provided")
        print("Usage: manage_browan_devices.py <action> --api-key <key>")
        print("Or configure CHIRPSTACK_API_KEY in /opt/iot-platform/00-chirsptack-tooling/.env")
        sys.exit(1)

    # Connect to ChirpStack
    channel = grpc.insecure_channel(CHIRPSTACK_SERVER)
    auth_token = [("authorization", f"Bearer {api_key}")]

    # Get tenant ID
    tenant_client = api.TenantServiceStub(channel)
    req = api.ListTenantsRequest()
    req.limit = 1
    resp = tenant_client.List(req, metadata=auth_token)

    if not resp.result:
        print("Error: No tenants found")
        sys.exit(1)

    tenant_id = resp.result[0].id
    print(f"Tenant: {resp.result[0].name}")

    if args.action == 'import':
        print(f"Region: {args.region} → {REGION_MAP.get(args.region, args.region)}")
        print()
        created, skipped, errors = import_profiles(
            channel,
            auth_token,
            tenant_id,
            args.region,
            not args.no_prefix
        )
        print()
        print("=" * 50)
        print(f"Summary:")
        print(f"  Created: {created}")
        print(f"  Skipped: {skipped}")
        print(f"  Errors: {errors}")
        print()
        print(f"View at: https://chirpstack.sensemy.cloud")

    elif args.action == 'list':
        profiles = list_profiles(channel, auth_token, tenant_id)
        print()
        print(f"Found {len(profiles)} Browan device profiles:")
        for p in profiles:
            print(f"  • {p.name} ({p.id})")

    elif args.action == 'delete':
        print()
        confirm = input("Are you sure you want to delete all Browan profiles? (yes/no): ")
        if confirm.lower() == 'yes':
            deleted = delete_profiles(channel, auth_token, tenant_id)
            print()
            print(f"Deleted {deleted} device profiles")
        else:
            print("Cancelled")

if __name__ == "__main__":
    main()
