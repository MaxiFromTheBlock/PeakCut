# Plan — #76 Wiedergabe-UX (synchrone Ton+Bild-Vorschau)

> **Herkunft:** Carls Umsetzungsplan (2026-06-15) als Bau-Basis + Claude-Cross-
> Review (3 Flags), von Carl in den Plan eingearbeitet. Diagnose-Grundlage:
> `docs/specs/2026-06-15-wiedergabe-76-diagnose.md`.
> **Bau-Freigabe (Carl):** auf sauberem Stand NACH dem Slice-B/Integritäts-
> Merge nach main. Konstellation: Carl plant, Claude baut TDD, Max entscheidet.

## Bau-Status (2026-06-15)

Gebaut von Claude, TDD, je eigener Commit (`1f797ff..38c11b9` auf develop):
- [x] **Task 0** Baseline (621 grün beim Merge).
- [x] **Task 1** playback_modes (Gate A). [x] **Task 2** playback_windows (Gate B).
- [x] **Task 3** playback_audio_source (Gate C) + **P2-Fix** (Mic-Quellen-Fingerprint, Carl-Review).
- [x] **Task 4** PeakVideoPreview Clip-API (Gate D).
- [x] **Task 4.5** Drift-Spike (`scripts/verify_qmediaplayer_position_resolution.py`)
  — **gelaufen 2026-06-15** an Teil-2-Material: Start-Latenz 60ms,
  position()-Kadenz Audio ~99ms / Video ~51ms, **roh-Drift (free-run, ohne
  Korrektur) p95 94ms / max 116ms**. Befund: 40ms liegt unter dem
  Granularitätsboden (Carls Flag 1 bestätigt) → Schwelle provisorisch **100ms**
  (`config.playback_drift_tolerance_ms`, Carl-Vorabfreigabe). Roh ≠ korrigiert:
  der finale Wert kommt aus dem korrigierten Task-9-Lauf an einer echten Folge
  mit gültigen In/Out-Punkten. **Offen für Carl-Methodik: ist 100ms (≈2,5 Frames)
  als Boundary-Beurteilungs-Vorschau ok, oder enger korrigieren (mehr Bild-Snaps)?**
- [x] **Task 5** ReviewPlaybackController (Gate E) — **Carl-Review durch**, zwei
  P1s gefixt (Video-Readiness-Signal + Post-Korrektur-Restdrift als Gate-Wert,
  corrected-Signal). Controller-Sanity-Gate (Task 9 an Teil-2, key-Modus)
  **BESTANDEN: Restdrift max 85ms ≤ 100ms, 6 Korrekturen**. → Task 6 frei.
- [x] **Task 9** echtes Drift-Messskript (`scripts/verify_playback_sync_real.py`) — Max läuft es nach der Integration (Gate I).
- [ ] **Task 6** ReviewPage-Integration — **gesperrt bis Carl-Gate-E-OK** (riskanteste Naht: session.mode-Migration key/speak/smart, sinn_btn raus, play_current aus dem Review-Pfad).
- [ ] **Task 7** Session/Legacy entkoppeln. [ ] **Task 8** UI-State. [ ] **Task 10** Schluss-Gate.

Volle Suite zuletzt 674 grün. Drift-Toleranz config-gesteuert
(`playback_drift_tolerance_ms=40`, finaler Wert aus dem Spike).

## Architektur-Call
Zwei QMediaPlayer, **Audio als Master-Uhr**, Video folgt und wird bei Drift korrigiert.
- **Video:** bestehender `PeakVideoPreview.player`, bleibt stumm.
- **Audio:** neuer separater `QMediaPlayer` nur für hörbaren Key/Speak/Smart-Ton.
- **Nicht** QAudioSink/QSoundEffect: QSoundEffect ist für kurze Effekte; QAudioSink
  hieße PCM selbst puffern/clocken/seeken (mehr Low-Level als nötig). QMediaPlayer
  liefert `position()`/`setPosition()`/`mediaStatus`/`playbackState` → messbare Drift.
- **simpleaudio** wird aus dem Review-/Session-Wiedergabepfad entfernt, bleibt aber
  im Repo für `MicPreviewWorker` (Zuordnungsseite, `mic_preview_worker.py:53`).
  Komplett-Entfernung = separater Mini-DEP-Slice, nicht #76.

### Mix-Quelle
- **Key:** `project.keyboard_track` direkt.
- **Speak/Smart mit Mix:** `audio_routing.get_mix_track(project)` direkt.
- **Speak/Smart ohne Mix:** Fallback `get_speech_audio_segment(...)` → temporär
  gerenderte WAV (`.peakcut/preview_audio/<hash>.wav`). Kein Auto-Mix-Feature,
  nur Preview-Fallback; produktiv bleibt Mix bevorzugt. **Vorher
  `session.load_audio_lazy()`** (im Resolver-Test mitprüfen).

## Drei eingearbeitete Schärfungen (aus Claude-Cross-Review)
1. **Drift-Spike VOR dem Controller (neues Gate D2).** `scripts/verify_qmediaplayer_position_resolution.py`:
   minimaler Doppel-QMediaPlayer-Prototyp (noch nicht in ReviewPage), spielt echten
   Clip, loggt positionChanged-Kadenz, Startlatenz, gemessene Drift, Korrekturhäufigkeit.
   Ergebnis legt die Gate-Schwelle fest: Ziel ≤ 40 ms; wenn AVFoundation gröber
   reportet, **dokumentiert** ≤ 80/100 ms. Messbar stabil, nicht „gefühlt synchron".
2. **Harter Lifecycle-Vertrag (Controller + PeakVideoPreview), schließt CONC-3.**
   Controller `stop()`/`cleanup()`: beide Player stoppen, Timer stop, dynamische
   Signale trennen, `audio_player`/`audio_output` `deleteLater()`, idempotent.
   `PeakVideoPreview.cleanup()` erweitern: `player.stop()`, Video/Audio-Output lösen
   (wenn sauber möglich), `player.deleteLater()`, `audio_output.deleteLater()`.
3. **Readiness-Gate vor gemeinsamem Start.** Kleine State-Machine: `prepare(window, source)`
   setzt beide Medien; Start erst wenn **beide** ready (MediaStatus Loaded/Buffered):
   Audio→`media_start_ms`, Video→`window.start_ms`, definierte Startreihenfolge, dann
   Drift-Monitor. Timeout (~5s) → kontrollierter Fehlerstatus, kein hängender Play-Button.
   Ersetzt „setPosition; play; hoffen".

## Tasks & Gate-Reihenfolge
- **Task 0 — Safety-Harness.** Pin-1 unverändert; #76 fasst keinen Exporter/Archive an.
  Characterization des heutigen `sinn_btn` (wird später invertiert). *Gate 0: Pin-1 grün,
  kein Export-/Archive-/Folgenschnitt-Code im Diff.*
- **Task 1 — Playback-Mode Contracts.** `core/playback_modes.py` (key/speak/smart,
  normalize/next/label), `session.mode` aus `config.playback_mode` (Default "key"),
  `switch_mode()` spielt NICHT mehr automatisch, `load_analysis_results` normalisiert
  statt hart "keyboard". Config-Default `"playback_mode": "key"`. **Gate A.**
- **Task 2 — Playback Window Resolver.** `core/playback_windows.py`:
  `PlaybackWindow(mode,start,end,disabled_reason)`, `build_playback_window(session,peak)`.
  Key=pos+preview_dur; Speak=in/out; Smart=ClipCandidate (gültig nur: nicht ignoriert,
  existiert, nicht discarded, score>0.0, end>start), sonst disabled. Qt-frei. **Gate B.**
- **Task 3 — Audio Source Resolver.** `core/playback_audio_source.py`:
  `PlaybackAudioSource(path,media_start,media_end,timeline_start,timeline_end,cleanup_path)`,
  `resolve_playback_audio_source(session,window)` nach Mix-Regeln oben; ohne Mix →
  load_audio_lazy + WAV-Render. Keine neue Mix-Heuristik (nur audio_routing). **Gate C.**
- **Task 4 — PeakVideoPreview Clip-API.** `prepare_clip(in,out)` (setzt, startet nicht),
  `play_prepared()`, `pause_clip()`, `stop_clip_at(out)`, `current_mix_position()`.
  `play_from` bleibt abwärtskompatibel (intern prepare+play). Offset-Mapping
  `_mix_to_video_ms`/`_video_to_mix_ms` UNVERÄNDERT, Screenshot/LUT unberührt. **Gate D.**
- **Task 4.5 — Drift/Position-Spike.** s. Schärfung 1. **Gate D2: Schwelle finalisiert.**
- **Task 5 — Qt Playback Controller.** `gui/review_playback_controller.py`: besitzt
  `audio_player`/`audio_output` + bekommt `video_preview`; `play(window,source)`/`stop()`/
  `is_playing()` + `finished`/`drift_updated`. Readiness-Gate (Schärfung 3) + Master-Uhr
  (Audio→Mix-Timeline, Video folgt, Drift>Schwelle → `video_preview.set_position`) +
  harter Cleanup (Schärfung 2). Tests mit Fake-Playern. **Gate E.**
- **Task 6 — ReviewPage Integration.** `sinn_btn` entfernen; `on_play` → build_window →
  (disabled? Status/Tooltip) → resolve_source → Controller.play; `navigate_to_peak` stoppt
  Wiedergabe + statischer Frame; `_poll_playback` beobachtet Controller statt simpleaudio;
  `_on_mode_toggle` stoppt + cycelt + `config.set_value("playback_mode")` + kein Auto-Play;
  `_refresh_sinn_btn`→`_refresh_play_availability`. **Gate F: ReviewPage nutzt kein
  session.play_current/stop_playback/is_playing mehr.**
- **Task 7 — Session/Legacy entkoppeln.** `session.play_current` nicht mehr Review-Pfad;
  ReviewPage + `closeEvent` stoppen den neuen Controller; `core/playback.py` bleibt nur
  für MicPreviewWorker. **Gate G:** `rg session.play_current|stop_playback|is_playing`
  zeigt keine Review-/Main-Playback-Abhängigkeit mehr.
- **Task 8 — UI-State.** Play ▶/■, Mode-Button Key/Speak/Smart, Smart-disabled-Tooltip,
  Key/Speak nur bei fehlender Quelle disabled, Navigation refresht Tooltip. **Gate H.**
- **Task 9 — Drift-Messskript.** `scripts/verify_playback_sync_real.py` (--archive/--peak-index/
  --mode/--duration-s): QApplication + Controller, sampled 100ms (audio/video/drift),
  500ms Warmup ignoriert, Report max/p95/corrections/pass-fail. **Gate I: max Drift nach
  Warmup ≤ finalisierte Schwelle, am Sheila-Material laufen lassen, dokumentiert.**
- **Task 10 — Schluss-Gate.** Full suite grün, Pin-1 byte-identisch, `rg` bestätigt kein
  `sinn_btn`/`session.play_current`/simpleaudio im Review-Pfad; App-Smoke (Key/Speak/Smart
  synchron, Smart-ohne-Candidate disabled, Modewechsel/Back/Next stoppt, CloseEvent räumt
  auf). **Merge-Gate J:** Drift ≤ Schwelle, Max kann ≥5 Sheila-Sinnabschnitte hörend+
  sichtend beurteilen, keine Export-Diffs.

## Aufteilung
Nicht riskant parallelisieren. Claude: Tasks 1–3 (pure Core/Resolver) + Task 9/Spike.
Controller/ReviewPage (4–6, die gefährliche Naht) seriell mit Carl-Gegenreview an
Gate E/F. Carl-Cross-Review an Gate E/F/I. Nicht zwei Leute gleichzeitig in
ReviewPage + QMediaPlayer-Lifecycle.

## Plan-Pin
#76 ist erst fertig, wenn simpleaudio im Review-Pfad tot ist — keine gemeinsame
Uhr per Timer-Drumherum, sondern eine messbare: **Audio Master, Video folgt.**
Pin-1 (Keyboardstellen-XML) bleibt trivial erfüllt; Keyboard-Mode-Preview muss
weiter funktionieren.
