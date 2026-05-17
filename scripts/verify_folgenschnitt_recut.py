#!/usr/bin/env python3
"""Verifikation: Hartmut-Rosa-Folge mit den NEUEN Stufe-2-Zahlen
neu durchrechnen, OHNE die schwere Audio-Analyse erneut zu fahren.

Nutzt die gecachte `speaker_activity.csv` der echten Folge als Eingabe,
fährt die Folgenschnitt-Pipeline zweimal über IDENTISCHE Eingabe — einmal
mit den ALTEN, einmal mit den NEUEN v1-Zahlen — und vergleicht die
Block-Längen-Statistik. Der OLD-Lauf validiert sich selbst gegen die
bereits existierende `Folgenschnitt - Hartmut Rosa.xml` (325 Clips,
Median 16.4s) — stimmt das nicht, ist die Mic→Person-Zuordnung falsch.

Reine Verifikation, KEINE App-Logik.
"""

import csv
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.folgenschnitt_models import (  # noqa: E402
    ActivityFrame,
    CameraAssignment,
    MicAssignment,
    SHOT_CLOSE,
    SHOT_WIDE,
)
from core.folgenschnitt_decisions import (  # noqa: E402
    build_edit_decisions,
    build_speaker_turns,
)
from core.folgenschnitt_loosening import (  # noqa: E402
    LooseningParams,
    LOOSENING_DEFAULTS,
    apply_time_logic_loosening,
    build_pause_ranges,
    build_stage1_base_camera_assignments,
)

OLD_PARAMS = LooseningParams(
    min_block_to_loosen_ms=120_000,
    first_block_ms=110_000,
    target_block_ms=90_000,
    densify_factor=0.85,
    min_block_ms=50_000,
    totale_interval_ms=240_000,
    totale_block_ms=25_000,
    snap_window_ms=15_000,
)


def load_activity(csv_path):
    """speaker_activity.csv -> [ActivityFrame]. The exporter writes
    'unknown' for a None speaker; map it back to None or pause detection
    silently breaks."""
    frames = []
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        fns = reader.fieldnames
        keys = [c[:-3] for c in fns
                if c.endswith("_db") and not c.endswith("_noise_floor_db")
                and f"{c[:-3]}_noise_floor_db" in fns]
        for row in reader:
            def _spk(v):
                return None if v in ("", "unknown", "None") else v
            frames.append(ActivityFrame(
                start_ms=int(row["start_ms"]),
                end_ms=int(row["end_ms"]),
                levels_db={k: float(row[f"{k}_db"]) for k in keys
                           if row.get(f"{k}_db") not in (None, "")},
                noise_floor_db={k: float(row[f"{k}_noise_floor_db"])
                                for k in keys
                                if row.get(f"{k}_noise_floor_db")
                                not in (None, "")},
                dominance_db=float(row["dominance_db"] or 0.0),
                raw_speaker=_spk(row["raw_speaker"]),
                smoothed_speaker=_spk(row["smoothed_speaker"]),
                confidence=float(row["confidence"] or 0.0),
            ))
    return frames


def run_pipeline(frames, mic_assignments, camera_assignments, params):
    turns = build_speaker_turns(frames, mic_assignments)
    seq_end = max((f.end_ms for f in frames), default=0)
    base = build_stage1_base_camera_assignments(
        mic_assignments, camera_assignments)
    stage1 = build_edit_decisions(turns, base, sequence_end_ms=seq_end)
    decisions = apply_time_logic_loosening(
        stage1, camera_assignments,
        pause_ranges=build_pause_ranges(frames), params=params)
    return decisions


def stats(decisions):
    lens = sorted((d.end_ms - d.start_ms) / 1000 for d in decisions)
    n = len(lens)
    total_min = sum(lens) / 60 if lens else 0.0
    if n >= 2:
        q = statistics.quantiles(lens, n=4, method="inclusive")
        p25, p75 = q[0], q[2]
    else:
        p25 = p75 = lens[0] if lens else 0.0
    return {
        "n": n,
        "min": round(min(lens), 1) if lens else 0.0,
        "p25": round(p25, 1),
        "median": round(statistics.median(lens), 1) if lens else 0.0,
        "p75": round(p75, 1),
        "max": round(max(lens), 1) if lens else 0.0,
        "mean": round(statistics.mean(lens), 1) if lens else 0.0,
        "cuts_per_min": round(max(0, n - 1) / total_min, 2)
        if total_min else 0.0,
        "below_35s": sum(1 for x in lens if x < 35),
        "above_90s": sum(1 for x in lens if x > 90),
    }


def _line(tag, s):
    return (f"{tag:5} n={s['n']:>4}  min {s['min']:>5}  P25 {s['p25']:>5}  "
            f"Med {s['median']:>5}  P75 {s['p75']:>5}  max {s['max']:>6}  "
            f"Ø {s['mean']:>5}  Schnitte/Min {s['cuts_per_min']:>4}  "
            f"<35s:{s['below_35s']:>3}  >90s:{s['above_90s']:>3}")


def main():
    csv_path = (sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Downloads/Hartmut Rosa - PeakCut Export/speaker_activity.csv"))
    frames = load_activity(csv_path)
    print(f"Frames: {len(frames)}  Folgenlänge "
          f"{max(f.end_ms for f in frames)/60000:.1f} min")

    # Confirmed assignment: 2 mics = the two partners; Matze 1 cam (wide),
    # Hartmut Rosa 2 cams (wide+close). Which mic is whom is resolved by
    # self-validation against the existing 325-clip export.
    def build(matze_key_is_mic1):
        m, r = (("Matze", "Hartmut Rosa") if matze_key_is_mic1
                else ("Hartmut Rosa", "Matze"))
        mics = [MicAssignment(track_index=0, path="MIC1", person=m),
                MicAssignment(track_index=1, path="MIC2", person=r)]
        cams = [
            CameraAssignment("Cam04", SHOT_WIDE, "Matze"),
            CameraAssignment("Cam02", SHOT_WIDE, "Hartmut Rosa"),
            CameraAssignment("Cam01", SHOT_CLOSE, "Hartmut Rosa"),
        ]
        return mics, cams

    best = None
    for mic1_is_matze in (True, False):
        mics, cams = build(mic1_is_matze)
        old = stats(run_pipeline(frames, mics, cams, OLD_PARAMS))
        # baseline oracle: existing XML = 325 clips, median ~16.4s
        score = abs(old["n"] - 325) + abs(old["median"] - 16.4)
        if best is None or score < best[0]:
            best = (score, mic1_is_matze, mics, cams, old)
    _, mic1_is_matze, mics, cams, old = best
    new = stats(run_pipeline(frames, mics, cams, LOOSENING_DEFAULTS))

    who = "MIC1=Matze" if mic1_is_matze else "MIC1=Hartmut Rosa"
    print(f"Selbst-validierte Zuordnung: {who} "
          f"(OLD-Lauf trifft 325/16.4-Baseline am besten)\n")
    print(_line("OLD", old))
    print(_line("NEU", new))
    print(f"\nBaseline (vorhandene XML, OLD-Zahlen): 325 Clips, "
          f"Median 16.4s, P75 50.0s, max 118s, 1.95 Schn./Min")
    print(f"OLD-Lauf reproduziert: {old['n']} Clips, Median "
          f"{old['median']}s, P75 {old['p75']}s, max {old['max']}s "
          f"— {'PLAUSIBEL' if abs(old['n']-325)<=15 else 'ABWEICHUNG (prüfen!)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
