#!/usr/bin/env bash
# One-time setup for Raspberry Pi Zero 2 W with Adafruit RGB Matrix HAT
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Flight Tracker LED — Pi Setup ==="

# ── System packages ──────────────────────────────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update
sudo apt-get install -y \
    python3-dev python3-pip python3-pillow \
    git build-essential

# ── rpi-rgb-led-matrix ──────────────────────────────────────────────
RGB_MATRIX_DIR="/opt/rpi-rgb-led-matrix"
if [ ! -d "$RGB_MATRIX_DIR" ]; then
    echo "[2/5] Cloning rpi-rgb-led-matrix..."
    sudo git clone https://github.com/hzeller/rpi-rgb-led-matrix.git "$RGB_MATRIX_DIR"
else
    echo "[2/5] rpi-rgb-led-matrix already cloned, pulling latest..."
    sudo git -C "$RGB_MATRIX_DIR" pull
fi

echo "[3/5] Building rpi-rgb-led-matrix Python bindings..."
cd "$RGB_MATRIX_DIR"
sudo make build-python PYTHON="$(which python3)"
sudo make install-python PYTHON="$(which python3)"

# ── Python dependencies ─────────────────────────────────────────────
echo "[4/5] Installing Python dependencies..."
pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null \
    || pip3 install -r "$SCRIPT_DIR/requirements.txt"

# ── Disable onboard audio (conflicts with GPIO) ─────────────────────
echo "[5/5] Disabling onboard audio..."
BOOT_CONFIG="/boot/config.txt"
if [ -f "/boot/firmware/config.txt" ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
fi

if grep -q "^dtparam=audio=on" "$BOOT_CONFIG" 2>/dev/null; then
    sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$BOOT_CONFIG"
    echo "  Audio disabled in $BOOT_CONFIG (reboot required)"
elif ! grep -q "dtparam=audio" "$BOOT_CONFIG" 2>/dev/null; then
    echo "dtparam=audio=off" | sudo tee -a "$BOOT_CONFIG" > /dev/null
    echo "  Audio disabled in $BOOT_CONFIG (reboot required)"
else
    echo "  Audio already disabled"
fi

# ── Optional: systemd service ────────────────────────────────────────
read -rp "Create systemd service for auto-start at boot? [y/N] " CREATE_SERVICE
if [[ "${CREATE_SERVICE,,}" == "y" ]]; then
    sudo tee /etc/systemd/system/flight-tracker.service > /dev/null <<EOF
[Unit]
Description=Flight Tracker LED Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$(which python3) $SCRIPT_DIR/main.py
WorkingDirectory=$SCRIPT_DIR
Restart=on-failure
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable flight-tracker.service
    echo "  Service created and enabled. Start with: sudo systemctl start flight-tracker"
fi

echo ""
echo "=== Setup complete ==="
echo "1. Edit config.py to set HOME_LAT and HOME_LON"
echo "2. Reboot if audio was just disabled"
echo "3. Run: sudo python3 $SCRIPT_DIR/main.py"
