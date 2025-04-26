# settings.py - Správa nastavení
import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '../../data/settings.json')

def load_settings():
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
