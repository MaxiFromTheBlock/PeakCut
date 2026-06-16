import os
import re

from . import import_classifier


def extract_guest_name(file_paths: list[str]) -> str:
    """Extract guest name from the 'mix' filename among the given file paths.

    Expected patterns: "Prefix - Gastname mix.wav", "Prefix - Gastname (mix).wav".

    #77 Task 6: Mix-Erkennung über den zentralen, token-bewussten
    import_classifier statt naivem 'mix'-Substring — so zählt 'mixer_recording.wav'
    nicht mehr fälschlich als Mix-Datei.
    """
    for f in file_paths:
        name = os.path.basename(f)
        if import_classifier.is_mix_track(name):
            base = os.path.splitext(name)[0]
            parts = base.split(" - ")
            if len(parts) > 1:
                guest = parts[1].split("(")[0].strip()
                guest = re.sub(r'\s*mix\s*$', '', guest, flags=re.IGNORECASE).strip()
                if guest:
                    return guest
    return "Unknown"
