# PeakCut — Kontext

## Architektur

**Python/PyQt6 Desktop-App**

Zentrale Referenz: ../CLAUDE.md (App/CLAUDE.md im Repo) — da steht ALLES.
Dieses Dokument ist die Kurzversion fuer den PO.

## Tech-Stack

- Python 3.11 + PyQt6
- 261 Tests, CI via GitHub Action (libegl1/libgl1-Fix — CI war seit Tagen rot)
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
  Masken starten komplett leer (kein geratener Default); Namen einmal
  tippen → überall wählbar. Hörprobe pro Mic. Review-Dropdown zeigt die
  Zuordnung, Screenshots erben das Label.
- Harte Leitplanke: Keyboardstellen-Export bricht NIE wegen Folgenschnitt;
  unvollständige Zuordnung → nur Hinweis, Folgenschnitt-XML entfällt. Eine
  bewusst leere Zuordnung wird NICHT heimlich durch Defaults ersetzt.

## Smart Clip-Grenzen / Roadmap #3 (auf develop, Smoke 2026-05-21)

- Pro Drücker: Whisper transkribiert die Folge (parallel zur Analyse),
  ein Scaffold sammelt natürliche Schnittkanten (Satz-/Pausen-/Sprecher-
  Wechsel), Claude entscheidet den kleinsten zusammenhängenden Sinn-
  abschnitt, eine deterministische Bremse snappt auf gelieferte Kanten
  und fängt jeden strukturellen Defekt ab.
- Drei Ergebnis-Kategorien statt blankem Fallback: OK / DECIDER_VERWORFEN
  (Claude antwortete, Bremse lehnte ab — konservativer Rückfall mit
  Konfidenz 0.0 als echtes Signal) / INFRA_FEHLT (kein/ungültiger Key,
  Modell/API/Transkript fehlt — KEINE Pseudo-Einträge, lauter Hinweis
  in der Statuszeile).
- Optionaler Descript-`.docx`-Upload als Transkriptquelle (Whisper-
  Bypass, minutengrob). Cache via Mix-Fingerprint (size+mtime_ns):
  zweites Öffnen derselben Folge → kein Whisper mehr.
- Job B (Scaffold→Decider→Bremse) läuft im Review-Hintergrund, NICHT
  am Export-Knopf. Sinnabschnitt-Zusatzdateien (TXT/XML) entstehen
  genau einmal pro Lauf, wenn Basis-Export fertig UND Smart bereit.
- Claude-Key kommt aus dem macOS-Schlüsselbund (BYOK, v1) über einen
  abstrakten Provider-Steckplatz; späterer Managed/Cloud-Tier ist ein
  Tausch der Implementierung, kein Neubau.
- Smoke 2026-05-21 an Sheila-de-Liz-Material: 35/36 Peaks haben
  narrative Sinnabschnitt-Vorschläge mit Konfidenz 0.78–0.80,
  R4-Disziplin live bewährt. Wiedergabe-UX-Slice (#76) ist Voraussetzung
  fürs eigentliche Hör-Urteil → vor dem Prompt-Tuning-Slice (#70).

## Folgenschnitt Stufe 2 / Track 1 (auf main gelandet 2026-05-17)

- Lange Ein-Personen-Monologe werden in grosse, ausgewogene Minuten-
  Blöcke aufgelockert (Rotation durch die Kameras der Person + periodische
  Establishing-Totale), Schnitte snappen auf Sprechpausen, harter
  Mindest-Block. Stufe 1 bleibt bit-stabil.
- Generisch: jede Kamera-Kombi (inkl. nur Totale) → valide XML.
- Carl-Schluss-Review technisch grün. v1-Zahlen aus Schirach-Kompass
  justiert (min_block_to_loosen 90s, first 70s, target 55s, min_block
  35s, totale_block 20s) — weiter PROVISORISCH. Neu-Verifikation an
  echter Folge (Hartmut Rosa, gecachte Analyse) erledigt: max-Block
  118s→89s, Blöcke >90s 26→0, Clips 325→347. Auf main gelandet
  (Merge 3395ecd). Alex-Sichtung + Fremdproduktion = erwartete Real-
  Bestätigung, ggf. kleiner Tunables-Nachdreh (kein Regressionsrisiko).
- `scripts/verify_folgenschnitt_recut.py`: fährt Pipeline über gecachte
  speaker_activity.csv (alt vs neu), OLD-Lauf selbst-validiert gegen
  bestehende XML.
- Schätz-Hilfe `scripts/analyze_fcpxml.py` (Carl-Spec, NICHT autoritativ):
  liest messy Premiere-FCPXML rückwärts, Confidence-Gate mit
  Plausibilitätsbremse. Schirach HIGH/brauchbar, Hüther LOW/verworfen.

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
