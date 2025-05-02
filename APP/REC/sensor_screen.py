# sensor_screen.py - Obrazovka senzorov
from kivymd.uix.screen import MDScreen
from kivy.properties import DictProperty, StringProperty, BooleanProperty, ObjectProperty
from kivy.clock import Clock
from config.system_state import load_state
from config.devices_manager import load_devices
from kivymd.uix.list import TwoLineAvatarIconListItem, IconLeftWidget, IconRightWidget
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.uix.image import AsyncImage
from kivymd.uix.card import MDCard
import notification_service as ns
import os
from datetime import datetime
from collections import defaultdict
from kivymd.uix.fitimage import FitImage

class ImageCard(MDCard):
    """Karta s obrázkom zo senzora/kamery pre galériu"""
    image_source = StringProperty("")
    device_name = StringProperty("")
    room_name = StringProperty("")
    timestamp_text = StringProperty("")
    device_id = StringProperty("")
    timestamp = ObjectProperty(None)
    
    def __init__(self, image_path, device_name, room_name, device_id, timestamp=None, callback=None, **kwargs):
        super().__init__(**kwargs)
        self.image_source = image_path
        self.device_name = device_name
        self.room_name = room_name
        self.device_id = device_id
        self.timestamp = timestamp
        self.callback = callback
        
        # Formátovanie časovej značky
        if timestamp:
            try:
                dt = datetime.fromtimestamp(timestamp)
                self.timestamp_text = f"Zachytené: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
            except Exception:
                self.timestamp_text = "Neznámy čas zachytenia"
        else:
            self.timestamp_text = "Neznámy čas zachytenia"
    
    def on_image_click(self):
        if self.callback:
            self.callback(self.image_source, self.timestamp)

class ImageViewerDialog(MDBoxLayout):
    """Dialog pre zobrazenie obrázka zo senzora/kamery"""
    image_source = StringProperty("")
    timestamp_text = StringProperty("")
    is_fullscreen = BooleanProperty(False)
    
    def __init__(self, image_path, timestamp=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = "12dp"
        self.padding = "12dp"
        self.size_hint_y = None
        self.height = "400dp"
        
        self.image_source = image_path
        
        # Formátovanie časovej značky
        if timestamp:
            try:
                dt = datetime.fromtimestamp(timestamp)
                self.timestamp_text = f"Zachytené: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
            except Exception:
                self.timestamp_text = "Neznámy čas zachytenia"
        else:
            self.timestamp_text = "Neznámy čas zachytenia"
    
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

class SensorScreen(MDScreen):
    sensor_states = DictProperty({})
    last_update = StringProperty("")
    system_armed = BooleanProperty(False)
    armed_mode = StringProperty("disarmed")
    alarm_active = BooleanProperty(False)
    image_dialog = ObjectProperty(None)
    current_view = StringProperty("list")
    
    def on_pre_enter(self):
        self.update_sensor_states()
        if not hasattr(self, '_poll_event'):
            self._poll_event = Clock.schedule_interval(lambda dt: self.update_sensor_states(), 2)
        
        # Initialize view mode
        self.switch_view("list")
    
    def on_leave(self):
        # Zrušenie časovača, keď opustíme obrazovku
        if hasattr(self, '_poll_event') and self._poll_event is not None:
            self._poll_event.cancel()
            self._poll_event = None
    
    def go_back(self):
        # Návrat na hlavnú obrazovku
        if self.manager:
            self.manager.current = 'dashboard'
    
    def switch_view(self, view_mode):
        """Prepne medzi zobrazeniami zoznamu a galérie"""
        self.current_view = view_mode
        self.ids.view_manager.current = view_mode
        
        # Update the view content
        self.update_view()
    
    def update_view(self):
        """Aktualizuje obsah aktuálneho zobrazenia"""
        if self.current_view == "list":
            self.update_sensor_list()
        elif self.current_view == "gallery":
            self.update_image_gallery()
    
    def on_sensor_states(self, instance, value):
        """Aktualizácia obsahu pri zmene stavu senzorov"""
        self.update_view()
    
    def update_sensor_list(self):
        """Aktualizuje zoznam senzorov"""
        # Vyčistenie zoznamu a naplnenie novými údajmi
        self.ids.sensors_list.clear_widgets()
        
        # Zoradenie senzorov podľa miestnosti a zariadenia
        sorted_keys = sorted(self.sensor_states.keys(), 
                           key=lambda k: (self.sensor_states[k]['room'], 
                                         self.sensor_states[k]['device_name']))
        
        # Vytvorenie položky zoznamu pre každý senzor
        for key in sorted_keys:
            sensor_data = self.sensor_states[key]
            icon_name = self.get_sensor_icon(key.split('_')[1], sensor_data.get('triggered', False))
            
            icon = IconLeftWidget(icon=icon_name)
            if sensor_data.get('triggered', False):
                icon.theme_text_color = "Custom"
                icon.text_color = sensor_data['color']
            
            # Vytvorenie hlavnej položky zoznamu
            item = TwoLineAvatarIconListItem(
                text=f"{sensor_data['room']} - {sensor_data['sensor']}",
                secondary_text=sensor_data['status']
            )
            
            # Nastavenie farby textu podľa stavu
            if sensor_data.get('triggered', False):
                item.theme_text_color = "Custom"
                item.text_color = sensor_data['color']
                item.secondary_theme_text_color = "Custom"
                item.secondary_text_color = sensor_data['color']
                
                # Ak je senzor spustený a systém je zabezpečený, pridáme ikonu alarmu
                if self.system_armed:
                    alarm_icon = IconRightWidget(icon="alarm-light")
                    alarm_icon.theme_text_color = "Custom"
                    alarm_icon.text_color = [1, 0, 0, 1]
                    item.add_widget(alarm_icon)
            
            # Pridanie klikateľných akcií pre viac informácií
            item.bind(on_release=lambda x, k=key: self.show_sensor_detail(k))
                
            item.add_widget(icon)
            self.ids.sensors_list.add_widget(item)

    def update_image_gallery(self):
        """Aktualizuje galériu obrázkov zo senzorov"""
        # Vyčistenie mriežky
        self.ids.image_grid.clear_widgets()
        
        # Zhromaždenie všetkých jedinečných zariadení
        device_images = {}
        device_info = {}
        
        for key, sensor in self.sensor_states.items():
            device_id = sensor['device_id']
            if device_id not in device_info:
                device_info[device_id] = {
                    'name': sensor['device_name'],
                    'room': sensor['room']
                }
            
            # Ak má senzor obrázok, pridaj do zoznamu
            if sensor.get('image_path'):
                img_path = sensor['image_path']
                if device_id not in device_images or (device_id in device_images and 
                                                    img_path['timestamp'] > device_images[device_id]['timestamp']):
                    device_images[device_id] = img_path
        
        # Vytvorenie karty s obrázkom pre každé zariadenie
        for device_id, img_info in device_images.items():
            device = device_info.get(device_id, {'name': device_id, 'room': 'Neznáma miestnosť'})
            
            card = ImageCard(
                image_path=img_info['path'],
                device_name=device['name'],
                room_name=device['room'],
                device_id=device_id,
                timestamp=img_info['timestamp'],
                callback=lambda path, timestamp: self.show_image(path, timestamp)
            )
            
            self.ids.image_grid.add_widget(card)
        
        # Nastavenie výšky mriežky
        self.ids.image_grid.height = len(device_images) * 340 / 2 + 20  # Približne polovica kariet v riadku
    
    def update_sensor_states(self):
        from datetime import datetime
        # Načítanie stavu systému
        system_state = load_state()
        self.armed_mode = system_state.get('armed_mode', 'disarmed')
        self.system_armed = self.armed_mode != 'disarmed'
        self.alarm_active = system_state.get('alarm_active', False)
        
        # Načítanie stavu senzorov zo súboru
        states = {}
        
        try:
            devices = load_devices()
            
            # Načítanie stavu z device_status.json
            import json
            import os
            device_status_path = os.path.join(os.path.dirname(__file__), '../data/device_status.json')
            
            # Kontrola existencie súboru
            if not os.path.exists(device_status_path):
                print(f"Súbor device_status.json neexistuje na {device_status_path}")
                self.sensor_states = {}
                self.last_update = f"Aktualizované: {datetime.now().strftime('%H:%M:%S')} - Žiadne údaje"
                return
            
            with open(device_status_path, 'r', encoding='utf-8') as f:
                device_states = json.load(f)
                
            # Transformácia senzorov pre zobrazenie
            for device in devices:
                device_id = device['id']  # Možno bude potrebné upraviť podľa skutočného kľúča v dátach
                if device_id in device_states:
                    device_name = device['name'] if 'name' in device else device_id
                    room = device.get('room', 'Neznáma miestnosť')
                    
                    for sensor_type, status in device_states[device_id].items():
                        # Preskočíme nerelevantné kľúče
                        if sensor_type not in ['motion', 'door', 'window']:
                            continue
                            
                        sensor_name = self.get_sensor_name(sensor_type)
                        state_text = self.get_state_text(sensor_type, status)
                        state_color = self.get_state_color(sensor_type, status)
                        
                        # Určenie, či je senzor v stave, ktorý spúšťa alarm
                        triggered = (sensor_type == 'motion' and status == 'DETECTED') or \
                                    (sensor_type in ['door', 'window'] and status == 'OPEN')
                        
                        # Stav alarmu pre daný senzor
                        alarm_state = triggered and self.system_armed
                        if self.armed_mode == 'armed_home' and sensor_type == 'motion':
                            # V režime "Doma" ignorujeme pohybové senzory
                            alarm_state = False
                        
                        states[f"{device_id}_{sensor_type}"] = {
                            'device_id': device_id,
                            'device_name': device_name,
                            'room': room,
                            'sensor': sensor_name,
                            'sensor_type': sensor_type,
                            'raw_status': status,
                            'status': state_text,
                            'color': state_color,
                            'triggered': triggered,
                            'alarm_state': alarm_state,
                            'would_trigger_alarm': triggered and self.armed_mode == 'armed_away',
                            'ignored_in_home_mode': sensor_type == 'motion' and self.armed_mode == 'armed_home',
                            'image_path': self.find_latest_image(device_id)
                        }
        except Exception as e:
            print(f"Chyba pri načítaní stavov senzorov: {e}")
            import traceback
            traceback.print_exc()
            
        self.sensor_states = states
        self.last_update = f"Aktualizované: {datetime.now().strftime('%H:%M:%S')}"
    
    def get_sensor_name(self, sensor_type):
        names = {
            'motion': 'Pohybový senzor',
            'door': 'Dverový kontakt',
            'window': 'Okenný kontakt'
        }
        return names.get(sensor_type, sensor_type.capitalize())
    
    def get_state_text(self, sensor_type, status):
        if sensor_type == 'motion':
            return 'DETEGOVANÝ POHYB' if status == 'DETECTED' else 'ŽIADNY POHYB'
        elif sensor_type == 'door':
            return 'OTVORENÉ' if status == 'OPEN' else 'ZATVORENÉ'
        elif sensor_type == 'window':
            return 'OTVORENÉ' if status == 'OPEN' else 'ZATVORENÉ'
        else:
            return status
    
    def get_state_color(self, sensor_type, status):
        if sensor_type == 'motion' and status == 'DETECTED':
            return [1, 0, 0, 1]  # červená
        elif sensor_type in ['door', 'window'] and status == 'OPEN':
            return [1, 0, 0, 1]  # červená
        else:
            return [0, 0.7, 0, 1]  # zelená
    
    def get_sensor_icon(self, sensor_type, triggered=False):
        if sensor_type == 'motion':
            return 'motion-sensor' if not triggered else 'motion-sensor-alert'
        elif sensor_type == 'door':
            return 'door-closed' if not triggered else 'door-open'
        elif sensor_type == 'window':
            return 'window-closed' if not triggered else 'window-open'
        else:
            return 'devices'
    
    def find_latest_image(self, device_id):
        """Nájde najnovší obrázok pre dané zariadenie"""
        images_dir = os.path.join(os.path.dirname(__file__), '../data/images')
        
        if not os.path.exists(images_dir):
            return None
            
        # Hľadanie všetkých obrázkov pre dané zariadenie
        device_images = []
        for filename in os.listdir(images_dir):
            if filename.startswith(f"{device_id}_") and filename.endswith('.jpg'):
                image_path = os.path.join(images_dir, filename)
                timestamp = os.path.getmtime(image_path)
                device_images.append((image_path, timestamp))
        
        # Zoradenie podľa času (najnovšie prvé)
        if device_images:
            device_images.sort(key=lambda x: x[1], reverse=True)
            return {'path': device_images[0][0], 'timestamp': device_images[0][1]}
            
        return None
    
    def show_sensor_detail(self, sensor_key):
        """Zobrazí detailný dialóg o senzore"""
        if sensor_key not in self.sensor_states:
            return
            
        sensor = self.sensor_states[sensor_key]
        
        # Vytvorenie informácií o stave alarmu
        alarm_info = ""
        if self.system_armed:
            if sensor['alarm_state']:
                alarm_info = "POZOR! Senzor spustil alarm!"
            elif sensor['ignored_in_home_mode']:
                alarm_info = "Senzor je v režime Doma ignorovaný."
            elif sensor['triggered']:
                alarm_info = "Senzor je spustený, ale alarm nie je aktívny."
            else:
                alarm_info = "Senzor je v normálnom stave."
        else:
            if sensor['triggered']:
                alarm_info = "Senzor je spustený, ale systém nie je zabezpečený."
            else:
                alarm_info = "Senzor je v normálnom stave."
        
        # Pridanie informácie o dostupnom obrázku
        image_info = ""
        if sensor.get('image_path'):
            image_info = "\n\nK dispozícii je zachytený obrázok."
        
        content = f"""
Miestnosť: {sensor['room']}
Zariadenie: {sensor['device_name']}
Typ senzora: {sensor['sensor']}
Stav: {sensor['status']}

{alarm_info}{image_info}
        """
        
        # Vytvorenie tlačidiel dialógu
        buttons = [
            MDFlatButton(
                text="ZATVORIŤ",
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x: self.dialog.dismiss()
            )
        ]
        
        # Ak je alarm aktívny, pridáme tlačidlo na jeho zastavenie
        if self.alarm_active and sensor['alarm_state']:
            buttons.append(
                MDFlatButton(
                    text="ZASTAVIŤ ALARM",
                    theme_text_color="Custom",
                    text_color=[1, 0, 0, 1],
                    on_release=lambda x: self.stop_alarm_and_dismiss()
                )
            )
        
        # Ak má senzor obrázok, pridáme tlačidlo pre jeho zobrazenie
        if sensor.get('image_path'):
            buttons.append(
                MDFlatButton(
                    text="ZOBRAZIŤ OBRÁZOK",
                    theme_text_color="Custom",
                    text_color=self.theme_cls.primary_color,
                    on_release=lambda x: self.show_image(sensor['image_path']['path'], sensor['image_path']['timestamp'])
                )
            )
        
        # Vytvorenie dialógu
        self.dialog = MDDialog(
            title=f"{sensor['sensor']} - {sensor['room']}",
            text=content,
            buttons=buttons
        )
        self.dialog.open()
    
    def show_image(self, image_path, timestamp):
        """Zobrazí obrázok zo senzora/kamery"""
        if hasattr(self, 'dialog') and self.dialog:
            self.dialog.dismiss()
            
        # Vytvorenie obsahu dialógu pre obrázok
        content = ImageViewerDialog(image_path=image_path, timestamp=timestamp)
        
        # Vytvorenie referencie na content objekt pre použitie v tlačidlách
        self.image_content = content
        
        # Tlačidlá pre dialóg
        buttons = [
            MDFlatButton(
                text="ZATVORIŤ",
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x: self.image_dialog.dismiss()
            ),
            MDFlatButton(
                text="FULLSCREEN",
                theme_text_color="Custom",
                text_color=self.theme_cls.primary_color,
                on_release=lambda x: self.toggle_fullscreen()
            )
        ]
        
        self.image_dialog = MDDialog(
            title="Náhľad z kamery",
            type="custom",
            content_cls=content,
            buttons=buttons,
            size_hint=(0.9, None)
        )
        self.image_dialog.open()
    
    def toggle_fullscreen(self):
        """Prepína medzi normálnym a fullscreen režimom pre náhľad obrázku"""
        if hasattr(self, 'image_content') and self.image_content:
            self.image_content.toggle_fullscreen()
            
            # Aktualizácia textu tlačidla podľa aktuálneho stavu
            for btn in self.image_dialog.buttons:
                if btn.text == "FULLSCREEN" or btn.text == "UKONČIŤ FULLSCREEN":
                    btn.text = "UKONČIŤ FULLSCREEN" if self.image_content.is_fullscreen else "FULLSCREEN"
    
    def stop_alarm_and_dismiss(self):
        """Zastaví alarm a zatvorí dialóg"""
        ns.stop_alarm()
        self.dialog.dismiss()
        # Aktualizácia zobrazenia
        self.update_sensor_states()