"""#77 import classifier - central file-role suggestions.

Pure core module: no Qt, no filesystem reads, no project mutation. The
classifier suggests roles for the import dialog; the confirmed slots become
the source of truth later in #77.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

ROLE_MARKER = "marker"
ROLE_MIC = "mic"
ROLE_MIX = "mix"
ROLE_TRANSCRIPT = "transcript"
ROLE_CAMERA = "camera"
ROLE_IGNORE = "ignore"

IMPORT_ROLES = frozenset({
    ROLE_MARKER,
    ROLE_MIC,
    ROLE_MIX,
    ROLE_TRANSCRIPT,
    ROLE_CAMERA,
    ROLE_IGNORE,
})

_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3"})
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov"})
_TRANSCRIPT_EXTENSIONS = frozenset({".docx"})

_MIX_TOKENS = frozenset({"mix", "mixdown"})
_MARKER_TOKENS = frozenset({"keyboard", "keys", "klavier", "marker"})
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ImportCandidate:
    path: str
    suggested_role: str
    reason: str = ""

    def __post_init__(self):
        if self.suggested_role not in IMPORT_ROLES:
            raise ValueError(f"Unknown import role: {self.suggested_role!r}")


@dataclass(frozen=True)
class ImportSlots:
    marker_track: str | None = None
    mic_tracks: tuple[str, ...] = ()
    mix_track: str | None = None
    transcript_path: str | None = None
    videos: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "mic_tracks", tuple(self.mic_tracks or ()))
        object.__setattr__(self, "videos", tuple(self.videos or ()))
        object.__setattr__(self, "ignored", tuple(self.ignored or ()))


def _extension(path: str | None) -> str:
    if not path:
        return ""
    return os.path.splitext(os.path.basename(path))[1].lower()


def _tokens(path: str | None) -> tuple[str, ...]:
    if not path:
        return ()
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return tuple(token for token in _TOKEN_SPLIT.split(stem) if token)


def is_audio_path(path) -> bool:
    return _extension(path) in _AUDIO_EXTENSIONS


def is_video_path(path) -> bool:
    return _extension(path) in _VIDEO_EXTENSIONS


def is_transcript_path(path) -> bool:
    return _extension(path) in _TRANSCRIPT_EXTENSIONS


def is_mix_track(path) -> bool:
    return any(token in _MIX_TOKENS for token in _tokens(path))


def is_marker_track(path) -> bool:
    return any(token in _MARKER_TOKENS for token in _tokens(path))


def suggest_role(path) -> str:
    if is_transcript_path(path):
        return ROLE_TRANSCRIPT
    if is_video_path(path):
        return ROLE_CAMERA
    if is_audio_path(path):
        if is_marker_track(path):
            return ROLE_MARKER
        if is_mix_track(path):
            return ROLE_MIX
        return ROLE_MIC
    return ROLE_IGNORE


def suggest_import_slots(paths) -> ImportSlots:
    marker_track = None
    mic_tracks = []
    mix_track = None
    transcript_path = None
    videos = []
    ignored = []

    for path in paths or ():
        role = suggest_role(path)
        if role == ROLE_MARKER:
            if marker_track is None:
                marker_track = path
            else:
                ignored.append(path)
        elif role == ROLE_MIX:
            if mix_track is None:
                mix_track = path
            else:
                ignored.append(path)
        elif role == ROLE_MIC:
            mic_tracks.append(path)
        elif role == ROLE_TRANSCRIPT:
            if transcript_path is None:
                transcript_path = path
            else:
                ignored.append(path)
        elif role == ROLE_CAMERA:
            videos.append(path)
        else:
            ignored.append(path)

    return ImportSlots(
        marker_track=marker_track,
        mic_tracks=tuple(mic_tracks),
        mix_track=mix_track,
        transcript_path=transcript_path,
        videos=tuple(videos),
        ignored=tuple(ignored),
    )


def normalize_import_slots(slots: ImportSlots) -> ImportSlots:
    marker_track = slots.marker_track
    mix_track = slots.mix_track
    transcript_path = slots.transcript_path
    mic_tracks = []
    videos = list(slots.videos)
    ignored = list(slots.ignored)

    for path in slots.mic_tracks:
        if is_marker_track(path):
            if marker_track is None:
                marker_track = path
            else:
                ignored.append(path)
        elif is_mix_track(path):
            if mix_track is None:
                mix_track = path
            else:
                ignored.append(path)
        else:
            mic_tracks.append(path)

    return ImportSlots(
        marker_track=marker_track,
        mic_tracks=tuple(mic_tracks),
        mix_track=mix_track,
        transcript_path=transcript_path,
        videos=tuple(videos),
        ignored=tuple(ignored),
    )


def validate_import_slots(slots: ImportSlots) -> list[str]:
    messages = []
    if not slots.marker_track:
        messages.append("Marker-Spur fehlt.")
    if not slots.mic_tracks and not slots.mix_track:
        messages.append(
            "Keine Sprachquelle: mindestens ein Mic oder Mix erforderlich.")

    mix_count = (1 if slots.mix_track else 0)
    mix_count += sum(1 for path in slots.mic_tracks if is_mix_track(path))
    mix_count += sum(1 for path in slots.ignored if is_mix_track(path))
    if mix_count > 1:
        messages.append("Mehrere Mix-Spuren erkannt.")

    marker_count = (1 if slots.marker_track else 0)
    marker_count += sum(1 for path in slots.mic_tracks if is_marker_track(path))
    marker_count += sum(1 for path in slots.ignored if is_marker_track(path))
    if marker_count > 1:
        messages.append("Mehrere Marker-Spuren erkannt.")

    return messages
