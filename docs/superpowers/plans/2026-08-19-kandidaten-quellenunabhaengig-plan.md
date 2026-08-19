# Stellen quellenunabhängig machen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `session.clip_candidates` wird die allgemeine Stellen-Liste mit eigener Identität und Herkunft, ohne dass sich für eine Hotel-Matze-Folge irgendetwas sichtbar ändert.

**Architecture:** `session.peaks` bleibt unangetastet die Marker-Wahrheit (dadurch ist Pin-1 strukturell nicht betroffen). `ClipCandidate` bekommt `candidate_id`/`origin`/`anchor_ms` und ein optionales `peak_id`. Fünf bestehende blinde Joins auf `peak_id` werden auf **eine** zentrale Marker-Sicht umgestellt, die bei Doppelzuordnung kontrolliert fehlschlägt. Akten-Schema v5 → v6 als **eine atomare** Vertragsänderung; v1–v5 werden beim Hydrieren migriert, wo `session.peaks` verfügbar ist.

**Tech Stack:** Python 3.11, pytest. Kein Qt in `core/`. Zwei Repos: `PeakCut/App` (Kern) und `PeakCut-web` (Oberfläche, importiert den Kern).

## Global Constraints

- **Pin-1:** Die Keyboardstellen-XML bleibt **byte-identisch**. `tests/test_audio_routing_safety.py` läuft nach jedem Task.
- **Kern ist Qt-frei.** Nichts in `src/core/` importiert PyQt.
- **Volle Suite grün nach jedem Task.** Baseline vor Beginn: **852 passed**.
- **Origin-Werte, exakt:** `marker` · `transcript` · `auto` · `manual`. Datenbegriff `marker`, **nicht** `pedal` — das Gerät ist inzwischen eine Kickdrum. UI-Label darf „Pedal" heißen.
- **`origin` ≠ `source`.** `source` ist in der Decision belegt und bedeutet „**wer** hat entschieden" (`manual`, `ignore_peak`). Nicht überladen.
- **Die heutige Smart-Grenzen-Berechnung erzeugt KEINEN `transcript`-Origin.** Sie verbessert nur die `boundary` eines Marker-Kandidaten. Origin bleibt `marker`.
- **Strikte v6-Felder.** Keine großzügigen Defaults in `from_dict` für echte v6-Daten — sonst tarnen sich beschädigte Akten als gültig.
- **`anchor_ms` niemals aus `boundary.start_ms` ableiten.** Bei Marker-Stellen sitzt der Tritt mitten in der Grenze.
- **Arbeitszweig:** `feature/redesign`. Nach Gate B wandert v6 sofort auf `develop` + `main` (die v4/v5-Falle vom 17.08. darf sich nicht wiederholen).
- **Testlauf:** `./venv311/bin/python -m pytest tests/ -q` aus `PeakCut/App`.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `src/core/clip_candidates.py` (modify) | Datenmodell + Statusmaschine. Bekommt `candidate_id`/`origin`/`anchor_ms`, `CandidateDecision`, Origin-Konstanten. |
| `src/core/candidate_view.py` (**create**) | **Die** Marker-Sicht. Qt-frei, von Kern UND Web importierbar. Einzige Stelle, die Kandidaten über `peak_id` joint. |
| `src/core/session.py` (modify) | `_bootstrap_clip_candidates` → `_reconcile_marker_candidates`; `ignore_peak` über die Marker-Sicht. |
| `src/core/project_archive.py` (modify) | Schema 6, strikte Serialisierung, v1–v5-Migration beim Hydrieren mit Peak-Join. |
| `src/core/playback_windows.py` (modify) | Join → Marker-Sicht. |
| `src/core/xml_sequence_helpers.py` (modify) | Join → Marker-Sicht. |
| `src/core/clip_boundary/pipeline.py` (modify) | Join → Marker-Sicht. |
| `../../PeakCut-web/engine/engine_core.py` (modify) | Web-Serialisierer: Join → Marker-Sicht. |
| `tests/test_candidate_baseline_lock.py` (**create**) | Task 0: friert den Ist-Zustand ein. |
| `tests/test_candidate_contract_v6.py` (**create**) | Vertrag + Migration + Roundtrip. |
| `tests/test_candidate_reconcile.py` (**create**) | Lebenszyklus: Neu-Analyse zerstört nichts. |
| `tests/test_candidate_collisions.py` (**create**) | Alle fünf Kollisionspfade. |
| `tests/test_candidate_integration.py` (**create**) | Nicht-Marker-Kandidat end-to-end. |

---

### Task 0: Sicherheitsnetz

Friert den heutigen Zustand ein, **bevor** irgendetwas umgebaut wird. Alle Tests hier sind GRÜN gegen den aktuellen Code (sie beschreiben, was sich nicht ändern darf) — bis auf die als RED markierten, die den Zielzustand beschreiben und mit `pytest.mark.xfail(strict=True)` laufen, bis ihr Task sie erfüllt.

**Files:**
- Test: `tests/test_candidate_baseline_lock.py` (create)

**Interfaces:**
- Consumes: nichts
- Produces: `make_session_with_peaks(peaks_ms, *, ignored=())` — Helfer, den Task 2–4 wiederverwenden. Signatur: `(list[int], *, tuple[int, ...]) -> PeakCutSession`

- [ ] **Step 1: Helfer + Baseline-Tests schreiben**

```python
# tests/test_candidate_baseline_lock.py
"""Task 0 — Netz VOR dem Umbau (Carl-Gate A, 2026-08-19).

Diese Datei beschreibt, was sich durch die Quellenunabhaengigkeit NICHT
aendern darf. Sie ist gruen gegen den heutigen Code.
"""
import pytest

from core.clip_candidates import PROPOSED, DISCARDED
from core.project import PeakCutProject
from core.session import PeakCutSession

# pytest.ini setzt bereits `pythonpath = src` — kein sys.path-Gefummel noetig.
_CFG = {"fps": 25, "context_duration_ms": 15000}


def make_session_with_peaks(peaks_ms, *, ignored=()):
    """Session mit synthetischen Peaks; ohne Audio/Video, rein Datenweg.

    PeakCutSession verlangt (project, config) — siehe src/core/session.py:37.
    Muster uebernommen aus tests/test_clip_candidates_session.py:21.
    """
    session = PeakCutSession(PeakCutProject(), dict(_CFG))
    session.load_analysis_results({
        "peaks": [
            {"index": i, "position_ms": ms,
             "in_point_ms": max(0, ms - 15000), "out_point_ms": ms + 15000,
             "context_ms": 15000, "ignored": i in ignored}
            for i, ms in enumerate(peaks_ms)
        ],
        "video_offsets": [],
    })
    return session


def test_baseline_ein_kandidat_je_peak():
    session = make_session_with_peaks([10_000, 60_000, 120_000])
    assert len(session.clip_candidates) == 3
    assert [c.peak_id for c in session.clip_candidates] == [0, 1, 2]


def test_baseline_ignorierter_peak_wird_discarded():
    session = make_session_with_peaks([10_000, 60_000], ignored=(1,))
    assert session.clip_candidates[0].status == PROPOSED
    assert session.clip_candidates[1].status == DISCARDED


def test_baseline_boundary_kommt_aus_in_out_des_peaks():
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.boundary.start_ms == 45_000
    assert cand.boundary.end_ms == 75_000
```

- [ ] **Step 2: Baseline laufen lassen — muss GRÜN sein**

Run: `./venv311/bin/python -m pytest tests/test_candidate_baseline_lock.py -q`
Expected: `3 passed`. Wenn hier etwas rot ist, stimmt die Annahme über den Ist-Zustand nicht — **stoppen und klären**, nicht anpassen.

- [ ] **Step 3: RED-Tests für den Zielzustand anhängen**

```python
# ans Ende von tests/test_candidate_baseline_lock.py

@pytest.mark.xfail(strict=True, reason="Task 1: Vertrag noch nicht umgestellt")
def test_ziel_kandidat_hat_identitaet_und_herkunft():
    from core.clip_candidates import ORIGIN_MARKER
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER


@pytest.mark.xfail(strict=True, reason="Task 1: anchor_ms noch nicht da")
def test_ziel_anker_ist_der_tritt_nicht_der_anfang():
    session = make_session_with_peaks([60_000])
    cand = session.clip_candidates[0]
    assert cand.anchor_ms == 60_000          # der Tritt
    assert cand.anchor_ms != cand.boundary.start_ms   # NICHT der Anfang


@pytest.mark.xfail(strict=True, reason="Task 2: Reconcile noch nicht gebaut")
def test_ziel_neu_analyse_erhaelt_fremdquellen():
    from core.clip_candidates import ClipBoundary, ClipCandidate, ORIGIN_AUTO
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:abc", origin=ORIGIN_AUTO, anchor_ms=90_000,
        peak_id=None, boundary=ClipBoundary(80_000, 100_000)))
    session.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
                   "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    ids = {c.candidate_id for c in session.clip_candidates}
    assert "auto:abc" in ids, "Neu-Analyse hat den Auto-Kandidaten vernichtet"
```

- [ ] **Step 4: Laufen lassen — die drei neuen müssen xfail sein, nicht xpass**

Run: `./venv311/bin/python -m pytest tests/test_candidate_baseline_lock.py -q`
Expected: `3 passed, 3 xfailed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_candidate_baseline_lock.py
git commit -m "test(kandidaten): Task 0 — Sicherheitsnetz vor dem Umbau

Baseline (gruen) + Zielzustand als strict xfail: Identitaet/Herkunft,
anchor_ms als eigener Sprungpunkt, Erhalt von Fremdquellen bei Neu-Analyse."
```

---

### Task 1: Vollständiger v6-Vertrag (atomar)

Modelle, `CandidateDecision`, Schema 6, strikte Serialisierung, v1–v5-Migration mit Peak-Join, exakter v6-Roundtrip — **in einem Commit**. Getrennt gäbe es einen Zwischenstand, in dem Speichern die neuen Felder verliert.

**Files:**
- Modify: `src/core/clip_candidates.py`
- Modify: `src/core/project_archive.py:18` (Version), `:182-196` (schreiben), `:594-614` (hydrieren)
- Modify: `src/core/session.py:89-105` (Bootstrap setzt die neuen Felder)
- Test: `tests/test_candidate_contract_v6.py` (create)

**Interfaces:**
- Consumes: `make_session_with_peaks` aus Task 0
- Produces:
  - `ORIGIN_MARKER = "marker"`, `ORIGIN_TRANSCRIPT = "transcript"`, `ORIGIN_AUTO = "auto"`, `ORIGIN_MANUAL = "manual"`, `ALL_ORIGINS: tuple[str, ...]`
  - `ClipCandidate(candidate_id: str, origin: str, anchor_ms: int, peak_id: int | None, boundary: ClipBoundary, status: str = PROPOSED, transcript_excerpt: str = "", reason: str = "", score: float | None = None)`
  - `CandidateDecision(candidate_id: str, from_status: str, to_status: str, decided_at: str, source: str = "manual")`
  - `PeakDecision = CandidateDecision` (Alias, damit bestehende Importe im Repo nicht brechen)
  - `transition(candidate, to_status, *, now, source="manual") -> tuple[ClipCandidate, CandidateDecision | None]`
  - `marker_candidate_id(peak_id: int) -> str` → `f"marker:{peak_id}"`
  - `CURRENT_SCHEMA_VERSION = 6`

- [ ] **Step 1: Failing test für den Vertrag schreiben**

```python
# tests/test_candidate_contract_v6.py
"""Task 1 — v6-Vertrag: Identitaet, Herkunft, Anker, Migration, Roundtrip."""
import json
import os

import pytest

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, CandidateDecision, ClipCandidateError,
    ORIGIN_MARKER, ORIGIN_AUTO, PROPOSED, SELECTED, marker_candidate_id)


def test_marker_candidate_id_format():
    assert marker_candidate_id(0) == "marker:0"
    assert marker_candidate_id(17) == "marker:17"


def test_kandidat_traegt_identitaet_herkunft_anker():
    c = ClipCandidate(candidate_id="marker:0", origin=ORIGIN_MARKER,
                      anchor_ms=60_000, peak_id=0,
                      boundary=ClipBoundary(45_000, 75_000))
    assert c.candidate_id == "marker:0"
    assert c.origin == ORIGIN_MARKER
    assert c.anchor_ms == 60_000
    assert c.peak_id == 0


def test_unbekannte_herkunft_wird_abgelehnt():
    with pytest.raises(ClipCandidateError):
        ClipCandidate(candidate_id="x", origin="pedal", anchor_ms=1,
                      peak_id=None, boundary=ClipBoundary(0, 10))


def test_v6_roundtrip_ist_exakt():
    c = ClipCandidate(candidate_id="auto:7f3", origin=ORIGIN_AUTO,
                      anchor_ms=90_000, peak_id=None,
                      boundary=ClipBoundary(80_000, 100_000),
                      status=SELECTED, reason="starker Einstieg", score=0.81)
    assert ClipCandidate.from_dict(json.loads(json.dumps(c.to_dict()))) == c


def test_v6_ohne_pflichtfelder_wird_abgelehnt():
    """Strikt (Carl): grosszuegige Defaults wuerden kaputte v6-Akten tarnen."""
    with pytest.raises((ClipCandidateError, KeyError)):
        ClipCandidate.from_dict({"boundary": {"start_ms": 0, "end_ms": 10},
                                 "status": PROPOSED})


def test_decision_haengt_an_candidate_id():
    d = CandidateDecision(candidate_id="auto:7f3", from_status=PROPOSED,
                          to_status=SELECTED, decided_at="2026-08-19T10:00:00")
    assert d.to_dict()["candidate_id"] == "auto:7f3"
    assert "peak_id" not in d.to_dict()


def test_alte_decision_mit_peak_id_wird_gelesen():
    """v1-v5-Decisions sind eine reine String-Abbildung — kein Peak noetig."""
    d = CandidateDecision.from_dict({
        "peak_id": 3, "from_status": PROPOSED, "to_status": SELECTED,
        "decided_at": "2026-06-01T10:00:00", "source": "manual"})
    assert d.candidate_id == "marker:3"
```

- [ ] **Step 2: Laufen lassen — muss fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_contract_v6.py -q`
Expected: FAIL, `ImportError: cannot import name 'ORIGIN_MARKER'`

- [ ] **Step 3: `clip_candidates.py` umbauen**

```python
# src/core/clip_candidates.py — Origin-Konstanten NACH den Status-Konstanten

ORIGIN_MARKER = "marker"          # Fusspedal/Kickdrum — Datenbegriff, NICHT "pedal"
ORIGIN_TRANSCRIPT = "transcript"  # transkriptweiter Finder (eigener spaeterer Slice)
ORIGIN_AUTO = "auto"              # automatische Clip-Findung
ORIGIN_MANUAL = "manual"          # von Hand im Review gesetzt

ALL_ORIGINS = (ORIGIN_MARKER, ORIGIN_TRANSCRIPT, ORIGIN_AUTO, ORIGIN_MANUAL)


def marker_candidate_id(peak_id: int) -> str:
    """Identitaet eines markergebundenen Kandidaten.

    ACHTUNG (Carl): ueber Analyselaeufe hinweg NICHT stabil, sobald Marker
    eingefuegt/entfernt werden. Echte Reanalyse mit veraendertem Marker-Satz
    braucht zeitliches Event-Matching -> eigener spaeterer Slice.
    """
    return f"marker:{peak_id}"
```

```python
# src/core/clip_candidates.py — ClipCandidate ersetzen

@dataclass(frozen=True)
class ClipCandidate:
    candidate_id: str
    origin: str
    anchor_ms: int          # Sprungpunkt. NIEMALS aus boundary.start_ms ableiten.
    peak_id: int | None     # nur Rueckreferenz fuer origin == marker
    boundary: ClipBoundary
    status: str = PROPOSED
    transcript_excerpt: str = ""
    reason: str = ""
    score: float | None = None

    def __post_init__(self):
        if self.status not in _ALL_STATUS:
            raise ClipCandidateError(f"Unbekannter Status: {self.status!r}")
        if self.origin not in ALL_ORIGINS:
            raise ClipCandidateError(f"Unbekannte Herkunft: {self.origin!r}")
        if not self.candidate_id:
            raise ClipCandidateError("candidate_id darf nicht leer sein")
        if self.origin == ORIGIN_MARKER and self.peak_id is None:
            raise ClipCandidateError("Marker-Kandidat ohne peak_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "origin": self.origin,
            "anchor_ms": self.anchor_ms,
            "peak_id": self.peak_id,
            "boundary": self.boundary.to_dict(),
            "status": self.status,
            "transcript_excerpt": self.transcript_excerpt,
            "reason": self.reason,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ClipCandidate":
        """STRIKT: v6-Pflichtfelder muessen da sein. v1-v5 werden NICHT hier
        migriert — das passiert beim Hydrieren, wo session.peaks vorliegt
        (anchor_ms == peak.position_ms ist hier nicht ableitbar)."""
        missing = [k for k in ("candidate_id", "origin", "anchor_ms") if k not in d]
        if missing:
            raise ClipCandidateError(
                f"v6-Kandidat unvollstaendig, fehlt: {', '.join(missing)}")
        peak_id = d.get("peak_id")
        return cls(
            candidate_id=str(d["candidate_id"]),
            origin=str(d["origin"]),
            anchor_ms=int(d["anchor_ms"]),
            peak_id=None if peak_id is None else int(peak_id),
            boundary=ClipBoundary.from_dict(d["boundary"]),
            status=str(d.get("status", PROPOSED)),
            transcript_excerpt=str(d.get("transcript_excerpt", "")),
            reason=str(d.get("reason", "")),
            score=d.get("score"),
        )
```

```python
# src/core/clip_candidates.py — PeakDecision -> CandidateDecision

@dataclass(frozen=True)
class CandidateDecision:
    candidate_id: str
    from_status: str
    to_status: str
    decided_at: str
    source: str = "manual"   # WER hat entschieden (nicht: woher kam die Stelle)

    def __post_init__(self):
        for s in (self.from_status, self.to_status):
            if s not in _ALL_STATUS:
                raise ClipCandidateError(f"Unbekannter Status: {s!r}")
        if self.to_status not in _ALLOWED.get(self.from_status, set()):
            raise ClipCandidateError(
                f"Illegaler Uebergang im Log: {self.from_status} -> {self.to_status}")

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "from_status": self.from_status,
                "to_status": self.to_status, "decided_at": self.decided_at,
                "source": self.source}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandidateDecision":
        """Nimmt v6 (candidate_id) UND v1-v5 (peak_id) entgegen. Anders als beim
        Kandidaten ist das hier eine reine String-Abbildung — kein Peak noetig."""
        cid = d.get("candidate_id")
        if cid is None:
            if "peak_id" not in d:
                raise ClipCandidateError("Decision ohne candidate_id/peak_id")
            cid = marker_candidate_id(int(d["peak_id"]))
        return cls(candidate_id=str(cid), from_status=str(d["from_status"]),
                   to_status=str(d["to_status"]), decided_at=str(d["decided_at"]),
                   source=str(d.get("source", "manual")))


PeakDecision = CandidateDecision   # Alias: bestehende Importe im Repo bleiben heil
```

In `transition()` die Zeile, die `peak_id=candidate.peak_id` setzt, ersetzen durch `candidate_id=candidate.candidate_id`.

- [ ] **Step 4: Bootstrap in `session.py` auf die neuen Felder heben**

```python
# src/core/session.py — in _bootstrap_clip_candidates, der cands.append-Block
            cands.append(ClipCandidate(
                candidate_id=marker_candidate_id(pk.index),
                origin=ORIGIN_MARKER,
                anchor_ms=pk.position_ms,      # der Tritt, NICHT lo
                peak_id=pk.index,
                boundary=ClipBoundary(lo, hi),
                status=DISCARDED if pk.ignored else PROPOSED))
```
Import oben im Block ergänzen: `ORIGIN_MARKER, marker_candidate_id`.

- [ ] **Step 5: Schema 6 + Migration beim Hydrieren**

```python
# src/core/project_archive.py:18
CURRENT_SCHEMA_VERSION = 6  # v6 (Carl-Gate A 2026-08-19): Kandidaten quellenunabhaengig — candidate_id/origin/anchor_ms/optionales peak_id; Decisions an candidate_id. v5-Slots bleiben.
```

```python
# src/core/project_archive.py — im payload (bei ~:188) die Decision-Sektion umbenennen
        "clip_candidates": _to_dict_list(getattr(session, "clip_candidates", [])),
        # v6: Decisions haengen an candidate_id. Alte Akten schreiben "peak_decisions";
        # gelesen werden BEIDE (siehe Hydrieren), geschrieben nur noch der neue Name.
        "candidate_decisions": _to_dict_list(getattr(session, "peak_decisions", [])),
```

```python
# src/core/project_archive.py — beim Parsen (bei ~:264)
        "clip_candidates": payload.get("clip_candidates"),
        "peak_decisions": payload.get("candidate_decisions",
                                      payload.get("peak_decisions")),
```

```python
# src/core/project_archive.py — Hydrieren (ersetzt den try-Block bei ~:603-614)
    from .clip_candidates import (
        ClipCandidate, CandidateDecision, ClipCandidateError,
        ClipBoundary, ORIGIN_MARKER, marker_candidate_id)

    def _hydrate_candidate(d):
        """v6 direkt; v1-v5 hier migrieren — HIER, weil session.peaks vorliegt.
        anchor_ms == position_ms des zugehoerigen Peaks. Kein passender Peak ->
        kontrollierter Fehler statt Raten (Carl)."""
        if "candidate_id" in d and "origin" in d and "anchor_ms" in d:
            return ClipCandidate.from_dict(d)
        peak_id = int(d["peak_id"])
        peak = next((p for p in session.peaks if p.index == peak_id), None)
        if peak is None:
            raise ProjectArchiveError(
                f"Alte Akte: Kandidat verweist auf Peak {peak_id}, den es nicht gibt.")
        return ClipCandidate(
            candidate_id=marker_candidate_id(peak_id),
            origin=ORIGIN_MARKER,
            anchor_ms=peak.position_ms,
            peak_id=peak_id,
            boundary=ClipBoundary.from_dict(d["boundary"]),
            status=str(d.get("status", "proposed")),
            transcript_excerpt=str(d.get("transcript_excerpt", "")),
            reason=str(d.get("reason", "")),
            score=d.get("score"))

    try:
        if cc is not None:
            session.clip_candidates = [_hydrate_candidate(d) for d in cc]
        if pd is not None:
            session.peak_decisions = [CandidateDecision.from_dict(d) for d in pd]
    except (ClipCandidateError, KeyError, TypeError, ValueError) as e:
        raise ProjectArchiveError(f"ClipCandidate-Daten unlesbar: {e}") from e
```

- [ ] **Step 6: Migrations-Test anhängen**

```python
# ans Ende von tests/test_candidate_contract_v6.py
def test_v5_akte_migriert_anchor_aus_dem_peak(tmp_path):
    """Der Anker MUSS aus peak.position_ms kommen, nicht aus boundary.start_ms."""
    from tests.test_candidate_baseline_lock import make_session_with_peaks
    from core.project_archive import save_project_archive, load_project_archive

    session = make_session_with_peaks([60_000])
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))

    akte = root / ".peakcut" / "project.json"
    payload = json.loads(akte.read_text())
    payload["schema_version"] = 5
    payload["clip_candidates"] = [{
        "peak_id": 0, "boundary": {"start_ms": 45_000, "end_ms": 75_000},
        "status": "proposed", "transcript_excerpt": "", "reason": "", "score": None}]
    payload["peak_decisions"] = []
    payload.pop("candidate_decisions", None)
    akte.write_text(json.dumps(payload))

    loaded = load_project_archive(str(root), {})
    cand = loaded.clip_candidates[0]
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER
    assert cand.anchor_ms == 60_000
    assert cand.anchor_ms != cand.boundary.start_ms
```

> Falls `load_project_archive` eine andere Rückgabe hat als `(session, warnings)`: die tatsächliche Signatur aus `project_archive.py:499` übernehmen und den Test daran anpassen — **nicht** die Produktionssignatur ändern.

- [ ] **Step 7: Vertrag + Suite laufen lassen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_contract_v6.py tests/test_candidate_baseline_lock.py -q`
Expected: alle Vertragstests PASS; in `test_candidate_baseline_lock.py` schlagen jetzt die ersten zwei xfail-Tests in **XPASS (strict → FAIL)** um.

- [ ] **Step 8: Erfüllte xfail-Marker entfernen**

Die Marker `@pytest.mark.xfail(...)` über `test_ziel_kandidat_hat_identitaet_und_herkunft` und `test_ziel_anker_ist_der_tritt_nicht_der_anfang` löschen. Der dritte (`test_ziel_neu_analyse_erhaelt_fremdquellen`) bleibt bis Task 2.

- [ ] **Step 9: Volle Suite + Pin-1**

Run: `./venv311/bin/python -m pytest tests/ -q`
Expected: `>= 852 passed, 1 xfailed`. **Jeder rote Test hier ist ein echter Fund** — Verbraucher, die noch `PeakDecision(peak_id=…)` bauen oder `ClipCandidate(...)` positional aufrufen. Reparieren, nicht umgehen.

- [ ] **Step 10: Commit**

```bash
git add src/core/clip_candidates.py src/core/session.py src/core/project_archive.py tests/
git commit -m "feat(kandidaten): Task 1 — v6-Vertrag atomar (Identitaet, Herkunft, Anker)

candidate_id/origin/anchor_ms/optionales peak_id; CandidateDecision haengt an
candidate_id (PeakDecision bleibt Alias). Schema 5 -> 6. Strikte v6-Felder,
v1-v5-Migration beim Hydrieren mit Peak-Join: anchor_ms == peak.position_ms,
kein passender Peak -> ProjectArchiveError statt Raten."
```

---

### Task 2: Session-Lebenszyklus — Reconciliation statt Replace

Heute vernichtet `_bootstrap_clip_candidates` (`session.py:104-105`) bei **jeder** Neu-Analyse die gesamte Kandidatenliste **und** das Entscheidungslog.

**Files:**
- Modify: `src/core/session.py:89-105`
- Test: `tests/test_candidate_reconcile.py` (create)

**Interfaces:**
- Consumes: `ClipCandidate`, `ORIGIN_MARKER`, `marker_candidate_id` (Task 1); `make_session_with_peaks` (Task 0)
- Produces: `PeakCutSession._reconcile_marker_candidates() -> None`; `session.clip_candidates` ist **immer** nach `(anchor_ms, candidate_id)` sortiert

- [ ] **Step 1: Failing tests schreiben**

```python
# tests/test_candidate_reconcile.py
"""Task 2 — Neu-Analyse darf Fremdquellen und Entscheidungen nicht vernichten.

GRENZE (Carl): Diese Tests laufen mit UNVERAENDERTEM Marker-Satz.
marker:<peak_id> ist bei eingefuegten/entfernten Markern ueber Analyselaeufe
hinweg nicht stabil — echte Reanalyse braucht zeitliches Event-Matching und
wird hier bewusst NICHT versprochen.
"""
import pytest

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, CandidateDecision, ClipCandidateError,
    ORIGIN_AUTO, ORIGIN_MARKER, PROPOSED, SELECTED)
from tests.test_candidate_baseline_lock import make_session_with_peaks

PEAKS = [60_000]
SAME_ANALYSIS = {
    "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
               "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False}],
    "video_offsets": [],
}


def _with_auto(session):
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:abc", origin=ORIGIN_AUTO, anchor_ms=90_000,
        peak_id=None, boundary=ClipBoundary(80_000, 100_000)))
    return session


def test_neu_analyse_erhaelt_auto_kandidaten():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.load_analysis_results(SAME_ANALYSIS)
    assert "auto:abc" in {c.candidate_id for c in session.clip_candidates}


def test_neu_analyse_erhaelt_das_entscheidungslog():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.peak_decisions.append(CandidateDecision(
        candidate_id="auto:abc", from_status=PROPOSED, to_status=SELECTED,
        decided_at="2026-08-19T10:00:00"))
    session.load_analysis_results(SAME_ANALYSIS)
    assert len(session.peak_decisions) == 1


def test_bearbeitungszustand_eines_marker_kandidaten_bleibt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates[0] = ClipCandidate(
        candidate_id="marker:0", origin=ORIGIN_MARKER, anchor_ms=60_000,
        peak_id=0, boundary=ClipBoundary(50_000, 70_000),
        status=SELECTED, reason="von Hand justiert", score=0.9)
    session.load_analysis_results(SAME_ANALYSIS)
    cand = next(c for c in session.clip_candidates if c.candidate_id == "marker:0")
    assert cand.status == SELECTED
    assert cand.reason == "von Hand justiert"
    assert cand.boundary.start_ms == 50_000


def test_fehlender_marker_kandidat_wird_ergaenzt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates = []
    session.load_analysis_results(SAME_ANALYSIS)
    assert [c.candidate_id for c in session.clip_candidates] == ["marker:0"]


def test_sortierung_ist_deterministisch_nach_anker():
    session = _with_auto(make_session_with_peaks(PEAKS))
    session.load_analysis_results(SAME_ANALYSIS)
    ankers = [c.anchor_ms for c in session.clip_candidates]
    assert ankers == sorted(ankers)


def test_doppelte_candidate_id_wird_abgelehnt():
    session = make_session_with_peaks(PEAKS)
    session.clip_candidates.append(ClipCandidate(
        candidate_id="marker:0", origin=ORIGIN_AUTO, anchor_ms=99_000,
        peak_id=None, boundary=ClipBoundary(90_000, 110_000)))
    with pytest.raises(ClipCandidateError):
        session.load_analysis_results(SAME_ANALYSIS)
```

- [ ] **Step 2: Laufen lassen — muss fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_reconcile.py -q`
Expected: FAIL — die Auto-Kandidaten sind nach `load_analysis_results` weg.

- [ ] **Step 3: `_bootstrap_clip_candidates` durch Reconciliation ersetzen**

```python
# src/core/session.py — ersetzt _bootstrap_clip_candidates komplett
    def _reconcile_marker_candidates(self):
        """Gleicht NUR die Partition origin == marker ab.

        Bestehende Marker-Kandidaten behalten ihren Bearbeitungszustand,
        fehlende werden ergaenzt, Nicht-Marker-Kandidaten bleiben unangetastet.
        Das Entscheidungslog wird NIE pauschal geleert — es ist die Grundlage
        des lernenden Scores.
        """
        from .clip_candidates import (
            ClipBoundary, ClipCandidate, ClipCandidateError,
            ORIGIN_MARKER, PROPOSED, DISCARDED, marker_candidate_id)

        seen = {}
        for c in self.clip_candidates:
            if c.candidate_id in seen:
                raise ClipCandidateError(
                    f"Doppelte candidate_id: {c.candidate_id!r}")
            seen[c.candidate_id] = c

        keep = [c for c in self.clip_candidates if c.origin != ORIGIN_MARKER]
        by_id = {c.candidate_id: c for c in self.clip_candidates
                 if c.origin == ORIGIN_MARKER}

        for pk in self.peaks:
            cid = marker_candidate_id(pk.index)
            existing = by_id.get(cid)
            if existing is not None:
                keep.append(existing)       # Bearbeitungszustand bleibt
                continue
            lo, hi = pk.in_point_ms, pk.out_point_ms
            if hi <= lo:                    # defensiv (Clamp-Edge)
                hi = lo + 1
            keep.append(ClipCandidate(
                candidate_id=cid, origin=ORIGIN_MARKER,
                anchor_ms=pk.position_ms, peak_id=pk.index,
                boundary=ClipBoundary(lo, hi),
                status=DISCARDED if pk.ignored else PROPOSED))

        keep.sort(key=lambda c: (c.anchor_ms, c.candidate_id))
        self.clip_candidates = keep
        # peak_decisions bewusst NICHT angefasst.

    # Rueckwaertskompatibler Name: project_archive.py:314 ruft ihn per hasattr.
    _bootstrap_clip_candidates = _reconcile_marker_candidates
```

In `load_analysis_results` (`session.py:187`) den Aufruf auf `self._reconcile_marker_candidates()` umstellen. **Wichtig:** in `__init__` müssen `self.clip_candidates = []` und `self.peak_decisions = []` gesetzt bleiben (`session.py:65`), damit der erste Lauf definiert startet.

- [ ] **Step 4: Tests laufen lassen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_reconcile.py -q`
Expected: `6 passed`

- [ ] **Step 5: Letzten xfail-Marker entfernen und volle Suite fahren**

`@pytest.mark.xfail` über `test_ziel_neu_analyse_erhaelt_fremdquellen` in `tests/test_candidate_baseline_lock.py` löschen.

Run: `./venv311/bin/python -m pytest tests/ -q`
Expected: alles grün, keine xfails mehr.

- [ ] **Step 6: Commit**

```bash
git add src/core/session.py tests/
git commit -m "feat(kandidaten): Task 2 — Reconciliation statt Replace

_bootstrap_clip_candidates loeschte bei JEDER Neu-Analyse die gesamte
Kandidatenliste und das Entscheidungslog. Jetzt wird nur die Marker-Partition
abgeglichen; Fremdquellen, Bearbeitungszustand und Decisions bleiben.
Deterministische Sortierung (anchor_ms, candidate_id), doppelte candidate_id
wird abgelehnt.

GRENZE: gilt fuer unveraenderten Marker-Satz. marker:<peak_id> ist bei
eingefuegten/entfernten Markern nicht stabil -> eigener spaeterer Slice."
```

---

### Task 3: Zentrale Marker-Sicht — alle fünf blinden Joins

Fünf Stellen joinen Kandidaten blind über `peak_id`. **Keine fünf verstreuten `origin`-Prüfungen** — eine Sicht, die bei Doppelzuordnung kontrolliert fehlschlägt.

**Files:**
- Create: `src/core/candidate_view.py`
- Modify: `src/core/playback_windows.py:62`, `src/core/xml_sequence_helpers.py:69`, `src/core/session.py` (`ignore_peak`), `src/core/clip_boundary/pipeline.py:105`
- Modify: `../../PeakCut-web/engine/engine_core.py:82`
- Test: `tests/test_candidate_collisions.py` (create)

**Interfaces:**
- Consumes: `ORIGIN_MARKER`, `ClipCandidate` (Task 1)
- Produces:
  - `marker_candidates_by_peak_id(session) -> dict[int, ClipCandidate]` — nur `origin == marker`; **raises `ClipCandidateError`** bei doppelter Marker-Zuordnung auf denselben Peak
  - `marker_candidate_for_peak(session, peak_id: int) -> ClipCandidate | None`

- [ ] **Step 1: Kollisionstests für alle fünf Pfade schreiben**

```python
# tests/test_candidate_collisions.py
"""Task 3 — ein auto-Kandidat mit kollidierender Legacy-peak_id darf NIRGENDS
als Marker-Kandidat durchschlagen. Fuenf Pfade (Carl 2026-08-19)."""
import pytest

from core.candidate_view import (
    marker_candidate_for_peak, marker_candidates_by_peak_id)
from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ClipCandidateError, ORIGIN_AUTO, ORIGIN_MARKER)
from tests.test_candidate_baseline_lock import make_session_with_peaks

COLLIDING_PEAK_ID = 0


def _session_with_collision():
    """auto-Kandidat traegt absichtlich dieselbe peak_id wie ein aktiver Peak."""
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id="auto:kollision", origin=ORIGIN_AUTO, anchor_ms=61_000,
        peak_id=COLLIDING_PEAK_ID, boundary=ClipBoundary(55_000, 65_000),
        score=0.99, reason="Eindringling"))
    return session


def test_sicht_liefert_nur_den_marker_kandidaten():
    session = _session_with_collision()
    cand = marker_candidate_for_peak(session, COLLIDING_PEAK_ID)
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER


def test_sicht_schlaegt_bei_doppelter_marker_zuordnung_fehl():
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id="marker:0:dublette", origin=ORIGIN_MARKER, anchor_ms=60_000,
        peak_id=0, boundary=ClipBoundary(45_000, 75_000)))
    with pytest.raises(ClipCandidateError):
        marker_candidates_by_peak_id(session)


def test_pfad_playback_spielt_nicht_das_fremdfenster():
    from core.playback_modes import PLAYBACK_MODE_SMART
    from core.playback_windows import build_playback_window
    session = _session_with_collision()
    win = build_playback_window(session, PLAYBACK_MODE_SMART, peak_index=0)
    assert (win.start_ms, win.end_ms) != (55_000, 65_000), \
        "Smart-Fenster kam vom kollidierenden auto-Kandidaten"


def test_pfad_smart_xml_nimmt_den_eindringling_nicht_auf():
    from core.xml_sequence_helpers import active_smart_candidates
    session = _session_with_collision()
    ids = {c.candidate_id for _, c in active_smart_candidates(session)}
    assert "auto:kollision" not in ids


def test_pfad_ignorieren_trifft_den_marker_kandidaten():
    session = _session_with_collision()
    session.set_current_peak(0)
    session.ignore_peak()
    intruder = next(c for c in session.clip_candidates
                    if c.candidate_id == "auto:kollision")
    marker = next(c for c in session.clip_candidates
                  if c.candidate_id == "marker:0")
    assert marker.status == "discarded"
    assert intruder.status == "proposed", "Ignorieren traf den falschen Kandidaten"
```

> Verifiziert: `build_playback_window(session, mode, peak_index=None) -> PlaybackWindow(mode, start_ms, end_ms, disabled_reason="")`. Der Peak wird intern über `_resolve_peak` aufgelöst, deshalb reicht `peak_index`.

- [ ] **Step 2: Laufen lassen — muss fehlschlagen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_collisions.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'core.candidate_view'`

- [ ] **Step 3: Die Marker-Sicht bauen**

```python
# src/core/candidate_view.py
"""Die EINE Stelle, die Kandidaten ueber peak_id joint (Carl-Gate A 2026-08-19).

Vorher taten das fuenf Stellen blind — XML-Export, Smart-Playback, Ignorieren,
Grenzen-Pipeline und der Web-Serialisierer. Ein Kandidat aus einer anderen
Quelle mit kollidierender Legacy-peak_id konnte dort den Marker-Kandidaten
verdraengen; im Web-Serialisierer sogar still ueberschreiben.

Qt-frei: wird auch aus PeakCut-web importiert.
"""
from .clip_candidates import ClipCandidateError, ORIGIN_MARKER


def marker_candidates_by_peak_id(session) -> dict:
    """peak_id -> Marker-Kandidat. Schlaegt bei Doppelzuordnung FEHL statt
    stillschweigend einen Treffer zu waehlen."""
    out = {}
    for c in (getattr(session, "clip_candidates", None) or []):
        if c.origin != ORIGIN_MARKER or c.peak_id is None:
            continue
        if c.peak_id in out:
            raise ClipCandidateError(
                f"Zwei Marker-Kandidaten fuer Peak {c.peak_id}: "
                f"{out[c.peak_id].candidate_id!r} und {c.candidate_id!r}")
        out[c.peak_id] = c
    return out


def marker_candidate_for_peak(session, peak_id: int):
    """Marker-Kandidat zu einem Peak, oder None."""
    return marker_candidates_by_peak_id(session).get(peak_id)


__all__ = ["marker_candidates_by_peak_id", "marker_candidate_for_peak"]
```

- [ ] **Step 4: Die vier Kern-Verbraucher umstellen**

```python
# src/core/playback_windows.py — ersetzt den next(...)-Join bei ~:62
    from .candidate_view import marker_candidate_for_peak
    cand = marker_candidate_for_peak(session, peak.index)
```

```python
# src/core/xml_sequence_helpers.py — ersetzt die Filterliste in active_smart_candidates
    from .candidate_view import marker_candidates_by_peak_id
    number_map = build_peak_number_map(session)
    by_peak = marker_candidates_by_peak_id(session)
    active = [c for pid, c in by_peak.items()
              if pid in number_map and c.status != DISCARDED and c.score is not None]
    active.sort(key=lambda c: number_map[c.peak_id])
```

```python
# src/core/session.py — in ignore_peak den for/continue/break-Block ersetzen
        from .candidate_view import marker_candidate_for_peak
        target = marker_candidate_for_peak(self, peak.index)
        if target is not None:
            i = self.clip_candidates.index(target)
            try:
                new, dec = transition(
                    target, DISCARDED, now=datetime.now().isoformat(),
                    source="ignore_peak")
            except ClipCandidateError:
                new, dec = None, None   # z.B. published (terminal) -> nichts aendern
            if dec is not None:
                self.clip_candidates[i] = new
                self.peak_decisions.append(dec)
```

```python
# src/core/clip_boundary/pipeline.py — ersetzt by_id bei ~:105
    from ..candidate_view import marker_candidates_by_peak_id
    by_id = {pid: cands.index(c)
             for pid, c in marker_candidates_by_peak_id(session).items()}
```

> Verifiziert: `pipeline.py:72` setzt `cands = session.clip_candidates` — es ist dieselbe Liste, `cands.index(c)` trifft also den richtigen Eintrag. Die zentrale Sicht liefert bereits nur Marker-Kandidaten; ein zusätzlicher `origin`-Check hier wäre genau die verstreute Prüfung, die Carl vermeiden wollte.

- [ ] **Step 5: Web-Serialisierer umstellen (zweites Repo)**

```python
# PeakCut-web/engine/engine_core.py — ersetzt den cands-Aufbau bei ~:82
    from core.candidate_view import marker_candidates_by_peak_id
    cands = {}
    for pid, c in marker_candidates_by_peak_id(session).items():
        cands[pid] = {"score": c.score, "reason": getattr(c, "reason", None),
                      "start_ms": c.boundary.start_ms, "end_ms": c.boundary.end_ms,
                      "status": str(c.status)}
```

- [ ] **Step 6: Kollisionstests + volle Suite**

Run: `./venv311/bin/python -m pytest tests/test_candidate_collisions.py -q`
Expected: `5 passed`

Run: `./venv311/bin/python -m pytest tests/ -q`
Expected: alles grün.

- [ ] **Step 7: Web-Suite fahren (zweites Repo)**

```bash
cd ../../PeakCut-web && python3 -m pytest engine -q
```
Expected: `362 passed` (oder mehr), keine neuen Fehler.

- [ ] **Step 8: Zwei Commits, ein Repo je Commit**

```bash
cd ~/Desktop/MF/Vibecoding/PeakCut/App
git add src/core/candidate_view.py src/core/playback_windows.py \
        src/core/xml_sequence_helpers.py src/core/session.py \
        src/core/clip_boundary/pipeline.py tests/test_candidate_collisions.py
git commit -m "feat(kandidaten): Task 3 — zentrale Marker-Sicht statt fuenf blinder Joins

candidate_view.marker_candidates_by_peak_id/_for_peak filtern origin==marker
und schlagen bei Doppelzuordnung kontrolliert fehl. Umgestellt: XML-Export,
Smart-Playback, Ignorieren, Grenzen-Pipeline. Kollisionstest je Pfad."

cd ~/Desktop/MF/Vibecoding/PeakCut-web
git add engine/engine_core.py
git commit -m "fix(engine): Kandidaten-Map ueber die zentrale Marker-Sicht

cands[c.peak_id] = ... konnte einen Marker-Kandidaten still ueberschreiben —
in genau der Map, die die Oberflaeche liest."
```

---

### Task 4: Integration

Ein Nicht-Marker-Kandidat läuft den **vollständigen** Datenweg, ohne die Exporte zu berühren.

**Files:**
- Test: `tests/test_candidate_integration.py` (create)

**Interfaces:**
- Consumes: alles aus Task 1–3

- [ ] **Step 1: Integrationstest schreiben**

```python
# tests/test_candidate_integration.py
"""Task 4 — Gate-A-Nachweis: ein auto-Kandidat durch den ganzen Datenweg."""
import json

from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ORIGIN_AUTO, PROPOSED, SELECTED, transition)
from core.project_archive import load_project_archive, save_project_archive
from core.xml_sequence_helpers import active_smart_candidates
from tests.test_candidate_baseline_lock import make_session_with_peaks

AUTO_ID = "auto:integration"


def test_auto_kandidat_kompletter_datenweg(tmp_path):
    # 1. erzeugen
    session = make_session_with_peaks([60_000, 180_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id=AUTO_ID, origin=ORIGIN_AUTO, anchor_ms=120_000,
        peak_id=None, boundary=ClipBoundary(110_000, 130_000),
        reason="starker Einstieg", score=0.77))
    session._reconcile_marker_candidates()

    # 2. sortiert nach anchor_ms
    assert [c.anchor_ms for c in session.clip_candidates] == [60_000, 120_000, 180_000]

    # 3. Statusuebergang ueber candidate_id
    i = next(i for i, c in enumerate(session.clip_candidates)
             if c.candidate_id == AUTO_ID)
    new, dec = transition(session.clip_candidates[i], SELECTED,
                          now="2026-08-19T12:00:00")
    session.clip_candidates[i] = new
    session.peak_decisions.append(dec)
    assert dec.candidate_id == AUTO_ID

    # 4. Origin-Filter: kein Leck in die Smart-XML
    assert AUTO_ID not in {c.candidate_id for _, c in active_smart_candidates(session)}

    # 5. v6 speichern/laden exakt
    root = tmp_path / "folge"
    root.mkdir()
    save_project_archive(session, str(root))
    payload = json.loads((root / ".peakcut" / "project.json").read_text())
    assert payload["schema_version"] == 6

    loaded = load_project_archive(str(root), {})
    back = next(c for c in loaded.clip_candidates if c.candidate_id == AUTO_ID)
    assert back.origin == ORIGIN_AUTO
    assert back.anchor_ms == 120_000
    assert back.status == SELECTED
    assert back.score == 0.77
    assert [d.candidate_id for d in loaded.peak_decisions] == [AUTO_ID]

    # 6. Neu-Analyse ueberlebt er
    loaded.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60_000, "in_point_ms": 45_000,
                   "out_point_ms": 75_000, "context_ms": 15_000, "ignored": False},
                  {"index": 1, "position_ms": 180_000, "in_point_ms": 165_000,
                   "out_point_ms": 195_000, "context_ms": 15_000, "ignored": False}],
        "video_offsets": [],
    })
    assert AUTO_ID in {c.candidate_id for c in loaded.clip_candidates}
    assert len(loaded.peak_decisions) == 1
```

- [ ] **Step 2: Laufen lassen**

Run: `./venv311/bin/python -m pytest tests/test_candidate_integration.py -q`
Expected: `1 passed`. Bei Fehlern in Schritt 5/6: **nicht den Test aufweichen** — das sind echte Lücken in Task 1/2.

- [ ] **Step 3: Pin-1 ausdrücklich prüfen**

Run: `./venv311/bin/python -m pytest tests/test_audio_routing_safety.py -q`
Expected: `6 passed` — die Keyboardstellen-XML ist byte-identisch.

- [ ] **Step 4: Volle Suite, beide Repos**

```bash
cd ~/Desktop/MF/Vibecoding/PeakCut/App && ./venv311/bin/python -m pytest tests/ -q
cd ~/Desktop/MF/Vibecoding/PeakCut-web && python3 -m pytest engine -q
```
Expected: beide grün.

- [ ] **Step 5: Echte Produktionsakte gegenprüfen (kein Test, Handgriff)**

```bash
cd ~/Desktop/MF/Vibecoding/PeakCut-web && PEAKCUT_EXPORT_GATE=1 python3 -m pytest engine/tests/test_export_parity.py -q
```
Expected: `6 passed` — Keyboardstellen-XML/TXT und Folgenschnitt-XML byte-identisch zur Ilka-Akte. **Das ist der eigentliche Beweis**, dass sich für eine Hotel-Matze-Folge nichts geändert hat.

- [ ] **Step 6: Commit**

```bash
git add tests/test_candidate_integration.py
git commit -m "test(kandidaten): Task 4 — auto-Kandidat kompletter Datenweg

Erzeugen, Sortierung nach anchor_ms, Statusuebergang ueber candidate_id,
v6 Speichern/Laden exakt, Neu-Analyse ueberlebt, kein Leck in die Smart-XML.
Pin-1 und das reale Export-Paritaets-Gate gegen die Ilka-Akte gruen."
```

---

### Gate B: Vertragsfreeze

- [ ] **Step 1: Briefing an Carl (über Max, als Codeblock im Chat)**

Inhalt: Commits je Task, Testzahlen vorher/nachher, Ergebnis des realen Paritäts-Gates gegen die Ilka-Akte, sowie jede Abweichung vom Plan, die beim Bauen nötig wurde — insbesondere, ob `_reconcile_marker_candidates` als Alias unter dem alten Namen `_bootstrap_clip_candidates` bleiben muss (`project_archive.py:314` ruft ihn per `hasattr`) oder ob die Aufrufstelle sauber mitgezogen wurde.

- [ ] **Step 2: Nach Carls Freigabe v6 auf alle Zweige**

```bash
cd ~/Desktop/MF/Vibecoding/PeakCut/App
git branch -f develop feature/redesign && git push origin develop
# main per --no-ff Marker-Commit, Max-Go abwarten (Konvention seit 26f8097)
```

Grund: Die v4/v5-Falle vom 17.08. darf sich nicht wiederholen — eine Akte in v6 wäre auf einem v5-Zweig nicht lesbar.

- [ ] **Step 3: Erst danach Producer**

Getrennt, je mit eigenem Entwurf: manueller Producer · Auto-Finder (Max' paralleles Werkzeug) · transkriptweiter Finder. **Zuletzt** die Review-Navigation von Peak-Index auf `candidate_id`.
