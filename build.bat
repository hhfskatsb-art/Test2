@echo off
REM ===========================================================================
REM  Baut die Windows-EXE des France-Travail-CV-Downloaders.
REM  Einfach doppelklicken (oder in der Eingabeaufforderung ausfuehren).
REM  Voraussetzung: Python 3.10+ ist installiert.
REM ===========================================================================

echo [1/3] Abhaengigkeiten installieren...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto :error

echo [2/3] EXE bauen...
pyinstaller --noconfirm --onefile ^
    --name FranceTravailCVDownloader ^
    --collect-all playwright ^
    cv_downloader.py || goto :error

echo [3/3] Fertig!
echo Die EXE liegt hier: dist\FranceTravailCVDownloader.exe
echo (Beim ersten Start wird Chromium automatisch nachgeladen.)
pause
exit /b 0

:error
echo.
echo FEHLER beim Build. Bitte Ausgabe oben pruefen.
pause
exit /b 1
