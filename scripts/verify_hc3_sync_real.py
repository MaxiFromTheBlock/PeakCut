#!/usr/bin/env python3
"""HC-3-Realprüfung: das NEUE Fenster-Lesen darf an echtem Material
exakt dieselben Sync-Offsets liefern wie der ALTE Code.

Prüfstein: die von Alex akzeptierte Hartmut-Rosa-XML (mit ALTEM Code
erzeugt) — daraus die Offsets je Kamera, dann das NEUE sync_videos()
auf dem echten lokalen HR-Rohmaterial fahren (echte ffmpeg-Extraktion,
langes Mehrkamera-Material = das HC-3-Szenario) und vergleichen.
"""

import importlib.util
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.sync import sync_videos, format_offset  # noqa: E402

_b = os.path.join(os.path.dirname(__file__), "build_hr_recut_xml.py")
_s = importlib.util.spec_from_file_location("bhr", _b)
bhr = importlib.util.module_from_spec(_s)
_s.loader.exec_module(bhr)


def main():
    fps, paths, offs, _ = bhr._read_old(bhr.EXPORT_OLD)
    cams = [bhr._cam_path(paths, t) for t in ("Cam04", "Cam02", "Cam01")]
    reference = bhr._cam_path(paths, "Mix")
    for p in cams + [reference]:
        if not os.path.isfile(p):
            print(f"ABBRUCH: Rohmaterial fehlt: {p}")
            return 1

    # ALTE Offsets (aus akzeptierter XML, mediane in-start Frames -> TC)
    old_tc = {}
    for base, fr in offs.items():
        old_tc[base] = format_offset(fr / fps, fps)

    with tempfile.TemporaryDirectory() as td:
        print("Starte NEUES sync_videos() auf echtem HR-Material "
              "(ffmpeg-Extraktion, kann dauern)...")
        new = sync_videos(cams, reference, td, fps=fps,
                           status_fn=lambda m: print("  ", m))

    print("\nVergleich ALT (akzeptierte XML) vs NEU (HC-3 Fenster-Lesen):")
    ok = True
    for fname, new_tc in sorted(new):
        o = old_tc.get(fname, "?")
        match = (o == new_tc)
        ok = ok and match
        print(f"  {fname:55} ALT {o:>14}  NEU {new_tc:>14}  "
              f"{'OK' if match else 'ABWEICHUNG'}")
    if not new:
        print("  (sync_videos lieferte nichts zurück)")
        ok = False
    print(f"\n{'PASS — Offsets bit-identisch' if ok else 'FAIL — Offsets weichen ab, NICHT mergen'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
