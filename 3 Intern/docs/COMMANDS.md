# Commands

Quick reference for all terminal commands.

## App starten

```bash
cd /Users/max/Desktop/PeakCut/App
"./3 Intern/venv311/bin/python" "./3 Intern/src/main.py"
```

## Virtual Environment

### Aktivieren (optional, für manuelles pip)
```bash
source "./3 Intern/venv311/bin/activate"
```

### Deaktivieren
```bash
deactivate
```

### Neu erstellen
```bash
rm -rf "./3 Intern/venv311"
~/.pyenv/versions/3.11.*/bin/python3 -m venv "./3 Intern/venv311"
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

## Dependencies

### Installieren
```bash
"./3 Intern/venv311/bin/pip" install -r "./3 Intern/requirements.txt"
```

### Aktualisieren (freeze)
```bash
"./3 Intern/venv311/bin/pip" freeze > "./3 Intern/requirements.txt"
```

### Einzelnes Paket installieren
```bash
"./3 Intern/venv311/bin/pip" install paketname
```

## Git

### Status
```bash
git status
```

### Änderungen committen
```bash
git add -A
git commit -m "Beschreibung"
```

### Auf Tag zurücksetzen
```bash
git checkout v1.1.0
```

### Tags anzeigen
```bash
git tag -l
```

### Neuen Tag erstellen
```bash
git tag -a v1.2.0 -m "Version 1.2.0"
```

## Debugging

### Python direkt ausführen
```bash
"./3 Intern/venv311/bin/python" -c "import peaks; print('OK')"
```

### Logs anzeigen
```bash
cat "./3 Intern/logs/"*.log
```

### Prozess beenden
```bash
pkill -f "main.py"
```
