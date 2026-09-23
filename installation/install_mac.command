#!/bin/bash
# Sprite Drawer installer for macOS.
# Installs Python 3.14 (if missing), creates a private .venv in the project
# folder, and installs the packages from requirements.txt into it.

cd "$(dirname "$0")/.." || exit 1

PY_VERSION="3.14.3"
PY_PKG_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-macos11.pkg"

fail() {
    echo
    echo "INSTALL FAILED: $1"
    echo
    exit 1
}

find_python() {
    PY=""
    for candidate in \
        "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14" \
        "/opt/homebrew/bin/python3.14" \
        "/usr/local/bin/python3.14" \
        "$(command -v python3.14 2>/dev/null)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ] \
            && "$candidate" -c "import sys" >/dev/null 2>&1; then
            PY="$candidate"
            return 0
        fi
    done
    return 1
}

echo
echo "=============================================="
echo "  Sprite Drawer installer (macOS)"
echo "=============================================="
echo

echo "[1/3] Checking for Python 3.14..."
if find_python; then
    echo "      Found: $PY"
else
    echo "      Not found. Downloading Python ${PY_VERSION} from python.org..."
    PKG="/tmp/python-${PY_VERSION}-macos11.pkg"
    curl -L --fail --progress-bar -o "$PKG" "$PY_PKG_URL" \
        || fail "Could not download Python. Check your internet connection and try again."
    echo
    echo "      Installing Python. Your Mac will ask for your login password."
    echo "      (Nothing appears on screen while you type it. That is normal.)"
    echo
    sudo installer -pkg "$PKG" -target / \
        || fail "Python could not be installed."
    rm -f "$PKG"
    find_python || fail "Python was installed but could not be found. Restart your Mac and run this installer again."
    echo "      Installed: $PY"
fi

echo
echo "[2/3] Setting up Sprite Drawer's private Python environment..."
if [ -x .venv/bin/python ] \
    && .venv/bin/python -c "import sys; sys.exit(sys.version_info[:2] != (3, 14))" >/dev/null 2>&1; then
    echo "      Already set up."
else
    rm -rf .venv
    "$PY" -m venv .venv || fail "Could not create the environment."
    echo "      Done."
fi

echo
echo "[3/3] Installing packages (this can take a few minutes)..."
.venv/bin/python -m pip install --disable-pip-version-check --upgrade pip \
    || fail "Could not update pip. Check your internet connection and try again."
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt \
    || fail "Could not install packages. Check your internet connection and try again."
.venv/bin/python -c "import PySide6.QtWidgets, PySide6.QtPdf, PIL, pillow_heif" \
    || fail "Packages installed but could not be loaded."

echo
echo "=============================================="
echo "  Install complete!"
echo "  Next: read CONTROLS.md, then start the app"
echo "  with installation/run_mac.command (see README.md)."
echo "=============================================="
echo
