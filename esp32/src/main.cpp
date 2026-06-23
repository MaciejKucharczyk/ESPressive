#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"
#include <map>
#include <Adafruit_BME280.h>
#include <Wire.h>
#include <Preferences.h>

// Pod zapisywanie UUIDv4
Preferences preferences;

// ESP32 pin definitions
#define SDA 25
#define SCL 26 


Adafruit_BME280 bme;  // sensor object

WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

String deviceId;
String topic;

const char* ca_cert = R"EOF(
-----BEGIN CERTIFICATE-----
MIIDZTCCAk2gAwIBAgIUNbcfhy+HatJtmBZrsgCDiaPAH04wDQYJKoZIhvcNAQEL
BQAwQjELMAkGA1UEBhMCWFgxFTATBgNVBAcMDERlZmF1bHQgQ2l0eTEcMBoGA1UE
CgwTRGVmYXVsdCBDb21wYW55IEx0ZDAeFw0yNjA2MjMwMDIyMzhaFw0zNjA2MjAw
MDIyMzhaMEIxCzAJBgNVBAYTAlhYMRUwEwYDVQQHDAxEZWZhdWx0IENpdHkxHDAa
BgNVBAoME0RlZmF1bHQgQ29tcGFueSBMdGQwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQC8wBbhJBy9jYUg8MhiE/c2An4JwZvLdj5m84URrzHcbU9l4pUq
bm+YaNnLPhns2oPIsHCbAjfy6BldyxttsnsumD89r7yr9dmEdMk5YRKNfcx4rlFU
LTm2irrVHkNxbF8+BHevqbd11JP1D1WUF5/d3Q/mjV0T4yIm25rdAOpSI1dbqwLK
6CGPnFaNZchEjbMYJXv+Doqz1AG7I6WXrjfj1arxEOo/ziK1w2ux7nWuZBULBxE3
BvCiQzqJG9pUh5Ey49AqelUJPVdRleZLxvvTJ/56nBllFTI+EkIEMMMMdv9wXIm9
JJXR2JAWp1D+v6r75eJEfR/VHrBbX9GVhz1xAgMBAAGjUzBRMB0GA1UdDgQWBBTm
YiiLeCY4l6S2Bou/CjoeFN1UKTAfBgNVHSMEGDAWgBTmYiiLeCY4l6S2Bou/Cjoe
FN1UKTAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQANBwOp2sDj
VD5cKEIbPiQ/X0e4/tUkl2EIhXBlvFmSNM6OqpHa21N70AZv8GXnpUjc/n5/cP5c
R0XXVM2ejjSMAMHQUkkMCjt74ECjup1ULRGfPLnzaC6a1oSd4E9gXBwhmr0IlqVE
tLgeHiiQxt1kGJr7lszYfVIM/XvnbDJ1dJEoqM7y27qN4LgTWqK5ADnj5d7mn+Pp
xJXhN87guCH0ssEv95SZne+yAZaumlwaq79/hDNBfGinEVpJZScJ4xCpNpOXqXDV
wxbhnTdAIx1WmZ5+r/xQnp54UPowSG+gpAv9Zgp24OJN1h42W/ONyrm3q9gmVTdt
uHInHGRgO8Xc
-----END CERTIFICATE-----
  )EOF";

// zmienne komunikatow
int tempCounter = 0;
int humCounter = 0; 
int pressCounter = 0;

// Zmienne do kontroli czasu (nieblokujące millis)
unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;
unsigned long lastMeasurementMs = 0;

const unsigned long WIFI_RETRY_MS = 5000;
const unsigned long MQTT_RETRY_MS = 3000;
const unsigned long MEASUREMENT_PERIOD_MS = 5000; // Pomiary co 5 sekund

String generateUUIDv4() {
  uint8_t uuid[16];
  // Wypełnij bufor losowymi bajtami
  for (int i = 0; i < 16; i++) {
      uuid[i] = esp_random() & 0xFF;
  }

  // Ustaw wersję 4 (4-ty bajt -> 0x4x)
  uuid[6] = (uuid[6] & 0x0F) | 0x40;
  // Ustaw wariant (8-my bajt -> 10xxxxxx)
  uuid[8] = (uuid[8] & 0x3F) | 0x80;

  char buffer[37];
  snprintf(buffer, sizeof(buffer),
           "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           uuid[0], uuid[1], uuid[2], uuid[3],
           uuid[4], uuid[5],
           uuid[6], uuid[7],
           uuid[8], uuid[9],
           uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]);
  return String(buffer);
}

// Sprawdzamy, czy UUIDv4 juz istnieje
String getOrGenerateDeviceId() {
  preferences.begin("device-config", false); // otwórz przestrzeń "device-config"
  String id = preferences.getString("uuid", "");

  if (id == "") {
      // Jeśli ID jest puste, wygeneruj nowe
      id = generateUUIDv4(); 
      preferences.putString("uuid", id); // Zapisz na stałe w NVS
      Serial.println("Nowe UUID wygenerowane i zapisane: " + id);
  } else {
      Serial.println("Wczytano istniejące UUID: " + id);
  }
  preferences.end();
  return id;
}

// timestamp UNIX w milisekundach
long long getTimestampMs() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return ((long long)tv.tv_sec * 1000LL) + (tv.tv_usec / 1000);
}


String statusTopic() {
  return "lab/" + String(MQTT_GROUP) + "/" + deviceId + "/status";
}

// publikacja statusu online/offline
void publishOnlineStatus(const char* state) {
  if (!mqttClient.connected()) {
    return;
  }
  
  JsonDocument doc;
  doc["device_id"] = deviceId;
  doc["status"] = state;
  doc["ts_ms"] = getTimestampMs();
  
  char buffer[128];
  serializeJson(doc, buffer, sizeof(buffer));
  
  // Publikacja z flagą RETAINED = true
  mqttClient.publish(statusTopic().c_str(), buffer, true);
  Serial.print("[MQTT] Status urządzenia: ");
  Serial.println(buffer);
}

bool connectMqttIfNeeded()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    return false;
  }
  if (mqttClient.connected())
  {
    return true;
  }
  if (millis() - lastMqttAttemptMs < MQTT_RETRY_MS)
  {
    return false;
  }
  lastMqttAttemptMs = millis();
  String willPayload =
      "{\"device_id\":\"" + deviceId + "\",\"status\":\"offline\"}";
  bool ok = mqttClient.connect(
      deviceId.c_str(),
      MQTT_USER,             // Login
      MQTT_PASS,
      statusTopic().c_str(),
      0,
      true,
      willPayload.c_str());
  if (ok)
  {
    Serial.println("MQTT connected");
    publishOnlineStatus("online");
  }
  else
  {
    Serial.print("MQTT connect failed, rc=");
    Serial.println(mqttClient.state());
  }
  return ok;
}

String generateDeviceIdFromEfuse()
{
  uint64_t chipId = ESP.getEfuseMac();
  char id[32];
  snprintf(id, sizeof(id), "esp32-%04X%08X",
           (uint16_t)(chipId >> 32),
           (uint32_t)chipId);
  return String(id);
}

void get_bme_sensor_data()
{
  float temp = bme.readTemperature();
  float hum = bme.readHumidity();
  float pressure = bme.readPressure() / 100.0F; // hPa
}

// Polaczenie z WI-FI - nieblokujace
void connectWiFiIfNeeded() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  
  if (millis() - lastWifiAttemptMs < WIFI_RETRY_MS) {
    return;
  }
  
  lastWifiAttemptMs = millis();
  Serial.println("[WiFi] Rozlaczono. Proba ponownego laczenia...");
  
  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void connectMQTT()
{
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqttClient.connected())
  {
    Serial.print("Laczenie z MQTT...");
    if (mqttClient.connect(deviceId.c_str()))
    {
      Serial.println("OK");
    }
    else
    {
      Serial.print("blad, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" - ponowna proba za 2 s");
      delay(2000);
    }
  }
}

void publishMeasurement(String topic, String label, float value, int precision, String unit, int counter)
{
  JsonDocument doc;
  doc["schema_version"] = "1.0";
  doc["device_id"] = deviceId;
  doc["sensor_type"] = label;
  doc["value"] = value;
  doc["unit"] = unit;
  doc["timestamp"] = millis();
  doc["message_seq"] = counter;
  char payload[256];
  serializeJson(doc, payload);
  mqttClient.publish(topic.c_str(), payload);
  Serial.print("Publikacja na topic: ");
  Serial.println(topic.c_str());
  Serial.println(payload);
}

void publishStatus(String sensor_type, String status, String message)
{ 
  JsonDocument doc;
  doc["schema_version"] = "1.0";
  doc["device_id"] = deviceId;
  doc["sensor_type"] = sensor_type;
  doc["status"] = status;
  doc["message"] = message;
  doc["code"] = 123;
  doc["timestamp"] = millis();

  String newTopic = topic + "/status/" + sensor_type;
  char payload[256];
  serializeJson(doc, payload);
  mqttClient.publish(newTopic.c_str(), payload);
  Serial.print("Publikacja na topic [status]: ");
  Serial.println(newTopic);
  Serial.println(payload);
}

void processMeasurement(float temp, float hum, float pres)
{ 
  String errorType = "Nan value";
  // Walidacja
  if(!isnan(temp))
  {
    tempCounter+=1;
    publishMeasurement(topic + "/temperature", "temperature", temp, 2, " C", tempCounter);
    publishStatus("temperature", "SUCCESS", "");
  }
  else 
  {
    publishStatus("temperature", "error", "[ERROR] Blad odczytu danych z czujnika");
  }

  if(!isnan(hum))
  {
    humCounter+=1;
    publishMeasurement(topic + "/humidity", "humidity", hum, 1, " %", humCounter);
    publishStatus("humidity", "SUCCESS", "");
  }
  else
  {
    publishStatus("humidity", "ERROR: " + errorType, "[ERROR] Blad odczytu danych z czujnika");
  }

  if(!isnan(pres))
  {
    pressCounter+=1;
    publishMeasurement(topic + "/pressure", "pressure",    pres, 0, " hPa", pressCounter);
    publishStatus("pressure", "SUCCESS", "");
  }
  else
  {
    publishStatus("pressure", "ERROR: " + errorType, "[ERROR] Blad odczytu danych z czujnika");
  }
  
}

void setup()
{
  Serial.begin(115200);
  delay(1000);
  // deviceId = generateDeviceIdFromEfuse(); -- bez UUID
  deviceId = getOrGenerateDeviceId();
  topic = "lab/" + String(MQTT_GROUP) + "/" + deviceId;
  Serial.print("Device ID: ");
  Serial.println(deviceId);

   // I2C config 
  Wire.begin(SDA, SCL);
  Wire.setClock(400000); // 400kHz I2C

  bool ok = bme.begin(0x76, &Wire);
  
  espClient.setInsecure();
  mqttClient.setServer(MQTT_HOST, 8883);
  //espClient.setCACert(ca_cert);
  

  if (!ok) {
    Serial.println("Could not find a valid BME280 sensor, check wiring!");
    while (1);
  }
  //connectWiFiIfNeeded();
  // connectMQTT();
}

void loop()
{
  // 1. Dba o WiFi (samo sprawdza, czy trzeba się łączyć)
  connectWiFiIfNeeded();

  // 2. Dba o MQTT. Zwróci true tylko, jeśli mamy WiFi i aktywne połączenie z brokerem
  if (connectMqttIfNeeded()) {
    mqttClient.loop(); // Utrzymujemy sesję tylko, gdy połączono
  }

  // 3. Pomiary co 5 sekund
  if (millis() - lastMeasurementMs >= MEASUREMENT_PERIOD_MS) {
    lastMeasurementMs = millis();
    
    float temp = bme.readTemperature();
    float hum = bme.readHumidity();
    float pressure = bme.readPressure() / 100.0F; // hPa
    
    Serial.println("Odczytane wartosci: ");
    Serial.print("Temperatura: ");
    Serial.print(temp);
    Serial.print(" Wilgotnosc: ");
    Serial.print(hum);
    Serial.print(" Cisnienie: ");
    Serial.println(pressure);

    // Wysyłamy dane (mqttClient.connected() wykonujemy tu raz, tuż przed wysyłką, dla pewności)
    if (mqttClient.connected()) {
      processMeasurement(temp, hum, pressure);
    }
  }
}