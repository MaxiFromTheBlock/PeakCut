from status import update
import os
import shutil
import soundfile as sf
import numpy as np
from scipy.signal import correlate
from moviepy.editor import VideoFileClip


def cleanup_temp():
    """Löscht alle Dateien im temp-Ordner."""
    temp_folder = os.path.join(os.getcwd(), 'temp')
    if os.path.exists(temp_folder):
        for f in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, f)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                update(f"⚠️ Could not delete {f}: {e}")

def extract_audio_from_video(video_path, output_path):
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(output_path, codec='pcm_s16le')

def load_audio_as_array(path):
    data, samplerate = sf.read(path)
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)  # Stereo → Mono
    return data, samplerate

def calculate_offset(reference, target):
    corr = correlate(target, reference, mode='full')
    lag = np.argmax(corr) - len(reference) + 1
    return lag

def format_offset(offset_seconds, fps=25):
    total_frames = int(offset_seconds * fps)
    sign = "-" if total_frames < 0 else ""
    total_frames = abs(total_frames)

    hours = total_frames // (3600 * fps)
    minutes = (total_frames % (3600 * fps)) // (60 * fps)
    seconds = (total_frames % (60 * fps)) // fps
    frames = total_frames % fps

    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

def run_sync():
    update("✅ [SYNC] Starting sync...")

    material_folder = os.path.join(os.getcwd(), 'material')
    export_folder = os.path.join(os.getcwd(), 'export')
    temp_folder = os.path.join(os.getcwd(), 'temp')

    # Cleanup temp folder before starting
    cleanup_temp()

    os.makedirs(temp_folder, exist_ok=True)
    os.makedirs(export_folder, exist_ok=True)

    video_files = [f for f in os.listdir(material_folder) if f.lower().endswith(('.mp4', '.mov'))]
    audio_files = [f for f in os.listdir(material_folder) if f.lower().endswith(('.wav', '.mp3'))]

    update(f"Found videos: {video_files}")
    update(f"Found audio files: {audio_files}")

    if not video_files or not audio_files:
        update("❌ Videos or audio files missing.")
        return

    reference_file = [f for f in audio_files if 'mix' in f.lower()]
    if not reference_file:
        update("❌ No reference audio file with 'mix' in name found.")
        return

    reference_path = os.path.join(material_folder, reference_file[0])
    reference_data, ref_sr = load_audio_as_array(reference_path)

    results = []

    for video in video_files:
        video_path = os.path.join(material_folder, video)
        temp_audio_path = os.path.join(temp_folder, f"{os.path.splitext(video)[0]}_audio.wav")

        update(f"🎬 Extracting audio from {video}...")
        extract_audio_from_video(video_path, temp_audio_path)

        target_data, target_sr = load_audio_as_array(temp_audio_path)

        if target_sr != ref_sr:
            update(f"⚠ Sample rates differ ({target_sr} vs {ref_sr}), skipping {video}.")
            continue

        update(f"🔍 Calculating offset for {video}...")
        offset_samples = calculate_offset(reference_data, target_data)
        offset_seconds = offset_samples / ref_sr

        formatted_offset = format_offset(offset_seconds)
        results.append((video, formatted_offset))
        update(f"✅ {video} Offset: {formatted_offset}")

    output_file = os.path.join(export_folder, 'video_offsets.txt')
    with open(output_file, 'w') as f:
        for video, offset in results:
            f.write(f"{video}: {offset}\n")

    # Cleanup temp files after sync
    cleanup_temp()

    update(f"📄 Offsets saved to {output_file}")
