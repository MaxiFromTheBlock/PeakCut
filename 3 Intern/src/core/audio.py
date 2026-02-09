import numpy as np
from pydub import AudioSegment
import simpleaudio as sa


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
    audio_data = segment.set_channels(1).set_frame_rate(44100).set_sample_width(2)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        sa.play_buffer(raw, 1, 2, 44100)
    except Exception as e:
        import sys
        print(f"Audio playback error: {e}", file=sys.stderr)


def stop_playback():
    """Stop all audio playback."""
    try:
        sa.stop_all()
    except Exception as e:
        import sys
        print(f"Stop playback error: {e}", file=sys.stderr)
