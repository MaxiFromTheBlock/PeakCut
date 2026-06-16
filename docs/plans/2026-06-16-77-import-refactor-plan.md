# #77 Import-Refactor - feste Slots statt Namensraten

Stand: 2026-06-16, `develop` nach #76 / Slice B / Daten-Integritaets-Riegel.

Ziel: Import wird explizit und strukturell. Dateien landen nicht mehr durch verstreute
Substring-Heuristiken in impliziten Listen, sondern in festen Slots:

- Marker-Spur
- echte Mics
- Mix
- Transkript
- Kameras
- ignoriert

Wichtigste Designentscheidung: **feste Slots mit Auto-Vorschlag + Nutzerbestaetigung**.
Keine reine Heuristik als Wahrheit mehr, aber auch keine leere Handarbeit. PeakCut darf
vorschlagen; der bestaetigte Slot-Zustand ist danach die Quelle der Wahrheit.

Nicht-Ziel in diesem Slice: neues Projekt-Hub-Design, Batch-Import, Profile, Wegfall der
Marker-Pflicht, KI-/Prompt-Tuning, Sync-/Exporter-Neudesign.

Harte Pins:

- **Pin-1:** Keyboardstellen-XML bleibt byte-identisch fuer denselben logischen Import.
- **HC-2:** keine Worker-/Subprocess-Lifecycle-Aufweichung.
- **#71a:** `audio_routing` bleibt die Laufzeit-Wahrheit fuer Speech-Audio, liest aber
  kuenftig das strukturelle `project.mix_track`.
- **Schema:** v4 ist rueckwaertskompatibel. v1-v3-Akten laden; Zukunfts-Akten bleiben
  wie DATA-2 blockiert.

## Architekturentscheidungen

1. **Neues Core-Modul `core/import_classifier.py`.**
   Das ist die zentrale Stelle fuer Import-Rollen und leichte Dateinamen-Vorschlaege.
   `audio_routing.is_mix_track()` delegiert danach dorthin, damit bestehende Consumer-API
   stabil bleibt.

2. **`PeakCutProject` bekommt echte Slots.**
   Canonical:
   - `marker_track`
   - `mic_tracks`
   - `mix_track`
   - `transcript_path`
   - `videos`

   Backward-compat:
   - `keyboard_track` bleibt als Alias auf `marker_track`, damit nicht der ganze Code
     in einem Rutsch umbenannt werden muss.
   - `set_files(keyboard, mics, videos, mix=None, transcript=None)` bleibt mit alten
     drei positional args kompatibel.

3. **Mix raus aus `mic_tracks`.**
   Nach #77 gilt im Modell: `mic_tracks` enthaelt nur echte Sprecher-Mics.
   Loader fuer v1-v3-Akten migrieren legacy `mic_tracks=[MIC1, MIC2, Mix]` beim Laden:
   `mix_track=Mix`, `mic_tracks=[MIC1, MIC2]`.

4. **Marker-Rename in der UI, nicht erzwungener Big-Bang im Core.**
   Nutzertext sagt "Marker-Spur". Technische Namen `keyboard_track` duerfen als Alias
   weiter existieren, solange sie nicht neue UI-Texte oder neue Schema-v4-Felder sind.

5. **Transkript-Slot ist optional und nutzt bestehende Roadmap-#3-Mechanik.**
   Wenn ein `.docx` bestaetigt wurde und ein Mix vorhanden ist, importiert PeakCut es
   ueber `transcript_archive.import_descript_transcript()` in `.peakcut/transcript.json`
   und setzt `session.transcript_ref`. Wenn das fehlschlaegt: lauter Hinweis, Normalflow
   bleibt intakt.

6. **Pflichtcheck: Marker + (Mics oder Mix).**
   - Marker fehlt -> kein Analyse-Start.
   - Weder echte Mics noch Mix -> kein Analyse-Start.
   - Videos optional.
   - Transkript optional.
   - Mix optional, aber empfohlen fuer Sync/Smart/Speak.

## Gates

- **Gate 0:** Pin-1/Safety-Harness steht, bevor Modelldreh beginnt.
- **Gate A STOPP:** Core-Vertraege `ImportRole`/`ImportSlots`/Project-Slots eingefroren.
- **Gate B:** Schema-v4 Migration und Save/Load-Roundtrip gruen.
- **Gate C:** Audio-Routing/Session/Exporter laufen mit strukturellem Mix, kein Phasing-Rueckfall.
- **Gate D:** Import-UI erzeugt bestaetigte Slots; alter `_categorize_files`-Namensratenpfad ist raus.
- **Gate E:** App-Smoke: bestehende HM-Akte, frischer HM-Import, Fremdproduktion mit Mix, Transkript-Import.

## Task 0 - Safety-Harness und Ist-Pins

Files:

- Add/extend: `tests/test_import_refactor_safety.py`
- Run with existing pins: `tests/test_audio_routing_safety.py`, `tests/test_multitrack_folgenschnitt_safety.py`,
  `tests/test_keyboardstellen_smart_regression.py`

Steps:

1. Schreibe einen Pin-Test fuer Keyboardstellen-XML mit einem logischen Projekt:
   Marker + MIC1 + MIC2 + Mix + Kamera. Der Test muss die XML-Bytes oder den bestehenden
   SHA-256-Pin verriegeln. Er darf nicht auf die interne Frage "Mix in mic_tracks?"
   angewiesen sein.
   Der Test muss explizit den XML-Audio-Metadaten-Drift fangen:
   `XMLExporter` probt `project.get_reference_track()` fuer `sample_rate`,
   `bit_depth` und `channelcount`. Der Fixture braucht deshalb eine Mix-Datei mit
   anderer Kanalzahl als mindestens ein Mic (z.B. stereo Mix, mono Mic) und asserted
   den erwarteten `channelcount`/Probe-Quellen-Pfad im XML. Sonst kann die v4-Migration
   "gruen" aussehen und trotzdem Premiere-Bytes veraendern.

2. Schreibe einen Guest-Name-Pin fuer typische HM-Mix-Namen:
   `Sheila Mix.mp3`, `Hotel Matze - Sheila de Liz Mix.mp3`, `Episode - Mix.mp3`,
   `Podcast_mixdown.wav`. Erwartung: bestehende Gastnamen bleiben gleich.

3. Schreibe einen Charakterisierungstest fuer heutigen Legacy-Import:
   Dateiliste mit Marker, MIC1, MIC2, Mix, Cam, Transcript wird aktuell noch so
   klassifiziert, dass Mix in den Audio-Dateien auftaucht. Dieser Test darf spaeter in
   Task 5 gezielt auf den neuen Slot-Dialog umgestellt werden, aber Task 0 macht die
   Ausgangslage sichtbar.

4. Run:
   `./venv311/bin/python -m pytest tests/test_import_refactor_safety.py tests/test_audio_routing_safety.py tests/test_keyboardstellen_smart_regression.py -q`

Gate 0: rot -> gruen, kein Produktionscode.

## Task 1 - Core-Vertraege: Import-Rollen und Slot-State

Files:

- Add: `src/core/import_classifier.py`
- Add: `tests/test_import_classifier.py`

Vertrag:

- Rollen als Strings, keine Enum-Abhaengigkeit im JSON:
  - `marker`
  - `mic`
  - `mix`
  - `transcript`
  - `camera`
  - `ignore`

- Frozen Dataclasses:
  - `ImportCandidate(path: str, suggested_role: str, reason: str = "")`
  - `ImportSlots(marker_track: str | None, mic_tracks: tuple[str, ...], mix_track: str | None,
    transcript_path: str | None, videos: tuple[str, ...], ignored: tuple[str, ...])`

- Funktionen:
  - `is_audio_path(path) -> bool`
  - `is_video_path(path) -> bool`
  - `is_transcript_path(path) -> bool`
  - `is_mix_track(path) -> bool`
  - `is_marker_track(path) -> bool`
  - `suggest_role(path) -> str`
  - `suggest_import_slots(paths) -> ImportSlots`
  - `validate_import_slots(slots) -> list[str]`
  - `normalize_import_slots(slots) -> ImportSlots`

Heuristiken:

- Mix: token-bewusst wie #71a: `mix`, `mixdown`.
- Marker: token-bewusst und zentral: `keyboard`, `keys`, `klavier`, `marker`.
  Wichtig: keine naive Substring-Falle fuer `monkey.wav`, `keynote.mov` oder
  `Key Largo.wav`. Das einzelne Token `key` ist absichtlich **kein** Marker-Token:
  es bringt im echten Material keinen Nutzen und waere ein ueberraschender Default.
- Transcript: `.docx` als v1. Optional spaeter `.txt/.srt`, aber nicht in diesem Slice.
- Audio ohne Mix/Marker -> `mic`.
- Video `.mp4/.mov` -> `camera`.
- Sonst `ignore`.

Tests:

- Token-False-Positive: `mixer_recording.wav` ist kein Mix, `monkey.wav` kein Marker.
- `Key Largo.wav` ist kein Marker.
- HM-Positive: echte Mix-Namen bleiben Mix.
- Marker-Positive: `keyboard.wav`, `Keys.wav`, `Klavier.wav`, `Marker.wav`.
- Slot-Vorschlag mit mehreren Mics/Kameras/Transcript.
- Validation: Marker fehlt, keine Speech-Audio-Quelle, mehrere Mixe, mehrere Marker.
  Mehrere Mixe/Marker sind nicht fatal im Core: `normalize_import_slots` waehlt den ersten
  und legt Rest nach `ignored`, UI kann lauter warnen.

Gate A STOPP: Carl/Claude bestaetigen die Datenform, bevor Project/Archive darauf bauen.

## Task 2 - Project-Modell: strukturelle Slots, Backward-Compat-Aliase

Files:

- Modify: `src/core/project.py`
- Extend: `tests/test_project.py`
- Add/extend: `tests/test_project_slots.py`

Implementierung:

1. `PeakCutProject.__init__`:
   - interne Felder `_marker_track`, `mic_tracks`, `mix_track`, `transcript_path`, `videos`.
   - `keyboard_track` als Property-Alias auf `marker_track`.

2. `set_files(keyboard, mics, videos, mix=None, transcript=None)`:
   - alte Aufrufe bleiben gueltig.
   - `marker_track = keyboard`.
   - `mic_tracks = list(mics)`, aber defensiv Mix via `import_classifier.is_mix_track`
     ausfiltern, wenn ein Legacy-Caller noch Mix in `mics` gibt.
   - `mix_track = mix or erster Mix aus legacy mics`.
   - `transcript_path = transcript`.
   - `_guest_name` resetten.

3. `get_all_file_paths()`:
   Marker + echte Mics + Mix + Transcript + Videos.

4. `get_reference_track()`:
   - `mix_track` zuerst.
   - Legacy-Fallback: scan `mic_tracks` via `audio_routing.get_mix_track` fuer alte Tests/Objekte.
   - Diese Reihenfolge ist Pin-1-relevant: Task 2 muss schon vor Task 4 garantieren,
     dass `get_reference_track()` den strukturellen `mix_track` bevorzugt, bevor der
     Loader in Task 4 die Mix-Datei aus legacy `mic_tracks` herauszieht. Sonst kann
     der XMLExporter auf ein mono Mic zurueckfallen und `channelcount`/Audio-Metadaten
     veraendern.

Tests:

- Alter 3-Arg-`set_files`-Aufruf mit `mics=[MIC1, Mix]` migriert zu `mic_tracks=[MIC1]`,
  `mix_track=Mix`.
- Neuer 5-Arg-Aufruf setzt alle Slots.
- `keyboard_track` und `marker_track` sind echte Aliase.
- `get_all_file_paths` enthaelt alle Slots genau einmal.
- `get_reference_track` bevorzugt `mix_track`.

## Task 3 - audio_routing und Speech-Audio mit strukturellem Mix

Files:

- Modify: `src/core/audio_routing.py`
- Modify: `src/core/session.py`
- Extend: `tests/test_audio_routing.py`
- Extend: `tests/test_mp3_exporter_via_audio_routing.py`
- Extend: `tests/test_playback_audio_source.py`

Implementierung:

1. `audio_routing.is_mix_track` delegiert zu `import_classifier.is_mix_track`.

2. `get_mix_track(project)`:
   - `project.mix_track` zuerst.
   - Legacy-Fallback scannt `project.mic_tracks`.

3. `get_source_mic_tracks(project)`:
   - Gibt `project.mic_tracks` ohne Mix-Fallback zurueck.

4. `PeakCutSession`:
   - neues Feld `mix_audio: AudioSegment | None`.
   - `load_audio_lazy()` laedt Marker, Mix und echte Mics.
   - `mic_audios` bleibt 1:1 zu `project.mic_tracks`, nicht inklusive Mix.

5. `get_speech_audio_segment(session, start_ms, end_ms)`:
   - Mix vorhanden -> `session.mix_audio[start:end]`.
   - kein Mix -> Overlay echter Mics wie heute.
   - Legacy-Fallback fuer alte ad-hoc Sessions mit Mix in `mic_tracks` bleibt bis Tests
     umgestellt sind, aber nicht als primaerer Pfad.

Tests:

- Struktureller Mix: `project.mix_track=Mix`, `mic_tracks=[MIC1, MIC2]` -> Segment nur Mix,
  keine Overlay-Aufrufe.
- Kein Mix -> Overlay MIC1+MIC2.
- Legacy `mics=[MIC1, Mix]` bleibt phasingfrei.
- `mic_tracks/mic_audios` aligned nach `load_audio_lazy`.
- `resolve_playback_audio_source` nutzt strukturellen Mix.

Gate C Teil 1: #71a-Phasing-Schutz ist strukturell erhalten.

## Task 4 - Schema v4: Persistenz und Migration

Files:

- Modify: `src/core/project_archive.py`
- Add: `tests/test_project_archive_schema_v4_import_slots.py`
- Extend: `tests/test_project_archive.py`
- Extend: `tests/test_audio_routing_safety.py` oder neuer Pin in Task 0

Schema v4:

```json
"project": {
  "marker_track": "...",
  "mic_tracks": ["MIC1.wav", "MIC2.wav"],
  "mix_track": "Mix.mp3",
  "transcript_path": "Transkript.docx",
  "videos": ["CAM1.mov"],
  "guest_name": "...",
  "path_root_strategy": "common_parent",
  "has_external_paths": false
}
```

Backward load:

- v1-v3:
  - `marker_track = project.keyboard_track`
  - `mix_track = erster Mix aus project.mic_tracks`
  - `mic_tracks = mic_tracks ohne Mix`
  - `transcript_path = None`
  - `keyboard_track` im Payload wird weiter akzeptiert.

Save:

- schreibt `schema_version = 4`.
- schreibt nur `marker_track`, nicht mehr `keyboard_track` als canonical.
- Optional: `legacy_keyboard_track` NICHT schreiben, damit v4 klar ist.

Root/Pfad-Mapping:

- `_media_paths(project)` enthaelt Marker, echte Mics, Mix, Transcript, Videos.
- `build_archive_payload` relativiert `mix_track` und `transcript_path`.
- `load_project_archive` setzt Project-Slots ueber neuen `set_files`.

Tests:

- v3-Akte mit Mix in `mic_tracks` laedt als struktureller Mix.
- v4-Akte roundtript exakt.
- Ordner-Umzug relativiert Marker/Mics/Mix/Transcript/Videos.
- Zukunfts-Schema-Guard bleibt.
- Pin-1-XML identisch nach Save -> Load -> Re-Export.

Gate B STOPP: Schema-v4 durch Carl/Claude blessen.

## Task 5 - Consumer-Umhaengung: Analyse, Export, Folgenschnitt, Smart

Files:

- Modify: `src/gui/workers.py`
- Modify: `src/core/analysis_process.py` nur falls noetig fuer Benennung/Docs.
- Modify: `src/core/folgenschnitt_pipeline.py`
- Modify: `src/core/folgenschnitt_multitrack_layout.py`
- Modify: `src/core/sinnabschnitt_exporter.py`
- Modify: `src/core/exporters.py` falls Tests zeigen, dass audio source noch legacy annimmt.
- Extend relevant tests.

Ziel:

- `AnalysisWorker` gibt echte `mic_tracks` und `reference_track=project.mix_track` weiter.
- Speaker-Activity bekommt keine Mix-Datei mehr.
- Sync nutzt Mix, wenn vorhanden.
- MP3Exporter/Speak/Smart/Multitrack-Audio nutzen weiter `audio_routing`.
- XMLExporter/FolgenschnittXMLExporter bleiben Pin-1-kompatibel. Kein bewusstes XML-Format-Delta.

Tests:

- `AnalysisWorker` config_data enthaelt `mic_tracks` ohne Mix und `reference_track=Mix`.
- `analysis_process` speaker assignments sehen nur echte Mics.
- `folgenschnitt_multitrack_layout.build_audio_track_plan` waehlt Mix aus `mix_track`.
- `sinnabschnitt_exporter` Audio-Referenz waehlt `mix_track`, Fallback erster echter Mic.
- `MP3Exporter` phasingfrei mit strukturellem Mix.

Gate C: Audio-/Analyse-Consumer gruen, #71a- und #76-Fokustests gruen.

## Task 6 - Guest-Name und letzte Heuristik-Inseln zentralisieren

Files:

- Modify: `src/core/guest_name.py`
- Modify: `src/core/speaker_activity.py`
- Extend: `tests/test_guest_name.py` oder add `tests/test_guest_name_import_classifier.py`
- Extend: `tests/test_speaker_activity_mix_hub.py`

Implementierung:

- `guest_name.extract_guest_name` nutzt `import_classifier.is_mix_track`, nicht `"mix" in name.lower()`.
- Falls `PeakCutProject.guest_name` aufgerufen wird, sind `mix_track` und `get_all_file_paths`
  bereits richtig.
- `speaker_activity._is_speaker_mic_candidate` nutzt `import_classifier.is_marker_track`
  plus `audio_routing.is_mix_track`; keine lokalen Keyboard-Substring-Inseln mehr.

Tests:

- `mixer_recording.wav` erzeugt nicht versehentlich Gastname.
- HM-Mix-Namen bleiben stabil.
- `keyboard`, `keys`, `klavier`, `marker` werden als Nicht-Sprecher-Mic ausgeschlossen.
- `monkey.wav` / `keynote.wav` bleiben Sprecher-Mic oder werden nach Rolle korrekt nicht als Marker erkannt.

## Task 7 - Import-UI: Slot-Dialog statt `_categorize_files`

Files:

- Add: `src/gui/import_slots_dialog.py`
- Modify: `src/gui/main_window.py`
- Add: `tests/test_import_slots_dialog_state.py`
- Extend: `tests/test_project_archive_main_window.py` oder neues `tests/test_main_window_import_slots.py`

UI-Entscheidung:

- Nach Datei-Auswahl zeigt PeakCut einen Dialog "Import zuordnen".
- Jede Datei hat eine Rollen-Auswahl: Marker, Mic, Mix, Transkript, Kamera, Ignorieren.
- Auto-Vorschlag ist vorausgewaehlt, aber sichtbar korrigierbar.
- Unten Validierungsstatus:
  - Marker fehlt.
  - Keine Sprachquelle: mindestens ein Mic oder Mix erforderlich.
  - Mehrere Marker/Mixe: nur einer erlaubt; Nutzer muss korrigieren oder PeakCut nimmt nicht an.
- Button "Weiter" ist nur bei validen Slots aktiv.

Implementierungs-Schnitt:

- Pure Funktion/State fuer Tests: `build_import_dialog_state(paths)`, `apply_role_change(state, path, role)`,
  `slots_from_state(state)`.
- Qt-Dialog ist duenner Wrapper um diesen State.
- `MainWindow._on_import`:
  1. file dialog
  2. slot dialog
  3. `find_project_archive_for_files` mit allen bestaetigten Slots
  4. Gastname-Dialog
  5. `_start_analysis`

Ersetzt:

- `_categorize_files` wird entfernt oder zu einem reinen Test-/Legacy-Helfer ohne Produktionsaufruf.
- `_keyboard_file`, `_mic_files`, `_video_files` erhalten Werte aus `ImportSlots`.
- neues `_mix_file`, `_transcript_file`.

Tests:

- Dateien werden vorgeschlagen, Nutzer kann Mix zu Mic korrigieren und umgekehrt.
- Ohne Marker bleibt Weiter disabled.
- Mit Marker + Mix, aber ohne Mics ist Import valide.
- Mit Marker + Mics, aber ohne Mix ist Import valide.
- Transcript-Docx bleibt optional.
- `MainWindow._start_analysis` erstellt Project mit Mix und Transcript getrennt.

Gate D STOPP: Max/Claude bestaetigen UI-Flow vor Transcript-Wiring.

## Task 8 - Transcript-Slot-Wiring

Files:

- Modify: `src/gui/main_window.py`
- Possibly modify: `src/gui/workers.py`
- Add: `tests/test_import_transcript_slot.py`

Verhalten:

- Wenn `transcript_path` gesetzt und `project.get_reference_track()` vorhanden:
  - MainWindow startet nach Session-Erzeugung den bestehenden entkoppelten
    Transcript-Pfad, nicht einen synchronen Main-Thread-Import. Mechanik:
    `_transcript_worker`/Roadmap-#3-Finished-Vertrag wiederverwenden oder eine
    kleine Worker-Variante mit demselben Lifecycle-Muster fuer Descript-Import
    bauen. Wichtig ist: kein `import_descript_transcript()` direkt im UI-Thread
    vor der Analyse.
  - Ergebnis setzt `session.transcript_ref`, `session.transcript_error=None`.
  - Fehler setzt `session.transcript_error` und sendet Status, blockiert Analyse nicht.
- Wenn kein Mix vorhanden:
  - Transcript wird im Project gespeichert, aber nicht importiert.
  - Status: "Transkript vorhanden, aber kein Mix fuer Ausricht-Schutz".

Wichtig:

- Nicht in `AnalysisWorker` pressen. Descript-Import ist kein Analyse-Ergebnis und soll
  nicht den HC-2-Analysepfad vergroessern. Gleichzeitig darf er die UI nicht blockieren:
  er laeuft ueber den bestehenden entkoppelten TranscriptWorker-/finished-Hook-Stil.
- Autosave schreibt spaeter `transcript_ref` wie Roadmap #3.

Tests:

- Transcript-Slot mit Mix ruft Import-Helfer und setzt Ref.
- Transcript-Slot ohne Mix blockiert nicht.
- Kaputte docx blockiert nicht und erzeugt Status.

## Task 9 - Alte Tests und Safety-Pins auf neue Welt umstellen

Files:

- Update/replace:
  - `tests/test_audio_routing_safety.py`
  - `tests/test_mp3_exporter_via_audio_routing.py`
  - `tests/test_xml_reference_stability.py`
  - `tests/test_project_archive.py`
  - alle Tests, die "Mix in mic_tracks" als gewollten Dauerzustand pinnen.

Regel:

- Tests duerfen Legacy-Mix-in-mic_tracks nur noch als Migration/Backward-Compat testen.
- Neue Normalform: `project.mix_track` separat, `project.mic_tracks` echte Mics.

Schluss-Suche:

- `rg -n "\"mix\" in|keyboard|keys|klavier|mic_tracks.*mix|session.play_current" src tests`
- Jede Fundstelle einordnen:
  - zentraler Klassifizierer,
  - bewusst alter Schema-Key,
  - Test-Fixture,
  - oder zu fixender Rest.

Gate:

- Keine neue Heuristik-Insel.
- Guest-Name-Insel weg.
- Speaker-Activity-Keyboard-Insel weg.

## Task 10 - Integration und App-Smoke

Testbloecke:

1. Core:
   `./venv311/bin/python -m pytest tests/test_import_classifier.py tests/test_project_slots.py tests/test_project_archive_schema_v4_import_slots.py -q`

2. Audio/Export:
   `./venv311/bin/python -m pytest tests/test_audio_routing.py tests/test_mp3_exporter_via_audio_routing.py tests/test_playback_audio_source.py tests/test_xml_reference_stability.py -q`

3. UI:
   `./venv311/bin/python -m pytest tests/test_import_slots_dialog_state.py tests/test_main_window_import_slots.py -q`

4. Pins:
   `./venv311/bin/python -m pytest tests/test_import_refactor_safety.py tests/test_audio_routing_safety.py tests/test_keyboardstellen_smart_regression.py tests/test_multitrack_folgenschnitt_safety.py -q`

5. Full suite:
   `./venv311/bin/python -m pytest -q`

Manual smoke:

- HM bestehende `.peakcut` v3 laden -> v4 speichern -> Keyboardstellen-XML byte-identisch.
- Frischer HM-Import mit Marker/MIC1/MIC2/Mix/Cams -> Dialog-Vorschlaege korrekt -> Export normal.
- Fremdproduktion 1plus1 mit Marker-Hack/Mics/Mix/Cams -> Mix separiert, Folgenschnitt-Export normal.
- Import mit nur Marker+Mix -> Analyse startet, Sprecheraktivitaet ggf. leer, Keyboardstellen/Speak/Smart-Quelle sauber.
- Import mit Marker+Mics ohne Mix -> Analyse startet, Speak-Fallback rendert Mics, Smart meldet "kein Mix" wie bisher.
- Import mit Transcript.docx + Mix -> transcript.json/ref entsteht, Smart kann ohne Whisper starten.

Merge-Kriterien:

- Full suite gruen.
- Pin-1 stabil.
- Keine ungetrackten Repro-Skripte/Smoke-Artefakte.
- `rg` zeigt keine unentschiedene Namens-Heuristik-Insel mehr.
- Max bestaetigt frischen Import-Flow in der App.

## Aufteilungsvorschlag Claude/Carl

Sinnvoll teilbar:

- Claude: Task 0, Task 4, Task 7, Task 8, Task 10 App-Smoke.
- Carl: Task 1, Task 2, Task 3, Task 6, Cross-Review Task 5.
- Gemeinsam: Task 5, weil dort Audio/Analyse/Folgenschnitt zusammenlaufen und #71a/#76-Pins am empfindlichsten sind.

Wenn nur eine Person baut: Reihenfolge strikt Task 0 -> 1 -> 2 -> 4 -> 3 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10.
Task 4 vor Task 3 ist Absicht: sobald das Project-Modell steht, muss Save/Load frueh beweisen, dass v3-Migration
nicht spaeter still eine zweite Wahrheit erzeugt.
