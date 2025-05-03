#!/usr/bin/env python3
# SEND.py - Program pre Raspberry Pi pre fyzické senzory
import json
import threading
import time
import os
import socket
import RPi.GPIO as GPIO
import libcamera
import subprocess
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
mqtt_broker = DEFAULT_MQTT_BROKER

# Časovač pre zachytenie fotografie
last_photo_time = 0
PHOTO_COOLDOWN = 2  # 2 sekundy cooldown medzi zachytením fotografií

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
STATUS_INTERVAL = 30
DEBOUNCE_TIME = 0.1
MQTT_RECONNECT_INTERVAL = 5
DISCOVERY_RETRY_INTERVAL = 60

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
                
                if 'mqtt' in config:
                    mqtt_config = config['mqtt']
                    DEFAULT_MQTT_BROKER = mqtt_config.get('broker', DEFAULT_MQTT_BROKER)
                    MQTT_PORT = mqtt_config.get('port', MQTT_PORT)
                    MQTT_USERNAME = mqtt_config.get('username', MQTT_USERNAME)
                    MQTT_PASSWORD = mqtt_config.get('password', MQTT_PASSWORD)
                
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
        
        start_time = time.time()
        discovery_timeout = 10
        
        while time.time() - start_time < discovery_timeout:
            try:
                data, addr = sock.recvfrom(1024)
                print(f"Prijatá odpoveď od {addr}")
                
                message = json.loads(data.decode("utf-8"))
                
                if message.get("type") == "mqtt_discovery" or message.get("type") == "mqtt_discovery_response":
                    discovered_broker = message.get("broker_ip")
                    discovered_port = message.get("broker_port", MQTT_PORT)
                    
                    if discovered_broker:
                        print(f"Nájdený MQTT broker: {discovered_broker}:{discovered_port}")
                        
                        mqtt_broker = discovered_broker
                        MQTT_PORT = discovered_port
                        
                        for _ in range(3):
                            GPIO.output(LED_PIN, GPIO.HIGH)
                            time.sleep(0.1)
                            GPIO.output(LED_PIN, GPIO.LOW)
                            time.sleep(0.1)
                            
                        return True
            except socket.timeout:
                continue
            except json.JSONDecodeError as e:
                print(f"Prijatá neplatná JSON odpoveď: {e}")
                continue
            except Exception as e:
                print(f"Chyba pri spracovaní odpovede: {e}")
                continue
                
            time.sleep(0.1)
            
    except socket.error as e:
        print(f"Socket chyba pri vyhľadávaní MQTT brokera: {e}")
    except Exception as e:
        print(f"Všeobecná chyba pri hľadaní MQTT brokera: {e}")
    finally:
        sock.close()
        
    print(f"Použijem predvolenú adresu MQTT brokera: {DEFAULT_MQTT_BROKER}")
    mqtt_broker = DEFAULT_MQTT_BROKER
    
    GPIO.output(LED_PIN, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(LED_PIN, GPIO.LOW)
    
    return False

def setup_gpio():
    """Nastavenie GPIO pinov."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    GPIO.setup(MOTION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(DOOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(WINDOW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.LOW)
    
    GPIO.add_event_detect(MOTION_PIN, GPIO.BOTH, callback=motion_callback, bouncetime=200)
    GPIO.add_event_detect(DOOR_PIN, GPIO.BOTH, callback=door_callback, bouncetime=200)
    GPIO.add_event_detect(WINDOW_PIN, GPIO.BOTH, callback=window_callback, bouncetime=200)

def setup_camera():
    """Inicializácia kamery."""
    global camera
    
    try:
        subprocess.run(["libcamera-still", "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        print(f"Kamera inicializovaná - rozlíšenie: {camera_resolution}, rotácia: {camera_rotation}°")
        
        print(f"Zahriatie kamery ({camera_warmup_time}s)...")
        time.sleep(camera_warmup_time)
        
        camera = {"resolution": camera_resolution, "rotation": camera_rotation}
        
    except Exception as e:
        print(f"Chyba pri inicializácii kamery: {e}")
        camera = None

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback pri pripojení k MQTT brokeru."""
    global mqtt_connected
    
    if rc == 0:
        mqtt_connected = True
        print(f"Pripojený k MQTT brokeru ({mqtt_broker}:{MQTT_PORT})")
        
        client.subscribe(MQTT_TOPIC_CONTROL, qos=MQTT_QOS)
        
        publish_mqtt_status("ONLINE")
        
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
        send_all_sensors_status()
    elif command == 'capture':
        threading.Thread(target=capture_and_send_image).start()
    elif command == 'restart':
        print("Prijatý príkaz na reštart programu")
    elif command == 'identify':
        print("Zariadenie identifikované")
        for _ in range(10):
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(0.2)
    elif command == 'discover':
        print("Prijatý príkaz na vyhľadanie MQTT brokera")
        if find_mqtt_broker():
            if mqtt_client:
                mqtt_client.disconnect()
                setup_mqtt()

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
        "room": DEVICE_NAME,
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
        
        if message:
            payload["message"] = message
            
        result = mqtt_client.publish(
            MQTT_TOPIC_STATUS, 
            json.dumps(payload), 
            qos=MQTT_QOS,
            retain=True
        )
        
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
    global last_motion_time, last_motion_state, last_photo_time
    
    current_time = time.time()
    if current_time - last_motion_time > DEBOUNCE_TIME:
        last_motion_time = current_time
        current_state = GPIO.input(MOTION_PIN) == GPIO.HIGH
        
        if current_state != last_motion_state:
            last_motion_state = current_state
            publish_sensor_status("motion", current_state)
            
            if current_state:
                GPIO.output(LED_PIN, GPIO.HIGH)
                threading.Timer(0.5, lambda: GPIO.output(LED_PIN, GPIO.LOW)).start()
                
                if current_time - last_photo_time > PHOTO_COOLDOWN:
                    last_photo_time = current_time
                    print(f"Pohyb detegovaný - zachytávam snímku (cooldown: {PHOTO_COOLDOWN}s)...")
                    threading.Thread(target=capture_and_send_image).start()
                else:
                    print(f"Pohyb detegovaný - ignorujem fotografovanie (cooldown ešte neuplynul, zostáva {PHOTO_COOLDOWN - (current_time - last_photo_time):.1f}s)")

def door_callback(channel):
    """Callback pre dverový kontakt."""
    global last_door_time, last_door_state
    
    current_time = time.time()
    if current_time - last_door_time > DEBOUNCE_TIME:
        last_door_time = current_time
        current_state = GPIO.input(DOOR_PIN) == GPIO.HIGH
        
        if current_state != last_door_state:
            last_door_state = current_state
            publish_sensor_status("door", current_state)

def window_callback(channel):
    """Callback pre okenný kontakt."""
    global last_window_time, last_window_state
    
    current_time = time.time()
    if current_time - last_window_time > DEBOUNCE_TIME:
        last_window_time = current_time
        current_state = GPIO.input(WINDOW_PIN) == GPIO.HIGH
        
        if current_state != last_window_state:
            last_window_state = current_state
            publish_sensor_status("window", current_state)

def publish_sensor_status(sensor_type, state):
    """Publikuje stav konkrétneho senzora cez MQTT."""
    if not mqtt_client or not mqtt_connected:
        return False
    
    try:
        state_value = ""
        if sensor_type == "motion":
            state_value = "DETECTED" if state else "IDLE"
        elif sensor_type in ["door", "window"]:
            state_value = "OPEN" if state else "CLOSED"
        
        payload = {
            "device_id": DEVICE_ID,
            "device_name": DEVICE_NAME,
            "room": DEVICE_NAME,
            sensor_type: state_value,
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
    motion_state = GPIO.input(MOTION_PIN) == GPIO.HIGH
    door_state = GPIO.input(DOOR_PIN) == GPIO.HIGH
    window_state = GPIO.input(WINDOW_PIN) == GPIO.HIGH
    
    publish_sensor_status("motion", motion_state)
    publish_sensor_status("door", door_state)
    publish_sensor_status("window", window_state)

def capture_and_send_image():
    """Zachytí snímok z kamery a odošle ho cez MQTT."""
    if camera is None:
        print("Kamera nie je dostupná")
        return
    
    try:
        GPIO.output(LED_PIN, GPIO.HIGH)
        
        temp_image_path = os.path.join(os.path.dirname(__file__), "temp_capture.jpg")
        
        width, height = camera["resolution"]
        rotation = camera["rotation"]
        
        cmd = [
            "libcamera-still",
            "--width", str(width),
            "--height", str(height), 
            "--rotation", str(rotation),
            "--nopreview",
            "--output", temp_image_path,
            "--immediate"
        ]
        
        print("Zachytávam snímku pomocou libcamera-still...")
        subprocess.run(cmd, check=True)
        
        with open(temp_image_path, "rb") as f:
            image_data = f.read()
            
        try:
            os.remove(temp_image_path)
        except:
            pass
        
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            "image_data": base64_data,
            "metadata": {
                "device_id": DEVICE_ID,
                "device_name": DEVICE_NAME,
                "room": DEVICE_NAME,
                "timestamp": time.time(),
                "format": "jpeg",
                "trigger": "motion"
            }
        }
        
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
        GPIO.output(LED_PIN, GPIO.LOW)

def cleanup():
    """Vykoná čistiace operácie pred ukončením programu."""
    print("Čistenie zdrojov...")
    
    if mqtt_connected and mqtt_client is not None:
        try:
            publish_mqtt_status("OFFLINE", "Program ukončený")
            mqtt_client.disconnect()
            mqtt_client.loop_stop()
        except:
            pass
    
    try:
        GPIO.cleanup()
    except:
        pass
    
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
        load_config()
        
        setup_gpio()
        
        setup_camera()
        
        find_mqtt_broker()
        
        setup_mqtt()
        
        threading.Thread(target=mqtt_monitor, daemon=True, name="MQTTMonitorThread").start()
        
        last_motion_state = GPIO.input(MOTION_PIN) == GPIO.LOW
        last_door_state = GPIO.input(DOOR_PIN) == GPIO.LOW
        last_window_state = GPIO.input(WINDOW_PIN) == GPIO.LOW
        
        publish_mqtt_status("ONLINE", "Program spustený")
        
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
