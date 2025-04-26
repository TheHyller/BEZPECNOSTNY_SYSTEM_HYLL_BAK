# dashboard_screen.py - Panel senzorov
from kivymd.uix.screen import MDScreen
from kivy.clock import Clock
from kivy.properties import BooleanProperty, StringProperty, ObjectProperty
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivy.uix.gridlayout import GridLayout
from config.system_state import load_state, update_state
from config.devices_manager import load_devices
from config.settings import load_settings
import notification_service as ns
import time
import json
import os

class PinInputDialog(MDBoxLayout):
    """Dialóg pre zadanie PIN kódu."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.padding = "24dp"
        self.size_hint_y = None
        self.height = "400dp"  # Zväčšená výška pre umiestnenie klávesnice
        
        # Text pole pre zadanie PIN kódu
        self.pin_input = MDTextField(
            hint_text="Zadajte PIN kód",
            password=True,
            helper_text="Pre potvrdenie operácie je potrebný PIN",
            helper_text_mode="persistent",
            size_hint_y=None,
            height="48dp",
            readonly=True  # Nastavené na True, aby sa nezobrazovala softvérová klávesnica
        )
        self.add_widget(self.pin_input)
        
        # Pridanie medzery
        spacer = MDBoxLayout(size_hint_y=None, height="24dp")
        self.add_widget(spacer)
        
        # Numerická klávesnica
        numpad = GridLayout(
            cols=3,
            spacing="12dp",
            size_hint_y=None,
            height="240dp"
        )
        
        # Vytvorenie tlačidiel 1-9
        for i in range(1, 10):
            btn = MDRaisedButton(
                text=str(i),
                size_hint=(1, 1),
                font_size="24sp"
            )
            btn.bind(on_release=lambda x, num=i: self.on_numpad_press(num))
            numpad.add_widget(btn)
        
        # Tlačidlo Vymazať (C)
        clear_btn = MDRaisedButton(
            text="C",
            size_hint=(1, 1),
            font_size="24sp",
            md_bg_color=[0.8, 0.2, 0.2, 1]
        )
        clear_btn.bind(on_release=lambda x: self.on_clear_press())
        numpad.add_widget(clear_btn)
        
        # Tlačidlo 0
        zero_btn = MDRaisedButton(
            text="0",
            size_hint=(1, 1),
            font_size="24sp"
        )
        zero_btn.bind(on_release=lambda x: self.on_numpad_press(0))
        numpad.add_widget(zero_btn)
        
        # Prázdne tlačidlo (alebo alternatívne Backspace)
        back_btn = MDRaisedButton(
            text="←",
            size_hint=(1, 1),
            font_size="24sp",
            md_bg_color=[0.4, 0.4, 0.4, 1]
        )
        back_btn.bind(on_release=lambda x: self.on_backspace_press())
        numpad.add_widget(back_btn)
        
        self.add_widget(numpad)
    
    def on_numpad_press(self, number):
        """Spracovanie stlačenia čísla na numerickej klávesnici."""
        # Ochrana proti dvojitému stlačeniu - kontrola času od posledného stlačenia
        current_time = time.time()
        if hasattr(self, 'last_press_time'):
            # Ak uplynulo menej ako 300ms, ignorujeme stlačenie
            if current_time - self.last_press_time < 0.3:
                return
        
        self.last_press_time = current_time
        self.pin_input.text += str(number)
    
    def on_clear_press(self):
        """Vymazanie celého PIN kódu."""
        self.pin_input.text = ""
        self.pin_input.error = False
        self.pin_input.helper_text = "Pre potvrdenie operácie je potrebný PIN"
    
    def on_backspace_press(self):
        """Vymazanie posledného znaku PIN kódu."""
        self.pin_input.text = self.pin_input.text[:-1]

class DashboardScreen(MDScreen):
    # Vlastnosti pre sledovanie stavu systému
    system_armed = BooleanProperty(False)
    alarm_active = BooleanProperty(False)
    armed_mode = StringProperty("disarmed")  # 'disarmed', 'armed_home', 'armed_away'
    status_text = StringProperty("")
    last_update = ObjectProperty(None)
    
    # Počty zariadení a senzorov
    device_count = StringProperty("0")
    online_device_count = StringProperty("0")
    sensors_triggered = StringProperty("0")
    
    # Dialóg pre zadanie PIN kódu
    pin_dialog = None
    current_action = None  # 'arm_home', 'arm_away', 'disarm', 'stop_alarm'
    
    def on_pre_enter(self):
        """Aktualizácia stavu pri otvorení obrazovky."""
        self.update_from_state()
        # Nastavenie pravidelnej aktualizácie každú sekundu
        if not hasattr(self, '_poll_event'):
            self._poll_event = Clock.schedule_interval(lambda dt: self.update_from_state(), 1)

    def update_from_state(self):
        """Aktualizuje UI podľa aktuálneho stavu systému."""
        state = load_state()
        
        # Kontrola stavu zabezpečenia
        self.armed_mode = state.get('armed_mode', 'disarmed')
        self.system_armed = self.armed_mode != 'disarmed'
        self.alarm_active = state.get('alarm_active', False)
        alarm_countdown_active = state.get('alarm_countdown_active', False)
        self.last_update = time.strftime("%H:%M:%S", time.localtime())
        
        # Automaticky zatvoriť PIN dialóg, ak už nie je potrebný (napr. pri deaktivácii z iného rozhrania)
        if hasattr(self, 'pin_dialog') and self.pin_dialog:
            if self.current_action == "stop_alarm" and not self.alarm_active:
                self.pin_dialog.dismiss()
                self.pin_dialog = None
            elif self.current_action == "disarm" and not self.system_armed and not alarm_countdown_active:
                self.pin_dialog.dismiss()
                self.pin_dialog = None
        
        # Nastavenie textu stavu
        if self.alarm_active:
            self.status_text = "ALARM AKTÍVNY! Narušenie detekované!"
        elif alarm_countdown_active:
            countdown_remaining = max(0, int(state.get('alarm_countdown_deadline', 0) - time.time()))
            self.status_text = f"POZOR! Odpočítavanie alarmu: {countdown_remaining}s"
        elif self.armed_mode == 'armed_home':
            self.status_text = "Systém zabezpečený - režim Doma"
        elif self.armed_mode == 'armed_away':
            self.status_text = "Systém zabezpečený - režim Preč"
        else:
            self.status_text = "Systém nezabezpečený"
        
        # Aktualizácia štatistík zariadení
        try:
            devices = load_devices()
            online_devices = 0
            triggered_sensors = 0
            
            # Načítanie stavu zariadení
            device_status_path = os.path.join(os.path.dirname(__file__), '../data/device_status.json')
            if os.path.exists(device_status_path):
                with open(device_status_path, 'r', encoding='utf-8') as f:
                    device_status = json.load(f)
                    
                # Počítanie zariadení online a aktivovaných senzorov
                for device_id, device_data in device_status.items():
                    # Kontrola, či je zariadenie online
                    if device_data.get('status') == 'ONLINE':
                        online_devices += 1
                        
                    # Počítanie aktivovaných senzorov
                    if device_data.get('motion') == 'DETECTED':
                        triggered_sensors += 1
                    if device_data.get('door') == 'OPEN':
                        triggered_sensors += 1
                    if device_data.get('window') == 'OPEN':
                        triggered_sensors += 1
            
            # Aktualizácia UI
            self.device_count = str(len(devices))
            self.online_device_count = str(online_devices)
            self.sensors_triggered = str(triggered_sensors)
            
        except Exception as e:
            print(f"Chyba pri aktualizácii štatistík zariadení: {e}")
        
        # Aktualizácia tlačidiel
        self.update_button_states()

    def update_button_states(self):
        """Aktualizuje stav tlačidiel na základe aktuálneho stavu systému."""
        if hasattr(self.ids, 'arm_home_btn'):
            # Tlačidlo režimu Doma nemožno použiť, ak je systém už v akomkoľvek režime zabezpečenia
            self.ids.arm_home_btn.disabled = self.system_armed or self.alarm_active
            
        if hasattr(self.ids, 'arm_away_btn'):
            # Tlačidlo režimu Preč nemožno použiť, ak je systém už v akomkoľvek režime zabezpečenia
            self.ids.arm_away_btn.disabled = self.system_armed or self.alarm_active
            
        if hasattr(self.ids, 'disarm_btn'):
            # Tlačidlo deaktivácie je aktívne iba ak je systém zabezpečený
            self.ids.disarm_btn.disabled = not self.system_armed
            
        if hasattr(self.ids, 'alarm_stop_btn'):
            # Tlačidlo zastavenia alarmu je aktívne iba ak je spustený alarm
            self.ids.alarm_stop_btn.disabled = not self.alarm_active

    def show_pin_dialog(self, action):
        """Zobrazí dialóg pre zadanie PIN kódu."""
        self.current_action = action
        
        # Vytvorenie obsahu dialógu
        content = PinInputDialog()
        
        # Vytvorenie tlačidiel
        cancel_btn = MDFlatButton(
            text="ZRUŠIŤ",
            on_release=lambda x: self.pin_dialog.dismiss()
        )
        
        confirm_btn = MDFlatButton(
            text="POTVRDIŤ",
            on_release=lambda x: self.verify_pin(content.pin_input.text)
        )
        
        # Vytvorenie a zobrazenie dialógu
        self.pin_dialog = MDDialog(
            title="Overiť PIN kód" if action in ["arm_home", "arm_away"] else "Zadajte PIN kód",
            type="custom",
            content_cls=content,
            buttons=[cancel_btn, confirm_btn]
        )
        self.pin_dialog.open()
    
    def verify_pin(self, pin):
        """Overí zadaný PIN kód a vykoná požadovanú akciu."""
        if not pin:
            # Prázdny PIN
            return
            
        # Načítanie nastavení a správneho PIN kódu
        settings = load_settings()
        correct_pin = settings.get("security_pin", "1234")
        
        if pin == correct_pin:
            # PIN je správny, vykonanie akcie
            self.pin_dialog.dismiss()
            
            if self.current_action == "arm_home":
                self._arm_system_home()
            elif self.current_action == "arm_away":
                self._arm_system_away()
            elif self.current_action == "disarm":
                self._disarm_system()
            elif self.current_action == "stop_alarm":
                self._stop_alarm()
        else:
            # Nesprávny PIN
            content = self.pin_dialog.content_cls
            content.pin_input.error = True
            content.pin_input.helper_text = "Nesprávny PIN kód"
            content.pin_input.text = ""
    
    def arm_system_home(self):
        """Zobrazí PIN dialóg pre aktiváciu systému v režime Doma."""
        self.show_pin_dialog("arm_home")
    
    def _arm_system_home(self):
        """Aktivuje systém v režime Doma (ignoruje pohybové senzory)."""
        # Nastavenie režimu zabezpečenia
        update_state({"armed_mode": "armed_home", "alarm_active": False})
        ns.send_notification("Systém zabezpečený v režime Doma")
        
        # Aktualizácia UI
        self.update_from_state()

    def arm_system_away(self):
        """Zobrazí PIN dialóg pre aktiváciu systému v režime Preč."""
        self.show_pin_dialog("arm_away")
    
    def _arm_system_away(self):
        """Aktivuje systém v režime Preč (všetky senzory aktívne)."""
        # Nastavenie režimu zabezpečenia
        update_state({"armed_mode": "armed_away", "alarm_active": False})
        ns.send_notification("Systém zabezpečený v režime Preč")
        
        # Aktualizácia UI
        self.update_from_state()

    def disarm_system(self):
        """Zobrazí PIN dialóg pre deaktiváciu systému."""
        self.show_pin_dialog("disarm")
    
    def _disarm_system(self):
        """Deaktivuje zabezpečenie systému."""
        # Nastavenie režimu zabezpečenia
        update_state({"armed_mode": "disarmed"})
        ns.send_notification("Systém bol deaktivovaný")
        
        # Aktualizácia UI
        self.update_from_state()

    def stop_alarm(self):
        """Zobrazí PIN dialóg pre zastavenie alarmu."""
        self.show_pin_dialog("stop_alarm")
    
    def _stop_alarm(self):
        """Zastaví aktívny alarm a deaktivuje zabezpečenie systému."""
        if self.alarm_active:
            # Zastavenie alarmu a deaktivácia systému
            ns.stop_alarm()
            update_state({"armed_mode": "disarmed"})
            ns.send_notification("Alarm bol zastavený a systém deaktivovaný")
            
            # Aktualizácia UI
            self.update_from_state()

    def update_sensor_status(self):
        """Aktualizuje stav senzorov (volaný z hlavnej aplikácie)."""
        self.update_from_state()

    def update_device_status(self):
        """Aktualizuje stav zariadení (volaný z hlavnej aplikácie)."""
        self.update_from_state()
