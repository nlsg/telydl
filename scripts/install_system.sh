#!/bin/bash
set -e

SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_DIR="/etc/systemd/system"
SERVICE_FILE="telydl.service"

echo "Installing TelyDl systemd service..."

mkdir -p "$SERVICE_DIR"

sed 's|^WorkingDirectory=.*|WorkingDirectory=/opt/telydl|' "$SERVICE_FILE" > "$SERVICE_DIR/$SERVICE_FILE"

systemctl stop "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable "$SERVICE_FILE"
systemctl start "$SERVICE_FILE"

echo "TelyDl service installed successfully."
echo "To start the service, run: systemctl --user start $SERVICE_FILE"
echo "To check status, run: systemctl --user status $SERVICE_FILE"

watch systemctl status "$SERVICE_FILE"

