# Setup-Anleitung

Diese Anleitung erklärt die Installation von PeakCut auf macOS - auch für Python-Anfänger.

## Voraussetzungen

- macOS (getestet auf macOS 15 Sequoia)
- Terminal-Zugang

## Schritt 1: Python 3.11 installieren

PeakCut benötigt Python 3.11. Am einfachsten installierst du es mit pyenv:

### pyenv installieren (einmalig)

```bash
# Homebrew installieren (falls nicht vorhanden)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# pyenv installieren
brew install pyenv

# Shell konfigurieren (für zsh)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# Terminal neu starten oder:
source ~/.zshrc
```

### Python 3.11 installieren

```bash
pyenv install 3.11
```

## Schritt 2: Virtual Environment erstellen

Öffne Terminal und navigiere zum App-Ordner:

```bash
cd /Users/DEIN_NAME/Desktop/PeakCut/App
```

Erstelle das Virtual Environment:

```bash
~/.pyenv/versions/3.11.*/bin/python3 -m venv "3 Intern/venv311"
```

## Schritt 3: Dependencies installieren

```bash
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

## Schritt 4: App starten

```bash
# PyQt6 Version (empfohlen)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main_pyqt.py"

# Tkinter Version (Legacy)
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"
```

## Benutzung

1. **Material vorbereiten**: Lege deine Dateien in den Ordner `1 Material/`
   - Keyboard-Audio: Dateiname muss "keyboard", "keys" oder "klavier" enthalten
   - Reference-Audio: Dateiname muss "mix" enthalten (für Video-Sync)
   - Videos: .mp4 oder .mov Dateien

2. **Analyze**: Klicke auf "Analyze" um Peaks zu erkennen

3. **Preview**: Nutze Play/Next/Back um durch die Peaks zu navigieren
   - "Switch" wechselt zwischen Keyboard- und Mic-Modus
   - "Ignore" markiert einen Peak zum Überspringen

4. **Export**: Klicke auf "Export" um MP3 + TXT zu erstellen
   - Ergebnisse landen in `2 Export/`

## Fehlerbehebung

### "No keyboard file found"
Stelle sicher, dass deine Keyboard-Audiodatei "keyboard", "keys" oder "klavier" im Dateinamen enthält.

### App startet nicht
Lösche das venv und erstelle es neu:
```bash
rm -rf "./3 Intern/venv311"
~/.pyenv/versions/3.11.*/bin/python3 -m venv "./3 Intern/venv311"
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

### TTS funktioniert nicht
PeakCut nutzt macOS `say` mit der deutschen Stimme "Anna". Prüfe ob sie installiert ist:
```bash
say -v Anna "Test"
```
Falls nicht, installiere sie unter: Systemeinstellungen > Bedienungshilfen > Gesprochene Inhalte > Systemstimme > Stimmen verwalten
