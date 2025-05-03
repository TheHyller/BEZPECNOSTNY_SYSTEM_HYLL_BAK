#!/bin/bash
# Script to launch only the SEND module of the Security System

# Set working directory to script directory
cd "$(dirname "$0")"

# Display startup message
echo "Launching SEND module..."

# Check if Mosquitto is running, if not start it
if ! pgrep mosquitto > /dev/null; then
    echo "Starting Mosquitto MQTT broker..."
    sudo systemctl start mosquitto
    # Wait for Mosquitto initialization
    sleep 5
else
    echo "Mosquitto MQTT broker is already running."
fi

# Launch the SEND module
echo "Starting SEND module..."
cd SEND
nohup python3 SEND.py > send.log 2>&1 &

echo "SEND module has been successfully launched!"
echo "Check the send.log file in the SEND directory for more information."