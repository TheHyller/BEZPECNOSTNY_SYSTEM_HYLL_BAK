#!/usr/bin/env python3
# mqtt_discovery.py - Automatické zisťovanie MQTT brokera na sieti

import socket
import json
import time
import threading
import logging
from datetime import datetime

class MQTTDiscoveryService:
    """Služba pre automatické zisťovanie MQTT brokera na sieti.
    
    Vysiela UDP broadcast s informáciami o MQTT brokeri, aby sa zariadenia
    mohli automaticky nakonfigurovať bez potreby manuálneho nastavenia IP adresy.
    """
    
    def __init__(self, broker_ip="0.0.0.0", broker_port=1883, interval=10):
        """Inicializácia služby pre zisťovanie MQTT brokera.
        
        Args:
            broker_ip: IP adresa MQTT brokera
            broker_port: Port MQTT brokera
            interval: Interval vysielania v sekundách
        """
        self.broker_ip = broker_ip
        self.broker_port = broker_port
        self.interval = interval
        self.running = False
        self.broadcast_thread = None
        self.request_thread = None
        self.log = logging.getLogger("mqtt_discovery")
        
    def get_local_ip(self):
        """Získa lokálnu IP adresu zariadenia."""
        try:
            # Vytvorenie socket pripojenia na verejný DNS server
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            self.log.error(f"Chyba pri získavaní lokálnej IP: {e}")
            return "127.0.0.1"
    
    def start_broadcast(self):
        """Spustí vysielanie informácií o MQTT brokeri na sieti."""
        if self.running:
            self.log.warning("Discovery služba už beží")
            return
            
        self.running = True
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True, name="MQTTDiscoveryThread")
        self.broadcast_thread.start()
        
        # Spustenie počúvania na priame požiadavky
        self.request_thread = threading.Thread(target=self._listen_for_requests, daemon=True, name="MQTTDiscoveryRequestThread")
        self.request_thread.start()
        
        self.log.info("MQTT discovery služba spustená")
        
    def stop_broadcast(self):
        """Zastaví vysielanie informácií o MQTT brokeri."""
        self.running = False
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=2)
            self.broadcast_thread = None
        if self.request_thread:
            self.request_thread.join(timeout=2)
            self.request_thread = None
        self.log.info("MQTT discovery služba zastavená")
        
    def _broadcast_loop(self):
        """Slučka pre pravidelné vysielanie informácií o MQTT brokeri."""
        # Ak je broker IP 0.0.0.0, treba zistiť skutočnú lokálnu IP adresu
        if self.broker_ip == "0.0.0.0":
            self.broker_ip = self.get_local_ip()
            
        # Vytvorenie socketu pre UDP broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Port pre discovery
        broadcast_port = 12345
        broadcast_address = ("255.255.255.255", broadcast_port)
            
        self.log.info(f"Vysielam informácie o MQTT brokeri na {self.broker_ip}:{self.broker_port}")
        
        try:
            while self.running:
                # Vytvorenie správy s informáciami o brokeri
                message = {
                    "type": "mqtt_discovery",
                    "broker_ip": self.broker_ip,
                    "broker_port": self.broker_port,
                    "timestamp": datetime.now().isoformat(),
                    "system_id": "home_security_system"
                }
                
                # Konverzia na JSON a odoslanie
                json_message = json.dumps(message).encode("utf-8")
                sock.sendto(json_message, broadcast_address)
                self.log.debug(f"Odoslaná discovery správa: {message}")
                
                # Čakanie pred ďalším vysielaním
                time.sleep(self.interval)
                
        except Exception as e:
            self.log.error(f"Chyba pri vysielaní discovery správ: {e}")
        finally:
            sock.close()
    
    def _listen_for_requests(self):
        """Počúva priame požiadavky na discovery a odpovedá na ne."""
        # Ak je broker IP 0.0.0.0, treba zistiť skutočnú lokálnu IP adresu
        if self.broker_ip == "0.0.0.0":
            self.broker_ip = self.get_local_ip()
            
        # Vytvorenie socketu pre UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Port pre discovery
        discovery_port = 12345
            
        self.log.info(f"Počúvam na požiadavky o discovery na porte {discovery_port}")
        
        try:
            # Binding na discovery port
            sock.bind(("", discovery_port))
            sock.settimeout(1.0)  # Krátky timeout pre pravidelné kontroly self.running
            
            while self.running:
                try:
                    # Čakanie na správu
                    data, addr = sock.recvfrom(1024)
                    self.log.info(f"Prijatá požiadavka od {addr}")
                    
                    # Parsovanie JSON správy
                    try:
                        message = json.loads(data.decode("utf-8"))
                        
                        # Kontrola, či ide o požiadavku na discovery
                        if message.get("type") == "mqtt_discovery_request":
                            # Získanie informácií o zariadení (ak sú dostupné)
                            device_id = message.get("device_id", "unknown_device")
                            device_name = message.get("device_name", "Unknown Device")
                            
                            self.log.info(f"Prijatá požiadavka na discovery od zariadenia {device_id} ({device_name})")
                            
                            # Vytvorenie odpovede
                            response = {
                                "type": "mqtt_discovery_response",
                                "broker_ip": self.broker_ip,
                                "broker_port": self.broker_port,
                                "timestamp": datetime.now().isoformat(),
                                "system_id": "home_security_system"
                            }
                            
                            # Odoslanie odpovede späť zariadeniu
                            json_response = json.dumps(response).encode("utf-8")
                            sock.sendto(json_response, addr)
                            self.log.info(f"Odoslaná odpoveď zariadeniu {device_id} na {addr}")
                    except json.JSONDecodeError:
                        self.log.warning(f"Prijatá neplatná JSON správa od {addr}: {data}")
                    except Exception as e:
                        self.log.error(f"Chyba pri spracovaní požiadavky: {e}")
                except socket.timeout:
                    # Timeout - pokračujeme v kontrole self.running
                    continue
                except Exception as e:
                    self.log.error(f"Chyba pri čakaní na požiadavky: {e}")
        except Exception as e:
            self.log.error(f"Chyba pri počúvaní na požiadavky: {e}")
        finally:
            sock.close()

class MQTTBrokerFinder:
    """Trieda pre vyhľadávanie MQTT brokera na sieti.
    
    Počúva UDP broadcast správy a deteguje informácie o MQTT brokeri.
    """
    
    def __init__(self, timeout=30):
        """Inicializácia hľadača MQTT brokera.
        
        Args:
            timeout: Časový limit v sekundách pre hľadanie brokera
        """
        self.timeout = timeout
        self.log = logging.getLogger("mqtt_finder")
        
    def find_broker(self):
        """Vyhľadá MQTT broker na sieti.
        
        Returns:
            Dictionary s informáciami o brokeri alebo None ak sa nenašiel
        """
        # Port pre discovery
        discovery_port = 12345
        
        # Vytvorenie socketu pre príjem UDP správ
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.timeout)
        
        try:
            # Binding na discovery port
            sock.bind(("", discovery_port))
            self.log.info(f"Čakám na MQTT discovery správu ({self.timeout}s)...")
            
            # Čakanie na správu
            data, addr = sock.recvfrom(1024)
            self.log.info(f"Prijatá správa od {addr}")
            
            # Parsovanie JSON správy
            message = json.loads(data.decode("utf-8"))
            
            if message.get("type") == "mqtt_discovery":
                broker_info = {
                    "broker_ip": message.get("broker_ip"),
                    "broker_port": message.get("broker_port"),
                    "system_id": message.get("system_id"),
                    "timestamp": message.get("timestamp")
                }
                self.log.info(f"Nájdený MQTT broker: {broker_info['broker_ip']}:{broker_info['broker_port']}")
                return broker_info
                
        except socket.timeout:
            self.log.warning(f"Vypršal časový limit ({self.timeout}s) pre hľadanie MQTT brokera")
        except Exception as e:
            self.log.error(f"Chyba pri hľadaní MQTT brokera: {e}")
        finally:
            sock.close()
            
        return None

# Testovanie modulu pri priamom spustení
if __name__ == "__main__":
    # Konfigurácia logovania
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s"
    )
    
    # Test discovery služby
    discovery = MQTTDiscoveryService()
    discovery.start_broadcast()
    
    try:
        print("Služba beží. Stlačte Ctrl+C pre ukončenie.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Ukončenie služby.")
    finally:
        discovery.stop_broadcast()