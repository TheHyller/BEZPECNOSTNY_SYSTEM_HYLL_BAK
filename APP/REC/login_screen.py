# login_screen.py - Prihlasovacia obrazovka
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivy.properties import StringProperty
from kivy.lang import Builder
from kivy.clock import Clock
from config.system_state import load_state, save_state, is_locked_out, set_lockout
from config.settings import load_settings
from notification_service import play_alarm, stop_alarm, send_email
import time
from datetime import datetime

class LoginScreen(MDScreen):
    pin = StringProperty("")
    failed_attempts = 0
    locked = False
    first_update = True  # Flag to identify first update
    countdown_text = StringProperty("")
    alarm_activated = False  # Stav pre sledovanie, či už bol spustený alarm
    last_press_time = 0  # Čas posledného stlačenia tlačidla - ochrana proti dvojitému stlačeniu

    def on_pre_enter(self):
        self.first_update = True  # Reset flag when entering screen
        if not hasattr(self, '_poll_event'):
            self._poll_event = Clock.schedule_interval(lambda dt: self.update_from_state(), 1)
        self.update_from_state()
    
    def update_from_state(self):
        state = load_state()
        self.locked = state['lockout_until'] and time.time() < state['lockout_until']
        
        # Aktualizácia odpočítavania ak je alarm aktivovaný
        alarm_deadline = state.get('alarm_deadline')
        if state['alarm_triggered'] and alarm_deadline:
            seconds_left = max(0, int(alarm_deadline - time.time()))
            self.countdown_text = f"Zostávajúci čas: {seconds_left} s"
            
            # Ak čas vypršal a alarm ešte nebol spustený
            if seconds_left <= 0 and not self.alarm_activated:
                self.countdown_text = "Čas vypršal! Alarm aktivovaný!"
                self.alarm_activated = True
                
                # Spustenie zvukového alarmu
                play_alarm()
                
                # Odoslanie emailu
                self.send_alarm_email()
            
            # Ak niekto deaktivoval alarm
            elif not state['alarm_triggered'] and self.alarm_activated:
                self.alarm_activated = False
                stop_alarm()
        else:
            self.countdown_text = ""
            if self.alarm_activated:
                self.alarm_activated = False
                stop_alarm()
            
        if self.locked:
            self.ids.pin_input.hint_text = "Zamknuté, skúste neskôr."
        else:
            if self.ids.pin_input.hint_text not in ["PIN", "Nesprávny PIN!"]:
                self.ids.pin_input.hint_text = "PIN"
                
        # Vynulovanie PIN len pri prvom načítaní obrazovky, nie pri každej aktualizácii
        if self.first_update:
            self.pin = ""
            self.ids.pin_input.text = ""
            self.first_update = False
            
    def send_alarm_email(self):
        """Odošle email s upozornením o aktivácii alarmu."""
        settings = load_settings()
        notification_prefs = settings.get('notification_preferences', {})
        
        if notification_prefs.get('email', False):
            message = "UPOZORNENIE: Alarm bol aktivovaný! Nikto nezadal PIN kód v stanovenom čase. Skontrolujte svoj domáci bezpečnostný systém."
            send_email(message, settings)

    def on_number_press(self, number):
        """Spracovanie stlačenia čísla na numerickej klávesnici."""
        if self.locked:
            return
        
        # Ochrana proti dvojitému stlačeniu - kontrola času od posledného stlačenia
        current_time = time.time()
        if hasattr(self, 'last_press_time'):
            # Ak uplynulo menej ako 300ms, ignorujeme stlačenie
            if current_time - self.last_press_time < 0.3:
                return
                
        self.last_press_time = current_time
        
        if len(self.pin) < 6:
            self.pin += str(number)
            self.ids.pin_input.text = "*" * len(self.pin)

    def on_clear(self):
        """Vymazanie celého PIN kódu."""
        if self.locked:
            return
        self.pin = ""
        self.ids.pin_input.text = ""
        self.ids.pin_input.hint_text = "PIN"
        
    def on_backspace(self):
        """Vymazanie posledného znaku PIN kódu."""
        if self.locked:
            return
        if len(self.pin) > 0:
            self.pin = self.pin[:-1]
            self.ids.pin_input.text = "*" * len(self.pin)

    def on_enter(self):
        if self.locked:
            return
        state = load_state()
        settings = load_settings()
        if self.pin == settings['pin_code']:
            self.failed_attempts = 0
            dashboard = self.manager.get_screen('dashboard')
            if hasattr(dashboard, 'deactivate_system'):
                dashboard.deactivate_system()
            self.manager.current = "dashboard"  # Presmerovanie priamo na dashboard
        else:
            self.failed_attempts += 1
            self.on_clear()
            self.ids.pin_input.hint_text = "Nesprávny PIN!"
            if self.failed_attempts >= 3:
                set_lockout(30)
                self.failed_attempts = 0
