import os
import re


def extract_guest_name(file_paths: list[str]) -> str:
    """Extract guest name from 'mix' filename among the given file paths.

    Expected patterns: "Prefix - Gastname mix.wav", "Prefix - Gastname (mix).wav"
    """
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
