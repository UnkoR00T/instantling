#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"

if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "tkinter not found, installing it (needs sudo)..."
    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm tk
    elif command -v apt-get >/dev/null 2>&1; then
        sudo apt-get install -y python3-tk
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3-tkinter
    elif command -v zypper >/dev/null 2>&1; then
        sudo zypper install -y python3-tk
    else
        echo "Couldn't detect your package manager. Install tkinter manually." >&2
        exit 1
    fi
fi

if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install selenium
fi

exec .venv/bin/python instant.py "$@"
