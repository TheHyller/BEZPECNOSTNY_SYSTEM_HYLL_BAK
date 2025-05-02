# main.py - Inicializácia aplikácie a listenerov
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.config import Config

# Nastavenie konfigurácie pred importom ostatných Kivy modulov
Config.set('kivy', 'exit_on_escape', '1')  # Umožní ukončenie na Escape
Config.set('graphics', 'multisamples', '0')  # Oprava pre niektoré OpenGL problémy
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')  # Lepšia podpora myši

import threading
import time
import json
import os
import traceback

try:
    # Import KivyMD - must be before our custom screens
    from kivymd.app import MDApp
    from kivymd.theming import ThemeManager
    
    from dashboard_screen import DashboardScreen
    from sensor_screen import SensorScreen
    from alerts_screen import AlertsScreen
    from settings_screen import SettingsScreen
    from login_screen import LoginScreen
    from mqtt_client import mqtt_client
    import notification_service as ns
    from config.system_state import update_state, load_state
except Exception as e:
    # Log import errors for debugging
    print(f"CRITICAL IMPORT ERROR: {e}")
    traceback.print_exc()
    # We'll continue to try to initialize what we can

# Nastavenie cesty k súborom
os.environ['KIVY_HOME'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.kivy'))

class MainApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set theme colors for KivyMD
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = "Light"
        
    def build(self):
        self.title = 'Domáci bezpečnostný systém'
        
        try:
            # Vytvorenie správcu obrazoviek
            self.sm = ScreenManager()
            
            # Pridanie obrazoviek
            self.sm.add_widget(LoginScreen(name='login'))
            self.sm.add_widget(DashboardScreen(name='dashboard'))
            self.sm.add_widget(SensorScreen(name='sensors'))
            self.sm.add_widget(AlertsScreen(name='alerts'))
            self.sm.add_widget(SettingsScreen(name='settings'))
            
            # Explicitly set the current screen to login
            self.sm.current = 'login'
            
            # Set up app initialization in a separate thread to avoid UI freezing
            Clock.schedule_once(self.delayed_initialization, 1)
            
            return self.sm
        except Exception as e:
            print(f"ERROR BUILDING APP: {e}")
            traceback.print_exc()
            # Return a minimal screen to avoid crash
            from kivy.uix.label import Label
            return Label(text=f"Error initializing app:\n{e}\n\nCheck console for details.")
    
    def delayed_initialization(self, dt):
        """Perform delayed initialization tasks after the UI has loaded"""
        try:
            # Registrovanie MQTT callback funkcií
            mqtt_client.register_callback("on_sensor_message", self.handle_sensor_update)
            mqtt_client.register_callback("on_image_message", self.handle_image_message)
            mqtt_client.register_callback("on_status_message", self.handle_status_message)
            
            # Spustenie MQTT klienta
            mqtt_client.start()
            
            # Spustenie služby detekcie zariadení cez MQTT
            mqtt_client.start_discovery_service()
            
            # Inicializácia stavu alarmu v systéme
            update_state({"alarm_active": False, "armed_mode": "disarmed"})
            
            # Spustenie monitorovania senzorov pre alarmy
            ns.start_sensor_monitoring()
            
            # Spustenie webového rozhrania v samostatnom vlákne
            self.start_web_interface()
        except Exception as e:
            print(f"ERROR IN DELAYED INITIALIZATION: {e}")
            traceback.print_exc()
    
    def start_web_interface(self):
        """Spúšťa webové rozhranie v samostatnom vlákne."""
        # Kontrolujeme, či už web server nebeží v app.py
        try:
            # Skúsime pripojiť sa na port 5000 - ak je dostupný, znamená to,
            # že web server ešte nie je spustený
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 5000))
            sock.close()
            
            if result != 0:  # Port nie je používaný, môžeme spustiť server
                from web_app import start_web_app
                web_thread = threading.Thread(target=start_web_app, daemon=True)
                web_thread.start()
                print("Webové rozhranie spustené z main.py")
            else:
                print("Webové rozhranie už beží na porte 5000")
        except Exception as e:
            print(f"Chyba pri kontrole/spustení webového rozhrania: {e}")
    
    def handle_sensor_update(self, device_id, data):
        """Spracuje aktualizácie zo senzorov prijaté cez MQTT."""
        print(f"Aktualizácia senzora z {device_id}: {data}")
        
        # Kontrola stavov senzorov pre upozornenia
        if 'motion' in data and data['motion'] == 'DETECTED':
            # Získať názov miestnosti pre zariadenie
            room_name = data.get('room', device_id)
            ns.send_notification(f"Zaznamenaný pohyb v miestnosti {room_name}")
            
        if 'door' in data and data['door'] == 'OPEN':
            room_name = data.get('room', device_id)
            ns.send_notification(f"Otvorené dvere v miestnosti {room_name}")
            
        if 'window' in data and data['window'] == 'OPEN':
            room_name = data.get('room', device_id)
            ns.send_notification(f"Otvorené okno v miestnosti {room_name}")
        
        # Aktualizácia obrazoviek
        app = App.get_running_app()
        for screen_name in ['dashboard', 'sensors']:
            screen = app.root.get_screen(screen_name)
            if hasattr(screen, 'update_sensor_status'):
                Clock.schedule_once(lambda dt: screen.update_sensor_status())
    
    def handle_image_message(self, device_id, image_path, metadata):
        """Spracuje správy s obrázkami prijaté cez MQTT."""
        print(f"Prijatý obrázok od zariadenia {device_id}: {image_path}")
        
        # Pridanie upozornenia s obrázkom
        message = f"Zachytená fotografia z {device_id}"
        ns.add_alert(message, image_path=image_path)
    
    def handle_status_message(self, device_id, status):
        """Spracuje správy o stave zariadení prijaté cez MQTT."""
        print(f"Prijatý stav zariadenia {device_id}: {status}")
        
        # Aktualizácia stavu zariadenia v systéme
        try:
            from config.devices_manager import devices_manager
            from config.system_state import system_state
            
            # Aktualizácia stavu zariadenia
            if isinstance(status, dict):
                # Aktualizácia času poslednej aktivity
                status['last_seen'] = time.time()
                
                # Aktualizácia stavu zariadenia v správcovi zariadení
                devices_manager.update_device_status(device_id, status)
                
                # Aktualizácia stavu systému
                if status.get('status') == 'ONLINE':
                    system_state.set_device_online(device_id, True)
                elif status.get('status') == 'OFFLINE':
                    system_state.set_device_online(device_id, False)
                
                # Ak je zariadenie novo objavené, registrovať ho
                if not devices_manager.device_exists(device_id):
                    # Vytvorenie nového zariadenia v správcovi zariadení
                    device_type = status.get('type', 'unknown')
                    device_name = status.get('name', f'Zariadenie {device_id}')
                    devices_manager.add_device(device_id, device_name, device_type)
                    ns.add_alert(f"Nájdené nové zariadenie: {device_name}")
                    
            # Aktualizácia UI
            app = App.get_running_app()
            for screen_name in ['dashboard', 'sensors']:
                screen = app.root.get_screen(screen_name)
                if hasattr(screen, 'update_device_status'):
                    Clock.schedule_once(lambda dt: screen.update_device_status())
        except Exception as e:
            print(f"ERROR IN HANDLE STATUS MESSAGE: {e}")
            traceback.print_exc()
    
    def on_stop(self):
        """Čistenie pri ukončení aplikácie."""
        print("Zastavujem aplikáciu...")
        
        # Zastavenie monitorovania senzorov
        ns.stop_sensor_monitoring()
        
        # Ak je alarm aktívny, vypneme ho
        if ns.is_alarm_active():
            ns.stop_alarm()
        
        # Zastavenie MQTT klienta
        mqtt_client.stop()

if __name__ == '__main__':
    MainApp().run()
