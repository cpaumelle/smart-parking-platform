"""
ChirpStack MQTT Client for Simulator
Publishes uplink messages via MQTT to ChirpStack integration
Subscribes to downlink commands
"""

import json
import base64
import time
from datetime import datetime
from typing import Optional, Dict, List
import paho.mqtt.client as mqtt
import threading


class ChirpStackMQTTClient:
    """
    ChirpStack client that uses MQTT integration for uplinks/downlinks
    This simulates devices sending real uplinks through ChirpStack
    """
    
    def __init__(self, config: dict):
        # Extract configuration
        self.tenant_id = config['chirpstack']['tenant_id']
        self.application_id = config['chirpstack']['application_id']
        
        # MQTT configuration
        mqtt_config = config.get('mqtt', {})
        self.mqtt_broker = mqtt_config.get('broker', 'localhost')
        self.mqtt_port = mqtt_config.get('port', 1883)
        self.mqtt_username = mqtt_config.get('username', None)
        self.mqtt_password = mqtt_config.get('password', None)
        
        # Statistics
        self.uplinks_sent = 0
        self.downlinks_received = 0
        self.errors = 0
        
        # MQTT client
        self.client = mqtt.Client(client_id=f"parking-simulator-{int(time.time())}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Authentication if provided
        if self.mqtt_username and self.mqtt_password:
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        # Connection state
        self.connected = False
        self.connect_lock = threading.Lock()
        
        # Downlink callback
        self.downlink_callback = None
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            print(f"[MQTT] Connecting to {self.mqtt_broker}:{self.mqtt_port}...")
            self.client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection (with timeout)
            timeout = 5
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                print("[MQTT] ✓ Connected successfully")
                return True
            else:
                print("[MQTT] ✗ Connection timeout")
                return False
                
        except Exception as e:
            print(f"[MQTT] ✗ Connection error: {e}")
            self.errors += 1
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        print("[MQTT] Disconnected")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            with self.connect_lock:
                self.connected = True
            
            # Subscribe to all downlink topics for this application
            topic = f"application/{self.application_id}/device/+/command/down"
            client.subscribe(topic)
            print(f"[MQTT] Subscribed to downlinks: {topic}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")
            self.errors += 1
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        with self.connect_lock:
            self.connected = False
        
        if rc != 0:
            print(f"[MQTT] Unexpected disconnect (code {rc})")
            self.errors += 1
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received from MQTT broker"""
        try:
            # Parse downlink message
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # Extract device info
            topic_parts = msg.topic.split('/')
            dev_eui = topic_parts[3]  # application/{app}/device/{deveui}/command/down
            
            # Extract downlink data
            fport = payload.get('fPort', 0)
            data_b64 = payload.get('data', '')
            data = base64.b64decode(data_b64) if data_b64 else b''
            
            self.downlinks_received += 1
            
            print(f"[MQTT ↓ Downlink] DEV_EUI: {dev_eui}, FPort: {fport}, Payload: {data.hex()}")
            
            # Call downlink callback if registered
            if self.downlink_callback:
                self.downlink_callback(dev_eui, fport, data)
                
        except Exception as e:
            print(f"[MQTT] Error processing downlink: {e}")
            self.errors += 1
    
    def send_uplink(self, dev_eui: str, fport: int, payload: bytes, 
                    confirmed: bool = False, fcnt: Optional[int] = None) -> bool:
        """
        Send an uplink message via MQTT
        
        Args:
            dev_eui: Device EUI
            fport: LoRaWAN FPort
            payload: Binary payload
            confirmed: Whether uplink requires confirmation
            fcnt: Frame counter (auto-increment if None)
            
        Returns:
            True if published successfully
        """
        if not self.connected:
            print("[MQTT] Not connected - attempting to reconnect...")
            if not self.connect():
                return False
        
        try:
            # Encode payload to base64
            payload_b64 = base64.b64encode(payload).decode('ascii')
            
            # Use frame counter or auto-increment
            if fcnt is None:
                fcnt = self.uplinks_sent
            
            # Construct uplink message (ChirpStack integration format)
            uplink_message = {
                "deduplicationId": f"sim-{dev_eui}-{int(time.time()*1000)}",
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "deviceInfo": {
                    "tenantId": self.tenant_id,
                    "tenantName": "SenseMy",
                    "applicationId": self.application_id,
                    "applicationName": "Parking Simulator",
                    "deviceProfileId": "simulated-profile",
                    "deviceProfileName": "Simulated Device",
                    "deviceName": f"Simulator-{dev_eui}",
                    "devEui": dev_eui,
                    "deviceClassEnabled": "CLASS_A",
                    "tags": {
                        "simulator": "true",
                        "testing": "true"
                    }
                },
                "devAddr": self._generate_dev_addr(dev_eui),
                "adr": True,
                "dr": 5,
                "fCnt": fcnt,
                "fPort": fport,
                "confirmed": confirmed,
                "data": payload_b64,
                "object": {},  # Decoded object (will be decoded by transform service)
                "rxInfo": [
                    {
                        "gatewayId": "simulated-gateway-001",
                        "uplinkId": int(time.time() * 1000000),
                        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "rssi": -60,
                        "snr": 8.5,
                        "channel": 0,
                        "rfChain": 0,
                        "location": {},
                        "context": base64.b64encode(b"simulated").decode('ascii'),
                        "metadata": {},
                        "crcStatus": "CRC_OK"
                    }
                ],
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
            
            # Publish to ChirpStack MQTT topic
            topic = f"application/{self.application_id}/device/{dev_eui}/event/up"
            message_json = json.dumps(uplink_message)
            
            result = self.client.publish(topic, message_json, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.uplinks_sent += 1
                print(f"[MQTT ↑ Uplink] DEV_EUI: {dev_eui}, FPort: {fport}, "
                      f"Payload: {payload.hex()}, Count: {fcnt}")
                return True
            else:
                print(f"[MQTT] Publish failed with code {result.rc}")
                self.errors += 1
                return False
                
        except Exception as e:
            print(f"[MQTT] Error sending uplink: {e}")
            import traceback
            traceback.print_exc()
            self.errors += 1
            return False
    
    def register_downlink_callback(self, callback):
        """Register a callback function for downlinks"""
        self.downlink_callback = callback
    
    def _generate_dev_addr(self, dev_eui: str) -> str:
        """Generate a device address from DEV_EUI for simulation"""
        hash_val = hash(dev_eui) & 0xFFFFFFFF
        return f"{hash_val:08x}"
    
    def get_statistics(self) -> Dict:
        """Get client statistics"""
        return {
            'uplinks_sent': self.uplinks_sent,
            'downlinks_received': self.downlinks_received,
            'errors': self.errors,
            'connected': self.connected,
            'success_rate': (
                (self.uplinks_sent + self.downlinks_received) / 
                max(1, self.uplinks_sent + self.downlinks_received + self.errors)
            ) * 100
        }
    
    def test_connection(self) -> bool:
        """Test connection to MQTT broker"""
        return self.connect()


class MockChirpStackClient:
    """
    Mock ChirpStack client for testing without MQTT
    Just logs uplinks/downlinks locally
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.uplinks_sent = 0
        self.downlinks_received = 0
        self.errors = 0
        self.connected = True
        
        self.uplink_log = []
        self.downlink_log = []
        self.downlink_callback = None
        
        print("[Mock MQTT] Running in MOCK mode (no real MQTT connection)")
    
    def connect(self) -> bool:
        """Mock connect always succeeds"""
        self.connected = True
        return True
    
    def disconnect(self):
        """Mock disconnect"""
        self.connected = False
    
    def send_uplink(self, dev_eui: str, fport: int, payload: bytes, 
                    confirmed: bool = False, fcnt: Optional[int] = None) -> bool:
        """Mock uplink - just log it"""
        if fcnt is None:
            fcnt = self.uplinks_sent
        
        self.uplinks_sent += 1
        self.uplink_log.append({
            'timestamp': datetime.now(),
            'dev_eui': dev_eui,
            'fport': fport,
            'payload': payload.hex(),
            'confirmed': confirmed,
            'fcnt': fcnt
        })
        
        print(f"[Mock ↑ Uplink] DEV_EUI: {dev_eui}, FPort: {fport}, "
              f"Payload: {payload.hex()}, Count: {fcnt}")
        return True
    
    def register_downlink_callback(self, callback):
        """Register a callback function for downlinks"""
        self.downlink_callback = callback
    
    def simulate_downlink(self, dev_eui: str, fport: int, payload: bytes):
        """Simulate receiving a downlink (for testing)"""
        self.downlinks_received += 1
        self.downlink_log.append({
            'timestamp': datetime.now(),
            'dev_eui': dev_eui,
            'fport': fport,
            'payload': payload.hex()
        })
        
        print(f"[Mock ↓ Downlink] DEV_EUI: {dev_eui}, FPort: {fport}, Payload: {payload.hex()}")
        
        if self.downlink_callback:
            self.downlink_callback(dev_eui, fport, payload)
    
    def get_statistics(self) -> Dict:
        """Get mock statistics"""
        return {
            'uplinks_sent': self.uplinks_sent,
            'downlinks_received': self.downlinks_received,
            'errors': self.errors,
            'connected': self.connected,
            'success_rate': 100.0  # Mock always succeeds
        }
    
    def test_connection(self) -> bool:
        """Mock always succeeds"""
        print("[Mock MQTT] Connection successful (mock mode)")
        return True
