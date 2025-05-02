# web_app.py - Flask web rozhranie
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort
from config.system_state import load_state, save_state, set_lockout, is_locked_out, update_state
from config.settings import load_settings, save_settings
from config.devices_manager import load_devices
from config.alerts_log import get_recent_alerts, clear_alerts
from mqtt_client import mqtt_client  # Importovanie mqtt_client singleton
import notification_service as ns
from datetime import datetime, timedelta
import time
import json
import os
import threading

app = Flask(__name__, template_folder='templates')

# Štatistiky MQTT pripojenia
mqtt_stats = {
    'start_time': time.time(),
    'message_count': 0,
    'connected_devices': {},
    'reconnect_count': 0,
    'last_error': None
}

# Registrácia callback funkcie pre aktualizáciu štatistík
@mqtt_client.on_message
def on_mqtt_message(topic, payload):
    mqtt_stats['message_count'] += 1
    
    # Aktualizácia zoznamu zariadení, ak sa jedná o status správu
    if topic.startswith(mqtt_client.config['topics']['status']):
        try:
            device_id = topic.split('/')[-1]
            status = payload.get('status', 'UNKNOWN')
            
            if device_id not in mqtt_stats['connected_devices']:
                mqtt_stats['connected_devices'][device_id] = {}
            
            mqtt_stats['connected_devices'][device_id].update({
                'id': device_id,
                'status': status,
                'last_seen': datetime.now().isoformat(),
                'name': payload.get('device_name', device_id),
                'room': payload.get('room', None),
                'ip': payload.get('ip', None)
            })
        except Exception as e:
            app.logger.error(f"Chyba pri spracovaní MQTT status správy: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sensors')
def sensors_page():
    return render_template('sensors.html')

@app.route('/alerts')
def alerts_page():
    return render_template('alerts.html')

@app.route('/mqtt')
def mqtt_page():
    return render_template('mqtt_status.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/api/sensors', methods=['GET'])
def api_sensors():
    try:
        devices = load_devices()
        device_status_path = os.path.join(os.path.dirname(__file__), '../data/device_status.json')
        
        if not os.path.exists(device_status_path):
            app.logger.warning("Device status file not found")
            return jsonify({"sensors": [], "metrics": {"total_devices": 0, "online_devices": 0, "triggered_sensors": 0}}), 200
        
        # Load device states
        with open(device_status_path, 'r', encoding='utf-8') as f:
            device_states = json.load(f)
            
        sensors_data = []
        unique_devices = set()
        online_devices = set()
        triggered_count = 0
        
        for device in devices:
            # Check for either 'id' or 'device_id' field
            device_id = None
            if 'id' in device:
                device_id = device['id']
            elif 'device_id' in device:
                device_id = device['device_id']
            else:
                app.logger.warning(f"Device missing identifier field: {device}")
                continue
                
            # Ensure 'name' field is present, fallback to device_id if not
            device_name = device.get('name', device.get('device_name', device_id))
            unique_devices.add(device_id)
            
            # Check if device is online
            if device_id in device_states:
                if device_states[device_id].get('status') == 'ONLINE':
                    online_devices.add(device_id)
                
                room = device.get('room', 'Neznáma miestnosť')
                
                for sensor_type, status in device_states[device_id].items():
                    # Skip non-sensor fields
                    if sensor_type not in ['motion', 'door', 'window']:
                        continue
                        
                    # Count triggered sensors
                    if (sensor_type == 'motion' and status == 'DETECTED') or \
                       (sensor_type in ['door', 'window'] and status == 'OPEN'):
                        triggered_count += 1
                        
                    sensor_name = get_sensor_name(sensor_type)
                    state_text = get_state_text(sensor_type, status)
                    
                    sensors_data.append({
                        'device_id': device_id,
                        'device_name': device_name,
                        'room': room,
                        'sensor_type': sensor_type,
                        'sensor': sensor_name,
                        'status': state_text,
                        'raw_status': status,
                        'status_class': get_status_class(sensor_type, status)
                    })
                    
        # Add summary metrics to the response
        metrics = {
            'total_devices': len(unique_devices),
            'online_devices': len(online_devices),
            'triggered_sensors': triggered_count
        }
                    
        return jsonify({
            "sensors": sensors_data,
            "metrics": metrics
        })
    except KeyError as e:
        app.logger.error(f"KeyError pri získavaní senzorov: {e}")
        return jsonify({"error": f"Key error: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"Chyba pri získavaní senzorov: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/state', methods=['GET'])
def api_state():
    state = load_state()
    
    return jsonify(state)

@app.route('/api/system/arm', methods=['POST'])
def api_arm_system():
    """API endpoint pre aktiváciu zabezpečenia v konkrétnom režime."""
    try:
        data = request.get_json()
        arm_mode = data.get('mode', 'armed_away')  # armed_home alebo armed_away
        pin = data.get('pin')
        
        if arm_mode not in ['armed_home', 'armed_away']:
            return jsonify({"success": False, "message": "Neplatný režim zabezpečenia"}), 400
        
        # Kontrola PIN kódu
        settings = load_settings()
        if pin != settings.get('pin_code'):
            # Zlý PIN kód - zvýšiť počet neúspešných pokusov
            state = load_state()
            state['failed_attempts'] = state.get('failed_attempts', 0) + 1
            if state['failed_attempts'] >= 3:
                set_lockout(30)
                state['failed_attempts'] = 0
            save_state(state)
            return jsonify({"success": False, "message": "Nesprávny PIN kód!"}), 401
            
        # Aktualizácia stavu systému
        update_state({"armed_mode": arm_mode, "alarm_active": False, "failed_attempts": 0})
        
        # Odoslanie notifikácie
        mode_name = "Doma" if arm_mode == "armed_home" else "Preč"
        ns.send_notification(f"Systém zabezpečený v režime {mode_name}")
        
        return jsonify({
            "success": True, 
            "message": f"Systém zabezpečený v režime {mode_name}"
        })
    except Exception as e:
        app.logger.error(f"Chyba pri aktivácii zabezpečenia: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/system/disarm', methods=['POST'])
def api_disarm_system():
    """API endpoint pre deaktiváciu zabezpečenia."""
    try:
        # Kontrola PIN kódu
        data = request.get_json()
        pin = data.get('pin')
        
        settings = load_settings()
        if pin != settings.get('pin_code'):
            # Zlý PIN kód - zvýšiť počet neúspešných pokusov
            state = load_state()
            state['failed_attempts'] = state.get('failed_attempts', 0) + 1
            if state['failed_attempts'] >= 3:
                set_lockout(30)
                state['failed_attempts'] = 0
            save_state(state)
            return jsonify({"success": False, "message": "Nesprávny PIN kód!"}), 401
        
        # Aktualizácia stavu systému
        update_state({
            "armed_mode": "disarmed", 
            "alarm_active": False,
            "alarm_countdown_active": False,  # Explicitly disable countdown
            "alarm_countdown_deadline": None,
            "alarm_trigger_message": None,
            "failed_attempts": 0
        })
        
        # Ak je aktívny alarm alebo odpočítavanie, zastavíme ho
        if ns.is_alarm_active() or ns.is_alarm_countdown_active():
            ns.stop_alarm()
        
        # Synchronizácia interného stavu s aktuálnym systémovým stavom
        ns.sync_state_from_system()
        
        # Odoslanie notifikácie
        ns.send_notification("Systém deaktivovaný")
        
        return jsonify({
            "success": True, 
            "message": "Systém úspešne deaktivovaný"
        })
    except Exception as e:
        app.logger.error(f"Chyba pri deaktivácii zabezpečenia: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/system/alarm/stop', methods=['POST'])
def api_stop_alarm():
    """API endpoint pre zastavenie alarmu a deaktiváciu systému."""
    try:
        # Kontrola PIN kódu
        data = request.get_json()
        pin = data.get('pin')
        
        settings = load_settings()
        if pin != settings.get('pin_code'):
            return jsonify({"success": False, "message": "Nesprávny PIN kód!"}), 401
        
        # Zastavenie alarmu a deaktivácia systému
        ns.stop_alarm()
        update_state({
            "armed_mode": "disarmed",
            "alarm_active": False,
            "alarm_countdown_active": False,
            "alarm_countdown_deadline": None,
            "alarm_trigger_message": None
        })
        
        # Synchronizácia interného stavu s aktuálnym systémovým stavom
        ns.sync_state_from_system()
        
        # Odoslanie notifikácie
        ns.send_notification("Alarm zastavený a systém deaktivovaný")
        
        return jsonify({
            "success": True, 
            "message": "Alarm zastavený a systém deaktivovaný"
        })
    except Exception as e:
        app.logger.error(f"Chyba pri zastavovaní alarmu: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def api_alerts():
    """API endpoint pre získanie histórie upozornení."""
    try:
        count = request.args.get('count', 10, type=int)
        alerts = get_recent_alerts(count)
        return jsonify({"alerts": alerts})
    except Exception as e:
        app.logger.error(f"Chyba pri získavaní histórie upozornení: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/alerts/clear', methods=['POST'])
def api_alerts_clear():
    """API endpoint pre vymazanie všetkých upozornení."""
    try:
        success = clear_alerts()
        if success:
            return jsonify({"success": True, "message": "Všetky upozornenia boli vymazané"})
        else:
            return jsonify({"success": False, "message": "Chyba pri vymazávaní upozornení"}), 500
    except Exception as e:
        app.logger.error(f"Chyba pri vymazávaní upozornení: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/image', methods=['GET'])
def api_get_image():
    """Poskytuje obrázky z alertov."""
    try:
        image_path = request.args.get('path')
        if not image_path:
            return "Chýba parameter 'path'", 400
        
        # Verifikácia cesty - bezpečnostné opatrenie proti úniku súborov mimo povolených adresárov
        image_path = os.path.abspath(image_path)
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
        
        # Kontrola, či cesta je v povolenej zložke (napr. /data/images/)
        if not image_path.startswith(data_dir):
            return "Prístup zamietnutý", 403
            
        if not os.path.exists(image_path):
            return "Obrázok nenájdený", 404
            
        # Odoslanie súboru
        return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        app.logger.error(f"Chyba pri získavaní obrázku: {e}")
        return "Interná chyba serveru", 500

@app.route('/api/activate', methods=['POST'])
def api_activate():
    """Spätná kompatibilita s pôvodným API - nastaví režim 'armed_away'"""
    try:
        # Kontrola PIN kódu
        data = request.get_json()
        pin = data.get('pin')
        
        settings = load_settings()
        if pin != settings.get('pin_code'):
            # Zlý PIN kód - zvýšiť počet neúspešných pokusov
            state = load_state()
            state['failed_attempts'] = state.get('failed_attempts', 0) + 1
            if state['failed_attempts'] >= 3:
                set_lockout(30)
                state['failed_attempts'] = 0
            save_state(state)
            return jsonify({"success": False, "message": "Nesprávny PIN kód!"}), 401
        
        update_state({"armed_mode": "armed_away", "alarm_active": False, "failed_attempts": 0})
        ns.send_notification("Systém zabezpečený v režime Preč")
        return jsonify({"success": True, "message": "Systém zabezpečený v režime Preč"})
    except Exception as e:
        app.logger.error(f"Chyba pri aktivácii zabezpečenia: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sensor_trigger', methods=['POST'])
def api_sensor_trigger():
    state = load_state()
    # Kontrola či alarm už nie je spustený, aby sme predišli resetovaniu časovača
    if not state['system_activated'] or state['alarm_triggered']:
        return jsonify({"ok": False, "msg": "Systém nie je aktivovaný alebo alarm už beží"}), 400
        
    state['alarm_triggered'] = True
    # Nastav deadline 60 sekúnd od teraz, ale len ak už nie je nastavený
    if not state.get('alarm_deadline'):
        deadline = (datetime.now() + timedelta(seconds=60)).timestamp()
        state['alarm_deadline'] = deadline
    save_state(state)
    return jsonify({"ok": True})

@app.route('/api/pin', methods=['POST'])
def api_pin():
    if is_locked_out():
        return jsonify({"success": False, "message": "Zamknuté, skúste neskôr."}), 403
        
    data = request.get_json()
    pin = data.get('pin', '')
    settings = load_settings()
    state = load_state()
    
    if pin == settings['pin_code']:
        # Ak je aktívny alarm, deaktivujeme ho, ale režim zabezpečenia ponecháme aktívny
        if state.get('alarm_active', False):
            ns.stop_alarm()
            update_state({"alarm_active": False})
            return jsonify({"success": True, "message": "Alarm deaktivovaný"})
        
        # Inak deaktivujeme celý systém
        update_state({
            "armed_mode": "disarmed",
            "alarm_active": False, 
            "failed_attempts": 0
        })
        return jsonify({"success": True, "message": "Systém deaktivovaný"})
    else:
        state['failed_attempts'] = state.get('failed_attempts', 0) + 1
        if state['failed_attempts'] >= 3:
            set_lockout(30)
            state['failed_attempts'] = 0
        save_state(state)
        return jsonify({"success": False, "message": "Nesprávny PIN kód!"}), 401

@app.route('/api/mqtt/status', methods=['GET'])
def api_mqtt_status():
    """Poskytuje informácie o stave MQTT pripojenia"""
    uptime = int(time.time() - mqtt_stats['start_time'])
    
    # Spočítanie online zariadení
    online_devices = 0
    for device in mqtt_stats['connected_devices'].values():
        if device.get('status') == 'ONLINE':
            online_devices += 1
            
    return jsonify({
        'connected': mqtt_client.connected,
        'broker': mqtt_client.config.get('broker', 'unknown'),
        'port': mqtt_client.config.get('port', 1883),
        'uptime': uptime,
        'message_count': mqtt_stats['message_count'],
        'device_count': len(mqtt_stats['connected_devices']),
        'online_device_count': online_devices,
        'reconnect_count': mqtt_stats['reconnect_count'],
        'last_error': mqtt_stats['last_error']
    })

@app.route('/api/mqtt/devices', methods=['GET'])
def api_mqtt_devices():
    """Poskytuje zoznam všetkých MQTT zariadení a ich stavov"""
    return jsonify({
        'devices': list(mqtt_stats['connected_devices'].values())
    })

@app.route('/api/mqtt/devices/clear', methods=['POST'])
def api_mqtt_devices_clear():
    """Vymaže zoznam všetkých MQTT zariadení zo systému"""
    try:
        mqtt_stats['connected_devices'] = {}
        
        # Resetovať pripojenia prostredníctvom MQTT príkazov na všetky zariadenia
        for topic in mqtt_client.config['topics'].values():
            if mqtt_client.connected:
                # Odoslanie broadcast príkazu na resetovanie zariadení
                mqtt_client.client.publish(f"{topic}/broadcast", json.dumps({
                    "command": "RECONNECT",
                    "timestamp": datetime.now().isoformat()
                }))
        
        # Reštartovať MQTT klienta
        mqtt_stats['reconnect_count'] += 1
        mqtt_client.stop()
        time.sleep(1)  # Krátke oneskorenie pre ukončenie spojenia
        mqtt_client.config = mqtt_client._load_config()
        mqtt_client.start()
        
        return jsonify({'success': True, 'message': 'Zoznam zariadení bol vymazaný a rozoslané príkazy na opätovné pripojenie'})
    except Exception as e:
        mqtt_stats['last_error'] = str(e)
        app.logger.error(f"Chyba pri vymazávaní zoznamu zariadení: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mqtt/config', methods=['GET', 'POST'])
def api_mqtt_config():
    """Získať alebo nastaviť MQTT konfiguráciu"""
    if request.method == 'GET':
        # Vrátiť aktuálnu konfiguráciu (bez citlivých údajov ako je heslo)
        config = mqtt_client.config.copy()
        if 'password' in config:
            config['password'] = '********' if config['password'] else ''
        return jsonify(config)
    
    elif request.method == 'POST':
        try:
            # Aktualizovať konfiguráciu
            new_config = request.json
            
            # Validácia základných polí
            if not new_config.get('broker'):
                return jsonify({'success': False, 'message': 'Chýba adresa MQTT brokera'}), 400
                
            # Načítanie aktuálnej konfigurácie
            current_config = mqtt_client.config
            
            # Aktualizácia konfigurácie
            for key, value in new_config.items():
                # Nenastavovať heslo, ak je to "********" (používateľ ho nezmenil)
                if key == 'password' and value == '********':
                    continue
                current_config[key] = value
            
            # Uloženie konfigurácie do súboru
            config_path = os.path.join(os.path.dirname(__file__), '../data/mqtt_config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(current_config, f, indent=4, ensure_ascii=False)
            
            return jsonify({'success': True, 'message': 'Konfigurácia bola úspešne aktualizovaná'})
        except Exception as e:
            app.logger.error(f"Chyba pri aktualizácii MQTT konfigurácie: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mqtt/reconnect', methods=['POST'])
def api_mqtt_reconnect():
    """Pokúsi sa znovu pripojiť MQTT klienta s aktuálnou konfiguráciou"""
    try:
        mqtt_stats['reconnect_count'] += 1
        
        # Zastavenie a opätovné spustenie MQTT klienta
        mqtt_client.stop()
        time.sleep(1)  # Krátke oneskorenie pre ukončenie spojenia
        
        # Znovunačítanie konfigurácie a spustenie klienta
        mqtt_client.config = mqtt_client._load_config()
        mqtt_client.start()
        
        return jsonify({'success': True, 'message': 'MQTT klient sa opätovne pripája'})
    except Exception as e:
        mqtt_stats['last_error'] = str(e)
        app.logger.error(f"Chyba pri reštartovaní MQTT klienta: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mqtt/command', methods=['POST'])
def api_mqtt_command():
    """Odošle príkaz na konkrétne zariadenie cez MQTT"""
    try:
        data = request.json
        target_device = data.get('device_id')
        command = data.get('command')
        command_data = data.get('data', {})
        
        if not target_device or not command:
            return jsonify({'success': False, 'message': 'Chýba device_id alebo command'}), 400
            
        result = mqtt_client.publish_control_message(target_device, command, command_data)
        if result:
            return jsonify({'success': True, 'message': f'Príkaz {command} odoslaný na zariadenie {target_device}'})
        else:
            return jsonify({'success': False, 'message': 'Chyba pri odosielaní príkazu - MQTT klient nepripojený'}), 503
    except Exception as e:
        app.logger.error(f"Chyba pri odosielaní MQTT príkazu: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/identify/<device_id>', methods=['POST'])
def api_identify_device(device_id):
    """API endpoint for sending IDENTIFY command to a specific device"""
    try:
        # Verify the device_id matches a recognized pattern
        if not device_id or not isinstance(device_id, str) or len(device_id) < 3:
            return jsonify({'success': False, 'message': 'Neplatné ID zariadenia'}), 400
            
        # Send the IDENTIFY command to the device via MQTT
        result = mqtt_client.publish_control_message(
            device_id, 
            "IDENTIFY",  # Command name
            {
                "timestamp": time.time()
            }
        )
        
        if result:
            app.logger.info(f"Príkaz IDENTIFY odoslaný na zariadenie {device_id}")
            return jsonify({'success': True, 'message': f'Zariadenie {device_id} by malo teraz blikať LED indikátorom'})
        else:
            return jsonify({'success': False, 'message': 'Nepodarilo sa odoslať príkaz - MQTT klient nie je pripojený'}), 503
            
    except Exception as e:
        app.logger.error(f"Chyba pri identifikácii zariadenia: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def api_settings():
    """API endpoint pre získanie aktuálnych nastavení systému."""
    try:
        settings = load_settings()
        return jsonify(settings)
    except Exception as e:
        app.logger.error(f"Chyba pri načítavaní nastavení: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/pin', methods=['POST'])
def api_settings_pin():
    """API endpoint pre zmenu PIN kódu."""
    try:
        data = request.get_json()
        old_pin = data.get('oldPin')
        new_pin = data.get('newPin')
        
        if not old_pin or not new_pin:
            return jsonify({"success": False, "message": "Chýba starý alebo nový PIN"}), 400
            
        if len(new_pin) < 4:
            return jsonify({"success": False, "message": "PIN musí mať aspoň 4 znaky"}), 400
            
        settings = load_settings()
        
        if old_pin != settings.get('pin_code'):
            return jsonify({"success": False, "message": "Nesprávny aktuálny PIN kód"}), 401
            
        # Aktualizácia PIN kódu
        settings['pin_code'] = new_pin
        save_settings(settings)
        
        return jsonify({"success": True, "message": "PIN kód bol úspešne aktualizovaný"})
    except Exception as e:
        app.logger.error(f"Chyba pri aktualizácii PIN kódu: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/notifications', methods=['POST'])
def api_settings_notifications():
    """API endpoint pre aktualizáciu nastavení notifikácií."""
    try:
        data = request.get_json()
        sound_enabled = data.get('sound')
        email_enabled = data.get('email')
        
        if sound_enabled is None or email_enabled is None:
            return jsonify({"success": False, "message": "Chýbajú parametre notifikačných nastavení"}), 400
            
        settings = load_settings()
        
        if "notification_preferences" not in settings:
            settings["notification_preferences"] = {}
            
        settings["notification_preferences"]["sound"] = sound_enabled
        settings["notification_preferences"]["email"] = email_enabled
        
        save_settings(settings)
        
        return jsonify({"success": True, "message": "Nastavenia notifikácií boli úspešne aktualizované"})
    except Exception as e:
        app.logger.error(f"Chyba pri aktualizácii nastavení notifikácií: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/email', methods=['POST'])
def api_settings_email():
    """API endpoint pre aktualizáciu e-mailových nastavení."""
    try:
        data = request.get_json()
        
        # Validácia požadovaných polí
        required_fields = ['enabled', 'smtp_server', 'smtp_port', 'username', 'recipient']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"Chýba parameter {field}"}), 400
                
        # Načítanie existujúcich nastavení
        settings = load_settings()
        
        if "email_settings" not in settings:
            settings["email_settings"] = {}
            
        # Aktualizácia polí
        settings["email_settings"]["enabled"] = data["enabled"]
        settings["email_settings"]["smtp_server"] = data["smtp_server"]
        settings["email_settings"]["smtp_port"] = data["smtp_port"]
        settings["email_settings"]["username"] = data["username"]
        settings["email_settings"]["recipient"] = data["recipient"]
        
        # Aktualizácia hesla, len ak bolo zadané nové
        if "password" in data:
            settings["email_settings"]["password"] = data["password"]
            
        save_settings(settings)
        
        return jsonify({"success": True, "message": "E-mailové nastavenia boli úspešne aktualizované"})
    except Exception as e:
        app.logger.error(f"Chyba pri aktualizácii e-mailových nastavení: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/settings/email/test', methods=['POST'])
def api_settings_email_test():
    """API endpoint pre odoslanie testovacieho e-mailu."""
    try:
        settings = load_settings()
        
        # Kontrola, či sú nastavenia e-mailu nakonfigurované
        if not settings.get("email_settings") or not settings["email_settings"].get("enabled"):
            return jsonify({"success": False, "message": "E-mailové notifikácie nie sú povolené"}), 400
            
        # Skúsime poslať testovací e-mail
        test_message = "Toto je testovacia správa z vášho domáceho bezpečnostného systému."
        success = ns.send_email(test_message, settings)
        
        if success:
            return jsonify({"success": True, "message": "Testovací e-mail bol úspešne odoslaný"})
        else:
            return jsonify({"success": False, "message": "Nepodarilo sa odoslať testovací e-mail"}), 500
    except Exception as e:
        app.logger.error(f"Chyba pri odosielaní testovacieho e-mailu: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/latest_images', methods=['GET'])
def api_latest_images():
    """Poskytuje posledné obrázky pre jednotlivé zariadenia."""
    try:
        # Cesta k priečinku s obrázkami
        images_dir = os.path.join(os.path.dirname(__file__), '../data/images')
        
        # Kontrola existencie priečinka
        if not os.path.exists(images_dir):
            return jsonify({"images": {}}), 200
        
        # Nájdenie najnovších obrázkov pre každé zariadenie
        device_images = {}
        image_files = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
        
        for image_file in image_files:
            # Názov zariadenia je na začiatku súboru pred podtržníkom
            parts = image_file.split('_')
            if len(parts) < 2:
                continue
                
            device_id = parts[0]
            
            # Získanie času vytvorenia súboru
            image_path = os.path.join(images_dir, image_file)
            timestamp = os.path.getmtime(image_path)
            
            # Ak zariadenie ešte nemá obrázok alebo je tento novší
            if device_id not in device_images or timestamp > device_images[device_id]['timestamp']:
                device_images[device_id] = {
                    'path': image_path,
                    'timestamp': timestamp,
                    'filename': image_file
                }
        
        return jsonify({"images": device_images})
    except Exception as e:
        app.logger.error(f"Chyba pri získavaní obrázkov: {e}")
        return jsonify({"error": str(e)}), 500

def get_sensor_name(sensor_type):
    names = {
        'motion': 'Pohybový senzor',
        'door': 'Dverový kontakt',
        'window': 'Okenný kontakt'
    }
    return names.get(sensor_type, sensor_type.capitalize())
    
def get_state_text(sensor_type, status):
    if sensor_type == 'motion':
        return 'DETEGOVANÝ' if status == 'DETECTED' else 'ŽIADNY POHYB'
    elif sensor_type == 'door':
        return 'OTVORENÉ' if status == 'OPEN' else 'ZATVORENÉ'
    elif sensor_type == 'window':
        return 'OTVORENÉ' if status == 'OPEN' else 'ZATVORENÉ'
    else:
        return status

def get_status_class(sensor_type, status):
    if sensor_type == 'motion' and status == 'DETECTED':
        return 'danger'
    elif sensor_type in ['door', 'window'] and status == 'OPEN':
        return 'danger'
    else:
        return 'success'

def start_web_app():
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=True)