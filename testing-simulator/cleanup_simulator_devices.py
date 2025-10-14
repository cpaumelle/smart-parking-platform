#!/usr/bin/env python3
"""
Cleanup script to delete all simulator devices from ChirpStack
Deletes devices with DevEUI prefixes: PARK* and BUSY*
"""

import sys
import yaml
import requests
from typing import List

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_devices(api_url, api_token, application_id) -> List[dict]:
    """Get all devices in an application"""
    headers = {"Grpc-Metadata-Authorization": f"Bearer {api_token}"}
    endpoint = f"{api_url}/applications/{application_id}/devices"
    
    try:
        response = requests.get(f"{endpoint}?limit=1000", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('result', [])
        else:
            print(f"Error getting devices: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def delete_device(api_url, api_token, dev_eui: str) -> bool:
    """Delete a device from ChirpStack"""
    headers = {"Grpc-Metadata-Authorization": f"Bearer {api_token}"}
    endpoint = f"{api_url}/devices/{dev_eui}"
    
    try:
        response = requests.delete(endpoint, headers=headers, timeout=10)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"Error deleting {dev_eui}: {e}")
        return False

def main():
    # Load configuration
    config = load_config()
    
    api_url = config['chirpstack']['api_url']
    api_token = config['chirpstack']['api_token']
    application_id = config['chirpstack']['application_id']
    
    sensor_prefix = config['simulation']['sensor_dev_eui_prefix']
    busylight_prefix = config['simulation']['busylight_dev_eui_prefix']
    
    print(f"Cleanup Simulator Devices")
    print(f"=" * 80)
    print(f"API URL: {api_url}")
    print(f"Application ID: {application_id}")
    print(f"Looking for devices with prefixes: {sensor_prefix}*, {busylight_prefix}*")
    print()
    
    # Get all devices
    print("Fetching devices from ChirpStack...")
    devices = get_devices(api_url, api_token, application_id)
    print(f"Found {len(devices)} total devices in application")
    
    # Filter simulator devices
    simulator_devices = [
        d for d in devices 
        if d.get('devEui', '').startswith(sensor_prefix) or 
           d.get('devEui', '').startswith(busylight_prefix)
    ]
    
    if not simulator_devices:
        print(f"\n✓ No simulator devices found to delete")
        return
    
    print(f"\nFound {len(simulator_devices)} simulator devices:")
    for device in simulator_devices:
        print(f"  - {device.get('devEui')}: {device.get('name')}")
    
    # Confirm deletion
    print(f"\n⚠️  This will delete {len(simulator_devices)} devices from ChirpStack!")
    response = input("Continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Delete devices
    print("\nDeleting devices...")
    deleted = 0
    failed = 0
    
    for device in simulator_devices:
        dev_eui = device.get('devEui')
        if delete_device(api_url, api_token, dev_eui):
            print(f"  ✓ Deleted: {dev_eui}")
            deleted += 1
        else:
            print(f"  ✗ Failed: {dev_eui}")
            failed += 1
    
    print()
    print(f"=" * 80)
    print(f"Cleanup complete!")
    print(f"  Deleted: {deleted}")
    print(f"  Failed: {failed}")
    print(f"=" * 80)

if __name__ == "__main__":
    main()
