@echo off
echo Spúšťam Bezpečnostný Systém...

:: Nastavenie pracovného adresára na umiestnenie skriptu
cd /d "%~dp0"

:: Kontrola, či je nainštalovaný Mosquitto a spustenie, ak je
where mosquitto >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Spúšťam Mosquitto MQTT broker...
    start "" mosquitto -v -c mosquitto.conf
    echo Čakám 5 sekúnd na inicializáciu Mosquitto...
    timeout /t 5 /nobreak >nul
) else (
    echo Mosquitto MQTT broker nebol nájdený v PATH.
    echo Nainštalujte Mosquitto z https://mosquitto.org/download/
    echo alebo sa uistite, že je v premennej prostredia PATH.
    echo.
    echo Pokračujem bez spustenia Mosquitto...
    timeout /t 3 /nobreak >nul
)

:: Spustenie modulu SEND v novom okne
echo Spúšťam modul SEND...
start "SEND Modul" cmd /k "cd SEND && python SEND.py"

:: Počkanie pred spustením modulu REC
timeout /t 2 /nobreak >nul

:: Spustenie modulu REC (desktopová aplikácia)
echo Spúšťam desktopovú aplikáciu REC...
start "REC Modul - Desktop" cmd /k "cd REC && python main.py"

:: Spustenie webovej aplikácie REC
echo Spúšťam webovú aplikáciu REC...
start "REC Modul - Web" cmd /k "cd REC && python web_app.py"

echo Všetky komponenty boli úspešne spustené!
echo.
echo Pre ukončenie systému zatvorte všetky otvorené terminálové okná.
echo.

exit