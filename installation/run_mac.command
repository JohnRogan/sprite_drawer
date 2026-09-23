#!/bin/bash
# Starts Sprite Drawer on macOS. Run installation/install_mac.command once first.

cd "$(dirname "$0")/.." || exit 1

if [ ! -x .venv/bin/python ]; then
    echo
    echo "Sprite Drawer is not installed yet. Run installation/install_mac.command first."
    echo
    exit 1
fi

exec .venv/bin/python main.py
