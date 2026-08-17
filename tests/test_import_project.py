"""Import Slice 3 / Brocken B(ii): bestaetigte Rollen -> Laufzeit-Projekt.

Keine Namensheuristik mehr — die WAHRHEIT sind die bestaetigten Rollen
(ConfirmedImportSlots). Carl-Adapter Opt. 2: das Laufzeit-PeakCutProject bekommt fuer
den legacy XMLExporter Mics + [Mix] in mic_tracks (Pin-1), waehrend die bestaetigte
Mix-Rolle (auch None) die Wahrheit fuer mix_track bleibt — set_files' Namens-Erkennung
darf das NICHT ueberstimmen.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.import_model import ConfirmedImportSlots  # noqa: E402
from core.import_project import build_project_from_confirmed_slots  # noqa: E402


def _slots():
    return ConfirmedImportSlots(
        marker="/m/MIC4.wav", mix="/m/P8Mix.wav",
        mics=("/m/MIC1.wav", "/m/MIC2.wav"),
        videos=("/m/Cam01.mp4", "/m/Cam02.mp4"),
        transcript="/m/t.json",
    )


def test_marker_videos_transcript_from_slots():
    p = build_project_from_confirmed_slots(_slots())
    assert p.marker_track == "/m/MIC4.wav"
    assert p.keyboard_track == "/m/MIC4.wav"          # Alias
    assert list(p.videos) == ["/m/Cam01.mp4", "/m/Cam02.mp4"]
    assert p.transcript_path == "/m/t.json"


def test_adapter_mix_in_mic_tracks_pin1():
    # Carl-Adapter: legacy mic_tracks = echte Mics + [Mix] -> XMLExporter behaelt den
    # Mix-Audiotrack (Pin-1). mix_track ZUSAETZLICH separat = der bestaetigte Mix.
    p = build_project_from_confirmed_slots(_slots())
    assert set(p.mic_tracks) == {"/m/MIC1.wav", "/m/MIC2.wav", "/m/P8Mix.wav"}
    assert p.mix_track == "/m/P8Mix.wav"


def test_marker_is_name_blind():
    # MIC4 (kein Marker-Token) wird ueber die bestaetigte Rolle korrekt Marker.
    p = build_project_from_confirmed_slots(_slots())
    assert os.path.basename(p.marker_track) == "MIC4.wav"


def test_no_mix_means_clean_mics_and_no_invented_mix():
    slots = ConfirmedImportSlots(
        marker="/m/MIC4.wav", mics=("/m/MIC1.wav",), videos=("/m/Cam01.mp4",))
    p = build_project_from_confirmed_slots(slots)
    assert list(p.mic_tracks) == ["/m/MIC1.wav"]
    assert p.mix_track is None


def test_confirmed_role_overrides_name_heuristic():
    # Datei "mix.wav" als MIC bestaetigt (kein confirmed Mix) -> mix_track bleibt None.
    # Rolle ist Wahrheit; set_files' Namens-Erkennung darf nicht heimlich einen Mix setzen.
    slots = ConfirmedImportSlots(
        marker="/m/MIC4.wav", mics=("/m/mix.wav",), videos=("/m/Cam01.mp4",))
    p = build_project_from_confirmed_slots(slots)
    assert p.mix_track is None
    assert list(p.mic_tracks) == ["/m/mix.wav"]


def test_audio_routing_parity_with_legacy_pin1():
    # (iv) Pin-Gate: fuer den HM-Fall (Marker + 2 Mics + P8Mix) ist die Audio-Routing-
    # Struktur identisch zur legacy-Namens-Erkennung -> Mix wird als Speech allein
    # gespielt, MIC1/2 sind die Quell-Mics. Damit bleibt die Keyboardstellen-XML/
    # get_speech_audio_segment byte-stabil (Pin-1), obwohl der Marker namens-blind ist.
    from core import audio_routing
    from core.project import PeakCutProject
    slots = ConfirmedImportSlots(
        marker="/m/MIC4.wav", mix="/m/P8Mix.wav",
        mics=("/m/MIC1.wav", "/m/MIC2.wav"), videos=())
    confirmed = build_project_from_confirmed_slots(slots)

    legacy = PeakCutProject()  # alte Form: Mix per Name in der Mic-Liste erkannt
    legacy.set_files(keyboard="/m/MIC4.wav",
                     mics=["/m/MIC1.wav", "/m/MIC2.wav", "/m/P8Mix.wav"], videos=[])

    assert set(confirmed.mic_tracks) == set(legacy.mic_tracks)
    assert audio_routing.get_mix_track(confirmed) == audio_routing.get_mix_track(legacy)
    assert (set(audio_routing.get_source_mic_tracks(confirmed))
            == set(audio_routing.get_source_mic_tracks(legacy)))
    assert audio_routing.get_mix_track(confirmed) == "/m/P8Mix.wav"
