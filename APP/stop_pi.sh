#!/bin/bash
# Skript na zastavenie Bezpečnostného Systému pre Raspberry Pi

echo "Zastavujem komponenty Bezpečnostného Systému..."

# Ukončenie Python procesov našej aplikácie
echo "Zastavujem moduly SEND a REC..."
pkill -f "python3 SEND.py"
pkill -f "python3 web_app.py"
pkill -f "python3 main.py"

echo "Všetky komponenty boli úspešne zastavené!"