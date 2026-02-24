import numpy as np
from pydub import AudioSegment
import simpleaudio as sa

_current_playback = None


def detect_peaks(audio_path, threshold_factor, min_gap_ms):
    """Detect peaks in audio file above threshold with minimum gap filtering.

    Returns list of peak times in milliseconds.
    """
    audio = AudioSegment.from_file(audio_path)
    samples = np.array(audio.get_array_of_samples())
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

    return filtered_times


def play_audio(segment):
    """Play an AudioSegment via simpleaudio."""
    global _current_playback
    audio_data = segment.set_channels(1).set_frame_rate(44100).set_sample_width(2)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        _current_playback = sa.play_buffer(raw, 1, 2, 44100)
    except (sa.SimpleaudioError, OSError) as e:
        import sys
        print(f"Audio playback error: {e}", file=sys.stderr)


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
        import sys
        print(f"Stop playback error: {e}", file=sys.stderr)
    _current_playback = None
