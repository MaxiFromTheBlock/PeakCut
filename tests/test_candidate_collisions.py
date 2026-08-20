"""Task 3 — ein auto-Kandidat mit kollidierender Legacy-peak_id darf NIRGENDS
als Marker-Kandidat durchschlagen. Fuenf Pfade (Carl 2026-08-19).

ZWEITE VERTEIDIGUNGSLINIE (Gate B / A3, 2026-08-21): seit die Invarianten im
`__post_init__` von ClipCandidate sitzen, lassen sich die Kandidaten dieser
Datei nicht mehr regulaer bauen — die Kollision ist an der Wurzel geschlossen.
Diese Tests bleiben trotzdem bestehen und arbeiten ab jetzt mit ABSICHTLICH
UNGUELTIGEN Objekten (`tests/malformed_candidates.malformed_candidate`, baut
per object.__setattr__ am Konstruktor vorbei). Carl woertlich: „Die zentrale
Marker-Sicht bleibt trotzdem als Defense-in-Depth bestehen. Die
Kollisionspruefungen koennen mit absichtlich malformed Testobjekten weiter
beweisen, dass die Verbraucher robust bleiben." Genau darum geht es hier:
solche Daten koennen weiterhin von aussen kommen (handeditierte/beschaedigte
.peakcut-Akte, aelterer Schreiber, Schwester-Repo) — die Verbraucher duerfen
daran nicht zerbrechen.
"""
import pytest

from core.candidate_view import (
    marker_candidate_for_peak, marker_candidates_by_peak_id)
from core.clip_candidates import (
    ClipBoundary, ClipCandidateError, ORIGIN_AUTO, ORIGIN_MARKER)
from tests.malformed_candidates import malformed_candidate
from tests.test_candidate_baseline_lock import make_session_with_peaks

COLLIDING_PEAK_ID = 0


def _session_with_collision(*, intruder_first=False):
    """auto-Kandidat traegt absichtlich dieselbe peak_id wie ein aktiver Peak.

    UNGUELTIG per A3 (origin != marker ⇒ peak_id muss None sein) — bewusst am
    Konstruktor vorbei gebaut, s. Modul-Docstring.

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
    intruder = malformed_candidate(
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
    zum Werfen bringt (Fix-Runde-1-Szenario fuer Befund 1+2).

    UNGUELTIG per A3 (origin == marker ⇒ candidate_id == marker:<peak_id>) --
    bewusst am Konstruktor vorbei gebaut, s. Modul-Docstring. Die abweichende
    ID ist hier notwendig: mit zwei mal exakt "marker:0" wuerde der Test nicht
    mehr die peak_id-Doppelzuordnung pruefen, sondern die ID-Dublette."""
    session = make_session_with_peaks([60_000])
    session.clip_candidates.append(malformed_candidate(
        candidate_id="marker:0:dublette", origin=ORIGIN_MARKER, anchor_ms=60_000,
        peak_id=0, boundary=ClipBoundary(45_000, 75_000)))
    return session


def test_sicht_liefert_nur_den_marker_kandidaten():
    session = _session_with_collision()
    cand = marker_candidate_for_peak(session, COLLIDING_PEAK_ID)
    assert cand.candidate_id == "marker:0"
    assert cand.origin == ORIGIN_MARKER


def test_sicht_schlaegt_bei_doppelter_marker_zuordnung_fehl():
    session = _session_with_marker_marker_collision()
    with pytest.raises(ClipCandidateError):
        marker_candidates_by_peak_id(session)


def test_pfad_playback_spielt_nicht_das_fremdfenster():
    """Pruefer-Befund (Mutationstest, Fix-Runde 2): die alte Fassung pruefte
    nur "!= Eindringling-Fenster (55_000, 65_000)". Das blieb auch dann wahr,
    wenn die Herkunfts-Pruefung in candidate_view.py:18 entfernt wird -- der
    Fix aus Task 3 uebersetzt einen Kollisionsfehler in ein disabled-Fenster
    (0, 0), und der Marker-Kandidat hat hier ohnehin (ohne Score) ein
    disabled (0, 0)-Fenster -> (0, 0) != (55_000, 65_000) ist auch OHNE
    Filter wahr, der Test war stumm. Score gesetzt macht den Marker-Pfad
    ECHT enabled + pruefbar; die Zusicherung ist jetzt POSITIV: das Fenster
    muss GENAU der Boundary des MARKER-Kandidaten entsprechen."""
    from dataclasses import replace
    from core.playback_modes import PLAYBACK_MODE_SMART
    from core.playback_windows import build_playback_window
    session = _session_with_collision(intruder_first=True)
    marker = next(c for c in session.clip_candidates
                  if c.candidate_id == "marker:0")
    session.clip_candidates[session.clip_candidates.index(marker)] = \
        replace(marker, score=0.9)
    win = build_playback_window(session, PLAYBACK_MODE_SMART, peak_index=0)
    assert (win.start_ms, win.end_ms) == \
        (marker.boundary.start_ms, marker.boundary.end_ms), \
        "Smart-Fenster muss die Boundary des MARKER-Kandidaten sein, " \
        "nicht (0,0) oder die des Eindringlings"


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


def test_pfad_on_ignore_faengt_kollisionsfehler_ab_statt_qt_crash():
    """Zweiter Absturzweg (Fix-Runde 2): session.ignore_peak() kann seit
    Task 3 ClipCandidateError werfen (marker_candidate_for_peak, doppelte
    Marker-Zuordnung auf denselben Peak) -- session.py laesst den Fehler
    BEWUSST durchfliegen (siehe test_pfad_ignorieren_bei_kollision_
    laesst_peak_unveraendert oben: der Fehler muss fliegen, BEVOR etwas
    veraendert wurde). review_page.on_ignore ist aber ein ungeschuetzter
    Qt-Slot ohne sys.excepthook -- PyQt6 killt den Prozess bei einer
    unbehandelten Slot-Exception (SIGABRT), fuer build_playback_window
    schon gefangen (Test oben), fuer ignore_peak bisher nicht. on_ignore
    muss den Fehler HIER kontrolliert als Statuszeile melden statt ihn
    bis zur Qt-Grenze durchzureichen."""
    import types
    from gui.review_page import ReviewPage

    session = _session_with_marker_marker_collision()
    session.set_current_peak(0)

    class _Sig:
        def __init__(self):
            self.messages = []

        def emit(self, msg):
            self.messages.append(msg)

        def connect(self, _cb):
            pass

    navigated = []
    fake_self = types.SimpleNamespace(
        session=session,
        status_message=_Sig(),
        session_changed=_Sig(),
        navigate_to_peak=lambda idx: navigated.append(idx))

    ReviewPage.on_ignore(fake_self)   # darf NICHT raisen (kein SIGABRT)

    assert fake_self.status_message.messages, \
        "kein verstaendlicher Hinweis fuer den Nutzer"
    assert session.peaks[0].ignored is False, \
        "Peak-Mutation trotz fehlgeschlagenem Ignorieren"
    assert navigated == [], "Navigation trotz fehlgeschlagenem Ignorieren"
    assert fake_self.session_changed.messages == [], \
        "session_changed trotz fehlgeschlagenem Ignorieren"
