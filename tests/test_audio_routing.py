"""#71a Task 1 — Audio-Routing-Verträge (Carl Gate A).

Token-bewusste Mix-Erkennung statt naiver Substring-Suche. Heuristik
nach Carl-Spec 2026-05-21:

    basename ohne Extension, lowercased
    tokens = split on non-alphanumeric boundaries
    Mix-Datei ⇔ 'mix' ODER 'mixdown' als eigenes Token

Damit fallen Edge-Cases wie 'mixer_recording.wav' und
'mixedfeelings.wav' raus, die mit der alten 'mix in basename'-
Heuristik fälschlich gematcht hätten. Echte HM-Mix-Namen
(Sheila Mix.mp3, Hotel Matze - Sheila de Liz Mix.mp3, ... - Mix.mp3,
Podcast_mixdown.wav) bleiben erkannt.

Gate-A: nach diesem Task sind die Verträge eingefroren — Folge-Tasks
(MP3Exporter, Review, AssignmentPage, SinnabschnittExporter) hängen
sich daran.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.audio_routing import (  # noqa: E402
    get_mix_track,
    get_source_mic_tracks,
    is_mix_track,
)


# --- is_mix_track: positive Fälle (HM-real, Max-bestätigt) -----------


def test_is_mix_track_matches_sheila_mix_basename():
    assert is_mix_track("Sheila Mix.mp3")


def test_is_mix_track_matches_hm_long_prefix_with_dash():
    assert is_mix_track("Hotel Matze - Sheila de Liz Mix.mp3")


def test_is_mix_track_matches_simple_dash_form():
    """Carl-Spec '... - Mix.mp3': Mix als alleinstehendes Token
    nach einem Trenner."""
    assert is_mix_track("Episode 47 - Mix.mp3")


def test_is_mix_track_matches_mixdown_token():
    """Carl-Spec optional: mixdown als Synonym (z.B. Podcast-
    Produktionen, die ihre Master-Datei 'mixdown' nennen)."""
    assert is_mix_track("Podcast_mixdown.wav")


# --- is_mix_track: negative Fälle (Token-Härtung) --------------------


def test_is_mix_track_rejects_mic_files():
    assert not is_mix_track("MIC1.wav")
    assert not is_mix_track("MIC2.wav")


def test_is_mix_track_rejects_mixer_recording():
    """Carl-Spec: 'mix' als Substring in 'mixer' darf nicht matchen.
    Schützt vor False-Positives wie Mischpult-Recordings."""
    assert not is_mix_track("mixer_recording.wav")


def test_is_mix_track_rejects_mixedfeelings():
    """Carl-Spec: 'mix' als Substring in zusammengeschriebenen
    Wörtern darf nicht matchen — keine Halbtreffer."""
    assert not is_mix_track("mixedfeelings.wav")


def test_is_mix_track_rejects_empty():
    assert not is_mix_track("")


# --- is_mix_track: Robustheit ----------------------------------------


def test_is_mix_track_case_insensitive():
    assert is_mix_track("SHEILA MIX.MP3")
    assert is_mix_track("sheila mix.mp3")
    assert is_mix_track("Sheila MIX.MP3")


def test_is_mix_track_handles_full_paths():
    """Funktioniert mit absoluten Pfaden — relevant, weil
    project.mic_tracks absolute Pfade enthält."""
    assert is_mix_track("/Users/max/material/Sheila Mix.mp3")
    assert not is_mix_track("/Users/max/material/MIC1.wav")


def test_is_mix_track_handles_various_separators():
    """Token-Split funktioniert mit Spaces, Underscores, Dashes,
    Dots, Klammern."""
    assert is_mix_track("HM_2026-05_Mix.wav")
    assert is_mix_track("episode.42.mix.mp3")
    assert is_mix_track("episode(mix).mp3")


# --- get_mix_track / get_source_mic_tracks: gegen Project-Stub -------


class _StubProject:
    """Minimaler PeakCutProject-Stub: das einzige Attribut, auf das
    die Helper zugreifen, ist mic_tracks."""

    def __init__(self, mic_tracks):
        self.mic_tracks = list(mic_tracks)


def test_get_mix_track_finds_mix_in_mic_list():
    p = _StubProject(["MIC1.wav", "MIC2.wav", "Sheila Mix.mp3"])
    assert get_mix_track(p) == "Sheila Mix.mp3"


def test_get_mix_track_returns_none_when_no_mix():
    p = _StubProject(["MIC1.wav", "MIC2.wav"])
    assert get_mix_track(p) is None


def test_get_mix_track_returns_first_when_multiple_mixes():
    """Defensive: zwei Mix-Dateien sind ein Datenfehler, aber wenn
    sie auftreten, deterministisch die erste."""
    p = _StubProject(["A Mix.mp3", "B Mix.mp3"])
    assert get_mix_track(p) == "A Mix.mp3"


def test_get_mix_track_returns_none_for_empty_project():
    p = _StubProject([])
    assert get_mix_track(p) is None


def test_get_source_mic_tracks_filters_mix_out():
    p = _StubProject(["MIC1.wav", "Sheila Mix.mp3", "MIC2.wav"])
    assert get_source_mic_tracks(p) == ["MIC1.wav", "MIC2.wav"]


def test_get_source_mic_tracks_preserves_order_of_real_mics():
    """Reihenfolge echter Mics bleibt unverändert, wenn die Mix
    in der Mitte rausgefiltert wird."""
    p = _StubProject(
        ["MIC2.wav", "MIC1.wav", "Sheila Mix.mp3", "MIC3.wav"]
    )
    assert get_source_mic_tracks(p) == [
        "MIC2.wav",
        "MIC1.wav",
        "MIC3.wav",
    ]


def test_get_source_mic_tracks_does_not_mutate_project():
    """Helper liest, mutiert nicht — Schema bleibt unangetastet
    (Pin-3)."""
    mics = ["MIC1.wav", "Sheila Mix.mp3", "MIC2.wav"]
    p = _StubProject(mics)
    _ = get_source_mic_tracks(p)
    assert p.mic_tracks == mics


def test_get_source_mic_tracks_returns_all_when_no_mix():
    p = _StubProject(["MIC1.wav", "MIC2.wav"])
    assert get_source_mic_tracks(p) == ["MIC1.wav", "MIC2.wav"]


def test_get_source_mic_tracks_empty_when_only_mix():
    """Edge-Case: nur eine Mix-Datei, keine echten Mics."""
    p = _StubProject(["Sheila Mix.mp3"])
    assert get_source_mic_tracks(p) == []


# --- Carl-Zusatz-Pin: Smart-Boundary-Pipeline findet HM-Mixnamen -----


def test_reference_track_finds_hm_mix_names_for_smart_boundary_pipeline():
    """Carl-Pin: PeakCutProject.get_reference_track() — auf
    is_mix_track umgestellt — findet weiterhin die HM-typischen
    Mix-Namen. Wenn dieser Test rot wird, würde die Smart-
    Boundary-Pipeline silent skippen ('Sinnabschnitte: kein Mix
    gefunden')."""
    from core.project import PeakCutProject

    cases = [
        (["MIC1.wav", "Sheila Mix.mp3"], "Sheila Mix.mp3"),
        (
            ["MIC1.wav", "MIC2.wav", "Hotel Matze - Sheila de Liz Mix.mp3"],
            "Hotel Matze - Sheila de Liz Mix.mp3",
        ),
        (["Episode - Mix.mp3"], "Episode - Mix.mp3"),
    ]

    for mics, expected_basename in cases:
        p = PeakCutProject()
        p.set_files(None, mics, [])
        ref = p.get_reference_track()
        assert ref is not None, (
            f"get_reference_track lieferte None für mics={mics}. "
            f"Smart-Boundary-Pipeline würde silent skippen."
        )
        assert os.path.basename(ref) == expected_basename, (
            f"Falsche Mix-Datei: erwartet {expected_basename!r}, "
            f"bekommen {ref!r}"
        )


def test_reference_track_returns_none_when_no_mix_in_project():
    """Pin: ohne Mix-Datei in der Mic-Liste liefert
    get_reference_track sauberes None (kein False-Positive durch
    mixer_recording.wav)."""
    from core.project import PeakCutProject

    p = PeakCutProject()
    p.set_files(None, ["MIC1.wav", "MIC2.wav", "mixer_recording.wav"], [])
    assert p.get_reference_track() is None
