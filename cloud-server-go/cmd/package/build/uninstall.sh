#!/bin/bash
# Cloud Agent Uninstallation Script

set -e

INSTALL_DIR="/usr/local/cloud-agent"

echo "=== Cloud Agent Uninstaller ==="

if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root"
    exit 1
fi

echo "Stopping service..."
if [ -f /etc/init.d/cloud-agent ]; then
    service cloud-agent stop 2>/dev/null || true
fi

echo "Removing files..."
rm -rf "$INSTALL_DIR"

echo "=== Uninstallation Complete ==="
exit 0