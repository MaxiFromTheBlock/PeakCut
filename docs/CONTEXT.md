# PeakCut — Kontext

## Architektur

**Python/PyQt6 Desktop-App**

Zentrale Referenz: ../CLAUDE.md (App/CLAUDE.md im Repo) — da steht ALLES.
Dieses Dokument ist die Kurzversion fuer den PO.

## Tech-Stack

- Python 3.11 + PyQt6
- 140 Tests, CI via GitHub Action
- Distribution: Launcher-App in /Applications, ruft Repo-Code direkt auf
  (PyInstaller-Bundle-Strategie geparkt — siehe Distribution-Sektion in CLAUDE.md)

## Design-Prinzipien

- Apple-Style: hell, weiss (NICHT dark!)
- 4-Page Flow: Welcome → Analysis → Zuordnung → Review
- Review-Page ist das Herzstueck
- Qualitaet auf Zaha-Hadid-Niveau

## Folgenschnitt (Stufe 1, produktiv-fähig)

- Automatischer sprecherbasierter Rohschnitt als zweite FCP7-XML.
- Generisches Datenmodell (freie Person × Shot-Typ) — produktionsunabhängig,
  nicht mehr Hotel-Matze-fest verdrahtet.
- Eigener gekapselter Zuordnungs-Schritt zwischen Analyse und Review.
- Harte Leitplanke: Keyboardstellen-Export bricht NIE wegen Folgenschnitt;
  unvollständige Zuordnung → nur Hinweis, Folgenschnitt-XML entfällt.

## Bekannte Einschraenkungen

- macOS only (say Command fuer TTS, fcntl fuer Lock)
- Kein Undo fuer Ignore und In/Out-Aenderungen
- Analyse-Zeitschaetzung ungenau

## CheckIn-Integration

- CLI: --guest "Name" --export-dir "/pfad/" (main_pyqt.py)
- Signal: .peakcut_done im Export-Dir (workers.py)
- export_dir ist settable Property auf PeakCutProject

## Aktuelle Prioritaeten

1. V3 Vision: Smart Scan, Create Mix, Screenshots Page, Hub-Architektur
2. UI Revamp (Figma → PyQt6, oder Electron?)
3. Versionsnummer + Code Signing (geparkt — erst noetig wenn PeakCut wieder extern verteilt wird)

## Branches

- main: Stable Releases
- develop: Aktive Entwicklung
