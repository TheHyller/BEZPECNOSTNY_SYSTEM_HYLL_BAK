#!/bin/bash
# Script to launch only the REC module of the Security System

# Set working directory to script directory
cd "$(dirname "$0")"

# Display startup message
echo "Launching REC module..."

# Check if Mosquitto is running, if not start it
if ! pgrep mosquitto > /dev/null; then
    echo "Starting Mosquitto MQTT broker..."
    sudo systemctl start mosquitto
    # Wait for Mosquitto initialization
    sleep 5
else
    echo "Mosquitto MQTT broker is already running."
fi

# Launch the REC module components
cd REC

# Launch the web application
echo "Starting REC web application..."
nohup python3 web_app.py > web_app.log 2>&1 &

# Launch the desktop application if we're in a graphical environment
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    echo "Starting REC desktop application..."
    nohup python3 main.py > main.log 2>&1 &
else
    echo "No display detected. Skipping desktop application launch."
fi

echo "REC module has been successfully launched!"
echo "Check the web_app.log and main.log files in the REC directory for more information."