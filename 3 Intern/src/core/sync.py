import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve


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


def extract_audio_from_video(video_path, output_path):
    """Extract audio track from video file using ffmpeg directly."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", output_path],
        capture_output=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode(errors='replace')[:200]}")


def load_audio_as_array(path):
    """Load audio file as numpy array. Converts stereo to mono."""
    data, samplerate = sf.read(path)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    return data, samplerate


def calculate_offset(reference, target, downsample_factor=10):
    """Calculate offset between reference and target audio via FFT cross-correlation.

    Uses downsampling to reduce memory, then FFT-based correlation which is
    O((N+M)*log(N+M)) instead of O(N*M) — drastically faster for long recordings.
    """
    ref_ds = reference[::downsample_factor]
    target_ds = target[::downsample_factor]

    # FFT correlation: flip reference, convolve (equivalent to correlate)
    corr = fftconvolve(target_ds, ref_ds[::-1], mode='full')
    lag = np.argmax(corr) - len(ref_ds) + 1

    return lag * downsample_factor


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


def _sync_single_video(video_path, reference_data, ref_sr, temp_dir, fps, status_fn=None):
    """Sync a single video against reference audio. Returns (filename, offset_timecode) or None."""
    def status(msg):
        if status_fn:
            status_fn(msg)

    video_filename = os.path.basename(video_path)
    video_name = os.path.splitext(video_filename)[0]
    temp_audio_path = os.path.join(temp_dir, f"{video_name}_audio.wav")

    status(f"Extracting audio: {video_filename}...")
    extract_audio_from_video(video_path, temp_audio_path)

    target_data, target_sr = load_audio_as_array(temp_audio_path)

    if target_sr != ref_sr:
        status(f"Sample rates differ ({target_sr} vs {ref_sr}), skipping {video_filename}.")
        return None

    status(f"Calculating offset: {video_filename}...")
    offset_samples = calculate_offset(reference_data, target_data)
    offset_seconds = offset_samples / ref_sr

    formatted_offset = format_offset(offset_seconds, fps)
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
    reference_data, ref_sr = load_audio_as_array(reference_path)

    video_offsets = []

    if len(video_files) == 1:
        # Single video — no thread overhead
        result = _sync_single_video(
            video_files[0], reference_data, ref_sr, temp_dir, fps, status_fn
        )
        if result:
            video_offsets.append(result)
    else:
        status(f"Synchronisiere {len(video_files)} Videos parallel...")
        with ThreadPoolExecutor(max_workers=len(video_files)) as executor:
            futures = {
                executor.submit(
                    _sync_single_video, video_path,
                    reference_data, ref_sr, temp_dir, fps, status_fn
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
                    status(f"Sync failed for {os.path.basename(video_path)}: {e}")

    cleanup_temp(temp_dir)

    return video_offsets
