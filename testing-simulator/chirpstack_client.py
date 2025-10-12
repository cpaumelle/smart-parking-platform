"""
ChirpStack API Client
Handles communication with ChirpStack server for uplinks and downlinks
"""

import requests
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional
import time


class ChirpStackClient:
    """
    Client for interacting with ChirpStack gRPC-gateway REST API
    """
    
    def __init__(self, config: dict):
        self.api_url = config['chirpstack']['api_url']
        self.api_token = config['chirpstack']['api_token']
        self.tenant_id = config['chirpstack']['tenant_id']
        self.application_id = config['chirpstack']['application_id']
        
        self.headers = {
            'Content-Type': 'application/json',
            'Grpc-Metadata-Authorization': f'Bearer {self.api_token}'
        }
        
        # Statistics
        self.uplinks_sent = 0
        self.downlinks_sent = 0
        self.errors = 0
        
    def send_uplink(self, dev_eui: str, fport: int, payload: bytes, 
                    confirmed: bool = False) -> bool:
        """
        Simulate an uplink from a device to ChirpStack
        
        Args:
            dev_eui: Device EUI
            fport: LoRaWAN FPort
            payload: Binary payload
            confirmed: Whether uplink requires confirmation
            
        Returns:
            True if successful
        """
        try:
            # Encode payload to base64
            payload_b64 = base64.b64encode(payload).decode('ascii')
            
            # Construct uplink message
            uplink_data = {
                "deviceInfo": {
                    "tenantId": self.tenant_id,
                    "applicationId": self.application_id,
                    "devEui": dev_eui,
                    "deviceName": f"sensor-{dev_eui}"
                },
                "devAddr": self._generate_dev_addr(dev_eui),
                "fPort": fport,
                "data": payload_b64,
                "confirmed": confirmed,
                "fCnt": self.uplinks_sent,
                "rxInfo": [{
                    "gatewayId": "0000000000000001",
                    "rssi": -60,
                    "snr": 8.5,
                    "context": base64.b64encode(b"simulated").decode('ascii')
                }],
                "txInfo": {
                    "frequency": 868100000,
                    "modulation": {
                        "lora": {
                            "bandwidth": 125000,
                            "spreadingFactor": 7,
                            "codeRate": "CR_4_5"
                        }
                    }
                }
            }
            
            # Send to ChirpStack integration endpoint
            # Note: In real implementation, this would go through the integration
            # For simulation, we'll use the device queue endpoint or integration webhook
            
            endpoint = f"{self.api_url}/devices/{dev_eui}/queue"
            
            # For simulation purposes, we're actually just logging this
            # In production, your integration would handle the uplink
            self.uplinks_sent += 1
            
            # Log the uplink (in real system, this goes through LoRaWAN network)
            print(f"[Uplink] DEV_EUI: {dev_eui}, FPort: {fport}, "
                  f"Payload: {payload.hex()}, Count: {self.uplinks_sent}")
            
            return True
            
        except Exception as e:
            print(f"[ChirpStack] Error sending uplink: {e}")
            self.errors += 1
            return False
    
    def enqueue_downlink(self, dev_eui: str, fport: int, payload: bytes, 
                         confirmed: bool = False) -> bool:
        """
        Enqueue a downlink message to a device
        
        Args:
            dev_eui: Device EUI
            fport: LoRaWAN FPort
            payload: Binary payload
            confirmed: Whether downlink requires confirmation
            
        Returns:
            True if successfully queued
        """
        try:
            # Encode payload to base64
            payload_b64 = base64.b64encode(payload).decode('ascii')
            
            # Construct downlink queue item
            queue_item = {
                "queueItem": {
                    "confirmed": confirmed,
                    "fPort": fport,
                    "data": payload_b64
                }
            }
            
            endpoint = f"{self.api_url}/devices/{dev_eui}/queue"
            
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=queue_item,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.downlinks_sent += 1
                print(f"[Downlink] DEV_EUI: {dev_eui}, FPort: {fport}, "
                      f"Payload: {payload.hex()}")
                return True
            else:
                print(f"[ChirpStack] Downlink failed: {response.status_code} - {response.text}")
                self.errors += 1
                return False
                
        except Exception as e:
            print(f"[ChirpStack] Error enqueuing downlink: {e}")
            self.errors += 1
            return False
    
    def get_device_queue(self, dev_eui: str) -> List[Dict]:
        """Get current downlink queue for a device"""
        try:
            endpoint = f"{self.api_url}/devices/{dev_eui}/queue"
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
            else:
                return []
                
        except Exception as e:
            print(f"[ChirpStack] Error getting device queue: {e}")
            return []
    
    def flush_device_queue(self, dev_eui: str) -> bool:
        """Clear all downlinks from device queue"""
        try:
            endpoint = f"{self.api_url}/devices/{dev_eui}/queue"
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"[ChirpStack] Error flushing queue: {e}")
            return False
    
    def get_device_info(self, dev_eui: str) -> Optional[Dict]:
        """Get device information from ChirpStack"""
        try:
            endpoint = f"{self.api_url}/devices/{dev_eui}"
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            print(f"[ChirpStack] Error getting device info: {e}")
            return None
    
    def list_devices(self) -> List[Dict]:
        """List all devices in the application"""
        try:
            endpoint = f"{self.api_url}/applications/{self.application_id}/devices"
            response = requests.get(
                endpoint, 
                headers=self.headers,
                params={'limit': 1000},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', [])
            else:
                return []
                
        except Exception as e:
            print(f"[ChirpStack] Error listing devices: {e}")
            return []
    
    def create_device(self, dev_eui: str, name: str, device_profile_id: str) -> bool:
        """Create a new device in ChirpStack (for setup)"""
        try:
            device_data = {
                "device": {
                    "devEui": dev_eui,
                    "name": name,
                    "applicationId": self.application_id,
                    "deviceProfileId": device_profile_id,
                    "description": f"Simulated device: {name}"
                }
            }
            
            endpoint = f"{self.api_url}/devices"
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=device_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"[ChirpStack] Device created: {dev_eui}")
                return True
            else:
                print(f"[ChirpStack] Failed to create device: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[ChirpStack] Error creating device: {e}")
            return False
    
    def delete_device(self, dev_eui: str) -> bool:
        """Delete a device from ChirpStack"""
        try:
            endpoint = f"{self.api_url}/devices/{dev_eui}"
            response = requests.delete(endpoint, headers=self.headers, timeout=10)
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"[ChirpStack] Error deleting device: {e}")
            return False
    
    def _generate_dev_addr(self, dev_eui: str) -> str:
        """Generate a device address from DEV_EUI for simulation"""
        # Simple hash-based generation
        hash_val = hash(dev_eui) & 0xFFFFFFFF
        return f"{hash_val:08x}"
    
    def get_statistics(self) -> Dict:
        """Get client statistics"""
        return {
            'uplinks_sent': self.uplinks_sent,
            'downlinks_sent': self.downlinks_sent,
            'errors': self.errors,
            'success_rate': (
                (self.uplinks_sent + self.downlinks_sent) / 
                max(1, self.uplinks_sent + self.downlinks_sent + self.errors)
            ) * 100
        }
    
    def test_connection(self) -> bool:
        """Test connection to ChirpStack API"""
        try:
            # Try to list applications (simple API test)
            endpoint = f"{self.api_url}/applications/{self.application_id}"
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                print("[ChirpStack] Connection successful!")
                return True
            else:
                print(f"[ChirpStack] Connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[ChirpStack] Connection error: {e}")
            return False


class MockChirpStackClient(ChirpStackClient):
    """
    Mock ChirpStack client for testing without actual ChirpStack server
    """
    
    def __init__(self, config: dict):
        # Don't call super().__init__ to avoid connection setup
        self.api_url = "mock://chirpstack"
        self.api_token = "mock_token"
        self.tenant_id = "mock_tenant"
        self.application_id = "mock_app"
        
        self.uplinks_sent = 0
        self.downlinks_sent = 0
        self.errors = 0
        
        # Store messages for inspection
        self.uplink_log = []
        self.downlink_log = []
    
    def send_uplink(self, dev_eui: str, fport: int, payload: bytes, 
                    confirmed: bool = False) -> bool:
        """Mock uplink - just log it"""
        self.uplinks_sent += 1
        self.uplink_log.append({
            'timestamp': datetime.now(),
            'dev_eui': dev_eui,
            'fport': fport,
            'payload': payload.hex(),
            'confirmed': confirmed
        })
        return True
    
    def enqueue_downlink(self, dev_eui: str, fport: int, payload: bytes, 
                         confirmed: bool = False) -> bool:
        """Mock downlink - just log it"""
        self.downlinks_sent += 1
        self.downlink_log.append({
            'timestamp': datetime.now(),
            'dev_eui': dev_eui,
            'fport': fport,
            'payload': payload.hex(),
            'confirmed': confirmed
        })
        print(f"[Mock Downlink] DEV_EUI: {dev_eui}, FPort: {fport}, Payload: {payload.hex()}")
        return True
    
    def test_connection(self) -> bool:
        """Mock always succeeds"""
        print("[Mock ChirpStack] Connection successful (mock mode)")
        return True
