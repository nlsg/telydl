#!/bin/bash
set -e

SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="telydl.service"

echo "Installing TelyDl systemd service..."

mkdir -p "$SERVICE_DIR"
cp "$SERVICE_FILE" "$SERVICE_DIR/"

systemctl --user stop "$SERVICE_FILE"
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_FILE"
systemctl --user start "$SERVICE_FILE"

echo "TelyDl service installed successfully."
echo "To start the service, run: systemctl --user start $SERVICE_FILE"
echo "To check status, run: systemctl --user status $SERVICE_FILE"

watch systemctl --user status "$SERVICE_FILE"

