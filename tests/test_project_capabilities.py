"""Contract-Slice (Carl): capability-driven Import. Wahrheit = bestaetigte Rollen
(ConfirmedImportSlots); daraus leitet compute_capabilities ab, welche Outputs moeglich
sind — pro Feature ein eigenes Minimum, NICHTS global Pflicht. UI + Engine lesen denselben
Vertrag (enabled / missing / warnings / evidence). Reine Daten, keine UI, kein Export.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from core.import_model import ConfirmedImportSlots
from core.project_capabilities import (
    compute_capabilities,
    CAP_SCREENSHOTS,
    CAP_KEYBOARDSTELLEN,
    CAP_FOLGENSCHNITT,
    CAP_SINNABSCHNITTE,
)


def test_full_material_enables_everything():
    slots = ConfirmedImportSlots(
        marker="MIC4.wav", mix="P8Mix.wav", mics=("MIC1.wav", "MIC2.wav"),
        videos=("Cam01.mp4", "Cam02.mp4"), transcript="t.json",
    )
    caps = compute_capabilities(slots)
    for name in (CAP_SCREENSHOTS, CAP_KEYBOARDSTELLEN, CAP_FOLGENSCHNITT, CAP_SINNABSCHNITTE):
        assert caps.enabled(name), name
    # voll versorgt -> keine Warnungen
    assert caps.get(CAP_FOLGENSCHNITT).warnings == ()
    assert caps.get(CAP_SINNABSCHNITTE).warnings == ()


def test_no_marker_disables_only_keyboardstellen():
    # Max-Kernpunkt: ohne Marker gibt es trotzdem Folgenschnitt + Screenshots (+ Sinnabschnitte)
    slots = ConfirmedImportSlots(
        marker=None, mix="P8Mix.wav", mics=("MIC1.wav",), videos=("Cam01.mp4",), transcript="t.json",
    )
    caps = compute_capabilities(slots)
    assert caps.enabled(CAP_SCREENSHOTS)
    assert caps.enabled(CAP_FOLGENSCHNITT)
    assert caps.enabled(CAP_SINNABSCHNITTE)
    assert not caps.enabled(CAP_KEYBOARDSTELLEN)
    assert "Marker" in caps.get(CAP_KEYBOARDSTELLEN).missing


def test_single_video_only_enables_just_screenshots():
    # Externer Minimal-Fall: nur 1 Video -> Screenshots gehen, sonst nichts (ehrlich blockfrei)
    caps = compute_capabilities(ConfirmedImportSlots(videos=("Cam01.mp4",)))
    assert caps.enabled(CAP_SCREENSHOTS)
    assert not caps.enabled(CAP_KEYBOARDSTELLEN)
    assert not caps.enabled(CAP_FOLGENSCHNITT)   # kein Sprach-Ton
    assert not caps.enabled(CAP_SINNABSCHNITTE)  # kein Sprach-Ton
    assert "Sprach-Ton" in caps.get(CAP_SINNABSCHNITTE).missing


def test_mics_without_mix_enables_with_warning():
    # Mix ist OPTIONAL: Folgenschnitt/Sinnabschnitte gehen ueber echte Mics, mit Hinweis.
    slots = ConfirmedImportSlots(
        mics=("MIC1.wav", "MIC2.wav"), videos=("Cam01.mp4",),  # kein Mix, kein Marker, kein Transkript
    )
    caps = compute_capabilities(slots)
    assert caps.enabled(CAP_FOLGENSCHNITT)
    assert any("Mix" in w for w in caps.get(CAP_FOLGENSCHNITT).warnings)  # "kein Mix -> Mics-Fallback"
    assert caps.enabled(CAP_SINNABSCHNITTE)
    assert any("Transkript" in w for w in caps.get(CAP_SINNABSCHNITTE).warnings)  # noch kein Transkript
    assert not caps.enabled(CAP_KEYBOARDSTELLEN)


def test_empty_material_enables_nothing():
    caps = compute_capabilities(ConfirmedImportSlots())
    for name in (CAP_SCREENSHOTS, CAP_KEYBOARDSTELLEN, CAP_FOLGENSCHNITT, CAP_SINNABSCHNITTE):
        assert not caps.enabled(name), name
    assert "Video" in caps.get(CAP_SCREENSHOTS).missing


def test_capabilities_are_serializable_same_contract_for_ui_and_engine():
    # UI + Engine lesen denselben Vertrag -> muss als plain dict ueber die Bruecke gehen.
    caps = compute_capabilities(ConfirmedImportSlots(videos=("v.mp4",)))
    d = caps.as_dict()
    assert d[CAP_SCREENSHOTS]["enabled"] is True
    assert set(d[CAP_KEYBOARDSTELLEN].keys()) == {"enabled", "missing", "warnings", "evidence"}
    import json
    json.dumps(d)  # serialisierbar
