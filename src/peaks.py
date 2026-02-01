import os
import numpy as np
from pydub import AudioSegment
import simpleaudio as sa
from status import update

# Globale Variablen zur Navigation
_peaks = []
_current_peak = 0
_keyboard_audio = None
_mic_audios = []
_mode = "keyboard"  # oder "mic"
_ignored_peaks = set()

# Parameter
PREVIEW_DURATION_MS = 1000   # Bei Keyboard
CONTEXT_DURATION_MS = 15000  # Bei Mikrofon

def detect_peaks(audio_path, threshold_factor=0.4, min_gap_ms=15000):
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

def format_peak_time(ms, fps=25):
    total_seconds = ms / 1000
    total_frames = int(total_seconds * fps)
    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def run_peak_analysis():
    global _peaks, _current_peak, _keyboard_audio, _mic_audios, _mode
    update("✅ [PEAKS] Starte Peakanalyse...")

    material_folder = os.path.join(os.getcwd(), 'material')
    export_folder = os.path.join(os.getcwd(), 'export')
    os.makedirs(export_folder, exist_ok=True)

    files = os.listdir(material_folder)
    keyboard_file = None
    mic_files = []

    for f in files:
        if any(kw in f.lower() for kw in ["keyboard", "keys", "klavier"]):
            keyboard_file = os.path.join(material_folder, f)
        elif f.lower().endswith(".wav"):
            mic_files.append(os.path.join(material_folder, f))

    mic_files = [f for f in mic_files if keyboard_file not in f]

    if not keyboard_file:
        update("❌ Keine Keyboard-Datei gefunden.")
        return

    _peaks = detect_peaks(keyboard_file)
    _keyboard_audio = AudioSegment.from_wav(keyboard_file)
    _mic_audios = [AudioSegment.from_wav(f) for f in mic_files]
    _current_peak = 0
    _mode = "keyboard"

    update(f"✅ {_peaks.__len__()} Peaks erkannt.")
    for idx, t in enumerate(_peaks, 1):
        update(f"{idx}: {t / 1000:.2f}s")

    update("▶️ Analyse abgeschlossen. Drücke PLAY, um zu starten.")

def play_current_peak(index=None):
    global _current_peak
    if not _peaks:
        update("❌ Keine Peaks geladen.")
        return

    if index is not None:
        _current_peak = index

    if _current_peak >= len(_peaks):
        update("❌ Ungültiger Peakindex.")
        return

    time_ms = _peaks[_current_peak]

    if _mode == "keyboard":
        segment = _keyboard_audio[time_ms:time_ms + PREVIEW_DURATION_MS]
    else:
        start = max(0, time_ms - CONTEXT_DURATION_MS)
        end = time_ms + CONTEXT_DURATION_MS
        segment = _mic_audios[0][start:end]
        for audio in _mic_audios[1:]:
            segment = segment.overlay(audio[start:end])

    update(f"▶️ Spiele Peak {_current_peak + 1} ({_mode})...")
    play_audio(segment)

def play_audio(segment):
    audio_data = segment.set_channels(1).set_frame_rate(44100).set_sample_width(2)
    raw = audio_data.raw_data
    try:
        sa.stop_all()
        sa.play_buffer(raw, 1, 2, 44100)
    except Exception as e:
        update(f"❌ Fehler bei der Audiowiedergabe: {e}")

def stop_playback():
    try:
        sa.stop_all()
        update("🛑 Wiedergabe gestoppt.")
    except Exception as e:
        update(f"⚠ Fehler beim Stoppen: {e}")

def go_forward():
    global _current_peak
    if _current_peak < len(_peaks) - 1:
        _current_peak += 1
        play_current_peak()
    else:
        update("✅ Ende der Liste erreicht.")

def go_back():
    global _current_peak
    if _current_peak > 0:
        _current_peak -= 1
        play_current_peak()
    else:
        update("✅ Anfang der Liste erreicht.")

def repeat_current():
    play_current_peak()

def switch_mode():
    global _mode
    _mode = "mic" if _mode == "keyboard" else "keyboard"
    update(f"🔀 Modus gewechselt: {_mode.upper()}")
    play_current_peak()

def ignore_current_peak():
    global _ignored_peaks
    _ignored_peaks.add(_current_peak)
    update(f"🚫 Peak {_current_peak + 1} ignoriert.")

# 🔓 Getter für Exportmodul
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
