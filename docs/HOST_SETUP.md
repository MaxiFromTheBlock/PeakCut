# PeakCut auf einem frischen Mac

Diese Anleitung richtet das Python/PyQt-Repo ein, ohne einen alten Benutzerpfad,
ein kopiertes Virtualenv oder Geheimnisse vom vorherigen Mac vorauszusetzen.

## Voraussetzungen

- Apple-Silicon-Mac mit eingeloggter grafischer Sitzung fuer die App selbst
- Homebrew
- Python 3.11 (Projekt-Pin: `.python-version`)
- ffmpeg/ffprobe im `PATH`
- GitHub-Zugriff auf das private Repository

```bash
brew install python@3.11 ffmpeg
cd "$HOME/code/PeakCut"
/opt/homebrew/bin/python3.11 -m venv venv311
./venv311/bin/python -m pip install --upgrade pip
./venv311/bin/python -m pip install -r requirements.txt
```

Fuer die optionale Smart-Grenzen-Pipeline:

```bash
./venv311/bin/python -m pip install -r requirements-smart.txt
```

Das Whisper-Modell wird bei der ersten echten Nutzung separat geladen. Der
Anthropic-Schluessel wird nicht kopiert oder in `config.json` abgelegt. Max legt
auf dem neuen Mac einen eigenen Schluesselbund-Eintrag mit
`scripts/setup_claude_key.sh` an (Service `PeakCut Anthropic`, Account `default`).

## Konfiguration und Launcher

Im Entwicklungsmodus entsteht `config.json` beim ersten Start aus den Defaults.
Die aktuelle lokale Datei enthaelt nur Einstellungen, ist aber absichtlich nicht
versioniert. Sie kann nach Freigabe separat uebernommen oder neu eingestellt werden.

Ein benutzerpfadfreier Launcher wird aus dem aktuellen Checkout erzeugt:

```bash
bash scripts/install_launcher.sh
open "$HOME/Applications/PeakCut.app"
```

Der Installer ueberschreibt keinen vorhandenen Launcher. `PeakCut.spec` und
`PeakCut.icns` sind versionierte Build-Eingaben; `bundled_ffmpeg/`, `venv311/`,
`logs/` und `temp/` sind regenerierbare bzw. laufzeitspezifische Daten.

## Verifikation

Headless per SSH:

```bash
QT_QPA_PLATFORM=offscreen ./venv311/bin/python -m pytest -q
./venv311/bin/python -c "import PyQt6, numpy, scipy, soundfile; print('imports ok')"
ffmpeg -version
ffprobe -version
```

Mit grafischer Sitzung/Screen Sharing:

```bash
./venv311/bin/python src/main_pyqt.py
```

Danach eine Testakte oeffnen und Bild, Ton, Scrub, LUT, Screenshot und Export
pruefen. Ohr-/Bildabnahme und Premiere-Import sind keine headless Gates.

## Host-Grenze

Analyse, Export, Kern-Tests und Builds koennen per SSH laufen. Die PyQt-App
benoetigt WindowServer plus eingeloggte grafische Sitzung. Nach FileVault-Neustart
oder vor dem Benutzer-Login ist sie nicht fernbedienbar. Ob Screen Sharing den
fuer die Ohrabnahme erforderlichen Systemton liefert, muss am Host real geprueft
werden; bis dahin bleibt die finale A/V- und Premiere-Abnahme am Arbeits-Mac.
