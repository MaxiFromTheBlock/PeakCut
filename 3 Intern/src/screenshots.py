# screenshots.py - Extract screenshots from videos around peak times

import os
import numpy as np
from PIL import Image
from moviepy.editor import VideoFileClip
import random
from status import update
from utils import MATERIAL_DIR, EXPORT_DIR

# Path to the LUT file
LUT_PATH = "/Applications/Adobe Premiere Pro 2025/Adobe Premiere Pro 2025.app/Contents/Lumetri/LUTs/Creative/Kodak 5205 Fuji 3510 (by Adobe).cube"


def parse_cube_lut(filepath):
    """Parse a .cube LUT file and return the 3D LUT array."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    lut_size = None
    lut_data = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('TITLE'):
            continue
        if line.startswith('LUT_3D_SIZE'):
            lut_size = int(line.split()[-1])
            continue
        if line.startswith('DOMAIN_MIN') or line.startswith('DOMAIN_MAX'):
            continue

        # Parse RGB values
        try:
            r, g, b = map(float, line.split())
            lut_data.append([r, g, b])
        except:
            continue

    if lut_size and lut_data:
        lut_array = np.array(lut_data).reshape((lut_size, lut_size, lut_size, 3))
        return lut_array, lut_size
    return None, None


def apply_lut(image, lut_array, lut_size):
    """Apply 3D LUT to an image using trilinear interpolation."""
    img_array = np.array(image).astype(np.float32) / 255.0

    # Scale to LUT indices
    indices = img_array * (lut_size - 1)

    # Get integer indices and fractions for interpolation
    idx_low = np.floor(indices).astype(np.int32)
    idx_high = np.ceil(indices).astype(np.int32)
    idx_high = np.clip(idx_high, 0, lut_size - 1)
    frac = indices - idx_low

    # Simple nearest-neighbor for speed (trilinear is complex)
    r_idx = np.clip(np.round(indices[:,:,0]).astype(int), 0, lut_size-1)
    g_idx = np.clip(np.round(indices[:,:,1]).astype(int), 0, lut_size-1)
    b_idx = np.clip(np.round(indices[:,:,2]).astype(int), 0, lut_size-1)

    result = lut_array[r_idx, g_idx, b_idx]
    result = np.clip(result * 255, 0, 255).astype(np.uint8)

    return Image.fromarray(result)


def to_monochrome(image):
    """Convert image to monochrome (grayscale) but keep as RGB."""
    gray = image.convert('L')
    return gray.convert('RGB')


def extract_screenshots(num_screenshots=100):
    """Extract random screenshots from videos."""
    update("📸 [SCREENSHOTS] Starting extraction...")

    # Find video files
    video_files = [f for f in os.listdir(MATERIAL_DIR) if f.lower().endswith(('.mp4', '.mov'))]
    if not video_files:
        update("❌ No video files found in Material folder.")
        return

    # Create screenshots folder
    screenshots_dir = os.path.join(EXPORT_DIR, "Screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    # Load LUT
    lut_array, lut_size = None, None
    if os.path.exists(LUT_PATH):
        update("🎨 Loading LUT...")
        lut_array, lut_size = parse_cube_lut(LUT_PATH)
        if lut_array is not None:
            update("✅ LUT loaded successfully")
        else:
            update("⚠️ Could not parse LUT, using original colors")
    else:
        update("⚠️ LUT file not found, using original colors")

    for video_idx, video_file in enumerate(video_files, 1):
        video_path = os.path.join(MATERIAL_DIR, video_file)
        camera_name = f"Kamera {video_idx}"

        # Create subfolder for this camera
        camera_dir = os.path.join(screenshots_dir, camera_name)
        os.makedirs(camera_dir, exist_ok=True)

        update(f"🎬 Processing {video_file} as {camera_name}...")

        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration

            # Log video resolution
            update(f"   Resolution: {clip.w}x{clip.h}")

            # Generate random timestamps across the video
            # Avoid first and last 5 seconds (usually intro/outro)
            margin = 5
            if duration > margin * 2:
                timestamps = sorted(random.uniform(margin, duration - margin) for _ in range(num_screenshots))
            else:
                timestamps = sorted(random.uniform(0, duration) for _ in range(num_screenshots))

            for image_counter, time in enumerate(timestamps, 1):
                # Extract frame at full resolution
                frame = clip.get_frame(time)
                image = Image.fromarray(frame)

                # Apply LUT if available
                if lut_array is not None:
                    image = apply_lut(image, lut_array, lut_size)

                # Convert to monochrome
                image = to_monochrome(image)

                # Save as PNG for best quality
                filename = f"{camera_name}_Bild {image_counter}.png"
                filepath = os.path.join(camera_dir, filename)
                image.save(filepath)

            clip.close()
            update(f"✅ {camera_name}: {num_screenshots} screenshots saved")

        except Exception as e:
            update(f"❌ Error processing {video_file}: {e}")

    update(f"📸 Screenshots saved to: {screenshots_dir}")


if __name__ == "__main__":
    extract_screenshots()
