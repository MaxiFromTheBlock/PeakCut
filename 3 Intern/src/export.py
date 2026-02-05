import os
import subprocess
from urllib.parse import quote
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

    # Also create FCP XML for Premiere Pro
    run_xml_export(gastname)

    update(f"✅ Export complete: MP3 + TXT + XML")


def _file_url(filepath):
    """Convert file path to file:// URL for FCP XML."""
    abs_path = os.path.abspath(filepath)
    encoded = quote(abs_path, safe='/:')
    return f"file://localhost{encoded}"


def _ms_to_frames(ms, fps):
    """Convert milliseconds to frame count."""
    return int(ms / 1000 * fps)


def _parse_timecode_to_ms(tc_str, fps):
    """Parse timecode string (HH:MM:SS:FF) to milliseconds."""
    negative = tc_str.startswith("-")
    tc_str = tc_str.lstrip("-")
    parts = tc_str.split(":")
    if len(parts) != 4:
        return 0
    hours, minutes, seconds, frames = map(int, parts)
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + int(frames * 1000 / fps)
    return -total_ms if negative else total_ms


def run_xml_export(gastname):
    """Export peaks as FCP XML for Premiere Pro with all video + audio tracks."""
    peaks = get_peaks()
    ignored = get_ignored_peaks()
    fps = config.get("fps")
    context_duration = config.get("context_duration_ms")
    video_offsets = get_video_offsets()

    if not peaks:
        return

    # Find media files in MATERIAL_DIR
    video_files = []
    audio_files = []
    for f in sorted(os.listdir(MATERIAL_DIR)):
        fl = f.lower()
        if fl.endswith(('.mp4', '.mov')):
            video_files.append(f)
        elif fl.endswith(('.wav', '.mp3')):
            if not any(kw in fl for kw in ["keyboard", "keys", "klavier"]):
                audio_files.append(f)

    # Build offset lookup (video filename → offset in ms)
    offset_lookup = {}
    for video_filename, offset_str in video_offsets:
        offset_lookup[video_filename] = _parse_timecode_to_ms(offset_str, fps)

    # Filter active peaks
    active_peaks = []
    peak_num = 1
    for i, peak_ms in enumerate(peaks):
        if i not in ignored:
            active_peaks.append((peak_num, peak_ms))
            peak_num += 1

    if not active_peaks:
        return

    # Calculate total sequence duration in frames
    total_frames = 0
    for _, peak_ms in active_peaks:
        clip_in = max(0, peak_ms - context_duration)
        clip_out = peak_ms + context_duration
        total_frames += _ms_to_frames(clip_out - clip_in, fps)

    # Rate block (reused everywhere)
    rate_block = f"""<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"""

    # Timecode block
    tc_block = f"""<timecode>
        {rate_block}
        <string>00:00:00:00</string>
        <frame>0</frame>
        <displayformat>NDF</displayformat>
      </timecode>"""

    xml_path = os.path.join(EXPORT_DIR, f"Keyboardstellen - {gastname}.xml")

    with open(xml_path, "w") as f:
        # Header
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE xmeml>\n')
        f.write('<xmeml version="5">\n')
        f.write(f'  <sequence id="peakcut-sequence">\n')
        f.write(f'    <name>PeakCut</name>\n')
        f.write(f'    <duration>{total_frames}</duration>\n')
        f.write(f'    {rate_block}\n')
        f.write(f'    {tc_block}\n')
        f.write(f'    <format>\n')
        f.write(f'      <samplecharacteristics>\n')
        f.write(f'        <width>3840</width>\n')
        f.write(f'        <height>2160</height>\n')
        f.write(f'        <pixelaspectratio>Square</pixelaspectratio>\n')
        f.write(f'        {rate_block}\n')
        f.write(f'      </samplecharacteristics>\n')
        f.write(f'    </format>\n')
        f.write(f'    <media>\n')

        # === VIDEO TRACKS ===
        f.write(f'      <video>\n')
        f.write(f'        <format>\n')
        f.write(f'          <samplecharacteristics>\n')
        f.write(f'            <width>3840</width>\n')
        f.write(f'            <height>2160</height>\n')
        f.write(f'            <pixelaspectratio>Square</pixelaspectratio>\n')
        f.write(f'            {rate_block}\n')
        f.write(f'          </samplecharacteristics>\n')
        f.write(f'        </format>\n')

        for track_idx, video_file in enumerate(video_files):
            file_id = f"file-video-{track_idx + 1}"
            video_path = os.path.join(MATERIAL_DIR, video_file)
            video_name = os.path.splitext(video_file)[0]
            offset_ms = offset_lookup.get(video_file, 0)

            f.write(f'        <track>\n')

            record_pos = 0
            for clip_idx, (peak_num, peak_ms) in enumerate(active_peaks):
                clip_id = f"clipitem-v{track_idx + 1}-{clip_idx + 1}"
                adjusted_peak = peak_ms + offset_ms
                source_in = max(0, adjusted_peak - context_duration)
                source_out = adjusted_peak + context_duration
                clip_duration = source_out - source_in

                source_in_f = _ms_to_frames(source_in, fps)
                source_out_f = _ms_to_frames(source_out, fps)
                clip_dur_f = _ms_to_frames(clip_duration, fps)
                rec_start_f = record_pos
                rec_end_f = record_pos + clip_dur_f

                f.write(f'          <clipitem id="{clip_id}">\n')
                f.write(f'            <name>Peak {peak_num}</name>\n')
                f.write(f'            <duration>{clip_dur_f}</duration>\n')
                f.write(f'            {rate_block}\n')
                f.write(f'            <start>{rec_start_f}</start>\n')
                f.write(f'            <end>{rec_end_f}</end>\n')
                f.write(f'            <in>{source_in_f}</in>\n')
                f.write(f'            <out>{source_out_f}</out>\n')

                # First clip defines the file, rest reference it
                if clip_idx == 0:
                    f.write(f'            <file id="{file_id}">\n')
                    f.write(f'              <name>{video_file}</name>\n')
                    f.write(f'              <pathurl>{_file_url(video_path)}</pathurl>\n')
                    f.write(f'              {rate_block}\n')
                    f.write(f'              {tc_block}\n')
                    f.write(f'              <media>\n')
                    f.write(f'                <video>\n')
                    f.write(f'                  <samplecharacteristics>\n')
                    f.write(f'                    <width>3840</width>\n')
                    f.write(f'                    <height>2160</height>\n')
                    f.write(f'                    <pixelaspectratio>Square</pixelaspectratio>\n')
                    f.write(f'                    {rate_block}\n')
                    f.write(f'                  </samplecharacteristics>\n')
                    f.write(f'                </video>\n')
                    f.write(f'                <audio>\n')
                    f.write(f'                  <samplecharacteristics>\n')
                    f.write(f'                    <samplerate>48000</samplerate>\n')
                    f.write(f'                    <depth>16</depth>\n')
                    f.write(f'                  </samplecharacteristics>\n')
                    f.write(f'                  <channelcount>2</channelcount>\n')
                    f.write(f'                </audio>\n')
                    f.write(f'              </media>\n')
                    f.write(f'            </file>\n')
                else:
                    f.write(f'            <file id="{file_id}"/>\n')

                f.write(f'          </clipitem>\n')
                record_pos = rec_end_f

            f.write(f'        </track>\n')

        f.write(f'      </video>\n')

        # === AUDIO TRACKS ===
        f.write(f'      <audio>\n')
        f.write(f'        <format>\n')
        f.write(f'          <samplecharacteristics>\n')
        f.write(f'            <samplerate>48000</samplerate>\n')
        f.write(f'            <depth>16</depth>\n')
        f.write(f'          </samplecharacteristics>\n')
        f.write(f'        </format>\n')

        for track_idx, audio_file in enumerate(audio_files):
            file_id = f"file-audio-{track_idx + 1}"
            audio_path = os.path.join(MATERIAL_DIR, audio_file)

            f.write(f'        <track>\n')

            record_pos = 0
            for clip_idx, (peak_num, peak_ms) in enumerate(active_peaks):
                clip_id = f"clipitem-a{track_idx + 1}-{clip_idx + 1}"
                source_in = max(0, peak_ms - context_duration)
                source_out = peak_ms + context_duration
                clip_duration = source_out - source_in

                source_in_f = _ms_to_frames(source_in, fps)
                source_out_f = _ms_to_frames(source_out, fps)
                clip_dur_f = _ms_to_frames(clip_duration, fps)
                rec_start_f = record_pos
                rec_end_f = record_pos + clip_dur_f

                audio_name = os.path.splitext(audio_file)[0]
                f.write(f'          <clipitem id="{clip_id}">\n')
                f.write(f'            <name>{audio_name}</name>\n')
                f.write(f'            <duration>{clip_dur_f}</duration>\n')
                f.write(f'            {rate_block}\n')
                f.write(f'            <start>{rec_start_f}</start>\n')
                f.write(f'            <end>{rec_end_f}</end>\n')
                f.write(f'            <in>{source_in_f}</in>\n')
                f.write(f'            <out>{source_out_f}</out>\n')

                if clip_idx == 0:
                    f.write(f'            <file id="{file_id}">\n')
                    f.write(f'              <name>{audio_file}</name>\n')
                    f.write(f'              <pathurl>{_file_url(audio_path)}</pathurl>\n')
                    f.write(f'              {rate_block}\n')
                    f.write(f'              {tc_block}\n')
                    f.write(f'              <media>\n')
                    f.write(f'                <audio>\n')
                    f.write(f'                  <samplecharacteristics>\n')
                    f.write(f'                    <samplerate>48000</samplerate>\n')
                    f.write(f'                    <depth>16</depth>\n')
                    f.write(f'                  </samplecharacteristics>\n')
                    f.write(f'                  <channelcount>2</channelcount>\n')
                    f.write(f'                </audio>\n')
                    f.write(f'              </media>\n')
                    f.write(f'            </file>\n')
                else:
                    f.write(f'            <file id="{file_id}"/>\n')

                f.write(f'            <sourcetrack>\n')
                f.write(f'              <mediatype>audio</mediatype>\n')
                f.write(f'            </sourcetrack>\n')
                f.write(f'          </clipitem>\n')
                record_pos = rec_end_f

            f.write(f'        </track>\n')

        f.write(f'      </audio>\n')

        # Close
        f.write(f'    </media>\n')
        f.write(f'  </sequence>\n')
        f.write(f'</xmeml>\n')
