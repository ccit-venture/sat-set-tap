#!/bin/bash
# setup_raspi.sh — jalankan sekali di RPi (sebagai user pi)
# Siapkan dependency, folder deploy, dan aktifkan service systemd.
#
# Asumsi:
#   - Repo di-clone ke /home/pi/sat-set-tap (branch master)
#   - User pi punya akses sudo
#
# Usage:
#   git clone https://github.com/ccit-venture/sat-set-tap.git /home/pi/sat-set-tap
#   cd /home/pi/sat-set-tap
#   bash raspi/setup/setup_raspi.sh

set -e

DEPLOY_DIR="/home/pi/sat-set-tap"
RASPI_DIR="$DEPLOY_DIR/raspi"

echo "=== Sat Set Tap — Raspberry Pi Setup ==="
echo "Deploy dir: $DEPLOY_DIR"
echo ""

# 1. Update & install Redis + Python deps
echo "[1/4] Install Redis & Python packages..."
sudo apt update -q
sudo apt install -y redis-server python3-pip python3-venv socat
pip3 install --break-system-packages -r "$RASPI_DIR/requirements.txt"

# 2. Aktifkan Redis saat boot
echo "[2/4] Enable Redis service..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Cek Redis jalan
if redis-cli ping | grep -q "PONG"; then
    echo "      ✓ Redis OK"
else
    echo "      ✗ Redis gagal start — cek: sudo systemctl status redis-server"
    exit 1
fi

# 3. Setup environment
echo "[3/4] Setup .env dari template..."
if [ ! -f "$RASPI_DIR/backend/.env" ]; then
    cp "$RASPI_DIR/backend/.env.example" "$RASPI_DIR/backend/.env"
    echo "      ✓ .env dibuat dari template"
    echo "      ⚠  Edit $RASPI_DIR/backend/.env (isi REDIS_PASS, SERIAL_PORT, dll)"
else
    echo "      ✓ .env sudah ada"
fi

# 4. Install systemd services (auto-start saat boot)
echo "[4/4] Install systemd services..."
sudo cp "$RASPI_DIR/setup/satset-dashboard.service" /etc/systemd/system/
sudo cp "$RASPI_DIR/setup/satset-receiver.service"  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable satset-dashboard satset-receiver
sudo systemctl start  satset-dashboard satset-receiver

echo ""
echo "=== Setup selesai! ==="
echo ""
echo "Cek status:  sudo systemctl status satset-dashboard satset-receiver"
echo "Cek log:     journalctl -u satset-receiver -f"
echo "Dashboard:   http://<tailscale-ip>:8080"
