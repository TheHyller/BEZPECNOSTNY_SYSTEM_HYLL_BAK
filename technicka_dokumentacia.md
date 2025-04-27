# Bezpečnostný systém pre domácnosť - Technická dokumentácia

## 1. Prehľad systému

Bezpečnostný systém pre domácnosť predstavuje komplexné a modulárne bezpečnostné riešenie navrhnuté pre rezidenčné prostredie, s distribuovanou sieťou senzorov a multikanálovou komunikačnou infraštruktúrou. Architektúra implementuje viacvrstvový prístup k bezpečnostnému monitorovaniu, zahŕňajúci rôzne hardvérové platformy vrátane Raspberry Pi a ESP mikrokontrolérov, centralizovaných prostredníctvom MQTT správcovskej infraštruktúry.

Systém funguje na báze komunikačného paradigma vydavateľ-odberateľ, čo umožňuje výmenu dát v reálnom čase medzi heterogénnymi komponentmi so zachovaním robustnej odolnosti voči chybám prostredníctvom mechanizmov automatického objavovania brokerov a algoritmov správy pripojení.

## 2. Architektúra systému

### 2.1 Vysokoúrovňová architektúra

Bezpečnostný systém pre domácnosť využíva distribuovanú architektúru pozostávajúcu z troch primárnych komponentov:

1. **Vysielacie moduly (SEND)**: Jednotky založené na Raspberry Pi zodpovedné za komunikáciu s fyzickými senzormi (detektory pohybu, kontakty na dverách/oknách) a zachytávanie obrazu z kamery. Tieto moduly fungujú ako koncové body zberu dát, ktoré monitorujú zmeny v prostredí a odosielajú upozornenia o udalostiach do centrálneho systému.

2. **Vysielacie moduly založené na ESP (ESP_SEND)**: Mikrokontrolérové senzory využívajúce platformy ESP8266/ESP32, poskytujúce bezdrôtové senzorové uzly s redukovanou spotrebou energie. Tieto moduly rozširujú pokrytie systému prostredníctvom strategického rozmiestnenia v oblastiach, kde by bola implementácia plnohodnotného Raspberry Pi nepraktická.

3. **Prijímací modul (REC)**: Centralizovaná jednotka spracovania implementujúca grafické používateľské rozhranie (framework Kivy) a webové rozhranie (framework Flask) pre monitorovanie systému, správu konfigurácie a reaktívne notifikácie. Tento modul slúži ako riadiace centrum systému, spracováva prichádzajúce údaje zo senzorov a vykonáva príslušné odozvy.

4. **MQTT komunikačná vrstva**: Protokol Message Queuing Telemetry Transport umožňuje asynchrónnu komunikáciu medzi všetkými komponentmi systému, zabezpečuje spoľahlivý prenos dát s konfigurovateľnými parametrami kvality služieb.

### 2.2 Tok dát

```
┌─────────────┐          MQTT         ┌─────────────┐
│  SEND Unit  │◄───────Správy────────►│    MQTT     │
│ (Raspberry) │                       │   Broker    │
└─────────────┘                       │             │
                                      │             │
┌─────────────┐          MQTT         │             │
│ ESP_SEND    │◄───────Správy────────►│             │
│  (ESP8266)  │                       │             │
└─────────────┘                       └──────┬──────┘
                                             │
                                             │ MQTT
                                             │ Správy
                                             ▼
                                      ┌─────────────┐
                                      │  REC Unit   │
                                      │ (Prijímač)  │
                                      └─────────────┘
                                             │
                                  ┌──────────┴──────────┐
                                  │                     │
                           ┌──────▼─────┐        ┌──────▼─────┐
                           │ Kivy GUI   │        │  Flask Web │
                           │ Rozhranie  │        │  Rozhranie │
                           └────────────┘        └────────────┘
```

## 3. Popis komponentov

### 3.1 Modul SEND (Raspberry Pi)

Modul SEND funguje ako sofistikovaná jednotka zberu dát, komunikujúca s fyzickými bezpečnostnými senzormi prostredníctvom GPIO pripojení, pričom implementuje rozsiahle mechanizmy spracovania chýb a správy pripojení.

**Kľúčové vlastnosti:**
- **Integrácia viacerých senzorov**: Komunikuje s pohybovými senzormi, dverovými kontaktmi, okennými senzormi prostredníctvom konfigurovateľných GPIO pinov
- **Automatizované objavovanie MQTT brokera**: Implementuje sieťový objavovací protokol založený na UDP na dynamické lokalizovanie MQTT brokerov
- **Integrácia kamery**: Zachytáva a prenáša obrázky pri detekcii pohybu
- **Kontextové vnímanie**: Kontextualizuje údaje senzorov s informáciami o polohe (označenie miestnosti)
- **Správa trvalého pripojenia**: Implementuje pokročilé stratégie opätovného pripojenia s algoritmami exponenciálneho odstupu

**Hlavné súbory:**
- `SEND/SEND.py`: Hlavná implementácia pre senzory a funkcie kamery Raspberry Pi
- `SEND/config.json`: Konfiguračné parametre pre senzory, MQTT a nastavenia kamery

### 3.2 Modul ESP_SEND (ESP8266/ESP32)

Modul ESP_SEND predstavuje implementáciu ľahkého senzorového uzla optimalizovanú pre energetickú účinnosť pri zachovaní základných možností bezpečnostného monitorovania.

**Kľúčové vlastnosti:**
- **Nízkoenergetická prevádzka**: Optimalizovaná pre batériové napájanie s konfigurovateľnými intervalmi hlásenia
- **Detekcia pohybu**: Obsahuje pohybové senzory na monitorovanie priestoru
- **Dynamická konfigurácia siete**: Podporuje statické aj automatické objavovanie brokerov
- **Vzdialená spravovateľnosť**: Reaguje na riadiace príkazy pre hlásenie stavu a aktualizácie konfigurácie
- **Identifikácia zariadenia**: Vysiela detailné metadáta zariadenia umožňujúce automatickú integráciu

**Hlavné súbory:**
- `ESP_SEND/ESP_SEND.ino`: Implementácia Arduino pre mikrokontroléry ESP8266/ESP32

### 3.3 Modul REC (Prijímač)

Modul REC predstavuje centrálne inteligentné centrum systému, spracováva prichádzajúce údaje zo senzorov, spravuje inventár zariadení a poskytuje multimodálne používateľské rozhrania pre interakciu so systémom.

**Kľúčové vlastnosti:**
- **Duálne rozhranie**: Implementuje ako desktopovú aplikáciu (Kivy), tak aj webové rozhranie (Flask)
- **Motor na spracovanie udalostí**: Analyzuje prichádzajúce údaje zo senzorov pre bezpečnostné implikácie
- **Notifikačný systém**: Viackanálové upozornenia prostredníctvom vizuálnych, zvukových a potenciálne mobilných notifikácií
- **Správa konfigurácie**: Centralizovaná správa systémových parametrov a konfigurácií zariadení
- **Autentifikačný systém**: Prístupová kontrola založená na rolách pre prevádzku systému
- **Analýza historických dát**: Zaznamenávanie udalostí s možnosťou získavania a analýzy

**Hlavné súbory:**
- `REC/main.py`: Základná inicializácia aplikácie a spracovanie udalostí
- `REC/mqtt_client.py`: Sofistikovaná implementácia MQTT klienta s pokročilým spracovaním chýb
- `REC/web_app.py`: Implementácia webového rozhrania pomocou Flask
- `REC/dashboard_screen.py`, `REC/alerts_screen.py`, atď.: Implementácie jednotlivých obrazoviek pre Kivy UI
- `REC/config/`: Konfiguračné moduly pre zariadenia, stav systému a nastavenia

## 4. Komunikačný protokol

### 4.1 Štruktúra MQTT tém

Systém využíva hierarchickú štruktúru tém pre MQTT komunikáciu:

- `home/security/sensors/{device_id}`: Publikácie údajov zo senzorov
- `home/security/status/{device_id}`: Informácie o stave zariadenia (online/offline stavy)
- `home/security/control/{device_id}`: Príkazové a riadiace správy
- `home/security/images/{device_id}`: Obrazové dáta zo zariadení s kamerou

### 4.2 Formát správ

Všetky správy využívajú JSON formátovanie pre štruktúrovanú výmenu dát:

**Príklad správy senzora:**
```json
{
  "device_id": "rpi_send_1",
  "room": "Vstupná chodba",
  "sensor": "motion",
  "state": true,
  "label": "Pohyb",
  "timestamp": 1650284533.123
}
```

**Príklad správy o stave:**
```json
{
  "device_id": "esp_sensor_1",
  "room": "Obývačka",
  "status": "ONLINE",
  "timestamp": 1650284533.123,
  "uptime": 3600,
  "ip": "192.168.1.105",
  "rssi": -67
}
```

### 4.3 Objavovací protokol

Systém implementuje inovatívny objavovací mechanizmus založený na UDP pre automatické lokalizovanie MQTT brokerov v sieti:

1. Vysielacie moduly vysielajú UDP objavovacie požiadavky na porte 12345
2. Prijímač odpovedá s informáciami o umiestnení brokera
3. Vysielacie moduly nadväzujú MQTT spojenia pomocou objavených parametrov

Tento prístup eliminuje požiadavky na manuálnu konfiguráciu, čím uľahčuje scenáre nasadenia typu plug-and-play.

## 5. Ukladanie dát

### 5.1 Štruktúra súborov

Systém využíva konfiguráciu založenú na JSON a ukladanie stavov:

- `data/devices.json`: Inventár zariadení a metadáta
- `data/device_status.json`: Aktuálny prevádzkový stav všetkých zariadení
- `data/system_state.json`: Systémové stavové premenné
- `data/settings.json`: Používateľsky konfigurovateľné systémové parametre
- `data/alerts.log`: Chronologický záznam bezpečnostných udalostí
- `data/mqtt_config.json`: Konfiguračné nastavenia MQTT pripojenia

### 5.2 Ukladanie obrázkov

Obrázky zachytené kamerou sú uložené s nasledujúcou nomenklatúrou:
`data/images/{device_id}_{timestamp}.jpg`

## 6. Používateľské rozhrania

### 6.1 Kivy GUI

Desktopová aplikácia prezentuje intuitívne používateľské rozhranie pozostávajúce z viacerých špecializovaných obrazoviek:

- **Dashboard obrazovka**: Prehľad systému s kľúčovými indikátormi stavu
- **Obrazovka senzorov**: Detailné zobrazenie stavu senzorov s historickými údajmi
- **Obrazovka upozornení**: Chronologický zoznam bezpečnostných udalostí so správou upozornení
- **Obrazovka nastavení**: Konfiguračné parametre systému
- **Prihlasovacia obrazovka**: Autentifikačné rozhranie s kontrolou prístupu založenou na rolách

### 6.2 Webové rozhranie

Webové rozhranie založené na Flasku poskytuje možnosti vzdialeného prístupu:

- Monitorovanie senzorov v reálnom čase prostredníctvom WebSocket komunikácie
- Responzívny dizajn pre prístup z rôznych zariadení
- Vizualizácia stavu MQTT
- Prehľadové panely stavu senzorov
- REST API pre integráciu s externými systémami

#### 6.2.1 Webové API Endpointy

Systém poskytuje rozsiahle REST API pre interakciu s bezpečnostným systémom:

- **GET /api/sensors**: Získanie aktuálneho stavu všetkých senzorov
- **GET /api/state**: Získanie aktuálneho stavu bezpečnostného systému
- **POST /api/system/arm**: Aktivácia zabezpečenia v konkrétnom režime (armed_home/armed_away)
- **POST /api/system/disarm**: Deaktivácia zabezpečovacieho systému
- **POST /api/system/alarm/stop**: Zastavenie aktívneho alarmu a deaktivácia systému
- **GET /api/alerts**: Získanie histórie upozornení
- **POST /api/alerts/clear**: Vymazanie histórie upozornení
- **GET /api/image**: Získanie obrázkov z alertov
- **GET /api/mqtt/status**: Informácie o stave MQTT pripojenia
- **GET /api/mqtt/devices**: Zoznam všetkých MQTT zariadení a ich stavov
- **POST /api/mqtt/devices/clear**: Vymazanie zoznamu MQTT zariadení a obnovenie pripojení
- **GET, POST /api/mqtt/config**: Získanie alebo nastavenie MQTT konfigurácie
- **POST /api/mqtt/reconnect**: Opätovné pripojenie MQTT klienta
- **POST /api/mqtt/command**: Odoslanie príkazu na konkrétne zariadenie cez MQTT

## 7. Technické detaily implementácie

### 7.1 Viacvláknová architektúra

Systém využíva sofistikované viacvláknové spracovanie na zachovanie reakcieschopnosti:

- Samostatné vlákno pre MQTT komunikáciu
- Separátne vlákno pre prevádzku webového servera
- Backgroundové vlákna pre monitorovanie senzorov a spracovanie upozornení
- Hlavné vlákno pre vykresľovanie UI a spracovanie udalostí

### 7.2 Spracovanie chýb a odolnosť

Robustné mechanizmy spracovania chýb zabezpečujú stabilitu systému:

- Exponenciálny odstup pre pokusy o opätovné pripojenie
- Postupná degradácia počas zlyhaní komponentov
- Trvalé monitorovanie pripojenia s automatizovanou obnovou
- Komplexné spracovanie výnimiek s detailným záznamom

### 7.3 Bezpečnostné aspekty

Systém implementuje niekoľko bezpečnostných opatrení:

- Podpora TLS pre šifrovanú MQTT komunikáciu
- Autentifikácia pre MQTT aj webové rozhrania
- Last Will and Testament (LWT) pre spoľahlivé sledovanie stavu zariadení
- Konfigurovateľné úrovne kvality služieb pre garancie doručenia správ
- Mechanizmus odstupňovaného zamykania po viacerých neúspešných pokusoch o zadanie PIN kódu

## 8. Konfiguračné parametre

### 8.1 MQTT konfigurácia

```json
{
  "broker": "localhost",
  "port": 1883,
  "username": "",
  "password": "",
  "client_id_prefix": "home_security_",
  "topics": {
    "sensor": "home/security/sensors",
    "image": "home/security/images",
    "control": "home/security/control",
    "status": "home/security/status"
  },
  "use_tls": false,
  "qos": 1
}
```

### 8.2 Konfigurácia senzorov

Parametre senzorov sú konfigurované prostredníctvom priradení GPIO pinov a nastaveniami správania:

- **Pohybové senzory**: Konfigurovateľná citlivosť a intervaly resetovania
- **Dverové/okenné kontakty**: Konfigurácia normálne otvorené/zatvorené
- **Nastavenia kamery**: Parametre rozlíšenia, snímkovej frekvencie a rotácie

## 9. Inštalácia a nastavenie

### 9.1 Požiadavky

- Mosquitto MQTT broker
- Python 3.8+ pre moduly REC a SEND
- Arduino IDE s podporou ESP8266/ESP32 pre moduly ESP_SEND
- Potrebné Python balíčky podľa špecifikácií v requirements.txt

### 9.2 Kroky inštalácie

1. Nainštalujte MQTT broker podľa mosquitto_install.md
2. Nainštalujte Python závislosti pomocou súborov requirements:
   - `pip install -r requirements.txt`
   - Pre Raspberry Pi: `pip install -r requirements_pi.txt`
3. Nakonfigurujte systémové parametre v súboroch data/*.json
4. Naprogramujte ESP zariadenia pomocou Arduino IDE s ESP_SEND.ino
5. Nasaďte Raspberry Pi jednotky so SEND.py
6. Spustite prijímač pomocou main.py

## 10. Prevádzka systému

### 10.1 Prevádzkové stavy

Systém definuje niekoľko prevádzkových stavov:

- **Deaktivovaný (disarmed)**: Monitorovanie aktívne, ale bez generovania upozornení
- **Aktivovaný domáci režim (armed_home)**: Perimetrické senzory aktívne (dvere, okná), vnútorné pohybové senzory neaktívne, umožňuje pohyb v dome
- **Aktivovaný režim neprítomnosti (armed_away)**: Všetky senzory aktívne s rozšíreným oneskorením vstupu, plné zabezpečenie
- **Odpočítavanie alarmu (alarm_countdown_active)**: Prechodný stav po detekcii narušenia, umožňuje deaktiváciu pred spustením poplachu
- **Poplach (alarm_active)**: Detekované aktívne porušenie bezpečnosti, spustené notifikácie a audio alarm

### 10.2 Spracovanie udalostí

Systém spracováva udalosti podľa nasledujúceho pracovného postupu:

1. Aktivácia senzora generuje MQTT správu
2. Prijímač spracováva správu vzhľadom na aktuálny stav systému
3. Ak sú splnené podmienky pre spustenie odpočítavania alarmu:
   - Začína sa odpočítavanie do poplachu (zvyčajne 60 sekúnd)
   - Používateľ má čas na deaktiváciu systému zadaním správneho PIN kódu
4. Ak sa systém nedeaktivuje počas odpočítavania:
   - Aktivuje sa plný poplach
   - Spustí sa zvuková signalizácia
   - Odošlú sa notifikácie
5. Udalosť sa zaznamená do trvalého úložiska
6. Prvky UI sa aktualizujú tak, aby odrážali aktuálny stav

### 10.3 Notifikačný systém

Systém poskytuje viacúrovňové notifikácie:

- Vizuálne upozornenia v Kivy a webovom rozhraní
- Zvukové upozornenia pre kritické udalosti
- Možnosť integrácie s externými notifikačnými systémami

## 11. Rozšíriteľnosť

Modulárna architektúra uľahčuje rozširovanie systému prostredníctvom:

- Dodatočné typy senzorov prostredníctvom štandardizovaného formátu MQTT správ
- Integrácia s externými systémami pomocou MQTT bridge funkcionality
- Vlastné notifikačné kanály prostredníctvom notifikačnej služby
- Dodatočné UI pohľady prostredníctvom správcu obrazoviek Kivy

## 12. Úvahy o budúcom vývoji

Potenciálne vylepšenia pre budúce verzie:

- Detekcia pohybu založená na AI pre redukciu falošných poplachov
- Cloudová integrácia pre vzdialené monitorovanie
- Integrácia hlasového asistenta
- Rozšírené typy senzorov (dym, voda, plyn)
