"""#3-Revision Task 8 — Smart-Statuszeile + Sinnabschnitt-Knopf-Gate.

Spec §11 R5, Carl Task 8: eine durchgängige Smart-Statuszeile im
Review zeigt den aktuellen Zustand, der Sinnabschnitt-▶-Knopf ist
disabled mit Tooltip, solange für den aktuellen Drücker kein
Kandidat mit score is not None vorliegt. Tests gegen Fake-Self,
ohne echte Qt-Widgets.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gui.review_page import ReviewPage  # noqa: E402


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
        smart_ready=False, smart_status_text=""):
    label, btn, cap = _label()
    ns = types.SimpleNamespace()
    cfg = {"smart_boundary_alignment_tolerance_ms": 120000}
    ns.session = types.SimpleNamespace(
        config=cfg,
        peaks=peaks if peaks is not None else [],
        current_peak=current_peak,
        transcript=transcript, transcript_ref=transcript_ref,
        transcript_error=transcript_error,
        clip_candidates=candidates if candidates is not None else [])
    ns.smart_status_label = label
    ns.sinn_btn = btn
    ns._smart_worker = smart_worker
    ns._smart_ready = smart_ready
    ns._smart_status_text = smart_status_text
    return ns, cap


def _peak(idx):
    return types.SimpleNamespace(index=idx, position_ms=idx * 1000)


def _cand(peak_id, score=None):
    return types.SimpleNamespace(peak_id=peak_id, score=score)


# --- Statuszeile: 5 Zustände aus Carls Plan ----------------------------

def test_status_transkription_laeuft_when_nothing_yet():
    fs, cap = _fs()                            # nichts da
    ReviewPage._refresh_smart_status(fs)
    assert "Transkription läuft" in cap["text"]


def test_status_transkript_bereit_berechne_sinnabschnitte():
    fs, cap = _fs(transcript="T",
                   smart_worker=types.SimpleNamespace())     # läuft
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
    # Carl-Gegenreview [P2]: Drift darf "bereit" nicht ganz untergehen.
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


# --- Sinnabschnitt-▶-Knopf: enabled bei Treffer für aktuellen Peak ----

def test_button_enabled_when_current_peak_has_score():
    fs, cap = _fs(peaks=[_peak(1), _peak(2)], current_peak=0,
                   candidates=[_cand(1, 0.8), _cand(2, None)],
                   smart_ready=True)
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is True
    assert cap["tooltip"]                            # nicht leer


def test_button_disabled_when_current_peak_lacks_score():
    fs, cap = _fs(peaks=[_peak(1), _peak(2)], current_peak=1,
                   candidates=[_cand(1, 0.8), _cand(2, None)],
                   smart_ready=True)
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is False
    assert "kein Sinnabschnitt" in cap["tooltip"].lower() \
        or "diesen drücker" in cap["tooltip"].lower()


def test_button_disabled_during_smart_run_with_reason_tooltip():
    fs, cap = _fs(peaks=[_peak(1)], candidates=[_cand(1, None)],
                   smart_worker=types.SimpleNamespace())
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is False
    assert "berechn" in cap["tooltip"].lower()


def test_button_disabled_without_transcript_with_reason():
    fs, cap = _fs(peaks=[_peak(1)], candidates=[_cand(1, None)])
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is False
    assert "transkri" in cap["tooltip"].lower()


def test_button_disabled_when_transcript_error_with_reason():
    fs, cap = _fs(peaks=[_peak(1)], candidates=[_cand(1, None)],
                   transcript_ref={"path": "x"},
                   transcript_error="Sidecar kaputt")
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is False
    assert "transkri" in cap["tooltip"].lower()


def test_button_disabled_when_no_peak_selected():
    fs, cap = _fs(peaks=[])
    ReviewPage._refresh_sinn_btn(fs)
    assert cap["enabled"] is False


# --- Carl-Gegenreview ---------------------------------------------------

def test_on_smart_done_infra_with_running_worker_shows_infra_message():
    # [P2] Bei INFRA war der _smart_worker noch gesetzt, deshalb
    # gewann "berechne…"; nach Cleanup muss die INFRA-Meldung
    # tatsächlich in der Statuszeile stehen.
    from core.clip_boundary.models import (
        SmartBoundaryRunResult, BoundaryOutcome)
    fs, cap = _fs(transcript="T")
    fs._refresh_smart_status = lambda: ReviewPage._refresh_smart_status(fs)
    fs._refresh_sinn_btn = lambda: ReviewPage._refresh_sinn_btn(fs)
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
    # [P3] Score-Guard öffnete den Riegel ohne Refresh -> Tooltip blieb
    # für nicht-aktuellen Peak bis zum Peak-Wechsel auf "steht noch
    # nicht zur Verfügung". Jetzt soll der Refresh sofort laufen.
    fs, cap = _fs(transcript="T", peaks=[_peak(1), _peak(2)],
                   current_peak=1,
                   candidates=[_cand(1, 0.8), _cand(2, None)])
    fs.session.config = {"smart_boundary_enabled": True,
                          "smart_boundary_claude_model": "m"}
    fs._refresh_smart_status = lambda: ReviewPage._refresh_smart_status(fs)
    fs._refresh_sinn_btn = lambda: ReviewPage._refresh_sinn_btn(fs)
    fs._maybe_write_sinnabschnitt_artifacts = \
        lambda: ReviewPage._maybe_write_sinnabschnitt_artifacts(fs)
    fs._base_export_done_for_run = False
    fs._sinnabschnitt_artifacts_written = False
    ReviewPage._maybe_start_smart_worker(fs)
    assert "bereit" in cap["text"].lower()
    assert cap["enabled"] is False
    assert "diesen drücker" in cap["tooltip"].lower() \
        or "kein sinnabschnitt" in cap["tooltip"].lower()


def test_set_session_clears_sticky_infra_status():
    # [P3] set_session resettete die drei Riegel-Flags, aber NICHT
    # _smart_status_text — eine alte INFRA-Meldung konnte ohne
    # neuen Status durchscheinen.
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
        _refresh_sinn_btn=lambda: None,
        smart_status_label=label, sinn_btn=btn,
        _smart_status_text="alte INFRA-Meldung",
        _base_export_done_for_run=True, _smart_ready=True,
        _sinnabschnitt_artifacts_written=True)
    session = types.SimpleNamespace(folgenschnitt_camera_assignments=[])
    ReviewPage.set_session(fs, session, [])
    assert fs._smart_status_text == ""
