#!/usr/bin/env bash
# Move to the script's directory
cd "$(dirname "$0")"

# Quick check for python3
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Auto-detecting package manager to install Python..."
    if command -v apt-get &> /dev/null; then
        sudo apt update && sudo apt install -y python3
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --needed --noconfirm python
    else
        echo "Could not auto-install Python. Please install python3 manually."
        exit 1
    fi
fi

# Run the unified Python installer/launcher
python3 run.py "$@"
