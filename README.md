# 🏠 Home Security System

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.7%2B-brightgreen.svg)](https://www.python.org/)
[![Kivy](https://img.shields.io/badge/Kivy-Framework-orange.svg)](https://kivy.org/)
[![Flask](https://img.shields.io/badge/Flask-Framework-green.svg)](https://flask.palletsprojects.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Protocol-yellow.svg)](https://mqtt.org/)

> Komplexný bezpečnostný systém pre monitorovanie a správu zabezpečenia domácnosti s využitím IoT zariadení.

## 📋 Obsah
- [Prehľad projektu](#prehľad-projektu)
- [Funkcie](#funkcie)
- [Architektúra systému](#architektúra-systému)
- [Požiadavky](#požiadavky)
- [Inštalácia](#inštalácia)
- [Konfigurácia](#konfigurácia)
- [Spustenie](#spustenie)
- [API dokumentácia](#api-dokumentácia)
- [Štruktúra projektu](#štruktúra-projektu)
- [Prispievanie](#prispievanie)
- [Licencia](#licencia)
- [Kontakt](#kontakt)

## 📝 Prehľad projektu
Tento domáci bezpečnostný systém umožňuje komplexné monitorovanie a správu zabezpečenia pomocou rôznych modulov. Systém integruje Raspberry Pi a ESP zariadenia pre zber dát zo senzorov a poskytuje užívateľské rozhranie cez desktop aplikáciu aj webové rozhranie.

## ✨ Funkcie
- 🔐 Monitorovanie bezpečnostných senzorov v reálnom čase
- 🔔 Notifikácie pri detekcii narušenia
- 📊 Dashboard pre prehľadnú vizualizáciu stavu systému
- 📱 Mobilné a webové rozhranie pre vzdialený prístup
- 📈 História udalostí a generovanie reportov
- 🔧 Konfigurovateľné nastavenia a pravidlá

## 🏗️ Architektúra systému
Systém sa skladá z troch hlavných modulov:

- **SEND modul** (Raspberry Pi, Python) - Zber a odosielanie senzorických dát z fyzického zariadenia
- **ESP_SEND modul** (ESP8266/ESP32, Arduino) - Alternatívny hardvérový zber dát z mikrokontrolérov
- **REC modul** (Python Kivy/Flask) - Užívateľské rozhranie a spracovanie dát v desktop a webovej verzii

Komunikácia medzi modulmi prebieha cez protokol MQTT, čo zabezpečuje rýchlu a spoľahlivú výmenu dát.

## 📋 Požiadavky
- Python 3.7+
- Raspberry Pi 3/4 (pre SEND modul)
- ESP8266/ESP32 (pre ESP_SEND modul)
- MQTT Broker (napr. Mosquitto)
- Kivy (pre desktop aplikáciu)
- Flask (pre webovú aplikáciu)
- Senzory (pohybové, teplotné, atď. podľa konfigurácie)

## 🔧 Inštalácia

### Príprava prostredia
```bash
# Klonovanie repozitára
git clone https://github.com/username/home-security-system.git
cd home-security-system
```

### SEND modul (Raspberry Pi)
```bash
# Inštalácia závislostí
pip install -r SEND/requirements.txt

# Inštalácia MQTT broker (ak ešte nie je)
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service
```

### REC modul (Desktop/Web)
```bash
# Inštalácia závislostí
pip install -r REC/requirements.txt
```

### ESP_SEND modul
1. Nainštalujte Arduino IDE z [arduino.cc](https://www.arduino.cc/en/software)
2. Nainštalujte podporu pre ESP8266/ESP32 cez Board Manager
3. Nainštalujte potrebné knižnice:
   - PubSubClient
   - ArduinoJson
   - WiFiManager

Podrobné inštalačné pokyny nájdete v [install_instructions.md](install_instructions.md).

## ⚙️ Konfigurácia
Nastavenia konfigurácie sú dostupné v nasledujúcich súboroch:

- `SEND/config.json` - Konfigurácia senzorov a MQTT pripojenia pre Raspberry Pi
- `ESP_SEND/ESP_SEND.ino` - Nastavenia siete a MQTT pre ESP zariadenia
- `data/mqtt_config.json` - Nastavenia MQTT brokera
- `data/settings.json` - Všeobecné nastavenia systému
- `data/devices.json` - Zoznam a konfigurácia zariadení

### Príklad konfigurácie MQTT
```json
{
  "broker": "localhost",
  "port": 1883,
  "username": "user",
  "password": "password",
  "topic_prefix": "home/security/"
}
```

## 🚀 Spustenie

### SEND modul (Raspberry Pi)
```bash
# Spustenie hlavného programu
python SEND/SEND.py

# Spustenie v testovacom režime
python SEND/TESTER.py
```

### REC modul
- Desktop verzia:
  ```bash
  python REC/main.py
  ```
- Webová verzia:
  ```bash
  python REC/web_app.py
  ```
  Následne otvorte prehliadač na adrese http://localhost:5000
  Alebo otvorte prehliadač na adrese http://(IP-Rec_jednotka):5000

### ESP_SEND modul
1. Otvorte súbor `ESP_SEND/ESP_SEND.ino` v Arduino IDE
2. Nakonfigurujte nastavenia siete v kóde
3. Nahrajte kód do ESP zariadenia
4. Pre testovanie použite `ESP_SEND/ESP_TESTER.ino`

## 📚 API dokumentácia
Webová aplikácia poskytuje API pre integráciu s inými systémami. Dokumentáciu API nájdete v [technical_documentation.md](technical_documentation.md).

## 📁 Štruktúra projektu
```
├── SEND/              # Raspberry Pi senzorický modul
│   ├── SEND.py        # Hlavný program pre zber dát
│   ├── TESTER.py      # Testovací program
│   └── config.json    # Konfiguračný súbor
├── ESP_SEND/          # ESP8266/ESP32 senzorický modul
│   ├── ESP_SEND.ino   # Hlavný program pre ESP
│   └── ESP_TESTER.ino # Testovací program
├── REC/               # Prijímací modul
│   ├── config/        # Konfiguračné moduly
│   ├── templates/     # HTML šablóny pre web
│   ├── sounds/        # Zvukové notifikácie
│   ├── main.py        # Hlavný program desktop aplikácie
│   └── web_app.py     # Webová aplikácia
├── data/              # Dátové súbory
│   ├── alerts.log     # História upozornení
│   ├── device_status.json # Stav zariadení
│   └── settings.json  # Nastavenia
├── LICENSE            # Licenčný súbor
└── install_instructions.md # Podrobné pokyny na inštaláciu
```

## 🤝 Prispievanie
Príspevky sú vítané! Ak chcete prispieť:

1. Vytvorte fork tohto repozitára
2. Vytvorte svoju feature branch (`git checkout -b feature/amazing-feature`)
3. Commit-nite vaše zmeny (`git commit -m 'Add amazing feature'`)
4. Push do branch-e (`git push origin feature/amazing-feature`)
5. Otvorte Pull Request

## 📄 Licencia
Tento projekt je distribuovaný pod licenciou MIT. Pre viac informácií si pozrite súbor [LICENSE](LICENSE).

## 📞 Kontakt
Branislav Hýll - [hyll@hylllab.eu](mailto:hyll@hylllab.eu)

Project Link: [https://github.com/Hyller/home-security-system](https://github.com/Hyller/home-security-system)

---

*© 2025 Home Security System. Všetky práva vyhradené.*
