import os
import sys
import subprocess
from abc import ABC, abstractmethod
from urllib.parse import quote

from pydub import AudioSegment

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import TEMP_DIR, ASSETS_DIR, parse_timecode_to_ms, ms_to_timecode, ms_to_frames


PAUSE_DURATION_MS = 500


def extract_guest_name(file_paths: list[str]) -> str:
    """Extract guest name from 'mix' filename among the given file paths.

    Expected patterns: "Prefix - Gastname mix.wav", "Prefix - Gastname (mix).wav"
    """
    import re
    for f in file_paths:
        name = os.path.basename(f)
        if "mix" in name.lower():
            base = os.path.splitext(name)[0]
            parts = base.split(" - ")
            if len(parts) > 1:
                guest = parts[1].split("(")[0].strip()
                guest = re.sub(r'\s*mix\s*$', '', guest, flags=re.IGNORECASE).strip()
                if guest:
                    return guest
    return "Unknown"


def generate_tts_number(n, temp_dir, voice):
    """Generate number via macOS TTS (say command)."""
    os.makedirs(temp_dir, exist_ok=True)
    aiff_path = os.path.join(temp_dir, f"tts_{n}.aiff")

    try:
        result = subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, str(n)],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0 and os.path.exists(aiff_path):
            audio = AudioSegment.from_file(aiff_path)
            os.remove(aiff_path)
            return audio
    except Exception:
        pass

    return None


def load_spoken_number(n, temp_dir, assets_dir, voice):
    """Load spoken number: TTS -> MP3 fallback -> silence."""
    # 1. Try TTS
    tts_audio = generate_tts_number(n, temp_dir, voice)
    if tts_audio:
        return tts_audio

    # 2. Fallback: existing MP3/WAV files
    for ext in [".mp3", ".wav"]:
        path = os.path.join(assets_dir, "zahlen", f"{n}{ext}")
        if os.path.exists(path):
            return AudioSegment.from_file(path)

    # 3. Last fallback: silence
    return AudioSegment.silent(duration=300)


def _file_url(filepath):
    """Convert file path to file:// URL for FCP XML."""
    abs_path = os.path.abspath(filepath)
    encoded = quote(abs_path, safe='/:')
    return f"file://localhost{encoded}"


_ms_to_frames = ms_to_frames  # Local alias for readability in XML generation


def _probe_video_info(video_path):
    """Probe video file for resolution using ffprobe. Returns (width, height) or (3840, 2160) as fallback."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 3840, 2160


def _probe_audio_info(audio_path):
    """Probe audio file for sample rate using ffprobe. Returns sample_rate or 48000 as fallback."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except Exception:
        pass
    return 48000


# --- Exporter base class ---

class BaseExporter(ABC):
    """Base class for all exporters."""

    @abstractmethod
    def export(self, session) -> str:
        """Export and return filepath."""
        pass


# --- MP3 Exporter ---

class MP3Exporter(BaseExporter):
    """Export numbered MP3 clips with TTS."""

    def export(self, session) -> str:
        os.makedirs(session.project.export_dir, exist_ok=True)

        # Ensure audio is loaded (lazy loading after subprocess analysis)
        session.load_audio_lazy()

        mic_audios = session.mic_audios
        config = session.config
        voice = config.get("tts_voice", "Anna")

        active_peaks = session.get_active_peaks()
        if not active_peaks or not mic_audios:
            return ""

        segments = []
        for peak_num, peak in active_peaks:
            number_audio = load_spoken_number(peak_num, TEMP_DIR, ASSETS_DIR, voice)
            start = peak.in_point_ms
            end = peak.out_point_ms
            segment = mic_audios[0][start:end]
            for m in mic_audios[1:]:
                segment = segment.overlay(m[start:end])
            segments.append(number_audio + AudioSegment.silent(duration=100) + segment)
            segments.append(AudioSegment.silent(duration=PAUSE_DURATION_MS))

        if not segments:
            return ""

        result = segments[0]
        for seg in segments[1:]:
            result += seg

        gastname = session.project.guest_name
        mp3_path = os.path.join(session.project.export_dir,
                                f"Keyboardstellen - {gastname}.mp3")
        result.export(mp3_path, format="mp3")

        session.status_update.emit(f"MP3 exported: {os.path.basename(mp3_path)}")
        return mp3_path


# --- TXT Exporter ---

class TXTExporter(BaseExporter):
    """Export timecode text file."""

    def export(self, session) -> str:
        os.makedirs(session.project.export_dir, exist_ok=True)

        config = session.config
        fps = config.get("fps", 25)

        active_peaks = session.get_active_peaks()
        if not active_peaks:
            return ""

        gastname = session.project.guest_name
        txt_path = os.path.join(session.project.export_dir,
                                f"Keyboardstellen - {gastname}.txt")

        with open(txt_path, "w") as f:
            # Video offsets (if any)
            if session.video_offsets:
                f.write("=" * 40 + "\n")
                f.write("VIDEO OFFSETS\n")
                f.write("=" * 40 + "\n")
                for video, offset in session.video_offsets:
                    f.write(f"{video}: {offset}\n")
                f.write("\n")

            # Peak timestamps
            f.write("=" * 40 + "\n")
            f.write("KEYBOARD PEAKS\n")
            f.write("=" * 40 + "\n\n")
            for peak_num, peak in active_peaks:
                f.write(f"[PEAK {peak_num}]\n")
                f.write(f"peak_time = {ms_to_timecode(peak.position_ms, fps)}\n")
                f.write(f"clip_start = {ms_to_timecode(peak.in_point_ms, fps)}\n")
                f.write(f"clip_end = {ms_to_timecode(peak.out_point_ms, fps)}\n\n")

        session.status_update.emit(f"TXT exported: {os.path.basename(txt_path)}")
        return txt_path


# --- XML Exporter ---

class XMLExporter(BaseExporter):
    """Export FCP XML for Premiere Pro / Final Cut / DaVinci."""

    def export(self, session) -> str:
        os.makedirs(session.project.export_dir, exist_ok=True)

        config = session.config
        fps = config.get("fps", 25)
        video_offsets = session.video_offsets

        active_peaks = session.get_active_peaks()
        if not active_peaks:
            return ""

        # Use actual imported files (they may not be in material_dir)
        video_paths = list(session.project.videos)
        audio_paths = list(session.project.mic_tracks)

        # Build offset lookup (video filename -> offset in ms)
        offset_lookup = {}
        for video_filename, offset_str in video_offsets:
            offset_lookup[video_filename] = parse_timecode_to_ms(offset_str, fps)

        # Probe media info from first available files
        vid_w, vid_h = 3840, 2160
        if video_paths:
            vid_w, vid_h = _probe_video_info(video_paths[0])

        sample_rate = 48000
        if audio_paths:
            sample_rate = _probe_audio_info(audio_paths[0])

        # Calculate total sequence duration in frames
        total_frames = 0
        for _, peak in active_peaks:
            total_frames += _ms_to_frames(peak.clip_duration_ms, fps)

        rate_block = f"""<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"""
        tc_block = f"""<timecode>
        {rate_block}
        <string>00:00:00:00</string>
        <frame>0</frame>
        <displayformat>NDF</displayformat>
      </timecode>"""

        gastname = session.project.guest_name
        xml_path = os.path.join(session.project.export_dir,
                                f"Keyboardstellen - {gastname}.xml")

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
            f.write(f'        <width>{vid_w}</width>\n')
            f.write(f'        <height>{vid_h}</height>\n')
            f.write(f'        <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'        {rate_block}\n')
            f.write(f'      </samplecharacteristics>\n')
            f.write(f'    </format>\n')
            f.write(f'    <media>\n')

            # === VIDEO TRACKS ===
            f.write(f'      <video>\n')
            f.write(f'        <format>\n')
            f.write(f'          <samplecharacteristics>\n')
            f.write(f'            <width>{vid_w}</width>\n')
            f.write(f'            <height>{vid_h}</height>\n')
            f.write(f'            <pixelaspectratio>Square</pixelaspectratio>\n')
            f.write(f'            {rate_block}\n')
            f.write(f'          </samplecharacteristics>\n')
            f.write(f'        </format>\n')

            for track_idx, video_path in enumerate(video_paths):
                file_id = f"file-video-{track_idx + 1}"
                video_file = os.path.basename(video_path)
                offset_ms = offset_lookup.get(video_file, 0)

                f.write(f'        <track>\n')

                record_pos = 0
                for clip_idx, (peak_num, peak) in enumerate(active_peaks):
                    clip_id = f"clipitem-v{track_idx + 1}-{clip_idx + 1}"
                    source_in = max(0, peak.in_point_ms + offset_ms)
                    source_out = peak.out_point_ms + offset_ms
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

                    if clip_idx == 0:
                        f.write(f'            <file id="{file_id}">\n')
                        f.write(f'              <name>{video_file}</name>\n')
                        f.write(f'              <pathurl>{_file_url(video_path)}</pathurl>\n')
                        f.write(f'              {rate_block}\n')
                        f.write(f'              {tc_block}\n')
                        f.write(f'              <media>\n')
                        f.write(f'                <video>\n')
                        f.write(f'                  <samplecharacteristics>\n')
                        f.write(f'                    <width>{vid_w}</width>\n')
                        f.write(f'                    <height>{vid_h}</height>\n')
                        f.write(f'                    <pixelaspectratio>Square</pixelaspectratio>\n')
                        f.write(f'                    {rate_block}\n')
                        f.write(f'                  </samplecharacteristics>\n')
                        f.write(f'                </video>\n')
                        f.write(f'                <audio>\n')
                        f.write(f'                  <samplecharacteristics>\n')
                        f.write(f'                    <samplerate>{sample_rate}</samplerate>\n')
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
            f.write(f'            <samplerate>{sample_rate}</samplerate>\n')
            f.write(f'            <depth>16</depth>\n')
            f.write(f'          </samplecharacteristics>\n')
            f.write(f'        </format>\n')

            for track_idx, audio_path in enumerate(audio_paths):
                file_id = f"file-audio-{track_idx + 1}"
                audio_file = os.path.basename(audio_path)

                f.write(f'        <track>\n')

                record_pos = 0
                for clip_idx, (peak_num, peak) in enumerate(active_peaks):
                    clip_id = f"clipitem-a{track_idx + 1}-{clip_idx + 1}"
                    source_in = peak.in_point_ms
                    source_out = peak.out_point_ms
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
                        f.write(f'                    <samplerate>{sample_rate}</samplerate>\n')
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

        session.status_update.emit(f"XML exported: {os.path.basename(xml_path)}")
        return xml_path
