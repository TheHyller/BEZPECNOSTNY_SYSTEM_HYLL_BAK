#!/usr/bin/env python3
# TESTER.py - Testovací program pre Raspberry Pi bez fyzických senzorov
import json
import threading
import time
import os
import random
import paho.mqtt.client as mqtt
import socket

# Nastavenia testovacieho zariadenia
DEVICE_ID = "rpi_tester_1"
DEVICE_NAME = "Spálňa"  # Miestnosť umiestnenia

# MQTT nastavenia - predvolené hodnoty
DEFAULT_MQTT_BROKER = "localhost"  # Predvolená IP adresa MQTT brokera
MQTT_PORT = 1883
MQTT_USERNAME = ""  # Ponechať prázdne ak autentifikácia nie je potrebná
MQTT_PASSWORD = ""  # Ponechať prázdne ak autentifikácia nie je potrebná
MQTT_CLIENT_ID = f"home_security_tester_{DEVICE_ID}_{int(time.time())}"
MQTT_TOPIC_SENSOR = f"home/security/sensors/{DEVICE_ID}"
MQTT_TOPIC_STATUS = f"home/security/status/{DEVICE_ID}"
MQTT_TOPIC_CONTROL = f"home/security/control/{DEVICE_ID}"
MQTT_TOPIC_IMAGE = f"home/security/images/{DEVICE_ID}"
MQTT_QOS = 1

# Konfigurácia pre automatické zisťovanie MQTT brokera
MQTT_DISCOVERY_PORT = 12345
MQTT_DISCOVERY_TIMEOUT = 30  # sekundy

# Premenné pre MQTT
mqtt_client = None
mqtt_connected = False
mqtt_broker = DEFAULT_MQTT_BROKER
last_discovery_attempt = 0
DISCOVERY_RETRY_INTERVAL = 60  # sekúnd

# Typy senzorov na testovanie
SENSOR_TYPES = ["motion", "door", "window"]

# Slovenské reťazce pre výpis
SENSOR_LABELS = {
    "motion": "Pohyb",
    "door": "Dvere",
    "window": "Okno"
}

# Intervaly pre simuláciu (v sekundách)
STATUS_INTERVAL = 5
MQTT_RECONNECT_INTERVAL = 5

def load_config():
    """Načíta konfiguráciu zo súboru config.json ak existuje."""
    global DEFAULT_MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, mqtt_broker
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                config = json.load(file)
                
                if 'mqtt' in config:
                    mqtt_config = config['mqtt']
                    DEFAULT_MQTT_BROKER = mqtt_config.get('broker', DEFAULT_MQTT_BROKER)
                    MQTT_PORT = mqtt_config.get('port', MQTT_PORT)
                    MQTT_USERNAME = mqtt_config.get('username', MQTT_USERNAME)
                    MQTT_PASSWORD = mqtt_config.get('password', MQTT_PASSWORD)
                    
                print("Konfigurácia načítaná z config.json")
    except Exception as e:
        print(f"Chyba pri načítaní konfigurácie: {e}")

def find_mqtt_broker():
    """Automaticky vyhľadá MQTT broker na sieti pomocou broadcast protokolu."""
    global mqtt_broker, last_discovery_attempt
    
    print("Hľadám MQTT broker na sieti...")
    last_discovery_attempt = time.time()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(MQTT_DISCOVERY_TIMEOUT)
    
    try:
        discovery_message = json.dumps({
            "type": "mqtt_discovery_request",
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME
        }).encode('utf-8')
        
        broadcast_address = "255.255.255.255"
        print(f"Odosielam broadcast discovery požiadavku na {broadcast_address}:{MQTT_DISCOVERY_PORT}")
        sock.sendto(discovery_message, (broadcast_address, MQTT_DISCOVERY_PORT))
        
        sock.bind(("", MQTT_DISCOVERY_PORT))
        print(f"Čakám na MQTT discovery odpoveď ({MQTT_DISCOVERY_TIMEOUT}s)...")
        
        data, addr = sock.recvfrom(1024)
        print(f"Prijatá odpoveď od {addr}")
        
        message = json.loads(data.decode("utf-8"))
        
        if message.get("type") == "mqtt_discovery" or message.get("type") == "mqtt_discovery_response":
            discovered_broker = message.get("broker_ip")
            discovered_port = message.get("broker_port", MQTT_PORT)
            
            print(f"Nájdený MQTT broker: {discovered_broker}:{discovered_port}")
            
            mqtt_broker = discovered_broker
            MQTT_PORT = discovered_port
            
            return True
            
    except socket.timeout:
        print(f"Vypršal časový limit ({MQTT_DISCOVERY_TIMEOUT}s) pre hľadanie MQTT brokera")
    except Exception as e:
        print(f"Chyba pri hľadaní MQTT brokera: {e}")
    finally:
        sock.close()
        
    print(f"Použijem predvolenú adresu MQTT brokera: {DEFAULT_MQTT_BROKER}")
    mqtt_broker = DEFAULT_MQTT_BROKER
    return False

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback pri pripojení k MQTT brokeru."""
    global mqtt_connected
    
    if rc == 0:
        mqtt_connected = True
        print(f"Pripojený k MQTT brokeru ({mqtt_broker}:{MQTT_PORT})")
        
        client.subscribe(MQTT_TOPIC_CONTROL, qos=MQTT_QOS)
        
        publish_mqtt_status("ONLINE", "Testovací program spustený")
        
    else:
        mqtt_connected = False
        print(f"Nepodarilo sa pripojiť k MQTT brokeru, kód: {rc}")

def on_mqtt_disconnect(client, userdata, rc):
    """Callback pri odpojení od MQTT brokera."""
    global mqtt_connected
    mqtt_connected = False
    
    if rc != 0:
        print(f"Neočakávané odpojenie od MQTT brokera, kód: {rc}")
    else:
        print("Odpojený od MQTT brokera")

def on_mqtt_message(client, userdata, msg):
    """Spracovanie prijatých MQTT správ."""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode('utf-8'))
        print(f"MQTT správa prijatá: {topic} - {payload}")
        
        if topic == MQTT_TOPIC_CONTROL:
            handle_control_message(payload)
    except json.JSONDecodeError:
        print(f"Neplatný JSON formát: {msg.payload}")
    except Exception as e:
        print(f"Chyba pri spracovaní MQTT správy: {e}")

def handle_control_message(payload):
    """Spracovanie riadiacich príkazov."""
    command = payload.get('command')
    
    if command == 'status':
        send_all_sensors_status()
    elif command == 'restart':
        print("Prijatý príkaz na reštart programu")
    elif command == 'identify':
        print("Zariadenie identifikované")

def setup_mqtt():
    """Nastavenie a spustenie MQTT klienta."""
    global mqtt_client
    
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    lwt_payload = json.dumps({
        "status": "OFFLINE",
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "timestamp": time.time()
    })
    mqtt_client.will_set(MQTT_TOPIC_STATUS, lwt_payload, qos=MQTT_QOS, retain=True)
    
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message
    
    mqtt_client.loop_start()
    
    try_mqtt_connect()

def try_mqtt_connect():
    """Pokus o pripojenie k MQTT brokeru."""
    global mqtt_broker
    
    if mqtt_client is None:
        return
        
    try:
        print(f"Pripájam sa k MQTT brokeru {mqtt_broker}:{MQTT_PORT}...")
        print("Tip: Skontrolujte, či je služba Mosquitto MQTT broker spustená.")
        mqtt_client.connect(mqtt_broker, MQTT_PORT, keepalive=60)
    except ConnectionRefusedError as e:
        print(f"Broker odmietol pripojenie: {e}")
        print("Skontrolujte, či je Mosquitto broker spustený pomocou príkazu 'services.msc' (Windows) alebo 'sudo systemctl status mosquitto' (Linux)")
        print(f"Ďalší pokus o pripojenie za {MQTT_RECONNECT_INTERVAL} sekúnd...")
        threading.Timer(MQTT_RECONNECT_INTERVAL, try_mqtt_connect).start()
    except Exception as e:
        print(f"Chyba pri pripájaní k MQTT brokeru: {e}")
        print(f"Ďalší pokus o pripojenie za {MQTT_RECONNECT_INTERVAL} sekúnd...")
        threading.Timer(MQTT_RECONNECT_INTERVAL, try_mqtt_connect).start()

def publish_mqtt_status(status, message=""):
    """Publikovanie stavu zariadenia cez MQTT."""
    global mqtt_connected
    
    if not mqtt_connected or mqtt_client is None:
        return False
    
    payload = {
        "status": status,
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "room": DEVICE_NAME,
        "timestamp": time.time()
    }
    
    if message:
        payload["message"] = message
    
    try:
        mqtt_client.publish(MQTT_TOPIC_STATUS, json.dumps(payload), qos=MQTT_QOS, retain=True)
        return True
    except Exception as e:
        print(f"Chyba pri publikovaní MQTT stavu: {e}")
        return False

def publish_mqtt_sensor_data(sensor_type, status):
    """Publikovanie údajov zo senzora cez MQTT."""
    global mqtt_connected
    
    if not mqtt_connected or mqtt_client is None:
        return False
        
    payload = {
        sensor_type: status,
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "room": DEVICE_NAME,
        "timestamp": time.time()
    }
    
    try:
        mqtt_client.publish(MQTT_TOPIC_SENSOR, json.dumps(payload), qos=MQTT_QOS)
        return True
    except Exception as e:
        print(f"Chyba pri publikovaní MQTT údajov zo senzora: {e}")
        return False

def publish_mqtt_image(image_path, trigger_type="motion"):
    """Publikovanie obrázka cez MQTT."""
    global mqtt_connected
    
    if not mqtt_connected or mqtt_client is None or not os.path.exists(image_path):
        return False
        
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
            
        import base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            "image_data": image_base64,
            "metadata": {
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "room": DEVICE_NAME,
                "trigger": trigger_type,
                "timestamp": time.time(),
                "filename": os.path.basename(image_path)
            }
        }
        
        mqtt_client.publish(MQTT_TOPIC_IMAGE, json.dumps(payload), qos=MQTT_QOS)
        print("Obrázok publikovaný cez MQTT")
        return True
    except Exception as e:
        print(f"Chyba pri publikovaní MQTT obrázka: {e}")
        return False

def send_all_sensors_status():
    """Odošle stav všetkých senzorov."""
    status = {
        "motion": "DETECTED" if random.random() < 0.3 else "IDLE",
        "door": "OPEN" if random.random() < 0.2 else "CLOSED",
        "window": "OPEN" if random.random() < 0.2 else "CLOSED",
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "room": DEVICE_NAME,
        "timestamp": time.time()
    }
    
    if mqtt_connected and mqtt_client is not None:
        try:
            mqtt_client.publish(MQTT_TOPIC_SENSOR, json.dumps(status), qos=MQTT_QOS)
            print("Všetky stavy senzorov publikované cez MQTT")
        except Exception as e:
            print(f"Chyba pri publikovaní MQTT údajov zo všetkých senzorov: {e}")
    else:
        print("MQTT nie je pripojené, nemožno publikovať stavy senzorov")

def send_status(sensor_type, status):
    """Odošle stav senzora."""
    success = publish_mqtt_sensor_data(sensor_type, status)
    
    if success:
        print(f"Odoslaný stav: {SENSOR_LABELS.get(sensor_type, sensor_type)} = {status}")
        return True
    else:
        print(f"Nepodarilo sa odoslať stav {sensor_type} = {status}")
        return False

def send_test_image():
    """Simulácia odoslania obrázka po detekcii pohybu."""
    image_path = os.path.join(os.path.dirname(__file__), "test_image.jpg")
    
    if not os.path.exists(image_path):
        with open(image_path, "w") as f:
            f.write("Toto je testovací súbor namiesto obrázka.")
    
    success = publish_mqtt_image(image_path)
    
    if success:
        print(f"Odoslaný testovací obrázok cez MQTT")
    else:
        print("Nepodarilo sa odoslať testovací obrázok")

def simulate_sensors():
    """Simuluje zmeny stavu senzorov a náhodne generuje udalosti."""
    print("Spúšťam simuláciu senzorov...")
    
    while True:
        sensor_type = random.choice(SENSOR_TYPES)
        
        if sensor_type == "motion":
            status = "DETECTED" if random.random() < 0.3 else "IDLE" 
            if status == "DETECTED":
                threading.Thread(target=send_test_image).start()
        else:
            status = "OPEN" if random.random() < 0.2 else "CLOSED"
        
        send_status(sensor_type, status)
        
        time.sleep(STATUS_INTERVAL)

def mqtt_monitor():
    """Monitoruje stav MQTT pripojenia a pokúša sa o opätovné pripojenie."""
    global mqtt_connected, mqtt_broker, last_discovery_attempt
    
    while True:
        if not mqtt_connected and mqtt_client is not None:
            current_time = time.time()
            
            if current_time - last_discovery_attempt > DISCOVERY_RETRY_INTERVAL:
                print("Znova sa pokúšam nájsť MQTT broker...")
                if find_mqtt_broker():
                    mqtt_client.disconnect()
                    setup_mqtt()
                else:
                    try_mqtt_connect()
            else:
                print("MQTT pripojenie nie je aktívne, pokúšam sa znovu pripojiť...")
                try_mqtt_connect()
            
        time.sleep(MQTT_RECONNECT_INTERVAL)

def cleanup():
    """Vykoná čistiace operácie pred ukončením programu."""
    if mqtt_connected and mqtt_client is not None:
        try:
            publish_mqtt_status("OFFLINE", "Program ukončený")
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        except:
            pass

def main():
    """Hlavná funkcia programu."""
    print("=== TESTOVACÍ PROGRAM PRE RASPBERRY PI - SIMULÁCIA SENZOROV ===")
    
    load_config()
    
    find_mqtt_broker()
    
    setup_mqtt()
    
    threading.Thread(target=mqtt_monitor, daemon=True, name="MQTTMonitorThread").start()
    
    try:
        simulate_sensors()
    except KeyboardInterrupt:
        print("\nUkončujem testovanie...")
        cleanup()

if __name__ == "__main__":
    main()