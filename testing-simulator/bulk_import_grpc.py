#!/usr/bin/env python3
"""
ChirpStack Bulk Device Import using gRPC API
Creates test devices from CSV file
"""

import sys
import csv
import grpc
from chirpstack_api import api

def create_device_with_keys(client, auth_token, dev_eui, name, description, 
                           app_id, profile_id, app_key, skip_fcnt):
    """Create a device and set its OTAA keys"""
    
    try:
        # Create device
        device = api.Device()
        device.dev_eui = bytes.fromhex(dev_eui)
        device.name = name
        device.description = description
        # application_id field may not exist in protobuf
        # device.application_id = app_id
        # device_profile_id field may not exist in protobuf
        # device.device_profile_id = profile_id
        # Skip fcnt check not available in protobuf
        device.is_disabled = False
        device.tags.update({"simulator": "true", "testing": "true"})
        
        req = api.CreateDeviceRequest()
        req.device.CopyFrom(device)
        
        client.Create(req, metadata=auth_token)
        print(f"  ✓ Device created: {name}")
        
        # Set device keys
        device_keys = api.DeviceKeys()
        device_keys.dev_eui = bytes.fromhex(dev_eui)
        device_keys.nwk_key = bytes.fromhex(app_key)
        device_keys.app_key = bytes.fromhex(app_key)
        
        keys_req = api.CreateDeviceKeysRequest()
        keys_req.device_keys.CopyFrom(device_keys)
        
        client.CreateKeys(keys_req, metadata=auth_token)
        print(f"  ✓ Keys configured")
        
        return True
        
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.ALREADY_EXISTS:
            print(f"  ⚠️  Device already exists (skipping)")
            return False
        else:
            print(f"  ✗ Error: {e.code()} - {e.details()}")
            return False
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return False

def bulk_import(csv_file, server, api_token):
    """Import devices from CSV"""
    
    print("=" * 80)
    print("ChirpStack Bulk Device Import (gRPC)")
    print("=" * 80)
    print(f"Server: {server}")
    print(f"CSV File: {csv_file}")
    print()
    
    # Create gRPC channel
    channel = grpc.insecure_channel(server)
    client = api.DeviceServiceStub(channel)
    auth_token = [("authorization", f"Bearer {api_token}")]
    
    success_count = 0
    error_count = 0
    
    with open(csv_file, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        print(f"CSV Columns: {', '.join(reader.fieldnames)}\n")
        
        for row in reader:
            print(f"Creating: {row['name']} ({row['deveui']})...")
            
            success = create_device_with_keys(
                client=client,
                auth_token=auth_token,
                dev_eui=row['deveui'],
                name=row['name'],
                description=row['description'],
                app_id=row['application_id'],
                profile_id=row['device_profile_id'],
                app_key=row['appkey'],
                skip_fcnt=row.get('skip_fcnt_check', 'true').lower() == 'true'
            )
            
            if success:
                success_count += 1
            else:
                error_count += 1
            
            print()
    
    channel.close()
    
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
    
    api_url = config['chirpstack']['api_url']
    api_token = config['chirpstack']['api_token']
    
    # Extract server (remove http:// and /api)
    server = api_url.replace('http://', '').replace('/api', '')
    
    csv_file = 'test_devices.csv'
    
    print(f"\n📋 Configuration:")
    print(f"   Server: {server}")
    print(f"   CSV: {csv_file}\n")
    
    bulk_import(csv_file, server, api_token)
