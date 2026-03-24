import os

import numpy as np
from pydub import AudioSegment

from utils import get_logger

_log = get_logger("peakcut.detection")


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
    samples = np.abs(np.array(audio.get_array_of_samples()))
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
