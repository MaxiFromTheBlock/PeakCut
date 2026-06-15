"""#3-Revision Task 8 / #76 — Smart-Statuszeile + Play-Verfügbarkeit.

Statuszeile (Spec §11 R5) unverändert. Der frühere Sinnabschnitt-▶-Knopf
ist mit #76 entfallen; _refresh_play_availability (hist. Name) steuert jetzt die
Play-Verfügbarkeit für den aktuellen Modus: in 'smart' disabled ohne
gültigen Kandidaten, in 'key'/'speak' bei vorhandener Quelle enabled.
Tests gegen Fake-Self, ohne echte Qt-Widgets.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402
from core.clip_candidates import ClipBoundary, PROPOSED  # noqa: E402


def _label():
    captured = {"text": None, "enabled": None, "tooltip": None}
    label = types.SimpleNamespace(
        setText=lambda t: captured.__setitem__("text", t))
    btn = types.SimpleNamespace(
        setEnabled=lambda b: captured.__setitem__("enabled", b),
        setToolTip=lambda t: captured.__setitem__("tooltip", t))
    return label, btn, captured


def _fs(*, transcript=None, transcript_ref=None, transcript_error=None,
        peaks=None, current_peak=0, candidates=None, smart_worker=None,
        smart_ready=False, smart_status_text="", mode="key"):
    label, btn, cap = _label()
    ns = types.SimpleNamespace()
    cfg = {"smart_boundary_alignment_tolerance_ms": 120000,
           "preview_duration_ms": 1000}
    ns.session = types.SimpleNamespace(
        config=cfg, mode=mode,
        peaks=peaks if peaks is not None else [],
        current_peak=current_peak,
        transcript=transcript, transcript_ref=transcript_ref,
        transcript_error=transcript_error,
        clip_candidates=candidates if candidates is not None else [])
    ns.smart_status_label = label
    ns.play_btn = btn
    ns._smart_worker = smart_worker
    ns._smart_ready = smart_ready
    ns._smart_status_text = smart_status_text
    return ns, cap


def _peak(idx):
    return types.SimpleNamespace(index=idx, position_ms=idx * 1000,
                                 in_point_ms=idx * 1000,
                                 out_point_ms=idx * 1000 + 30000,
                                 ignored=False)


def _cand(peak_id, score=None):
    return types.SimpleNamespace(
        peak_id=peak_id, score=score, status=PROPOSED,
        boundary=ClipBoundary(start_ms=peak_id * 1000,
                              end_ms=peak_id * 1000 + 40000))


# --- Statuszeile: 5 Zustände aus Carls Plan (unverändert) --------------

def test_status_transkription_laeuft_when_nothing_yet():
    fs, cap = _fs()
    ReviewPage._refresh_smart_status(fs)
    assert "Transkription läuft" in cap["text"]


def test_status_transkript_bereit_berechne_sinnabschnitte():
    fs, cap = _fs(transcript="T", smart_worker=types.SimpleNamespace())
    ReviewPage._refresh_smart_status(fs)
    assert "berechne Sinnabschnitte" in cap["text"]


def test_status_sinnabschnitte_bereit_with_count():
    fs, cap = _fs(transcript="T", smart_ready=True,
                   candidates=[_cand(1, 0.8), _cand(2, 0.0),
                               _cand(3, None)])
    ReviewPage._refresh_smart_status(fs)
    assert "Sinnabschnitte bereit (2)" in cap["text"]


def test_status_infra_message_visible():
    fs, cap = _fs(transcript="T",
                   smart_status_text="Sinnabschnitte nicht berechnet: "
                                     "API-Key ungültig")
    ReviewPage._refresh_smart_status(fs)
    assert "API-Key ungültig" in cap["text"]


def test_status_drift_visible_from_ref():
    fs, cap = _fs(transcript=None,
                   transcript_ref={"path": "x",
                                    "transcript_span_ms": 600_000,
                                    "audio_duration_ms": 4_200_000})
    ReviewPage._refresh_smart_status(fs)
    assert "passt nicht zur Audiodauer" in cap["text"]


def test_status_ready_with_drift_combines_not_silences():
    fs, cap = _fs(transcript="T", smart_ready=True,
                   candidates=[_cand(1, 0.8)],
                   transcript_ref={"path": "x",
                                    "transcript_span_ms": 600_000,
                                    "audio_duration_ms": 4_200_000})
    ReviewPage._refresh_smart_status(fs)
    assert "bereit" in cap["text"].lower()
    assert "passt nicht" in cap["text"].lower() \
        or "transkript-länge" in cap["text"].lower()


def test_status_transkript_error_visible():
    fs, cap = _fs(transcript=None,
                   transcript_ref={"path": "x"},
                   transcript_error="Sidecar kaputt")
    ReviewPage._refresh_smart_status(fs)
    assert "Transkript" in cap["text"] and (
        "kaputt" in cap["text"] or "fehlt" in cap["text"])


# --- Play-Verfügbarkeit (#76, modusbasiert) ---------------------------

def test_play_enabled_in_smart_mode_with_candidate():
    fs, cap = _fs(mode="smart", peaks=[_peak(1), _peak(2)], current_peak=0,
                   candidates=[_cand(1, 0.8), _cand(2, None)],
                   smart_ready=True)
    ReviewPage._refresh_play_availability(fs)
    assert cap["enabled"] is True


def test_play_disabled_in_smart_mode_without_candidate():
    fs, cap = _fs(mode="smart", peaks=[_peak(1), _peak(2)], current_peak=1,
                   candidates=[_cand(1, 0.8), _cand(2, None)],
                   smart_ready=True)
    ReviewPage._refresh_play_availability(fs)
    assert cap["enabled"] is False
    assert "sinnabschnitt" in cap["tooltip"].lower() \
        or "drücker" in cap["tooltip"].lower()


def test_play_enabled_in_key_mode():
    fs, cap = _fs(mode="key", peaks=[_peak(1)], current_peak=0)
    ReviewPage._refresh_play_availability(fs)
    assert cap["enabled"] is True


def test_play_enabled_in_speak_mode():
    fs, cap = _fs(mode="speak", peaks=[_peak(1)], current_peak=0)
    ReviewPage._refresh_play_availability(fs)
    assert cap["enabled"] is True


def test_play_disabled_when_no_peak_selected():
    fs, cap = _fs(peaks=[])
    ReviewPage._refresh_play_availability(fs)
    assert cap["enabled"] is False


# --- Carl-Gegenreview ---------------------------------------------------

def test_on_smart_done_infra_with_running_worker_shows_infra_message():
    from core.clip_boundary.models import (
        SmartBoundaryRunResult, BoundaryOutcome)
    fs, cap = _fs(transcript="T")
    fs._refresh_smart_status = lambda: ReviewPage._refresh_smart_status(fs)
    fs._refresh_play_availability = lambda: ReviewPage._refresh_play_availability(fs)
    fs._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(fs)
    fs._smart_worker = types.SimpleNamespace(deleteLater=lambda: None)
    fs.status_message = types.SimpleNamespace(emit=lambda *a: None)
    fs.session_changed = types.SimpleNamespace(emit=lambda *a: None)
    fs._base_export_done_for_run = False
    fs._sinnabschnitt_artifacts_written = False
    res = SmartBoundaryRunResult(
        (), BoundaryOutcome.INFRA_FEHLT, "API-Key ungültig", 0, 0)
    ReviewPage._on_smart_boundaries_done(fs, res)
    assert "ungültig" in cap["text"].lower()


def test_persisted_scores_refresh_status_and_button_immediately():
    fs, cap = _fs(transcript="T", peaks=[_peak(1), _peak(2)],
                   current_peak=1, mode="smart",
                   candidates=[_cand(1, 0.8), _cand(2, None)])
    fs.session.config = {"smart_boundary_enabled": True,
                          "smart_boundary_claude_model": "m",
                          "preview_duration_ms": 1000}
    fs._refresh_smart_status = lambda: ReviewPage._refresh_smart_status(fs)
    fs._refresh_play_availability = lambda: ReviewPage._refresh_play_availability(fs)
    fs._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(fs)
    fs._base_export_done_for_run = False
    fs._sinnabschnitt_artifacts_written = False
    ReviewPage._maybe_start_smart_worker(fs)
    assert "bereit" in cap["text"].lower()
    assert cap["enabled"] is False          # Peak 2 (smart) ohne Kandidat


def test_set_session_clears_sticky_infra_status():
    label, btn, cap = _label()
    fs = types.SimpleNamespace(
        camera_combo=types.SimpleNamespace(
            clear=lambda: None, addItem=lambda *a, **kw: None),
        video_preview=types.SimpleNamespace(
            set_videos=lambda v: None, set_session=lambda s: None,
            screenshot_done=types.SimpleNamespace(connect=lambda cb: None)),
        _populate_lut_combo=lambda: None,
        _maybe_start_smart_worker=lambda: None,
        _refresh_smart_status=lambda: None,
        _refresh_play_availability=lambda: None,
        smart_status_label=label, play_btn=btn,
        mode_btn=types.SimpleNamespace(setText=lambda t: None),
        _smart_status_text="alte INFRA-Meldung",
        _base_export_done_for_run=True, _smart_ready=True,
        _sinnabschnitt_artifacts_written=True)
    session = types.SimpleNamespace(folgenschnitt_camera_assignments=[],
                                    mode="key")
    ReviewPage.set_session(fs, session, [])
    assert fs._smart_status_text == ""
