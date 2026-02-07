#!/bin/bash
# ============================================================
# Pi Photo Frame - Kiosk Mode Setup Script (Legacy)
# ============================================================
#
# NOTE: For new installations, use scripts/install.sh instead.
# It uses Docker + Caddy (HTTPS) and is simpler to manage.
#
# This script sets up a native (non-Docker) deployment with
# systemd + Chromium kiosk mode.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="pi-photo-frame"

echo "=========================================="
echo "Pi Photo Frame - Kiosk Setup (Legacy)"
echo "=========================================="
echo ""
echo "NOTE: For new installations, consider using scripts/install.sh"
echo "which uses Docker + HTTPS and is easier to manage."
echo ""

# Check if running on a Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null && ! grep -q "BCM" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This doesn't appear to be a Raspberry Pi."
    echo "The script will continue, but some features may not work."
    echo ""
fi

# Update system
echo "[1/7] Updating system packages..."
sudo apt-get update -qq

# Install required packages
echo "[2/7] Installing required packages..."
sudo apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    chromium-browser \
    unclutter \
    xdotool \
    xserver-xorg \
    x11-xserver-utils

# Create virtual environment and install Python dependencies
echo "[3/7] Setting up Python environment..."
cd "$SCRIPT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet -r requirements.txt
deactivate

# Create systemd service for Flask app
echo "[4/7] Creating Flask server service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Pi Photo Frame Web Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment=PATH=$SCRIPT_DIR/venv/bin:/usr/bin
ExecStart=$SCRIPT_DIR/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create autostart directory if it doesn't exist
mkdir -p ~/.config/autostart

# Create kiosk autostart entry
echo "[5/7] Creating kiosk autostart..."
tee ~/.config/autostart/photo-frame-kiosk.desktop > /dev/null <<EOF
[Desktop Entry]
Type=Application
Name=Photo Frame Kiosk
Exec=$SCRIPT_DIR/start_kiosk.sh
X-GNOME-Autostart-enabled=true
EOF

# Create kiosk start script
echo "[6/7] Creating kiosk start script..."
tee "$SCRIPT_DIR/start_kiosk.sh" > /dev/null <<'KIOSKEOF'
#!/bin/bash

# Wait for the Flask server to be ready
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        echo "Server is ready!"
        break
    fi
    sleep 1
done

# Get the display token from auth.json (if it exists)
AUTH_FILE="$(dirname "$0")/auth.json"
DISPLAY_URL="http://localhost:5000/display"

if [ -f "$AUTH_FILE" ]; then
    TOKEN=$(python3 -c "import json; print(json.load(open('$AUTH_FILE')).get('display_token', ''))" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        DISPLAY_URL="http://localhost:5000/display?token=$TOKEN"
    fi
fi

# Disable screen blanking/power management
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after 0.5 seconds of inactivity
unclutter -idle 0.5 -root &

# Start Chromium in kiosk mode
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --no-first-run \
    --start-fullscreen \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000 \
    "$DISPLAY_URL"
KIOSKEOF

chmod +x "$SCRIPT_DIR/start_kiosk.sh"

# Enable and start the service
echo "[7/7] Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "The Flask server is now running."
echo ""
echo "Access the upload page at:"
echo "  http://$(hostname -I | awk '{print $1}'):5000/upload"
echo "  or http://$(hostname).local:5000/upload"
echo ""
echo "To complete kiosk setup, reboot your Pi:"
echo "  sudo reboot"
echo ""
echo "After reboot, the display will automatically show photos."
echo ""
echo "Useful commands:"
echo "  - Check server status: sudo systemctl status ${SERVICE_NAME}"
echo "  - View server logs: journalctl -u ${SERVICE_NAME} -f"
echo "  - Restart server: sudo systemctl restart ${SERVICE_NAME}"
echo "  - Stop kiosk (press): Ctrl+Alt+F1 (to switch to terminal)"
echo ""
