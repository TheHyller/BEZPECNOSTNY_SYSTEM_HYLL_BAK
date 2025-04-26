# Home Security System - Technical Documentation

## 1. System Overview

The Home Security System represents a comprehensive and modular security solution designed for residential environments, featuring distributed sensor networks with multichannel communication protocols. The architecture implements a multi-tiered approach to security monitoring, incorporating various hardware platforms including Raspberry Pi and ESP microcontrollers, centralized through an MQTT message broker infrastructure.

The system operates on a publisher-subscriber communication paradigm, facilitating real-time data exchange between heterogeneous components while maintaining robust fault tolerance through automatic broker discovery mechanisms and connection management algorithms.

## 2. System Architecture

### 2.1 High-Level Architecture

The Home Security System employs a distributed architecture consisting of three primary components:

1. **Sender Modules (SEND)**: Raspberry Pi-based units responsible for interfacing with physical sensors (motion detectors, door/window contact sensors) and capturing camera imagery. These modules function as data acquisition endpoints that monitor environmental changes and transmit event notifications to the central system.

2. **ESP-based Sender Modules (ESP_SEND)**: Microcontroller-based sensors utilizing ESP8266/ESP32 platforms, providing wireless sensor nodes with reduced power consumption profiles. These modules extend the system's coverage through strategic deployment in areas where full Raspberry Pi implementation would be impractical.

3. **Receiver Module (REC)**: A centralized processing unit implementing both graphical user interface (Kivy framework) and web interface (Flask framework) for system monitoring, configuration management, and responsive notifications. This module serves as the system's command center, processing incoming sensor data and executing appropriate response protocols.

4. **MQTT Communication Layer**: Message Queuing Telemetry Transport protocol facilitates asynchronous communication between all system components, ensuring reliable data transmission with configurable quality of service parameters.

### 2.2 Data Flow

```
┌─────────────┐         MQTT         ┌─────────────┐
│  SEND Unit  │◄──────Messages─────►│    MQTT     │
│ (Raspberry) │                      │   Broker    │
└─────────────┘                      │             │
                                     │             │
┌─────────────┐         MQTT         │             │
│ ESP_SEND    │◄──────Messages─────►│             │
│  (ESP8266)  │                      │             │
└─────────────┘                      └──────┬──────┘
                                            │
                                            │ MQTT
                                            │ Messages
                                            ▼
                                     ┌─────────────┐
                                     │  REC Unit   │
                                     │  (Receiver) │
                                     └─────────────┘
                                            │
                                 ┌──────────┴──────────┐
                                 │                     │
                          ┌──────▼─────┐        ┌──────▼─────┐
                          │  Kivy GUI  │        │  Flask Web │
                          │ Interface  │        │  Interface │
                          └────────────┘        └────────────┘
```

## 3. Component Description

### 3.1 SEND Module (Raspberry Pi)

The SEND module functions as a sophisticated data acquisition unit, interfacing with physical security sensors through GPIO connections while implementing extensive error handling and connection management protocols.

**Key Features:**
- **Multi-sensor Integration**: Interfaces with motion sensors, door contacts, window sensors through configurable GPIO pins
- **Automated MQTT Broker Discovery**: Implements UDP-based network discovery protocol to locate MQTT brokers dynamically
- **Camera Integration**: Captures and transmits images upon motion detection events
- **Environmental Awareness**: Contextualizes sensor data with location information (room designation)
- **Persistent Connection Management**: Implements advanced reconnection strategies with exponential backoff algorithms

**Primary Files:**
- `SEND/SEND.py`: Main implementation for Raspberry Pi sensors and camera functionality
- `SEND/config.json`: Configuration parameters for sensors, MQTT, and camera settings

### 3.2 ESP_SEND Module (ESP8266/ESP32)

The ESP_SEND module represents a lightweight sensor node implementation optimized for power efficiency while maintaining core security monitoring capabilities.

**Key Features:**
- **Low-Power Operation**: Optimized for battery operation with configurable reporting intervals
- **Motion Detection**: Incorporates motion sensors for area monitoring
- **Dynamic Network Configuration**: Supports both static and automatic broker discovery
- **Remote Manageability**: Responds to control commands for status reporting and configuration updates
- **Device Identification**: Broadcasts detailed device metadata facilitating automatic integration

**Primary Files:**
- `ESP_SEND/ESP_SEND.ino`: Arduino implementation for ESP8266/ESP32 microcontrollers

### 3.3 REC Module (Receiver)

The REC module represents the system's central intelligence hub, processing incoming sensor data, managing device inventory, and providing multi-modal user interfaces for system interaction.

**Key Features:**
- **Dual Interface Paradigm**: Implements both desktop application (Kivy) and web interface (Flask)
- **Event Processing Engine**: Analyzes incoming sensor data for security implications
- **Notification System**: Multi-channel alerting through visual, auditory, and potentially mobile notifications
- **Configuration Management**: Centralized management of system parameters and device configurations
- **Authentication System**: Role-based access control for system operation
- **Historical Data Analysis**: Event logging with retrieval and analysis capabilities

**Primary Files:**
- `REC/main.py`: Core application initialization and event handling
- `REC/mqtt_client.py`: Sophisticated MQTT client implementation with advanced error handling
- `REC/web_app.py`: Web interface implementation using Flask
- `REC/dashboard_screen.py`, `REC/alerts_screen.py`, etc.: Individual screen implementations for Kivy UI
- `REC/config/`: Configuration management modules for devices, system state, and settings

## 4. Communication Protocol

### 4.1 MQTT Topic Structure

The system utilizes a hierarchical topic structure for MQTT communications:

- `home/security/sensors/{device_id}`: Sensor data publications
- `home/security/status/{device_id}`: Device status information (online/offline states)
- `home/security/control/{device_id}`: Command and control messages
- `home/security/images/{device_id}`: Image data from camera-enabled devices

### 4.2 Message Format

All messages utilize JSON formatting for structured data exchange:

**Sensor Message Example:**
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

**Status Message Example:**
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

### 4.3 Discovery Protocol

The system implements an innovative UDP-based discovery mechanism to automatically locate MQTT brokers on the network:

1. Sender modules broadcast UDP discovery requests on port 12345
2. The receiver responds with broker location information
3. Sender modules establish MQTT connections using discovered parameters

This approach eliminates manual configuration requirements, facilitating plug-and-play deployment scenarios.

## 5. Data Storage

### 5.1 File Structure

The system utilizes JSON-based configuration and state storage:

- `data/devices.json`: Device inventory and metadata
- `data/device_status.json`: Current operational status of all devices
- `data/system_state.json`: System-wide state variables
- `data/settings.json`: User-configurable system parameters
- `data/alerts.log`: Chronological record of security events

### 5.2 Image Storage

Camera-captured images are stored with the following nomenclature:
`data/images/{device_id}_{timestamp}.jpg`

## 6. User Interfaces

### 6.1 Kivy GUI

The desktop application presents an intuitive user interface comprising multiple specialized screens:

- **Dashboard Screen**: System overview with key status indicators
- **Sensor Screen**: Detailed sensor status visualization with historical data
- **Alerts Screen**: Chronological list of security events with alert management
- **Settings Screen**: System configuration parameters
- **Login Screen**: Authentication interface with role-based access control

### 6.2 Web Interface

The Flask-based web interface provides remote access capabilities:

- Real-time sensor monitoring through WebSocket communications
- Mobile-responsive design for multi-device accessibility
- MQTT status visualization
- Sensor status dashboards

## 7. Technical Implementation Details

### 7.1 Multi-threading Architecture

The system employs sophisticated multi-threading to maintain responsiveness:

- Dedicated thread for MQTT communications
- Separate thread for web server operation
- Background threads for sensor monitoring and alert processing
- Main thread for UI rendering and event processing

### 7.2 Error Handling and Resilience

Robust error handling mechanisms ensure system stability:

- Exponential backoff for reconnection attempts
- Graceful degradation during component failures
- Persistent connection monitoring with automated recovery
- Comprehensive exception handling with detailed logging

### 7.3 Security Considerations

The system implements several security measures:

- TLS support for encrypted MQTT communications
- Authentication for both MQTT and web interfaces
- Last Will and Testament (LWT) for reliable device status tracking
- Configurable quality of service levels for message delivery guarantees

## 8. Configuration Parameters

### 8.1 MQTT Configuration

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

### 8.2 Sensor Configuration

Sensor parameters are configured through GPIO pin assignments and behavior settings:

- **Motion Sensors**: Configurable sensitivity and reset intervals
- **Door/Window Contacts**: Normally open/closed configuration
- **Camera Settings**: Resolution, frame rate, and rotation parameters

## 9. Installation and Setup

### 9.1 Prerequisites

- Mosquitto MQTT broker
- Python 3.8+ for REC and SEND modules
- Arduino IDE with ESP8266/ESP32 support for ESP_SEND modules
- Required Python packages as specified in requirements.txt

### 9.2 Installation Steps

1. Install the MQTT broker according to mosquitto_install.md
2. Install Python dependencies using the requirements files:
   - `pip install -r requirements.txt`
   - For Raspberry Pi: `pip install -r requirements_pi.txt`
3. Configure the system parameters in data/*.json files
4. Program ESP devices using Arduino IDE with ESP_SEND.ino
5. Deploy Raspberry Pi units with SEND.py
6. Launch the receiver with main.py

## 10. System Operations

### 10.1 Operational States

The system defines several operational states:

- **Disarmed**: Monitoring active but no alerts generated
- **Armed Home**: Perimeter sensors active, interior motion sensors inactive
- **Armed Away**: All sensors active with extended entry delay
- **Alarm**: Active security breach detected, notifications triggered

### 10.2 Event Handling

The system processes events according to the following workflow:

1. Sensor activation generates MQTT message
2. Receiver processes message against current system state
3. If alarm conditions met, notification sequence initiated
4. Event logged to persistent storage
5. UI elements updated to reflect current status

## 11. Extensibility

The modular architecture facilitates system expansion through:

- Additional sensor types through standardized MQTT message format
- Integration with third-party systems via MQTT bridge capability
- Custom notification channels through the notification service
- Additional UI views through Kivy screen manager

## 12. Future Development Considerations

Potential enhancements for future versions:

- AI-based motion detection for false alarm reduction
- Cloud integration for remote monitoring
- Mobile application development
- Voice assistant integration
- Expanded sensor types (smoke, water, gas)