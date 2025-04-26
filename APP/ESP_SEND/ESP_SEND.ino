// ESP_SEND.ino - Hlavný Arduino skript pre ESP8266/ESP32
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFiUdp.h>

// ---------- KONFIGURÁCIA ----------
const char* ssid = "YOUR_WIFI_SSID";      // Zadajte názov vašej WiFi siete
const char* password = "YOUR_WIFI_PASSWORD"; // Zadajte heslo k vašej WiFi sieti
const char* deviceId = "esp_sensor_1";     // Identifikátor zariadenia
const char* deviceRoom = "Obývačka";       // Miestnosť umiestnenia

// Nastavenie pinov pre senzory - upravte podľa vašej dosky
const int MOTION_PIN = 5;  // D1 na NodeMCU

// MQTT konfigurácia - predvolené hodnoty, budú aktualizované automaticky
const char* default_mqtt_server = "192.168.1.100";  // Predvolená IP adresa MQTT brokera
const int default_mqtt_port = 1883;                // Predvolený port MQTT brokera
const char* mqtt_username = "";                     // MQTT používateľské meno (prázdne ak nie je potrebné)
const char* mqtt_password = "";                     // MQTT heslo (prázdne ak nie je potrebné)

// Premenné pre aktuálne hodnoty MQTT brokera (môžu byť upravené pri autodiscovery)
char mqtt_server[40] = "";
int mqtt_port = 1883;
bool broker_discovered = false;

// Konfigurácia MQTT Discovery
const int discovery_port = 12345;
const unsigned long discovery_timeout = 60000; // 60 sekúnd
unsigned long last_discovery_attempt = 0;

// MQTT témy
const char* mqtt_topic_base = "home/security";
const char* mqtt_sensor_topic = "home/security/sensors";
const char* mqtt_status_topic = "home/security/status";
const char* mqtt_control_topic = "home/security/control";

// Časovač pre pravidelné odosielanie dát
unsigned long lastSensorUpdate = 0;
const unsigned long sensorUpdateInterval = 5000;  // 5 sekúnd
unsigned long lastStatusUpdate = 0;
const unsigned long statusUpdateInterval = 60000; // 1 minúta

// Premenné pre stav senzorov
bool motionDetected = false;
unsigned long lastMotionTime = 0;
const unsigned long motionResetDelay = 10000;  // 10 sekúnd bez pohybu = reset

// Inicializácia klientov
WiFiClient espClient;
PubSubClient mqttClient(espClient);
WiFiUDP udp;

// Premenná pre sledovanie stavu
bool previouslyConnected = false;

void setup() {
  // Inicializácia sériovej komunikácie
  Serial.begin(115200);
  Serial.println("Spúšťam ESP senzorový modul...");
  
  // Inicializácia pinov
  pinMode(MOTION_PIN, INPUT);
  
  // Pripojenie na WiFi
  setupWifi();
  
  // Inicializácia UDP pre discovery
  udp.begin(discovery_port);
  
  // Nastavíme počiatočné hodnoty pre MQTT server
  strncpy(mqtt_server, default_mqtt_server, sizeof(mqtt_server));
  mqtt_port = default_mqtt_port;
  
  // Pokúsime sa o automatickú detekciu MQTT brokera
  discoverMQTTBroker();
  
  // Nastavenie MQTT servera
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(mqttCallback);
}

void loop() {
  // Kontrola pripojenia k WiFi a MQTT
  if (!mqttClient.connected()) {
    // Ak nie sme pripojení, skúsime znova objaviť broker iba ak:
    // 1. Ešte sme neobjavili broker, ALEBO
    // 2. Už uplynul čas od posledného pokusu
    if (!broker_discovered || (millis() - last_discovery_attempt > discovery_timeout)) {
      discoverMQTTBroker();
      mqttClient.setServer(mqtt_server, mqtt_port);
    }
    reconnectMQTT();
  }
  
  // Spracovanie MQTT správ
  mqttClient.loop();
  
  // Čítanie senzorov a odosielanie dát
  readSensors();
  
  // Pravidelné odosielanie stavu zariadenia
  sendDeviceStatus();
  
  // Pravidelná kontrola UDP paketov pre discovery
  checkDiscoveryPackets();
}

void setupWifi() {
  delay(10);
  Serial.println();
  Serial.print("Pripájam sa k WiFi sieti: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("WiFi pripojené");
  Serial.print("IP adresa: ");
  Serial.println(WiFi.localIP());
}

// Funkcia pre automatické zistenie MQTT brokera v sieti
bool discoverMQTTBroker() {
  Serial.println("Hľadám MQTT broker na sieti...");
  last_discovery_attempt = millis();
  
  // Príprava správy pre broadcast discovery požiadavku
  StaticJsonDocument<256> doc;
  doc["type"] = "mqtt_discovery_request";
  doc["device_id"] = deviceId;
  doc["device_name"] = deviceRoom;
  
  char jsonBuffer[256];
  size_t n = serializeJson(doc, jsonBuffer);
  
  // Odoslanie broadcast paketu
  IPAddress broadcastIP(255, 255, 255, 255);
  udp.beginPacket(broadcastIP, discovery_port);
  udp.write((uint8_t*)jsonBuffer, n);
  udp.endPacket();
  
  Serial.print("Odoslaná broadcast požiadavka na port ");
  Serial.println(discovery_port);
  
  // Počúvame na UDP porte pre discovery odpoveď
  unsigned long start_time = millis();
  
  // Nastavenie timeoutu pre čakanie na odpoveď
  while (millis() - start_time < 10000) {  // 10 sekúnd timeout
    int packetSize = udp.parsePacket();
    if (packetSize) {
      Serial.print("Prijatý UDP paket, veľkosť: ");
      Serial.println(packetSize);

      // Načítanie paketu
      char packetBuffer[255];
      int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
      packetBuffer[len] = '\0';
      
      // Parsovanie JSON správy
      StaticJsonDocument<512> responseDoc;
      DeserializationError error = deserializeJson(responseDoc, packetBuffer);
      
      if (error) {
        Serial.print("deserializeJson() zlyhalo: ");
        Serial.println(error.c_str());
        continue; // Skúsime ďalší paket
      }
      
      // Kontrola, či ide o MQTT discovery správu alebo odpoveď
      if (responseDoc.containsKey("type") && 
          (strcmp(responseDoc["type"], "mqtt_discovery") == 0 || 
           strcmp(responseDoc["type"], "mqtt_discovery_response") == 0)) {
        // Získanie IP adresy a portu brokera
        const char* discovered_broker = responseDoc["broker_ip"];
        int discovered_port = responseDoc["broker_port"];
        
        Serial.print("Nájdený MQTT broker na IP: ");
        Serial.print(discovered_broker);
        Serial.print(" port: ");
        Serial.println(discovered_port);
        
        // Aktualizácia konfigurácie
        strncpy(mqtt_server, discovered_broker, sizeof(mqtt_server));
        mqtt_port = discovered_port;
        broker_discovered = true;
        
        return true;
      }
    }
    
    delay(100); // Krátka pauza pre zníženie zaťaženia CPU
  }
  
  Serial.println("MQTT broker nebol nájdený v časovom limite. Použijem predvolenú konfiguráciu.");
  return false;
}

// Funkcia pre kontrolu UDP paketov počas behu
void checkDiscoveryPackets() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    // Načítanie paketu
    char packetBuffer[255];
    int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    packetBuffer[len] = '\0';
    
    // Parsovanie JSON správy
    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, packetBuffer);
    
    if (!error && doc.containsKey("type") && strcmp(doc["type"], "mqtt_discovery") == 0) {
      const char* discovered_broker = doc["broker_ip"];
      int discovered_port = doc["broker_port"];
      
      // Ak sa IP alebo port zmenili
      if (strcmp(discovered_broker, mqtt_server) != 0 || discovered_port != mqtt_port) {
        Serial.print("Aktualizácia MQTT brokera na IP: ");
        Serial.print(discovered_broker);
        Serial.print(" port: ");
        Serial.println(discovered_port);
        
        // Aktualizácia konfigurácie
        strncpy(mqtt_server, discovered_broker, sizeof(mqtt_server));
        mqtt_port = discovered_port;
        broker_discovered = true;
        
        // Odpojenie od aktuálneho brokera
        if (mqttClient.connected()) {
          mqttClient.disconnect();
        }
        
        // Nastavenie nového servera
        mqttClient.setServer(mqtt_server, mqtt_port);
      }
    }
  }
}

void reconnectMQTT() {
  // Pokúšať sa o pripojenie, ale s limitovaným počtom pokusov
  int maxRetries = 5;
  int retry = 0;
  
  while (!mqttClient.connected() && retry < maxRetries) {
    Serial.print("Pokus o MQTT pripojenie (");
    Serial.print(retry + 1);
    Serial.print("/");
    Serial.print(maxRetries);
    Serial.print(") k ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.print(mqtt_port);
    Serial.println("...");
    
    // Vytvorenie klientského ID
    String clientId = "ESP-";
    clientId += String(random(0xffff), HEX);
    
    // Pokus o pripojenie
    bool connected = false;
    if (mqtt_username[0] != '\0') {
      connected = mqttClient.connect(clientId.c_str(), mqtt_username, mqtt_password);
    } else {
      connected = mqttClient.connect(clientId.c_str());
    }
    
    if (connected) {
      Serial.println("pripojené");
      
      // Prihlásenie sa na tému pre príkazy
      String controlTopic = String(mqtt_control_topic) + "/" + deviceId;
      mqttClient.subscribe(controlTopic.c_str());
      Serial.print("Prihlásený na kontrolnej téme: ");
      Serial.println(controlTopic);
      
      // Odoslanie informácie o pripojení
      sendConnectMessage();
      
      // Aktualizácia príznaku pripojenia
      previouslyConnected = true;
    } else {
      Serial.print("zlyhalo, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" skúsim znova o 5 sekúnd");
      
      retry++;
      delay(5000);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Prijatá správa na téme: ");
  Serial.print(topic);
  Serial.print(", dĺžka: ");
  Serial.println(length);
  
  // Vytvorenie bufferu pre správu
  char message[length + 1];
  for (unsigned int i = 0; i < length; i++) {
    message[i] = (char)payload[i];
  }
  message[length] = '\0';
  
  Serial.print("Správa: ");
  Serial.println(message);
  
  // Parsovanie JSON správy
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.print("deserializeJson() zlyhalo: ");
    Serial.println(error.c_str());
    return;
  }
  
  // Spracovanie príkazu
  const char* command = doc["command"];
  
  if (strcmp(command, "RESET") == 0) {
    Serial.println("Príkaz na resetovanie zariadenia");
    ESP.restart();
  }
  else if (strcmp(command, "STATUS") == 0) {
    Serial.println("Príkaz na odoslanie aktuálneho stavu");
    sendSensorData(true);
    sendDeviceStatus();
  }
  else if (strcmp(command, "DISCOVER") == 0) {
    Serial.println("Príkaz na vyhľadanie MQTT brokera");
    discoverMQTTBroker();
    // Ak sa broker zmenil, odpojíme sa a znova pripojíme
    if (broker_discovered) {
      mqttClient.disconnect();
      mqttClient.setServer(mqtt_server, mqtt_port);
      reconnectMQTT();
    }
  }
}

void readSensors() {
  // Čítanie pohybového senzora
  int motionValue = digitalRead(MOTION_PIN);
  
  // Ak je detekovaný pohyb
  if (motionValue == HIGH) {
    if (!motionDetected) {
      motionDetected = true;
      sendSensorData(true);  // Okamžite odošleme informáciu o zmene
    }
    lastMotionTime = millis();
  }
  
  // Kontrola, či nevypršal časovač pohybu
  if (motionDetected && (millis() - lastMotionTime > motionResetDelay)) {
    motionDetected = false;
    sendSensorData(true);  // Okamžite odošleme informáciu o zmene
  }
  
  // Pravidelné odosielanie údajov zo senzorov
  if (millis() - lastSensorUpdate > sensorUpdateInterval) {
    sendSensorData(false);
    lastSensorUpdate = millis();
  }
}

void sendSensorData(bool forced) {
  // Kontrola pripojenia
  if (!mqttClient.connected()) {
    return;
  }
  
  // Vytvorenie JSON dokumentu
  StaticJsonDocument<256> doc;
  
  // Pridanie údajov o zariadení
  doc["device_id"] = deviceId;
  doc["room"] = deviceRoom;
  doc["timestamp"] = millis();
  
  // Pridanie údajov zo senzorov
  doc["motion"] = motionDetected ? "DETECTED" : "CLEAR";
  
  // Serializácia do JSON
  char jsonBuffer[256];
  size_t n = serializeJson(doc, jsonBuffer);
  
  // Odoslanie na MQTT tému
  String topic = String(mqtt_sensor_topic) + "/" + deviceId;
  bool success = mqttClient.publish(topic.c_str(), jsonBuffer, n);
  
  if (success) {
    Serial.println("Údaje zo senzorov odoslané");
  } else {
    Serial.println("Chyba pri odosielaní údajov zo senzorov");
  }
}

void sendDeviceStatus() {
  // Pravidelné odosielanie stavu zariadenia
  if (millis() - lastStatusUpdate > statusUpdateInterval || !previouslyConnected) {
    // Kontrola pripojenia
    if (!mqttClient.connected()) {
      return;
    }
    
    // Vytvorenie JSON dokumentu
    StaticJsonDocument<256> doc;
    
    // Informácie o zariadení
    doc["device_id"] = deviceId;
    doc["room"] = deviceRoom;
    doc["status"] = "ONLINE";
    doc["timestamp"] = millis();
    doc["uptime"] = millis() / 1000;
    doc["ip"] = WiFi.localIP().toString();
    doc["rssi"] = WiFi.RSSI();
    doc["firmware"] = "1.0.0";
    
    // Serializácia do JSON
    char jsonBuffer[256];
    size_t n = serializeJson(doc, jsonBuffer);
    
    // Odoslanie na MQTT tému
    String topic = String(mqtt_status_topic) + "/" + deviceId;
    bool success = mqttClient.publish(topic.c_str(), jsonBuffer, n);
    
    if (success) {
      Serial.println("Stav zariadenia odoslaný");
    } else {
      Serial.println("Chyba pri odosielaní stavu zariadenia");
    }
    
    lastStatusUpdate = millis();
    previouslyConnected = true;
  }
}

void sendConnectMessage() {
  // Kontrola pripojenia
  if (!mqttClient.connected()) {
    return;
  }
  
  // Vytvorenie JSON dokumentu
  StaticJsonDocument<256> doc;
  
  // Informácie o zariadení
  doc["device_id"] = deviceId;
  doc["room"] = deviceRoom;
  doc["event"] = "CONNECT";
  doc["timestamp"] = millis();
  doc["ip"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  
  // Serializácia do JSON
  char jsonBuffer[256];
  size_t n = serializeJson(doc, jsonBuffer);
  
  // Odoslanie na MQTT tému
  String topic = String(mqtt_status_topic) + "/" + deviceId;
  mqttClient.publish(topic.c_str(), jsonBuffer, n);
}
