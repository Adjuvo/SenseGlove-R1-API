#!/usr/bin/env bash
# Installs the udev rule that allows non-root access to the SenseGlove R1 device over USB in Linux.
set -euo pipefail

RULE_FILE="/etc/udev/rules.d/99-rembrandt.rules"
RULE_CONTENT='SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="10f3", MODE="0666"'

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script only applies to Linux. On Windows, install the Zadig WinUSB driver instead (see docs/python_getting_started.md)." >&2
    exit 1
fi

if [[ -f "$RULE_FILE" ]] && grep -qF "$RULE_CONTENT" "$RULE_FILE"; then
    echo "udev rule already installed at $RULE_FILE"
else
    echo "Installing udev rule to $RULE_FILE (requires sudo)..."
    echo "$RULE_CONTENT" | sudo tee "$RULE_FILE" > /dev/null
fi

echo "Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Done. Unplug and replug the glove for the new permissions to take effect."
