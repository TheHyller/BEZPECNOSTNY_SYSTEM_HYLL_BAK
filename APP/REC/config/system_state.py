# system_state.py - Správa stavu systému
import json
import os
import logging
from datetime import datetime

# Cesta k súboru so stavom systému
STATE_FILE = os.path.join(os.path.dirname(__file__), '../../data/system_state.json')

# Výchozí stav systému
DEFAULT_STATE = {
    "system_activated": False,
    "armed_mode": "disarmed",  # disarmed, armed_home, armed_away
    "alarm_active": False,
    "alarm_triggered": False,
    "grace_period": False,
    "failed_attempts": 0,
    "last_updated": datetime.now().isoformat()
}

def ensure_state_file_exists():
    """Zabezpečí, že súbor so stavom existuje a má správnu štruktúru."""
    try:
        # Skontrolujeme, či existuje adresár
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        
        # Skontrolujeme, či existuje súbor
        if not os.path.exists(STATE_FILE):
            # Ak nie, vytvoríme ho s predvoleným stavom
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_STATE, f, ensure_ascii=False, indent=2)
            logging.info(f"Vytvorený nový súbor stavu systému: {STATE_FILE}")
            return True
        
        return True
    except Exception as e:
        logging.error(f"Chyba pri kontrole/vytváraní súboru stavu: {e}")
        return False

def load_state():
    """Načíta aktuálny stav systému zo súboru."""
    try:
        # Zabezpečíme, že súbor existuje
        ensure_state_file_exists()
        
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        # Zabezpečiť, že všetky potrebné kľúče existujú
        for key, value in DEFAULT_STATE.items():
            if key not in state:
                state[key] = value
        
        return state
    except Exception as e:
        logging.error(f"Chyba pri načítaní stavu systému: {e}")
        # V prípade chyby vrátime predvolený stav
        return DEFAULT_STATE.copy()

def save_state(state):
    """Uloží stav systému do súboru."""
    try:
        # Zabezpečíme, že adresár existuje
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Chyba pri ukladaní stavu systému: {e}")
        return False

def update_state(updates):
    """Aktualizuje stav systému špecifickými hodnotami."""
    try:
        state = load_state()
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(state.get(key, {}), dict):
                # Ak je hodnota slovník, vykonať vnorené zlúčenie
                state[key] = {**state.get(key, {}), **value}
            else:
                # Inak jednoducho aktualizovať hodnotu
                state[key] = value
        
        # Pridať časovú značku poslednej aktualizácie
        state['last_updated'] = datetime.now().isoformat()
        
        save_state(state)
        return state
    except Exception as e:
        logging.error(f"Chyba pri aktualizácii stavu systému: {e}")
        return None

def set_lockout(seconds):
    """Nastaví lockout systému na určený počet sekúnd."""
    try:
        state = load_state()
        until = (datetime.now().timestamp() + seconds)
        state['lockout_until'] = until
        save_state(state)
        return True
    except Exception as e:
        logging.error(f"Chyba pri nastavovaní lockout: {e}")
        return False

def is_locked_out():
    """Kontroluje, či je systém v stave lockout."""
    try:
        state = load_state()
        until = state.get('lockout_until')
        if until is None:
            return False
        return datetime.now().timestamp() < until
    except Exception as e:
        logging.error(f"Chyba pri kontrole lockout stavu: {e}")
        return False
