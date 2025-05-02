// ESP_SEND.ino - Hlavný Arduino skript pre ESP8266
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
const int LED_PIN = 2;     // D4 na NodeMCU - vstavané LED na ESP8266

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
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // ESP8266 LED je aktívna v LOW
  
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
  
  // Vizuálna indikácia pripájania k WiFi pomocou LED
  digitalWrite(LED_PIN, HIGH);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_PIN, LOW);  // LED zapnutá počas pripájania
    delay(250);
    digitalWrite(LED_PIN, HIGH); // LED vypnutá
    delay(250);
    Serial.print(".");
  }
  
  // Vizuálna indikácia úspešného pripojenia k WiFi - 3x zablikanie
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, LOW);
    delay(100);
    digitalWrite(LED_PIN, HIGH);
    delay(100);
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
  
  // Vizuálna indikácia hľadania brokera - rýchle blikanie LED
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_PIN, LOW);
    delay(50);
    digitalWrite(LED_PIN, HIGH);
    delay(50);
  }
  
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
        
        // Úspech - zablikanie LED 2x dlhšie
        digitalWrite(LED_PIN, LOW);
        delay(200);
        digitalWrite(LED_PIN, HIGH);
        delay(200);
        digitalWrite(LED_PIN, LOW);
        delay(200);
        digitalWrite(LED_PIN, HIGH);
        
        return true;
      }
    }
    
    delay(100); // Krátka pauza pre zníženie zaťaženia CPU
  }
  
  Serial.println("MQTT broker nebol nájdený v časovom limite. Použijem predvolenú konfiguráciu.");
  
  // Neúspech - rozsvietenie LED na dlhší čas
  digitalWrite(LED_PIN, LOW);
  delay(500);
  digitalWrite(LED_PIN, HIGH);
  
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
    
    // Vizuálna indikácia pokusu o pripojenie
    digitalWrite(LED_PIN, LOW); 
    delay(100);
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    
    // Vytvorenie klientského ID
    String clientId = "ESP-";
    clientId += String(random(0xffff), HEX);
    
    // Pripravenie Last Will and Testament (LWT) správy
    StaticJsonDocument<200> lwt;
    lwt["status"] = "OFFLINE";
    lwt["device_id"] = deviceId;
    lwt["device_name"] = deviceId;
    lwt["room"] = deviceRoom;
    lwt["timestamp"] = millis();
    
    char lwtBuffer[200];
    serializeJson(lwt, lwtBuffer);
    
    // Pokus o pripojenie s LWT
    bool connected = false;
    String statusTopic = String(mqtt_status_topic) + "/" + deviceId;
    
    if (mqtt_username[0] != '\0') {
      connected = mqttClient.connect(
        clientId.c_str(),
        mqtt_username,
        mqtt_password,
        statusTopic.c_str(),  // LWT topic
        0,                    // QoS
        true,                 // retain
        lwtBuffer             // LWT message
      );
    } else {
      connected = mqttClient.connect(
        clientId.c_str(),
        statusTopic.c_str(),  // LWT topic
        0,                    // QoS
        true,                 // retain
        lwtBuffer             // LWT message
      );
    }
    
    if (connected) {
      Serial.println("MQTT pripojené!");
      
      // Prihlásenie sa na tému pre príkazy
      String controlTopic = String(mqtt_control_topic) + "/" + deviceId;
      mqttClient.subscribe(controlTopic.c_str());
      Serial.print("Prihlásený na kontrolnej téme: ");
      Serial.println(controlTopic);
      
      // Odoslanie informácie o pripojení
      sendConnectMessage();
      
      // Aktualizácia príznaku pripojenia
      previouslyConnected = true;
      
      // Vizuálna indikácia úspešného pripojenia - 3x zablikanie
      for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, LOW);
        delay(100);
        digitalWrite(LED_PIN, HIGH);
        delay(100);
      }
    } else {
      Serial.print("zlyhalo, rc=");
      Serial.print(mqttClient.state());
      
      // Poskytnutie užívateľsky prívetivej správy o chybe
      switch (mqttClient.state()) {
        case -4: 
          Serial.println(" - Timeout pri pripájaní");
          break;
        case -3: 
          Serial.println(" - Server nedostupný");
          break;
        case -2: 
          Serial.println(" - Chyba pri pripájaní");
          break;
        case -1: 
          Serial.println(" - Server odmietol pripojenie");
          break;
        case 1: 
          Serial.println(" - Chyba protokolu");
          break;
        case 2: 
          Serial.println(" - Identifikátor odmietnutý");
          break;
        case 3: 
          Serial.println(" - Server nedostupný");
          break;
        case 4: 
          Serial.println(" - Chybné používateľské meno/heslo");
          break;
        case 5: 
          Serial.println(" - Neautorizované pripojenie");
          break;
        default: 
          Serial.println(" - Neznáma chyba");
      }
      
      Serial.println("Skontrolujte, či je Mosquitto broker spustený a dostupný.");
      Serial.println("Ďalší pokus o 5 sekúnd...");
      
      // Vizuálna indikácia zlyhania - dlhé bliknutie
      digitalWrite(LED_PIN, LOW);
      delay(500);
      digitalWrite(LED_PIN, HIGH);
      
      retry++;
      delay(5000);
    }
  }
  
  if (!mqttClient.connected()) {
    Serial.println("Nepodarilo sa pripojiť k MQTT brokeru po viacerých pokusoch.");
    Serial.println("Skúsim znova neskôr.");
  }
}

// Funkcia pre čítanie senzorov
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

// Funkcia pre odosielanie údajov zo senzorov
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

// Funkcia pre odosielanie stavu zariadenia
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

// Funkcia pre odosielanie informácie o pripojení
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

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Prijatá správa na téme: ");
  Serial.print(topic);
  Serial.print(", dĺžka: ");
  Serial.println(length);
  
  // Blikneme LED na oznámenie prijatia novej správy
  digitalWrite(LED_PIN, LOW);
  delay(50);
  digitalWrite(LED_PIN, HIGH);
  
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
    
    // Indikácia chyby - tri rýchle bliknutia
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(50);
      digitalWrite(LED_PIN, HIGH);
      delay(50);
    }
    
    return;
  }
  
  // Spracovanie príkazu
  if (!doc.containsKey("command")) {
    Serial.println("Správa neobsahuje príkaz");
    return;
  }
  
  const char* command = doc["command"];
  
  if (strcmp(command, "RESET") == 0) {
    Serial.println("Príkaz na resetovanie zariadenia");
    
    // Vizuálna indikácia reštartu - séria bliknutí
    for (int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(100);
      digitalWrite(LED_PIN, HIGH);
      delay(100);
    }
    
    ESP.restart();
  }
  else if (strcmp(command, "STATUS") == 0) {
    Serial.println("Príkaz na odoslanie aktuálneho stavu");
    
    // Krátke bliknutie pre potvrdenie
    digitalWrite(LED_PIN, LOW);
    delay(200);
    digitalWrite(LED_PIN, HIGH);
    
    sendSensorData(true);
    sendDeviceStatus();
  }
  else if (strcmp(command, "DISCOVER") == 0) {
    Serial.println("Príkaz na vyhľadanie MQTT brokera");
    
    // Série krátkych bliknutí pre indikáciu discovery
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(50);
      digitalWrite(LED_PIN, HIGH);
      delay(50);
    }
    
    discoverMQTTBroker();
    
    // Ak sa broker zmenil, odpojíme sa a znova pripojíme
    if (broker_discovered) {
      mqttClient.disconnect();
      mqttClient.setServer(mqtt_server, mqtt_port);
      reconnectMQTT();
    }
  }
  else if (strcmp(command, "IDENTIFY") == 0) {
    // Nový príkaz na identifikáciu zariadenia - bliká LED pre ľahkú lokalizáciu zariadenia
    Serial.println("Príkaz na identifikáciu zariadenia");
    
    // Séria dlhých bliknutí pre jasnú identifikáciu
    for (int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(300);
      digitalWrite(LED_PIN, HIGH);
      delay(300);
    }
  }
  else {
    Serial.print("Neznámy príkaz: ");
    Serial.println(command);
    
    // Indikácia neznámeho príkazu - dve dlhé bliknutia
    for (int i = 0; i < 2; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(500);
      digitalWrite(LED_PIN, HIGH);
      delay(500);
    }
  }
}
