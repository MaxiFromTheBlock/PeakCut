"""Task 3 — ein auto-Kandidat mit kollidierender Legacy-peak_id darf NIRGENDS
als Marker-Kandidat durchschlagen. Fuenf Pfade (Carl 2026-08-19)."""
import pytest

from core.candidate_view import (
    marker_candidate_for_peak, marker_candidates_by_peak_id)
from core.clip_candidates import (
    ClipBoundary, ClipCandidate, ClipCandidateError, ORIGIN_AUTO, ORIGIN_MARKER)
from tests.test_candidate_baseline_lock import make_session_with_peaks

COLLIDING_PEAK_ID = 0


def _session_with_collision(*, intruder_first=False):
    """auto-Kandidat traegt absichtlich dieselbe peak_id wie ein aktiver Peak.

    intruder_first steuert die Listenposition. Die fuenf alten blinden Joins
    reagieren NICHT alle auf dieselbe Kollisions-Richtung: next()/enumerate-
    basierte Joins (playback_windows.py, session.ignore_peak) picken den
    ERSTEN Treffer -> die Kollision muss VOR dem Marker stehen, um den alten
    Bug wirklich auszuloesen. Die Dict-Comprehension in clip_boundary/
    pipeline.py (`{c.peak_id: i for i, c in enumerate(cands)}`) picken den
    LETZTEN Treffer -> dort muss die Kollision NACH dem Marker stehen. Ohne
    diese Unterscheidung waeren manche Gegenproben grün, obwohl der alte Bug
    in diesem konkreten Aufbau (Marker zufaellig zuerst in der Liste) gar
    nicht ausgeloest wird."""
    session = make_session_with_peaks([60_000])
    intruder = ClipCandidate(
        candidate_id="auto:kollision", origin=ORIGIN_AUTO, anchor_ms=61_000,
        peak_id=COLLIDING_PEAK_ID, boundary=ClipBoundary(55_000, 65_000),
        score=0.99, reason="Eindringling")
    if intruder_first:
        session.clip_candidates.insert(0, intruder)
    else:
        session.clip_candidates.append(intruder)
    return session


def _session_with_marker_marker_collision():
    """Zwei ECHTE Marker-Kandidaten auf demselben peak_id (nicht ein
    auto-Eindringling) -- der Fall, der marker_candidates_by_peak_id selbst
    zum Werfen bringt (Fix-Runde-1-Szenario fuer Befund 1+2)."""
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(ClipCandidate(
        candidate_id="marker:0:dublette", origin=ORIGIN_MARKER, anchor_ms=60_000,
        peak_id=0, boundary=ClipBoundary(45_000, 75_000)))
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
    session = _session_with_collision(intruder_first=True)
    win = build_playback_window(session, PLAYBACK_MODE_SMART, peak_index=0)
    assert (win.start_ms, win.end_ms) != (55_000, 65_000), \
        "Smart-Fenster kam vom kollidierenden auto-Kandidaten"


def test_pfad_smart_xml_nimmt_den_eindringling_nicht_auf():
    from core.xml_sequence_helpers import active_smart_candidates
    session = _session_with_collision()
    ids = {c.candidate_id for _, c in active_smart_candidates(session)}
    assert "auto:kollision" not in ids


def test_pfad_ignorieren_trifft_den_marker_kandidaten():
    session = _session_with_collision(intruder_first=True)
    session.set_current_peak(0)
    session.ignore_peak()
    intruder = next(c for c in session.clip_candidates
                    if c.candidate_id == "auto:kollision")
    marker = next(c for c in session.clip_candidates
                  if c.candidate_id == "marker:0")
    assert marker.status == "discarded"
    assert intruder.status == "proposed", "Ignorieren traf den falschen Kandidaten"


def test_pfad_grenzen_pipeline_aktualisiert_den_marker_nicht_den_eindringling():
    """Fuenfter Pfad: clip_boundary/pipeline.py baut `by_id` peak_id -> Index
    in `cands` und schreibt die Decider-Boundary dort rein. Bei einer Dict-
    Comprehension ueber die blanke Liste gewinnt der zuletzt gesehene
    Kandidat mit dieser peak_id -- hier der Eindringling statt des Markers."""
    from core.clip_boundary.pipeline import prepare_smart_boundaries
    from core.clip_boundary.models import BoundaryDecision
    from core.transcription import Transcript, TranscriptSegment

    session = _session_with_collision()
    session.speaker_activity = []
    session.transcript = Transcript(segments=(
        TranscriptSegment(0, 700_000, "langer Gespraechsabschnitt"),))

    class _GoodDecider:
        def decide(self, scaffold):
            return BoundaryDecision(
                scaffold.window_start_ms, scaffold.window_end_ms, "ok", 0.9)

    cfg = {
        "fps": 25, "context_duration_ms": 15000,
        "smart_boundary_min_duration_ms": 12000,
        "smart_boundary_max_duration_ms": 180000,
        "smart_boundary_confidence_threshold": 0.5,
        "smart_boundary_fallback_before_ms": 45000,
        "smart_boundary_fallback_after_ms": 30000,
        "smart_boundary_snap_tolerance_ms": 1500,
        "smart_boundary_search_before_ms": 180000,
        "smart_boundary_search_after_ms": 60000,
        "smart_boundary_sentence_gap_ms": 900,
    }
    prepare_smart_boundaries(session, _GoodDecider(), config=cfg)

    marker = next(c for c in session.clip_candidates
                  if c.candidate_id == "marker:0")
    intruder = next(c for c in session.clip_candidates
                    if c.candidate_id == "auto:kollision")
    assert marker.reason == "ok", \
        "Decider-Ergebnis landete nicht beim Marker-Kandidaten"
    assert intruder.reason == "Eindringling", \
        "Grenzen-Pipeline hat den Eindringling statt des Markers aktualisiert"
    assert intruder.boundary.start_ms == 55_000
    assert intruder.boundary.end_ms == 65_000


def test_pfad_ignorieren_bei_kollision_laesst_peak_unveraendert():
    """Fix-Runde 1, Pruefer-Befund 1: session.py:188 setzte peak.ignored=True
    VOR dem Lookup ueber die Sicht. Wirft marker_candidate_for_peak
    (doppelte Marker-Zuordnung auf denselben Peak), blieb der Peak bisher
    trotzdem ignoriert, obwohl kein Kandidat verworfen und keine Decision
    geschrieben wurde -- halb-mutierter Zustand. Widerspricht demselben
    Grundsatz, den session.py:124-126 (Reconcile) schon festschreibt: der
    Fehler muss fliegen, BEVOR etwas veraendert wurde. Im Web-Repo bleibt
    ohne diesen Fix zusaetzlich die gecachte Sitzung (with_project_session)
    dauerhaft halb mutiert im RAM stehen (kein Save, keine Cache-Raeumung
    ausserhalb des Save-Fehlerzweigs)."""
    session = _session_with_marker_marker_collision()
    session.set_current_peak(0)
    candidates_before = list(session.clip_candidates)
    with pytest.raises(ClipCandidateError):
        session.ignore_peak()
    assert session.peaks[0].ignored is False, \
        "Peak blieb ignoriert, obwohl ignore_peak() fehlgeschlagen ist"
    assert session.clip_candidates == candidates_before, \
        "Kandidatenliste wurde trotz Fehler veraendert"
    assert session.peak_decisions == [], \
        "Decision wurde trotz Fehler geschrieben"


def test_pfad_playback_faengt_kollisionsfehler_ab_statt_qt_crash():
    """Fix-Runde 1, Pruefer-Befund 2: build_playback_window kann seit Task 3
    ClipCandidateError werfen (marker_candidate_for_peak). Die Aufrufer sind
    ungeschuetzte Qt-Slots (review_page.on_play, _refresh_play_availability)
    ohne sys.excepthook -- PyQt6 killt den Prozess bei einer unbehandelten
    Slot-Exception (SIGABRT). build_playback_window muss den Fehler HIER
    kontrolliert als disabled_reason melden statt ihn bis zur Qt-Grenze
    durchzureichen."""
    from core.playback_modes import PLAYBACK_MODE_SMART
    from core.playback_windows import build_playback_window
    session = _session_with_marker_marker_collision()
    win = build_playback_window(session, PLAYBACK_MODE_SMART, peak_index=0)
    assert win.disabled, "Kollisionsfehler haette abgefangen werden muessen"
    assert win.disabled_reason, "kein verstaendlicher Grund fuer den Nutzer"
