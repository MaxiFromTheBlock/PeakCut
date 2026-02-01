import os
import subprocess
from pydub import AudioSegment
from status import update
from utils import format_peak_time, MATERIAL_DIR, EXPORT_DIR, TEMP_DIR, ASSETS_DIR
from peaks import (
    get_peaks,
    get_mode,
    get_keyboard_audio,
    get_mic_audios,
    get_ignored_peaks
)
from sync import get_video_offsets

# Parameter
PREVIEW_DURATION_MS = 1000
CONTEXT_DURATION_MS = 15000
PAUSE_DURATION_MS = 500

def extract_guest_name():
    for f in os.listdir(MATERIAL_DIR):
        if "mix" in f.lower():
            base = os.path.splitext(f)[0]
            parts = base.split(" - ")
            if len(parts) > 1:
                return parts[1].split("(")[0].strip()
    return "Unknown"

def generate_tts_number(n):
    """Generate number via macOS TTS (say command)."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    aiff_path = os.path.join(TEMP_DIR, f"tts_{n}.aiff")

    try:
        # macOS say: -v Anna (German voice), -o output file
        result = subprocess.run(
            ["say", "-v", "Anna", "-o", aiff_path, str(n)],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0 and os.path.exists(aiff_path):
            audio = AudioSegment.from_file(aiff_path)
            os.remove(aiff_path)  # Cleanup
            update(f"🔊 Number {n} generated via TTS")
            return audio
    except Exception as e:
        update(f"⚠️ TTS failed for {n}: {e}")

    return None


def load_spoken_number(n):
    """Load spoken number: TTS → MP3 fallback → silence."""
    # 1. Try TTS
    tts_audio = generate_tts_number(n)
    if tts_audio:
        return tts_audio

    # 2. Fallback: existing MP3/WAV files
    for ext in [".mp3", ".wav"]:
        path = os.path.join(ASSETS_DIR, "zahlen", f"{n}{ext}")
        if os.path.exists(path):
            update(f"🔊 Number {n} loaded ({ext}) [Fallback]")
            return AudioSegment.from_file(path)

    # 3. Last fallback: silence with warning
    update(f"❌ Number {n}: Neither TTS nor MP3 available!")
    return AudioSegment.silent(duration=300)


def run_export():
    update("✅ [EXPORT] Starting audio export...")

    os.makedirs(EXPORT_DIR, exist_ok=True)

    peaks = get_peaks()
    ignored = get_ignored_peaks()
    mode = get_mode()

    if not peaks:
        update("❌ No peaks found.")
        return

    segments = []
    final_timestamps = []

    if mode == "keyboard":
        audio = get_keyboard_audio()
        counter = 1
        for i, t in enumerate(peaks):
            if i in ignored:
                continue
            number_audio = load_spoken_number(counter)
            segment = audio[t:t + PREVIEW_DURATION_MS]
            segments.append(number_audio + AudioSegment.silent(duration=100) + segment)
            segments.append(AudioSegment.silent(duration=PAUSE_DURATION_MS))
            final_timestamps.append((counter, t, t, t + PREVIEW_DURATION_MS))
            counter += 1
    else:
        mic_audios = get_mic_audios()
        counter = 1
        for i, t in enumerate(peaks):
            if i in ignored:
                continue
            number_audio = load_spoken_number(counter)
            start = max(0, t - CONTEXT_DURATION_MS)
            end = t + CONTEXT_DURATION_MS
            segment = mic_audios[0][start:end]
            for m in mic_audios[1:]:
                segment = segment.overlay(m[start:end])
            segments.append(number_audio + AudioSegment.silent(duration=100) + segment)
            segments.append(AudioSegment.silent(duration=PAUSE_DURATION_MS))
            final_timestamps.append((counter, t, start, end))
            counter += 1

    if not segments:
        update("⚠️ All peaks were ignored.")
        return

    result = segments[0]
    for seg in segments[1:]:
        result += seg

    gastname = extract_guest_name()
    base_filename = f"Keyboardstellen - {gastname}"
    mp3_path = os.path.join(EXPORT_DIR, base_filename + ".mp3")
    txt_path = os.path.join(EXPORT_DIR, base_filename + ".txt")

    result.export(mp3_path, format="mp3")

    with open(txt_path, "w") as f:
        # Video offsets (if any)
        video_offsets = get_video_offsets()
        if video_offsets:
            f.write("=" * 40 + "\n")
            f.write("VIDEO OFFSETS\n")
            f.write("=" * 40 + "\n")
            for video, offset in video_offsets:
                f.write(f"{video}: {offset}\n")
            f.write("\n")

        # Peak timestamps
        f.write("=" * 40 + "\n")
        f.write("KEYBOARD PEAKS\n")
        f.write("=" * 40 + "\n\n")
        for num, peak, start, end in final_timestamps:
            f.write(f"[PEAK {num}]\n")
            f.write(f"peak_time = {format_peak_time(peak)}\n")
            f.write(f"clip_start = {format_peak_time(start)}\n")
            f.write(f"clip_end = {format_peak_time(end)}\n\n")

    update(f"✅ Export complete: {mp3_path}")
