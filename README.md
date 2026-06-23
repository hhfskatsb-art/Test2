# France Travail – automatischer CV-Downloader

Tool, das im Hintergrund auf France Travail (Recruiter-Bereich) automatisch die
CVs der Kandidaten herunterlädt, Einträge **ohne CV sofort überspringt** und
alle CVs in einem **eigenen Ordner** (`cv_downloads/`) speichert.

> ⚠️ Nur für den eigenen, legitimen Recruiter-Zugang. CVs sind personenbezogene
> Daten (DSGVO). Verarbeite sie nur im Rahmen deiner Berechtigung und der
> France-Travail-Nutzungsbedingungen.

## Verbesserte Prompt

> **Aufgabe:** Erstelle ein Python-Programm, das auf der France-Travail-
> Recruiter-Plattform automatisch und im Hintergrund (Headless-Browser) die
> Lebensläufe (CVs) der Kandidaten herunterlädt.
>
> **Anforderungen:**
> 1. Login einmalig manuell über einen sichtbaren Browser (inkl. 2FA), Session
>    lokal speichern und wiederverwenden – keine Passwörter im Code.
> 2. Die Kandidatenliste inkl. aller Folgeseiten (Pagination) durchgehen.
> 3. Pro Kandidat das CV herunterladen, **falls vorhanden**.
> 4. Wenn **kein CV** existiert: Eintrag sofort überspringen und mit dem
>    nächsten weitermachen (kein Abbruch, keine Fehlermeldung).
> 5. Alle CVs in einem **eigenen Ordner** speichern, Dateiname = Kandidatenname.
> 6. Bereits geladene CVs merken → beim erneuten Start nichts doppelt laden
>    (resume-fähig).
> 7. Höflichkeitspause zwischen den Downloads, robustes Fehler-Handling,
>    Fortschritts-Logging, am Ende eine Statistik (geladen / übersprungen).

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Benutzung

```bash
# 1) Einmalig einloggen (Browser öffnet sich, du loggst dich ein, dann ENTER)
python cv_downloader.py --login

# 2) Im Hintergrund laufen lassen und CVs laden
python cv_downloader.py

# Optional: Browser sichtbar mitlaufen lassen (zum Debuggen / Selektoren prüfen)
python cv_downloader.py --show
```

Die CVs liegen danach in `cv_downloads/`.

## Anpassung

France Travail ändert sein Layout gelegentlich. Falls nichts gefunden wird,
passe oben in `cv_downloader.py` an:

- `START_URL` – die konkrete Such-/Ergebnisseite mit deiner Kandidatenliste.
- `SELECTORS` – die CSS-Selektoren für Kandidatenkarte, Profil-Öffnen,
  CV-Download-Button und „Nächste Seite". Tipp: mit `--show` starten und im
  Browser per Rechtsklick → „Untersuchen" die echten Selektoren ablesen.
- `DELAY_BETWEEN` – Pause zwischen den Kandidaten.

## Dateien

| Datei | Zweck |
|-------|-------|
| `cv_downloader.py` | Hauptprogramm |
| `requirements.txt` | Abhängigkeiten (Playwright) |
| `cv_downloads/` | Zielordner für die CVs (wird automatisch angelegt) |
| `.ft_session.json` | gespeicherte Login-Session (nicht teilen!) |
