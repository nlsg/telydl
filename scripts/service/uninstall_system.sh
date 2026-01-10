#!/bin/bash
set -e

SERVICE_FILE="telydl.service"

echo "Uninstalling TelyDl systemd service..."

systemctl --user stop "$SERVICE_FILE" || true
systemctl --user disable "$SERVICE_FILE" || true

# rm -f "$HOME/.config/systemd/user/$SERVICE_FILE"
rm -f "/etc/systemd/system/$SERVICE_FILE"

systemctl daemon-reload

echo "TelyDl service uninstalled successfully."
