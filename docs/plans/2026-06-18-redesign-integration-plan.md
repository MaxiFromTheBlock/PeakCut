# PeakCut Redesign — Integrations- & Slice-Plan

> Quelle: ultracode-Kartier-Workflow (4 parallele Reader → Synthese → adversariale
> Kritik, 6 Agenten) vom 2026-06-18, gegen den Code verifiziert + Kritik-korrigiert.
> Mockup: `qt_mockup/` aus „Design für PEakcut-App neu.zip" (Präsentationsschicht,
> kein Backend). Bau auf Branch `feature/redesign`, päckchenweise, TDD.
>
> **Leitplanken (durchgehend versiegelt):** Pin-1 (Keyboardstellen-XML byte-identisch
> → `XMLExporter`/`ExportWorker`/Sinnabschnitt-Codepfad NICHT anfassen, nur Signal
> binden) · #76-Wiedergabe-Controller (`review_playback_controller.py`) NICHT
> umschreiben, nur `session.mode` setzen · der `_scrubbed_pos`-Reset (#76-A) muss
> erhalten bleiben. Nach jedem Slice: volle Suite + Pin-1-Tests als Tor.

## Grundprinzip
Das Mockup liefert Optik + Layout als echtes Qt. Unser Backend ist sauber getrennt
(core ist Qt-frei). Arbeit = **vorhandene Funktionen in die neuen Steckplätze
verkabeln**, nicht neu erfinden. Jedes Mockup-Widget hat ein benanntes Signal +
`# TODO`-Naht zur bestehenden Funktion.

## Vom Kritik-Agent korrigiert (VOR dem Bau beachten)
1. **Kein „accent_orange"-KeyError.** Die Synthese warnte vor einem Crash durch
   fehlenden Farb-Schlüssel — falsch: der Schlüssel wird in `src/` nirgends benutzt.
   **Echte Slice-1-Gefahr:** die neue Palette ändert *geteilte* Werte (Akzent
   `#007AFF`→`#0A6FE0`, `bg_tertiary`, `text_secondary`, `border_light`). Damit färbt
   sich u. a. der **abgenommene Dropdown-Lesbarkeits-Fix** (Pixel-Probe war exakt
   `#007AFF`) sofort um — Slice 1 braucht eine **visuelle Gegenprüfung aller 4 Seiten
   + des Dropdowns**, nicht nur „App startet ohne Fehler".
2. **`back_clicked` existiert im Backend NICHT.** Der „← Zurück"-Button + freie
   Stepper-Sprünge im Mockup sind **neu zu bauende Navigation** (App ist heute strikt
   linear; kollidiert mit dem HC-4-Cache-Sprung). Nicht „1:1 umhängen".
3. **Welcome-Dropzone verspricht Drag&Drop, das es nirgends gibt** (kein
   `setAcceptDrops`/`dropEvent` im ganzen Baum). Entweder eigener Slice ODER
   Beschriftung entschärfen.
4. **Personen-Combos müssen editierbar bleiben** (`setEditable(True)` →
   `combo.lineEdit().editingFinished`). Daran hängt der wachsende gemeinsame
   Namens-Pool (Abnahme v2.10). Mockup-Combos sind nicht editierbar → würde den Pool
   killen. Also: editierbar **und** `_apply_readable_popup` **und**
   `_register_person_combo` — drei Dinge, nicht eins.

Außerdem: **Review-Umbau in EINEM Päckchen ist zu groß** (faktisch der ganze
765-Zeilen-„God-Object"-Umbau) → in 5a–5d geteilt. Und die **immer sichtbare
Smart-Statuszeile** (R5: „berechne…/Drift/INFRA…") braucht im 3-Scope-Layout einen
festen Platz, sonst geht sie verloren.

## Offene Entscheidungen (Max)
- **D1 — Look: Fusion-Stil oder nativer macOS-Stil?** Das Mockup ist NUR unter
  `Fusion` verifiziert; die echte App läuft nativ → Slider/Combo/Radien rendern
  anders. → wird in Slice 1 per gerendertem Vorher/Nachher-PNG (nativ) entschieden.
- **D2 — Ignorieren-Button:** nur Status-Anzeige (Einweg wie heute, mit Auto-Advance)
  ODER echtes Un-Ignore (neue Session-Methode + ClipCandidate-Reaktivierung)?
- **D3 — Welcome-Dropzone:** Drag&Drop bauen oder Beschriftung entschärfen?
- **D4 — Zurück-Navigation:** linearen Flow lassen oder „Zurück" bauen (braucht
  State-Konzept wegen HC-4-Sprung)?
- (D2–D4 erst entscheiden, wenn wir an den jeweiligen Slice kommen.)

## Slice-Reihenfolge (niedrigstes Risiko zuerst)

| # | Slice | Risiko | Carl | Hängt an |
|---|---|---|---|---|
| 1 | **Stylesheet/Palette** (`peakcut_style`→`apple_style`, gleiche API) | mittel | nein | — |
| 2 | **Welcome** reskin (Hero, Dropzone-Optik, Import-Button); Recents leer | niedrig | nein | 1 |
| 3 | **Analyse** reskin (Text-Progress; Dummy-Felder Dauer/ETA/Zähler ausblenden) | niedrig | nein | 1 |
| 4 | **Zuordnung** reskin auf bestehende Logik (Combos editierbar + Popup-Fix!) | mittel | nein | 1 |
| 5a | **Review-Skelett**: Player + Transport + Mode + Export (#76-Kern) | hoch | **ja** | 1 |
| 5b | **Review-Timeline + Scrub** (frac↔Mix-ms, `_scrubbed_pos`-Disziplin) | hoch | **ja** | 5a |
| 5c | **Review-Smart-Panel** + die R5-Statuszeile (festen Platz geben) | mittel | **ja** | 5a |
| 5d | **Review-Kosmetik** Kamera/LUT/Helligkeit (nicht-editierbar, ResettableSlider) | mittel | ja | 5a |
| 6 | **Untertitel-Toggle** (statischer Transkript-Text; default AUS) | niedrig | nein | 5c |
| 7 | **LUT „+ hinzufügen"** als Combo-Sentinel (Backend existiert) | niedrig | nein | 5d |
| 8 | **Peak-Liste interaktiv** (Klick→navigate, Konfidenz-%, Tally) | mittel | nein | 5a |
| 9 | **Recents-Persistenz** (MRU in config; recent_opened muss **Pfad** tragen, nicht Name) | mittel | nein | 2 |
| 10 | **SRT-Export + Live-Sync** (groß, Pin-1-sensibel, Descript prüfen) | hoch | **ja** | 6 |

**Slice 1 Akzeptanz:** App startet, alle 4 Seiten laden, volle Suite + Pin-1 grün,
gerendertes PNG aller 4 Seiten **nativ** + Dropdown-Highlight neu pixel-geprüft
(jetzt `#0A6FE0`), D1 von Max entschieden.

## Nicht verlieren (Kritik + Vollständigkeits-Check)
- Keyboard-Shortcuts (→/←/Space/I/S, an Index 3): Methodennamen `on_play/on_back/
  on_next/on_ignore/on_screenshot` dürfen NICHT umbenannt werden (sonst stille
  Tot-Schaltung). Slice-5-Akzeptanz: alle 5 Tasten am echten Fenster testen.
- `on_ignore`: Einweg + **Auto-Advance** + ClipCandidate→discarded + `session_changed`
  (Autosave) — NICHT das Mockup-Toggle-Verhalten portieren.
- Echtes `PeakVideoPreview` statt Mockup-QFrame; Controller in `_build_ui` erzeugt.
- Async-Kamera-Thumbnails (ThumbnailWorker) statt statischem „CAMERA FEED".
- Gastname-Dialog, 0-Peaks-Guard, HC-4-Cache-Sprung, Export-Optionen-Block der
  Zuordnung (Slice B), `cleanup()`-Pfad, Autosave-Kette — alle erhalten.
- Peak-Labels („Anekdote/Pointe") im Mockup sind Dummy — es gibt KEINE Labels im
  Backend; weglassen, nicht erfinden.

## Prozess
Carl plant + gate-reviewt 5a–5d (wie #76, mit Pin-1/#76-Test-Tor je Teil). Claude
baut TDD, Max entscheidet (D1–D4) + Premiere-/App-Abnahme. Volle Maschinen-Map +
Kritik: Workflow-Output `wf_8011d07a-f08`.
