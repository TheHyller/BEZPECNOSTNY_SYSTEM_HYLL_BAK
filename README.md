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
- [UML dokumentácia](#uml-dokumentácia)
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
- 🔍 Obrazová galéria pre vizuálnu verifikáciu alarmov
- 🔑 Robustný autentifikačný systém s kontrolou prístupu

## 🏗️ Architektúra systému
Systém sa skladá z troch hlavných modulov:

- **SEND modul** (Raspberry Pi, Python) - Zber a odosielanie senzorických dát z fyzického zariadenia
- **ESP_SEND modul** (ESP8266, Arduino) - Alternatívny hardvérový zber dát z mikrokontrolérov
- **REC modul** (Python Kivy/Flask) - Užívateľské rozhranie a spracovanie dát v desktop a webovej verzii

Komunikácia medzi modulmi prebieha cez protokol MQTT, čo zabezpečuje rýchlu a spoľahlivú výmenu dát.

## 📋 Požiadavky
- Python 3.7+
- Raspberry Pi 3/4 (pre SEND modul)
- ESP8266 (pre ESP_SEND modul)
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
pip install -r APP/requirements_pi.txt

# Inštalácia MQTT broker (ak ešte nie je)
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service
```

### REC modul (Desktop/Web)
```bash
# Inštalácia závislostí
pip install -r APP/requirements.txt
```

### ESP_SEND modul
1. Nainštalujte Arduino IDE z [arduino.cc](https://www.arduino.cc/en/software)
2. Nainštalujte podporu pre ESP8266 cez Board Manager
3. Nainštalujte potrebné knižnice:
   - PubSubClient
   - ArduinoJson
   - WiFiManager

Podrobné inštalačné pokyny nájdete v [mosquitto_install.md](mosquitto_install.md) a [install_instructions.md](install_instructions.md).

## ⚙️ Konfigurácia
Nastavenia konfigurácie sú dostupné v nasledujúcich súboroch:

- `APP/SEND/config.json` - Konfigurácia senzorov a MQTT pripojenia pre Raspberry Pi
- `APP/ESP_SEND/ESP_SEND.ino` - Nastavenia siete a MQTT pre ESP zariadenia
- `APP/data/mqtt_config.json` - Nastavenia MQTT brokera
- `APP/data/settings.json` - Všeobecné nastavenia systému
- `APP/data/devices.json` - Zoznam a konfigurácia zariadení
- `APP/mosquitto.conf` - Konfigurácia MQTT brokera Mosquitto

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
python APP/SEND/SEND.py

# Spustenie v testovacom režime
python APP/SEND/TESTER.py

# Automatické spustenie pri štarte systému
./APP/autostart_pi.sh
```

### REC modul
- Desktop verzia:
  ```bash
  python APP/REC/main.py
  
  # Alebo pomocou autostart skriptu
  ./APP/autostart_win.bat
  ```
- Webová verzia:
  ```bash
  python APP/REC/web_app.py
  ```
  Následne otvorte prehliadač na adrese http://localhost:5000 
  Alebo otvorte prehliadač na adrese http://(IP-Rec_jednotka):5000

### ESP_SEND modul
1. Otvorte súbor `APP/ESP_SEND/ESP_SEND.ino` v Arduino IDE
2. Nakonfigurujte nastavenia siete v kóde
3. Nahrajte kód do ESP zariadenia
4. Pre testovanie použite `APP/ESP_SEND/ESP_TESTER.ino`

## 📚 API dokumentácia
Webová aplikácia poskytuje API pre integráciu s inými systémami. Podrobnú dokumentáciu API nájdete v [technicka_dokumentacia.md](technicka_dokumentacia.md).

## 📁 Štruktúra projektu
```
├── APP/                # Hlavný adresár aplikácie obsahujúci všetky moduly systému
│   ├── SEND/           # Raspberry Pi senzorický modul pre monitorovanie bezpečnostných senzorov
│   │   ├── SEND.py     # Hlavný program pre zber a odosielanie dát zo senzorov cez MQTT
│   │   ├── TESTER.py   # Testovací program na simuláciu senzorov bez fyzického hardvéru
│   │   └── config.json # Konfiguračný súbor s nastaveniami senzorov, MQTT a ďalších parametrov
│   ├── ESP_SEND/       # ESP8266 senzorický modul pre alternatívne IoT zariadenia
│   │   ├── ESP_SEND.ino # Hlavný program pre ESP zariadenia na zber a odosielanie dát
│   │   └── ESP_TESTER.ino # Testovací program pre ESP zariadenia bez fyzických senzorov
│   ├── REC/            # Prijímací modul pre spracovanie dát a užívateľské rozhranie
│   │   ├── app.py      # Základná aplikačná logika a definícia aplikačných tried
│   │   ├── main.py     # Hlavný program desktop aplikácie s inicializáciou komponentov
│   │   ├── mqtt_client.py # MQTT klient implementácia pre príjem a odosielanie správ
│   │   ├── mqtt_discovery.py # MQTT objavovací mechanizmus pre automatickú detekciu zariadení
│   │   ├── notification_service.py # Služba pre notifikácie a upozornenia rôznymi kanálmi
│   │   ├── web_app.py  # Webová aplikácia poskytujúca prístup cez webový prehliadač
│   │   ├── alerts_screen.py # Obrazovka upozornení zobrazujúca históriu alarmov
│   │   ├── dashboard_screen.py # Dashboard obrazovka s prehľadom stavu celého systému
│   │   ├── login_screen.py # Prihlasovacia obrazovka pre autentifikáciu užívateľov
│   │   ├── sensor_screen.py # Obrazovka senzorov pre detailnú správu senzorov
│   │   ├── settings_screen.py # Obrazovka nastavení systému a užívateľských preferencií
│   │   ├── theme_helper.py # Pomocník pre témy a vizuálne nastavenia aplikácie
│   │   ├── config/     # Konfiguračné moduly pre správu nastavení systému
│   │   ├── templates/  # HTML šablóny pre webové rozhranie aplikácie
│   │   └── sounds/     # Zvukové notifikácie pre alarmy a upozornenia
│   ├── data/           # Dátové súbory a úložisko pre stav systému
│   │   ├── alerts.log  # História upozornení a bezpečnostných incidentov
│   │   ├── device_status.json # Stav zariadení a ich aktuálne hodnoty
│   │   └── settings.json # Nastavenia celého systému a užívateľské konfigurácie
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

Projekt Link: [https://github.com/Hyller/home-security-system](https://github.com/Hyller/home-security-system)

---
