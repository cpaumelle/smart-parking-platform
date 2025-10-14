#!/usr/bin/env python3
"""
Create Test Devices in ChirpStack
Creates 10 clearly labeled TESTING devices:
- 5 parking sensors (Class A)
- 5 Kuando Busylights (Class C)
"""

import yaml
import requests
import sys
import secrets

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
    
    def get_device_profiles(self):
        """Get all device profiles"""
        try:
            endpoint = f"{self.api_url}/device-profiles"
            params = {"tenantId": self.tenant_id, "limit": 100}
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            else:
                print(f"Error getting device profiles: {response.status_code}")
                print(f"Response: {response.text}")
                return []
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_applications(self):
        """Get all applications"""
        try:
            endpoint = f"{self.api_url}/applications"
            params = {"tenantId": self.tenant_id, "limit": 100}
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            else:
                print(f"Error getting applications: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def create_device(self, dev_eui, name, description, application_id, device_profile_id):
        """Create a device in ChirpStack"""
        try:
            device_data = {
                "device": {
                    "devEui": dev_eui,
                    "name": name,
                    "applicationId": application_id,
                    "deviceProfileId": device_profile_id,
                    "description": description,
                    "skipFcntCheck": True,  # Helpful for testing
                    "isDisabled": False
                }
            }
            
            endpoint = f"{self.api_url}/devices"
            response = requests.post(endpoint, headers=self.headers, json=device_data, timeout=10)
            
            if response.status_code in [200, 201]:
                return True, "Device created successfully"
            elif response.status_code == 409:
                return False, "Device already exists"
            else:
                return False, f"Error {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, f"Exception: {e}"
    
    def create_device_keys(self, dev_eui, app_key=None, nwk_key=None):
        """Create device keys for OTAA"""
        try:
            if not app_key:
                app_key = secrets.token_hex(16)  # Generate random 128-bit key
            if not nwk_key:
                nwk_key = app_key  # For LoRaWAN 1.0.x, nwkKey = appKey
            
            keys_data = {
                "deviceKeys": {
                    "devEui": dev_eui,
                    "nwkKey": nwk_key,
                    "appKey": app_key
                }
            }
            
            endpoint = f"{self.api_url}/devices/{dev_eui}/keys"
            response = requests.post(endpoint, headers=self.headers, json=keys_data, timeout=10)
            
            if response.status_code in [200, 201]:
                return True, app_key, nwk_key
            else:
                return False, None, None
                
        except Exception as e:
            print(f"Error creating keys: {e}")
            return False, None, None

def main():
    print("=" * 80)
    print("ChirpStack Test Device Creator")
    print("=" * 80)
    print("\nThis will create 10 TESTING devices:")
    print("  - 5 parking sensors (Class A)")
    print("  - 5 Kuando Busylights (Class C)")
    print()
    
    # Load configuration
    config = load_config()
    manager = ChirpStackDeviceManager(config)
    
    # Get device profiles
    print("📋 Fetching device profiles...")
    profiles = manager.get_device_profiles()
    
    if not profiles:
        print("❌ No device profiles found!")
        sys.exit(1)
    
    # Find the right profiles
    class_a_profile = None
    class_c_profile = None
    
    for profile in profiles:
        name = profile.get('name', '').lower()
        if 'busylight' in name or 'kuando' in name:
            class_c_profile = profile
        elif 'class a' in name and not class_a_profile:
            class_a_profile = profile
    
    if not class_a_profile or not class_c_profile:
        print("❌ Could not find required device profiles!")
        print("\nAvailable profiles:")
        for p in profiles:
            print(f"  - {p['name']} (ID: {p['id']})")
        sys.exit(1)
    
    print(f"✓ Class A Profile: {class_a_profile['name']}")
    print(f"✓ Class C Profile: {class_c_profile['name']}")
    
    # Get applications
    print("\n📋 Fetching applications...")
    apps = manager.get_applications()
    
    if not apps:
        print("❌ No applications found!")
        sys.exit(1)
    
    # Find the right applications
    sensor_app = None
    busylight_app = None
    
    for app in apps:
        name = app.get('name', '').lower()
        if 'class a' in name:
            sensor_app = app
        elif 'class c' in name or 'led' in name:
            busylight_app = app
    
    if not sensor_app or not busylight_app:
        print("❌ Could not find required applications!")
        print("\nAvailable applications:")
        for a in apps:
            print(f"  - {a['name']} (ID: {a['id']})")
        sys.exit(1)
    
    print(f"✓ Sensor Application: {sensor_app['name']}")
    print(f"✓ Busylight Application: {busylight_app['name']}")
    
    # Confirm creation
    print("\n" + "=" * 80)
    response = input("Create 10 test devices? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    print("\n" + "=" * 80)
    print("Creating devices...")
    print("=" * 80)
    
    created = 0
    failed = 0
    device_info = []
    
    # Create 5 parking sensors
    print("\n🚗 Creating 5 TESTING parking sensors...")
    for i in range(5):
        dev_eui = f"TEST{i:04d}SENSOR00"  # TEST0000SENSOR00, etc.
        name = f"TESTING Sensor {i+1}"
        description = f"⚠️ TESTING ONLY - Simulated parking sensor {i+1} - Safe to delete"
        
        success, message = manager.create_device(
            dev_eui=dev_eui,
            name=name,
            description=description,
            application_id=sensor_app['id'],
            device_profile_id=class_a_profile['id']
        )
        
        if success:
            # Create OTAA keys
            keys_success, app_key, nwk_key = manager.create_device_keys(dev_eui)
            
            if keys_success:
                print(f"  ✓ {name} ({dev_eui})")
                device_info.append({
                    'type': 'sensor',
                    'name': name,
                    'dev_eui': dev_eui,
                    'app_key': app_key,
                    'nwk_key': nwk_key
                })
                created += 1
            else:
                print(f"  ⚠️  {name} ({dev_eui}) - device created but keys failed")
                created += 1
        else:
            print(f"  ✗ {name} ({dev_eui}) - {message}")
            failed += 1
    
    # Create 5 Kuando Busylights
    print("\n💡 Creating 5 TESTING Kuando Busylights...")
    for i in range(5):
        dev_eui = f"TEST{i:04d}BUSYLT00"  # TEST0000BUSYLT00, etc.
        name = f"TESTING Busylight {i+1}"
        description = f"⚠️ TESTING ONLY - Simulated Kuando Busylight {i+1} - Safe to delete"
        
        success, message = manager.create_device(
            dev_eui=dev_eui,
            name=name,
            description=description,
            application_id=busylight_app['id'],
            device_profile_id=class_c_profile['id']
        )
        
        if success:
            # Create OTAA keys
            keys_success, app_key, nwk_key = manager.create_device_keys(dev_eui)
            
            if keys_success:
                print(f"  ✓ {name} ({dev_eui})")
                device_info.append({
                    'type': 'busylight',
                    'name': name,
                    'dev_eui': dev_eui,
                    'app_key': app_key,
                    'nwk_key': nwk_key
                })
                created += 1
            else:
                print(f"  ⚠️  {name} ({dev_eui}) - device created but keys failed")
                created += 1
        else:
            print(f"  ✗ {name} ({dev_eui}) - {message}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("Device Creation Summary")
    print("=" * 80)
    print(f"  Created: {created}")
    print(f"  Failed: {failed}")
    
    # Save device information
    if device_info:
        print("\n📝 Saving device information to test_devices_keys.txt...")
        with open('test_devices_keys.txt', 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("TESTING Devices - Created on ChirpStack\n")
            f.write("=" * 80 + "\n\n")
            f.write("⚠️  IMPORTANT: These are test devices - safe to delete\n")
            f.write("⚠️  Keep these keys secure - they allow devices to join the network\n\n")
            
            for device in device_info:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"Type: {device['type'].upper()}\n")
                f.write(f"Name: {device['name']}\n")
                f.write(f"DevEUI: {device['dev_eui']}\n")
                f.write(f"AppKey: {device['app_key']}\n")
                f.write(f"NwkKey: {device['nwk_key']}\n")
        
        print(f"  ✓ Saved to: test_devices_keys.txt")
    
    print("\n" + "=" * 80)
    print("✅ Device creation complete!")
    print("=" * 80)
    
    if created > 0:
        print("\n📌 Next Steps:")
        print("  1. Check ChirpStack UI to verify devices appear")
        print("  2. Use the keys in test_devices_keys.txt for device configuration")
        print("  3. Test sending uplinks from sensors")
        print("  4. Test sending downlinks to busylights")
        print(f"  5. Delete devices when done: python cleanup_test_devices.py")
    
    print("\n💡 Tip: All test devices are clearly marked as 'TESTING' in ChirpStack")

if __name__ == "__main__":
    main()
