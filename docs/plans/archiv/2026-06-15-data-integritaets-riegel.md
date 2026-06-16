# Plan — Daten-Integritäts-Riegel (DATA-1 / DATA-2 / KI-2 + AUD-1a)

> **Herkunft:** Carls Umsetzungsplan (2026-06-15) als Bau-Basis, nach dem
> Mehr-Agenten-Health-Check (`2026-06-15-state-of-peakcut-health-check.md`).
> Claude-Cross-Review der Vorbedingungen am Code: bestätigt (siehe unten).
> Konstellation: Carl plant, Claude baut TDD an Gates, Max entscheidet.

## Scope & Reihenfolge
Ein kleines Paket auf `develop`, **getrennte Commits + Gates**:
1. **DATA-1** — atomare Writes (`core/atomic_io.py`).
2. **DATA-2** — Schema-Versions-Policy (kein still-kaputt-Speichern von Zukunfts-Akten).
3. **KI-2** — R2-Ausricht-Riegel (misaligned Transkript → keine Kandidaten).
4. **AUD-1a** (optional, Max-Go: JA) — `speaker_activity`-Mix-Heuristik an `audio_routing.is_mix_track` andocken.

**NICHT in diesem Paket:** Export-Orchestrierung raus aus GUI (ARCH-1) → vor NAS/Hybrid.
Großer Klassifizierer-Merge → #77. `guest_name.py`/`_categorize_files` → #77.

## Harte Leitplanken
- Pin-1: Keyboardstellen-XML byte-identisch (SHA-256).
- 593 Tests bleiben grün; jede Näht bringt eigene Tests.
- Kein Quickfix-Guard — Wurzel-Fix.

## Cross-Review-Verifikation (Claude, am Code geprüft)
- ✅ `atomic_io.py` als neutrales Modul korrekt: `transcript_archive` importiert
  `project_archive` (Modulebene, Zeile 19) → geteilter Helfer dort gäbe Import-Zyklus.
- ✅ Toleranz-Schalter existiert bereits: `smart_boundary_alignment_tolerance_ms = 120000` (`config.py:40`).
- ✅ `BoundaryOutcome.INFRA_FEHLT` + `SmartBoundaryRunResult` existieren; das
  „INFRA_FEHLT → 0 Kandidaten"-Invariant ist schon im Dataclass erzwungen (`models.py:192-195`);
  Pipeline hat den INFRA-Abbruchpfad bereits (`pipeline.py`). KI-2 = zweiter Auslöser.
- ⚠️ **Bewusste Vertragsänderung:** `tests/test_project_archive.py:71`
  (`test_lower_or_newer_schema_..._loads_best_effort`) pinnt aktuell, dass eine
  Zukunfts-Akte (v999) „best effort" lädt — genau der DATA-2-Bug. Der Test wird
  gesplittet: Zukunft (>CURRENT) → erwartet `ProjectArchiveError`; uralt (v0) → lädt weiter.

## Tasks

### Task 0 — Safety-Harness (erledigt, grün)
Pin-Tests vorab grün: multitrack_safety, audio_routing_safety, project_archive*,
smart_run_result, smart_two_condition_barrier. **64/64 grün, Pin-1 stabil.**

### Task 1 — Atomarer JSON-Schreiber (DATA-1)
- Neu: `src/core/atomic_io.py` → `write_json_atomic(path, payload, *, indent=None, ensure_ascii=False, fsync=True)`:
  temp im selben Ordner → json.dump → flush → optional `os.fsync` → `os.replace` →
  best-effort Directory-fsync; bei Exception tmp löschen, alte Datei intakt, re-raise.
- `project_archive.save_project_archive` (247-248) + `transcript_archive.write_transcript_json` (82-85) nutzen den Helfer.
- **Gate A:** Abbruch lässt alte Akte intakt; Transcript-Roundtrip grün.

### Task 2 — Schema-Versions-Policy (DATA-2)
- `project_archive.py`: fehlend→v1; ≤CURRENT→laden; >CURRENT→`ProjectArchiveError`;
  ungültiger Wert→kontrollierter Fehler. **Save prüft die vorhandene Akte** und
  überschreibt eine Zukunfts-Akte NICHT (sonst frisst Autosave sie nach abgelehntem Load).
- Kein Passthrough-Bag, kein Read-only-UI in diesem Slice.
- **Gate B:** Keine Zukunfts-Akte still kaputtschreibbar; HC-4/Candidate/Transcript/v3-Roundtrips grün.

### Task 3 — R2-Ausricht-Riegel (KI-2)
- `clip_boundary/pipeline.py`: vor dem Peak-Loop — span+duration vorhanden & Drift > Toleranz
  → `SmartBoundaryRunResult(category=INFRA_FEHLT, ...)`, Decider nicht aufgerufen, keine Kandidaten.
  Fehlende Dauer/span → nicht blockieren.
- `review_page.py`: INFRA = laute Statusmeldung, keine Sinnabschnitt-Artefakte, kein „Smart-Ergebnis"-Autosave.
- Toleranz aus `smart_boundary_alignment_tolerance_ms`.
- **Gate C:** Misalignment erzeugt keine `ClipCandidate.score`, keine Artefakte, keine Keyboardstellen-Änderung.

### Task 4 — `speaker_activity` an Hub (AUD-1a, optional, Max-Go: JA)
- `speaker_activity._is_speaker_mic_candidate`: Mix-Erkennung über `audio_routing.is_mix_track`
  statt `"mix" in basename`. keyboard/keys/klavier bleiben lokal (→ #77). `guest_name`/`_categorize_files` unangetastet.
- **Gate D:** `mixer_recording.wav` bleibt Sprecher-Mic; `Sheila Mix.mp3`/`MIXDOWN.wav` ausgeschlossen; kein Pin-1-Drift.

## Abschluss
Relevante Subsets + Full Suite + Pin-1-SHA + App-Smoke (.peakcut Save/Load + Smart-Misalignment-Status).
CONTEXT.md + CLAUDE.md updaten. Carl-Schluss-Cross-Review vor evtl. main-Merge.
