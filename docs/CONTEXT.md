# PeakCut — Kontext

> **Stand: 2026-08-19/20.** Davor war dieses Dokument auf dem Stand vom 18.06. eingefroren
> und in mehreren Punkten nachweislich falsch (Schema-Version, „Import geparkt", ein
> bereits gelöster Bug als offen). Beim Fortschreiben: Behauptungen gegen den Code
> prüfen, nicht gegen die Erinnerung.

## Architektur

**Ein Kern, zwei Oberflächen — beide sind Mac-Programme, nichts läuft im Internet.**

| | Repo / Zweig | Was |
|---|---|---|
| **Kern + PyQt-Oberfläche** | `PeakCut/App` · `feature/redesign` | Das produktive PeakCut. Analyse, Erkennung, Zuordnung, alle Exporter + die Oberfläche, mit der Max arbeitet. Python 3.11 + PyQt6. |
| **Neue Oberfläche** | `PeakCut-web` · `develop` | Electron + React. Rechnet **nichts** selbst, ruft den Kern nebenan auf (`engine/engine_core.py` hängt `../../PeakCut/App/src` in den Import-Pfad). „web" = Bautechnik der Oberfläche, **kein** Server, keine Cloud. |

**Zielbild (Max-Entscheid 2026-08-17): Die neue Oberfläche soll die PyQt-App
ersetzen.** Damit sind Paketierung (installierbar per Doppelklick), Selbst-Start der
Engine und CheckIn-Anbindung echte Aufgaben, keine Optionen. Bis dahin bleibt die
PyQt-App der Produktionsstand.

Zentrale Referenz: ../CLAUDE.md (App/CLAUDE.md im Repo) — da steht ALLES.
Dieses Dokument ist die Kurzversion fuer den PO.

## Tech-Stack

- Python 3.11 + PyQt6
- CI via GitHub Action (libegl1/libgl1-Fix — CI war seit Tagen rot)
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
  R4-Disziplin live bewährt.
- **#71a Audio-Routing-Mini-Slice auf main 2026-05-25:** Phasing-
  Wurzel im Cutter-MP3 und in der Review-Speak-Mode-Wiedergabe
  behoben. Mix-Datei wurde beim Import in `project.mic_tracks`
  einsortiert und von MP3Exporter + `session.play_current` mit den
  Einzel-Mics overlay-summiert — jeder Sprecher doppelt. Zentraler
  Helfer `core/audio_routing.py` mit Token-Heuristik wurde
  eingeführt, alle Hör-/Renderpfade hängen sich daran auf. XML-
  Pfade + `.peakcut`-Schema unangetastet (Pin-1 stabil). Max-O-Ton
  „kein Phasing mehr" am realen Re-Export. **Wichtige Übergangs-
  Asymmetrie (Absicht, kein Vergessen):** Mix liegt strukturell
  weiter in `project.mic_tracks`, der `audio_routing`-Helper
  filtert ihn nur zur Laufzeit raus. Strukturelle Trennung (eigenes
  `project.mix_track`-Feld, Mix nicht mehr in mic_tracks, Schema-v3)
  kommt erst mit **#77 Import-Refactor** — bis dahin ist das so
  korrekt. Nächste Slices: **#76 Wiedergabe-UX** (baufertig auf
  dem Helper-Fundament) → **Import-Refactor + Marker-Rename (#37,
  #77)** → **Prompt-Tuning (#70)**.

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

## Aktuelle Prioritaeten (Stand 2026-08-17)

Maßgeblich = „Offene Slices" unten + App/BACKLOG.md (Todo-SSOT).

Die Energie liegt seit Juli auf der **neuen Oberfläche** (`PeakCut-web`), nicht am
Kern. Reihenfolge dort, nach dem Gesundheitscheck (Carl) + Ultracode-Sweep (Claude)
vom 12./17.08.:

1. ✅ **Kern-Zweige zusammengeführt** (Merge `deb6265`) — Schema v5 jetzt überall.
   ✅ **Kandidaten quellenunabhängig** (feature/kandidaten-quellenunabhaengig,
   2026-08-19/20) — Schema v5 → **v6** jetzt überall, siehe unten.
2. **Doku geradeziehen** (dieses Dokument, CLAUDE.md, PeakCut-web/README.md).
3. **Startprüfung Web↔Kern** — Schema-/Modul-Handshake statt „nimm den Nachbarordner".
   Muss `export_parity.py` mitnehmen (eigener zweiter Draht zum Kern).
4. **Gastname durchreichen** — reißt heute an drei Stellen; färbt die Sprecher-
   Vorbelegung VOR der Analyse, also nicht nachreichbar.
5. **Oberfläche ehrlich machen** — sie sagt „Marker optional" und bricht ohne Marker ab.
6. **A/V-Selbstcheck reparieren** — `verify:review` ist seit 21.06. TOT (läuft in einen
   Timeout, kann gar nicht grün werden). Der gesamte Juli-Umbau am Abspieler entstand
   ohne Messgerät.
7. **Kalter Handdurchlauf** (Max) → Export-Vergleich → `develop` → `main`.
8. Danach: Sicherheits-Kleinkram, CI im Web-Repo, Electron-Aktualisierung, ARCH-1.

Am Kern selbst weiter offen: Produkt-Validierung (#70 Prompt-Tuning + Cutter-Sign-off),
Slice A (Dialog-Totale Cross-Talk), Export-Steuerung in den Kern (ARCH-1, vor NAS),
SRT (groß). (Die frühere „V3 Vision: Smart Scan / Create Mix / Hub"-Liste war überholt
2026-05-18.)

## Offene Slices

### Kandidaten quellenunabhängig (2026-08-19/20, feature/kandidaten-quellenunabhaengig)
Bisher kam eine „Stelle" nur vom Fußpedal-Marker. Jetzt quellenunabhängig: künftig auch
aus Transkript-Analyse, automatischer Clip-Findung oder von Hand gesetzt. `ClipCandidate`
trägt eine stabile Identität (`candidate_id`), ihre Herkunft (`origin` —
marker/transcript/auto/manual) und einen expliziten Anker (`anchor_ms`, NIE aus
`boundary.start_ms` abgeleitet); `peak_id` ist nur noch eine optionale Rückreferenz für
markergebundene Kandidaten. `.peakcut`-Schema **v5 → v6**. Neues Qt-freies Modul
`core/candidate_view.py` bündelt fünf vorher blind über `peak_id` joinende Stellen
(XML-Export, Smart-Playback, Ignorieren, Grenzen-Pipeline, Web-Serialisierer) — ein
Fremdkandidat mit kollidierender Legacy-`peak_id` konnte dort vorher den echten
Marker-Kandidaten verdrängen. Vier-Augen mit Carl (Spec + Gate A), TDD über 4 Tasks +
Abschluss-Review + Fix-Welle, 888 Kern-Tests grün, Web 362 grün, Pin-1 stabil. Reale
Ilka-Akte read-only migrationsgeprüft (31/31 korrekt, SHA vorher==nachher). Merge-
Auflagen: v6 gleichzeitig auf `feature/redesign`+`develop`+`main`, Web-Merge zusammen
mit dem Kern-Merge. **Offen (→ BACKLOG.md):** zwei herkunftsblinde Aggregate in
`review_page.py`, fehlende Nachsortierung/Eindeutigkeitsprüfung beim Akten-Laden,
Namensdrift `peak_decisions`/`candidate_decisions`, `main_window.py` fängt
`ClipCandidateError` an zwei Stellen nicht, offene Vertragsfrage `peak_id` bei
`origin != marker`. Details: CLAUDE.md → Changelog.

### Kern-Zweige zusammengeführt (2026-08-17, Merge `deb6265`)
`feature/redesign` → `develop` → `main`, alle drei inhaltlich identisch, 845 Tests +
CI grün. Vorher trug nur `feature/redesign` Schema v5 und die Import-Pivot-Module —
ein Zweigwechsel hätte Max' Produktionsakte unlesbar und die neue Oberfläche
unstartbar gemacht. Enthält: Phasing-Wurzelfix `91cc8ae` (P8Mix), Marker-Auto-
Erkennung `4fbb3d1` (Inhalt statt Name), Import-Pivot (capability-driven, Schema v5
mit PENDING-Zustand, `project_capabilities` mit 7 verriegelten Tests).

### Import-Pivot — im Kern GEBAUT, in der PyQt-App ohne Anschluss
`core/material_scanner.py`, `core/project_capabilities.py`, `core/import_model.py`,
`core/import_project.py`, `project_archive.read_pending_import` sind fertig und
getestet. **Aber:** `material_scanner` hat in `App/src` keinen Aufrufer — die PyQt-App
rät weiterhin per Dateiname (`gui/main_window.py:219-236`). Genutzt wird der Pivot
bisher nur von der neuen Oberfläche. (Ersetzt die alte Notiz „#77 Strukturteil gebaut,
Rest geparkt" — der Rest ist gebaut, nur nicht verdrahtet.)

### Capability-Vertrag vs. Realität (offen, Produktentscheidung)
`tests/test_project_capabilities.py:35` verriegelt: ohne Marker gehen Screenshots,
Folgenschnitt und Sinnabschnitte trotzdem. **Gebaut ist das nicht** — der Kern selbst
verlangt den Marker (`core/analysis_process.py:127-131`), die PyQt-App auch
(`gui/main_window.py:174-186`), die Web-Analyse bricht mit `KEIN_MARKER` ab. Der
Vertrag ist eine Absichtserklärung mit Tests, kein Weg. Entweder bauen oder in der
Oberfläche ehrlich zurücknehmen.

### Ältere Slices (historisch, Stand 2026-06-18)

**Marker + Vergleichbarkeit GEBAUT auf develop (2026-06-18), Max-Premiere-Abnahme ✓:**
Keyboardstellen-XML und Sinnabschnitt-XML sind jetzt direkt vergleichbar — beide mit
Video + denselben Tonspuren + nummerierten Bereich-Markern „Stelle N" (synchron trotz
candidate.peak_id-Versatz). Sequenzen „Keyboardstellen raw"/„smart", Clip-Namen =
Quelldateien. Neuer Helfer `core/xml_sequence_helpers.py`. Carl-Plan, TDD (785 Tests),
Pin-1 bewusst neu eingefroren. **Offen:** Carl-Schluss-Review; nächster Slice „smarte
Grenzen auf Satzanfang/-ende einrasten" (mechanisch, ≠ #70-Aufhänger-Wahl).

**#77 Import-Refactor — Strukturteil GEBAUT auf develop (2026-06-16), Rest geparkt:**
Eigenes `project.mix_track`-Feld, zentraler Klassifizierer (`core/import_classifier.py`),
`.peakcut`-Schema v4 (additiv + rückwärtskompatibel). Vier-Augen mit Carl, Review grün
(Tasks 0/1/2/3/4/6). Bewusst ADDITIV: Mix bleibt vorerst zusätzlich in `mic_tracks`
(XMLExporter baut Audio noch von dort — sonst Pin-1-Bruch). **Geparkt:** Task 5 (Mix
strippen), Task 7 Import-UI, Task 8 Transcript — bis Produkt-/Kundenrichtung klar ist.
Plan: `docs/plans/2026-06-16-77-import-refactor-plan.md`.

**Erste Eigen-Produktion Philip Siefer (2026-06-17):** Max hat selbst geschnitten.
Folgenschnitt-XML „funktioniert super" (erste echte Eigen-Nutzung). Sinnabschnitt-XML
importierbar gemacht (fehlende FCP7-Audio-Pflichtangaben, Commit `64870c0`, eigener
Codepfad, Pin-1 unberührt). ~~**OFFEN (Bug):** Sinnabschnitt-XML zeigt nur Ton, kein
Bild~~ → **ERLEDIGT am 2026-06-18** durch den Marker-Slice: die Sinnabschnitt-XML wurde
von Audio-only auf kompakte Multicam gehoben (Video je Kamera + dieselben Tonspuren wie
raw). Ebenso erledigt: **nummerierte Marker**. **Weiter offen:** SRT-Untertitel (groß).

**Fix-Runde (2026-06-16/17):** Python 3.11 gepinnt, Shot-/Person-Dropdown lesbar
(visuell bestätigt), Crash auf „Weiter" bei Personen-Shot ohne Person behoben.

**Fundament-Health-Check 2026-06-15** (`docs/specs/2026-06-15-state-of-peakcut-health-check.md`):
Urteil mostly-solid. **Slice B + Daten-Integritäts-Riegel GELANDET auf main
(2026-06-15, Premiere- + App-Smoke bestanden)** (atomare
Writes DATA-1, Schema-Policy DATA-2, R2-Ausricht-Riegel KI-2, speaker_activity-
Mix-Hub AUD-1a — 621 Tests grün, Pin-1 stabil; Plan:
`docs/plans/archiv/2026-06-15-data-integritaets-riegel.md`). Reconciled Reihenfolge
(Carl+Claude): Slice-B-Merge → #76 Wiedergabe (Gate vor jedem KI-Tuning) →
#77 Import-Refactor (zieht den restlichen Klassifizierer-Merge mit) → #70
Prompt-Tuning → Slice A (halb-automatisch) → Export-Orchestrierung aus dem GUI
vor NAS. Tickende Uhr: pydub/audioop bei Python 3.13 + Python-Pin nicht erzwungen.

**#76 Wiedergabe-UX GELANDET auf main (2026-06-16):** synchrone Ton+Bild-Vorschau
über `ReviewPlaybackController` (Audio = Master, Drift-Korrektur, Schwelle 100ms
provisorisch), Modus key/speak/smart, Play ab Scrub-Stelle (speak/smart auf der
Mix-Spur, key = Marker-Clip). App-Smoke (Max) + Gate E/F (Carl) bestanden,
689 Tests grün. Plan: `docs/plans/archiv/2026-06-15-wiedergabe-76-plan.md`.
**#77 Strukturteil danach gebaut (2026-06-16, develop) — siehe oben.**

Reihenfolge nach #71a-Merge (2026-05-25) und Fremdmaterial-Test (2026-06-01):
1. **Slice B — Multi-Track-Folgenschnitt-XML** (CODE-FERTIG 2026-06-06,
   Premiere-Smoke vorbereitet 2026-06-10): Tasks 0-8 alle durch
   (Pin-1, Contracts, Layout-Planung, Audio-Quellenwahl, Multi-Track-
   Video, Audio-Mix-only, Schema-v3, UI-Toggle, Integration). Carl
   Pre-Smoke-Review grün. **Offen: nur noch Max' Premiere-Sichtung**
   beider XMLs (liegen in `~/Downloads/Teil 2 - Smoke {disable,remove}/`,
   erzeugt durch `scripts/smoke_multitrack_export.py`), dann Carl-
   Schluss-Review, dann Merge. Default-Mode = disable. 593 Tests grün,
   Pin-1 stabil.
2. **#76 Wiedergabe-UX** — GELANDET auf main 2026-06-16 (siehe oben).
3. **Slice A — Dialog-Totale Cross-Talk-Pass**: Totale bei Cross-Talk-
   Phasen einfügen, NICHT genereller Zeit-Pass. Inhaltliche
   Unterscheidung (Cross-Talk vs. humorvoller Schlagabtausch).
   Wartet auf Max' Material-Markierung aus 1plus1.
4. **#37/#77 Import-Refactor + Marker-Rename** — strukturelle Mix-Trennung.
5. **#70 Prompt-Tuning** — Few-Shot + A/B-Harness.

Details + Bau-Status pro Task: App/CLAUDE.md, Sektion „Slice B
Bau-Status — Stand 2026-06-03".

## Branches (Stand 2026-08-17)

- **feature/redesign: HIER wird gearbeitet** — und das ist zugleich Max'
  Produktionsstand, weil der Launcher den Repo-Code direkt aufruft.
- develop: Integrationszweig
- main: Stable Releases (`--no-ff` Marker-Commit, Max-Go nötig)

Alle drei sind seit `deb6265` inhaltlich identisch. **Vor jedem Zweigwechsel prüfen:**
läuft eine Produktion, und trägt der Zielzweig `CURRENT_SCHEMA_VERSION` ≥ dem, was in
den vorhandenen `.peakcut`-Akten steht? Details in CLAUDE.md → „Git Workflow".
