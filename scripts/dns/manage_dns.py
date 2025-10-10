#!/usr/bin/env python3
"""
OVH DNS Management Script for verdegris.eu
Manages DNS records via OVH API
"""

import ovh
import sys
import configparser

# Configuration
ZONE = "verdegris.eu"
CONFIG_FILE = "/opt/smart-parking/scripts/dns/ovh.conf"

def get_client():
    """Initialize OVH API client from config file"""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    return ovh.Client(
        endpoint=config['default']['endpoint'],
        application_key=config['default']['application_key'],
        application_secret=config['default']['application_secret'],
        consumer_key=config['default']['consumer_key']
    )

def list_records(subdomain=None):
    """List all DNS records or filter by subdomain"""
    client = get_client()
    
    if subdomain:
        records = client.get(f'/domain/zone/{ZONE}/record', fieldType='A', subDomain=subdomain)
    else:
        records = client.get(f'/domain/zone/{ZONE}/record', fieldType='A')
    
    print(f"\n{'ID':<10} {'Subdomain':<30} {'Target':<20} {'TTL':<10}")
    print("-" * 70)
    
    for record_id in records:
        record = client.get(f'/domain/zone/{ZONE}/record/{record_id}')
        subdomain_display = record['subDomain'] if record['subDomain'] else '@'
        print(f"{record['id']:<10} {subdomain_display:<30} {record['target']:<20} {record['ttl']:<10}")
    
    return records

def add_record(subdomain, target_ip, ttl=3600):
    """Add a new A record"""
    client = get_client()
    
    print(f"Adding DNS record: {subdomain}.{ZONE} -> {target_ip}")
    
    try:
        result = client.post(f'/domain/zone/{ZONE}/record',
            fieldType='A',
            subDomain=subdomain,
            target=target_ip,
            ttl=ttl
        )
        
        # Refresh zone to apply changes
        client.post(f'/domain/zone/{ZONE}/refresh')
        
        print(f"✅ Record added successfully! ID: {result['id']}")
        print(f"   {subdomain}.{ZONE} -> {target_ip}")
        return result['id']
        
    except Exception as e:
        print(f"❌ Error adding record: {e}")
        return None

def delete_record(record_id):
    """Delete a DNS record by ID"""
    client = get_client()
    
    try:
        # Get record details first
        record = client.get(f'/domain/zone/{ZONE}/record/{record_id}')
        subdomain_display = record['subDomain'] if record['subDomain'] else '@'
        print(f"Deleting: {subdomain_display}.{ZONE} -> {record['target']}")
        
        client.delete(f'/domain/zone/{ZONE}/record/{record_id}')
        client.post(f'/domain/zone/{ZONE}/refresh')
        
        print(f"✅ Record {record_id} deleted successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting record: {e}")
        return False

def update_record(subdomain, new_ip, ttl=3600):
    """Update an existing record or create if doesn't exist"""
    client = get_client()
    
    # Find existing records
    records = client.get(f'/domain/zone/{ZONE}/record', fieldType='A', subDomain=subdomain)
    
    if records:
        # Delete old records
        for record_id in records:
            delete_record(record_id)
    
    # Add new record
    return add_record(subdomain, new_ip, ttl)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  List all A records:        python3 manage_dns.py list")
        print("  List specific subdomain:   python3 manage_dns.py list <subdomain>")
        print("  Add record:                python3 manage_dns.py add <subdomain> <ip>")
        print("  Update record:             python3 manage_dns.py update <subdomain> <ip>")
        print("  Delete record:             python3 manage_dns.py delete <record_id>")
        print("\nExamples:")
        print("  python3 manage_dns.py list")
        print("  python3 manage_dns.py add * 151.80.58.99")
        print("  python3 manage_dns.py update www 151.80.58.99")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        subdomain = sys.argv[2] if len(sys.argv) > 2 else None
        list_records(subdomain)
        
    elif command == "add":
        if len(sys.argv) < 4:
            print("Usage: manage_dns.py add <subdomain> <ip>")
            sys.exit(1)
        subdomain = sys.argv[2]
        ip = sys.argv[3]
        add_record(subdomain, ip)
        
    elif command == "update":
        if len(sys.argv) < 4:
            print("Usage: manage_dns.py update <subdomain> <ip>")
            sys.exit(1)
        subdomain = sys.argv[2]
        ip = sys.argv[3]
        update_record(subdomain, ip)
        
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: manage_dns.py delete <record_id>")
            sys.exit(1)
        record_id = int(sys.argv[2])
        delete_record(record_id)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
