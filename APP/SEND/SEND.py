#!/usr/bin/env python3
# SEND.py - Program pre Raspberry Pi pre fyzické senzory
import json
import threading
import time
import os
import socket
import RPi.GPIO as GPIO
from picamera2 import Picamera2
from libcamera import controls
import io
import paho.mqtt.client as mqtt
import base64

# Nastavenia zariadenia
DEVICE_ID = "rpi_send_1"
DEVICE_NAME = "Vstupná chodba"  # Miestnosť umiestnenia

# MQTT nastavenia - predvolené hodnoty
DEFAULT_MQTT_BROKER = "localhost"  # Zmeniť na predvolenú IP adresu MQTT brokera
MQTT_PORT = 1883
MQTT_USERNAME = ""  # Ponechať prázdne ak autentifikácia nie je potrebná
MQTT_PASSWORD = ""  # Ponechať prázdne ak autentifikácia nie je potrebná
MQTT_CLIENT_ID = f"home_security_sender_{DEVICE_ID}_{int(time.time())}"
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
mqtt_broker = DEFAULT_MQTT_BROKER  # Táto hodnota môže byť nahradená pri automatickom zisťovaní

# Nastavenia GPIO pinov
MOTION_PIN = 17  # GPIO pre pohybový senzor
DOOR_PIN = 18    # GPIO pre dverový kontakt
WINDOW_PIN = 27  # GPIO pre okenný kontakt
LED_PIN = 22     # GPIO pre LED indikátor

# Slovenské reťazce pre výpis
SENSOR_LABELS = {
    "motion": "Pohyb",
    "door": "Dvere",
    "window": "Okno"
}

# Intervaly (v sekundách)
STATUS_INTERVAL = 30    # 30 sekúnd interval pre odoslanie všetkých stavov
DEBOUNCE_TIME = 0.5     # 500ms debounce pre senzory
MQTT_RECONNECT_INTERVAL = 5  # 5 sekúnd interval pre opätovné pripojenie k MQTT
DISCOVERY_RETRY_INTERVAL = 60  # 60 sekúnd interval pre opätovný pokus o zistenie brokera

# Časovače poslednej zmeny
last_motion_time = 0
last_door_time = 0
last_window_time = 0
last_discovery_attempt = 0

# Posledné stavy senzorov
last_motion_state = False
last_door_state = False
last_window_state = False

# Premenne pre kameru
camera = None
camera_resolution = (640, 480)
camera_framerate = 24
camera_rotation = 0
camera_warmup_time = 2  # sekundy na inicializáciu kamery

def load_config():
    """Načíta konfiguráciu zo súboru config.json ak existuje."""
    global MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, mqtt_broker
    global camera_resolution, camera_framerate, camera_rotation, camera_warmup_time
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                config = json.load(file)
                
                # Nastavenia MQTT
                if 'mqtt' in config:
                    mqtt_config = config['mqtt']
                    # Načítame predvolenú hodnotu, ale použijeme ju iba ak sa nenájde broker automaticky
                    DEFAULT_MQTT_BROKER = mqtt_config.get('broker', DEFAULT_MQTT_BROKER)
                    MQTT_PORT = mqtt_config.get('port', MQTT_PORT)
                    MQTT_USERNAME = mqtt_config.get('username', MQTT_USERNAME)
                    MQTT_PASSWORD = mqtt_config.get('password', MQTT_PASSWORD)
                
                # Nastavenia kamery
                if 'camera' in config:
                    camera_config = config['camera']
                    width = camera_config.get('resolution_width', camera_resolution[0])
                    height = camera_config.get('resolution_height', camera_resolution[1])
                    camera_resolution = (width, height)
                    camera_framerate = camera_config.get('framerate', camera_framerate)
                    camera_rotation = camera_config.get('rotation', camera_rotation)
                    camera_warmup_time = camera_config.get('warmup_time', camera_warmup_time)
                
                print("Konfigurácia načítaná z config.json")
    except Exception as e:
        print(f"Chyba pri načítaní konfigurácie: {e}")

def find_mqtt_broker():
    """Automaticky vyhľadá MQTT broker na sieti pomocou broadcast protokolu."""
    global mqtt_broker, last_discovery_attempt, MQTT_PORT
    
    print("Hľadám MQTT broker na sieti...")
    last_discovery_attempt = time.time()
    
    # Vytvorenie UDP socketu pre odoslanie a príjem discovery správ
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(MQTT_DISCOVERY_TIMEOUT)
    
    try:
        # Príprava broadcast discovery správy
        discovery_message = json.dumps({
            "type": "mqtt_discovery_request",
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME
        }).encode('utf-8')
        
        # Odoslanie broadcast správy
        broadcast_address = "255.255.255.255"  # UDP broadcast adresa
        print(f"Odosielam broadcast discovery požiadavku na {broadcast_address}:{MQTT_DISCOVERY_PORT}")
        sock.sendto(discovery_message, (broadcast_address, MQTT_DISCOVERY_PORT))
        
        # Nastavenie timeoutu pre čakanie na odpoveď - 10 sekúnd
        start_time = time.time()
        discovery_timeout = 10
        
        # Čakanie na odpoveď so slučkou, ktorá skúša viackrát počas timeoutu
        while time.time() - start_time < discovery_timeout:
            try:
                # Skúsime prijať odpoveď
                data, addr = sock.recvfrom(1024)
                print(f"Prijatá odpoveď od {addr}")
                
                # Parsovanie JSON správy
                message = json.loads(data.decode("utf-8"))
                
                # Kontrola či ide o správny typ správy
                if message.get("type") == "mqtt_discovery" or message.get("type") == "mqtt_discovery_response":
                    discovered_broker = message.get("broker_ip")
                    discovered_port = message.get("broker_port", MQTT_PORT)
                    
                    if discovered_broker:
                        print(f"Nájdený MQTT broker: {discovered_broker}:{discovered_port}")
                        
                        # Aktualizácia globálnych premenných
                        mqtt_broker = discovered_broker
                        MQTT_PORT = discovered_port
                        
                        # Blikanie LED pre vizuálnu indikáciu úspešného objavenia
                        for _ in range(3):
                            GPIO.output(LED_PIN, GPIO.HIGH)
                            time.sleep(0.1)
                            GPIO.output(LED_PIN, GPIO.LOW)
                            time.sleep(0.1)
                            
                        return True
            except socket.timeout:
                # Timeout pri čakaní na dáta
                continue
            except json.JSONDecodeError as e:
                print(f"Prijatá neplatná JSON odpoveď: {e}")
                continue
            except Exception as e:
                print(f"Chyba pri spracovaní odpovede: {e}")
                continue
                
            # Krátka pauza pred ďalším pokusom
            time.sleep(0.1)
            
    except socket.error as e:
        print(f"Socket chyba pri vyhľadávaní MQTT brokera: {e}")
    except Exception as e:
        print(f"Všeobecná chyba pri hľadaní MQTT brokera: {e}")
    finally:
        sock.close()
        
    # Ak sa nepodarilo nájsť broker, použijeme predvolenú hodnotu
    print(f"Použijem predvolenú adresu MQTT brokera: {DEFAULT_MQTT_BROKER}")
    mqtt_broker = DEFAULT_MQTT_BROKER
    
    # Indikácia zlyhaného vyhľadávania pomocou LED
    GPIO.output(LED_PIN, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(LED_PIN, GPIO.LOW)
    
    return False

def setup_gpio():
    """Nastavenie GPIO pinov."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Nastavenie vstupov pre senzory s internými pull-up rezistormi
    GPIO.setup(MOTION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DOOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(WINDOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Nastavenie výstupu pre LED
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    
    # Nastavenie callbackov pre edge detekciu
    GPIO.add_event_detect(MOTION_PIN, GPIO.BOTH, callback=motion_callback, bouncetime=200)
    GPIO.add_event_detect(DOOR_PIN, GPIO.BOTH, callback=door_callback, bouncetime=200)
    GPIO.add_event_detect(WINDOW_PIN, GPIO.BOTH, callback=window_callback, bouncetime=200)

def setup_camera():
    """Inicializácia kamery."""
    global camera
    
    try:
        camera = Picamera2()
        camera_config = camera.create_still_configuration(main={"size": camera_resolution})
        camera.configure(camera_config)
        
        # Nastavenie rotácie ak je potrebná
        if camera_rotation in [0, 90, 180, 270]:
            camera.set_controls({"RotationDegrees": camera_rotation})
            
        print(f"Kamera inicializovaná - rozlíšenie: {camera_resolution}, rotácia: {camera_rotation}°")
        
        # Zahriatie kamery
        print(f"Zahriatie kamery ({camera_warmup_time}s)...")
        camera.start()
        time.sleep(camera_warmup_time)
        camera.stop()
        
    except Exception as e:
        print(f"Chyba pri inicializácii kamery: {e}")
        camera = None

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback pri pripojení k MQTT brokeru."""
    global mqtt_connected
    
    if rc == 0:
        mqtt_connected = True
        print(f"Pripojený k MQTT brokeru ({mqtt_broker}:{MQTT_PORT})")
        
        # Prihlásenie na odber riadiacich správ
        client.subscribe(MQTT_TOPIC_CONTROL, qos=MQTT_QOS)
        
        # Publikovanie ONLINE statusu
        publish_mqtt_status("ONLINE")
        
        # Blikanie LED pre indikáciu úspešného pripojenia
        for _ in range(3):
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.1)
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
    global last_discovery_attempt
    
    command = payload.get('command')
    
    if command == 'status':
        # Odoslanie stavových údajov na vyžiadanie
        send_all_sensors_status()
    elif command == 'capture':
        # Zachytenie a odoslanie snímku z kamery
        threading.Thread(target=capture_and_send_image).start()
    elif command == 'restart':
        print("Prijatý príkaz na reštart programu")
        # Tu by mohol byť kód pre reštart programu
    elif command == 'identify':
        print("Zariadenie identifikované")
        # Blikanie LED pre identifikáciu
        for _ in range(10):
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.2)
    elif command == 'discover':
        # Príkaz na vyhľadanie MQTT brokera
        print("Prijatý príkaz na vyhľadanie MQTT brokera")
        if find_mqtt_broker():
            # Ak sa broker zmenil, odpojíme sa a znova nastavíme pripojenie
            if mqtt_client:
                mqtt_client.disconnect()
                setup_mqtt()

def setup_mqtt():
    """Nastavenie a spustenie MQTT klienta."""
    global mqtt_client
    
    # Vytvorenie klienta
    mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
    
    # Nastavenie prihlasovacích údajov ak sú poskytnuté
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Nastavenie Last Will and Testament (LWT)
    lwt_payload = json.dumps({
        "status": "OFFLINE",
        "device_id": DEVICE_ID,
        "device_name": DEVICE_NAME,
        "room": DEVICE_NAME,
        "timestamp": time.time()
    })
    mqtt_client.will_set(MQTT_TOPIC_STATUS, lwt_payload, qos=MQTT_QOS, retain=True)
    
    # Nastavenie callback funkcií
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message
    
    # Spustenie vlákna pre MQTT
    mqtt_client.loop_start()
    
    # Pokus o pripojenie
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
        # Nastavenie časovača pre opätovný pokus
        threading.Timer(MQTT_RECONNECT_INTERVAL, try_mqtt_connect).start()
    except Exception as e:
        print(f"Chyba pri pripájaní k MQTT brokeru: {e}")
        print(f"Ďalší pokus o pripojenie za {MQTT_RECONNECT_INTERVAL} sekúnd...")
        # Nastavenie časovača pre opätovný pokus
        threading.Timer(MQTT_RECONNECT_INTERVAL, try_mqtt_connect).start()

def mqtt_monitor():
    """Monitoruje stav MQTT pripojenia a pokúša sa o opätovné pripojenie."""
    global mqtt_connected, mqtt_broker, last_discovery_attempt
    
    while True:
        # Ak nie sme pripojení k MQTT brokeru
        if not mqtt_connected and mqtt_client is not None:
            current_time = time.time()
            
            # Ak uplynul čas od posledného pokusu o automatické zistenie brokera,
            # skúsime ho znova nájsť
            if current_time - last_discovery_attempt > DISCOVERY_RETRY_INTERVAL:
                print("Znova sa pokúšam nájsť MQTT broker...")
                if find_mqtt_broker():
                    # Ak sa broker zmenil, odpojíme sa a znova nastavíme pripojenie
                    mqtt_client.disconnect()
                    setup_mqtt()
                else:
                    # Ak sa nezmenil, skúsime sa znova pripojiť
                    try_mqtt_connect()
            else:
                # Skúšame sa pripojiť na aktuálny broker
                print("MQTT pripojenie nie je aktívne, pokúšam sa znovu pripojiť...")
                try_mqtt_connect()
            
        time.sleep(MQTT_RECONNECT_INTERVAL)

def publish_mqtt_status(status, message=None):
    """Publikuje status zariadenia cez MQTT."""
    if not mqtt_client or not mqtt_connected:
        print(f"MQTT nie je pripojené, nemôžem publikovať status: {status}")
        return False
    
    try:
        payload = {
            "status": status,
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "room": DEVICE_NAME,
            "timestamp": time.time()
        }
        
        # Pridanie správy ak bola poskytnutá
        if message:
            payload["message"] = message
            
        # Publikovanie na status topic
        result = mqtt_client.publish(
            MQTT_TOPIC_STATUS, 
            json.dumps(payload), 
            qos=MQTT_QOS,
            retain=True
        )
        
        # Kontrola úspešného odoslania
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Status publikovaný: {status}" + (f" - {message}" if message else ""))
            return True
        else:
            print(f"Chyba pri publikovaní statusu: {result.rc}")
            return False
    except Exception as e:
        print(f"Chyba pri publikovaní statusu: {e}")
        return False

def motion_callback(channel):
    """Callback pre pohybový senzor."""
    global last_motion_time, last_motion_state
    
    current_time = time.time()
    if current_time - last_motion_time > DEBOUNCE_TIME:
        last_motion_time = current_time
        current_state = GPIO.input(MOTION_PIN) == GPIO.LOW  # Invertovaná logika s pull-up
        
        if current_state != last_motion_state:
            last_motion_state = current_state
            publish_sensor_status("motion", current_state)
            
            # Zapneme LED na okamih ak bol detekovaný pohyb
            if current_state:
                GPIO.output(LED_PIN, GPIO.HIGH)
                threading.Timer(0.5, lambda: GPIO.output(LED_PIN, GPIO.LOW)).start()

def door_callback(channel):
    """Callback pre dverový kontakt."""
    global last_door_time, last_door_state
    
    current_time = time.time()
    if current_time - last_door_time > DEBOUNCE_TIME:
        last_door_time = current_time
        current_state = GPIO.input(DOOR_PIN) == GPIO.LOW  # Invertovaná logika s pull-up
        
        if current_state != last_door_state:
            last_door_state = current_state
            publish_sensor_status("door", current_state)

def window_callback(channel):
    """Callback pre okenný kontakt."""
    global last_window_time, last_window_state
    
    current_time = time.time()
    if current_time - last_window_time > DEBOUNCE_TIME:
        last_window_time = current_time
        current_state = GPIO.input(WINDOW_PIN) == GPIO.LOW  # Invertovaná logika s pull-up
        
        if current_state != last_window_state:
            last_window_state = current_state
            publish_sensor_status("window", current_state)

def publish_sensor_status(sensor_type, state):
    """Publikuje stav konkrétneho senzora cez MQTT."""
    if not mqtt_client or not mqtt_connected:
        return False
    
    try:
        # Convert boolean state to expected string formats
        state_value = ""
        if sensor_type == "motion":
            state_value = "DETECTED" if state else "IDLE"
        elif sensor_type in ["door", "window"]:
            state_value = "OPEN" if state else "CLOSED"
        
        # Create payload with correct format
        payload = {
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "room": DEVICE_NAME,
            sensor_type: state_value,  # Use sensor_type as key with state_value string
            "timestamp": time.time()
        }
        
        result = mqtt_client.publish(
            MQTT_TOPIC_SENSOR,
            json.dumps(payload),
            qos=MQTT_QOS
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Sensor {SENSOR_LABELS.get(sensor_type, sensor_type)}: {state_value}")
            return True
        else:
            print(f"Chyba pri publikovaní stavu senzora: {result.rc}")
            return False
    except Exception as e:
        print(f"Chyba pri publikovaní stavu senzora: {e}")
        return False

def send_all_sensors_status():
    """Odošle aktuálny stav všetkých senzorov."""
    # Čítanie aktuálneho stavu senzorov - s pull-up rezistormi, LOW znamená aktivný senzor
    motion_state = GPIO.input(MOTION_PIN) == GPIO.LOW  # True ak je senzor aktivovaný (pin je LOW)
    door_state = GPIO.input(DOOR_PIN) == GPIO.LOW
    window_state = GPIO.input(WINDOW_PIN) == GPIO.LOW
    
    # Publikovanie stavu každého senzora
    publish_sensor_status("motion", motion_state)
    publish_sensor_status("door", door_state)
    publish_sensor_status("window", window_state)

def capture_and_send_image():
    """Zachytí snímok z kamery a odošle ho cez MQTT."""
    if camera is None:
        print("Kamera nie je dostupná")
        return
    
    try:
        # Indikácia začiatku snímania LED
        GPIO.output(LED_PIN, GPIO.HIGH)
        
        # Zachytenie snímky do in-memory súboru
        camera.start()
        time.sleep(0.5)  # Krátka pauza na stabilizáciu kamery
        
        # Vytvorenie in-memory súboru pre obrázok
        stream = io.BytesIO()
        
        # Zachytenie snímky do súboru
        camera.capture_file(stream, format='jpeg')
        camera.stop()
        
        # Získanie dát zo streamu
        stream.seek(0)
        image_data = stream.getvalue()
        
        # Kódovanie obrázku do base64
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # Príprava payload s metadátami
        payload = {
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "room": DEVICE_NAME,
            "timestamp": time.time(),
            "format": "jpeg",
            "encoding": "base64",
            "image": base64_data
        }
        
        # Publikovanie správy s obrázkom
        if mqtt_connected:
            print("Odosielam zachytený obrázok...")
            result = mqtt_client.publish(
                MQTT_TOPIC_IMAGE,
                json.dumps(payload),
                qos=MQTT_QOS
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Obrázok úspešne odoslaný, veľkosť: {len(base64_data)} B")
            else:
                print(f"Chyba pri odosielaní obrázku: {result.rc}")
        
    except Exception as e:
        print(f"Chyba pri zachytávaní alebo odosielaní obrázku: {e}")
    finally:
        # Vypnutie LED indikátora
        GPIO.output(LED_PIN, GPIO.LOW)

def cleanup():
    """Vykoná čistiace operácie pred ukončením programu."""
    print("Čistenie zdrojov...")
    
    # Ukončenie MQTT
    if mqtt_connected and mqtt_client is not None:
        try:
            publish_mqtt_status("OFFLINE", "Program ukončený")
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        except:
            pass
    
    # Uvoľnenie GPIO
    try:
        GPIO.cleanup()
    except:
        pass
    
    # Uvoľnenie kamery - PiCamera2 nemá metódu close(), stačí zastaviť kameru
    if camera is not None:
        try:
            if camera.started:
                camera.stop()
        except:
            pass

def main():
    """Hlavná funkcia programu."""
    print("=== PROGRAM PRE RASPBERRY PI - FYZICKÉ SENZORY A KAMERA ===")
    
    try:
        # Načítanie konfigurácie
        load_config()
        
        # Nastavenie GPIO - presunute hore pred find_mqtt_broker
        setup_gpio()
        
        # Inicializácia kamery - presunute hore, aby bola kamera dostupna skorej
        setup_camera()
        
        # Automatické vyhľadanie MQTT brokera
        find_mqtt_broker()
        
        # Nastavenie MQTT po zistení brokera
        setup_mqtt()
        
        # Spustenie vlákna monitorovania MQTT
        threading.Thread(target=mqtt_monitor, daemon=True, name="MQTTMonitorThread").start()
        
        # Čítanie počiatočného stavu senzorov
        last_motion_state = GPIO.input(MOTION_PIN) == GPIO.LOW
        last_door_state = GPIO.input(DOOR_PIN) == GPIO.LOW
        last_window_state = GPIO.input(WINDOW_PIN) == GPIO.LOW
        
        # Odoslanie počiatočného stavu
        publish_mqtt_status("ONLINE", "Program spustený")
        
        # Nekonečná slučka pre udržanie programu v behu
        print("Program beží. Stlačte Ctrl+C pre ukončenie.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nUkončujem program...")
    except Exception as e:
        print(f"Kritická chyba: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
