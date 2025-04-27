# Inštalačné pokyny pre bezpečnostný systém

## Požiadavky
- Python 3.8 alebo novší
- Pripojenie na internet pre inštaláciu balíčkov
- Pre ESP moduly: Arduino IDE

## Inštalácia na Windows (prijímač/REC)

1. **Inštalácia Python závislostí**
   ```bash
   # Prejdite do priečinka projektu
   cd cesta/k/priečinku

   # Inštalácia závislostí
   pip install -r requirements.txt
   ```

2. **Inštalácia a konfigurácia MQTT brokera**
   - Stiahnite a nainštalujte Mosquitto broker z [oficiálnej stránky](https://mosquitto.org/download/)
   - Po inštalácii upravte konfiguračný súbor (zvyčajne v `C:\Program Files\mosquitto\mosquitto.conf`):
   ```
   listener 1883
   allow_anonymous true
   ```
   - Spustite Mosquitto broker ako službu:
   ```bash
   # Inštalácia služby (spustiť ako administrátor)
   net start mosquitto
   # Alebo pre ručné spustenie
   "C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Program Files\mosquitto\mosquitto.conf"
   ```
   - Overte, či broker beží správne:
   ```bash
   # Prihlásenie na odber správ (v prvom termináli)
   mosquitto_sub -h localhost -t "test/topic"
   
   # Odoslanie testovacej správy (v druhom termináli)
   mosquitto_pub -h localhost -t "test/topic" -m "Test správa"
   ```

3. **Inštalácia dodatočných nástrojov pre audio**
   - Pre správne prehrávanie zvuku pomocou knižnice `playsound` môže byť potrebné nainštalovať:
     - PyAudio: `pip install PyAudio`
     - Ak vzniknú problémy, stiahnite si inštalátor z [Neoficiálnych Windows binárnych súborov](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)

4. **Spustenie prijímača**
   ```bash
   # Spustenie Kivy aplikácie
   python REC/main.py
   
   # Spustenie webovej aplikácie samostatne (voliteľné)
   python REC/web_app.py
   ```

## Inštalácia na Raspberry Pi (odosielateľ/SEND)

1. **Aktualizácia systému**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

2. **Inštalácia potrebných nástrojov**
   ```bash
   sudo apt install -y python3-pip python3-dev
   ```

3. **Inštalácia MQTT brokera**
   ```bash
   # Inštalácia Mosquitto brokera
   sudo apt install -y mosquitto mosquitto-clients
   
   # Nastavenie automatického spustenia
   sudo systemctl enable mosquitto.service
   
   # Konfigurácia brokera
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
   Pridajte nasledujúce riadky do súboru:
   ```
   listener 1883
   allow_anonymous true
   ```
   
   Potom reštartujte službu:
   ```bash
   sudo systemctl restart mosquitto
   ```
   
   Overte správne fungovanie:
   ```bash
   # Odber správ (v prvom termináli)
   mosquitto_sub -h localhost -t "test/topic"
   
   # Publikovanie správ (v druhom termináli)
   mosquitto_pub -h localhost -t "test/topic" -m "Test správa"
   ```

4. **Inštalácia Python závislostí**
   ```bash
   # Prejdite do priečinka projektu
   cd cesta/k/priečinku

   # Inštalácia závislostí
   pip3 install -r requirements_pi.txt
   ```

5. **Nastavenie autorizácií pre hardvérový prístup**
   ```bash
   # Pridanie užívateľa do potrebných skupín pre kameru a GPIO
   sudo usermod -a -G gpio,video $USER
   ```

6. **Konfigurácia**
   - Upravte súbor `SEND/config.json` podľa vašich potrebných nastavení
   - Skontrolujte čísla GPIO pinov pre pripojené senzory

7. **Spustenie testovacieho programu**
   ```bash
   # Spustenie testovacieho programu bez fyzických senzorov
   python3 SEND/TESTER.py
   ```

8. **Nastavenie automatického spustenia pri štarte systému**
   ```bash
   # Otvorenie crontab
   crontab -e
   
   # Pridajte nasledujúci riadok pre automatické spustenie pri štarte
   @reboot python3 /cesta/k/priečinku/SEND/SEND.py &
   ```

## Inštalácia na ESP8266/ESP32 (odosielateľ)

1. **Nastavenie Arduino IDE**
   - Nainštalujte Arduino IDE z [oficiálnej stránky](https://www.arduino.cc/en/software)
   - Pridajte správcu dosiek ESP:
     - Prejdite na Súbor > Nastavenia
     - Do poľa "Dodatočné URL správcov dosiek" pridajte:
       - Pre ESP8266: `http://arduino.esp8266.com/stable/package_esp8266com_index.json`
       - Pre ESP32: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Nainštalujte dosku cez Nástroje > Doska > Správca dosiek
     - Vyhľadajte ESP8266 alebo ESP32 a nainštalujte

2. **Inštalácia potrebných knižníc**
   - Prejdite na Nástroje > Spravovať knižnice
   - Nainštalujte nasledujúce knižnice:
     - ArduinoJson
     - ESP8266WiFi (pre ESP8266) alebo WiFi (pre ESP32)
     - **PubSubClient** (pre MQTT komunikáciu)

3. **Nahratie kódu**
   - Otvorte súbor `ESP_SEND/ESP_SEND.ino` alebo `ESP_SEND/ESP_TESTER.ino`
   - Upravte SSID a heslo pre vašu WiFi sieť
   - Skontrolujte nastavenia pre vašu miestnosť a typ zariadenia
   - **Upravte MQTT broker IP adresu a port**
   - Vyberte správnu dosku a port z menu Nástroje
   - Nahrajte kód do zariadenia

## Riešenie problémov

### Windows
- **Problém s audio knižnicami**: Ak máte problémy s prehrávaním zvuku, skúste:
  ```bash
  pip uninstall playsound
  pip install playsound==1.2.2
  ```

- **Chyba pri spustení Kivy**: Ak sa Kivy nespúšťa správne:
  - Skontrolujte, či máte nainštalované všetky závislosti
  - Skúste nainštalovať binárne balíčky pre Windows: `pip install kivy[full]`

- **MQTT broker sa nedá spustiť**: Ak máte problémy so spustením Mosquitto:
  - Skontrolujte, či nie je blokovaný port 1883 (môžete zmeniť port v konfigurácii)
  - Skontrolujte firewall nastavenia a povoľte komunikáciu na porte 1883
  - Skontrolujte chybové logy: `C:\Program Files\mosquitto\mosquitto.log`

### Raspberry Pi
- **GPIO chyby**: Uistite sa, že aplikácia beží s dostatočnými oprávneniami:
  ```bash
  sudo python3 SEND/SEND.py
  ```

- **Problémy s kamerou**: Ak PiCamera nefunguje:
  - Skontrolujte, či je kamera pripojená správne
  - Povoľte kameru cez `sudo raspi-config` > Interfacing Options > Camera
  - Reštartujte Pi: `sudo reboot`

- **MQTT problémy**: Ak máte problémy s MQTT komunikáciou:
  - Overte, či beží broker: `systemctl status mosquitto`
  - Skontrolujte sieťové nastavenia a firewall
  - Otestujte komunikáciu pomocou `mosquitto_pub` a `mosquitto_sub` nástrojov

### ESP
- **Problémy s WiFi pripojením**: Skontrolujte, či sú SSID a heslo správne
- **Neprijímanie odpovedí**: Uistite sa, že UDP porty nie sú blokované firewallom
- **MQTT problémy**: 
  - Skontrolujte, či je správna IP adresa MQTT brokera
  - Veľkosť bufferu v PubSubClient môže byť potrebné upraviť pre dlhšie správy
  - Použite sériový monitor na diagnostiku pripojenia