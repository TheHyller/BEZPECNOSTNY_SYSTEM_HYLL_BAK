# Návod na inštaláciu MQTT brokera Mosquitto

Tento návod vysvetľuje, ako nainštalovať a nakonfigurovať MQTT broker Mosquitto pre Bezpečnostný Systém.

## Inštalačné pokyny

### Windows

1. Stiahnite inštalátor Mosquitto z oficiálnej stránky:
   - Navštívte [https://mosquitto.org/download/](https://mosquitto.org/download/)
   - Stiahnite najnovší Windows inštalátor (odporúča sa 64-bitová verzia)

2. Spustite inštalátor:
   - Prijmite licenčnú zmluvu
   - Vyberte "Úplnú" inštaláciu
   - Keď budete vyzvaní, nainštalujte službu a pridajte do cesty

3. Po inštalácii:
   - Mosquitto bude nainštalovaný ako služba systému Windows (môžete ho nájsť v Službách)
   - Predvolený inštalačný adresár je `C:\Program Files\mosquitto`

4. Skopírujte poskytnutý súbor `mosquitto.conf` do inštalačného adresára alebo použite predvolený

5. Spustite službu:
   - Otvorte Príkazový riadok ako Správca
   - Spustite: `net start mosquitto`
   - Alternatívne môžete použiť Správcu služieb systému Windows

### Raspberry Pi

1. Nainštalujte Mosquitto:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   ```

2. Povolte Mosquitto aby sa spustil pri štarte:
   ```bash
   sudo systemctl enable mosquitto
   ```

3. Skopírujte poskytnutú konfiguráciu:
   ```bash
   sudo cp mosquitto.conf /etc/mosquitto/conf.d/home-security.conf
   ```

4. Vytvorte požadované adresáre:
   ```bash
   sudo mkdir -p /etc/mosquitto/data/mosquitto
   sudo chown mosquitto:mosquitto /etc/mosquitto/data/mosquitto
   ```

5. Reštartujte službu:
   ```bash
   sudo systemctl restart mosquitto
   ```

## Overenie inštalácie

Pre overenie, že Mosquitto funguje:

1. Otvorte dve terminálové okná

2. V prvom okne sa prihláste na testovací téma:
   ```bash
   # Windows:
   mosquitto_sub -h localhost -t test/topic

   # Raspberry Pi:
   mosquitto_sub -h localhost -t test/topic
   ```

3. V druhom okne publikujte správu:
   ```bash
   # Windows:
   mosquitto_pub -h localhost -t test/topic -m "Ahoj MQTT"

   # Raspberry Pi:
   mosquitto_pub -h localhost -t test/topic -m "Ahoj MQTT"
   ```

4. Mali by ste vidieť "Ahoj MQTT" sa objaviť v prvom okne

## Použitie s Bezpečnostným Systémom

Bezpečnostný Systém je nakonfigurovaný na použitie Mosquitto na localhoste (127.0.0.1) port 1883 predvolene.

1. Skontrolujte nastavenia MQTT v súboroch:
   - `data/mqtt_config.json` - Aktualizujte nastavenia brokera, ak je to potrebné
   - `SEND/config.json` - Uistite sa, že nastavenia MQTT sa zhodujú
   
2. Pri používaní skriptov automatického štartu:
   - `autostart_win.bat` skontroluje a spustí Mosquitto, ak je k dispozícii
   - `autostart_pi.sh` použije systémovú službu Mosquitto

## Zabezpečenie Mosquitto

Pre produkčné prostredia sa odporúča zabezpečiť váš MQTT broker:

1. Vytvorte súbor hesiel:
   ```bash
   # Windows:
   mosquitto_passwd -c passwordfile meno_používateľa

   # Raspberry Pi:
   sudo mosquitto_passwd -c /etc/mosquitto/passwd meno_používateľa
   ```

2. Aktualizujte konfiguračný súbor pre použitie autentifikácie odkomentovaním:
   ```
   allow_anonymous false
   password_file ./data/mosquitto/passwd  # alebo úplná cesta k súboru passwd
   ```

3. Pre SSL/TLS šifrovanie vygenerujte certifikáty a odkomentujte súvisiace sekcie v konfiguračnom súbore.

---

Pre podrobnejšie informácie o konfigurácii Mosquitto navštívte [oficiálnu dokumentáciu](https://mosquitto.org/documentation/)