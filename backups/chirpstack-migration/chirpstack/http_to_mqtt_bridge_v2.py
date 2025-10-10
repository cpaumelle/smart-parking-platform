#!/usr/bin/env python3
"""
ChirpStack HTTP to MQTT Bridge
Receives HTTP POST from ChirpStack HTTP integration and:
1. Publishes to local MQTT broker
2. Forwards to original ingest platform
"""
import json
import requests
from flask import Flask, request
import paho.mqtt.client as mqtt

app = Flask(__name__)

# MQTT Configuration  
MQTT_BROKER = "10.44.1.110"
MQTT_PORT = 1883

# Forward URL
FORWARD_URL = "https://ingest.sensemy.cloud/uplink?source=chirpstack"

# Initialize MQTT client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

@app.route("/uplink", methods=["POST"])
def uplink():
    try:
        data = request.get_json()
        
        # Extract fields from ChirpStack HTTP integration payload
        app_id = data.get("applicationID", "unknown")
        dev_eui = data.get("devEUI", "unknown") 
        event_type = "up"
        
        # Construct MQTT topic matching ChirpStack format
        topic = f"application/{app_id}/device/{dev_eui}/event/{event_type}"
        
        # Publish to MQTT
        mqtt_client.publish(topic, json.dumps(data), qos=0)
        print(f"Published to MQTT: {topic}")
        
        # Forward to original ingest platform
        try:
            resp = requests.post(FORWARD_URL, json=data, timeout=5)
            print(f"Forwarded to ingest platform: {resp.status_code}")
        except Exception as e:
            print(f"Warning: Failed to forward to ingest platform: {e}")
        
        return "OK", 200
        
    except Exception as e:
        print(f"Error: {e}")
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3002)
