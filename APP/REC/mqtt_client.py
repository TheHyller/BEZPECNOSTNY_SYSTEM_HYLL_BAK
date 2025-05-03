# mqtt_client.py - MQTT klient pre prijímač
import json
import os
import threading
import time
import random
import math
from datetime import datetime
import paho.mqtt.client as mqtt
from config.system_state import update_state
from config.devices_manager import update_device_status
import base64

class MQTTClient:
    def __init__(self):
        self.client = None
        self.connected = False
        self.config = self._load_config()
        self.reconnect_attempt = 0
        self.callbacks = {
            "on_sensor_message": [],
            "on_image_message": [],
            "on_status_message": [],
            "on_message": []
        }
        
    def _load_config(self):
        """Načíta konfiguráciu MQTT z JSON súboru."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '../data/mqtt_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Chyba pri načítaní MQTT konfigurácie: {e}")
            return {
                "broker": "localhost",
                "port": 1883,
                "username": "",
                "password": "",
                "client_id_prefix": "home_security_",
                "topics": {
                    "sensor": "home/security/sensors",
                    "image": "home/security/images",
                    "control": "home/security/control",
                    "status": "home/security/status"
                },
                "use_tls": False,
                "qos": 1,
                "reconnect_delay": 5,
                "clean_session": True,
                "keep_alive_interval": 60,
                "last_will": {
                    "enabled": False,
                    "topic": "home/security/status/receiver",
                    "message": "OFFLINE",
                    "qos": 1,
                    "retain": True
                },
                "reconnect_settings": {
                    "max_retries": 10,
                    "base_delay": 5,
                    "max_delay": 120,
                    "use_exponential_backoff": True
                },
                "client_id_settings": {
                    "use_random_suffix": True,
                    "persistent_storage": False,
                    "storage_path": "../data/mqtt_client_id.txt"
                }
            }
    
    def _generate_client_id(self):
        """Generuje ID klienta podľa nakonfigurovaných nastavení."""
        client_id_settings = self.config.get('client_id_settings', {})
        prefix = self.config.get('client_id_prefix', 'home_security_')
        
        if client_id_settings.get('persistent_storage', False):
            storage_path = os.path.join(os.path.dirname(__file__), 
                                       client_id_settings.get('storage_path', '../data/mqtt_client_id.txt'))
            try:
                if os.path.exists(storage_path):
                    with open(storage_path, 'r') as f:
                        client_id = f.read().strip()
                        if client_id:
                            return client_id
            except Exception as e:
                print(f"Chyba pri načítaní ID klienta: {e}")
        
        if client_id_settings.get('use_random_suffix', True):
            random_suffix = ''.join(random.choices('0123456789abcdef', k=8))
            timestamp = int(time.time())
            client_id = f"{prefix}receiver_{random_suffix}_{timestamp}"
        else:
            client_id = f"{prefix}receiver_{int(time.time())}"
        
        if client_id_settings.get('persistent_storage', False):
            try:
                storage_dir = os.path.dirname(storage_path)
                if not os.path.exists(storage_dir):
                    os.makedirs(storage_dir)
                with open(storage_path, 'w') as f:
                    f.write(client_id)
            except Exception as e:
                print(f"Chyba pri ukladaní ID klienta: {e}")
        
        return client_id
    
    def _calculate_reconnect_delay(self):
        """Vypočíta oneskorenie pre opätovné pripojenie pomocou exponenciálneho backoffu."""
        reconnect_settings = self.config.get('reconnect_settings', {})
        base_delay = reconnect_settings.get('base_delay', 5)
        max_delay = reconnect_settings.get('max_delay', 120)
        
        if reconnect_settings.get('use_exponential_backoff', True):
            delay = min(base_delay * (2 ** self.reconnect_attempt), max_delay)
            delay = delay * (0.8 + 0.4 * random.random())
        else:
            delay = min(base_delay * self.reconnect_attempt, max_delay)
            if delay < base_delay:
                delay = base_delay
                
        return delay
    
    def start(self):
        """Spustí MQTT klienta v samostatnom vlákne."""
        if self.client is not None:
            print("MQTT klient už beží")
            return
        
        client_id = self._generate_client_id()
        clean_session = self.config.get('clean_session', True)
        
        self.client = mqtt.Client(client_id=client_id, clean_session=clean_session)
        
        if self.config.get('username') and self.config.get('password'):
            self.client.username_pw_set(self.config['username'], self.config['password'])
        
        if self.config.get('use_tls', False):
            self.client.tls_set()
        
        last_will = self.config.get('last_will', {})
        if last_will.get('enabled', False):
            lwt_topic = last_will.get('topic', f"{self.config['topics']['status']}/receiver")
            lwt_msg = last_will.get('message', 'OFFLINE')
            if isinstance(lwt_msg, dict):
                lwt_msg = json.dumps({
                    **lwt_msg,
                    "timestamp": datetime.now().isoformat()
                })
            lwt_qos = last_will.get('qos', self.config.get('qos', 1))
            lwt_retain = last_will.get('retain', True)
            
            self.client.will_set(lwt_topic, lwt_msg, qos=lwt_qos, retain=lwt_retain)
            print(f"Nastavená Last Will správa na téme {lwt_topic}")
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        threading.Thread(target=self._connect_and_loop, daemon=True, 
                         name="MQTTClientThread").start()
        print(f"MQTT klient spustený s ID: {client_id}, clean session: {clean_session}")
    
    def _connect_and_loop(self):
        """Pripojí sa k brokeru a spustí smyčku MQTT klienta."""
        reconnect_settings = self.config.get('reconnect_settings', {})
        max_retries = reconnect_settings.get('max_retries', 0)
        self.reconnect_attempt = 0
        
        while True:
            if max_retries > 0 and self.reconnect_attempt >= max_retries:
                print(f"Dosiahnutý maximálny počet pokusov o pripojenie ({max_retries}). Ukončujem...")
                break
                
            try:
                keep_alive = self.config.get('keep_alive_interval', 60)
                print(f"Pripájam sa k MQTT brokeru {self.config['broker']}:{self.config['port']} "
                      f"(pokus č. {self.reconnect_attempt + 1}, keep-alive: {keep_alive}s)...")
                
                self.client.connect(self.config['broker'], self.config['port'], keepalive=keep_alive)
                self.reconnect_attempt = 0
                self.client.loop_forever()
            except Exception as e:
                print(f"Chyba MQTT pripojenia: {e}")
                self.connected = False
                
                self.reconnect_attempt += 1
                delay = self._calculate_reconnect_delay()
                
                print(f"Pokus o opätovné pripojenie za {delay:.1f} sekúnd... "
                      f"(pokus {self.reconnect_attempt}{' z ' + str(max_retries) if max_retries > 0 else ''})")
                time.sleep(delay)
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback pri úspešnom pripojení k brokeru."""
        if rc == 0:
            self.connected = True
            print(f"Úspešne pripojený k MQTT brokeru ({self.config['broker']})")
            
            for topic_type, topic in self.config['topics'].items():
                client.subscribe(f"{topic}/#", qos=self.config.get('qos', 1))
                print(f"Prihlásený na téme: {topic}/#")
            
            self.publish_status("ONLINE", "Prijímač je pripravený")
        else:
            print(f"Neúspešné pripojenie k MQTT brokeru, kód: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback pri odpojení od brokera."""
        self.connected = False
        if rc != 0:
            print(f"Neočakávané odpojenie od MQTT brokera, kód: {rc}")
        else:
            print("Odpojený od MQTT brokera")
    
    def _on_message(self, client, userdata, message):
        """Spracuje prichádzajúcu MQTT správu."""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            topic_base = topic.split('/')[0:3]
            topic_base = '/'.join(topic_base)
            
            try:
                payload_data = json.loads(payload)
            except json.JSONDecodeError:
                payload_data = {"raw": payload}
                
            for callback in self.callbacks.get("on_message", []):
                callback(topic, payload_data)
                
            if topic_base == self.config['topics']['sensor']:
                self._process_sensor_message(topic, payload_data)
            elif topic_base == self.config['topics']['image']:
                self._process_image_message(topic, payload_data)
            elif topic_base == self.config['topics']['status']:
                self._process_status_message(topic, payload_data)
            else:
                print(f"Prijatá správa na neznámej téme: {topic}")
        except Exception as e:
            print(f"Chyba pri spracovaní MQTT správy: {e}")
    
    def _process_sensor_message(self, topic, payload):
        """Spracuje správu zo senzora."""
        try:
            device_id = topic.split('/')[-1]
            data = payload
            
            print(f"Prijatá správa zo senzora {device_id}: {data}")
            
            device_status = {}
            if device_id not in device_status:
                device_status[device_id] = {}
            
            for sensor_type, status in data.items():
                if sensor_type in ['motion', 'door', 'window']:
                    device_status[device_id][sensor_type] = status
            
            update_device_status(device_status)
            
            if any(status == 'DETECTED' for status in data.values()) or \
               any(status == 'OPEN' for status in data.values()):
                update_state("alert", True)
            
            for callback in self.callbacks["on_sensor_message"]:
                callback(device_id, data)
                
        except Exception as e:
            print(f"Chyba pri spracovaní správy zo senzora: {e}")
    
    def _process_image_message(self, topic, payload):
        """Spracuje správu s obrázkom."""
        try:
            device_id = topic.split('/')[-1]
            data = payload
            
            print(f"Prijatá správa s obrázkom od zariadenia {device_id}")
            
            if 'image_data' in data and 'metadata' in data:
                image_data = base64.b64decode(data['image_data'])
                metadata = data['metadata']
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_dir = os.path.join(os.path.dirname(__file__), '../data/images')
                os.makedirs(image_dir, exist_ok=True)
                
                image_path = os.path.join(image_dir, f"{device_id}_{timestamp}.jpg")
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                
                print(f"Obrázok uložený: {image_path}")
                
                for callback in self.callbacks["on_image_message"]:
                    callback(device_id, image_path, metadata)
        except Exception as e:
            print(f"Chyba pri spracovaní správy s obrázkom: {e}")
    
    def _process_status_message(self, topic, payload):
        """Spracuje správu o stave zariadenia."""
        try:
            device_id = topic.split('/')[-1]
            data = payload
            
            print(f"Prijatý stav zariadenia {device_id}: {data}")
            
            for callback in self.callbacks["on_status_message"]:
                callback(device_id, data)
                
            if isinstance(data, dict) and data.get('status') == 'DISCOVER':
                print(f"Prijatá požiadavka na discovery od {device_id}")
                self.publish_control_message(device_id, "DISCOVERY_RESPONSE", {
                    "system_id": "SECURITY_SYSTEM",
                    "status": "ONLINE",
                    "broker_ip": self.config['broker']
                })
        except Exception as e:
            print(f"Chyba pri spracovaní správy o stave: {e}")
    
    def start_discovery_service(self):
        """Spustí službu pre detekciu nových zariadení cez MQTT."""
        if not self.connected:
            print("MQTT klient nie je pripojený, nemôžem spustiť službu detekcie zariadení")
            return
            
        discovery_topic = f"{self.config['topics']['status']}/discovery"
        self.client.subscribe(discovery_topic, qos=self.config.get('qos', 1))
        print(f"Spustená služba detekcie zariadení, počúvam na téme {discovery_topic}")
        
        self.publish_status("ONLINE", "Prijímač je pripravený na detekciu zariadení")
    
    def publish_control_message(self, target_device, command, data=None):
        """Publikuje riadiacu správu pre konkrétne zariadenie."""
        if not self.connected:
            print("MQTT klient nie je pripojený")
            return False
        
        if data is None:
            data = {}
            
        payload = {
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        topic = f"{self.config['topics']['control']}/{target_device}"
        return self.client.publish(
            topic, 
            json.dumps(payload), 
            qos=self.config.get('qos', 1)
        )
    
    def publish_status(self, status, message=""):
        """Publikuje stav prijímača."""
        if not self.connected:
            print("MQTT klient nie je pripojený")
            return False
            
        payload = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        topic = f"{self.config['topics']['status']}/receiver"
        return self.client.publish(
            topic, 
            json.dumps(payload), 
            qos=self.config.get('qos', 1)
        )
    
    def register_callback(self, event_type, callback):
        """Registruje callback funkciu pre určitý typ udalosti."""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            return True
        return False
    
    def on_message(self, callback):
        """Dekorátor pre jednoduchú registráciu callback funkcie pre všetky správy."""
        if "on_message" not in self.callbacks:
            self.callbacks["on_message"] = []
        self.callbacks["on_message"].append(callback)
        return callback
    
    def stop(self):
        """Zastaví MQTT klienta."""
        if self.client and self.connected:
            print("Zastavujem MQTT klienta...")
            self.publish_status("OFFLINE", "Prijímač sa vypína")
            self.client.disconnect()
            self.client.loop_stop()
            self.client = None
            self.connected = False
            print("MQTT klient zastavený")

# Singleton inštancia
mqtt_client = MQTTClient()