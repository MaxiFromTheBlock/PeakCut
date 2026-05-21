import os
import subprocess
from abc import ABC, abstractmethod
from urllib.parse import quote
from xml.sax.saxutils import escape

from pydub import AudioSegment

from utils import TEMP_DIR, ASSETS_DIR, parse_timecode_to_ms, ms_to_timecode, ms_to_frames, get_logger
from core.media_probe import run_ffprobe

_log = get_logger("peakcut.export")

PAUSE_DURATION_MS = 500
_TTS_TIMEOUT_S = 5
_TTS_FALLBACK_SILENCE_MS = 300
_TTS_NUMBER_GAP_MS = 100


def generate_tts_number(n, temp_dir, voice):
    """Generate number via macOS TTS (say command)."""
    os.makedirs(temp_dir, exist_ok=True)
    aiff_path = os.path.join(temp_dir, f"tts_{n}.aiff")

    try:
        result = subprocess.run(
            ["say", "-v", voice, "-o", aiff_path, str(n)],
            capture_output=True,
            timeout=_TTS_TIMEOUT_S
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
    return AudioSegment.silent(duration=_TTS_FALLBACK_SILENCE_MS)


def _file_url(filepath):
    """Convert file path to file:// URL for FCP XML."""
    abs_path = os.path.abspath(filepath)
    encoded = quote(abs_path, safe='/:')
    return f"file://localhost{encoded}"


_ms_to_frames = ms_to_frames  # Local alias for readability in XML generation


def _probe_video_info(video_path):
    """Probe video file for resolution using ffprobe. Returns (width, height) or (3840, 2160) as fallback."""
    out = run_ffprobe(["-v", "quiet", "-select_streams", "v:0",
                       "-show_entries", "stream=width,height",
                       "-of", "csv=p=0", video_path])
    if out and out.strip():
        parts = out.strip().split(",")
        if len(parts) >= 2:
            try:
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
    return 3840, 2160


def _probe_audio_info(audio_path):
    """Probe audio file for sample rate, bit depth, and channels using ffprobe.

    Returns (sample_rate, bit_depth, channels) with fallbacks (48000, 16, 2).
    """
    sample_rate, bit_depth, channels = 48000, 16, 2
    out = run_ffprobe(["-v", "quiet", "-select_streams", "a:0",
                       "-show_entries",
                       "stream=sample_rate,bits_per_sample,channels",
                       "-of", "flat", audio_path])
    if out:
        for line in out.strip().splitlines():
            key, _, val = line.partition("=")
            val = val.strip('"')
            if key.endswith("sample_rate") and val.isdigit():
                sample_rate = int(val)
            elif key.endswith("bits_per_sample") and val.isdigit() and int(val) > 0:
                bit_depth = int(val)
            elif key.endswith("channels") and val.isdigit():
                channels = int(val)
    return sample_rate, bit_depth, channels


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
        _log.info("MP3 export starting (%d peaks)", len(session.peaks))
        os.makedirs(session.project.export_dir, exist_ok=True)

        # Ensure audio is loaded (lazy loading after subprocess analysis)
        session.load_audio_lazy()

        mic_audios = session.mic_audios
        config = session.config
        voice = config.get("tts_voice", "Anna")

        # Quickfix 2026-05-21 (vor #71a Task 1): wenn die Mix-Datei
        # in mic_tracks einsortiert ist (heutiges _categorize_files-
        # Verhalten), darf sie NICHT mit den Einzel-Mics overlay-
        # summiert werden — sonst Phasing (Mix enthält die Mics
        # bereits). In dem Fall ziehen wir nur den Mix als Sprach-
        # Quelle. Der saubere audio_routing.py-Helper folgt mit
        # #71a Task 1, dieser Quickfix wird dann durch ihn ersetzt.
        mix_path = session.project.get_reference_track()
        mix_idx = None
        if mix_path:
            try:
                mix_idx = session.project.mic_tracks.index(mix_path)
            except ValueError:
                mix_idx = None

        active_peaks = session.get_active_peaks()
        if not active_peaks or not mic_audios:
            return ""

        segments = []
        for peak_num, peak in active_peaks:
            number_audio = load_spoken_number(peak_num, TEMP_DIR, ASSETS_DIR, voice)
            start = peak.in_point_ms
            end = peak.out_point_ms
            if mix_idx is not None and mix_idx < len(mic_audios):
                # Mix vorhanden -> nur Mix-Spur, kein Overlay
                segment = mic_audios[mix_idx][start:end]
            else:
                # Kein Mix -> alte Overlay-Logik (Backward-Compat)
                segment = mic_audios[0][start:end]
                for m in mic_audios[1:]:
                    segment = segment.overlay(m[start:end])
            segments.append(number_audio + AudioSegment.silent(duration=_TTS_NUMBER_GAP_MS) + segment)
            segments.append(AudioSegment.silent(duration=PAUSE_DURATION_MS))

        if not segments:
            return ""

        result = segments[0]
        for seg in segments[1:]:
            result += seg

        gastname = session.project.guest_name
        mp3_path = os.path.join(session.project.export_dir,
                                f"Keyboardstellen - {gastname}.mp3")
        result.export(mp3_path, format="mp3", bitrate="192k")

        _log.info("MP3 export done: %s (%d active peaks)", mp3_path, len(active_peaks))
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

        # Task #72 (Smoke 2026-05-20): nicht mic_tracks[0] direkt nehmen —
        # die Reihenfolge hängt von der Import-Reihenfolge ab, also würden
        # zwei Re-Imports desselben Datei-Satzes unterschiedliche XMLs
        # erzeugen (channelcount 1↔2 je nachdem ob MIC1 oder Mix zuerst
        # kommt). Stattdessen die Mix-Spur deterministisch via
        # get_reference_track wählen, Fallback auf mics[0]. Gleiche
        # Semantik wie SinnabschnittExporter.
        sample_rate, bit_depth, channels = 48000, 16, 2
        if audio_paths:
            ref = (session.project.get_reference_track()
                   or audio_paths[0])
            sample_rate, bit_depth, channels = _probe_audio_info(ref)

        # Calculate total sequence duration in frames
        total_frames = 0
        for _, peak in active_peaks:
            in_f = _ms_to_frames(peak.in_point_ms, fps)
            out_f = _ms_to_frames(peak.out_point_ms, fps)
            total_frames += out_f - in_f

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
                    source_out = max(0, peak.out_point_ms + offset_ms)

                    source_in_f = _ms_to_frames(source_in, fps)
                    source_out_f = _ms_to_frames(source_out, fps)
                    clip_dur_f = source_out_f - source_in_f
                    rec_start_f = record_pos
                    rec_end_f = record_pos + clip_dur_f

                    f.write(f'          <clipitem id="{clip_id}">\n')
                    f.write(f'            <name>{escape(os.path.splitext(video_file)[0])}</name>\n')
                    f.write(f'            <duration>{clip_dur_f}</duration>\n')
                    f.write(f'            {rate_block}\n')
                    f.write(f'            <start>{rec_start_f}</start>\n')
                    f.write(f'            <end>{rec_end_f}</end>\n')
                    f.write(f'            <in>{source_in_f}</in>\n')
                    f.write(f'            <out>{source_out_f}</out>\n')

                    if clip_idx == 0:
                        f.write(f'            <file id="{file_id}">\n')
                        f.write(f'              <name>{escape(video_file)}</name>\n')
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
                        f.write(f'                    <depth>{bit_depth}</depth>\n')
                        f.write(f'                  </samplecharacteristics>\n')
                        f.write(f'                  <channelcount>{channels}</channelcount>\n')
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
            f.write(f'            <depth>{bit_depth}</depth>\n')
            f.write(f'          </samplecharacteristics>\n')
            f.write(f'        </format>\n')

            for track_idx, audio_path in enumerate(audio_paths):
                file_id = f"file-audio-{track_idx + 1}"
                audio_file = os.path.basename(audio_path)

                f.write(f'        <track>\n')

                record_pos = 0
                for clip_idx, (peak_num, peak) in enumerate(active_peaks):
                    clip_id = f"clipitem-a{track_idx + 1}-{clip_idx + 1}"
                    source_in_f = _ms_to_frames(peak.in_point_ms, fps)
                    source_out_f = _ms_to_frames(peak.out_point_ms, fps)
                    clip_dur_f = source_out_f - source_in_f
                    rec_start_f = record_pos
                    rec_end_f = record_pos + clip_dur_f

                    audio_name = os.path.splitext(audio_file)[0]
                    f.write(f'          <clipitem id="{clip_id}">\n')
                    f.write(f'            <name>{escape(audio_name)}</name>\n')
                    f.write(f'            <duration>{clip_dur_f}</duration>\n')
                    f.write(f'            {rate_block}\n')
                    f.write(f'            <start>{rec_start_f}</start>\n')
                    f.write(f'            <end>{rec_end_f}</end>\n')
                    f.write(f'            <in>{source_in_f}</in>\n')
                    f.write(f'            <out>{source_out_f}</out>\n')

                    if clip_idx == 0:
                        f.write(f'            <file id="{file_id}">\n')
                        f.write(f'              <name>{escape(audio_file)}</name>\n')
                        f.write(f'              <pathurl>{_file_url(audio_path)}</pathurl>\n')
                        f.write(f'              {rate_block}\n')
                        f.write(f'              {tc_block}\n')
                        f.write(f'              <media>\n')
                        f.write(f'                <audio>\n')
                        f.write(f'                  <samplecharacteristics>\n')
                        f.write(f'                    <samplerate>{sample_rate}</samplerate>\n')
                        f.write(f'                    <depth>{bit_depth}</depth>\n')
                        f.write(f'                  </samplecharacteristics>\n')
                        f.write(f'                  <channelcount>{channels}</channelcount>\n')
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
