import os

import numpy as np
from pydub import AudioSegment
import simpleaudio as sa

from utils import get_logger

_log = get_logger("peakcut.audio")
_PLAYBACK_SAMPLE_RATE = 44100
_PLAYBACK_SAMPLE_WIDTH = 2  # 16-bit audio (bytes per sample)
_PLAYBACK_CHANNELS = 1

_current_playback = None


def detect_peaks(audio_path, threshold_factor, min_gap_ms):
    """Detect peaks in audio file above threshold with minimum gap filtering.

    Returns list of peak times in milliseconds.
    """
    _log.info("Peak detection: %s (threshold=%.2f, gap=%dms)", audio_path, threshold_factor, min_gap_ms)
    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as e:
        _log.error("Failed to load audio file %s: %s", audio_path, e)
        raise RuntimeError(f"Audio-Datei nicht lesbar: {os.path.basename(audio_path)}") from e
    samples = np.array(audio.get_array_of_samples())
    if len(samples) == 0:
        _log.warning("Audio file is empty: %s", audio_path)
        return []
    threshold = np.max(samples) * threshold_factor

    peaks = np.where(samples > threshold)[0]
    times_ms = (peaks / audio.frame_rate) * 1000
    unique_times = np.unique(times_ms.astype(int))

    filtered_times = []
    last_time = -min_gap_ms * 2
    for t in unique_times:
        if t - last_time >= min_gap_ms:
            filtered_times.append(t)
            last_time = t

    _log.info("Found %d peaks", len(filtered_times))
    return filtered_times


def play_audio(segment):
    """Play an AudioSegment via simpleaudio."""
    global _current_playback
    audio_data = segment.set_channels(_PLAYBACK_CHANNELS).set_frame_rate(_PLAYBACK_SAMPLE_RATE).set_sample_width(_PLAYBACK_SAMPLE_WIDTH)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        _current_playback = sa.play_buffer(raw, _PLAYBACK_CHANNELS, _PLAYBACK_SAMPLE_WIDTH, _PLAYBACK_SAMPLE_RATE)
    except (sa.SimpleaudioError, OSError) as e:
        _log.error("Audio playback error: %s", e)


def is_playing():
    """Check if audio is currently playing."""
    if _current_playback is None:
        return False
    try:
        return _current_playback.is_playing()
    except (sa.SimpleaudioError, OSError):
        return False


def stop_playback():
    """Stop all audio playback."""
    global _current_playback
    try:
        sa.stop_all()
    except (sa.SimpleaudioError, OSError) as e:
        _log.error("Stop playback error: %s", e)
    _current_playback = None
