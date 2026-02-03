import os
import numpy as np
from pydub import AudioSegment
import simpleaudio as sa
from status import update
from utils import MATERIAL_DIR, EXPORT_DIR
import config

# Global navigation state
_peaks = []
_current_peak = 0
_keyboard_audio = None
_mic_audios = []
_mode = "keyboard"  # or "mic"
_ignored_peaks = set()


def detect_peaks(audio_path):
    threshold_factor = config.get("threshold_factor")
    min_gap_ms = config.get("min_gap_ms")
    audio = AudioSegment.from_wav(audio_path)
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


def run_peak_analysis():
    global _peaks, _current_peak, _keyboard_audio, _mic_audios, _mode
    update("✅ [PEAKS] Starting peak analysis...")

    os.makedirs(EXPORT_DIR, exist_ok=True)

    files = os.listdir(MATERIAL_DIR)
    keyboard_file = None
    mic_files = []

    for f in files:
        if any(kw in f.lower() for kw in ["keyboard", "keys", "klavier"]):
            keyboard_file = os.path.join(MATERIAL_DIR, f)
        elif f.lower().endswith(".wav"):
            mic_files.append(os.path.join(MATERIAL_DIR, f))

    mic_files = [f for f in mic_files if keyboard_file not in f]

    if not keyboard_file:
        update("❌ No keyboard file found.")
        return

    _peaks = detect_peaks(keyboard_file)
    _keyboard_audio = AudioSegment.from_wav(keyboard_file)
    _mic_audios = [AudioSegment.from_wav(f) for f in mic_files]
    _current_peak = 0
    _mode = "keyboard"

    update(f"✅ {len(_peaks)} peaks detected.")
    for idx, t in enumerate(_peaks, 1):
        update(f"{idx}: {t / 1000:.2f}s")

    update("▶️ Analysis complete. Press Play to start.")

def play_current_peak(index=None):
    global _current_peak
    if not _peaks:
        update("❌ No peaks loaded.")
        return

    if index is not None:
        _current_peak = index

    if _current_peak >= len(_peaks):
        update("❌ Invalid peak index.")
        return

    time_ms = _peaks[_current_peak]
    preview_duration = config.get("preview_duration_ms")
    context_duration = config.get("context_duration_ms")

    if _mode == "keyboard":
        segment = _keyboard_audio[time_ms:time_ms + preview_duration]
    else:
        start = max(0, time_ms - context_duration)
        end = time_ms + context_duration
        segment = _mic_audios[0][start:end]
        for audio in _mic_audios[1:]:
            segment = segment.overlay(audio[start:end])

    update(f"▶️ Playing peak {_current_peak + 1} ({_mode})...")
    play_audio(segment)

def play_audio(segment):
    audio_data = segment.set_channels(1).set_frame_rate(44100).set_sample_width(2)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        sa.play_buffer(raw, 1, 2, 44100)
    except Exception as e:
        update(f"❌ Audio playback error: {e}")

def stop_playback():
    try:
        sa.stop_all()
        update("🛑 Playback stopped.")
    except Exception as e:
        update(f"⚠ Error stopping playback: {e}")

def go_forward():
    global _current_peak
    if _current_peak < len(_peaks) - 1:
        _current_peak += 1
        play_current_peak()
    else:
        update("✅ End of list reached.")

def go_back():
    global _current_peak
    if _current_peak > 0:
        _current_peak -= 1
        play_current_peak()
    else:
        update("✅ Beginning of list reached.")

def repeat_current():
    play_current_peak()

def switch_mode():
    global _mode
    _mode = "mic" if _mode == "keyboard" else "keyboard"
    update(f"🔀 Mode switched: {_mode.upper()}")
    play_current_peak()

def ignore_current_peak():
    global _ignored_peaks
    _ignored_peaks.add(_current_peak)
    update(f"🚫 Peak {_current_peak + 1} ignored.")

# Getters for export module
def get_peaks():
    return _peaks

def get_keyboard_audio():
    return _keyboard_audio

def get_mic_audios():
    return _mic_audios

def get_ignored_peaks():
    return _ignored_peaks

def get_mode():
    return _mode

def get_current_peak_index():
    return _current_peak

def set_current_peak(index):
    global _current_peak
    if 0 <= index < len(_peaks):
        _current_peak = index
