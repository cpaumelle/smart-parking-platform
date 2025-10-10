"""mqtt_publisher.py - Publish uplinks to MQTT broker"""
import json
import logging
import paho.mqtt.client as mqtt
import os

logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.44.1.110")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Global MQTT client
mqtt_client = None

def init_mqtt():
    """Initialize MQTT client connection"""
    global mqtt_client
    logger.info(f"🔄 Attempting MQTT connection to {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        logger.info(f"✅ MQTT client connected to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to MQTT broker: {e}", exc_info=True)
        mqtt_client = None

def publish_to_mqtt(app_id: str, dev_eui: str, event_type: str, payload: dict):
    """Publish message to MQTT topic matching ChirpStack format"""
    global mqtt_client

    if not mqtt_client:
        logger.warning("⚠️ MQTT client not initialized, skipping publish")
        return

    try:
        topic = f"application/{app_id}/device/{dev_eui}/event/{event_type}"
        message = json.dumps(payload)

        mqtt_client.publish(topic, message, qos=0)
        logger.info(f"📡 Published to MQTT: {topic}")

    except Exception as e:
        logger.error(f"❌ MQTT publish failed: {e}")
