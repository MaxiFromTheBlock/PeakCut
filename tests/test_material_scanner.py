"""Scanner-Slice (Carl): Dauer-Cluster (Aufnahme vs. Bibliothek) + DUENNE Inhalts-Evidence.
NUR Report (Liste ImportCandidate), KEIN Schreiben. Name ist nur Evidence — der Inhalt
(Dauer + Marker-Signal) schlaegt den Namen. Probe-/Signal-Funktionen injizierbar -> Logik
ohne echte Medien testbar.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from core.material_scanner import scan_material
from core.import_model import KIND_AUDIO, KIND_VIDEO, ROLE_MARKER, ROLE_MIC, ROLE_MIX, ROLE_CAMERA, ROLE_IGNORE

EP = 9695000  # Folgenlaenge ms (Johanna real)


def test_clusters_recording_vs_library_188_problem():
    paths = ["mix.wav", "mic1.wav", "mic4.wav", "cam1.mp4", "cam2.mp4"] + [f"sfx{i}.wav" for i in range(20)]
    dur = {"mix.wav": EP, "mic1.wav": EP, "mic4.wav": EP, "cam1.mp4": EP + 5000, "cam2.mp4": EP + 5000}
    dur.update({f"sfx{i}.wav": 3000 for i in range(20)})  # 3s Bibliothek
    cands = {c.path: c for c in scan_material(paths, probe_duration=lambda p: dur.get(p))}
    assert cands["mix.wav"].evidence.episode_length
    assert cands["cam1.mp4"].evidence.episode_length and cands["cam1.mp4"].kind == KIND_VIDEO
    assert not cands["sfx0.wav"].evidence.episode_length
    assert cands["sfx0.wav"].suggested_role == ROLE_IGNORE   # Bibliothek, NICHT Mic
    # die 20 SFX werden NIE zu Mics (das alte 188-Problem)
    assert not any("sfx" in c.path for c in cands.values() if c.suggested_role == ROLE_MIC)


def test_marker_by_content_not_name():
    # "MIC4" (Name = Mic) = Stille + LAUTE Impulse -> MARKER; Musik "KLAVIER" (kurz) -> IGNORE.
    paths = ["MIC4.wav", "KLAVIER_V1.wav", "mic1.wav"]
    dur = {"MIC4.wav": EP, "KLAVIER_V1.wav": 4000, "mic1.wav": EP}
    sig = {"MIC4.wav": (0.95, 0.6), "mic1.wav": (0.2, 0.5)}  # (stille, peak)
    cands = {c.path: c for c in scan_material(
        paths, probe_duration=lambda p: dur.get(p), audio_signal=lambda p: sig.get(p))}
    assert cands["MIC4.wav"].suggested_role == ROLE_MARKER      # Inhalt schlaegt Namen-Token
    assert cands["mic1.wav"].suggested_role == ROLE_MIC
    assert cands["KLAVIER_V1.wav"].suggested_role == ROLE_IGNORE  # kurz -> Bibliothek, NIE Marker allein


def test_empty_channel_is_not_marker_and_not_mic():
    # leerer Kanal (Stille OHNE Impulse, peak ~0) darf weder Marker noch Mic werden -> ignore.
    # (Johanna real: MIC3/5/6/PHONE/SOUND_PAD = stille 1.0 aber kein Pegel.)
    paths = ["MIC4.wav", "PHONE.wav", "mic1.wav"]
    dur = {p: EP for p in paths}
    sig = {"MIC4.wav": (1.0, 0.7), "PHONE.wav": (1.0, 0.004), "mic1.wav": (0.3, 0.5)}
    cands = {c.path: c for c in scan_material(
        paths, probe_duration=lambda p: dur.get(p), audio_signal=lambda p: sig.get(p))}
    assert cands["MIC4.wav"].suggested_role == ROLE_MARKER    # Stille + Impulse
    assert cands["PHONE.wav"].suggested_role == ROLE_IGNORE   # Stille ohne Impulse = leer
    assert cands["mic1.wav"].suggested_role == ROLE_MIC


def test_mix_uses_name_only_as_hint():
    paths = ["P8Mix.wav", "mic1.wav"]
    dur = {"P8Mix.wav": EP, "mic1.wav": EP}
    cands = {c.path: c for c in scan_material(paths, probe_duration=lambda p: dur.get(p))}
    assert cands["P8Mix.wav"].suggested_role == ROLE_MIX   # name_hint (B1-Muster) als Hinweis
    assert cands["P8Mix.wav"].evidence.name_hint == ROLE_MIX
    assert cands["mic1.wav"].suggested_role == ROLE_MIC


def test_video_short_social_clip_excluded_by_duration():
    paths = ["cam1.mp4", "Social_Abbinder.mp4"]
    dur = {"cam1.mp4": EP, "Social_Abbinder.mp4": 30000}  # 30s Social-Clip
    cands = {c.path: c for c in scan_material(paths, probe_duration=lambda p: dur.get(p))}
    assert cands["cam1.mp4"].suggested_role == ROLE_CAMERA
    assert cands["Social_Abbinder.mp4"].suggested_role == ROLE_IGNORE


def test_report_only_returns_list_no_side_effects():
    assert scan_material([], probe_duration=lambda p: None) == []
    # nicht-Medien (z.B. .txt) tauchen nicht als Kandidaten auf
    cands = scan_material(["notes.txt", "cam.mp4"], probe_duration=lambda p: EP)
    assert [c.path for c in cands] == ["cam.mp4"]
