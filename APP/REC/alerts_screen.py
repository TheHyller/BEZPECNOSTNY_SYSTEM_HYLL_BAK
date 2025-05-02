# alerts_screen.py - História upozornení
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget, ThreeLineAvatarIconListItem
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivy.uix.image import AsyncImage
from kivy.properties import StringProperty, BooleanProperty
from datetime import datetime
from config.alerts_log import get_recent_alerts, get_alerts_by_level, clear_alerts as clear_all_alerts
import os

class AlertImageViewerDialog(MDBoxLayout):
    """Dialog pre zobrazenie obrázka z upozornenia"""
    image_source = StringProperty("")
    timestamp_text = StringProperty("")
    additional_info = StringProperty("")
    is_fullscreen = BooleanProperty(False)
    
    def __init__(self, image_path, timestamp=None, additional_info="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.padding = "12dp"
        self.size_hint_y = None
        self.height = "400dp"
        
        self.image_source = image_path
        self.additional_info = additional_info
        
        # Formátovanie časovej značky
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                self.timestamp_text = f"Čas: {dt.strftime('%d.%m.%Y %H:%M:%S')}"
            except Exception:
                self.timestamp_text = "Neznámy čas"
        else:
            self.timestamp_text = "Neznámy čas"
    
    def toggle_fullscreen(self):
        """Prepínanie medzi normálnym a celoobrazovkovým zobrazením"""
        self.is_fullscreen = not self.is_fullscreen
        
        if self.is_fullscreen:
            # Celoobrazovkový režim
            self.height = "600dp"  # Zväčšenie výšky
            self.padding = "0dp"   # Odstránenie odsadenia
            self.spacing = "0dp"   # Odstránenie medzer
        else:
            # Normálny režim
            self.height = "400dp"
            self.padding = "12dp"
            self.spacing = "12dp"

class AlertsScreen(MDScreen):
    current_filter = "all"
    current_dialog = None
    image_content = None
    
    def on_enter(self):
        """Volaná keď sa užívateľ presunie na túto obrazovku"""
        self.load_alerts()
    
    def load_alerts(self):
        """Načíta a zobrazí upozornenia podľa aktuálneho filtra"""
        alerts_list = self.ids.alerts_list
        alerts_list.clear_widgets()
        
        # Získanie upozornení podľa aktuálneho filtra
        if self.current_filter == "all":
            alerts = get_recent_alerts(count=50)  # Načítame posledných 50 upozornení
        else:
            alerts = get_alerts_by_level(self.current_filter, count=50)
            
        if not alerts:
            # Ak nie sú žiadne upozornenia, zobrazíme informáciu
            item = TwoLineAvatarIconListItem(
                text="Žiadne upozornenia",
                secondary_text="Nenašli sa žiadne záznamy v histórii upozornení"
            )
            icon = IconLeftWidget(icon="information")
            item.add_widget(icon)
            alerts_list.add_widget(item)
            return
            
        # Zobraziť všetky upozornenia
        for alert in alerts:
            # Formátovanie času
            try:
                timestamp = datetime.fromisoformat(alert.get("timestamp", ""))
                formatted_time = timestamp.strftime("%d.%m.%Y %H:%M:%S")
            except (ValueError, TypeError):
                formatted_time = "Neznámy čas"
                
            # Ikona podľa typu upozornenia
            icon_name = {
                "info": "information",
                "warning": "alert", 
                "danger": "alarm-light",
                "alert": "alarm-light",
            }.get(alert.get("level", "info"), "information")
            
            # Vytvorenie položky zoznamu
            has_image = "image_path" in alert and os.path.exists(alert["image_path"])
            
            # Ak má alert obrázok, pridaj informáciu o tom do textu
            if has_image:
                item = ThreeLineAvatarIconListItem(
                    text=alert.get("message", "Neznáme upozornenie"),
                    secondary_text=f"{formatted_time}",
                    tertiary_text="Kliknutím zobrazíte detaily s obrázkom"
                )
                # Nastavenie akcie po kliknutí na položku
                item.bind(on_release=lambda item, alert=alert: self.show_image_dialog(alert))
            else:
                item = TwoLineAvatarIconListItem(
                    text=alert.get("message", "Neznáme upozornenie"),
                    secondary_text=f"{formatted_time}"
                )
            
            # Pridanie ikony podľa typu upozornenia
            icon = IconLeftWidget(icon=icon_name)
            if has_image:
                icon.theme_text_color = "Custom"
                icon.text_color = [0.2, 0.6, 1, 1]  # Modrá farba pre položky s obrázkom
            item.add_widget(icon)
            
            # Pridanie položky do zoznamu
            alerts_list.add_widget(item)
    
    def show_image_dialog(self, alert):
        """Zobrazí dialóg s detailmi a obrázkom z upozornenia"""
        if not alert or "image_path" not in alert or not os.path.exists(alert["image_path"]):
            return
        
        try:
            # Formátovanie času
            timestamp = alert.get("timestamp", "")
            formatted_time = timestamp
        except Exception:
            formatted_time = "Neznámy čas"
            
        # Vytvorenie dodatočných informácií o upozornení
        additional_info = f"Typ: {alert.get('level', 'info').upper()}\n{alert.get('message', '')}"
        
        # Vytvorenie obsahu dialógu pre obrázok
        content = AlertImageViewerDialog(
            image_path=alert["image_path"],
            timestamp=timestamp,
            additional_info=additional_info
        )
        
        # Vytvorenie referencie na content objekt pre použitie v tlačidlách
        self.image_content = content
        
        # Tlačidlá pre dialóg
        buttons = [
            MDFlatButton(
                text="ZATVORIŤ",
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x: self.close_dialog()
            ),
            MDFlatButton(
                text="FULLSCREEN",
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x: self.toggle_fullscreen()
            )
        ]
        
        # Zatvorenie predchádzajúceho dialógu, ak existuje
        if self.current_dialog:
            self.current_dialog.dismiss()
        
        self.current_dialog = MDDialog(
            title=alert.get("message", "Detaily upozornenia"),
            type="custom",
            content_cls=content,
            buttons=buttons,
            size_hint=(0.9, None)
        )
        self.current_dialog.open()
    
    def toggle_fullscreen(self):
        """Prepína medzi normálnym a fullscreen režimom pre náhľad obrázku"""
        if hasattr(self, 'image_content') and self.image_content:
            self.image_content.toggle_fullscreen()
            
            # Aktualizácia textu tlačidla podľa aktuálneho stavu
            for btn in self.current_dialog.buttons:
                if btn.text == "FULLSCREEN" or btn.text == "UKONČIŤ FULLSCREEN":
                    btn.text = "UKONČIŤ FULLSCREEN" if self.image_content.is_fullscreen else "FULLSCREEN"
    
    def close_dialog(self):
        """Zatvorí aktuálny dialóg"""
        if self.current_dialog:
            self.current_dialog.dismiss()
            self.current_dialog = None
            
    def filter_alerts(self, filter_type):
        """Aplikuje filter na zobrazenie upozornení"""
        self.current_filter = filter_type
        self.load_alerts()
    
    def clear_alerts(self):
        """Vymaže všetky upozornenia z histórie"""
        # Vymazanie upozornení zo súboru
        clear_all_alerts()
        # Aktualizácia zobrazenia
        self.load_alerts()
