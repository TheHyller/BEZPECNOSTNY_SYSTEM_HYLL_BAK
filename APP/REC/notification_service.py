import os
import threading
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import logging
from config.system_state import load_state, update_state
from config.settings import load_settings
from config.alerts_log import add_alert_log, get_recent_alerts

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s"
)

ALARM_SOUND_FILE = os.path.join(os.path.dirname(__file__), 'sounds/alarm.wav')

_alarm_active = False
_alarm_thread = None
_monitoring_thread = None
_monitoring_active = False
_last_sensor_states = {}

_alarm_start_time = None
_alarm_duration_threshold = 59
_alarm_duration_email_sent = False
_alarm_duration_monitor_thread = None

_alarm_countdown_active = False
_alarm_countdown_thread = None
_alarm_countdown_deadline = None
_alarm_trigger_message = None
_alarm_countdown_duration = 60

def is_alarm_active():
    return _alarm_active

def is_alarm_countdown_active():
    return _alarm_countdown_active

def get_alarm_countdown_seconds():
    if not _alarm_countdown_active or not _alarm_countdown_deadline:
        return 0
    
    remaining = _alarm_countdown_deadline - time.time()
    return max(0, int(remaining))

def get_alarm_trigger_message():
    return _alarm_trigger_message

def play_alarm():
    global _alarm_active, _alarm_thread, _alarm_start_time, _alarm_duration_email_sent, _alarm_duration_monitor_thread
    
    if _alarm_active:
        return
    
    try:
        if not os.path.exists(ALARM_SOUND_FILE):
            logging.warning(f"Zvukový súbor alarmu nebol nájdený: {ALARM_SOUND_FILE}")
            return False
        
        update_state({"alarm_active": True})
        _alarm_active = True
        _alarm_start_time = time.time()
        _alarm_duration_email_sent = False
        
        _alarm_thread = threading.Thread(target=_alarm_sound_loop, daemon=True)
        _alarm_thread.start()
        
        _alarm_duration_monitor_thread = threading.Thread(target=_monitor_alarm_duration, daemon=True)
        _alarm_duration_monitor_thread.start()
        
        logging.info("Alarm bol spustený")
        return True
    except Exception as e:
        logging.error(f"Chyba pri spúšťaní alarmu: {e}")
        return False

def stop_alarm():
    global _alarm_active, _alarm_countdown_active, _alarm_countdown_deadline, _alarm_trigger_message
    
    try:
        if _alarm_countdown_active:
            _alarm_countdown_active = False
            _alarm_countdown_deadline = None
            _alarm_trigger_message = None
            
            update_state({
                "alarm_countdown_active": False,
                "alarm_countdown_deadline": None,
                "alarm_trigger_message": None,
                "alarm_countdown_remaining": 0
            })
            
            logging.info("Odpočítavanie alarmu zastavené")
            
        _alarm_active = False
        update_state({"alarm_active": False})
        
        try:
            from mqtt_client import mqtt_client
            if mqtt_client and hasattr(mqtt_client, "publish_control_message"):
                mqtt_client.publish_control_message("all", "RESET", {
                    "command": "RESET",
                    "message": "Alarm deaktivovaný používateľom"
                })
                logging.info("Príkaz RESET odoslaný všetkým zariadeniam na zastavenie alarmu")
        except Exception as e:
            logging.error(f"Chyba pri odosielaní príkazu RESET zariadeniam: {e}")
        
        logging.info("Alarm bol zastavený")
        return True
    except Exception as e:
        logging.error(f"Chyba pri zastavení alarmu: {e}")
        return False

def _alarm_sound_loop():
    global _alarm_active
    
    try:
        import pygame
        pygame.mixer.init()
        alarm_sound = pygame.mixer.Sound(ALARM_SOUND_FILE)
        
        while _alarm_active:
            alarm_sound.play()
            time.sleep(2)
    except ImportError:
        logging.error("Knižnica pygame nie je nainštalovaná. Zvukový alarm nebude prehrávať.")
        try:
            if os.name == "nt":
                import winsound
                while _alarm_active:
                    winsound.Beep(1000, 500)
                    winsound.Beep(800, 500)
                    time.sleep(1)
            else:
                logging.warning("Zvukový alarm nie je dostupný na tejto platforme bez pygame.")
        except Exception as e:
            logging.error(f"Chyba pri prehrávaní alternatívneho zvuku alarmu: {e}")
    except Exception as e:
        logging.error(f"Chyba pri prehrávaní zvuku alarmu: {e}")

def _monitor_alarm_duration():
    global _alarm_active, _alarm_start_time, _alarm_duration_threshold, _alarm_duration_email_sent
    
    while _alarm_active:
        try:
            if _alarm_start_time:
                elapsed_time = time.time() - _alarm_start_time
                if elapsed_time > _alarm_duration_threshold and not _alarm_duration_email_sent:
                    send_notification(
                        f"Alarm beží už viac ako {elapsed_time:.0f} sekúnd.",
                        level="warning"
                    )
                    _alarm_duration_email_sent = True
            time.sleep(1)
        except Exception as e:
            logging.error(f"Chyba pri monitorovaní trvania alarmu: {e}")

def send_notification(message, level="info", image_path=None):
    try:
        if image_path is None:
            image_path = find_latest_image()
            if image_path:
                logging.info(f"Automaticky vybraný najnovší obrázok pre notifikáciu: {image_path}")
        
        add_alert_log(message, level, image_path)
        
        settings = load_settings()
        notification_prefs = settings.get("notification_preferences", {})
        
        if notification_prefs.get("email", False) and level in ["warning", "danger"]:
            send_email(message, settings, image_path)
        
        if level in ["warning", "danger", "alert"]:
            system_state = load_state()
            armed_mode = system_state.get('armed_mode', 'disarmed')
            
            if armed_mode != 'disarmed' and not system_state.get('alarm_active', False):
                logging.warning(f"Spúšťa sa alarm na základe notifikácie: {message}")
                update_state({"alarm_active": True})
                play_alarm()
                
                from kivy.clock import Clock
                from functools import partial
                def show_disarm_dialog(dt):
                    try:
                        from kivy.app import App
                        app = App.get_running_app()
                        if hasattr(app, 'sm'):
                            dashboard = app.sm.get_screen('dashboard')
                            if hasattr(dashboard, 'stop_alarm'):
                                dashboard.stop_alarm()
                    except Exception as e:
                        logging.error(f"Nepodarilo sa zobraziť dialóg na deaktiváciu alarmu: {e}")
                
                Clock.schedule_once(show_disarm_dialog, 0.5)
        
        logging.info(f"Notifikácia odoslaná: {message}")
        return True
    except Exception as e:
        logging.error(f"Chyba pri odosielaní notifikácie: {e}")
        return False

def send_email(message, settings=None, image_path=None):
    if settings is None:
        settings = load_settings()
    
    email_config = settings.get("email_settings", {})
    recipient = email_config.get("recipient")
    
    if not recipient:
        logging.warning("Nepodarilo sa odoslať e-mail: Nie je nastavený príjemca")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config.get("username", "security@homesystem.local")
        msg['To'] = recipient
        msg['Subject'] = "Domáci bezpečnostný systém - Upozornenie"
        
        body = f"""
        Domáci bezpečnostný systém - Upozornenie
        
        {message}
        
        Čas: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        """
        
        if image_path is None:
            body += "\n\nŽiadny obrázok nie je k dispozícii."
        else:
            body += "\n\nObrázok z kamery je priložený v prílohe."
            
        msg.attach(MIMEText(body, 'plain'))
        
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as img_file:
                    img_data = img_file.read()
                    
                if image_path.lower().endswith(('.jpg', '.jpeg')):
                    img_attachment = MIMEImage(img_data, _subtype="jpeg")
                else:
                    img_attachment = MIMEBase('application', 'octet-stream')
                    img_attachment.set_payload(img_data)
                    encoders.encode_base64(img_attachment)
                    
                img_filename = os.path.basename(image_path)
                img_attachment.add_header('Content-Disposition', f'attachment; filename="{img_filename}"')
                msg.attach(img_attachment)
                
                logging.info(f"Obrázok {image_path} priložený k e-mailu")
            except Exception as e:
                logging.error(f"Chyba pri pridávaní obrázka do e-mailu: {e}")
        
        smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
        smtp_port = email_config.get("smtp_port", 587)
        
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        
        username = email_config.get("username", "")
        password = email_config.get("password", "")
        
        if not username or not password:
            logging.warning("Nepodarilo sa odoslať e-mail: Chýba používateľské meno alebo heslo")
            return False
        
        server.login(username, password)
        text = msg.as_string()
        server.sendmail(username, recipient, text)
        server.quit()
        
        logging.info(f"E-mail úspešne odoslaný na adresu: {recipient}" + 
                    (f" s prílohou {image_path}" if image_path else ""))
        return True
    except Exception as e:
        logging.error(f"Chyba pri odosielaní e-mailu: {e}")
        return False

def start_sensor_monitoring():
    global _monitoring_active, _monitoring_thread
    
    if _monitoring_active:
        return
    
    _monitoring_active = True
    _monitoring_thread = threading.Thread(target=_monitor_sensors_loop, daemon=True)
    _monitoring_thread.start()
    
    logging.info("Monitorovanie senzorov spustené")
    return True

def stop_sensor_monitoring():
    global _monitoring_active
    
    _monitoring_active = False
    logging.info("Monitorovanie senzorov zastavené")
    return True

def _monitor_sensors_loop():
    global _monitoring_active, _last_sensor_states
    
    while _monitoring_active:
        try:
            system_state = load_state()
            armed_mode = system_state.get('armed_mode', 'disarmed')
            
            if armed_mode != 'disarmed':
                _check_sensor_triggers(armed_mode)
            
            time.sleep(1)
        except Exception as e:
            logging.error(f"Chyba v monitorovacej slučke senzorov: {e}")
            time.sleep(5)

def _check_sensor_triggers(armed_mode):
    global _last_sensor_states
    
    try:
        device_status_path = os.path.join(os.path.dirname(__file__), '../data/device_status.json')
        
        if not os.path.exists(device_status_path):
            return
        
        with open(device_status_path, 'r', encoding='utf-8') as f:
            current_states = json.load(f)
        
        if not _last_sensor_states:
            _last_sensor_states = current_states.copy()
            return
            
        for device_id, device_data in current_states.items():
            if not isinstance(device_data, dict):
                continue
                
            trigger_alarm = False
            trigger_message = None
            room_name = device_data.get('room', device_id)
            device_name = device_data.get('device_name', device_id)
            
            if 'motion' in device_data and device_data['motion'] == 'DETECTED':
                if armed_mode == 'armed_away':
                    if device_id not in _last_sensor_states or _last_sensor_states[device_id].get('motion') != 'DETECTED':
                        logging.info(f"Pohyb detegovaný pre {device_id} v {room_name}")
                        trigger_alarm = True
                        trigger_message = f"Zaznamenaný pohyb v miestnosti {room_name} ({device_name})"
            
            if 'door' in device_data and device_data['door'] == 'OPEN':
                if device_id not in _last_sensor_states or _last_sensor_states[device_id].get('door') != 'OPEN':
                    logging.info(f"Dvere otvorené pre {device_id} v {room_name}")
                    trigger_alarm = True
                    trigger_message = f"Otvorené dvere v miestnosti {room_name} ({device_name})"
            
            if 'window' in device_data and device_data['window'] == 'OPEN':
                if device_id not in _last_sensor_states or _last_sensor_states[device_id].get('window') != 'OPEN':
                    logging.info(f"Otvorené okno v miestnosti pre {device_id} in {room_name}")
                    trigger_alarm = True
                    trigger_message = f"Otvorené okno v miestnosti {room_name} ({device_name})"
            
            if trigger_alarm and trigger_message:
                system_state = load_state()
                
                if (_alarm_countdown_active or system_state.get('alarm_countdown_active', False)) and not _alarm_active:
                    logging.warning(f"Dodatočná udalosť počas odpočítavania: {trigger_message}")
                    add_alert(f"Dodatočná udalosť počas odpočítavania: {trigger_message}", level="warning")
                    
                    update_additional_trigger_message(trigger_message)
                
                elif (not system_state.get('alarm_active', False) and 
                    not system_state.get('alarm_countdown_active', False) and
                    not _alarm_countdown_active and not _alarm_active):
                    logging.warning(f"Spúšťa sa odpočítavanie alarmu: {trigger_message}")
                    start_alarm_countdown(trigger_message)
        
        _last_sensor_states = current_states.copy()
        
    except Exception as e:
        logging.error(f"Chyba pri kontrole senzorov: {e}")
        import traceback
        logging.error(traceback.format_exc())

def add_alert(message, level="info", image_path=None):
    return add_alert_log(message, level, image_path)

def start_alarm_countdown(trigger_message):
    global _alarm_countdown_active, _alarm_countdown_thread, _alarm_countdown_deadline, _alarm_trigger_message
    
    if _alarm_countdown_active:
        return False
    
    if _alarm_active:
        return False
        
    try:
        _alarm_countdown_active = True
        _alarm_countdown_deadline = time.time() + _alarm_countdown_duration
        _alarm_trigger_message = trigger_message
        
        update_state({
            "alarm_countdown_active": True,
            "alarm_countdown_deadline": _alarm_countdown_deadline,
            "alarm_trigger_message": trigger_message
        })
        
        countdown_message = f"POZOR: {trigger_message}. Máte {_alarm_countdown_duration} sekúnd na deaktiváciu systému."
        add_alert(countdown_message, level="warning")
        
        _alarm_countdown_thread = threading.Thread(target=_monitor_alarm_countdown, daemon=True)
        _alarm_countdown_thread.start()
        
        logging.info(f"Spustené odpočítavanie alarmu: {_alarm_countdown_duration} sekúnd")
        
        try:
            from kivy.clock import Clock

            def show_disarm_dialog(dt):
                try:
                    from kivy.app import App
                    app = App.get_running_app()
                    if hasattr(app, 'sm'):
                        dashboard = app.sm.get_screen('dashboard')
                        if hasattr(dashboard, 'stop_alarm'):
                            logging.info("Zobrazujem dialóg pre deaktiváciu alarmu")
                            app.sm.current = 'dashboard'
                            dashboard.stop_alarm()
                        else:
                            logging.error("Metóda stop_alarm na dashboard obrazovke nie je dostupná")
                    else:
                        logging.error("Screen manager 'sm' nie je dostupný v aplikácii")
                except Exception as e:
                    logging.error(f"Zlyhalo zobrazenie dialógu pre deaktiváciu: {e}")
            
            Clock.schedule_once(show_disarm_dialog, 0.5)
            
        except Exception as e:
            logging.error(f"Chyba pri zobrazovaní dialógu pre deaktiváciu: {e}")
        
        return True
    except Exception as e:
        logging.error(f"Chyba pri spúšťaní odpočítavania alarmu: {e}")
        return False

def stop_alarm_countdown():
    global _alarm_countdown_active, _alarm_countdown_deadline, _alarm_trigger_message
    
    try:
        _alarm_countdown_active = False
        _alarm_countdown_deadline = None
        _alarm_trigger_message = None
        
        update_state({
            "alarm_countdown_active": False,
            "alarm_countdown_deadline": None,
            "alarm_trigger_message": None
        })
        
        logging.info("Odpočítavanie alarmu zastavené")
        return True
    except Exception as e:
        logging.error(f"Chyba pri zastavovaní odpočítavania alarmu: {e}")
        return False

def _monitor_alarm_countdown():
    global _alarm_countdown_active, _alarm_countdown_deadline, _alarm_trigger_message
    
    while _alarm_countdown_active and time.time() < _alarm_countdown_deadline:
        remaining = max(0, int(_alarm_countdown_deadline - time.time()))
        update_state({"alarm_countdown_remaining": remaining})
        time.sleep(1)
    
    if _alarm_countdown_active:
        logging.warning("Odpočítavanie ukončené, spúšťa sa alarm")
        
        _alarm_countdown_active = False
        update_state({"alarm_countdown_active": False})
        
        trigger_message = _alarm_trigger_message or "Nedeaktivovaný alarm po odpočítavaní"
        send_notification(f"ALARM: {trigger_message}", level="danger")
        play_alarm()

def update_additional_trigger_message(new_message):
    global _alarm_trigger_message
    
    if _alarm_trigger_message:
        if new_message not in _alarm_trigger_message:
            _alarm_trigger_message = f"{_alarm_trigger_message}; {new_message}"
            
            update_state({"alarm_trigger_message": _alarm_trigger_message})
            logging.info(f"Aktualizovaná správa o príčine alarmu: {_alarm_trigger_message}")
    else:
        _alarm_trigger_message = new_message
        update_state({"alarm_trigger_message": _alarm_trigger_message})
        
    return _alarm_trigger_message

def sync_state_from_system():
    global _alarm_active, _alarm_countdown_active, _alarm_countdown_deadline, _alarm_trigger_message
    
    try:
        system_state = load_state()
        
        _alarm_active = system_state.get("alarm_active", False)
        _alarm_countdown_active = system_state.get("alarm_countdown_active", False)
        _alarm_countdown_deadline = system_state.get("alarm_countdown_deadline", None)
        _alarm_trigger_message = system_state.get("alarm_trigger_message", None)
        
        logging.info("Interný stav synchronizovaný so systémovým súborom stavu")
        return True
    except Exception as e:
        logging.error(f"Chyba pri synchronizácii stavov: {e}")
        return False

def find_latest_image(device_id=None):
    images_dir = os.path.join(os.path.dirname(__file__), '../data/images')
    
    if not os.path.exists(images_dir):
        return None
        
    device_images = []
    for filename in os.listdir(images_dir):
        if filename.endswith('.jpg'):
            if device_id is not None and not filename.startswith(f"{device_id}_"):
                continue
                
            image_path = os.path.join(images_dir, filename)
            timestamp = os.path.getmtime(image_path)
            device_images.append((image_path, timestamp))
    
    if device_images:
        device_images.sort(key=lambda x: x[1], reverse=True)
        return device_images[0][0]
        
    return None
