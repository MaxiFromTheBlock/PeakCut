import os
import numpy as np
import soundfile as sf
from scipy.signal import correlate
from moviepy.editor import VideoFileClip


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
    """Extract audio track from video file."""
    clip = VideoFileClip(video_path)
    try:
        # logger=None suppresses MoviePy's stdout output that breaks JSON parsing
        clip.audio.write_audiofile(output_path, codec='pcm_s16le', logger=None)
    finally:
        clip.close()  # CRITICAL: Prevent file handle leaks and zombie ffmpeg processes


def load_audio_as_array(path):
    """Load audio file as numpy array. Converts stereo to mono."""
    data, samplerate = sf.read(path)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    return data, samplerate


def calculate_offset(reference, target, downsample_factor=10):
    """Calculate offset between reference and target audio via cross-correlation.

    Uses downsampling to prevent memory explosion on long audio files.
    A 1-hour file at 48kHz would otherwise need ~2.7GB RAM for correlation.
    """
    # Downsample to reduce memory usage (10x = 270MB instead of 2.7GB)
    ref_ds = reference[::downsample_factor]
    target_ds = target[::downsample_factor]

    corr = correlate(target_ds, ref_ds, mode='full')
    lag = np.argmax(corr) - len(ref_ds) + 1

    # Scale back to original sample rate
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


def sync_videos(video_files, reference_path, temp_dir, fps=25, status_fn=None):
    """Sync videos with reference audio. Returns list of (filename, offset_timecode).

    Args:
        video_files: List of video file paths
        reference_path: Path to reference audio file (the 'mix' track)
        temp_dir: Directory for temporary audio extracts
        fps: Framerate for timecode calculation
        status_fn: Optional callback for status messages
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

    for video_path in video_files:
        video_filename = os.path.basename(video_path)
        video_name = os.path.splitext(video_filename)[0]
        temp_audio_path = os.path.join(temp_dir, f"{video_name}_audio.wav")

        status(f"Extracting audio from {video_filename}...")
        extract_audio_from_video(video_path, temp_audio_path)

        target_data, target_sr = load_audio_as_array(temp_audio_path)

        if target_sr != ref_sr:
            status(f"Sample rates differ ({target_sr} vs {ref_sr}), skipping {video_filename}.")
            continue

        status(f"Calculating offset for {video_filename}...")
        offset_samples = calculate_offset(reference_data, target_data)
        offset_seconds = offset_samples / ref_sr

        formatted_offset = format_offset(offset_seconds, fps)
        video_offsets.append((video_filename, formatted_offset))
        status(f"{video_filename} Offset: {formatted_offset}")

    cleanup_temp(temp_dir)

    return video_offsets
