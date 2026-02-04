# Git Workflow & Branch-Regeln

Regeln für die Arbeit mit Git in diesem Projekt.

---

## Branch-Struktur

```
main     ← Stable releases (production-safe)
develop  ← Aktive Entwicklung (default für neue Features)
```

## Wann welcher Branch?

### Direkt auf `develop` arbeiten:
- Kleine Features (< 1 Tag Arbeit)
- Bug Fixes
- Dokumentations-Updates
- Config-Änderungen

### Neuer Feature-Branch (`feature/name`):
- Große Features (> 1 Tag Arbeit)
- Experimentelle Änderungen
- Breaking Changes
- Wenn mehrere Leute parallel arbeiten

```bash
# Feature-Branch erstellen
git checkout develop
git checkout -b feature/mein-feature

# Nach Fertigstellung
git checkout develop
git merge feature/mein-feature
git branch -d feature/mein-feature
```

### Wann nach `main` mergen?
- Nach erfolgreichem Test einer Version
- Vor Auslieferung an Produktion
- Mit Version-Tag

```bash
git checkout main
git merge develop
git tag -a v1.4.0 -m "Version 1.4.0"
git push origin main --tags
```

---

## Commit-Regeln

### Wann committen?
- Nach jeder abgeschlossenen Änderung
- Bevor du zu einem anderen Feature wechselst
- Am Ende einer Arbeitssession
- **Kleine, häufige Commits > große, seltene Commits**

### Commit-Message Format
```
Kurze Beschreibung (max 50 Zeichen)

- Detail 1
- Detail 2

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Beispiele
```bash
# Gut
"Add EDL export for Premiere Pro"
"Fix video sync offset calculation"
"Update README with PyQt6 instructions"

# Schlecht
"WIP"
"fixes"
"update"
```

---

## Vor dem Arbeiten: Status-Check

**Immer zuerst ausführen:**
```bash
git branch      # Auf welchem Branch bin ich?
git status      # Gibt es uncommitted changes?
```

### Checkliste vor neuer Arbeit:
- [ ] Bin ich auf `develop` (oder dem richtigen Feature-Branch)?
- [ ] Ist alles committed?
- [ ] Ist der Branch aktuell? (`git pull`)

---

## Push-Regeln

### Wann pushen?
- Nach größeren Meilensteinen
- Am Ende einer Session
- Vor längerer Pause

### Wann NICHT pushen?
- Mitten in einer unfertigen Änderung
- Wenn Tests fehlschlagen
- Auf `main` ohne vorherigen Test

---

## Notfall-Befehle

```bash
# Letzte Änderungen verwerfen (uncommitted)
git checkout -- .

# Letzten Commit rückgängig (behält Änderungen)
git reset --soft HEAD~1

# Branch-Stand von Remote holen
git fetch origin
git reset --hard origin/develop
```

---

## Zusammenfassung für Claude

**Bei jeder Session prüfen:**
1. `git branch` - Welcher Branch?
2. `git status` - Alles clean?

**Nach jeder Änderung:**
1. Committen mit aussagekräftiger Message
2. Bei Bedarf pushen

**Bei großen Features:**
1. Neuen Branch von develop erstellen
2. Nach Fertigstellung mergen & Branch löschen

---

*Erstellt: 2025-02-04*
