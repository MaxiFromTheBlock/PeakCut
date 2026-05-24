"""Audio-Routing — eine zentrale Wahrheit für 'Mix' vs. 'echte Mics'.

Hintergrund (#71a Carl-Plan B-prime, 2026-05-21):

Beim Import landet die Mix-Datei aktuell in derselben Liste wie die
Einzel-Mic-Spuren (``project.mic_tracks``), weil der Importer alles
außer 'keyboard/keys/klavier' als Mic einsortiert. Sowohl
``MP3Exporter`` als auch ``session.play_current()`` Mic-Mode haben
historisch ``mic_audios[0]`` + Overlay über ``mic_audios[1:]``
genutzt — wodurch der bereits gemischte ProTools-Mix on-top zu den
Einzel-Mics addiert wurde und Phasing entstand.

Dieses Modul bündelt die Mix-Erkennung als token-bewusste
Heuristik, damit alle Consumer (MP3Exporter, Review-Wiedergabe,
Zuordnungs-Seite, Sinnabschnitt-Fallback) **derselben Wahrheit**
folgen — solange das Datenmodell die Mix-Datei noch nicht
strukturell vom Rest trennt. Die strukturelle Trennung (eigenes
``project.mix_track``-Feld, ``mic_tracks`` ohne Mix) kommt mit
``#77 Import-Refactor`` plus ``.peakcut``-Schema-v3.

Heuristik (Carl-Spec, Max-bestätigt 2026-05-21):

    basename ohne Extension, lowercased
    tokens = split on non-alphanumeric boundaries
    Mix-Datei  ⇔  'mix' ODER 'mixdown' als eigenes Token

Damit fallen Substring-False-Positives wie ``mixer_recording.wav``
oder ``mixedfeelings.wav`` raus, die mit der alten naiven
``'mix' in basename``-Heuristik fälschlich gematcht hätten. Echte
HM-Mix-Namen (``Sheila Mix.mp3``, ``Hotel Matze - Sheila de Liz
Mix.mp3``, ``Episode - Mix.mp3``, ``Podcast_mixdown.wav``) bleiben
erkannt.

Pin-1-Schutz: ``XMLExporter`` und ``FolgenschnittXMLExporter`` werden
durch dieses Modul *nicht* berührt — der Pin-Hash in
``tests/test_audio_routing_safety.py`` muss stabil bleiben.
"""

from __future__ import annotations

import os
import re

# Token-Whitelist: aktuell bewusst eng. Erweiterung über
# Konfigurations-Slot kommt frühestens mit #77 Import-Refactor.
_MIX_TOKENS = frozenset({"mix", "mixdown"})

# Splits an allem, was nicht alphanumerisch ist — Spaces, Underscores,
# Dashes, Dots, Klammern, etc. Damit wird "Sheila Mix.mp3" zu
# ["sheila", "mix"], aber "mixer_recording.wav" zu ["mixer", "recording"]
# (kein Match auf das Mix-Token).
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def is_mix_track(path: str) -> bool:
    """Token-bewusste Erkennung: ist diese Datei eine Mix-Spur?

    True ⇔ der Datei-Basename (ohne Extension, lowercased, an
    nicht-alphanumerischen Grenzen gesplittet) enthält 'mix' oder
    'mixdown' als eigenständiges Token.
    """
    if not path:
        return False
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0].lower()
    tokens = (t for t in _TOKEN_SPLIT.split(stem) if t)
    return any(token in _MIX_TOKENS for token in tokens)


def get_mix_track(project) -> str | None:
    """Erste Mix-Datei in ``project.mic_tracks`` zurückgeben.

    None, wenn keine vorhanden ist. Reine Lese-Operation — mutiert
    weder das Project noch ``mic_tracks``.
    """
    for path in project.mic_tracks:
        if is_mix_track(path):
            return path
    return None


def get_source_mic_tracks(project) -> list[str]:
    """``project.mic_tracks`` ohne Mix-Spuren — Reihenfolge der
    echten Mic-Spuren bleibt erhalten.

    Liefert immer eine neue Liste, keine Referenz auf ``mic_tracks``
    selbst.
    """
    return [path for path in project.mic_tracks if not is_mix_track(path)]


def get_speech_audio_segment(session, start_ms: int, end_ms: int):
    """Zentrale Audio-Quellen-Wahl für Sprach-Wiedergabe und -Export.

    Regel (#71a Task 2):

    - Pre-Condition: ``len(mic_tracks) == len(mic_audios)``. Bei
      Mismatch → ``None`` (korrupter Zustand, KEIN Silent-Fallback;
      Carl-P2-Linie: lieber klare Lücke als versteckt falsches
      Audio).
    - Mix in ``mic_tracks`` → nur Mix-Segment, kein Overlay
      (verhindert Phasing, der ganze Grund für #71a).
    - Sonst Overlay aller echten Mic-Spuren (Backward-Compat).
    - Keine echten Mics → ``None``.

    Args:
        session: Objekt mit ``project.mic_tracks`` und ``mic_audios``.
        start_ms, end_ms: Fenstergrenzen.

    Returns:
        ``AudioSegment`` | ``None``.
    """
    mic_tracks = session.project.mic_tracks
    mic_audios = session.mic_audios

    if len(mic_tracks) != len(mic_audios):
        return None

    mix_path = get_mix_track(session.project)
    if mix_path:
        try:
            idx = mic_tracks.index(mix_path)
        except ValueError:
            idx = None
        if idx is not None:
            return mic_audios[idx][start_ms:end_ms]

    real_mic_indices = [
        i for i, p in enumerate(mic_tracks) if not is_mix_track(p)
    ]
    if not real_mic_indices:
        return None

    segment = mic_audios[real_mic_indices[0]][start_ms:end_ms]
    for i in real_mic_indices[1:]:
        segment = segment.overlay(mic_audios[i][start_ms:end_ms])
    return segment
