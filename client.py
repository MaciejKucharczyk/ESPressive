from datetime import datetime
import re
import paho.mqtt.subscribe as subscribe

def get_message_distance(topic, hostname) -> list:
    msg = subscribe.simple(topic, hostname=hostname)
    msg_str = msg.payload.decode('utf-8')
    match = re.search(r'\d+(?:\.\d+)?', msg_str)
    if match:
        distance = float(match.group(0))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] Distance: {distance} cm")
        return [distance, timestamp]
    
def get_message_bme(topic, hostname) -> list:
    msg = subscribe.simple(topic, hostname=hostname)
    msg_str = msg.payload.decode('utf-8')
    pattern = r"Temperature: ([0-9\.]+) C, Humidity: ([0-9\.]+) %, Pressure: ([0-9\.]+) hPa"

    match = re.match(pattern, msg_str)
    if match:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temp = float(match.group(1))
        hum = float(match.group(2))
        pressure = float(match.group(3))

        print("Temp =", temp)
        print("Hum  =", hum)
        print("Pressure =", pressure)
        return [temp, hum, pressure, timestamp]
    else:
        print("Failed to parse BME message")