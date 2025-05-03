# settings_screen.py - Nastavenia systému
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDSwitch
from kivy.properties import StringProperty
from kivy.uix.behaviors import FocusBehavior
from config.settings import load_settings, save_settings
from kivy.properties import BooleanProperty

class SettingsScreen(MDScreen):
    pin_code = StringProperty("")
    sound_notifications = BooleanProperty(True)
    email_notifications = BooleanProperty(False)
    smtp_server = StringProperty("")
    smtp_port = StringProperty("587")
    email_username = StringProperty("")
    email_password = StringProperty("")
    email_recipient = StringProperty("")
    email_enabled = BooleanProperty(False)
    
    def on_pre_enter(self):
        self.load_settings_from_file()
    
    def load_settings_from_file(self):
        settings = load_settings()
        self.pin_code = settings.get("pin_code", "1234")
        
        notification_prefs = settings.get("notification_preferences", {})
        self.sound_notifications = notification_prefs.get("sound", True)
        self.email_notifications = notification_prefs.get("email", False)
        
        email_settings = settings.get("email_settings", {})
        self.email_enabled = email_settings.get("enabled", False)
        self.smtp_server = email_settings.get("smtp_server", "")
        self.smtp_port = str(email_settings.get("smtp_port", "587"))
        self.email_username = email_settings.get("username", "")
        self.email_password = email_settings.get("password", "")
        self.email_recipient = email_settings.get("recipient", "")
    
    def save_settings_to_file(self):
        settings = load_settings()
        
        settings["pin_code"] = self.pin_code
        
        if "notification_preferences" not in settings:
            settings["notification_preferences"] = {}
        settings["notification_preferences"]["sound"] = self.sound_notifications
        settings["notification_preferences"]["email"] = self.email_notifications
        
        if "email_settings" not in settings:
            settings["email_settings"] = {}
        settings["email_settings"]["enabled"] = self.email_enabled
        settings["email_settings"]["smtp_server"] = self.smtp_server
        settings["email_settings"]["smtp_port"] = int(self.smtp_port or 587)
        settings["email_settings"]["username"] = self.email_username
        settings["email_settings"]["password"] = self.email_password
        settings["email_settings"]["recipient"] = self.email_recipient
        
        save_settings(settings)
    
    def on_sound_notifications(self, instance, value):
        self.save_settings_to_file()
    
    def on_email_notifications(self, instance, value):
        self.save_settings_to_file()
        
    def on_email_enabled(self, instance, value):
        self.save_settings_to_file()
    
    def update_pin_code(self, new_pin):
        if new_pin and len(new_pin) >= 4:
            self.pin_code = new_pin
            self.save_settings_to_file()
            return True
        return False
        
    def update_email_settings(self):
        self.save_settings_to_file()
        return True
        
    def go_back(self):
        if self.manager:
            self.manager.current = 'dashboard'
