"""Audio-Routing — eine zentrale Wahrheit für 'Mix' vs. 'echte Mics'.

Hintergrund (#71a Carl-Plan B-prime, 2026-05-21):

Beim Import landet die Mix-Datei aktuell in derselben Liste wie die
Einzel-Mic-Spuren (``project.mic_tracks``), weil der Importer alles
außer der Marker-Spur (Namens-Token 'keyboard/keys/klavier') als Mic
einsortiert. Sowohl
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
``#77 Import-Refactor``. Während Gate B bleibt der Mix aus Pin-1-
Gründen noch zusätzlich in ``mic_tracks``.

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

from . import import_classifier


def is_mix_track(path: str) -> bool:
    """Token-bewusste Erkennung: ist diese Datei eine Mix-Spur?

    True ⇔ der Datei-Basename (ohne Extension, lowercased, an
    nicht-alphanumerischen Grenzen gesplittet) enthält 'mix' oder
    'mixdown' als eigenständiges Token.
    """
    return import_classifier.is_mix_track(path)


def get_mix_track(project) -> str | None:
    """Mix-Datei zurückgeben.

    #77 Task 3: ``project.mix_track`` ist die strukturelle Quelle der
    Wahrheit. Der Scan über ``project.mic_tracks`` bleibt als Legacy-
    Fallback für alte Objekte und den Gate-B-Zwischenzustand.
    """
    mix_track = getattr(project, "mix_track", None)
    if isinstance(mix_track, str) and mix_track:
        return mix_track
    for path in getattr(project, "mic_tracks", ()):
        if is_mix_track(path):
            return path
    return None


def get_source_mic_tracks(project) -> list[str]:
    """``project.mic_tracks`` ohne Mix-Spuren — Reihenfolge der
    echten Mic-Spuren bleibt erhalten.

    Liefert immer eine neue Liste, keine Referenz auf ``mic_tracks``
    selbst.
    """
    return [
        path for path in getattr(project, "mic_tracks", ())
        if not is_mix_track(path)
    ]


def get_speech_audio_segment(session, start_ms: int, end_ms: int):
    """Zentrale Audio-Quellen-Wahl für Sprach-Wiedergabe und -Export.

    Regel (#71a Task 2):

    - Struktureller Mix + ``session.mix_audio`` → nur Mix-Segment,
      kein Overlay.
    - Legacy-Mix in ``mic_tracks`` → nur Mix-Segment
      (verhindert Phasing, der ganze Grund für #71a).
    - Kein Mix → Overlay aller echten Mic-Spuren (Backward-Compat).
    - Keine echten Mics → ``None``.

    Args:
        session: Objekt mit ``project.mic_tracks`` und ``mic_audios``.
        start_ms, end_ms: Fenstergrenzen.

    Returns:
        ``AudioSegment`` | ``None``.
    """
    mic_tracks = getattr(session.project, "mic_tracks", [])
    mic_audios = getattr(session, "mic_audios", [])
    mix_path = get_mix_track(session.project)
    if mix_path:
        mix_audio = getattr(session, "mix_audio", None)
        if mix_audio is not None:
            return mix_audio[start_ms:end_ms]
        if len(mic_tracks) != len(mic_audios):
            return None
        try:
            idx = mic_tracks.index(mix_path)
        except ValueError:
            return None
        return mic_audios[idx][start_ms:end_ms]

    if len(mic_tracks) != len(mic_audios):
        return None

    real_mic_indices = [
        i for i, p in enumerate(mic_tracks) if not is_mix_track(p)
    ]
    if not real_mic_indices:
        return None

    segment = mic_audios[real_mic_indices[0]][start_ms:end_ms]
    for i in real_mic_indices[1:]:
        segment = segment.overlay(mic_audios[i][start_ms:end_ms])
    return segment
