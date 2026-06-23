#!/usr/bin/env python3
"""
France Travail – automatischer CV-Downloader (Recruiter-Workflow)

Was das Tool macht:
  - Öffnet die France-Travail-Recruiter-Seite in einem (optional unsichtbaren)
    Browser.
  - Du loggst dich beim ersten Start EINMAL selbst ein (inkl. 2FA). Die Session
    wird lokal gespeichert, danach laeuft alles automatisch im Hintergrund.
  - Geht die Liste der Kandidaten/Bewerber durch.
  - Laedt das CV herunter, wenn eines vorhanden ist.
  - Ueberspringt den Eintrag sofort, wenn es kein CV gibt.
  - Speichert alle CVs in einem eigenen Ordner.
  - Merkt sich bereits geladene CVs -> beim erneuten Start wird nichts doppelt
    geladen (resume-faehig).

WICHTIG: Nur fuer den eigenen, legitimen Recruiter-Zugang verwenden. CVs sind
personenbezogene Daten (DSGVO). Verarbeite sie nur im Rahmen deiner Berechtigung
und der Nutzungsbedingungen von France Travail.

Bedienung:
  pip install -r requirements.txt
  playwright install chromium
  python cv_downloader.py --login        # einmalig: Browser oeffnet, du loggst dich ein
  python cv_downloader.py                 # laeuft im Hintergrund und laedt CVs

Die CSS-Selektoren unten (Abschnitt SELECTORS) muessen ggf. an das aktuelle
France-Travail-Layout angepasst werden – sie sind klar markiert.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import (
    Error as PWError,
    TimeoutError as PWTimeout,
    sync_playwright,
)


def base_dir() -> Path:
    """Ordner, in dem das Programm/die .exe liegt (auch im PyInstaller-Build)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def ensure_chromium() -> None:
    """Stellt sicher, dass der Chromium-Browser installiert ist.

    Bei der gebauten .exe ist der Browser nicht enthalten, deshalb wird er
    beim ersten Start automatisch nachgeladen (idempotent, danach gecached).
    Funktioniert auch im PyInstaller-Frozen-Modus ueber den Playwright-Driver.
    """
    # Browser neben das Programm legen, damit alles portabel bleibt.
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH", str(base_dir() / "ms-playwright")
    )
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
        if exe and Path(exe).exists():
            return  # Browser schon vorhanden
    except PWError:
        pass

    log("Chromium wird einmalig heruntergeladen (kann etwas dauern)...")
    try:
        from playwright._impl._driver import (
            compute_driver_executable,
            get_driver_env,
        )

        driver = compute_driver_executable()
        cmd = list(driver) if isinstance(driver, (list, tuple)) else [str(driver)]
        subprocess.run(
            [*cmd, "install", "chromium"], env=get_driver_env(), check=True
        )
    except Exception:  # noqa: BLE001 - Fallback fuer Nicht-Frozen-Umgebung
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"], check=True
        )
    log("Chromium ist bereit.")

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

# Startseite des Recruiter-Bereichs mit der Kandidaten-/Bewerberliste.
# Passe das ggf. an die konkrete Such-/Ergebnisseite an, die du nutzt.
START_URL = "https://candidat.francetravail.fr/"

# Ordner, in dem die CVs landen (eigener Folder, neben dem Programm/der .exe).
OUTPUT_DIR = base_dir() / "cv_downloads"

# Datei mit dem gespeicherten Login (Cookies/Session).
STORAGE_STATE = base_dir() / ".ft_session.json"

# Liste bereits geladener CVs (zum Ueberspringen beim naechsten Lauf).
SEEN_FILE = OUTPUT_DIR / "_geladen.json"

# Hoeflichkeitspause zwischen zwei Kandidaten (Sekunden), damit die Plattform
# nicht ueberlastet wird.
DELAY_BETWEEN = 2.0

# Wie lange (ms) auf Elemente gewartet wird, bevor "nicht vorhanden" gilt.
WAIT_MS = 6000

# --------------------------------------------------------------------------- #
# SELECTORS – hier ggf. an das aktuelle Layout anpassen
# --------------------------------------------------------------------------- #
SELECTORS = {
    # Jede Karte/Zeile eines Kandidaten in der Ergebnisliste.
    "candidate_card": "[data-test-id='profil-card'], .profil-card, article.resultat",
    # Link/Button, der das Kandidatenprofil oeffnet (relativ zur Karte).
    "open_profile": "a, button",
    # Der Download-/CV-Button im geoeffneten Profil.
    "cv_download": (
        "a:has-text('CV'), button:has-text('CV'), "
        "a:has-text('Télécharger'), a[href$='.pdf'], a[download]"
    ),
    # Zurueck-zur-Liste-Button (falls Profil als eigene Seite oeffnet).
    "back_to_list": "button:has-text('Retour'), a:has-text('Retour')",
    # Name des Kandidaten (fuer den Dateinamen).
    "candidate_name": "h1, h2, [data-test-id='nom-candidat']",
    # "Naechste Seite"-Button der Ergebnisliste (Pagination).
    "next_page": "a[rel='next'], button:has-text('Suivant'), .pagination-next",
}


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #

def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def safe_filename(name: str, fallback: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^\w\-. ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or fallback


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# Login (einmalig, sichtbarer Browser)
# --------------------------------------------------------------------------- #

def do_login() -> None:
    ensure_chromium()
    log("Login-Modus: Browser oeffnet sich. Bitte einloggen (inkl. 2FA).")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(START_URL)
        print(
            "\n>>> Logge dich jetzt im Browser ein.\n"
            ">>> Wenn du fertig und auf der Kandidatenliste bist, hier ENTER "
            "druecken...\n"
        )
        input()
        context.storage_state(path=str(STORAGE_STATE))
        browser.close()
    log(f"Session gespeichert in {STORAGE_STATE}. Jetzt: 'python cv_downloader.py'")


# --------------------------------------------------------------------------- #
# Ein einzelnes Profil verarbeiten
# --------------------------------------------------------------------------- #

def download_cv_for_card(page, card, index: int, seen: set[str]) -> str:
    """Oeffnet ein Profil, laedt das CV (falls vorhanden) und kehrt zurueck.

    Rueckgabe: 'downloaded' | 'skipped' | 'already'
    """
    # Profil oeffnen
    try:
        opener = card.locator(SELECTORS["open_profile"]).first
        opener.click(timeout=WAIT_MS)
    except PWTimeout:
        log(f"  #{index}: Profil konnte nicht geoeffnet werden -> skip")
        return "skipped"

    page.wait_for_load_state("networkidle", timeout=WAIT_MS)

    # Name fuer Dateinamen / Dedupe
    try:
        raw_name = page.locator(SELECTORS["candidate_name"]).first.inner_text(
            timeout=WAIT_MS
        )
    except PWTimeout:
        raw_name = ""
    key = safe_filename(raw_name, f"kandidat_{index}")

    if key in seen:
        log(f"  #{index}: '{key}' bereits geladen -> skip")
        _go_back(page)
        return "already"

    # Gibt es ueberhaupt ein CV?
    cv_btn = page.locator(SELECTORS["cv_download"]).first
    try:
        cv_btn.wait_for(state="visible", timeout=WAIT_MS)
    except PWTimeout:
        log(f"  #{index}: '{key}' hat kein CV -> skip")
        _go_back(page)
        return "skipped"

    # CV herunterladen
    try:
        with page.expect_download(timeout=WAIT_MS * 2) as dl_info:
            cv_btn.click()
        download = dl_info.value
        suffix = Path(download.suggested_filename).suffix or ".pdf"
        target = OUTPUT_DIR / f"{key}{suffix}"
        # Bei Namensgleichheit nicht ueberschreiben.
        n = 2
        while target.exists():
            target = OUTPUT_DIR / f"{key}_{n}{suffix}"
            n += 1
        download.save_as(str(target))
        seen.add(key)
        save_seen(seen)
        log(f"  #{index}: CV gespeichert -> {target.name}")
        _go_back(page)
        return "downloaded"
    except PWTimeout:
        log(f"  #{index}: '{key}' CV-Download fehlgeschlagen -> skip")
        _go_back(page)
        return "skipped"


def _go_back(page) -> None:
    """Zurueck zur Ergebnisliste (Button bevorzugt, sonst Browser-Back)."""
    back = page.locator(SELECTORS["back_to_list"]).first
    try:
        if back.is_visible(timeout=1500):
            back.click()
            page.wait_for_load_state("networkidle", timeout=WAIT_MS)
            return
    except PWTimeout:
        pass
    page.go_back(wait_until="networkidle")


# --------------------------------------------------------------------------- #
# Hauptlauf
# --------------------------------------------------------------------------- #

def run(headless: bool = True) -> None:
    if not STORAGE_STATE.exists():
        log("Keine gespeicherte Session gefunden – starte zuerst den Login.")
        do_login()
        if not STORAGE_STATE.exists():
            log("Login wurde nicht abgeschlossen. Abbruch.")
            return

    ensure_chromium()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seen = load_seen()
    stats = {"downloaded": 0, "skipped": 0, "already": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=str(STORAGE_STATE), accept_downloads=True
        )
        page = context.new_page()
        log(f"Oeffne {START_URL}")
        page.goto(START_URL, wait_until="networkidle")

        page_num = 1
        while True:
            log(f"--- Ergebnisseite {page_num} ---")
            try:
                page.wait_for_selector(SELECTORS["candidate_card"], timeout=WAIT_MS)
            except PWTimeout:
                log("Keine Kandidaten auf dieser Seite gefunden. Ende.")
                break

            count = page.locator(SELECTORS["candidate_card"]).count()
            log(f"{count} Kandidaten auf dieser Seite.")

            for i in range(count):
                # Karte bei jeder Iteration neu greifen (DOM kann sich aendern).
                card = page.locator(SELECTORS["candidate_card"]).nth(i)
                result = download_cv_for_card(page, card, i + 1, seen)
                stats[result] += 1
                time.sleep(DELAY_BETWEEN)

            # Naechste Seite?
            nxt = page.locator(SELECTORS["next_page"]).first
            try:
                if not nxt.is_visible(timeout=2000):
                    log("Keine weitere Seite. Fertig.")
                    break
                nxt.click()
                page.wait_for_load_state("networkidle", timeout=WAIT_MS)
                page_num += 1
            except PWTimeout:
                log("Keine weitere Seite. Fertig.")
                break

        browser.close()

    log(
        f"Abgeschlossen. Geladen: {stats['downloaded']}, "
        f"uebersprungen (kein CV/Fehler): {stats['skipped']}, "
        f"bereits vorhanden: {stats['already']}."
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="France Travail – automatischer CV-Downloader"
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Einmaliger sichtbarer Login; speichert die Session.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Browser sichtbar laufen lassen (Debug). Standard: Hintergrund.",
    )
    args = parser.parse_args()

    try:
        if args.login:
            do_login()
        else:
            run(headless=not args.show)
    finally:
        # Bei der .exe (Doppelklick) Fenster offen halten, sonst schliesst es sofort.
        if getattr(sys, "frozen", False):
            input("\nFertig. ENTER zum Schliessen...")


if __name__ == "__main__":
    main()
