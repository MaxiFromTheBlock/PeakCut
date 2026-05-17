import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

from utils import get_logger, FFMPEG_BIN

_log = get_logger("peakcut.sync")
_FFMPEG_EXTRACT_TIMEOUT_S = 300
_SYNC_WINDOW_S = 600  # First 10 minutes for fast sync
_CORRELATION_THRESHOLD = 0.1  # Minimum normalized correlation for a valid sync


def cleanup_temp(temp_dir):
    """Delete all files in temp folder."""
    if os.path.exists(temp_dir):
        for f in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, f)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception:
                pass


def extract_audio_from_video(video_path, output_path, target_sr=None):
    """Extract audio track from video file using ffmpeg directly.

    If target_sr is given, resample to that rate (ensures matching sample rates for correlation).
    """
    cmd = [FFMPEG_BIN, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le"]
    if target_sr:
        cmd.extend(["-ar", str(target_sr)])
    cmd.append(output_path)
    _log.debug("ffmpeg cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, timeout=_FFMPEG_EXTRACT_TIMEOUT_S)
    if result.returncode != 0:
        err_msg = result.stderr.decode(errors='replace')[:200]
        _log.error("ffmpeg failed for %s: %s", video_path, err_msg)
        raise RuntimeError(f"ffmpeg failed: {err_msg}")


def load_audio_as_array(path, max_seconds=None):
    """Load audio file as numpy array. Converts stereo to mono.

    If max_seconds is given, only load that many seconds from the start.
    """
    if max_seconds is None:
        data, samplerate = sf.read(path)
    else:
        # Echtes Teil-Lesen: nur n Frames von der Platte holen, statt
        # voll zu lesen und danach zu schneiden (HC-3). Numerisch
        # identisch, weil die Mono-Mittelung pro Frame unabhängig ist
        # (mean(full)[:n] == mean(full[:n]) == mean(read n)).
        samplerate = sf.info(path).samplerate
        max_samples = int(samplerate * max_seconds)
        data, samplerate = sf.read(path, frames=max_samples)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    return data, samplerate


def calculate_offset(reference, target, downsample_factor=10):
    """Calculate offset between reference and target audio via FFT cross-correlation.

    Uses downsampling to reduce memory, then FFT-based correlation which is
    O((N+M)*log(N+M)) instead of O(N*M) — drastically faster for long recordings.

    Returns (offset_samples, confidence) where confidence is 0.0-1.0.
    """
    ref_ds = reference[::downsample_factor]
    target_ds = target[::downsample_factor]

    # FFT correlation: flip reference, convolve (equivalent to correlate)
    corr = fftconvolve(target_ds, ref_ds[::-1], mode='full')
    peak_idx = np.argmax(corr)
    lag = peak_idx - len(ref_ds) + 1

    # Normalized confidence: peak correlation vs. energy of inputs
    peak_val = corr[peak_idx]
    energy = np.sqrt(np.sum(ref_ds ** 2) * np.sum(target_ds ** 2))
    confidence = float(peak_val / energy) if energy > 0 else 0.0

    return lag * downsample_factor, confidence


def format_offset(offset_seconds, fps=25):
    """Convert offset in seconds to SMPTE timecode string."""
    total_frames = int(offset_seconds * fps)
    sign = "-" if total_frames < 0 else ""
    total_frames = abs(total_frames)

    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps

    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def _sync_single_video(video_path, reference_window, ref_sr,
                       ref_full_loader, temp_dir, fps, status_fn=None):
    """Sync a single video against reference audio. Returns (filename, offset_timecode) or None.

    reference_window = nur das _SYNC_WINDOW_S-Anfangsfenster der Referenz.
    ref_full_loader() = lazy, thread-sicher, lädt die VOLLE Referenz nur
    beim ersten Fallback (geteilt über parallele Kameras).
    """
    def status(msg):
        if status_fn:
            status_fn(msg)

    video_filename = os.path.basename(video_path)
    video_name = os.path.splitext(video_filename)[0]
    temp_audio_path = os.path.join(temp_dir, f"{video_name}_audio.wav")

    status(f"Extracting audio: {video_filename}...")
    try:
        extract_audio_from_video(video_path, temp_audio_path, target_sr=ref_sr)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        _log.error("Audio extraction failed for %s: %s", video_filename, e)
        raise RuntimeError(f"Audio-Extraktion fehlgeschlagen für {video_filename}") from e

    # Schneller Pfad: nur das Anfangsfenster von der Platte holen
    status(f"Calculating offset: {video_filename}...")
    target_window, _ = load_audio_as_array(
        temp_audio_path, max_seconds=_SYNC_WINDOW_S)
    offset_samples, confidence = calculate_offset(
        reference_window, target_window)

    if confidence < _CORRELATION_THRESHOLD:
        _log.info("Sync %s: weak correlation (%.4f) with %ds window, retrying with full audio",
                  video_filename, confidence, _SYNC_WINDOW_S)
        status(f"Retrying full sync: {video_filename}...")
        reference_full = ref_full_loader()
        target_full, _ = load_audio_as_array(temp_audio_path)
        offset_samples, confidence = calculate_offset(
            reference_full, target_full)

    offset_seconds = offset_samples / ref_sr

    formatted_offset = format_offset(offset_seconds, fps)
    _log.info("Sync %s: offset=%s (%.3fs, %d samples, confidence=%.4f)",
              video_filename, formatted_offset, offset_seconds, offset_samples, confidence)
    status(f"{video_filename} Offset: {formatted_offset}")
    return (video_filename, formatted_offset)


def sync_videos(video_files, reference_path, temp_dir, fps=25, status_fn=None):
    """Sync videos with reference audio in parallel. Returns list of (filename, offset_timecode).

    Each video is synced in its own thread. Audio extraction spawns ffmpeg subprocesses
    and correlation uses numpy (both release the GIL), so threads give real parallelism.
    """
    if not video_files or not reference_path:
        return []

    def status(msg):
        if status_fn:
            status_fn(msg)

    cleanup_temp(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    status("Loading reference audio...")
    reference_window, ref_sr = load_audio_as_array(
        reference_path, max_seconds=_SYNC_WINDOW_S)

    # Volle Referenz nur lazy beim ersten Fallback laden — und nur EINMAL,
    # auch wenn mehrere Kameras parallel zurückfallen (Lock + Cache).
    _ref_full_cache = {}
    _ref_full_lock = threading.Lock()

    def ref_full_loader():
        with _ref_full_lock:
            if "data" not in _ref_full_cache:
                full, full_sr = load_audio_as_array(reference_path)
                if full_sr != ref_sr:
                    raise RuntimeError(
                        f"Referenz-Samplerate inkonsistent: "
                        f"Fenster {ref_sr} vs. voll {full_sr}")
                _ref_full_cache["data"] = full
            return _ref_full_cache["data"]

    video_offsets = []

    if len(video_files) == 1:
        # Single video — no thread overhead
        result = _sync_single_video(
            video_files[0], reference_window, ref_sr, ref_full_loader,
            temp_dir, fps, status_fn
        )
        if result:
            video_offsets.append(result)
    else:
        status(f"Synchronisiere {len(video_files)} Videos parallel...")
        with ThreadPoolExecutor(max_workers=len(video_files)) as executor:
            futures = {
                executor.submit(
                    _sync_single_video, video_path,
                    reference_window, ref_sr, ref_full_loader,
                    temp_dir, fps, status_fn
                ): video_path
                for video_path in video_files
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        video_offsets.append(result)
                except Exception as e:
                    video_path = futures[future]
                    _log.error("Sync failed for %s: %s", os.path.basename(video_path), e, exc_info=True)
                    status(f"Sync failed for {os.path.basename(video_path)}: {e}")

    cleanup_temp(temp_dir)

    return video_offsets
