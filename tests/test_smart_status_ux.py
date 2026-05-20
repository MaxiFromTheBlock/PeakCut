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
