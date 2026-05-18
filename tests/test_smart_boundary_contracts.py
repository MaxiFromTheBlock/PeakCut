"""Roadmap #3 Gate A — Datenverträge einfrieren (Carl-Finalplan).

STOPP-Gate: Nach Freigabe nicht mehr an diesen Contracts drehen.
Reine Datenmodelle + Protocols. Kein Worker, kein Scaffold-/Decider-
Logik, keine Pipeline (= spätere Tasks/Gates).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.transcription import (  # noqa: E402
    TranscriptWord, TranscriptSegment, Transcript,
    TranscriptionEngine, TranscriptError,
)
from core.clip_boundary.models import (  # noqa: E402
    BoundarySnapCandidate, BoundaryScaffold, BoundaryDecision,
    BoundaryDecider, BoundaryError,
)


# --- Transcript-Verträge --------------------------------------------------

def test_transcript_word_validation():
    TranscriptWord(0, 1, "hi")  # ok
    for bad in ((5, 5, "x"), (4, 1, "x"), (-1, 10, "x")):
        try:
            TranscriptWord(*bad)
            assert False, f"ungueltig muss abgelehnt werden: {bad}"
        except ValueError:
            pass


def test_transcript_roundtrip_exact():
    w1 = TranscriptWord(1000, 1200, "Das")
    w2 = TranscriptWord(1200, 1500, "System")
    seg = TranscriptSegment(1000, 1500, "Das System", words=(w1, w2))
    t = Transcript(segments=(seg,))
    assert TranscriptWord.from_dict(w1.to_dict()) == w1
    assert TranscriptSegment.from_dict(seg.to_dict()) == seg
    assert Transcript.from_dict(t.to_dict()) == t
    # leeres Transcript ist gültig (kein Sprachinhalt -> Müll-Drücker)
    empty = Transcript()
    assert Transcript.from_dict(empty.to_dict()) == empty
    assert empty.segments == ()


def test_transcript_segment_words_optional_and_tuple():
    seg = TranscriptSegment(0, 100, "nur Segment")
    assert seg.words == ()
    assert TranscriptSegment.from_dict(seg.to_dict()) == seg


def test_transcription_engine_protocol_is_runtime_checkable():
    class FakeEngine:
        def transcribe(self, audio_path, *, language, model):
            return Transcript()

    assert isinstance(FakeEngine(), TranscriptionEngine)
    assert not isinstance(object(), TranscriptionEngine)


def test_transcript_error_exists():
    assert issubclass(TranscriptError, Exception)


# --- Clip-Boundary-Verträge ----------------------------------------------

def test_snap_candidate_validation():
    BoundarySnapCandidate(0, "sentence_end")  # ok
    BoundarySnapCandidate(5000, "pause", label="nach Frage")  # ok
    for bad in ((-1, "pause"), (100, "")):
        try:
            BoundarySnapCandidate(*bad)
            assert False, f"ungueltig: {bad}"
        except ValueError:
            pass


def test_scaffold_validation_peak_in_window():
    BoundaryScaffold(peak_id=3, peak_ms=60000,
                     window_start_ms=0, window_end_ms=120000)  # ok
    # window_end <= window_start
    try:
        BoundaryScaffold(peak_id=1, peak_ms=10, window_start_ms=50,
                         window_end_ms=50)
        assert False
    except ValueError:
        pass
    # Peak ausserhalb des Fensters
    try:
        BoundaryScaffold(peak_id=1, peak_ms=999999,
                         window_start_ms=0, window_end_ms=1000)
        assert False, "Peak ausserhalb Fenster muss abgelehnt werden"
    except ValueError:
        pass


def test_scaffold_roundtrip_exact():
    sc = BoundaryScaffold(
        peak_id=7, peak_ms=60000, window_start_ms=0, window_end_ms=180000,
        transcript_excerpt="… Text mit [PEAK] Markierung …",
        snap_candidates=(BoundarySnapCandidate(1000, "sentence_end"),
                         BoundarySnapCandidate(2000, "pause", "x")))
    assert BoundaryScaffold.from_dict(sc.to_dict()) == sc


def test_boundary_decision_validation_and_roundtrip():
    d = BoundaryDecision(123000, 171000, "Frage bis Pointe", 0.74)
    assert BoundaryDecision.from_dict(d.to_dict()) == d
    for bad in ((100, 100, "x", 0.5), (200, 100, "x", 0.5),
                (-1, 10, "x", 0.5),
                (0, 10, "x", -0.1), (0, 10, "x", 1.1)):
        try:
            BoundaryDecision(*bad)
            assert False, f"ungueltig: {bad}"
        except ValueError:
            pass


def test_boundary_decider_protocol_is_runtime_checkable():
    class FakeDecider:
        def decide(self, scaffold):
            return BoundaryDecision(0, 1, "stub", 0.0)

    assert isinstance(FakeDecider(), BoundaryDecider)
    assert not isinstance(object(), BoundaryDecider)


def test_boundary_error_exists():
    assert issubclass(BoundaryError, Exception)
