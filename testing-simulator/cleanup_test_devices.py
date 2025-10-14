#!/usr/bin/env python3
"""
Cleanup Test Devices from ChirpStack
Deletes all devices with DevEUI starting with "TEST"
"""

import yaml
import requests
import sys

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

class ChirpStackDeviceManager:
    def __init__(self, config):
        self.api_url = config['chirpstack']['api_url']
        self.api_token = config['chirpstack']['api_token']
        self.tenant_id = config['chirpstack']['tenant_id']
        self.headers = {
            "Grpc-Metadata-Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    def get_all_devices(self):
        """Get all devices across all applications"""
        devices = []
        
        try:
            # Get all applications
            apps_endpoint = f"{self.api_url}/applications"
            params = {"tenantId": self.tenant_id, "limit": 100}
            response = requests.get(apps_endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"Error getting applications: {response.status_code}")
                return []
            
            applications = response.json().get('result', [])
            
            # Get devices from each application
            for app in applications:
                app_id = app['id']
                devices_endpoint = f"{self.api_url}/devices"
                params = {"applicationId": app_id, "limit": 1000}
                response = requests.get(devices_endpoint, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    app_devices = response.json().get('result', [])
                    devices.extend(app_devices)
            
            return devices
            
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def delete_device(self, dev_eui):
        """Delete a device from ChirpStack"""
        try:
            endpoint = f"{self.api_url}/devices/{dev_eui}"
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Error deleting {dev_eui}: {e}")
            return False

def main():
    print("=" * 80)
    print("ChirpStack Test Device Cleanup")
    print("=" * 80)
    print("\nThis will delete all devices with DevEUI starting with 'TEST'")
    print()
    
    # Load configuration
    config = load_config()
    manager = ChirpStackDeviceManager(config)
    
    # Get all devices
    print("📋 Fetching all devices from ChirpStack...")
    all_devices = manager.get_all_devices()
    print(f"Found {len(all_devices)} total devices")
    
    # Filter test devices
    test_devices = [d for d in all_devices if d.get('devEui', '').startswith('TEST')]
    
    if not test_devices:
        print("\n✓ No test devices found - nothing to delete!")
        sys.exit(0)
    
    # Show test devices
    print(f"\n⚠️  Found {len(test_devices)} TEST devices:")
    for device in test_devices:
        dev_eui = device.get('devEui')
        name = device.get('name', 'Unnamed')
        description = device.get('description', '')
        print(f"  - {dev_eui}: {name}")
        if 'TESTING' in description:
            print(f"    {description[:60]}...")
    
    # Confirm deletion
    print("\n" + "=" * 80)
    response = input(f"Delete these {len(test_devices)} test devices? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    # Delete devices
    print("\n" + "=" * 80)
    print("Deleting test devices...")
    print("=" * 80)
    
    deleted = 0
    failed = 0
    
    for device in test_devices:
        dev_eui = device.get('devEui')
        name = device.get('name', 'Unnamed')
        
        if manager.delete_device(dev_eui):
            print(f"  ✓ Deleted: {name} ({dev_eui})")
            deleted += 1
        else:
            print(f"  ✗ Failed: {name} ({dev_eui})")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("Cleanup Summary")
    print("=" * 80)
    print(f"  Deleted: {deleted}")
    print(f"  Failed: {failed}")
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    main()
