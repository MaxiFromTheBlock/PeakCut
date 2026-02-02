"""
LUT Processor - Loads and applies .cube LUT files to images
Correctly handles the .cube file format where R varies fastest
"""
import numpy as np
from PIL import Image
from pathlib import Path


class LUTProcessor:
    """Handles loading and applying .cube LUT files."""

    def __init__(self):
        self.lut_data = None
        self.lut_size = 0
        self.lut_path = None
        self.domain_min = np.array([0.0, 0.0, 0.0])
        self.domain_max = np.array([1.0, 1.0, 1.0])

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

    def apply_to_pil_image(self, image: Image.Image) -> Image.Image:
        """
        Apply the loaded LUT to a PIL Image.

        Args:
            image: Input PIL Image

        Returns:
            PIL Image with LUT applied
        """
        if self.lut_data is None:
            return image

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Apply LUT
        img_array = np.array(image)
        result_array = self.apply_to_image(img_array)

        return Image.fromarray(result_array)

    def is_loaded(self) -> bool:
        """Check if a LUT is currently loaded."""
        return self.lut_data is not None

    def get_lut_name(self) -> str:
        """Get the name of the loaded LUT file."""
        if self.lut_path:
            return Path(self.lut_path).stem
        return ""

    def clear(self):
        """Clear the loaded LUT."""
        self.lut_data = None
        self.lut_size = 0
        self.lut_path = None
        self.domain_min = np.array([0.0, 0.0, 0.0])
        self.domain_max = np.array([1.0, 1.0, 1.0])
