import os
import subprocess
from pydub import AudioSegment
from status import update
from utils import format_peak_time, MATERIAL_DIR, EXPORT_DIR, TEMP_DIR, ASSETS_DIR
import config
from peaks import (
    get_peaks,
    get_mic_audios,
    get_ignored_peaks
)
from sync import get_video_offsets

PAUSE_DURATION_MS = 500


def ms_to_timecode(ms, fps):
    """Convert milliseconds to SMPTE timecode HH:MM:SS:FF"""
    total_frames = int(ms / 1000 * fps)
    frames = total_frames % fps
    total_seconds = total_frames // fps
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


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
    voice = config.get("tts_voice")

    try:
        result = subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, str(n)],
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
    mic_audios = get_mic_audios()

    if not peaks:
        update("❌ No peaks found.")
        return

    if not mic_audios:
        update("❌ No mic audio files found.")
        return

    segments = []
    final_timestamps = []
    context_duration = config.get("context_duration_ms")

    counter = 1
    for i, t in enumerate(peaks):
        if i in ignored:
            continue
        number_audio = load_spoken_number(counter)
        start = max(0, t - context_duration)
        end = t + context_duration
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

    # Also create EDL
    run_edl_export(gastname)

    update(f"✅ Export complete: MP3 + TXT + EDL")


def run_edl_export(gastname):
    """Export peaks as EDL file (CMX 3600 format) with real clips."""
    peaks = get_peaks()
    ignored = get_ignored_peaks()
    fps = config.get("fps")
    context_duration = config.get("context_duration_ms")

    if not peaks:
        return

    edl_path = os.path.join(EXPORT_DIR, f"Keyboardstellen - {gastname}.edl")

    with open(edl_path, "w") as f:
        f.write(f"TITLE: PeakCut Export - {gastname}\n")
        f.write("FCM: NON-DROP FRAME\n\n")

        event_num = 1
        record_position_ms = 0

        for i, peak_ms in enumerate(peaks):
            if i in ignored:
                continue

            # Source timecodes (in original media)
            source_in_ms = max(0, peak_ms - context_duration)
            source_out_ms = peak_ms + context_duration
            clip_duration_ms = source_out_ms - source_in_ms

            # Record timecodes (position in sequence)
            record_in_ms = record_position_ms
            record_out_ms = record_position_ms + clip_duration_ms

            source_in = ms_to_timecode(source_in_ms, fps)
            source_out = ms_to_timecode(source_out_ms, fps)
            record_in = ms_to_timecode(record_in_ms, fps)
            record_out = ms_to_timecode(record_out_ms, fps)

            f.write(f"{event_num:03d}  AX       V     C        ")
            f.write(f"{source_in} {source_out} {record_in} {record_out}\n")
            f.write(f"* FROM CLIP NAME: Peak {event_num}\n\n")

            record_position_ms = record_out_ms
            event_num += 1
