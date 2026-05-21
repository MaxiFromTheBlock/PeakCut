"""Task #72 — Reference-Track-Stabilität im XMLExporter.

Sheila-Smoke 2026-05-20 hat aufgedeckt: das Keyboardstellen-XML
unterscheidet sich zwischen zwei Läufen mit identischem Datei-Satz,
wenn die mic_tracks-Reihenfolge anders ist. Ursache: XMLExporter
nutzt `audio_paths[0]` (= mic_tracks[0]) als Audio-Probe-Quelle für
channelcount/sample_rate — abhängig davon, in welcher Reihenfolge
der User die Dateien im Import-Dialog ausgewählt hat.

SinnabschnittExporter macht's bereits richtig: `get_reference_track()
or mic_tracks[0]`. Diese Tests verriegeln dieselbe Semantik für
XMLExporter: deterministisch zuerst die 'mix'-Spur, dann mics[0] als
Fallback.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.exporters import XMLExporter  # noqa: E402
from core.project import PeakCutProject  # noqa: E402
from core.session import PeakCutSession  # noqa: E402


_BASE_CFG = {"fps": 25, "context_duration_ms": 15000}


def _session(tmp_path, mic_order):
    """Session mit Test-Material; mic_order steuert die Reihenfolge
    in der mic_tracks-Liste."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = PeakCutProject()
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "MIC mix.mp3", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    kb = str(tmp_path / "KB.wav")
    mics_by_name = {
        "MIC1": str(tmp_path / "MIC1.wav"),
        "MIC2": str(tmp_path / "MIC2.wav"),
        "MIX":  str(tmp_path / "MIC mix.mp3"),
    }
    mics = [mics_by_name[n] for n in mic_order]
    vids = [str(tmp_path / "CAM.mp4")]
    p.set_files(kb, mics, vids)
    p.guest_name = "TestGast"
    p.export_dir = str(tmp_path / "exp")
    s = PeakCutSession(p, dict(_BASE_CFG))
    s.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60000,
                   "context_ms": 15000, "ignored": False}],
        "video_offsets": []})
    return s


def test_xmlexporter_probes_mix_track_independent_of_mic_order(tmp_path):
    """Bei identischem Datei-Satz mit vertauschter mic_tracks-Reihenfolge
    MUSS XMLExporter dieselbe Audio-Probe-Quelle (die Mix-Spur) wählen.
    Nicht das erste mic — sonst entstehen unterschiedliche XMLs aus
    Re-Imports (Smoke-Befund 2026-05-20)."""
    probed = []
    with patch("core.exporters._probe_audio_info",
                side_effect=lambda p: probed.append(p) or (48000, 16, 2)), \
         patch("core.exporters._probe_video_info", return_value=(1920, 1080)):
        # Reihenfolge A: MIX zuerst
        s1 = _session(tmp_path / "a", ["MIX", "MIC1", "MIC2"])
        XMLExporter().export(s1)
        # Reihenfolge B: MIX als letztes
        s2 = _session(tmp_path / "b", ["MIC1", "MIC2", "MIX"])
        XMLExporter().export(s2)

    # Beide Läufe MÜSSEN dieselbe Audio-Quelle gepröbt haben —
    # nämlich die Mix-Spur (per get_reference_track gefunden).
    assert len(probed) == 2
    base_a = os.path.basename(probed[0])
    base_b = os.path.basename(probed[1])
    assert "mix" in base_a.lower(), \
        f"Lauf A pröbte nicht die Mix-Spur, sondern {base_a!r}"
    assert "mix" in base_b.lower(), \
        f"Lauf B pröbte nicht die Mix-Spur, sondern {base_b!r}"


def test_xmlexporter_falls_back_to_first_mic_when_no_mix(tmp_path):
    """Wenn keine Mix-Spur vorhanden ist, fällt der XMLExporter auf
    das erste Mic zurück (Verhalten wie SinnabschnittExporter)."""
    p = PeakCutProject()
    for name in ("KB.wav", "MIC1.wav", "MIC2.wav", "CAM.mp4"):
        (tmp_path / name).write_bytes(b"\x00")
    kb = str(tmp_path / "KB.wav")
    mics = [str(tmp_path / "MIC1.wav"), str(tmp_path / "MIC2.wav")]
    p.set_files(kb, mics, [str(tmp_path / "CAM.mp4")])
    p.guest_name = "TestGast"
    p.export_dir = str(tmp_path / "exp")
    s = PeakCutSession(p, dict(_BASE_CFG))
    s.load_analysis_results({
        "peaks": [{"index": 0, "position_ms": 60000,
                   "context_ms": 15000, "ignored": False}],
        "video_offsets": []})

    probed = []
    with patch("core.exporters._probe_audio_info",
                side_effect=lambda p: probed.append(p) or (48000, 16, 2)), \
         patch("core.exporters._probe_video_info", return_value=(1920, 1080)):
        XMLExporter().export(s)
    assert len(probed) == 1
    assert os.path.basename(probed[0]) == "MIC1.wav"
