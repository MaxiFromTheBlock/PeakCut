#!/usr/bin/env python3
"""Erzeugt eine in Premiere importierbare Hartmut-Rosa-Folgenschnitt-XML
mit den NEUEN v1-Zahlen, als A/B zur bereits von Alex akzeptierten alten
XML. KEINE Neu-Analyse: Pfade + Sync-Offsets werden aus der alten XML
übernommen (Offsets frame-genau, ≤1 Frame Abweichung — sub-Frame-Original
ist nirgends gespeichert).

Sicherheitsnetz: erzeugt zuerst die ALTE XML mit dem echten Exporter neu
und vergleicht clip-für-clip gegen die akzeptierte XML. Nur wenn jede
Abweichung ≤1 Frame ist, ist die Mechanik beweisbar treu und die Neu-XML
unterscheidet sich garantiert NUR durch die Zahlen.

Reine Verifikation/Artefakt-Erzeugung, KEINE App-Logik.
"""

import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import core.folgenschnitt_exporter as fx  # noqa: E402
from core.folgenschnitt_exporter import FolgenschnittXMLExporter  # noqa: E402
from core.folgenschnitt_models import (  # noqa: E402
    CameraAssignment, MicAssignment, SHOT_CLOSE, SHOT_WIDE)
from core.folgenschnitt_decisions import (  # noqa: E402
    build_edit_decisions, build_speaker_turns)
from core.folgenschnitt_loosening import (  # noqa: E402
    LOOSENING_DEFAULTS, apply_time_logic_loosening, build_pause_ranges,
    build_stage1_base_camera_assignments)
from utils import ms_to_timecode  # noqa: E402

# reuse the verified cached-CSV loader + OLD params + pipeline runner
_vfr_path = os.path.join(os.path.dirname(__file__),
                         "verify_folgenschnitt_recut.py")
import importlib.util  # noqa: E402
_s = importlib.util.spec_from_file_location("vfr", _vfr_path)
vfr = importlib.util.module_from_spec(_s)
_s.loader.exec_module(vfr)

EXPORT_OLD = os.path.expanduser(
    "~/Downloads/Hartmut Rosa - PeakCut Export/Folgenschnitt - Hartmut Rosa.xml")
CSV = os.path.expanduser(
    "~/Downloads/Hartmut Rosa - PeakCut Export/speaker_activity.csv")
OUT_DIR = os.path.expanduser("~/Downloads/Hartmut Rosa - PeakCut Export NEU")


class _Cfg:
    def get(self, k, d=None):
        return 25 if k == "fps" else d


class _Project:
    def __init__(self, videos, mics, export_dir, guest):
        self.videos = videos
        self.mic_tracks = mics
        self.export_dir = export_dir
        self.guest_name = guest


class _Status:
    def emit(self, *a, **k):
        pass


class _Session:
    def __init__(self, project, video_offsets, decisions):
        self.project = project
        self.config = _Cfg()
        self.video_offsets = video_offsets
        self.folgenschnitt_edit_decisions = decisions
        self.status_update = _Status()


def _read_old(path):
    root = ET.parse(path).getroot()
    seq = root.find("sequence")
    fps = int(seq.find("rate/timebase").text)
    paths, by_cam = {}, {}
    clips = seq.find("media/video/track").findall("clipitem")
    old_clips = []
    for c in clips:
        nm = c.findtext("name")
        sf, ef, inf, outf = (int(c.findtext(t))
                             for t in ("start", "end", "in", "out"))
        old_clips.append((nm, sf, ef, inf, outf))
        by_cam.setdefault(nm, []).append((sf, inf))
    for pu in seq.iter("pathurl"):
        p = urllib.parse.unquote(pu.text.replace("file://localhost", ""))
        paths[os.path.basename(p)] = p
    # best-fit integer-frame offset per camera (median of in-start),
    # keyed by the real filename WITH extension (exporter's lookup key)
    offs = {}
    for nm, lst in by_cam.items():
        diffs = sorted(s_in - s for s, s_in in lst)
        base = next((b for b in paths if os.path.splitext(b)[0] == nm), nm)
        offs[base] = diffs[len(diffs) // 2]
    return fps, paths, offs, old_clips


def _cam_path(paths, token):
    return next(p for b, p in paths.items() if token in b)


def _build(decisions, paths, offs, guest, export_dir):
    os.makedirs(export_dir, exist_ok=True)
    fps = 25
    voff = []
    for base, fr in offs.items():
        off_ms = int(round(fr * 1000 / fps))
        sign = "-" if off_ms < 0 else ""
        voff.append((base, sign + ms_to_timecode(abs(off_ms), fps)))
    vids = [_cam_path(paths, t) for t in ("Cam04", "Cam02", "Cam01")]
    mics = [_cam_path(paths, t) for t in ("MIC1", "MIC2")]
    sess = _Session(_Project(vids, mics, export_dir, guest), voff, decisions)
    return FolgenschnittXMLExporter().export(sess)


def _clips_of(xml_path):
    seq = ET.parse(xml_path).getroot().find("sequence")
    out = []
    for c in seq.find("media/video/track").findall("clipitem"):
        out.append(tuple(int(c.findtext(t))
                         for t in ("start", "end", "in", "out"))
                   + (c.findtext("name"),))
    return out


def main():
    frames = vfr.load_activity(CSV)
    fps, paths, offs, _ = _read_old(EXPORT_OLD)

    mics = [MicAssignment(0, "MIC1", "Matze"),
            MicAssignment(1, "MIC2", "Hartmut Rosa")]
    cams = [CameraAssignment(_cam_path(paths, "Cam04"), SHOT_WIDE, "Matze"),
            CameraAssignment(_cam_path(paths, "Cam02"), SHOT_WIDE,
                             "Hartmut Rosa"),
            CameraAssignment(_cam_path(paths, "Cam01"), SHOT_CLOSE,
                             "Hartmut Rosa")]

    def decisions(params):
        turns = build_speaker_turns(frames, mics)
        seq_end = max(f.end_ms for f in frames)
        base = build_stage1_base_camera_assignments(mics, cams)
        st1 = build_edit_decisions(turns, base, sequence_end_ms=seq_end)
        return apply_time_logic_loosening(
            st1, cams, pause_ranges=build_pause_ranges(frames),
            params=params)

    fx._probe_video_info = lambda *a, **k: (3840, 2160)
    fx._probe_audio_info = lambda *a, **k: (44100, 16, 1)

    # 1) faithfulness gate: regenerate OLD, compare to accepted XML
    tmp = os.path.join(OUT_DIR, "_GATE")
    _build(decisions(vfr.OLD_PARAMS), paths, offs, "Hartmut Rosa", tmp)
    regen = _clips_of(os.path.join(tmp, "Folgenschnitt - Hartmut Rosa.xml"))
    accepted = _clips_of(EXPORT_OLD)
    if len(regen) != len(accepted):
        print(f"GATE FAIL: {len(regen)} vs {len(accepted)} Clips")
        return 1
    max_dev = 0
    for (rs, re_, ri, ro, rn), (as_, ae, ai, ao, an) in zip(regen, accepted):
        if rn != an or rs != as_ or re_ != ae:
            print(f"GATE FAIL: Struktur weicht ab @clip {rn} vs {an}")
            return 1
        max_dev = max(max_dev, abs(ri - ai), abs(ro - ao))
    if max_dev > 1:
        print(f"GATE FAIL: Offset-Abweichung {max_dev} Frames (>1)")
        return 1
    print(f"GATE OK: ALT regeneriert == akzeptierte XML "
          f"(Struktur identisch, max {max_dev} Frame Sync-Abweichung, "
          f"{len(regen)} Clips)")

    # 2) the deliverable: NEW numbers
    new_dec = decisions(LOOSENING_DEFAULTS)
    out = _build(new_dec, paths, offs, "Hartmut Rosa", OUT_DIR)
    print(f"NEU geschrieben: {out}")
    print(f"  Clips: {len(_clips_of(out))} (ALT akzeptiert: {len(accepted)})")
    print("  Sync identisch zur akzeptierten XML (≤1 Frame); es "
          "unterscheiden sich NUR die Schnittpunkte (neue v1-Zahlen).")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
