# devices_manager.py - Správa zariadení
import json
import os
from datetime import datetime

# Opravená cesta k súboru - pridané os.path.join a os.path.dirname
DEVICES_FILE = os.path.join(os.path.dirname(__file__), '../../data/devices.json')
DEVICE_STATUS_FILE = os.path.join(os.path.dirname(__file__), '../../data/device_status.json')

def load_devices():
    with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_devices(devices):
    with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)

def load_device_status():
    """Načíta stav zariadení zo súboru."""
    try:
        with open(DEVICE_STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Ak súbor neexistuje alebo je poškodený, vytvorí nový
        return {}

def save_device_status(status_data):
    """Uloží stav zariadení do súboru."""
    # Uistí sa, že adresár existuje
    os.makedirs(os.path.dirname(DEVICE_STATUS_FILE), exist_ok=True)
    
    with open(DEVICE_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status_data, f, ensure_ascii=False, indent=2)

def update_device_status(device_status_update):
    """
    Aktualizuje stav zariadenia a ukladá ho do súboru
    
    Args:
        device_status_update (dict): Slovník so stavmi zariadení na aktualizáciu
                                    vo formáte {device_id: {sensor_type: status}}
    """
    status_data = load_device_status()
    
    # Aktualizácia už existujúcich zariadení
    for device_id, device_info in device_status_update.items():
        if device_id not in status_data:
            status_data[device_id] = {}
        
        # Aktualizácia stavu a času poslednej aktualizácie
        if isinstance(device_info, dict):
            # Aktualizácia všetkých hodnôt zo slovníka
            for key, value in device_info.items():
                status_data[device_id][key] = value
        else:
            # Ak je device_info priamo hodnota (string), považujeme ju za stav
            status_data[device_id]['status'] = device_info
        
        status_data[device_id]['last_update'] = datetime.now().isoformat()
    
    save_device_status(status_data)
    return status_data

# Zachovanie kompatibility so starým formátom
def update_device_status_old(device_id, status, data=None):
    """
    Aktualizuje stav zariadenia a ukladá ho do súboru (pôvodný formát)
    
    Args:
        device_id (str): ID zariadenia
        status (str): Stav zariadenia (online/offline/alert)
        data (dict, optional): Doplnkové dáta zo senzora
    """
    status_data = load_device_status()
    
    if device_id not in status_data:
        status_data[device_id] = {}
    
    status_data[device_id]['status'] = status
    status_data[device_id]['last_update'] = datetime.now().isoformat()
    
    if data:
        status_data[device_id]['data'] = data
    
    save_device_status(status_data)
    return status_data
