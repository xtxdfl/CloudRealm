#!/bin/bash
# Cloud Agent Installation Script
# Version: 1.0.0

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/usr/local/cloud-agent"
LOG_DIR="/usr/local/cloud-agent/log"

echo "=== Cloud Agent Installer ==="
echo "Version: 1.0.0"
echo "Install Directory: $INSTALL_DIR"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/python"
mkdir -p "$INSTALL_DIR/conf"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$LOG_DIR"