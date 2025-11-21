import json
from paho.mqtt import client as mqtt
from client import get_message_bme

DATA_FILE = "data/data.json"
MAX_SAMPLES = 100

mqtt_server = "broker.hivemq.com"
mqtt_topic_bme = "esp32/sensor/BME280"

result = {}

# Pull BME data
payload = get_message_bme(mqtt_topic_bme, mqtt_server)

# Validate payload
if payload and isinstance(payload, list) and len(payload) == 4:
    temp, hum, pressure, timestamp = payload
    new_sample = {
        "temperature": temp,
        "humidity": hum,
        "pressure": pressure,
        "timestamp": timestamp
    }
    # Load existing data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    except FileNotFoundError:
        data = []

    # Append new sample
    data.append(new_sample)

    # Keep max MAX_SAMPLES
    if len(data) > MAX_SAMPLES:
        data = data[-MAX_SAMPLES:]  # saving MAX_SAMPLES only

    # Save back to JSON
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

else:
    print("No valid data received, skipping.")
