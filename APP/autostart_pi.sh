#!/bin/bash
# Skript automatického štartu Bezpečnostného Systému pre Raspberry Pi

# Nastavenie pracovného adresára na adresár skriptu
cd "$(dirname "$0")"

# Zobrazenie správy o štarte
echo "Spúšťam Bezpečnostný Systém..."

# Kontrola, či je Mosquitto spustený, ak nie, spustiť ho
if ! pgrep mosquitto > /dev/null; then
    echo "Spúšťam Mosquitto MQTT broker..."
    sudo systemctl start mosquitto
    # Čakanie na inicializáciu Mosquitto
    sleep 5
else
    echo "Mosquitto MQTT broker je už spustený."
fi

# Spustenie modulu SEND na pozadí
echo "Spúšťam modul SEND..."
cd SEND
nohup python3 SEND.py > send.log 2>&1 &
cd ..

# Chvíľu počkať pred spustením modulu REC
sleep 2

# Spustenie modulov REC
echo "Spúšťam webovú aplikáciu REC..."
cd REC
nohup python3 web_app.py > web_app.log 2>&1 &

# Spustenie desktopovej aplikácie ak sme v grafickom prostredí
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    echo "Spúšťam desktopovú aplikáciu REC..."
    nohup python3 main.py > main.log 2>&1 &
else
    echo "Žiadny displej nebol detegovaný. Preskakujem spustenie desktopovej aplikácie."
fi

echo "Všetky komponenty boli úspešne spustené!"
echo "Pre viac informácií skontrolujte súbory s logmi v adresároch SEND a REC."
echo "Pre zastavenie systému použite skript stop_pi.sh."