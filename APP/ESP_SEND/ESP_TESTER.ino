// ESP_TESTER.ino - Testovací program pre ESP8266 bez fyzických senzorov
#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <time.h>

// ---------- KONFIGURÁCIA ----------
const char* ssid = "WIFI";       // Zadajte názov vašej WiFi siete
const char* password = "PASS"; // Zadajte heslo k vašej WiFi sieti
const char* deviceId = "esp_tester_1";     // Identifikátor zariadenia
const char* deviceRoom = "Obývačka";       // Miestnosť umiestnenia
const int LED_PIN = 2;                     // LED na signalizáciu aktivity (D4 na NodeMCU)

// MQTT nastavenia
const char* mqtt_server = "192.168.1.100";  // IP adresa MQTT brokera (zmeňte na vašu)
const int mqtt_port = 1883;                 // Port MQTT brokera
const char* mqtt_client_id = "esp_tester_1";
const char* mqtt_username = "";             // Nechajte prázdne ak nepoužívate autentifikáciu
const char* mqtt_password = "";             // Nechajte prázdne ak nepoužívate autentifikáciu
const char* mqtt_topic_sensor = "home/security/sensors/esp_tester_1";
const char* mqtt_topic_status = "home/security/status/esp_tester_1";
const char* mqtt_topic_control = "home/security/control/esp_tester_1";

// Typy senzorov na testovanie
const char* sensorTypes[] = {"motion", "door", "window"};
const int numSensorTypes = 3;

// Komunikačné nastavenia
WiFiUDP udp;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
char rec_ip[16] = "";
const int UDP_DISCOVER_PORT = 12345;  // Port pre UDP discovery
const int UDP_STATUS_PORT = 8081;

// Intervaly pre simuláciu (v ms)
const unsigned long discoverInterval = 30000;  // 30 sekúnd interval pre znovu-objavenie prijímača
const unsigned long statusInterval = 5000;     // 5 sekúnd interval pre simuláciu zmeny stavu
const unsigned long mqttReconnectInterval = 5000; // 5 sekúnd interval pre opätovné pripojenie k MQTT

// Časovače
unsigned long lastDiscoverTime = 0;
unsigned long lastStatusTime = 0;
unsigned long lastMqttReconnectTime = 0;

// Buffer pre JSON správy
char mqttBuffer[512];

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- ESP TESTER - SIMULÁCIA SENZOROV ---");
  
  // Nastavenie LED pinu
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Inicializácia náhodného generátora
  randomSeed(analogRead(0));
  
  // Pripojenie k WiFi
  connectToWifi();
  
  // Nastavenie MQTT
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(mqttCallback);
  
  // Prvotné vyhľadanie prijímača (UDP)
  discoverReceiver();
}

void loop() {
  // Kontrola MQTT pripojenia
  if (!mqttClient.connected()) {
    reconnectMqtt();
  }
  mqttClient.loop();

  // Pravidelné vyhľadávanie prijímača (UDP)
  if (millis() - lastDiscoverTime > discoverInterval) {
    discoverReceiver();
    lastDiscoverTime = millis();
  }

  // Simulácia zmeny stavu senzorov
  if (millis() - lastStatusTime > statusInterval) {
    simulateSensors();
    lastStatusTime = millis();
  }
}

void connectToWifi() {
  Serial.print("Pripájanie k WiFi sieti ");
  Serial.print(ssid);
  Serial.println("...");
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Blikanie LED počas pripájania
    delay(500);
    Serial.print(".");
  }
  
  digitalWrite(LED_PIN, HIGH); // LED zostane svietiť po pripojení
  
  Serial.println("\nWiFi pripojené!");
  Serial.print("IP adresa: ");
  Serial.println(WiFi.localIP());
}

void reconnectMqtt() {
  // Kontrola či už nie je čas na pokus o MQTT pripojenie
  if (millis() - lastMqttReconnectTime < mqttReconnectInterval) {
    return;
  }
  
  Serial.print("Pripájanie k MQTT brokeru...");
  
  // Vytvorenie LWT (Last Will and Testament) správy
  StaticJsonDocument<200> lwt;
  lwt["status"] = "OFFLINE";
  lwt["device_id"] = deviceId;
  lwt["room"] = deviceRoom;
  char lwtBuffer[200];
  serializeJson(lwt, lwtBuffer);
  
  // Pripojenie k MQTT brokeru
  if (mqttClient.connect(mqtt_client_id, 
                        mqtt_username, 
                        mqtt_password,
                        mqtt_topic_status,  // LWT topic
                        0,                  // QoS
                        true,               // retain
                        lwtBuffer)) {       // LWT message
    Serial.println("pripojené!");
    
    // Prihlásenie na riadiaci topic
    mqttClient.subscribe(mqtt_topic_control);
    
    // Publikovanie ONLINE statusu
    StaticJsonDocument<200> status;
    status["status"] = "ONLINE";
    status["device_id"] = deviceId;
    status["device_name"] = deviceId;
    status["room"] = deviceRoom;
    status["ip"] = WiFi.localIP().toString();
    
    serializeJson(status, mqttBuffer);
    mqttClient.publish(mqtt_topic_status, mqttBuffer, true); // retain flag true
    
    // Zablikanie LED
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, LOW);
      delay(100);
      digitalWrite(LED_PIN, HIGH);
      delay(100);
    }
    
  } else {
    Serial.print("zlyhalo, rc=");
    Serial.print(mqttClient.state());
    Serial.println(" skúsim znova o 5 sekúnd");
  }
  
  lastMqttReconnectTime = millis();
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Prijatá správa v topicu: ");
  Serial.println(topic);
  
  // Kopírovanie správy do bufferu a pridanie null-terminácie
  char message[length + 1];
  memcpy(message, payload, length);
  message[length] = '\0';
  
  Serial.print("Správa: ");
  Serial.println(message);
  
  // Parsovanie JSON správy
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.print("Chyba deserializácie JSON: ");
    Serial.println(error.c_str());
    return;
  }
  
  // Spracovanie príkazov
  const char* command = doc["command"];
  
  if (command) {
    if (strcmp(command, "status") == 0) {
      publishSensorData();
    } 
    else if (strcmp(command, "restart") == 0) {
      Serial.println("Reštartujem zariadenie...");
      ESP.restart();
    }
  }
}

void discoverReceiver() {
  Serial.println("Vyhľadávanie MQTT brokera (UDP)...");
  udp.begin(UDP_DISCOVER_PORT);
  
  // Príprava JSON správy pre discovery request
  StaticJsonDocument<256> doc;
  doc["type"] = "mqtt_discovery_request";
  doc["device_id"] = deviceId;
  doc["device_name"] = deviceRoom;
  
  char jsonBuffer[256];
  size_t n = serializeJson(doc, jsonBuffer);
  
  // Odoslanie broadcast paketu
  udp.beginPacket("255.255.255.255", UDP_DISCOVER_PORT);
  udp.write((uint8_t*)jsonBuffer, n);
  udp.endPacket();
  
  Serial.print("Odoslaná broadcast požiadavka na port ");
  Serial.println(UDP_DISCOVER_PORT);
  
  // Čakanie na odpoveď
  unsigned long startTime = millis();
  bool receiverFound = false;
  
  while (millis() - startTime < 5000) {  // 5 sekúnd timeout
    int packetSize = udp.parsePacket();
    if (packetSize) {
      char packetBuffer[255];
      int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
      packetBuffer[len] = '\0';
      
      Serial.print("Prijatý UDP paket, veľkosť: ");
      Serial.println(packetSize);
      
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
        
        // Aktualizácia konfigurácie MQTT
        strncpy(rec_ip, discovered_broker, sizeof(rec_ip));
        
        // Aktualizácia MQTT brokera, ak sa líši od aktuálneho
        if (strcmp(discovered_broker, mqtt_server) != 0 || discovered_port != mqtt_port) {
          Serial.println("Aktualizujem MQTT nastavenia...");
          // Ak už sme pripojení k brokeru, odpojíme sa
          if (mqttClient.connected()) {
            mqttClient.disconnect();
          }
          mqttClient.setServer(discovered_broker, discovered_port);
        }
        
        receiverFound = true;
        break;
      }
    }
    delay(100);
  }
  
  if (!receiverFound) {
    Serial.println("MQTT broker nebol nájdený v časovom limite.");
  }
}

void simulateSensors() {
  // Náhodne vyberieme typ senzora pre simuláciu
  int sensorIndex = random(numSensorTypes);
  const char* sensorType = sensorTypes[sensorIndex];
  
  // Simulácia stavu senzora
  const char* status;
  if (strcmp(sensorType, "motion") == 0) {
    status = (random(10) < 3) ? "DETECTED" : "IDLE";  // 30% šanca na detekciu pohybu
  } else {
    status = (random(10) < 2) ? "OPEN" : "CLOSED";    // 20% šanca na otvorené dvere/okno
  }
  
  // Bliknutie LED pre indikovanie odosielania stavu
  digitalWrite(LED_PIN, LOW);
  delay(50);
  digitalWrite(LED_PIN, HIGH);
  
  // Odoslanie stavu (UDP aj MQTT)
  sendStatus(sensorType, status);
  
  // Výpis do konzoly
  Serial.print("Simulovaný senzor: ");
  Serial.print(sensorType);
  Serial.print(", Stav: ");
  Serial.println(status);
}

void sendStatus(const char* sensorType, const char* status) {
  // Odoslanie cez UDP (staršia metóda)
  if (strlen(rec_ip) > 0) {
    char msg[128];
    snprintf(msg, sizeof(msg), "SENSOR:%s:%s:%s:%s", deviceId, deviceRoom, sensorType, status);
    
    udp.beginPacket(rec_ip, UDP_STATUS_PORT);
    udp.write(msg);
    udp.endPacket();
  }
  
  // Odoslanie cez MQTT (nová metóda)
  if (mqttClient.connected()) {
    StaticJsonDocument<256> sensorData;
    sensorData[sensorType] = status;
    sensorData["device_id"] = deviceId;
    sensorData["device_name"] = deviceId;
    sensorData["room"] = deviceRoom;
    sensorData["timestamp"] = millis();
    
    serializeJson(sensorData, mqttBuffer);
    mqttClient.publish(mqtt_topic_sensor, mqttBuffer);
  }
}

void publishSensorData() {
  // Príprava správy so stavmi všetkých senzorov
  StaticJsonDocument<384> sensorData;
  
  sensorData["motion"] = (random(10) < 3) ? "DETECTED" : "IDLE";
  sensorData["door"] = (random(10) < 2) ? "OPEN" : "CLOSED";
  sensorData["window"] = (random(10) < 2) ? "OPEN" : "CLOSED";
  
  sensorData["device_id"] = deviceId;
  sensorData["device_name"] = deviceId;
  sensorData["room"] = deviceRoom;
  sensorData["timestamp"] = millis();
  
  // Odoslanie cez MQTT
  if (mqttClient.connected()) {
    serializeJson(sensorData, mqttBuffer);
    mqttClient.publish(mqtt_topic_sensor, mqttBuffer);
    
    Serial.println("Publikované všetky stavy senzorov");
  } else {
    Serial.println("Nemožno publikovať stavy - MQTT klient nepripojený");
  }
}