#!/usr/bin/env bash
# ===========================================================================
#  Baut eine eigenstaendige Programmdatei (Linux/macOS) des CV-Downloaders.
#  Nutzung:  bash build.sh
#  Voraussetzung: Python 3.10+
# ===========================================================================
set -euo pipefail

echo "[1/3] Abhaengigkeiten installieren..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller

echo "[2/3] Programmdatei bauen..."
pyinstaller --noconfirm --onefile \
    --name FranceTravailCVDownloader \
    --collect-all playwright \
    cv_downloader.py

echo "[3/3] Fertig! Datei: dist/FranceTravailCVDownloader"
echo "(Beim ersten Start wird Chromium automatisch nachgeladen.)"
