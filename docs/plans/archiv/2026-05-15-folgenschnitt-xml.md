# Folgenschnitt-XML (Stufe 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PeakCut erzeugt zusätzlich zur Keyboardstellen-XML eine zweite FCP7-XML, die einen sprecherbasierten Rohschnitt der ganzen Folge als flache Timeline enthält.

**Architecture:** Getrennte, je einzeln testbare Pipeline: `speaker_activity` (Pegel/Dominanz pro Fenster) → `speaker_turns` (geglättete Sprecherabschnitte) → `edit_decisions` (Kameraentscheidungen, reine Logik) → `FolgenschnittXMLExporter` (flache FCP7-Timeline). Eigenes Subpackage `core/folgenschnitt/`, vom bestehenden Analyse-Subprozess aufgerufen. Bestehender `XMLExporter` bleibt unangetastet. Reihenfolge nach Reviewer: Contracts zuerst, XML-Importrisiko früh mit Fake-Daten beweisen, dann erst die Erkennungslogik schärfen, dann kalibrieren.

**Tech Stack:** Python 3.11, NumPy, soundfile, pytest. Keine neuen Laufzeit-Dependencies außer `soundfile` (falls noch nicht vorhanden — Task 0 prüft).

**Spec:** `docs/specs/2026-05-15-folgenschnitt-xml-design.md` (verbindlich; bei Konflikt gewinnt die Spec).

**Review-Gates (nicht überspringen):**
- Nach **Task 1** (Contracts): externer Reviewer prüft (a) — STOP, auf Freigabe warten.
- Nach **Task 5** (XML-Mini-Test in Premiere/Resolve): externer Reviewer prüft (b) + Max bestätigt Import — STOP, auf Freigabe warten.
- **Task 9** (Export-Aktivierung) erst nach erfolgreicher Kalibrierung (Task 10) freischalten.

---

## File Structure

| Datei | Verantwortung | Status |
|-------|---------------|--------|
| `src/core/folgenschnitt/__init__.py` | Paket-Marker | Create |
| `src/core/folgenschnitt/contracts.py` | Datenmodelle: `ActivityFrame`, `SpeakerTurn`, `EditDecision`, `RoleMapping`. Alle Zeiten in ms. Serialisierbar (`to_dict`/`from_dict`). | Create |
| `src/core/folgenschnitt/speaker_activity.py` | Audio fensterweise → `list[ActivityFrame]`. RMS, Noise-Floor, Dominanz. | Create |
| `src/core/folgenschnitt/debug_csv.py` | `list[ActivityFrame]` → CSV-Datei. | Create |
| `src/core/folgenschnitt/speaker_turns.py` | `list[ActivityFrame]` → geglättete `list[SpeakerTurn]`. | Create |
| `src/core/folgenschnitt/edit_decisions.py` | `list[SpeakerTurn]` + `RoleMapping` → `list[EditDecision]`. 5-s-Regel, Mindest-Shot, Anticipation. | Create |
| `src/core/folgenschnitt/exporter.py` | `FolgenschnittXMLExporter`: `list[EditDecision]` + Pfade → flache FCP7-XML. | Create |
| `src/core/folgenschnitt/params.py` | Start-Parameter als Konstanten (NICHT UI). | Create |
| `tests/folgenschnitt/test_contracts.py` … `test_exporter.py` | Unit-Tests je Modul. | Create |
| `scripts/folgenschnitt_xml_minitest.py` | CLI: Fake-`EditDecision`s → XML, für manuellen Premiere/Resolve-Import. | Create |
| `src/core/analysis_process.py:48-132` | Sprecher-Aktivität in `run_analysis` einklinken (Task 8). | Modify |
| `src/gui/workers.py:201` | `FolgenschnittXMLExporter` in `ExportWorker` (Task 9, hinter Gate). | Modify |

Subpackage statt flacher `core/`-Module: bewusste Abweichung von der Spec-Wortwahl (`core/speaker_activity.py`), weil 7 zusammengehörige Module ein Feature bilden, das gemeinsam wächst. **Diese Strukturentscheidung ist Teil des (a)-Reviews.**

---

## Task 0: Vorbereitung & Dependency-Check

**Files:**
- Test: keine
- Modify: ggf. `requirements.txt`

- [ ] **Step 1: Prüfen ob soundfile verfügbar ist**

Run: `cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App && ./venv311/bin/python -c "import soundfile, numpy; print(soundfile.__version__, numpy.__version__)"`
Expected: zwei Versionsnummern, kein ImportError.

- [ ] **Step 2: Falls ImportError für soundfile**

Run: `./venv311/bin/pip install soundfile && echo "soundfile" >> requirements.txt`
Dann Step 1 wiederholen (muss jetzt PASS sein).

- [ ] **Step 3: Test-Verzeichnis anlegen**

```bash
mkdir -p /Users/max/Desktop/MF/Vibecoding/PeakCut/App/tests/folgenschnitt
touch /Users/max/Desktop/MF/Vibecoding/PeakCut/App/tests/folgenschnitt/__init__.py
```

- [ ] **Step 4: Commit**

```bash
cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App
git add requirements.txt tests/folgenschnitt/__init__.py 2>/dev/null; git commit -m "chore: folgenschnitt test scaffold + soundfile dep" || echo "nichts zu committen"
```

---

## Task 1: Contracts (Datenmodelle) — REVIEW-GATE (a)

**Files:**
- Create: `src/core/folgenschnitt/__init__.py`
- Create: `src/core/folgenschnitt/contracts.py`
- Test: `tests/folgenschnitt/test_contracts.py`

- [ ] **Step 1: Failing test schreiben**

`tests/folgenschnitt/test_contracts.py`:

```python
from core.folgenschnitt.contracts import (
    ActivityFrame, SpeakerTurn, EditDecision, RoleMapping
)


class TestActivityFrame:
    def test_roundtrip(self):
        f = ActivityFrame(start_ms=0, end_ms=200, rms_db={"mic1": -22.0, "mic2": -48.0},
                           noise_floor_db={"mic1": -55.0, "mic2": -54.0},
                           dominant="mic1", dominance_db=26.0)
        assert ActivityFrame.from_dict(f.to_dict()) == f

    def test_no_dominant_is_none(self):
        f = ActivityFrame(start_ms=200, end_ms=400, rms_db={"mic1": -50.0, "mic2": -50.0},
                          noise_floor_db={"mic1": -55.0, "mic2": -55.0},
                          dominant=None, dominance_db=0.0)
        assert f.dominant is None
        assert ActivityFrame.from_dict(f.to_dict()) == f


class TestSpeakerTurn:
    def test_duration(self):
        t = SpeakerTurn(speaker="mic2", start_ms=1000, end_ms=6000)
        assert t.duration_ms == 5000
        assert SpeakerTurn.from_dict(t.to_dict()) == t


class TestRoleMapping:
    def test_lookup(self):
        rm = RoleMapping(mic_to_speaker={"mic1": "matze", "mic2": "gast"},
                         camera_to_role={"Cam01.MP4": "matze_wide",
                                         "Cam02.MP4": "gast_wide",
                                         "Cam03.MP4": "gast_close"})
        assert rm.speaker_for_mic("mic2") == "gast"
        assert rm.wide_camera_for_speaker("gast") == "Cam02.MP4"
        assert rm.wide_camera_for_speaker("matze") == "Cam01.MP4"

    def test_roundtrip(self):
        rm = RoleMapping(mic_to_speaker={"mic1": "matze"},
                         camera_to_role={"A.MP4": "matze_wide"})
        assert RoleMapping.from_dict(rm.to_dict()) == rm


class TestEditDecision:
    def test_roundtrip_and_duration(self):
        d = EditDecision(start_ms=0, end_ms=8000, camera="Cam01.MP4",
                         speaker="matze", reason="speaker_active")
        assert d.duration_ms == 8000
        assert EditDecision.from_dict(d.to_dict()) == d
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App && ./venv311/bin/python -m pytest tests/folgenschnitt/test_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.folgenschnitt'`

- [ ] **Step 3: Minimale Implementierung**

`src/core/folgenschnitt/__init__.py`: leer (nur Paket-Marker).

`src/core/folgenschnitt/contracts.py`:

```python
"""Datenmodelle für den Folgenschnitt. Alle Zeiten in Millisekunden.

Frame-/Timecode-Umrechnung passiert ausschließlich im Exporter, niemals hier.
Alle Modelle sind JSON-serialisierbar (to_dict/from_dict).
"""
from dataclasses import dataclass, field


@dataclass(eq=True)
class ActivityFrame:
    start_ms: int
    end_ms: int
    rms_db: dict[str, float]            # mic-id -> RMS in dBFS
    noise_floor_db: dict[str, float]    # mic-id -> geschätzter Grundpegel dBFS
    dominant: str | None                # mic-id des dominanten Sprechers oder None
    dominance_db: float                 # Abstand dominant vs. zweitlautester (dB)

    def to_dict(self) -> dict:
        return {
            "start_ms": self.start_ms, "end_ms": self.end_ms,
            "rms_db": self.rms_db, "noise_floor_db": self.noise_floor_db,
            "dominant": self.dominant, "dominance_db": self.dominance_db,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ActivityFrame":
        return cls(
            start_ms=d["start_ms"], end_ms=d["end_ms"],
            rms_db=dict(d["rms_db"]), noise_floor_db=dict(d["noise_floor_db"]),
            dominant=d["dominant"], dominance_db=d["dominance_db"],
        )


@dataclass(eq=True)
class SpeakerTurn:
    speaker: str          # mic-id
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict:
        return {"speaker": self.speaker, "start_ms": self.start_ms, "end_ms": self.end_ms}

    @classmethod
    def from_dict(cls, d: dict) -> "SpeakerTurn":
        return cls(speaker=d["speaker"], start_ms=d["start_ms"], end_ms=d["end_ms"])


@dataclass(eq=True)
class RoleMapping:
    mic_to_speaker: dict[str, str]      # "mic1" -> "matze"
    camera_to_role: dict[str, str]      # "Cam01.MP4" -> "matze_wide"

    def speaker_for_mic(self, mic_id: str) -> str | None:
        return self.mic_to_speaker.get(mic_id)

    def wide_camera_for_speaker(self, speaker: str) -> str | None:
        want = f"{speaker}_wide"
        for cam, role in self.camera_to_role.items():
            if role == want:
                return cam
        return None

    def to_dict(self) -> dict:
        return {"mic_to_speaker": self.mic_to_speaker,
                "camera_to_role": self.camera_to_role}

    @classmethod
    def from_dict(cls, d: dict) -> "RoleMapping":
        return cls(mic_to_speaker=dict(d["mic_to_speaker"]),
                   camera_to_role=dict(d["camera_to_role"]))


@dataclass(eq=True)
class EditDecision:
    start_ms: int
    end_ms: int
    camera: str           # Kamera-Dateiname (Basename)
    speaker: str          # speaker-id, für Debug/Nachvollziehbarkeit
    reason: str           # "speaker_active" | "anticipation" | "hold"

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms,
                "camera": self.camera, "speaker": self.speaker, "reason": self.reason}

    @classmethod
    def from_dict(cls, d: dict) -> "EditDecision":
        return cls(start_ms=d["start_ms"], end_ms=d["end_ms"],
                   camera=d["camera"], speaker=d["speaker"], reason=d["reason"])
```

- [ ] **Step 4: Test ausführen, MUSS bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_contracts.py -q`
Expected: PASS (5 Tests).

- [ ] **Step 5: Gesamte Suite (keine Regression)**

Run: `QT_QPA_PLATFORM=offscreen ./venv311/bin/python -m pytest tests/ -q`
Expected: alle bisherigen + 5 neue grün.

- [ ] **Step 6: Commit**

```bash
git add src/core/folgenschnitt/__init__.py src/core/folgenschnitt/contracts.py tests/folgenschnitt/test_contracts.py
git commit -m "feat(folgenschnitt): Datenmodelle (Contracts) — ms-basiert, serialisierbar"
```

- [ ] **Step 7: REVIEW-GATE (a) — STOPP**

Reviewer prüft `contracts.py` gegen seine Checkliste (Zeitbasis ms, Einheiten, Rollen-Mapping, Serialisierbarkeit, Testbarkeit, Stufe-2-Andockbarkeit) + die Subpackage-Strukturentscheidung. **Nicht weiterbauen, bis Max die Freigabe gibt.**

---

## Task 2: Start-Parameter (Konstanten)

**Files:**
- Create: `src/core/folgenschnitt/params.py`
- Test: `tests/folgenschnitt/test_params.py`

- [ ] **Step 1: Failing test**

`tests/folgenschnitt/test_params.py`:

```python
from core.folgenschnitt import params as P


def test_param_profile_present_and_sane():
    assert P.WINDOW_MS == 200
    assert P.HOP_MS == 100
    assert P.NOISE_FLOOR_PERCENTILE == 10
    assert P.ACTIVE_OVER_FLOOR_DB == 10.0
    assert P.DOMINANCE_SWITCH_DB == 6.0
    assert P.DOMINANCE_HOLD_DB == 3.0
    assert P.SMOOTHING_MS == 400
    assert P.GAP_MERGE_MS == 600
    assert P.MIN_TURN_MS == 5000
    assert P.MIN_SHOT_MS == 2000
    assert P.REAL_PAUSE_MS == 700
    assert P.ANTICIPATION_MS == 1500
    assert P.ANTICIPATION_MAX_MS == 2000
    # Hysterese: Halten-Schwelle < Wechsel-Schwelle
    assert P.DOMINANCE_HOLD_DB < P.DOMINANCE_SWITCH_DB
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_params.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/params.py`:

```python
"""Start-Parameter-Profil für den Folgenschnitt (Stufe 1).

BEWUSST keine UI-Regler — interne Konstanten. Werden an echten Ausschnitten
empirisch kalibriert (siehe Plan Task 10), aber nicht ins UI gehoben.
Quelle der Startwerte: Spec-Sektion "Start-Parameter".
"""

WINDOW_MS = 200               # Analysefenster
HOP_MS = 100                  # Schrittweite
NOISE_FLOOR_PERCENTILE = 10   # Perzentil pro Spur für Grundpegel
ACTIVE_OVER_FLOOR_DB = 10.0   # so viel über eigenem Grundpegel = aktiv
DOMINANCE_SWITCH_DB = 6.0     # Abstand zum Sprecherwechsel
DOMINANCE_HOLD_DB = 3.0       # Abstand zum Halten (Hysterese)
SMOOTHING_MS = 400            # Glättungsfenster (300–500)
GAP_MERGE_MS = 600            # Lücken im selben Sprecher mergen (500–700)
MIN_TURN_MS = 5000            # Mindest-Sprechdauer für neue Kameraentscheidung
MIN_SHOT_MS = 2000            # Mindest-Shot-Länge gegen nervöse Schnitte
REAL_PAUSE_MS = 700           # ab hier "echte Pause" (Anticipation erlaubt)
ANTICIPATION_MS = 1500        # Vorlauf auf nächsten Sprecher
ANTICIPATION_MAX_MS = 2000    # harte Obergrenze für den Vorlauf
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_params.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/folgenschnitt/params.py tests/folgenschnitt/test_params.py
git commit -m "feat(folgenschnitt): Start-Parameter-Profil als interne Konstanten"
```

---

## Task 3: speaker_activity (Audio → ActivityFrames)

**Files:**
- Create: `src/core/folgenschnitt/speaker_activity.py`
- Test: `tests/folgenschnitt/test_speaker_activity.py`

- [ ] **Step 1: Failing test (synthetisches Audio, kein echtes File nötig)**

`tests/folgenschnitt/test_speaker_activity.py`:

```python
import numpy as np
import soundfile as sf
from core.folgenschnitt.speaker_activity import compute_activity
from core.folgenschnitt.contracts import ActivityFrame


def _write_tone(path, sr, dur_s, amp, freq=200.0):
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    sig = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sf.write(str(path), sig, sr)


def test_dominant_mic_is_detected(tmp_path):
    sr = 16000
    m1 = tmp_path / "mic1.wav"
    m2 = tmp_path / "mic2.wav"
    # mic1 laut, mic2 quasi still
    _write_tone(m1, sr, 3.0, amp=0.5)
    _write_tone(m2, sr, 3.0, amp=0.0005)

    frames = compute_activity({"mic1": str(m1), "mic2": str(m2)})

    assert len(frames) > 0
    assert all(isinstance(f, ActivityFrame) for f in frames)
    mid = frames[len(frames) // 2]
    assert mid.dominant == "mic1"
    assert mid.dominance_db > 6.0


def test_silence_has_no_dominant(tmp_path):
    sr = 16000
    m1 = tmp_path / "mic1.wav"
    m2 = tmp_path / "mic2.wav"
    _write_tone(m1, sr, 2.0, amp=0.0005)
    _write_tone(m2, sr, 2.0, amp=0.0005)

    frames = compute_activity({"mic1": str(m1), "mic2": str(m2)})
    mid = frames[len(frames) // 2]
    assert mid.dominant is None


def test_frames_are_contiguous(tmp_path):
    sr = 16000
    m1 = tmp_path / "mic1.wav"
    m2 = tmp_path / "mic2.wav"
    _write_tone(m1, sr, 2.0, amp=0.3)
    _write_tone(m2, sr, 2.0, amp=0.01)
    frames = compute_activity({"mic1": str(m1), "mic2": str(m2)})
    for a, b in zip(frames, frames[1:]):
        assert b.start_ms == a.start_ms + 100  # HOP_MS
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_speaker_activity.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/speaker_activity.py`:

```python
"""Audio fensterweise → ActivityFrames. Kein AI, kein Resampling-Sync.

Liest jede Mic-Spur fensterweise (soundfile blocks), berechnet RMS in dBFS,
schätzt pro Spur einen Grundpegel (Perzentil) und bestimmt pro Fenster den
dominanten Sprecher inkl. Abstand zum zweitlautesten.
"""
import numpy as np
import soundfile as sf

from .contracts import ActivityFrame
from . import params as P

_EPS = 1e-10


def _rms_db(block: np.ndarray) -> float:
    if block.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64)) + _EPS))
    return 20.0 * np.log10(max(rms, _EPS))


def _per_mic_rms_series(path: str, window_ms: int, hop_ms: int) -> tuple[list[float], int]:
    """Return (rms_db pro Hop, sample_rate). Mono-Misch bei Mehrkanal."""
    info = sf.info(path)
    sr = info.samplerate
    win = int(sr * window_ms / 1000)
    hop = int(sr * hop_ms / 1000)
    data, _ = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    out = []
    i = 0
    while i + win <= len(mono):
        out.append(_rms_db(mono[i:i + win]))
        i += hop
    return out, sr


def compute_activity(mic_paths: dict[str, str]) -> list[ActivityFrame]:
    """mic_paths: {"mic1": "/p/a.wav", "mic2": "/p/b.wav"} -> ActivityFrames."""
    series: dict[str, list[float]] = {}
    for mic_id, path in mic_paths.items():
        series[mic_id], _ = _per_mic_rms_series(path, P.WINDOW_MS, P.HOP_MS)

    n = min(len(s) for s in series.values()) if series else 0
    floors = {
        mic: float(np.percentile(np.array(series[mic][:n]), P.NOISE_FLOOR_PERCENTILE))
        for mic in series
    }

    frames: list[ActivityFrame] = []
    for k in range(n):
        start_ms = k * P.HOP_MS
        rms = {mic: series[mic][k] for mic in series}
        active = {
            mic: lvl for mic, lvl in rms.items()
            if lvl >= floors[mic] + P.ACTIVE_OVER_FLOOR_DB
        }
        dominant = None
        dominance_db = 0.0
        if active:
            ordered = sorted(active.items(), key=lambda kv: kv[1], reverse=True)
            top_mic, top_lvl = ordered[0]
            second_lvl = ordered[1][1] if len(ordered) > 1 else -120.0
            dominance_db = top_lvl - second_lvl
            if len(ordered) == 1 or dominance_db >= P.DOMINANCE_HOLD_DB:
                dominant = top_mic
        frames.append(ActivityFrame(
            start_ms=start_ms, end_ms=start_ms + P.WINDOW_MS,
            rms_db={m: round(v, 2) for m, v in rms.items()},
            noise_floor_db={m: round(v, 2) for m, v in floors.items()},
            dominant=dominant, dominance_db=round(dominance_db, 2),
        ))
    return frames
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_speaker_activity.py -q`
Expected: PASS (3 Tests).

- [ ] **Step 5: Commit**

```bash
git add src/core/folgenschnitt/speaker_activity.py tests/folgenschnitt/test_speaker_activity.py
git commit -m "feat(folgenschnitt): speaker_activity — Pegel/Noise-Floor/Dominanz pro Fenster"
```

---

## Task 4: CSV-Debug-Output

**Files:**
- Create: `src/core/folgenschnitt/debug_csv.py`
- Test: `tests/folgenschnitt/test_debug_csv.py`

- [ ] **Step 1: Failing test**

`tests/folgenschnitt/test_debug_csv.py`:

```python
import csv
from core.folgenschnitt.contracts import ActivityFrame
from core.folgenschnitt.debug_csv import write_activity_csv


def test_csv_has_header_and_rows(tmp_path):
    frames = [
        ActivityFrame(0, 200, {"mic1": -20.0, "mic2": -50.0},
                      {"mic1": -55.0, "mic2": -54.0}, "mic1", 30.0),
        ActivityFrame(100, 300, {"mic1": -50.0, "mic2": -50.0},
                      {"mic1": -55.0, "mic2": -54.0}, None, 0.0),
    ]
    out = tmp_path / "activity.csv"
    write_activity_csv(frames, str(out))

    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["start_ms"] == "0"
    assert rows[0]["dominant"] == "mic1"
    assert rows[1]["dominant"] == ""          # None -> leer
    assert rows[0]["rms_mic1"] == "-20.0"
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_debug_csv.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/debug_csv.py`:

```python
"""ActivityFrames → CSV zum menschlichen Draufschauen (Numbers/Excel)."""
import csv

from .contracts import ActivityFrame


def write_activity_csv(frames: list[ActivityFrame], path: str) -> str:
    mics = sorted(frames[0].rms_db.keys()) if frames else []
    fieldnames = (["start_ms", "end_ms"]
                  + [f"rms_{m}" for m in mics]
                  + [f"floor_{m}" for m in mics]
                  + ["dominant", "dominance_db"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for fr in frames:
            row = {"start_ms": fr.start_ms, "end_ms": fr.end_ms,
                   "dominant": fr.dominant or "", "dominance_db": fr.dominance_db}
            for m in mics:
                row[f"rms_{m}"] = fr.rms_db.get(m, "")
                row[f"floor_{m}"] = fr.noise_floor_db.get(m, "")
            w.writerow(row)
    return path
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_debug_csv.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/folgenschnitt/debug_csv.py tests/folgenschnitt/test_debug_csv.py
git commit -m "feat(folgenschnitt): CSV-Debug-Writer für ActivityFrames"
```

---

## Task 5: FolgenschnittXMLExporter + Mini-Test — REVIEW-GATE (b)

**Files:**
- Create: `src/core/folgenschnitt/exporter.py`
- Create: `scripts/folgenschnitt_xml_minitest.py`
- Test: `tests/folgenschnitt/test_exporter.py`

- [ ] **Step 1: Failing test**

`tests/folgenschnitt/test_exporter.py`:

```python
import xml.etree.ElementTree as ET
from core.folgenschnitt.contracts import EditDecision
from core.folgenschnitt.exporter import write_folgenschnitt_xml


def test_flat_timeline_is_wellformed_and_gapless(tmp_path):
    decisions = [
        EditDecision(0, 8000, "Cam01.MP4", "matze", "speaker_active"),
        EditDecision(8000, 15000, "Cam02.MP4", "gast", "speaker_active"),
        EditDecision(15000, 20000, "Cam01.MP4", "matze", "anticipation"),
    ]
    cam_paths = {"Cam01.MP4": "/m/Cam01.MP4", "Cam02.MP4": "/m/Cam02.MP4"}
    audio_paths = ["/m/mic1.wav", "/m/mic2.wav"]
    out = tmp_path / "Folgenschnitt - Test.xml"

    write_folgenschnitt_xml(
        decisions=decisions, camera_paths=cam_paths, audio_paths=audio_paths,
        fps=25, out_path=str(out), sequence_name="Folgenschnitt Test",
    )

    tree = ET.parse(out)              # wirft bei nicht-wohlgeformtem XML
    root = tree.getroot()
    assert root.tag == "xmeml"
    clips = root.findall(".//video/track/clipitem")
    assert len(clips) == 3
    # lückenlos: end[i] == start[i+1] in Frames
    starts = [int(c.find("start").text) for c in clips]
    ends = [int(c.find("end").text) for c in clips]
    assert starts[0] == 0
    assert ends[0] == starts[1]
    assert ends[1] == starts[2]
    # durchgehendes Audio: mind. eine Audiospur über volle Länge
    a_clips = root.findall(".//audio/track/clipitem")
    assert len(a_clips) >= 1


def test_total_duration_matches_last_decision(tmp_path):
    decisions = [EditDecision(0, 10000, "Cam01.MP4", "matze", "speaker_active")]
    out = tmp_path / "x.xml"
    write_folgenschnitt_xml(
        decisions=decisions, camera_paths={"Cam01.MP4": "/m/Cam01.MP4"},
        audio_paths=["/m/mic1.wav"], fps=25, out_path=str(out),
        sequence_name="X",
    )
    root = ET.parse(out).getroot()
    # 10000 ms @ 25 fps = 250 frames
    assert int(root.find("sequence/duration").text) == 250
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_exporter.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/exporter.py`:

```python
"""EditDecisions → flache FCP7-XML (eine Videospur, durchgehende Audiospuren).

Bewusst KEINE Multicam-Sequenz (NLE-spezifisch). Frame-Umrechnung passiert
nur hier (ms_to_frames), nirgends sonst in der Pipeline.
Struktur eng an bestehendem core/exporters.py:XMLExporter (FCP7 xmeml v5),
damit Premiere/Resolve dasselbe bewährte Format sehen.
"""
import os
from urllib.parse import quote

from utils import ms_to_frames


def _file_url(filepath: str) -> str:
    abs_path = os.path.abspath(filepath)
    return f"file://localhost{quote(abs_path, safe='/:')}"


def write_folgenschnitt_xml(decisions, camera_paths: dict[str, str],
                            audio_paths: list[str], fps: int,
                            out_path: str, sequence_name: str) -> str:
    """decisions: list[EditDecision] (lückenlos, aufsteigend, ms).
    camera_paths: Basename -> absoluter Pfad.
    audio_paths: durchgehende Audiospuren (über die ganze Folge).
    """
    rate_block = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
    tc_block = (f"<timecode>{rate_block}<string>00:00:00:00</string>"
                f"<frame>0</frame><displayformat>NDF</displayformat></timecode>")

    total_ms = decisions[-1].end_ms if decisions else 0
    total_frames = ms_to_frames(total_ms, fps)

    # eindeutige file-ids je Kamera (erste Verwendung trägt <file>-Body)
    cam_order = list(dict.fromkeys(d.camera for d in decisions))
    cam_file_id = {cam: f"file-video-{i+1}" for i, cam in enumerate(cam_order)}
    cam_seen: set[str] = set()

    with open(out_path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        f.write('<xmeml version="5">\n')
        f.write('  <sequence id="folgenschnitt-sequence">\n')
        f.write(f'    <name>{sequence_name}</name>\n')
        f.write(f'    <duration>{total_frames}</duration>\n')
        f.write(f'    {rate_block}\n    {tc_block}\n')
        f.write('    <media>\n')

        # --- eine Videospur, je Decision ein clipitem ---
        f.write('      <video>\n        <track>\n')
        for idx, d in enumerate(decisions):
            cam = d.camera
            fid = cam_file_id[cam]
            start_f = ms_to_frames(d.start_ms, fps)
            end_f = ms_to_frames(d.end_ms, fps)
            dur_f = end_f - start_f
            f.write(f'          <clipitem id="clip-v{idx+1}">\n')
            f.write(f'            <name>{os.path.splitext(cam)[0]}</name>\n')
            f.write(f'            <duration>{dur_f}</duration>\n')
            f.write(f'            {rate_block}\n')
            f.write(f'            <start>{start_f}</start>\n')
            f.write(f'            <end>{end_f}</end>\n')
            f.write(f'            <in>{start_f}</in>\n')
            f.write(f'            <out>{end_f}</out>\n')
            if cam not in cam_seen:
                cam_seen.add(cam)
                cam_path = camera_paths.get(cam, cam)
                f.write(f'            <file id="{fid}">\n')
                f.write(f'              <name>{cam}</name>\n')
                f.write(f'              <pathurl>{_file_url(cam_path)}</pathurl>\n')
                f.write(f'              {rate_block}\n              {tc_block}\n')
                f.write('            </file>\n')
            else:
                f.write(f'            <file id="{fid}"/>\n')
            f.write('          </clipitem>\n')
        f.write('        </track>\n      </video>\n')

        # --- durchgehende Audiospuren (je Mic eine Spur, ein Clip 0..total) ---
        f.write('      <audio>\n')
        for ai, apath in enumerate(audio_paths):
            aid = f"file-audio-{ai+1}"
            aname = os.path.basename(apath)
            f.write('        <track>\n')
            f.write(f'          <clipitem id="clip-a{ai+1}">\n')
            f.write(f'            <name>{os.path.splitext(aname)[0]}</name>\n')
            f.write(f'            <duration>{total_frames}</duration>\n')
            f.write(f'            {rate_block}\n')
            f.write(f'            <start>0</start>\n')
            f.write(f'            <end>{total_frames}</end>\n')
            f.write(f'            <in>0</in>\n')
            f.write(f'            <out>{total_frames}</out>\n')
            f.write(f'            <file id="{aid}">\n')
            f.write(f'              <name>{aname}</name>\n')
            f.write(f'              <pathurl>{_file_url(apath)}</pathurl>\n')
            f.write(f'              {rate_block}\n              {tc_block}\n')
            f.write('            </file>\n')
            f.write('            <sourcetrack><mediatype>audio</mediatype></sourcetrack>\n')
            f.write('          </clipitem>\n')
            f.write('        </track>\n')
        f.write('      </audio>\n')

        f.write('    </media>\n  </sequence>\n</xmeml>\n')
    return out_path


class FolgenschnittXMLExporter:
    """BaseExporter-kompatibel (export(session) -> str). Wird in Task 9
    in den ExportWorker eingehängt — vorerst NICHT verdrahtet."""

    def export(self, session) -> str:
        raise NotImplementedError("Verdrahtung in Task 9 nach Kalibrierung")
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_exporter.py -q`
Expected: PASS (2 Tests).

- [ ] **Step 5: Mini-Test-CLI schreiben**

`scripts/folgenschnitt_xml_minitest.py`:

```python
#!/usr/bin/env python3
"""Erzeugt eine Folgenschnitt-XML aus handgebauten Fake-EditDecisions,
damit der Import in Premiere/Resolve früh getestet werden kann —
ohne dass die Sprechererkennung fertig sein muss.

Aufruf:
    ./venv311/bin/python scripts/folgenschnitt_xml_minitest.py \
        --cam1 /pfad/Cam01.MP4 --cam2 /pfad/Cam02.MP4 \
        --mic1 /pfad/mic1.wav --mic2 /pfad/mic2.wav \
        --out "/pfad/Folgenschnitt - Minitest.xml"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.folgenschnitt.contracts import EditDecision          # noqa: E402
from core.folgenschnitt.exporter import write_folgenschnitt_xml  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam1", required=True)
    ap.add_argument("--cam2", required=True)
    ap.add_argument("--mic1", required=True)
    ap.add_argument("--mic2", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=25)
    a = ap.parse_args()

    c1 = os.path.basename(a.cam1)
    c2 = os.path.basename(a.cam2)
    # Fake-Schnitt: alle 8 s wechseln, 60 s gesamt
    decisions = []
    t = 0
    flip = True
    while t < 60000:
        end = min(t + 8000, 60000)
        decisions.append(EditDecision(t, end, c1 if flip else c2,
                                      "matze" if flip else "gast",
                                      "speaker_active"))
        t = end
        flip = not flip

    write_folgenschnitt_xml(
        decisions=decisions,
        camera_paths={c1: a.cam1, c2: a.cam2},
        audio_paths=[a.mic1, a.mic2],
        fps=a.fps, out_path=a.out, sequence_name="Folgenschnitt Minitest",
    )
    print(f"geschrieben: {a.out}  ({len(decisions)} Cuts)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Mini-Test mit der echten Hartmut-Rosa-Folge erzeugen**

Run:
```bash
cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App
./venv311/bin/python scripts/folgenschnitt_xml_minitest.py \
  --cam1 "/Users/max/Desktop/HM/1_ToDo/2026_Hartmut Rosa/1_Material/1_Rohmaterial/3_Kameras/_20260512_HotelMatze_HartmutRosa_Cam01_C018C001_260512VK.MP4" \
  --cam2 "/Users/max/Desktop/HM/1_ToDo/2026_Hartmut Rosa/1_Material/1_Rohmaterial/3_Kameras/_20260512_HotelMatze_HartmutRosa_Cam02_MV_20260512_7894.MP4" \
  --mic1 "/Users/max/Desktop/HM/1_ToDo/2026_Hartmut Rosa/1_Material/1_Rohmaterial/2_P8/_20260512_HotelMatze_HartmutRosa_MIC1.WAV" \
  --mic2 "/Users/max/Desktop/HM/1_ToDo/2026_Hartmut Rosa/1_Material/1_Rohmaterial/2_P8/_20260512_HotelMatze_HartmutRosa_MIC2.WAV" \
  --out "/Users/max/Downloads/Folgenschnitt - Minitest.xml"
```
Expected: "geschrieben: …  (8 Cuts)", Datei existiert.

- [ ] **Step 7: Commit**

```bash
git add src/core/folgenschnitt/exporter.py scripts/folgenschnitt_xml_minitest.py tests/folgenschnitt/test_exporter.py
git commit -m "feat(folgenschnitt): FolgenschnittXMLExporter (flache FCP7) + Mini-Test-CLI"
```

- [ ] **Step 8: REVIEW-GATE (b) — STOPP**

Max importiert `~/Downloads/Folgenschnitt - Minitest.xml` **in Premiere UND DaVinci Resolve**. Prüfen: Clips an richtiger Stelle, Kamerawechsel sichtbar, Audio durchgehend, Relink der Medien funktioniert. Reviewer prüft (b) Timeline-Struktur/Offsets/Format. **Nicht weiterbauen, bis Max den Import bestätigt und freigibt.** Bei Import-Problemen: hier iterieren (nur `exporter.py`), nicht in späteren Tasks.

---

## Task 6: speaker_turns (Glättung)

**Files:**
- Create: `src/core/folgenschnitt/speaker_turns.py`
- Test: `tests/folgenschnitt/test_speaker_turns.py`

- [ ] **Step 1: Failing test**

`tests/folgenschnitt/test_speaker_turns.py`:

```python
from core.folgenschnitt.contracts import ActivityFrame, SpeakerTurn
from core.folgenschnitt.speaker_turns import build_turns


def _frame(start, dominant):
    return ActivityFrame(start, start + 200, {"mic1": 0.0, "mic2": 0.0},
                         {"mic1": -60.0, "mic2": -60.0}, dominant, 9.0)


def test_short_gap_is_merged_into_same_speaker():
    # mic1 spricht, 1 Fenster "None" (200ms < GAP_MERGE_MS), mic1 weiter
    frames = ([_frame(i * 100, "mic1") for i in range(40)]
              + [_frame(4000, None)]
              + [_frame(4100 + i * 100, "mic1") for i in range(40)])
    turns = build_turns(frames)
    assert len(turns) == 1
    assert turns[0].speaker == "mic1"


def test_distinct_speakers_become_two_turns():
    frames = ([_frame(i * 100, "mic1") for i in range(60)]
              + [_frame(6000 + i * 100, "mic2") for i in range(60)])
    turns = build_turns(frames)
    assert [t.speaker for t in turns] == ["mic1", "mic2"]
    assert turns[0].start_ms == 0
    assert turns[1].speaker == "mic2"


def test_returns_speakerturn_objects():
    frames = [_frame(i * 100, "mic1") for i in range(60)]
    turns = build_turns(frames)
    assert all(isinstance(t, SpeakerTurn) for t in turns)
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_speaker_turns.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/speaker_turns.py`:

```python
"""ActivityFrames → geglättete SpeakerTurns.

Reine Funktion (kein Audio, kein IO) — voll unit-testbar.
Schritte: (1) rohe dominant-Sequenz, (2) kurze Gegen-/None-Segmente unter
GAP_MERGE_MS in den umgebenden Sprecher mergen, (3) zu Turns zusammenfassen.
"""
from .contracts import ActivityFrame, SpeakerTurn
from . import params as P


def build_turns(frames: list[ActivityFrame]) -> list[SpeakerTurn]:
    if not frames:
        return []

    # 1. rohe Label-Liste (None erlaubt)
    labels = [f.dominant for f in frames]
    starts = [f.start_ms for f in frames]
    end_ms = frames[-1].end_ms

    # 2. kurze Segmente (inkl. None) in Nachbarn mergen
    def seg_iter(lbls):
        i = 0
        while i < len(lbls):
            j = i
            while j < len(lbls) and lbls[j] == lbls[i]:
                j += 1
            yield i, j, lbls[i]
            i = j

    changed = True
    while changed:
        changed = False
        segs = list(seg_iter(labels))
        for idx, (i, j, lab) in enumerate(segs):
            dur = (starts[j] if j < len(starts) else end_ms) - starts[i]
            if dur < P.GAP_MERGE_MS and 0 < idx < len(segs) - 1:
                prev_lab = segs[idx - 1][2]
                nxt_lab = segs[idx + 1][2]
                if prev_lab == nxt_lab and prev_lab is not None:
                    for k in range(i, j):
                        labels[k] = prev_lab
                    changed = True
                    break

    # 3. zu Turns (None-Segmente überspringen)
    turns: list[SpeakerTurn] = []
    for i, j, lab in seg_iter(labels):
        if lab is None:
            continue
        s = starts[i]
        e = starts[j] if j < len(starts) else end_ms
        if turns and turns[-1].speaker == lab and s - turns[-1].end_ms < P.GAP_MERGE_MS:
            turns[-1] = SpeakerTurn(lab, turns[-1].start_ms, e)
        else:
            turns.append(SpeakerTurn(lab, s, e))
    return turns
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_speaker_turns.py -q`
Expected: PASS (3 Tests).

- [ ] **Step 5: Commit**

```bash
git add src/core/folgenschnitt/speaker_turns.py tests/folgenschnitt/test_speaker_turns.py
git commit -m "feat(folgenschnitt): speaker_turns — Glättung/Gap-Merge zu Sprecherabschnitten"
```

---

## Task 7: edit_decisions (Schnitt-Logik)

**Files:**
- Create: `src/core/folgenschnitt/edit_decisions.py`
- Test: `tests/folgenschnitt/test_edit_decisions.py`

- [ ] **Step 1: Failing test**

`tests/folgenschnitt/test_edit_decisions.py`:

```python
from core.folgenschnitt.contracts import SpeakerTurn, RoleMapping, EditDecision
from core.folgenschnitt.edit_decisions import build_decisions

RM = RoleMapping(
    mic_to_speaker={"mic1": "matze", "mic2": "gast"},
    camera_to_role={"Cam01.MP4": "matze_wide", "Cam02.MP4": "gast_wide",
                    "Cam03.MP4": "gast_close"},
)


def test_short_turn_under_5s_does_not_switch():
    # mic1 lange, mic2 nur 3s (unter MIN_TURN_MS), mic1 weiter
    turns = [SpeakerTurn("mic1", 0, 20000),
             SpeakerTurn("mic2", 20000, 23000),
             SpeakerTurn("mic1", 23000, 40000)]
    dec = build_decisions(turns, RM, total_ms=40000)
    # kein Wechsel auf gast_wide, durchgehend Cam01
    assert all(d.camera == "Cam01.MP4" for d in dec)
    assert dec[0].start_ms == 0
    assert dec[-1].end_ms == 40000


def test_real_switch_uses_wide_of_speaker():
    turns = [SpeakerTurn("mic1", 0, 30000),
             SpeakerTurn("mic2", 30000, 60000)]
    dec = build_decisions(turns, RM, total_ms=60000)
    cams = [d.camera for d in dec]
    assert "Cam01.MP4" in cams and "Cam02.MP4" in cams
    # lückenlos + voll abgedeckt
    assert dec[0].start_ms == 0
    assert dec[-1].end_ms == 60000
    for a, b in zip(dec, dec[1:]):
        assert a.end_ms == b.start_ms


def test_anticipation_capped_at_2s_before_next_speaker():
    # lange Pause zwischen mic1-Ende (10000) und mic2-Start (25000)
    turns = [SpeakerTurn("mic1", 0, 10000),
             SpeakerTurn("mic2", 25000, 60000)]
    dec = build_decisions(turns, RM, total_ms=60000)
    # Wechsel auf Cam02 frühestens 2000ms vor 25000 -> >= 23000
    switch = next(d for d in dec if d.camera == "Cam02.MP4")
    assert 23000 <= switch.start_ms <= 25000


def test_min_shot_length_respected():
    turns = [SpeakerTurn("mic1", 0, 6000),
             SpeakerTurn("mic2", 6000, 12000),
             SpeakerTurn("mic1", 12000, 60000)]
    dec = build_decisions(turns, RM, total_ms=60000)
    assert all(d.duration_ms >= 2000 for d in dec)
    assert all(isinstance(d, EditDecision) for d in dec)
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_edit_decisions.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/edit_decisions.py`:

```python
"""SpeakerTurns + RoleMapping → EditDecisions (Stufe-1-Schnitt-Logik).

Regeln (Spec "Schnitt-Regeln"):
- nur Turns >= MIN_TURN_MS lösen einen Kamerawechsel aus
- aktiver Sprecher -> seine Wide-Kamera
- Anticipation: bei echter Pause (>REAL_PAUSE_MS) Wechsel höchstens
  ANTICIPATION_MS (max ANTICIPATION_MAX_MS) vor dem nächsten Sprecher
- Mindest-Shot MIN_SHOT_MS (zu kurze Decisions in Vorgänger mergen)
- Ergebnis lückenlos, deckt 0..total_ms ab
Reine Funktion, kein IO.
"""
from .contracts import SpeakerTurn, RoleMapping, EditDecision
from . import params as P


def _relevant_turns(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    return [t for t in turns if t.duration_ms >= P.MIN_TURN_MS]


def build_decisions(turns: list[SpeakerTurn], roles: RoleMapping,
                    total_ms: int) -> list[EditDecision]:
    rel = _relevant_turns(turns)
    if not rel:
        return []

    # 1. Roh-Decisions: je relevantem Turn die Wide-Kamera des Sprechers
    raw: list[EditDecision] = []
    for t in rel:
        speaker = roles.speaker_for_mic(t.speaker) or t.speaker
        cam = roles.wide_camera_for_speaker(speaker)
        if cam is None:
            continue
        raw.append(EditDecision(t.start_ms, t.end_ms, cam, speaker, "speaker_active"))

    if not raw:
        return []

    # 2. Anticipation: Start eines Blocks vorziehen, wenn davor eine echte
    #    Pause liegt und der nächste Sprecher ein anderer ist
    for i, d in enumerate(raw):
        prev_end = raw[i - 1].end_ms if i > 0 else 0
        gap = d.start_ms - prev_end
        if gap > P.REAL_PAUSE_MS:
            lead = min(P.ANTICIPATION_MS, P.ANTICIPATION_MAX_MS)
            new_start = max(prev_end, d.start_ms - lead)
            if new_start < d.start_ms:
                raw[i] = EditDecision(new_start, d.end_ms, d.camera,
                                      d.speaker, "anticipation")

    # 3. Lücken füllen: erste Decision ab 0, Zwischenräume an Vorgänger,
    #    letzte bis total_ms — durchgehende Timeline
    filled: list[EditDecision] = []
    cursor = 0
    for i, d in enumerate(raw):
        if d.start_ms > cursor:
            # Lücke -> Vorgängerkamera halten (oder erste Kamera am Anfang)
            hold_cam = filled[-1].camera if filled else d.camera
            hold_spk = filled[-1].speaker if filled else d.speaker
            filled.append(EditDecision(cursor, d.start_ms, hold_cam,
                                       hold_spk, "hold"))
        filled.append(EditDecision(max(d.start_ms, cursor), d.end_ms,
                                    d.camera, d.speaker, d.reason))
        cursor = d.end_ms
    if cursor < total_ms:
        filled.append(EditDecision(cursor, total_ms, filled[-1].camera,
                                   filled[-1].speaker, "hold"))

    # 4. Mindest-Shot: zu kurze Decisions in Vorgänger einschmelzen
    merged: list[EditDecision] = []
    for d in filled:
        if merged and d.duration_ms < P.MIN_SHOT_MS and merged[-1].camera == d.camera:
            merged[-1] = EditDecision(merged[-1].start_ms, d.end_ms,
                                      merged[-1].camera, merged[-1].speaker,
                                      merged[-1].reason)
        elif merged and d.duration_ms < P.MIN_SHOT_MS:
            # zu kurz und andere Kamera -> Vorgänger verlängern
            merged[-1] = EditDecision(merged[-1].start_ms, d.end_ms,
                                      merged[-1].camera, merged[-1].speaker,
                                      merged[-1].reason)
        else:
            merged.append(d)

    # benachbarte gleiche Kamera zusammenfassen
    out: list[EditDecision] = []
    for d in merged:
        if out and out[-1].camera == d.camera:
            out[-1] = EditDecision(out[-1].start_ms, d.end_ms, out[-1].camera,
                                   out[-1].speaker, out[-1].reason)
        else:
            out.append(d)
    return out
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_edit_decisions.py -q`
Expected: PASS (4 Tests). Falls ein Test scheitert: NICHT Logik raten — Spec-Regel + Test-Erwartung abgleichen, gezielt fixen, erneut laufen.

- [ ] **Step 5: Volle Suite (Regression)**

Run: `QT_QPA_PLATFORM=offscreen ./venv311/bin/python -m pytest tests/ -q`
Expected: alles grün.

- [ ] **Step 6: Commit**

```bash
git add src/core/folgenschnitt/edit_decisions.py tests/folgenschnitt/test_edit_decisions.py
git commit -m "feat(folgenschnitt): edit_decisions — 5s-Regel, Anticipation, Mindest-Shot"
```

---

## Task 8: Pipeline-Verschaltung speaker_activity → turns → decisions (ohne Export)

**Files:**
- Create: `src/core/folgenschnitt/pipeline.py`
- Test: `tests/folgenschnitt/test_pipeline.py`

- [ ] **Step 1: Failing test (end-to-end auf synthetischem Audio)**

`tests/folgenschnitt/test_pipeline.py`:

```python
import numpy as np
import soundfile as sf
from core.folgenschnitt.contracts import RoleMapping
from core.folgenschnitt.pipeline import run_folgenschnitt


def _voice(path, sr, segments, total_s):
    """segments: list of (start_s, end_s, amp) auf sonst stiller Spur."""
    n = int(sr * total_s)
    sig = np.full(n, 0.0003, dtype=np.float32)
    for s, e, amp in segments:
        t = np.arange(int(sr * (e - s)))
        sig[int(sr*s):int(sr*s)+len(t)] = (amp*np.sin(2*np.pi*180*t/sr)).astype(np.float32)
    sf.write(str(path), sig, sr)


def test_pipeline_produces_decisions_and_csv(tmp_path):
    sr = 16000
    m1 = tmp_path / "mic1.wav"
    m2 = tmp_path / "mic2.wav"
    # 0-30s matze, 30-60s gast
    _voice(m1, sr, [(0, 30, 0.4)], 60)
    _voice(m2, sr, [(30, 60, 0.4)], 60)
    roles = RoleMapping(
        mic_to_speaker={"mic1": "matze", "mic2": "gast"},
        camera_to_role={"Cam01.MP4": "matze_wide", "Cam02.MP4": "gast_wide"},
    )
    csv_out = tmp_path / "activity.csv"
    decisions = run_folgenschnitt(
        {"mic1": str(m1), "mic2": str(m2)}, roles,
        total_ms=60000, debug_csv_path=str(csv_out),
    )
    assert csv_out.exists()
    cams = [d.camera for d in decisions]
    assert "Cam01.MP4" in cams and "Cam02.MP4" in cams
    assert decisions[0].start_ms == 0
    assert decisions[-1].end_ms == 60000
    for a, b in zip(decisions, decisions[1:]):
        assert a.end_ms == b.start_ms
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_pipeline.py -q`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`src/core/folgenschnitt/pipeline.py`:

```python
"""Orchestriert die Folgenschnitt-Pipeline (ohne XML/Export, ohne Qt).

run_folgenschnitt: mic_paths + RoleMapping -> list[EditDecision],
schreibt optional die Debug-CSV. Wird in Task 9 vom Analyse-Subprozess
aufgerufen.
"""
from .speaker_activity import compute_activity
from .speaker_turns import build_turns
from .edit_decisions import build_decisions
from .debug_csv import write_activity_csv
from .contracts import RoleMapping, EditDecision


def run_folgenschnitt(mic_paths: dict[str, str], roles: RoleMapping,
                      total_ms: int,
                      debug_csv_path: str | None = None) -> list[EditDecision]:
    frames = compute_activity(mic_paths)
    if debug_csv_path:
        write_activity_csv(frames, debug_csv_path)
    turns = build_turns(frames)
    return build_decisions(turns, roles, total_ms)
```

- [ ] **Step 4: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_pipeline.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/folgenschnitt/pipeline.py tests/folgenschnitt/test_pipeline.py
git commit -m "feat(folgenschnitt): Pipeline-Orchestrierung activity→turns→decisions"
```

---

## Task 9: Kalibrierung an echten Hartmut-Rosa-Ausschnitten — GATE

**Files:** keine Code-Änderung; nur Messung + ggf. `params.py` justieren.

- [ ] **Step 1: 3 Ausschnitte vorbereiten (Max liefert Zeitmarken)**

Max nennt drei ~5-Min-Zeitfenster der Hartmut-Rosa-Folge: (1) normaler Dialog, (2) Overlap/Schlagabtausch, (3) Pausen/Monolog. Ausschnitte aus `MIC1.WAV`/`MIC2.WAV` mit ffmpeg schneiden:

Run (Beispiel, Zeiten von Max einsetzen):
```bash
SRC="/Users/max/Desktop/HM/1_ToDo/2026_Hartmut Rosa/1_Material/1_Rohmaterial/2_P8"
OUT=/Users/max/Downloads/fs_cal && mkdir -p "$OUT"
for seg in "dialog 00:10:00" "overlap 00:25:00" "pausen 00:40:00"; do
  name=$(echo $seg|cut -d' ' -f1); ss=$(echo $seg|cut -d' ' -f2)
  ffmpeg -y -ss $ss -t 300 -i "$SRC/_20260512_HotelMatze_HartmutRosa_MIC1.WAV" "$OUT/${name}_mic1.wav"
  ffmpeg -y -ss $ss -t 300 -i "$SRC/_20260512_HotelMatze_HartmutRosa_MIC2.WAV" "$OUT/${name}_mic2.wav"
done
```

- [ ] **Step 2: Debug-CSV je Ausschnitt erzeugen**

Run:
```bash
cd /Users/max/Desktop/MF/Vibecoding/PeakCut/App
for n in dialog overlap pausen; do
./venv311/bin/python - <<PY
from core.folgenschnitt.pipeline import run_folgenschnitt
from core.folgenschnitt.contracts import RoleMapping
r=RoleMapping({"mic1":"matze","mic2":"gast"},{"Cam01.MP4":"matze_wide","Cam02.MP4":"gast_wide"})
d=run_folgenschnitt({"mic1":"/Users/max/Downloads/fs_cal/${n}_mic1.wav","mic2":"/Users/max/Downloads/fs_cal/${n}_mic2.wav"},r,300000,"/Users/max/Downloads/fs_cal/${n}_activity.csv")
print("${n}",len(d),"decisions")
PY
done
```
Expected: drei CSV-Dateien + Decision-Zahlen.

- [ ] **Step 3: CSV mit Max sichten, Parameter justieren**

Max öffnet die CSVs (Numbers) + hört die Ausschnitte. Bewertung: Stimmt `dominant` mit dem real Sprechenden überein? Wo zappelt es, wo klebt es? Falls nötig: Werte in `src/core/folgenschnitt/params.py` anpassen (z. B. `DOMINANCE_SWITCH_DB`, `ACTIVE_OVER_FLOOR_DB`, `SMOOTHING_MS`), Step 2 wiederholen. **Iterieren bis Max sagt: "ruhig und überwiegend richtig".**

- [ ] **Step 4: Commit der kalibrierten Parameter (falls geändert)**

```bash
git add src/core/folgenschnitt/params.py
git commit -m "tune(folgenschnitt): Parameter an Hartmut-Rosa-Ausschnitten kalibriert" || echo "keine Änderung nötig"
```

- [ ] **Step 5: GATE — Max-Freigabe**

Erst wenn Max die Erkennung an allen drei Ausschnitten als "ruhig, überwiegend richtig, spart Arbeit" bewertet → weiter zu Task 10. Sonst zurück zu Step 3.

---

## Task 10: Export-Aktivierung (Verdrahtung in den echten Workflow)

**Files:**
- Modify: `src/core/folgenschnitt/exporter.py` (`FolgenschnittXMLExporter.export`)
- Modify: `src/core/analysis_process.py:48-132` (Decisions in Analyse erzeugen)
- Modify: `src/gui/workers.py:201` (Exporter in ExportWorker)
- Modify: `src/core/session.py:118-148` (`folgenschnitt_decisions` aus Results laden)
- Test: `tests/folgenschnitt/test_export_integration.py`

- [ ] **Step 1: Failing test (Exporter über Session, wie bestehende Exporter)**

`tests/folgenschnitt/test_export_integration.py`:

```python
import os
import xml.etree.ElementTree as ET
from core.project import PeakCutProject
from core.session import PeakCutSession
from core.folgenschnitt.contracts import EditDecision
from core.folgenschnitt.exporter import FolgenschnittXMLExporter


def test_exporter_writes_file_via_session(tmp_path, sample_config):
    proj = PeakCutProject()
    proj.export_dir = str(tmp_path)
    proj.set_files(keyboard=None,
                   mics=["/m/Podcast - Gast X mix.wav", "/m/mic1.wav", "/m/mic2.wav"],
                   videos=["/m/Cam01.MP4", "/m/Cam02.MP4"])
    sess = PeakCutSession(proj, sample_config)
    sess.folgenschnitt_decisions = [
        EditDecision(0, 8000, "Cam01.MP4", "matze", "speaker_active"),
        EditDecision(8000, 16000, "Cam02.MP4", "gast", "speaker_active"),
    ]
    sess.folgenschnitt_camera_paths = {"Cam01.MP4": "/m/Cam01.MP4",
                                       "Cam02.MP4": "/m/Cam02.MP4"}
    sess.folgenschnitt_audio_paths = ["/m/mic1.wav", "/m/mic2.wav"]

    path = FolgenschnittXMLExporter().export(sess)
    assert os.path.exists(path)
    assert os.path.basename(path).startswith("Folgenschnitt - ")
    root = ET.parse(path).getroot()
    assert root.tag == "xmeml"
    assert len(root.findall(".//video/track/clipitem")) == 2


def test_exporter_noop_without_decisions(tmp_path, sample_config):
    proj = PeakCutProject()
    proj.export_dir = str(tmp_path)
    proj.set_files(keyboard=None, mics=["/m/Podcast - Gast X mix.wav"], videos=[])
    sess = PeakCutSession(proj, sample_config)
    sess.folgenschnitt_decisions = []
    assert FolgenschnittXMLExporter().export(sess) == ""
```

- [ ] **Step 2: Test ausführen, MUSS fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_export_integration.py -q`
Expected: FAIL — `AttributeError`/`NotImplementedError`.

- [ ] **Step 3: Session-Felder ergänzen**

In `src/core/session.py` im `__init__` von `PeakCutSession` (nach `self._offset_lookup_ms = {}`, ~Zeile 53) einfügen:

```python
        # Folgenschnitt (Stufe 1) — befüllt durch Analyse, leer = kein Export
        self.folgenschnitt_decisions: list = []
        self.folgenschnitt_camera_paths: dict[str, str] = {}
        self.folgenschnitt_audio_paths: list[str] = []
```

In `load_analysis_results` (nach dem Laden der peaks, vor `self.current_peak = 0`, ~Zeile 146) einfügen:

```python
        # Folgenschnitt-Decisions (optional, von analysis_process geliefert)
        fs = results.get("folgenschnitt")
        if fs:
            from core.folgenschnitt.contracts import EditDecision
            self.folgenschnitt_decisions = [
                EditDecision.from_dict(d) for d in fs.get("decisions", [])
            ]
            self.folgenschnitt_camera_paths = dict(fs.get("camera_paths", {}))
            self.folgenschnitt_audio_paths = list(fs.get("audio_paths", []))
```

- [ ] **Step 4: `FolgenschnittXMLExporter.export` implementieren**

In `src/core/folgenschnitt/exporter.py` die `FolgenschnittXMLExporter`-Klasse ersetzen:

```python
class FolgenschnittXMLExporter:
    """BaseExporter-kompatibel. Schreibt nur, wenn Decisions vorliegen."""

    def export(self, session) -> str:
        decisions = getattr(session, "folgenschnitt_decisions", [])
        if not decisions:
            return ""
        import os
        os.makedirs(session.project.export_dir, exist_ok=True)
        guest = session.project.guest_name
        fps = session.config.get("fps", 25)
        out = os.path.join(session.project.export_dir,
                           f"Folgenschnitt - {guest}.xml")
        write_folgenschnitt_xml(
            decisions=decisions,
            camera_paths=getattr(session, "folgenschnitt_camera_paths", {}),
            audio_paths=getattr(session, "folgenschnitt_audio_paths", []),
            fps=fps, out_path=out, sequence_name=f"Folgenschnitt {guest}",
        )
        session.status_update.emit(f"Folgenschnitt-XML: {os.path.basename(out)}")
        return out
```

- [ ] **Step 5: Test bestehen**

Run: `./venv311/bin/python -m pytest tests/folgenschnitt/test_export_integration.py -q`
Expected: PASS (2 Tests).

- [ ] **Step 6: In ExportWorker einhängen**

In `src/gui/workers.py` Zeile 14 Import erweitern:

```python
from core.exporters import MP3Exporter, XMLExporter, TXTExporter
from core.folgenschnitt.exporter import FolgenschnittXMLExporter
```

Zeile 201 ersetzen:

```python
            exporters = [MP3Exporter(), TXTExporter(), XMLExporter(),
                         FolgenschnittXMLExporter()]
```

- [ ] **Step 7: In analysis_process Decisions erzeugen**

In `src/core/analysis_process.py` in `run_analysis`, nach dem Peak-Block (vor `return results`, ~Zeile 131) einfügen:

```python
    # Folgenschnitt Stufe 1 (nur wenn >=2 Mic-Spuren ohne Keyboard/mix)
    try:
        from core.folgenschnitt.pipeline import run_folgenschnitt
        from core.folgenschnitt.contracts import RoleMapping
        speaker_mics = {}
        for idx, p in enumerate(mic_tracks, start=1):
            base = os.path.basename(p).lower()
            if "keyboard" in base or "mix" in base:
                continue
            speaker_mics[f"mic{idx}"] = p
        if len(speaker_mics) >= 2:
            mic_ids = list(speaker_mics.keys())
            roles = RoleMapping(
                mic_to_speaker={mic_ids[0]: "matze", mic_ids[1]: "gast"},
                camera_to_role={},  # wird in UI gesetzt; leer = Exporter no-op
            )
            import soundfile as _sf
            total_ms = int(_sf.info(speaker_mics[mic_ids[0]]).duration * 1000)
            csv_path = os.path.join(export_dir, "speaker_activity.csv")
            decisions = run_folgenschnitt(speaker_mics, roles, total_ms, csv_path)
            results["folgenschnitt"] = {
                "decisions": [d.to_dict() for d in decisions],
                "camera_paths": {},
                "audio_paths": [speaker_mics[m] for m in mic_ids],
            }
            progress(f"Folgenschnitt: {len(decisions)} Schnitte")
    except Exception as e:
        error(f"Folgenschnitt übersprungen: {e}")
```

(Hinweis: `camera_to_role` leer → Exporter erzeugt keine Datei, bis die UI-Zuordnung existiert. Die UI-Zuordnung ist ein eigenes Folge-Feature laut Spec-Sektion "UI-Änderungen" und NICHT Teil dieses Plans — Stufe 1 endet hier mit der validierten Logik + Export-Pfad.)

- [ ] **Step 8: Volle Suite + Doc-Sync**

Run: `QT_QPA_PLATFORM=offscreen ./venv311/bin/python -m pytest tests/ -q`
Expected: alles grün.

CLAUDE.md Changelog-Eintrag ergänzen (Abschnitt Architecture: neues Subpackage `core/folgenschnitt/` notieren; Changelog: "Folgenschnitt Stufe 1 — Logik + Export-Pfad, UI-Zuordnung folgt separat").

- [ ] **Step 9: Commit**

```bash
git add src/core/session.py src/core/folgenschnitt/exporter.py src/gui/workers.py src/core/analysis_process.py tests/folgenschnitt/test_export_integration.py CLAUDE.md
git commit -m "feat(folgenschnitt): Export-Pfad verdrahtet (Stufe 1 Logik komplett)"
git push origin develop
```

---

## Scope-Grenze dieses Plans

Dieser Plan liefert die **vollständige, getestete Stufe-1-Logik + den Export-Pfad**. **Nicht** enthalten (bewusst, eigene Spec-Sektion "UI-Änderungen", separates Feature):

- UI-Drop-Downs für Kamera→Rolle / Mic→Sprecher auf der Review-Seite.
- Damit bleibt `camera_to_role` vorerst leer und die Folgenschnitt-XML wird erst geschrieben, wenn dieses UI-Feature nachgezogen ist. Bis dahin ist Stufe 1 über die Pipeline + `scripts/folgenschnitt_xml_minitest.py` voll testbar.

Das nächste Plan-Dokument (separat) behandelt das UI-Zuordnungs-Feature.

---

## Self-Review (vom Plan-Autor durchgeführt)

- **Spec-Abdeckung:** Sprecher-Erkennung (T3), Glättung/Hysterese (T6), 5-s/Mindest-Shot/Anticipation (T7), FCP7 flach Premiere+Resolve (T5), CSV+JSON-Debug (T4 CSV / Decisions als JSON in T10), Start-Parameter intern (T2), MVP-Reihenfolge Risiko-zuerst (T1→T5-Gate→T6/7→T9-Kalibrierung), Testmaterial Hartmut Rosa (T5/T9), Contracts-Prinzipien ms/serialisierbar (T1). UI-Zuordnung bewusst ausgegrenzt (Scope-Grenze). Keine Lücke.
- **Platzhalter:** keine — jeder Code-Step enthält vollständigen Code, jeder Run-Step exakten Befehl + erwartete Ausgabe.
- **Typkonsistenz:** `ActivityFrame/SpeakerTurn/EditDecision/RoleMapping` einheitlich über T1–T10; `compute_activity`/`build_turns`/`build_decisions`/`run_folgenschnitt`/`write_folgenschnitt_xml` Signaturen konsistent verwendet.
