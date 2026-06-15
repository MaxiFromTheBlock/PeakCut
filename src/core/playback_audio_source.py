"""#76 Task 3 — Audio Source Resolver (Carl-Plan 2026-06-15).

Einheitliche, dateibasierte (QMediaPlayer-taugliche) Hörquelle je Fenster.
Beschreibt WELCHE Datei, WELCHER Ausschnitt darin (media_*), und wie der
auf die Mix-Timeline abbildet (timeline_*) — damit der Controller die
Player-Position in Timeline-Koordinaten umrechnen kann.

- Key:            Keyboard-Datei, media == timeline.
- Speak/Smart+Mix: Mix-Datei, media == timeline.
- Speak/Smart ohne Mix: get_speech_audio_segment -> temporär gerenderte WAV
  (gecacht über Hash), media_start=0, timeline_start=window.start_ms.

Keine neue Mix-Heuristik — nur audio_routing.
"""

import hashlib
import os
from dataclasses import dataclass

from . import audio_routing
from .playback_modes import PLAYBACK_MODE_KEY, normalize_playback_mode
from .project_archive import ARCHIVE_DIR, material_root, _media_paths

_PREVIEW_DIR = "preview_audio"


@dataclass(frozen=True)
class PlaybackAudioSource:
    path: str = ""
    media_start_ms: int = 0
    media_end_ms: int = 0
    timeline_start_ms: int = 0
    timeline_end_ms: int = 0
    cleanup_path: str | None = None
    disabled_reason: str = ""

    @property
    def disabled(self):
        return bool(self.disabled_reason)


def _disabled(reason):
    return PlaybackAudioSource(disabled_reason=reason)


def _file_source(path, window):
    """Volle-Timeline-Datei: Media-Koordinaten == Timeline-Koordinaten."""
    return PlaybackAudioSource(
        path=path,
        media_start_ms=window.start_ms, media_end_ms=window.end_ms,
        timeline_start_ms=window.start_ms, timeline_end_ms=window.end_ms)


def _source_fingerprint(project):
    """Fingerabdruck der echten Mic-Quellen (P2, Carl 2026-06-15): der
    Fallback rendert aus den Mics — wechselt eine Mic-Datei oder ihr Inhalt,
    muss der Cache-Key sich ändern, sonst spielt PeakCut stale Audio."""
    parts = []
    for p in audio_routing.get_source_mic_tracks(project):
        try:
            st = os.stat(p)
            parts.append(f"{p}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{p}:?")
    return "|".join(parts)


def _preview_path(project, window):
    root = material_root(_media_paths(project),
                         getattr(project, "keyboard_track", None))
    out_dir = os.path.join(root, ARCHIVE_DIR, _PREVIEW_DIR)
    key = (f"{window.mode}|{window.start_ms}|{window.end_ms}|"
           f"{getattr(project, 'keyboard_track', '')}|"
           f"{_source_fingerprint(project)}")
    name = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + ".wav"
    return out_dir, os.path.join(out_dir, name)


def resolve_playback_audio_source(session, window):
    if window.disabled:
        return _disabled(window.disabled_reason)

    project = session.project
    mode = normalize_playback_mode(window.mode)

    if mode == PLAYBACK_MODE_KEY:
        kb = getattr(project, "keyboard_track", None)
        if not kb:
            return _disabled("Keine Keyboard-Datei vorhanden.")
        return _file_source(kb, window)

    # speak / smart: Mix bevorzugt
    mix = audio_routing.get_mix_track(project)
    if mix:
        return _file_source(mix, window)

    # Fallback ohne Mix: echte Mics zu einer Vorschau-WAV rendern (gecacht).
    # #76 (A): Free-Play (offenes Ende) ohne Mix wird nicht gerendert —
    # on_play erlaubt Free-Play nur bei seekbarer Datei-Quelle.
    if window.end_ms is None:
        return _disabled("Free-Play ohne Mix nicht unterstützt.")
    out_dir, path = _preview_path(project, window)
    dur = window.end_ms - window.start_ms
    if os.path.isfile(path):
        return PlaybackAudioSource(
            path=path, media_start_ms=0, media_end_ms=dur,
            timeline_start_ms=window.start_ms, timeline_end_ms=window.end_ms)

    if hasattr(session, "load_audio_lazy"):
        session.load_audio_lazy()
    seg = audio_routing.get_speech_audio_segment(
        session, window.start_ms, window.end_ms)
    if seg is None:
        return _disabled("Keine Audioquelle für die Vorschau.")

    os.makedirs(out_dir, exist_ok=True)
    seg.export(path, format="wav")
    return PlaybackAudioSource(
        path=path, media_start_ms=0, media_end_ms=dur,
        timeline_start_ms=window.start_ms, timeline_end_ms=window.end_ms)
