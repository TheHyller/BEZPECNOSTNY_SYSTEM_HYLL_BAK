# alerts_log.py - Práca s logom upozornení
import os
import json
import time
from datetime import datetime
import logging

# Cesta k súboru s logom upozornení
ALERTS_LOG_FILE = os.path.join(os.path.dirname(__file__), '../../data/alerts.log')

def ensure_log_file_exists():
    """Zabezpečí, že súbor s logom upozornení existuje."""
    try:
        os.makedirs(os.path.dirname(ALERTS_LOG_FILE), exist_ok=True)
        
        if not os.path.exists(ALERTS_LOG_FILE):
            with open(ALERTS_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            return True
        return True
    except Exception as e:
        logging.error(f"Chyba pri vytváraní súboru logu upozornení: {e}")
        return False

def add_alert_log(message, level="info", image_path=None):
    """Pridá nový záznam do logu upozornení."""
    try:
        ensure_log_file_exists()
        
        # Načítanie súčasného logu
        try:
            with open(ALERTS_LOG_FILE, 'r', encoding='utf-8') as f:
                alerts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Ak je súbor prázdny alebo neexistuje, začneme s prázdnym zoznamom
            alerts = []
        
        # Vytvorenie nového záznamu
        new_alert = {
            "timestamp": datetime.now().isoformat(),
            "unix_time": int(time.time()),
            "message": message,
            "level": level,
        }
        
        # Ak je k dispozícii cesta k obrázku, pridáme ju
        if image_path and os.path.exists(image_path):
            new_alert["image_path"] = image_path
        
        # Pridanie na začiatok zoznamu (najnovšie záznamy budú na začiatku)
        alerts.insert(0, new_alert)
        
        # Obmedzenie počtu záznamov (uchováme max. 1000 záznamov)
        max_records = 1000
        if len(alerts) > max_records:
            alerts = alerts[:max_records]
        
        # Zápis aktualizovaného logu
        with open(ALERTS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logging.error(f"Chyba pri pridávaní záznamu do logu upozornení: {e}")
        return False

def get_recent_alerts(count=10, level=None, since=None):
    """Získa najnovšie upozornenia z logu.
    
    Args:
        count (int): Maximálny počet upozornení na vrátenie
        level (str, optional): Filter podľa úrovne závažnosti
        since (int, optional): Unix timestamp; vráti iba upozornenia novšie ako tento čas
        
    Returns:
        list: Zoznam upozornení
    """
    try:
        ensure_log_file_exists()
        
        try:
            with open(ALERTS_LOG_FILE, 'r', encoding='utf-8') as f:
                alerts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        
        # Aplikovanie filtrov
        if level:
            alerts = [alert for alert in alerts if alert.get('level') == level]
            
        if since:
            alerts = [alert for alert in alerts if alert.get('unix_time', 0) > since]
        
        # Obmedzenie počtu záznamov
        return alerts[:count]
    except Exception as e:
        logging.error(f"Chyba pri získavaní upozornení: {e}")
        return []

def clear_alerts():
    """Vymaže všetky upozornenia z logu."""
    try:
        with open(ALERTS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Chyba pri čistení logu upozornení: {e}")
        return False

def get_alerts_by_level(level, count=None):
    """Získa upozornenia podľa úrovne závažnosti."""
    try:
        ensure_log_file_exists()
        
        with open(ALERTS_LOG_FILE, 'r', encoding='utf-8') as f:
            alerts = json.load(f)
        
        filtered_alerts = [alert for alert in alerts if alert.get('level') == level]
        
        if count:
            filtered_alerts = filtered_alerts[:count]
            
        return filtered_alerts
    except Exception as e:
        logging.error(f"Chyba pri získavaní upozornení podľa úrovne: {e}")
        return []
