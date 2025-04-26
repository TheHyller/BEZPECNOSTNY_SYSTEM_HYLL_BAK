# app.py - Hlavná trieda KivyMD aplikácie
from kivymd.app import MDApp
from login_screen import LoginScreen
from dashboard_screen import DashboardScreen
from alerts_screen import AlertsScreen
from settings_screen import SettingsScreen
from sensor_screen import SensorScreen
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
import threading
import asyncio
import subprocess
import os
import time
import socket
from web_app import app as flask_app
from config.system_state import load_state, save_state, is_locked_out, set_lockout, update_state
from config.settings import load_settings
from mqtt_client import mqtt_client
import notification_service as ns
# Importovanie MQTT discovery služby
from mqtt_discovery import MQTTDiscoveryService
import logging
import sys

# Nastavenie pre vstavený MQTT broker
broker_config = {
    'host': '0.0.0.0',
    'port': 1883,
}

# Konfigurácia logovania
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s"
)

# Cesty k možným inštaláciám mosquitto
MOSQUITTO_PATHS = [
    "mosquitto",  # Ak je v PATH
    "C:\\Program Files\\mosquitto\\mosquitto.exe",
    "C:\\mosquitto\\mosquitto.exe",
    "/usr/sbin/mosquitto",
    "/usr/bin/mosquitto",
    "/usr/local/bin/mosquitto"
]

class SecurityApp(MDApp):
    def build(self):
        self.title = "Domáci bezpečnostný systém"
        self.sm = ScreenManager()
        
        # Nastavenie témy aplikácie - výraznejšie farby pre lepšiu viditeľnosť
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_hue = "700"  # Tmavší odtieň modrej pre lepšiu viditeľnosť
        
        try:
            # Pokus o načítanie KV súborov
            Builder.load_file('login_screen.kv')
            Builder.load_file('dashboard_screen.kv')
            Builder.load_file('sensor_screen.kv')
            Builder.load_file('settings_screen.kv')
            Builder.load_file('alerts_screen.kv')  # Načítanie nového KV súboru pre obrazovku upozornení
            
            # Pridanie obrazoviek do ScreenManager s menami
            self.sm.add_widget(LoginScreen(name='login'))
            self.sm.add_widget(DashboardScreen(name='dashboard'))
            self.sm.add_widget(SensorScreen(name='sensors'))
            self.sm.add_widget(AlertsScreen(name='alerts'))
            self.sm.add_widget(SettingsScreen(name='settings'))
            
            # Inicializácia stavu alarmu v systéme
            update_state({"alarm_active": False, "armed_mode": "disarmed"})
            
            # Spustenie monitorovania senzorov pre alarmy
            ns.start_sensor_monitoring()
            
            # Výslovné nastavenie počiatočnej obrazovky
            self.sm.current = 'dashboard'  # alebo 'login' podľa potreby
            
        except Exception as e:
            logging.error(f"Chyba pri načítavaní aplikácie: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        return self.sm
        
    def on_stop(self):
        """Čistenie pri ukončení aplikácie."""
        try:
            # Zastavenie monitorovania senzorov
            ns.stop_sensor_monitoring()
            
            # Ak je alarm aktívny, vypneme ho
            if ns.is_alarm_active():
                ns.stop_alarm()
            
            # Zastavenie MQTT klienta
            mqtt_client.stop()
            
        except Exception as e:
            logging.error(f"Chyba pri ukončovaní aplikácie: {e}")

def run_flask():
    try:
        # Použitie threaded=True parametra, aby Flask mohol správne obsluhovať viacero požiadaviek
        # a zmena debug=False, aby sa zabránilo problémom s opätovným spúšťaním vlákna
        flask_app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
    except Exception as e:
        logging.error(f"Chyba pri spúšťaní Flask aplikácie: {e}")

def find_mosquitto_path():
    """Nájde cestu k spustiteľnému súboru Mosquitto"""
    for path in MOSQUITTO_PATHS:
        try:
            # Skúsime spustiť mosquitto s parametrom -h pre overenie verzie a potom ihneď ukončíme
            subprocess.run([path, "-h"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          timeout=1, 
                          check=False)
            print(f"Nájdený Mosquitto na: {path}")
            return path
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    
    print("VAROVANIE: Mosquitto nenájdený v žiadnej štandardnej ceste. Skúste ho nainštalovať.")
    return None

def check_mosquitto_installation():
    """Skontroluje, či je Mosquitto nainštalovaný a vráti cestu k nemu."""
    mosquitto_path = find_mosquitto_path()
    if not mosquitto_path:
        print("Mosquitto nie je nainštalovaný alebo nie je v PATH.")
        print("Prosím, nainštalujte Mosquitto MQTT broker:")
        if sys.platform.startswith('win'):
            print("Windows: Stiahnite inštalátor z https://mosquitto.org/download/ a nainštalujte")
        elif sys.platform.startswith('linux'):
            print("Linux: sudo apt-get install mosquitto")
        elif sys.platform.startswith('darwin'):
            print("macOS: brew install mosquitto")
        else:
            print("Navštívte https://mosquitto.org/download/ pre inštrukcie")
        
    return mosquitto_path

def create_config_file():
    """Vytvorí konfiguračný súbor pre Mosquitto"""
    try:
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/mqtt')
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, 'mosquitto.conf')
        
        # Rozšírená konfigurácia pre Mosquitto
        config_content = """# Konfigurácia Mosquitto pre Domáci bezpečnostný systém
listener 1883
allow_anonymous true
persistence true
persistence_location ../data/mqtt/
log_dest file ../data/mqtt/mosquitto.log
log_type all
connection_messages true
log_timestamp true
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        print(f"Vytvorený konfiguračný súbor: {config_path}")
        return config_path
    except Exception as e:
        logging.error(f"Chyba pri vytváraní konfiguračného súboru: {e}")
        return None

def is_port_in_use(port):
    """Skontroluje, či je port už používaný"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    except Exception as e:
        logging.error(f"Chyba pri kontrole portu {port}: {e}")
        return False

def run_mqtt_broker():
    """Spustí MQTT broker ako externý proces"""
    # Kontrola, či je port 1883 voľný
    if is_port_in_use(1883):
        print("VAROVANIE: Port 1883 je už používaný. MQTT broker možno už beží.")
        # Napriek tomu pokračujeme, aby sme mohli spustiť discovery službu
    
    # Získanie cesty k Mosquitto
    mosquitto_path = check_mosquitto_installation()
    if not mosquitto_path:
        print("MQTT broker nemohol byť spustený, pokračujem bez neho.")
        return
    
    # Vytvorenie konfiguračného súboru
    config_path = create_config_file()
    if not config_path:
        print("Nepodarilo sa vytvoriť konfiguračný súbor, pokračujem bez MQTT brokera.")
        return
    
    # Spustenie Mosquitto ako subprocess
    try:
        # Použijeme parameter -c pre konfiguračný súbor a -v pre verbose výstup
        process = subprocess.Popen(
            [mosquitto_path, "-c", config_path, "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"MQTT broker spustený (PID: {process.pid})")
        
        # Čakáme krátko, aby sa broker stihol inicializovať
        time.sleep(2)
        
        # Získanie lokálnej IP adresy pre discovery službu
        local_ip = get_local_ip()
        
        # Spustenie MQTT discovery služby
        try:
            discovery = MQTTDiscoveryService(broker_ip=local_ip, broker_port=1883)
            discovery.start_broadcast()
            print("MQTT discovery služba spustená - zariadenia teraz môžu automaticky nájsť broker")
        except Exception as e:
            logging.error(f"Chyba pri spúšťaní MQTT discovery služby: {e}")
        
        # Čítame a vypisujeme výstup z Mosquitto
        while True:
            output = process.stdout.readline()
            if output:
                print(f"MQTT broker: {output.strip()}")
            
            # Ak proces skončil, ukončíme slučku
            if process.poll() is not None:
                print("MQTT broker sa neočakávane ukončil")
                break
                
    except Exception as e:
        print(f"Chyba pri spúšťaní MQTT brokera: {e}")

def get_local_ip():
    """Získa lokálnu IP adresu zariadenia."""
    try:
        # Vytvorenie socket pripojenia na verejný DNS server
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Chyba pri získavaní lokálnej IP: {e}")
        return "127.0.0.1"

if __name__ == "__main__":
    try:
        # Spustenie MQTT brokera v samostatnom vlákne
        threading.Thread(target=run_mqtt_broker, daemon=True, name="MQTTBrokerThread").start()
        
        # Spustenie Flask aplikácie v samostatnom vlákne
        threading.Thread(target=run_flask, daemon=True, name="FlaskThread").start()
        
        # Spustenie MQTT klienta po spustení brokera (krátke oneskorenie pre istotu)
        threading.Timer(2.0, mqtt_client.start).start()
        
        # Spustenie hlavnej aplikácie
        SecurityApp().run()
    except Exception as e:
        logging.error(f"Kritická chyba pri spúšťaní aplikácie: {e}")
        import traceback
        traceback.print_exc()
