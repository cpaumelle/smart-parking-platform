#!/usr/bin/env python3
"""
ChirpStack Bulk Device Import - Adapted for Testing Simulator
Creates 10 test devices (5 sensors + 5 busylights) from CSV
"""

import sys
import csv
import requests
import json

def bulk_import_devices(csv_file, server, api_token):
    """Import devices from CSV file"""
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Grpc-Metadata-Authorization": f"Bearer {api_token}",
    }
    
    success_count = 0
    error_count = 0
    
    print("=" * 80)
    print("ChirpStack Bulk Device Import")
    print("=" * 80)
    print(f"Server: {server}")
    print(f"CSV File: {csv_file}")
    print()
    
    with open(csv_file, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        print(f"CSV Columns: {', '.join(reader.fieldnames)}")
        print()
        
        for row in reader:
            dev_eui = row['deveui']
            name = row['name']
            
            # Create device payload
            payload = {
                "device": {
                    "devEui": dev_eui,
                    "name": name,
                    "applicationId": row['application_id'],
                    "deviceProfileId": row['device_profile_id'],
                    "description": row['description'],
                    "skipFcntCheck": row.get('skip_fcnt_check', 'true').lower() == 'true',
                    "isDisabled": False,
                    "tags": {
                        "simulator": "true",
                        "testing": "true"
                    }
                }
            }
            
            # Create device
            print(f"Creating device: {name} ({dev_eui})...")
            r = requests.post(
                f'http://{server}/api/devices',
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if r.status_code in [200, 201]:
                # Device created successfully, now add keys
                app_key = row['appkey']
                
                payload_keys = {
                    "deviceKeys": {
                        "devEui": dev_eui,
                        "nwkKey": app_key,
                        "appKey": app_key  # For LoRaWAN 1.0.x, both are the same
                    }
                }
                
                r_keys = requests.post(
                    f'http://{server}/api/devices/{dev_eui}/keys',
                    json=payload_keys,
                    headers=headers,
                    timeout=10
                )
                
                if r_keys.status_code in [200, 201]:
                    print(f"  ✓ Device and keys configured successfully")
                    success_count += 1
                else:
                    print(f"  ⚠️  Device created but keys failed: {r_keys.status_code}")
                    print(f"     Response: {r_keys.text}")
                    success_count += 1  # Device still created
                    
            elif r.status_code == 409:
                print(f"  ⚠️  Device already exists (skipping)")
                error_count += 1
            else:
                print(f"  ✗ Failed to create device: {r.status_code}")
                print(f"     Response: {r.text}")
                error_count += 1
            
            print()
    
    print("=" * 80)
    print("Import Summary")
    print("=" * 80)
    print(f"Successfully created: {success_count}")
    print(f"Errors/Skipped: {error_count}")
    print("=" * 80)

if __name__ == "__main__":
    import yaml
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Use config values
    api_url = config['chirpstack']['api_url']
    api_token = config['chirpstack']['api_token']
    
    # Extract server from api_url (remove http:// and /api)
    server = api_url.replace('http://', '').replace('/api', '')
    
    csv_file = 'test_devices.csv'
    
    print(f"\n📋 Using configuration:")
    print(f"   API URL: {api_url}")
    print(f"   Server: {server}")
    print(f"   CSV: {csv_file}\n")
    
    bulk_import_devices(csv_file, server, api_token)
