# notification_service.py - Služba pre notifikácie a alarmy
import os
import threading
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from config.system_state import load_state, update_state
from config.settings import load_settings
from config.alerts_log import add_alert_log, get_recent_alerts

# Konfigurácia logovania
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s"
)

# Cesta k zvukovému súboru alarmu
ALARM_SOUND_FILE = os.path.join(os.path.dirname(__file__), 'sounds/alarm.wav')

# Globálne premenné pre správu alarmu
_alarm_active = False
_alarm_thread = None
_monitoring_thread = None
_monitoring_active = False
_last_sensor_states = {}

def is_alarm_active():
    """Vráti informáciu, či je alarm práve aktívny."""
    return _alarm_active

def play_alarm():
    """Spustí zvukový alarm."""
    global _alarm_active, _alarm_thread
    
    if _alarm_active:
        return  # Alarm už beží
    
    try:
        # Kontrola, či zvukový súbor existuje
        if not os.path.exists(ALARM_SOUND_FILE):
            logging.warning(f"Zvukový súbor alarmu nebol nájdený: {ALARM_SOUND_FILE}")
            return False
        
        # Nastavenie stavu alarmu v systéme
        update_state({"alarm_active": True})
        _alarm_active = True
        
        # Spustenie alarmu v samostatnom vlákne
        _alarm_thread = threading.Thread(target=_alarm_sound_loop, daemon=True)
        _alarm_thread.start()
        
        logging.info("Alarm bol spustený")
        return True
    except Exception as e:
        logging.error(f"Chyba pri spúšťaní alarmu: {e}")
        return False

def stop_alarm():
    """Zastaví zvukový alarm."""
    global _alarm_active
    
    try:
        # Zmena stavu alarmu
        _alarm_active = False
        update_state({"alarm_active": False})
        
        logging.info("Alarm bol zastavený")
        return True
    except Exception as e:
        logging.error(f"Chyba pri zastavení alarmu: {e}")
        return False

def _alarm_sound_loop():
    """Prehráva zvuk alarmu v slučke."""
    global _alarm_active
    
    try:
        import pygame
        pygame.mixer.init()
        alarm_sound = pygame.mixer.Sound(ALARM_SOUND_FILE)
        
        # Prehrávanie zvuku, kým je alarm aktívny
        while _alarm_active:
            alarm_sound.play()
            time.sleep(2)  # Čakanie medzi prehrávaniami
    except ImportError:
        logging.error("Knižnica pygame nie je nainštalovaná. Zvukový alarm nebude prehrávať.")
        # Alternatívny zvukový alarm pomocou operačného systému
        try:
            if os.name == "nt":  # Windows
                import winsound
                while _alarm_active:
                    winsound.Beep(1000, 500)
                    winsound.Beep(800, 500)
                    time.sleep(1)
            else:
                # Na Linuxe/Mac by sme mohli použiť iný spôsob, ale zatiaľ len logujeme
                logging.warning("Zvukový alarm nie je dostupný na tejto platforme bez pygame.")
        except Exception as e:
            logging.error(f"Chyba pri prehrávaní alternatívneho zvuku alarmu: {e}")
    except Exception as e:
        logging.error(f"Chyba pri prehrávaní zvuku alarmu: {e}")

def send_notification(message, level="info", image_path=None):
    """Odosiela notifikáciu užívateľovi."""
    try:
        # Pridanie do logu upozornení
        add_alert_log(message, level, image_path)
        
        # Kontrola nastavení pre notifikácie
        settings = load_settings()
        notification_prefs = settings.get("notification_preferences", {})
        
        # Ak sú povolené e-mailové notifikácie a ide o dôležitú notifikáciu
        if notification_prefs.get("email", False) and level in ["warning", "danger"]:
            send_email(message, settings)
        
        logging.info(f"Notifikácia odoslaná: {message}")
        return True
    except Exception as e:
        logging.error(f"Chyba pri odosielaní notifikácie: {e}")
        return False

def send_email(message, settings=None):
    """Odošle e-mail s upozornením."""
    if settings is None:
        settings = load_settings()
    
    email_config = settings.get("email_config", {})
    recipient = email_config.get("recipient")
    
    # Ak nie je nastavený príjemca, nemôžeme poslať e-mail
    if not recipient:
        logging.warning("Nepodarilo sa odoslať e-mail: Nie je nastavený príjemca")
        return False
    
    try:
        # Vytvorenie MIME správy
        msg = MIMEMultipart()
        msg['From'] = email_config.get("username", "security@homesystem.local")
        msg['To'] = recipient
        msg['Subject'] = "Domáci bezpečnostný systém - Upozornenie"
        
        body = f"""
        Domáci bezpečnostný systém - Upozornenie
        
        {message}
        
        Čas: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Nastavenie SMTP servera
        server = smtplib.SMTP(
            email_config.get("smtp_server", "smtp.gmail.com"),
            email_config.get("smtp_port", 587)
        )
        server.starttls()
        
        # Prihlásenie a odoslanie e-mailu
        server.login(
            email_config.get("username", ""),
            email_config.get("password", "")
        )
        text = msg.as_string()
        server.sendmail(
            email_config.get("username", ""),
            recipient,
            text
        )
        server.quit()
        
        logging.info(f"E-mail odoslaný na adresu: {recipient}")
        return True
    except Exception as e:
        logging.error(f"Chyba pri odosielaní e-mailu: {e}")
        return False

def start_sensor_monitoring():
    """Spustí monitorovanie senzorov pre alarm."""
    global _monitoring_active, _monitoring_thread
    
    if _monitoring_active:
        return  # Monitorovanie už beží
    
    _monitoring_active = True
    _monitoring_thread = threading.Thread(target=_monitor_sensors_loop, daemon=True)
    _monitoring_thread.start()
    
    logging.info("Monitorovanie senzorov spustené")
    return True

def stop_sensor_monitoring():
    """Zastaví monitorovanie senzorov."""
    global _monitoring_active
    
    _monitoring_active = False
    logging.info("Monitorovanie senzorov zastavené")
    return True

def _monitor_sensors_loop():
    """Hlavná slučka pre monitorovanie senzorov."""
    global _monitoring_active, _last_sensor_states
    
    while _monitoring_active:
        try:
            # Načítanie stavu systému
            system_state = load_state()
            armed_mode = system_state.get('armed_mode', 'disarmed')
            
            # Ak je systém zabezpečený, kontrolujeme senzory
            if armed_mode != 'disarmed':
                _check_sensor_triggers(armed_mode)
            
            # Čakáme 1 sekundu pred ďalšou kontrolou
            time.sleep(1)
        except Exception as e:
            logging.error(f"Chyba v monitorovacej slučke senzorov: {e}")
            time.sleep(5)  # Dlhšie čakanie v prípade chyby

def _check_sensor_triggers(armed_mode):
    """Kontroluje senzory a spúšťa alarm v prípade potreby."""
    global _last_sensor_states
    
    try:
        # Cesta k súboru so stavom zariadení
        device_status_path = os.path.join(os.path.dirname(__file__), '../data/device_status.json')
        
        # Ak súbor neexistuje, nemôžeme kontrolovať senzory
        if not os.path.exists(device_status_path):
            return
        
        # Načítanie aktuálneho stavu zariadení
        with open(device_status_path, 'r', encoding='utf-8') as f:
            current_states = json.load(f)
        
        # Kontrola zmien stavu
        for device_id, device_data in current_states.items():
            # Preskakovanie kľúčov, ktoré nie sú zariadenia
            if not isinstance(device_data, dict):
                continue
                
            # Kontrola nových alarmových stavov
            trigger_alarm = False
            trigger_message = None
            room_name = device_data.get('room', device_id)
            
            # Kontrola pohybu - len v režime armed_away
            if 'motion' in device_data and device_data['motion'] == 'DETECTED':
                # V režime Doma ignorujeme pohybové detektory
                if armed_mode == 'armed_away':
                    trigger_alarm = True
                    trigger_message = f"Zaznamenaný pohyb v miestnosti {room_name}"
            
            # Kontrola otvorenia dverí - vždy
            if 'door' in device_data and device_data['door'] == 'OPEN':
                # Kontrola, či to nie je nová správa (zmena stavu)
                if device_id not in _last_sensor_states or _last_sensor_states[device_id].get('door') != 'OPEN':
                    trigger_alarm = True
                    trigger_message = f"Otvorené dvere v miestnosti {room_name}"
            
            # Kontrola otvorenia okna - vždy
            if 'window' in device_data and device_data['window'] == 'OPEN':
                # Kontrola, či to nie je nová správa (zmena stavu)
                if device_id not in _last_sensor_states or _last_sensor_states[device_id].get('window') != 'OPEN':
                    trigger_alarm = True
                    trigger_message = f"Otvorené okno v miestnosti {room_name}"
            
            # Ak bol detekovaný alarm, spustiť ho
            if trigger_alarm and trigger_message:
                system_state = load_state()
                
                # Ak alarm ešte nie je aktívny, aktivujeme ho
                if not system_state.get('alarm_active', False):
                    logging.warning(f"Spúšťa sa alarm: {trigger_message}")
                    send_notification(trigger_message, level="danger")
                    play_alarm()
        
        # Uloženie aktuálnych stavov pre ďalšie porovnanie
        _last_sensor_states = current_states.copy()
        
    except Exception as e:
        logging.error(f"Chyba pri kontrole senzorov: {e}")

def add_alert(message, level="info", image_path=None):
    """Pridá upozornenie do logu upozornení."""
    return add_alert_log(message, level, image_path)
