import os
from pydub import AudioSegment
from status import update
from peaks import (
    get_peaks,
    get_mode,
    get_keyboard_audio,
    get_mic_audios,
    get_ignored_peaks
)

# Parameter
PREVIEW_DURATION_MS = 1000
CONTEXT_DURATION_MS = 15000
PAUSE_DURATION_MS = 500

def extract_guest_name():
    material_folder = os.path.join(os.getcwd(), "material")
    for f in os.listdir(material_folder):
        if "mix" in f.lower():
            base = os.path.splitext(f)[0]
            parts = base.split(" - ")
            if len(parts) > 1:
                return parts[1].split("(")[0].strip()
    return "Unbekannt"

def load_spoken_number(n):
    for ext in [".mp3", ".wav"]:
        path = os.path.join("assets", "zahlen", f"{n}{ext}")
        if os.path.exists(path):
            update(f"🔊 Zahl {n} geladen ({ext})")
            return AudioSegment.from_file(path)
    update(f"⚠️ Keine Sprachdatei für Zahl {n} gefunden.")
    return AudioSegment.silent(duration=300)

def format_peak_time(ms, fps=25):
    total_seconds = ms / 1000
    total_frames = int(total_seconds * fps)
    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def run_export():
    update("✅ [EXPORT] Audioexport gestartet...")

    export_folder = os.path.join(os.getcwd(), "export")
    os.makedirs(export_folder, exist_ok=True)

    peaks = get_peaks()
    ignored = get_ignored_peaks()
    mode = get_mode()

    if not peaks:
        update("❌ Keine Peaks gefunden.")
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
        update("⚠️ Alle Peaks wurden ignoriert.")
        return

    result = segments[0]
    for seg in segments[1:]:
        result += seg

    gastname = extract_guest_name()
    base_filename = f"Keyboardstellen - {gastname}"
    mp3_path = os.path.join(export_folder, base_filename + ".mp3")
    txt_path = os.path.join(export_folder, base_filename + ".txt")

    result.export(mp3_path, format="mp3")

    with open(txt_path, "w") as f:
        for num, peak, start, end in final_timestamps:
            f.write(f"[PEAK {num}]\n")
            f.write(f"peak_time = {format_peak_time(peak)}\n")
            f.write(f"clip_start = {format_peak_time(start)}\n")
            f.write(f"clip_end = {format_peak_time(end)}\n\n")

    update(f"✅ Export abgeschlossen: {mp3_path}")
