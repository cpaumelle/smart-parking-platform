#!/usr/bin/env python3
"""
Test MQTT Uplink Integration
Sends a single test uplink to verify MQTT connectivity
"""

from chirpstack_mqtt_client import ChirpStackMQTTClient
import yaml
import time

print("=" * 80)
print("MQTT Uplink Test")
print("=" * 80)

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Update MQTT broker to localhost (since we're running outside Docker)
config['mqtt']['broker'] = 'localhost'

print("\n1. Connecting to MQTT broker...")
print(f"   Broker: {config['mqtt']['broker']}:{config['mqtt']['port']}")
print(f"   Application ID: {config['chirpstack']['application_id']}")

client = ChirpStackMQTTClient(config)

if not client.connect():
    print("\n❌ Failed to connect to MQTT broker")
    exit(1)

print("   ✓ Connected successfully")

# Wait a moment for subscription to complete
time.sleep(1)

print("\n2. Sending test uplink...")
test_dev_eui = "TEST0000SENSOR00"
test_fport = 2
test_payload = bytes.fromhex("010064")  # Simulated parking sensor payload

success = client.send_uplink(
    dev_eui=test_dev_eui,
    fport=test_fport,
    payload=test_payload,
    confirmed=False
)

if success:
    print("   ✓ Uplink sent successfully")
else:
    print("   ✗ Failed to send uplink")

print("\n3. Waiting for potential downlink response (5 seconds)...")
time.sleep(5)

# Get statistics
stats = client.get_statistics()
print("\n4. Statistics:")
print(f"   Uplinks sent: {stats['uplinks_sent']}")
print(f"   Downlinks received: {stats['downlinks_received']}")
print(f"   Errors: {stats['errors']}")
print(f"   Success rate: {stats['success_rate']:.1f}%")

# Disconnect
client.disconnect()

print("\n" + "=" * 80)
print("Test Complete!")
print("=" * 80)
print("\nNext steps:")
print("  1. Check your ingest service logs to see if uplink was received")
print("  2. Check ChirpStack UI for the device uplink")
print("  3. Run the simulator: python3 demo.py")
