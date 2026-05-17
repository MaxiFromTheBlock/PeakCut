"""
LUT Processor - Loads and applies .cube LUT files to images
Correctly handles the .cube file format where R varies fastest
"""
import os
import shutil
from dataclasses import dataclass

import numpy as np
from pathlib import Path


class LUTProcessor:
    """Handles loading and applying .cube LUT files."""

    def __init__(self):
        self.lut_data = None
        self.lut_size = 0
        self.lut_path = None
        self.domain_min = np.array([0.0, 0.0, 0.0])
        self.domain_max = np.array([1.0, 1.0, 1.0])
        self._lookup_table = None  # Pre-computed 256³ table for fast apply
        self._flat_lookup = None   # Flattened view for 1D indexing

    def load_cube(self, filepath: str) -> bool:
        """
        Load a .cube LUT file.

        Args:
            filepath: Path to the .cube file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix.lower() != '.cube':
                return False

            with open(filepath, 'r') as f:
                lines = f.readlines()

            lut_size = 0
            data_lines = []
            domain_min = [0.0, 0.0, 0.0]
            domain_max = [1.0, 1.0, 1.0]

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if line.startswith('LUT_3D_SIZE'):
                    lut_size = int(line.split()[-1])
                elif line.startswith('DOMAIN_MIN'):
                    parts = line.split()
                    if len(parts) >= 4:
                        domain_min = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif line.startswith('DOMAIN_MAX'):
                    parts = line.split()
                    if len(parts) >= 4:
                        domain_max = [float(parts[1]), float(parts[2]), float(parts[3])]
                elif line.startswith('TITLE') or line.startswith('LUT_1D_SIZE'):
                    continue
                else:
                    values = line.split()
                    if len(values) >= 3:
                        try:
                            rgb = [float(values[0]), float(values[1]), float(values[2])]
                            data_lines.append(rgb)
                        except ValueError:
                            continue

            if lut_size == 0 or len(data_lines) != lut_size ** 3:
                print(f"LUT size mismatch: expected {lut_size**3}, got {len(data_lines)}")
                return False

            self.lut_size = lut_size
            self.domain_min = np.array(domain_min, dtype=np.float32)
            self.domain_max = np.array(domain_max, dtype=np.float32)

            # .cube format stores data with R changing fastest, then G, then B
            # So the order is: for each B, for each G, for each R
            # We reshape to [B, G, R, 3] for natural indexing
            self.lut_data = np.array(data_lines, dtype=np.float32).reshape(
                (lut_size, lut_size, lut_size, 3)
            )
            self.lut_path = filepath
            self._build_lookup_table()
            return True

        except Exception as e:
            print(f"Error loading LUT: {e}")
            return False

    def apply_to_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply the loaded LUT to an image using trilinear interpolation.

        Args:
            image: Input image as numpy array (RGB, 0-255)

        Returns:
            Image with LUT applied
        """
        if self.lut_data is None:
            return image

        # Normalize to 0-1 and apply domain scaling
        img_float = image.astype(np.float32) / 255.0

        # Map from domain_min-domain_max to 0-1
        # Most LUTs use 0-1 domain, but some use different ranges
        img_normalized = (img_float - self.domain_min) / (self.domain_max - self.domain_min)
        img_normalized = np.clip(img_normalized, 0.0, 1.0)

        # Scale to LUT indices
        scale = self.lut_size - 1
        r = img_normalized[:, :, 0] * scale
        g = img_normalized[:, :, 1] * scale
        b = img_normalized[:, :, 2] * scale

        # Get integer indices for trilinear interpolation
        r0 = np.floor(r).astype(int)
        g0 = np.floor(g).astype(int)
        b0 = np.floor(b).astype(int)

        # Clamp to valid range
        r0 = np.clip(r0, 0, self.lut_size - 2)
        g0 = np.clip(g0, 0, self.lut_size - 2)
        b0 = np.clip(b0, 0, self.lut_size - 2)

        r1 = r0 + 1
        g1 = g0 + 1
        b1 = b0 + 1

        # Fractional parts
        rf = r - r0
        gf = g - g0
        bf = b - b0

        # Ensure fractions are in [0, 1]
        rf = np.clip(rf, 0.0, 1.0)
        gf = np.clip(gf, 0.0, 1.0)
        bf = np.clip(bf, 0.0, 1.0)

        # LUT is stored as [B, G, R, output_RGB]
        # Get the 8 corner values for trilinear interpolation
        c000 = self.lut_data[b0, g0, r0]  # (b0, g0, r0)
        c001 = self.lut_data[b0, g0, r1]  # (b0, g0, r1)
        c010 = self.lut_data[b0, g1, r0]  # (b0, g1, r0)
        c011 = self.lut_data[b0, g1, r1]  # (b0, g1, r1)
        c100 = self.lut_data[b1, g0, r0]  # (b1, g0, r0)
        c101 = self.lut_data[b1, g0, r1]  # (b1, g0, r1)
        c110 = self.lut_data[b1, g1, r0]  # (b1, g1, r0)
        c111 = self.lut_data[b1, g1, r1]  # (b1, g1, r1)

        # Add dimension for broadcasting
        rf = rf[:, :, np.newaxis]
        gf = gf[:, :, np.newaxis]
        bf = bf[:, :, np.newaxis]

        # Trilinear interpolation
        # First interpolate along R
        c00 = c000 + (c001 - c000) * rf
        c01 = c010 + (c011 - c010) * rf
        c10 = c100 + (c101 - c100) * rf
        c11 = c110 + (c111 - c110) * rf

        # Then interpolate along G
        c0 = c00 + (c01 - c00) * gf
        c1 = c10 + (c11 - c10) * gf

        # Finally interpolate along B
        result = c0 + (c1 - c0) * bf

        # Clamp and convert back to 0-255
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)

        return result

    def _build_lookup_table(self):
        """Pre-compute 256³ RGB lookup table for instant LUT application.

        Builds a (256, 256, 256, 3) uint8 array where table[R, G, B] = output RGB.
        Takes ~200ms once, then apply_fast() is a simple array lookup.
        """
        if self.lut_data is None:
            self._lookup_table = None
            return

        table = np.empty((256, 256, 256, 3), dtype=np.uint8)

        for b_val in range(256):
            # Test image: R varies along rows (axis 0), G along cols (axis 1)
            img = np.empty((256, 256, 3), dtype=np.uint8)
            img[:, :, 0] = np.arange(256)[:, np.newaxis]  # R
            img[:, :, 1] = np.arange(256)[np.newaxis, :]  # G
            img[:, :, 2] = b_val  # B constant
            table[:, :, b_val] = self.apply_to_image(img)

        self._lookup_table = table
        self._flat_lookup = table.reshape(-1, 3)  # View for fast 1D indexing

    def apply_fast(self, image: np.ndarray) -> np.ndarray:
        """Apply LUT using pre-computed lookup table. Near-instant.

        Falls back to trilinear interpolation if table not built.
        """
        if self._flat_lookup is None:
            return self.apply_to_image(image)
        h, w = image.shape[:2]
        idx = (image[:, :, 0].astype(np.int32) * 65536
               + image[:, :, 1].astype(np.int32) * 256
               + image[:, :, 2])
        return self._flat_lookup[idx.ravel()].reshape(h, w, 3)

    def is_loaded(self) -> bool:
        """Check if a LUT is currently loaded."""
        return self.lut_data is not None


@dataclass(frozen=True)
class LutAddResult:
    ok: bool
    reason: str  # added | overwritten | not_found | not_cube | invalid | exists
    filename: str | None = None


def add_lut_to_library(src_path: str, luts_dir: str,
                        overwrite: bool = False) -> LutAddResult:
    """Validate a .cube file and copy it into the LUT library.

    Validation uses the real parser (LUTProcessor.load_cube) so a broken
    LUT never pollutes the library. On a name collision the caller must
    opt in via overwrite=True (so the UI can ask first).
    """
    if not os.path.isfile(src_path):
        return LutAddResult(False, "not_found")
    if os.path.splitext(src_path)[1].lower() != ".cube":
        return LutAddResult(False, "not_cube")
    if not LUTProcessor().load_cube(src_path):
        return LutAddResult(False, "invalid")

    filename = os.path.basename(src_path)
    dest = os.path.join(luts_dir, filename)

    if os.path.abspath(src_path) == os.path.abspath(dest):
        return LutAddResult(True, "added", filename)  # already the library file
    if os.path.exists(dest) and not overwrite:
        return LutAddResult(False, "exists", filename)

    os.makedirs(luts_dir, exist_ok=True)
    existed = os.path.exists(dest)
    shutil.copy2(src_path, dest)
    return LutAddResult(True, "overwritten" if existed else "added", filename)
