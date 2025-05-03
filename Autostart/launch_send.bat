@echo off
echo Spustam modul SEND...

:: Nastavenie pracovneho adresara na umiestnenie skriptu
cd /d "%~dp0"

:: Kontrola, ci je nainstalovaný Mosquitto a spustenie, ak je
where mosquitto >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Spustam Mosquitto MQTT broker...
    start "" mosquitto -v -c mosquitto.conf
    echo Cakam 5 sekund na inicializaciu Mosquitto...
    timeout /t 5 /nobreak >nul
) else (
    echo Mosquitto MQTT broker nebol najdeny v PATH.
    echo Nainštalujte Mosquitto z https://mosquitto.org/download/
    echo alebo sa uistite, ze je v premennej prostredia PATH.
    echo.
    echo Pokracujem bez spustenia Mosquitto...
    timeout /t 3 /nobreak >nul
)

:: Spustenie modulu SEND v novom okne
echo Spustam modul SEND...
start "SEND Modul" cmd /k "cd SEND && python SEND.py"

echo SEND modul bol uspesne spusteny!
echo.
echo Pre ukoncenie zatvorte otvorene terminálove okno SEND modulu.